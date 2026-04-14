"""
Backfill de `liquidated_at` = `date` en compras/ventas/doble-partidas
y corrección de `MoneyMovement.date` para pagos/cobros de contado relacionados.

Contexto:
    Antes del commit `bdc0791` (2026-04-13 16:40 COT), al liquidar compras,
    ventas o dobles partidas se seteaba `liquidated_at = datetime.now(UTC)`
    en vez de la fecha del documento. Antes del commit `e892e81`
    (2026-04-13 06:50 COT), los MoneyMovements auto-creados en la liquidación
    (`payment_to_supplier`, `collection_from_client`) heredaban `date = now()`.

    Los reportes financieros filtran por `liquidated_at`, por lo que los
    registros históricos quedan mal reflejados. Este script corrige los datos.

Estrategia:
    - Fase A: UPDATE purchases/sales/double_entries SET liquidated_at = date
      WHERE liquidated_at IS NOT NULL
        AND liquidated_at::date != date::date
        AND liquidated_at < :cutoff_A
    - Fase B: UPDATE money_movements SET date = related.date
      WHERE movement_type IN ('payment_to_supplier', 'collection_from_client')
        AND (purchase_id IS NOT NULL OR sale_id IS NOT NULL)
        AND date < :cutoff_B
        AND date::date != related.date::date
    - Auditoría previa: tabla `backfill_liquidated_at_audit` con snapshot
      (entity_table, entity_id, field, old_value, new_value).
    - Todo en una sola transacción. Idempotente (filtros WHERE).

Uso:
    cd backend
    ./venv/bin/python scripts/backfill_liquidated_at.py --dry-run
    ./venv/bin/python scripts/backfill_liquidated_at.py --apply \\
        --cutoff-liquidated "2026-04-13T21:00:00+00:00" \\
        --cutoff-mm         "2026-04-13T12:00:00+00:00"
"""
import argparse
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text

from app.core.config import settings


DEFAULT_CUTOFF_LIQUIDATED = "2026-04-13T21:00:00+00:00"
DEFAULT_CUTOFF_MM = "2026-04-13T12:00:00+00:00"


AUDIT_TABLE_DDL = """
CREATE TABLE IF NOT EXISTS backfill_liquidated_at_audit (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_table text NOT NULL,
    entity_id    uuid NOT NULL,
    field        text NOT NULL,
    old_value    timestamptz,
    new_value    timestamptz,
    migrated_at  timestamptz NOT NULL DEFAULT now()
)
"""


# ---------------------------------------------------------------------------
# Queries de diagnóstico (dry-run)
# ---------------------------------------------------------------------------

COUNT_PHASE_A = {
    "purchases": """
        SELECT COUNT(*) FROM purchases
        WHERE liquidated_at IS NOT NULL
          AND liquidated_at::date != date::date
          AND liquidated_at < :cutoff
    """,
    "sales": """
        SELECT COUNT(*) FROM sales
        WHERE liquidated_at IS NOT NULL
          AND liquidated_at::date != date::date
          AND liquidated_at < :cutoff
    """,
    "double_entries": """
        SELECT COUNT(*) FROM double_entries
        WHERE liquidated_at IS NOT NULL
          AND liquidated_at::date != date
          AND liquidated_at < :cutoff
    """,
}

SAMPLE_PHASE_A = {
    "purchases": """
        SELECT id, purchase_number, date, liquidated_at FROM purchases
        WHERE liquidated_at IS NOT NULL
          AND liquidated_at::date != date::date
          AND liquidated_at < :cutoff
        ORDER BY liquidated_at ASC LIMIT 20
    """,
    "sales": """
        SELECT id, sale_number, date, liquidated_at FROM sales
        WHERE liquidated_at IS NOT NULL
          AND liquidated_at::date != date::date
          AND liquidated_at < :cutoff
        ORDER BY liquidated_at ASC LIMIT 20
    """,
    "double_entries": """
        SELECT id, double_entry_number, date, liquidated_at FROM double_entries
        WHERE liquidated_at IS NOT NULL
          AND liquidated_at::date != date
          AND liquidated_at < :cutoff
        ORDER BY liquidated_at ASC LIMIT 20
    """,
}

COUNT_PHASE_B = {
    "payment_to_supplier": """
        SELECT COUNT(*) FROM money_movements mm
        JOIN purchases p ON mm.purchase_id = p.id
        WHERE mm.movement_type = 'payment_to_supplier'
          AND mm.purchase_id IS NOT NULL
          AND mm.date < :cutoff
          AND mm.date::date != p.date::date
    """,
    "collection_from_client": """
        SELECT COUNT(*) FROM money_movements mm
        JOIN sales s ON mm.sale_id = s.id
        WHERE mm.movement_type = 'collection_from_client'
          AND mm.sale_id IS NOT NULL
          AND mm.date < :cutoff
          AND mm.date::date != s.date::date
    """,
}

SAMPLE_PHASE_B = {
    "payment_to_supplier": """
        SELECT mm.id, p.purchase_number, p.date AS doc_date, mm.date AS mm_date
        FROM money_movements mm
        JOIN purchases p ON mm.purchase_id = p.id
        WHERE mm.movement_type = 'payment_to_supplier'
          AND mm.purchase_id IS NOT NULL
          AND mm.date < :cutoff
          AND mm.date::date != p.date::date
        ORDER BY mm.date ASC LIMIT 20
    """,
    "collection_from_client": """
        SELECT mm.id, s.sale_number, s.date AS doc_date, mm.date AS mm_date
        FROM money_movements mm
        JOIN sales s ON mm.sale_id = s.id
        WHERE mm.movement_type = 'collection_from_client'
          AND mm.sale_id IS NOT NULL
          AND mm.date < :cutoff
          AND mm.date::date != s.date::date
        ORDER BY mm.date ASC LIMIT 20
    """,
}


# ---------------------------------------------------------------------------
# INSERT en auditoría (captura old_value antes del UPDATE)
# ---------------------------------------------------------------------------

AUDIT_INSERTS_PHASE_A = {
    "purchases": """
        INSERT INTO backfill_liquidated_at_audit
            (entity_table, entity_id, field, old_value, new_value)
        SELECT 'purchases', id, 'liquidated_at', liquidated_at, date
        FROM purchases
        WHERE liquidated_at IS NOT NULL
          AND liquidated_at::date != date::date
          AND liquidated_at < :cutoff
    """,
    "sales": """
        INSERT INTO backfill_liquidated_at_audit
            (entity_table, entity_id, field, old_value, new_value)
        SELECT 'sales', id, 'liquidated_at', liquidated_at, date
        FROM sales
        WHERE liquidated_at IS NOT NULL
          AND liquidated_at::date != date::date
          AND liquidated_at < :cutoff
    """,
    # double_entries.date es tipo Date: convertir a timestamptz mediodía UTC.
    "double_entries": """
        INSERT INTO backfill_liquidated_at_audit
            (entity_table, entity_id, field, old_value, new_value)
        SELECT 'double_entries', id, 'liquidated_at', liquidated_at,
               (date + TIME '12:00:00') AT TIME ZONE 'UTC'
        FROM double_entries
        WHERE liquidated_at IS NOT NULL
          AND liquidated_at::date != date
          AND liquidated_at < :cutoff
    """,
}

AUDIT_INSERTS_PHASE_B = {
    "payment_to_supplier": """
        INSERT INTO backfill_liquidated_at_audit
            (entity_table, entity_id, field, old_value, new_value)
        SELECT 'money_movements', mm.id, 'date', mm.date, p.date
        FROM money_movements mm
        JOIN purchases p ON mm.purchase_id = p.id
        WHERE mm.movement_type = 'payment_to_supplier'
          AND mm.purchase_id IS NOT NULL
          AND mm.date < :cutoff
          AND mm.date::date != p.date::date
    """,
    "collection_from_client": """
        INSERT INTO backfill_liquidated_at_audit
            (entity_table, entity_id, field, old_value, new_value)
        SELECT 'money_movements', mm.id, 'date', mm.date, s.date
        FROM money_movements mm
        JOIN sales s ON mm.sale_id = s.id
        WHERE mm.movement_type = 'collection_from_client'
          AND mm.sale_id IS NOT NULL
          AND mm.date < :cutoff
          AND mm.date::date != s.date::date
    """,
}


# ---------------------------------------------------------------------------
# UPDATEs
# ---------------------------------------------------------------------------

UPDATE_PHASE_A = {
    "purchases": """
        UPDATE purchases SET liquidated_at = date
        WHERE liquidated_at IS NOT NULL
          AND liquidated_at::date != date::date
          AND liquidated_at < :cutoff
    """,
    "sales": """
        UPDATE sales SET liquidated_at = date
        WHERE liquidated_at IS NOT NULL
          AND liquidated_at::date != date::date
          AND liquidated_at < :cutoff
    """,
    # double_entries.date es Date → convertir a timestamptz mediodía UTC.
    "double_entries": """
        UPDATE double_entries
        SET liquidated_at = (date + TIME '12:00:00') AT TIME ZONE 'UTC'
        WHERE liquidated_at IS NOT NULL
          AND liquidated_at::date != date
          AND liquidated_at < :cutoff
    """,
}

UPDATE_PHASE_B = {
    "payment_to_supplier": """
        UPDATE money_movements mm
        SET date = p.date
        FROM purchases p
        WHERE mm.purchase_id = p.id
          AND mm.movement_type = 'payment_to_supplier'
          AND mm.purchase_id IS NOT NULL
          AND mm.date < :cutoff
          AND mm.date::date != p.date::date
    """,
    "collection_from_client": """
        UPDATE money_movements mm
        SET date = s.date
        FROM sales s
        WHERE mm.sale_id = s.id
          AND mm.movement_type = 'collection_from_client'
          AND mm.sale_id IS NOT NULL
          AND mm.date < :cutoff
          AND mm.date::date != s.date::date
    """,
}


# ---------------------------------------------------------------------------
# Execution
# ---------------------------------------------------------------------------


def parse_cutoff(value: str, label: str) -> datetime:
    try:
        return datetime.fromisoformat(value)
    except ValueError as e:
        print(f"ERROR: --cutoff-{label} inválido '{value}': {e}")
        sys.exit(2)


def warn_if_prod(db_url: str) -> None:
    # Heurística básica: replicate_prod.sh usa port 5434. Prod NO es localhost.
    lowered = db_url.lower()
    if "localhost" in lowered or "127.0.0.1" in lowered or "@postgres" in lowered:
        return
    print("=" * 70)
    print("ADVERTENCIA: DATABASE_URL no apunta a localhost.")
    print(f"  {db_url}")
    print("Si esto es producción, asegúrate de tener BACKUP antes de --apply.")
    print("=" * 70)


def run_dry_run(conn, cutoff_a: datetime, cutoff_b: datetime) -> None:
    print("\n=== FASE A — liquidated_at en compras/ventas/DP ===")
    print(f"Cutoff A (liquidado antes de): {cutoff_a.isoformat()}\n")
    for table, q in COUNT_PHASE_A.items():
        count = conn.execute(text(q), {"cutoff": cutoff_a}).scalar()
        print(f"  {table:20s} → {count} candidatos")
        if count:
            rows = conn.execute(text(SAMPLE_PHASE_A[table]), {"cutoff": cutoff_a}).fetchall()
            for r in rows[:5]:
                print(f"      {dict(r._mapping)}")
            if len(rows) > 5:
                print(f"      ... ({len(rows)} en total, mostrando 5)")

    print("\n=== FASE B — date en MoneyMovements (pago/cobro contado) ===")
    print(f"Cutoff B (MM antes de): {cutoff_b.isoformat()}\n")
    for mtype, q in COUNT_PHASE_B.items():
        count = conn.execute(text(q), {"cutoff": cutoff_b}).scalar()
        print(f"  {mtype:25s} → {count} candidatos")
        if count:
            rows = conn.execute(text(SAMPLE_PHASE_B[mtype]), {"cutoff": cutoff_b}).fetchall()
            for r in rows[:5]:
                print(f"      {dict(r._mapping)}")
            if len(rows) > 5:
                print(f"      ... ({len(rows)} en total, mostrando 5)")

    print("\nDry-run completo. Ningún cambio aplicado.")


def run_apply(conn, cutoff_a: datetime, cutoff_b: datetime) -> None:
    print("\n>>> Creando tabla de auditoría (si no existe)...")
    conn.execute(text(AUDIT_TABLE_DDL))

    print(">>> INSERT auditoría Fase A (liquidated_at)...")
    for table, q in AUDIT_INSERTS_PHASE_A.items():
        r = conn.execute(text(q), {"cutoff": cutoff_a})
        print(f"     {table:20s} → {r.rowcount} filas auditadas")

    print(">>> INSERT auditoría Fase B (MoneyMovement.date)...")
    for mtype, q in AUDIT_INSERTS_PHASE_B.items():
        r = conn.execute(text(q), {"cutoff": cutoff_b})
        print(f"     {mtype:25s} → {r.rowcount} filas auditadas")

    # Fase B PRIMERO: depende de purchases.date / sales.date (campo documento),
    # no de liquidated_at. Orden indiferente en la práctica, pero así
    # mantenemos claridad con lo planeado.
    print("\n>>> UPDATE Fase B — money_movements.date = related.date ...")
    for mtype, q in UPDATE_PHASE_B.items():
        r = conn.execute(text(q), {"cutoff": cutoff_b})
        print(f"     {mtype:25s} → {r.rowcount} filas actualizadas")

    print("\n>>> UPDATE Fase A — liquidated_at = date ...")
    for table, q in UPDATE_PHASE_A.items():
        r = conn.execute(text(q), {"cutoff": cutoff_a})
        print(f"     {table:20s} → {r.rowcount} filas actualizadas")

    print("\n>>> Verificación post-update (esperado 0 en todas):")
    for table, q in COUNT_PHASE_A.items():
        count = conn.execute(text(q), {"cutoff": cutoff_a}).scalar()
        print(f"     {table:20s} → {count} pendientes")
    for mtype, q in COUNT_PHASE_B.items():
        count = conn.execute(text(q), {"cutoff": cutoff_b}).scalar()
        print(f"     {mtype:25s} → {count} pendientes")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Ejecuta el backfill. Sin esta flag, solo dry-run.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Solo reportar candidatos (default si no se pasa --apply).",
    )
    parser.add_argument(
        "--cutoff-liquidated",
        default=DEFAULT_CUTOFF_LIQUIDATED,
        help=f"ISO timestamp cutoff Fase A (default {DEFAULT_CUTOFF_LIQUIDATED})",
    )
    parser.add_argument(
        "--cutoff-mm",
        default=DEFAULT_CUTOFF_MM,
        help=f"ISO timestamp cutoff Fase B (default {DEFAULT_CUTOFF_MM})",
    )
    args = parser.parse_args()

    cutoff_a = parse_cutoff(args.cutoff_liquidated, "liquidated")
    cutoff_b = parse_cutoff(args.cutoff_mm, "mm")

    db_url = settings.DATABASE_URL
    print(f"DATABASE_URL: {db_url}")
    warn_if_prod(db_url)

    engine = create_engine(db_url)

    if args.apply:
        print(f"\n*** MODO APPLY ***")
        print(f"Cutoff A (liquidated_at): {cutoff_a.isoformat()}")
        print(f"Cutoff B (money_movements.date): {cutoff_b.isoformat()}")
        with engine.begin() as conn:
            run_apply(conn, cutoff_a, cutoff_b)
        print("\n>>> COMMIT OK. Backfill completado.")
    else:
        print("\n*** MODO DRY-RUN *** (usa --apply para ejecutar)")
        with engine.connect() as conn:
            run_dry_run(conn, cutoff_a, cutoff_b)


if __name__ == "__main__":
    main()
