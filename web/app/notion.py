"""Repositorio sobre la API de Notion (lectura y escritura).

La API envuelve cada propiedad en su tipo, por ejemplo:

    "Importe": {"type": "number", "number": 12.5}
    "Tipo":    {"type": "select", "select": {"name": "Gasto"}}

`aplanar()` lo convierte en {"Importe": 12.5, "Tipo": "Gasto"} para leer, y
`a_propiedades()` hace el camino inverso para escribir, usando esquema.py.
"""
import threading
import time
from datetime import date, datetime

import requests

from .esquema import ENTIDADES
from .repositorio import NoEncontrado, normalizar

API = "https://api.notion.com/v1"
VERSION = "2022-06-28"

DB = {
    "cuentas": "f9254c6213a740ad9bb2f18b01ad98c1",
    "categorias": "54af8712b04145e8b0356ac0b7e7423d",
    "suscripciones": "172d96c31ec24dea841a60253251b069",
    "deudas": "3787922069074996af6b818819beb350",
    "movimientos": "d77b034da9bd483ca6e44b045e205351",
}


class ErrorNotion(Exception):
    pass


# ---------- Notion -> diccionario ----------

def _valor(p):
    tipo = p["type"]
    v = p.get(tipo)
    if tipo in ("title", "rich_text"):
        return "".join(t.get("plain_text", "") for t in v)
    if tipo == "select":
        return v["name"] if v else None
    if tipo == "date":
        return v["start"] if v else None
    if tipo == "relation":
        return [r["id"] for r in v]
    if tipo == "formula":
        sub = v["type"]
        return _valor({"type": sub, sub: v.get(sub)}) if sub == "date" else v.get(sub)
    if tipo == "rollup":
        sub = v["type"]
        return v.get(sub) if sub in ("number", "date") else None
    return v  # number, checkbox, url...


def aplanar(pagina):
    plano = {"id": pagina["id"]}
    icono = pagina.get("icon")
    plano["emoji"] = icono["emoji"] if icono and icono.get("type") == "emoji" else ""
    for nombre, prop in pagina["properties"].items():
        plano[nombre] = _valor(prop)
    return plano


# ---------- diccionario -> Notion ----------

def _iso(v):
    if isinstance(v, (date, datetime)):
        return v.isoformat()
    return v or None


def a_propiedades(entidad, datos):
    """Convierte {"Importe": 12.5, "Cuenta": ["id"]...} en el JSON de propiedades de Notion."""
    props = {}
    for c in entidad.campos:
        if c.nombre not in datos:
            continue
        v = datos[c.nombre]
        if c.tipo == "title":
            props[c.nombre] = {"title": [{"text": {"content": v or ""}}]}
        elif c.tipo == "number":
            props[c.nombre] = {"number": None if v in (None, "") else float(v)}
        elif c.tipo == "select":
            props[c.nombre] = {"select": {"name": v} if v else None}
        elif c.tipo in ("date", "datetime"):
            props[c.nombre] = {"date": {"start": _iso(v)} if v else None}
        elif c.tipo == "checkbox":
            props[c.nombre] = {"checkbox": bool(v)}
        elif c.tipo == "relation":
            props[c.nombre] = {"relation": [{"id": i} for i in v]}
    return props


def _icono(datos):
    if "emoji" not in datos:
        return {}
    return {"icon": {"type": "emoji", "emoji": datos["emoji"]} if datos["emoji"] else None}


class RepoNotion:
    def __init__(self, token, sesion=None, cache_segundos=60):
        self.sesion = sesion or requests.Session()
        self.sesion.headers.update({
            "Authorization": f"Bearer {token}",
            "Notion-Version": VERSION,
            "Content-Type": "application/json",
        })
        self.cache_segundos = cache_segundos
        self._cache = {}
        self._lock = threading.Lock()

    # --- HTTP ---

    def _pedir(self, metodo, ruta, json=None):
        r = self.sesion.request(metodo, f"{API}/{ruta}", json=json, timeout=15)
        if r.status_code == 404:
            raise NoEncontrado(ruta)
        if r.status_code != 200:
            raise ErrorNotion(f"Notion respondió {r.status_code}: {r.text[:300]}")
        return r.json()

    def _query(self, db, filtro=None):
        """Consulta una base de datos entera, siguiendo la paginación (100 por página)."""
        resultados, cursor = [], None
        while True:
            body = {"page_size": 100}
            if filtro:
                body["filter"] = filtro
            if cursor:
                body["start_cursor"] = cursor
            datos = self._pedir("POST", f"databases/{db}/query", body)
            resultados += [aplanar(p) for p in datos["results"]]
            if not datos.get("has_more"):
                return resultados
            cursor = datos["next_cursor"]

    def _cacheado(self, clave, funcion):
        with self._lock:
            guardado = self._cache.get(clave)
            if guardado and time.time() - guardado[0] < self.cache_segundos:
                return guardado[1]
        valor = funcion()
        with self._lock:
            self._cache[clave] = (time.time(), valor)
        return valor

    def vaciar_cache(self):
        with self._lock:
            self._cache.clear()

    # --- lectura ---

    def listar(self, clave):
        return self._cacheado(clave, lambda: self._query(DB[clave]))

    def movimientos(self, desde=None, hasta=None):
        filtros = []
        if desde:
            filtros.append({"property": "Fecha", "date": {"on_or_after": desde.isoformat()}})
        if hasta:
            filtros.append({"property": "Fecha", "date": {"before": hasta.isoformat()}})
        filtro = {"and": filtros} if filtros else None
        return self._cacheado(("movimientos", desde, hasta), lambda: self._query(DB["movimientos"], filtro))

    def obtener(self, clave, id_):
        return aplanar(self._pedir("GET", f"pages/{id_}"))

    # --- escritura (cada cambio vacía la caché para que se vea al momento) ---

    def crear(self, clave, datos):
        entidad = ENTIDADES[clave]
        datos = normalizar(entidad, datos)
        body = {"parent": {"database_id": DB[clave]}, "properties": a_propiedades(entidad, datos)}
        body.update(_icono(datos))
        pagina = self._pedir("POST", "pages", body)
        self.vaciar_cache()
        return aplanar(pagina)

    def actualizar(self, clave, id_, datos):
        entidad = ENTIDADES[clave]
        datos = normalizar(entidad, datos)
        body = {"properties": a_propiedades(entidad, datos)}
        body.update(_icono(datos))
        pagina = self._pedir("PATCH", f"pages/{id_}", body)
        self.vaciar_cache()
        return aplanar(pagina)

    def archivar(self, clave, id_):
        # En Notion "archivar" = mover a la papelera: se puede recuperar desde allí
        self._pedir("PATCH", f"pages/{id_}", {"archived": True})
        self.vaciar_cache()
