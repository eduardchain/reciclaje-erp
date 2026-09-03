# Plan — Salidas de plomo a Willard (W1)

**Fecha:** 2026-08-24 · **Estado:** para QA · **Origen:** reunión Johana + Hugo 24-ago
**Golden:** 🔴 gate duro si se deriva `Sale` (tabla compartida)

---

## 1. El modelo del cliente, y el hecho del que se deduce todo

Hay **dos deudas en plomo con Willard y son de dueños distintos.** Esa sola frase explica por qué
un tipo de entrega mueve dos contadores y otro solo mueve uno.

Hugo, 00:37 (la recapitulación):

> "Willard me entrega baterías a mí en X parte del país. Cuando llegan a Barranquilla, se hace un
> ingreso **para Johana**. Eso genera una deuda en plomo a Willard, pero en nuestro inventario queda
> cargado como unidades de batería."

> "Con materiales es diferente. Willard me los envía **directamente a planta**, por eso no pasan por
> Johana ni por los inventarios de ese balance. Queda un plomo a pagar de **la planta directamente a
> Willard**."

Johana lo había dicho igual (00:14): *"el postconsumo sí tengo la deuda yo… pero el [drosses] es una
deuda de la planta."*

| | Baterías (postconsumo) | Materiales (drosses) |
|---|---|---|
| Willard las manda a | **Circunvalar** | **Planta (Juan Mina), directo** |
| Dueño de la deuda en plomo | **Circunvalar** | **Planta** |
| Cuenta kg existente | `willard_baterias` (por sede) | `willard_drosses` |

Y un tercer contador, que no es con Willard sino **interno**: lo que planta le debe a Circunvalar
(`intersede`), que nace cuando Circunvalar manda aportantes a Juan Mina.

Hugo: *"planta tiene una [deuda] con Circunvalar que la está pagando **o por venta o por entrega de
abono a baterías** — eso es lo único que resta de la deuda de planta."*

### Los tres tipos, ya sin misterio

| Tipo | `willard_baterias` | `willard_drosses` | `intersede` | Por qué |
|---|---|---|---|---|
| **Venta** | — | — | ✅ baja | planta le paga a Circunvalar con plomo |
| **Abono batería** | ✅ baja | — | ✅ baja, **mismo kg** | pago en cadena: planta → Circunvalar → Willard |
| **Abono material** | — | ✅ baja | — | Circunvalar nunca estuvo en esa cadena |

El abono de batería baja dos contadores **por la misma cantidad** porque es un solo pago que salda
dos deudas encadenadas. No es una regla arbitraria: es la consecuencia de que la deuda de
postconsumo sea de Circunvalar y planta la esté pagando por ella.

### La plata

Sobre **toda** entrega se factura a Willard **maquila + flete** y nace una CxC. Hugo, 00:29:

> "Cuando uno entrega el material automáticamente uno factura la maquila y el flete de ese plomo, y
> se crea una cuenta por cobrar a Willard."

Después el ingreso se reparte entre las dos unidades:

> "Una parte de la maquila y **la totalidad de los fletes** son ingresos para Circunvalar." (00:31)
> "Esa factura tiene un valor mayor al que le cobra planta… le abona la cantidad de kilogramos por
> el **valor establecido**." (00:38)

Es **un valor por kg de plomo** (no un porcentaje), igual para baterías y materiales, que cambia
cada año, y **no mueve plata de ninguna cuenta**: es cómo se reparte el ingreso entre sedes.
Estructuralmente idéntico al par `internal_maquila_*` de #84.

---

## 2. Decisiones

**D1 — Documento nuevo `WillardDelivery`, espejo de la Entrada.** Cabecera + líneas, con el mismo
ciclo de estados que la Entrada tipo compra (#93/#95): `draft` (Registrada) → `reviewed` (Revisada,
`purchases.review`) → `liquidated` → `annulled`.

El peso de báscula es **más** crítico acá que en la entrada: es lo que se factura **y** lo que
descarga la deuda. Se reusa la regla de #95: opcional al capturar, obligatorio al revisar.

**D2 — La venta deriva una `Sale`; los abonos no.** Patrón #93 (Entrada → N Purchases): el documento
físico manda, el financiero se deriva. Una venta de plomo a Willard **es** una venta — ingreso, COGS
al promedio móvil, saldo del cliente, estado de cuenta, reportes: todo ya existe y no se reimplementa.
Un abono no es una venta: no hay ingreso por el plomo, se descarga una deuda en kg.

**D3 — Los kg se descargan según la tabla de §1**, con `source_type="willard_delivery"` (ya
reservado en el modelo, [kg_ledger.py:158](../../backend/app/models/kg_ledger.py#L158)) y
`delta_kg` **negativo**. Snapshot de fórmula por línea al liquidar, como el traslado.

**D4 — Maquila y flete a Willard: `service_income_accrual`, tipo nuevo.**
`service_income` exige cuenta ([money_movement.py:319](../../backend/app/services/money_movement.py#L319))
— sirve para plata cobrada, no para una factura. Se necesita *tercero(+), cuenta NULL, ingreso al
P&L*, la forma que #88 estableció con `asset_sale_receivable`. Catálogo **47 → 48**.

El nombre calca el vocabulario que ya existe: `expense_accrual` es a `expense` lo que
`service_income_accrual` es a `service_income` — causado sin mover cuenta.

**🔴 NO entra a `INFLOW_TYPES`.** `service_income` sí está ahí
([reports.py:166](../../backend/app/services/reports.py#L166)) y el cash flow **suma por tipo sin
filtrar cuenta NULL** (la trampa que #86 dejó anotada): agregarlo inflaría el flujo de caja con
plata que nadie recibió. Se cobra después por los flujos normales y ahí sí entra.

**D4b — Cae en la línea `service_income` del P&L, y fragmenta por sede.**

Los números del cliente lo deciden. Circunvalar factura $100 y le abona $40 a planta:

| | Fragmentando | Plegado org-level |
|---|---|---|
| Circunvalar | +100 − 40 = **+60** | −40 = **−40** ← la sede que gana, en rojo |
| Juan Mina | +40 | +40 |
| Consolidado | +100 ✅ | +100 ✅ |

El consolidado cierra en las dos; **por sede la segunda miente.** Y sin fragmentar, D5 reparte algo
invisible: el par movería $40 de un ingreso que por sede vale $0.

**Cómo se fragmenta sin crear línea nueva.** `_not_by_sede` es `[false()]` aplicado **por bloque de
query** ([reports.py:523](../../backend/app/services/reports.py#L523)), no por línea de salida. Se
agrega un **segundo bloque** para `service_income_accrual` **sin** ese filtro, y su total se suma al
**mismo acumulador `service_income`**. Query separada ≠ línea separada.

Consecuencias, todas verificadas:

- **La conciliación #59 no se toca** — sigue en 7 líneas. `test_reconciliation_residual_zero` y el
  golden de `test_asset_sale.py` (que resta las 7 a mano) quedan intactos por construcción.
- **Sin schema nuevo ni cambio en el frontend del P&L.**
- **Semánticamente es correcto**: maquila y flete *son* ingreso por servicios. Una línea propia
  separaría dos cosas que el cliente lee como una.
- **Auto-corrige a futuro**: el tipo fragmenta porque *su writer captura `warehouse_id`*. Un writer
  futuro que no lo capture deja `warehouse_id` NULL → $0 por sede, que es el default seguro.

**🔴 El guardrail que sí muerde no es la conciliación: es el drill-down.**
`test_service_income_parity` ([test_pnl_drilldown_parity.py:393](../../backend/tests/test_pnl_drilldown_parity.py#L393))
exige `sum(listado con movement_type=service_income) == pnl["service_income"]` (tolerancia $1). Con
la línea sumando dos tipos, el listado tiene que consultar **los dos** — el param `movement_type`
acepta CSV desde #49, así que la URL del drill-down pasa a
`service_income,service_income_accrual` y el test se actualiza a la misma CSV. Es el guardrail
haciendo exactamente su trabajo.

**D4c — La sede que factura sale de un setting, no de una deducción.** El par (D5) y el
`warehouse_id` de la factura necesitan saber cuál es Circunvalar. La salida sale de Juan Mina (D8),
pero la otra punta no se puede derivar sin adivinar. Setting nuevo `willard_sede_facturacion`,
**default `None` → no se emite par y la factura nace sin bodega** (= $0 por sede, comportamiento
inerte). Mismo patrón que las sedes de #80.

**D4d — Facturar y descargar deuda son efectos independientes** (punto 4 de QA). Si falta una tarifa,
el kg **se descarga igual** y la factura queda pendiente con warning — nunca al revés. Un efecto
físico no puede quedar colgado de un dato de configuración. Test propio.

**D5 — El reparto es un par `internal_maquila_*`**, la mecánica de #84 sin tocar: `account_id=NULL`,
`third_party_id=NULL`, etiquetado por bodega, enlazado por `transfer_pair_id`, y **solo mueve el P&L
por sede**. Gasto en Circunvalar, ingreso en Juan Mina — la misma dirección que el par del traslado.

**D6 — Las tarifas ya existen y solo les falta valor.** E1 reservó los códigos:

| Código | Unidad | Qué es |
|---|---|---|
| `maquila_willard` | `per_kg_lead` | lo que se le factura a Willard |
| `flete_willard_planta_planta` | `per_kg_lead` | el flete de la entrega |

Falta **uno**: el valor que Circunvalar le abona a planta. No es `maquila_willard` (Hugo: la factura
tiene un valor *mayor*) ni los $1.500 del traslado (respuesta de Hugo en vivo: *"es otro valor"*).
Se agrega `abono_planta_por_kg`, `per_kg_lead`. Append-only (#35) → "cambia anual" sale gratis y el
histórico no se re-escribe.

**Inventario de sitios de la tarifa** (el plan decía "se agrega al Literal" y eran cuatro):

| Sitio | Por qué no se puede saltar |
|---|---|
| `TariffCode` Literal, [service_tariff.py:13](../../backend/app/schemas/service_tariff.py#L13) | sin esto, 422 |
| `CANONICAL_UNIT_BY_CODE`, [:26](../../backend/app/schemas/service_tariff.py#L26) | su propio comentario avisa: un error acá **"factura mal en E4 silenciosamente"** |
| `frontend/src/types/sac-config.ts` | espejo del Literal + mapa de etiquetas + mapa de unidades |
| `scripts/seed_sac_org.py` → `TARIFFS` | el valor placeholder del supuesto A |

**D7 — Todo detrás de `kg_ledger_enabled`** con `require_org_flag` en el router (patrón #75/#98 D6):
403 incluso para admins. El par de maquila además gatea inline con `internal_maquila_enabled` (#84).

**D8 — Guard de bodega: la salida es de Juan Mina.** Hugo, 00:27: *"drosses nunca sale de
Circunvalar, siempre sale de Juan Mina."* Se valida contra la sede de planta, con 400 que explica.
Ver §5: es la única de las tres afirmaciones que se llevó a guard.

**D9 — Anulación por reversa completa**, patrón #93 D20: revierte inventario, kg, la factura, el par
y la `Sale` derivada. No se rebobina nada del costo promedio: el reingreso es ponderado (#66).

**D12 — El abono lleva su costo al P&L por un `decrease` de inventario.**

Decision que aparecio al construir, no estaba en el plan. Un abono no es una
venta: no hay ingreso por el plomo. Pero el inventario que sale SI esta
valorizado (la recepcion Willard entra al costo promedio vigente, #75 D2), asi
que sin un vehiculo el activo baja y **nada lo compensa** — el resultado del mes
mentiria.

El `decrease` es ese vehiculo: entra a `adjustment_net` del P&L, conserva valor
por construccion (#66) y ya esta probado. Es el mismo camino que #84 uso para la
merma de traslados.

Cuesta una tercera columna en `inventory_adjustments` (`willard_delivery_id`,
nullable, no serializada) — mismo precedente exacto que `transfer_id` (#84) e
`inbound_order_id` (#93).

**Aspereza declarada:** el cliente vera esas salidas dentro de "Ajustes de
Inventario" en el P&L, que semanticamente no es lo que son. La alternativa
—una linea propia— exige tocar la conciliacion #59 y el schema, y el valor de
distinguirlas depende de la respuesta de Hugo a Q-B. Si dice que la deuda es un
pasivo, esta linea desaparece de todos modos.

**D10 — El mensaje del guard de maquila deja de mentir.** `INTERNAL_MAQUILA_MOVEMENT_TYPES` bloquea
anular el par desde Tesorería con un texto **hardcodeado**
([money_movement.py:1065](../../backend/app/services/money_movement.py#L1065)):

> *"Anule el traslado desde el módulo de Traslados."*

Con un segundo emisor ese mensaje manda al usuario al módulo equivocado — la clase de defecto
"el formateador que miente" (#97), que ninguna herramienta estática ve. Se deriva del `source_type`
del movimiento (`transfer` → Traslados, `willard_delivery` → Salidas), con test propio: un mensaje
sin nada que lo sostenga se degrada en el primer refactor (#99).

---

## 2b. Inventario de sitios del tipo de movimiento nuevo

#86 y #88 dejaron anotado que las etiquetas viven en "5 mapas duplicados". **Medidos hoy son 6
archivos** los que referencian un tipo de movimiento (tomando `asset_sale_receivable` como sonda):

| Sitio | Qué rompe si falta |
|---|---|
| `VALID_MOVEMENT_TYPES`, [models/money_movement.py:104](../../backend/app/models/money_movement.py#L104) | el movimiento no se puede crear |
| Terna de signos — efecto vivo + `THIRD_PARTY_BALANCE_DIRECTION` + los 2 mapas del statement + `_reverse_effects` | saldo del tercero desalineado entre vivo, reporte y anulación |
| `INFLOW_TYPES` | **NO se agrega** — ver D4 |
| P&L, segundo bloque de query | ver D4b |
| Drill-down `service_income` → CSV | `test_service_income_parity` |
| Frontend ×6: `types/money-movement.ts`, `TreasuryPage`, `MovementDetailPage`, `AccountMovementsPage`, `AccountStatementPage`, `TreasuryDashboardPage` | el movimiento aparece con su código crudo en pantalla |

---

## 2c. Desviación de alcance declarada

Daniel aprobó **"W1 no mueve plata; el cobro va en W3"**. Este plan **factura**: emite la CxC de
maquila y flete con la entrega.

**Por qué se desvía:** Hugo, 00:29 — *"cuando uno entrega el material **automáticamente** uno factura
la maquila y el flete de ese plomo, y se crea una cuenta por cobrar a Willard."* Separarlas habría
inventado un paso que el cliente no tiene.

**Lo que W3 conserva:** el **cobro** (la plata entrando a una cuenta) sigue fuera. Acá nace la CxC,
no el recaudo.

**Lo que cambia el perfil de riesgo:** tipo de movimiento nuevo, línea del P&L tocada, y `Sale`
derivada en tabla compartida → **el golden pasa de conveniente a gate duro.**

---

## 3. Los dos supuestos, y el que NO se supone

**Supuesto A (valores de tarifa) — se encogió a UN número.** Con Q-A resuelta,
`maquila_willard` = **$1.500** deja de ser supuesto. Quedan dos por sembrar:
`flete_willard_planta_planta` y `abono_planta_por_kg` (la porción de los $1.500 que va a planta).
Ambos se ajustan en Config → Tarifas sin tocar código. **No es un supuesto de diseño, es un dato
faltante** — la forma (por kg de plomo, versionada anual) está confirmada por Hugo.

**Supuesto B (dirección del reparto).** Circunvalar paga, Juan Mina recibe. Se deduce de *"todo lo
factura Johana"* + *"ella le abona a planta"*. Si fuera al revés, es cambiar dos constantes.

**✅ Q-A — RESUELTA por Hugo (24-ago). Es UN solo cobro, y ocurre en la ENTREGA.**

> *"No, no señor, es un solo cobro. Cuando llega a Circunvalar la batería se hace el ingreso al
> inventario, también queda una deuda en plomo a Willard, y **cuando yo despacho el plomo de la
> planta se le factura — una parte de los 1500 se le abonan a planta y lo otro le queda a la
> comercializadora**. Pero no es un cobro doble."*

Tres cosas se aclaran de golpe:

1. **Los $1.500 son `maquila_willard`** — lo que se le factura a Willard en la entrega. Deja de ser
   un placeholder: es un dato confirmado.
2. **`abono_planta_por_kg` es una PORCIÓN de esos $1.500**, no otro número independiente. Eso
   reconcilia el *"es otro valor"* que Hugo había dicho antes: es otro valor **porque es una tajada
   de**, no porque sea una tarifa paralela.
3. **🔴 La maquila del traslado (#84) cobra en el momento equivocado.** El traslado CV→Juan Mina
   emite hoy el par a `maquila_intersede_cv_jm` = **$1.500** — el mismo número, las mismas dos sedes,
   la misma dirección. Es el mismo hecho económico contado antes de tiempo: la maquila se gana
   cuando el plomo vuelve a Willard, no cuando el material cruza internamente.

**D11 — El par de la entrega NO se gatea con `internal_maquila_enabled`.**

`internal_maquila_enabled` se lee en **exactamente dos sitios, los dos en `transfer.py`**
([:306](../../backend/app/services/transfer.py#L306) y
[:631](../../backend/app/services/transfer.py#L631)) — verificado en este ciclo. Entonces la
corrección del punto 3 **no cuesta código**: SAC apaga ese flag y el traslado deja de cobrar.

Pero eso solo funciona si el par de la entrega gatea por su cuenta — `willard_sede_facturacion`
(D4c) + tarifa vigente. Si compartiera el flag, apagarlo mataría los dos y quedaría el modo de falla
de #94/#99: *"el guard funciona"* y *"lo apagué para todos"* viéndose idénticos. **Test propio.**

**Lo que NO se re-escribe:** apagar el flag afecta traslados **futuros**. Los pares ya emitidos
quedan como están — el pasado no se re-escribe (#61).

*Runbook:* al deployar, apagar `internal_maquila_enabled` en SAC. Y avisarle a Johana que el traslado
CV→Juan Mina deja de generar el cobro, que ahora nace con la entrega a Willard.

**Q-B — ¿El plomo que sale como abono es pérdida del mes, o pagar una deuda ya registrada?** Hoy la
deuda con Willard vive **solo en kilos**: en el balance no hay pasivo contra el cual descontarla. Y
el inventario Willard entra al costo promedio vigente (#75 D2), así que **sí tiene costo**. Entonces
un abono saca inventario valorizado sin ingreso que lo compense, y el resultado del mes lo absorbe.

*Default propuesto si no responde a tiempo:* dejarlo así — el ingreso del negocio Willard **es** la
maquila y el flete; el plomo nunca fue de SAC para venderlo. Es defendible y no requiere modelo
nuevo. Pero si Hugo dice que es un pasivo, hay que valorizar la deuda en pesos y eso **sí** es otro
ciclo (tabla nueva, línea de balance, y el histórico de kg habría que valorizarlo hacia atrás).

---

## 4. Lo que este plan NO hace

- **No valoriza la deuda en plomo.** Ver Q-B.
- **No toca la maquila del traslado.** Ver Q-A.
- **No modela Bogotá como unidad.** Johana lo describió como *"otra empresa"* con inventario y
  cuentas propias, que entra a Barranquilla como el proveedor "SA Bogotá". Es un frente aparte (S).
- **No toca `willard_baterias` por sede.** Existen dos cuentas (CV y JM); este plan descarga la de la
  sede que corresponda y no unifica nada.

---

## 5. La afirmación que se lleva a guard, y las dos que no

Tres afirmaciones del cliente son candidatas a validación dura. Solo una lo merece:

| Afirmación | ¿Guard? | Por qué |
|---|---|---|
| "Drosses siempre sale de Juan Mina" | ✅ **sí** | Salir de otra sede daría números equivocados en silencio: descargaría `willard_drosses` sin que el material haya estado en planta |
| "Abono de batería siempre con factura" | ❌ no | Es una regularidad operativa, no un invariante; bloquear le quita una salida legítima al usuario (#17/#76) |
| "El valor por kg es igual para materiales y baterías" | ❌ no | Es la configuración de hoy. Una tarifa por tipo sería una generalización sin pedido |

---

## 6. Tests

| Test | Qué fija |
|---|---|
| `test_venta_descarga_solo_intersede` | D3, tipo 1 |
| `test_abono_bateria_descarga_ambos_mismo_kg` | 🔴 la regla que costó media reunión entender |
| `test_abono_material_no_toca_intersede` | D3, tipo 3 — el contraste con el anterior |
| `test_venta_deriva_sale_con_cogs` | D2 |
| `test_abono_no_deriva_sale` | D2, el lado negativo |
| `test_factura_maquila_y_flete_crea_cxc` | D4, los tres tipos |
| `test_par_reparto_no_mueve_cuentas` | D5: cero efecto en caja, efecto en P&L por sede |
| `test_par_reparto_pnl_consolidado_invariante` | D5: el consolidado no se mueve |
| `test_salida_desde_otra_sede_bloquea` | D8 |
| `test_peso_obligatorio_al_revisar` | D1 (regla #95) |
| `test_annul_round_trip` | D9: inventario, kg, factura, par y Sale vuelven al origen |
| `test_sin_flag_403` | D7 |
| `test_guard_maquila_nombra_el_modulo_correcto` | D10, los dos emisores |
| `test_factura_fragmenta_por_sede` | 🔴 D4b: Circunvalar +60 / Juan Mina +40, con los números de QA |
| `test_consolidado_invariante_con_y_sin_sede` | D4b: el consolidado da +100 en las dos lecturas |
| `test_service_income_parity` (actualizado) | 🔴 D4b: el drill-down consulta la CSV de los dos tipos |
| `test_factura_no_entra_al_cash_flow` | D4: causado, cuenta NULL — la trampa de #86 |
| `test_kg_se_descarga_sin_tarifa` | D4d: el efecto físico no depende de la configuración |
| `test_sin_setting_sede_facturacion_no_emite_par` | D4c: default inerte |
| `test_par_entrega_emite_con_flag_maquila_apagado` | 🔴 D11: apagar el traslado no apaga la entrega |
| `test_conciliacion_sigue_en_7_lineas` | D4b: que la decisión de no crear línea quede sostenida |

---

## 7. Gates

- Suite completa
- 🔴 **Golden ×3 orgs — gate duro** si se deriva `Sale` con columna nueva. Con el patrón D1 de #94/#98
  (columna nullable, NULL = comportamiento de hoy) debe dar **0 diffs**.
- Parity check (hay migraciones)
- `ruff` y `eslint`
- **Abrir la pantalla.** Ningún gate ejecuta React (#93/#97): los cuatro modos de falla conocidos
  —hook tras return condicional, `Decimal` serializado como string, formateador que miente, llave de
  cache que miente— solo se ven ahí.

---

## 8. Ronda 1 de QA — cerrado, y una devolución

**GO condicionado**, con 4 items. Los cuatro resueltos:

| Item | Dónde quedó |
|---|---|
| MAYOR 1 — línea del P&L y sede | **D4b**: cae en `service_income` **y fragmenta** |
| MAYOR 2 — consecuencia en la conciliación | **D4b**: sigue en 7 líneas (ver devolución) |
| MENOR — inventario de sitios | **D6** (tarifa, 4 sitios) y **§2b** (tipo, 6 sitios) |
| Alcance "W1 no mueve plata" | **§2c**, declarado |

Y las cuatro preguntas quedaron respondidas por QA: D2 se sostiene con un argumento mejor que el mío
(una línea a precio cero no da margen cero — da **pérdida por el COGS completo**, #60, y contamina
el Reporte de Ventas con volumen fantasma); el default de Q-B es deployable **porque D4 factura con
la entrega**, así que ingreso y costo caen en el mismo mes; el par no tiene acoplamiento fuera del
mensaje; y §5 está bien trazada — de ahí salió **D4d**.

### 🔴 Devolución: MAYOR 2 no es consecuencia de MAYOR 1

QA infirió: *"sacar un tipo de `_not_by_sede` implica separarlo, o sea que le toca línea propia, y
la conciliación pasa de 7 a 8 — schema, bloque, frontend y los dos tests de oro."*

**Query separada ≠ línea separada.** `_not_by_sede` es `[false()]` que se agrega a la lista de
filtros **de cada bloque de query**
([reports.py:523](../../backend/app/services/reports.py#L523)), no a la línea de salida. Un segundo
bloque sin ese filtro, sumando al **mismo acumulador `service_income`**, fragmenta por sede sin
tocar el schema, el frontend ni la conciliación.

O sea que el costo que QA calculó —el precedente de `asset_sale_gain` en #88— **no se paga**.

**Lo que sí hay que pagar, y QA no lo vio (ni yo en la ronda 1):** con la línea sumando dos tipos,
`test_service_income_parity` revienta salvo que el drill-down consulte los dos. La CSV de
`movement_type` existe desde #49, así que es un cambio de una URL y del test — pero es el guardrail
mordiendo, y merecía estar en el plan desde el principio.

**Pregunta para la ronda 2:** ¿hay algo que asuma *"la línea `service_income` == el movement_type
`service_income`"* fuera del test de paridad? Barrí el P&L, el cash flow y los tabs de Tesorería y
no encontré más, pero es justo la clase de acoplamiento implícito que se ve mejor desde afuera.

---

## 9. Ronda 2 de QA — GO condicionado a un item, resuelto

| Item | Dónde quedó |
|---|---|
| MAYOR 2 — la devolución | QA verificó la cadena y la confirmó: *query separada ≠ línea separada* |
| Q1 — acoplamiento de la línea | Cerrada con barrido independiente: el único candidato (Cash Flow) es correcto |
| 🟠 Q2 — el costo del abono por sede | **Condición de salida. Hecha** — bloque propio, ver §7 del informe |
| 🟡 MENOR — #84 dice algo hoy falso | Corregido en el canon, y eran **dos** frases |

**El item que me corrigieron.** Mi §7 proponía dejar el costo org-level porque *"si Q-B resulta ser
pasivo, la pregunta se disuelve sola"*. QA: ese argumento **corta para los dos lados** — si Hugo dice
que no es pasivo (el default que yo mismo llamaba deployable), la asimetría queda permanente. Estaba
apostando el reporte a la respuesta menos probable de las dos.

Y la magnitud no era una imprecisión: **invertía el signo** del P&L de la sede que entrega, con un
hueco que no se veía desde ninguna de las dos. El plomo vale su costo promedio; el reparto es una
tarifa por kg. No son del mismo orden.

Lo que lo cierra es una distinción que yo no había hecho: **todo lo que #84 fragmentó eran pares
completos**. Este era el primer ingreso sin su costo — *"faltan cosas"* vs *"hay una cosa mal"*.

**Precisión de QA que corrige este plan**: si Q-B resulta ser pasivo, el `decrease` **no desaparece**.
El material sale físicamente igual; lo que se mueve es dónde aterriza su valor.
