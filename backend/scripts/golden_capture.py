#!/usr/bin/env python
"""Captura golden ×3 orgs prod (Costa, Biogreen, MetaRecycling) contra un backend.

Uso: python capture_golden.py --base-url http://localhost:8001 --out before/
Credenciales superuser: env SEED_SU_EMAIL / SEED_SU_PASSWORD.

⚠️ CORRER SIEMPRE **ESTA** COPIA DEL SCRIPT PARA before Y PARA after.
El script solo habla HTTP, asi que sirve igual contra el backend viejo (:8001,
worktree de origin/main) que contra el nuevo (:8002). Usar la copia del worktree
para `before` produce un set de archivos distinto y `golden_diff.py` lo reporta
como `SOBRAN en after`, que cuenta como diff REAL — un falso positivo que cuesta
una corrida entera. Es load-bearing desde 2026-08-13, cuando la captura de
estado de cuenta paso de uno a dos terceros.
"""
import argparse
import json
import os
import sys
from pathlib import Path

import requests

API = "/api/v1"

# Sentinela de corrida COMPLETA. Se escribe solo si `failures == 0`; su ausencia
# es lo que le permite a golden_diff distinguir "no corrio" de "paso".
MANIFEST = "_manifest.json"

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

        # --- Estado de cuenta: DOS terceros, porque prueban cosas distintas ---
        #
        # 🔴 Hasta 2026-08-13 se capturaba uno solo, el de `max |saldo|`. Medido
        # ese dia contra la replica, en las 3 orgs eso elige un socio con 3, 3 y
        # 4 movimientos y CERO operaciones comerciales: el saldo grande lo
        # producen inyecciones de capital, no la actividad. O sea que la muestra
        # no era poco representativa — estaba **anti-correlacionada** con lo que
        # hay que probar.
        #
        # La consecuencia es retroactiva: esa captura nunca ejercito las rutas
        # comerciales del statement. El reposicionamiento de eventos por
        # `liquidated_at` (#61), los eventos sinteticos de retencion (#93) y un
        # `UnboundLocalError` que reventaba con 500 el estado de cuenta de
        # cualquier comisionista (#96) pasaron los tres por este gate sin que los
        # mirara.
        #
        # `hot` (mas saldo) y `busy` (mas eventos) prueban cosas distintas y
        # cuestan lo mismo. Si coinciden, se escribe una sola captura.
        try:
            tps = get("/third-parties", {"limit": 5000})
            items = tps["items"] if isinstance(tps, dict) else tps

            def _capturar(tp, sufijo):
                stmt = get(f"/money-movements/third-party/{tp['id']}",
                           {"date_from": "2026-01-01", "date_to": "2026-07-23"})
                payload = {"third_party_id": str(tp["id"]),
                           "third_party_name": tp.get("name"), "statement": stmt}
                (out / f"{org_name}__tp_statement{sufijo}.json").write_text(
                    json.dumps(payload, indent=1, sort_keys=True, ensure_ascii=False))
                return len(stmt.get("items", []))

            hot = max(items, key=lambda t: (abs(float(t.get("current_balance") or 0)),
                                            str(t["id"])))
            _capturar(hot, "")

            # El mas activo: se mide pidiendo el statement de los candidatos con
            # saldo != 0. Es O(n) llamadas, por eso se acota a 40 — suficiente
            # para dar con un proveedor de cientos de operaciones y barato.
            candidatos = sorted(
                (t for t in items if t["id"] != hot["id"]),
                key=lambda t: (abs(float(t.get("current_balance") or 0)), str(t["id"])),
                reverse=True,
            )[:40]
            busy, n_busy = None, -1
            for t in candidatos:
                try:
                    # ⚠️ NO llamar `s` a esto: `s` es la requests.Session del
                    # modulo. Shadowearla convierte cada `s.get(...)` posterior
                    # en `dict.get(...)` y revienta TODAS las capturas siguientes.
                    st = get(f"/money-movements/third-party/{t['id']}",
                             {"date_from": "2026-01-01", "date_to": "2026-07-23"})
                except Exception:  # noqa: BLE001
                    continue  # un candidato caido no debe tumbar la captura
                if len(st.get("items", [])) > n_busy:
                    busy, n_busy = t, len(st.get("items", []))
            if busy is not None:
                _capturar(busy, "_busy")
        except Exception as e:  # noqa: BLE001
            print(f"  FAIL {org_name}/tp_statement: {e}")
            failures += 1

        print(f"  {org_name}: OK")

    escritas = sorted(f.name for f in out.glob("*.json") if f.name != MANIFEST)
    print(f"Capturas escritas: {len(escritas)} en {out}")
    if failures:
        # Sin manifiesto: golden_diff aborta en vez de diffear una superficie
        # incompleta. Un lado a medias que coincide con el otro a medias sale
        # verde y el gate se estrecha en silencio.
        sys.exit(f"{failures} capturas fallaron")
    (out / MANIFEST).write_text(json.dumps(
        {"capturas": len(escritas), "archivos": escritas, "base_url": args.base_url},
        indent=1, sort_keys=True, ensure_ascii=False))


if __name__ == "__main__":
    main()
