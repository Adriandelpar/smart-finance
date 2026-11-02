"""Acceso a los datos: la web solo habla con un "repositorio".

Hay dos implementaciones con la misma interfaz:

  - RepoNotion (notion.py): la real, lee y escribe en la API de Notion.
  - RepoMemoria (aquí):     la demo; guarda todo en memoria y calcula a mano
                            lo que en Notion hacen las fórmulas y rollups.

Interfaz común:
    listar(clave)                 -> [registro]   cuentas, categorias, suscripciones, deudas
    movimientos(desde, hasta)     -> [registro]   hasta es exclusivo; None = sin límite
    obtener(clave, id)            -> registro
    crear(clave, datos)           -> registro
    actualizar(clave, id, datos)  -> registro
    archivar(clave, id)

Un registro es un diccionario plano: {"id", "emoji", "<propiedad>": valor, ...}.
Las relaciones son listas de ids.
"""
import copy
import threading
import uuid
from calendar import monthrange
from datetime import date, datetime

from .esquema import ENTIDADES


class NoEncontrado(Exception):
    pass


# ---------- utilidades de fechas compartidas ----------

def sumar_meses(d, n):
    m = d.month - 1 + n
    a = d.year + m // 12
    m = m % 12 + 1
    return d.replace(year=a, month=m, day=min(d.day, monthrange(a, m)[1]))


def a_fecha(valor):
    if not valor:
        return None
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    return datetime.fromisoformat(str(valor).replace("Z", "+00:00")).date()


def siguiente_pago(primero, frecuencia, hoy=None):
    """Primera fecha >= hoy de la serie primero, primero+paso, primero+2·paso..."""
    hoy = hoy or date.today()
    primero = a_fecha(primero)
    if not primero:
        return None
    paso = 12 if frecuencia == "Anual" else 1
    k = max(0, ((hoy.year - primero.year) * 12 + hoy.month - primero.month) // paso - 1)
    fecha = sumar_meses(primero, k * paso)
    while fecha < hoy:
        k += 1
        fecha = sumar_meses(primero, k * paso)
    return fecha


def normalizar(entidad, datos):
    """Deja en `datos` solo campos conocidos, con relaciones como lista de ids."""
    limpio = {}
    for c in entidad.campos:
        if c.nombre not in datos:
            continue
        v = datos[c.nombre]
        if c.tipo == "relation":
            if isinstance(v, (list, tuple)):
                v = [x for x in v if x]
            else:
                v = [v] if v else []
        limpio[c.nombre] = v
    if entidad.con_emoji and "emoji" in datos:
        limpio["emoji"] = datos["emoji"] or ""
    return limpio


# ---------- repositorio en memoria (modo demo) ----------

class RepoMemoria:
    def __init__(self, datos_iniciales):
        self._lock = threading.Lock()
        self._datos = {clave: [dict(r) for r in datos_iniciales.get(clave, [])] for clave in ENTIDADES}

    # lectura

    def listar(self, clave):
        with self._lock:
            registros = [copy.deepcopy(r) for r in self._datos[clave]]
            return self._calcular(clave, registros)

    def movimientos(self, desde=None, hasta=None):
        with self._lock:
            res = []
            for m in self._datos["movimientos"]:
                f = a_fecha(m.get("Fecha"))
                if desde and (not f or f < desde):
                    continue
                if hasta and (not f or f >= hasta):
                    continue
                res.append(copy.deepcopy(m))
            return res

    def obtener(self, clave, id_):
        lista = self.movimientos() if clave == "movimientos" else self.listar(clave)
        for r in lista:
            if r["id"] == id_:
                return r
        raise NoEncontrado(id_)

    # escritura

    def crear(self, clave, datos):
        registro = {"id": str(uuid.uuid4()), "emoji": ""}
        registro.update(normalizar(ENTIDADES[clave], datos))
        with self._lock:
            self._datos[clave].append(registro)
        return self.obtener(clave, registro["id"])

    def actualizar(self, clave, id_, datos):
        with self._lock:
            for r in self._datos[clave]:
                if r["id"] == id_:
                    r.update(normalizar(ENTIDADES[clave], datos))
                    break
            else:
                raise NoEncontrado(id_)
        return self.obtener(clave, id_)

    def archivar(self, clave, id_):
        with self._lock:
            antes = len(self._datos[clave])
            self._datos[clave] = [r for r in self._datos[clave] if r["id"] != id_]
            if len(self._datos[clave]) == antes:
                raise NoEncontrado(id_)

    # lo que en Notion hacen las fórmulas y rollups

    def _calcular(self, clave, registros):
        movs = self._datos["movimientos"]
        hoy = date.today()
        if clave == "cuentas":
            for c in registros:
                saldo = float(c.get("Saldo inicial") or 0)
                for m in movs:
                    imp = float(m.get("Importe") or 0)
                    if c["id"] in (m.get("Cuenta") or []):
                        saldo += imp if m.get("Tipo") == "Ingreso" else -imp
                    if c["id"] in (m.get("Cuenta destino") or []) and m.get("Tipo") == "Transferencia":
                        saldo += imp
                c["Saldo"] = round(saldo, 2)
        elif clave == "suscripciones":
            for s in registros:
                sig = siguiente_pago(s.get("Primer cobro"), s.get("Frecuencia"), hoy)
                s["Siguiente pago"] = sig.isoformat() if sig else None
                s["Días restantes"] = (sig - hoy).days if sig else None
        elif clave == "deudas":
            for d in registros:
                pagos = [m for m in movs if d["id"] in (m.get("Deuda") or [])]
                pagado = sum(float(m.get("Importe") or 0) for m in pagos)
                d["Total pagado"] = round(pagado, 2)
                d["Nº pagos"] = len(pagos)
                d["Pendiente"] = round(float(d.get("Total deuda") or 0) - pagado, 2)
                primera = a_fecha(d.get("Primera cuota"))
                sig = sumar_meses(primera, len(pagos)) if primera else None
                d["Siguiente pago"] = sig.isoformat() if sig else None
                d["Días restantes"] = (sig - hoy).days if sig else None
        return registros
