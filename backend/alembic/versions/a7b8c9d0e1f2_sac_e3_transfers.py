"""SAC E3.1 — Traslados dos pasos + maquila intersede (plan-sac-e3-1 v1.1 §2.2)

Todo ADITIVO, nullable/server_default, cero RENAME/DROP/backfill:
1. warehouses.is_transit (bool, server_default false) — GATE DURO tabla compartida.
2. warehouses.transit_target_warehouse_id (FK self, nullable) — ruteo unico.
3. CREATE TABLE transfers + transfer_lines (cabecera + lineas, multi-material).
4. inventory_adjustments.transfer_id (FK, nullable) — cascade de anulacion de
   merma/excedente (C1: NO se expone en response schema).
5. Permiso inventory.transfer_receive (dual-write triple con services/role.py;
   SIN asignar a roles de sistema — D4).

Los 2 tipos MM nuevos (internal_maquila_expense/income) NO requieren migracion:
movement_type es String(50) sin CHECK ni enum de BD.

FKs sin nombre explicito -> default de PG = paridad con create_all.

Revision ID: a7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-07-20
"""
from typing import Sequence, Union
from uuid import uuid4

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

from app.models.base import GUID

revision: str = "a7b8c9d0e1f2"
down_revision: Union[str, None] = "f6a7b8c9d0e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


NEW_PERMISSIONS = [
    ("inventory.transfer_receive", "Recibir Traslados Intersede", "inventory",
     "Permite confirmar recepcion y resolver discrepancias de traslados dos pasos (SAC)", 147),
]


def upgrade() -> None:
    # 1-2. Columnas en warehouses (tabla compartida — golden gate duro)
    op.add_column(
        "warehouses",
        sa.Column(
            "is_transit",
            sa.Boolean(),
            nullable=False,
            server_default="false",
            comment="Bodega virtual de transito intersede (SAC E3.1)",
        ),
    )
    op.add_column(
        "warehouses",
        sa.Column(
            "transit_target_warehouse_id",
            GUID(),
            nullable=True,
            comment="Bodega fisica destino a la que rutea esta bodega de transito",
        ),
    )
    op.create_foreign_key(
        None,
        "warehouses",
        "warehouses",
        ["transit_target_warehouse_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # 3. Tablas transfers + transfer_lines
    op.create_table(
        "transfers",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("organization_id", GUID(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("transfer_number", sa.Integer(), nullable=False,
                  comment="Consecutivo por org (advisory lock, patron inbound_order)"),
        sa.Column("from_warehouse_id", GUID(), sa.ForeignKey("warehouses.id", ondelete="RESTRICT"), nullable=False,
                  comment="Sede origen (CV o BOG)"),
        sa.Column("to_warehouse_id", GUID(), sa.ForeignKey("warehouses.id", ondelete="RESTRICT"), nullable=False,
                  comment="Sede destino fisica final (JM)"),
        sa.Column("transit_warehouse_id", GUID(), sa.ForeignKey("warehouses.id", ondelete="RESTRICT"), nullable=False,
                  comment="Bodega virtual de transito resuelta al despacho (is_transit=True)"),
        sa.Column("dispatch_date", sa.DateTime(timezone=True), nullable=False, index=True,
                  comment="Fecha negocio del despacho"),
        sa.Column("received_date", sa.DateTime(timezone=True), nullable=True,
                  comment="Fecha negocio de la recepcion (E11: fecha canonica de los efectos)"),
        sa.Column("status", sa.String(16), nullable=False, server_default="dispatched", index=True,
                  comment="dispatched | held_discrepancy | received | annulled — derivado de lineas"),
        sa.Column("notes", sa.String(500), nullable=True),
        sa.Column("created_by", GUID(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("received_by", GUID(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("annulled_reason", sa.String(500), nullable=True),
        sa.Column("annulled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("annulled_by", GUID(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("organization_id", "transfer_number", name="uq_transfers_org_number"),
    )
    op.create_index("ix_transfers_org_status", "transfers", ["organization_id", "status"])
    op.create_index("ix_transfers_org_dispatch", "transfers", ["organization_id", "dispatch_date"])

    op.create_table(
        "transfer_lines",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("organization_id", GUID(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("transfer_id", GUID(), sa.ForeignKey("transfers.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("material_id", GUID(), sa.ForeignKey("materials.id", ondelete="RESTRICT"), nullable=False, index=True),
        sa.Column("quantity_dispatched", sa.Numeric(15, 4), nullable=False),
        sa.Column("quantity_received", sa.Numeric(15, 4), nullable=True,
                  comment="Bascula destino; ge=0 permite recibido=0 = merma total (bloq-7)"),
        sa.Column("resolved_quantity", sa.Numeric(15, 4), nullable=True,
                  comment="Cantidad final tras resolver discrepancia (preserva la bascula original)"),
        sa.Column("unit_cost", sa.Numeric(15, 2), nullable=False,
                  comment="Snapshot current_average_cost ORG-WIDE al despacho (#5, invariante 1)"),
        sa.Column("is_contributor", sa.Boolean(), nullable=False, server_default="false",
                  comment="Snapshot al despacho: tenia MaterialConversionFormula vigente"),
        sa.Column("conversion_formula_snapshot", JSONB(), nullable=True,
                  comment="Snapshot de la formula vigente AL DESPACHO (E7). NULL si no aportante"),
        sa.Column("kg_lead_equivalent", sa.Numeric(14, 4), nullable=True,
                  comment="quantity_efectiva x factor_snapshot. NULL hasta emitir efectos"),
        sa.Column("maquila_amount", sa.Numeric(15, 2), nullable=True,
                  comment="kg_lead_equivalent x tarifa maquila_intersede_cv_jm"),
        sa.Column("discrepancy_task_id", GUID(), sa.ForeignKey("discrepancy_tasks.id", ondelete="SET NULL"), nullable=True,
                  comment="Poblado si la linea salio de tolerancia"),
        sa.Column("effects_emitted", sa.Boolean(), nullable=False, server_default="false",
                  comment="True cuando intersede + par de esta linea ya se emitieron"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("quantity_dispatched > 0", name="ck_transfer_lines_qty_dispatched_positive"),
        sa.CheckConstraint("quantity_received IS NULL OR quantity_received >= 0",
                           name="ck_transfer_lines_qty_received_ge_zero"),
    )
    op.create_index("ix_transfer_lines_org_material", "transfer_lines", ["organization_id", "material_id"])

    # 4. FK de cascade de merma/excedente (C1: interna, no se serializa)
    op.add_column(
        "inventory_adjustments",
        sa.Column(
            "transfer_id",
            GUID(),
            nullable=True,
            comment="Traslado padre cuando el ajuste es merma/excedente de recepcion (SAC E3.1)",
        ),
    )
    op.create_foreign_key(
        None,
        "inventory_adjustments",
        "transfers",
        ["transfer_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # 5. Permiso (idempotente, patron f9a2b3c4d5e6; SIN role_assignments — D4)
    conn = op.get_bind()
    new_codes = [p[0] for p in NEW_PERMISSIONS]
    existing = conn.execute(
        sa.text("SELECT code FROM permissions WHERE code = ANY(:codes)"),
        {"codes": new_codes},
    ).fetchall()
    existing_codes = {row[0] for row in existing}

    for code, display_name, module, description, sort_order in NEW_PERMISSIONS:
        if code not in existing_codes:
            conn.execute(
                sa.text(
                    "INSERT INTO permissions (id, code, display_name, module, description, sort_order) "
                    "VALUES (:id, :code, :display_name, :module, :description, :sort_order)"
                ),
                {
                    "id": str(uuid4()),
                    "code": code,
                    "display_name": display_name,
                    "module": module,
                    "description": description,
                    "sort_order": sort_order,
                },
            )


def downgrade() -> None:
    conn = op.get_bind()
    codes = [p[0] for p in NEW_PERMISSIONS]
    perms = conn.execute(
        sa.text("SELECT id FROM permissions WHERE code = ANY(:codes)"),
        {"codes": codes},
    ).fetchall()
    perm_ids = [row[0] for row in perms]
    if perm_ids:
        conn.execute(
            sa.text("DELETE FROM role_permissions WHERE permission_id = ANY(:ids)"),
            {"ids": perm_ids},
        )
        conn.execute(
            sa.text("DELETE FROM permissions WHERE id = ANY(:ids)"),
            {"ids": perm_ids},
        )

    op.drop_column("inventory_adjustments", "transfer_id")
    op.drop_index("ix_transfer_lines_org_material", table_name="transfer_lines")
    op.drop_table("transfer_lines")
    op.drop_index("ix_transfers_org_dispatch", table_name="transfers")
    op.drop_index("ix_transfers_org_status", table_name="transfers")
    op.drop_table("transfers")
    op.drop_column("warehouses", "transit_target_warehouse_id")
    op.drop_column("warehouses", "is_transit")
