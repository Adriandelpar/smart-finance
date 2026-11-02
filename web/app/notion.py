"""Cliente mínimo de la API de Notion: solo lectura.

La API devuelve cada propiedad envuelta en su tipo, por ejemplo:

    "Importe": {"type": "number", "number": 12.5}
    "Tipo":    {"type": "select", "select": {"name": "Gasto"}}

`aplanar()` lo convierte en un diccionario simple {"Importe": 12.5, "Tipo": "Gasto"},
que es la misma forma que usan los datos de demo.
"""
import time
from datetime import date, datetime

import requests

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


class Cliente:
    def __init__(self, token, sesion=None, cache_segundos=60):
        self.sesion = sesion or requests.Session()
        self.sesion.headers.update({
            "Authorization": f"Bearer {token}",
            "Notion-Version": VERSION,
            "Content-Type": "application/json",
        })
        self.cache_segundos = cache_segundos
        self._cache = {}

    def _query(self, db, filtro=None):
        """Consulta una base de datos entera, siguiendo la paginación (100 por página)."""
        resultados, cursor = [], None
        while True:
            body = {"page_size": 100}
            if filtro:
                body["filter"] = filtro
            if cursor:
                body["start_cursor"] = cursor
            r = self.sesion.post(f"{API}/databases/{db}/query", json=body, timeout=15)
            if r.status_code != 200:
                raise ErrorNotion(f"Notion respondió {r.status_code}: {r.text[:300]}")
            datos = r.json()
            resultados += [aplanar(p) for p in datos["results"]]
            if not datos.get("has_more"):
                return resultados
            cursor = datos["next_cursor"]

    def obtener(self, mes=None, refrescar=False):
        mes = mes or date.today().strftime("%Y-%m")
        guardado = self._cache.get(mes)
        if guardado and not refrescar and time.time() - guardado[0] < self.cache_segundos:
            return guardado[1]

        a, m = map(int, mes.split("-"))
        inicio = date(a, m, 1)
        fin = date(a + (m == 12), m % 12 + 1, 1)
        datos = {
            "cuentas": self._query(DB["cuentas"]),
            "categorias": self._query(DB["categorias"]),
            "suscripciones": self._query(DB["suscripciones"]),
            "deudas": self._query(DB["deudas"]),
            # solo los movimientos del mes que se está viendo
            "movimientos": self._query(DB["movimientos"], {"and": [
                {"property": "Fecha", "date": {"on_or_after": inicio.isoformat()}},
                {"property": "Fecha", "date": {"before": fin.isoformat()}},
            ]}),
            "generado": datetime.now().isoformat(),
        }
        self._cache[mes] = (time.time(), datos)
        return datos
