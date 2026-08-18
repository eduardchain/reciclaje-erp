# Plan — Entrada sin proveedor: reparto al liquidar y descuadre de entrada (SAC)

**Versión:** v1.4 — 🟢 GO. Cierra las dos condiciones del GO condicionado (A1 fechas del descuadre,
A2 contabilidad de `unliquidate`) e incorpora A3/A4/A5 y W-1.
**Origen:** conversación de Daniel con el cliente, 2026-08-05, + Excel real de Johana
("COMPRA VARIOS (GREENLOOP)", entrada **15.422** del 22/07/2026, 13 proveedores) + 16 respuestas de
Daniel.
**Supersede:** [plan-sac-multiproveedor-por-linea.md](plan-sac-multiproveedor-por-linea.md) (#89,
construido y con QA GO, **nunca commiteado**). Ver §9.
**Decisión CLAUDE.md que le corresponderá:** **#93**.

> **v1.0 → v1.1.** Dos respuestas de Daniel eliminaron las dos piezas más caras: **no hay stock en
> tránsito** (D9) y **la liquidación es atómica** (D14), con lo que el estado "Parcial" desaparece.
>
> **v1.2.** Daniel aprobó el camino de reversa único (D14) y comunicarle al cliente que el
> truncamiento no se compensa (D5).
>
> **v1.3 — micro-QA 🔴 NO-GO + refutación adversarial.** QA encontró que D6 promete una regla de
> valoración que D7 solo cumplía para el sobrante (B1). Se resuelve **valorando también el faltante
> al precio de referencia**: resultó correcto y más barato de lo que QA estimó, porque
> `remove_from_pool` ya existe. Pero la refutación encontró **tres huecos peores, todos en D14** —la
> parte que QA explícitamente aprobó—: la liquidación atómica **no es construible** con el código de
> hoy. El argumento de D14 sigue en pie; faltan tres primitivas. Cambian D3, D6, D7, D8, D11, D14;
> aparecen D15–D19; §7 y §8 se reescriben.
>
> **v1.4 — cierre del GO condicionado.** A1 se resuelve con **una regla más fuerte que la lectura de
> QA**: no "checkpoint HOY + movimiento con fecha de la Entrada", sino **todo el evento de liquidación
> en un solo día** (D21) — la fecha de la Entrada NO fecha ningún efecto. Razón: si el ajuste del
> descuadre se fechara al día de captura, un corte entre captura y liquidación mostraría las 2
> unidades del sobrante **sin las 67 de las compras** (que cuentan por `liquidated_at`), un inventario
> que nunca existió. A2 queda en D20 (helper compartido de reversa — no una tercera copia del código
> más delicado del motor) con sus tres declaraciones. A3 (guard hermano de #84), A4 (docstring MCH),
> A5 (el source_type nuevo NO es reversión) y W-1 (el signo del fix del annul) entran al ciclo.

---

## 1. Qué se construye

Hoy la Entrada nace con un proveedor. **Deja de tenerlo.** La captura registra únicamente el hecho
físico —qué material, cuánto, en qué camión, con qué remisión— porque en el patio **nadie sabe
todavía de quién es el material**.

El proveedor aparece **al liquidar**: Johana reparte la cantidad recibida entre N proveedores con sus
cantidades, y de ahí salen N compras.

Lo repartido casi nunca cuadra exacto con lo pesado. Esa diferencia —el **descuadre de entrada**— es
el corazón del ciclo:

- **El inventario se queda con lo que SAC pesó.** Es la verdad física y no se negocia.
- **Los estados de cuenta reciben lo asignado a cada proveedor.** Es la verdad comercial.
- **La diferencia es una ganancia o una pérdida**, visible y marcada como tal.

Un sobrante es material que SAC tiene y no le debe a nadie. Un faltante es material que SAC paga y no
tiene. Ninguno de los dos se esconde en el costo promedio.

### El ejemplo real (Excel de Johana, entrada 15.422 del 22/07/2026)

Un camión de Green Loop, **13 proveedores**, 13 materiales, $12.423.777 pesados contra $12.393.275
repartidos. Dos filas descuadran: MOTO por faltante (los proveedores reportan ~1.022,7 kg contra
1.018 de báscula) y PLOMO BALANCIN por sobrante (69 pesadas contra 67 reportadas).

De ese documento salen cinco hechos que gobiernan el diseño:

| Hecho | Consecuencia |
|---|---|
| **Una fila por material**, con una sola columna de precio | D3 |
| 13 proveedores en un camión, hasta 8 sobre un mismo material | D2 |
| Los proveedores llevan los consecutivos **16166…16178** — 13 seguidos | confirma D14: nacen juntos |
| Cantidades decimales en kg (54,7 · 131,4 · 188,7) y enteras en unidades | ya soportado (#54), y D11 |
| La diferencia se lee **por fila** | D5 |

---

## 2. Preguntas resueltas

Las 16 respuestas de Daniel (2026-08-05/06):

| # | Pregunta | Respuesta |
|---|---|---|
| 1 | ¿Precio del descuadre? | **Precio de referencia del material en esa entrada**, editable. Daniel propuso costo promedio; se descartó con el argumento de D6 y lo aceptó. |
| 2 | ¿Se ve en inventario antes de saber de quién es? | **No hace falta.** La ventana es de horas o días. |
| 3 | ¿Entra "revisada"? | Sí, de una vez. |
| 4 | ¿Ajustar qué corrige? | La cantidad pesada de la entrada, y después se liquida. |
| 5 | ¿Descuadre por material o por entrada? | **Por material** — *"pueden haber trucamiento entre referencias"*. |
| 6 | ¿Willard pierde proveedor? | **No.** Confirmado con Johana: es otro canal. |
| 7 | ¿Precio por material o por proveedor? | Uno por material **con excepción editable**; la UI reutiliza el primero digitado. |
| 8 | ¿Comisión del recolector? | **Una por entrada.** |
| 9 | ¿Umbral del descuadre? | **Tolerancia configurable.** |
| 10 | ¿Quién revisa? | Permiso nuevo + rol nuevo. |
| 11 | ¿Ventana captura→liquidación? | Horas o días. No es problema. |
| 12 | ¿Reparto completo o por partes? | **Todo de una.** |
| 13 | ¿Precio si el material no está en la entrada? | **Lista de precios vigente** sugerida, con opción manual. |
| 14 | ¿El golden es gate de este ciclo? | **Sí — regla fija**: *"golden gate siempre, que nada de las otras empresas se rompa."* |
| 15 | ¿Se bloquea un reparto vacío? | **Sí**, con la propuesta de D8: no se bloquea el *monto* del descuadre, se bloquea la *ausencia de intención*. |
| 16 | ¿Base de la comisión? | **Lo pesado** (incluye el descuadre). Con **14 kg por unidad, sea cual sea la unidad** (Hugo). |

**Sin puntos abiertos de producto.** Queda una pregunta de alcance en D19 (P&L por sede) que el plan
propone declarar como limitación conocida.

---

## 3. Modelo de datos

### D1 — La línea pierde el proveedor y gana el reparto

`inbound_order_lines.third_party_id` (que #89 creó NOT NULL) **desaparece**. La línea vuelve a ser lo
que su nombre dice: material + cantidad pesada.

Tabla nueva **`inbound_line_allocations`**:

```
id                 PK
inbound_line_id    FK → inbound_order_lines  (CASCADE)
third_party_id     FK → third_parties        (RESTRICT)
quantity           Numeric(15,4)  NOT NULL   > 0
unit_price         Numeric(15,2)  NOT NULL   >= 0
invoice_number     String(50)     NULL       -- factura del proveedor
organization_id    FK  (OrganizationMixin)
UNIQUE (inbound_line_id, third_party_id)
```

**Por qué tabla**: un material se reparte entre hasta 8 proveedores en el ejemplo real, y el número
no está acotado.

**Por qué `unit_price` acá**: respuesta 7. El precio normal es uno por material —la UI lo replica
sola— pero la excepción tiene que poder registrarse, y el único lugar donde cabe es el reparto.

### D2 — Tabla puente entrada↔compras (heredada de #89)

`inbound_order_purchases` se conserva tal cual: exclusiva de SAC.

⚠️ **Corrección a la v1.2**: decía "cero tablas compartidas tocadas" y **era falso** —
`inventory_adjustments.inbound_order_id` (D7) es una columna en una tabla de las 7 organizaciones. El
patrón es sano (precedente: `transfer_id` de #84) pero la afirmación no lo era, y arrastra el gate
del golden (D18).

🔴 **La trampa 1:N sigue viva**. Un `outerjoin(Purchase)` en el listado haría que una entrada de 13
proveedores salga **13 veces** en la bandeja y la paginación pierda filas. El enrich va por
**lookup por página** (patrón #87 B1), nunca por join. Test bloqueante con 13 proveedores.

### D3 — `reference_unit_price`, y una fila por material

`inbound_order_lines.reference_unit_price` Numeric(15,2) NULL. Es el precio del material en esa
entrada: el que la UI pre-llena en cada reparto nuevo y el que valora el descuadre (D6). Nace al
liquidar y es editable.

🔴 **`UNIQUE (inbound_order_id, material_id)` en las líneas** (nuevo en v1.3). Sin él, el mismo
material puede aparecer en dos líneas con **dos precios de referencia distintos el mismo día** — que
es textualmente el defecto con el que D6 descarta el costo promedio. Además dos descuadres del mismo
material **no conmutan**: el `increase` mueve el promedio al que el `decrease` valoraría. El Excel de
Johana tiene una fila por material; el modelo lo hace obligatorio.

### D4 — Cuatro estados, y ahora es una columna

```
registrada → revisada → liquidada
                    ↘ anulada
```

- **registrada**: capturada en el patio. Solo hecho físico, cero efectos.
- **revisada**: alguien con el permiso nuevo confirmó cantidades. **Habilita liquidar.**
- **liquidada**: existen las N compras.
- **anulada**.

Con liquidación atómica (D14) **no existe "Parcial"**, y el estado deja de derivarse de las compras:
es una columna en `inbound_orders`. Se cae el espejo SQL↔Python y su test de paridad.

---

## 4. El descuadre

### D5 — Por material, y no se netea

Para cada línea: `descuadre = line.quantity − Σ allocations.quantity`.

Positivo = **sobrante** → ganancia. Negativo = **faltante** → pérdida.

⚠️ **Los descuadres NO se netean entre materiales.** Puede haber truncamiento entre referencias: el +2
de un material y el −2 de otro pueden ser el mismo hecho físico. Se muestran **juntos en la misma
pantalla** para que Johana lo entienda, pero **el efecto en resultados no se cancela**: reclasificar 2
unidades de un material de $4.418 a uno de $2.200 deja $4.436 reales.

🔴 **Requisito de entrega (aprobado por Daniel)**: decírselo al cliente **antes** del despliegue. La
expectativa natural es que "se compense", y descubrirlo en el estado de resultados sería descubrirlo
de la peor forma.

### D6 — Se valora al precio de referencia, en los dos sentidos

**La decisión**: `reference_unit_price` de la línea, editable, **tanto para el sobrante como para el
faltante**.

**Por qué no el costo promedio** (primera propuesta de Daniel): si SAC pesó 69 de BALANCIN y los
proveedores reportan 67, esas 2 unidades valen lo que SAC habría pagado ese día — $4.418, que está en
la fila. Valorarlas al costo promedio, que puede venir de meses atrás, deja la **misma entrada con dos
costos distintos para el mismo material el mismo día** y produce un número que no corresponde a ningún
hecho. El costo promedio contesta otra pregunta ("cuánto vale mi inventario"), no esta ("cuánto me
costó este descuadre").

**Por qué no el promedio ponderado de lo repartido**: con excepciones de precio (D1), el ponderado
haría que el valor del descuadre dependa de **cuáles proveedores resultaron ser la excepción** —
arbitrario e inexplicable en una frase.

**Cuando el material no está en la entrada** (truncamiento puro: reportan GRUPO 4 y solo se capturó
GRUPO 3): **lista de precios vigente** (#10) como sugerido, editable; sin precio en lista, obligatorio
digitarlo. ⚠️ Requiere que se pueda **crear la línea con cantidad pesada 0** — hoy
`InboundOrderLineCreate.quantity` es `gt=0` y no habría dónde colgar el reparto (D16).

### D7 — El mecanismo: ajuste de inventario, con `unit_cost` explícito

| Caso | Mecanismo | P&L |
|---|---|---|
| Sobrante | `InventoryAdjustment` **increase** a `reference_unit_price` | `adjustment_net` (ganancia) |
| Faltante | `InventoryAdjustment` **decrease** a `reference_unit_price` | `adjustment_net` (pérdida) |

**El hallazgo de QA (B1) y su resolución.** `IncreaseCreate` tiene `unit_cost` obligatorio;
`DecreaseCreate` **no lo tiene** y el servicio usa `material.current_average_cost` — o sea, el faltante
se valoraría exactamente al promedio que D6 rechaza. Se resuelve **agregando el costo explícito al
camino del decrease**, que resultó correcto y barato porque `remove_from_pool` (#66) ya existe y su
contrato es literalmente *"saca del pool `quantity` unidades que habían entrado a `unit_cost`"* — que
es el faltante: esos kg **sí entraron**, con las compras de esta misma entrada.

**Aritmética verificada** (caso MOTO real, con los helpers reales, no reimplementados):

```
tras las compras : 1.122,7 kg   avg 95,54645052106528903536118286   pool $107.270
remove_from_pool(1122.7, avg, 4,7, $100) → rama 1 → avg 95,52772808586762075134168157  adj $0
compra limpia de 1.018 @ $100                     → avg 95,52772808586762075134168157
                                                     IDÉNTICO a 26 dígitos
```

Con el mecanismo de hoy la pérdida sería $449,07 en vez de $470, y quedarían **$20,93 de inventario
sobrevalorado** — material que SAC no tiene.

**🟢 La propiedad que ordena el debate**: fuera de la rama limpia, la opción se **degrada sola** al
número de hoy. En las ramas de hueco, `remove_from_pool` deja el avg quieto y devuelve
`cost_adjustment = q·(p−A)`; el P&L neto es `−q·p + q·(p−A) = −q·A`, que es exactamente el
comportamiento actual. **No puede romper nada nuevo.** La condición de la rama limpia se enuncia en
una frase: **el material queda con stock positivo después de la entrada**, que en SAC es el caso
normal (llega el camión y después se vende).

**🔴 Requisito de orden**: el ajuste del descuadre se aplica **al final, sobre el pool ya alimentado
por las N compras**. Emitirlo antes deja el pool pre-entrada (en SAC ~0 o negativo) y caen las ramas
de hueco de rutina, con lo que D6 no se cumpliría casi nunca.

**Los 7 cambios** (cero migraciones, cero columnas nuevas — `cost_adjustment` y `annul_cost_adjustment`
ya existen):

| # | Dónde | Qué |
|---|---|---|
| 1 | `services/inventory_adjustment.py` — firma de `decrease` | `unit_cost_override: Optional[Decimal] = None`. **Va en el servicio, no en el schema** (D15). |
| 2 | mismo, cuerpo | `remove_from_pool` cuando viene, **y persistir `cost_adjustment`** — sin eso el P&L sobre-reporta la pérdida en las ramas de hueco |
| 3 | mismo + catálogo MCH (10→12, con el de D20) | `record_cost_change` con `source_type` nuevo (`inbound_discrepancy` o similar). El `decrease` **hoy no escribe MCH**; sin esto el invariante "avg == último MCH" revienta y `_get_inventory_as_of` valuaría todo corte posterior al avg viejo. **Fecha: D21** (todo el evento en el día de la liquidación). **A5**: este source_type es **operativo, no reversión** — NO entra a `MCH_FASE5_REVERSAL_TYPES`; el silencio es el default correcto y queda escrito para que nadie lo "arregle" con buena intención |
| 4 | `services/inventory_adjustment.py:429-435` | 🔴 **simetría del `annul` para `qty < 0`** — ver abajo. **W-1, trampa de signo**: la rama del increase divide por `qty` (positivo); acá `quantity` se persistió **negativa**, así que la línea simétrica divide por `−qty` y respeta el signo que `remove_from_pool` le dio al relleno. Hoy el error sería invisible (siempre 0); con el override deja de serlo |
| 5 | `services/reports.py` (`mch_source_is_cancelled`) | 5ª rama, o el checkpoint de un descuadre **anulado** sigue visible en cortes (doctrina #41) |
| 6 | `tests/test_avg_cost_model_l.py` | extender `adj_annul` a decreases con precio |
| 7 | `models/material_cost_history.py` | **A4**: el docstring del modelo lista 5 source_types y la realidad son 10 (este ciclo la lleva a 12) — actualizarlo en el mismo cambio, la deriva documental es cómo se pierden las lecciones |

🔴 **El bug que esta decisión activa (y que hay que arreglar en el mismo ciclo).** El `annul` es
asimétrico: para `qty > 0` reconstruye la contribución real (`unit_cost + cost_adjustment/qty`, la H1
de #66); para `qty < 0` usa `adjustment.unit_cost` **crudo**. Hoy es inocuo porque un `decrease` nunca
escribe `cost_adjustment` — al hacerlo, anular un descuadre en rama de hueco **inventa valor**
(verificado: pool $1.000 → decrease 30 @ $100 → annul deja pool $3.700 en vez de $1.000). El fix es
una línea simétrica a la 422. **El stress walk no lo atraparía**: `adj_annul` solo escoge entre
increases confirmados, así que el bug pasaría el CI en verde.

**Marcado**: `inventory_adjustments.inbound_order_id` (FK, CASCADE, **no se serializa** — precedente
#75/#84) + `reason` canónico `"Descuadre de entrada #N"`.

**Limitación declarada**: en las ramas de hueco, D6 no se cumple y el número correcto sale **partido
en dos líneas** del P&L (`adjustment_net` y "Ajuste Costo por Sobreventa y Reversiones"). Se declara,
no se descubre.

**Sin línea nueva en el P&L**: `adjustment_net` ya existe, ya está en la identidad de conciliación
(#59) y ya tiene drill-down (#49). Una línea nueva obligaría a tocar la conciliación, el P&L mensual
(#50), los Excel y el drill-down. **Pero `adjustment_net` va a cambiar de significado en SAC**: hoy
responde "cuánto perdí en conteos y mermas" y con camiones diarios de 13 proveedores va a responder
otra cosa. La salida es un **filtro en el drill-down** (`adjustment_source=inbound_discrepancy|manual`),
precedente exacto de `exclude_migration_seeds` (#49). A Johana se le **muestra funcionando**; si
después pide el renglón, es aditivo.

### D8 — Tolerancia configurable, y el reparto vacío

Setting `inbound_discrepancy_tolerance_pct` (default a definir con Johana; `transfer_tolerance_pct`
usa 0.05 y es **fracción, no porcentaje**). ⚠️ Va en `OrgSettingsPayload` **y** en `SETTING_DEFAULTS`
— sin la clave backend, `get_org_setting` lanza `KeyError` (D12 de E1).

**Por qué porcentaje y no pesos**: en el ejemplo real, 4,7 kg sobre 1.018 son 0,46% y 2 unidades sobre
69 son 2,9%. Un umbral absoluto trataría igual dos situaciones que no se parecen.

**El sistema NUNCA bloquea por el tamaño del descuadre** (#17/#76). Dentro de tolerancia, aviso suave;
fuera, resaltado. Las dos salidas de la respuesta 4: **ajustar** la cantidad pesada y liquidar limpio,
o **permitir** y que se vuelva el ajuste de D7.

🔴 **Pero sí se bloquea la ausencia de intención** (respuesta 15). Una línea **sin ninguna asignación**
produce un descuadre del 100%: en el ejemplo, PLOMO BALANCIN sin repartir daría `69 × $4.418 =
$304.842` de **ganancia sin proveedor y sin compra** — una fila del formulario que se quedó sin
llenar, convertida en utilidad. Eso no es un descuadre, es un reparto que falta.

Regla: liquidar con una línea sin asignaciones → **error que nombra la línea**. Si Johana de verdad
quiere declarar que ese material no es de nadie, lo marca **explícitamente** por línea
(`unallocated_intentional`), y entonces sí entra como ganancia. Se bloquea el descuido, no el monto.

---

## 5. Inventario y liquidación

### D9 — Sin tránsito: la Entrada no toca inventario hasta liquidar

Entre la captura y la liquidación pasan horas o días, y en esa ventana el material está físicamente en
bodega pero **el sistema no lo muestra**. Se acepta (respuestas 2 y 11).

**Qué se evita**: que la Entrada sea lo primero del sistema en sostener `current_stock_transit` sin ser
una compra —hoy solo `purchase.py` y `sale.py` lo mueven— y que el traspaso al liquidar toque la
máquina de costo promedio (#64–#66).

**Nota honesta**: es un paso atrás respecto de lo desplegado (hoy la Entrada tipo compra crea una
compra registrada que sí deja tránsito), pero eso lleva un día en producción. Agregarlo después es
aditivo.

### D14 — La liquidación es atómica, y le faltan tres primitivas

**Decisión (respuesta 12)**: se reparte todo y se liquida de una. **El descuadre solo se puede calcular
cuando todos reportaron**: liquidar por partes haría que todo pareciera faltante hasta el final. La
atomicidad no es comodidad de implementación, es lo que le da sentido al descuadre. El Excel lo
confirma: los 13 proveedores llevan consecutivos seguidos (16166…16178), o sea que nacen juntos.

**Camino de reversa único** (aprobado por Daniel): cancelar una compra derivada por separado → **400**,
"anule la liquidación de la entrada". `unliquidate` revierte las N compras, el ajuste y la comisión, y
devuelve la entrada a `revisada` **conservando el reparto**. Si se pudiera cancelar una sola de las 13,
la Entrada quedaría con un descuadre calculado sobre un reparto que ya cambió.

🔴 **Lo que la v1.2 daba por hecho y NO existe** (los tres huecos que encontró la refutación):

1. **`purchase.liquidate()` no tiene `commit` y hace `db.commit()` adentro.** Trece llamadas son trece
   commits: si la séptima revienta (precio ≤ 0, fondos insuficientes, retención contra tercero
   inactivo), **las seis anteriores quedan grabadas** — seis saldos movidos, el promedio recalculado
   seis veces, la Entrada sin liquidar. El riesgo R4 de la v1.2 mitigaba con "todo o nada" algo que el
   código no soporta. **Fix**: `commit: bool = True`, el mismo párrafo aditivo ya aplicado tres veces
   (`create`, `cancel`, `update`); `increase`/`decrease` ya lo aceptan.
2. **`unliquidate` no tiene primitiva.** No existe la transición liquidada → registrada (`cancel()`
   fija `"cancelled"`). Hacerlo con lo que hay sería cancelar 13 y crear 13: quema 13 consecutivos y
   deja 13 canceladas en 13 estados de cuenta. **Fix**: transición propia que revierte efectos sin
   cambiar `status` a `cancelled` ni consumir numeración.
3. **`inbound_order.annul()` rechaza si alguna derivada está liquidada** (`"Cancele primero las
   compras… la anulación de la entrada solo cubre compras registradas"`). Con D14 eso es **siempre** →
   la Entrada nunca se podría anular. **Fix**: el annul de una entrada liquidada delega en
   `unliquidate` y después anula.

Las tres son aditivas y ninguna toca semántica existente.

### D20 — La contabilidad de costo de `unliquidate` (A2 de QA)

**(c) primero, porque gobierna a las otras dos — un helper, no una tercera copia.** La reconstrucción
deque-por-firma de #66 H1 (la contribución real de cada línea: costo ajustado por comisión +
`cost_adjustment/qty` del relleno) ya vive **dos veces** en `purchase.py`: en `liquidate` y en
`cancel`. `unliquidate` NO será la tercera implementación del código más delicado del motor: el cuerpo
de reversa de `cancel()` se **factoriza** en un helper compartido (`_revert_liquidation_effects`), y
entonces `cancel() = helper + status="cancelled" + auditoría` y `unliquidate = helper +
status="registered" + liquidated_at=NULL`, sin quemar consecutivo y sin filas de cancelación en los
estados de cuenta.

**(a) El MCH de la reversa**: source_type nuevo **`purchase_unliquidation`** (catálogo 11→12, junto al
de D7). Es una **reversión**: entra a `MCH_FASE5_REVERSAL_TYPES` (a diferencia del de D7 — A5), con la
fecha de checkpoint de las reversiones: `business_today()` (#91).

**(b) El checkpoint original se queda, POR DECISIÓN**: el `purchase_liquidation` de la liquidación
original no se toca (#66, append-only) y `mch_source_is_cancelled` **no se extiende** — la compra
termina en `registered`, no `cancelled`, y agregarle una rama "desliquidada" borraría el checkpoint de
los cortes y rompería la cadena del avg entre la liquidación y su reversa. Hoy quedaría correcto por
omisión; queda escrito para que sea por decisión.

**Consecuencia declarada** (doctrina #41, "las canceladas nunca existieron"): los cortes consultados
**dentro de la ventana liquidación → unliquidate** se re-presentan — la cantidad de las N compras
cuenta por `liquidated_at`, que vuelve a NULL. En la práctica la ventana son minutos (Johana corrige y
re-liquida); es la misma semántica que cancelar y recrear, sin sus cicatrices.

### D21 — Un solo reloj para todo el evento de liquidación (A1 de QA)

**Todo lo que la liquidación escribe lleva EL MISMO día de negocio: el de la liquidación**
(`business_today()`, #90/#91): `liquidated_at` de las N compras, `date` del ajuste de descuadre,
`date` de la causación de la comisión, y `transaction_date` de todos los MCH del evento. Las compras
nacen con `date` = fecha de la Entrada (documento) y ese es su único vínculo con el día de captura.
**Sin back-dating** — es la regla que el cliente ya confirmó en #62: *"la operación cuenta el día que
la liquidan"*.

**Por qué NO la lectura de QA** ("checkpoint HOY, movimiento con la fecha de la Entrada", calco de
H1a): H1a es correcta para Willard porque ahí el evento **es la recepción** — la confirmación es
documental. Acá el evento financiero es la **liquidación**. Si el ajuste del descuadre se fechara al
día de captura, un corte entre captura y liquidación mostraría las 2 unidades del sobrante **sin las
67 de las compras** (que cuentan por `liquidated_at`, #61c) — un inventario que nunca existió en
ningún momento. Con D21, **nada aterriza antes del día de liquidar**: la estabilidad de cortes que A1
pide se cumple por construcción, no por convención de checkpoint.

Criterio nuevo (§7.32): liquidar una Entrada capturada días atrás **no cambia ningún corte anterior
al día de la liquidación** — as-of en la fecha de captura, un día después, y la víspera de liquidar:
idénticos antes y después.

### D15 — El parámetro va en el servicio, no en el schema

`unit_cost_override` en la firma de `inventory_adjustment.decrease`, **no** en `DecreaseCreate`.

**Por qué**: el schema es el contrato del endpoint HTTP, que usan las 7 organizaciones desde la
pantalla de Ajustes. Exponerlo ahí invita a que alguien valore una merma manual a un precio arbitrario
—que es justo lo que #66 quiso evitar— y amplía la superficie pública para un caso interno. En el
servicio, el único que puede pasarlo es el código del descuadre.

Llamadores actuales de `decrease`: **dos** (el endpoint y la merma de traslados de #84), **ninguno**
pasa el parámetro → el camino de hoy queda byte a byte, y el invariante B1 de #84 ("un traslado NUNCA
cambia el avg") se preserva por construcción.

### D16 — Cantidad pesada 0 y precio de referencia 0

Dos guardas de esquema chocan con casos legítimos:

- `InboundOrderLineCreate.quantity` es `gt=0`: sin relajarlo a `ge=0` **no hay dónde colgar** el
  reparto de un material que los proveedores reportan y la báscula no vio (el caso de truncamiento del
  propio D5).
- `IncreaseCreate.unit_cost` es `gt=0`: un sobrante con precio de referencia vacío revienta con **422
  en mitad de la liquidación** — y, sin el fix 1 de D14, después de haber commiteado las compras que
  alcanzaron a liquidar.

Ambos se resuelven en el punto de entrada: el precio de referencia es **obligatorio al liquidar** para
toda línea con descuadre ≠ 0.

### D17 — El ajuste del descuadre no se anula desde Ajustes de Inventario

`annul()` solo valida `status != "confirmed"`: no hay guard por `transfer_id` (la merma de #84 tiene
el mismo agujero) ni lo habría por `inbound_order_id`. Anular el ajuste desde la pantalla de Ajustes
rompería el invariante `stock == Σ repartido + descuadre` **en silencio** y podría dejar la Entrada
irreversible.

Guard: ajuste con `inbound_order_id` → **422 que guía a la Entrada**. Mismo patrón que los guards de
Tesorería para movimientos de módulo (#67/#69/#86).

**A3 — se cierra también el hermano**: el mismo guard cubre `transfer_id` en el mismo punto — la merma
de #84 es anulable hoy desde Ajustes y rompería en silencio el invariante del traslado ("un traslado
nunca cambia el avg"). Son las mismas tres líneas, y ambos FK solo existen en datos SAC: cero efecto
para las otras organizaciones.

---

## 6. Efectos en otros módulos

### D10 — Permiso nuevo, rol solo para SAC

- **Permiso** `purchases.review` al catálogo general, con dual-write triple. **Sin asignar a roles de
  sistema** — política D4 de E1 (#74).
  ⚠️ **Corrección de QA (B4)**: la v1.2 proponía `inventory.review_inbound`. Es la familia equivocada:
  los 6 endpoints de entradas se guardan con `purchases.*` (create/view/edit/liquidate/cancel), y el
  precedente contrario (`inventory.transfer_receive`, #84) es correcto justamente porque los traslados
  **sí** son de inventario.
- **Rol** custom `revisor_inventario`, en `seed_sac_org.py`. Precedente: el `bascula_sac` de Erwin.

**Por qué no un sexto rol de sistema**: se crean en **todas** las organizaciones. Costa, Biogreen y las
demás verían un rol que no pidieron.

### D11 — La comisión del recolector: una por entrada, sobre lo pesado

Hoy se causa **dentro de `purchase.liquidate()`** (#83). Con 13 compras serían **13 causaciones por un
camión**. Pasa a causarse **una sola vez al liquidar la Entrada**, con `source_id` = la entrada. Sigue
siendo `expense_accrual` — **gasto, no prorrateo al costo**; la decisión de producto de #83 no cambia.
Willard sigue sin comisión.

**Base = la cantidad PESADA** (respuesta 16), no la repartida: Green Loop transportó lo que llegó,
incluido el material que ningún proveedor reclamó. Beneficio de paso: la comisión se puede calcular y
mostrar **antes** de repartir.

🔴 **Unidades mezcladas — la regla de los 14 kg.** La tarifa `comision_green_loop` es `per_kg_material`
y un camión trae 37 baterías (unidades) y 1.018 kg de MOTO: sumarlos no significa nada. Hugo definió
**14 kg por unidad, sea cual sea la unidad**. La regla:

```
base = Σ  ( material.default_unit == "kg" ?  línea.quantity  :  línea.quantity × 14 )
```

**Dónde vive el 14**: junto al precio, en `ServiceTariff` — los dos números son parte del mismo acuerdo
con Green Loop y deben versionarse juntos (append-only, #74: las entradas viejas conservan el suyo).
`service_tariffs` es tabla exclusiva de SAC.

**Por qué NO configurable por referencia** (Daniel lo dejó abierto): los 14 kg **no son un peso, son un
acuerdo** — nadie cree que una GRUPO 0.7 y una GRUPO 5 pesen lo mismo. Por referencia serían 37 lugares
donde equivocarse, y el día que alguien edite uno, la comisión deja de ser explicable. Si algún día se
necesita, `material_conversion_formulas` ya existe y sería aditivo.

### D12 — Remisión y factura, por fin separadas

- **Remisión**: una, de la **Entrada**, la del camión. Se captura en el patio.
- **Factura**: una por **proveedor**, en su reparto. Llega con la liquidación.

### D13 — Willard intacto

Confirmado con Johana (respuesta 6). Todo este plan aplica **solo al tipo compra**. El flujo de 2 pasos
de Willard (#81), la homogeneidad de mundos y la sede determinista (#80) siguen igual.

### D18 — El golden es gate de deploy

Regla fija de Daniel (respuesta 14): *"golden gate siempre, que nada de las otras empresas se rompa."*

Este ciclo **sí toca tabla compartida** (`inventory_adjustments.inbound_order_id`, D7) y **sí cambia un
camino compartido** (`decrease` gana un parámetro, `annul` corrige su asimetría — D7 fix 4, que afecta
a **cualquier** decrease anulado, no solo a los del descuadre). Golden ×3 orgs de producción, con el
diff en cero, antes de desplegar.

### D19 — El descuadre vale $0 en el P&L por sede (limitación declarada)

Con `?warehouse_id=`, `_not_by_sede = [false()]` se aplica a los filtros de ajustes, de sobreventa y de
reversiones: **el descuadre no aparece en el P&L por sede** que #84 construyó para que SAC vea CV/BOG/JM
por separado. Lo mismo le pasa a la comisión del recolector (los gastos también son `false()` por sede).

El dato existe —la Entrada tiene una bodega y el ajuste la hereda—, es el reporte el que lo descarta.
**No es algo que este ciclo introduzca**: es la limitación de #84 (todo lo que no sea venta/COGS/comisión
vale $0 por sede) aplicada a una fuente nueva. Se declara; ampliarlo es ciclo propio y hay que decidirlo
con Daniel cuando SAC empiece a mirar ese reporte.

---

## 7. Criterios de aceptación

**Captura y revisión**
1. Entrada tipo compra sin proveedor → se crea; **cero efectos** (ni inventario ni financieros).
2. Entrada `registrada` → liquidar da error que guía a revisar primero.
3. Revisar sin `purchases.review` → 403; con el permiso → `revisada`.
4. Willard sin cambios: nace `draft`, confirma, nunca pide reparto.
5. Dos líneas con el mismo material → rechazado (D3).

**Reparto y descuadre**
6. 13 proveedores sobre 13 materiales → 13 compras liquidadas, con consecutivos seguidos.
7. Sobrante → `increase` a `reference_unit_price`; ganancia en `adjustment_net`.
8. Faltante → `decrease` a `reference_unit_price`; pérdida en `adjustment_net` = `qty × precio`.
9. Descuadre cero → **ningún ajuste creado**.
10. Dentro de tolerancia → aviso; fuera → resaltado. **Nunca bloqueo por monto.**
11. 🔴 Línea sin ninguna asignación → **error que la nombra**; con `unallocated_intentional` → pasa y
    entra como ganancia (D8).
12. Ajustar la cantidad pesada y liquidar → descuadre cero, sin ajuste.
13. Precio de excepción en un proveedor → su compra lleva su precio; el descuadre sigue al de referencia.
14. Material repartido que no está en la entrada → línea con cantidad 0, precio de lista sugerido (D16).
15. Descuadre ≠ 0 sin precio de referencia → error **antes** de empezar a liquidar, no a mitad.

**Invariantes**
16. 🔴 **Test estrella**: el costo promedio es **idéntico** liquidando con 1 proveedor o con 13, con y
    sin descuadre, **con stock final positivo** (la condición de rama limpia de D7).
17. Faltante con pool en hueco → el P&L neto es `−q·A`, igual que hoy (la degradación de D7).
18. `stock_liquidado == Σ repartido + descuadre == cantidad pesada`.
19. Una entrada de 13 proveedores aparece **una sola vez** en la bandeja.
20. 🔴 Anular un `decrease` hecho con precio explícito → **round-trip exacto** al pool original
    (el bug del fix 4 de D7; el stress walk debe cubrirlo).
21. `avg == último MCH` después del descuadre (el MCH del fix 3).

**Reversas**
22. `unliquidate` → revierte N compras + ajuste + comisión, vuelve a `revisada`, conserva el reparto,
    **sin quemar consecutivos** y **sin dejar canceladas en los estados de cuenta**.
23. `unliquidate` **avisa, nunca bloquea** (#76) — si bloqueara, vuelve el deadlock del Ciclo C con 13
    compras adentro.
24. Cancelar una compra derivada por separado → 400 que guía a `unliquidate`.
25. Anular una entrada **liquidada** → delega en `unliquidate` y anula (hoy es imposible, D14 fix 3).
26. Anular el ajuste de descuadre desde Ajustes de Inventario → **422 que guía a la Entrada** (D17).

**Atomicidad**
27. 🔴 Falla en la compra #7 de 13 → **ninguna** queda grabada; la Entrada sigue `revisada`.

**No-regresión (las otras 6 organizaciones)**
28. 🔴 Una organización sin `kg_ledger_enabled` ve el listado de compras **campo por campo idéntico**.
29. Un `decrease` sin `unit_cost_override` se comporta byte a byte como hoy — incluidos el endpoint y
    la merma de traslados (#84), y el invariante "un traslado nunca cambia el avg". ⚠️ Este criterio
    **no cubre el fix del `annul`** (aplica con o sin override): esa red son el 20, el 33 y el golden.
30. Comisión del recolector, retenciones y costo promedio de una compra normal: sin cambios.
31. 🔴 **Golden ×3 orgs de producción con diff en cero** (D18).

**Estabilidad temporal y annul (v1.4)**
32. 🔴 Liquidar una Entrada capturada días atrás **no cambia ningún corte anterior al día de la
    liquidación** (D21): as-of en la fecha de captura y en la víspera de liquidar, idénticos antes y
    después.
33. Anular un `decrease` preexistente (sin `cost_adjustment`, que son TODOS los de hoy) → idéntico al
    comportamiento actual: el fix del annul es **no-op por álgebra** (`u + 0/−q = u`).
34. `unliquidate` escribe `purchase_unliquidation` (reversión, en `MCH_FASE5_REVERSAL_TYPES`) y el
    `purchase_liquidation` original **permanece** en los cortes (D20b).
35. Anular la merma de un traslado desde Ajustes de Inventario → **422 que guía al traslado** (A3).

---

## 8. Riesgos

| # | Riesgo | Mitigación |
|---|---|---|
| R1 | ~~Traspaso de tránsito toca el costo promedio~~ | **Eliminado en v1.1** (D9) |
| R2 | La trampa 1:N vuelve por una consulta nueva | Test bloqueante con 13 proveedores; **prohibido** `outerjoin(Purchase)` en el listado |
| R3 | El cliente espera que el truncamiento "se compense" | Comunicarlo **antes** del despliegue (D5) |
| R4 | 13 compras en una transacción | `commit: bool` (D14 fix 1) + criterio 27. **Ya no se mitiga con una promesa** |
| R5 | `revisada` frena la operación si nadie tiene el permiso | El sembrado crea el rol y lo asigna antes de desplegar |
| R6 | 🔴 El fix del `annul` (D7 fix 4) toca **todos** los decreases anulados de las 7 orgs | Golden (D18) + criterio 20 + extender el stress walk |
| R7 | El orden del ajuste decide la rama y nadie lo nota | Requisito explícito en D7 + criterio 16 |
| R8 | `adjustment_net` cambia de significado en SAC | Filtro de drill-down (D7) y mostrárselo a Johana funcionando |

---

## 9. Qué se hereda de #89

**#89 no se commitea por separado.** Su migración `f7a8b9c0d1e2` **nunca llegó a producción**, así que
el gate del backfill (backup, verificación de organizaciones, ventana de reversión) **ya no aplica**.
Eso fue suerte de calendario, no mérito: una semana después habría habido que migrar datos productivos
hacia un modelo muerto.

🔴 **Procedimiento antes de codificar** (hallazgo B3 de QA): dev tiene `f7a8b9c0d1e2` **aplicado** y sin
commitear, así que la BD y el árbol están desalineados. El camino: `alembic downgrade` en dev a la
revisión previa (`158e8a0`, la de #88) → descartar la migración de #89 → escribir **UNA sola** migración
de #93 con la puente + `inbound_line_allocations` + `reference_unit_price` +
`inventory_adjustments.inbound_order_id` + el `UNIQUE(order, material)`, **sin** `third_party_id` en la
línea.

⚠️ **La v1.0 sobrevaloró la herencia.** Con liquidación atómica se cae también la maquinaria de estado
parcial, que era buena parte de #89.

**Se hereda**: la tabla puente y su argumento; el patrón de **lookup por página** para el enrich; la
factura por proveedor (se muda al reparto).

**Se descarta**: `third_party_id` NOT NULL en la línea; `partially_liquidated` con su espejo SQL↔Python
y su test de paridad; `_group_signature`; el selector por línea y el interruptor "un solo proveedor /
varios"; la remisión por proveedor en la captura.

---

## 10. Fuera de alcance

- Stock en tránsito entre captura y liquidación (D9).
- Enlazar descuadres relacionados por truncamiento (D5).
- Línea propia en el P&L para el descuadre (D7) — el drill-down primero.
- Descuadre y comisión en el P&L por sede (D19).
- Liquidación por partes (D14).
- Camino Willard (D13).
- Factor de kg por unidad configurable por referencia (D11).
- Certificados de retención y resumen mensual (Q-08, otro ciclo).
