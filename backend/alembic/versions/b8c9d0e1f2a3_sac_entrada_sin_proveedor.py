"""SAC #93 — Entrada sin proveedor: reparto al liquidar y descuadre de entrada.

UNA sola migracion (plan-sac-entrada-sin-proveedor v1.4 §9; la f7a8b9c0d1e2 de
#89 se descarto sin llegar a produccion):

1. CREATE TABLE inbound_order_purchases (puente 1:N entrada<->compras, D2,
   heredada de #89) + backfill desde inbound_orders.purchase_id (filas legacy
   1:1 de los ciclos B-D; la columna queda INERTE, regla sin-DROP).
2. CREATE TABLE inbound_line_allocations (el reparto, D1).
3. inbound_orders.third_party_id -> NULLABLE (D1: la captura tipo compra no
   conoce el proveedor; willard lo exige el SERVICIO) + reviewed_by/reviewed_at
   (auditoria minima de D10).
4. inbound_order_lines.reference_unit_price + unallocated_intentional (D3/D8)
   + UNIQUE(inbound_order_id, material_id) (D3 — una fila por material).
5. inventory_adjustments.inbound_order_id (D7 — 🔴 TABLA COMPARTIDA, unico
   toque a las 7 orgs; nullable, no se serializa; gate golden D18).
6. service_tariffs.kg_per_unit (D11 — los 14 kg/unidad de la comision, junto
   al precio porque se versionan juntos).
7. Permiso purchases.review (dual-write triple; SIN roles de sistema — D4 E1).
8. Backfill de estado para filas legacy tipo compra: el estado deja de
   derivarse de la compra (D4) — 'confirmed' queda exclusivo de willard.

GATES DE DATOS (la migracion SE DETIENE, no adivina):
- G1: entradas tipo compra con su derivada aun 'registered' — no hay estado
  destino seguro ('reviewed' duplicaria compras al liquidar por el flujo
  nuevo). Runbook: liquidarlas o anularlas ANTES del deploy.
- G2: lineas con material duplicado en una entrada — romperian el UNIQUE de
  D3 con un error opaco; mejor uno que nombra las entradas.

FKs sin nombre explicito -> default de PG = paridad con create_all.

Revision ID: b8c9d0e1f2a3
Revises: e6f7a8b9c0d1
Create Date: 2026-08-06
"""
from typing import Sequence, Union
from uuid import uuid4

import sqlalchemy as sa
from alembic import op

from app.models.base import GUID

revision: str = "b8c9d0e1f2a3"
down_revision: Union[str, None] = "e6f7a8b9c0d1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


NEW_PERMISSIONS = [
    ("purchases.review", "Revisar Entradas", "purchases",
     "Permite marcar una entrada como revisada (confirma cantidades y habilita liquidar, SAC)", 148),
]


def upgrade() -> None:
    conn = op.get_bind()

    # ── G1: entradas tipo compra con derivada 'registered' (sin estado destino) ──
    pending = conn.execute(
        sa.text(
            "SELECT io.order_number, o.name FROM inbound_orders io "
            "JOIN purchases p ON p.id = io.purchase_id "
            "JOIN organizations o ON o.id = io.organization_id "
            "WHERE io.inbound_type = 'purchase' AND io.status != 'annulled' "
            "AND p.status = 'registered' ORDER BY io.order_number"
        )
    ).fetchall()
    if pending:
        detail = ", ".join(f"#{r[0]} ({r[1]})" for r in pending)
        raise RuntimeError(
            f"Migracion detenida (G1): hay {len(pending)} entrada(s) tipo compra con su "
            f"compra derivada sin liquidar: {detail}. Liquidelas o anulelas desde la UI "
            "ANTES de migrar — el modelo nuevo no tiene estado seguro para ellas."
        )

    # ── G2: material duplicado en una misma entrada (romperia el UNIQUE de D3) ──
    dups = conn.execute(
        sa.text(
            "SELECT io.order_number, COUNT(*) FROM inbound_order_lines l "
            "JOIN inbound_orders io ON io.id = l.inbound_order_id "
            "GROUP BY io.order_number, l.inbound_order_id, l.material_id "
            "HAVING COUNT(*) > 1"
        )
    ).fetchall()
    if dups:
        detail = ", ".join(f"#{r[0]}" for r in dups)
        raise RuntimeError(
            f"Migracion detenida (G2): entradas con el mismo material en mas de una linea: "
            f"{detail}. Consolide las lineas antes de migrar (D3: una fila por material)."
        )

    # ── 1. Puente entrada<->compras (D2) ──
    op.create_table(
        "inbound_order_purchases",
        sa.Column("inbound_order_id", GUID(),
                  sa.ForeignKey("inbound_orders.id", ondelete="CASCADE"),
                  primary_key=True),
        sa.Column("purchase_id", GUID(),
                  sa.ForeignKey("purchases.id", ondelete="CASCADE"),
                  primary_key=True),
        sa.Column("organization_id", GUID(),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"),
                  nullable=False, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("purchase_id", name="uq_inbound_order_purchases_purchase"),
    )

    # Backfill de las filas legacy 1:1 (ciclos B-D); purchase_id queda INERTE
    conn.execute(
        sa.text(
            "INSERT INTO inbound_order_purchases (inbound_order_id, purchase_id, organization_id) "
            "SELECT io.id, io.purchase_id, io.organization_id FROM inbound_orders io "
            "WHERE io.purchase_id IS NOT NULL"
        )
    )

    # ── 2. El reparto (D1) ──
    op.create_table(
        "inbound_line_allocations",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("inbound_line_id", GUID(),
                  sa.ForeignKey("inbound_order_lines.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("third_party_id", GUID(),
                  sa.ForeignKey("third_parties.id", ondelete="RESTRICT"),
                  nullable=False),
        sa.Column("quantity", sa.Numeric(15, 4), nullable=False),
        sa.Column("unit_price", sa.Numeric(15, 2), nullable=False),
        sa.Column("invoice_number", sa.String(50), nullable=True,
                  comment="Factura del proveedor (D12) — llega con la liquidacion"),
        sa.Column("organization_id", GUID(),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"),
                  nullable=False, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("quantity > 0", name="ck_inbound_alloc_qty_positive"),
        sa.CheckConstraint("unit_price >= 0", name="ck_inbound_alloc_price_non_negative"),
        sa.UniqueConstraint("inbound_line_id", "third_party_id",
                            name="uq_inbound_alloc_line_third_party"),
    )
    op.create_index("ix_inbound_line_allocations_line", "inbound_line_allocations", ["inbound_line_id"])

    # ── 3. Cabecera: proveedor nullable + auditoria de revision ──
    op.alter_column(
        "inbound_orders", "third_party_id",
        existing_type=GUID(), nullable=True,
        comment="Willard: titular de la cuenta kg. Tipo compra: NULL desde #93 (el proveedor vive en el reparto)",
        existing_comment="Proveedor real (una entrada POR proveedor, v0.5 §7.3)",
    )
    op.add_column(
        "inbound_orders",
        sa.Column("reviewed_by", GUID(), nullable=True),
    )
    op.create_foreign_key(
        None, "inbound_orders", "users", ["reviewed_by"], ["id"], ondelete="SET NULL",
    )
    op.add_column(
        "inbound_orders",
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
    )
    # D12: remision del camion (documento de patio) — columna propia, NO se
    # recicla invoice_number (#87 acaba de pagar el costo del doble sentido)
    op.add_column(
        "inbound_orders",
        sa.Column("remission_number", sa.String(50), nullable=True,
                  comment="Remision del camion (documento de patio, D12) — una por entrada"),
    )

    # ── 4. Linea: precio de referencia + intencion + una fila por material ──
    op.add_column(
        "inbound_order_lines",
        sa.Column("reference_unit_price", sa.Numeric(15, 2), nullable=True,
                  comment="Precio de referencia del material en esta entrada — valora el descuadre (D6)"),
    )
    op.add_column(
        "inbound_order_lines",
        sa.Column("unallocated_intentional", sa.Boolean(), nullable=False,
                  server_default="false",
                  comment="Declaracion explicita 'este material no es de nadie' — habilita liquidar sin reparto (D8)"),
    )
    op.create_unique_constraint(
        "uq_inbound_lines_order_material", "inbound_order_lines",
        ["inbound_order_id", "material_id"],
    )

    # ── 5. 🔴 Tabla compartida: marca del ajuste de descuadre (D7) ──
    op.add_column(
        "inventory_adjustments",
        sa.Column("inbound_order_id", GUID(), nullable=True,
                  comment="Entrada padre cuando el ajuste es descuadre de entrada (SAC #93)"),
    )
    op.create_foreign_key(
        None, "inventory_adjustments", "inbound_orders",
        ["inbound_order_id"], ["id"], ondelete="CASCADE",
    )

    # ── 6. Tarifa: equivalencia kg/unidad (D11) ──
    op.add_column(
        "service_tariffs",
        sa.Column("kg_per_unit", sa.Numeric(10, 4), nullable=True,
                  comment="Kg equivalentes por unidad para la base de comision (solo comision_green_loop)"),
    )
    op.create_check_constraint(
        "ck_service_tariffs_kg_per_unit_positive", "service_tariffs",
        "kg_per_unit IS NULL OR kg_per_unit > 0",
    )

    # ── 7. Backfill de estado legacy (post-G1 solo quedan liquidated/cancelled) ──
    conn.execute(
        sa.text(
            "UPDATE inbound_orders io SET status = "
            "CASE WHEN p.status = 'cancelled' THEN 'annulled' ELSE 'liquidated' END "
            "FROM purchases p WHERE p.id = io.purchase_id "
            "AND io.inbound_type = 'purchase' AND io.status != 'annulled'"
        )
    )

    # ── 8. Permiso (idempotente, patron c4d5e6f7a8b9; SIN role_assignments — D4) ──
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

    # Permiso
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

    op.drop_constraint("ck_service_tariffs_kg_per_unit_positive", "service_tariffs", type_="check")
    op.drop_column("service_tariffs", "kg_per_unit")

    op.drop_column("inventory_adjustments", "inbound_order_id")

    op.drop_constraint("uq_inbound_lines_order_material", "inbound_order_lines", type_="unique")
    op.drop_column("inbound_order_lines", "unallocated_intentional")
    op.drop_column("inbound_order_lines", "reference_unit_price")

    op.drop_column("inbound_orders", "remission_number")
    op.drop_column("inbound_orders", "reviewed_at")
    op.drop_column("inbound_orders", "reviewed_by")

    # Best effort: el modelo viejo no conoce reviewed/liquidated en tipo compra
    # ('confirmed' era su unico estado vivo; el display derivaba de la compra).
    conn.execute(
        sa.text(
            "UPDATE inbound_orders SET status = 'confirmed' "
            "WHERE inbound_type = 'purchase' AND status IN ('reviewed', 'liquidated')"
        )
    )
    # ⚠️ Falla con razon si hay capturas nuevas sin proveedor (NULL): el modelo
    # viejo no puede representarlas — es la ventana de reversion del gate.
    op.alter_column(
        "inbound_orders", "third_party_id",
        existing_type=GUID(), nullable=False,
        comment="Proveedor real (una entrada POR proveedor, v0.5 §7.3)",
        existing_comment="Willard: titular de la cuenta kg. Tipo compra: NULL desde #93 (el proveedor vive en el reparto)",
    )

    op.drop_table("inbound_line_allocations")
    op.drop_table("inbound_order_purchases")
