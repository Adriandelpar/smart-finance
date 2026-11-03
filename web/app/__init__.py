"""Smart Finance — aplicación web para gestionar los datos de Notion."""
import csv
import hashlib
import hmac
import io
import json
import os
import re
import secrets
from datetime import date, datetime

from flask import (Flask, Response, abort, flash, redirect, render_template, request,
                   session, url_for)

from . import demo, formularios, notion, resumen
from .esquema import ENTIDADES, GESTIONABLES
from .repositorio import NoEncontrado, RepoMemoria, sumar_meses


def euros(n, signo=False):
    """1234.5 -> '1.234,50 €' (formato español)."""
    n = n or 0
    s = f"{abs(n):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    prefijo = ("+" if n > 0 else "−" if n < 0 else "") if signo else ("−" if n < 0 else "")
    return f"{prefijo}{s} €"


def create_app(config=None):
    app = Flask(__name__)
    app.config.update(
        NOTION_TOKEN=os.environ.get("NOTION_TOKEN", "").strip(),
        # Contraseña opcional: en local no hace falta; si la web se publica, sí.
        APP_PASSWORD=os.environ.get("APP_PASSWORD", ""),
        SECRET_KEY=os.environ.get("SECRET_KEY", ""),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
    )
    app.config.update(config or {})
    if not app.config["SECRET_KEY"]:
        # Si gunicorn arranca varios procesos, cada uno llama a create_app(): una clave
        # aleatoria sería distinta en cada uno y la sesión se perdería. Derivarla de la
        # configuración da la misma en todos.
        semilla = f"smart-finance:{app.config['APP_PASSWORD']}:{app.config['NOTION_TOKEN']}"
        app.config["SECRET_KEY"] = hashlib.sha256(semilla.encode()).hexdigest()

    app.jinja_env.filters["euros"] = euros

    # Sin token -> modo demo, con datos de ejemplo editables en memoria
    if app.config["NOTION_TOKEN"]:
        app.repo = notion.RepoNotion(app.config["NOTION_TOKEN"])
        app.config["MODO_DEMO"] = False
    else:
        app.repo = RepoMemoria(demo.datos_iniciales())
        app.config["MODO_DEMO"] = True

    # ---------- seguridad: login opcional y CSRF ----------

    @app.before_request
    def proteger():
        if app.config["APP_PASSWORD"] and request.endpoint not in ("login", "salud", "static", "manifiesto"):
            if not session.get("dentro"):
                return redirect(url_for("login", siguiente=request.full_path))
        if request.method == "POST":
            # Sin esto, cualquier web que visites podría enviar un formulario a
            # localhost:8000 y borrarte movimientos (ataque CSRF).
            enviado = request.form.get("csrf", "")
            if not hmac.compare_digest(enviado, session.get("csrf", "")):
                abort(400, "Formulario caducado. Recarga la página y vuelve a intentarlo.")

    @app.context_processor
    def globales():
        if "csrf" not in session:
            session["csrf"] = secrets.token_urlsafe(32)
        return {"csrf": session["csrf"], "demo": app.config["MODO_DEMO"],
                "con_login": bool(app.config["APP_PASSWORD"]), "ENTIDADES": ENTIDADES,
                "GESTIONABLES": GESTIONABLES}

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if not app.config["APP_PASSWORD"]:
            return redirect(url_for("resumen_mes"))
        error = None
        if request.method == "POST":
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

    @app.errorhandler(notion.ErrorNotion)
    def error_notion(e):
        return render_template("error.html", mensaje=str(e)), 502

    @app.errorhandler(NoEncontrado)
    def no_encontrado(e):
        return render_template("error.html", titulo="No existe",
                               mensaje="Ese registro no existe o se ha eliminado."), 404

    # ---------- utilidades ----------

    def catalogos():
        return {clave: app.repo.listar(clave) for clave in GESTIONABLES}

    def nombres(cat):
        """id -> "emoji Nombre" de todo lo que puede aparecer en una relación."""
        res = {}
        for clave, registros in cat.items():
            titulo = ENTIDADES[clave].titulo
            for r in registros:
                res[r["id"]] = f"{r.get('emoji') or ''} {r.get(titulo) or ''}".strip()
        return res

    def volver(por_defecto):
        destino = request.form.get("volver") or request.args.get("volver") or ""
        return destino if destino.startswith("/") and not destino.startswith(("//", "/\\")) else por_defecto

    # ---------- resumen ----------

    @app.get("/")
    def resumen_mes():
        mes = request.args.get("mes") or resumen.clave_mes(date.today())
        if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", mes):
            abort(400)
        if "refrescar" in request.args and hasattr(app.repo, "vaciar_cache"):
            app.repo.vaciar_cache()
        cat = catalogos()
        inicio = resumen.inicio_mes(mes)
        datos = {**cat, "movimientos": app.repo.movimientos(sumar_meses(inicio, -11), sumar_meses(inicio, 1))}
        return render_template("resumen.html", r=resumen.construir(datos, mes))

    # ---------- movimientos ----------

    @app.get("/movimientos")
    def movimientos():
        a = request.args
        periodo = a.get("periodo", "mes")
        if periodo not in resumen.PERIODOS:
            abort(400)
        agrupar = a.get("agrupar", "")
        if agrupar not in resumen.AGRUPACIONES:
            abort(400)
        try:
            mes = a.get("mes") or resumen.clave_mes(date.today())
            if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", mes):
                raise ValueError(mes)
            desde, hasta = resumen.rango_periodo(periodo, a.get("desde"), a.get("hasta"), mes=mes)
        except ValueError:
            abort(400)
        cat = catalogos()
        filas = resumen.enriquecer(app.repo.movimientos(desde, hasta), cat["cuentas"], cat["categorias"])
        filas = resumen.filtrar(filas, a.get("tipo", ""), a.get("cuenta", ""), a.get("categoria", ""), a.get("q", ""))

        if a.get("formato") == "csv":
            return exportar_csv(filas)

        return render_template(
            "movimientos.html", grupos=resumen.agrupar(filas, agrupar), total=resumen.totales(filas),
            cat=cat, f=a, periodo=periodo, agrupar=agrupar, mes=mes,
            mes_anterior=resumen.mes_desplazado(mes, -1), mes_siguiente=resumen.mes_desplazado(mes, 1),
            nombre_mes=resumen.nombre_mes(mes),
            PERIODOS=resumen.PERIODOS, AGRUPACIONES=resumen.AGRUPACIONES,
        )

    def exportar_csv(filas):
        salida = io.StringIO()
        w = csv.writer(salida, delimiter=";")  # ; para que Excel/LibreOffice en español lo abran bien
        w.writerow(["Fecha", "Concepto", "Tipo", "Importe", "Cuenta", "Cuenta destino", "Categoría"])
        for f in reversed(filas):
            w.writerow([f["fecha"].strftime("%Y-%m-%d %H:%M") if f["fecha"] else "", f["concepto"], f["tipo"],
                        f"{f['importe'] * (f['signo'] or 1):.2f}".replace(".", ","),
                        f["cuenta"] or "", f["destino"] or "", f["categoria"] or ""])
        nombre = f"movimientos-{date.today().isoformat()}.csv"
        return Response("﻿" + salida.getvalue(), mimetype="text/csv",
                        headers={"Content-Disposition": f"attachment; filename={nombre}"})

    def pagina_formulario(clave, registro, errores=None, valores=None):
        cat = catalogos()
        entidad = ENTIDADES[clave]
        return render_template(
            "formulario.html", entidad=entidad, registro=registro,
            valores=valores if valores is not None else formularios.valores_iniciales(entidad, registro),
            errores=errores or {}, opciones=formularios.opciones_relaciones(entidad, cat),
            volver=volver(url_for("movimientos") if clave == "movimientos" else url_for("lista", clave=clave)),
        ), (422 if errores else 200)

    def guardar(clave, id_=None):
        entidad = ENTIDADES[clave]
        datos, errores = formularios.leer(entidad, request.form)
        if errores:
            registro = app.repo.obtener(clave, id_) if id_ else None
            return pagina_formulario(clave, registro, errores, valores=request.form)
        if id_:
            app.repo.actualizar(clave, id_, datos)
            flash(f"Cambios guardados en «{datos[entidad.titulo]}».")
        else:
            app.repo.crear(clave, datos)
            flash(f"Añadido «{datos[entidad.titulo]}».")
        return redirect(volver(url_for("movimientos") if clave == "movimientos" else url_for("lista", clave=clave)))

    @app.route("/movimientos/nuevo", methods=["GET", "POST"])
    def nuevo_movimiento():
        if request.method == "POST":
            return guardar("movimientos")
        tipo = request.args.get("tipo", "Gasto")
        return pagina_formulario("movimientos", None, valores=formularios.valores_iniciales(
            ENTIDADES["movimientos"], None, {"Tipo": tipo, "Fecha": datetime.now().strftime("%Y-%m-%dT%H:%M")}))

    @app.route("/movimientos/<id_>", methods=["GET", "POST"])
    def editar_movimiento(id_):
        if request.method == "POST":
            return guardar("movimientos", id_)
        return pagina_formulario("movimientos", app.repo.obtener("movimientos", id_))

    # ---------- cuentas, categorías, suscripciones y deudas ----------

    def comprobar_clave(clave):
        if clave not in GESTIONABLES:
            abort(404)

    @app.get("/gestion/<clave>")
    def lista(clave):
        comprobar_clave(clave)
        cat = catalogos()
        return render_template("lista.html", entidad=ENTIDADES[clave], registros=cat[clave], nombres=nombres(cat))

    @app.route("/gestion/<clave>/nuevo", methods=["GET", "POST"])
    def nuevo(clave):
        comprobar_clave(clave)
        if request.method == "POST":
            return guardar(clave)
        return pagina_formulario(clave, None)

    @app.route("/gestion/<clave>/<id_>", methods=["GET", "POST"])
    def editar(clave, id_):
        comprobar_clave(clave)
        if request.method == "POST":
            return guardar(clave, id_)
        return pagina_formulario(clave, app.repo.obtener(clave, id_))

    @app.post("/eliminar/<clave>/<id_>")
    def eliminar(clave, id_):
        if clave not in ENTIDADES:
            abort(404)
        registro = app.repo.obtener(clave, id_)
        app.repo.archivar(clave, id_)
        nombre = registro.get(ENTIDADES[clave].titulo) or ENTIDADES[clave].singular
        flash(f"Eliminado «{nombre}»." + ("" if app.config["MODO_DEMO"] else " Puedes recuperarlo desde la papelera de Notion."))
        return redirect(volver(url_for("movimientos") if clave == "movimientos" else url_for("lista", clave=clave)))

    @app.get("/manifest.webmanifest")
    def manifiesto():
        """Lo que lee el móvil para instalar la web como app (PWA)."""
        datos = {
            "name": "Smart Finance",
            "short_name": "Finanzas",
            "description": "Gastos, ingresos, presupuestos y suscripciones",
            "lang": "es",
            "start_url": "/",
            "scope": "/",
            "display": "standalone",          # sin barra del navegador, como una app
            "background_color": "#e8edf1",
            "theme_color": "#16243a",
            "icons": [
                {"src": url_for("static", filename="iconos/icono-192.png"), "sizes": "192x192", "type": "image/png"},
                {"src": url_for("static", filename="iconos/icono-512.png"), "sizes": "512x512", "type": "image/png"},
                {"src": url_for("static", filename="iconos/icono-maskable-512.png"), "sizes": "512x512",
                 "type": "image/png", "purpose": "maskable"},
            ],
            "shortcuts": [
                {"name": "Añadir movimiento", "url": "/movimientos/nuevo"},
                {"name": "Movimientos", "url": "/movimientos"},
            ],
        }
        return Response(json.dumps(datos, ensure_ascii=False), mimetype="application/manifest+json")

    @app.get("/salud")
    def salud():
        return {"estado": "ok", "demo": app.config["MODO_DEMO"]}

    return app
