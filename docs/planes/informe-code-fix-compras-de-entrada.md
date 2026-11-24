# Informe — La compra de Entrada: el total al re-liquidar (#130) y las puertas de Compras

Autor: Eco Coder 2 · 23-nov-2026 · rama `coder-2/bug-total-reliquidar` (base develop `dea2320`)
Plan: `plan-fix-compras-de-entrada.md` v1.1 (`760aa82`, GO de Eco QA 2 `8dafe84e`; D1/D2 de Daniel y nota O4 en `75764be`). Nivel **lógica**.
Código en `6b206ab` (OK de commit de QA 2 sobre el árbol `7f27dad9`, veredicto `de7707b4`). Sin migración. Toca código compartido (`purchase.py`, dos pantallas de Compras); para Costa y Meta es byte a byte (B2, G1 = 0 compras con Entrada).

## Qué cambió

**A — el total viejo al re-liquidar (#130)** (`backend/app/services/purchase.py`, `update`)
- En la rama `commit=False`, después del `flush`, se expiran las colecciones que `update` reescribió con DELETE masivo + `db.add`: `lines` si llegaron líneas, `commissions` si llegaron comisiones. La próxima carga encuentra las filas nuevas.
- Antes, `liquidate` (que la Entrada llama justo después) recalculaba `total_amount` con las líneas viejas de la colección cargada y lo grababa: la compra y el saldo del proveedor quedaban con el total anterior. Medido con el mismo test temporal (`d7d5b321`) antes y después: `refresh ANTES` pasa de `lines=[100]` y 100.000 a `lines=[102]` y 102.000.
- La rama `commit=True` no cambia: ya hacía `commit` + `refresh`.

**B — liquidar o editar la compra por fuera de la Entrada**
- Helper `_linked_inbound_number(db, purchase_id)`: el mismo SELECT que vivía dentro de `cancel` (Entrada no anulada, por la puente), ahora UN predicado para las tres puertas.
- `liquidate` y `update` ganan el kwarg `from_inbound=False`. Sin él, una compra de Entrada da **400** «Esta compra pertenece a la Entrada #N — liquídela desde la Entrada» / «— corrija el reparto desde la Entrada». La excepción va por el kwarg y **nunca** por `commit=False` (P11).
- `inbound_order.py`: las dos llamadas de la Entrada (`update` de la re-liquidación y `liquidate`) pasan `from_inbound=True`. `cancel` ya lo pasaba.
- **D1 (Daniel):** editar se bloquea entero, ningún campo. Revierte el «se permite» de #75 D7b; `test_edit_derived_purchase_allowed` pasa a `_blocked`.
- **D2 (Daniel):** «Cancelar» también se oculta.
- Front: `PurchasesPage` (listado y card mobile, `ActionsCell`) y `PurchaseDetailPage` suman `!purchase.inbound_order_id` a `canEdit`, `canLiquidate` y `canCancel`. Queda el banner «Origen: Entrada #N».

**422 de la factura en la Entrada** (O3/O4): «La factura vive en el reparto de cada compra: escríbala al liquidar. Si la Entrada ya está liquidada, revierta la liquidación y vuelva a liquidar con la factura en el reparto; la liquidación quedará con la fecha del día en que vuelva a liquidar.»

## Desviaciones y pendientes

1. **O4 (declarada):** el texto del 422 menciona que re-liquidar fecha la liquidación con el día (D21 de #93). No estaba en la v1.1; lo pidió QA 2 en el GO para que el aviso no esconda el costo del camino que indica.
2. **O1 de QA 2 (declarado, no se corrige):** tras `update(commit=False)` con cambio de proveedor, la relación `purchase.supplier` queda con el objeto viejo en memoria. No es alcanzable desde la Entrada (un cambio de proveedor cancela la compra y crea otra, `inbound_order.py:869–870`) y el saldo va bien por el `refresh` del paso 4c (sonda de QA 2 `0f37c7ac`). No se tocó `app/` por algo inalcanzable.
3. **Rama legacy 1:1 de Entradas** (InboundDetailPage 384–389, InboundOrdersPage 245–249): sigue navegando a `/purchases/{id}/liquidate`, que ahora da 400. Es la del plan §B3; G3 midió 0 Entradas legacy en producción. No se toca.
4. **Deep-links** `/purchases/:id/edit` y `/liquidate` quedan vivos: por URL, el 400 sale como toast con el número de la Entrada. Esto es por construcción del hook (`getApiErrorMessage`); no hay captura que lo muestre.

## Gates (evidencia en `~/sac-evidencia/2026-11-23/bug-total-compra-130/coder2-construccion/`)

- **Construcción:** 19 tests nuevos o extendidos, todos con montos escritos a mano (`nuevos_r1.log`, 19 passed). La medición del mecanismo, repetida con el mismo test temporal, da `lines=[102]` y 102.000 antes del `refresh` (`mecanismo_arreglado.log`). Front: `tsc` 0, eslint 37 (= techo) y 0 en los dos archivos, `build` OK (`front_gates.log`). Guardas: 52 passed (`guardas_autor.log`).
- **QA 2, pasada 1:** código bien, con una condición. **C1:** ningún test leía el texto nuevo del 422; ahora `test_editable_after_liquidation` exige «revierta la liquidación» y «fecha del día». **O2:** T1 ahora afirma el descuadre en sus dos fuentes, el ORM (cantidad −2 firmada, valor 2.000) y el detalle HTTP que ve Johana (cantidad 2, valor −2.000). Delta `b8942670`, solo tests, con OK (`714dbeb0`).
- **Dirigidas:** **1405 passed** contra la predicción de 1405 (`--collect-only`), EXIT=0, en 2:27:54. El set sale del grep de la superficie tocada, con el comando en `dirigidas_set_p2.log`: 47 archivos más `test_advisory_locks` y `test_crucible_charges`. El árbol era `7f27dad9` al INICIO y al FIN (`dirigidas_p2.log` `a9fe0a0f`). QA 2 rehízo el grep y barrió `integration_helpers.py` y `conftest.py`: no falta nada.
- **Plantado:** P1–P11 y P8b contra la matriz de `760aa82`, más la fila C1 como anexo y el contraste. **14/14 en la diagonal**, sin caídas de más y sin ninguna en la dirección peligrosa (`plantado/plantado.log` `071be23a`, script `c783902a`). De las caídas, 77 son AssertionError y 4 son «DID NOT RAISE»; ningún test quedó sin resultado ni falló por un import. Notas:
  - P4 se comporta igual que P1: `synchronize_session="fetch"` en los DELETE no arregla la colección.
  - P7 cae por el 400 «Entrada #1» en el setup de toda liquidación de Entrada, como predijo QA 2.
  - Contraste: T1 con el reparto IGUAL pasa también con P1. Sin cambio de reparto no se llama a `update`; la cantidad nueva es la premisa del test.
  - **Desviación del §C2:** el plantado se hizo **en el lugar**, no «sobre una copia del árbol». Hubo respaldo por ruta, restauración verificada por sha después de cada fila, `PYTHONDONTWRITEBYTECODE=1` y `.pyc` borrados, con cierre absoluto: `git diff HEAD` = `7f27dad9`. `:8012` (con `--reload`, sirve este árbol) recibió 0 requests durante las 15 recargas del plantado (`qa-2-bug130/pasada2/requests_8012_plantado.log` `870a3cb7`).
- **Capturas D1/D2** a 1440 y 390, de detalle y listado con el menú abierto: **12/12** (`capturas/captura_puertas.log` `8f0521bf`, 12 png). La compra #15 (de Entrada, registrada) y la #13 (de Entrada, liquidada) no muestran Editar, Liquidar ni Cancelar. La #4 (directa, registrada) es el control positivo y muestra las tres. Antes, una prueba de vida (`prueba_vida.log` `912565cc`): `:8012` responde 400 «Entrada #35» a liquidar y editar la #15 sin escribir nada.
- **Golden: no aplica, medido** (`golden_no_aplica.log` `9925e58c`). Las líneas cambiadas, mapeadas por `ast`, caen en `liquidate`, `update` y `cancel` de compras, en el helper y en `liquidate` y `update` de la Entrada: todo escrituras. Ningún endpoint de las rutas de `CAPTURES` importa esos servicios; el control positivo es `endpoints/purchases.py`, que sí los importa.
- **Higiene (observación de QA 2):** las capturas en dev leyeron la credencial del superusuario de `~/.config/sac-prod.env`, con el API fijo a localhost: nada salió a producción. Para dev alcanza la cuenta demo (`~/.config/ecobalance/cuentas-demo.env`), y es la que se usa de ahora en más.
- **Previo, visto por QA 2 en las capturas** (no es de este cambio): a 390, la fila de botones del detalle de una compra directa desborda, porque el `div` de `PurchaseDetailPage` no tiene `flex-wrap`, desde antes de `dea2320`. El Coordinador me lo asignó como tarea chica, en una rama aparte.

## Borrador de la decisión (la numera el Coordinador)

**La compra de una Entrada se maneja solo desde la Entrada, y re-liquidar con el reparto cambiado deja el total nuevo (bug #130 + D1/D2 de Daniel, 23-nov; cero migraciones)**: `purchase.update(commit=False)` reescribía líneas y comisiones con DELETE masivo + `db.add`, que no tocan la colección ya cargada; `liquidate`, llamado a continuación por la Entrada, recalculaba `total_amount` con las líneas viejas y lo grababa. Ahora `update` expira esas colecciones después del `flush`, solo en la rama `commit=False`. Y una compra de Entrada no se liquida, edita ni cancela desde Compras: un solo predicado (`_linked_inbound_number`, Entrada no anulada por la puente) da 400 con el número de la Entrada en las tres puertas, y la excepción va por el kwarg `from_inbound`, nunca por `commit=False`; las pantallas ocultan Editar, Liquidar y Cancelar. Revierte el «se permite editar» de #75 D7b. ⚠️ Un test de re-liquidación tiene que cambiar el reparto Y afirmar montos escritos a mano: `test_t16_slots_son_identidad` pasaba por el bug cambiando 100→150 y solo miraba estados.
