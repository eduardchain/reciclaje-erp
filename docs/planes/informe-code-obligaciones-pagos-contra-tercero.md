# Informe de implementación — Obligaciones: traslados contra tercero (plan v1.1 QA-GO)

**Fecha**: 2026-08-04 · **Rama**: develop (working tree, SIN commitear — espera QA de código + pruebas de Daniel)
**Plan**: `docs/planes/plan-obligaciones-pagos-contra-tercero.md` v1.1 · **Decisión CLAUDE.md**: #86

---

## 1. Resumen

Se implementó el plan completo, sin desviaciones de diseño. Dos acciones nativas del módulo F:

- `POST /financial-obligations/{id}/interest-transfer` — traslada `pending_interest` (total o parcial) contra un tercero destino, sin caja.
- `POST /financial-obligations/{id}/capital-transfer` — abono a capital con contrapartida tercero, sin caja.

Cada acción crea un **par enlazado**: MM de tipo nuevo sobre el titular de la obligación + leg `tp_transfer_out`/`tp_transfer_in` (tipos EXISTENTES) sobre el destino, cruzados por `transfer_pair_id` y AMBOS estampados con `financial_obligation_id`. Cuenta NULL en ambos → cash flow intacto por construcción.

## 2. Catálogo y terna — los 7 sitios (tabla §4 del plan)

| # | Sitio | Cambio |
|---|-------|--------|
| 1 | `models/money_movement.py` VALID_MOVEMENT_TYPES | +4 tipos (41→45), comentarios de signos |
| 2 | `services/financial_obligation.py` EFFECT_SIGNS | +6 entradas: los 4 nuevos (0, ±1) y los 2 legs `tp_transfer_*` (0, ∓1) — un solo camino de efectos (W2) |
| 3 | `services/reports.py` THIRD_PARTY_BALANCE_DIRECTION | +4 (`obligation_*: 1`, `loan_*: -1`) — único mapa, lo consumen vivo y as-of |
| 4 | `endpoints/money_movements.py` mapa TP del statement | +4, mismos signos; comentario en el mapa de CUENTA de que NO entran |
| 5 | INFLOW/OUTFLOW_TYPES (cash flow + dashboard) | **Sin cambios — deliberado**: cuenta NULL y el cash flow suma por tipo sin filtrar cuenta; test `before==after` lo clava |
| 6 | EXPENSE_MOVEMENT_TYPES / P&L | **Sin cambios — deliberado**: el interés ya entró al P&L al causarse; el traslado es solo movimiento de saldo |
| 7 | **GAP-1 (QA)**: `CAPITAL_DELTA_SIGNS` + `_capital_movements` | +2 SOLO capital transfers (−1); los de interés explícitamente FUERA. Test de matemática a mano `test_motor_capital_transfer_mid_month` |

## 3. Decisiones del plan ejecutadas

- **D4 contraparte**: mismo tercero → 400; titular de OTRA obligación activa → 400; entidad de sistema → 400; **sin restricción por signo** (regla de Daniel — test `test_transfer_makes_third_party_more_negative_allowed`). Validación vía `money_movement_service._validate_third_party` + checks propios en `_validate_transfer_counterpart`.
- **D5 retro guard**: solo capital (creación con `_retro_guard`, anulación con `_retro_guard_annul`); interés sin guard (no toca la base del motor).
- **Límites**: interés ≤ `pending_interest` → 400; capital ≤ `capital_balance` → 400.
- **D8/N1 dicts paralelos**: `INTEREST_TRANSFER_TYPE`, `CAPITAL_TRANSFER_TYPE`, `TRANSFER_LEG_TYPE` por dirección, junto a los existentes.
- **W4/N2 sumas del módulo**: `_capital_movements` y las reconstrucciones suman SOLO tipos propios; el leg aparece en `get_statement` por FK (display-only, correcto).
- **Anulación**: solo desde el módulo, cascade del par vía `_annul_transfer_leg` (reverse de efectos + auditoría en ambos). Anular el leg directo desde el módulo → 400 guía. Interés anulado → `pending_interest` +=; capital anulado → retro guard + `capital_balance` +=.
- **Guard Tesorería ampliado**: `services/money_movement.py` pasa del set de 8 tipos a `if movement.financial_obligation_id:` → 422 (ampliación estricta: cubre los 4 nuevos Y los legs estampados; cruces `tp_transfer_*` normales siguen anulables — test de no-regresión).
- **Cero migraciones** (`movement_type` es String(50) sin pg_enum), **cero permisos nuevos** (`treasury.manage_obligations`).

## 4. Frontend

- `ObligationDetailPage`: `ActionDialog` gana radios "Desde cuenta" / "Contra tercero (sin caja)" (default cuenta; oculto en desembolso), `EntitySelect` filtrado (excluye titular y entidades de sistema), preview informativo del saldo resultante del destino. Labels +6 en `MOVEMENT_LABELS`.
- `MovementDetailPage`: guard del botón Anular y banner guía pasan a campo-based (`isObligationOwned` = tipo ∈ OBLIGATION_TYPES ∪ `financial_obligation_id`) — cubre los legs.
- +4 labels en los 5 mapas duplicados (TreasuryPage, AccountMovementsPage, TreasuryDashboardPage, AccountStatementPage, MovementDetailPage) y en el union `MoneyMovementType`.
- Servicios/hooks/types: `interestTransfer`/`capitalTransfer`, `useObligationTransfer(action)`, `ObligationTransferCreate`.
- Verificación: `npx tsc --noEmit` limpio, `npm run build` ✓ (3.84s).

## 5. Evidencia de tests

- **Nuevos**: `TestObligationTransfers` (19) + `test_payable_walk_with_transfers` con invariante nuevo `check_dest` (saldo contraparte == Σ legs) = **20 tests**. Cobertura: happy payable/receivable interés+capital, parcial, más-negativo permitido, los 3 rechazos de contraparte, límites, retro guard creación+anulación, settled, round-trip de anulación del par, 422 Tesorería en ambos legs + cruce normal sigue anulable, leg vía módulo 400, **cash flow before==after**, statements de ambos terceros, transfer-all-then-settle, y el test estrella del motor (30M@2% M−2 + traslado 12M el día 16 de M−1 → 600.000/480.000; annul → 600.000; re-traslado+accrue → pending 1.080.000, capital 18M).
- **Corridas focalizadas** (5433, de a una): transfers+walk 22/22 · `test_financial_obligations.py`+`test_balance_historico_fixes.py`+`test_inactive_balances.py` = 116 passed · `test_api_money_movements.py`+`test_api_reports.py`+`test_integration_14_account_statement.py` = 249 passed.
- **Suite completa**: **1427 passed, 0 failed en 22:20** (baseline 1407 + 20 nuevos exactos — cero regresión org-wide).
- Walk existente: sets de reconstrucción extendidos (capital pagado += capital transfers, interés pagado += interest transfers; legs fuera con comentario W4).

## 6. Desviaciones y notas menores

> **Veredicto QA 2026-08-04: 🟢 LUZ VERDE** — 7 sitios de la terna confirmados uno a uno, 116/116 re-corridos de primera mano + tsc EXIT 0 sobre el 1427/1427 de la suite. Desviación aceptada: guards D4 en **400** (no 422 como decía la letra del plan) — es el idioma del módulo F desde #69; la consistencia interna gana. CLAUDE.md #86 ya lo documenta como 400.

- El handler de traslado valida **monto antes que contraparte** (un 400 de "supera los intereses pendientes" puede preceder al de entidad de sistema). Sin efecto funcional; el test de entidad de sistema usa capital-transfer para aislar la validación.
- `MoneyMovementType` (union TS) no tenía los tipos de #69 listados en el plan como pendientes — solo se agregaron los 4 nuevos (los de #69 ya estaban).

## 7. Checklist para pruebas de Daniel

1. En una obligación payable con intereses causados: "Pagar Intereses" → radio "Contra tercero (sin caja)" → elegir la cuenta personal → verificar que `pending_interest` baja, el titular baja su saldo y el destino queda más negativo (o menos positivo).
2. Estado de cuenta de AMBOS terceros: el par aparece con descripción "(traslado)" en el destino.
3. Anular el traslado desde el módulo → ambos MMs quedan anulados, contadores restaurados.
4. Intentar anular desde Tesorería → mensaje que guía al módulo (422).
5. Abono a capital contra tercero con saldo negativo → permitido, más negativo.
6. Cash flow del período: sin cambios por los traslados.
