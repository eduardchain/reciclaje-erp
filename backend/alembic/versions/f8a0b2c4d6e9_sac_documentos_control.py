"""SAC: documentos de control (estibas, tubulares, electrolito a $0)

Plan: docs/planes/plan-sac-documentos-control.md v1.2 §4.1-§4.3.

1. `material_kg_profiles.control_only` (NOT NULL, default false): material
   que se registra solo por el consecutivo. Tabla exclusiva SAC.
2. `inbound_orders.closed_at` / `closed_by` (nullable): auditoria del cierre
   sin valor. El estado `closed` es un valor nuevo de una columna String(16)
   SIN CHECK (ninguna migracion lo creo), asi que no hace falta tocarlo.
3. Tablas `control_dispatches` y `control_dispatch_lines`: Salida de control,
   sin efectos. `created_at`/`updated_at` con `server_default` aca y en el
   modelo (#100). FKs sin nombre: el default de PG, paridad con create_all (#111).

Aditiva pura: una columna con default, dos nullable y dos tablas vacias.
Downgrade: borra las marcas de control, la auditoria del cierre y las
salidas de control. ⚠️ Las Entradas en `closed` quedan con un estado que el
codigo anterior no conoce (lo pinta como Liquidada): antes de bajar, hay que
reabrirlas.

Revision ID: f8a0b2c4d6e9
Revises: e7f9a1b3c5d8
"""
from alembic import op
import sqlalchemy as sa

from app.models.base import GUID

revision = "f8a0b2c4d6e9"
down_revision = "e7f9a1b3c5d8"
branch_labels = None
depends_on = None


def _timestamps():
    return [
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
    ]


def upgrade() -> None:
    op.add_column(
        "material_kg_profiles",
        sa.Column("control_only", sa.Boolean(), server_default=sa.text("false"),
                  nullable=False,
                  comment="Material solo de control: se registra por el consecutivo, sin valor ni efectos"),
    )

    op.add_column(
        "inbound_orders",
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True,
                  comment="Instante real del cierre sin valor (auditoria)"),
    )
    op.add_column("inbound_orders", sa.Column("closed_by", GUID(), nullable=True))
    op.create_foreign_key(
        None, "inbound_orders", "users", ["closed_by"], ["id"], ondelete="SET NULL",
    )

    op.create_table(
        "control_dispatches",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("organization_id", GUID(),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("dispatch_number", sa.Integer(), nullable=False,
                  comment="Consecutivo propio por org (next_number, secuencia control_dispatch_number)"),
        sa.Column("date", sa.DateTime(timezone=True), nullable=False,
                  comment="Fecha de negocio — BusinessDate mediodia UTC via schema"),
        sa.Column("warehouse_id", GUID(),
                  sa.ForeignKey("warehouses.id", ondelete="RESTRICT"), nullable=False,
                  comment="Bodega de donde sale"),
        sa.Column("third_party_id", GUID(),
                  sa.ForeignKey("third_parties.id", ondelete="RESTRICT"), nullable=True,
                  comment="A quien (opcional: no se pregunto que anotan, Q-75)"),
        sa.Column("remission_number", sa.String(50), nullable=False,
                  comment="Remision del MISMO talonario de las Entradas (Q-75)"),
        sa.Column("notes", sa.String(1000), nullable=True),
        sa.Column("status", sa.String(16), server_default="registered", nullable=False,
                  comment="registered | annulled"),
        sa.Column("annulled_reason", sa.String(500), nullable=True),
        sa.Column("annulled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("annulled_by", GUID(),
                  sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_by", GUID(),
                  sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        *_timestamps(),
        sa.UniqueConstraint("organization_id", "dispatch_number",
                            name="uq_control_dispatches_org_number"),
        sa.CheckConstraint("status IN ('registered', 'annulled')",
                           name="ck_control_dispatches_status"),
    )
    op.create_index(
        "ix_control_dispatches_organization_id", "control_dispatches", ["organization_id"],
    )

    op.create_table(
        "control_dispatch_lines",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("organization_id", GUID(),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("dispatch_id", GUID(),
                  sa.ForeignKey("control_dispatches.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("material_id", GUID(),
                  sa.ForeignKey("materials.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("quantity", sa.Numeric(15, 4), nullable=False),
        sa.Column("scale_weight_kg", sa.Numeric(15, 3), nullable=True),
        *_timestamps(),
        sa.UniqueConstraint("dispatch_id", "material_id",
                            name="uq_control_dispatch_lines_dispatch_material"),
        sa.CheckConstraint("quantity > 0", name="ck_control_dispatch_lines_quantity"),
    )
    op.create_index(
        "ix_control_dispatch_lines_organization_id", "control_dispatch_lines",
        ["organization_id"],
    )
    op.create_index(
        "ix_control_dispatch_lines_dispatch_id", "control_dispatch_lines", ["dispatch_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_control_dispatch_lines_dispatch_id", table_name="control_dispatch_lines")
    op.drop_index("ix_control_dispatch_lines_organization_id", table_name="control_dispatch_lines")
    op.drop_table("control_dispatch_lines")
    op.drop_index("ix_control_dispatches_organization_id", table_name="control_dispatches")
    op.drop_table("control_dispatches")
    op.drop_constraint("inbound_orders_closed_by_fkey", "inbound_orders", type_="foreignkey")
    op.drop_column("inbound_orders", "closed_by")
    op.drop_column("inbound_orders", "closed_at")
    op.drop_column("material_kg_profiles", "control_only")
