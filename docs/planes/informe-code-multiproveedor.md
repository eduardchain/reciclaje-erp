# Informe CODE — Multi-proveedor por línea en la Entrada (SAC)

**Fecha:** 2026-08-04. **Plan:** `plan-sac-multiproveedor-por-linea.md` **v1.2** (micro-QA 🟢 GO condicionado, 4 condiciones cerradas). **Decisión:** #89 en CLAUDE.md. Sin commit — quedan pruebas de Daniel.

Una Entrada deja de tener **un** proveedor en la cabecera y pasa a tener **un proveedor por línea de material**. De una sola Entrada derivan **N compras**, una por proveedor, cada una con su remisión, su liquidación, sus retenciones y su saldo. Ingrid liquida de a una y la Entrada muestra **"Parcial"** hasta terminar.

---

## 1. Qué se construyó (mapa de archivos)

**Backend:**
- `app/models/inbound_order.py`: **`InboundOrderPurchase`** (tabla puente, `inbound_order_id`+`purchase_id` ambos PK, `UNIQUE(purchase_id)`, CASCADE en las dos FKs) + relación `InboundOrder.purchases` (`secondary`, `viewonly`, ordenada por `purchase_number`); `inbound_orders.third_party_id` → **nullable** (proveedor de cabecera solo si todas las líneas comparten uno); `inbound_orders.purchase_id` marcada **INERTE** en el `comment`; `InboundOrderLine.third_party_id` **NOT NULL** + índice + relación.
- `alembic/versions/f7a8b9c0d1e2_sac_multiproveedor_por_linea.py`: crea la puente, backfillea desde `inbound_orders.purchase_id`, agrega la columna de línea nullable → backfill desde la cabecera → `SET NOT NULL`, y afloja la cabecera. **Cero tablas compartidas tocadas.** Docstring con el SQL de la condición 2 de QA y la advertencia del downgrade.
- `app/services/inbound_order.py` (+620 líneas): `_resolve_line_suppliers`, `_homogeneous_supplier`, `_resolve_supplier_invoices`, `_group_lines_by_supplier`, `_link_purchase`, `_derive_purchases`, `_group_signature`, `_apply_supplier_invoices`, `_reapply_purchase_groups`; `display_status_of` con el cuarto valor; `get_multi` con `_has_purchase(*conds)` (EXISTS).
- `app/schemas/inbound_order.py`: `InboundOrderLineCreate.third_party_id` opcional, `SupplierInvoice`, `supplier_invoices[]` en create y update, `InboundOrderSupplierGroup`, `supplier_count`, `suppliers[]`, `display_status` con `partially_liquidated`.
- `app/api/v1/endpoints/inbound_orders.py`: `_enrich` arma los grupos, `invoice_number` condicional por tipo, `collector_commission_total` suma sobre todas las compras vivas, `display_status` como Query ampliado.
- **Caminos compartidos (D11):** `endpoints/purchases.py` (`_inbound_origin_map`) y `services/purchase.py` (guard D7b + origen de la comisión del recolector) pasan a leer la puente.
- `app/services/purchase.py`: `update()` gana `commit: bool = True` (patrón #75 D7) para que la re-derivación por grupo corra en una sola transacción.

**Frontend:** `types/inbound-order.ts` (línea con proveedor, `SupplierInvoice`, `InboundOrderSupplierGroup`, `InboundDisplayStatus` de 4 valores), `services/inboundOrders.ts`, y las 4 páginas — captura con interruptor "un solo proveedor / varios" y remisión por proveedor; edición con proveedor y precio por línea, grupos liquidados deshabilitados y remisiones por proveedor; detalle con tarjetas por proveedor y **Liquidar por grupo**; listado con "Varios (N)", tab "Parciales" y `Liquidar (N)`.

---

## 2. Las cuatro decisiones que cargan el ciclo

**D2 — tabla puente en vez de columna en `purchases`.** Es la enmienda que pidió Daniel (*"hay que ser cuidadoso que esto afecte solo a SAC"*). `purchases` la comparten las 7 organizaciones; `inbound_order_purchases` es exclusiva de SAC. La no-regresión deja de ser un argumento y pasa a ser una propiedad del esquema: **la migración no toca ninguna tabla compartida**.

**D3 — el listado no puede usar `join`.** El vínculo era 1:1 y el `outerjoin(Purchase)` era seguro; con 1:N una entrada de 12 proveedores saldría **12 veces** en la bandeja y la paginación perdería filas. Todo el filtrado de estado se reescribió con `EXISTS`/`NOT EXISTS`. Test bloqueante `test_twelve_suppliers_appear_once`.

**D4 — `partially_liquidated`.** Estado derivado sobre las compras vivas: ninguna liquidada → registrada; todas → liquidada; algunas → parcial; ninguna viva → anulada. El espejo Python↔SQL tiene test de paridad bloqueante (`test_filter_parity_with_field`) porque son dos implementaciones de la misma regla.

**D1 — la línea es la fuente de verdad.** `inbound_order_lines.third_party_id` es NOT NULL siempre; la cabecera guarda el proveedor solo cuando es homogéneo y **nunca se lee para efectos**. Mata de raíz la clase de bug "¿cuál de los dos leo?" en los ~19 sitios que tocan el proveedor de una entrada.

---

## 3. Cómo se cerraron las condiciones del GO de QA

| Condición | Cierre |
|---|---|
| **1 — Johana: ¿ruta Willard multi-proveedor?** | Respondida por Daniel: *"no, willard es un solo proveedor (willard)"*. D9 (multi solo en tipo compra) queda firme; guard con test `test_willard_with_two_suppliers_422`. |
| **2 — Canon a v0.6 en los DOS lugares** | `requerimientos-funcionales.md` v0.5 → **v0.6**: §7.3 reescrito con el argumento H1 (*"la regla se relaja únicamente en compra regular de chatarra y se conserva intacta donde vive su razón"*) y la tabla de actores corregida. De paso se corrigieron 8 afirmaciones obsoletas sobre la comisión de Green Loop (QA había encontrado 2). |
| **3 — Encuadre: SAC ya es producción** | Las 3 condiciones del backfill quedaron en §7.1 del plan como gate de deploy, y la 3ª (downgrade) además en el docstring de la migración. |
| **4 — H2, conteos** | Organizaciones: confirmado. Catálogo de movimientos: la discrepancia 45 vs 47 venía del árbol de trabajo sucio del otro agente; tras `158e8a0` el 47 es correcto en HEAD. La afirmación se reformuló sin número. |

**H1 adoptado íntegro.** C1 y C3 eran la misma pregunta y **#80 —ya desplegada— la contesta**: el canal Willard ya está separado del de compras por construcción. La lectura de QA era mejor que la del plan v1.0 y así quedó escrita.

---

## 4. D11 — los dos caminos compartidos, probados y no argumentados

La puente elimina el riesgo de esquema, pero dos funciones corren hoy para **todas** las organizaciones y necesariamente cambian de tabla consultada:

| Función | Corre en | Cambio |
|---|---|---|
| `_inbound_origin_map` (`endpoints/purchases.py`) | cada listado de compras de cada organización, sin gate de flag | lee la puente en vez de `inbound_orders.purchase_id` |
| Guard D7b (`services/purchase.py`) | cada cancelación de compra registrada de cada organización | join a la puente |

Una organización sin `kg_ledger_enabled` no tiene ni una fila en `inbound_orders` ni en la puente → resultado vacío antes y después. Eso es el **test 23** (`test_org_without_flag_sees_no_change`): organización sin flag, con compras, listadas y canceladas, response comparado campo por campo. Ambos sitios llevan comentario ⚠️ D11 marcándolos como camino compartido.

> **Re-QA N1 aplicado.** La v1 de este informe decía "ambas filtran por `organization_id`" y era impreciso: `_inbound_origin_map` sí, el guard D7b no —filtraba solo por `purchase_id` y `status != 'annulled'`. Era seguro (la compra ya se cargó con scope de organización y la puente tiene `UNIQUE(purchase_id)`), pero el scope era **implícito**, y la asimetría entre dos caminos que hacen lo mismo es lo que invita al error futuro. El guard ahora filtra `InboundOrder.organization_id` explícitamente: mismo resultado, defensa en profundidad, y los dos caminos se leen igual.

**Optimización deliberadamente NO incluida:** saltar `_inbound_origin_map` con el flag apagado ahorraría una consulta a las otras 6 organizaciones. Es una mejora real, pero es un cambio de comportamiento en camino compartido que este ciclo no pide.

---

## 5. Efectos que caen solos (y el que no)

- **Comisión del recolector (#83):** se causa dentro de `purchase.liquidate()`. Con N compras salen N causaciones sin tocar esa lógica — `test_commission_accrues_per_supplier`. La firma del `expense_accrual` (`source_id` = la entrada) pasó a resolverse por la puente.
- **Retenciones (#79):** por compra, o sea por proveedor — `test_retentions_are_per_supplier`.
- **Costo promedio:** `test_average_cost_identical_split_or_whole` clava que partir una entrada en 3 proveedores da **el mismo avg** que capturarla entera. La derivación no altera el modelo de costos.
- **El que no cae solo — edición (D7):** `_reapply_purchase_groups` re-arma **solo el grupo cuyas líneas cambiaron** (firma comparable por grupo); si el proveedor ya está liquidado, 422 nombrándolo. `test_edit_other_supplier_while_one_liquidated` es el que prueba que el grupo intacto no se toca.

> **Bug real encontrado al escribir ese test:** `_group_signature` comparaba `str(Decimal)` sin normalizar escala — la línea guardada (`Numeric(15,4)` → `'100.0000'`) nunca coincidía con la del payload (`'100'`), así que **toda** edición multi-proveedor reportaba "las líneas de X ya están liquidadas" aunque X no se hubiera tocado. Corregido cuantizando a la escala de la BD antes de comparar, con el porqué en el docstring.

---

## 6. Tests existentes que cambiaron (un test cambiado puede tapar una regresión)

Dos archivos previos se tocaron. Se listan aparte para que se puedan auditar sin buscarlos:

| Archivo | Cambio | Carácter |
|---|---|---|
| `test_sac_ajustes_0803.py` | 10 asserts `order.purchase` → `order.purchases[0]` | **Mecánico.** La relación 1:1 pasó a colección; ni un assert cambió de significado. |
| `test_inbound_orders.py` | `test_edit_purchase_type_lines_422` → **`test_edit_purchase_type_lines_reapplies`** | 🔴 **Re-semantizado: el 422 pasa a 200.** |

El segundo es el único cambio de contrato del ciclo y merece mirada de QA. Antes, editar las líneas de una entrada tipo compra se bloqueaba con 422 remitiendo a la compra derivada (D7b, "doble verdad prohibida"). Con multi-proveedor esa vía **ya no alcanza**: una compra pertenece a UN proveedor y no puede mover una línea a otro, así que reasignar el proveedor de una línea solo se puede hacer desde la entrada. El test nuevo verifica las dos mitades: las líneas ahora responden 200 y se re-aplican, **y la fecha sigue devolviendo 422** — o sea que D7b no se aflojó, se acotó exactamente a lo que sigue viviendo en la compra.

---

## 7. Evidencia de gates

| Gate | Resultado |
|---|---|
| Tests nuevos | **24/24 verdes** — `test_sac_multiproveedor.py` (estructura 5, estado derivado 7, edición y anulación 5, efectos 3, guards y aislamiento 4). Cuatro marcados 🔴 bloqueantes: paridad Python↔SQL, 12 proveedores una sola fila, organización sin flag sin cambio, avg idéntico. |
| Suite completa | **1492/1492 verdes** en 27:59 (1468 previos + 24 nuevos, **cero regresiones**, exit 0). |
| Migración | `alembic upgrade head` OK en dev(5434); **round-trip** `downgrade`+`upgrade` probado. La BD de test se recrea desde los modelos (alembic contra 5433 es no-op). |
| Schema parity | **Cero divergencias propias.** Quedan las **4** preexistentes que #87 ya documentó (renderings cosméticos de CHECKs de `kg_ledger_accounts` ×2, `material_kg_profiles` y `retention_configs`) — ninguna de este ciclo, que no crea ningún CHECK. |
| tsc / build | Limpios (`tsc --noEmit` exit 0; `vite build` 4.5s). |
| 390px | Patrones CLAUDE.md aplicados: `FormLineGrid` (`grid-cols-1` mobile), tarjetas por proveedor apiladas con `flex-col sm:flex-row`, botones `w-full sm:w-auto`, tabla de líneas con `overflow-x-auto -mx-3 sm:mx-0`, remisiones `w-full sm:w-56`. Verificación en DevTools durante las pruebas de Daniel. |

**No-regresión estructural:** la migración no toca ninguna tabla compartida; los dos caminos compartidos leen una tabla vacía en las otras 6 organizaciones (test 23); una entrada de un solo proveedor recorre exactamente el camino de hoy (`test_single_supplier_behaves_exactly_as_before`).

> **Lo que atrapó el parity check** (y no se habría visto a ojo): la migración creaba el índice de `inbound_order_id` pero no el de `organization_id`, que `OrganizationMixin` declara con `index=True` y `create_all` sí crea. Producción habría quedado sin ese índice —silenciosamente, porque nada falla sin él— y con el esquema divergiendo del modelo. Corregido y verificado con un `downgrade`+`upgrade` completo.

**Tres lugares del frontend leían campos compat que solo se llenan con UNA compra viva** (`purchase_id`/`purchase_number`/`purchase_status`): el diálogo de anular, el bloqueo del selector de recolector y la ruta del botón Liquidar. Con varias compras esos campos son `null` — no rompían, **mentían**: el diálogo ofrecía anular una entrada con compras liquidadas (que el backend rechaza) y prometía cancelar "la compra #(vacío)". Los tres pasan a leer `suppliers[]`.

---

## 8. Antes del deploy — las 3 condiciones del backfill (§7.1 del plan)

1. **Backup completo de producción.** Ya está en `/deploy`; acá es bloqueante: sin backup verde, no se migra.
2. **Verificar el conteo por organización** con el SQL del docstring de la migración. La premisa es que **solo SAC aparece** en `inbound_orders` / `inbound_order_lines`. Si aparece otra, la migración **se detiene**.
3. **Downgrade:** revertir **solo antes de que se capture la primera entrada multi-proveedor**. Después, el camino es hacia adelante — sus líneas conservarían el proveedor pero la cabecera quedaría NULL, estado que el código anterior no espera.

   **Re-QA N2 — la ventana se pregunta, no se recuerda.** Se cierra sola con el uso y nada en el código la vigila. Antes de intentar cualquier `downgrade`, correr:

   ```sql
   SELECT COUNT(*) FROM inbound_orders io
   WHERE (SELECT COUNT(DISTINCT third_party_id)
          FROM inbound_order_lines WHERE inbound_order_id = io.id) > 1;
   ```

   `> 0` ⇒ la ventana ya se cerró y revertir perdería proveedores. Mismo criterio empírico que la condición 2: contar en vez de asumir. Está también en el docstring de la migración, que es donde lo va a leer quien esté por revertir.

**La ventana es ahora:** `inbound_orders` lleva días de datos reales y solo en SAC. En tres meses el backfill son miles de filas con retenciones y pagos encima.

---

## 9. Fuera de alcance (declarado)

Liquidación **en bloque** de las N compras (la reunión pidió capturar rápido, no liquidar rápido — ciclo propio si lo piden al usarlo); el estado **"revisada"** (bloqueado por usuarios faltantes); el camino **Willard** completo; el consecutivo de arranque configurable.
