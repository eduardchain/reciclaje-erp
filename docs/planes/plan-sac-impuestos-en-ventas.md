# Plan — IVA y retenciones en lo que SAC factura (CC-013 / Q-41)

**Estado:** v1.0, para revisión de QA. Nada construido.
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

### D4 — Entidades separadas, y el balance las ubica por signo
Son dos cuentas contables distintas y juntarlas las netearía:

| Concepto | Qué es | Entidad | Saldo |
|---|---|---|---|
| IVA generado | SAC le debe a la DIAN | `[Impuestos] IVA por Pagar` | en contra |
| Retención practicada a SAC | SAC ya pagó impuesto | `[Impuestos] ReteFuente a Favor`, etc. | a favor |

**Medido, no supuesto**: `_classify_third_party` manda una entidad `liability` con saldo a favor a `liability_advances`, que es **activo**, y con saldo en contra a `liability_debt`, que es **pasivo**. O sea que el balance ya las ubica bien por signo, sin tocar el clasificador.

⚠️ Y por eso las entidades de venta son **distintas** de las de compra: la retefuente que SAC practica a un chatarrero es un pasivo, y la que Willard le practica a SAC es un activo. Reutilizar `[Retenciones] ReteFuente` para las dos las netearía y perdería la distinción.

### D5 — La base se declara, no se asume
`base_amount` se persiste siempre, y **cada tipo dice sobre qué se aplica**: retefuente e ICA sobre el subtotal, reteIVA sobre el IVA. El precálculo del frontend usa la base correcta.

Sin esto, la reteIVA se podría configurar como "2,85 % del subtotal" y daría el número correcto **solo mientras el IVA sea 19 %**. El día que cambie, el número queda mal en silencio. Un valor que parece configuración y es en realidad otra fórmula.

### D6 — El IVA se precalcula por línea
Redondeando cada línea y sumando, que es lo que hace Siigo. Con el sistema registrando, el precálculo es una ayuda y el usuario podría corregir el centavo a mano; hacerlo bien cuesta lo mismo y evita esa fricción todos los días.

### D7 — Cero efecto en el P&L
El IVA no es ingreso y la retención no es gasto. `sale.total_amount` sigue siendo el subtotal, que es lo que el P&L lee. **Test de oro**: el P&L de un período es idéntico antes y después de agregarle impuestos a una venta.

### D8 — El concepto se deriva donde se puede
Venta de un bien → concepto de venta; maquila y flete → concepto de servicios. El usuario lo puede cambiar. Derivarlo es menos superficie y menos error que preguntarlo, y las facturas muestran que la correspondencia es estable.

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

| | T1 conservación | T2 sin impuestos = hoy | T3 base de reteIVA | T4 P&L intacto | T5 balance por signo | T6 anulación | T7 sin flag | T8 permiso | T9 por línea | G pantalla |
|---|---|---|---|---|---|---|---|---|---|---|
| P1 el IVA no acredita al cliente | cae | — | — | — | cae | — | — | — | — | — |
| P2 la retención suma en vez de restar | cae | — | — | — | cae | — | — | — | — | — |
| P3 reteIVA sobre el subtotal | — | — | **cae** | — | — | — | — | — | — | — |
| P4 el IVA entra a `total_amount` | — | — | — | **cae** | — | — | — | — | — | — |
| P5 la entidad a favor nace `liability` en contra | — | — | — | — | **cae** | — | — | — | — | — |
| P6 la anulación no revierte | — | — | — | — | — | **cae** | — | — | — | — |
| P7 sin bandera el payload pasa | — | **cae** | — | — | — | — | **cae** | — | — | — |
| P8 el permiso cambia a solo lectura | — | — | — | — | — | — | — | **cae** | — | — |
| P9 el IVA se precalcula sobre el total | — | — | — | — | — | — | — | — | **cae** | — |
| P10 el formulario compartido pide impuestos sin bandera | — | — | — | — | — | — | — | — | — | **cae, y solo acá** |

**T8 se escribe con el control positivo de #111**: un rol con lectura y sin gestión, que debe **leer en 200** antes de que se le niegue la escritura. Sin ese 200, el 403 puede venir de la bandera y el test no prueba el permiso.

---

## 7. Gates

| Gate | Por qué |
|---|---|
| **Golden ×3 organizaciones** | **Gate duro.** El saldo de terceros y el balance cambian de forma. Control positivo obligatorio: se declara **antes** cuántas claves aditivas se esperan y en qué capturas, y una prueba de vida que demuestre que los dos puertos corren códigos distintos (#110) |
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
