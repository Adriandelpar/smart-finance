# Panel web

Un panel para revisar los datos de un vistazo: saldo y reparto por cuentas, balance del mes, gasto por categoría frente al presupuesto, movimientos, próximos pagos y deudas. Se puede navegar entre meses.

El panel **solo lee**. Los movimientos se siguen metiendo desde el móvil, que habla directamente con Notion y funciona desde cualquier sitio.

## Cómo funciona

```
Navegador ──► Flask (web/app) ──► API de Notion
              el token vive aquí,
              nunca llega al navegador
```

¿Por qué hace falta un servidor y no basta con un HTML? Por dos motivos:

1. **El token es una contraseña.** Si la página llamara a Notion directamente, el token tendría que ir dentro del HTML y cualquiera que abriera la página podría leerlo.
2. **Notion no lo permite.** La API de Notion no acepta peticiones desde un navegador (no envía cabeceras CORS), así que una página web no puede hablar con ella aunque quiera.

El servidor hace de intermediario: guarda el token, pide los datos a Notion y le entrega al navegador solo el HTML ya montado.

## Arrancarlo en el portátil

### Con Docker (Linux o Windows)

Necesitas Docker (en Windows, [Docker Desktop](https://www.docker.com/products/docker-desktop/)).

```bash
git clone https://github.com/Adriandelpar/smart-finance.git
cd smart-finance
cp .env.example .env        # en Windows: copy .env.example .env
# edita .env y pon tu NOTION_TOKEN
docker compose up -d --build
```

Abre <http://localhost:8000>. Para pararlo, `docker compose down`. Como tiene `restart: unless-stopped`, se levanta solo cada vez que arranca Docker.

Sin `.env` (o con `NOTION_TOKEN` vacío) arranca en **modo demo**, con datos de ejemplo.

### Sin Docker

```bash
cd web
python -m venv .venv
source .venv/bin/activate          # en Windows: .venv\Scripts\activate
pip install -r requirements.txt
export NOTION_TOKEN=ntn_...        # en Windows (PowerShell): $env:NOTION_TOKEN="ntn_..."
flask --app app run
```

Abre <http://localhost:5000>.

## Seguridad en local

- `docker-compose.yml` publica el puerto en `127.0.0.1`, así que **solo tu propio ordenador** puede entrar. Nadie de tu wifi ve el panel.
- Por eso en local no hace falta contraseña. Si quieres verlo desde el móvil en casa, cambia el puerto a `"8000:8000"`, entra con la IP del portátil y **pon `APP_PASSWORD`** en el `.env`.

## Verlo fuera de casa (opcional y gratis)

Fuera de casa, la forma más simple de ver tus datos es la **app de Notion**, que ya enseña todo el panel de Smart Finance.

Si algún día quieres esta web en internet sin pagar servidor, la misma imagen de Docker se puede desplegar en un hosting con plan gratuito, como [Render](https://render.com/):

1. New → Web Service → conecta este repositorio de GitHub.
2. Root directory: `web`. Runtime: Docker.
3. Variables de entorno: `NOTION_TOKEN` y **`APP_PASSWORD` (obligatoria: la web quedará en internet)**.
4. Render te da una URL `https://...onrender.com` con HTTPS.

Ten en cuenta que en los planes gratuitos el servicio se duerme tras un rato sin visitas y la primera carga tarda unos segundos en despertar.

## Variables de entorno

| Variable | Obligatoria | Para qué |
|---|---|---|
| `NOTION_TOKEN` | No (sin ella, modo demo) | Secreto de la integración de Notion |
| `APP_PASSWORD` | Solo si la publicas | Pide contraseña para entrar |
| `SECRET_KEY` | No | Firma la cookie de sesión. Si falta, se deriva de `APP_PASSWORD` |

## Tests

```bash
cd web
pip install -r requirements-dev.txt
pytest
```

Prueban los cálculos del resumen, el cliente de Notion con la red simulada (paginación, filtro por mes, caché, errores) y las rutas (login, mes inválido, página de error). La CI además construye la imagen, la arranca y comprueba que responde.
