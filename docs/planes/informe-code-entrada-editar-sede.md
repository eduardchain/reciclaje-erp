# Informe de código — Editar la sede de una Entrada (SAC)

**Plan:** `docs/planes/plan-sac-entrada-editar-sede.md` v1.2 (§1–§6 sede; §7 addendum PDF, va en commit aparte por A1) · **Base:** 325eabf · **Nivel:** lógica
**Fecha:** 2026-11-19 · **QA:** «QA Ecobalance»

Johana, por Daniel, se equivocó de sede en algunas Entradas y no podía corregirla: la sede era inmutable, tanto en el schema (`extra="forbid"` → 422) como en la pantalla, donde aparecía como texto fijo. Daniel decidió por la ventanita:
- **D1.** Una desliquidada (revisada con compras vivas) responde 422 «anule y registre de nuevo».
- **D2.** Cambiar la sede no devuelve a Registrada.

QA dio el GO de plan condicionado a C1–C4 y Daniel autorizó construir.

## 1. Qué cambia

| Pieza | Archivo |
|---|---|
| `InboundOrderUpdate.warehouse_id` | `app/schemas/inbound_order.py` |
| `_change_warehouse`, llamado al inicio de `update` y solo si la sede es distinta | `app/services/inbound_order.py` |
| Selector «Sede» en Editar, solo para tipo compra sin efectos | `pages/inbound/InboundEditPage.tsx`, `types/inbound-order.ts` |
| 13 tests (T1–T9, T5 ×3, T7c) | `tests/test_sac_entrada_editar_sede.py` (nuevo) |

Sin migración, sin permisos nuevos y sin tablas compartidas. El router es exclusivo de SAC y está detrás del flag.

**Orden de los guards:**
1. `None` da 422 «obligatoria».
2. Un estado distinto de draft/reviewed da 422 «…liquidada/confirmada — la sede ya no se puede cambiar».
3. En tipo compra, si hay compras vivas por el puente, 422 «ya tuvo compras (#N)», que es D1. El comentario explica por qué hace falta: `purchase_signature` no incluye la bodega, así que re-liquidar reusaría la compra con sus líneas en la sede vieja.
4. `_validate_warehouse`, el mismo validador de `create`.
5. Asignación.
6. En Willard sin `lines`, se revalida la captura con la sede nueva.

**Dos reglas más:**
- La llamada va antes del bloque del recolector (O3) y de los bloques de líneas. Así, con `lines` en el payload, Willard valida contra la sede nueva (T7c).
- Reenviar la misma sede es un no-op (`str()` en los dos lados), así que no rompe la edición de notas de una liquidada (C3, T9).

**Pantalla.** El selector aparece solo con tipo compra en draft/reviewed, no legacy y sin compras vivas. Ofrece bodegas receptoras, el mismo filtro que Crear. En Willard la sede sigue como texto, porque en SAC hay una sola sede válida por mundo; el servidor igual la acepta y la revalida.

## 2. Gates

Logs en `~/sac-evidencia/2026-11-19/editar-sede/`.

**Estáticos:** ruff limpio en app y tests; tsc 0; eslint 37, igual al techo.

**Plantado P1–P9** (`plantado_run.log`; predicciones en `plantado_predicciones.md`, escritas antes). Respaldo por ruta, .pyc borrado, `PYTHONDONTWRITEBYTECODE=1`. Sha del servicio igual antes y después (`2af3dbf1…f7343`). **9 de 9 en la diagonal**:

| P | Defecto | Cayeron | Nota |
|---|---|---|---|
| P1 | No asigna | T1, T2, T7, T7b, T7c | T7c se agregó después de escribir la predicción de P1. Cae por el mismo mecanismo que T7: con la sede sin asignar, el revalidador corre contra la sede vieja, que es válida. Dirección barata |
| P2 | Sin guard de estado | T3, T8 | En T3 aparece el texto de D1, «ya tuvo compras»: C2 funcionó |
| P3 | Sin D1 | T4 | |
| P4 | Sin `_validate_warehouse` | T5 ×3 | Incluida la bodega de OTRA org, que sin el guard se aceptaba |
| P5 | Willard sin revalidar | T7, T7b | T7c no cae, como se predijo |
| P6 | Decertifica | T2 | |
| P7 | None aceptado | T6 | 404 «Bodega no encontrada», como anticipó QA (O1) |
| P8 | Sin el «distinto» | T9 | |
| P9 | Llamada debajo de los bloques de líneas | T7c | |

**Dirigidas** (`dirigidos.log`, con C4): 8 archivos, **241 passed, EXIT=0**, con la predicción tomada de collect-only. 0 FAILED/ERROR/Traceback.

**Suite completa:** `suite_sede.log`, ver §4.

**Golden: no aplica, medido.** `grep -c inbound backend/scripts/golden_capture.py` = 0, y el ciclo no toca código compartido.

## 3. Observaciones

- **Willard confirmada y tipo compra liquidada:** la sede no se cambia; se anulan y se registran de nuevo. Cambiarla movería inventario, kilos y plata ya registrados.
- **Desliquidadas (D1):** si Johana tiene alguna con la sede equivocada, el único camino es anularla y recrearla. Hoy no sé si existe alguna en producción.
- **Willard en pantalla:** la sede no se ofrece. Si algún día SAC tiene dos bodegas con cuenta de baterías del mismo titular, el selector se puede abrir para Willard con el filtro de Crear. El backend ya lo soporta (T7b, mitad positiva).

## 4. Suite completa

`suite_sede.log`, de 17:29:38 a 19:35:16 (2:05:23). Tardó casi el doble de lo normal por contención de CPU; la medición vale igual porque cierra con FIN, EXIT y conteo.

- **2161 passed, EXIT=0**, capturado dentro del bloque. Cero FAILED, ERROR o Traceback en todo el recorrido.
- **La predicción de 2161 se escribió antes**: está en `suite.sh` (17:29:37) y en la línea 2 del log («prediccion: 2161 passed»), impresa antes de pytest. `suite_prediccion.md` tiene el detalle, pero se escribió 15 s después del INICIO y no sirve como prueba de anterioridad. La predicción sale de dos mediciones. Primera: 2148 de `suite_remision.log` más los 13 items del archivo nuevo, con `git diff --name-only 919849a -- backend/tests` vacío. Segunda, independiente: `--collect-only`.
- **El árbol quedó quieto.** `ARBOL_FIN == ARBOL_INICIO` (`3257a978…26bb`). Archivos con mtime posterior al inicio: 0, con control positivo de 672.
- Antes de arrancar, 5433 tenía 0 sesiones.
