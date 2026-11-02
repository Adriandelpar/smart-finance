"""Datos de ejemplo para el modo demo (cuando no hay NOTION_TOKEN).

Tienen la misma forma que lo que devuelve notion.py ya "aplanado",
así el resto de la app no sabe si los datos son reales o de demo.
"""
from datetime import date, datetime, timedelta


def _dentro(dias):
    return (date.today() + timedelta(days=dias)).isoformat()

# (concepto, importe, tipo, cuenta, categoría, extra)
_PLANTILLA = [
    ("Beca prácticas", 300.00, "Ingreso", "c1", "k8", {}),
    ("Spotify", 11.99, "Gasto", "c1", "k5", {"Suscripción": ["s1"]}),
    ("Bonobús", 21.00, "Gasto", "c2", "k3", {}),
    ("Mercadona", 38.72, "Gasto", "c1", "k2", {}),
    ("Retirada cajero", 50.00, "Transferencia", "c1", None, {"Cuenta destino": ["c2"]}),
    ("Gimnasio", 29.90, "Gasto", "c1", "k6", {"Suscripción": ["s2"]}),
    ("Cuota portátil", 62.50, "Gasto", "c1", "k7", {"Deuda": ["d1"]}),
    ("Cena con los de clase", 24.00, "Gasto", "c3", "k1", {}),
    ("Entradas Betis", 45.00, "Gasto", "c1", "k4", {}),
    ("Burger con Pablo", 15.00, "Ingreso", "c3", "k9", {}),
    ("Mercadona", 41.30, "Gasto", "c1", "k2", {}),
    ("Ratón inalámbrico", 29.99, "Gasto", "c1", "k7", {}),
    ("Kebab", 7.50, "Gasto", "c2", "k1", {}),
    ("Hamburguesa", 12.50, "Gasto", "c1", "k1", {}),
]


def _repartir(inicio, dias, plantilla, prefijo):
    """Reparte los movimientos de la plantilla a lo largo de `dias` días desde `inicio`."""
    movs = []
    n = len(plantilla)
    for i, (concepto, importe, tipo, cuenta, cat, extra) in enumerate(plantilla):
        dia = inicio + timedelta(days=(i * max(dias - 1, 0)) // max(n - 1, 1))
        fecha = datetime(dia.year, dia.month, dia.day, 9 + (i * 5) % 13)
        m = {"id": f"{prefijo}{i}", "Concepto": concepto, "Fecha": fecha.isoformat(), "Importe": importe,
             "Tipo": tipo, "Cuenta": [cuenta], "Categoría": [cat] if cat else []}
        m.update(extra)
        movs.append(m)
    return movs


def _movimientos(hoy):
    inicio_mes = hoy.replace(day=1)
    fin_anterior = inicio_mes - timedelta(days=1)
    inicio_anterior = fin_anterior.replace(day=1)
    # mes anterior completo + lo que va de mes (como mínimo los primeros movimientos)
    actuales = _PLANTILLA[: max(4, min(len(_PLANTILLA), hoy.day // 2 + 3))]
    return (_repartir(inicio_mes, hoy.day, actuales, "a")
            + _repartir(inicio_anterior, fin_anterior.day, _PLANTILLA, "p"))


def obtener():
    hoy = date.today()
    return {
        "cuentas": [
            {"id": "c1", "emoji": "💳", "Nombre": "Débito", "Tipo": "Banco", "Saldo": 1243.18, "Activa": True},
            {"id": "c2", "emoji": "💵", "Nombre": "Efectivo", "Tipo": "Efectivo", "Saldo": 85.40, "Activa": True},
            {"id": "c3", "emoji": "📲", "Nombre": "Bizum / PayPal", "Tipo": "Digital", "Saldo": 32.75, "Activa": True},
        ],
        "categorias": [
            {"id": "k1", "emoji": "🍔", "Nombre": "Comida", "Tipo": "Gasto", "Presupuesto mensual": 150},
            {"id": "k2", "emoji": "🛒", "Nombre": "Supermercado", "Tipo": "Gasto", "Presupuesto mensual": 120},
            {"id": "k3", "emoji": "🚌", "Nombre": "Transporte", "Tipo": "Gasto", "Presupuesto mensual": 40},
            {"id": "k4", "emoji": "🎮", "Nombre": "Ocio", "Tipo": "Gasto", "Presupuesto mensual": 60},
            {"id": "k5", "emoji": "📺", "Nombre": "Suscripciones", "Tipo": "Gasto", "Presupuesto mensual": None},
            {"id": "k6", "emoji": "💪", "Nombre": "Gimnasio y salud", "Tipo": "Gasto", "Presupuesto mensual": 35},
            {"id": "k7", "emoji": "💻", "Nombre": "Tecnología", "Tipo": "Gasto", "Presupuesto mensual": None},
            {"id": "k8", "emoji": "💼", "Nombre": "Nómina / prácticas", "Tipo": "Ingreso", "Presupuesto mensual": None},
            {"id": "k9", "emoji": "🤝", "Nombre": "Bizum recibido", "Tipo": "Ingreso", "Presupuesto mensual": None},
        ],
        "movimientos": _movimientos(hoy),
        "suscripciones": [
            {"id": "s1", "Nombre": "Spotify", "Importe": 11.99, "Frecuencia": "Mensual", "Activa": True, "Siguiente pago": _dentro(27), "Días restantes": 27},
            {"id": "s2", "Nombre": "Gimnasio", "Importe": 29.90, "Frecuencia": "Mensual", "Activa": True, "Siguiente pago": _dentro(19), "Días restantes": 19},
            {"id": "s3", "Nombre": "Netflix", "Importe": 7.99, "Frecuencia": "Mensual", "Activa": True, "Siguiente pago": _dentro(3), "Días restantes": 3},
            {"id": "s4", "Nombre": "Dominio adriandelpar.com", "Importe": 12.00, "Frecuencia": "Anual", "Activa": True, "Siguiente pago": _dentro(140), "Días restantes": 140},
        ],
        "deudas": [
            {"id": "d1", "Nombre": "Portátil MSI", "Total deuda": 750.0, "Cuota": 62.50, "Nº cuotas": 12, "Total pagado": 312.50, "Pendiente": 437.50, "Nº pagos": 5, "Siguiente pago": _dentro(19), "Días restantes": 19},
        ],
        "generado": datetime.now().isoformat(),
        "mes": hoy.strftime("%Y-%m"),
    }
