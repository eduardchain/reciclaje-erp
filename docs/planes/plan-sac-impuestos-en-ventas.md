# Plan — IVA y retenciones en lo que SAC factura (CC-013 / Q-41)

**Estado:** v1.1, para segunda revisión de QA. Nada construido.
**v1.1 corrige un error mío en D4, que era la única afirmación que el plan hacía como medida, y cierra C3–C9.**
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

**No se tocan `sales`, `sale_lines` ni `money_movements`.** El golden sigue siendo gate duro porque el saldo de terceros y el balance sí cambian de forma, pero la superficie de esquema compartido es **cero**.

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
3. El marcador de sistema **protege** a las entidades de aparecer en selectores y de ser editadas o desactivadas. La alternativa (quitarles ese marcador) las dejaba sueltas en Maestros.

| Concepto | Qué es | Entidad | Saldo | Sección |
|---|---|---|---|---|
| IVA generado | SAC le debe a la DIAN | `[Impuestos] IVA por Pagar` | en contra | pasivo, sin tocar nada |
| Retención practicada a SAC | anticipo de impuesto | `[Impuestos] ReteFuente a Favor`, etc. | a favor | **activo, por la regla nueva** |

⚠️ **Consecuencia que cambia un gate**: `reports.py` **se toca**, así que *"superficie compartida cero"* deja de ser cierto y el golden pasa de gate por forma a **gate por código**, con prueba de vida y control positivo (ver §7).

⚠️ Las entidades de venta son **distintas** de las de compra: la retefuente que SAC le practica a un chatarrero es pasivo y la que Willard le practica a SAC es activo. Compartir entidad las netearía, y QA confirmó que netearlas es un error contable real, no una preferencia.

⚠️ **El panel de Dinero Inactivo (#68) excluye `prepaid_expenses` a propósito.** Con la corrección, las retenciones a favor quedan fuera de esa exclusión, y eso **es lo que se quiere**: a la DIAN no se le persigue un cobro, la retención se descuenta en la declaración. Queda declarado para que nadie lo lea como un olvido.

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

| | T1 conservación | T2 sin impuestos = hoy | T3 base de reteIVA | T4 P&L intacto | T5 balance ×4 caminos | T6 reversión | T7 sin flag | T8 permiso | T9 por línea | T10 statement | T11 dueño único | G pantalla |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| P1 el IVA no acredita al cliente | al menos | — | — | — | al menos | — | — | — | — | al menos | — | — |
| P2 la retención suma en vez de restar | al menos | — | — | — | al menos | — | — | — | — | al menos | — | — |
| P3 reteIVA sobre el subtotal | — | — | **cae** | — | — | — | — | — | — | — | — | — |
| P4 el IVA entra a `total_amount` | — | — | — | al menos | — | — | — | — | — | — | — | — |
| P5 la regla nueva del clasificador no se aplica | — | — | — | — | **al menos** | — | — | — | — | — | — | — |
| P5b la regla se aplica solo en el clasificador vivo | — | — | — | — | **cae, y solo en el as-of** | — | — | — | — | — | — | — |
| P6 la reversión no revierte | — | — | — | — | — | **cae** | — | — | — | al menos | — | — |
| P7 sin bandera el payload pasa | — | al menos | — | — | — | — | **cae** | — | — | — | — | — |
| P8 el permiso cambia a solo lectura | — | — | — | — | — | — | — | **cae** | — | — | — | — |
| P9 el IVA se precalcula sobre el total | — | — | — | — | — | — | — | — | **cae** | — | — | — |
| P10 el statement no emite el evento | — | — | — | — | — | — | — | — | — | **cae** | — | — |
| P11 la venta derivada acepta impuestos | — | — | — | — | — | — | — | — | — | — | **cae** | — |
| P12 el formulario compartido pide impuestos sin bandera | — | — | — | — | — | — | — | — | — | — | — | **cae, y solo acá** |

⚠️ **C8 de QA, y es la regla que me salté dos veces en #111**: las filas que viven en el camino compartido de liquidación y saldos se predicen como **"al menos estos"**, nunca "y solo". Solo P12 lleva *"y solo acá"*, porque es pantalla y no hay otra vía que la toque.

**T10 es el que QA exigió y faltaba (C4)**: el cliente y cada entidad ganan movimientos de saldo que **no son `MoneyMovement`**. Si el estado de cuenta no emite sus eventos, el saldo corrido deja de cerrar contra el saldo vivo, que es el invariante de #55 — y fue exactamente el bloqueante de QA en #93 con las retenciones de compra. Se prueba en **las dos superficies**: el estado de cuenta del CLIENTE y el de una ENTIDAD de impuestos.

**T5 recorre los CUATRO caminos**: Balance General y Detallado, vivo y a fecha de corte. Son dos clasificadores distintos, y P5b existe justamente para que corregir uno solo no pase en verde.

**T8 se escribe con el control positivo de #111**: un rol con lectura y sin gestión, que debe **leer en 200** antes de que se le niegue la escritura. Sin ese 200, el 403 puede venir de la bandera y el test no prueba el permiso.

---

## 7. Gates

| Gate | Por qué |
|---|---|
| **Golden ×3 organizaciones** | **Gate duro, y desde D4 lo es POR CÓDIGO y no solo por forma**: `reports.py` cambia. **C7 declarado antes de correr**: para Costa, Biogreen y Meta se esperan **0 diffs y 0 claves aditivas** — nada de esto les llega y ninguna respuesta compartida gana un campo. Como #110 demostró que ese resultado **no distingue** "no rompió nada" de "comparé viejo contra juntos", el control positivo es obligatorio y es contra **SAC**: una entidad de impuestos a favor cae en la sección nueva en el puerto nuevo y en Gastos Prepagados en el viejo. Más la prueba de vida escrita en el log de que los dos puertos corren códigos distintos |
| Suite completa a archivo | con `EXIT` dentro del bloque y mtime sobre los cinco directorios, excluyendo `__pycache__` |
| Parity check a archivo | hay migración nueva |
| Plantado de los 10 defectos | matriz commiteada antes, cierre por sha256 |
| Pantalla | las dos vías, con y sin impuestos, **y una organización que no sea SAC** para ver que el formulario no cambió |

---

## 8. Fuera de alcance, declarado

1. **El IVA descontable en compras.** Si un proveedor le factura IVA a SAC es un activo, y hoy no existe. Nadie lo pidió.
2. **Emitir la factura electrónica.** D1.
3. **Conciliar contra Siigo.** El número de factura amarra los dos, pero nadie compara los totales. Si divergen, no hay alarma.
4. **Corregir las tres tarifas sembradas.** Se ajustan desde la pantalla y el sembrado no las pisa.
5. **El resto de las organizaciones.** Todo detrás de la bandera.

---

## 9. Lo que queda abierto con el cliente

1. **Qué tarifas configurar exactamente.** Las facturas dan cuatro combinaciones: retefuente 2,5 y 4, ICA 1,1 y 1,25. Si hay más conceptos, aparecerán; el catálogo los admite sin código.
2. **Si hay ventas sin IVA y cuáles.** Daniel lo anticipó. El diseño ya las soporta, pero saber cuáles son ayuda a no configurar de más.
3. **Q-37 sigue reabierta** y este ciclo no la toca.
