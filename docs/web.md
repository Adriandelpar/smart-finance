# Aplicación web

Para gestionar las finanzas desde el portátil. Lee y escribe en el mismo Notion que usa el móvil, así que lo que hagas en un sitio aparece en el otro.

| Página | Qué hace |
|---|---|
| **Resumen** | Saldo total y por cuenta, balance del mes y comparación con el anterior, gráfico de ingresos y gastos de los últimos 12 meses (cada barra lleva a su mes), gasto por categoría frente al presupuesto, gasto por cuenta, próximos pagos y deudas |
| **Movimientos** | Filtros por periodo (un mes, mes pasado, 3 meses, año, todo o entre fechas), tipo, cuenta, categoría y texto. **Agrupar** por mes, día, cuenta, categoría o tipo con subtotales. Exportar a CSV (se abre en Excel o LibreOffice) |
| **Añadir / editar movimiento** | Gasto, ingreso o transferencia. El formulario se adapta al tipo: en transferencias pide cuenta de destino, en gastos deja enlazarlo a una suscripción o deuda |
| **Cuentas, Categorías, Suscripciones, Deudas** | Tablas con lo calculado (saldo, siguiente pago, cuotas pagadas…) y formularios para añadir, cambiar o eliminar. Las categorías llevan emoji y presupuesto |

Eliminar algo lo manda a la **papelera de Notion**, desde donde se puede recuperar.

En **modo demo** (sin token) todo funciona igual sobre datos de ejemplo guardados en memoria: puedes crear, editar y borrar para probar, y al reiniciar vuelve a empezar.

## Cómo funciona

```
Navegador ──► Flask (web/app) ──► API de Notion
              el token vive aquí,
              nunca llega al navegador
```

Por dentro:

| Fichero | Papel |
|---|---|
| `esquema.py` | Qué campos tiene cada entidad y de qué tipo. Lo usan los formularios, las tablas y la traducción a Notion |
| `repositorio.py` | La interfaz común (`listar`, `crear`, `actualizar`, `archivar`…) y `RepoMemoria`, la demo, que calcula a mano lo que en Notion hacen las fórmulas |
| `notion.py` | `RepoNotion`: la misma interfaz sobre la API de Notion, con caché de 60 s que se vacía al escribir |
| `formularios.py` | Convierte lo que manda un `<form>` (siempre texto) a números, fechas y relaciones, y valida |
| `resumen.py` | Cálculos: totales, filtros, agrupaciones, comparativas y la serie de 12 meses. Funciones puras |
| `__init__.py` | Rutas de Flask, login opcional y protección CSRF |

Como la web habla siempre con "un repositorio", no sabe si detrás está Notion o la demo. Es el mismo principio que usar una interfaz en vez de una clase concreta: cambiar de almacenamiento (por ejemplo a PostgreSQL) solo exigiría escribir otro repositorio.

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

- `docker-compose.yml` publica el puerto en `127.0.0.1`, así que **solo tu propio ordenador** puede entrar. Nadie de tu wifi ve la web.
- Por eso en local no hace falta contraseña.
- Todos los formularios llevan un **token CSRF**. Sin él, cualquier página que visitaras podría enviar en secreto un formulario a `localhost:8000` (tu navegador sí llega ahí) y borrarte movimientos. Con el token, la web solo acepta formularios que ella misma ha generado.
- Si quieres usarla desde el móvil en casa, cambia el puerto a `"8000:8000"`, entra con la IP del portátil y **pon `APP_PASSWORD`** en el `.env`.

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

46 tests: las fórmulas replicadas (saldos, siguiente pago, cuotas), la traducción a y desde el JSON de Notion, el repositorio de Notion con la red simulada (paginación, caché que se vacía al escribir, archivar), la validación de formularios, filtros y agrupaciones, y las rutas (crear, editar y eliminar, CSRF, CSV, login). La CI además construye la imagen, la arranca y comprueba que responde.
