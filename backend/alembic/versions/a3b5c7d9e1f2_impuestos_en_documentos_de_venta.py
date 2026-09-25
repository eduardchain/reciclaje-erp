"""IVA y retenciones en lo que SAC factura (CC-013 / Q-41)

Tres cosas:

1. `document_taxes` — tabla nueva, exclusiva del flujo de impuestos. Vacia para
   TODA organizacion hasta que alguien capture el primer impuesto.

2. `third_party_categories.system_code` — columna **sobre una tabla COMPARTIDA
   por las siete organizaciones**. Nace nullable y sin sembrado, asi que en las
   seis que no son SAC queda NULL en todas las filas y el predicado de
   clasificacion da False en todas: la no-regresion es demostrable por
   construccion (patron D1 de #94 y #98), no verificable caso por caso.
   El indice unico es PARCIAL sobre `system_code IS NOT NULL`, o sea que no
   toca ninguna fila existente (A1 de QA: la unicidad no se documenta, se hace
   imposible — #58 la dejo escrita como advertencia y ahi quedo).

3. `retention_configs.base_kind` — con `server_default='subtotal'`, que es
   exactamente lo que hacen hoy las dos pantallas de compras. COMPRAS QUEDA
   BYTE A BYTE (D5).

⚠️ `created_at`/`updated_at` llevan `server_default=now()` porque
`TimestampMixin` lo tiene: la base de test nace de los modelos y la de
produccion de las migraciones, y `schema_parity_check.py` excluye
`server_default` a proposito — o sea que la direccion "el modelo lo tiene, la
migracion no" NO la ve ningun gate y se manifiesta como un 500 en el primer
POST contra la base migrada (leccion de #100).

Revision ID: a3b5c7d9e1f2
Revises: e8f0a2b4c6d9
"""
from alembic import op
import sqlalchemy as sa

from app.models.base import GUID

revision = "a3b5c7d9e1f2"
down_revision = "e8f0a2b4c6d9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # 1. document_taxes
    # ------------------------------------------------------------------
    op.create_table(
        "document_taxes",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("organization_id", GUID(), nullable=False),
        sa.Column("sale_id", GUID(), nullable=True),
        sa.Column("willard_delivery_id", GUID(), nullable=True),
        sa.Column("third_party_id", GUID(), nullable=False),
        sa.Column("tax_type", sa.String(16), nullable=False),
        sa.Column("municipality", sa.String(60), nullable=True),
        sa.Column("concept", sa.String(60), nullable=True),
        sa.Column("rate", sa.Numeric(7, 4), nullable=True),
        sa.Column("base_amount", sa.Numeric(15, 2), nullable=False),
        sa.Column("amount", sa.Numeric(15, 2), nullable=False),
        sa.Column("reverted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        # ⚠️ FKs SIN nombre explicito, a proposito: `create_all` — de donde nace
        # la base de test — deja que PG las nombre, y una migracion que las
        # bautiza distinto abre una divergencia permanente que caza el parity
        # check (#111).
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["sale_id"], ["sales.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["willard_delivery_id"], ["willard_deliveries.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["third_party_id"], ["third_parties.id"], ondelete="RESTRICT"),
        sa.CheckConstraint(
            "(sale_id IS NOT NULL)::int + (willard_delivery_id IS NOT NULL)::int = 1",
            name="ck_document_taxes_single_owner",
        ),
        sa.CheckConstraint("amount > 0", name="ck_document_taxes_amount_positive"),
        sa.CheckConstraint(
            "tax_type IN ('iva', 'retefuente', 'reteiva', 'ica')",
            name="ck_document_taxes_type",
        ),
        sa.CheckConstraint(
            "(tax_type = 'ica') = (municipality IS NOT NULL)",
            name="ck_document_taxes_ica_municipality",
        ),
    )
    op.create_index("ix_document_taxes_sale", "document_taxes", ["sale_id"])
    op.create_index("ix_document_taxes_delivery", "document_taxes", ["willard_delivery_id"])
    op.create_index(
        "ix_document_taxes_organization_id", "document_taxes", ["organization_id"]
    )

    # ------------------------------------------------------------------
    # 2. third_party_categories.system_code  (TABLA COMPARTIDA)
    # ------------------------------------------------------------------
    op.add_column(
        "third_party_categories",
        sa.Column(
            "system_code",
            sa.String(30),
            nullable=True,
            comment="Codigo estable de categoria de sistema. NULL = categoria normal (CC-013 D4b)",
        ),
    )
    op.create_index(
        "uq_third_party_categories_system_code",
        "third_party_categories",
        ["organization_id", "system_code"],
        unique=True,
        postgresql_where=sa.text("system_code IS NOT NULL"),
    )

    # ------------------------------------------------------------------
    # 3. retention_configs.base_kind
    # ------------------------------------------------------------------
    op.add_column(
        "retention_configs",
        sa.Column(
            "base_kind",
            sa.String(16),
            nullable=False,
            server_default=sa.text("'subtotal'"),
            comment="subtotal | iva — sobre que se aplica la tasa (CC-013 D5)",
        ),
    )
    op.create_check_constraint(
        "ck_retention_configs_base_kind",
        "retention_configs",
        "base_kind IN ('subtotal', 'iva')",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_retention_configs_base_kind", "retention_configs", type_="check"
    )
    op.drop_column("retention_configs", "base_kind")

    op.drop_index("uq_third_party_categories_system_code", table_name="third_party_categories")
    op.drop_column("third_party_categories", "system_code")

    op.drop_index("ix_document_taxes_organization_id", table_name="document_taxes")
    op.drop_index("ix_document_taxes_delivery", table_name="document_taxes")
    op.drop_index("ix_document_taxes_sale", table_name="document_taxes")
    op.drop_table("document_taxes")
