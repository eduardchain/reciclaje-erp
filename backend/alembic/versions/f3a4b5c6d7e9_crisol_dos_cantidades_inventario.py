"""Correcciones del cierre con SAC (#109): el documento de crisol gana dos
cantidades y mueve inventario.

Tabla EXCLUSIVA de SAC (`crucible_charges`; router tras `require_org_flag`, cero
filas en las orgs cliente). No se toca ninguna tabla compartida: el enlace a la
transformacion vive de ESTE lado a proposito.

1. `lead_kg` Numeric(14,4): kg de PLOMO del evento. Patron `series` de #105 —
   nullable -> UPDATE lead_kg = quantity_kg -> NOT NULL -> CHECK. El backfill es
   EXACTO: en todo documento previo las dos cantidades coinciden (los retornos
   de dross viejos se registraron tomando los kg digitados como plomo).
2. `transformation_id` FK nullable a `material_transformations` + indice (una FK
   en PG no crea indice; el guard de anulacion directa busca por esta columna).
   NULL = documento previo al ciclo: no movio inventario.

Plan: docs/planes/plan-sac-correcciones-cierre-0918.md v1.1 (QA GO).

Revision ID: f3a4b5c6d7e9
Revises: e2f3a4b5c6d7
"""
from alembic import op
import sqlalchemy as sa


revision = "f3a4b5c6d7e9"
down_revision = "e2f3a4b5c6d7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "crucible_charges",
        sa.Column(
            "lead_kg",
            sa.Numeric(14, 4),
            nullable=True,
            comment="Kg de PLOMO del evento (charge: = quantity_kg; dross_return: x factor de la formula)",
        ),
    )
    conn = op.get_bind()
    filled = conn.execute(
        sa.text("UPDATE crucible_charges SET lead_kg = quantity_kg WHERE lead_kg IS NULL")
    ).rowcount
    print(f"[f3a4b5c6d7e9] lead_kg llenado desde quantity_kg en {filled} documento(s) de crisol")
    op.alter_column("crucible_charges", "lead_kg", nullable=False)
    op.create_check_constraint(
        "ck_crucible_charges_lead_kg",
        "crucible_charges",
        "lead_kg > 0 AND lead_kg <= quantity_kg",
    )

    op.add_column(
        "crucible_charges",
        sa.Column(
            "transformation_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("material_transformations.id", ondelete="RESTRICT"),
            nullable=True,
            comment="Transformacion que mueve el inventario de este documento (#109 D4). NULL = documento previo al ciclo",
        ),
    )
    op.create_index(
        "ix_crucible_charges_transformation_id", "crucible_charges", ["transformation_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_crucible_charges_transformation_id", table_name="crucible_charges")
    op.drop_column("crucible_charges", "transformation_id")
    op.drop_constraint("ck_crucible_charges_lead_kg", "crucible_charges", type_="check")
    op.drop_column("crucible_charges", "lead_kg")
