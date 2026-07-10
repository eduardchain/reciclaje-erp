# Reporte para QA — PR-3: warning al cancelar compra que proyecta hueco

**Fecha:** 2026-07-10 · **Estado:** implementado, SIN commitear (pendiente QA) · **Rama:** develop
**Plan:** `docs/planes/plan-fix-estructural-costo-promedio.md` sección 5 (Fase 3 — QW-D redefinido). Aditivo sobre PR-1/PR-2; no bloquea el deploy del paquete.

## 1. Qué hace

Cancelar una compra **liquidada** cuyo material ya fue vendido pasa el guard (`check_can_revert` es correcto: las ventas no crean MCH bajo Modelo L) pero deja `current_stock_liquidated` negativo **en silencio**. Ahora el sistema **avisa sin bloquear** (filosofía #17 "avisar, no bloquear"): con PR-2 el hueco es un estado consistente (se maneja al rellenarse), esto es información al operador.

## 2. El cambio (3 archivos + tests)

- **`purchase.py cancel()`**: retorna `tuple[Purchase, list[str]]` (mismo patrón que create/update). Tras revertir, arma warnings **una vez por material con el estado FINAL** (dedup en multi-línea; también avisa si el material YA estaba en hueco — "queda negativo" es honesto en ambos casos). Solo rama `was_liquidated` (cancelar registered devuelve transit, no toca liquidated).
- **`endpoints/purchases.py cancel_purchase`**: destructura la tupla y setea `response_data["warnings"]` — `PurchaseResponse.warnings` ya existía (Optional, línea 188).
- **`usePurchases.ts useCancelPurchase`**: `onSuccess(data)` → `toast.warning` por cada warning (duration 8s). `PurchaseResponse.warnings?` ya estaba en el tipo TS.
- Único caller del servicio era el endpoint (verificado) — sin más firmas que ajustar.

Mensaje: `"El stock liquidado de {code} queda negativo tras la cancelación: {qty} {unit} (el material ya fue vendido)"`.

## 3. Tests (2 nuevos) y verificación

- `TestCancelPurchaseHoleWarning::test_cancel_projecting_hole_returns_warning`: compra 100 auto → venta 80 liquidada → cancelar compra → **200 + warning** con "ML-COBRE" y "-80"; `liquidated == -80`.
- `::test_cancel_without_hole_no_warning`: cancelar con stock de sobra → sin warnings.
- Corrida: `test_avg_cost_model_l.py` (19) + `test_api_purchases.py` completo = **85 passed, 1 failed** (el pre-existente #54 exacto). Los cancels existentes (round-trip QW-A, oversell PR-2, stress walk) verdes con la firma nueva. `tsc --noEmit` OK.

## 4. Puntos con lupa

1. **Firma cambiada de `cancel()`** (Purchase → tupla): grep confirmó un solo caller (endpoint). El stress walk y los tests de cancel existentes pasan por el endpoint → cubiertos.
2. **Warning con estado final por material** (no por línea): una compra multi-línea del mismo material no duplica el aviso.
3. **DP fuera**: compras DP no pasan por `purchase.cancel` (bloqueadas antes).
4. UI: v1 = toast (el plan contempla "preview antes de confirmar" como mejora opcional futura con endpoint dedicado — no en este PR).

Al cerrar (tras QA): se documenta dentro de #65 (una línea — es la Fase 3 del mismo plan) o como nota; memoria actualizada.
