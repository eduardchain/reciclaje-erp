"""
Modelo MaterialKgProfile — clasificacion SAC del material (plan-sac-recepcion-y-materiales.md, CC-005).

Extension 1:1 OPCIONAL del maestro compartido `materials`, aislada en tabla
SAC-only (flag kg_ledger_enabled). NO se toca `materials` — los otros 3 clientes
en produccion no ven este cambio (plan §3 pto 1, D4/D5).

Clasifica el material en "mundos":
- compra_regular (bool): se muestra en el selector de Compra regular (deriva Purchase).
- willard_world (none | postconsumo | drosses): single-valued (postconsumo XOR
  drosses); los kg de una linea Willard rutean a UNA cuenta segun este tag
  (postconsumo -> willard_baterias por sede; drosses -> willard_drosses org-wide).

`compra_regular` y `willard_world` son ortogonales: una bateria es
(compra_regular=false, willard_world=postconsumo); un material de compra propia es
(compra_regular=true, willard_world=none).
"""
from datetime import datetime
from typing import Optional, TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, GUID, OrganizationMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.material import Material


class MaterialKgProfile(Base, OrganizationMixin, TimestampMixin):
    """Perfil de clasificacion Willard de un material (SAC-only, 1:1 opcional)."""

    __tablename__ = "material_kg_profiles"

    id: Mapped[UUID] = mapped_column(GUID(), primary_key=True, default=uuid4)

    material_id: Mapped[UUID] = mapped_column(
        GUID(),
        ForeignKey("materials.id", ondelete="CASCADE"),
        nullable=False,
    )

    compra_regular: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
        comment="Se muestra en el selector de Compra regular (deriva Purchase)",
    )

    willard_world: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="none",
        server_default="none",
        comment="none | postconsumo | drosses — ruteo de cuenta kg por linea",
    )

    created_by: Mapped[Optional[UUID]] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    __table_args__ = (
        # 1:1 por material dentro de la org (evita MultipleResultsFound, cf #58, D4)
        UniqueConstraint(
            "organization_id", "material_id", name="uq_material_kg_profiles_org_material"
        ),
        # String+CHECK, NO pg_enum (por el schema_parity_check, D4)
        CheckConstraint(
            "willard_world IN ('none', 'postconsumo', 'drosses')",
            name="ck_material_kg_profiles_world",
        ),
        Index("ix_material_kg_profiles_material", "material_id"),
    )

    # --- Relationships ---
    material: Mapped["Material"] = relationship("Material", foreign_keys=[material_id])

    def __repr__(self) -> str:
        return (
            f"<MaterialKgProfile material={self.material_id} "
            f"compra_regular={self.compra_regular} world={self.willard_world}>"
        )
