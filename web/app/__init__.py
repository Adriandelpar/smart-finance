"""Smart Finance — panel web para revisar los datos de Notion."""
import os
import re

from flask import Flask, abort, render_template, request

from . import demo, notion, resumen


def euros(n, signo=False):
    """1234.5 -> '1.234,50 €' (formato español)."""
    s = f"{abs(n):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    prefijo = ("+" if n > 0 else "−" if n < 0 else "") if signo else ("−" if n < 0 else "")
    return f"{prefijo}{s} €"


def create_app(config=None):
    app = Flask(__name__)
    app.config.update(
        NOTION_TOKEN=os.environ.get("NOTION_TOKEN", "").strip(),
    )
    app.config.update(config or {})
    app.jinja_env.filters["euros"] = euros

    # Sin token -> modo demo con datos de ejemplo
    if app.config["NOTION_TOKEN"]:
        cliente = notion.Cliente(app.config["NOTION_TOKEN"])
        app.config["MODO_DEMO"] = False

        def obtener_datos(mes, refrescar=False):
            return cliente.obtener(mes, refrescar)
    else:
        app.config["MODO_DEMO"] = True

        def obtener_datos(mes, refrescar=False):
            return demo.obtener()

    app.obtener_datos = obtener_datos

    @app.get("/")
    def panel():
        mes = request.args.get("mes")
        if mes and not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", mes):
            abort(400)
        try:
            datos = app.obtener_datos(mes, refrescar="refrescar" in request.args)
        except notion.ErrorNotion as e:
            return render_template("error.html", mensaje=str(e)), 502
        r = resumen.construir(datos, mes)
        return render_template("panel.html", r=r, demo=app.config["MODO_DEMO"])

    @app.get("/salud")
    def salud():
        return {"estado": "ok", "demo": app.config["MODO_DEMO"]}

    return app
