"""
Modelo MaterialConversionFormula — formulas de conversion Willard (SAC E1, v0.5 §11.1.3).

Tabla maestra de factores por material y sub-cuenta Willard (escurrido/pinza
cuando aplica — caso SEC §6.4). Append-only siguiendo el patron puro de
decision #35 (PriceList): la vigente es max(created_at, id) por
(material_id, willard_account_subtype). Sin valid_from/valid_to.

`parameters` valida por formula_type en el schema Pydantic (Anexo D):
- battery_to_lead: {kg_lead_per_unit, material_reference?}
- drosses_to_lead: {lead_percentage}
- scrap_with_terminal_to_lead: {scrap_factor, terminal_weight_kg, material_reference?}
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
        comment="battery_to_lead | drosses_to_lead | scrap_with_terminal_to_lead | custom (bloqueado F1)",
    )

    parameters: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        comment="Estructura por formula_type — ver Anexo D del doc v0.5",
    )

    willard_account_subtype: Mapped[Optional[str]] = mapped_column(
        String(16),
        nullable=True,
        comment="escurrido | pinza — discriminador de FORMULA dentro de Willard Drosses (caso SEC); "
        "NULL para materiales de formula unica",
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
        # Soporta la consulta "formula vigente" por (material, subtype).
        # ix_mcf_org del doc se omite: OrganizationMixin ya indexa organization_id.
        Index(
            "ix_mcf_material_current",
            "material_id",
            "willard_account_subtype",
            text("created_at DESC"),
        ),
    )

    # --- Relationships ---
    material: Mapped["Material"] = relationship("Material", foreign_keys=[material_id])

    def __repr__(self) -> str:
        return (
            f"<MaterialConversionFormula {self.formula_type} material={self.material_id} "
            f"subtype={self.willard_account_subtype}>"
        )
