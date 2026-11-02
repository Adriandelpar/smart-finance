"""Qué campos tiene cada entidad y de qué tipo son.

Es la "fuente de verdad" que usan:
  - el repositorio de Notion, para traducir a/desde el JSON de la API,
  - el repositorio en memoria (modo demo),
  - los formularios y tablas genéricas de la web.

Los nombres de campo son exactamente los nombres de las propiedades en Notion.
"""
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Campo:
    nombre: str
    tipo: str                 # title | number | select | date | datetime | checkbox | relation
    opciones: tuple = ()      # para select
    destino: str = ""         # para relation: entidad a la que apunta
    obligatorio: bool = False
    ayuda: str = ""


@dataclass(frozen=True)
class Entidad:
    clave: str                # cuentas, categorias...
    singular: str
    plural: str
    campos: tuple
    calculados: tuple = field(default=())   # solo lectura (fórmulas y rollups de Notion)
    con_emoji: bool = False

    @property
    def titulo(self):
        return next(c.nombre for c in self.campos if c.tipo == "title")

    def campo(self, nombre):
        return next(c for c in self.campos if c.nombre == nombre)


CUENTAS = Entidad(
    "cuentas", "cuenta", "Cuentas",
    campos=(
        Campo("Nombre", "title", obligatorio=True),
        Campo("Tipo", "select", ("Banco", "Efectivo", "Digital")),
        Campo("Saldo inicial", "number", ayuda="Lo que tenía la cuenta antes de empezar a apuntar movimientos."),
        Campo("Activa", "checkbox"),
    ),
    calculados=("Saldo",),
    con_emoji=True,
)

CATEGORIAS = Entidad(
    "categorias", "categoría", "Categorías",
    campos=(
        Campo("Nombre", "title", obligatorio=True),
        Campo("Tipo", "select", ("Gasto", "Ingreso"), obligatorio=True),
        Campo("Presupuesto mensual", "number", ayuda="Déjalo vacío si no quieres límite."),
    ),
    con_emoji=True,
)

SUSCRIPCIONES = Entidad(
    "suscripciones", "suscripción", "Suscripciones",
    campos=(
        Campo("Nombre", "title", obligatorio=True),
        Campo("Importe", "number", obligatorio=True),
        Campo("Frecuencia", "select", ("Mensual", "Anual"), obligatorio=True),
        Campo("Primer cobro", "date", obligatorio=True,
              ayuda="La fecha de cualquier cobro ya hecho. Con ella se calcula el siguiente."),
        Campo("Cuenta", "relation", destino="cuentas"),
        Campo("Categoría", "relation", destino="categorias"),
        Campo("Activa", "checkbox"),
    ),
    calculados=("Siguiente pago", "Días restantes"),
)

DEUDAS = Entidad(
    "deudas", "deuda", "Deudas",
    campos=(
        Campo("Nombre", "title", obligatorio=True),
        Campo("Total deuda", "number", obligatorio=True),
        Campo("Cuota", "number", obligatorio=True),
        Campo("Nº cuotas", "number", obligatorio=True),
        Campo("Primera cuota", "date", obligatorio=True),
        Campo("Cuenta", "relation", destino="cuentas"),
        Campo("Categoría", "relation", destino="categorias"),
    ),
    calculados=("Total pagado", "Nº pagos", "Pendiente", "Siguiente pago", "Días restantes"),
)

MOVIMIENTOS = Entidad(
    "movimientos", "movimiento", "Movimientos",
    campos=(
        Campo("Concepto", "title", obligatorio=True),
        Campo("Fecha", "datetime", obligatorio=True),
        Campo("Importe", "number", obligatorio=True, ayuda="Siempre en positivo: el tipo dice si suma o resta."),
        Campo("Tipo", "select", ("Gasto", "Ingreso", "Transferencia"), obligatorio=True),
        Campo("Cuenta", "relation", destino="cuentas", obligatorio=True),
        Campo("Cuenta destino", "relation", destino="cuentas", ayuda="Solo en transferencias."),
        Campo("Categoría", "relation", destino="categorias"),
        Campo("Suscripción", "relation", destino="suscripciones"),
        Campo("Deuda", "relation", destino="deudas"),
    ),
)

ENTIDADES = {e.clave: e for e in (CUENTAS, CATEGORIAS, SUSCRIPCIONES, DEUDAS, MOVIMIENTOS)}

# Las que se gestionan con el formulario genérico (movimientos tiene página propia)
GESTIONABLES = ("cuentas", "categorias", "suscripciones", "deudas")
