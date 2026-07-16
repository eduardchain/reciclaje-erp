#!/usr/bin/env python3
"""Verificacion de paridad de schema: dev (migrado por Alembic) vs test (create_all).

Gate H3 del ciclo QA SAC (plan-sac-e1-configuracion.md D13/§9): la BD de test se
recrea desde los modelos (conftest DROP SCHEMA + create_all), asi que TODA columna,
indice, CHECK, UNIQUE y FK de las migraciones debe existir identico en los modelos
— sin espejo, la suite no ejercita las migraciones y un --autogenerate futuro
propondria DROPs.

Compara (por tabla): columnas (nombre, tipo, nullable), indices (indexdef exacto de
pg_indexes — los DESC y NULLS NOT DISTINCT quedan visibles verbatim), constraints
CHECK/UNIQUE/FK/PK (pg_get_constraintdef exacto).

EXCLUIDO deliberadamente: server_default de columnas — divergencia PRE-EXISTENTE en
todo el repo (los modelos usan default= de Python, las migraciones server_default=;
ej: financial_obligations.capital_balance). No es introducida por E1 y no afecta
comportamiento (el ORM siempre manda el valor). Cualquier otra dimension debe dar
diff CERO.

⚠️ Regla E2-E5 (hallazgo MENOR del veredicto QA E1, 2026-07-16): por la exclusion
anterior, este gate NO atrapa un default de BD faltante en los modelos. Toda tabla
nueva cuyo comportamiento dependa de un server_default (filas insertadas por SQL
crudo, backfills, clientes fuera del ORM) debe declarar el default TAMBIEN en el
modelo — la suite corre contra create_all y es la unica red que lo delata.

Uso (desde backend/):
  ./venv/bin/python3 scripts/schema_parity_check.py
Recrea el schema de la BD de TEST desde los modelos (5433, disposable) y diffea
contra dev (5434, solo lectura — jamas se modifica).

⚠️ NO correr mientras pytest este corriendo: ambos son duenos de 5433 y el
DROP SCHEMA de este script revienta la suite en curso (y viceversa: el DROP
del conftest invalida el snapshot de este script). Secuencial siempre.
"""
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy import create_engine, text

from app.core.config import settings as app_settings
from app.models import Base

TEST_DATABASE_URL = "postgresql://admin:test_password@localhost:5433/reciclaje_test"

EXCLUDED_TABLES = {"alembic_version"}

# --- Baseline PRE-EXISTENTE (verificado 2026-07-16, cero objetos SAC E1) ---
# Divergencias historicas dev<->modelos que NO introdujo E1. Cada categoria:
# (a) backfill_liquidated_at_audit: tabla one-shot del script de backfill
#     (decision #43) — existe solo en dev, nunca en modelos.
# (b) FKs con nombre explicito en migraciones viejas (fk_*) vs nombre default
#     de PG en create_all (<tabla>_<col>_fkey) — MISMA definicion, otro nombre.
# (c) Indices renombrados (ix_del_* vs ix_double_entry_lines_*, ix_org_members_*).
# (d) Indice organization_id del mixin ausente en dev en 3 tablas viejas
#     (las migraciones originales no lo crearon; los compuestos org_* lo cubren).
# (e) permissions: la migracion creo UNIQUE constraint + index no-unique; el
#     modelo usa unique=True + index=True (un solo indice unico).
# (f) uq_obligation_accrual_period: predicado WHERE semanticamente identico,
#     normalizacion de PG distinta (ARRAY cast rendering).
# Una divergencia NUEVA (fuera de esta lista) hace fallar el gate (exit 1).
BASELINE = {
    ("columna", "backfill_liquidated_at_audit"),   # (a) — toda la tabla
    ("constraint", "backfill_liquidated_at_audit"),
    ("indice", "backfill_liquidated_at_audit"),
    ("constraint", "double_entries"),               # (b)
    ("constraint", "expense_categories"),
    ("constraint", "fixed_assets"),
    ("constraint", "money_movements"),
    ("constraint", "organization_members"),
    ("constraint", "permissions"),                  # (e)
    ("constraint", "profit_distributions"),
    ("constraint", "purchases"),
    ("constraint", "sales"),
    ("constraint", "scheduled_expenses"),
    ("indice", "double_entry_lines"),               # (c)
    ("indice", "organization_members"),
    ("indice", "inventory_adjustments"),            # (d)
    ("indice", "material_transformations"),
    ("indice", "money_movements"),                  # (d) + (f)
    ("indice", "permissions"),                      # (e)
}

# Objetos SAC E1 — si un problema los menciona JAMAS es baseline (guard anti-abuso
# del allowlist: p.ej. un FK nuevo de E1 mal espejado en money_movements caeria
# en ("constraint","money_movements") — este set lo rescata al gate).
E1_MARKERS = (
    "kg_ledger", "service_tariff", "conversion_formula", "inbound_order",
    "furnace_charge", "crucible_charge", "discrepancy_task", "daily_ok_seal",
    "driver", "vehicle", "warehouse_id", "tariff_id", "source_type", "source_id",
    "willard_", "is_system_entity", "settings",
)


def snapshot(engine):
    """Snapshot del schema public: columnas, indices y constraints por tabla."""
    snap = {"columns": defaultdict(dict), "indexes": defaultdict(dict), "constraints": defaultdict(dict)}
    with engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT table_name, column_name, data_type, character_maximum_length, "
            "       numeric_precision, numeric_scale, is_nullable "
            "FROM information_schema.columns WHERE table_schema='public' "
            "ORDER BY table_name, column_name"
        )).fetchall()
        for t, col, dtype, chlen, nprec, nscale, nullable in rows:
            if t in EXCLUDED_TABLES:
                continue
            type_repr = dtype
            if chlen:
                type_repr += f"({chlen})"
            elif nprec and dtype == "numeric":
                type_repr += f"({nprec},{nscale})"
            snap["columns"][t][col] = f"{type_repr} nullable={nullable}"

        rows = conn.execute(text(
            "SELECT tablename, indexname, indexdef FROM pg_indexes "
            "WHERE schemaname='public' ORDER BY tablename, indexname"
        )).fetchall()
        for t, name, idxdef in rows:
            if t in EXCLUDED_TABLES:
                continue
            snap["indexes"][t][name] = idxdef

        rows = conn.execute(text(
            "SELECT rel.relname, con.conname, pg_get_constraintdef(con.oid) "
            "FROM pg_constraint con JOIN pg_class rel ON rel.oid = con.conrelid "
            "JOIN pg_namespace nsp ON nsp.oid = rel.relnamespace "
            "WHERE nsp.nspname='public' ORDER BY rel.relname, con.conname"
        )).fetchall()
        for t, name, condef in rows:
            if t in EXCLUDED_TABLES:
                continue
            snap["constraints"][t][name] = condef
    return snap


def diff_section(label, dev_map, test_map):
    """Retorna lista de (es_baseline, texto) por cada divergencia."""
    problems = []
    tables = sorted(set(dev_map) | set(test_map))
    for t in tables:
        dev_items, test_items = dev_map.get(t, {}), test_map.get(t, {})
        for name in sorted(set(dev_items) | set(test_items)):
            in_dev, in_test = dev_items.get(name), test_items.get(name)
            if in_dev == in_test:
                continue
            if in_dev is None:
                txt = f"  [{label}] {t}.{name}: SOLO en test-create_all -> {in_test}"
            elif in_test is None:
                txt = f"  [{label}] {t}.{name}: SOLO en dev-migrado -> {in_dev}"
            else:
                txt = f"  [{label}] {t}.{name}: DIFIERE\n    dev : {in_dev}\n    test: {in_test}"
            touches_e1 = any(m in txt.lower() for m in E1_MARKERS)
            is_baseline = (label, t) in BASELINE and not touches_e1
            problems.append((is_baseline, txt))
    return problems


def main():
    dev_url = app_settings.DATABASE_URL
    if "5433" in dev_url:
        print("ABORTA: DATABASE_URL apunta a la BD de test — revisa .env")
        sys.exit(2)
    if "76.13.118.195" in dev_url or "ecobalance.cc" in dev_url:
        print("ABORTA: DATABASE_URL apunta a produccion — este script es dev/test only")
        sys.exit(2)

    print(f"Dev (migrado):      {dev_url.split('@')[-1]}")
    print(f"Test (create_all):  {TEST_DATABASE_URL.split('@')[-1]}")

    test_engine = create_engine(TEST_DATABASE_URL)
    with test_engine.connect() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
        conn.commit()
    Base.metadata.create_all(bind=test_engine)
    print("Schema de test recreado desde los modelos (create_all).\n")

    dev_engine = create_engine(dev_url)
    dev_snap, test_snap = snapshot(dev_engine), snapshot(test_engine)

    problems = []
    problems += diff_section("columna", dev_snap["columns"], test_snap["columns"])
    problems += diff_section("indice", dev_snap["indexes"], test_snap["indexes"])
    problems += diff_section("constraint", dev_snap["constraints"], test_snap["constraints"])

    # Visibilidad H3: los indices especiales verbatim en ambos lados
    print("=== Indices foco H3 (verbatim, ambos lados identicos si no aparecen en el diff) ===")
    for t, idxs in sorted(test_snap["indexes"].items()):
        for name, idxdef in sorted(idxs.items()):
            if "DESC" in idxdef or "NULLS NOT DISTINCT" in idxdef:
                print(f"  {idxdef}")
    print()

    baseline = [txt for is_b, txt in problems if is_b]
    new_diffs = [txt for is_b, txt in problems if not is_b]

    if baseline:
        print(f"=== Baseline pre-existente ({len(baseline)} items, ninguno de E1 — ver docstring) ===")
        for p in baseline:
            print(p)
        print()

    if new_diffs:
        print(f"=== ✗ DIFF NUEVO NO CERO: {len(new_diffs)} diferencias fuera del baseline ===")
        for p in new_diffs:
            print(p)
        sys.exit(1)

    n_tables = len(set(dev_snap["columns"]) | set(test_snap["columns"]))
    n_idx = sum(len(v) for v in dev_snap["indexes"].values())
    n_cons = sum(len(v) for v in dev_snap["constraints"].values())
    print(f"=== ✓ DIFF CERO fuera del baseline === {n_tables} tablas, {n_idx} indices, "
          f"{n_cons} constraints comparados.")
    print("(server_default excluido: divergencia pre-existente repo-wide, ver docstring)")


if __name__ == "__main__":
    main()
