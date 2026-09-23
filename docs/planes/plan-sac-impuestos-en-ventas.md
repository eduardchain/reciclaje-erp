# Plan — IVA y retenciones en lo que SAC factura (CC-013 / Q-41)

**Estado:** v1.4, con **GO para construir**. Nada construido todavía.
**v1.1** corrigió un error mío en D4, la única afirmación que el plan hacía como medida.
**v1.2** especifica la regla nueva, que era el centro del ciclo y no estaba escrita, y corrige una conclusión mía que contradecía su propia razón (C10–C13).
**v1.3** incorpora las cuatro condiciones del GO (C14–C17): borra el párrafo que había quedado contradiciendo a D4c, reconoce que sí hay esquema compartido y lo trata como tal, agrega los guards de la categoría de sistema y nombra el loader que cambia. De paso corrige una **quinta** afirmación mía que tampoco era cierta.
**v1.4** suma los tres agregados del GO (A1–A3), declara el `behavior_type` de la categoría y corrige el nombre del código de sistema. Se commitea **antes** de plantar nada.
**Base:** `1327d32` (develop, #111).
**Evidencia:** dos facturas reales que Johana envió el 2026-09-22, extraídas y verificadas al centavo.

---

## 1. Qué lo pide, y qué contestaron las facturas

Johana lo introdujo ella misma el 18-sep, asumiendo que el sistema ya lo hacía: *"Al momento de facturar, pues ahí me permite agregar IVA, retención, todo eso, ¿verdad?"* (L195). No lo hace.

De la reunión quedó **firme** el IVA del 19 % al facturar, y quedaron **sin confirmar** el IVA sobre la venta de plomo y las retenciones, que ella solo nombró. Las dos facturas cierran eso con un documento en vez de un recuerdo:

| | **FE 2118** abono, 11-sep | **FE 2127** venta, 17-sep |
|---|---|---|
| Concepto | MAQUILA 13.905,50 kg × 2.097 + FLETE | PLOMO PURO 16.975,50 kg × 6.246 |
| Base | 29.674.337,00 | 106.028.973,00 |
| IVA | 19 % | 19 % |
| ReteFuente | **4 %** | **2,5 %** |
| ReteIVA | **15 % del IVA** | **15 % del IVA** |
| ReteICA | **12,5 por mil** | **11 por mil** |
| Total a pagar | 32.908.839,74 | 119.335.609,11 |

Las dos cuadran exacto: `base + IVA − las tres retenciones = total a pagar`.

**Los cuatro hallazgos que ninguna transcripción tenía:**

1. **La venta de plomo sí lleva IVA.** Era lo único no confirmado de Q-41(a): en la transcripción esa frase es de Daniel, no de Johana.
2. **Las tarifas dependen del CONCEPTO, no del cliente.** Vender un bien retiene 2,5 %; facturar un servicio, 4 %. El ICA también cambia, 11 contra 12,5 por mil. Es el mismo cliente en las dos facturas.
3. **El IVA se calcula POR LÍNEA y se redondea por línea.** Lo delata un centavo en la FE 2118: sobre el total da `5.638.124,03` y la factura dice `04`; línea por línea da exacto.
4. **SAC factura en Siigo**, con CUFE y resolución DIAN. Eso responde una pregunta que estaba **abierta en nuestros propios requerimientos** (§18: *"¿SAC ya factura electrónica hoy?"*).

De paso, dos tarifas del sistema quedaron verificadas contra un documento: el flete da exactamente $37/kg y la maquila $2.097/kg.

**Y una pregunta se disolvió sin preguntarla.** Q-41(d) preguntaba si el reparto a planta se calcula sobre la base sin IVA. El código reparte `kg × tarifa`, o sea **por kilo**: el IVA no lo toca ni puede tocarlo. Medido en `_bill_and_split`, no deducido.

---

## 2. Alcance, decidido por Daniel el 2026-09-22

- **Solo SAC**, detrás de `kg_ledger_enabled`.
- **Las dos vías**: Salidas de Plomo (venta y abonos) **y** las ventas normales de SAC (aluminio, chatarra), que salen por el módulo compartido.
- **El sistema REGISTRA lo que Siigo emitió**, no emite.
- **Todo opcional** (Daniel, mismo día): *"ojo que esto es opcional, de pronto hacen ventas sin IVA o retenciones"*.

---

## 3. Lo que ya existe y se reutiliza

El modelo de retenciones de COMPRA (#75 / #78 / #79) aporta, tal cual:

- **`retention_configs`**, el catálogo de tarifas, que ya tiene un campo **`concept`** creado justamente porque alguien previó que retefuente varía entre compras y servicios. Las facturas confirman esa previsión.
- **`retention_entities.py`**, dueño único del formato de nombres, con búsqueda sin acentos ni mayúsculas (H4) y get-or-create idempotente.
- **El patrón compensatorio**: el tercero queda acreditado por el neto y cada impuesto acredita a su entidad; el total se conserva al peso.
- **La reversión con `reverted_at`**, auditoría sin borrado físico.
- **Los eventos sintéticos en el estado de cuenta**, que ya existen para `purchase_retention`.

### Lo que NO sirve y hay que corregir

| Qué | Hoy | Debe ser |
|---|---|---|
| ReteIVA: sobre qué base | `rate × subtotal` | **`15 % del IVA`** |
| Las tres tarifas sembradas | 2,5 / 2,0 / 0,7 % | 2,5 y 4 / 15 del IVA / 1,1 y 1,25 % |
| IVA | no existe | por línea |
| Dirección contable | pasivo siempre | **pasivo el IVA, activo la retención que nos practican** |

Las tres tarifas sembradas dicen "sin uso aún" y se ajustan desde la pantalla; el sembrado tolera las que ya existen y no las pisa (medido en `create_retention_configs`). Así que corregirlas no reescribe nada y no es parte de este ciclo.

---

## 4. Decisiones

### D1 — Registra, no emite
Los montos se **capturan** al liquidar, con precálculo editable, que es exactamente el patrón de #79. El `invoice_number`, que ya existe tanto en `Sale` como en `WillardDelivery`, amarra el documento con Siigo. El sistema no genera CUFE ni numeración: hacerlo lo volvería un proveedor tecnológico ante la DIAN, y además convive mal con Siigo emitiendo las mismas facturas.

### D2 — Cada impuesto es opcional e independiente, y "ninguno" es de primera clase
Nada se exige y nada se infiere. Hay ventas sin IVA (exentas, excluidas, cliente no responsable) y clientes que no practican retenciones por no ser agentes retenedores. **El payload ausente deja el camino actual byte a byte** (data-gated, #75 D9), que además es la no-regresión de las otras seis organizaciones: nunca les llega.

⚠️ Corolario de **#98 D10**, que es la lección que más caro salió: el formulario de Ventas es **compartido**. Sin la bandera no puede pedir nada, no puede mandar nada y el hook del catálogo va con `enabled`, para que no dispare ni una sola petición en Costa, Biogreen o Meta.

### D3 — Tabla propia, dueño único por FKs nullables más CHECK
`document_taxes` con `sale_id` y `willard_delivery_id` nullables y un CHECK de exactamente uno. Es el precedente del repo: `attachments` (#102) y las tres columnas que fue ganando `inventory_adjustments` (#84, #93, #100).

**No se tocan `sales`, `sale_lines` ni `money_movements`.**

🔴 **Pero la superficie de esquema compartido NO es cero, y v1.2 decía que sí (C15 de QA).** D4b agrega `system_code` a `third_party_categories`, que es de las **siete** organizaciones. La frase venía de cuando el reconocimiento todavía no estaba decidido, y sobrevivió a la decisión que la volvió falsa.

Se trata como lo que es, con el argumento de **D1 de #94 y #98**: la columna nace **nullable y sin sembrado**, así que en las seis organizaciones que no son SAC queda `NULL` en todas las filas y el predicado de D4b da `False` en todas — la no-regresión es **demostrable por construcción**, no verificable caso por caso. Consecuencias:

- **Gate nuevo: smoke contra la base ya migrada, con un `POST` real a categorías** (§7). Es la lección de **#100**: la base de test nace de los modelos y la de producción de las migraciones, así que un `server_default` que falte en la migración **no lo ve ningún gate** — solo un `POST` de verdad contra la base migrada.
- **El golden no ve la columna**: verificado con comando, `/third-party-categories` no está entre las 14 rutas de `CAPTURES`. Lo que el golden sí ve es la **sección** nueva del balance, que es de lo que habla §7.

### D4 — Entidades separadas, y el clasificador se corrige en los dos sitios

🔴 **La v1.0 afirmaba algo FALSO, y era lo único que afirmaba como medido.** Decía que el balance ubica una entidad de pasivo por el signo de su saldo, y de ahí colgaba todo. Lo desmintió QA y lo verifiqué: en `reports.py:2352`, **veinte líneas antes** del bloque que yo leí, hay una regla que gana:

```python
if tp.is_system_entity and bal > 0:
    return "prepaid_expenses"
```

Las entidades de impuestos nacerían de sistema (`retention_entities.py:87`), así que una retención **a favor** caería en **Gastos Prepagados**, no en el activo por anticipos. Y está en **dos** clasificadores: `_classify_third_party` (vivo, :2352) y `_classify_tp_by_balance` (as-of, :3094).

**Cómo lo cometí**: el grep me llevó a la línea donde estaba lo que buscaba y no leí la función desde arriba. Es #111 en su forma exacta, un día después de escribirla.

**Decisión de Daniel (2026-09-22): se corrige el clasificador**, con una regla **específica de impuestos** en los dos sitios. Razones:

1. **Contablemente es otra cuenta.** En el PUC, la retención que nos practican es anticipo de impuestos (1355) y los gastos prepagados son otra cosa. El balance que Johana le muestra a su contador tiene que decirlo bien. La retención que SAC practica sí es pasivo (2365/2367/2368) y el IVA generado también (2408).
2. **Medido: no mueve nada de las otras empresas.** Hoy solo hay **dos** entidades de sistema con saldo a favor en las tres organizaciones, y las dos son prepagos legítimos: un seguro anual de bodegas y una cartera perdida. Ninguna es de impuestos. Por eso la regla nueva es específica y no invierte la existente.

   **De dónde salió el dato (C13 de QA)**: de la base de **desarrollo, puerto 5434**, que tiene réplica de las organizaciones cliente con movimientos hasta el **17 de septiembre de 2026**. **Producción no se consultó** — está prohibido y no se hizo. Si el dato se quiere fresco al día del deploy, se vuelve a medir contra una réplica nueva, no contra producción.
3. El marcador de sistema las **oculta de los listados** (`third_party.py:148`) y **bloquea desactivarlas** (`:293`). La alternativa (quitarles ese marcador) las dejaba sueltas en Maestros.

   🔴 **Corrección de una quinta afirmación mía.** v1.2 decía aquí que el marcador protege también *"de ser editadas"*, y al medirlo para C16 resultó **falso**: `ThirdPartyService.update` no mira `is_system_entity` en ninguna línea. Protege de dos cosas, no de tres. Es lo que hace necesario a **D4d**: si editar fuera imposible, el guard de asignación sobraría.

| Concepto | Qué es | Entidad | Saldo | Sección |
|---|---|---|---|---|
| IVA generado | SAC le debe a la DIAN | `[Impuestos] IVA por Pagar` | en contra | pasivo, sin tocar nada |
| Retención practicada a SAC | anticipo de impuesto | `[Impuestos] ReteFuente a Favor`, etc. | a favor | **activo, por la regla nueva** |

⚠️ **Consecuencia que cambia un gate**: `reports.py` **se toca**, así que *"superficie compartida cero"* deja de ser cierto y el golden pasa de gate por forma a **gate por código**, con prueba de vida y control positivo (ver §7).

⚠️ Las entidades de venta son **distintas** de las de compra: la retefuente que SAC le practica a un chatarrero es pasivo y la que Willard le practica a SAC es activo. Compartir entidad las netearía, y QA confirmó que netearlas es un error contable real, no una preferencia.

⚠️ **El panel de Dinero Inactivo (#68) excluye `prepaid_expenses` a propósito**, y corregir el clasificador saca a las retenciones de esa exclusión. Eso hay que atajarlo: **D4c**.

### D4b — Cómo se reconoce una entidad de impuestos, y a dónde va (C10 de QA)

La v1.1 decidía *corregir el clasificador* sin decir **cómo reconoce** la entidad ni **a qué sección** la manda. Las dos cosas deciden el ciclo.

**Reconocimiento: por código, nunca por texto.** `third_party_categories` gana `system_code` (nullable), y las entidades de impuestos se asignan a la categoría con `system_code='taxes'`. Es el patrón de **#58**, que eligió `system_code` en vez del nombre justamente porque un nombre es renombrable; y el repo ya tiene un caso que clasifica por texto —`"obligaci"` en el nombre de la categoría— que no conviene imitar.

⚠️ **El código se llama `taxes`, no `tax_advance`** (corrección de nomenclatura de v1.4, no de diseño). Una **sola** categoría alberga las dos clases de entidad, la que debe y la que tiene a favor, y el **signo** decide la sección: el `bal > 0` ya está en el contexto de los tres consumidores, así que el IVA por pagar nunca llega a la rama de activos. Un código llamado `tax_advance` sobre una categoría que también contiene el IVA por pagar **miente al que lo lea después**. Regla: *el código nombra lo que la categoría ES, no el efecto que dispara.* La sección del balance sí se llama `tax_advances`, porque eso es lo que el contador lee ahí.

🔴 **A1 — la unicidad no se documenta, se hace imposible.** #58 dejó escrito que dos filas con el mismo código revientan con `MultipleResultsFound` y ahí quedó, como advertencia. Acá va un **índice único parcial** `(organization_id, system_code) WHERE system_code IS NOT NULL`: en las seis organizaciones que no son SAC todas las filas son `NULL`, así que el índice no las toca, y la segunda fila con el mismo código **no se puede insertar**. El get-or-create busca **por código**, nunca por nombre. Fila P propia.

**`behavior_type = 'liability'`** (QA pidió declararlo), y esa elección paga dos cosas gratis, verificadas en `ThirdPartyFormDialog.tsx`:

- **Ya está oculta del multi-select**: `HIDDEN_BEHAVIORS = ["liability", "provision"]` (:90) — no hay que agregar lógica nueva al diálogo, y el tercero aparece con el copy *"se administra desde su módulo correspondiente"* (:117/:123). Sin esto, la pantalla ofrecería una categoría que el servidor rechaza, que es la clase de defecto de #97 y #104.
- **Es el precedente de #75**, donde la categoría "Retenciones" de compras ya nace `liability`.

⚠️ **Consecuencia declarada, no resuelta acá**: una entidad a favor es `liability` + sistema, así que aparece en el selector de **Pago de pasivo** (`useLiabilities(includeSystem=true)`, W5 de #78). Pagarle a un anticipo de impuestos no tiene sentido y aumentaría el saldo a favor. **No bloquea** porque el nombre de la entidad dice "a Favor" y porque filtrarlo es el mismo predicado en una línea; se decide con Daniel al ver la pantalla.

🔴 **Un solo predicado, no tres expresiones escritas a mano.** Helper `_is_tax_entity(tp, category_codes)` usado en los **tres** consumidores: `_classify_third_party` (:2352), `_classify_tp_by_balance` (:3094) y el panel de Dinero Inactivo (:416). Si fueran tres copias, P5b solo atraparía que **falte** una, no que **diverjan**, que es el modo de falla más difícil de ver.

**Sección: `tax_advances`, nueva.** Reusar `liability_advances` haría que el balance diga *"anticipos de pasivos"*, que no es lo que el contador espera leer.

**Qué loader cambia, y por qué el helper único no alcanza solo (C17 de QA).** Medido: `_load_tp_behavior_map` (`reports.py:222`) devuelve **nombres** de categoría, no códigos — `(tp_behaviors, tp_cat_names, tp_cat_by_behavior)` —, así que un helper único alimentado con lo que hay hoy no puede reconocer nada por código.

El loader gana un **cuarto** elemento, `tp_cat_codes: dict[UUID, set[str]]`, del mismo `select` (una columna más, cero consultas nuevas). Los dos clasificadores y el panel lo reciben como parámetro nuevo.

🟢 **El desempaquetado hace ruido si alguien olvida un sitio.** Los **seis** llamadores del loader desempaquetan la tupla (`:410`, `:1726`, `:1845`, `:2072`, `:2182`, `:4195`); un cuarto elemento los revienta a todos con `ValueError` hasta que se actualicen. No se puede dejar uno a medias en silencio, que es justo el modo de falla que P5b persigue.

**Y el as-of usa el mismo loader**: `_classify_tp_by_balance` se llama desde `:1873` y `:2271`, los dos dentro de funciones que ya cargaron el mapa con ese mismo `_load_tp_behavior_map`. O sea que los dos caminos reciben el mismo dato por construcción, que es lo que C17 pedía asegurar.

**La superficie real, enumerada por grep y no de memoria** (es lo que QA pidió medir):

| Dónde | Cuánto |
|---|---|
| `services/reports.py` y `schemas/reports.py` | 16 apariciones de `prepaid_expenses`: buckets del General vivo y as-of, los dos del Detallado, los totales de activos y el schema |
| Frontend | 5 archivos: `types/reports.ts`, `BalanceSheetPage`, `BalanceDetailedPage`, `excelExport`, `pdfExport` |

⚠️ **Esto corrige §7**: una sección nueva es una **clave aditiva** en `BalanceSheetAssets`, así que las tres organizaciones cliente la reciben en `0.0`. El golden ya **no** espera *"0 diffs y 0 aditivas"*.

### D4c — La entidad de impuestos sigue FUERA del panel de cobro (C11 de QA)

🔴 **La v1.1 concluía al revés de su propia razón.** Escribí *"a la DIAN no se le persigue un cobro, la retención se descuenta en la declaración"* y de ahí saqué que **entrara** al panel de Dinero Inactivo. Es exactamente lo contrario: esa razón es el argumento para que **siga excluida**.

Verificado: el panel usa el **mismo** clasificador (`reports.py:416`) y su docstring dice que excluye los prepagados *"entidades de sistema, no perseguibles"*. Al mover la retención a una sección activa, aparecería como saldo a cobrar con su semáforo de días, del tipo *"ReteFuente a Favor — 60 días"*, invitando a llamar a la DIAN.

Por eso la exclusión del panel se **amplía** con el mismo predicado de D4b, y hay fila P propia con su test: *la entidad de impuestos aparece en el panel*.

### D4d — La categoría de impuestos es de sistema, y se defiende (C16 de QA)

#58 le puso **cuatro** guards a la unidad de negocio de sistema. Esta categoría necesita los suyos, porque hoy **cualquier usuario asigna categorías** desde el formulario de terceros (#37, multi-select). Sin guard, ponerle a un proveedor normal la categoría con `system_code='taxes'` manda su saldo a favor a la sección de impuestos **y lo saca del panel de cobro**, las dos cosas en silencio.

**Lo medido primero, porque cambia el diseño del guard:**

| Qué | Estado hoy | Hace falta guard |
|---|---|---|
| Asignar categorías a un tercero | `_sync_category_assignments` (`third_party.py:57`) es el **único** punto: create (`:242`) y update (`:278`) pasan los dos por ahí | **sí**, y uno solo cubre las dos vías |
| Cambiar el `behavior_type` de una categoría | **ya es imposible**: `ThirdPartyCategoryUpdate` no expone el campo | no — se declara, no se agrega |
| Desactivar la categoría por `PATCH` | `is_active` **sí** se puede cambiar | **sí** |
| Eliminar la categoría | `delete` bloquea con terceros asignados, pero **no antes** de la primera venta con retención | **sí** |
| Renombrarla | libre | **no**, y es deliberado: el reconocimiento es por código (#58) |
| Escribir `system_code` a mano | no se expone en los schemas de create ni update | no — pero **sí test** (A2) |
| Reparentar la categoría (`parent_id`) | `ThirdPartyCategoryUpdate` **sí** lo expone | **sí** (A3) |

**A2 — la protección por ausencia se fija con un test.** Verificado: `ThirdPartyCategoryCreate` no declara `model_config` y `Update` solo trae `from_attributes`, o sea que **ninguno** tiene `extra="forbid"` y Pydantic **ignora el campo en silencio**. Eso hoy alcanza, pero es una propiedad que nadie enunció y que se pierde el día que alguien agregue `system_code` al schema. El test manda `system_code='taxes'` por `POST` y por `PATCH` y exige que la fila quede en `NULL`: así la ausencia deja de ser un accidente y pasa a ser un invariante que revienta si cambia.

**A3 — reparentar se bloquea junto con desactivar.** No rompe la clasificación, que va por código, pero **cambia el `display_name`** de la categoría en el balance y en el estado de cuenta, y una categoría de sistema no cuelga de otra: es raíz por definición. Renombrar **sí** se permite, que es exactamente la asimetría de #58 y la razón de ser del código.

🔴 **El guard tiene que ser SIMÉTRICO, y eso lo decide un detalle de implementación.** `_sync_category_assignments` **borra todas las asignaciones y las recrea**. Entonces hay dos formas de romper la clasificación y las dos pasan por la misma línea:

- **agregar** la categoría a un tercero normal — su saldo a favor migra a impuestos;
- **quitársela** a una entidad de impuestos — sus retenciones vuelven a caer en Gastos Prepagados y el balance le miente al contador.

Se rechazan las dos, con `422` que explica. Nada de conservar la asignación por lo bajo: arreglar en silencio deja al usuario creyendo que guardó algo que no guardó, y este repo ya pagó esa lección varias veces.

🟢 **El flujo legítimo no pasa por el guard, y eso es estructura y no suerte:** `retention_entities.py:109` crea la asignación **directo**, sin `_sync_category_assignments`. Mismo reparto que #58, donde la unidad de sistema se siembra en `create_organization` y los guards viven en los puntos de entrada del usuario.

⚠️ **El test tiene que probar las dos mitades**, y esa es la parte que QA subrayó: que el usuario **no** pueda asignarla **y** que la entidad nacida del flujo de impuestos **sí** la tenga. Sin la segunda mitad, un guard que rechace absolutamente todo pasa en verde — es el control positivo de #111 aplicado acá.

🟢 **Y el guard no estorba la edición normal, medido en el diálogo**: `ThirdPartyFormDialog` inicializa `categoryIds` con **todas** las categorías del tercero, incluidas las ocultas (:59), y las devuelve enteras al guardar (:76). O sea que editarle el teléfono a una entidad de impuestos manda la categoría de vuelta sin quitarla → el delta es vacío → pasa. **La mitad positiva del test usa ese mismo payload**, el que arma el diálogo, y no uno inventado: un test que mande `category_ids` sin la categoría probaría el rechazo, no la convivencia.

🟢 **Dato que ayuda a la robustez**: el loader **no filtra categorías por `is_active`** (verificado con QA), así que una categoría de impuestos desactivada a mano seguiría clasificando bien. El guard de `is_active` se mantiene igual, pero por claridad de la configuración, no porque el balance dependa de él.

### D5 — La base se declara, no se asume
`base_amount` se persiste siempre, y **cada tipo dice sobre qué se aplica**: retefuente e ICA sobre el subtotal, reteIVA sobre el IVA. El precálculo del frontend usa la base correcta.

Sin esto, la reteIVA se podría configurar como "2,85 % del subtotal" y daría el número correcto **solo mientras el IVA sea 19 %**. El día que cambie, el número queda mal en silencio. Un valor que parece configuración y es en realidad otra fórmula.

**C3 — qué pasa con COMPRAS.** El precálculo `rate × subtotal` vive en dos pantallas compartidas, `PurchaseLiquidatePage` e `InboundLiquidatePage` (medido por grep, no de memoria). El campo de base nace con **default `subtotal`**, que es exactamente lo que esas dos hacen hoy, así que **compras queda byte a byte**. Solo cambiaría si alguien configurara una reteIVA con base en el IVA y la usara en una compra, y ahí el precálculo daría cero — que es lo correcto, porque en una compra de chatarra no hay IVA que retener (el chatarrero no es responsable de IVA, y por eso la reteIVA sembrada dice "sin uso aún"). Hoy ese caso daría un porcentaje del subtotal, o sea un número inventado.

### D6 — El IVA se precalcula por línea
Redondeando cada línea y sumando, que es lo que hace Siigo. Con el sistema registrando, el precálculo es una ayuda y el usuario podría corregir el centavo a mano; hacerlo bien cuesta lo mismo y evita esa fricción todos los días.

### D7 — Cero efecto en el P&L
El IVA no es ingreso y la retención no es gasto. `sale.total_amount` sigue siendo el subtotal, que es lo que el P&L lee. **Test de oro**: el P&L de un período es idéntico antes y después de agregarle impuestos a una venta.

### D8 — El concepto se deriva donde se puede
Venta de un bien → concepto de venta; maquila y flete → concepto de servicios. El usuario lo puede cambiar. Derivarlo es menos superficie y menos error que preguntarlo, y las facturas muestran que la correspondencia es estable.

### D10 — Dueño único cuando la Salida deriva una venta (C5 de QA)

La Salida tipo venta **crea una `Sale`**, así que hay dos documentos para una sola factura y el CHECK de una fila no impide que los dos lleven impuestos. **El dueño es la Salida**, que es el documento que el usuario liquida y el que conoce el tipo y el concepto.

Guard explícito: una venta con `willard_delivery_id` **rechaza** el payload de impuestos, con un mensaje que manda a la Salida. Es el patrón del guard de #93 D7b, donde cancelar una compra derivada manda a anular la Entrada. Fila propia en la matriz.

### D11 — Los puntos que revierten, enumerados por grep (C6 de QA)

No de memoria. `grep` sobre los servicios da **exactamente dos**:

| Camino | Dónde |
|---|---|
| Cancelar una venta | `sale.py:500` |
| Anular una Salida de Plomo | `willard_delivery.py:335` → `_reverse_liquidation` en `:936` |

**No existe des-liquidar en ventas**, a diferencia de compras, que lo tiene desde #93 D20. Si algún día se agrega, tiene que revertir impuestos y esta tabla es donde se mira.

Los dos revierten con `reverted_at`, sin borrado físico, igual que las retenciones de compra.

### D9 — Rige hacia adelante
No reescribe documentos ya liquidados (#61). Los saldos existentes no se mueven.

---

## 5. Cómo queda un documento con impuestos

Con la FE 2127, la venta de plomo:

```
Cliente Willard      + 106.028.973,00   (el subtotal, como hoy)
Cliente Willard      +  20.145.504,87   IVA que también le cobramos
Cliente Willard      −   2.650.724,33   retefuente que nos descuenta
Cliente Willard      −   3.021.825,73   reteIVA
Cliente Willard      −   1.166.318,70   ICA
                     ────────────────
Willard queda debiendo 119.335.609,11   = el total a pagar de la factura

[Impuestos] IVA por Pagar        −  20.145.504,87   pasivo con la DIAN
[Impuestos] ReteFuente a Favor   +   2.650.724,33   activo
[Impuestos] ReteIVA a Favor      +   3.021.825,73   activo
[Impuestos] ICA a Favor Barranquilla + 1.166.318,70 activo
```

La suma de todo da cero: lo que el cliente deja de deber es exactamente lo que SAC tiene a favor, y el IVA que cobra de más es exactamente lo que le debe a la DIAN. Conservación por construcción, igual que en compras.

---

## 6. Matriz defecto × test

**Se commitea antes de plantar nada.** La columna de lo esperado sale de ese commit y no se reescribe (#105). ⚠️ Los defectos que vivan en vía compartida se predicen como *"al menos estos"*, que es la regla que me salté dos veces en #111.

| | T1 conservación | T2 sin impuestos = hoy | T3 base de reteIVA | T4 P&L intacto | T5 balance ×4 caminos | T6 reversión | T7 sin flag | T8 permiso | T9 por línea | T10 statement | T11 dueño único | T12 fuera del panel | T13 guard de asignación | T14 categoría blindada | G pantalla |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| P1 el IVA no acredita al cliente | al menos | — | — | — | al menos | — | — | — | — | al menos | — | — | — | — | — |
| P2 la retención suma en vez de restar | al menos | — | — | — | al menos | — | — | — | — | al menos | — | — | — | — | — |
| P3 reteIVA sobre el subtotal | — | — | **cae** | — | — | — | — | — | — | — | — | — | — | — | — |
| P4 el IVA entra a `total_amount` | — | — | — | al menos | — | — | — | — | — | — | — | — | — | — | — |
| P5 la regla nueva del clasificador no se aplica | — | — | — | — | **al menos** | — | — | — | — | — | — | — | — | — | — |
| P5b la regla se aplica solo en el clasificador vivo | — | — | — | — | **cae, y solo en el as-of** | — | — | — | — | — | — | — | — | — | — |
| P6 la reversión no revierte | — | — | — | — | — | **cae** | — | — | — | al menos | — | — | — | — | — |
| P7 sin bandera el payload pasa | — | al menos | — | — | — | — | **cae** | — | — | — | — | — | — | — | — |
| P8 el permiso cambia a solo lectura | — | — | — | — | — | — | — | **cae** | — | — | — | — | — | — | — |
| P9 el IVA se precalcula sobre el total | — | — | — | — | — | — | — | — | **cae** | — | — | — | — | — | — |
| P10 el statement no emite el evento | — | — | — | — | — | — | — | — | — | **cae** | — | — | — | — | — |
| P11 la venta derivada acepta impuestos | — | — | — | — | — | — | — | — | — | — | **cae** | — | — | — | — |
| P13 la entidad de impuestos aparece en el panel de cobro | — | — | — | — | — | — | — | — | — | — | — | **cae** | — | — | — |
| P14 el reconocimiento va por nombre y alguien renombra | — | — | — | — | **al menos** | — | — | — | — | — | — | — | — | — | — |
| P15 el guard de la categoría de sistema no está | — | — | — | — | — | — | — | — | — | — | — | — | **al menos** | — | — |
| P15b el guard rechaza también la vía del sistema | — | — | — | — | al menos | — | — | — | — | — | — | — | **al menos** | — | — |
| P16 sin el índice único, dos categorías con el mismo código | — | — | — | — | al menos | — | — | — | — | — | — | — | — | **al menos** | — |
| P17 `system_code` se vuelve escribible desde la API | — | — | — | — | — | — | — | — | — | — | — | — | — | **al menos** | — |
| P18 el guard del PATCH no cubre `parent_id` | — | — | — | — | — | — | — | — | — | — | — | — | — | **al menos** | — |
| P12 el formulario compartido pide impuestos sin bandera | — | — | — | — | — | — | — | — | — | — | — | — | — | — | **cae, y solo acá** |

⚠️ **C8 de QA, y es la regla que me salté dos veces en #111**: las filas que viven en el camino compartido de liquidación y saldos se predicen como **"al menos estos"**, nunca "y solo". Solo P12 lleva *"y solo acá"*, porque es pantalla y no hay otra vía que la toque.

**T10 es el que QA exigió y faltaba (C4)**: el cliente y cada entidad ganan movimientos de saldo que **no son `MoneyMovement`**. Si el estado de cuenta no emite sus eventos, el saldo corrido deja de cerrar contra el saldo vivo, que es el invariante de #55 — y fue exactamente el bloqueante de QA en #93 con las retenciones de compra. Se prueba en **las dos superficies**: el estado de cuenta del CLIENTE y el de una ENTIDAD de impuestos.

**T5 recorre los CUATRO caminos**: Balance General y Detallado, vivo y a fecha de corte. Son dos clasificadores distintos, y P5b existe justamente para que corregir uno solo no pase en verde.

**T14 blinda la categoría misma** (A1–A3): la segunda fila con el mismo código **no entra** (índice único parcial), `system_code` mandado por la API queda en `NULL`, y el `PATCH` no la desactiva ni la reparenta — pero **sí la renombra**, que es la asimetría de #58 y la razón de que el reconocimiento sea por código.

**T13 son dos mitades y las dos hacen falta (D4d)**: que un usuario **no** pueda asignar ni quitar la categoría de impuestos desde el formulario de terceros (`422` en las dos direcciones, porque `_sync_category_assignments` borra y recrea), **y** que la entidad nacida del flujo de impuestos **sí** la tenga. P15b existe por la segunda mitad: un guard escrito de más — que bloquee también a `retention_entities.py` — dejaría al ciclo sin poder crear sus propias entidades, y sin esa fila el plantado no lo distingue de un guard correcto.

**T8 se escribe con el control positivo de #111**: un rol con lectura y sin gestión, que debe **leer en 200** antes de que se le niegue la escritura. Sin ese 200, el 403 puede venir de la bandera y el test no prueba el permiso.

---

## 7. Gates

| Gate | Por qué |
|---|---|
| **Golden ×3 organizaciones** | **Gate duro, y desde D4 lo es POR CÓDIGO y no solo por forma**: `reports.py` cambia. 🔴 **C7 corregido en v1.2**: la sección nueva de D4b **es una clave aditiva**, así que lo que se declara antes de correr es **2 claves aditivas de valor `0.0`** — `tax_advances` en la captura del Balance General vivo y en la del corte histórico —, **0 diffs reales** y el resto byte a byte. Eso es además un **control positivo por construcción**: si esas dos claves no aparecen, el golden comparó dos códigos iguales. Se verifica antes si el Detallado emite secciones vacías; si las emite, son dos aditivas más y se declaran igual. Más el control positivo contra **SAC** (una entidad de impuestos a favor cae en la sección nueva en un puerto y en Gastos Prepagados en el otro) y la prueba de vida en el log |
| Suite completa a archivo | con `EXIT` dentro del bloque y mtime sobre los cinco directorios, excluyendo `__pycache__` |
| Parity check a archivo | hay dos migraciones nuevas: `document_taxes` y la columna de D4b |
| **Smoke contra la base ya migrada, con `POST` real a categorías** | **C15**: la columna nueva vive en una tabla de las siete organizaciones, y un `server_default` que falte en la migración **no lo ve ningún otro gate** — la base de test nace de los modelos y la de producción de las migraciones (#100) |
| **Plantado de los 20 defectos** | matriz commiteada antes, cierre por sha256 y respaldo **por ruta completa**, nunca por basename (#106) |
| Pantalla | las dos vías, con y sin impuestos, **y una organización que no sea SAC** para ver que el formulario no cambió. Además: el selector de **Pago de pasivo**, donde las entidades a favor van a aparecer por ser `liability` + sistema (ver D4b) — es lo que Daniel decide ahí mismo |

---

## 8. Fuera de alcance, declarado

1. 🔴 **Cómo se SALDA un anticipo de impuestos (C12 de QA, y Daniel tiene que saberlo).** Contablemente se cruza contra el IVA por pagar al presentar la declaración. Ese cruce **hoy no se puede registrar**: `money_movement.py:902` y `:909` rechazan con 400 cualquier traslado entre terceros donde participe una entidad de sistema, y el pago normal solo sirve para el lado en contra. Consecuencia declarada: **este ciclo crea saldos a favor que el sistema no tiene cómo cerrar, y van a crecer indefinidamente.** Queda fuera de alcance porque abrir el cruce toca una validación compartida por todas las organizaciones, pero es deuda con fecha de vencimiento: el día que SAC presente su primera declaración, la va a necesitar.
2. **Filtrar las entidades a favor del selector de Pago de pasivo.** Aparecen ahí por ser `liability` + sistema (D4b). Pagarle a un anticipo de impuestos no tiene sentido y **aumentaría** el saldo a favor. No bloquea: el nombre dice *"a Favor"* y filtrarlo es el mismo predicado en una línea. Se mira en la pantalla y lo decide Daniel.
3. **El IVA descontable en compras.** Si un proveedor le factura IVA a SAC es un activo, y hoy no existe. Nadie lo pidió.
4. **Emitir la factura electrónica.** D1.
5. **Conciliar contra Siigo.** El número de factura amarra los dos, pero nadie compara los totales. Si divergen, no hay alarma.
6. **Corregir las tres tarifas sembradas.** Se ajustan desde la pantalla y el sembrado no las pisa.
7. **El resto de las organizaciones.** Todo detrás de la bandera.

---

## 9. Lo que queda abierto con el cliente

1. **Qué tarifas configurar exactamente.** Las facturas dan cuatro combinaciones: retefuente 2,5 y 4, ICA 1,1 y 1,25. Si hay más conceptos, aparecerán; el catálogo los admite sin código.
2. **Si hay ventas sin IVA y cuáles.** Daniel lo anticipó. El diseño ya las soporta, pero saber cuáles son ayuda a no configurar de más.
3. **Q-37 sigue reabierta** y este ciclo no la toca.
