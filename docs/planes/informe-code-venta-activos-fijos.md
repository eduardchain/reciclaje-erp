# Informe de implementación — Venta de Activos Fijos (plan v1.0 QA-GO)

**Fecha**: 2026-08-04 · **Rama**: develop (working tree, SIN commitear — espera QA de código + pruebas de Daniel)
**Plan**: `docs/planes/plan-venta-activos-fijos.md` v1.0 · **Decisión CLAUDE.md**: #88 (el consecutivo corrió a 88 porque el ciclo rápido SAC tomó el 87, como anticipó el QA)

---

## 1. Resumen

Plan implementado completo, sin desviaciones de diseño. `POST /fixed-assets/{id}/sell` (precio + XOR cuenta/tercero) y `POST /{id}/sale/annul`. D1 ejecutado tal cual: la venta NO genera depreciación acelerada — el libro queda congelado y `sale_gain = precio − libro` es la única huella en resultados.

## 2. Los 7 puntos verificados del plan

| Punto | Implementación |
|---|---|
| Catálogo 45→47 | `VALID_MOVEMENT_TYPES` +2 con comentarios de signos (smoke: `len == 47`) |
| Terna | `ACCOUNT_BALANCE_DIRECTION` +collection(+1); `THIRD_PARTY_BALANCE_DIRECTION` +receivable(+1) (único mapa, vivo y as-of); 2 mapas del statement espejo; `INFLOW_TYPES` +collection con campo desglose `asset_sale_collections` (4 sitios del patrón #67); receivable NO entra a inflows |
| Guard Tesorería | `ASSET_MOVEMENT_TYPES` +2 → anular directo 422 (test en ambos tipos) |
| P&L D6 | `SUM(fixed_assets.sale_gain)` JOIN MM por `sale_movement_id`, `status='confirmed'`, fechada por `MM.date`, `_not_by_sede` ($0 por sede M1); suma a `total_gross_profit`; cascada #71 por arrastre (test con las 2 identidades y la línea ≠ 0) |
| Conciliación 7 líneas | `PnlReconciliation.asset_sale_gain` + test de oro EXISTENTE extendido (identidad + assert 0 en fixture sin ventas) + test propio con venta real y residual < $1. Barrido de literales "6 líneas" hecho (QA nota 1): docstring schema, comentario reports.py:4565, comentario types/reports.ts |
| Migración | `e6f7a8b9c0d1` (3 columnas nullable + FK RESTRICT, espejo exacto en el modelo), aplicada en dev 5434; cero backfill |
| Anti-doble-conteo D1 | `sell()` no toca `current_value` ni crea `AssetDepreciation`; test `test_sell_to_account_with_loss` asserta libro congelado + `depreciations == []` |

## 3. Decisiones ejecutadas

- **D3**: comprador cualquier tercero menos provision/liability (espejo #32, validación calcada de la contrapartida de revalorización `fixed_asset.py`); sin restricción por signo (test dedicado: saldo −50M + venta 30M → −20M).
- **D5**: precio ≤ 0 → 422; disposed/cancelled → 400; depreciaciones pendientes → warning en `warnings[]` del response (patrón compras #17), helper `_pending_months` informativo.
- **D8**: `annul_sale` con barandilla LIFO defensiva (imposible por construcción, assert barato), status restaurado DERIVADO (`active` | `fully_depreciated` según libro vs salvage — test en ambos casos), columnas `sale_*` quedan como rastro con `sale_active=False`.
- **D9**: as-of exacto por construcción — golden corte-de-ayer en tests (venta hoy no mueve ni activo ni caja de ayer; corte de hoy y vivo: activo fuera, caja + precio).
- **QA nota 2**: `sale_active` (MM confirmed) gobierna la sección Venta del detail y el badge "Vendido" — tras anular sin re-vender, ni sección ni badge.

## 4. Frontend

- `SellAssetModal` (nuevo, espejo de RevalueAssetModal): valor en libros visible, radio "Cuenta de dinero" / "A crédito (tercero)" **sin default** (#63), EntitySelect de compradores filtrado (sin provision/liability), preview vivo Ganancia/Pérdida coloreada, warning ámbar de pendientes, copy del consumo de saldo (#31).
- `FixedAssetDetailPage`: botón "Vender", sección "Venta" (precio, libro al vender, ganancia/pérdida, link al MM) solo si vigente, "Anular Venta" con razón obligatoria, badge "Vendido" índigo.
- `FixedAssetsPage`: badge "Vendido" (helper `assetBadgeLabel/Class`) en tabla desktop y cards mobile.
- P&L: fila condicional en periodo y mensual + Excel (3 exports) + línea en conciliación de Rentabilidad por UN + "Venta de Activos" en Cash Flow.
- Tesorería: +2 labels en los 5 mapas duplicados, +2 en union `MoneyMovementType`, `ASSET_OWNED_TYPES` +2 en MovementDetailPage (botón anular oculto + nota guía).
- `useSellAsset` muestra los warnings del backend como toast ámbar; invalidación vía `invalidateAfterFixedAsset` (ya cubría reports/money-movements/accounts/third-parties).

## 5. Evidencia

- `test_asset_sale.py`: **23/23 verdes** (6 clases: happy paths 5, validaciones 5, P&L 3, cash flow/as-of/statement 3, anulación 6, RBAC 1).
- Regresión focalizada: **334 passed** (`test_api_fixed_assets` + `test_asset_revaluation` + `test_integration_08` + `test_api_reports` + `test_api_money_movements` + `test_integration_14` + `test_balance_historico_fixes`).
- Suite completa: **1468 passed, 0 failed en 25:36** (baseline 1445 + 23 nuevos exactos — cero regresión org-wide).
- Frontend: `npx tsc --noEmit` EXIT 0, `npm run build` ✓ 3.69s.
- Migración aplicada en dev 5434 (`e6f7a8b9c0d1 (head)`); 5433 se recrea por conftest (no-op).
- Parity check (secuencial tras la suite, regla QA E1): **cero divergencias de este ciclo** — solo las 4 cosméticas pre-existentes de renderings de CHECK documentadas en #87 (pendiente normalizar el comparador, fuera de este alcance).

## 6. Desviaciones y notas

> **Veredicto QA 2026-08-04: 🟢 LUZ VERDE** — terna de 7 sitios, D1, línea P&L, anulación y las 2 notas verificadas de primera mano (71/71 re-corridos + tsc EXIT 0) sobre el 1468/1468 de la suite. Desviación aceptada: comprador provision/liability → **404** (no 400 como decía la letra del plan) — espejo exacto de la contrapartida de revalorización #67, consistencia del módulo gana; el test lo asserta así.

- Ninguna desviación de diseño. Nota menor: la validación de contrapartida usa 404 "Tercero no encontrado" para provision/liability (calco exacto del código de revalorización) — consistencia interna del módulo.
- El parity check arrastra las 4 divergencias cosméticas de renderings de CHECK documentadas en #87 (pendiente normalizar el comparador, no es de este ciclo).

## 7. Checklist para pruebas de Daniel

1. Activo activo → "Vender" → precio mayor al libro → cuenta: caja sube el precio, el activo sale del balance, P&L muestra "Ganancia/Pérdida por Venta de Activos".
2. Vender a crédito (tercero): la CxC aparece en el estado de cuenta del comprador y en el panel de Dinero Inactivo; cobrarla después por el flujo normal de recaudos.
3. Vender bajo el libro: la línea del P&L sale negativa (pérdida).
4. Balance histórico: el corte de AYER no se mueve tras vender hoy.
5. Anular la venta: plata/CxC devuelta, activo vuelve a Activo (o Totalmente Depreciado), la línea sale del P&L, badge "Vendido" desaparece.
6. Intentar anular el movimiento desde Tesorería → mensaje guía al módulo de activos.
7. Vender con meses de depreciación sin aplicar → toast ámbar con la advertencia.
8. 390px: modal usable, preview visible, sección Venta legible.
