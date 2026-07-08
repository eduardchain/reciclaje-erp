# Plan: Rentabilidad por UN sin Doble Partida + Sección Pasa Mano

**Requerimiento A** (reunión cliente 2026-07-06). Estado: PENDIENTE APROBACIÓN QA.

## 1. Contexto y decisiones tomadas con el cliente

El reporte Rentabilidad por UN (`GET /reports/profitability-by-business-unit`) mezcla hoy datos de Doble Partida (Pasa Mano) con los de bodega, distorsionando el análisis:

| # | Fuga verificada en código | Ubicación |
|---|---|---|
| 1 | `de_profit` (margen DP) se suma a la utilidad bruta de cada UN vía el material de las líneas DP. Ventas por UN excluyen DP pero la utilidad bruta no → columnas inconsistentes | `reports.py:3312-3338, 3468` |
| 2 | Comisiones de DP contaminan las UN de bodega: la query de `commission_accrual` no filtra `Sale.double_entry_id IS NULL` (las comisiones DP sí llevan `sale_id`, confirmado en `double_entry.py:340`) | `reports.py:3402-3415` |
| 3 | Fletes/bonos de DP registrados como gasto general se prorratean 100% entre UNs de bodega (la base de prorrateo ya excluye DP → bodega absorbe gastos ajenos) | modelo de datos |

**Nota**: la base de prorrateo (`_get_purchases_by_bu`) es **$ de compras liquidadas** (no kg) y **ya excluye DP** desde el diseño original (`double_entry_id IS NULL`, commit `3a1fd0d`). No se toca.

**Decisiones del cliente (Daniel, 2026-07-07):**
1. Base de prorrateo se mantiene: $ compras liquidadas.
2. Pasa Mano recibe SOLO gastos directos asignados explícitamente (+ sus comisiones). Sin prorrateo automático de generales.
3. `de_profit` se elimina de las filas por UN → se muda a una sección Pasa Mano separada.
4. Mecanismo de asignación: **UN especial de sistema "Pasa Mano"** (Opción 1 aprobada).

## 2. Alcance

**Entra:**
- UN de sistema "Pasa Mano" (modelo + migración + seed + guards).
- Fix comisiones DP (fuga #2).
- Reporte: tabla por UN solo-bodega + sección Pasa Mano (fuga #1).
- Frontend: `ProfitabilityBUPage` actualizada + exclusiones en selectores.
- Puente táctico fuga #3: el cliente podrá asignar fletes/bonos de DP como gasto directo a la UN Pasa Mano desde el día uno.

**NO entra (requerimiento B, discusión aparte):**
- Fletes/bonos como ítem de liquidación por operación.
- Cambios al P&L (requerimiento C).

## 3. Backend

### 3.1 Modelo + migración

- `BusinessUnit.system_code: str | None` — nueva columna nullable (`business_unit.py`). Valor `"double_entry"` identifica la UN Pasa Mano. Lookup por código (no por nombre → el cliente puede renombrarla).
- **Migración Alembic**: agrega columna + **backfill**: crea UN `Pasa Mano` con `system_code='double_entry'` para cada organización existente (idempotente: solo si la org no tiene ya una UN con ese system_code). Patrón de migración `3acfc5ab3d68` (seed Socios, decisión #47).
- **Seed org nueva** (`services/organization.py`): crear la UN Pasa Mano al crear la org. ⚠️ Nota: hoy las orgs NO reciben ninguna BusinessUnit por defecto — este es un **path de seed nuevo** (no existe un "seed de BUs" al cual sumarse; el seed existente crea categorías de terceros, no UNs).
- ⚠️ Correr `alembic upgrade head` en dev (5434) y test (5433). Producción SOLO vía `/deploy`.

### 3.2 Guards (validaciones)

| Regla | Dónde | Respuesta |
|---|---|---|
| No asignar materiales a UN sistema | `services/material.py` create/update (validar `business_unit_id`) | 400 "No se pueden asignar materiales a la UN Pasa Mano" |
| No eliminar (soft delete) UN sistema | endpoint DELETE `business_units.py` | 400 |
| No desactivar (`is_active=False`) UN sistema | endpoint PATCH | 400 (rename SÍ permitido) |
| No incluir UN sistema en `applicable_business_unit_ids` (gastos compartidos) | validación en creación de MoneyMovement / ScheduledExpense / FixedAsset (los 3 exponen el campo — verificado) | 422 |
| **No incluir UN sistema en reclasificación compartida** (gap detectado por QA: `PATCH /money-movements/{id}/classification`, `UpdateClassificationRequest` acepta ambos campos sin guard — bypass real del guard de creación) | `update_classification` en `services/money_movement.py` | 422 |
| Reclasificación DIRECTA a UN sistema (`business_unit_id`) | — | **PERMITIDA** (Gustavo puede reclasificar un flete existente a Pasa Mano — es deseable) |
| No incluir UN sistema en `default_applicable_business_unit_ids` de ExpenseCategory (5º punto de entrada; no es bypass real — el backend no aplica defaults, solo prefill de frontend — pero sin guard produce forms pre-llenados que revientan 422 al guardar) | `services/expense_category.py` create/update | 422 |
| `default_business_unit_id = UN sistema` en ExpenseCategory | — | **PERMITIDA** (ej. categoría "Bonos Foráneos" con default directo a Pasa Mano) |
| Asignación DIRECTA de gasto a UN sistema | — | **PERMITIDA** (es el propósito) |

**Total: 5 puntos de entrada con guard de compartido** (create MM, ScheduledExpense, FixedAsset, PATCH classification, ExpenseCategory defaults) — cada uno con test propio.

### 3.3 Reporte `get_profitability_by_business_unit`

- `all_bu_keys` excluye la UN sistema → no aparece como fila de la tabla bodega.
- **Sección 4 (de_profit)**: se elimina del cálculo por UN. `total_gross_profit` de cada UN = `revenue - cogs`. El total DP se calcula aparte para la sección Pasa Mano.
- **Sección 6 (comisiones)**: JOIN a `Sale` + filtro `Sale.double_entry_id.is_(None)` para la tabla bodega. Las comisiones DP se acumulan aparte para la sección Pasa Mano.
- **Sección 5 (gastos)**: ⚠️ CRÍTICO — un gasto directo con `business_unit_id = UN sistema` hoy caería en `"unassigned"` (por `key = bu_id if bu_id in bu_names else "unassigned"`). Manejar explícito: si `bu_id == pasamano_bu_id` → acumular en `pasamano_direct` (con desglose por categoría), NO en unassigned.
- **Nueva sección Pasa Mano** en el response:
  - `sales_total`: Σ ventas de DPs liquidadas en el período (lado venta)
  - `purchases_total`: Σ compras (lado compra)
  - `gross_profit`: Σ `(sale_unit_price - purchase_unit_price) × quantity` (= de_profit actual; debe cuadrar con "Utilidad Pasa Mano" del P&L)
  - `commissions`: Σ commission_accrual de ventas DP del período
  - `direct_expenses` + `direct_expenses_detail[]` (por categoría)
  - `net_profit` = gross_profit − commissions − direct_expenses
  - `net_margin` = net_profit / sales_total
- **Totales**: `totals` sigue siendo solo-bodega (consistente con la tabla). Nuevo campo `grand_total_net` = bodega net + pasamano net (para la línea final "Total General").

### 3.4 Schemas (`schemas/reports.py`)

- `BusinessUnitProfitability`: eliminar campo `de_profit` (breaking OK, frontend se actualiza junto).
- Nuevo `DoubleEntryProfitability` con los campos de 3.3.
- `ProfitabilityByBUResponse`: + `double_entry: DoubleEntryProfitability`, + `grand_total_net: float`.
- `BusinessUnitResponse`: exponer `system_code` (frontend lo necesita para filtrar selectores).

### 3.5 Sin cambios

- `_get_purchases_by_bu` / `_prorate_expense` (base $ compras intacta).
- Reporte de Gastos (#44): la UN Pasa Mano aparece como grupo natural — comportamiento deseado, cero cambios.
- Costo Real por Material: UN sin materiales → ausente naturalmente.
- Permisos RBAC: mismo endpoint, mismo permiso (`reports.view` / `reports.view_profitability`).

### 3.6 ⚠️ Advertencias de implementación (QA — no romper colaterales)

1. **Colisión de nombres `de_profit`**: existen DOS `de_profit` distintos. El que se elimina es `BusinessUnitProfitability.de_profit` (schema `reports.py:556`) + la sección by-BU (`reports.py:3312-3338, 3468`). **NO tocar** el `de_profit` local de `_calculate_profit` (líneas ~258, 326, 502, 509, 663) — alimenta `double_entry_profit` del P&L y es un campo completamente distinto con el mismo nombre. PROHIBIDO find-replace global de `de_profit`.
2. **NO "sincronizar" `_compute_expense_allocations`**: la exclusión de la UN sistema de `bu_names` va SOLO en `get_profitability_by_business_unit` (~3269-3277), NUNCA en `_compute_expense_allocations` (~3718-3726) — el Reporte de Gastos DEBE mostrar la UN Pasa Mano como grupo. Dejar comentario explícito en ambos lados.
3. **Limitación conocida (pre-existente, NO arreglar acá)**: en la sección Pasa Mano, `gross_profit` filtra por `DoubleEntry.liquidated_at` pero las comisiones filtran por `MoneyMovement.date` — misma inconsistencia que ya tiene la tabla bodega. El test de paridad con P&L cubre solo `gross_profit`. Documentar, no tocar.

## 4. Frontend

| Archivo | Cambio |
|---|---|
| `types/reports.ts` | Quitar `de_profit`, agregar `DoubleEntryProfitability`, `grand_total_net`, `system_code` en BU |
| `pages/reports/ProfitabilityBUPage.tsx` | Quitar columna DP de la tabla. Card "Pasa Mano" debajo de la tabla: Ventas, Compras, Margen bruto, (−) Comisiones, (−) Gastos directos (expandible por categoría), **Utilidad neta + %**. Línea final "Total General" (bodega + pasamano). Mobile-first: card `grid-cols-1 sm:grid-cols-2`, tabla ya tiene overflow wrapper |
| `components/shared/BusinessUnitAllocationSelector.tsx` | Single-select (UN directa): UN Pasa Mano VISIBLE. Multi-select (compartido): UN Pasa Mano EXCLUIDA |
| `pages/materials/MaterialFormDialog.tsx` | Excluir UN sistema del selector |
| `pages/config/` (BusinessUnitsPage) | Badge "Sistema" en la fila, deshabilitar eliminar |
| Excel export del reporte | Reflejar nueva estructura (tabla bodega + bloque pasamano) |

Verificación responsive obligatoria (390px + desktop 1280px) según CLAUDE.md.

## 5. Tests (regla obligatoria CLAUDE.md)

**Fixture nuevo**: org con 2 UNs bodega + venta bodega liquidada con comisión + DP liquidada con comisión + gasto general + gasto directo a UN bodega + gasto directo a UN Pasa Mano.

| Test | Verifica |
|---|---|
| `test_pasamano_bu_created_on_new_org` | Seed crea UN con system_code |
| `test_migration_backfill_idempotent` | (vía servicio) segunda corrida no duplica |
| `test_material_cannot_use_system_bu` | 400 al crear/editar material con UN sistema |
| `test_system_bu_cannot_be_deleted` / `_deactivated` | 400; rename OK |
| `test_shared_expense_rejects_system_bu` | 422 en applicable_business_unit_ids (create MoneyMovement) |
| `test_shared_scheduled_expense_rejects_system_bu` | 422 (ScheduledExpense) |
| `test_shared_fixed_asset_rejects_system_bu` | 422 (FixedAsset) |
| `test_reclassify_shared_to_system_bu_rejected` | 422 en PATCH /classification con UN sistema en applicable (gap QA) |
| `test_reclassify_direct_to_system_bu_allowed` | 200 en PATCH /classification con business_unit_id = UN sistema |
| `test_expense_category_default_shared_rejects_system_bu` | 422 en default_applicable_business_unit_ids |
| `test_expense_category_default_direct_to_system_bu_allowed` | 201 con default_business_unit_id = UN sistema |
| `test_direct_expense_to_system_bu_allowed` | 201 |
| `test_bu_rows_exclude_dp_commissions` | Comisiones DP NO caen en UNs bodega (bug $57M) |
| `test_bu_rows_have_no_de_profit` | total_gross_profit = revenue − cogs |
| `test_pasamano_section_totals` | ventas/compras/margen/comisiones/gastos directos/neta correctos |
| `test_pasamano_margin_matches_pnl` | pasamano.gross_profit == P&L double_entry_profit (paridad) |
| `test_pasamano_direct_expense_not_in_unassigned` | El gasto directo a UN sistema no fuga a "Sin Asignar" (ni en este reporte ni en el de Gastos #44) |
| `test_org_without_dp_activity` | Sección pasamano en ceros, tabla bodega intacta |
| Actualizar tests existentes de `TestProfitabilityByBU` | Referencias a `de_profit` |

## 6. Criterios de aceptación

1. La tabla por UN muestra SOLO operación de bodega — ventas, costos, utilidad bruta, gastos y comisiones consistentes entre sí (sin DP en ninguna columna).
2. Las comisiones de pasamano ya no aparecen en la UN Chatarra.
3. La sección Pasa Mano muestra: ventas, compras, margen bruto (== P&L), comisiones, gastos directos, utilidad neta y %.
4. Gustavo puede registrar un gasto directo a "Pasa Mano" desde los formularios de tesorería existentes.
5. Un gasto compartido no puede incluir la UN Pasa Mano; un material no puede pertenecer a ella.
6. El prorrateo de generales entre UNs bodega da los mismos valores que antes del cambio (base intacta).
7. Total General = neta bodega + neta pasamano.

## 7. Riesgos

- **Breaking schema** (`de_profit` eliminado): frontend y backend van en el mismo commit/deploy. Sin consumidores externos del API.
- **Migración con seed**: idempotente; si una org ya tiene una UN llamada "Pasa Mano" (sin system_code), se crea otra con system_code — mitigación: la migración primero intenta adoptar una UN existente con nombre exacto "Pasa Mano" sin materiales; si tiene materiales, crea nueva con nombre "Pasa Mano (DP)".
- **Datos históricos**: gastos de fletes DP ya registrados como generales siguen prorrateados a bodega en periodos pasados (no se reclasifican). El cliente decide si reclasifica manualmente con `PATCH /classification` (decisión #39).

## 8. Estimación

Backend (modelo+migración+guards×5+reporte+schema): ~medio día largo. Frontend: ~medio día. Tests: ~19 nuevos + ajustes a `TestProfitabilityByBU`. Total: **1.5 días** de trabajo efectivo. Sin dependencias externas. Deploy sin downtime (migración aditiva).

---

**Historial de revisión:**
- v1 (2026-07-07): plan inicial.
- v2 (2026-07-07): incorpora revisión QA — gap del endpoint de reclasificación (guard + 2 tests), guard en ExpenseCategory defaults (5º punto de entrada, detectado en verificación posterior; no-bypass pero consistencia UX), advertencias de implementación §3.6 (colisión `de_profit`, no sincronizar `_compute_expense_allocations`, limitación de fechas pre-existente), aclaración seed (path nuevo), tests por cada punto de entrada. Veredicto QA: OK condicionado → condiciones incorporadas.
