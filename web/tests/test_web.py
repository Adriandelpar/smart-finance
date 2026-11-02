"""Tests de la web: cálculos del resumen, cliente de Notion (con la red simulada) y rutas."""
from datetime import date

import pytest

from app import create_app, demo, euros, notion, resumen


# ---------- formato ----------

def test_euros_formato_espanol():
    assert euros(1234.5) == "1.234,50 €"
    assert euros(-32.5) == "−32,50 €"
    assert euros(0) == "0,00 €"


# ---------- resumen ----------

def datos_minimos(movimientos, mes="2026-10"):
    return {
        "cuentas": [
            {"id": "c1", "Nombre": "Débito", "Saldo": 100.0, "Activa": True},
            {"id": "c2", "Nombre": "Efectivo", "Saldo": 50.0, "Activa": True},
            {"id": "c3", "Nombre": "Vieja", "Saldo": 999.0, "Activa": False},
        ],
        "categorias": [
            {"id": "k1", "Nombre": "Comida", "Tipo": "Gasto", "Presupuesto mensual": 100},
            {"id": "k2", "Nombre": "Ocio", "Tipo": "Gasto", "Presupuesto mensual": 50},
            {"id": "k3", "Nombre": "Ropa", "Tipo": "Gasto", "Presupuesto mensual": 80},
        ],
        "movimientos": movimientos,
        "suscripciones": [
            {"id": "s1", "Nombre": "Netflix", "Importe": 12.0, "Frecuencia": "Mensual", "Activa": True,
             "Siguiente pago": "2026-10-20", "Días restantes": 5},
            {"id": "s2", "Nombre": "Dominio", "Importe": 12.0, "Frecuencia": "Anual", "Activa": True,
             "Siguiente pago": "2026-10-10", "Días restantes": 1},
        ],
        "deudas": [
            {"id": "d1", "Nombre": "Coche", "Total deuda": 1000.0, "Cuota": 100.0, "Nº cuotas": 10,
             "Total pagado": 300.0, "Pendiente": 700.0, "Nº pagos": 3, "Siguiente pago": "2026-10-15", "Días restantes": 3},
            {"id": "d2", "Nombre": "Pagada", "Total deuda": 50.0, "Cuota": 50.0, "Nº cuotas": 1,
             "Total pagado": 50.0, "Pendiente": 0.0, "Nº pagos": 1, "Siguiente pago": "2026-10-01"},
        ],
    }


def mov(concepto, importe, tipo, fecha="2026-10-05T12:00:00", cat=None, cuenta="c1", **extra):
    m = {"id": concepto, "Concepto": concepto, "Importe": importe, "Tipo": tipo, "Fecha": fecha,
         "Cuenta": [cuenta], "Categoría": [cat] if cat else []}
    m.update(extra)
    return m


def test_total_solo_cuentas_activas():
    r = resumen.construir(datos_minimos([]), "2026-10")
    assert r["total"] == 150.0
    assert [c["nombre"] for c in r["cuentas"]] == ["Débito", "Efectivo"]


def test_balance_del_mes_ignora_transferencias_y_otros_meses():
    r = resumen.construir(datos_minimos([
        mov("Sueldo", 500, "Ingreso"),
        mov("Cena", 30, "Gasto", cat="k1"),
        mov("Cajero", 40, "Transferencia", **{"Cuenta destino": ["c2"]}),
        mov("Septiembre", 999, "Gasto", fecha="2026-09-30T23:00:00", cat="k1"),
    ]), "2026-10")
    assert r["ingresos"] == 500
    assert r["gastos"] == 30
    assert r["neto"] == 470
    assert len(r["movimientos"]) == 3


def test_estados_del_presupuesto():
    r = resumen.construir(datos_minimos([
        mov("Mucho", 120, "Gasto", cat="k1"),   # 120 de 100 -> pasado
        mov("Casi", 45, "Gasto", cat="k2"),     # 45 de 50   -> cerca (>80 %)
    ]), "2026-10")
    estados = {c["nombre"]: c["estado"] for c in r["categorias"]}
    assert estados == {"Comida": "pasado", "Ocio": "cerca", "Ropa": "bien"}  # Ropa sale aunque no tenga gasto


def test_pagos_ordenados_y_deudas_pagadas_fuera():
    r = resumen.construir(datos_minimos([]), "2026-10")
    assert [p["nombre"] for p in r["pagos"]] == ["Dominio", "Coche", "Netflix"]
    assert r["coste_mensual_suscripciones"] == pytest.approx(12 + 12 / 12)


def test_navegacion_entre_meses():
    assert resumen.mes_desplazado("2026-01", -1) == "2025-12"
    assert resumen.mes_desplazado("2026-12", 1) == "2027-01"
    assert resumen.nombre_mes("2026-11") == "noviembre de 2026"


def test_demo_tiene_movimientos_este_mes():
    r = resumen.construir(demo.obtener())
    assert r["es_mes_actual"]
    assert r["movimientos"]


# ---------- cliente de Notion (sin red) ----------

class RespuestaFalsa:
    def __init__(self, datos, status=200):
        self.datos, self.status_code, self.text = datos, status, str(datos)

    def json(self):
        return self.datos


class SesionFalsa:
    """Imita requests.Session: devuelve páginas de Notion y apunta las peticiones."""
    def __init__(self, paginas_por_db, status=200):
        self.headers, self.peticiones = {}, []
        self.paginas, self.status = paginas_por_db, status

    def post(self, url, json, timeout):
        self.peticiones.append((url, json))
        db = url.split("/databases/")[1].split("/")[0]
        paginas = self.paginas.get(db, [])
        # simula paginación: de una en una
        i = int(json.get("start_cursor") or 0)
        return RespuestaFalsa({"results": paginas[i:i + 1], "has_more": i + 1 < len(paginas),
                               "next_cursor": str(i + 1)}, self.status)


def pagina_cuenta(id_, nombre, saldo):
    return {"id": id_, "icon": {"type": "emoji", "emoji": "💳"}, "properties": {
        "Nombre": {"type": "title", "title": [{"plain_text": nombre}]},
        "Saldo": {"type": "formula", "formula": {"type": "number", "number": saldo}},
        "Activa": {"type": "checkbox", "checkbox": True},
        "Movimientos": {"type": "relation", "relation": [{"id": "m1"}]},
        "Σ Recibido": {"type": "rollup", "rollup": {"type": "number", "number": 20}},
    }}


def test_aplanar_propiedades():
    plano = notion.aplanar(pagina_cuenta("c1", "Débito", -32.5))
    assert plano == {"id": "c1", "emoji": "💳", "Nombre": "Débito", "Saldo": -32.5, "Activa": True,
                     "Movimientos": ["m1"], "Σ Recibido": 20}


def test_cliente_sigue_la_paginacion_y_filtra_el_mes():
    sesion = SesionFalsa({notion.DB["cuentas"]: [pagina_cuenta("c1", "A", 1), pagina_cuenta("c2", "B", 2)]})
    datos = notion.Cliente("ntn_falso", sesion=sesion).obtener("2026-12")
    assert [c["Nombre"] for c in datos["cuentas"]] == ["A", "B"]
    assert sesion.headers["Authorization"] == "Bearer ntn_falso"
    filtro = next(j["filter"] for u, j in sesion.peticiones if notion.DB["movimientos"] in u)
    assert filtro["and"][0]["date"] == {"on_or_after": "2026-12-01"}
    assert filtro["and"][1]["date"] == {"before": "2027-01-01"}


def test_cliente_usa_cache():
    sesion = SesionFalsa({})
    c = notion.Cliente("t", sesion=sesion)
    c.obtener("2026-10")
    n = len(sesion.peticiones)
    c.obtener("2026-10")
    assert len(sesion.peticiones) == n
    c.obtener("2026-10", refrescar=True)
    assert len(sesion.peticiones) == 2 * n


def test_cliente_error_de_notion():
    with pytest.raises(notion.ErrorNotion):
        notion.Cliente("t", sesion=SesionFalsa({}, status=401)).obtener("2026-10")


# ---------- rutas ----------

@pytest.fixture
def cliente_demo():
    return create_app({"NOTION_TOKEN": "", "APP_PASSWORD": ""}).test_client()


def test_panel_demo(cliente_demo):
    r = cliente_demo.get("/")
    assert r.status_code == 200
    html = r.data.decode()
    assert "Tienes" in html and "Datos de ejemplo" in html


def test_mes_invalido(cliente_demo):
    assert cliente_demo.get("/?mes=2026-13").status_code == 400
    assert cliente_demo.get("/?mes=<script>").status_code == 400


def test_salud(cliente_demo):
    assert cliente_demo.get("/salud").json == {"estado": "ok", "demo": True}


def test_login_obligatorio_si_hay_contrasena():
    c = create_app({"NOTION_TOKEN": "", "APP_PASSWORD": "secreta"}).test_client()
    assert c.get("/").status_code == 302
    assert c.post("/login", data={"clave": "mal"}).status_code == 401
    assert c.post("/login?siguiente=//evil.com", data={"clave": "secreta"}).headers["Location"] == "/"
    assert c.get("/").status_code == 200
    c.post("/salir")
    assert c.get("/").status_code == 302


def test_error_de_notion_muestra_ayuda():
    app = create_app({"NOTION_TOKEN": "", "APP_PASSWORD": ""})

    def falla(mes, refrescar=False):
        raise notion.ErrorNotion("Notion respondió 401")
    app.obtener_datos = falla
    r = app.test_client().get("/")
    assert r.status_code == 502
    assert "Conexiones" in r.data.decode()


def test_misma_clave_de_sesion_en_todos_los_workers():
    # cada worker de gunicorn crea su propia app: la clave tiene que coincidir
    a = create_app({"NOTION_TOKEN": "", "APP_PASSWORD": "secreta", "SECRET_KEY": ""})
    b = create_app({"NOTION_TOKEN": "", "APP_PASSWORD": "secreta", "SECRET_KEY": ""})
    assert a.config["SECRET_KEY"] == b.config["SECRET_KEY"]
    c = create_app({"NOTION_TOKEN": "", "APP_PASSWORD": "otra", "SECRET_KEY": ""})
    assert c.config["SECRET_KEY"] != a.config["SECRET_KEY"]
