"""
Modelo MaterialConversionFormula — formulas de conversion Willard (SAC E1, v0.5 §11.1.3).

Tabla maestra de factores por material (uno por material). Append-only siguiendo
el patron puro de decision #35 (PriceList): la vigente es max(created_at, id) por
material_id. Sin valid_from/valid_to. El subtipo escurrido/pinza se elimino
(CC-001): son materiales distintos, cada uno con su factor.

`parameters` valida por formula_type en el schema Pydantic (Anexo D). El tipo se
deriva de la unidad del material (unidad -> battery_to_lead; kg -> drosses_to_lead):
- battery_to_lead: {kg_lead_per_unit, material_reference?}
- drosses_to_lead: {lead_percentage}
"""
from typing import Optional, TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, Index, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, GUID, OrganizationMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.material import Material


class MaterialConversionFormula(Base, OrganizationMixin, TimestampMixin):
    """Formula de conversion material fisico -> kg de plomo equivalente."""

    __tablename__ = "material_conversion_formulas"

    id: Mapped[UUID] = mapped_column(GUID(), primary_key=True, default=uuid4)

    material_id: Mapped[UUID] = mapped_column(
        GUID(),
        ForeignKey("materials.id", ondelete="RESTRICT"),
        nullable=False,
    )

    formula_type: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        comment="battery_to_lead | drosses_to_lead | custom (bloqueado F1) — derivado de la unidad",
    )

    parameters: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        comment="Estructura por formula_type — ver Anexo D del doc v0.5",
    )

    notes: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        comment="Contexto del cambio (ej: renegociacion IPC 2026)",
    )

    created_by: Mapped[UUID] = mapped_column(
        GUID(),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )

    __table_args__ = (
        # Soporta la consulta "formula vigente" por material.
        # ix_mcf_org del doc se omite: OrganizationMixin ya indexa organization_id.
        Index(
            "ix_mcf_material_current",
            "material_id",
            text("created_at DESC"),
        ),
    )

    # --- Relationships ---
    material: Mapped["Material"] = relationship("Material", foreign_keys=[material_id])

    def __repr__(self) -> str:
        return (
            f"<MaterialConversionFormula {self.formula_type} material={self.material_id}>"
        )
