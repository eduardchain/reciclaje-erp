# Plan — Pagos de obligaciones contra tercero (traslado de intereses y abonos a capital sin caja)

**Versión**: 1.1 (GAP-1 de QA plegado: 7º sitio de la terna — motor de intereses; N1 y N2 adoptadas)
**Fecha**: 2026-07-16
**Módulo**: Obligaciones Financieras (#69)
**Migraciones**: CERO. **Permisos nuevos**: CERO (reusa `treasury.manage_obligations`).

---

## 1. Contexto y problema

Caso real (Costa, obligación payable de Abdel): el cliente causó intereses ($2.5M) y quiso "matarlos" trasladándolos a la **cuenta personal** del mismo prestamista (2 terceros distintos en el sistema). Intentó el cruce entre terceros (`tp_transfer_out/in`): el tercero de la obligación quedó en 0 pero **el módulo siguió mostrando el pendiente** — los contadores (`capital_balance`, `pending_interest`) viven en la obligación y solo los mueven las operaciones del módulo. El cruce rompía el invariante `tp.balance == signo×(capital+pendientes)`. Lo anuló y resolvió con 2 movimientos por caja (pagar intereses + recibir depósito, neto cero) — **workaround bendecido vigente**.

Daniel confirmó que el flujo es frecuente ("la mayoría de esas obligaciones") y aprobó construirlo nativo, con una extensión: **también abonos a capital fondeados por un tercero**, y regla explícita: **el tercero contraparte puede quedar más negativo — el sistema lo permite, nunca bloquea por saldo** (filosofía #17/#76).

## 2. Qué se construye

Dos acciones nuevas en el módulo (backend + UI), para ambas direcciones (payable/receivable):

1. **Trasladar intereses a un tercero**: liquida `pending_interest` (total o parcial) con contrapartida un tercero — sin caja.
2. **Abono/recaudo de capital contra un tercero**: reduce `capital_balance` con contrapartida un tercero — sin caja.

Economía (caso payable, ej. Abdel): la deuda por intereses/capital de la obligación se convierte en deuda ordinaria en la cuenta personal. Obligación al día, tercero personal más negativo (le debemos más). Caja intacta.

## 3. Decisiones de diseño

**D1 — 4 tipos MM nuevos (catálogo 41→45), patrón accrual (cuenta NULL por construcción)**:

| Tipo | Dirección | tp obligación | tercero contraparte (leg par) |
|---|---|---|---|
| `obligation_interest_transfer` | payable | +1 | `tp_transfer_out` (−1) |
| `obligation_capital_transfer` | payable | +1 | `tp_transfer_out` (−1) |
| `loan_interest_transfer` | receivable | −1 | `tp_transfer_in` (+1) |
| `loan_capital_transfer` | receivable | −1 | `tp_transfer_in` (+1) |

**Por qué tipos nuevos y no reusar `obligation_interest_payment` con cuenta NULL**: el cash flow (sitio 6 de la terna) suma por tipo SIN filtrar `account_id IS NOT NULL` — tanto los rubros (`obligation_interest_payments` etc.) como el loop de opening balance (`reports.py:1316-1333`). Reusar tipos exigiría filtrar cuenta en N sitios (frágil, un olvido = flujo de caja fantasma). Los tipos nuevos **no entran** a `INFLOW/OUTFLOW_TYPES` → cash flow intacto por construcción — precedente exacto: los 2 accruals de #69 ("entran SOLO a los mapas de tercero").

**D2 — El leg contraparte es un `tp_transfer_out/in` EXISTENTE**, vinculado por `transfer_pair_id` (par, patrón transferencias/#84) y **estampado con `financial_obligation_id`**. Ventaja: estado de cuenta, mapas de saldo y as-of del tercero contraparte ya manejan esos tipos hoy — cero sitios nuevos para el leg.

**D3 — Anulación SOLO desde el módulo, cascade del par** (espejo #84): anular cualquiera de los 2 legs en Tesorería → 422 guía al módulo. Implementación: el guard de `money_movement.annul()` pasa de type-based a **`movement.financial_obligation_id IS NOT NULL` → 422** (cubre los legs `tp_transfer_*` del par sin ensanchar el set de tipos; los cruces normales sin obligación siguen anulables como hoy). `financial_obligation.annul_movement()` gana ramas para los 4 tipos: revierte efectos en AMBOS terceros, restaura contador (`pending_interest += X` / `capital_balance += X`), retro guard en capital (D5), y marca `annulled` los DOS MMs del par.

**D4 — Contraparte: cualquier tercero activo de la org, EXCEPTO**:
   (a) el mismo tercero de la obligación (422) — dejaría `tp.balance ≠ capital+pendientes` por construcción (la deuda "ordinaria" viviría en el mismo tercero fuera de los contadores; el walk lo detectaría);
   (b) un tercero que sea titular de **otra obligación activa** (422 "gestione desde el módulo de esa obligación") — moverle el saldo por fuera desincronizaría ese otro módulo: exactamente la clase de bug que motivó este plan;
   (c) provisiones/entidades de sistema (mismas reglas del cruce entre terceros actual — espejar su validación).
   **Sin restricción por signo ni por behavior_type**: el tercero puede quedar más negativo (regla explícita de Daniel). La UI muestra preview del saldo resultante (informativo, no bloquea).

**D5 — Guards heredados intactos**: interés: `amount ≤ pending_interest` (400), sin retro guard (igual que el pago actual — no toca tramos). Capital: `amount ≤ capital_balance` (400) + **retro guard** de período causado (creación y anulación, espejo exacto del abono actual — el capital en período causado rompe la matemática de tramos). Obligación settled → 400. Montos `gt=0`; sin regla nueva de pesos enteros (igual que pagos actuales; el pendiente ya nace entero por #69b).

**D6 — P&L, gastos, panel #68 y conciliación intactos por construcción**: el efecto P&L de los intereses ocurrió al CAUSAR (accrual); el traslado es solo de saldos. Los 4 tipos nuevos NO entran a `EXPENSE_MOVEMENT_TYPES`, ni a INFLOW/OUTFLOW, ni a mapas de cuenta. Panel #68: los traslados SÍ cuentan como actividad (evento real de gestión, a diferencia del accrual batch — deliberado). Conciliación #59/#69: sin cambios (no hay línea nueva de P&L).

**D8 (N1 QA) — Dicts paralelos por dirección**: `INTEREST_TRANSFER_TYPE = {payable: "obligation_interest_transfer", receivable: "loan_interest_transfer"}` y `CAPITAL_TRANSFER_TYPE = {...}` — espejo exacto de los 4 dicts existentes (`ACCRUAL_TYPE`, etc.). `_capital_movements` y los handlers consultan los dicts, nunca strings sueltos — hace imposible olvidar una dirección.

**D7 — Schema nuevo `ObligationTransferCreate`** (`amount`, `third_party_id` contraparte, `date`, `reference_number?`, `notes?`) + 2 endpoints: `POST /financial-obligations/{id}/interest-transfer` y `POST /{id}/capital-transfer` (permiso `treasury.manage_obligations`, mismo del resto). No se toca `ObligationMovementCreate` (su `account_id` sigue required — cero regresión en los pagos actuales).

## 4. Terna de signos — sitio por sitio (los 6 de #67/#69)

| Sitio | Cambio |
|---|---|
| `EFFECT_SIGNS` (financial_obligation.py, vivo) | +4 entradas: `(0, ±1)` (cuenta 0 como accruals) |
| `THIRD_PARTY_BALANCE_DIRECTION` (reports.py) | +4 entradas `±1` |
| 2 mapas del statement (money_movements.py) | +4 entradas `±1` cada uno |
| `ACCOUNT_BALANCE_DIRECTION` / mapas de cuenta | **NO entran** (cuenta siempre NULL) |
| `INFLOW/OUTFLOW_TYPES` (cash flow + dashboard) | **NO entran** |
| `VALID_MOVEMENT_TYPES` (modelo) | +4 con comentario de signos |
| **7º sitio (GAP-1 QA) — motor de intereses del módulo**: `_capital_movements` (:557) + `CAPITAL_DELTA_SIGNS` (:93) | Los **2 tipos de capital** entran a ambos: a la lista de `_capital_movements` (vía `CAPITAL_TRANSFER_TYPE[direction]`, D8) y a `CAPITAL_DELTA_SIGNS` con **−1** (espejo de `*_capital_payment/collection`). Los **2 tipos de interés NO entran** (no mueven capital — prevenir el over-add simétrico). Sin esto: exclusión SILENCIOSA (ni KeyError) → `_initial_capital` reconstruye mal el semilla y `_events_for_period` arma tramos con capital desactualizado → **toda causación posterior a un traslado de capital saldría con plata equivocada**, sin crash. Los contadores quedarían bien (el walk de contadores NO lo detecta) — por eso el test dedicado de §7.8. |

Los legs `tp_transfer_out/in` ya están en todos los mapas — cero cambios para ellos.

## 5. Mecánica de creación (servicio)

`create_interest_transfer` / `create_capital_transfer` (espejo de los handlers actuales):
1. `_get_active` + guards D4/D5.
2. MM obligación: tipo nuevo, `account_id=NULL`, `third_party_id` = tp obligación, `financial_obligation_id`, descripción "Traslado de intereses a {dest} — {tp}" / "Abono a capital desde {dest} — {tp}".
3. MM contraparte: `tp_transfer_out/in`, `third_party_id` = contraparte, `financial_obligation_id`, mismo `transfer_pair_id` (ambos legs), descripción espejo "(por obligación #N de {tp})".
4. Efectos: `_apply_effects` del tipo nuevo sobre tp obligación + efecto manual `∓X` sobre contraparte (o reusar el camino del cruce si es componible).
5. Contador: `pending_interest -= X` / `capital_balance -= X`.
6. Un solo commit (atómico).

## 6. Frontend

- **ObligationDetailPage**: los diálogos de "Pagar intereses" y "Abonar a capital" ganan selector de contrapartida — radio **"Desde cuenta"** (default, flujo actual intacto) / **"Contra tercero"** (nuevo: EntitySelect de terceros + preview "Saldo resultante de {tercero}: −$X" informativo). El monto máximo clickable (#69b) se mantiene.
- **Labels** de los 4 tipos en `constants.ts` + statement + Tesorería (con banner guía "gestione desde la obligación" en `MovementDetailPage`, patrón existente).
- Lista de movimientos del detail: muestra el par (leg contraparte con nombre del tercero destino).
- `queryInvalidation`: la acción invalida obligations + money-movements + third-parties + reports (mapa existente de treasury).

## 7. Tests (~18)

1. Happy ×4 (payable/receivable × interés/capital): contadores, saldos de AMBOS terceros, par vinculado (`transfer_pair_id`, ambos con `financial_obligation_id`), invariante `tp.balance == signo×(capital+pendientes)`.
2. **Regla de Daniel**: contraparte ya negativa → queda más negativa, 200 limpio (test explícito).
3. Mismo tercero → 422; tercero de otra obligación activa → 422; settled → 400.
4. Interés: `amount > pending` → 400; parcial OK. Capital: `amount > capital` → 400; retro guard período causado → 400 (creación Y anulación).
5. Anulación: desde el módulo revierte ambos terceros + contadores y anula los 2 legs (round-trip al origen); anular cualquiera de los legs en Tesorería → 422; **cruce normal sin obligación sigue anulable** (no-regresión del guard D3).
6. **Cash flow**: crear traslado → inflows/outflows/opening idénticos a antes (por construcción, pero con test).
7. Estado de cuenta de ambos terceros: legs visibles con saldo corrido correcto; golden parity statement vs balance detallado (#61) con un traslado en el fixture.
8. **TestObligationWalk extendido**: acciones de traslado intercaladas (causar→trasladar→anular traslado→pagar resto) con los 4 invariantes tras cada paso + invariante nuevo: saldo del tercero contraparte == Σ de sus movimientos. **Además (GAP-1 QA), la secuencia que clava la matemática del motor** — porque el invariante de contadores NO detecta un traslado de capital excluido del motor: traslado de capital a mitad del mes M (día D) → causar M (y M+1) → assert del interés contra cálculo A MANO con el tramo partido en el día D (el día del evento cuenta con saldo NUEVO — análogo del canónico $200K+$100K de #69). También el espejo: anular el traslado de capital → re-causar → interés vuelve al valor sin traslado.
9. Summary del módulo refleja pendiente/capital reducido.

## 8. Fuera de alcance

- Traslado de intereses **futuros/automático** (cada mes sigue siendo: causar → trasladar manualmente).
- Contraparte cuenta+tercero mixta en una sola operación.
- Reapertura de obligaciones settled.
- Migrar/convertir los 2 movimientos manuales que el cliente ya hizo por caja (quedan como están — correctos).

## 9. Riesgos y watch-points para QA

- **W1**: el guard D3 (`financial_obligation_id` → 422 en Tesorería) cambia el criterio del guard existente de type-based a campo-based — verificar que ningún flujo legítimo anulaba en Tesorería un MM con `financial_obligation_id` (hoy son solo los 8 tipos del módulo, ya bloqueados por tipo → el cambio es ampliación estricta, pero confirmarlo).
- **W2**: el efecto sobre el tercero contraparte debe pasar por UN solo camino (no duplicar con `_apply_effects` + camino del cruce a la vez).
- **W3**: `_get_tp_balances_as_of` (#41, 5 fuentes) — confirmar que la fuente MM usa el mapa de dirección que ganó las 4 entradas (sin mapa duplicado olvidado).
- **W4 (reforzado por N2 QA)**: el leg contraparte comparte `financial_obligation_id` — cualquier listado/suma del módulo que filtre por esa FK lo duplicaría. Regla: las sumas y el statement del módulo usan SOLO los tipos propios (los 10 del catálogo del módulo tras este plan); el test del par asserta explícitamente que el detail de la obligación y sus agregados no cuentan el leg `tp_transfer_*` dos veces. (`_capital_movements` ya filtra por tipos, no por FK — patrón a seguir.)
- **W5**: fixture del walk con contraparte compartida entre varias operaciones para cazar dobles efectos.
