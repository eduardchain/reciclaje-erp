"""Ciclo de planta (#107): etapas horno|crisol dentro de intersede, documentos de
crisol, diferencial del crisol y sede de facturacion en las Salidas de Plomo.

Tres tablas, las tres EXCLUSIVAS de SAC (routers tras `require_org_flag`;
cero filas en las orgs cliente):

1. `kg_ledger_movements.stage` (horno | crisol, nullable) + CHECK. Backfill:
   todo movimiento de una cuenta `intersede` existente es plomo CRUDO
   (`intersede_send` del traslado y descargas de Salidas) -> 'horno'. La regla
   "intersede exige etapa / las demas no" vive en el escritor unico del
   servicio (D1), no en un CHECK: cruza tablas.
2. `crucible_charges` (tabla de E1 sin servicio, vacia en todas las orgs):
   consecutivo, bodega (planta), notas, monto del par de maquila del retorno de
   dross, UNIQUE(org, numero) y CHECKs de tipo/estado. GATE DE DATOS: si la
   tabla tuviera filas (no deberia: nunca tuvo escritor) la migracion se detiene
   con RuntimeError en vez de inventarles numero y bodega (patron #106 D5).
3. `willard_deliveries.crucible_amount` (diferencial $300/kg de puro vendido,
   D4) y `billing_warehouse_id` (sede que factura, estampada al liquidar, Q-30
   D5).

Plan: docs/planes/plan-sac-ciclo-planta-crisol.md v1.1 (QA GO).

Revision ID: e2f3a4b5c6d7
Revises: d1e2f3a4b5c6
"""
from alembic import op
import sqlalchemy as sa


revision = "e2f3a4b5c6d7"
down_revision = "d1e2f3a4b5c6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()

    # 1. Etapa dentro de intersede
    op.add_column(
        "kg_ledger_movements",
        sa.Column(
            "stage",
            sa.String(10),
            nullable=True,
            comment=(
                "Etapa DENTRO de la cuenta intersede (#107 D1): horno | crisol. "
                "Obligatoria en intersede, NULL en las demas — la regla vive en "
                "services/kg_ledger.add_kg_movement, el UNICO escritor del libro"
            ),
        ),
    )
    op.create_check_constraint(
        "ck_kg_ledger_movements_stage",
        "kg_ledger_movements",
        "stage IS NULL OR stage IN ('horno', 'crisol')",
    )
    n = conn.execute(
        sa.text(
            "UPDATE kg_ledger_movements m SET stage = 'horno' "
            "FROM kg_ledger_accounts a "
            "WHERE a.id = m.account_id AND a.account_type = 'intersede' "
            "AND m.stage IS NULL"
        )
    ).rowcount
    print(f"[e2f3a4b5c6d7] intersede: {n} movimiento(s) existentes marcados como etapa 'horno' (crudo)")

    # 2. crucible_charges cobra vida — gate de datos ANTES de tocar columnas
    rows = conn.execute(sa.text("SELECT COUNT(*) FROM crucible_charges")).scalar()
    if rows:
        raise RuntimeError(
            f"crucible_charges tiene {rows} fila(s) y nunca tuvo servicio que las "
            "escribiera: esta migracion no les inventa numero ni bodega. Revise "
            "esas filas antes de continuar (nada se aplico)."
        )
    op.add_column(
        "crucible_charges",
        sa.Column(
            "charge_number",
            sa.Integer(),
            nullable=False,
            comment="Consecutivo por org: secuencia `crucible_number` del helper de locks (rango 14)",
        ),
    )
    op.add_column(
        "crucible_charges",
        sa.Column(
            "warehouse_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("warehouses.id", ondelete="RESTRICT"),
            nullable=False,
            comment="Planta (willard_sede_drosses): el crisol vive en Juan Mina",
        ),
    )
    op.add_column(
        "crucible_charges",
        sa.Column("notes", sa.String(1000), nullable=True),
    )
    op.add_column(
        "crucible_charges",
        sa.Column(
            "maquila_amount",
            sa.Numeric(15, 2),
            nullable=False,
            server_default="0",
            comment="Solo dross_return: par de maquila interna emitido (display; los MM se buscan por source)",
        ),
    )
    op.create_unique_constraint(
        "uq_crucible_charges_org_number",
        "crucible_charges",
        ["organization_id", "charge_number"],
    )
    op.create_check_constraint(
        "ck_crucible_charges_event_type",
        "crucible_charges",
        "event_type IN ('charge', 'dross_return', 'discharge')",
    )
    op.create_check_constraint(
        "ck_crucible_charges_status",
        "crucible_charges",
        "status IN ('confirmed', 'annulled')",
    )

    # 3. Salidas de Plomo: diferencial del crisol + sede que factura
    op.add_column(
        "willard_deliveries",
        sa.Column(
            "crucible_amount",
            sa.Numeric(15, 2),
            nullable=False,
            server_default="0",
            comment="Diferencial del crisol: $300/kg de puro VENDIDO, planta->CV (#107 D4)",
        ),
    )
    op.add_column(
        "willard_deliveries",
        sa.Column(
            "billing_warehouse_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("warehouses.id", ondelete="SET NULL"),
            nullable=True,
            comment="Sede que factura, estampada al liquidar (snapshot de willard_sede_facturacion; Q-30, #107 D5)",
        ),
    )


def downgrade() -> None:
    op.drop_column("willard_deliveries", "billing_warehouse_id")
    op.drop_column("willard_deliveries", "crucible_amount")
    op.drop_constraint("ck_crucible_charges_status", "crucible_charges", type_="check")
    op.drop_constraint("ck_crucible_charges_event_type", "crucible_charges", type_="check")
    op.drop_constraint("uq_crucible_charges_org_number", "crucible_charges", type_="unique")
    op.drop_column("crucible_charges", "maquila_amount")
    op.drop_column("crucible_charges", "notes")
    op.drop_column("crucible_charges", "warehouse_id")
    op.drop_column("crucible_charges", "charge_number")
    op.drop_constraint("ck_kg_ledger_movements_stage", "kg_ledger_movements", type_="check")
    op.drop_column("kg_ledger_movements", "stage")
