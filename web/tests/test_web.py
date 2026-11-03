"""Tests de la web: repositorios, cálculos, formularios y rutas."""
from datetime import date

import pytest

from app import create_app, euros, formularios, notion, resumen
from app.esquema import ENTIDADES
from app.repositorio import RepoMemoria, siguiente_pago, sumar_meses


# ---------- utilidades ----------

def test_euros_formato_espanol():
    assert euros(1234.5) == "1.234,50 €"
    assert euros(-32.5) == "−32,50 €"
    assert euros(10, signo=True) == "+10,00 €"


def test_sumar_meses_ajusta_fin_de_mes():
    assert sumar_meses(date(2026, 1, 31), 1) == date(2026, 2, 28)
    assert sumar_meses(date(2026, 11, 15), 2) == date(2027, 1, 15)


def test_siguiente_pago():
    hoy = date(2026, 11, 2)
    assert siguiente_pago("2026-01-05", "Mensual", hoy) == date(2026, 11, 5)
    assert siguiente_pago("2026-01-01", "Mensual", hoy) == date(2026, 12, 1)
    assert siguiente_pago("2025-03-20", "Anual", hoy) == date(2027, 3, 20)
    assert siguiente_pago("2026-11-02", "Mensual", hoy) == hoy


# ---------- repositorio en memoria: replica las fórmulas de Notion ----------

def datos_base():
    return {
        "cuentas": [
            {"id": "c1", "emoji": "", "Nombre": "Débito", "Saldo inicial": 100.0, "Activa": True},
            {"id": "c2", "emoji": "", "Nombre": "Efectivo", "Saldo inicial": 0.0, "Activa": True},
        ],
        "categorias": [
            {"id": "k1", "emoji": "🍔", "Nombre": "Comida", "Tipo": "Gasto", "Presupuesto mensual": 100},
            {"id": "k2", "emoji": "🎮", "Nombre": "Ocio", "Tipo": "Gasto", "Presupuesto mensual": 50},
            {"id": "k3", "emoji": "👕", "Nombre": "Ropa", "Tipo": "Gasto", "Presupuesto mensual": 80},
            {"id": "k9", "emoji": "💼", "Nombre": "Nómina", "Tipo": "Ingreso"},
        ],
        "suscripciones": [],
        "deudas": [
            {"id": "d1", "emoji": "", "Nombre": "Coche", "Total deuda": 300.0, "Cuota": 100.0, "Nº cuotas": 3,
             "Primera cuota": "2026-09-10"},
        ],
        "movimientos": [],
    }


def mov(concepto, importe, tipo, fecha="2026-10-05T12:00:00", cat=None, cuenta="c1", **extra):
    m = {"id": concepto, "emoji": "", "Concepto": concepto, "Importe": importe, "Tipo": tipo, "Fecha": fecha,
         "Cuenta": [cuenta], "Cuenta destino": [], "Categoría": [cat] if cat else [], "Suscripción": [], "Deuda": []}
    m.update(extra)
    return m


def test_saldo_con_gastos_ingresos_y_transferencias():
    d = datos_base()
    d["movimientos"] = [
        mov("Sueldo", 50, "Ingreso"),
        mov("Cena", 30, "Gasto", cat="k1"),
        mov("Cajero", 20, "Transferencia", **{"Cuenta destino": ["c2"]}),
    ]
    saldos = {c["Nombre"]: c["Saldo"] for c in RepoMemoria(d).listar("cuentas")}
    assert saldos == {"Débito": 100.0, "Efectivo": 20.0}   # 100 + 50 − 30 − 20


def test_deuda_cuenta_pagos_y_siguiente_cuota():
    d = datos_base()
    d["movimientos"] = [mov("Cuota", 100, "Gasto", Deuda=["d1"])]
    deuda = RepoMemoria(d).listar("deudas")[0]
    assert deuda["Total pagado"] == 100 and deuda["Nº pagos"] == 1 and deuda["Pendiente"] == 200
    assert deuda["Siguiente pago"] == "2026-10-10"


def test_crear_actualizar_y_archivar():
    repo = RepoMemoria(datos_base())
    nuevo = repo.crear("movimientos", {"Concepto": "Pizza", "Importe": 10.0, "Tipo": "Gasto",
                                       "Fecha": "2026-10-01T20:00", "Cuenta": "c1"})
    assert nuevo["Cuenta"] == ["c1"]                         # la relación se guarda como lista
    repo.actualizar("movimientos", nuevo["id"], {"Importe": 12.0})
    assert repo.obtener("movimientos", nuevo["id"])["Importe"] == 12.0
    repo.archivar("movimientos", nuevo["id"])
    assert repo.movimientos() == []


def test_movimientos_por_rango_hasta_exclusivo():
    d = datos_base()
    d["movimientos"] = [mov("a", 1, "Gasto", "2026-09-30T23:00:00"), mov("b", 1, "Gasto", "2026-10-01T00:00:00"),
                        mov("c", 1, "Gasto", "2026-11-01T00:00:00")]
    repo = RepoMemoria(d)
    assert [m["id"] for m in repo.movimientos(date(2026, 10, 1), date(2026, 11, 1))] == ["b"]


# ---------- traducción a Notion ----------

def test_a_propiedades_de_notion():
    props = notion.a_propiedades(ENTIDADES["movimientos"], {
        "Concepto": "Pizza", "Importe": 12.5, "Tipo": "Gasto", "Fecha": "2026-11-02T20:00+01:00",
        "Cuenta": ["c1"], "Categoría": [],
    })
    assert props["Concepto"] == {"title": [{"text": {"content": "Pizza"}}]}
    assert props["Importe"] == {"number": 12.5}
    assert props["Tipo"] == {"select": {"name": "Gasto"}}
    assert props["Fecha"] == {"date": {"start": "2026-11-02T20:00+01:00"}}
    assert props["Cuenta"] == {"relation": [{"id": "c1"}]}
    assert props["Categoría"] == {"relation": []}


def test_aplanar_propiedades():
    pagina = {"id": "c1", "icon": {"type": "emoji", "emoji": "💳"}, "properties": {
        "Nombre": {"type": "title", "title": [{"plain_text": "Débito"}]},
        "Saldo": {"type": "formula", "formula": {"type": "number", "number": -32.5}},
        "Siguiente pago": {"type": "formula", "formula": {"type": "date", "date": {"start": "2026-11-21"}}},
        "Σ Recibido": {"type": "rollup", "rollup": {"type": "number", "number": 20}},
        "Movimientos": {"type": "relation", "relation": [{"id": "m1"}]},
    }}
    assert notion.aplanar(pagina) == {"id": "c1", "emoji": "💳", "Nombre": "Débito", "Saldo": -32.5,
                                      "Siguiente pago": "2026-11-21", "Σ Recibido": 20, "Movimientos": ["m1"]}


class Respuesta:
    def __init__(self, datos, status=200):
        self.datos, self.status_code, self.text = datos, status, str(datos)

    def json(self):
        return self.datos


class SesionFalsa:
    """Imita requests.Session y apunta cada petición."""
    def __init__(self, paginas=None, status=200):
        self.headers, self.peticiones, self.paginas, self.status = {}, [], paginas or [], status

    def request(self, metodo, url, json=None, timeout=None):
        self.peticiones.append((metodo, url, json))
        if url.endswith("/query"):
            i = int((json or {}).get("start_cursor") or 0)
            return Respuesta({"results": self.paginas[i:i + 1], "has_more": i + 1 < len(self.paginas),
                              "next_cursor": str(i + 1)}, self.status)
        return Respuesta({"id": "nuevo", "properties": {}}, self.status)


def pagina(id_):
    return {"id": id_, "properties": {"Nombre": {"type": "title", "title": [{"plain_text": id_}]}}}


def test_notion_paginacion_cache_y_filtro_de_fechas():
    sesion = SesionFalsa([pagina("a"), pagina("b")])
    repo = notion.RepoNotion("ntn_falso", sesion=sesion)
    assert [c["Nombre"] for c in repo.listar("cuentas")] == ["a", "b"]
    assert sesion.headers["Authorization"] == "Bearer ntn_falso"
    n = len(sesion.peticiones)
    repo.listar("cuentas")
    assert len(sesion.peticiones) == n                       # segunda vez, de la caché
    repo.movimientos(date(2026, 12, 1), date(2027, 1, 1))
    filtro = sesion.peticiones[-1][2]["filter"]["and"]
    assert filtro == [{"property": "Fecha", "date": {"on_or_after": "2026-12-01"}},
                      {"property": "Fecha", "date": {"before": "2027-01-01"}}]


def test_notion_escribir_vacia_la_cache_y_archivar_usa_patch():
    sesion = SesionFalsa([pagina("a")])
    repo = notion.RepoNotion("t", sesion=sesion)
    repo.listar("categorias")
    repo.crear("categorias", {"Nombre": "Informática", "Tipo": "Gasto", "emoji": "🖥️"})
    metodo, url, body = sesion.peticiones[-1]
    assert metodo == "POST" and url.endswith("/pages")
    assert body["parent"] == {"database_id": notion.DB["categorias"]}
    assert body["icon"] == {"type": "emoji", "emoji": "🖥️"}
    repo.listar("categorias")
    assert sesion.peticiones[-1][1].endswith("/query")       # la caché se vació
    repo.archivar("categorias", "abc")
    assert sesion.peticiones[-1] == ("PATCH", f"{notion.API}/pages/abc", {"archived": True})


def test_notion_error():
    with pytest.raises(notion.ErrorNotion):
        notion.RepoNotion("t", sesion=SesionFalsa(status=401)).listar("cuentas")


# ---------- formularios ----------

def test_formulario_movimiento_convierte_tipos():
    datos, errores = formularios.leer(ENTIDADES["movimientos"], {
        "Concepto": " Pizza ", "Importe": "1.234,50", "Tipo": "Gasto", "Fecha": "2026-11-02T20:30",
        "Cuenta": "c1", "Categoría": "k1", "Cuenta destino": "c2"})
    assert not errores
    assert datos["Concepto"] == "Pizza" and datos["Importe"] == 1234.5
    assert datos["Fecha"] == "2026-11-02T20:30+01:00"
    assert datos["Cuenta destino"] == []                     # solo tiene sentido en transferencias


def test_formulario_errores():
    _, e = formularios.leer(ENTIDADES["movimientos"], {"Tipo": "Gasto", "Importe": "abc", "Fecha": "2026-11-02T20:30"})
    assert {"Concepto", "Importe", "Cuenta"} <= set(e)
    _, e = formularios.leer(ENTIDADES["movimientos"], {"Concepto": "x", "Tipo": "Transferencia", "Importe": "5",
                                                       "Fecha": "2026-11-02T20:30", "Cuenta": "c1", "Cuenta destino": "c1"})
    assert "Cuenta destino" in e
    _, e = formularios.leer(ENTIDADES["movimientos"], {"Concepto": "x", "Tipo": "Gasto", "Importe": "-5",
                                                       "Fecha": "2026-11-02T20:30", "Cuenta": "c1"})
    assert "Importe" in e


# ---------- resumen, filtros y agrupación ----------

def test_resumen_presupuesto_y_comparacion():
    d = datos_base()
    d["movimientos"] = [
        mov("Mucho", 120, "Gasto", cat="k1"), mov("Casi", 45, "Gasto", cat="k2"),
        mov("Septiembre", 20, "Gasto", "2026-09-15T12:00:00", cat="k1"),
        mov("Sueldo", 500, "Ingreso", cat="k9"),
    ]
    repo = RepoMemoria(d)
    datos = {k: repo.listar(k) for k in ("cuentas", "categorias", "suscripciones", "deudas")}
    datos["movimientos"] = repo.movimientos()
    r = resumen.construir(datos, "2026-10", hoy=date(2026, 10, 20))
    estados = {c["nombre"]: c["estado"] for c in r["categorias"]}
    assert estados == {"Comida": "pasado", "Ocio": "cerca", "Ropa": "bien"}
    comida = next(c for c in r["categorias"] if c["nombre"] == "Comida")
    assert comida["diferencia"] == 100                       # 120 este mes frente a 20 el anterior
    assert r["gastos"] == 165 and r["ingresos"] == 500
    assert [s["gastos"] for s in r["serie"][-2:]] == [20, 165]


def filas_ejemplo():
    cuentas = [{"id": "c1", "Nombre": "Débito"}, {"id": "c2", "Nombre": "Efectivo"}]
    cats = [{"id": "k1", "Nombre": "Comida", "emoji": "🍔"}, {"id": "k2", "Nombre": "Ocio", "emoji": "🎮"}]
    movs = [mov("Pizza", 10, "Gasto", "2026-10-05T12:00:00", cat="k1"),
            mov("Cine", 8, "Gasto", "2026-10-06T12:00:00", cat="k2", cuenta="c2"),
            mov("Kebab", 6, "Gasto", "2026-09-10T12:00:00", cat="k1", cuenta="c2"),
            mov("Cajero", 20, "Transferencia", "2026-10-07T12:00:00", **{"Cuenta destino": ["c2"]})]
    return resumen.enriquecer(movs, cuentas, cats)


def test_filtros():
    filas = filas_ejemplo()
    assert [f["concepto"] for f in resumen.filtrar(filas, categoria="k1")] == ["Pizza", "Kebab"]
    # la transferencia aparece en la cuenta de destino
    assert {f["concepto"] for f in resumen.filtrar(filas, cuenta="c2")} == {"Cine", "Kebab", "Cajero"}
    assert [f["concepto"] for f in resumen.filtrar(filas, texto="piz")] == ["Pizza"]
    assert [f["concepto"] for f in resumen.filtrar(filas, categoria="sin")] == ["Cajero"]


def test_agrupar_por_mes_y_por_categoria():
    filas = filas_ejemplo()
    por_mes = resumen.agrupar(filas, "mes")
    assert [g["titulo"] for g in por_mes] == ["Octubre de 2026", "Septiembre de 2026"]
    assert por_mes[0]["gastos"] == 18
    por_cat = resumen.agrupar(filas, "categoria")
    assert [g["titulo"] for g in por_cat] == ["🍔 Comida", "🎮 Ocio", "🔄 Transferencias"]
    assert por_cat[0]["gastos"] == 16


def test_rango_periodo():
    hoy = date(2026, 11, 2)
    assert resumen.rango_periodo("mes", hoy=hoy) == (date(2026, 11, 1), date(2026, 12, 1))
    assert resumen.rango_periodo("mes", hoy=hoy, mes="2026-02") == (date(2026, 2, 1), date(2026, 3, 1))
    assert resumen.rango_periodo("3m", hoy=hoy) == (date(2026, 9, 1), date(2026, 12, 1))
    assert resumen.rango_periodo("rango", "2026-10-01", "2026-10-31", hoy=hoy) == (date(2026, 10, 1), date(2026, 11, 1))
    assert resumen.rango_periodo("todo", hoy=hoy) == (None, None)


# ---------- rutas ----------

@pytest.fixture
def app():
    return create_app({"NOTION_TOKEN": "", "APP_PASSWORD": ""})


@pytest.fixture
def cliente(app):
    c = app.test_client()
    c.get("/")
    return c


def csrf(cliente):
    with cliente.session_transaction() as s:
        return s["csrf"]


@pytest.mark.parametrize("url", [
    "/", "/?mes=2026-09", "/movimientos", "/movimientos?periodo=todo&agrupar=categoria",
    "/movimientos?periodo=3m&agrupar=cuenta&tipo=Gasto&q=mer", "/movimientos?periodo=mes&mes=2026-10&agrupar=dia",
    "/movimientos?periodo=rango&desde=2026-09-01&hasta=2026-09-30", "/movimientos/nuevo",
    "/gestion/cuentas", "/gestion/categorias", "/gestion/suscripciones", "/gestion/deudas",
    "/gestion/deudas/nuevo", "/salud",
])
def test_paginas_responden(cliente, url):
    assert cliente.get(url).status_code == 200


@pytest.mark.parametrize("url", ["/?mes=2026-13", "/movimientos?periodo=nada", "/movimientos?agrupar=x",
                                 "/movimientos?periodo=mes&mes=<script>"])
def test_parametros_invalidos(cliente, url):
    assert cliente.get(url).status_code == 400


def test_entidad_desconocida_y_registro_inexistente(cliente):
    assert cliente.get("/gestion/usuarios").status_code == 404
    assert cliente.get("/movimientos/no-existe").status_code == 404


def test_crear_editar_y_eliminar_movimiento(app, cliente):
    t = csrf(cliente)
    saldo = lambda: next(c["Saldo"] for c in app.repo.listar("cuentas") if c["id"] == "c2")
    antes = saldo()
    r = cliente.post("/movimientos/nuevo", data={"csrf": t, "Tipo": "Gasto", "Concepto": "Pizza", "Importe": "12,50",
                                                 "Fecha": "2026-11-02T20:00", "Cuenta": "c2", "Categoría": "k1"})
    assert r.status_code == 302
    assert saldo() == pytest.approx(antes - 12.5)
    nuevo = next(m for m in app.repo.movimientos() if m["Concepto"] == "Pizza")

    r = cliente.post(f"/movimientos/{nuevo['id']}", data={"csrf": t, "Tipo": "Gasto", "Concepto": "Pizza",
                                                          "Importe": "20", "Fecha": "2026-11-02T20:00", "Cuenta": "c2"})
    assert r.status_code == 302 and saldo() == pytest.approx(antes - 20)

    assert cliente.post(f"/eliminar/movimientos/{nuevo['id']}", data={"csrf": t}).status_code == 302
    assert saldo() == pytest.approx(antes)


def test_formulario_con_errores_no_guarda(app, cliente):
    n = len(app.repo.movimientos())
    r = cliente.post("/movimientos/nuevo", data={"csrf": csrf(cliente), "Tipo": "Gasto", "Concepto": "",
                                                 "Importe": "", "Fecha": "", "Cuenta": ""})
    assert r.status_code == 422 and "obligatorio" in r.data.decode()
    assert len(app.repo.movimientos()) == n


def test_gestionar_categoria(app, cliente):
    t = csrf(cliente)
    cliente.post("/gestion/categorias/nuevo", data={"csrf": t, "Nombre": "Informática", "Tipo": "Gasto",
                                                    "Presupuesto mensual": "40", "emoji": "🖥️"})
    cat = next(c for c in app.repo.listar("categorias") if c["Nombre"] == "Informática")
    assert cat["emoji"] == "🖥️" and cat["Presupuesto mensual"] == 40
    assert "Informática" in cliente.get("/gestion/categorias").data.decode()


def test_csrf_obligatorio(app, cliente):
    n = len(app.repo.movimientos())
    r = cliente.post("/eliminar/movimientos/" + app.repo.movimientos()[0]["id"], data={})
    assert r.status_code == 400 and len(app.repo.movimientos()) == n


def test_redireccion_solo_interna(cliente):
    r = cliente.post("/gestion/categorias/nuevo", data={"csrf": csrf(cliente), "Nombre": "X", "Tipo": "Gasto",
                                                        "volver": "//evil.com"})
    assert r.headers["Location"] == "/gestion/categorias"


def test_exportar_csv(cliente):
    r = cliente.get("/movimientos?periodo=todo&tipo=Ingreso&formato=csv")
    assert r.mimetype == "text/csv"
    lineas = r.data.decode("utf-8-sig").strip().splitlines()
    assert lineas[0].startswith("Fecha;Concepto;Tipo;Importe")
    assert all(";Ingreso;" in l for l in lineas[1:])


def test_login_obligatorio_si_hay_contrasena():
    c = create_app({"NOTION_TOKEN": "", "APP_PASSWORD": "secreta"}).test_client()
    assert c.get("/").status_code == 302
    c.get("/login")
    t = csrf(c)
    assert c.post("/login", data={"csrf": t, "clave": "mal"}).status_code == 401
    assert c.post("/login?siguiente=//evil.com", data={"csrf": t, "clave": "secreta"}).headers["Location"] == "/"
    assert c.get("/").status_code == 200
    c.post("/salir", data={"csrf": t})
    assert c.get("/").status_code == 302


def test_misma_clave_de_sesion_en_todos_los_workers():
    a = create_app({"NOTION_TOKEN": "", "APP_PASSWORD": "secreta", "SECRET_KEY": ""})
    b = create_app({"NOTION_TOKEN": "", "APP_PASSWORD": "secreta", "SECRET_KEY": ""})
    assert a.config["SECRET_KEY"] == b.config["SECRET_KEY"]


def test_error_de_notion_muestra_ayuda(app):
    class RepoRoto:
        def listar(self, clave):
            raise notion.ErrorNotion("Notion respondió 401")
    app.repo = RepoRoto()
    r = app.test_client().get("/")
    assert r.status_code == 502 and "Conexiones" in r.data.decode()


def test_manifiesto_pwa(cliente):
    r = cliente.get("/manifest.webmanifest")
    assert r.mimetype == "application/manifest+json"
    m = r.get_json(force=True)
    assert m["display"] == "standalone" and m["start_url"] == "/"
    for icono in m["icons"]:
        assert cliente.get(icono["src"]).status_code == 200
    assert 'rel="manifest"' in cliente.get("/").data.decode()


def test_manifiesto_accesible_sin_login():
    c = create_app({"NOTION_TOKEN": "", "APP_PASSWORD": "secreta"}).test_client()
    assert c.get("/manifest.webmanifest").status_code == 200
