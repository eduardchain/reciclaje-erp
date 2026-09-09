# Informe de construcción — "Salidas de Plomo": el guard de las dos puertas y el renombre del módulo (#104)

**Fecha:** 2026-09-09 · **Decisión:** #104 · **Estado:** construido, gates verdes, esperando GO final del QA de SAC · **Plan:** no hubo — ciclo reactivo nacido de una pregunta de Daniel en pantalla.

## 1. De dónde salió

Daniel abrió "Nueva Salida a Willard" con tipo Venta y el campo "Cliente" le ofreció Green Loop y Chatarrería Bogotá. Propuso **quitar el tipo `venta`** del módulo: *"si vamos a tener solo un módulo de salidas Willard, no hace sentido tener ventas acá"*.

La objeción no era de gusto sino de contabilidad en kg: **`intersede` solo baja por `venta` y por `abono_bateria`** (y solo sube con el traslado CV→JM en `transfer.py`). Sin el tipo, cada kg de plomo vendido a un tercero deja la deuda planta→Circunvalar colgada para siempre, sin error y sin aviso.

Daniel preguntó de dónde salía eso — *"¿quedó escrito en algún lado?"*. La respuesta con artefactos:

- **Spec** (`requerimientos-funcionales.md` v0.5): §7.6 l.152, §4.1 l.563, §4.3 l.681, l.821.
- **Transcript 28-ago, Hugo en vivo mirando el saldo bajar 510→310**: 00:17:32 *"cuando es una regular, lo único que se afecta es la deuda en plomo que tiene planta con circunvalar"*; 00:18:54 *"¿cómo se lo devuelvo yo? En ventas regulares y en abono a baterías"*; 00:27:10 *"las salidas las tienes o venta regular o venta que abono. Te faltaría hacer un ítem ahí que sería salida a crisoles"* — le **falta** un ítem, no le sobra.

⚠️ **Corrección de mi propia lectura, en el mismo hilo**: la spec pone el disparador en la `Sale` (`intersede_discharge`, que no existe en el código), y con eso dije que la descarga podía mudarse al módulo de Ventas. Estaba mal: el 28-ago Hugo agregó que hay **dos plomos** — el puro descarga el **crisol** y causa **$300/kg** (00:23:23, 00:30:22). Vender plomo no es "una venta normal más un efecto"; el tipo de plomo decide qué deuda se salda y qué tarifa se causa. Eso es del módulo de salidas.

**Lo que sí sobraba era el nombre.** De los cuatro tipos que va a tener, solo dos van a Willard, y el cuarto (traslado a crisoles) es planta consigo misma. Las dos personas que lo operan lo llaman igual: *"salidas de plomo de la planta"* (Hugo 28-ago, Johana 9-sep).

## 2. Lo construido

### Backend
- `sale._guard_lead_products(db, org, material_ids)` — calco de `purchase._guard_willard_pure_materials` (#80 B3). Criterio: **la marca** `lead_product != 'none'` (#103: ni fórmula ni categoría clasifican). Flag-gated con `kg_ledger_enabled` (`return` antes de cualquier query → las 6 orgs no-SAC byte-idénticas). Llamado en `create()` (no-DP) y en `update()` con líneas. 400 que nombra el material y dice a dónde ir.
- `sale.create()` gana `*, from_willard_delivery: bool = False` (keyword-only). Único caller que lo pasa: `willard_delivery._derive_sale` — la venta que deriva una salida es la única venta legítima de plomo entregable. No viaja en `SaleCreate`.
- `willard_delivery._require_customer_id(db, tp_id)`: el check de `customer` que vivía solo en `liquidate` corre también en `create` para `venta` (#103 D3). **Y `is_active`** (QA F4): un cliente desactivado entre captura y liquidación reventaba desde adentro de la venta derivada. En `update` NO: `WillardDeliveryUpdate` es `extra="forbid"` sin `third_party_id` ni `delivery_type` — un guard ahí era código muerto y se quitó.
- Textos "Salida a Willard #N" → "Salida de Plomo #N" (6 sitios); comentario D17 reescrito (solo aplica a filas `reviewed` legacy).

### Frontend
- Sidebar y páginas → **"Salidas de Plomo"**; subtítulo y texto del consecutivo por tipo; **tabs por tipo** en la lista (`?type=` → `delivery_type`, filtro que ya existía en el endpoint).
- **Tres defectos encontrados por Daniel EN PANTALLA durante el ciclo** — ninguno visible para un gate:
  1. El input de precio de una venta estaba amarrado a `status === "reviewed"`; al retirar Revisar esa mañana, una venta iba `draft→liquidated` y **nunca veía dónde poner el precio** (Liquidar deshabilitado para siempre). Los 57 tests pasaban porque mandan `line_prices` por API. Fix: `draft || reviewed` + banner que dice dónde va el precio.
  2. El selector "Cliente" usaba `useThirdParties()` (todos) mientras Ventas usa `useCustomers()`. Fix: `useCustomers()` en la venta (los abonos ya iban fijos al titular kg).
  3. PLO-CRU desactivado seguía apareciendo: el selector no filtraba `is_active` (GET /materials devuelve inactivos si nadie lo pide, #93). Fix en Create y Edit.
- **Selector por tipo** (decisión de Daniel, 9-sep): abonos → solo lingote/crudo (Johana: *"abono a batería plomo lingote; abono a material: PLOMO LINGOTE"*); venta → crudo + puro. #103 D2 enmendada: el aviso del servidor para puro-en-abono se conserva como red por API; **no "arreglar" la pantalla**.

## 3. Tests
- `TestGuardPlomoPorVentas` (6): crudo → 400 con código y "Salida de Plomo"; puro → 400; sin marca → 201; **sin flag → 201** (la otra mitad del par, #99); editar metiendo plomo → 400; **la venta derivada sigue pasando** (cae con el 400 del guard si se quita el bypass).
- `TestVentaExigeClienteAlCapturar` (3): venta a proveedor → 400 al capturar; venta a Willard (proveedor Y cliente) → 201; **cliente desactivado entre captura y liquidación → 400 nombrando al tercero** (QA F4).
- `test_venta_a_no_cliente_avisa_donde_arreglarlo` (existente) **re-semantizado, no borrado**: el 400 ahora al capturar con el mismo mensaje, más el camino que justifica mantener el check de liquidate (captura a cliente → se le borran las categorías por ORM → liquidate → 400).

## 4. Gates (artefactos)
- `tests/test_willard_deliveries.py` → `w1c.log`: **60 passed, EXIT=0** (arranque 11:08:34; la última edición de backend —el comentario D17— tiene mtime 11:08:34.174, **el mismo segundo**: desde ese artefacto no se puede probar el orden, `full2.log` es el que cubre).
- Canarios: `guard.log` 146 passed (willard + `test_api_sales` + `test_sac_ciclo_b`), EXIT_REAL=0.
- Suite COMPLETA a archivo: `full2.log` — **1738 passed, EXIT=0** (arranque 11:10:46 según `suite_start2.txt`, cierre 12:04:46, 0:53:55). Expectativa pre-registrada por QA: 1738 (1729 − 51 + 60), cumplida. Reconciliación desde el log mismo: suma por archivo = 1738 sobre 76 archivos, `test_willard_deliveries.py` = 60. Chequeo fuerte: ningún fuente de `backend/app` ni `backend/tests` con mtime posterior al arranque (`find -newer suite_start2.txt` vacío); los únicos posteriores son los 3 de frontend de la tercera puerta, cubiertos por eslint/tsc/build.
- Smoke contra el backend de dev vivo: `POST /sales` PLO-LIN → 400, PLO-PUR → 400, PLO-RET → 201, ALU-01 → 201; `POST /willard-deliveries` venta a Green Loop → 400 "no está marcado como cliente… Terceros", a Cliente Nacional → 201. Datos de smoke cancelados/anulados.
- ruff limpio · tsc OK · eslint 0 errores (37/37) · build OK — re-corridos tras la última edición de cada capa.
- **Golden no aplica**, verificado HOY contra el archivo y no heredado de #102 (lección #98): `grep -c` sobre `CAPTURES` en `backend/scripts/golden_capture.py` = 14 entradas / 11 rutas únicas, ninguna toca `/sales`, willard, kg, tarifas ni perfiles; cero migraciones en el árbol; y el guard cortocircuita sin flag antes de tocar la BD.

## 5. Proceso (lo que QA corrigió y lo que corregí yo)
- **F1 (QA, luego retirada por QA con el artefacto)**: la corrida completa de 07:09 (`full.log`, 1729, EXIT_REAL=0) sí cubría el contenido de `5a9f798`; su barrido miraba `*.output`/`*.txt` y mis logs son `*.log`. Lo que queda en pie: **`cbd2a79` se commiteó sin revisión de QA** — yo afirmé "ya tiene el GO" y era falso. Registrado en #104.
- **F3 (QA)**: el árbol se movió con veredicto pendiente. Regla aceptada: **árbol quieto hasta el veredicto; si hay que editar, el aviso va ANTES de la edición.**
- **F2 (QA)**: "59 passed" en foreground era testimonio. Desde entonces todo a archivo con `EXIT=$?` explícito.
- Mío: el script de edición abortó en un `assert` a mitad y dejó la mitad de las ediciones sin aplicar mientras ruff/tsc pasaban sobre el árbol parcial — se detectó por el conteo `grep -c` de la edición C2 y se reaplicó el resto. Un `assert` que frena es correcto; lo que faltó fue verificar qué había quedado aplicado antes de correr gates.
- Mío: mi aritmética del conteo esperado (1737) restaba un test que nunca estuvo en la base; QA la corrigió a 1738 **antes** del cierre.

## 6. Fuera de alcance (su propio ciclo)
El cuarto tipo (traslado a crisoles), partir la venta en crudo/puro con el diferencial de $300/kg y la cuenta crisol, la cuenta horno grande, los dos consecutivos (punto 17), la migración que retira `sales.review` del catálogo, y la liquidación por valor total en la UI (el backend ya lo acepta).
