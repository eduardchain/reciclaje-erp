"""SAC recepcion+materiales: drop willard_account_subtype + material_kg_profiles

Plegado al working tree de E2 (plan-sac-recepcion-y-materiales.md, CC-001/004/005):
- Forward-drop de willard_account_subtype (fórmulas + inbound_orders) — CC-001:
  escurrido/pinza son materiales distintos, no un subtipo.
- Recrea ix_mcf_material_current a 2 columnas (material_id, created_at DESC).
- Crea material_kg_profiles (clasificacion Willard SAC-only, 1:1 opcional, CC-005).

No reescribe historia: E1 (b5c8e1a2f3d4) creo las columnas y corrio en dev+QA
(NUNCA prod — flag NULL). Esta migracion forward-dropea. Prod nunca tuvo E1/E2.

Revision ID: b1c2d3e4f5a6
Revises: f9a2b3c4d5e6
Create Date: 2026-07-16
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "b1c2d3e4f5a6"
down_revision: Union[str, None] = "f9a2b3c4d5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- 1. material_conversion_formulas: drop subtype + recrear indice 2-col ---
    op.drop_index("ix_mcf_material_current", table_name="material_conversion_formulas")
    op.drop_column("material_conversion_formulas", "willard_account_subtype")
    op.create_index(
        "ix_mcf_material_current",
        "material_conversion_formulas",
        ["material_id", sa.text("created_at DESC")],
        unique=False,
    )

    # --- 2. inbound_orders: drop subtype (colapso 4->2, CC-004) ---
    op.drop_column("inbound_orders", "willard_account_subtype")

    # --- 3. material_kg_profiles (SAC-only, 1:1 opcional, CC-005) ---
    op.create_table(
        "material_kg_profiles",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("material_id", sa.UUID(), nullable=False),
        sa.Column(
            "compra_regular", sa.Boolean(), nullable=False, server_default=sa.text("false"),
            comment="Se muestra en el selector de Compra regular (deriva Purchase)",
        ),
        sa.Column(
            "willard_world", sa.String(length=16), nullable=False, server_default="none",
            comment="none | postconsumo | drosses — ruteo de cuenta kg por linea",
        ),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.CheckConstraint(
            "willard_world IN ('none', 'postconsumo', 'drosses')",
            name="ck_material_kg_profiles_world",
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["material_id"], ["materials.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id", "material_id", name="uq_material_kg_profiles_org_material"
        ),
    )
    op.create_index(
        "ix_material_kg_profiles_organization_id", "material_kg_profiles",
        ["organization_id"], unique=False,
    )
    op.create_index(
        "ix_material_kg_profiles_material", "material_kg_profiles",
        ["material_id"], unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_material_kg_profiles_material", table_name="material_kg_profiles")
    op.drop_index("ix_material_kg_profiles_organization_id", table_name="material_kg_profiles")
    op.drop_table("material_kg_profiles")

    op.add_column(
        "inbound_orders",
        sa.Column("willard_account_subtype", sa.String(length=16), nullable=True,
                  comment="escurrido | pinza — obligatorio si el material es SEC (v0.5 §6.4)"),
    )

    op.drop_index("ix_mcf_material_current", table_name="material_conversion_formulas")
    op.add_column(
        "material_conversion_formulas",
        sa.Column("willard_account_subtype", sa.String(length=16), nullable=True,
                  comment="escurrido | pinza — discriminador de FORMULA dentro de Willard Drosses (caso SEC); "
                          "NULL para materiales de formula unica"),
    )
    op.create_index(
        "ix_mcf_material_current",
        "material_conversion_formulas",
        ["material_id", "willard_account_subtype", sa.text("created_at DESC")],
        unique=False,
    )
