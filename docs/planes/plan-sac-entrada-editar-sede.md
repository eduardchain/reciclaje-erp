# Plan — Editar la sede de una Entrada registrada o revisada (SAC)

**Versión:** v1.2 (C1–C4 y O2/O3 de QA; addendum PDF en §7) · **Fecha:** 2026-11-19 · **Nivel:** lógica · **Base:** `325eabf`

**Pedido.** Johana, por Daniel: se equivocó de sede en algunas Entradas y el sistema no le deja corregirla. Hoy la sede no se puede cambiar:
- `InboundOrderUpdate` no tiene `warehouse_id` y, con `extra="forbid"`, el servidor responde 422;
- la pantalla de edición la muestra como texto fijo, con la nota «Tipo y sede son inmutables».

**Decisiones de Daniel (19-nov, por la ventanita):**
- **D1.** Una Entrada desliquidada (revisada, con compras vivas) se **bloquea con aviso**: anular y registrar de nuevo.
- **D2.** Cambiar la sede de una Entrada revisada **no** la devuelve a Registrada. La revisión certifica pesos y cantidades, y la sede es cabecera, que es el mismo criterio de D17 (#95).

## 1. Alcance

| Caso | Hoy | Después |
|---|---|---|
| Compra, `draft` o `reviewed`, sin compras vivas | 422 | **Se cambia.** Cero efectos que revertir (D9 de #93) |
| Compra `reviewed` **con** compras vivas (desliquidada, o legacy 1:1) | 422 | **422** que nombra las compras (D1) |
| Compra `liquidated` | 422 | **422** «revierta la liquidación…», que de todos modos cae en D1 |
| Willard `draft` o `reviewed` | 422 | **Se cambia**, revalidando la captura con la sede nueva (`_validate_willard_capture`: drosses solo en planta; postconsumo solo en una bodega con cuenta de baterías cuyo titular sea el tercero) |
| Willard `confirmed` | 422 | **422**: mover kilos e inventario ya confirmados es anular y registrar de nuevo |
| Anulada | 404 | 404, sin cambio |

## 2. Backend

1. **`InboundOrderUpdate`:** se agrega `warehouse_id: Optional[UUID] = None` y se corrige el docstring («warehouse inmutable»).
2. **`InboundOrderService.update`:** con `"warehouse_id" in fields_set` y un valor distinto del actual, ANTES de los bloques de líneas:
   - `None` explícito da 422 «la sede es obligatoria».
   - Un estado distinto de `draft`/`reviewed` da 422 y el mensaje depende del tipo.
   - En tipo compra, `_linked_purchases` con alguna no `cancelled` da 422 con los números de compra (D1). El puente cubre también el legacy 1:1, porque el backfill de #93 lo creó.
   - `_validate_warehouse`: existencia, org, activa y receptora (la de tránsito no es receptora). Es el mismo validador de `create`.
   - Se asigna `order.warehouse_id`. En Willard, si no vienen `lines` en el payload, se corre `_validate_willard_capture` con las líneas persistidas. Si vienen, el bloque existente ya valida con `order.warehouse_id`, que ahora es la sede nueva.
   - **No** se decertifica (D2).
   - El guard va ANTES del bloque del recolector (O3). Su comentario explica por qué D1 es necesario: `purchase_signature` no incluye la bodega, así que una compra viva con la firma igual se reusaría con sus líneas en la sede vieja.
3. Un mismo `warehouse_id` que el actual es un no-op: no valida ni cambia nada, igual que los demás campos.
4. Sin migración, sin permisos nuevos y sin tablas compartidas. El router es exclusivo de SAC y está detrás del flag.

**Por qué la liquidación posterior queda bien sola.** Las compras nacen en `liquidate` con `warehouse_id=order.warehouse_id` (cabecera y líneas), y el descuadre también se lee de la cabecera. Cambiada la sede antes de liquidar, todo nace en la sede nueva. T1 lo afirma.

## 3. Frontend (`InboundEditPage`)

- Tipo compra no liquidada, no legacy y sin compras vivas (`order.purchases` con alguna `status !== "cancelled"`): un selector «Sede / Bodega» con las bodegas receptoras (`useWarehouses` filtrado por `is_receiving !== false`, como en Crear). Se manda en el payload solo si cambió.
- Willard: la sede sigue como texto. En SAC hay una sola sede válida por mundo (drosses → planta; baterías → la única bodega con cuenta de baterías), así que el backend la acepta y la revalida, pero la pantalla no la ofrece. Queda declarado.
- La nota pasa a decir «El tipo no se cambia; la sede se corrige mientras la entrada no esté liquidada», con la variante para desliquidada o Willard.
- A 390 px: el selector es `w-full`, dentro del grid de cabecera que ya existe.

## 4. Tests — `tests/test_sac_entrada_editar_sede.py` (nuevo)

| T | Caso | Afirma |
|---|---|---|
| T1 | Compra `draft`: cambio de sede y después revisar y liquidar, **con descuadre y comisión del recolector** (C1) | 200; el GET devuelve la sede nueva; las compras nacen con `warehouse_id` = sede nueva (cabecera **y** líneas); el ajuste de descuadre y el `MoneyMovement` de la comisión llevan la sede nueva; `SUM(inventory_movements)` da lo liquidado más el descuadre en la nueva y 0 en la vieja |
| T2 | Compra `reviewed`: cambio de sede | 200, **sigue `reviewed`** (D2) |
| T3 | Compra `liquidated` | 422 con el TEXTO del guard de estado (C2, no el de D1); sede intacta (leída por GET) |
| T4 | Compra desliquidada | 422 que nombra la compra; sede intacta |
| T5 | Bodega no receptora / inactiva / de otra org | 422 / 400 / 404; sede intacta |
| T6 | `warehouse_id: null` | 422; sede intacta |
| T7 | Willard drosses `draft` hacia una sede que no es planta | 422 con el mensaje de sede; intacta |
| T7b | Willard postconsumo `draft` hacia una bodega sin cuenta de baterías | 422 con el texto del revalidador (O2); intacta. Y control positivo: hacia otra bodega con cuenta del mismo titular, 200 |
| T7c | Willard `draft`: `lines` y sede nueva en el mismo PATCH, hacia una sede inválida (O3) | 422 del revalidador; intacta |
| T8 | Willard `confirmed` hacia un destino donde `_validate_willard_capture` PASARÍA (C2) | 422 del guard de estado; intacta |
| T9 | Entrada `liquidated` con `{notes, warehouse_id: la misma}` (C3) | 200, nota guardada y sede igual (comparación con `str()` en los dos lados) |

Lo de RBAC no aplica, porque no hay permisos nuevos: el PATCH ya exige `purchases.edit`.

## 5. Matriz de plantado (predicciones escritas antes)

| P | Defecto | Predicción |
|---|---|---|
| P1 | Se acepta `warehouse_id` pero nunca se asigna | T1, T2, T7b (mitad positiva) |
| P2 | Sin el guard de estado | T3, T8 |
| P3 | Sin el guard D1 (compras vivas) | T4 |
| P4 | Sin `_validate_warehouse` | T5 |
| P5 | Willard sin revalidar la captura | T7, T7b (mitad negativa) |
| P6 | Se decertifica al cambiar la sede | T2 |
| P7 | `None` explícito aceptado | T6 (probablemente con 500 por NOT NULL, O2) |
| P9 | `_change_warehouse` movida debajo de los bloques de líneas (O3) | T7c |
| P8 | Comparar sin el «distinto» (todo `warehouse_id` dispara los guards) | T9 |

## 6. Gates

- **Estáticos:** ruff, tsc, eslint (techo 37), build.
- **Dirigidas:** el archivo nuevo más `test_inbound_orders.py`, `test_sac_entrada_sin_proveedor.py`, `test_sac_ciclo_b.py`, `test_sac_ciclo_c.py`, `test_sac_entradas_remision.py`, `test_sac_ajustes_0803.py` y `test_sac_ciclo_d.py` (C4).
- **Plantado:** según §5.
- **Suite completa:** a archivo, con la predicción escrita antes.
- **Golden: no aplica, medido.** `grep -c inbound backend/scripts/golden_capture.py` = 0, y el ciclo no toca código compartido.
- **Pantalla:** Daniel en localhost, a 1440 y 390.

## 7. Addendum — PDF de compra de SAC (pedido de Johana, 19-nov)

Johana: «cambiar ese encabezado que solamente diga SAC y que donde dice compra número tal no diga sino entrada número tal y que el número sea el que yo coloco en remisión».

**Decisiones de Daniel (ventanita, 19-nov):**
- **D3.** El encabezado dice solo el nombre de la org, sin «EcoBalance ERP -», en **todos** los PDF y **solo en SAC**, es decir con `kg_ledger_enabled`. Costa y Meta siguen igual.
- **D4.** Si la Entrada no tiene remisión, el título dice «Entrada (sin remisión)».
- **D5.** El PDF **no** lleva el número de compra. QA propuso conservar una línea «Compra #N» para conciliar contra el estado de cuenta, y Daniel eligió quitarlo. Queda como decisión escrita.

**Condiciones de QA (GO de plan con A1–A4):**
- **A1.** Commit y pasada aparte, después del commit de la sede.
- **A2.** Función pura `pdfTitle(orgName, isSac)`, con el hook como envoltorio llamado arriba del componente. Sin el flag sale idéntico a hoy, incluido el nombre vacío, que da «EcoBalance ERP». Con el flag y el nombre vacío también da «EcoBalance ERP». Se miden las cuatro combinaciones.
- **A3.** La remisión vacía se define como en #117 (trim): «  » cuenta como sin remisión. El nombre del archivo se sanea como el `safeName` del estado de cuenta, y se mide con una remisión con espacios y otra con «/».
- **A4.** Se mide con pypdf en los dos llamadores de compra (detalle y listado), con SAC y con una org sin flag. Sin el flag el resultado es byte a byte «EcoBalance ERP - <org>» y «Compra #N». Para los demás PDF basta uno de encabezado en cada mitad.

**Diseño:**
- **Backend.** `_inbound_origin_map` suma `InboundOrder.remission_number` y `PurchaseResponse` gana `inbound_remission_number`. Se llena en list y detail, y llega null sin Entrada.
- **Frontend.** Las 6 funciones de `pdfExport.ts` reciben el título armado, y los 10 llamadores pasan `usePdfTitle()`. Para la compra con Entrada, el título es «Entrada #<remisión>» o «Entrada (sin remisión)», y el archivo es `entrada_<remisión saneada | sin_remision>.pdf`.
- **Tests backend.** Una Entrada con remisión la devuelve en detail y en list; una Entrada sin remisión devuelve null; una compra directa también da null. Plantado: no seleccionar la columna hace caer los dos primeros.
- **Golden: no aplica, medido.** `/purchases` no está en CAPTURES.
