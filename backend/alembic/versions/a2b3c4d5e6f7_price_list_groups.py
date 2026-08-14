"""SAC #98 — Listas de precios por proveedor (item 7 del ciclo Entradas).

Hugo, reunion 12-ago: "cuando yo vaya a liquidarle la compra a ese proveedor,
me llame la lista que le corresponde".

1. price_list_groups — la lista (nombre + activa). UNIQUE(org, name).
2. price_list_group_members — puente lista<->proveedor. UNIQUE(third_party_id)
   hace cumplir en la BASE la regla de Hugo "un tercero pertenece a una sola
   lista" (D2/D14), en vez de confiarlo a una validacion de servicio.
3. price_lists.price_list_group_id — 🔴 TABLA COMPARTIDA (las 7 orgs).

🔴 Por que la columna va DENTRO de price_lists y no en una tabla paralela (D1):
hace la no-regresion **demostrable en vez de verificable**. Con la columna en
NULL en las 3 orgs cliente —su estado el dia del deploy y para siempre, porque
el router de grupos esta gateado por require_org_flag en el BACKEND (D6), no
solo en la pantalla— cualquier consulta a la que se le olvide el filtro sigue
devolviendo exactamente las mismas filas que hoy. Ademas reusa los tres
mecanismos que ya funcionan: append-only, "vigente = el mas reciente por
created_at" (#35) y el historial por material.

Sin backfill: todo lo existente queda NULL = la lista general de siempre.

El indice compuesto mantiene barato el DISTINCT ON de get_all_current_prices /
get_table, que ahora filtran por grupo.

⚠️ NO es una captura del golden: `CAPTURES` (14 entradas) no incluye
/price-lists ni /third-parties — verificado 2026-08-14. El golden se corre igual
porque la regla es "toca tabla compartida, golden es gate", pero la proteccion
real es el NULL de arriba.

FKs sin nombre explicito -> default de PG = paridad con create_all.

Revision ID: a2b3c4d5e6f7
Revises: f8a9b0c1d2e3
Create Date: 2026-08-14
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from app.models.base import GUID

revision: str = "a2b3c4d5e6f7"
down_revision: Union[str, None] = "f8a9b0c1d2e3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── 1. La lista ──
    op.create_table(
        "price_list_groups",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False,
                  comment="Nombre de la lista (ej. 'Lista A', 'Grandes proveedores')"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("organization_id", GUID(),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"),
                  nullable=False, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("organization_id", "name", name="uq_price_list_groups_org_name"),
    )

    # ── 2. Puente lista<->proveedor ──
    # UNIQUE(third_party_id) sin organization_id: un tercero pertenece a UNA org,
    # asi que la unicidad global por tercero ya implica la unicidad por org, y
    # ademas es exactamente la regla de Hugo sin margen de interpretacion.
    op.create_table(
        "price_list_group_members",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("price_list_group_id", GUID(),
                  sa.ForeignKey("price_list_groups.id", ondelete="CASCADE"),
                  nullable=False, index=True),
        sa.Column("third_party_id", GUID(),
                  sa.ForeignKey("third_parties.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("organization_id", GUID(),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"),
                  nullable=False, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("third_party_id", name="uq_price_list_group_members_third_party"),
    )

    # ── 3. 🔴 La columna en la tabla compartida ──
    op.add_column(
        "price_lists",
        sa.Column(
            "price_list_group_id",
            GUID(),
            nullable=True,
            comment="Lista a la que pertenece este precio (NULL = lista general, comportamiento historico)",
        ),
    )
    op.create_foreign_key(
        None, "price_lists", "price_list_groups",
        ["price_list_group_id"], ["id"], ondelete="CASCADE",
    )
    # El DISTINCT ON de precios vigentes ahora discrimina por grupo.
    op.create_index(
        "ix_price_lists_org_group_material_created",
        "price_lists",
        ["organization_id", "price_list_group_id", "material_id",
         sa.text("created_at DESC")],
    )


def downgrade() -> None:
    op.drop_index("ix_price_lists_org_group_material_created", table_name="price_lists")
    op.drop_column("price_lists", "price_list_group_id")
    op.drop_table("price_list_group_members")
    op.drop_table("price_list_groups")
