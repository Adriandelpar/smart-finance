# Smart Finance

![CI](https://github.com/Adriandelpar/smart-finance/actions/workflows/ci.yml/badge.svg)

Gestor de gastos personal. Registro cada gasto en segundos desde un botón del centro de control del móvil, y en Notion tengo el control de cuentas, gasto por categoría con presupuesto, suscripciones y deudas.

## Arquitectura

```
┌─────────────────────────┐        HTTPS + Bearer token        ┌──────────────────────────┐
│  Android (HyperOS)      │  ───────────────────────────────►  │   API REST de Notion     │
│  HTTP Shortcuts         │   POST /databases/{id}/query       │                          │
│  └─ src/finanzas.js     │   POST /pages                      │  Bases de datos:         │
│     (cliente)           │   GET  /pages/{id}                 │  Movimientos, Cuentas,   │
└─────────────────────────┘  ◄───────────────────────────────  │  Categorías,             │
                                     JSON                      │  Suscripciones, Deudas   │
                                                               └──────────────────────────┘
```

- **Notion es el backend.** Guarda los datos y calcula todo con fórmulas y rollups: saldos, gasto del mes por categoría, próximo pago de cada suscripción, cuotas pendientes de cada deuda. Ver el [modelo de datos](docs/modelo-datos.md).
- **El móvil es solo un cliente.** Un script en JavaScript que se ejecuta en [HTTP Shortcuts](https://http-shortcuts.rmy.ch/). Primero *lee* cuentas, categorías, suscripciones y deudas para montar los menús, y luego *crea* el movimiento. No hay nada cableado: si añado una cuenta en Notion, aparece sola en el móvil.

## Qué hace

Al pulsar el botón **Finanzas**:

1. ¿Qué quieres registrar? → gasto, ingreso o transferencia
2. Gasto **único** → concepto, importe, cuenta, categoría
3. Gasto **recurrente** → elige una suscripción o una deuda; sugiere el importe y rellena cuenta y categoría
4. Guarda en Notion y muestra el saldo actualizado de la cuenta

Cancelar cualquier pregunta no guarda nada. Los importes aceptan coma decimal (`12,50`).

## Estructura

```
src/finanzas.js            Script del atajo (HTTP Shortcuts)
tests/finanzas.test.js     Tests con la app y la API de Notion simuladas
docs/modelo-datos.md       Esquema de las bases de datos de Notion
docs/instalacion-android.md Puesta en marcha en el móvil
.github/workflows/ci.yml   Sintaxis + tests + detección de tokens en cada push
```

## Desarrollo

```bash
npm test        # 8 tests, sin dependencias (node:test)
npm run lint    # comprobación de sintaxis
```

Los tests ejecutan el script real dentro de un sandbox de Node (`vm`), sustituyendo las funciones de HTTP Shortcuts (`prompt`, `showSelection`, `sendHttpRequest`…) por mocks. Así se prueba cada flujo sin móvil y sin tocar Notion.

## Seguridad

- El token de Notion vive solo en una variable de HTTP Shortcuts del móvil. **Nunca** está en el código.
- La integración de Notion solo tiene acceso a la página Smart Finance.
- La CI falla si detecta algo con pinta de token (`ntn_…`) en el repositorio.

## Hoja de ruta

- [ ] Dashboard web para el portátil (lectura rápida y esquemática de los datos)
- [ ] Contenerizarlo (Dockerfile + docker-compose)
- [ ] Despliegue automático en mi VPS con GitHub Actions
- [ ] Usar el dashboard también en el móvil como PWA, con una interfaz propia

## Autoría

Proyecto personal de Adrián Delgado (2º ASIR, IES Gonzalo Nazareno), desarrollado con ayuda de IA (Claude, de Anthropic). La idea, las decisiones y la puesta en marcha son mías; la IA me ha ayudado a diseñar el modelo de datos y a escribir el código.

Licencia [MIT](LICENSE).
