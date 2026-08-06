# Fix — Un solo reloj por evento (baja y venta de activos fijos)

**Fecha:** 2026-08-04. **Origen:** falla en la suite completa durante el QA de #89 — investigada, resultó no ser del ciclo. **Decisión:** #90 en CLAUDE.md. **Sin migración.**

> **En una línea:** `sell()` y `dispose()` fechaban el `MoneyMovement` con el día colombiano y el `disposed_at` con el instante UTC. Entre las 19:00 y 24:00 hora Colombia esos dos relojes caen en **días distintos**, y el balance a esa fecha mostraba **la plata adentro y el activo todavía en libros**.

---

## 1. Cómo apareció

La suite completa terminó **1491 pasan / 1 falla**: `test_asset_sale.py::test_golden_asof_yesterday_stable`, del ciclo #88 (venta de activos), ya desplegado a producción esa misma tarde. Los mismos tests habían pasado 40 minutos antes.

Lo primero fue descartar que fuera de #89: `git stash` del cambio, correr, **falló igual**. La diferencia entre las dos corridas no era el código — era la hora. La primera fue a las 23:18 UTC; la segunda, pasada la medianoche UTC.

La primera hipótesis fue el flake horario ya documentado (`gotcha_fechas_utc_vs_local`): test con un reloj, validador con otro. **Era incorrecta.** Al alinear el test la falla no desapareció: **se movió de assert**, del activo a la caja. Ese movimiento fue el dato que importaba — no era el test mirando mal, eran las dos mitades del balance mirando relojes distintos.

---

## 2. El defecto

`services/fixed_asset.py`, en `sell()` y en `dispose()`:

```python
col_today     = datetime.now(ZoneInfo("America/Bogota")).date()   # 2026-08-04
movement_date = datetime.combine(col_today, time(12,0), utc)      # → MoneyMovement.date
now           = datetime.now(timezone.utc)                        # 2026-08-05 02:20
...
asset.disposed_at = now                                           # ← frontera, otro reloj
```

Y en `reports.py`, las dos mitades del balance as-of se anclan a campos distintos:

| Lado | Filtro | Con corte `2026-08-04` (`cutoff_dt` = 08-05 00:00) |
|---|---|---|
| Caja | `MoneyMovement.date < cutoff_dt` | MM del 08-04 12:00 → **entra** (+130M) |
| Activo | `disposed_at >= cutoff_dt` (`_fa_existed_at_cutoff`) | 08-05 02:20 → **sigue en libros** |

**El balance no cuadra**, inflado por el valor en libros del activo.

**No es solo nocturno.** `disposed_at` queda grabado en el día siguiente **para siempre**: cualquier consulta futura de ese corte sigue mintiendo. Contradice #61 ("el pasado no se reescribe") y la promesa de #88 de *"exactitud as-of por construcción"* — cuyo golden probaba el borde de **ayer**, no el del **mismo día**, que es donde los relojes se separan.

### El caso más viejo

`dispose()` tiene el patrón idéntico y **no viene de #88: viene de #21**, en producción desde mucho antes.

### Lo que más pesa

`_fa_reval_future_delta` ([reports.py:2624](../../backend/app/services/reports.py#L2624)) **ya documenta este bug palabra por palabra**, encontrado en pruebas de usuario durante #67:

> *"Ancla DIARIA vía la fecha del MoneyMovement de contrapartida... Sin esta simetría, un corte del día anterior a la revalorización mostraría el activo con el valor nuevo pero la caja sin el egreso → el balance no cuadra (bug reportado en pruebas de usuario: corte de ayer 'crecía' por el monto)."*

Se arregló ahí anclando al `MM.date`, y **la lección no se propagó** a baja ni a venta. #88 se escribió después y repitió el patrón.

---

## 3. El arreglo

Helper `business_today()` en `services/fixed_asset.py` — el día de negocio de hoy a mediodía UTC — y los dos sitios estampan `disposed_at = movement_date`. Un solo reloj por evento.

`disposed_at` ya se **usaba** como fecha pura en todos sus consumidores (frontend `toLocaleDateString`, reporte `strftime('%d/%m/%Y')`), así que no hay regresión de display. Al contrario: ese label del balance detallado imprimía **el día siguiente** y ahora imprime el correcto.

**`cancel()` no se tocó** y lleva comentario explicando por qué: los `cancelled` se excluyen del corte **siempre, sin mirar fecha** (735c2c3, "nunca existió"), así que ahí `disposed_at` sí es auditoría pura.

### La otra mitad de la lección

El arreglo rompió el guard LIFO de `annul_sale`, que comparaba `AssetDepreciation.applied_at` (instante real) contra `disposed_at`. Al volverse `disposed_at` día de negocio, un `applied_at` de hace un minuto pasó a ser "posterior" a un mediodía ya pasado → **bloqueaba anulaciones legítimas**.

No es que el arreglo estuviera mal: **ordenar eventos y cortar reportes son preguntas distintas**. El guard pasa a usar `movement.created_at`, un instante de verdad. Cada comparación con su reloj:

- **Frontera de reporte** (corte as-of, filtro de período) → **día de negocio**
- **Orden de eventos** (guards LIFO) y **auditoría** (`created_at`, `annulled_at`) → **instante UTC**

---

## 4. Tests

`tests/test_fixed_asset_business_day.py`, 4 tests. **Verificados contra el bug con `git stash`: 4/4 fallan con el código de producción, 4/4 pasan con el arreglo.**

| Test | Qué clava |
|---|---|
| 🔴 `test_venta_disposed_at_cae_el_mismo_dia_que_su_movimiento` | La invariante que faltaba: `disposed_at.date() == MM.date.date()`, y a mediodía UTC. **Vale a cualquier hora.** |
| 🔴 `test_baja_disposed_at_cae_el_mismo_dia_que_su_depreciacion` | Lo mismo para `dispose()` (#21). |
| `test_venta_al_corte_de_hoy_saca_el_activo_y_mete_la_plata` | El síntoma: al corte del día, caja y activo se mueven **juntos**; el corte de ayer no se entera. |
| `test_baja_al_corte_de_hoy_saca_el_activo` | Ídem para la baja. |

Los dos de invariante son los que valen como guardarraíl permanente: los de balance solo discriminan **dentro** de la franja.

**El golden de #88 (`test_golden_asof_yesterday_stable`) ahora pasa sin haberlo tocado** — el mejor indicio de que el arreglo fue donde debía.

---

## 5. Gates

| Gate | Resultado |
|---|---|
| Tests nuevos | **4/4**, y **4/4 fallan** contra el código sin el arreglo |
| Activos fijos (5 archivos) | **91/91** |
| Suite completa | **1496/1496**, exit 0, **corrida entera dentro de la franja 00–05 UTC** — el horario que la rompía |
| Migración / parity | **No aplica**: cero cambios de esquema |
| Frontend | Sin cambios: `disposed_at` ya se consumía como fecha pura |

---

## 6. Datos en producción — a decidir antes del deploy

El defecto está **en producción**: `dispose()` desde hace mucho, `sell()` desde `deploy-2026-08-04-1737`. Los activos dados de baja o vendidos entre las 19:00 y 24:00 Colombia tienen `disposed_at` un día adelante, y **sus cortes históricos siguen torcidos hasta que se corrijan**.

El arreglo es hacia adelante; los datos existentes no se mueven solos. Antes de decidir el `UPDATE`, **contar** (solo lectura, patrón de la condición 2 del backfill de #89):

```sql
-- (a) VENTAS
SELECT fa.organization_id, COUNT(*)
FROM fixed_assets fa JOIN money_movements mm ON mm.id = fa.sale_movement_id
WHERE fa.disposed_at IS NOT NULL AND fa.disposed_at::date <> mm.date::date
GROUP BY 1;

-- (b) BAJAS (contraparte = depreciación acelerada, período con sufijo "B")
SELECT fa.organization_id, COUNT(*)
FROM fixed_assets fa
JOIN asset_depreciations ad ON ad.fixed_asset_id = fa.id AND ad.is_active
JOIN money_movements mm ON mm.id = ad.money_movement_id
WHERE fa.status = 'disposed' AND fa.sale_movement_id IS NULL
  AND ad.period LIKE '%B' AND fa.disposed_at::date <> mm.date::date
GROUP BY 1;

-- (c) BAJAS SIN MOVIMIENTO (activo ya depreciado del todo): no hay contraparte
--     con qué comparar; solo están torcidas las de la franja
SELECT organization_id, COUNT(*)
FROM fixed_assets
WHERE status = 'disposed' AND sale_movement_id IS NULL AND disposed_at IS NOT NULL
  AND (disposed_at AT TIME ZONE 'UTC')::time < TIME '05:00'
GROUP BY 1;
```

Validado en dev (5434): corre limpio y **discrimina** — hay 3 activos dados de baja como denominador y devuelve 0, o sea que esas 3 bajas ocurrieron fuera de la franja. **En producción hay que correrla igual**: la réplica de dev no tiene lo de esta noche.

Si el conteo da > 0, el `UPDATE` correctivo (alinear `disposed_at` al día de su movimiento) va con backup previo, como cualquier toque a datos productivos.

---

## 7. Alcance del barrido — y lo que apareció

> ⚠️ **Corrección.** La primera versión de este informe afirmaba que el patrón aparecía **dos veces, las dos en `fixed_asset.py`**. Esa conclusión salió de un barrido por grep de un solo ángulo. Un barrido posterior de cuatro ángulos independientes la **refutó**, y la verificación directa del código lo confirma. Lo que sigue reemplaza esa afirmación.

Lo que estaba mal no era el diagnóstico del defecto sino **su alcance**. El repo tiene **dos implementaciones en competencia de "hoy"**:

| Implementación | Reloj | Dónde |
|---|---|---|
| `fixed_asset.business_today()` | Bogotá ✅ | escrita en este fix |
| `financial_obligation._today_noon_utc()` | Bogotá ✅ | #69 |
| `transfer._today_noon()` | **UTC** ❌ | E3.1 |
| `datetime.now(timezone.utc).date()` en MCH de reversión | **UTC** ❌ | 7 sitios |

### 🔴 Lo serio — `MaterialCostHistory.transaction_date` de las reversiones (7 sitios, código compartido)

`purchase.py:846`, `sale.py:594`, `inventory_adjustment.py:457`, `material_transformation.py:394` y `440`, `inbound_order.py:522` y `631` escriben el checkpoint de costo con el **día UTC**. La **misma columna, para el mismo documento**, la escribe la liquidación con la fecha de negocio (`purchase.py:544`).

Y esa columna **es frontera**: `reports.py:2524` filtra `transaction_date <= cutoff_date`, y el comentario de `reports.py:2448-2451` dice explícitamente que los `source_type` de reversión **pasan** el filtro de status — o sea que quedan decididos **únicamente por su fecha**.

Efecto: una cancelación hecha entre las 19:00 y 24:00 Colombia queda fechada mañana; el corte as-of del día real no la ve, valúa el inventario al promedio viejo y **no coincide con el balance vivo** — de forma permanente. Es exactamente lo que advierte el comentario del propio código en `purchase.py:833-838`: *"sin este registro la cadena visible perdería el costo y as-of(hoy) != balance vivo"*. El registro está; lo que falla es qué día dice que es "hoy".

No es un error de diseño: la decisión #75 fija a propósito que el MCH de reversión se fecha **HOY** (backdatearlo re-presentaría cortes, #61). El defecto es sólo **de qué reloj sale ese "hoy"**.

Alcance: **las 7 organizaciones**, no solo SAC.

### `transfer._today_noon()` (E3.1, flag-gated)

Único normalizador a mediodía del repo construido sobre el reloj UTC; en la franja acuña **mañana** como fecha de negocio. Exposición real acotada: el frontend siempre manda fecha, así que muerde por la vía del `annul` (`transfer.py:721`), que no se la pide a nadie.

Detalle que vale la pena: `_validate_not_future`, justo debajo, cita la memoria del gotcha y usa `now(utc).date()` *"para evitar el flake"* — correcto contra un desajuste test-vs-validador, reloj equivocado para una fecha de negocio. La lección se aprendió a medias.

### `StockPage.tsx:148` (frontend)

`useState(new Date().toISOString().split("T")[0])` — el único de los 19 defaults de fecha del frontend que no usa `toLocalDateInput()`. En la franja pre-llena **mañana** en el modal de traslado.

### Revisado y sano

`revalue()` (#67 ya lo ancla al `MM.date`), `cancel()` (los `cancelled` se excluyen del corte por status), `annul_sale`/`annul_reval` (gatean por `is_active`), gastos diferidos (ambos lados UTC, consistente consigo mismo), compras/ventas/DP (`cancelled_at`) y ajustes/transformaciones/entradas (`annulled_at`).

La regla generalizada quedó en **CLAUDE.md**, porque hasta ahora solo vivía en `memory/`, que no está en el repo.
