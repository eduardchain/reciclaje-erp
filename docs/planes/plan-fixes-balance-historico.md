# Plan: Fixes de Balance Histórico (incidente Costa jul-2026)

**Estado: v2.1 IMPLEMENTADO (decisión #61) — pendiente QA de código + commit**
**Fecha: 2026-07-08**
**Origen:** incidente reportado por Reciclajes de la Costa — el Balance General as-of 03/05/2026 cambió entre una foto del 4-jun y una del 6-8-jul. Investigación cerrada con los 3 casos reproducidos al peso (ver memoria `incidente_balance_historico`). Daniel aprobó la dirección de los 4 fixes y el análisis de riesgos (2026-07-08).

---

## 0. Contexto y diagnóstico (resumen)

| Delta en fotos | Causa raíz | Mecanismo |
|---|---|---|
| Activos Fijos −4.072.186 | Camión LGU-673 dado de baja 9-jun | `_get_fixed_assets_as_of` filtra por status ACTUAL → disposed desaparece de cortes pasados |
| Inventario −26.479.187 (exacto) | 3 ventas de abril liquidadas 25-jun | El corte excluye ventas no liquidadas; al liquidarlas, su salida de stock cuenta retroactivamente en fecha documento |
| Anticipos −29.347.890 + CxC −14.709.000 (suma −44.056.890 exacta) | Cienaga y Luminarias Santa Marta desactivados 9-jun | `_get_tp_balances_as_of` + clasificador solo incluyen `is_active=true` → desaparición retroactiva |

Filosofía vigente (commit `735c2c3`, deliberada): **cancelado/anulado = "nunca existió"** (se excluye de cortes sin importar fecha). Este plan NO la cambia para cancelaciones; la corrige donde se aplicó por accidente a eventos de ciclo de vida que NO son errores (baja de activo, desactivación de tercero) y donde el timing usa la fecha equivocada (inventario, estado de cuenta).

**Fuera de alcance** (explícito): bug de costo promedio móvil (memoria `bug_costo_promedio_movil` — capa de ESCRITURA, requiere sesión de diseño propia), `cutoff_date` de terceros migrados (memoria `mejora_cutoff_date_terceros`), backdating explícito de fechas (inherente al sistema hasta cutoff_date).

---

## 1. Fix 1 — Activos dados de baja después del corte

**Problema:** `_get_fixed_assets_as_of` (reports.py:1879-1885) y `_get_fixed_assets_detailed_as_of` filtran `FixedAsset.status.notin_(["disposed","cancelled"])` por estado actual.

**Cambio (solo lectura):** incluir activos disposed cuya baja fue DESPUÉS del corte:

```python
or_(
    FixedAsset.status.notin_(["disposed", "cancelled"]),
    and_(
        FixedAsset.status == "disposed",
        FixedAsset.disposed_at.isnot(None),
        FixedAsset.disposed_at >= cutoff_dt,
    ),
)
```

- `cancelled` sigue excluido siempre (filosofía 735c2c3: error de captura).
- `disposed` con `disposed_at` NULL (edge legacy) → excluido (comportamiento actual, seguro).
- **Boundary intencional `>=`**: con la convención `cutoff_dt = as_of_date + 1 día 00:00 UTC` (snapshot al CIERRE del día), un activo dado de baja EL MISMO día del corte ya no está al cierre (`disposed_at < cutoff_dt` → excluido) y uno dado de baja al día siguiente sí está (`>= cutoff_dt` → incluido). Confirmado como intención (recomendación QA #3).
- **Valor: sin cambios.** `_fa_value_at_cutoff` ya reconstruye correcto: el write-off de la baja es una AssetDepreciation con `period` posterior al corte → fallback `current_value + Σ(deps posteriores)` = valor pre-baja. Verificado con LGU-673: 0 + 4.072.186 = 4.072.186 ✓.
- En `_get_fixed_assets_detailed_as_of`: mismo filtro; el item incluido gana sufijo en el nombre `" (baja DD/MM/YYYY)"` para que el usuario entienda por qué aparece un activo hoy dado de baja.
- La columna es `disposed_at` (timestamptz). NO existe `disposal_date`.

**Tests (4):** activo dado de baja después del corte aparece en balance-sheet y balance-detailed as-of con valor pre-baja; dado de baja ANTES del corte no aparece; cancelado nunca aparece; balance actual (sin as_of) no cambia.

---

## 2. Fix 2 — Terceros y cuentas inactivos en cortes históricos

**Problema:** `_get_tp_balances_as_of` (reports.py:1599-1606) suma `initial_balance` solo de activos, y los consumidores (`tp_objs` en balance_detailed ~:984 y balance_sheet ~:1347) descartan terceros que no estén en la lista de activos. Además hoy hay un **medio-conteo**: el inactivo pierde su initial_balance pero sus MMs/compras/ventas SÍ se acumulan en el dict (fuentes 1-5 no filtran is_active), y luego se descarta entero al clasificar — número frankenstein que por suerte nunca se muestra.

**Hechos verificados que simplifican el fix:**
- La desactivación EXIGE `current_balance == 0` y cero operaciones registradas pendientes (third_party.py:292-334) → en el balance ACTUAL (fast path) incluir o excluir inactivos es equivalente (están en 0). **El fast path no se toca.**
- `_load_tp_behavior_map` ya carga behaviors/categorías de TODOS los terceros (no filtra is_active) → la clasificación del inactivo funciona sin cambios.

**Cambio (solo lectura, solo modo histórico):**
1. `_get_tp_balances_as_of`: quitar el filtro `is_active == True` del loop de `initial_balance` (incluir todos). Esto elimina de paso el medio-conteo.
2. Consumidores en modo histórico: cargar `tp_objs` sin filtro `is_active` (balance_detailed y balance_sheet, SOLO en la rama as_of_date).
3. `_get_account_balances_as_of` (reports.py:1558-1563): mismo cambio para `MoneyAccount` (incluir inactivas; su saldo al corte = initial + movimientos ≤ corte; si es 0 se filtra solo por el `if balance != 0` existente).
4. UI: `BalanceDetailedItem` gana campo opcional `is_inactive: bool = False`; frontend muestra badge gris "Inactivo" junto al nombre en Balance Detallado. Balance General no cambia (agregados). El badge solo puede aparecer en cortes históricos.

**Nota semántica:** un corte POSTERIOR a la desactivación muestra al tercero con su saldo de ese momento (0 si lo zerearon antes, como exige la validación) → se filtra solo por `!= 0`, no aparece. Natural y correcto.

**Tests (5):** tercero con initial_balance + movimientos, desactivado (saldo 0) → corte anterior a la desactivación lo muestra con saldo completo y clasificado por sus behaviors; corte posterior no lo muestra (saldo 0); cuenta inactiva análogo; fast path (sin as_of) idéntico antes/después; `is_inactive` serializado en el response.

---

## 3. Fix 3 — Inventario histórico por fecha de liquidación

**Problema (caso 2):** `_get_inventory_as_of` (reports.py:1701) cuenta movimientos por `im.date` (fecha documento) pero la INCLUSIÓN depende del estado de liquidación ACTUAL (`unit_cost != 0` para compras, `~_active_at_cutoff(Sale.status)` para ventas). Liquidar hoy una operación vieja hace aparecer/desaparecer stock retroactivamente en la fecha del documento. El cliente pide explícitamente que el inventario se afecte en la **fecha de liquidación** — consistente con la decisión #42 (`liquidated_at` = fecha canónica de efecto financiero) y con las fuentes 2/3 de saldos de terceros.

**Diseño elegido — read-time, la capa física intacta:**
El corte histórico es una vista FINANCIERA. `InventoryMovement.date` NO se toca (kardex, tránsito, running balance y vistas físicas siguen por fecha documento).

En `_get_inventory_as_of`, la query de stock se divide por origen del movimiento:

| Movimiento | Condición de inclusión al corte | Fecha efectiva |
|---|---|---|
| `purchase` (ref purchase) | Purchase `status='liquidated'` AND `liquidated_at < cutoff_dt` | `p.liquidated_at` |
| `sale`/`sale_reversal` (ref sale) | Sale `status='liquidated'` AND `liquidated_at < cutoff_dt` | `s.liquidated_at` |
| resto (ajustes, transformaciones, transfers, reversas de canceladas vía ref) | igual que hoy | `im.date` |

Implementación: LEFT JOIN a purchases/sales por (reference_type, reference_id) y condición compuesta (o UNION de 3 ramas — decidir al implementar por legibilidad/planes de ejecución; mismo resultado).

- El proxy `unit_cost != 0` desaparece (lo reemplaza el join al estado real).
- Operaciones canceladas: excluidas SIEMPRE (original y reversa) — igual filosofía; **de paso se arregla un edge preexistente**: hoy una compra liquidada y cancelada después del corte deja stock fantasma (la original cuenta al corte, la reversa queda fechada después). Con el join a `status='liquidated'`, ambas salen.
- Ventas registradas (no liquidadas): excluidas, igual que hoy — pero ya no "entran solas" al liquidarse en fecha vieja: entran en `liquidated_at`.

**Costo — cerrar el segundo canal de retroactividad:**
`purchase.py:468` crea el `MaterialCostHistory` de liquidación con `transaction_date = purchase.date` (fecha documento). Aunque el stock ya no se mueva, liquidar tarde una compra vieja seguiría reescribiendo el COSTO de cortes anteriores (el `DISTINCT ON ... ORDER BY transaction_date DESC, created_at DESC` la elige). Cambio:

1. **Escritura:** usar el PARÁMETRO del método: `transaction_date = (liquidation_date or purchase.date).date()`. ⚠️ **NO escribir `purchase.liquidated_at.date()`**: el MCH se crea en purchase.py:468 y `purchase.liquidated_at` se asigna en :493 — 25 líneas DESPUÉS — leerlo en el loop daría None/valor viejo (bug silencioso, QA obligatoria #1). Alternativa equivalente: mover la asignación de `liquidated_at` arriba del loop de MCH.
2. **Migración de datos one-shot** (Alembic data migration, corre en prod vía `/deploy`):
   ```sql
   UPDATE material_cost_histories mch
   SET transaction_date = (p.liquidated_at AT TIME ZONE 'UTC')::date
   FROM purchases p
   WHERE mch.source_type = 'purchase_liquidation' AND mch.source_id = p.id
     AND p.liquidated_at IS NOT NULL
     AND mch.transaction_date IS DISTINCT FROM (p.liquidated_at AT TIME ZONE 'UTC')::date;
   ```
   Idempotente; reversible re-derivando de `purchase.date` (downgrade documentado). `liquidated_at` es mediodía UTC → `::date` en UTC da la fecha de negocio correcta.
3. MCH de transformaciones/ajustes: sin cambios (no tienen liquidación; su fecha doc ES su fecha de efecto).
4. Los consumidores de `transaction_date` son solo los lookups históricos de costo (fallbacks incluidos) — `check_can_revert`/reversal usan `created_at`/`source_id`, no se afectan.
5. **Precondición pre-deploy (recomendación QA):** verificar en réplica "cero compras/ventas/DPs con `status='liquidated'` AND `liquidated_at IS NULL`" — el fix introduce sensibilidad a NULL (una liquidada sin fecha desaparecería de todos los cortes). NO mitigar con COALESCE solo en inventario (desincronizaría con la ruta de terceros, que ya se comporta así). El backfill #43 lo cubre; el check es el cinturón.

**Efecto neto para el cliente:** con su workflow (liquidar eligiendo el día de la acción), los cortes viejos quedan estables: el inventario "entra/sale" del balance en la fecha de liquidación. Para Meta/Demo (liquidated_at == fecha doc en el 100%) el corte histórico da idéntico.

**Tests (7):** reproducir caso 2 como fixture (venta de abril liquidada en junio → el corte de mayo NO cambia tras liquidar; el stock sale en el corte de junio); compra en tránsito al corte excluida; compra liquidada después del corte excluida / antes incluida; compra cancelada post-corte sin stock fantasma (edge arreglado — documentar como fix de comportamiento); costo del corte estable al liquidar compra vieja (valida transaction_date nuevo); paridad con comportamiento previo cuando `liquidated_at == date` en todo (caso Meta); migración idempotente (segunda corrida = 0 filas).

---

## 4. Fix 4 — Estado de cuenta por fecha de liquidación

**Problema:** el estado de cuenta unificado (money_movements.py, decisión #16) posiciona compras en `p.date`, ventas en `s.date`, DPs en `de.date` (con `created_at` de sort_datetime) y comisiones en la fecha del documento de su venta/compra → discrepa del balance histórico (que usa `liquidated_at`) para el mismo tercero al mismo corte.

**Cambio backend (statement endpoint):** los eventos comerciales se posicionan en `liquidated_at`:

| Evento | transaction_date hoy | transaction_date nuevo | sort_datetime |
|---|---|---|---|
| `purchase_liquidation` | `p.date` | `p.liquidated_at` | `p.liquidated_at` |
| `sale_liquidation` | `s.date` | `s.liquidated_at` | `s.liquidated_at` |
| `double_entry_purchase/sale` | `de.date` | `de.liquidated_at` | `de.liquidated_at` |
| comisiones (venta/compra/DP) | fecha doc | `liquidated_at` de su operación | idem |
| cancelaciones (`*_cancellation`) | `cancelled_at` | sin cambio | sin cambio |
| MoneyMovements | `mm.date` | sin cambio | sin cambio |

- `sort_key` intacto (0=comercial, 1=tesorería, 2=cancelación) → el pago/cobro inmediato (MM con `date = liquidated_at`, decisión #42) queda el mismo día DESPUÉS de su compra/venta ✓ (hoy aparecen separados por semanas).
- **`filter_dt` (recomendación QA #2):** el windowing y el saldo de apertura (#55) filtran por `filter_dt`, que por default sigue a `transaction_date` — al mover `transaction_date` a `liquidated_at` en las ramas comerciales, verificar en implementación que `filter_dt` lo acompaña (no dejar un `filter_dt` explícito viejo apuntando a fecha doc). Cubierto por el test de opening-balance.
- El evento gana campo **`document_date`** (ISO) con la fecha del documento — el response schema del statement lo expone.
- La primera pasada de la decisión #55 (saldo de apertura) no cambia de lógica: al reposicionar eventos, cambia qué cae antes de `date_from`, y el invariante `initial + Σ == current_balance` se preserva por construcción (mismos eventos, mismos montos).

**Cambio frontend (AccountStatementPage / AccountMovementsPage / exports):**
- Fecha principal de la fila = fecha efecto (`transaction_date`). Cuando `document_date` difiere, sub-texto `doc: DD/MM/YY` bajo la fecha (web) — patrón dt/dd existente, sin columna nueva en mobile.
- PDF (decisión #51, ambos formatos): mobile — línea 2 gana el sufijo `· doc DD/MM` cuando difiere; desktop — la columna fecha muestra `DD/MM/YY (doc DD/MM)` con `ellipsis()` si no cabe.
- Excel: columna nueva "Fecha Doc" (vacía cuando coincide).

**Tests (6):** compra liquidada en fecha ≠ doc aparece posicionada en `liquidated_at` con `document_date` correcto; compra registrada antes de la ventana y liquidada adentro → se lista adentro y NO infla el saldo de apertura (extiende test de #55) + inverso (liquidada antes de la ventana → apertura la incluye, no se lista); comisión nunca antes que su venta; eventos de cancelación intactos; **test de oro del paquete**: `saldo corrido del estado de cuenta al corte X == saldo del tercero en balance detallado as-of X` (paridad que hoy es imposible por diseño y este paquete hace válida — guardrail permanente). ⚠️ **Fixture obligatorio no-trivial (QA obligatoria #2):** el tercero del test debe tener **un DP + una comisión de venta + una venta standalone**, todo creado por flujo natural (endpoints, sin accruals hand-dateados), porque los dos code paths representan DPs y comisiones vía tablas distintas con dedup distinto — statement: `sales_with_accrual` SIN filtro de fecha; balance-as-of: `accrual_sale_ids` con `date < cutoff` — y coinciden solo por la invariante "commission_accrual nace atómico con `date = liquidated_at` de su venta" (#23/#42); los DPs se cuentan vía Purchase/Sale (balance) vs DoubleEntry (statement) unidos por el `liquidated_at` compartido que asigna la liquidación del DP. Un fixture trivial (solo MMs) dejaría el guardrail hueco; DPs posicionados en `liquidated_at`.

---

## 5. Orden de implementación y commits

En `develop`, 4 commits secuenciales (cada fix autocontenido y testeable):

1. `fix(reports): activos dados de baja post-corte visibles en balance histórico` (Fix 1)
2. `fix(reports): terceros y cuentas inactivos visibles en cortes históricos` (Fix 2)
3. `fix(inventory,reports): inventario histórico por fecha de liquidación + MCH transaction_date` (Fix 3, incluye migración)
4. `feat(treasury): estado de cuenta posiciona eventos comerciales en fecha de liquidación` (Fix 4)

Gate de QA de Daniel ANTES de cada commit (regla vigente). Migración del Fix 3: aplicar en dev (5434) y test (5433) al implementar; prod SOLO vía `/deploy`.

## 6. Riesgos y mitigaciones (aprobados por Daniel 2026-07-08)

1. **Documentos ya entregados se re-presentan** (estados de cuenta históricos cambian de composición; total invariante) → avisar al cliente antes del deploy.
2. **"¿Dónde está mi compra de abril?"** → mitigado con doble fecha (`document_date` visible en web/PDF/Excel).
3. **Scope completo o incoherencia** → comisiones y DPs se mueven JUNTO con sus operaciones (mismo commit del Fix 4).
4. **Saldo de apertura de ventana se recalcula** → invariante preservado por construcción + tests extendidos de #55.
5. **Backdating explícito sigue reescribiendo cortes** → fuera de alcance (cutoff_date); expectativa a manejar con el cliente.
6. **Calidad de `liquidated_at` en prod** → VERIFICADO en réplica 8-jul: backfill #43 aplicado (existe `backfill_liquidated_at_audit`); Meta/Demo 100% `liquidated_at == date` (cero cambio visible); Costa 311/2010 compras y 195/791 ventas difieren = sus liquidaciones tardías legítimas.

## 7. Criterios de aceptación

1. Reproducción del incidente como fixtures: dar de baja un activo, desactivar un tercero (saldo 0) y liquidar una venta vieja NO cambian un corte histórico anterior a la acción. (Tests fix 1/2/3.)
2. Paridad estado de cuenta ↔ balance detallado as-of para el mismo tercero/corte (test de oro fix 4).
3. Balance actual (sin `as_of_date`) byte-idéntico antes/después de los fixes 1-3.
4. Para orgs con `liquidated_at == date` en todo (Meta), cortes históricos e inventario idénticos antes/después del fix 3.
5. Migración MCH idempotente y reversible.
6. UI: badge "Inactivo", sufijo "(baja ...)", doble fecha en statement — verificados en mobile 390px y desktop (regla responsive).

**Total estimado: ~22 tests nuevos.**

## 8. Actualizaciones de documentación al cerrar

- CLAUDE.md #41: nuevo comportamiento de FA/inactivos/inventario en cortes (la corrección de `_active_at_cutoff` ya se hizo).
- CLAUDE.md #16/#55: statement por `liquidated_at` + `document_date`.
- Nueva decisión #61 con el paquete completo.
- Memoria `incidente_balance_historico`: marcar implementado.

---

## v2.1 — Hallazgo en verificación de claims de QA (2026-07-08 — **Daniel decidió OPCIÓN B**)

Al verificar la justificación de la QA obligatoria #2 contra el código, se encontró que su premisa es **falsa**: el `commission_accrual` NO nace con `date = liquidated_at` — nace con **`date = sale.date`** (fecha documento) en ambos sitios: `sale.py:1215` (`_pay_commissions`, llamado en :406 DESPUÉS de asignar `liquidated_at` en :390) y `double_entry.py:337` (`_create_commission_records`, llamado ANTES del Step 6 que asigna `liquidated_at` en :349-357 — misma trampa de orden que la QA obligatoria #1).

**Consecuencias:** (i) asimetría P&L preexistente — venta liquidada tarde pone su revenue en el mes de liquidación pero su comisión en el mes del documento; (ii) **hueco de retroactividad NO cubierto por los fixes 1-4**: liquidar hoy una venta vieja CON comisión crea un MM retro-fechado a la fecha documento → reescribe el saldo histórico del comisionista (la familia exacta del incidente; en el incidente no se manifestó solo porque las 3 ventas de Aburrà no tenían comisión); (iii) la paridad del test de oro SÍ se sostiene sin tocar esto (ambos lados tratan el accrual como MM por `MM.date`), pero el test "comisión nunca antes que su venta" solo es exigible cerrando el hueco.

**Dimensionamiento (réplica prod 8-jul):** Meta 7 accruals / 0 desalineados; Demo 4 / 0; **Costa 894 / 160 desalineados ($41.672.254), de los cuales 53 cruzan de MES** (solo esos 53 moverían el P&L mensual histórico).

**Opción A:** no tocar accruals (statement-only). Deja el hueco (ii) y la asimetría (i); eliminar el test "comisión nunca antes que su venta" del alcance.
**Opción B (recomendada):** fecha canónica también para accruals — `sale.py:1215` → `date=sale.liquidated_at` (seguro: asignado en :390); DP → pasar `liq_dt` como parámetro a `_create_commission_records` (NO leer `double_entry.liquidated_at` dentro — se asigna después); **migración one-shot** (misma filosofía que la MCH del Fix 3): `UPDATE money_movements SET date = s.liquidated_at FROM sales s WHERE movement_type='commission_accrual' AND sale_id=s.id AND s.liquidated_at IS NOT NULL AND date != s.liquidated_at`. Impacto cliente: 53 comisiones de Costa cambian de mes en P&L histórico (alineándose con su revenue — la intención declarada de la decisión #23: "registra comisiones en P&L al liquidar, base devengado"). `pnl_drilldown_parity` y `pnl_monthly` no se rompen (ambos lados filtran por `MM.date`). Se integraría al commit del Fix 3 (escritura de fechas canónicas + migraciones).

## Historial QA

- v1 (2026-07-08): plan inicial. Pendiente revisión QA.
- v2 (2026-07-08): **QA aprobó** con 2 correcciones obligatorias incorporadas: (1) Fix 3 — NO leer `purchase.liquidated_at` en el loop de MCH (se asigna 25 líneas después, en :493); usar el parámetro `(liquidation_date or purchase.date).date()`. (2) Fix 4 — fixture del test de oro debe incluir DP + comisión + venta standalone por flujo natural (los dedup de accruals difieren entre statement y balance-as-of; fixture trivial = guardrail hueco). Recomendaciones no bloqueantes incorporadas: check pre-deploy de `liquidated_at IS NULL`, verificación de `filter_dt`, boundary `>=` confirmado como intención. QA verificó además: refs cosméticas corregidas (tp_objs en balance_sheet:988 y balance_detailed:1285), y el linchpin del Fix 4 — la liquidación de DP asigna el MISMO `liq_dt` a `purchase.liquidated_at`, `sale.liquidated_at` y `double_entry.liquidated_at` (double_entry.py:349-357), lo que hace posible la paridad statement↔balance.
