# Scripts archivados

Estos scripts fueron **reemplazados por el flujo estandar de migracion** documentado en [`../MIGRATION.md`](../MIGRATION.md). Se conservan aqui por git blame y referencia historica.

## Archivos

| Archivo | Por que se archivo |
|---|---|
| `migrate_metarecycling.py` | Reemplazado por `../migrate_org.py` (generico, parametrizable, soporta multi-bodega y UNs custom via Excel). Mantenia hardcodes de MetaRecycling: 7 UNs especificas, `WAREHOUSE_NAME='Principal'`, `DEFAULT_TP_CATEGORIES`. |
| `MIGRATION_METARECYCLING.md` | Reemplazado por `../MIGRATION.md` (playbook generico). El caso MetaRecycling queda como apendice. |
| `load_initial_data.py` | Estructuralmente unsafe: hacia SQL directo para Inventory + FixedAssets, hardcodeaba fecha `2026-03-20`, no generaba `MaterialCostHistory`, no marcaba con el reason de migracion (rompia decisiones #9/#28/#41/#46). Logica util ya portada a `migrate_org.py` (precios, asignacion UN). |
| `migration_metarecycling_template.xlsx` | Template viejo con datos de ejemplo de MetaRecycling, hojas faltantes (UnidadesNegocio, Bodegas, Precios). Reemplazado por `../../data/migration_template.xlsx` regenerado. |
| `fix_initial_balance.py` | Atado al flujo viejo. Si en el futuro hace falta corregir balances iniciales post-migracion, escribir un script nuevo aware del flujo de `migrate_org.py`. |

## Que NO archivamos

- `seed_demo_org.py` — vigente para reset rapido de la org demo en prod.
- `seed_test_data.py` — vigente para datos de prueba en dev.
- `backfill_liquidated_at.py` — script one-shot ya ejecutado en dev, mantener por historia.
- `generate_migration_template.py` — ACTIVO, regenera `../../data/migration_template.xlsx` cuando cambia el schema.

## Si necesitas recuperar algo

```bash
git log --follow -- backend/scripts/archive/load_initial_data.py
```

Da el historial completo de cada archivo archivado.
