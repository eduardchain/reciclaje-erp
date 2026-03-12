"""Utilidades para manejo consistente de fechas de negocio."""
from datetime import datetime, time, timezone
from typing import Annotated, Any

from pydantic import BeforeValidator


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
