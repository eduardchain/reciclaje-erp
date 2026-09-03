#!/usr/bin/env python
"""Diff golden BEFORE (main) vs AFTER (develop+E3.1).

Diffs esperados (aditivos, documentados):
  - warehouses: cada item gana is_receiving=true (Ciclo B), is_transit=false y
    transit_target_warehouse_id=null (E3.1), sede_warehouse_id=null (sedes).
  - pnl_*: gana internal_maquila_income=0.0 e internal_maquila_expense=0.0 (E3.1),
    tambien dentro de periods[]/totals del monthly.
Cualquier otra diferencia = FALLO del golden.
"""
import json
import sys
from pathlib import Path

# clave agregada -> valor exacto permitido, restringido por captura
ALLOWED_ADDED = {
    "warehouses": {
        "is_receiving": True,
        "is_transit": False,
        "transit_target_warehouse_id": None,
        # Sede de la bodega. NULL en las 3 orgs cliente = cada bodega es su
        # propia sede = todo traslado sigue siendo intersede (no-regresion).
        "sede_warehouse_id": None,
    },
    "pnl": {
        "internal_maquila_income": 0.0,
        "internal_maquila_expense": 0.0,
    },
    # E1 Migracion B agrego columnas a los MODELOS; los list endpoints
    # (response_model=dict + ORM -> jsonable_encoder) las serializan solas.
    # En prod SIEMPRE null (solo SAC las llena, org-scoped).
    "money_accounts": {"warehouse_id": None},
    "money_movements": {
        "warehouse_id": None, "tariff_id": None,
        "source_type": None, "source_id": None,
    },
}


def classify(capture_name: str) -> dict:
    if capture_name.startswith("pnl_"):
        return ALLOWED_ADDED["pnl"]
    if capture_name in ("warehouses", "money_accounts", "money_movements"):
        return ALLOWED_ADDED[capture_name]
    return {}


def diff(before, after, path, allowed, real, expected):
    if isinstance(before, dict) and isinstance(after, dict):
        for k in sorted(set(before) | set(after)):
            p = f"{path}.{k}" if path else k
            if k not in before:
                if k in allowed and after[k] == allowed[k]:
                    expected.append(p)
                else:
                    real.append(f"CLAVE NUEVA {p} = {after[k]!r}")
            elif k not in after:
                real.append(f"CLAVE PERDIDA {p} (era {before[k]!r})")
            else:
                diff(before[k], after[k], p, allowed, real, expected)
    elif isinstance(before, list) and isinstance(after, list):
        if len(before) != len(after):
            real.append(f"LEN {path}: {len(before)} -> {len(after)}")
            return
        for i, (b, a) in enumerate(zip(before, after)):
            diff(b, a, f"{path}[{i}]", allowed, real, expected)
    else:
        if before != after:
            real.append(f"VALOR {path}: {before!r} -> {after!r}")


MANIFEST = "_manifest.json"


def exigir_corrida_completa(lado: str, d: Path) -> None:
    """Aborta si ese lado no es una corrida COMPLETA de golden_capture.

    🔴 El 2026-08-18 este script dijo "0 diffs reales" comparando dos
    directorios INEXISTENTES: golden_capture aborta por credenciales faltantes
    antes del mkdir, y Path.glob sobre un directorio que no existe devuelve
    vacio sin excepcion. `missing`/`extra` de abajo ya comparan por NOMBRE —mas
    fuerte que por conteo, cualquier asimetria la cazan— pero son guardas
    RELATIVAS: con los dos lados vacios se satisfacen vacuosamente, y con los
    dos igualmente incompletos tambien. Este chequeo es el absoluto que faltaba.

    Misma familia que el smoke `0 == 0` (#98) y que el lint que no arrancaba
    (#97): un gate que no corrio se ve identico a uno que paso.
    """
    manifest = d / MANIFEST
    if not manifest.exists():
        sys.exit(
            f"ABORTA: {lado} ({d}) no tiene {MANIFEST}. La captura no corrio, no "
            f"termino, o fallo alguna. Re-corre golden_capture.py contra ese lado "
            f"— encadenado (`capture && capture && diff`) no se puede saltar."
        )
    esperados = json.loads(manifest.read_text())["archivos"]
    presentes = sorted(f.name for f in d.glob("*.json") if f.name != MANIFEST)
    if presentes != esperados:
        faltan = sorted(set(esperados) - set(presentes))
        sobran = sorted(set(presentes) - set(esperados))
        sys.exit(f"ABORTA: {lado} no coincide con su {MANIFEST} "
                 f"(faltan={faltan}, sobran={sobran})")


def main() -> None:
    before_dir, after_dir = Path(sys.argv[1]), Path(sys.argv[2])
    exigir_corrida_completa("BEFORE", before_dir)
    exigir_corrida_completa("AFTER", after_dir)
    total_real = 0
    total_expected = 0
    files = sorted(p for p in before_dir.glob("*.json") if p.name != MANIFEST)
    after_names = {p.name for p in after_dir.glob("*.json") if p.name != MANIFEST}
    missing = [p.name for p in files if p.name not in after_names]
    extra = sorted(after_names - {p.name for p in files})
    if missing:
        print(f"FALTAN en after: {missing}")
        total_real += len(missing)
    if extra:
        print(f"SOBRAN en after: {extra}")
        total_real += len(extra)

    for f in files:
        if f.name not in after_names:
            continue
        capture = f.stem.split("__", 1)[1]
        allowed = classify(capture)
        b = json.loads(f.read_text())
        a = json.loads((after_dir / f.name).read_text())
        real: list[str] = []
        expected: list[str] = []
        diff(b, a, "", allowed, real, expected)
        total_real += len(real)
        total_expected += len(expected)
        if real:
            print(f"❌ {f.stem}: {len(real)} diffs REALES")
            for line in real[:12]:
                print(f"     {line}")
            if len(real) > 12:
                print(f"     ... y {len(real) - 12} mas")
        elif expected:
            print(f"✅ {f.stem}: identico salvo {len(expected)} claves aditivas esperadas")
        else:
            print(f"✅ {f.stem}: byte-identico")

    print("=" * 70)
    print(f"RESULTADO: {total_real} diffs reales, {total_expected} claves aditivas esperadas")
    sys.exit(1 if total_real else 0)


if __name__ == "__main__":
    main()
