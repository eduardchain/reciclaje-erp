# Informe de código — El valor total digitado llega exacto a la compra

**Plan:** `docs/planes/plan-redondeo-precio-compras.md` v1.1, con la matriz de plantado §6 commiteada sola en `3f667a7` antes de plantar · **Base:** `4dc2c73` · **Nivel:** lógica
**Fecha:** 2026-11-19 · **QA:** «QA Ecobalance»

Johana, por Daniel, digitó un valor total de **$3.138.450** para 1.503 unidades y la compra nació en **$3.138.444,36**. Daniel eligió la opción A: guardar el precio con 8 decimales en las columnas compartidas.

## 1. Qué cambia

| Pieza | Archivo |
|---|---|
| Migración `b4c6d8e0f2a5`: `purchase_lines.unit_price`, `inventory_movements.unit_cost` e `inbound_line_allocations.unit_price` de `Numeric(15,2)` a `Numeric(21,8)` | `alembic/versions/b4c6d8e0f2a5_precio_compra_ocho_decimales.py` (nuevo) |
| Los tres modelos declaran `Numeric(21,8)` | `app/models/purchase.py`, `inventory_movement.py`, `inbound_order.py` |
| `PRICE_Q = 1e-8`; `REF_Q = 0,01` para el precio de referencia, con 422 si redondea a ≤ 0 (C2 de QA) | `app/services/inbound_order.py` |
| `effUnitPrice` a 8 decimales; `toCents` en todo valor que pasa de la vista previa a un `MoneyInput` editable de 2 decimales (C1 de QA) | `pages/inbound/InboundLiquidatePage.tsx` |
| Opciones de dos BDs para el golden (`--db-before` / `--db-after`) y la guarda de procedencia de escala | `scripts/golden_run.sh` |
| T1–T10 | `tests/test_redondeo_precio_compras.py` (nuevo) |
| Dos tests re-semantizados en `test_sac_entrada_sin_proveedor.py` y uno en `test_avg_cost_model_l.py` | ver §3 |

Sin permisos nuevos. **Dos tablas compartidas** (`purchase_lines`, `inventory_movements`): el golden aplica, con dos BDs, y por decisión del flujo del 19-nov corre en el checkpoint.

**Efecto declarado en filas nuevas de `inventory_movements`:** la venta liquidada (#64) guarda el promedio con 4 decimales en vez de 2. El COGS sale de `sale_lines.unit_cost` (2 decimales, sin cambio), así que no mueve ningún número del P&L. Por eso `test_cogs_uses_avg_at_liquidation_not_registration` pasa a afirmar `mv.unit_cost == avg_at_liquidation` en vez del valor redondeado.

**Desviación del plan, declarada:** en una Entrada la diferencia de la reversa va a `inbound_orders.annul_cost_adjustment`, no a `purchases.cancellation_cost_adjustment` como decía §5 T3b. T3b afirma sobre la columna correcta.

## 2. Gates

Logs en `~/sac-evidencia/2026-11-19/redondeo/`.

**Estáticos:** ruff limpio en app, tests y la migración; tsc 0; eslint 37, igual al techo.

**QA pasada 1:** `redondeo_p1.patch` (sha `859f2f2d…`) y, tras C1/C2, `redondeo_c1.patch` (sha `8d47af80…`).

**Smoke de migración en dev** (`smoke_migracion.log`): dos vueltas `upgrade` → `downgrade` → `upgrade`, con `information_schema` impreso en cada paso (21,8 ↔ 15,2).

**Smoke con POST real** (`smoke_post_johana.log`): :8001 con PID 23806, arrancado 23:31:32, después del último cambio de `app/` (23:23:28).
- Entrada #26 → compra #7.
- Asignación: `unit_price = 2088.12375250`, `total_price = 3138450.00`.
- Compra (GET): `total_amount = 3138450.0`, unitario de la línea `2088.1237525`.
- Saldo del proveedor: delta **−3.138.450,0**, exacto.

**Pantalla, mitad arreglada de P6** (`p6_pantalla.log`): Entrada #27 con un material de más. Al rotar a unitario la casilla muestra 2.088,12 y la vista previa $3.138.444,36; Tab no la mueve; con foco se lee «2088.12».

**Dirigidas por grep** (`dirigidas.log`; el comando está en su primera línea y la lista en `dirigidas_archivos.txt`: 54 archivos, incluidas las tres guardas del árbol). De 23:28:23 a 00:16:20 (0:47:50).
- **1515 passed, EXIT=0**, capturado dentro del bloque. Cero FAILED, ERROR o Traceback en todo el recorrido.
- La predicción de 1515 se escribió antes (`dirigidas_prediccion.txt`). El primer intento fue vacuo: en zsh una variable con varias rutas no se separa en palabras, y el `--collect-only` midió una sola ruta inexistente. Quedó escrito con su corrección, no borrado.
- El árbol quedó quieto. Archivos con mtime posterior al inicio, sin `__pycache__`, en `app/`, `tests/`, `alembic/`, `scripts/` y `frontend/src/`: 0, con control positivo de 179/93/105/23/276. Al terminar, 5433 tenía 0 sesiones. Las ediciones de esa hora fueron en el worktree del orden de materiales, fuera de este árbol.

**Plantado** (`plantado_run.log`, `p7_detalle.log`, `p6_pantalla.log`; matriz commiteada en `3f667a7` antes de plantar). Respaldo por ruta, `.pyc` borrado, `PYTHONDONTWRITEBYTECODE=1`. El sha del árbol plantado fue igual al inicio y al final (`bd277ab7…`, `igual=True`), y `git diff --stat` contra HEAD muestra solo el cambio del redondeo.

| P | Defecto | Predicción | Cayeron | Nota |
|---|---|---|---|---|
| P1 | `PRICE_Q` a 0,01 | al menos T1, T2, T4, T6, T8, `deriva_el_unitario`; no T3a, T3b, T5, T7, T9, T10, `demasiado_bajo` | exactamente esos 6 | diagonal exacta |
| P2 | movimiento a `15,2` | al menos T3a, T3b, T7, `cogs_uses_avg…` | exactamente esos 4 | T3b: ajuste −5,71, contra una cota de 0,08 |
| P3 | línea de compra a `15,2` | al menos T1; «los asserts de totales no la tumban» | T1, T2, T4, T6, T8, `deriva_el_unitario` | **La predicción de los totales falló, en la dirección barata.** El total que asserta T2 sale 987.654.109,2 = cantidad × unitario redondeado a 2: el total de la compra se recalcula desde el unitario ya pasado por la columna, no desde el valor en memoria. Que la liquidación relea la línea de la base es mi hipótesis del mecanismo, no algo medido. T4 cae por el total (línea 284), no por la firma |
| P4 | `effUnitPrice` a 2 decimales (pantalla) | ningún test; se ve en pantalla | — | Pantalla: «$ 2.088,12 c/u → $ 3.138.444,36», el defecto original. Control con el arreglo: «→ $ 3.138.450» |
| P5 | sin cuantizar el ref | T9, T10 | T9 (ajuste en 2088,1238), T10 (200 con ajuste a $0,001) | diagonal |
| P6 | sin `toCents` en la rotación (pantalla) | ningún test; plantado, el Tab mueve el total | — | Pantalla: al rotar queda $3.138.450, con foco «2088.1237525», **al hacer Tab pasa a $3.138.444,36**. Con el arreglo el Tab no lo mueve |
| P7 | sin la guarda ≤ 0 | T10; registrar por dónde revienta | T10 | Revienta en `IncreaseCreate` (`unit_cost` con `gt=0`) construido dentro del servicio: `ValidationError` sin capturar, o sea **500**. La guarda es la que lo vuelve un 422 legible |

Ninguna caída en la dirección peligrosa: todo test que la matriz decía que caía, cayó.

**Parity check** (`parity.log`): **DIFF CERO** fuera del baseline. 67 tablas, 300 índices y 367 constraints.

**Golden:** aplica (dos tablas compartidas). Corre en el checkpoint con dos BDs (`--db-before` sobre una copia sin migrar), como dice el plan §7.

## 3. Observaciones

- **Hallazgo preexistente, no se arregla acá (#101).** Con peso de báscula, la rotación de modo es total → kg → unitario. El precio por kg se redondea a centavos, así que $3.138.450 → 104,41 $/kg → **$3.138.564,60**: se pierden $114,60 si se rota por kg y se vuelve. No es de este cambio (pasa igual en la base). Queda declarado en el plan del reparto por compra §5: en la matriz el modo no rota la cifra.
- **C5 de QA, grep repetido sobre el árbol final** (`c5_grep_final.log`). Los `unit_price` de asignación, que es la columna que se ensancha, entran por `num()` (`InboundLiquidatePage.tsx:213/222`) o se pintan con `fmtMoney` (`InboundDetailPage.tsx:686`). Los `l.unit_price` / `line.unit_price` restantes (`InboundEditPage:595`, `InboundCreatePage:747`, `InboundOrdersPage:131/307`, `InboundDetailPage:146/623`) son de `inbound_order_lines`, que no se ensancha. Ningún valor de 8 decimales se pinta crudo.
- **Archivos nuevos**, que no entran en el `ARBOL_SHA` del log de dirigidas porque ese sha cubre solo lo rastreado por git:
  - `a33821b0…bd92` `alembic/versions/b4c6d8e0f2a5_precio_compra_ocho_decimales.py`
  - `e3c308ef…55f6` `tests/test_redondeo_precio_compras.py`

## 4. Suite completa

Diferida al checkpoint (regla del 19-nov). La predicción del checkpoint sale de `git diff --name-only 85b0d07 -- backend/tests`.

## 5. Condiciones de deploy (abiertas)

1. **Pantalla de Daniel en localhost:** el caso de Johana en la liquidación de una Entrada (vista previa sin ámbar, la compra en $3.138.450 y su PDF), y una compra directa de Costa.
2. **Golden con DOS bases en el checkpoint** (`golden_run.sh --db-before/--db-after`): la predicción de la guarda 4 escrita antes en el log (las tres columnas, 2 contra 8 decimales), y el control positivo de la Entrada (`unit_price` «2088.12» contra «2088.12000000») en el log antes de capturar.
3. **Suite completa en el checkpoint**, con la predicción derivada de `git diff --name-only 85b0d07 -- backend/tests` sobre la base de 2164.
