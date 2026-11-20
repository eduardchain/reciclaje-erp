# Matriz de plantado — reparto por compra (plan v1.2, §8)

Se commitea ANTES de plantar. La columna «predicción» no se reescribe después: si una fila difiere, se mide la causa y se anota en el informe, al lado.

- **Árbol medido:** el del patch completo `8a40ce44…` (base `81b3f13`), con el GO de QA del 20-nov.
- **Método:**
  - Respaldo por RUTA, no por nombre: hay dos `inbound_order.py`, dos `purchase.py` y dos `document_tax.py`.
  - `PYTHONDONTWRITEBYTECODE=1` y borrar el `.pyc` de cada archivo plantado.
  - Por fila corre `tests/test_sac_reparto_por_compra.py` completo con `--tb=line`; cada fila cae en su propio log.
  - **Cierre absoluto:** el sha256 de cada archivo tocado tiene que coincidir con `reparto_qa1b_files.sha256`, y `git diff --stat` tiene que ser idéntico al del inicio.
- **Backend vivo:** `:8001` corre sin `--reload`, así que un plantado en `app/` no lo sirve la pantalla ni escribe en dev.
- **Filas de pantalla (P14, P15):** ningún test ejecuta la pantalla, así que la predicción de tests es 0 y la medida es la pantalla, por HMR de Vite en `:5174`.
- **Vías compartidas:** las predicciones dicen «al menos estos» y la fila va marcada **≥**. Caer de más es la dirección barata; la peligrosa es un test que debía caer y no cayó.

| P | Defecto plantado (archivo) | Pieza del plan | Predicción | Primera falla esperada |
|---|---|---|---|---|
| P1 | Agrupar por PROVEEDOR: `groups` con llave = el primer slot de ese proveedor (`inbound_order.py`, paso 2) | §3.2 | **≥** T1, T3, T13 (T2 y T17 NO: con un solo proveedor las dos corridas agrupan igual y comparan iguales) | T1: el puente sale con 1 compra, no 2 · T3: el desempaque de dos filas · T13: no hay RuntimeError |
| P2 | Reusar por PROVEEDOR: en vez de `live_by_slot.pop(slot)`, la primera compra viva de ese proveedor, de cualquier slot (`inbound_order.py`) | §3.2, R6 | **0 — hueco esperado.** Ningún test intercambia proveedores entre slots: con un proveedor por slot, o el mismo en todos, los dos criterios eligen la misma compra | — Si da 0, se propone T3b: intercambiar proveedores entre slots y reliquidar (aviso a QA antes de escribirlo) |
| P3 | Signo del IVA de compra invertido: `TAX_SIGN_ON_PARTY["purchase"] = {"iva": +1}` (`models/document_tax.py`) | §4 | **≥** T7, T8, T8b, T9, T9b, T10 | T7: la entidad con −19.000, no +19.000 |
| P4 | As-of sin la rama `Purchase`: se quita `("purchase", tax_purchase_rows)` del loop (`reports.py`) | R2 | T10, y solo T10 | T10: el proveedor en 100.000 y la entidad ausente en el corte de hoy |
| P5 | Aviso de duplicado sin suprimir: `exclude_from_duplicates=None` (`inbound_order.py`) | R8 | T1 y T17, y solo esos | T1: aparece «mismo proveedor» en los warnings |
| P6 | El aviso se apaga para TODO `from_inbound`: si llega `exclude_from_duplicates`, `existing_count = 0` (`purchase.py`) | R8 | T17, y solo T17 | T17: la segunda Entrada del mismo día no avisa |
| P7 | `_tax_owner` sin la rama compra (`money_movements.py`) | R1 | **≥** T8, T9 (T9b NO seguro: tras anular, el vivo es 0 y omitir el par del IVA también deja el corrido en 0) | T8: el corrido de la entidad no cierra contra el vivo |
| P8 | `added`/`withheld` con el mapa de VENTA (`TAX_SIGN_ON_CUSTOMER[t] > 0`) (`services/document_tax.py`) | R2 del §4 | **0 — mutante equivalente hoy.** Una compra solo admite IVA, y los dos mapas clasifican el IVA como «suma a la factura». Se planta para dejarlo medido | — |
| P9 | El contado ignora el IVA: `net_payment = total − retenciones` (`purchase.py`, Step 10) | R3 | T7, y solo T7 | T7: la caja baja 97.500, no 116.500 |
| P10 | La reversa del IVA solo en el camino de la Entrada: se saca `revert_taxes` de `_revert_liquidation_effects` y se llama desde `inbound_order.unliquidate` (`purchase.py` + `inbound_order.py`) | R4 | **0 — equivalente en lo alcanzable hoy.** El cancel directo de una derivada está bloqueado (#93 D14, lo fija T9b) y una compra sin Entrada no lleva IVA. Se planta para dejar medido que la ubicación es defensiva | — |
| P11 | Backfill sin llenar el puente: se salta el `UPDATE inbound_order_purchases` (migración) | R5, R7 | T14, y solo T14 | T14: el puente sale con slot None |
| P12 | C1 revertido: una compra viva sin slot vuelve a `leftovers` en vez del 409 (`inbound_order.py`) | QA C1 | T18b, y solo T18b | T18b: `_liq` recibe 200 y esperaba 409 (antes de mirar el status; la compra quedaría `cancelled`) |
| P13 | Sin defensa dura: se quita el chequeo `expected != p.supplier_id` (`inbound_order.py`) | QA c (§3.2) | T18, y solo T18 | T18: 200, esperaba 409 |
| P14 | PANTALLA — «Agregar categoría y usar» manda SOLO la categoría de proveedor (`CreateSupplierDialog.tsx`) | §5 | 0 tests (T12 emula el payload correcto) | Pantalla: el PATCH lleva 1 id y el tercero pierde la categoría de cliente |
| P15 | PANTALLA — quitar una compra renumera los slots (`InboundLiquidatePage.tsx`, `removeCol`) | R6 | 0 tests | Pantalla: con 1, 2, 3, al quitar la 2 los encabezados quedan «Compra 1, 2» y no «1, 3» |
