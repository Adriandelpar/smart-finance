# Smart Finance

![CI](https://github.com/Adriandelpar/smart-finance/actions/workflows/ci.yml/badge.svg)

Gestor de gastos personal. Registro cada gasto en segundos desde un botón del centro de control del móvil, y lo reviso en un panel web en el portátil: cuentas, gasto por categoría con presupuesto, suscripciones y deudas. Los datos viven en Notion.

![Panel web en modo demo](docs/img/panel.png)

## Arquitectura

```
 ┌───────────────────────┐                                 ┌──────────────────────────┐
 │ Android (HyperOS)     │   POST /pages (crear)           │                          │
 │ HTTP Shortcuts        │ ──────────────────────────────► │   API REST de Notion     │
 │ src/finanzas.js       │   POST /databases/{id}/query    │                          │
 └───────────────────────┘                                 │  Movimientos, Cuentas,   │
   meter gastos, desde donde sea                           │  Categorías,             │
                                                           │  Suscripciones, Deudas   │
 ┌───────────────────────┐                                 │                          │
 │ Portátil (Docker)     │   POST /databases/{id}/query    │                          │
 │ Flask + gunicorn      │ ──────────────────────────────► │                          │
 │ web/app               │   (solo lectura)                └──────────────────────────┘
 └──────────▲────────────┘
            │ http://localhost:8000
        navegador
```

- **Notion es el backend.** Guarda los datos y calcula los saldos con fórmulas y rollups. Ver el [modelo de datos](docs/modelo-datos.md).
- **El móvil es un cliente para escribir.** Un script de [HTTP Shortcuts](https://http-shortcuts.rmy.ch/) que lee cuentas, categorías, suscripciones y deudas para montar los menús y crea el movimiento. No hay nada cableado: si añado una cuenta en Notion, aparece sola en el móvil.
- **El portátil es un cliente para leer.** Una web en Flask, dentro de Docker, que pide los datos a Notion y los presenta ordenados. El token se queda en el servidor y nunca llega al navegador. Ver [docs/web.md](docs/web.md).

## Qué hace

### Desde el móvil

Al pulsar el botón **Finanzas**:

1. ¿Qué quieres registrar? → gasto, ingreso o transferencia
2. Gasto **único** → concepto, importe, cuenta, categoría
3. Gasto **recurrente** → elige una suscripción o una deuda; sugiere el importe y rellena cuenta y categoría
4. Guarda en Notion y muestra el saldo actualizado de la cuenta

Cancelar cualquier pregunta no guarda nada. Los importes aceptan coma decimal (`12,50`).

### En el portátil

```bash
cp .env.example .env     # y pon tu NOTION_TOKEN
docker compose up -d --build
```

Y abre <http://localhost:8000>. Sin token arranca con datos de ejemplo.

## Estructura

```
src/finanzas.js              Script del atajo del móvil (HTTP Shortcuts)
tests/finanzas.test.js       Tests del atajo con la app y Notion simulados
web/app/notion.py            Cliente de solo lectura de la API de Notion
web/app/resumen.py           Cálculos del panel (funciones puras)
web/app/templates, static    HTML y CSS del panel
web/tests/                   Tests de la web (pytest)
web/Dockerfile               Imagen con gunicorn y usuario sin privilegios
docker-compose.yml           Arranque en local, solo en 127.0.0.1
docs/                        Modelo de datos, instalación en Android y guía de la web
.github/workflows/ci.yml     Tests, build del contenedor y detección de tokens
```

## Desarrollo

```bash
npm test                          # atajo: 8 tests, sin dependencias (node:test)
cd web && pytest                  # web: 17 tests
docker compose up -d --build      # panel en http://localhost:8000
```

Los tests ejecutan el script real dentro de un sandbox de Node (`vm`), sustituyendo las funciones de HTTP Shortcuts (`prompt`, `showSelection`, `sendHttpRequest`…) por mocks. Así se prueba cada flujo sin móvil y sin tocar Notion.

## Seguridad

- El token de Notion vive solo en una variable de HTTP Shortcuts del móvil y en el `.env` del portátil. **Nunca** está en el código.
- La web escucha solo en `127.0.0.1` y tiene contraseña opcional (`APP_PASSWORD`) para el día que se publique.
- La integración de Notion solo tiene acceso a la página Smart Finance.
- La CI falla si detecta algo con pinta de token (`ntn_…`) en el repositorio.

## Hoja de ruta

- [x] Atajo del móvil para gastos, ingresos, transferencias y pagos recurrentes
- [x] Panel web para el portátil
- [x] Contenedor Docker y CI que lo construye y lo prueba
- [ ] Gráfico de evolución del saldo mes a mes
- [ ] Publicarlo gratis (Render) para verlo fuera de casa
- [ ] Usar el panel también en el móvil como PWA

## Autoría

Proyecto personal de Adrián Delgado (2º ASIR, IES Gonzalo Nazareno), desarrollado con ayuda de IA (Claude, de Anthropic). La idea, las decisiones y la puesta en marcha son mías; la IA me ha ayudado a diseñar el modelo de datos y a escribir el código.

Licencia [MIT](LICENSE).
