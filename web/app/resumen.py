"""Convierte los datos crudos (de Notion o de la demo) en lo que pinta el panel.

Todo lo de aquí son funciones puras: entran listas de diccionarios y sale
un diccionario. Así se pueden probar sin red y sin Flask.
"""
from datetime import date, datetime

MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
         "agosto", "septiembre", "octubre", "noviembre", "diciembre"]


def _fecha(iso):
    if not iso:
        return None
    return datetime.fromisoformat(iso.replace("Z", "+00:00"))


def _mes(iso):
    f = _fecha(iso)
    return f.strftime("%Y-%m") if f else None


def _num(v):
    return float(v) if isinstance(v, (int, float)) else 0.0


def mes_desplazado(mes, delta):
    a, m = map(int, mes.split("-"))
    m += delta
    a += (m - 1) // 12
    m = (m - 1) % 12 + 1
    return f"{a:04d}-{m:02d}"


def nombre_mes(mes):
    a, m = map(int, mes.split("-"))
    return f"{MESES[m - 1]} de {a}"


def construir(datos, mes=None):
    mes = mes or date.today().strftime("%Y-%m")
    cuentas = {c["id"]: c for c in datos["cuentas"]}
    categorias = {c["id"]: c for c in datos["categorias"]}

    # --- cuentas ---
    activas = [c for c in datos["cuentas"] if c.get("Activa", True)]
    total = sum(_num(c.get("Saldo")) for c in activas)
    lista_cuentas = [
        {"nombre": c["Nombre"], "emoji": c.get("emoji") or "", "tipo": c.get("Tipo"),
         "saldo": _num(c.get("Saldo")),
         "peso": (_num(c.get("Saldo")) / total) if total > 0 and _num(c.get("Saldo")) > 0 else 0}
        for c in sorted(activas, key=lambda c: -_num(c.get("Saldo")))
    ]

    # --- movimientos del mes ---
    del_mes = [m for m in datos["movimientos"] if _mes(m.get("Fecha")) == mes]
    del_mes.sort(key=lambda m: m.get("Fecha") or "", reverse=True)
    ingresos = sum(_num(m["Importe"]) for m in del_mes if m["Tipo"] == "Ingreso")
    gastos = sum(_num(m["Importe"]) for m in del_mes if m["Tipo"] == "Gasto")

    gasto_por_cat = {}
    for m in del_mes:
        if m["Tipo"] == "Gasto":
            for cid in m.get("Categoría") or ["sin"]:
                gasto_por_cat[cid] = gasto_por_cat.get(cid, 0) + _num(m["Importe"])

    lista_cats = []
    for cid, gastado in gasto_por_cat.items():
        c = categorias.get(cid, {"Nombre": "Sin categoría", "emoji": ""})
        presu = c.get("Presupuesto mensual")
        presu = _num(presu) if presu else None
        uso = gastado / presu if presu else None
        lista_cats.append({
            "nombre": c["Nombre"], "emoji": c.get("emoji") or "", "gastado": gastado,
            "presupuesto": presu, "uso": uso,
            "estado": None if uso is None else ("pasado" if uso > 1 else "cerca" if uso > 0.8 else "bien"),
        })
    # categorías con presupuesto pero sin gasto también se enseñan
    for cid, c in categorias.items():
        if c.get("Tipo") == "Gasto" and c.get("Presupuesto mensual") and cid not in gasto_por_cat:
            lista_cats.append({"nombre": c["Nombre"], "emoji": c.get("emoji") or "", "gastado": 0.0,
                               "presupuesto": _num(c["Presupuesto mensual"]), "uso": 0.0, "estado": "bien"})
    lista_cats.sort(key=lambda c: -c["gastado"])
    escala = max([c["gastado"] for c in lista_cats] + [c["presupuesto"] or 0 for c in lista_cats] + [1])
    for c in lista_cats:
        c["ancho"] = c["gastado"] / escala
        c["marca"] = (c["presupuesto"] / escala) if c["presupuesto"] else None

    movimientos = []
    for m in del_mes:
        signo = 1 if m["Tipo"] == "Ingreso" else -1 if m["Tipo"] == "Gasto" else 0
        cat = categorias.get((m.get("Categoría") or [None])[0]) or {}
        origen = cuentas.get((m.get("Cuenta") or [None])[0]) or {}
        destino = cuentas.get((m.get("Cuenta destino") or [None])[0]) or {}
        movimientos.append({
            "fecha": _fecha(m["Fecha"]), "concepto": m["Concepto"], "tipo": m["Tipo"],
            "importe": _num(m["Importe"]), "signo": signo,
            "categoria": cat.get("Nombre"), "emoji": cat.get("emoji") or ("🔄" if signo == 0 else ""),
            "cuenta": origen.get("Nombre"), "destino": destino.get("Nombre"),
        })

    # --- próximos pagos (suscripciones + cuotas), en orden de fecha ---
    pagos = []
    for s in datos["suscripciones"]:
        if s.get("Activa", True) and s.get("Siguiente pago"):
            pagos.append({"nombre": s["Nombre"], "importe": _num(s.get("Importe")), "tipo": s.get("Frecuencia"),
                          "fecha": _fecha(s["Siguiente pago"]), "dias": s.get("Días restantes")})
    for d in datos["deudas"]:
        if _num(d.get("Pendiente")) > 0 and d.get("Siguiente pago"):
            pagos.append({"nombre": d["Nombre"], "importe": _num(d.get("Cuota")), "tipo": "Cuota",
                          "fecha": _fecha(d["Siguiente pago"]), "dias": d.get("Días restantes")})
    pagos.sort(key=lambda p: p["fecha"])
    coste_mensual = sum(_num(s.get("Importe")) / (12 if s.get("Frecuencia") == "Anual" else 1)
                        for s in datos["suscripciones"] if s.get("Activa", True))

    deudas = []
    for d in datos["deudas"]:
        total_d = _num(d.get("Total deuda"))
        pagado = _num(d.get("Total pagado"))
        deudas.append({
            "nombre": d["Nombre"], "total": total_d, "pagado": pagado, "pendiente": _num(d.get("Pendiente")),
            "cuotas": int(_num(d.get("Nº pagos"))), "n_cuotas": int(_num(d.get("Nº cuotas"))),
            "progreso": min(pagado / total_d, 1) if total_d else 0,
        })

    return {
        "mes": mes, "nombre_mes": nombre_mes(mes),
        "mes_anterior": mes_desplazado(mes, -1), "mes_siguiente": mes_desplazado(mes, 1),
        "es_mes_actual": mes == date.today().strftime("%Y-%m"),
        "total": total, "cuentas": lista_cuentas,
        "ingresos": ingresos, "gastos": gastos, "neto": ingresos - gastos,
        "categorias": lista_cats, "movimientos": movimientos,
        "pagos": pagos, "coste_mensual_suscripciones": coste_mensual, "deudas": deudas,
        "generado": _fecha(datos.get("generado")),
    }
