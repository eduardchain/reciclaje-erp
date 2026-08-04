"""
Maestros minimos Driver y Vehicle (SAC E1, v0.5 §11.1.14).

Catalogos simples para InboundOrder, rutas de recoleccion y flete BOG-BAQ
(en Fase 2 los usa el movil del conductor). Los hornos NO necesitan maestro
propio en Fase 1 (los representan sus KgLedgerAccount intra_horno/crisol).

Unicidad de placa: en SERVICIO, no en BD (D14 del plan E1) — patron del repo
para maestros con soft delete (materials, warehouses, money_accounts): se
valida duplicado ACTIVO y se permite reusar la placa de un vehiculo inactivo.
"""
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, GUID, OrganizationMixin, TimestampMixin


class Driver(Base, OrganizationMixin, TimestampMixin):
    """Conductor (maestro minimo)."""

    __tablename__ = "drivers"

    id: Mapped[UUID] = mapped_column(GUID(), primary_key=True, default=uuid4)

    name: Mapped[str] = mapped_column(String(150), nullable=False)

    document_id: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)

    phone: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    def __repr__(self) -> str:
        return f"<Driver {self.name}>"


class Vehicle(Base, OrganizationMixin, TimestampMixin):
    """Vehiculo (maestro minimo)."""

    __tablename__ = "vehicles"

    id: Mapped[UUID] = mapped_column(GUID(), primary_key=True, default=uuid4)

    plate: Mapped[str] = mapped_column(
        String(15),
        nullable=False,
        comment="Unicidad de placa ACTIVA validada en servicio (D14) — sin UNIQUE en BD",
    )

    display_name: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)

    vehicle_type: Mapped[Optional[str]] = mapped_column(
        String(16),
        nullable=True,
        comment="camion | montacargas | otro",
    )

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    def __repr__(self) -> str:
        return f"<Vehicle {self.plate}>"
