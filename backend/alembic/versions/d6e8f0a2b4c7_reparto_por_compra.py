"""SAC: reparto por COMPRA en la Entrada (slots) + IVA en compras

Johana (19-nov, via Daniel) llena la liquidacion por proveedor y un mismo
proveedor puede tener DOS compras en una Entrada («son dos recolecciones»,
Q-65). La unidad del reparto deja de ser el proveedor y pasa a ser la compra
de la Entrada, identificada por `purchase_slot` (1, 2, 3…).
Plan: docs/planes/plan-sac-reparto-por-compra.md v1.2 §2.

1. `inbound_line_allocations.purchase_slot` NOT NULL (>= 1); la UNIQUE pasa de
   (linea, proveedor) a (linea, slot). Tabla exclusiva de SAC.
2. `inbound_order_purchases.purchase_slot` nullable, llenado en TODAS las filas
   (R5), incluidas las legacy 1:1. Sin UNIQUE (entrada, slot) a proposito.
3. `document_taxes.purchase_id` + CHECK de dueno «exactamente uno de tres».
   Tabla compartida por esquema, cero filas fuera de SAC; las filas existentes
   tienen purchase_id NULL y cumplen el CHECK nuevo.

GATE DE DATOS (#93 G1/G2): si alguna Entrada tiene dos compras VIVAS del mismo
proveedor (hoy imposible), la migracion se detiene con el listado en vez de
inventar slots.

BACKFILL (R7): UNA sola funcion (`compute_slots`) calcula, por Entrada, el
mapeo proveedor -> slot y la usan las asignaciones Y el puente. Es pura (recibe
filas, devuelve mapas) para que los tests la ejerzan sin correr alembic.

Revision ID: d6e8f0a2b4c7
Revises: c5d7e9f1a3b6
"""
import unicodedata

from alembic import op
import sqlalchemy as sa

from app.models.base import GUID

revision = "d6e8f0a2b4c7"
down_revision = "c5d7e9f1a3b6"
branch_labels = None
depends_on = None


def _norm(name):
    """Calco CONGELADO de `normalize_entity_name` (#78). Una migracion es una
    foto: no importa codigo de `app/`, que puede cambiar despues."""
    return (
        unicodedata.normalize("NFKD", name or "")
        .encode("ascii", "ignore")
        .decode("ascii")
        .lower()
        .strip()
    )


def live_duplicates(bridge_rows):
    """Gate: Entradas con dos compras VIVAS del mismo proveedor.

    bridge_rows: iterable de (order_id, purchase_id, supplier_id, purchase_number, status).
    Devuelve una lista de (order_id, supplier_id, [purchase_numbers]).
    """
    seen = {}
    for order_id, _pid, supplier_id, number, status in bridge_rows:
        if status == "cancelled":
            continue
        seen.setdefault((order_id, supplier_id), []).append(number)
    return [(o, s, sorted(n)) for (o, s), n in sorted(seen.items(), key=lambda kv: str(kv[0])) if len(n) > 1]


def compute_slots(alloc_suppliers, bridge_rows, names):
    """Mapeo proveedor -> slot por Entrada (UNA sola funcion para los dos lados).

    alloc_suppliers: iterable de (order_id, supplier_id) con asignaciones.
    bridge_rows:     iterable de (order_id, purchase_id, supplier_id, purchase_number, status).
    names:           {supplier_id: nombre}

    Regla (plan §2, R7): por Entrada, los proveedores se ordenan primero por el
    numero MAS BAJO de sus compras no canceladas del puente; los que no tienen
    compra viva van despues, por nombre normalizado y luego por id. El slot es
    la posicion 1, 2, 3…  «Viva» = status != 'cancelled' (R5).

    Devuelve (slot_of_supplier, slot_of_purchase):
      slot_of_supplier[(order_id, supplier_id)] -> slot
      slot_of_purchase[(order_id, purchase_id)] -> slot
    Una compra cancelada toma el slot de su proveedor si tiene; si no, el
    siguiente libre (en orden de numero de compra, determinista).
    """
    bridge_rows = list(bridge_rows)
    orders = {}
    for order_id, supplier_id in alloc_suppliers:
        orders.setdefault(order_id, {}).setdefault(supplier_id, None)
    for order_id, _pid, supplier_id, number, status in bridge_rows:
        sup = orders.setdefault(order_id, {})
        if status == "cancelled":
            continue
        prev = sup.get(supplier_id)
        sup[supplier_id] = number if prev is None else min(prev, number)

    slot_of_supplier = {}
    for order_id, sup in orders.items():
        with_live = sorted((n, str(s), s) for s, n in sup.items() if n is not None)
        without = sorted(
            (_norm(names.get(s)), str(s), s) for s, n in sup.items() if n is None
        )
        ordered = [t[2] for t in with_live] + [t[2] for t in without]
        for i, s in enumerate(ordered, start=1):
            slot_of_supplier[(order_id, s)] = i

    slot_of_purchase = {}
    next_free = {}
    for order_id, sup in orders.items():
        next_free[order_id] = len(sup) + 1
    for order_id, pid, supplier_id, number, status in sorted(
        bridge_rows, key=lambda r: (str(r[0]), r[3] or 0, str(r[1]))
    ):
        slot = slot_of_supplier.get((order_id, supplier_id))
        if slot is None:
            slot = next_free[order_id]
            next_free[order_id] += 1
        slot_of_purchase[(order_id, pid)] = slot
    return slot_of_supplier, slot_of_purchase


def _read(conn):
    alloc_suppliers = conn.execute(sa.text(
        "SELECT DISTINCT l.inbound_order_id, a.third_party_id "
        "FROM inbound_line_allocations a "
        "JOIN inbound_order_lines l ON l.id = a.inbound_line_id"
    )).fetchall()
    bridge_rows = conn.execute(sa.text(
        "SELECT b.inbound_order_id, b.purchase_id, p.supplier_id, p.purchase_number, p.status "
        "FROM inbound_order_purchases b JOIN purchases p ON p.id = b.purchase_id"
    )).fetchall()
    ids = {r[1] for r in alloc_suppliers} | {r[2] for r in bridge_rows}
    names = {}
    if ids:
        for tp_id, name in conn.execute(
            sa.text("SELECT id, name FROM third_parties WHERE id = ANY(:ids)"),
            {"ids": list(ids)},
        ):
            names[tp_id] = name
    return [tuple(r) for r in alloc_suppliers], [tuple(r) for r in bridge_rows], names


def backfill_slots(conn):
    """Escribe los slots de las asignaciones y del puente desde `compute_slots`.

    Recalcula TODAS las filas (no solo las NULL): en el upgrade todas lo son, y
    los tests la corren sobre filas ya llenas para fijar que es determinista.
    """
    alloc_suppliers, bridge_rows, names = _read(conn)
    dups = live_duplicates(bridge_rows)
    if dups:
        listado = "; ".join(
            f"entrada {o}: proveedor {s} con compras vivas #{', #'.join(str(n) for n in nums)}"
            for o, s, nums in dups
        )
        raise RuntimeError(
            "Reparto por compra: hay Entradas con dos compras VIVAS del mismo "
            "proveedor y la migracion no inventa slots. Revise y decida antes "
            f"de migrar (Daniel): {listado}"
        )
    slot_of_supplier, slot_of_purchase = compute_slots(alloc_suppliers, bridge_rows, names)
    for (order_id, supplier_id), slot in slot_of_supplier.items():
        conn.execute(sa.text(
            "UPDATE inbound_line_allocations a SET purchase_slot = :slot "
            "FROM inbound_order_lines l "
            "WHERE l.id = a.inbound_line_id AND l.inbound_order_id = :o "
            "AND a.third_party_id = :s"
        ), {"slot": slot, "o": order_id, "s": supplier_id})
    for (order_id, purchase_id), slot in slot_of_purchase.items():
        conn.execute(sa.text(
            "UPDATE inbound_order_purchases SET purchase_slot = :slot "
            "WHERE inbound_order_id = :o AND purchase_id = :p"
        ), {"slot": slot, "o": order_id, "p": purchase_id})
    return slot_of_supplier, slot_of_purchase


def upgrade() -> None:
    conn = op.get_bind()

    op.add_column(
        "inbound_line_allocations",
        sa.Column(
            "purchase_slot",
            sa.SmallInteger(),
            nullable=True,
            comment="Compra de la Entrada (1, 2, 3…). Q-65: un proveedor puede tener dos",
        ),
    )
    op.add_column(
        "inbound_order_purchases",
        sa.Column(
            "purchase_slot",
            sa.SmallInteger(),
            nullable=True,
            comment="Slot de la compra en la Entrada (backfill en todas las filas)",
        ),
    )

    backfill_slots(conn)

    op.alter_column("inbound_line_allocations", "purchase_slot", nullable=False)
    op.create_check_constraint(
        "ck_inbound_alloc_slot_positive", "inbound_line_allocations", "purchase_slot >= 1"
    )
    op.drop_constraint(
        "uq_inbound_alloc_line_third_party", "inbound_line_allocations", type_="unique"
    )
    op.create_unique_constraint(
        "uq_inbound_alloc_line_slot",
        "inbound_line_allocations",
        ["inbound_line_id", "purchase_slot"],
    )

    # document_taxes: tercer dueno. FK SIN nombre (paridad con create_all, #111)
    op.add_column(
        "document_taxes",
        sa.Column("purchase_id", GUID(), nullable=True),
    )
    op.create_foreign_key(
        None, "document_taxes", "purchases", ["purchase_id"], ["id"], ondelete="CASCADE"
    )
    op.create_index("ix_document_taxes_purchase", "document_taxes", ["purchase_id"])
    op.drop_constraint("ck_document_taxes_single_owner", "document_taxes", type_="check")
    op.create_check_constraint(
        "ck_document_taxes_single_owner",
        "document_taxes",
        "(sale_id IS NOT NULL)::int + (willard_delivery_id IS NOT NULL)::int"
        " + (purchase_id IS NOT NULL)::int = 1",
    )


def downgrade() -> None:
    # ⚠️ Bajar con IVA de compras capturado deja saldos aplicados sin las filas
    # que los explican (mismo dano que el downgrade de a3b5c7d9e1f2, #112): las
    # compras con IVA se desliquidan ANTES de bajar. Y con dos compras del mismo
    # proveedor en una Entrada, la UNIQUE vieja (linea, proveedor) no se puede
    # recrear: el downgrade falla en vez de borrar asignaciones.
    op.drop_constraint("ck_document_taxes_single_owner", "document_taxes", type_="check")
    op.execute("DELETE FROM document_taxes WHERE purchase_id IS NOT NULL")
    op.create_check_constraint(
        "ck_document_taxes_single_owner",
        "document_taxes",
        "(sale_id IS NOT NULL)::int + (willard_delivery_id IS NOT NULL)::int = 1",
    )
    op.drop_index("ix_document_taxes_purchase", table_name="document_taxes")
    op.drop_column("document_taxes", "purchase_id")

    op.drop_constraint("uq_inbound_alloc_line_slot", "inbound_line_allocations", type_="unique")
    op.create_unique_constraint(
        "uq_inbound_alloc_line_third_party",
        "inbound_line_allocations",
        ["inbound_line_id", "third_party_id"],
    )
    op.drop_constraint("ck_inbound_alloc_slot_positive", "inbound_line_allocations", type_="check")
    op.drop_column("inbound_order_purchases", "purchase_slot")
    op.drop_column("inbound_line_allocations", "purchase_slot")
