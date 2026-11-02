"""Smart Finance — panel web para revisar los datos de Notion."""
import os
import re

from flask import Flask, abort, render_template, request

from . import demo, resumen


def euros(n, signo=False):
    """1234.5 -> '1.234,50 €' (formato español)."""
    s = f"{abs(n):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    prefijo = ("+" if n > 0 else "−" if n < 0 else "") if signo else ("−" if n < 0 else "")
    return f"{prefijo}{s} €"


def create_app():
    app = Flask(__name__)
    app.jinja_env.filters["euros"] = euros

    def obtener_datos():
        return demo.obtener()

    app.obtener_datos = obtener_datos
    app.config["MODO_DEMO"] = True

    @app.get("/")
    def panel():
        mes = request.args.get("mes")
        if mes and not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", mes):
            abort(400)
        r = resumen.construir(app.obtener_datos(), mes)
        return render_template("panel.html", r=r, demo=app.config["MODO_DEMO"])

    @app.get("/salud")
    def salud():
        return {"estado": "ok"}

    return app
