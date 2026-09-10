# Plan — Ciclo de planta: crisol, plomo puro y la sede que factura (SAC)

**Versión 1.1 — 2026-09-10.** G1–G8 confirmados por Daniel el 2026-09-10 ("ok"). QA (`reciclaje-erp-3b`): **GO condicionado** — F1–F4 aplicadas en esta versión, O1–O4 recogidas; pendiente su re-verificación rápida. Código solo después. Cero líneas de código escritas.

> Regla del ciclo (CLAUDE.md, validación de requerimientos, punto 5): antes de este plan se leyó `inventario-preguntas-cliente.md`. **No hay ninguna pregunta nueva para el cliente**: todo lo que este ciclo necesita ya está respondido (sección 1). Lo que sí hay son **decisiones nuestras de modelo** (sección 7) — se confirman con Daniel, no con Hugo.

---

## 0. Qué se construye, en una pantalla

Hoy el sistema conoce **una** deuda de planta con Circunvalar (`intersede`), un solo plomo, y la venta derivada de una Salida nace en Juan Mina. La demo del 28-ago (Hugo) y los comentarios de Johana del 3-sep dicen otra cosa, y el registro CC-009 lo dejó como *"la mitad del modelo que falta"* (#100 (c)):

| # | Pieza | Hoy | Después de este ciclo |
|---|---|---|---|
| 1 | Dónde está el plomo dentro de planta | Un solo saldo `intersede` | `intersede` con **dos etapas**: *en horno (crudo)* y *en crisol*. La suma ES la deuda (Johana: *"intersede = horno grande + crisol"*) |
| 2 | Pasar crudo al crisol | No existe | Documento **"Traslado a crisoles"** (el 4º ítem que Hugo pidió): mueve kg de la etapa horno a la etapa crisol. **No mueve inventario, ni deuda, ni pesos** |
| 3 | Vender plomo puro | Descarga `intersede` igual que el crudo; sin diferencial | Descarga la etapa **crisol** y causa el **diferencial $300/kg** planta → Circunvalar (tarifa `maquila_crisol`, hoy sin consumidor) |
| 4 | El dross que sale del crisol | No modelado | Documento **"Retorno de dross al horno"**: kg de crisol → horno (la deuda no cambia) y **nueva maquila** $1.500/kg (Johana: *"un mismo kg puede causar maquila más de una vez"*) |
| 5 | Q-30: la venta derivada de una Salida | Nace en Juan Mina → el P&L de JM se lleva ingreso y COGS de un material que no es suyo | Ingreso y COGS se atribuyen a la **sede que factura** (Circunvalar) en el P&L por sede; el inventario sigue saliendo de planta |
| 6 | Pantalla | Cards Horno/Crisol ocultas (#103 D8) | Vuelven, como sub-líneas de Intersede; tab **Crisol** en Salidas de Plomo |

Lo que **no** se construye (sección 8): recetas/colada del horno grande (`FurnaceCharge`, Fase 2), FIFO de intersede, exportación, valoración del plomo en el balance (Q-B), margen propio vs Willard (Q-34), `willard_drosses` por sede.

---

## 1. Fuentes, y lo que NO se vuelve a preguntar

| Hecho que el ciclo necesita | Quién lo dijo | Dónde |
|---|---|---|
| Son dos hornos; puro sale de la deuda del crisol, crudo de la del horno | Hugo 28-ago :331 *"cuando es puro, sales de la deuda que tiene la planta en el horno de crisol y cuando es crudo sale de la deuda de planta del horno de crudo"* | transcripción 28-ago |
| Falta un ítem en Salidas: "salida a crisoles" | Hugo 28-ago :377 *"Te faltaría hacer un ítem ahí que sería salida a crisoles […] te va a alimentar un saldo de inventario de crisoles y cuando se venda el plomo puro ahí resta esa deuda"* | ídem |
| Pasar al crisol no afecta maquila ni saldos, solo "el traslado de un horno a otro" | Hugo 28-ago :381 *"puro no se afecta ninguna maquila, se afecta solamente el diferencial de 300. Pero los saldos no va a afectar sino el del traslado que haces de un horno a otro horno"* | ídem; registro fila 9 |
| Los $300 se causan al VENDER el puro, a favor de planta | Hugo 28-ago :425 *"Cuando yo ya hago una salida desde ese inventario a una venta como plomo puro […] ahí sí resta de esa deuda y […] le abonas un diferencial a la maquila de planta que es de 300"*; dirección planta→CV: spec §5 (*gasto sede origen / ingreso JM*, validado 2-jul) | registro fila 8 |
| Intersede = horno grande + crisol (una sola deuda, dos procesos) | Johana 3-sep 08:49; Hugo 28-ago *"no son dos deudas, la deuda es una sola, dos procesos"* | registro fila 7 |
| El dross del crisol vuelve al horno grande y causa maquila otra vez | Johana 3-sep 08:52; Hugo 28-ago :395 *"una generación de drosses que se la retorno a ella para volverlas a fundir y que ya vuelva y me pague el reproceso"* | registro fila 10, Q-33 🟢 |
| El dross del crisol **no sale físicamente de planta**: el retorno es contable (kg), no un camión a Circunvalar | **Lectura nuestra** de Johana fila 10 (*"al horno grande"*) + Hugo :433 *"se lo retorno a Johana, pero ya no en plomo, sino en dross por volver un material que se vuelve a pasar por horno, para refundir"* | **Se informa** al mostrar la pantalla (F4b de QA). Si el dross viajara a Circunvalar y volviera, sería un traslado y #84 cobraría la maquila una segunda vez, además de la del retorno |
| Tarifas: $1.500 horno · **$300 crisol** · $2.097 maquila Willard · $37 flete | Johana 3-sep 08:52 *"siguen las mismas tarifas"* | registro fila 13 |
| Johana factura todo; planta recibe su valor por kilo (Q-30 = defecto nuestro) | Hugo 24-ago 00:38:22 *"le queda un ingreso a Johana allá por la venta […] y le abona la cantidad de kilogramos por el valor establecido planta"*, *"todo lo factura Johana"* | registro Q-30 🟢, hoja de reunión §E |
| Puro solo se vende; el abono se hace con crudo (crudo puede salir por los 3 tipos) | Hugo 28-ago :369; Johana 9-sep | #103 D2, #104 |
| PLO-LIN es el crudo; PLO-PUR el puro | Johana 9-sep (Q-31) | seeder, #104 |
| La maquila interna se causa al trasladar CV→JM, una vez | Hugo 28-ago; decisión 2-jul | registro fila 1; `internal_maquila_enabled` ON en SAC |

**Se informa, no se pregunta**: el modelo de arriba y las decisiones de la sección 7. Si Hugo o Johana corrigen algo al verlo, se registra en el inventario con fecha.

---

## 2. Modelo — decisiones

### D1. Las etapas viven DENTRO de intersede (`kg_ledger_movements.stage`), no como dos cuentas más

La spec §4.1 tenía cinco cuentas independientes (`intra_horno`, `crisol` con sus CHECKs ya en el enum). Johana la corrigió el 3-sep (*intersede = horno grande + crisol*) y Hugo la explica igual (*una sola deuda, dos procesos*). Dos cuentas independientes obligarían a mantener el invariante `intersede == horno + crisol` con movimientos espejo en tres escritores distintos (traslado, salida, manual) — la clase de invariante que se vigila y un día se rompe en silencio.

**Elegido**: columna `stage` (`horno | crisol`, `String(10)`, nullable) en `kg_ledger_movements`. Regla, en UN punto del servicio de kg (`kg_ledger.add_movement`, nuevo). **F1 de QA: los escritores son CUATRO, no tres** — enumerados con `grep -rn "KgLedgerMovement(" app/` (artefacto, no memoria): `services/kg_ledger.py:364` (manual), `services/transfer.py:529` (`intersede_send`), `services/willard_delivery.py:504` (`willard_delivery`) y `services/inbound_order.py:1347` (`postconsumo_receipt` / `drosses_receipt` sobre las cuentas Willard; `stage` NULL — cambia el camino, no la semántica). Los cuatro pasan por `add_movement`, y una guarda al estilo `TestGuarda` de #106 (T18) exige que `KgLedgerMovement(` en `app/` aparezca SOLO dentro de `services/kg_ledger.py`: un quinto escritor no puede saltarse la regla en silencio. La regla:

- cuenta `intersede` → `stage` **obligatorio** (422 si falta);
- cualquier otra cuenta → `stage` **debe ser NULL** (422 si viene).

Los sub-saldos son `SUM(delta_kg) GROUP BY stage` sobre la cuenta intersede: el invariante es **por construcción** (no hay dos números que puedan divergir). El summary gana `intersede_horno_kg` e `intersede_crisol_kg`; los campos `total_intra_horno_kg` / `total_crisol_kg` y los tipos de cuenta `intra_horno`/`crisol` **se quedan como están** (regla sin-DROP; siguen sumando cuentas de esos tipos, que nadie crea). El statement de intersede muestra la etapa por fila.

⚠️ Lo que D1 NO entrega y hay que decirlo: la razón del cliente para el crisol como cuenta aparte era *"medir la eficiencia por etapa"* (visita 2-jul). La eficiencia del **crisol** sí sale (kg que entran a la etapa vs kg vendidos como puro + kg devueltos como dross → el 87% de Hugo). La del **horno grande** (aportante que entra vs crudo que sale) necesita `FurnaceCharge` con kg de aportante — Fase 2, fuera de este ciclo.

**Backfill**: los movimientos existentes de cuentas intersede son todos crudo (`intersede_send` del traslado y descargas de Salidas) → `stage='horno'`. Dev: 23 filas; prod SAC: las que haya (mismo UPDATE, idempotente).

### D2. Los documentos de crisol reutilizan `crucible_charges` (tabla de E1, vacía en todas las orgs)

La tabla y el modelo `CrucibleCharge` existen desde E1 sin servicio ni endpoint (el registro lo llama *"superficie configurable que no mueve nada: peor que no existir"*). Se les da vida en vez de crear una tabla nueva:

- `event_type`: **`charge`** = *Traslado a crisoles* (Hugo: "salida a crisoles"); **`dross_return`** = *Retorno de dross al horno*. **`discharge`** (cierre de refinación de la spec) queda **reservado y rechazado con 422**: en el modelo de Hugo el crisol no se "cierra", baja al vender puro y al devolver dross.
- Columnas nuevas (solo en `CrucibleCharge`, NO en el mixin — `furnace_charges` no cambia): `charge_number` INTEGER NOT NULL + `UNIQUE(organization_id, charge_number)`, `warehouse_id` FK (planta), `notes`, `maquila_amount` (solo `dross_return`), CHECKs `event_type IN ('charge','dross_return','discharge')` y `status IN ('confirmed','annulled')`. `quantity_kg` = **kg de plomo** (lo que se mueve entre etapas); `material_id` = material físico (crudo en `charge`; el dross en `dross_return`), informativo.
- **No es una Salida** (`WillardDelivery`): no tiene tercero, ni remisión, ni serie, ni liquidación. Nace `confirmed` (un solo paso: no hay revisor en salidas — Hugo 28-ago :149 —, y aquí ni siquiera hay pesos que certificar) y se anula.
- Router `/crucible-charges` gated `require_org_flag("kg_ledger_enabled")` (403 incluso admin), permisos **los mismos del router de Salidas**: `sales.view` (listar/detalle), `sales.create` (crear), `sales.cancel` (anular). Cero permisos nuevos. O2 de QA: `bascula` tiene `sales.create`, así que el pesador de planta podrá registrar traslados a crisoles y retornos de dross — aceptable, es quien está frente al horno; anular queda en `sales.cancel` (liquidador/admin).
- Numeración: `crucible_number` entra a `SEQUENCES` (`crucible_charges.charge_number`, sin partición) y a `RANK` con **14** — **F2 de QA: 13 ya es `willard_delivery`** (`advisory_locks.py:61`), y un empate rompe D4 de #106: `lock_sequences` ordena por rango con sort estable y D4b compara con `<`, así que dos flujos con (willard, crucible) cruzados se esperarían en cruz sin que la suite lo viera. Junto al assert de `:69` se agrega `assert len(set(RANK.values())) == len(RANK)` (rangos únicos, al importar) y T15 lo fija. `dross_return` declara `lock_sequences(db, org, "crucible_number", "movement_number")` porque numera el documento y después el par.

### D3. Efectos de cada documento de crisol

| Documento | kg (cuenta intersede) | Inventario | Pesos | Guards (422) | Avisos (no bloquean, #17/#76) |
|---|---|---|---|---|---|
| `charge` — Traslado a crisoles | `−kg` etapa **horno**, `+kg` etapa **crisol** (dos movimientos, neto 0) | ninguno | ninguno | material con `lead_product='crudo'` (puro o `none` → 422 nombrando el material); sede = planta (`willard_sede_drosses`, calco D8 #100); kg > 0 | "la etapa horno queda en −X kg" |
| `dross_return` — Retorno de dross al horno | `−kg` etapa **crisol**, `+kg` etapa **horno** (neto 0) | ninguno | **par** `internal_maquila_expense` (CV = `willard_sede_facturacion`) / `internal_maquila_income` (planta) por `kg × maquila_intersede_cv_jm`, categoría "Maquila Intersede", `source_type='crucible_charge'`, `tariff_id` snapshot | sede = planta; kg > 0; material activo (sin guard de clasificación: el dross no es plomo entregable) | "la etapa crisol queda en −X kg"; sin tarifa vigente → los kg se mueven igual y se avisa (D4d de #100) |
| anular cualquiera | movimientos kg → `annulled` por `(source_type, source_id)` | — | par → `annulled` (mismo patrón de `_reverse_liquidation`) | ya anulado → 422 | — |

El par del `dross_return` gatea por **`internal_maquila_enabled`** (D6 de la sección 7): es literalmente la maquila interna del horno, cobrada otra vez porque el kg vuelve a fundirse. Flag apagado → kg se mueven, par no se emite (el PAR de tests con-flag/sin-flag es la red, lección #99).

### D4. Venta de plomo puro: descarga la etapa crisol y causa el diferencial

En `willard_delivery.liquidate`, la descarga de `intersede` pasa a ser **por línea, según `lead_product`** (el perfil ya se lee en `_validate_lead_products`; se reutiliza, no se relee):

| Tipo de salida | Línea crudo | Línea puro |
|---|---|---|
| `venta` | `−kg` intersede/**horno** | `−kg` intersede/**crisol** + **par $300/kg** (`maquila_crisol`) |
| `abono_bateria` | `−kg` willard_baterias + `−kg` intersede/**horno** | `−kg` willard_baterias + `−kg` intersede/**crisol** (con el warning existente de #103 D2; sin par: es abono, no venta) |
| `abono_material` | `−kg` willard_drosses (intersede intacto, #100 D1) | ídem (warning existente) |

El par del diferencial: `internal_maquila_income` (warehouse = **sede de la salida**, planta) / `internal_maquila_expense` (warehouse = **sede que factura**, CV), monto `kg puro × maquila_crisol`, **categoría sistema "Crisol Refinación"** (indirecta, get-or-create #78 — la spec §5 la nombra así; separada de "Maquila Intersede" para que el Reporte de Gastos #44 muestre las dos por su nombre), `source_type='willard_delivery'` (ya está en el mapa D10 de `money_movement.annul` → se anula solo desde la Salida). Gated `internal_maquila_enabled`. ⚠️ **F4a de QA — en `willard_delivery.py` conviven DOS regímenes de gate y NO se unifican**: el par de `abono_material` (reparto del ingreso de Willard, CC-009) es por **TIPO** e **ignora** `internal_maquila_enabled`; los dos pares nuevos (el diferencial del crisol aquí y la maquila del dross en D3) son por **FLAG**. El contraste a tres bandas que lo sostiene: T5b + T7b (flag OFF → sin par) + `test_par_emite_en_abono_material` (flag OFF en el fixture → par emitido). Se persiste `willard_deliveries.crucible_amount` (patrón D3 de #101: insumo de un documento financiero; el endpoint arma la respuesta **campo por campo**, trampa #95 — hay test que lo lee por HTTP).

Sin tarifa `maquila_crisol` vigente → los kg se descargan igual y se avisa (D4d). Etapa crisol en negativo (vendió puro sin registrar el traslado a crisoles) → **aviso**, no bloqueo: *"la etapa crisol queda en −X kg: registre el Traslado a crisoles"*.

P&L por sede: el par entra por los tipos existentes (`internal_maquila_*`), así que JM ve el ingreso y CV el gasto **sin tocar `reports.py` para esto**; consolidado neteado por construcción (#84).

### D5. Q-30 — la venta derivada se atribuye a la sede que factura (solo en el P&L por sede)

`willard_deliveries.billing_warehouse_id` (nullable) se **estampa al liquidar** con `willard_sede_facturacion` (snapshot: el setting puede cambiar; la salida ya liquidada no). En `_calculate_profit`, los **tres** bloques que hoy filtran `Sale.warehouse_id == warehouse_id` (ventas :535, COGS :555, comisiones :1056) pasan a una expresión única:

```
sede_de_venta = coalesce(WillardDelivery.billing_warehouse_id, Sale.warehouse_id)
```

vía **outerjoin por `Sale.willard_delivery_id`** (FK muchos-a-uno en `sales`, #100: **no** duplica filas — es la relación inversa de la trampa 1:N de #89). Solo dentro de `if by_sede:`; el consolidado no cambia ni una línea. Para las 6 orgs sin Salidas el coalesce cae siempre en `Sale.warehouse_id` → byte a byte.

**El inventario NO cambia**: la `Sale` sigue naciendo en planta (`warehouse_id=delivery.warehouse_id`), el stock sale de Juan Mina. Solo cambia a qué sede le cuenta el ingreso y su costo en el reporte por sede. Ingreso **y** COGS juntos: el plomo es material de Circunvalar procesado por planta por una maquila (ya causada al trasladar); dejar el COGS en JM pintaría a planta con pérdida por un material que no es suyo (misma familia que D13 de #100).

Los abonos no se tocan: su costo ya fragmenta por la bodega del ajuste (D13) y su factura por la sede que factura (D4b); Q-B/Q-34 decidirán si eso cambia, y no bloquean este ciclo. **Asimetría declarada (O1 de QA, va en #107)**: el costo del abono queda en JM (#100 D13) y el COGS de la venta va a CV (D5) — dos reglas para dos hechos distintos: un abono devuelve plomo de Willard, una venta vende plomo de Circunvalar. **Paridad #49 intacta**: el selector de sede del P&L (`ProfitAndLossPeriodView`) va solo a la query del reporte, nunca a los links de drill-down, y `/reports/sales` no tiene filtro de bodega — Q-30 no puede desalinear un drill-down.

### D6. Inventario físico de planta: transformaciones manuales, sin recetas

Las conversiones físicas (crudo → puro + dross; dross → crudo) son `MaterialTransformation` **manuales** con el módulo existente (#17/#53), en Juan Mina. Este ciclo no las automatiza: no hay colada, ni recetas (T1), ni fundentes. Consecuencia declarada: si Hugo vende PLO-PUR sin haber registrado la transformación, el stock de puro queda negativo — **avisa, no bloquea** (#76), como cualquier venta. Los documentos de crisol son **control de dónde está el plomo** (Hugo, fila 9), y solo eso.

### D7. Pantalla

- **Salidas de Plomo**: 4º tab **Crisol** (`?type=crisol`) que lista los documentos de crisol (badge por evento, kg, fecha, estado) con dos botones: *Traslado a crisoles* y *Retorno de dross*. Formulario mínimo: material (filtrado a `crudo` en `charge`; libre en `dross_return`), kg de plomo, fecha (no futura, `business_today`), notas; **aviso vivo** del sub-saldo resultante (patrón #94). Detalle con anular.
- **Plomo (kg)**: bajo la card Intersede, dos sub-líneas *En horno (crudo)* / *En crisol* (reemplazan las cards ocultas por #103 D8). Statement de intersede: columna Etapa.
- **Detalle de Salida**: línea *Diferencial crisol* cuando `crucible_amount > 0`.
- `KG_SOURCE_TYPE_LABELS` se deriva del grep de `source_type` en los CUATRO escritores (F4c de QA: de un grep, no de memoria). Resultado (y filas en la BD de dev: 28 / 9 / 8 / 8 / 3): `willard_delivery`, `postconsumo_receipt`, `drosses_receipt` (los dos de `KG_SOURCE_BY_WORLD`, **vivos** — son el source de los kg de la Entrada; `inbound_receipt` de `inbound_order.py:1339` es el source del MCH/inventario, no del libro kg), `intersede_send`, `manual_adjustment`; más `migration_initial_load` (spec, sin escritor hoy) y el nuevo `crucible_charge`. Faltan hoy **dos**: `intersede_send` y `willard_delivery` — el statement imprime el código crudo (clase "el formateador que miente", #97). En la misma edición, `_OWNER_MODULE["willard_delivery"]` (`money_movement.py:1071`) pasa de "Salidas a Willard" a **"Salidas de Plomo"** (#104).

### D8. Seeder y settings

- Tarifa `maquila_crisol` **$300** `per_kg_lead` (Johana fila 13) — provisión idempotente (compara contra la vigente, no versiona de nuevo).
- Material **`DROSS-CRI` "DROSS DE CRISOL"** (categoría Drosses, kg, mundo `none`, `compra_regular=False`, `lead_product='none'`): el dross propio de planta no existía como material; sin él, el retorno no tiene qué nombrar y la transformación de D6 tampoco.
- Cero settings nuevos: `willard_sede_drosses` (planta) y `willard_sede_facturacion` (CV) ya existen y son los que este ciclo lee.

---

## 3. Alcance por pieza — tabla de sitios

| Capa | Archivo | Cambio |
|---|---|---|
| Migración | `alembic/versions/e2f3a4b5c6d7_*.py` (id verificado libre) | `kg_ledger_movements.stage` + CHECK + backfill `stage='horno'` en cuentas intersede; `crucible_charges` +4 columnas + UNIQUE + 2 CHECKs; `willard_deliveries.crucible_amount` (Numeric 15,2 default 0) + `billing_warehouse_id` (FK nullable). **Tres tablas exclusivas SAC**, cero filas en las orgs cliente |
| Modelo | `models/kg_ledger.py` | `stage`; comentario de `source_type` gana `crucible_charge` |
| Modelo | `models/plant_process.py` | columnas nuevas en `CrucibleCharge` (no en el mixin); CHECKs |
| Modelo | `models/willard_delivery.py` | `crucible_amount`, `billing_warehouse_id` |
| Servicio | `services/kg_ledger.py` | `add_movement()` (único escritor, regla de `stage`); `intersede_stage_balances()`; summary +2 campos; statement +`stage`; manual: `stage` en schema |
| Servicio | `services/transfer.py` | `intersede_send` pasa `stage='horno'` por `add_movement` |
| Servicio | `services/inbound_order.py` | el escritor de kg de la Entrada (`:1347`) pasa por `add_movement` con `stage` NULL — cambia el camino, no la semántica (F1) |
| Servicio | `services/willard_delivery.py` | `_discharge_kg` por línea y etapa (D4); `_emit_crucible_differential` (par $300); `billing_warehouse_id` al liquidar; reversa incluye el par nuevo (ya cubierto por `source_type/source_id`) |
| Servicio | `services/crucible_charge.py` (nuevo) | create/annul/list/get; `_emit_dross_maquila_pair`; guards D3 |
| Servicio | `services/money_movement.py` | mapa `_OWNER_MODULE` gana `"crucible_charge": ("el documento de crisol", "Salidas de Plomo → Crisol")` |
| Servicio | `services/reports.py` | expresión `sede_de_venta` en los 3 bloques por sede (D5) |
| Helper | `utils/advisory_locks.py` | `crucible_number` en `SEQUENCES` y `RANK=14`; `assert len(set(RANK.values())) == len(RANK)` |
| Schemas | `schemas/kg_ledger.py`, `schemas/willard_delivery.py`, `schemas/crucible_charge.py` (nuevo) | campos de arriba; `event_type: Literal["charge","dross_return"]` (discharge no se acepta) |
| Endpoints | `endpoints/crucible_charges.py` (nuevo) + registro en el router v1 | 5 rutas, flag + permisos de Salidas; respuesta con `warnings` (lección #100 D4d: **desde el primer día por HTTP**) |
| Endpoints | `endpoints/willard_deliveries.py`, `endpoints/kg_ledger.py` | campos nuevos en las respuestas armadas campo por campo |
| Seeder | `scripts/seed_sac_org.py` | tarifa `maquila_crisol`, material `DROSS-CRI` |
| Frontend | `pages/willard/*` (tab Crisol + 2 formularios + detalle), `pages/kg-ledger/KgLedgerPage.tsx`, `KgAccountStatementPage.tsx`, `types/kg-ledger.ts`, `types/crucible-charge.ts` (nuevo), `services/crucibleCharges.ts`, `hooks/useCrucibleCharges.ts`, `utils/queryInvalidation.ts` (+`["kg-ledger"]`, `["crucible-charges"]`, `["reports"]`) | D7 |
| Tests | `tests/test_crucible_charges.py` (nuevo), `tests/test_willard_deliveries.py` (+clase), `tests/test_kg_ledger.py` (+T13, +T18 guarda), `tests/test_advisory_locks.py`, `tests/test_pnl_by_warehouse.py`, `tests/test_inbound_orders.py` (re-semantización de camino, F1) | sección 4 |
| Docs | CLAUDE.md #107, Key Patterns (kg ledger etapas; catálogo de secuencias 13), `Current: N tests`; inventario de preguntas; registro; memoria | — |

**Re-semantización**: la declaración sale de un `grep` sobre los escritores de kg y sobre `/kg-ledger/movements` en `tests/` (lección #103), no de memoria. Candidatos conocidos: `test_inbound_orders.py` y `test_sac_ciclo_d.py` (el escritor de la Entrada cambia de camino, F1 — asserts iguales), `test_kg_ledger.py` (manual sobre cuenta — si es intersede, pasa a exigir `stage`), `test_sac_e1_config.py:515` (crea `KgLedgerMovement` por ORM: si la cuenta es intersede, `stage`), `test_sac_transfer_two_step.py` (asserts sobre `intersede_send` → siguen; ganan `stage='horno'`), `test_kg_ledger.py:471-473` (totales de tipos inertes siguen en 0 — sin cambio).

---

## 4. Matriz defecto × test (compromiso previo — se commitea ANTES de plantar)

Tests nuevos (T) y defectos a plantar (P). Predicción "≥ estos" donde el defecto vive en una vía compartida (regla de #105). O3 de QA: el fixture de `test_willard_deliveries.py` deja `internal_maquila_enabled=False` a propósito (prevención de D11); los tests flag-gated nuevos lo encienden explícito y T5b/T7b son el par OFF.

| # | Test | Qué fija |
|---|---|---|
| T1 | `test_intersede_send_nace_en_etapa_horno` | traslado CV→JM → movimiento con `stage='horno'`; summary `intersede_horno_kg == total_intersede_kg`, crisol 0 |
| T2 | `test_traslado_a_crisoles_mueve_etapas_no_deuda` | `charge` 30 kg: horno −30, crisol +30, `total_intersede_kg` **igual**, cero `InventoryMovement`, cero `MoneyMovement`, `charge_number` = 1 |
| T3 | `test_charge_solo_con_crudo` | material puro → 422 nombrándolo; `none` → 422; `discharge` → 422 |
| T4 | `test_charge_deja_horno_negativo_avisa` | horno 10, charge 30 → 201 + warning en la **respuesta HTTP** |
| T5a/T5b | `test_dross_return_emite_par_con_flag` / `test_dross_return_sin_flag_mueve_kg_sin_par` | crisol −kg, horno +kg, par $1.500×kg (categoría Maquila Intersede, warehouses CV/planta, `transfer_pair_id` cruzado) / sin par, kg iguales |
| T6 | `test_anular_documento_de_crisol` | kg y par → `annulled`; intersede intacto; anular el par desde Tesorería → 422 con "Salidas de Plomo → Crisol" |
| T7a/T7b/T7c | `test_venta_puro_descarga_crisol_y_causa_300` / `test_venta_puro_sin_flag_sin_par` / `test_venta_crudo_descarga_horno_sin_par` | etapa correcta por tipo de plomo; par $300×kg con categoría "Crisol Refinación"; `crucible_amount` **en la respuesta HTTP**; el contraste crudo/puro (lección #94: sin contraste no se distingue "funciona" de "lo apagué") |
| T8 | `test_venta_mixta_cada_linea_a_su_etapa` | 2 líneas (crudo 70, puro 26,1): horno −70, crisol −26,1, par solo por 26,1 |
| T9 | `test_abono_bateria_con_puro_descarga_crisol_sin_par` | warning existente + etapa crisol; `abono_material` no toca etapas |
| T10 | `test_pnl_por_sede_ve_el_diferencial` | JM `internal_maquila_income == 300×kg`, CV `expense`; consolidado neteado; conciliación #59 sin residuo |
| T11a/T11b | `test_q30_venta_derivada_se_atribuye_a_la_sede_que_factura` / `test_venta_normal_sigue_en_su_bodega` | ingreso y COGS en CV, $0 en JM, `cv + jm == consolidado`; una venta no derivada en JM sigue en JM (no-regresión) |
| T12 | `test_anular_venta_puro_devuelve_crisol_y_anula_par` | round-trip |
| T13 | `test_manual_intersede_exige_stage_y_otras_lo_rechazan` | 422 en los dos sentidos |
| T14 | `test_documento_de_crisol_solo_desde_planta` | calco D8 #100 |
| T15 | `test_advisory_locks` (TestLlave/TestMapa/TestOrden) | `crucible_number` en el mapa con rango **14**; rangos únicos (`len(set(RANK.values())) == len(RANK)`, F2); `dross_return` pide (crucible, movement) en orden |
| T16 | `test_statement_intersede_lleva_etapa` | cada fila trae `stage` por API |
| T17 | **smoke con artefacto, NO pytest** (F3 de QA): `crisol_migracion_dev.log` sobre 5434, patrón `locks_migracion_dev.log` | conteos por `(account_type, stage)` antes/después de `alembic upgrade`; una fila NO intersede plantada queda `NULL`; `stage='x'` rechazado por el CHECK; POST contra la BD migrada (gate 2). La suite es dueña de 5433 (se recrea desde los modelos, alembic es no-op ahí) y jamás toca 5434; "ninguna otra cuenta recibe `stage`" queda como pytest vía T13 (el escritor) |
| T18 | `test_ningun_escritor_de_kg_fuera_del_servicio` (calco de `TestGuarda` #106) | `KgLedgerMovement(` en `app/` aparece SOLO en `services/kg_ledger.py` (F1) |

| P | Defecto plantado | Debe caer |
|---|---|---|
| P1 | `intersede_send` no pasa `stage` | T1 (422 del escritor único) ≥ |
| P2 | `charge` mueve `total_intersede` (olvida el `+crisol`) | T2 |
| P3 | venta puro descarga `horno` | T7a, T8 ≥ |
| P4 | par $300 sin gate de flag | T7b |
| P5 | Q-30 sin `coalesce` (filtra solo por `billing`) | T11b |
| P6 | annul del documento no anula el par | T6 |
| P7 | `dross_return` sin par | T5a |
| P8 | respuesta sin `crucible_amount` (modelo+schema sí, endpoint no) | T7a |
| P9 | mapa D10 sin `crucible_charge` | T6 (mensaje) |
| P10 | `charge` acepta puro | T3 |
| P11 | un escritor construye `KgLedgerMovement(` directo (fuera de `add_movement`) | T18 |

---

## 5. Gates

1. Suite dirigida (willard, kg, transfer, pnl_by_warehouse, advisory_locks, crucible) → después **suite completa a archivo** con `EXIT=$?` y chequeo fuerte de mtime (app/, tests/, alembic/, scripts/, frontend/src/).
2. `schema_parity_check.py` → DIFF CERO fuera del baseline (2 tablas tocadas + 1 con 2 columnas); **smoke de migración a archivo** `crisol_migracion_dev.log` sobre 5434 (T17, F3): backfill + CHECK + POST contra la BD **migrada** (`server_default` en el mixin — lección `gate-migracion-vs-modelo`: la BD de test nace de los modelos y no lo ve).
3. **Golden ×3 orgs, aislado (develop-HEAD vs working tree)**: aplica porque se toca `reports.py` (camino compartido) y `money_movement.py`. Esperado **0 diffs** por construcción (cambios dentro de `if by_sede` y en un mensaje de guard); verificado contra `CAPTURES` con comando: ninguna captura pasa `warehouse_id`, ninguna toca kg/willard/crisol.
4. Plantado 11/11 con la matriz commiteada antes, resumen a archivo.
5. ruff limpio; eslint ≤ techo (37); tsc; build.
6. **Pantalla** (condición de commit, no de deploy — clase #97; O4 de QA: se mantiene, más fuerte que en #105): tab Crisol con los dos documentos, sub-líneas de Intersede que suman, venta de puro mostrando el diferencial, P&L por sede de una venta derivada.

## 6. Deploy / runbook (cuando Daniel lo decida; la condición de #100 sigue en pie)

- 1 migración (`e2f3a4b5c6d7`) vía `/deploy`; backfill idempotente.
- Seeder en **provisión** contra prod (sin `--reset`): tarifa `maquila_crisol` + material `DROSS-CRI`.
- Nada que configurar: los settings ya existen. Verificar que `internal_maquila_enabled` sigue ON en SAC (CC-009).
- Comunicar a Hugo/Johana: (a) la venta de puro exige primero el Traslado a crisoles (si no, aviso y crisol en negativo); (b) la transformación física crudo→puro es manual en Transformaciones; (c) **el retorno de dross NO se registra como traslado** (F4b): es un documento de crisol dentro de planta — registrado como traslado JM→CV→JM, #84 cobraría la maquila una segunda vez además de la del retorno.

---

## 7. Gaps — decisiones que necesitan tu confirmación ANTES de código

Ninguna es pregunta para el cliente; todas cambian lo que se construye.

| # | Decisión | Recomendación | Alternativa descartada y por qué |
|---|---|---|---|
| G1 | Etapas dentro de intersede (D1) | **Sí** | Dos cuentas más (spec literal): invariante vigilado en 3 escritores; y contradice lo que Johana y Hugo dicen (una deuda, dos procesos) |
| G2 | Los documentos de crisol como tab de Salidas de Plomo con entidad propia (D2) | **Sí** | Meterlos como 4º tipo de `WillardDelivery`: obligaría a volver nullable tercero y remisión (Hugo: "que no te deje avanzar sin remisión") y a una serie sin sentido |
| G3 | Q-30: ingreso **y** COGS de la venta derivada a Circunvalar en el P&L por sede; inventario sigue en planta (D5) | **Sí** | Solo el ingreso a CV: JM mostraría pérdida por un material que no es suyo. Cambiar `Sale.warehouse_id` a CV: sacaría stock de una bodega donde el plomo no está |
| G4 | El retorno de dross causa la nueva maquila **al registrarlo** (D3) | **Sí** | Causarla al refundir: no hay evento de colada en el sistema (Fase 2) y quedaría en el aire |
| G5 | Las conversiones físicas siguen manuales en Transformaciones (D6) | **Sí, este ciclo** | Recetas/colada: es T1 y depende de la tabla de estándares que Erwin no ha entregado (📎) |
| G6 | Los dos pares nuevos ($300 y dross) gatean por `internal_maquila_enabled` | **Sí** | Flag propio: son maquila interna entre las mismas sedes; un flag más es superficie sin pregunta detrás |
| G7 | Supuesto sin código: el crudo hecho con drosses de Willard vuelve por `abono_material`, no por `venta` | **Aceptar y anotar** | Si se vendiera, descargaría horno igual (aviso si queda negativo). Distinguir el origen del crudo es Q-34 |
| G8 | Fuera de alcance explícito (sección 8) | **Sí** | — |

Si G1 o G3 cambian, el plan cambia de forma (no de tamaño); el resto son ajustes.

## 8. Fuera de alcance (a propósito)

`FurnaceCharge`/colada y eficiencia del horno grande (Fase 2) · recetas del molino y de la fundición (T1, tabla de Erwin) · FIFO de intersede y `intersede_stale_days` · exportación · `willard_drosses` colgando de JM · valoración del plomo en el balance (Q-B, Hugo) · margen del plomo propio vs Willard (Q-34) · unificar `abono_planta_por_kg` y `maquila_intersede_cv_jm` (reunión) · flete/cargos por compra (Johana).

## 9. Inventario de preguntas — filas que pasan de ☑️ a ✅ al cerrar el ciclo

D4 ($300 crisol) · Q-30 · Q-33 · Q-viva.2 (horno/crisol) · "pasar crudo al crisol" · "los $300, cuándo y a quién" · "el dross que sale del crisol". Se actualizan el día del commit, en el mismo commit.

---

## Historial

- **v1.1 (2026-09-10)** — GO condicionado de QA aplicado: **F1** cuatro escritores de kg (no tres; `inbound_order.py:1347` incluido) por `add_movement` + guarda T18 + re-semantización de `test_inbound_orders.py`/`test_sac_ciclo_d.py`; **F2** `crucible_number` con rango 14 (13 es `willard_delivery`) + assert de rangos únicos; **F3** T17 pasa de pytest a smoke con artefacto sobre 5434; **F4** dos regímenes de gate escritos en D4, "el dross no viaja" como lectura nuestra en §1 y como (c) del runbook, mapa `KG_SOURCE_TYPE_LABELS` derivado del grep, `_OWNER_MODULE` → "Salidas de Plomo". O1 (asimetría D13/D5 en #107), O2 (quién crea: `bascula`), O3 (fixture flag OFF), O4 (pantalla = condición de commit) recogidas. Corrección factual a F4c: `postconsumo_receipt`/`drosses_receipt` **están vivos** (`KG_SOURCE_BY_WORLD`, escritor de la Entrada; 9 y 8 filas en dev) y `inbound_receipt` es source del MCH/inventario, no del libro kg — los faltantes del mapa son dos, no tres.
- **v1.0 (2026-09-10)** — plan inicial; G1–G8 confirmados por Daniel.
