# Plan de implementación — Fix estructural del costo promedio móvil (Modelo L)

**Fecha:** 2026-07-09 · **Estado:** PLAN PARA REVISIÓN DE QA (sin implementar)
**Decisión de negocio:** Daniel confirmó el **Modelo L** (2026-07-09) tras revisar los ejemplos de order-dependence, denominador negativo y C1. Respuestas previas: (1) no hay orden concreto de liquidación; (2) COGS al liquidar; (3) ventas al costo del stock liquidado.
**Relacionado:** memoria `bug_costo_promedio_movil`, `docs/planes/auditoria-costo-promedio-movil.md`, decisiones CLAUDE.md #3/#5/#8/#9/#17/#18/#42/#49/#59/#61.

---

## 0. Cómo leer este documento (para QA)

Cada fase tiene: el cambio exacto (archivo:línea del código ACTUAL), un ejemplo numérico verificable a mano, los casos borde analizados, y los tests que lo fijan. La sección 8 lista lo que **NO** cambia (refutar ahí es tan valioso como en lo que sí). La sección 10 son los puntos débiles auto-señalados — empezar por ahí.

Convención de los ejemplos: `pool` = `current_stock_liquidated` con su `current_average_cost`. "Valor del pool" = `liquidated × avg` (así valúa el sistema el inventario).

---

## 1. El problema (recap con el caso real)

Dos facetas del mismo desfase temporal:

**Faceta 1 — COGS rancio.** El COGS de la venta se congela al REGISTRAR ([sale.py:217](../../backend/app/services/sale.py#L217): `unit_cost = material.current_average_cost`) y **nunca** se recalcula: la liquidación solo mueve stock ([sale.py:392-398](../../backend/app/services/sale.py#L392-L398)). Si entre registro y liquidación se liquidan compras (el flujo báscula normal: registrar temprano, liquidar al final), la utilidad de esa venta queda calculada con un costo viejo — para siempre.

**Faceta 2 — promedio "inflado".** La liquidación de compra promedia contra `current_stock_liquidated` ([purchase.py:1231-1238](../../backend/app/services/purchase.py#L1231-L1238)), que aún contiene las unidades de ventas registradas-no-liquidadas (el registro de venta resta `stock`/`transit`, no `liquidated` — [sale.py:250-251](../../backend/app/services/sale.py#L250-L251)).

**Caso Clausen (Meta):** compra #54 (1.000 kg @ 8.000) liquidada 18:45 con venta #38 (2.440 kg) registrada 17:45 → promedió contra 4.469 kg en vez de 2.029 → avg $9.396,64. Y el COGS de la #38 quedó congelado con el avg de las 17:45.

**Bajo el Modelo L, la Faceta 2 deja de ser bug:** las 2.440 kg de la venta pendiente siguen legítimamente "en el pool" hasta que su venta se liquide. El $9.396,64 pasa a ser **el número correcto del modelo**. Lo que este plan arregla es la Faceta 1 (más los mecanismos que pierden valor: secciones 4 y 5). Esto hay que comunicárselo así al cliente: adoptamos una convención coherente, no "corregimos hacia EL número verdadero".

## 2. El modelo elegido y su trade-off (decidido, no re-litigar — pero sí refutable en consecuencias)

**Regla del Modelo L: nada existe financieramente hasta que se liquida.** La venta extrae del pool en SU liquidación, al promedio vigente en ese momento. Las compras siguen promediando contra el pool liquidado completo.

Trade-off aceptado por Daniel — el COGS depende del orden de liquidación (acotado por la diferencia de precios de las compras que se cruzan):

**Ejemplo canónico.** Pool 1.000 kg @ 9.000. Se registra compra de 500 @ 8.000 y venta de 800.

| Orden de liquidación | COGS venta (800) | Inventario final (700) | Suma |
|---|---|---|---|
| Venta primero, compra después | 800 × 9.000 = **7.200.000** | 700 × 8.285,71 = 5.800.000 | 13.000.000 ✓ |
| Compra primero, venta después | 800 × 8.666,67 = **6.933.333** | 700 × 8.666,67 = 6.066.667 | 13.000.000 ✓ |

La suma (COGS + inventario) es invariante = valor total entrado (9.000.000 + 4.000.000). El orden solo mueve el reparto. **Test de conservación = guardrail del modelo** (sección 9, T1).

Se descartó el Modelo P (COGS al registrar, order-independent) porque exige restar del pool al registrar → en el flujo báscula el pool se va negativo **todos los días** → fórmula de promedio con denominador ≤ 0 → costos absurdos (replay Costa: −$1.6M). Veto de Daniel 2026-06-16, re-confirmado 2026-07-09.

## 3. FASE 1 — Núcleo: el COGS se finaliza al liquidar la venta

### 3.1 Cambio

En `sale.liquidate()`, dentro del loop existente que mueve stock ([sale.py:392-398](../../backend/app/services/sale.py#L392-L398)), ANTES de mover:

```python
# Modelo L: finalizar COGS al promedio vigente a la liquidación.
# Pre-cargar movimientos de la venta y emparejar por firma (patrón QW-B, deque):
movements = db.query(InventoryMovement).filter(
    InventoryMovement.reference_type == "sale",
    InventoryMovement.reference_id == sale.id,
    InventoryMovement.movement_type == "sale",
).all()
movements_by_key: dict = defaultdict(deque)
for mv in movements:
    movements_by_key[(mv.material_id, mv.quantity)].append(mv)

for line in sale_lines:
    material = db.get(Material, line.material_id)

    final_cost = material.current_average_cost
    if final_cost == 0:
        final_cost = self._get_last_known_cost(db, material.id, organization_id)
    line.unit_cost = final_cost

    queue = movements_by_key.get((line.material_id, -line.quantity))
    inv_movement = queue.popleft() if queue else None
    if inv_movement:
        inv_movement.unit_cost = final_cost

    material.current_stock_transit += line.quantity      # (ya existe)
    material.current_stock_liquidated -= line.quantity   # (ya existe)
```

**No se crea MCH**: extraer al promedio no cambia el promedio (invariante del promedio ponderado). El avg del material queda intacto — solo cambia QUÉ costo se lleva la venta.

### 3.2 Por qué esto no puede tocar Pasa Mano (verificable)

- `sale.liquidate` **rechaza** ventas DP con 400 ([sale.py:316-320](../../backend/app/services/sale.py#L316-L320)).
- La liquidación de DP es un servicio propio ([double_entry.py:218](../../backend/app/services/double_entry.py#L218)) que fija `sl.unit_cost = de_line.purchase_unit_price` ([double_entry.py:297](../../backend/app/services/double_entry.py#L297)) — su COGS es el precio de compra del cruce, no inventario (decisión #1). **Cero cambios ahí.**

### 3.3 Casos borde analizados

| Caso | Comportamiento | Por qué está bien |
|---|---|---|
| `auto_liquidate` (1 paso) | create captura avg X, liquidate recalcula al MISMO avg X (nada cambió en medio) | Neutro por construcción. Test T3. |
| avg = 0 al liquidar (material nuevo) | Fallback `_get_last_known_cost` (mismo que create, [sale.py:218-219](../../backend/app/services/sale.py#L218-L219)). Bajo L este caso CAE en frecuencia: si alguna compra se liquidó antes que la venta, avg ya no es 0 (hoy el $0 del registro quedaba congelado — hallazgo del audit: ~$5,2M utilidad ficticia en Costa) | Mejora directa. Test T4. |
| Venta multi-línea del mismo material | Extraer no cambia avg → todas las líneas al mismo costo, **sin** orden-dependencia intra-venta (a diferencia del bug QW-B en compras) | El matching por firma usa deque desde el día 1 (lección QW-B). Si dos líneas comparten (material, qty) son intercambiables (mismo costo). |
| `received_quantity` (báscula) | COGS = `unit_cost × quantity` ORIGINAL; `total_price = received × price`. Sin cambio (decisión #18) | El recálculo solo toca `unit_cost`, nunca la fórmula. |
| Venta registered editada (revert-reapply) | Re-captura unit_cost provisional al avg vigente del re-apply ([sale.py:723-725](../../backend/app/services/sale.py#L723-L725)). Sin cambio | Sigue siendo provisional; se finaliza al liquidar. |
| Venta liquidada | No es editable (decisión #8) → no existe re-liquidación | N/A |
| Warehouse | La firma de matching no necesita warehouse: `sale.warehouse_id` es único por venta | Simplificación correcta hoy; si algún día hay ventas multi-bodega, la firma gana el campo. |

### 3.4 Consumidores de `SaleLine.unit_cost` — el valor cambia, ninguna fórmula cambia

- **P&L COGS**: `SUM(unit_cost × quantity)` [reports.py:299](../../backend/app/services/reports.py#L299), filtrado por `liquidated_at` (#42) → tiempo y valor quedan por fin alineados.
- **Reporte de ventas / dashboard** (#60): `total_price − unit_cost × quantity` [reports.py:2230+](../../backend/app/services/reports.py#L2230) — igual.
- **Profit por venta**: [sale.py:1019-1022](../../backend/app/services/sale.py#L1019-L1022) — derivado, no persistido → se actualiza solo.
- **Ventas registered** no entran a reportes financieros (filtran liquidadas por `liquidated_at`) → su unit_cost provisional solo se ve como "utilidad estimada" en el detalle. **Efecto UX consciente:** la utilidad mostrada de una venta registered puede cambiar al liquidarla. Aceptado (el número final es el bueno); opcional rotular "estimada" en UI.
- **Kardex** (`MovementHistoryPage` running balance): el `unit_cost` del movimiento de venta se muta in-place al liquidar. Precedente idéntico ya existente y documentado para compras: [reports.py:1841-1857](../../backend/app/services/reports.py#L1841-L1857) (el fallback histórico as-of tiene gate `unit_cost > 0` y solo lee movimientos de compra/ajuste, **no ventas** → no lo afecta).

## 4. FASE 2 — Conservación de valor (helper compartido)

Hoy hay **tres mecanismos que crean/destruyen valor sin registro**. Los tres comparten la misma raíz: incorporar unidades a un pool cuyo estado es negativo (o reingresar sin ponderar). Se resuelven con UN helper puro.

### 4.0 El helper: `app/services/inventory_costing.py` (nuevo, sin DB)

```python
def incorporate_into_pool(
    liquidated: Decimal,   # stock liquidado ANTES (puede ser negativo)
    avg_cost: Decimal,     # promedio vigente ANTES
    quantity: Decimal,     # unidades que entran (> 0)
    unit_cost: Decimal,    # costo real de lo que entra
) -> tuple[Decimal, Decimal]:
    """Retorna (new_avg_cost, cost_adjustment).

    cost_adjustment: diferencia entre lo ya cargado a COGS por el hueco
    y el costo real de reposición. > 0 = se cargó COGS de más (ganancia);
    < 0 = de menos (pérdida). 0 si liquidated >= 0.
    """
    if liquidated >= 0:
        new_liq = liquidated + quantity
        if liquidated == 0:
            return unit_cost, Decimal("0")
        new_avg = (liquidated * avg_cost + quantity * unit_cost) / new_liq
        return new_avg, Decimal("0")

    # Oversell: hueco de -liquidated unidades ya cargadas a COGS @ avg_cost.
    hole = -liquidated
    filled = min(hole, quantity)
    adjustment = (filled * (avg_cost - unit_cost)).quantize(Decimal("0.01"))
    remaining = quantity - filled
    if remaining > 0:
        return unit_cost, adjustment       # resto entra limpio al costo real
    return avg_cost, adjustment            # hueco no cubierto: sigue @ avg previo
```

Puro → testeable unitario sin BD (T5-T8). Los callers persisten el `adjustment` y hacen MCH.

**Ejemplo A — relleno completo (el C1 del scoping).** Pool −200 @ 10.000 (COGS ya cargado: 2.000.000). Compra 1.000 @ 8.000:
- `filled=200`, `adjustment = 200 × (10.000 − 8.000) = +400.000` (ganancia: se cargó de más), pool queda **800 @ 8.000**.
- Cuadre: compra 8.000.000 = COGS neto (2.000.000 − 400.000) + inventario (6.400.000) ✓.
- **Hoy** el reset deja 800 @ 8.000 pero el +400.000 no existe en ningún lado → salto patrimonial silencioso (lo que medía la validación patrimonial).

**Ejemplo B — relleno parcial encadenado.** Pool −800 @ 8.000. Compra 300 @ 9.000 → `adjustment = 300 × (8.000−9.000) = −300.000`, pool **−500 @ 8.000** (avg intacto). Luego compra 1.000 @ 9.500 → `adjustment = 500 × (8.000−9.500) = −750.000`, pool **500 @ 9.500**.
- Cuadre total: compras 12.200.000 = COGS neto (6.400.000 + 300.000 + 750.000 = 7.450.000) + inventario (4.750.000) ✓ — y 7.450.000 es exactamente 300×9.000 + 500×9.500, el costo real de reposición del hueco. La matemática cierra al centavo por construcción.

### 4.1 (2a) Liquidación de compra — reemplaza el reset de `_apply_cost_at_liquidation`

- [purchase.py:1231-1238](../../backend/app/services/purchase.py#L1231-L1238): la rama `old_liquidated <= 0 → avg = confirmed_price` se reemplaza por el helper. La rama positiva da resultados **idénticos** a hoy (T6 lo fija).
- **G1 (QA):** el helper recibe el **`adjusted_unit_cost`** (precio + comisión prorrateada/qty, decisión #30) como `unit_cost`, NUNCA el `unit_price` crudo — el adjustment de oversell debe calcularse con el costo real que entra al pool. Test lo fija con una compra comisionada que rellena hueco.
- **G2 (QA):** el helper se invoca DENTRO del loop per-línea de QW-B ([purchase.py:462-497](../../backend/app/services/purchase.py#L462-L497)), con el `current_stock_liquidated` **corriente** (ya actualizado por las líneas previas de la misma compra) — una compra multi-línea que rellena un hueco progresivamente debe ver el pool evolucionar línea a línea. Test: compra de 2 líneas del mismo material sobre hueco parcial.
- El `adjustment` de cada línea se persiste en columna nueva **`purchase_lines.cost_adjustment`** (Numeric(15,2), default 0) — migración Alembic (dev 5434 + test 5433, NUNCA prod manual).
- **Importante bajo Modelo L:** el oversell deja de ser exótico. Si el liquidador liquida ventas antes que compras (orden libre — respuesta 1 de Daniel), el pool queda negativo transitoriamente y la compra siguiente rellena. C1 pasa de "edge case" a **camino normal** → por eso esta fase no es opcional.
- **Cancelación de la compra**: revierte avg vía MCH (`previous_cost`) + resta stock + la compra sale del P&L (filtro status) → el adjustment sale con ella → el estado vuelve exacto al pre-compra. Consistente sin código extra (T9).

### 4.2 (2b) Cancelar venta liquidada — reingreso ponderado (la fuga de $152M)

**Hoy:** [sale.py:525-529](../../backend/app/services/sale.py#L525-L529) devuelve las unidades al pool **sin recalcular avg** → el inventario se re-valúa al promedio actual mientras el P&L devuelve el COGS histórico → diferencia fantasma. Es la fuga identificada en la validación patrimonial (mayo Costa: 7 ventas canceladas, $152M re-valuados).

**Ejemplo C.** Pool 200 @ 9.000 (= 1.800.000). Se cancela venta de 800 kg con COGS final 8.666,67 (P&L devuelve 6.933.333).
- **Hoy:** pool 1.000 @ 9.000 = 9.000.000 → inventario subió 7.200.000 pero el P&L devolvió 6.933.333 → **+266.667 fantasma**.
- **Fix:** reingreso ponderado vía helper con `unit_cost = line.unit_cost` (el COGS revertido): pool 1.000 @ (1.800.000 + 6.933.333)/1.000 = **8.733,33** → inventario sube exactamente 6.933.333 ✓ simetría perfecta con el P&L.

Cambio en `sale.cancel`, rama `was_liquidated` (el `sale_reversal` ya lleva `unit_cost=line.unit_cost`, [sale.py:517](../../backend/app/services/sale.py#L517) — solo falta ponderar):
- Aplicar helper por línea; si `new_avg != old_avg`, registrar **MCH `source_type="sale_cancellation"`** (nuevo, 5º tipo).
- El MCH nuevo hace que `check_can_revert` **bloquee automáticamente** revertir compras anteriores tras un cancel que movió el avg (correcto: el revert asume que nada más tocó el promedio). Agregar la etiqueta al dict `source_labels` de [material_cost_history.py](../../backend/app/services/material_cost_history.py) — hoy tiene 4.
- Cancel de venta **registered**: devuelve a `transit` ([sale.py:528-529](../../backend/app/services/sale.py#L528-L529)), que no participa del avg → **sin cambio**.
- Si el `adjustment` del helper ≠ 0 (cancelar mientras el pool está en hueco — raro), se persiste en columna nueva **`sales.cancellation_cost_adjustment`** y entra a la misma línea de P&L (sección 4.4), fechado por `cancelled_at`.

### 4.3 (2c) Ajustes increase y transformaciones destino — mismo patrón, fase posterior

El mismo reset existe en [inventory_adjustment.py:88-94](../../backend/app/services/inventory_adjustment.py#L88-L94) (increase) y [material_transformation.py:282-287](../../backend/app/services/material_transformation.py#L282-L287) (destinos). **Adoptan el helper en un PR separado** (mismo diseño, columnas análogas) para no inflar el primer QA. Anotado como deuda explícita con test pendiente. Nota: recount ([inventory_adjustment.py:238-249](../../backend/app/services/inventory_adjustment.py#L238-L249)) pondera contra `old_total` (no `liquidated`) — inconsistencia pre-existente señalada por el audit (0 usos multi-bodega hoy); NO se toca en este plan.

### 4.4 Línea nueva de P&L + conciliación (#59) — o el test de oro revienta

- Línea nueva en `_calculate_profit`: **"Ajuste de costo por sobreventa"** = `SUM(purchase_lines.cost_adjustment)` de compras `liquidated` por `liquidated_at` en el período **+** `SUM(sales.cancellation_cost_adjustment)` de ventas `cancelled` por `cancelled_at`. Signo: positivo suma a utilidad.
- ⚠️ **`test_reconciliation_residual_zero` (decisión #59) fallará por diseño** si la línea no se agrega también al bloque `PnlReconciliation` (las "4 líneas no atribuibles a UN" pasan a 5). Ese test existe exactamente para atrapar esto — el plan lo actualiza a propósito, no como efecto colateral.
- El P&L Mensual (#50) hereda la línea gratis (reusa `get_profit_and_loss` por columna). Drill-down (#49): la línea nace **sin** link (como otras líneas menores); si se quiere después, el patrón está.
- Frontend: fila nueva en `ProfitAndLossPeriodView` (+ Excel export) — mostrar solo si ≠ 0 para no ensuciar el P&L de quien nunca oversella.
- **G3 (QA — timing cross-período, comunicar al cliente):** el ajuste se fecha por el `liquidated_at` de la **compra que rellena**, no de la venta que sobrevendió. Venta sobrevende en mes M (COGS @ avg vigente), compra rellena en M+1 → el ajuste aparece en M+1. El margen "real" de esa venta queda repartido entre dos meses del P&L Mensual (#50). Es correcto (el ajuste ES un evento del momento del relleno — recién ahí se conoce el costo real), pero el cliente debe entenderlo: la corrección aterriza en un mes distinto al de la venta.
- **G4 (QA — atribución a UN):** el ajuste es org-level, NO por UN — entra al bloque de conciliación #59 como 5ª línea no atribuible. QA verificó que esto es estructuralmente **requerido** (no simplificación) para que el residual de Rentabilidad por UN cierre. Visibilidad por UN sería enhancement aparte.

## 5. FASE 3 — Aviso al cancelar compra que proyecta hueco (QW-D, redefinido)

El hallazgo original ("`check_can_revert` ciego a ventas") se redefine: no hay que "ver ventas" — basta **proyectar el resultado**: si al cancelar la compra algún material queda `current_stock_liquidated − qty < 0`, avisar. Con la Fase 2 el sistema ya es consistente ante huecos (nada se corrompe); esto es información al usuario, filosofía "avisar, no bloquear" (#17, stock negativo permitido).

- `purchase.cancel` acumula `warnings: list[str]` ("La cancelación deja stock liquidado negativo en FR001: −3.200 kg") y el endpoint los retorna en el response (patrón `warnings[]` existente en ventas/ajustes).
- Frontend: toast/`WarningsList` post-cancelación. (Mejora opcional futura: preview ANTES de confirmar — requeriría endpoint de preview; no en v1.)
- `check_can_revert` NO cambia su lógica MCH (sigue bloqueando lo suyo); solo gana la etiqueta `sale_cancellation` (sección 4.2).

## 6. FASE 4 — Remediación de datos históricos ~~(gated, NO bundlear)~~ — **DESCARTADA (decisión de negocio, Daniel 2026-07-10)**

> **🔴 DECISIÓN FINAL: NO se remedia.** Las reglas del Modelo L aplican **desde el deploy hacia adelante**; el COGS histórico queda con el método viejo, documentado. Razones: coherente con la doctrina #61 "el pasado no se reescribe"; el cliente ya vio esos P&L (re-presentarlos cuesta credibilidad, especialmente post-incidente Costa); magnitud <1% del COGS (Costa +$13,8M sobre $2.845M) ya cubierta por `docs/justificacion-cliente-diferencias-inventario.md`. La remediación NO tocaba cobros/estados de cuenta/saldos (solo COGS interno) — el descarte no es por riesgo técnico sino por costo de comunicación vs beneficio. **La remediación QW-B (#1074/#1295, ~$1M kardex) también se descarta por coherencia** (error de dato puntual, promedio actual ya auto-corregido; separable si algún día se reabre). El dry-run de abajo queda como registro por si se reabre la discusión.

Re-costear `SaleLine.unit_cost` (y el `InventoryMovement` espejo) de ventas **liquidadas** históricas al avg as-of su liquidación, leído de `MaterialCostHistory` — que el audit halló 100% íntegro (avg == último MCH, cadena continua) → **mucho más confiable que el replay físico** que falló en Costa.

- **Convención intradía:** para históricos, el orden real intradía se perdió en los backfills (#43/#61 reescribieron fechas a mediodía). Regla: tomar el `new_cost` del **último MCH del día** `<= liquidated_at::date` (orden `(transaction_date, created_at)`) = "como si la venta se liquidara al cierre del día". Documentar en el script; QA puede proponer alternativa.
- Incluye de una vez los COGS $0 congelados (material nuevo) — subset del mismo recompute.
- **Lo que NO se remedia:** el `current_average_cost` actual de los materiales (bajo L, los promedios tipo Clausen $9.396 son correctos del modelo) ni los 14 materiales con `liquidated < 0` (estado válido bajo L; la Fase 2 los maneja hacia adelante).
- Mecánica: script tipo #43 — `--dry-run` default con **reporte de deltas de COGS/utilidad por mes y por org** (el go/no-go de Daniel se toma viendo ese número), `--apply`, tabla audit snapshot para rollback selectivo, idempotente.
- **Re-presenta el P&L histórico UNA vez** → comunicar al cliente junto con el deploy pendiente de #61 (una sola conversación de "los números históricos se re-presentan").

### 6.1 Dry-run temprano ejecutado (2026-07-09, réplica prod fresca — ventas hasta hoy)

Simulación read-only de la remediación contra dev (LATERAL: último MCH con `COALESCE(transaction_date, created_at::date) <= liquidated_at::date`, desempate `created_at`). Solo ventas liquidadas no-DP:

| | Costa | Meta |
|---|---|---|
| Líneas evaluadas / que cambian | 543 / **420 (77%)** | 79 / 18 (23%) |
| Δ COGS **neto** (re-presentación total) | **+13.829.655** (utilidad acum. **baja** ~2,8% de $490M) | **−1.398.434** (utilidad **sube**) |
| Δ COGS bruto (Σ absolutos — compensaciones internas) | 82.811.521 | 4.264.341 |
| COGS actual total (referencia) | 2.845.654.714 | 715.772.050 |
| Sin MCH previo (quedan SIN remediar) | 27 líneas (~$55M COGS, IM001×14 y FR001×4 dominan — costo formado por carga inicial/ajustes legacy sin MCH; conservador dejarlas) | 0 |

Por mes (Δ COGS): Costa mar +6,1M / abr −0,3M / **may +16,5M** / jun −3,6M / jul −4,8M · Meta may −0,3M / jun −0,9M / jul −0,1M. Mayo-Costa concentra la re-presentación — consistente con que mayo era el mes de mayor deriva en la validación patrimonial. El neto acumulado es chico (~0,5% del COGS) pero el P&L **mensual** (#50) sí mostrará saltos de hasta $16,5M en un mes → esto es lo que el cliente notará; la comunicación debe ser por mes, no solo el total.

⚠️ **Dirección opuesta al audit**: el audit estimó "COGS Costa inflado $59,5M (utilidad subestimada)" bajo la vara del Modelo P (replay físico). La remediación L da +$13,8M en sentido contrario. No es contradicción: son convenciones distintas de atribución — cifra más de que "corregir" es elegir convención (sección 1).

**Valorización del inventario: $0 de cambio en TODAS las fases** (ver sección 8 ampliada). Contexto de magnitud: inventario liquidado hoy Costa $617,4M / Meta $74,5M. Costa tiene 8 materiales en hueco (`liquidated < 0`) valuados en **−$2,46M** dentro de esa cifra — ese es el orden de magnitud de los ajustes P&L que la Fase 2 hará visibles cuando las compras rellenen. Backlog Costa: 26 ventas registradas-sin-liquidar (328.635 kg, ~$239M al avg actual) cuyo COGS se fijará el día que las liquiden. Meta: 0 huecos, 0 backlog.

## 7. Orden de entrega (commits/QA separados)

1. **PR-1 = Fase 1** (núcleo L) — sin migración. ⚠️ **G5 (QA — restricción DURA, no negociable): PR-1 NO se deploya sin PR-2.** QA/commits separados; deploy SIEMPRE junto — el Modelo L sin manejo de oversell pisa la rama reset con MÁS frecuencia que hoy (sección 10.7).
2. **PR-2 = Fases 2a+2b+4.4** (helper + 2 columnas + MCH nuevo + línea P&L + conciliación) — 1 migración.
3. **PR-3 = Fase 3** (warnings cancel compra) — trivial tras PR-2.
4. **PR-4 = Fase 2c** (ajustes/transformaciones adoptan helper) — 1 migración.
5. ~~**Fase 4** — script de remediación con su propio QA y el go/no-go de Daniel sobre el dry-run.~~ **DESCARTADA 2026-07-10** (ver banner sección 6): las reglas aplican desde el deploy; sin re-presentación histórica (ni Fase 4 ni QW-B #1074/#1295).

Cada PR con QA-gate antes de commit (regla de la sesión).

## 8. Lo que NO cambia (tabla de invariantes para refutar)

| Invariante | Dónde | Por qué se preserva |
|---|---|---|
| Registro de venta resta `stock`/`transit`, no `liquidated`; sin efecto financiero | [sale.py:250-251](../../backend/app/services/sale.py#L250-L251) | El veto de junio: tocar el registro re-crea el denominador negativo. Es el corazón del Modelo L. |
| Compra liquidada pondera contra `liquidated` (rama positiva) | [purchase.py:1231-1238](../../backend/app/services/purchase.py#L1231-L1238) | Idéntico resultado con el helper cuando `liquidated >= 0` (T6). |
| DP: COGS = precio de compra del cruce; sin inventario | [double_entry.py:297](../../backend/app/services/double_entry.py#L297), bloqueos [sale.py:316](../../backend/app/services/sale.py#L316)/[483](../../backend/app/services/sale.py#L483) | Servicio propio; `sale.liquidate` rechaza DPs con 400. |
| `received_quantity`: COGS con cantidad original | Decisión #18 | El fix toca `unit_cost`, no la fórmula. |
| Cancelar compra NO recalcula COGS de ventas ya liquidadas | Decisión #9 | Sus COGS quedaron finalizados en SU liquidación (ahora con más razón). |
| `MaterialCostHistory` reversal usa `previous_cost` | [material_cost_history.py:8](../../backend/app/models/material_cost_history.py#L8) | Liquidar venta no crea MCH (avg no cambia); cancel-venta solo crea MCH si movió el avg. |
| Fórmulas de P&L/reportes sobre `SaleLine.unit_cost` | [reports.py:299](../../backend/app/services/reports.py#L299), #60 | Cambia el VALOR del campo, jamás la fórmula. |
| Balance histórico as-of (#41/#61) | [reports.py:1841-1857](../../backend/app/services/reports.py#L1841-L1857) | El fallback de costo solo lee movimientos de compra/ajuste (gate `unit_cost > 0`); inventario as-of ya cuenta ventas por `liquidated_at` (#61c). |
| Liquidación sin default de fecha (#62), `liquidated_at` canónico (#42) | Liquidate pages / backend | El COGS ahora se alinea a esa MISMA fecha — refuerza #42, no lo toca. |

## 9. Tests obligatorios (guardrails, con números esperados)

**Fase 1** — `tests/test_avg_cost_model_l.py` (nuevo):
- **T1 (oro — conservación):** escenario del ejemplo canónico en AMBOS órdenes de liquidación → en cada orden, `COGS + Σ(liquidated × avg)` == 13.000.000 (tolerancia $1). Fija el modelo.
- **T2 (COGS finaliza al liquidar):** venta registrada con avg 9.000; compra liquidada mueve avg a 8.666,67; liquidar venta → `SaleLine.unit_cost == 8.666,67` y `InventoryMovement.unit_cost` actualizado. Y el simétrico de orden (venta primero → 9.000).
- **T3 (auto_liquidate neutro):** 1-paso → unit_cost == avg del momento, idéntico a hoy.
- **T4 (avg 0 al liquidar):** material nuevo, venta registrada con avg 0, compra liquidada ANTES de liquidar la venta → COGS = costo de la compra (no $0). El caso "utilidad ficticia" muere.
- **T-P&L (paridad):** `pnl.cogs == Σ(unit_cost × qty)` de ventas liquidadas del período — post-cambio (los tests de paridad #49/#50 existentes deben seguir verdes sin tocarlos).

**Fase 2** — unitarios puros del helper + integración:
- **T5 (Ejemplo A):** `incorporate_into_pool(-200, 10000, 1000, 8000) == (8000, +400000)`.
- **T6 (rama positiva idéntica a hoy):** `(200, 9000, 500, 8000) == (8666.67, 0)`; `(0, X, q, c) == (c, 0)`.
- **T7 (Ejemplo B encadenado):** parcial → `(-800, 8000, 300, 9000) == (8000, -300000)`; luego `(-500, 8000, 1000, 9500) == (9500, -750000)`. Conservación del encadenado al centavo.
- **T8 (Ejemplo C — cancel ponderado):** integración: cancelar venta liquidada → avg 8.733,33; delta de valuación de inventario == COGS devuelto (simetría exacta); MCH `sale_cancellation` creado; `check_can_revert` de una compra ANTERIOR ahora bloquea.
- **T9 (round-trip compra con oversell):** liquidar compra que rellena hueco → cancelarla → pool, avg y P&L vuelven exactos al estado pre-compra.
- **T10 (P&L + conciliación):** la línea "Ajuste de costo por sobreventa" aparece con el monto del Ejemplo A; `test_reconciliation_residual_zero` actualizado a 5 líneas y verde.

**Fase 3:**
- **T11:** cancelar compra cuyo material fue vendido después → 200 OK + `warnings[]` con el material y el negativo proyectado; sin warning cuando no proyecta hueco.

**Regresión completa:** suite entera (949 + nuevos); los 6 fallos pre-existentes conocidos (#54) son los únicos tolerados.

## 10. Puntos para mirar con lupa (auto-señalados — QA empezar aquí)

1. **La order-dependence es una FEATURE aceptada, no un bug a "arreglar" en QA.** T1 fija la conservación en ambos órdenes; T2 fija que los COGS difieren entre órdenes. Si a alguien le "cuadra raro", la referencia es la decisión de Daniel (sección 2).
2. **Mutación in-place del `unit_cost` del movimiento de venta** al liquidar: el kardex histórico (running balance) mostrará el costo final también para el período registered. Precedente idéntico en compras desde #42 — pero verificar `MovementHistoryPage` con una venta registrada-luego-liquidada.
3. **Signo del `adjustment`**: `filled × (avg_previo − costo_entrante)`. Positivo = ganancia (COGS fue cargado de más). Verificar contra los Ejemplos A (+400.000) y B (−300.000/−750.000) a mano. Un signo invertido pasa T5 en valor absoluto — por eso T7 verifica el encadenado con cuadre total, que un signo invertido rompe.
4. **`quantize` del adjustment** a 2 decimales por línea: con muchas líneas el redondeo acumulado puede desviar centavos del cuadre exacto — T7 usa tolerancia $1 como los tests de paridad existentes.
5. **MCH `sale_cancellation` bloquea reverts de compras anteriores** (vía `check_can_revert`): endurece — casos que hoy se pueden cancelar dejarán de poderse tras cancelar una venta del mismo material. Es correcto (el revert sería matemáticamente inválido) pero es un cambio de comportamiento visible → mensaje de error ya lo explica vía `source_labels`.
6. **La rama `remaining == 0 → avg queda en avg_previo`** (hueco no cubierto): defendible (el hueco restante sigue "cargado" al avg con que se costeó), pero es una elección — alternativa sería promediar el costo entrante en el hueco. El cuadre del Ejemplo B solo cierra con la elegida.
7. **Ventana de deploy:** entre PR-1 y PR-2 en producción, el Modelo L SIN manejo de oversell puede pisar la rama reset actual con más frecuencia (liquidar ventas primero → hueco → compra resetea y borra valor). **Mitigación: deployar PR-1 y PR-2 juntos** (el orden de commits/QA es separado; el deploy no).
8. **Frecuencia real del oversell bajo L** en Costa: hoy ya hay 18 materiales con `transit < 0` y 328.635 kg vendidos-sin-liquidar — al liquidar ese backlog con el modelo nuevo, los huecos y ajustes van a APARECER en el P&L (línea nueva con montos visibles). No es un bug: es la deuda invisible haciéndose visible. Preparar la explicación al cliente.
9. **Nombres** (`cost_adjustment`, `cancellation_cost_adjustment`, "Ajuste de costo por sobreventa") — propuestas; QA/Daniel pueden mejorar antes de la migración (renombrar después cuesta).

## 11. Preguntas abiertas menores (no bloquean el arranque de PR-1)

- ¿La línea P&L nueva se muestra siempre o solo cuando ≠ 0? (Propuesta: solo ≠ 0.)
- ¿Rotular "utilidad estimada" en el detalle de ventas registered? (Propuesta: sí, texto gris pequeño — barato y evita la pregunta del cliente.)
- ~~Remediación (Fase 4): ¿se corre junto con la de QW-B #1074/#1295 en un solo paquete de re-presentación? (Propuesta: sí.)~~ **RESUELTA 2026-07-10: no se remedia ninguna de las dos** (banner sección 6).
