"""Leer y validar los formularios HTML a partir del esquema.

Un <form> siempre manda texto. Aquí se convierte cada campo a su tipo
(número, fecha, casilla, relación) y se comprueba lo obligatorio.
"""
from datetime import datetime
from zoneinfo import ZoneInfo

from .repositorio import a_fecha

ZONA = ZoneInfo("Europe/Madrid")


def _numero(texto):
    texto = (texto or "").strip().replace("€", "").replace(" ", "")
    if not texto:
        return None
    # admite 1.234,56 y 1234.56
    if "," in texto:
        texto = texto.replace(".", "").replace(",", ".")
    return float(texto)


def leer(entidad, form):
    datos, errores = {}, {}
    for c in entidad.campos:
        bruto = form.get(c.nombre, "")
        try:
            if c.tipo == "checkbox":
                valor = c.nombre in form
            elif c.tipo == "number":
                valor = _numero(bruto)
            elif c.tipo == "date":
                valor = a_fecha(bruto).isoformat() if bruto else None
            elif c.tipo == "datetime":
                # <input type="datetime-local"> manda "2026-11-02T18:30" en hora local
                valor = (datetime.fromisoformat(bruto).replace(tzinfo=ZONA).isoformat(timespec="minutes")
                         if bruto else None)
            elif c.tipo == "relation":
                valor = [bruto] if bruto else []
            else:
                valor = bruto.strip() or None
        except ValueError:
            errores[c.nombre] = "No es un valor válido."
            continue
        if c.tipo == "select" and valor and valor not in c.opciones:
            errores[c.nombre] = "Elige una de las opciones."
            continue
        if c.obligatorio and valor in (None, "", []):
            errores[c.nombre] = "Este campo es obligatorio."
            continue
        datos[c.nombre] = valor

    if entidad.con_emoji:
        datos["emoji"] = form.get("emoji", "").strip()[:4]

    # reglas propias de los movimientos
    if entidad.clave == "movimientos" and not errores:
        if datos["Importe"] is not None and datos["Importe"] <= 0:
            errores["Importe"] = "Pon el importe en positivo; el tipo indica si suma o resta."
        if datos["Tipo"] == "Transferencia":
            if not datos.get("Cuenta destino"):
                errores["Cuenta destino"] = "Una transferencia necesita cuenta de destino."
            elif datos["Cuenta destino"] == datos["Cuenta"]:
                errores["Cuenta destino"] = "La cuenta de destino tiene que ser distinta de la de origen."
            datos["Categoría"] = []
        else:
            datos["Cuenta destino"] = []
        if datos["Tipo"] != "Gasto":
            datos["Suscripción"], datos["Deuda"] = [], []
    for campo in ("Importe", "Cuota", "Total deuda", "Nº cuotas"):
        if campo in datos and datos[campo] is not None and datos[campo] < 0 and campo not in errores:
            errores[campo] = "No puede ser negativo."
    return datos, errores


def valores_iniciales(entidad, registro, extra=None):
    """Valores para rellenar el formulario (como texto, igual que los manda el navegador)."""
    valores = {}
    if registro is None:
        for c in entidad.campos:
            if c.tipo == "checkbox":
                valores[c.nombre] = "on"   # cuentas y suscripciones nuevas, activas por defecto
        valores.update(extra or {})
        return valores
    for c in entidad.campos:
        v = registro.get(c.nombre)
        if c.tipo == "relation":
            v = (v or [""])[0]
        elif c.tipo == "checkbox":
            v = "on" if v else None
        elif c.tipo == "number":
            v = "" if v is None else (f"{v:.2f}".rstrip("0").rstrip(".") if isinstance(v, float) else str(v))
        elif c.tipo == "date":
            v = (v or "")[:10]
        elif c.tipo == "datetime" and v:
            d = datetime.fromisoformat(v.replace("Z", "+00:00"))
            d = d.astimezone(ZONA) if d.tzinfo else d
            v = d.strftime("%Y-%m-%dT%H:%M")
        if v is not None:
            valores[c.nombre] = v
    if entidad.con_emoji:
        valores["emoji"] = registro.get("emoji") or ""
    return valores


def opciones_relaciones(entidad, catalogos):
    """Para cada campo relación, la lista [(id, etiqueta)] para el <select>."""
    from .esquema import ENTIDADES
    opciones = {}
    for c in entidad.campos:
        if c.tipo != "relation":
            continue
        destino = ENTIDADES[c.destino]
        registros = catalogos.get(c.destino, [])
        if c.destino == "cuentas":
            registros = [r for r in registros if r.get("Activa", True)]
        opciones[c.nombre] = [
            (r["id"], f"{r.get('emoji') or ''} {r.get(destino.titulo) or ''}".strip(),
             r.get("Tipo"))   # el tipo sirve para separar categorías de gasto e ingreso
            for r in sorted(registros, key=lambda r: (r.get(destino.titulo) or "").lower())
        ]
    return opciones
