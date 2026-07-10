# Plan: Revalorización de Activos Fijos (Requerimiento D — Costa)

**Fecha:** 2026-07-10 · **Estado:** pendiente QA · **Alcance:** 1 PR (backend + frontend + migración)

---

## 1. Contexto y requerimiento

El cliente (Reciclajes de la Costa) necesita **subir o bajar el valor en libros de un activo fijo existente**. Hoy no existe: su workaround fue dar de baja el activo viejo y crear uno nuevo con el valor mayor — la baja generó una depreciación acelerada (`depreciation_expense`) que apareció como **gasto no deseado en el P&L del mes**.

**Aclaración clave de Daniel (2026-07-10):** la contrapartida de la revalorización viene de **un tercero o una cuenta**. Contablemente esto NO es una revaluación NIIF a patrimonio — es una **adición/mejora capitalizable** (al alza) o una **recuperación de valor** (a la baja): el valor entra o sale contra caja o contra el saldo de un tercero. Consecuencias de diseño:

- **Cero efecto en P&L** (ni gasto ni ingreso) — exactamente lo que el cliente pidió.
- **Cero línea nueva de patrimonio** en el Balance.
- Mecánica espejo del patrón XOR de creación de activos (decisión #21: cuenta → pago inmediato; tercero → a crédito).

### Decisiones de negocio cerradas (Daniel, 2026-07-10)

| # | Pregunta | Respuesta |
|---|----------|-----------|
| 1 | ¿La mejora solo sube valor o también extiende vida útil? | **Ambas** — valor +X y opcionalmente meses +N |
| 2 | ¿Solo al alza? | **A la baja también** (activo−, contrapartida entra a cuenta o queda a cargo/favor del tercero) |
| 3 | ¿Efecto de la depreciación recalculada? | **Desde el mes siguiente, sin back-dating** (ver G1) |
| 4 | ¿Revertir la baja histórica del workaround? | **No — se queda como está** |

Decisión de diseño (default razonable, Daniel no objetó): `salvage_value` NO se toca.

---

## 2. Diseño

### 2.1 Tabla nueva: `asset_revaluations`

Cada revalorización es un evento auditado, append-only con anulación por status (patrón `AssetDepreciation.is_active`).

| Columna | Tipo | Notas |
|---------|------|-------|
| `id` | GUID PK | |
| `organization_id` | GUID FK | `OrganizationMixin` |
| `fixed_asset_id` | GUID FK CASCADE, index | |
| `revaluation_type` | String(10) | `increase` \| `decrease` |
| `amount` | Numeric(15,2) | siempre > 0; el signo lo da el type |
| `months_extended` | Integer, default 0 | solo `increase`; 0 en `decrease` |
| `value_before` / `value_after` | Numeric(15,2) | snapshot exacto (patrón `current_value_after` de AssetDepreciation) |
| `monthly_before` / `monthly_after` | Numeric(15,2) | snapshot de la cuota |
| `period` | String(10) | "YYYY-MM" derivado de la fecha de aplicación (hoy Bogotá) — ancla contable para as-of |
| `money_movement_id` | GUID FK RESTRICT, NOT NULL | el MM de contrapartida |
| `reason` | String(500) nullable | motivo |
| `applied_at` | DateTime tz | `now()` — tiebreaker dentro del mismo period |
| `applied_by` | GUID FK users | |
| `is_active` | Boolean default True | False al anular |
| `annulled_at/by/reason` | audit nullable | |

**Fecha del evento = hoy (Bogotá), sin input de fecha.** Coherente con `dispose()` (usa hoy) y con la doctrina anti back-dating #62. El MM lleva `date` = hoy mediodía UTC. No hay parámetro `date` en el request — elimina el back-dating por construcción.

### 2.2 Cuatro tipos nuevos de MoneyMovement (→ 25 en el catálogo)

Se descartó reutilizar `asset_payment`/`asset_purchase` para el alza: la baja necesita tipos nuevos sí o sí (no existe ningún tipo "cuenta+ por activo"), y mezclar 2 reusados + 2 nuevos deja estados de cuenta confusos ("Compra activo a crédito" para una revalorización). Cuatro tipos explícitos, un efecto cada uno (estilo del catálogo):

| Tipo | Cuenta | Tercero | Caso |
|------|--------|---------|------|
| `asset_revaluation_payment` | − | — | Alza pagada desde cuenta |
| `asset_revaluation_credit` | — | balance − (le debemos) | Alza a crédito con tercero |
| `asset_devaluation_collection` | + | — | Baja con reembolso a cuenta |
| `asset_devaluation_receivable` | — | balance + (nos debe / se reduce deuda) | Baja a cargo del tercero |

Reglas del tercero: mismas que el supplier de activos (#32) — cualquier behavior_type excepto `provision`/`liability`. Ninguno de los 4 tipos toca P&L (no entran a `EXPENSE_MOVEMENT_TYPES` ni a líneas de ingreso de `_calculate_profit`) → la conciliación #59/#65 NO gana líneas y su test de oro no se ve afectado. **Verificar con grep que ningún consumidor de P&L haga pattern-matching por prefijo** (`asset_%`).

### 2.3 Servicio `revalue()` — mecánica exacta

Validaciones (400/422):
1. `asset.status` ∈ {`active`, `fully_depreciated`} — `disposed`/`cancelled` → 400.
2. `amount > 0` (Pydantic `gt=0`).
3. XOR `source_account_id` / `third_party_id` (validator de schema, patrón #21). Cuenta con fondos si es `decrease`... **no**: en decrease la cuenta RECIBE. `require_funds` solo aplica en `increase` + cuenta.
4. `decrease`: `amount ≤ current_value − salvage_value` (el valor no puede caer bajo el residual; mantiene la matemática de cuotas). Sobre `fully_depreciated` → 400 (no hay nada que bajar).
5. `months_extended > 0` solo con `increase`; en `decrease` → 422.
6. `increase` sobre `fully_depreciated` exige `months_extended ≥ 1` (no hay meses restantes sobre los cuales repartir) y **revive el activo**: `status → active`.

Aplicación (transacción única, patrón `_create_movement` composable #20):
```
value_before   = asset.current_value
remaining_before = ceil((value_before − salvage) / monthly_old)   # 0 si fully_depreciated
remaining_after  = remaining_before + months_extended             # ≥ 1 garantizado por validación 6
value_after    = value_before ± amount
monthly_new    = ((value_after − salvage) / remaining_after).quantize(0.01)

asset.current_value        = value_after
asset.monthly_depreciation = monthly_new
asset.useful_life_months  += months_extended
# purchase_value, salvage_value, accumulated_depreciation, depreciation_rate: INTACTOS
```
- `decrease` que deja `value_after == salvage_value` → `status = fully_depreciated` (consistente con `apply_depreciation`).
- MM + balance de cuenta/tercero según tabla 2.2. `AssetRevaluation` con snapshots.
- La última cuota sigue auto-ajustándose al residual (`apply_depreciation` ya lo hace) → los redondeos de `monthly_new` se absorben solos.
- `depreciation_rate` queda como dato histórico informativo (el driver real es `monthly_depreciation`; ya es así tras el ajuste de última cuota).

### 2.4 G1 — semántica "desde el mes siguiente" (la única decisión semántica abierta)

Daniel aprobó "la depreciación recalculada arranca el mes siguiente". Implementación propuesta: **la cuota nueva rige para toda depreciación aplicada DESPUÉS de la revalorización** (event-ordered, coherente con Modelo L "cuenta cuando se aplica"). No se versiona la cuota por período — eso exigiría un motor de cuota-por-período que hoy no existe.

**Edge divergente a aceptar:** si la depreciación del MES CORRIENTE aún no se aplicó y se revaloriza hoy, la cuota de ESTE mes ya sale con el valor nuevo (estrictamente "mes siguiente" diría que este mes va con la cuota vieja). Mitigación UX: el modal muestra warning si el activo tiene períodos pendientes de depreciar ("Aplica primero las depreciaciones pendientes para que conserven la cuota anterior") — avisa, no bloquea (#17). El monto total a depreciar se conserva en cualquier orden (la última cuota ajusta al residual); solo cambia la distribución mensual.

### 2.5 Anulación de revalorización

`POST /fixed-assets/{id}/revaluations/{rev_id}/annul`:
- **Guard: bloquea si existe `AssetDepreciation` activa con `applied_at > rev.applied_at`** → 400 "Anule primero las depreciaciones aplicadas después de la revalorización" (anularlas ya es posible vía cancel de activo; individualmente no — ver Fuera de Alcance).
- ⚠️ **Este bloqueo NO contradice la Fase 5 (#66).** Allí el guard se retiró porque MCH era un ledger INCOMPLETO (ventas/decreases MCH-silenciosos → falsos permisos). Aquí `AssetDepreciation` + `AssetRevaluation` registran el 100% de los eventos que mueven `current_value` → el guard es exacto por construcción; bloquear es honesto y la reversión permitida es perfecta.
- Reversión simétrica: `current_value`, `monthly_depreciation`, `useful_life_months −= months_extended`, saldo de cuenta/tercero invertido, MM → `annulled`, `is_active = False` + audit. Estado: si el annul revierte un increase que había revivido un `fully_depreciated` → vuelve a `fully_depreciated`; si revierte un decrease que había marcado `fully_depreciated` → vuelve a `active`.
- Los 4 tipos nuevos entran a `ASSET_MOVEMENT_TYPES` en `money_movement.annul()` (bloqueo de anulación directa desde Tesorería, mensaje apuntando al módulo de activos).

### 2.6 `cancel()` del activo

Hoy revierte pago original + depreciaciones. Gana un paso: revertir también todas las revalorizaciones activas (saldos de cuenta/tercero + MMs → annulled + `is_active=False`). Orden: da igual matemáticamente (los efectos de saldo son sumas independientes), pero se hace después de las depreciaciones por simetría de auditoría.

`dispose()`: sin cambios — la depreciación acelerada usa `current_value` vigente (post-revalorización), correcto por construcción.

`update()`: sin cambios — la revalorización ES el camino sancionado para tocar valores con depreciaciones aplicadas.

---

## 3. Trampas críticas (zona incidente #61 — el pasado no se reescribe)

### H1 — Balance histórico as-of: reconstrucción pura con ancla DIARIA (corregido en pruebas de usuario)

`_fa_value_at_cutoff` (reports.py:2090) reconstruía el valor usando SOLO `AssetDepreciation`. Una revalorización cambia `current_value` fuera de ese marco → cortes posteriores quedaban mal.

**⚠️ El diseño v1 de este fix (merge de snapshots con ancla mensual `period`, como #41) tenía un defecto que salió en pruebas de usuario**: la revalorización anclaba al MES contable → un corte del día ANTERIOR al evento (mismo mes) mostraba el activo con el valor nuevo, pero la caja (ancla diaria del MM) sin el egreso → **el total de activos "crecía" por el monto sin contrapartida** (caso real: Camión LGU-673 +5M, corte de ayer). La semántica mensual es correcta para depreciaciones (la cuota pertenece al mes y su MM no toca caja); una revalorización es un **evento puntual con contrapartida de caja/tercero en un día concreto** — ambos lados deben moverse juntos en cualquier corte.

Fix definitivo — **reconstrucción pura, sin snapshots**:
```
valor(corte) = current_value + Σ dep.amount(period > corte_mensual) − Σ reval_firmada(MM.date >= corte_diario)
```
- Anclas mixtas deliberadas: depreciaciones por `period` mensual (#41 intacto); revalorizaciones por la **fecha del MoneyMovement de contrapartida** (JOIN, mismo boundary `>= cutoff_dt` que los saldos as-of de cuentas/terceros → simetría exacta, el balance cuadra en todo corte diario).
- Las sumas conmutan → exacta sin importar el orden de APLICACIÓN (una depreciación de mayo aplicada tarde en julio no contamina cortes intermedios; el merge de snapshots v1 sí era vulnerable a eso).
- Solo revalorizaciones `is_active` (anulada = nunca existió, filosofía 735c2c3). Cubre carga histórica #46 (depreciación pre-sistema embebida en `current_value`, sin filas que revertir).
- `AssetRevaluation.period` queda como ancla de display; **NUNCA usarlo para math as-of**.
- **Garantía no-restatement:** como la fecha del evento es siempre HOY (2.1), ningún corte anterior al DÍA del evento cambia. **Test de oro**: cortes ayer (mismo mes — el caso del bug) / mes anterior / nivel-2 / hoy, + assert de `total_assets`, `fixed_assets` y `cash_and_bank` del balance general de AYER idénticos antes y después de revalorizar.

### H2 — Sign maps: 4 dicts en 2 archivos (corrección QA #1 plegada)

Hay **cuatro copias** de los mapas de dirección, y un tipo ausente se ignora en silencio (`.get(mt, 0)`):
1. `reports.py:91` `ACCOUNT_BALANCE_DIRECTION` — saldos de cuenta as-of.
2. `reports.py:112` `THIRD_PARTY_BALANCE_DIRECTION` — saldos de tercero as-of.
3. `endpoints/money_movements.py:82` `ACCOUNT_BALANCE_DIRECTION` — **saldo corrido del estado de cuenta de CUENTA** (#55, líneas ~760/771: `base_balance = current_balance − net_effect`; con dirección 0 el saldo corrido queda corrido por el monto en cada fila, para siempre).
3. `endpoints/money_movements.py:56` `THIRD_PARTY_BALANCE_DIRECTION` — saldo corrido del estado de cuenta de TERCERO (línea ~882).

Entradas nuevas (idénticas en las 4 copias, según tabla 2.2):
- cuentas: `asset_revaluation_payment: -1`, `asset_devaluation_collection: +1`
- terceros: `asset_revaluation_credit: -1`, `asset_devaluation_receivable: +1`

Tests dedicados: (a) corte as-of posterior a una revalorización por cuenta y por tercero == saldo vivo; (b) **saldo corrido del estado de cuenta** (endpoint statement) con una revalorización en la ventana: fila con `balance_after` correcto y saldo inicial que reconcilia.

### H3 — Display de depreciación acumulada con valor > compra

Balance Detallado (vivo reports.py:1302 y as-of :2189) computa `accumulated_depreciation = purchase_value − current_value`. Tras un alza, `current_value` puede superar `purchase_value` → "depreciación acumulada" NEGATIVA en pantalla/Excel/PDF. Fix en ambos caminos: `acc_dep = purchase_value + Σ reval_deltas_firmados(≤ corte, activas) − current_value_al_corte` (en el vivo: Σ de todas las activas). El ítem puede además exponer `revalued_amount` para transparencia (schema `BalanceDetailedItem` ya es extensible).

### H4 — Cash Flow híbrido (#7) + frozensets (corrección QA #2 plegada)

Tres consumidores, no uno:
- **Buckets del período** (`mm_map`, reports.py:886): egresos `asset_payments += asset_revaluation_payment` (mismo bucket conceptual: capex); ingresos campo nuevo `asset_devaluation_collections` en `CashFlowResponse` (default 0.0 → backwards-compatible) + sumado al total. Frontend: línea condicional ≠ 0.
- **`OUTFLOW_TYPES` (reports.py:146) / `INFLOW_TYPES` (:136)**: reconstruyen el `opening_balance` del Cash Flow (~920) Y alimentan el MTD income/expense del Treasury Dashboard (~3190). `asset_payment` ya está espejado en OUTFLOW + mm_map — los tipos nuevos deben espejarse igual: `asset_revaluation_payment` → OUTFLOW_TYPES, `asset_devaluation_collection` → INFLOW_TYPES. Sin esto el opening_balance no reconcilia con el net_flow (el statement no cierra) y el dashboard MTD los pierde.
- `asset_revaluation_credit` / `asset_devaluation_receivable` NO tocan caja: fuera de buckets Y de frozensets (igual que `asset_purchase`).

Test: cash flow con revalorización pagada + devaluación cobrada dentro del período → `opening + inflows − outflows == closing` exacto, y dashboard MTD las incluye.

**Terna de signos (nota QA):** el signo que `revalue()` aplica al `current_balance` vivo debe coincidir EXACTO con los 3 lugares derivados (reports as-of, endpoint statement, frozensets/mm_map). `_create_movement` solo crea el registro — los efectos de saldo los aplica `revalue()` directamente, igual que `create()` hace con `asset_payment`. Los 4 tipos NO entran al dispatch del `create()` público de tesorería (module-owned, como `depreciation_expense`) ni a `_reverse_effects` (el bloqueo de `annul()` los hace inalcanzables ahí; agregar entradas muertas invita drift sin test).

### H5 — Estado de cuenta unificado (#16)

Los MMs con `third_party_id` aparecen solos (fuente MoneyMovements). Solo faltan labels frontend (`movementTypes` map) para los 4 tipos y decidir tabs de TreasuryPage: **no** ganan tab propio (volumen bajísimo); aparecen en "Todos" y en el estado de cuenta del tercero. `MovementCreatePage` NO los ofrece (se crean solo desde el módulo de activos, como `depreciation_expense`).

---

## 4. Consumidores — checklist completo

| Archivo | Cambio |
|---------|--------|
| `models/money_movement.py` | +4 tipos en `VALID_MOVEMENT_TYPES` con comentario de efecto |
| `models/fixed_asset.py` | modelo `AssetRevaluation` + relationship `revaluations` |
| `services/money_movement.py` | `_create_movement` funnel: efectos de los 4 tipos; `ASSET_MOVEMENT_TYPES` += 4; `_reverse_effects` NO los necesita (anulación solo vía módulo activos, pero implementarla defensivamente ahí también es barato y simétrico — decisión del implementador) |
| `services/fixed_asset.py` | `revalue()`, `annul_revaluation()`, `cancel()` extendido |
| `services/reports.py` | H1 (`_fa_value_at_cutoff` merge — cubre total Y detallado: ambos as-of enrutan por él, verificado :2163/:2186; el merge nivel 1 = máximo del UNION de ambas tablas por `(period, applied_at)`), H2 (2 sign maps), H3 (2 sitios), H4 (mm_map + frozensets INFLOW/OUTFLOW) |
| `endpoints/money_movements.py` | H2: los 2 mapas duplicados del statement (`THIRD_PARTY_BALANCE_DIRECTION`:56, `ACCOUNT_BALANCE_DIRECTION`:82) |
| `schemas/fixed_asset.py` | `AssetRevaluationRequest` (XOR validator), `AssetRevaluationResponse`, response del activo += `revaluations[]`, `revalued_total` |
| `schemas/reports.py` | `CashFlowResponse.asset_devaluation_collections`, `BalanceDetailedItem.revalued_amount` (opcional) |
| `endpoints/fixed_assets.py` | `POST /{id}/revalue`, `POST /{id}/revaluations/{rev_id}/annul` — permiso existente `treasury.manage_fixed_assets` (**sin migración de permisos**) |
| Migración Alembic | tabla `asset_revaluations` — **ID random hex** (lección PR-4) |
| Frontend | ver §6 |

Sin cambios: `_calculate_profit` (cero P&L), conciliación #59/#65, Rentabilidad por UN, Reporte de Gastos, migrate_org (revalorizaciones son post-migración; la carga histórica #46 ya cubre el valor inicial).

---

## 5. Fuera de alcance (explícito)

1. **Venta de activo** (baja con precio ≠ valor en libros y ganancia/pérdida en P&L) — la "baja" de este plan es ajuste de valor, no venta. Feature aparte si el cliente la pide.
2. **Revaluación NIIF a patrimonio** (sin contrapartida de caja/tercero) — el cliente pidió contrapartida cuenta/tercero explícitamente.
3. **Limpiar el workaround histórico** (activo dado de baja + gasto del mes) — Daniel: "déjalo así".
4. **Anulación individual de depreciaciones** — sigue no existiendo (solo cancel total del activo); el guard de 2.5 se apoya en eso.
5. **Cambio de `salvage_value`** vía revalorización.

---

## 6. Frontend (mobile-first, patrones CLAUDE.md)

- **`FixedAssetDetailPage`**: botón "Revalorizar" (PermissionGate `treasury.manage_fixed_assets`, solo status active/fully_depreciated) + sección "Revalorizaciones" (tabla desktop / cards mobile) con annul por fila (ConfirmDialog).
- **`RevalueAssetModal`**: toggle Alza/Baja → `MoneyInput` monto → XOR contrapartida (radio Cuenta/Tercero + `EntitySelect`) → `months_extended` (solo alza, Input numérico) → motivo (Textarea) → preview en vivo: "Valor: $X → $Y · Cuota: $A → $B · Meses restantes: N → M" → warning ámbar si hay depreciaciones pendientes (G1). Grid `grid-cols-1 sm:grid-cols-2`, dialog base ya responsive.
- **`FixedAssetsPage`**: sin cambios estructurales (el current_value ya se muestra).
- Labels de los 4 tipos en `movementTypes`/Excel/PDF del estado de cuenta.
- Invalidation: `invalidateAfterTreasury` + key `fixed-assets`.

---

## 7. Tests (≈22)

**Happy paths (4):** alza+cuenta, alza+tercero, baja+cuenta, baja+tercero — asserts: current_value, monthly_new exacto, saldo cuenta/tercero, MM tipo/monto, snapshot AssetRevaluation.
**Validaciones (7):** monto ≤ 0 (422); XOR fuente (422); baja > depreciable (400); baja sobre fully_depreciated (400); disposed/cancelled (400); months_extended en baja (422); alza sobre fully_depreciated sin meses (400) y con meses → revive active.
**Recalculo (3):** extensión de meses (monthly baja), alza sin extensión (monthly sube), última cuota ajusta a salvage tras revalorización (round-trip completo de depreciaciones).
**Anulación (4):** round-trip exacto al estado pre-revalorización (valor+cuota+saldo+status); bloqueo con depreciación posterior (400); anulación directa desde Tesorería bloqueada (422); cancel() de activo revierte revalorizaciones.
**Reportes (6):** H1 test de oro as-of 3 cortes + no-restatement de cortes previos; H2 saldos cuenta/tercero as-of == vivo; H2b **saldo corrido del estado de cuenta** (endpoint, cuenta Y tercero) con revalorización en ventana; H4 cash flow `opening + in − out == closing` + dashboard MTD; **P&L intocado** (net_profit idéntico antes/después de revalorizar — paridad).
**RBAC (1):** viewer → 403.

---

## 8. Orden de implementación

1. Migración (tabla) + modelo + tipos MM + funnel `_create_movement` + `ASSET_MOVEMENT_TYPES`.
2. `revalue()` + `annul_revaluation()` + `cancel()` extendido + schemas + endpoints.
3. Reports: H1 → H2 → H3 → H4 (con sus tests de oro primero, TDD en la zona #61).
4. Suite completa (BD 5433, UNA instancia de pytest).
5. Frontend (modal + detail + labels) + `tsc`.
6. QA → commit único a develop.
