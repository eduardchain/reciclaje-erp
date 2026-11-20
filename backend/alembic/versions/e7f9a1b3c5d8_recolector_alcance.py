"""SAC: marca de recolector en terceros + alcance de recolector por usuario

Plan: docs/planes/plan-sac-recolector-alcance.md v1.3 §3, §4 y §10.

1. `third_parties.collector_id` (nullable): «este tercero es de ESTE
   recolector» (Green Loop). Tabla COMPARTIDA: NULL en las 7 orgs al subir.
   FK autorreferente con nombre por defecto (#111) y SIN `ondelete` = NO ACTION
   (n1 de QA 2: RESTRICT se chequea fila por fila; NO ACTION al final de la
   sentencia; las dos impiden borrar solo al recolector).
2. Tabla `user_collector_scopes`: un usuario tiene a lo sumo UN alcance por org
   (UNIQUE org+user). Sus tres FKs son RESTRICT (N1): con CASCADE, borrar al
   recolector borraria el alcance y el usuario veria todo (fail-open).
   `created_at` con `server_default` aca y en el modelo (#100).

Aditiva pura: columna NULL y tabla vacia.
Downgrade: borra las marcas y los alcances; al re-subir hay que volver a
marcar (scripts/marcar_recolector.py) y volver a asignar.

Revision ID: e7f9a1b3c5d8
Revises: d6e8f0a2b4c7
"""
from alembic import op
import sqlalchemy as sa

from app.models.base import GUID

revision = "e7f9a1b3c5d8"
down_revision = "d6e8f0a2b4c7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "third_parties",
        sa.Column("collector_id", GUID(), nullable=True),
    )
    op.create_foreign_key(
        None, "third_parties", "third_parties", ["collector_id"], ["id"],
    )
    op.create_index(
        "ix_third_parties_collector_id", "third_parties", ["collector_id"],
    )

    op.create_table(
        "user_collector_scopes",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("organization_id", GUID(),
                  sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
                  nullable=False, index=True),
        sa.Column("user_id", GUID(),
                  sa.ForeignKey("users.id", ondelete="RESTRICT"),
                  nullable=False),
        sa.Column("collector_id", GUID(),
                  sa.ForeignKey("third_parties.id", ondelete="RESTRICT"),
                  nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("organization_id", "user_id",
                            name="uq_user_collector_scopes_org_user"),
    )


def downgrade() -> None:
    op.drop_table("user_collector_scopes")
    op.drop_index("ix_third_parties_collector_id", table_name="third_parties")
    op.drop_column("third_parties", "collector_id")
