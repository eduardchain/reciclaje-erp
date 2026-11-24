# Plan: al re-liquidar la Entrada, retención e IVA precargados se recalculan si cambió el subtotal (v1.3)

- **Autor:** Eco Coder 1. **Fecha:** 23-nov-2026.
- **Base:** `032342a` (% libre en Liquidar Entrada, #135). Rama nueva desde ahí, o desde la que indique el Coordinador al integrar.
- **Nivel:** lógica. Cambia el monto que se precalcula y que viaja en el payload al re-liquidar.
- **v1.0 → v1.1:** A1 decidida por Daniel («Sí, mostrarla»); sin otros cambios.
- **v1.1 → v1.2** (veredicto de QA 1, `ede725fb…`):
  - C1: cada fila compara contra una base de su MISMA fuente (R2), porque la base de la retención la calcula la pantalla y la del IVA es el `total_amount` del servidor.
  - C1: el subtotal de apertura viaja en el borrador (R8).
  - C1: E10 en los tres modos de precio y con una compra de varias líneas.
  - C1: U de fuentes cruzadas y una fila de plantado para el IVA.
  - C2: el plan ya no cita ninguna Entrada de dev; cada E crea la suya.
- **v1.2 → v1.3** (veredicto de QA 1, `dc7cfd86…`, C3):
  - Sale la pregunta (A). Desde el 20-nov la precarga trae solo la ÚLTIMA liquidación (`last_liquidation_batch`, `inbound_order.py:2353`), y el lote viejo no vuelve a propósito. Con eso, (A) solo dispararía con datos dañados o con una pantalla que no reproduce su propia cuenta, y en esos dos casos pisaría un monto escrito a mano.
  - Quedan solo la apertura contra el subtotal actual, pantalla contra pantalla. La apertura ES lo guardado puesto en pantalla.
  - Salen `savedBase`, `ivaSavedBase`, `ivaPurchaseTotal`, E11 y los U y las filas de plantado de (A).
- **Escrito fuera del worktree** mientras dura la pasada 1 de Ventas y Salidas, para que el árbol no se mueva. Se commitea en `docs/planes/` antes de construir.

## 0. Origen (vía el Coordinador, 23-nov)

- Primera pregunta: «¿Quieres que la retención siga al subtotal igual que el IVA?». Daniel: *«Si, no tiene sentido ese surgerido»*.
- El Coordinador le planteó un riesgo. Desde #134, corregir la factura de una compra de Entrada exige revertir y re-liquidar, y en ese caso el subtotal no cambia. Si el monto se recalculara siempre, un monto escrito a mano (por ejemplo, el de un certificado) volvería al % sin aviso.
- Regla afinada que Daniel aceptó con *«si, me sirve»*. Es la que construye este plan:
  - si el subtotal de la compra cambia respecto del guardado, la retención se recalcula con su % y no aparece «Sugerido»;
  - si el subtotal no cambia, queda el monto guardado tal cual, sea calculado o escrito a mano;
  - el IVA precargado lleva la misma regla;
  - no se toca la edición en vivo de #135: dentro de la misma sesión sigue ganando el último que se tocó.

## 1. El defecto, medido en el código

- `precargaRetention` (`frontend/src/utils/taxRows.ts:100-124`) devuelve siempre `touched: true`. Si se cambian cantidades al re-liquidar, el monto viejo queda fijo y aparece «Sugerido». Por ejemplo: ReteFuente 3 % en 2.250 sobre un subtotal nuevo de 80.000, cuando el 3 % da 2.400.
- `precargaIva` (`:239-248`) mide `ivaTouched = amount !== pctOf(base_amount, rate)`. Un IVA calculado sí sigue al subtotal, pero uno escrito a mano queda fijo aunque el subtotal cambie. Eso también cambia.
- La asimetría viene de #122, antes de #135.

## 2. La regla

**R0. «El subtotal cambió» = el subtotal actual de la compra en pantalla es distinto del subtotal de apertura.** Los dos lados salen de la misma cuenta de la pantalla (`st.subtotal`), así que no hay que comparar fuentes distintas (C1).
- **Subtotal de apertura (`openSubtotal`, por compra):** es `st.subtotal`, con la misma función, aplicada UNA vez al reparto recién precargado, antes de cualquier edición. Se guarda en la columna.
- La precarga trae solo la última liquidación (`last_liquidation_batch`) y el reparto se conserva (#93 D20; desde #134 la compra no se edita por fuera). Por eso la apertura es lo que se guardó, puesto en pantalla. Ese es el «subtotal guardado» de la regla de Daniel.
- Si la pantalla no reprodujera al centavo su propia cuenta, eso no cambia nada: la apertura y el subtotal actual salen de la misma cuenta sobre el mismo reparto, así que dan «igual» y el monto guardado se conserva. Es la dirección conservadora. E10 lo deja medido en los tres modos de precio.

- **R1.** La columna gana `openSubtotal`. La retención y el IVA precargados quedan marcados como precargados (`fromSaved: true`, nombre a fijar al construir). **Backend: sin cambios.**
- **R2. Si el subtotal cambió, se recalcula.** Mientras la fila siga precargada, si `st.subtotal ≠ openSubtotal`, el monto que vale es `pctOf(st.subtotal, rate)`, con el % guardado. Como coincide con el sugerido, «Sugerido» no aparece.
- **R3. Si el subtotal no cambió, queda el monto guardado.** Vale tal cual, haya sido calculado o escrito a mano. Si difiere del %, se ve «Sugerido» (A1).
- **R4. La comparación es a centavos:** `Math.round(x × 100)` en los dos lados.
- **R5. Lo que se edita en la sesión gana (#135, intacto).**
  - Editar el monto deja la fila fija (`touched`) y le quita la marca de precargada, así que R2 deja de aplicar.
  - Editar el % la destoca, como hoy (`withRate`).
  - Volver a dejar el subtotal en el valor de apertura, sin haber editado nada, devuelve el monto guardado (R3).
- **R6. Sin `openSubtotal`** (borrador anterior al cambio) **o sin % guardado** (`rate` nulo en filas viejas) **→ queda fijo**, como hoy. Es la dirección conservadora: un monto que no se mueve solo.
- **R7. Un solo predicado.**
  - `followsSubtotal(fromSaved, openSubtotal, subtotal, rate)` es una función pura con R0–R6, y la usan la retención y el IVA.
  - `effAmount` y `effIva` son el único lugar que decide el monto.
  - El IVA que la página calcula en línea (`InboundLiquidatePage.tsx:1078` y el `onAmount` de `:1625`) pasa a `effIva`, para que la tarjeta, el pie y el payload no puedan dar números distintos.
- **R8. Borrador.**
  - `openSubtotal` y la marca de precargada viajan en el borrador.
  - **El `openSubtotal` se guarda y NO se recalcula al recargar.** Si se recalculara sobre el reparto del borrador, que ya fue editado, daría «igual» y un cambio hecho antes de recargar volvería al monto viejo.
  - `assertDraftShape` acepta los campos nuevos como opcionales. Un borrador anterior al cambio no los trae y queda en R6.
- **R9. La rama T2** (tarifa que ya no sirve) usa la misma regla. Esa fila bloquea igual hasta que se elige la tarifa.

**Decidido por Daniel, vía el Coordinador:**
- **A1.** Con el subtotal sin cambio y un monto escrito a mano (R3), la pista «Sugerido: $X (r %)» se sigue viendo al lado, como hoy. Respuesta de Daniel: *«Sí, mostrarla (Recomendado)»*. No cambia el monto, avisa que difiere del % y deja volver al % con un clic. Con el subtotal cambiado (R2) no aparece, porque el monto ya es el sugerido.

## 3. Alcance, medido

| Archivo | Cambio |
|---|---|
| `frontend/src/utils/taxRows.ts` | la marca de precargada en `RetRow` y en `IvaState`; `followsSubtotal`; precargas, `withAmount`, `effAmount` y `effIva` con R0–R6 |
| `frontend/src/pages/inbound/InboundLiquidatePage.tsx` | `openSubtotal` por columna, calculado una sola vez al precargar; el IVA en línea pasa a `effIva` (R7); editar el monto del IVA le quita la marca; `assertDraftShape` (R8) |
| backend | no |

`precargaRetention`, `precargaIva` y `effAmount` solo se usan en `taxRows.ts` e `InboundLiquidatePage.tsx` (grep del símbolo, antes de construir se vuelve a correr).

## 4. Pruebas

- **U (puros, se suman al arnés de #135):**
  - **R2:** precargada, apertura 75.000 y subtotal 80.000, 3 % → 2.400. Vale igual para un monto escrito a mano (2.000) y para el IVA.
  - **R3:** apertura 75.000 y subtotal 75.000 → 2.250 si era el calculado, 2.000 si estaba a mano. Lo mismo para el IVA.
  - **R4:** 75.000,004 contra 75.000 → igual; 75.010 contra 75.000 → distinto.
  - **C1, reescrito para la regla de v1.3:** IVA guardado con `base_amount` 75.000,00, apertura 75.000,01 y subtotal 75.000,01. Queda en R3: el monto a mano se conserva aunque la pantalla no reproduzca el número del servidor. Si se compara contra `base_amount`, sigue al subtotal: este caso distingue las dos reglas.
  - **R5:** precargada + `withAmount` → fija aunque cambie el subtotal; precargada + `withRate` → sigue el % (como hoy).
  - **R6:** sin `openSubtotal` o con `rate` nulo → fija.
  - **R8:** el borrador revive con su `openSubtotal` y no lo recalcula; uno sin los campos nuevos revive en R6.
  - Los U de #135 siguen igual (sin `openSubtotal` caen en R6): se verifica que no cambian.
- **E (Playwright, 1440 y 390, en el e2e de #135). Cada E crea su propia Entrada por API (C2).**
  - **E9 (R2).** Se liquida una Entrada con IVA y ReteFuente escritos a mano. Se desliquida, se reabre Liquidar y se cambia una cantidad. Los dos montos siguen al subtotal nuevo, no aparece «Sugerido», y la API devuelve los montos nuevos al re-liquidar.
  - **E10 (R3, el riesgo del Coordinador; medición de C1).** Se repite en los **tres modos de precio**, cada uno con una compra de **varias líneas** e IVA y ReteFuente escritos a mano:
    - unitario con un precio de 8 decimales;
    - total no divisible (200.000 entre 3);
    - por kg.

    Se desliquida y se reabre sin cambiar nada:
    - los montos quedan iguales en pantalla;
    - al re-liquidar quedan iguales en la API;
    - el log imprime, por modo, la apertura, la `base` de la retención y el `total_amount`.
  - **E12 (R8).** Se cambia la cantidad, se recarga la página (borrador) y el monto sigue al subtotal nuevo.
- **Plantado:** matriz commiteada antes. Filas mínimas:
  - siempre fija (lo de hoy) → U de R2, E9;
  - recalcular siempre, sin mirar la apertura → U de R3, E10;
  - **el IVA comparado contra `base_amount` en vez de contra la apertura (C1)** → U de C1 (≥; E10 solo si algún modo da apertura ≠ `total_amount`, y eso lo mide E10);
  - comparar sin redondeo a centavos → U de R4;
  - `withAmount` sin quitar la marca de precargada → U de R5;
  - el IVA en línea de `:1078` sin pasar a `effIva` → E9 (la tarjeta y el pie divergen);
  - `openSubtotal` recalculado al revivir el borrador → U de R8, E12;
  - `assertDraftShape` que rechaza un campo nuevo → E12.
- **Dirigidas:** grep del símbolo y de los importadores del módulo, más las 3 guardas.
- **Golden:** no aplica; se mide con `git diff --stat <base> -- backend/app` vacío.

## 5. Fuera de alcance

- Ventas y Salidas de Plomo: no se reliquidan.
- `PurchaseLiquidatePage` (compartida).
- Datos ya guardados: no se reescriben. La regla solo decide qué se precarga en pantalla.
