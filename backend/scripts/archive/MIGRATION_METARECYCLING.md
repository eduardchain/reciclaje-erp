# Migracion MetaRecycling (Lovable) → EcoBalance

Procedimiento para migrar la organizacion **MetaRecycling** (cliente actualmente en Lovable/ReciclaTrac) a EcoBalance creando una nueva org en EcoBalance con snapshot a la fecha del go-live.

## Alcance

- Una sola org: `MetaRecycling`.
- Snapshot a fecha de corte (go-live). Sin historia de movimientos cerrados.
- Maestros: 7 Unidades de Negocio fijas + bodega Principal + categorias material/gasto/tercero + materiales + terceros + cuentas.
- Saldos: initial_balance en cuentas y terceros (sin generar movimientos).
- Stock: via `POST /inventory-adjustments/increase/` para sembrar `MaterialCostHistory`.
- Activos fijos: via `POST /fixed-assets/`. Activos pre-sistema con `historical_load=True` (no genera MoneyMovement, ver decision #46).

Cuentas excluidas:
- `Utilidades [Socio]` (Lovable) → NO migran. Su saldo se funde con `initial_balance` del inversionista en EcoBalance.
- `Credito Bancolombia` (Lovable) → NO migra como `MoneyAccount`. Se carga como Tercero con categoria `Obligaciones Financieras` (declarada en `CategoriaTerceros` con `tipo_comportamiento=inversionista`) e `initial_balance = -84_384_600`. El Balance Detallado lo ubica en la seccion `Obligaciones Financieras` dentro de Inversionistas (no en Pasivos), por convencion con otras orgs (RDLC). La clasificacion la hace `_classify_third_party` por nombre de categoria (substring "obligaci").

## Archivos

- `backend/scripts/migrate_metarecycling.py` — script principal.
- `backend/scripts/generate_migration_template.py` — regenera el template Excel.
- `data/migration_metarecycling_template.xlsx` — template con 9 hojas (8 que escriben + `MapeoUN` que solo orienta `Materiales`), cabeceras y filas de ejemplo (amarillas). Entregable a la AI de Lovable para que llene los datos reales.

## Pre-requisitos

1. **Backend EcoBalance corriendo** con el endpoint `POST /fixed-assets/` extendido (PR 1, decision #46).
2. **Superuser** valido en EcoBalance (para crear org).
3. **Backup completo** de BD antes de `--apply` en produccion.
4. **Excel preparado por la AI de Lovable** a partir del template:
   - Reemplazar filas de ejemplo (amarillas) por datos reales.
   - Conservar el layout: fila 1 = NOTAS (gris), fila 2 = cabeceras (azul), fila 3+ = datos.
   - Validar manualmente las hojas criticas: `MapeoUN`, `Materiales`, `Terceros.saldo_inicial`, `Cuentas.tipo`, `ActivosFijos.depreciacion_acumulada`.

## Procedimiento (siempre dry-run primero)

### Paso 1 — Regenerar el template (solo si el formato cambio)

```bash
cd backend
./venv/bin/python scripts/generate_migration_template.py
```

Produce `data/migration_metarecycling_template.xlsx`. Entregar este archivo a la AI de Lovable para que arme el Excel real.

### Paso 2 — Dry-run en BD dev local

Levantar BD dev (puerto 5434) y backend:

```bash
cd /Users/daniel.chain/Projects/reciclaje-erp
POSTGRES_PASSWORD=localdev123 docker-compose up -d
cd backend && ./venv/bin/alembic upgrade head
./venv/bin/uvicorn app.main:app --reload --port 8000 &
```

Dry-run (sin login, valida solo el Excel + dependencias entre hojas):

```bash
cd backend
./venv/bin/python scripts/migrate_metarecycling.py \
  --file ../data/migration_metarecycling.xlsx \
  --admin-email salomonchain@gmail.com \
  --admin-name "Salomon Chain" \
  --dry-run
```

Debe imprimir `Errores: 0`. Si hay errores, corregir el Excel y repetir.

### Paso 3 — Apply en dev local

Reusa el dry-run y ademas autentica como superuser.

```bash
./venv/bin/python scripts/migrate_metarecycling.py \
  --file ../data/migration_metarecycling.xlsx \
  --superuser-email <superuser>@ecobalance.com \
  --superuser-password '<pwd>' \
  --admin-email salomonchain@gmail.com \
  --admin-name "Salomon Chain" \
  --apply
```

El script:
1. Crea la org `MetaRecycling` (o reusa si ya existe).
2. Crea el usuario admin con password default `123456` si era nuevo (cambiar luego en UI).
3. Crea maestros, terceros con `initial_balance`, cuentas con `initial_balance`.
4. Siembra stock via `inventory-adjustments/increase/`.
5. Crea fixed assets (con `historical_load=True` cuando proveedor y cuenta estan vacios).
6. Corre verificacion automatica: conteos de filas (exactos) + sumas con tolerancia (default $100 COP).

Tolerar centavos de redondeo en datos importados:
```bash
--balance-tolerance 500.00
```

### Paso 4 — Smoke test UI (manual, ~15 min)

Login como Salomon Chain en EcoBalance dev:

- `Reportes / Balance Detallado`: verificar `Activos = Pasivos + Patrimonio` (verification.is_balanced=true). Credito Bancolombia aparece bajo `Obligaciones Financieras` dentro de Inversionistas.
- `Maestros / Materiales`: cantidad y unidades de negocio correctas.
- `Maestros / Terceros`: 8 tabs con conteos correctos, Credito Bancolombia en tab Inversionistas (categoria Obligaciones Financieras).
- `Inventario / Stock`: por material coincide con Lovable.
- `Tesoreria / Cuentas`: cuentas con sus saldos.
- Crear una compra de prueba: descuenta stock, actualiza balance proveedor, genera inventory_movement.

### Paso 5 — Apply en produccion

Solo cuando el cliente apruebe el dry-run + smoke test en dev.

```bash
./venv/bin/python scripts/migrate_metarecycling.py \
  --file ../data/migration_metarecycling.xlsx \
  --api-url https://api.ecobalance.com \
  --superuser-email <superuser>@ecobalance.com \
  --superuser-password '<pwd>' \
  --admin-email salomonchain@gmail.com \
  --admin-name "Salomon Chain" \
  --apply
```

El script es **local contra produccion** — no se ejecuta en el VPS. Lanzar desde la maquina del operador.

## Re-ejecucion (idempotencia)

El script detecta duplicados (HTTP 409 o nombre existente) y los omite sin error. Se puede re-ejecutar las veces necesarias.

**Limitacion conocida**: si una entidad ya existe, su `initial_balance` NO se actualiza en re-corridas (solo se omite). Si hay que corregir saldos despues de un apply parcial **pre go-live**, usar `--reset-org`:

```bash
./venv/bin/python scripts/migrate_metarecycling.py [...] --apply --reset-org
```

`--reset-org` soft-deletea la org existente (`is_active=False`) antes de re-aplicar limpio. **Solo viable pre go-live**, mientras nadie esta operando. Post go-live (operaciones en curso) las correcciones se hacen via UI/API normales, no via re-corrida.

## Skip de fases

Para no resemilla stock o activos en re-corridas:

```bash
--skip-phase 11,12
```

Fases:

| # | Nombre |
|---|---|
| 1 | Org + admin |
| 2 | BusinessUnits |
| 3 | Warehouse |
| 4 | CategoriaMateriales |
| 5 | CategoriaGastos |
| 6 | CategoriaTerceros |
| 7 | MapeoUN (referencia, no escribe) |
| 8 | Materiales |
| 9 | Terceros |
| 10 | Cuentas |
| 11 | Inventario |
| 12 | ActivosFijos |

## Estructura del Excel

9 hojas (la 4 `MapeoUN` no se carga, solo orienta `Materiales`):

1. **CategoriaMateriales** — `nombre`, `descripcion`
2. **CategoriaGastos** — `nombre`, `padre` (vacio = raiz), `es_directo` (SI/NO, solo en raiz)
3. **CategoriaTerceros** — `nombre`, `tipo_comportamiento`, `padre`. OPCIONAL: las 7 default ya vienen con la org.
4. **MapeoUN** — `categoria_material`, `unidad_negocio_default`, `notas`
5. **Materiales** — `codigo`, `nombre`, `categoria`, `unidad_negocio` (override opcional), `unidad`, `descripcion`
6. **Terceros** — `nombre`, `identificacion`, `email`, `telefono`, `direccion`, `categorias` (CSV), `saldo_inicial`
7. **Cuentas** — `nombre`, `tipo` (cash/bank/digital), `saldo_inicial`, `numero_cuenta`?, `banco`?
8. **Inventario** — `material_codigo`, `bodega` (default Principal), `cantidad`, `costo_unitario`, `fecha`?
9. **ActivosFijos** — `nombre`, `codigo_activo`?, `fecha_compra`, `valor_compra`, `valor_residual`, `vida_util_meses`, `fecha_inicio_depreciacion`, `depreciacion_acumulada`, `categoria_gasto`, `proveedor`?, `cuenta_pago`?, `unidad_negocio`?, `notas`?

**Regla activos fijos**: si `proveedor` Y `cuenta_pago` estan vacios → `historical_load=True` (no genera MoneyMovement, ver decision #46). Si hay `proveedor` → crea `asset_purchase` (afecta balance del proveedor). Si hay `cuenta_pago` → crea `asset_payment` (afecta cuenta). No se pueden poner ambos.

**Regla `vida_util_meses`**: convertida internamente a `depreciation_rate = 100 / vida_util_meses`. Vehiculos 60, maquinaria 120, herramientas 36.

## Verificacion automatica

Al final del `--apply` (si no se uso `--skip-phase`):

| Check | Como |
|---|---|
| # materiales activos | exacto (cuenta filas hoja Materiales) |
| # terceros activos | exacto (cuenta filas hoja Terceros) |
| Sum cuentas operativas | tolerancia $100 (vs suma `saldo_inicial` hoja Cuentas) |
| # activos fijos | exacto |
| Sum current_value activos | tolerancia $100 (vs `valor_compra - dep_acumulada`) |
| Balance General cuadra | `verification.is_balanced == true` o `diff <= tolerancia` |

Si algun check falla, el script aborta con exit code 1 y dump del diff.

## Rollback (pre go-live)

```bash
./venv/bin/python scripts/migrate_metarecycling.py [...] --apply --reset-org
```

Esto soft-deletea la org `MetaRecycling` y la vuelve a crear desde cero con el Excel actualizado.

**Post go-live** no hay rollback automatico — restaurar desde backup pre-deploy si hace falta deshacer.

## Notas sobre balance historico

`adjustment_increase` siembra `MaterialCostHistory.transaction_date = now()`. Consultas de Balance Detallado con `as_of_date < go-live` muestran el inventario con costo del fallback de decision #41 (ultimo adjustment), NO con el costo promedio historico de Lovable.

Es comportamiento aceptado — el go-live es el punto cero contable de EcoBalance. Para consultas historicas de inventario pre-corte, usar Lovable como archivo.

## Riesgos conocidos

| Riesgo | Mitigacion |
|---|---|
| Saldos de Lovable no cuadran contablemente | El check final detecta el descalce. Eduardo Chain investor (`-262_534_500`) absorbe la diferencia esperada (capital + utilidades). |
| Mapeo categoria→UN mal asignado | Revisar hoja `MapeoUN` antes de `--apply`. Re-correr con Excel ajustado es idempotente (con `--reset-org`). |
| Costo promedio recalculado difiere de Lovable | `adjustment_increase` con `unit_cost` siembra el costo. Compras posteriores recalculan. Si Lovable tenia costos sucios, aceptar snapshot como nueva linea base. |
| Activo con saldo pendiente sin proveedor en Lovable | El cliente enriquece `proveedor` en la hoja `ActivosFijos` antes de aplicar. Si queda vacio, activo se carga `historical_load=True` y la deuda no se modela (riesgo manejable). |
| Cliente corre `--apply` sin dry-run previo | Documentado aqui: SIEMPRE dry-run primero. |

## Procedencia del Excel

El Excel maestro lo arma la **AI de Lovable** (no a mano):

1. Daniel entrega el template `migration_metarecycling_template.xlsx` a la AI de Lovable.
2. La AI consulta Supabase y llena las 9 hojas + entrega el Excel completo.
3. Daniel/cliente revisa hojas criticas.
4. Daniel corre `--dry-run` en dev local. Ajusta Excel si hace falta. `--apply`.

96 terceros + 45 materiales + 80 stock + 5 assets — la transcripcion manual es bug humano garantizado.
