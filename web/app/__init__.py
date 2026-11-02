"""Smart Finance — panel web para revisar los datos de Notion."""
import hmac
import os
import re
import secrets

from flask import Flask, abort, redirect, render_template, request, session, url_for

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
        # Contraseña opcional: en local no hace falta; si la web se publica, sí.
        APP_PASSWORD=os.environ.get("APP_PASSWORD", ""),
        SECRET_KEY=os.environ.get("SECRET_KEY") or secrets.token_hex(32),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
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

    @app.before_request
    def exigir_login():
        if not app.config["APP_PASSWORD"] or request.endpoint in ("login", "salud", "static"):
            return None
        if not session.get("dentro"):
            return redirect(url_for("login", siguiente=request.full_path))

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if not app.config["APP_PASSWORD"]:
            return redirect(url_for("panel"))
        error = None
        if request.method == "POST":
            # compare_digest compara en tiempo constante (evita ataques de temporización)
            if hmac.compare_digest(request.form.get("clave", "").encode(), app.config["APP_PASSWORD"].encode()):
                session["dentro"] = True
                session.permanent = True
                siguiente = request.args.get("siguiente", "/")
                return redirect(siguiente if siguiente.startswith("/") and not siguiente.startswith(("//", "/\\")) else "/")
            error = "Contraseña incorrecta."
        return render_template("login.html", error=error), (401 if error else 200)

    @app.post("/salir")
    def salir():
        session.clear()
        return redirect(url_for("login"))

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
        return render_template("panel.html", r=r, demo=app.config["MODO_DEMO"],
                               con_login=bool(app.config["APP_PASSWORD"]))

    @app.get("/salud")
    def salud():
        return {"estado": "ok", "demo": app.config["MODO_DEMO"]}

    return app
