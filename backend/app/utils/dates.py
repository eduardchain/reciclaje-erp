"""Utilidades para manejo consistente de fechas de negocio."""
from datetime import date as _date, datetime, time, timezone
from typing import Annotated, Any
from zoneinfo import ZoneInfo

from pydantic import BeforeValidator

# El negocio ocurre en Colombia. El dia habil es el colombiano, SIEMPRE —
# aunque el servidor guarde instantes en UTC.
BOGOTA = ZoneInfo("America/Bogota")


def business_today() -> _date:
    """El dia de negocio de HOY (Colombia).

    ⚠️ ESTA es la unica forma correcta de preguntar "que dia es hoy" cuando la
    respuesta va a fecharse en un registro. NUNCA `datetime.now(timezone.utc).date()`
    ni `date.today()`.

    Entre las 00:00 y 05:00 UTC (19:00-24:00 en Colombia) el dia UTC ya es el
    siguiente. Usar el reloj UTC ahi hace que un hecho de hoy quede fechado
    MAÑANA, y como varias de esas fechas son FRONTERA de reportes (cortes
    as-of, filtros de periodo), el corte del dia real no ve el hecho — de
    forma permanente, no solo esa noche.

    `date.today()` da el dia colombiano solo porque el servidor corre en
    Bogota; es correcto por accidente de despliegue y ademas rompe contra los
    tests, que arman fechas en UTC. Este helper lo hace explicito.

    Para timestamps de AUDITORIA (`created_at`, `annulled_at`, `applied_at`) y
    para comparaciones de ORDEN de eventos (guards LIFO) el reloj correcto
    sigue siendo `datetime.now(timezone.utc)`: son instantes reales, no dias.
    """
    return datetime.now(BOGOTA).date()


def business_today_noon() -> datetime:
    """El dia de negocio de HOY, normalizado a mediodia UTC (`BusinessDate`).

    La version datetime de `business_today()`, para los campos que guardan
    fecha de negocio como datetime (`MoneyMovement.date`, `InventoryMovement.date`,
    `FixedAsset.disposed_at`...). Ver esa docstring para el porque del reloj.
    """
    return datetime.combine(business_today(), time(12, 0), tzinfo=timezone.utc)


def normalize_business_date(value: Any) -> datetime:
    """Normaliza fechas de negocio a mediodia UTC (12:00).
    Garantiza display correcto en cualquier timezone UTC-12 a UTC+12."""
    if value is None:
        return None
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            value = datetime.strptime(value[:10], "%Y-%m-%d")
    if hasattr(value, "date"):
        d = value.date()
    else:
        d = value  # ya es date
    return datetime.combine(d, time(12, 0), tzinfo=timezone.utc)


BusinessDate = Annotated[datetime, BeforeValidator(normalize_business_date)]
