"""Datos de ejemplo para el modo demo (cuando no hay NOTION_TOKEN).

Solo lleva los datos "de entrada"; los saldos, próximos pagos y cuotas
pagadas los calcula RepoMemoria igual que harían las fórmulas de Notion.
Genera seis meses de historial para que haya algo que agrupar y comparar.
"""
from datetime import date, datetime

from .repositorio import sumar_meses

# (concepto, importe, tipo, cuenta, categoría, día del mes, extra)
_PLANTILLA = [
    ("Beca prácticas", 300.00, "Ingreso", "c1", "k8", 1, {}),
    ("Spotify", 11.99, "Gasto", "c1", "k5", 3, {"Suscripción": ["s1"]}),
    ("Bonobús", 21.00, "Gasto", "c2", "k3", 4, {}),
    ("Mercadona", 38.72, "Gasto", "c1", "k2", 6, {}),
    ("Retirada cajero", 50.00, "Transferencia", "c1", None, 9, {"Cuenta destino": ["c2"]}),
    ("Gimnasio", 29.90, "Gasto", "c1", "k6", 11, {"Suscripción": ["s2"]}),
    ("Cuota portátil", 62.50, "Gasto", "c1", "k7", 14, {"Deuda": ["d1"]}),
    ("Cena con los de clase", 24.00, "Gasto", "c3", "k1", 16, {}),
    ("Entradas Betis", 45.00, "Gasto", "c1", "k4", 18, {}),
    ("Burger con Pablo", 15.00, "Ingreso", "c3", "k9", 20, {}),
    ("Mercadona", 41.30, "Gasto", "c1", "k2", 23, {}),
    ("Kebab", 7.50, "Gasto", "c2", "k1", 25, {}),
    ("Ratón inalámbrico", 29.99, "Gasto", "c1", "k7", 26, {}),
    ("Hamburguesa", 12.50, "Gasto", "c1", "k1", 28, {}),
]

# Pequeña variación por mes para que no sean todos iguales (determinista)
_VARIACION = [1.00, 0.85, 1.20, 0.95, 1.10, 0.90]
_FIJOS = {"Beca prácticas", "Spotify", "Gimnasio", "Cuota portátil", "Retirada cajero", "Bonobús"}
_SOLO_ALGUNOS_MESES = {"Entradas Betis": {0, 2, 4}, "Ratón inalámbrico": {1}}


def _movimientos(hoy):
    movs = []
    for atras in range(5, -1, -1):          # de hace 5 meses hasta el actual
        inicio = sumar_meses(hoy.replace(day=1), -atras)
        for i, (concepto, importe, tipo, cuenta, cat, dia, extra) in enumerate(_PLANTILLA):
            if concepto in _SOLO_ALGUNOS_MESES and atras not in _SOLO_ALGUNOS_MESES[concepto]:
                continue
            fecha = inicio.replace(day=min(dia, 28))
            if fecha > hoy:
                continue                    # el mes actual solo hasta hoy
            factor = 1 if concepto in _FIJOS else _VARIACION[(atras + i) % len(_VARIACION)]
            m = {
                "id": f"m{atras}-{i}", "emoji": "", "Concepto": concepto,
                "Fecha": datetime(fecha.year, fecha.month, fecha.day, 9 + (i * 5) % 13).isoformat(),
                "Importe": round(importe * factor, 2), "Tipo": tipo,
                "Cuenta": [cuenta], "Cuenta destino": [], "Categoría": [cat] if cat else [],
                "Suscripción": [], "Deuda": [],
            }
            m.update(extra)
            movs.append(m)
    return movs


def datos_iniciales(hoy=None):
    hoy = hoy or date.today()
    hace = lambda meses, dia: sumar_meses(hoy.replace(day=1), -meses).replace(day=dia).isoformat()
    return {
        "cuentas": [
            {"id": "c1", "emoji": "💳", "Nombre": "Débito", "Tipo": "Banco", "Saldo inicial": 1100.0, "Activa": True},
            {"id": "c2", "emoji": "💵", "Nombre": "Efectivo", "Tipo": "Efectivo", "Saldo inicial": 40.0, "Activa": True},
            {"id": "c3", "emoji": "📲", "Nombre": "Bizum / PayPal", "Tipo": "Digital", "Saldo inicial": 90.0, "Activa": True},
        ],
        "categorias": [
            {"id": "k1", "emoji": "🍔", "Nombre": "Comida", "Tipo": "Gasto", "Presupuesto mensual": 60},
            {"id": "k2", "emoji": "🛒", "Nombre": "Supermercado", "Tipo": "Gasto", "Presupuesto mensual": 100},
            {"id": "k3", "emoji": "🚌", "Nombre": "Transporte", "Tipo": "Gasto", "Presupuesto mensual": 25},
            {"id": "k4", "emoji": "🎮", "Nombre": "Ocio", "Tipo": "Gasto", "Presupuesto mensual": 50},
            {"id": "k5", "emoji": "📺", "Nombre": "Suscripciones", "Tipo": "Gasto", "Presupuesto mensual": None},
            {"id": "k6", "emoji": "💪", "Nombre": "Gimnasio y salud", "Tipo": "Gasto", "Presupuesto mensual": 35},
            {"id": "k7", "emoji": "💻", "Nombre": "Tecnología", "Tipo": "Gasto", "Presupuesto mensual": None},
            {"id": "k8", "emoji": "💼", "Nombre": "Nómina / prácticas", "Tipo": "Ingreso", "Presupuesto mensual": None},
            {"id": "k9", "emoji": "🤝", "Nombre": "Bizum recibido", "Tipo": "Ingreso", "Presupuesto mensual": None},
        ],
        "suscripciones": [
            {"id": "s1", "emoji": "", "Nombre": "Spotify", "Importe": 11.99, "Frecuencia": "Mensual",
             "Primer cobro": hace(5, 3), "Cuenta": ["c1"], "Categoría": ["k5"], "Activa": True},
            {"id": "s2", "emoji": "", "Nombre": "Gimnasio", "Importe": 29.90, "Frecuencia": "Mensual",
             "Primer cobro": hace(5, 11), "Cuenta": ["c1"], "Categoría": ["k6"], "Activa": True},
            {"id": "s3", "emoji": "", "Nombre": "Netflix", "Importe": 7.99, "Frecuencia": "Mensual",
             "Primer cobro": hace(2, 5), "Cuenta": ["c1"], "Categoría": ["k5"], "Activa": True},
            {"id": "s4", "emoji": "", "Nombre": "Dominio web", "Importe": 12.00, "Frecuencia": "Anual",
             "Primer cobro": hace(8, 20), "Cuenta": ["c1"], "Categoría": ["k7"], "Activa": True},
        ],
        "deudas": [
            {"id": "d1", "emoji": "", "Nombre": "Portátil", "Total deuda": 750.0, "Cuota": 62.50, "Nº cuotas": 12,
             "Primera cuota": hace(5, 14), "Cuenta": ["c1"], "Categoría": ["k7"]},
        ],
        "movimientos": _movimientos(hoy),
    }
