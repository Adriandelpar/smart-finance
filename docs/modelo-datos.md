# Modelo de datos en Notion

Todo vive dentro de una página de Notion llamada **Smart Finance** con cinco bases de datos relacionadas.

```
                ┌──────────────┐
                │   Cuentas    │◄──────────────┐
                └──────▲───────┘               │
          Cuenta /     │                       │ Cuenta
          Cuenta destino                       │
                ┌──────┴───────┐        ┌──────┴────────┐
                │ Movimientos  │───────►│ Suscripciones │
                └──────┬───────┘  Susc. └───────────────┘
            Categoría  │  Deuda         ┌───────────────┐
                ┌──────▼───────┐ ──────►│    Deudas     │
                │  Categorías  │        └───────────────┘
                └──────────────┘
```

**Movimientos** es la tabla central: cada gasto, ingreso o transferencia es una fila. Las demás tablas calculan sus totales a partir de los movimientos que tienen enlazados.

## Movimientos

| Propiedad | Tipo | Notas |
|---|---|---|
| Concepto | título | "Hamburguesa", "Netflix"… |
| Fecha | fecha | con hora |
| Importe | número (€) | **siempre positivo**; el signo lo decide *Tipo* |
| Tipo | select | Gasto · Ingreso · Transferencia |
| Cuenta | relación → Cuentas | cuenta de origen |
| Cuenta destino | relación → Cuentas | solo en transferencias |
| Categoría | relación → Categorías | |
| Suscripción | relación → Suscripciones | si es un pago recurrente |
| Deuda | relación → Deudas | si es una cuota |
| Monto | fórmula | `if(Tipo == "Ingreso", Importe, -Importe)` |
| Importe este mes | fórmula | `Importe` si la fecha es del mes actual, si no `0` |

## Cuentas

| Propiedad | Tipo | Notas |
|---|---|---|
| Nombre | título | Débito, Efectivo, Bizum / PayPal |
| Tipo | select | Banco · Efectivo · Digital |
| Saldo inicial | número (€) | |
| Activa | checkbox | |
| Σ Movimientos | rollup | suma de `Monto` de sus movimientos |
| Σ Recibido | rollup | suma de `Importe` de transferencias recibidas |
| Saldo | fórmula | `Saldo inicial + Σ Movimientos + Σ Recibido` |

## Categorías

| Propiedad | Tipo | Notas |
|---|---|---|
| Nombre | título | |
| Tipo | select | Gasto · Ingreso |
| Presupuesto mensual | número (€) | opcional |
| Este mes | rollup | suma de `Importe este mes` |
| Total histórico | rollup | suma de `Importe` |
| Restante | fórmula | presupuesto − este mes |
| Uso presupuesto | fórmula | este mes / presupuesto |
| Aviso | fórmula | ⚠️ por encima del 80 %, 🚨 si te pasas |

## Suscripciones

| Propiedad | Tipo | Notas |
|---|---|---|
| Nombre, Importe, Frecuencia (Mensual/Anual), Activa | | |
| Primer cobro | fecha | cualquier cobro pasado; sirve de referencia |
| Cuenta, Categoría | relaciones | se rellenan solas al pagar desde el móvil |
| Siguiente pago | fórmula | avanza meses/años desde *Primer cobro* hasta hoy |
| Días restantes | fórmula | |

## Deudas

| Propiedad | Tipo | Notas |
|---|---|---|
| Nombre, Total deuda, Cuota, Nº cuotas, Primera cuota | | |
| Total pagado / Nº pagos | rollups | sobre los movimientos enlazados |
| Pendiente, Cuotas pagadas, Siguiente pago, Progreso, Días restantes | fórmulas | |

## ¿Por qué rollups y no fórmulas sobre relaciones?

Las fórmulas 2.0 de Notion permiten hacer `prop("Movimientos").map(current.prop("Importe")).sum()`, pero la API de Notion rechaza crearlas (`Type error with formula`). Los rollups hacen lo mismo (es como un `SUM(...) GROUP BY` en SQL) y sí se pueden crear por API, así que el esquema es reproducible.
