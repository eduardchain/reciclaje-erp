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

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, Integer, String, UniqueConstraint, text
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

    lead_product: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="none",
        server_default="none",
        comment=(
            "none | crudo | puro — plomo entregable a Willard. Reemplaza la "
            "heuristica 'sin formula = es plomo', que servia para CALCULAR y se "
            "usaba para CLASIFICAR (con ella el plastico saldaba la deuda 1:1)."
        ),
    )

    # Renglon del formato en papel «Materiales recolectados» (pedido de Johana,
    # 19-nov). NULL = el material no esta en el formato. Se escribe SOLO por
    # PUT /material-kg-profiles/form-order (lista completa, REPLACE): el upsert
    # del perfil no lo conoce, asi que no lo puede borrar (#103 D4).
    form_order: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Renglon del formato en papel «Materiales recolectados» (NULL = no esta en el formato)",
    )

    # Documentos de control (plan-sac-documentos-control §4.1): material que
    # entra o sale SOLO por el consecutivo (estibas, tubulares, electrolito) —
    # no se liquida, no toca inventario, kg ni saldos. Se escribe SOLO por
    # PUT /material-kg-profiles/{id}/control: el upsert del perfil no la
    # conoce, asi que no la puede borrar (#103 D4). Exige willard_world y
    # lead_product en 'none' (coherencia en las dos direcciones, #112 D4d).
    control_only: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
        comment="Material solo de control: se registra por el consecutivo, sin valor ni efectos",
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
        CheckConstraint(
            "lead_product IN ('none', 'crudo', 'puro')",
            name="ck_material_kg_profiles_lead_product",
        ),
        Index("ix_material_kg_profiles_material", "material_id"),
        # Dos materiales no comparten renglon. Declarado tambien aca (y no solo
        # en la migracion) para que el parity check no de DIFF (F8, #98).
        Index(
            "uq_material_kg_profiles_org_form_order",
            "organization_id",
            "form_order",
            unique=True,
            postgresql_where=text("form_order IS NOT NULL"),
        ),
    )

    # --- Relationships ---
    material: Mapped["Material"] = relationship("Material", foreign_keys=[material_id])

    def __repr__(self) -> str:
        return (
            f"<MaterialKgProfile material={self.material_id} "
            f"compra_regular={self.compra_regular} world={self.willard_world} "
            f"lead={self.lead_product}>"
        )
