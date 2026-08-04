#!/usr/bin/env python
"""Captura golden ×3 orgs prod (Costa, Biogreen, MetaRecycling) contra un backend.

Uso: python capture_golden.py --base-url http://localhost:8001 --out before/
Credenciales superuser: env SEED_SU_EMAIL / SEED_SU_PASSWORD.
"""
import argparse
import json
import os
import sys
from pathlib import Path

import requests

API = "/api/v1"

ORGS = {
    "costa": "7888fbe3-d317-400b-a122-dfdd422654dc",
    "biogreen": "02b110cc-4d96-41ca-9b5e-6e31090fa037",
    "metarecycling": "8e49c64a-8a13-4c5f-80c8-7c3123c9d246",
}

# (nombre, path, params)
CAPTURES = [
    ("pnl_period", "/reports/profit-and-loss",
     {"date_from": "2026-07-01", "date_to": "2026-07-23"}),
    ("pnl_june", "/reports/profit-and-loss",
     {"date_from": "2026-06-01", "date_to": "2026-06-30"}),
    ("pnl_monthly", "/reports/profit-and-loss/monthly",
     {"date_from": "2026-05-01", "date_to": "2026-07-23", "cutoff_day": 1}),
    ("balance_sheet", "/reports/balance-sheet", {}),
    ("balance_sheet_asof", "/reports/balance-sheet", {"as_of_date": "2026-06-30"}),
    ("balance_detailed", "/reports/balance-detailed", {}),
    ("balance_detailed_asof", "/reports/balance-detailed", {"as_of_date": "2026-06-30"}),
    ("cash_flow", "/reports/cash-flow",
     {"date_from": "2026-06-01", "date_to": "2026-07-23"}),
    ("money_accounts", "/money-accounts", {"limit": 100}),
    ("warehouses", "/warehouses", {"limit": 100}),
    ("money_movements", "/money-movements", {"limit": 100, "skip": 0}),
    ("expenses", "/reports/expenses",
     {"date_from": "2026-06-01", "date_to": "2026-07-23", "group_by": "bu_then_category"}),
    ("expenses_detail", "/reports/expenses/detail",
     {"date_from": "2026-06-01", "date_to": "2026-07-23"}),
    ("profitability_bu", "/reports/profitability-by-business-unit",
     {"date_from": "2026-06-01", "date_to": "2026-07-23"}),
]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    email = os.environ.get("SEED_SU_EMAIL")
    password = os.environ.get("SEED_SU_PASSWORD")
    if not email or not password:
        sys.exit("Faltan SEED_SU_EMAIL / SEED_SU_PASSWORD")

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    s = requests.Session()
    r = s.post(f"{args.base_url}{API}/auth/login/json",
               json={"email": email, "password": password})
    r.raise_for_status()
    token = r.json()["access_token"]

    failures = 0
    for org_name, org_id in ORGS.items():
        headers = {"Authorization": f"Bearer {token}", "X-Organization-ID": org_id}

        def get(path, params):
            resp = s.get(f"{args.base_url}{API}{path}", headers=headers,
                         params=params, timeout=180)
            resp.raise_for_status()
            return resp.json()

        for name, path, params in CAPTURES:
            try:
                data = get(path, params)
            except Exception as e:  # noqa: BLE001
                print(f"  FAIL {org_name}/{name}: {e}")
                failures += 1
                continue
            (out / f"{org_name}__{name}.json").write_text(
                json.dumps(data, indent=1, sort_keys=True, ensure_ascii=False))

        # Estado de cuenta del tercero "mas caliente": max |saldo|, tie-break id
        try:
            tps = get("/third-parties", {"limit": 5000})
            items = tps["items"] if isinstance(tps, dict) else tps
            hot = max(items, key=lambda t: (abs(float(t.get("current_balance") or 0)),
                                            str(t["id"])))
            stmt = get(f"/money-movements/third-party/{hot['id']}",
                       {"date_from": "2026-01-01", "date_to": "2026-07-23"})
            payload = {"third_party_id": str(hot["id"]),
                       "third_party_name": hot.get("name"), "statement": stmt}
            (out / f"{org_name}__tp_statement.json").write_text(
                json.dumps(payload, indent=1, sort_keys=True, ensure_ascii=False))
        except Exception as e:  # noqa: BLE001
            print(f"  FAIL {org_name}/tp_statement: {e}")
            failures += 1

        print(f"  {org_name}: OK")

    n = len(list(out.glob("*.json")))
    print(f"Capturas escritas: {n} en {out}")
    if failures:
        sys.exit(f"{failures} capturas fallaron")


if __name__ == "__main__":
    main()
