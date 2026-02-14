"""
Modelo ExpenseCategory — Categorias de gastos para tesoreria.

Permite clasificar gastos en:
- Directos: asociados directamente a una compra o material (ej: flete, pesaje)
- Indirectos: gastos administrativos y operativos (ej: servicios, arriendo)

Esta distincion es fundamental para:
- Calcular el costo real del material (gastos directos se suman al costo)
- Analizar rentabilidad por linea de negocio (prorrateo de indirectos)
- Generar reportes de P&L precisos
"""
from uuid import UUID, uuid4
from typing import Optional

from sqlalchemy import String, Boolean
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin, OrganizationMixin, GUID


class ExpenseCategory(Base, TimestampMixin, OrganizationMixin):
    """
    Categoria de gasto para clasificacion en tesoreria.

    El campo is_direct_expense distingue entre gastos directos
    (afectan costo de material) e indirectos (gastos generales).
    """

    __tablename__ = "expense_categories"

    id: Mapped[UUID] = mapped_column(
        GUID(),
        primary_key=True,
        default=uuid4,
    )

    name: Mapped[str] = mapped_column(
        String(255), nullable=False, index=True,
    )

    description: Mapped[Optional[str]] = mapped_column(
        String(500), nullable=True,
    )

    is_direct_expense: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="True = gasto directo (afecta costo material). False = gasto indirecto (administrativo).",
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False,
    )

    def __repr__(self) -> str:
        tipo = "directo" if self.is_direct_expense else "indirecto"
        return f"<ExpenseCategory(id={self.id}, name='{self.name}', tipo={tipo})>"
