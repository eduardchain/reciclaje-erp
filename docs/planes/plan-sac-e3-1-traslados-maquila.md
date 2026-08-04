# Plan SAC E3.1 — Traslados dos pasos + Maquila intersede + P&L por sede

**Versión 1.2 — 2026-07-23.** Base: `requerimientos-funcionales.md` v0.5 (§5, §5.1-5.4, §7.5, §10, §12), `plan-ejecucion-fase1.md` Entrega 3. Ciclo de trabajo §5 (plan → QA → GO → código → informe → pruebas Daniel → commit develop).

> **Changelog v1.1 → v1.2 (cierre del ciclo de código):**
> - **C1 resuelto** (condición del GO): `inventory_adjustments.transfer_id` NO se serializa en ningún response schema — solo modelo + migración (precedente #75); `GET /inventory/adjustments` byte-idéntico por construcción.
> - **Re-QA del informe: 🟢 GO sin condiciones (2026-07-23)** — evidencia B1/M1/M2/N1-N5 verificada en código y tests con líneas citadas; cero hallazgos nuevos. Cosmético: docstring del guard tránsito alineado al orden real de los checks (`is_transit` primero — más barato para prod; la garantía prod-inerte se sostiene por ambas ramas).
> - **Golden ×3 orgs EJECUTADO 2026-07-23** (adelantado a pedido de Daniel, ya no diferido al viernes): **0 diffs reales** en 45 capturas; las 11 migraciones E1→E3.1 aplicaron limpias sobre réplica fresca. Además de los 3 diffs declarados (warehouses +3 claves, P&L +2 en 0.0) aparecieron claves aditivas **siempre null** en `GET /money-movements` (+4) y `GET /money-accounts` (+1): columnas E1 de los modelos que esos endpoints (`response_model=dict` + ORM → jsonable_encoder) serializan solos — allowlist con valor exacto null, documentado en informe §4. Harness persistido: `backend/scripts/golden_capture.py` / `golden_diff.py`; evidencia `docs/planes/evidencia-golden-2026-07-23/`. La org SAC dev renace post-réplica con `backend/scripts/seed_sac_org.py` (maestros + 37 materiales, ~2s).

> Este plan se construyó con un panel adversarial de 3 lentes (no-regresión / consistencia con decisiones / completitud) sobre 5 facetas de diseño. Los **31 hallazgos** (9 bloqueantes, 13 mayores, 9 menores) están resueltos en el cuerpo; el Apéndice A los tabula uno a uno para trazabilidad del QA.

> **Changelog v1.0 → v1.1 (correcciones del Micro-QA):**
> - **B1 (bloqueante) — E8 reconciliado con invariante #1.** La merma báscula NO puede ir por `cost_adjustment`/#65 (esa línea la produce **solo** `incorporate/remove_from_pool`, prohibidos en traslados por invariante #1). Reescrito: la merma es un **`InventoryAdjustment` `decrease` sobre la bodega de tránsito al avg org-wide** → aterriza en `adjustment_net` (**Ganancia/Pérdida por Ajustes de Inventario**, `reports.py:611`); un decrease al avg **no mueve el pool** (honra invariante #1). Verificado en código: `adjustment_net = Σ CASE WHEN quantity>0 THEN total_value ELSE -total_value`.
> - **M1 (mayor) — E13 recalibrado + filtro de comisiones corregido.** El schema de `MoneyMovement` **no tiene `warehouse_id` de captura de usuario** → `expense`/`service_income`/`tp_adjustment`/`commission_accrual` nacen con sede NULL. El P&L por sede fragmenta lo que **sí** lleva sede: **ventas** (`Sale.warehouse_id`), **COGS**, **comisiones** (por `Sale.warehouse_id`, la query ya hace `.outerjoin(Sale)` — **NO** por `MoneyMovement.warehouse_id`, que daría $0) y el **par de maquila** (query separada, líneas propias E4). **Gastos operativos y service_income salen $0 por sede** hasta que exista captura de sede en gastos (caja-menor-por-sede, E4/E5). El test de oro usa fixture con **comisión ≠ 0** (para no pasar en falso con $0==$0).
> - **M2 (mayor) — desviación "vendido" declarada + elevada.** El §5.4 congelado pide bloquear la anulación de un traslado cuyo material ya se **vendió**; E3.1 aplica warn-no-bloquea (#76) porque **no hay corrupción** (no existe `intersede_discharge` en E3.1 — anular solo revierte el `intersede_send` al estado previo; el stock negativo avisa). Declarado como desviación consciente en §2.7 + **Q-E3.1-d** a Johana/Hugo.
> - **Menores N1-N5** y sugerencias (etiqueta "maquila intersede" en vez de "del horno", N5 allowlist inline, N4 runbook crea tarifa, N3 recibido>despachado → held, N2 test multi-línea, N1 `invalidateAfterTransfer`) corregidos en el cuerpo.

---

## 0. Alcance

**E3 completo** = Maquila y planta. Se parte en dos sub-ciclos (como E2 → B/B.2/C/D):
- **E3.1 (este plan)**: traslados 2 pasos CV→JM / BOG→JM + `intersede_send` + par de **maquila intersede** ($1.500/kg, tarifa `maquila_intersede_cv_jm` — se causa al **recibir el traslado**, no al fundir; "del horno" era etiqueta imprecisa) + motor de P&L por sede.
- **E3.2 (siguiente)**: molino/horno/crisol como transformaciones de planta conectadas a kg + par de maquila del **crisol** ($300/kg). Reusa la infraestructura del par que E3.1 construye.

**DENTRO de E3.1:**
1. Traslado en dos pasos (despacho → recepción confirmada) con bodega de tránsito, **cabecera + líneas** (multi-material).
2. `intersede_send` por línea aportante sobre kg **recibidos** × factor.
3. Par de maquila intersede ($1.500/kg equivalente) — 2 tipos MoneyMovement nuevos, **por línea aportante**.
4. Tolerancia (3-5%) con `DiscrepancyTask` + resolución desde el traslado.
5. Motor de **P&L por sede** — fragmenta ventas + COGS + comisiones (por `Sale.warehouse_id`) + par de maquila; gastos/service_income $0 por sede hasta E4 (M1); maquila excluida del consolidado.

**FUERA de E3.1 (E3.2 / E4 / E5):**
- Horno/crisol, transformaciones de planta, par de crisol → **E3.2**.
- CV-TRANSITO / BOG→CV willard, flete BOG-BAQ, conciliación semanal → **E4**.
- Reporte/dashboard pulido "P&L por sede + consolidado", panel de excepciones unificado → **E5** (E3.1 solo expone el filtro `warehouse_id` en el P&L existente y escribe las `DiscrepancyTask`).

**Feature flags (ya existen en `SETTING_DEFAULTS`, nadie los lee aún — E3.1 los cablea):** `two_step_transfers_enabled` (default false, gobierna el módulo), `internal_maquila_enabled` (default false, gobierna el par), `transfer_tolerance_pct` (default 0.05). Las 3 empresas en producción quedan **byte-idénticas** por defaults + gating.

---

## 1. Decisiones de encuadre (contrato único — reconcilia las 5 facetas)

| # | Decisión | Racional |
|---|---|---|
| E1 | Tabla **`transfers` + `transfer_lines`** (cabecera + líneas, multi-material). NO extender `transfer_between_warehouses` (1-paso, sin entidad). NO mono-material. | El doc describe camiones con varios aportantes; `intersede_send`, tolerancia y par se evalúan **por línea** (una línea dentro de tolerancia, otra fuera). Precedente cabecera+líneas: `inbound_orders`. Resuelve bloq-8, menor-25. |
| E2 | **Todo es por línea**: `is_contributor`, `quantity_received`, tolerancia, `kg_lead_equivalent`, `intersede_send`, par de maquila. El estado de cabecera es **derivado** de las líneas. | Coherencia con el `intersede_send` por línea. El par hereda `business_unit_id` del material **de esa línea** (#58/#59). Resuelve bloq-8, mayor-13. |
| E3 | Campo de enlace del par = **`transfer_pair_id`** (el real, `money_movement.py:203`). NUNCA `linked_movement_id` (no existe). | Facetas C/E lo nombraron mal. Resuelve bloq-3, menor. |
| E4 | `internal_maquila_income` / `internal_maquila_expense` = **líneas propias del P&L**, JAMÁS plegadas en `service_income` ni `operating_expenses` compartido. | Si se pliegan en `service_income`, rompen el drill-down #49 y la conciliación #59 en la vista por-sede. Resuelve bloq-1, bloq-5. |
| E5 | `source_type='transfer'`, `source_id=transfer.id`. Set guard = **`INTERNAL_MAQUILA_MOVEMENT_TYPES`** (acotado; "plant" es E3.2). | Ancla al documento; nombre no se renombra en E3.2. Resuelve menor-25, P2. |
| E6 | **Nunca bloquear** (#76): fórmula ausente al recibir → recibe físico + retiene kg/par con `DiscrepancyTask`, NO rollback+400. | Faceta C proponía 400 → rompe #76 (material queda en tránsito sin poder recibirse). Resuelve mayor-14, mayor-22. |
| E7 | **Snapshot de fórmula AL DESPACHO**; el kg usa ese factor al recibir (`kg_equiv = quantity_received × factor_despacho`). Warn si la vigente difiere. | Append-only #35: un cambio de factor a mitad de traslado no debe alterar la maquila en silencio. "El traslado nace con sus reglas". Resuelve mayor-22. |
| E8 | **Bodega de tránsito queda en CERO tras cada recepción.** La merma báscula (recibido < despachado, dentro de tolerancia) se reconoce como **`InventoryAdjustment` `decrease` sobre la bodega de tránsito al `unit_cost=current_average_cost` org-wide (#5)** → aparece en **`adjustment_net`** ("Ganancia/Pérdida por Ajustes de Inventario", `reports.py:611`) como pérdida. **NO usa `cost_adjustment` ni la línea #65** (esa la produce solo `incorporate/remove_from_pool`, prohibidos en traslados por invariante #1). Un `decrease` al avg **no cambia el pool** → invariante #1 intacto. | Un residual permanente en JM-TRANSITO valuado a costo org-wide (#5) infla el Balance con toneladas fantasma. La merma es un ajuste **separado** de los movimientos de traslado (que sí siguen invariante #1). Resuelve mayor-16, mayor-17, **bloq-B1(v1.1)**. |
| E9 | **Anulación desde el servicio de traslado**, no vía `annul()`. El servicio marca ambos MM `annulled` + `_reverse_effects` (rama `pass` inerte) en la misma tx que revierte inventario + `intersede_send`. | `annul()` se auto-bloquea con el guard `INTERNAL_MAQUILA_MOVEMENT_TYPES` (mismo deadlock que atrapamos en ciclo C D7b). Resuelve bloq-2, bloq-4, P5. |
| E10 | Gating: `two_step_transfers_enabled` gatea el **router** (`require_org_flag`); `internal_maquila_enabled` gatea la **emisión del par INLINE** (`get_org_setting`), nunca como dependency. | Permite el caso "kg sin maquila" (two_step on / maquila off). Resuelve mayor-15. |
| E11 | **Fecha canónica única = `receipt_date`** para los 3 efectos (par, intersede, inventario físico de recepción). El MCH va a HOY (#61 H1a). | Simetría del evento en cortes históricos as-of. Resuelve menor-18. |
| E12 | **`is_transit` = adición GATE DURO** (como `is_receiving` #80): tabla compartida. Golden incluye `GET /warehouses` ×3 orgs; guard backend impide operar contra bodegas de tránsito. | `warehouses` es compartida. Resuelve mayor-10, mayor-21. |
| E13 | **P&L por sede de ventas + COGS + comisiones + par de maquila** (decisión de Daniel 2026-07-20, recalibrada M1). `warehouse_id` fragmenta lo que **efectivamente lleva sede**: ventas (`Sale.warehouse_id`, `sale.py:81`), COGS, comisiones (por `Sale.warehouse_id` — la query ya hace `.outerjoin(Sale)`, `reports.py:897`) y el par de maquila (líneas propias, query separada). **Gastos operativos y `service_income` salen $0 por sede** — sus writers de MoneyMovement **no capturan sede** (el schema no tiene el campo); la captura de gasto-por-sede (caja-menor-por-sede) es **E4/E5**. DP/transformaciones/ajustes solo en consolidado. | El schema `MoneyMovement` no expone `warehouse_id` de captura → filtrar gastos/comisiones por `MoneyMovement.warehouse_id` daría $0 (bug M1). "Utilidad cero JM" queda **parcialmente visible** en E3.1 (JM muestra +ingreso maquila; sus costos de planta llegan con gasto-por-sede en E4 — ver **Q-E3.1-e**). Resuelve mayor-23, Faceta D P1, **M1(v1.1)**. |

---

## 2. Contratos

### 2.1 Modelo de datos

**`transfers` (cabecera)** — `app/models/transfer.py` (nuevo):

| Columna | Tipo | Notas |
|---|---|---|
| `id` | GUID PK | |
| `organization_id` | GUID FK→organizations CASCADE | OrganizationMixin |
| `transfer_number` | Integer | Consecutivo por org, advisory lock (patrón `inbound_order._generate_order_number`). UNIQUE `(org, number)`. |
| `from_warehouse_id` | GUID FK→warehouses RESTRICT | Sede origen (CV o BOG). |
| `to_warehouse_id` | GUID FK→warehouses RESTRICT | Sede destino física final (JM). |
| `transit_warehouse_id` | GUID FK→warehouses RESTRICT | Bodega virtual de tránsito, resuelta al despacho. |
| `dispatch_date` | DateTime(tz) | Fecha negocio despacho. |
| `received_date` | DateTime(tz) nullable | Se puebla al recibir (paso 2). |
| `status` | String(16) `server_default='dispatched'` | `dispatched \| received \| held_discrepancy \| annulled` — **derivado de las líneas** (E2), persistido para la bandeja. |
| `created_by`/`received_by` | GUID FK→users SET NULL nullable | |
| `notes` | String(500) nullable | |
| `annulled_reason`/`annulled_at`/`annulled_by` | String(500)/DateTime(tz)/GUID | Auditoría anulación. |
| `created_at`/`updated_at` | DateTime(tz) `server_default=now()` | TimestampMixin. |

**`transfer_lines`** — `app/models/transfer.py`:

| Columna | Tipo | Notas |
|---|---|---|
| `id` | GUID PK | |
| `organization_id` | GUID FK CASCADE | |
| `transfer_id` | GUID FK→transfers CASCADE | |
| `material_id` | GUID FK→materials RESTRICT | |
| `quantity_dispatched` | Numeric(15,4) | CHECK `> 0`. |
| `quantity_received` | Numeric(15,4) nullable | CHECK `IS NULL OR >= 0` (**ge=0**, permite recibido=0 = merma total, resuelve bloq-7). |
| `resolved_quantity` | Numeric(15,4) nullable | Cantidad final tras resolver discrepancia (preserva la báscula original en `quantity_received`). |
| `unit_cost` | Numeric(15,2) | Snapshot `current_average_cost` ORG-WIDE al despacho (#5). |
| `is_contributor` | Boolean `server_default=false` | Snapshot al despacho: tenía `MaterialConversionFormula` vigente. |
| `conversion_formula_snapshot` | JSONB nullable | Snapshot de la fórmula vigente **AL DESPACHO** (E7). NULL si no aportante. |
| `kg_lead_equivalent` | Numeric(14,4) nullable | `quantity_efectiva × factor_snapshot`. NULL hasta emitir. |
| `maquila_amount` | Numeric(15,2) nullable | `kg_lead_equivalent × tarifa`. |
| `discrepancy_task_id` | GUID FK→discrepancy_tasks SET NULL nullable | Poblado si la línea salió de tolerancia. |
| `effects_emitted` | Boolean `server_default=false` | True cuando intersede + par de esa línea ya se emitieron (evita doble emisión al resolver). |
| `created_at`/`updated_at` | DateTime(tz) `server_default=now()` | |

**Estado de cabecera derivado (E2):** `received` si **todas** las líneas tienen `effects_emitted=True` (o son no-aportante ya movidas); `held_discrepancy` si **≥1** línea tiene `discrepancy_task_id` abierta; `dispatched` mientras no se reciba; `annulled` por anulación. Se persiste `status` y se recalcula en cada transición (helper `_recompute_status`).

**`warehouses` — 2 columnas nuevas** (`app/models/warehouse.py`):
- `is_transit` Boolean `server_default='false'` NOT NULL — bodega virtual de tránsito intersede.
- `transit_target_warehouse_id` GUID FK→warehouses SET NULL nullable — la bodega de tránsito apunta a su bodega física destino (mecanismo único de ruteo, resuelve menor-31; E4 lo reusa para CV-TRANSITO sin migración).

**Reusadas sin tocar:** `discrepancy_tasks` (E1, `app/models/exception_task.py::DiscrepancyTask`, `severity` CHECK `normal|high|critical`, `entity_type/entity_id` polimórficos), `kg_ledger_accounts`/`kg_ledger_movements` (`intersede`, `source_type` String(40)), `service_tariffs` (`maquila_intersede_cv_jm`, `per_kg_lead`).

### 2.2 Migración

Revisión encadenada al head actual **`f6a7b8c9d0e1`** (verificado con `alembic heads`). Naming: `<hash>_sac_e3_transfers.py`. **Todo aditivo, nullable/server_default, cero RENAME/DROP/backfill.**

1. `ADD COLUMN warehouses.is_transit` (bool, `server_default='false'`).
2. `ADD COLUMN warehouses.transit_target_warehouse_id` (GUID FK self, nullable, `ondelete='SET NULL'`).
3. `CREATE TABLE transfers` + `transfer_lines` (DDL en §2.1; FKs **sin nombre explícito** → PG asigna `<tabla>_<col>_fkey` = paridad con `create_all`; CHECKs/UNIQUEs también en el modelo — D13).
4. `ADD COLUMN inventory_adjustments.transfer_id` (GUID FK→transfers, nullable, `ondelete='SET NULL'`) — enlaza los ajustes hijos de merma/excedente al traslado para el cascade de anulación (§2.7); NULL para el 100% de los ajustes existentes y futuros no-traslado. Espejar la columna en el modelo `InventoryAdjustment` (D13, N-d). **C1 (QA): `transfer_id` NO se expone en el response schema de ajustes en E3.1** — es interno, solo para el cascade (precedente #75: `purchase_retentions.third_party_id` existe sin serializarse) → la serialización de `GET /inventory/adjustments` queda byte-idéntica por construcción para las 3 orgs prod, sin necesidad de ampliar el golden.
5. Permiso `inventory.transfer_receive` en tabla `permissions` (dual-write triple: migración + `PERMISSIONS_CATALOG` `services/role.py:19` + `MODULE_DISPLAY_NAMES` `services/role.py:213`; **sin asignar a roles de sistema**).

`server_default` declarado **también en el modelo** (el gate parity no lo atrapa, docstring `schema_parity_check.py:15`). Correr `alembic upgrade head` en dev(5434) **y** test(5433), luego `schema_parity_check.py` (secuencial, jamás con pytest corriendo). Registrar `Transfer`/`TransferLine` en `app/models/__init__.py` (si no, `create_all` de test no los ve → parity falla).

### 2.3 Tipos MoneyMovement + terna de signos

**2 tipos nuevos** en `VALID_MOVEMENT_TYPES` (`money_movement.py:58`, append): `internal_maquila_expense`, `internal_maquila_income`. Ambos `account_id=NULL` **y** `third_party_id=NULL` (primer par así salvo `depreciation_expense`). Catálogo 39→41. `movement_type` es String(50) sin CHECK ni enum de BD → cero migración de tipo (resuelve menor-26).

**Terna — dónde entra cada tipo** (ambos NULL/NULL → no tocan balances):

| Sitio | file:line | ¿Agregar? |
|---|---|---|
| `VALID_MOVEMENT_TYPES` | `money_movement.py:58` | **SÍ** ambos |
| `ACCOUNT_BALANCE_DIRECTION` (canónico + duplicado) | `reports.py:93`, `money_movements.py:92` | **NO** (account NULL → default 0) |
| `THIRD_PARTY_BALANCE_DIRECTION` (canónico + duplicado) | `reports.py:123`, `money_movements.py:56` | **NO** (tercero NULL → default 0) |
| `INFLOW_TYPES` / `OUTFLOW_TYPES` | `reports.py:157/171` | **NO** (no mueven caja) |
| Allowlist inline de `_calculate_profit` | `reports.py:817` (`movement_type.in_([...8 tipos...])`) | **NO** (N5 — es ESTE allowlist, no `EXPENSE_MOVEMENT_TYPES`, el que decide qué MM entra al P&L consolidado; fuera de él, la exclusión es por construcción) |
| `EXPENSE_MOVEMENT_TYPES` | `reports.py:3898` | **NO** (fuera → Gastos #44 / prorrateo #59 / Costo Real lo ignoran) |
| `_reverse_effects` rama `pass` explícita | `money_movement.py:~1814` | **SÍ** ambos (defensa; neteo inerte) |
| `INTERNAL_MAQUILA_MOVEMENT_TYPES` (set guard nuevo) | `money_movement.py:~1053` | **SÍ** ambos (422 al anular en Tesorería) |

**Emisión del par** vía embudo `_create_movement` (`money_movement.py:1499`, ya acepta `source_type/source_id/tariff_id/warehouse_id` desde #83 — cero pokes post-hoc), precedente `_apply_collector_commission` `purchase.py:1484`. Por línea aportante:
- `internal_maquila_expense`: `warehouse_id=from_warehouse_id` (CV/BOG), `business_unit_id=line.material.business_unit_id`, `expense_category_id`=categoría sistema "Maquila Intersede" (get-or-create `normalize_entity_name` #78, `is_system_entity=True`, `is_direct_expense=False`, solo en path gated), `amount=line.kg_lead_equivalent × tarifa`, `source_type='transfer'`, `source_id=transfer.id`, `tariff_id`, `date=receipt_date` (E11).
- `internal_maquila_income`: idéntico salvo `warehouse_id=to_warehouse_id` (JM), `expense_category_id=NULL`.
- `mm_exp.transfer_pair_id = mm_inc.id` y viceversa.

### 2.4 Endpoints + schemas

Router nuevo `app/api/v1/endpoints/transfers.py`, prefijo `/api/v1/transfers`, gated: `dependencies=[Depends(require_org_flag("two_step_transfers_enabled"))]` (403 incluso a admin sin flag).

| Método | Ruta | Permiso | Descripción |
|---|---|---|---|
| POST | `/transfers` | `inventory.transfer` | Despacho (cabecera + líneas). |
| POST | `/transfers/{id}/receive` | `inventory.transfer_receive` (NUEVO) | Recepción: `{lines: [{transfer_line_id, quantity_received}], receipt_date?, notes?}`. |
| POST | `/transfers/{id}/resolve` | `inventory.transfer_receive` | Resuelve líneas en discrepancia: `{lines: [{transfer_line_id, resolution: justify\|correct, final_quantity?}], notes}`. |
| POST | `/transfers/{id}/annul` | `inventory.transfer` | Cascade reversa. |
| GET | `/transfers` | `inventory.view` | Bandeja: `status`, `pending_receipt`, `from/to_warehouse_id`, `material_id`, `date_from/to`, paginado, `sort`. |
| GET | `/transfers/{id}` | `inventory.view` | Detalle con líneas + efectos + discrepancias. |

Schemas (`app/schemas/transfer.py`, `extra="forbid"` #74): `TransferDispatchCreate` (from/to_warehouse_id, dispatch_date opcional default hoy, notes, `lines: [{material_id, quantity_dispatched gt=0}]` min 1), `TransferReceiveRequest` (`lines: [{transfer_line_id, quantity_received ge=0}]`, receipt_date opcional), `TransferResolveRequest`, `TransferAnnulRequest` (reason min 3), `TransferResponse`/`TransferLineResponse` (con `display_status`, `variance_pct` por línea, `kg_lead_emitted`, `maquila_amount`, `discrepancy_task_id`, `material_unit` #54, auditoría, `warnings`).

### 2.5 State machine + efectos por transición

```
  POST /transfers            POST /receive (todas líneas ≤ tol)
[∅] ───────────► dispatched ──────────────────────────► received
                    │  POST /receive (≥1 línea > tol)      ▲
                    ▼                                       │ POST /resolve
              held_discrepancy ─────────────────────────────┘
  cualquier estado ≠ annulled:  POST /annul  ──────► annulled
```

| Transición | Efectos | Atomicidad |
|---|---|---|
| `∅→dispatched` | Por línea: 2 InventoryMovement `type='transfer'` (out origen `unit_cost=current_average_cost` org-wide #5; in tránsito), `reference_type='transfer'`, `reference_id=transfer.id`, `date=dispatch_date`. Snapshot `is_contributor` + `conversion_formula_snapshot` (E7). **CERO kg, CERO pesos.** | 1 tx. Stock insuficiente → **warning** (#76). |
| `dispatched→received` (línea ≤ tol) | (a) físico tránsito→JM por `quantity_received`; si `quantity_received < quantity_dispatched`, el residual del tránsito se cierra con **`InventoryAdjustment` `decrease` sobre la bodega de tránsito** por la diferencia, `unit_cost=current_average_cost` org-wide, `reason="Merma traslado #N"` → pérdida en `adjustment_net` (E8); **tránsito queda en CERO**. (b) si aportante: `intersede_send` `delta_kg=+quantity_received × factor_snapshot`. (c) si `internal_maquila_enabled`: par de maquila. `effects_emitted=True`. | **1 tx atómica.** Precondiciones fail-fast (§2.6). |
| `dispatched→held_discrepancy` (línea > tol **o `quantity_received > quantity_dispatched`**, N3) | SOLO físico entra (`quantity_received`, tope `quantity_dispatched` — el excedente NO se inventaría hasta resolver). Efectos b+c **retenidos**. `DiscrepancyTask` `severity='high'` (o `critical` si variance > umbral / recibido=0, resuelve bloq-7), `entity_type='Transfer'`. | 1 tx. |
| `held_discrepancy→received` (resolve) | Emite b+c con `resolved_quantity`. `correct` ajusta físico por delta. Cierra la task. | 1 tx atómica. |
| `*→annulled` | Cascade reversa (§2.7). | 1 tx. |

**Anti back-dating (#62):** `dispatch_date`/`receipt_date` default hoy, `<= hoy`, `receipt >= dispatch`. Efectos de recepción fechados en `receipt_date` (E11).

### 2.6 Tolerancia + discrepancia + resolución

```python
tolerance = Decimal(str(get_org_setting(db, org_id, "transfer_tolerance_pct")))  # float→Decimal (evita TypeError)
variance = (abs(qty_received - qty_dispatched) / qty_dispatched).quantize(Decimal("0.0001"))  # 4 dec fijos (resuelve menor-30)
within = variance <= tolerance
```

**Precondiciones fail-fast (400 legible ANTES de tocar nada, resuelve mayor-19):** cuenta `intersede` activa existe; bodega de tránsito existe; tarifa `maquila_intersede_cv_jm` vigente existe (si `internal_maquila_enabled`); fórmula vigente al despacho (si `is_contributor`). Documentar las 3 de config en el runbook (§7).

**Resolución** (`POST /resolve`, exige línea `held_discrepancy`): `justify` (acepta `quantity_received`) o `correct` (`final_quantity` obligatorio, ajusta físico por delta). "Arquear" = `correct` con conteo. Emite intersede + par con `resolved_quantity`, cierra la task (`resolution_entity_type='Transfer'`). **E3.1 escribe y resuelve `DiscrepancyTask` desde el traslado; el panel unificado es E5** (resuelve bloq-6).

**recibido=0** = merma total → `DiscrepancyTask` `critical` (resuelve bloq-7). **recibido > despachado** (N3): SIEMPRE → `held_discrepancy`, **aunque la variance quede dentro de tolerancia** — recibir más de lo despachado dejaría el tránsito NEGATIVO y cobraría maquila por kg que el origen nunca despachó; no es una merma tolerable, es una anomalía a revisar. Al resolver con `justify`/`correct` y `final_quantity > quantity_dispatched`: **en `held` ya entró el físico capado a `quantity_dispatched`** (tránsito ya en cero) — en resolve entra **SOLO el excedente** (`final_quantity − quantity_dispatched`) como `InventoryAdjustment` `increase` en la bodega DESTINO al avg org-wide (identidad D2: entra al propio avg → `incorporate_into_pool` da adjustment 0, avg intacto), `reason="Excedente traslado #N"` (N-a: sin doble entrada física; el test N3 asserta tránsito==0); intersede + par se emiten sobre `final_quantity` ("lo recibido es la verdad", pendiente confirmación Q-E3.1-a).

### 2.7 Anulación (cascade, orden atómico — E9)

`POST /transfers/{id}/annul`. El **servicio de traslado orquesta**, no `annul()` de Tesorería. Orden en 1 tx:
1. Revertir inventario físico (reversa append-only, patrón #66) **+ anular los `InventoryAdjustment` hijos del traslado** — la merma `decrease` (§2.5) y el `increase` de excedente (§2.6) — vía el annul estándar de ajustes (que ya conserva valor por #65/#66); se localizan por la FK `inventory_adjustments.transfer_id` (migración §2.2 ítem 4 — no se depende de strings en `reason`). Sin esto, anular un traslado recibido dejaría la pérdida de merma viva en `adjustment_net` de un traslado que "nunca existió".
2. `intersede_send` → `status='annulled'` (auditoría, patrón `inbound_order.py:522`).
3. Par MM: marcar ambos `annulled` + auditoría + `_reverse_effects` (rama `pass` inerte). **NO pasar por `annul()`** (su guard `INTERNAL_MAQUILA_MOVEMENT_TYPES` lo 422-earía — deadlock estilo ciclo C).
4. `held_discrepancy`: cerrar la task.

**Warn, no bloquea** (#76): si la reversa deja stock/kg negativo → warning (patrón PR-3 #65), no bloqueo.

**Desviación declarada del §5.4 congelado (M2, elevada como Q-E3.1-d):** el doc v0.5 §5.4 pide **bloquear con 400** la anulación de un traslado cuyo material ya fue "cargado al horno **o vendido**". E3.1 cubre "fundido" por vacuidad (no hay horno hasta E3.2) pero para "**vendido**" aplica deliberadamente **warn-no-bloquea**, desviándose de la letra congelada. Racional: (a) no hay corrupción posible — `intersede_discharge` no existe en E3.1, la anulación solo revierte el `intersede_send` y el inventario físico, y si JM ya vendió parte, el stock queda negativo **con warning**, que es exactamente la filosofía #76 vigente en toda la app (ventas, ajustes, ediciones de compra — el bloqueo homólogo de #73 se revirtió en #76 por incidente en prod); (b) un 400 aquí recrearía el mismo callejón operativo que motivó el hotfix #76. Si Johana/Hugo confirman que el bloqueo es requisito de control interno (no de integridad), se agrega el guard 400 en E3.2 junto con el de "fundido" (ahí sí hay irreversibilidad real). **Nota E3.2:** anular un traslado cuyo kg ya se fundió sí es irreversible → bloqueo se diseña allá (resuelve bloq-9 parcial).

### 2.8 P&L por sede (E13 recalibrado — M1)

`_calculate_profit` (`reports.py:475`) y `get_profit_and_loss` (`:1082`) + `_monthly` (`:1047`) ganan `warehouse_id: Optional[UUID]=None` e `include_internal_maquila: bool=False`. Regla de fuerza: `effective_include_maquila = include_internal_maquila or (warehouse_id is not None)`.

| `warehouse_id` | Semántica | `internal_maquila_*` |
|---|---|---|
| `None` (default) | **Consolidado** (byte-idéntico a hoy) | EXCLUIDOS (netean $0) |
| `<sede>` | **P&L por sede** | INCLUIDOS (CV=gasto, JM=ingreso) |

**Qué fragmenta por sede (y por qué campo — M1):**

| Línea P&L | Filtro por sede | Nota |
|---|---|---|
| Ventas / COGS / báscula | `Sale.warehouse_id == sede` (`sale.py:81`) | Campo real, poblado por el flujo de ventas. |
| Comisiones de venta | **`Sale.warehouse_id == sede`** vía el `.outerjoin(Sale)` que la query YA hace (`reports.py:897-909`) | ⚠️ **NUNCA `MoneyMovement.warehouse_id`**: `commission_accrual` nace con sede NULL → daría $0 y el test pasaría en falso. La comisión pertenece a la sede de SU venta. |
| Par de maquila | `MoneyMovement.warehouse_id` propio de cada tipo | Query separada, líneas propias del response (E4) — el único MM que nace con sede poblada en E3.1 (junto al recolector #83). |
| **Gastos operativos / `service_income` / tp_adjustment** | **NO se fragmentan → $0 por sede** | Sus writers no capturan sede (el schema de MM no tiene el campo). El response por-sede lleva nota `unallocated_expenses` (gastos del consolidado sin sede) para que el lector vea qué falta. Captura gasto-por-sede (caja-menor) = **E4/E5** (Q-E3.1-c/e). |
| DP / transformaciones / ajustes | Solo consolidado | Sin sede o E3.2. |

**Documentar en UI/response:** la suma de sedes ≠ consolidado por (a) líneas no atribuibles, (b) gastos sin sede, (c) el par de maquila (neteado en consolidado). La vista por-sede en E3.1 responde "¿cuánto margen genera cada sede y cuánta maquila fluye entre ellas?" — no "¿cuál es la utilidad neta completa de cada sede?" (eso llega con gasto-por-sede en E4/E5).

**No-regresión clave:** con `warehouse_id=None` e `include_internal_maquila=False` (100% del tráfico de las 3 empresas), `_calculate_profit` produce el **mismo dict byte a byte** — la selección de tipos MM sigue siendo el **allowlist inline** de `reports.py:817` (N5: NO es `EXPENSE_MOVEMENT_TYPES`, ese vive en `:3898` y alimenta Gastos #44/prorrateo #59/Costo Real) y los tipos maquila jamás entran a ese allowlist: la exclusión del consolidado es **por construcción**, el par se suma solo en la query separada gated por `effective_include_maquila`. Tests de oro #49/#50 verdes por construcción. Endpoint `/reports/profit-and-loss` gana 2 Query params opcionales (sin permiso nuevo, reusa `reports.view`/`view_pnl`).

### 2.9 Gating por flags (E10)

| `two_step` | `internal_maquila` | Comportamiento |
|---|---|---|
| false | (cualquiera) | `/transfers` → 403. Prod usa `/warehouse-transfer` 1-paso intacto. |
| true | false | 2 pasos + `intersede_send`, **sin par** (kg sin maquila). |
| true | true | Flujo completo. SAC nace aquí. |

`internal_maquila_enabled` se lee **inline** en el servicio (`if get_org_setting(...): _emit_maquila_pair()`), NUNCA como `require_org_flag`.

### 2.10 Bodegas de tránsito + guard backend (E8, E12)

- `is_transit=True` marca la bodega virtual; `transit_target_warehouse_id` apunta a la física (JM). Se siembran en el **runbook** de deploy E3.1 (no en `create_organization` — contaminaría orgs futuras). Despacho resuelve `transit_warehouse_id` por la ruta; 0 bodegas → 400 guía.
- **Guard backend** (resuelve mayor-21): rechaza 400 toda operación (transfer 1-paso origen **y** destino, compra, venta, ajuste — salvo el propio 2-pasos) contra `is_transit=True` cuando `two_step_transfers_enabled`. **Flag-check primero** → cortocircuita para las 3 empresas (sin query, sin regresión, resuelve mayor-12).
- **Tránsito en CERO** tras cada recepción (E8): la merma báscula se cierra con `decrease` al avg org-wide → pérdida en `adjustment_net`, no residual valuado (mecánica completa en §2.5; jamás `cost_adjustment`/#65 — B1).

### 2.11 RBAC

- Reusa `inventory.transfer` (despacho, anular) e `inventory.view` (bandeja/detalle).
- **Nuevo `inventory.transfer_receive`** (recepción/resolución — separación de funciones: David despacha en CV, JM confirma; base de la política "utilidad cero JM"). Dual-write triple, sin asignar a roles de sistema.

### 2.12 Frontend (UX, bandeja, empty-states, mobile — resuelve menor-29)

Módulo "Traslados" (patrón bandeja Entradas #82): lista con `display_status`, bandeja "Por recibir: N" (badge ámbar), form de despacho (líneas multi-material, `MoneyInput` decimal), form de recepción (cantidad por línea), resolución de discrepancia desde el detalle, filtro por sede en el P&L (selector excluye bodegas `is_transit`; la vista por-sede muestra la nota "gastos sin sede: $X" de §2.8). **Obligatorio** (regla CLAUDE.md): empty-states (bandeja vacía / sin bodega de tránsito → guía a Config / sin sedes), render dual desktop+cards mobile (reusar `OperationListCard`), sticky bottom en forms, verificación 390px. `hideWhenOrgFlag` oculta el modal 1-paso en SAC. Botón "Anular" oculto para tipos `internal_maquila_*` en Tesorería (nota guía al traslado, patrón #67).

**Cache invalidation (N1, decisión #27):** helper nuevo **`invalidateAfterTransfer`** en `queryInvalidation.ts` (precedente `invalidateAfterInboundOrder:77`): `transfers` + `inventory` + `materials` + `kg-ledger` + `money-movements` + `reports` (recepción emite par + intersede + posible ajuste de merma; despacho solo inventario, pero un solo helper mantiene la regla simple). Documentar en CLAUDE.md #27 al cerrar el ciclo.

---

## 3. Invariantes de negocio

1. **Costo org-wide invariante** (#5): un traslado NO cambia `current_average_cost` (out e in al mismo `unit_cost`). Nunca llamar `incorporate/remove_from_pool` en los movimientos de **despacho/recepción** (N-b: el alcance es esos movimientos — el cascade de anulación de la merma sí usa el reingreso ponderado canónico #66 del annul de ajustes, que puede ajustar el avg si se movió entre recepción y anulación; el walk no debe leerlo como violación).
2. **kg = fórmula × cantidad**: `balances(intersede) == Σ delta_kg confirmados`; `Σ delta_kg == Σ(quantity_efectiva × factor_snapshot)` de recepciones confirmadas.
3. **Par simétrico**: `internal_maquila_expense.amount == internal_maquila_income.amount`; suma consolidada de ambos == 0.
4. **Tránsito en cero**: tras cada recepción confirmada, la bodega de tránsito no acumula saldo residual — el cierre es un `InventoryAdjustment` `decrease` al avg org-wide (merma → `adjustment_net`), **jamás** `cost_adjustment`/#65 ni `remove_from_pool` (B1: esa línea es exclusiva de incorporate/remove, prohibidos en traslados por el invariante 1).
5. **Conciliación #59 intacta**: residual $0 con eventos de maquila presentes (ambos lados de la identidad los ignoran).
6. **Consolidado byte-idéntico**: `warehouse_id=None` ⇒ dict de `_calculate_profit` igual a hoy.

---

## 4. No-regresión

**Garantías estructurales:** flags default false + gating (las 3 empresas nunca crean `internal_maquila_*` ni pueblan `warehouse_id`); columnas aditivas nullable/server_default; `movement_type` String(50) sin CHECK; los 2 tipos fuera de todos los mapas de balance/flujo/gasto; guard anti-anulación; migración additive-only + server_default en modelo.

**Golden comparison (GATE DURO, diff exactamente CERO)** sobre réplica de prod ×3 orgs (Costa/Biogreen/MetaRecycling), antes (`main`) vs después (branch E3.1 + `alembic upgrade head`):
1. P&L consolidado (todos los campos). 2. P&L mensual. 3. P&L por-UN + **conciliación #59 (residual $0)**. 4. Balance Sheet (vivo + as-of). 5. Balance Detallado (vivo + as-of). 6. Cash Flow. 7. Saldos de cuentas. 8. Estado de cuenta (3-5 terceros no triviales). **+ (ampliación del panel, resuelve mayor-11):** 9. **`GET /warehouses`** ×3 orgs (por `is_transit` en tabla compartida). 10. **`GET /money-movements` paginado** (serialización de los 39 tipos previos). 11. **`/reports/expenses` + detalle** (`EXPENSE_MOVEMENT_TYPES`).

**Schema parity** (`schema_parity_check.py`, secuencial): diff CERO fuera del baseline de 19; declarar `server_default` en modelo (el gate no lo atrapa). Reportes a auditar uno a uno: Cash Flow, Balance (vivo+as-of), Dashboard/Treasury, Gastos #44, Rentabilidad UN #58, Conciliación #59, Estado de cuenta #16/#55, Drill-down #49.

---

## 5. Matriz de tests

**Archivos nuevos:** `tests/test_sac_transfer_two_step.py`, `tests/test_pnl_by_warehouse.py`. No-regresión se añade a `test_api_inventory_adjustments.py`, `test_integration_03_pnl.py`, `test_kg_ledger.py`.

**Bloqueantes (~31):** los 7 del doc §5.4 aplicables (`test_transfer_reception_creates_maquila_pair`, `test_transfer_annulment_annuls_pair`, `test_consolidated_pnl_excludes_internal_types`, `test_sale_liquidation_does_not_create_maquila` [guardián], `test_transfer_out_of_tolerance_blocks_pair`, `test_non_contributor_transfer_creates_no_pair`; crisol → E3.2) + happy path 2 pasos + "lo recibido es la verdad" (por línea) + BOG→JM (expense warehouse=BOG) + multi-material mixto aportante/no-aportante (estado derivado) + **multi-línea tolerancia mixta (N2): línea A dentro (emite) + línea B fuera (retiene) en la MISMA recepción → cabecera `held_discrepancy`, efectos de A emitidos, de B retenidos** + recibido=0 → task critical + **recibido>despachado → held SIEMPRE aunque variance ≤ tol (N3) + resolve con excedente → increase en destino identidad D2 (avg intacto)** + tolerancia borde (`<=`, quantize) + resolución emite final + Decimal/float sin TypeError + atomicidad (falta tarifa/cuenta intersede/bodega → rollback+400) + fórmula ausente al recibir → retiene, NO 400 (E6) + snapshot de fórmula al despacho (E7) + **tránsito en cero tras recepción con merma → `decrease` en tránsito, pérdida en `adjustment_net`, avg org-wide INTACTO y CERO `cost_adjustment` en cualquier tabla (B1 — el assert de avg intacto + cost_adjustment==0 es el guardián del invariante 1)** + gating (4 combinaciones) + P&L por sede (CV ventas+comisiones+gasto maquila, JM ingreso maquila, consolidado neto cero) + **test de oro por-sede con fixture de comisión ≠ 0 (M1: venta en CV con comisión → la línea comisiones por-sede == Σ accruals de ventas de esa sede ±$1; con el filtro equivocado daría $0 y el test REVIENTA, no pasa en falso)** + **gastos sin sede → $0 por sede + presentes en consolidado (documenta el alcance E13)** + conciliación #59 residual $0 con maquila + guard anti-anulación Tesorería 422 + anulación no-vía-annul() + **anular traslado recibido con merma → ajuste hijo (FK `transfer_id`) anulado en cascade, `adjustment_net` vuelve al valor pre-traslado (§2.7)** + **anular traslado con material ya vendido → 200 + warning, NO 400 (M2, test que documenta la desviación)** + RBAC permitido/denegado + walk de invariantes kg + no-regresión 1-paso byte-idéntico + P&L sin param byte-idéntico + guard operar-contra-tránsito.

**Deseables (~13):** snapshots, bandeja/estado derivado, MCH fecha, cash flow invariante, multi-tenant, walk de anulación, allowlist inline `:815` + `EXPENSE_MOVEMENT_TYPES` excluyen internos (N5), `kg_ledger.annul` sigue rechazando business types.

---

## 6. Decisiones abiertas / preguntas al cliente (Johana/Hugo — no bloquean; default conservador)

- **Q-E3.1-a — recibido > despachado**: ¿JM cobra maquila por kg que CV nunca despachó? Comportamiento v1.1 (N3): SIEMPRE pasa por discrepancia y un humano resuelve; al justificar, intersede + maquila se emiten sobre lo recibido ("lo recibido es la verdad"). Confirmar que el excedente SÍ paga maquila.
- **Q-E3.1-b — recepción parcial**: ¿un despacho CV→JM puede recibirse en 2 camiones/días? Default: atómica (todo o nada). Si es real → modelar `quantity_received` acumulativo + estado `partially_received` (impacto de scope).
- **Q-E3.1-c — gastos comunes por sede**: en E3.1 los gastos operativos NO llevan sede (salen $0 en la vista por-sede, §2.8/M1). ¿SAC necesita capturar arriendo/servicios por sede desde el día 1 (adelantaría caja-menor-por-sede de E4) o basta con margen+maquila por sede ahora y gastos en E4?
- **Q-E3.1-d — anular traslado con material ya vendido (M2)**: el doc §5.4 pide bloquear; E3.1 avisa sin bloquear (filosofía #76, sin corrupción posible — ver §2.7). ¿El bloqueo es requisito de control interno? Si sí → se agrega como guard en E3.2 junto al de "fundido".
- **Q-E3.1-e — "utilidad cero JM" en E3.1**: JM mostrará +ingreso maquila pero sus gastos de planta $0 hasta E4 (§2.8). ¿Sirve así como primera aproximación gerencial o esperamos a E4 para presentar la vista por-sede al cliente?

---

## 7. Runbook de deploy E3.1 (checklist bloqueante)

1. Sembrar bodega virtual **JM-TRANSITO** (`is_transit=True`, `transit_target_warehouse_id`=JM físico, `is_receiving=False`) en la org SAC.
2. Confirmar cuenta kg `intersede` activa (si no existe → crearla en Plomo (kg)). **Crear la tarifa `maquila_intersede_cv_jm` = $1.500 `per_kg_lead` vía `POST /service-tariffs`** (N4: NO existe seed — E1 solo creó el catálogo de códigos; "confirmar" fallaría porque no hay nada que confirmar; el precondition fail-fast §2.6 daría 400 en la primera recepción).
3. Marcar internas (Molino/Tránsito) según corresponda; verificar CV/BOG/JM existen como warehouses.
4. Encender `two_step_transfers_enabled` + `internal_maquila_enabled` en `settings` (REPLACE completo).
5. **Golden gate duro** (§4) diff cero ×3 orgs antes del merge.

---

## 8. Criterios de done

Suite completa verde (0 fallos) incl. ~27 bloqueantes; golden diff cero ×3 orgs (11 capturas); schema parity diff cero fuera del baseline; tsc/build limpios; migración corrida en dev(5434)+test(5433); 390px verificado; informe a QA con evidencia.

---

## Apéndice A — Resolución de los 31 hallazgos del panel adversarial

**Bloqueantes (9):** B1 income/expense líneas propias (E4, §2.8) · B2/B4 anulación sin annul(), guard deadlock (E9, §2.7) · B3 `transfer_pair_id` canónico (E3) · B5 = B1 · B6 DiscrepancyTask write+resolve-on-transfer, panel E5 (§2.6) · B7 recibido=0/>>despachado ge=0 + critical (§2.1/§2.6) · B8 cabecera+líneas, por-línea, estado derivado (E1/E2) · B9 orden atómico de reversa + warn; "fundido" a E3.2 (§2.7).

**Mayores (13):** M10/M11 is_transit GATE DURO + golden ampliado (E12, §4) · M12/M21 guard backend con flag-check primero (§2.10) · M13 par por-línea con BU del material (E2) · M14/M22 nunca bloquear, snapshot al despacho (E6/E7) · M15 gating inline (E10) · M16/M17 tránsito en cero, merma a P&L (E8) · M18 fecha canónica receipt_date (E11) · M19 fail-fast precondiciones (§2.6) · M20 recepción parcial → Q-E3.1-b · M23 P&L por sede completo (E13, §2.8).

**Menores (9):** categoría idempotente #78 (§2.3) · naming único transfers/transfer_lines/transfer_pair_id/source_type='transfer' (E1/E3/E5) · movement_type sin CHECK (§2.3) · status persistido mono-entidad, desviación de #82 documentada (§2.1) · residual #59 test con maquila (§5) · empty-state+mobile (§2.12) · tolerancia quantize 4 dec (§2.6) · ruteo `transit_target_warehouse_id` único (§2.1).

---

## Apéndice B — Resolución de los hallazgos del Micro-QA sobre v1.0

| # | Severidad | Hallazgo | Resolución en v1.1 |
|---|---|---|---|
| B1 | BLOQUEANTE | E8 citaba `cost_adjustment`/#65 para la merma — imposible (esa línea la produce solo `incorporate/remove_from_pool`, prohibidos en traslados por invariante #1) | E8 + §2.5 + §2.10 + invariante 4 reescritos: merma = `InventoryAdjustment` `decrease` en tránsito al avg org-wide → `adjustment_net` (`reports.py:611`, verificado: `CASE quantity>0 → total_value ELSE −total_value`). Test guardián: avg intacto + `cost_adjustment==0` en toda tabla. |
| M1 | MAYOR | E13 sobrevendido ("gastos por `MoneyMovement.warehouse_id`" daría $0 — el schema de MM no captura sede) + filtro de comisiones equivocado + test de oro pasable en falso ($0==$0) | E13 + §2.8 recalibrados: comisiones por `Sale.warehouse_id` (la query ya hace `.outerjoin(Sale)`, `reports.py:897`); gastos/service_income declarados $0 por sede hasta E4 (nota `unallocated_expenses` en response/UI); test de oro con fixture comisión ≠ 0. Preguntas Q-E3.1-c/e recalibradas. |
| M2 | MAYOR | Desviación silenciosa del §5.4 congelado: "vendido" nunca aparecía (el doc pide 400 al anular traslado de material vendido) | Desviación DECLARADA en §2.7 con racional (#76, sin corrupción — no hay `intersede_discharge` en E3.1) + elevada como **Q-E3.1-d** + test que documenta el warn (200+warning, NO 400). Si el cliente exige el bloqueo → guard en E3.2 junto a "fundido". |
| N1 | MENOR | Sin plan de cache invalidation | `invalidateAfterTransfer` en §2.12 (precedente `invalidateAfterInboundOrder:77`), documentar en #27. |
| N2 | MENOR | Faltaba test multi-línea tolerancia mixta | Añadido a §5 bloqueantes (línea A emite / B retiene en la misma recepción). |
| N3 | MENOR | recibido>despachado dentro de tolerancia → tránsito negativo + maquila sobre kg no despachados | SIEMPRE → `held_discrepancy` (aunque ≤ tol); resolve con excedente → `increase` en destino a identidad D2 (§2.5/§2.6). Q-E3.1-a actualizada. |
| N4 | MENOR | Runbook decía "confirmar" tarifa que NO existe (sin seed) | Paso 2 del runbook: **crear** vía `POST /service-tariffs` $1.500 `per_kg_lead`. |
| N5 | MENOR | §2.3 atribuía la exclusión del consolidado a `EXPENSE_MOVEMENT_TYPES` | Corregido: el gate real es el **allowlist inline** `reports.py:817` de `_calculate_profit`; `EXPENSE_MOVEMENT_TYPES` (`:3898`) gobierna Gastos #44/prorrateo #59/Costo Real. Ambas filas en la terna §2.3. |
| SUG | — | "Maquila del horno" es etiqueta imprecisa (se causa al recibir el traslado, no al fundir) | Renombrada a **"maquila intersede"** en título/§0/§2 (la tarifa siempre fue `maquila_intersede_cv_jm`). |
