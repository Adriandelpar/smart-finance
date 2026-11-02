"""Cálculos de la web a partir de los registros del repositorio.

Son funciones puras: entran listas de diccionarios y salen diccionarios.
Así se prueban sin red y sin Flask.
"""
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from .repositorio import a_fecha, sumar_meses

ZONA = ZoneInfo("Europe/Madrid")

MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
         "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
MESES_CORTOS = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]


def _fecha_hora(iso):
    """ISO -> datetime en hora de Madrid, sin zona (el móvil guarda en UTC con 'Z')."""
    if not iso:
        return None
    d = datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
    return d.astimezone(ZONA).replace(tzinfo=None) if d.tzinfo else d


def _num(v):
    return float(v) if isinstance(v, (int, float)) else 0.0


def clave_mes(d):
    return d.strftime("%Y-%m")


def inicio_mes(mes):
    a, m = map(int, mes.split("-"))
    return date(a, m, 1)


def mes_desplazado(mes, delta):
    return clave_mes(sumar_meses(inicio_mes(mes), delta))


def nombre_mes(mes):
    d = inicio_mes(mes)
    return f"{MESES[d.month - 1]} de {d.year}"


def nombre_mes_corto(mes):
    d = inicio_mes(mes)
    return f"{MESES_CORTOS[d.month - 1]} {str(d.year)[2:]}"


def signo(tipo):
    return 1 if tipo == "Ingreso" else -1 if tipo == "Gasto" else 0


# ---------- movimientos "enriquecidos" para pintar ----------

def enriquecer(movs, cuentas, categorias):
    """Añade a cada movimiento los nombres de cuenta y categoría, y su signo."""
    cu = {c["id"]: c for c in cuentas}
    ca = {c["id"]: c for c in categorias}
    filas = []
    for m in movs:
        cat = ca.get((m.get("Categoría") or [None])[0]) or {}
        origen = cu.get((m.get("Cuenta") or [None])[0]) or {}
        destino = cu.get((m.get("Cuenta destino") or [None])[0]) or {}
        fecha = _fecha_hora(m.get("Fecha"))
        filas.append({
            "id": m["id"], "fecha": fecha, "mes": clave_mes(fecha) if fecha else None,
            "concepto": m.get("Concepto") or "", "tipo": m.get("Tipo"),
            "importe": _num(m.get("Importe")), "signo": signo(m.get("Tipo")),
            "categoria_id": cat.get("id"), "categoria": cat.get("Nombre"),
            "emoji": cat.get("emoji") or ("🔄" if m.get("Tipo") == "Transferencia" else ""),
            "cuenta_id": origen.get("id"), "cuenta": origen.get("Nombre"),
            "destino_id": destino.get("id"), "destino": destino.get("Nombre"),
            "recurrente": bool(m.get("Suscripción") or m.get("Deuda")),
        })
    filas.sort(key=lambda f: f["fecha"] or datetime.min, reverse=True)
    return filas


def totales(filas):
    ingresos = sum(f["importe"] for f in filas if f["tipo"] == "Ingreso")
    gastos = sum(f["importe"] for f in filas if f["tipo"] == "Gasto")
    return {"ingresos": ingresos, "gastos": gastos, "neto": ingresos - gastos, "n": len(filas)}


# ---------- filtros y agrupación (página Movimientos) ----------

PERIODOS = {
    "mes": "Un mes",
    "anterior": "Mes pasado",
    "3m": "Últimos 3 meses",
    "anio": "Este año",
    "todo": "Todo",
    "rango": "Entre fechas",
}

AGRUPACIONES = {
    "": "Sin agrupar",
    "mes": "Mes",
    "dia": "Día",
    "cuenta": "Cuenta",
    "categoria": "Categoría",
    "tipo": "Tipo",
}


def rango_periodo(periodo, desde=None, hasta=None, hoy=None, mes=None):
    """Devuelve (desde, hasta_exclusivo) para el periodo elegido.

    Con periodo "mes" se puede indicar qué mes con `mes` ("2026-10"); por defecto, el actual.
    """
    hoy = hoy or date.today()
    este_mes = hoy.replace(day=1)
    if periodo == "mes" and mes:
        inicio = inicio_mes(mes)
        return inicio, sumar_meses(inicio, 1)
    if periodo == "anterior":
        return sumar_meses(este_mes, -1), este_mes
    if periodo == "3m":
        return sumar_meses(este_mes, -2), sumar_meses(este_mes, 1)
    if periodo == "anio":
        return date(hoy.year, 1, 1), date(hoy.year + 1, 1, 1)
    if periodo == "todo":
        return None, None
    if periodo == "rango":
        d = a_fecha(desde) if desde else None
        h = a_fecha(hasta) if hasta else None
        return d, (h + timedelta(days=1)) if h else None
    return este_mes, sumar_meses(este_mes, 1)


def filtrar(filas, tipo="", cuenta="", categoria="", texto=""):
    texto = (texto or "").strip().lower()
    res = []
    for f in filas:
        if tipo and f["tipo"] != tipo:
            continue
        # una transferencia "pertenece" a la cuenta de origen y a la de destino
        if cuenta and cuenta not in (f["cuenta_id"], f["destino_id"]):
            continue
        if categoria == "sin" and f["categoria_id"]:
            continue
        if categoria and categoria != "sin" and f["categoria_id"] != categoria:
            continue
        if texto and texto not in f["concepto"].lower() and texto not in (f["categoria"] or "").lower():
            continue
        res.append(f)
    return res


def agrupar(filas, por):
    """Agrupa las filas y calcula subtotales. Sin `por`, un único grupo."""
    if not por:
        return [{"titulo": None, "filas": filas, **totales(filas)}]

    def clave(f):
        if por == "mes":
            return f["mes"] or "", nombre_mes(f["mes"]).capitalize() if f["mes"] else "Sin fecha"
        if por == "dia":
            d = f["fecha"].date() if f["fecha"] else None
            return (d.isoformat() if d else ""), (d.strftime("%d/%m/%Y") if d else "Sin fecha")
        if por == "cuenta":
            return f["cuenta"] or "", f["cuenta"] or "Sin cuenta"
        if por == "categoria":
            if f["tipo"] == "Transferencia":
                return "~transferencias", "🔄 Transferencias"
            return f["categoria"] or "~", f"{f['emoji']} {f['categoria']}".strip() if f["categoria"] else "Sin categoría"
        return f["tipo"] or "", f["tipo"] or "Sin tipo"

    grupos = {}
    for f in filas:
        k, titulo = clave(f)
        grupos.setdefault(k, {"titulo": titulo, "filas": []})["filas"].append(f)
    lista = [{**g, **totales(g["filas"])} for g in grupos.values()]
    if por in ("mes", "dia"):
        orden = sorted(grupos)
        lista = [{**grupos[k], **totales(grupos[k]["filas"])} for k in reversed(orden)]
    elif por in ("cuenta", "categoria"):
        # primero lo que más mueve
        lista.sort(key=lambda g: -(g["gastos"] + g["ingresos"]))
    return lista


# ---------- resumen (página principal) ----------

def construir(datos, mes=None, hoy=None):
    """datos = {"cuentas", "categorias", "suscripciones", "deudas", "movimientos"}.

    `movimientos` debe incluir al menos los 12 meses anteriores a `mes` (para el gráfico).
    """
    hoy = hoy or date.today()
    mes = mes or clave_mes(hoy)
    filas = enriquecer(datos["movimientos"], datos["cuentas"], datos["categorias"])
    del_mes = [f for f in filas if f["mes"] == mes]
    mes_ant = mes_desplazado(mes, -1)
    del_anterior = [f for f in filas if f["mes"] == mes_ant]

    # --- cuentas ---
    activas = [c for c in datos["cuentas"] if c.get("Activa", True)]
    total = sum(_num(c.get("Saldo")) for c in activas)
    gasto_cuenta = {}
    for f in del_mes:
        if f["tipo"] == "Gasto" and f["cuenta_id"]:
            gasto_cuenta[f["cuenta_id"]] = gasto_cuenta.get(f["cuenta_id"], 0) + f["importe"]
    lista_cuentas = [
        {"id": c["id"], "nombre": c["Nombre"], "emoji": c.get("emoji") or "", "tipo": c.get("Tipo"),
         "saldo": _num(c.get("Saldo")), "gastado_mes": gasto_cuenta.get(c["id"], 0.0),
         "peso": (_num(c.get("Saldo")) / total) if total > 0 and _num(c.get("Saldo")) > 0 else 0}
        for c in sorted(activas, key=lambda c: -_num(c.get("Saldo")))
    ]

    # --- categorías del mes, con presupuesto y comparación con el mes anterior ---
    def por_categoria(fs):
        r = {}
        for f in fs:
            if f["tipo"] == "Gasto":
                k = f["categoria_id"] or "sin"
                r[k] = r.get(k, 0) + f["importe"]
        return r

    actual, anterior = por_categoria(del_mes), por_categoria(del_anterior)
    categorias = {c["id"]: c for c in datos["categorias"]}
    ids = set(actual) | {cid for cid, c in categorias.items()
                         if c.get("Tipo") == "Gasto" and c.get("Presupuesto mensual")}
    lista_cats = []
    for cid in ids:
        c = categorias.get(cid, {"Nombre": "Sin categoría", "emoji": ""})
        gastado = actual.get(cid, 0.0)
        presu = _num(c.get("Presupuesto mensual")) or None
        uso = gastado / presu if presu else None
        lista_cats.append({
            "id": cid, "nombre": c["Nombre"], "emoji": c.get("emoji") or "", "gastado": gastado,
            "anterior": anterior.get(cid, 0.0), "diferencia": gastado - anterior.get(cid, 0.0),
            "presupuesto": presu, "uso": uso,
            "estado": None if uso is None else ("pasado" if uso > 1 else "cerca" if uso > 0.8 else "bien"),
        })
    lista_cats.sort(key=lambda c: (-c["gastado"], c["nombre"]))
    escala = max([c["gastado"] for c in lista_cats] + [c["presupuesto"] or 0 for c in lista_cats] + [1])
    for c in lista_cats:
        c["ancho"] = c["gastado"] / escala
        c["marca"] = (c["presupuesto"] / escala) if c["presupuesto"] else None

    # --- evolución de los últimos 12 meses ---
    serie = []
    for k in range(11, -1, -1):
        m = mes_desplazado(mes, -k)
        t = totales([f for f in filas if f["mes"] == m])
        serie.append({"mes": m, "etiqueta": nombre_mes_corto(m), "actual": m == mes, **t})
    maximo = max([s["ingresos"] for s in serie] + [s["gastos"] for s in serie] + [1])
    medias = [s for s in serie if s["n"]]
    gasto_medio = sum(s["gastos"] for s in medias) / len(medias) if medias else 0

    # --- próximos pagos y deudas ---
    pagos = []
    for s in datos["suscripciones"]:
        if s.get("Activa", True) and s.get("Siguiente pago"):
            pagos.append({"nombre": s["Nombre"], "importe": _num(s.get("Importe")), "tipo": s.get("Frecuencia"),
                          "fecha": a_fecha(s["Siguiente pago"]), "dias": s.get("Días restantes")})
    for d in datos["deudas"]:
        if _num(d.get("Pendiente")) > 0 and d.get("Siguiente pago"):
            pagos.append({"nombre": d["Nombre"], "importe": _num(d.get("Cuota")), "tipo": "Cuota",
                          "fecha": a_fecha(d["Siguiente pago"]), "dias": d.get("Días restantes")})
    pagos.sort(key=lambda p: p["fecha"])
    coste_mensual = sum(_num(s.get("Importe")) / (12 if s.get("Frecuencia") == "Anual" else 1)
                        for s in datos["suscripciones"] if s.get("Activa", True))

    deudas = []
    for d in datos["deudas"]:
        total_d, pagado = _num(d.get("Total deuda")), _num(d.get("Total pagado"))
        deudas.append({
            "id": d["id"], "nombre": d["Nombre"], "total": total_d, "pagado": pagado,
            "pendiente": _num(d.get("Pendiente")),
            "cuotas": int(_num(d.get("Nº pagos"))), "n_cuotas": int(_num(d.get("Nº cuotas"))),
            "progreso": min(pagado / total_d, 1) if total_d else 0,
        })

    t_mes, t_ant = totales(del_mes), totales(del_anterior)
    return {
        "mes": mes, "nombre_mes": nombre_mes(mes),
        "mes_anterior": mes_ant, "mes_siguiente": mes_desplazado(mes, 1),
        "es_mes_actual": mes == clave_mes(hoy),
        "total": total, "cuentas": lista_cuentas,
        **t_mes, "gastos_anterior": t_ant["gastos"],
        "categorias": lista_cats, "movimientos": del_mes,
        "serie": serie, "serie_maximo": maximo, "gasto_medio": gasto_medio,
        "pagos": pagos, "coste_mensual_suscripciones": coste_mensual, "deudas": deudas,
    }
