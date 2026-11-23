# Plan: IVA y retenciones con % libre en Ventas y Salidas de Plomo (v1.1)

- **Autor:** Eco Coder 1. **Fecha:** 23-nov-2026.
- **Base:** `032342a` (Liquidar Entrada con % libre, OK de commit de QA 1). Rama `coder-1/impuestos-ventas-libres`.
- **Origen:** el plan `plan-sac-retefuente-porcentajes` v1.5 §2 dejó esto para un plan aparte, con «el mismo comportamiento». Daniel confirmó que Ventas y Salidas también van libres; arranca con el OK de commit de la Entrada.
- **Nivel:** lógica. Toca reglas de cálculo y el payload de dos liquidaciones, y una de las dos páginas es compartida.

**Cambios v1.0 → v1.1** (veredicto de QA 1, `8a672509…`):
- C1: el selector elige el TIPO de impuesto, no la tarifa (R0). Hay un predicado único para la tarjeta (R0b), y la detección de duplicados usa la clave del servidor (R6).
- C2: en un abono, editar el % no borra el monto digitado (R8).
- C3: e2e de recálculo al cambiar un precio, y un U sobre el % que usan la pista y el texto (§5).
- A2: la rama «sin fila de IVA» se cae. El servidor ya da 422 a una reteIVA sin IVA, así que la pantalla bloquea igual (R4b).

## 1. Qué cambia para el usuario

Hoy, en `DocumentTaxesCard`, cada fila tiene «Impuesto» (una TARIFA del catálogo, o el IVA) y «Monto», y el % viene fijo de la tarifa (o del `iva_rate_pct` de la org para el IVA). Con este plan:

- El selector elige el **tipo** de impuesto: IVA, ReteFuente, ReteIVA o ICA de un municipio. Es D1 de la Entrada.
- Cada fila gana una casilla **«% del subtotal»** (o «% del IVA» para una tarifa sobre el IVA), al lado del monto, como en Liquidar Entrada.
- Elegir el tipo trae el % de su tarifa y calcula el monto.
- Editar el % recalcula el monto en vivo, con el foco todavía en la casilla.
- Editar el monto lo deja fijo. Gana el último que se tocó (T4 de la Entrada).
- Un % alejado más de 5 veces de la referencia muestra el aviso ámbar y no bloquea (T7).
- Un % fuera de (0, 100] bloquea Liquidar (T5).
- El payload manda el % digitado en `rate`. Hoy manda el del catálogo.

## 2. Alcance, medido

| Archivo | Qué es | Toca |
|---|---|---|
| `components/shared/DocumentTaxesCard.tsx` | la tarjeta y sus funciones puras | sí |
| `pages/sales/SaleLiquidatePage.tsx` | **compartida (7 orgs)**; la tarjeta solo se pinta con `kg_ledger_enabled` (`:151`, `:491`) y sin la bandera el payload no lleva `taxes` (#98 D10) | solo si cambia la firma de la tarjeta |
| `pages/willard/WillardDeliveryDetailPage.tsx` | módulo SAC, todo detrás de la bandera | solo si cambia la firma |
| `utils/taxRows.ts` | ya tiene `pctOf`, `rateWarning`, `rateWarningText` y `rateOutOfRange` | se reutiliza; si se agrega algo, no cambia lo de la Entrada |
| backend | `DocumentTaxCreate.rate` ya tiene `le=100` (T12 de la Entrada, `032342a`) | **no** |

**Lo que NO aplica de la Entrada, y por qué:** T1', T2 y T2b (precarga y borrador). Una venta liquidada solo se cancela y una Salida liquidada solo se anula. Ninguna se reliquida ni guarda borrador, y la tarjeta arranca vacía. QA 1 lo verificó midiendo las rutas de escritura.

## 3. Reglas

- **R0. El selector elige el tipo.** Ofrece:
  - IVA, siempre;
  - ReteFuente y ReteIVA, si hay una tarifa usable de ese tipo;
  - un ICA por cada municipio con una tarifa usable.
  - **Tarifa de cada tipo:** la general (sin concepto), si la hay; si no, la primera. Es la preferencia de `pickTypeConfig` de la Entrada, con el predicado de R0b.
  - **Concepto:** viaja el de la tarifa elegida. El caso «No declarante» se cubre digitando el % (D1 de la Entrada).
- **R0b. Un solo predicado para la tarjeta:** `isUsableTaxConfig(cfg) = !!cfg.config_id && cfg.is_active`.
  - No es `isUsableConfig` de la Entrada: ese excluye `base_kind='iva'`, y en ventas la reteIVA sobre el IVA sí va.
  - El `base_kind` de la tarifa elegida decide la base (R4) y viaja en el payload.
- **R1. Fila:** `source` pasa a ser la clave del tipo (`iva`, `retefuente`, `reteiva`, `ica:<municipio normalizado>`), y la fila gana `rate: number`. Al elegir el tipo, `rate` toma el % de su tarifa (o `iva_rate_pct` para el IVA) y `touched=false`.
- **R2. «Gana el último»:** la misma semántica de `withRate` y `withAmount`. Pasar con Tab por el % sin cambiarlo no cuenta como tocarlo. Excepción en R8.
- **R3. IVA por línea (D6 de #112), con el % de la fila:** el IVA sugerido redondea cada línea a la tasa digitada y suma.
- **R4. Base de una tarifa sobre el IVA:** el monto EFECTIVO de la fila de IVA. Es lo mismo que guarda el servidor como `base_amount` (`document_tax.py:133-152`: `iva_total` sale del payload). Ver A2.
- **R4b. Tarifa sobre el IVA sin fila de IVA → bloquea,** con el texto del servidor: «Hay una retención que se aplica sobre el IVA y esta factura no tiene IVA…» (`document_tax.py:137-145`, hoy da 422 después de llenar todo).
- **R5. Aviso ×5:** la referencia es el `rate_pct` de la tarifa del tipo, o el `iva_rate_pct` de la org para el IVA («el IVA habitual»).
- **R6. Duplicados con la clave del servidor:** (tipo, municipio normalizado) (`document_tax.py:98-111`). El selector deshabilita los tipos ya usados, y `taxRowsValid` lo comprueba con la misma clave.
- **R6b. Bloqueo por rango:** `taxRowsValid` suma «% fuera de (0, 100]», con un texto que lo nombra.
- **R7. Payload:** `rate` = el % de la fila. `base_kind`, `municipality` y `concept` salen de la tarifa del tipo.
- **R8. Abono con base 0** (Salida tipo abono: la base la deriva el servidor y la pantalla la ve en 0). El % se muestra y viaja como dato. El monto sugerido es 0 y el usuario digita el de la factura.
  - **Si la base que conoce la pantalla es 0, editar el % NO destoca el monto** (C2).
  - Sin esto, corregir el % después de digitar el monto lo dejaba en % × 0 = 0, con la fila en rojo y Liquidar bloqueado.
- **R9. La pista y el texto usan el % de la fila:** «Sugerido: $X (r %)» y «r % de $base — editable», donde r es el % digitado y no el del catálogo.

## 4. Decisiones abiertas (para Daniel, vía el Coordinador)

- **A1. ¿«Agregar» propone algo?** En la Entrada, «+ Retención» propone la ReteFuente general (D1). Acá la tarjeta mezcla IVA y retenciones, y hoy la fila nueva arranca vacía.
  - **Recomendada: dejarla vacía, como hoy.** En una venta lo primero suele ser el IVA. Proponer una retención por defecto invertiría el orden en que se lee la factura.
  - Alternativa: proponer el IVA si todavía no hay una fila de IVA, y la ReteFuente general si ya la hay.
- **A2. Base de la reteIVA cuando se editó el IVA.**
  - **Recomendada: el monto efectivo de la fila de IVA (R4).**
    - Tiene sustento en el servidor: `apply_taxes` ya guarda como `base_amount` de la reteIVA el IVA efectivo del payload (`document_tax.py:133-152`).
    - Con la alternativa, el registro quedaría con `rate × base ≠ amount`.
    - En un abono, la reteIVA tendría sugerencia (el IVA digitado), en lugar de 0.
  - Alternativa: el IVA sugerido a la tasa de la org (hoy), ignorando la fila.

## 5. Pruebas

- **U (puros):**
  - R0–R9, cada regla con su caso;
  - R0b con una ReteIVA `base_kind='iva'` usable;
  - R6 con dos ReteFuente (general y «No declarante»): un solo tipo y una sola fila;
  - R8: con base 0, monto digitado y % editado, el monto se conserva;
  - R9 sobre el VALOR del % (el campo que alimenta la pista y el texto), no sobre el texto.
- **E (Playwright, 1440 y 390, solo :8011/:5181):**
  - **Venta, IVA 5 y ReteFuente 3,5:** el monto se lee con el foco en el %. Al liquidar, `taxes[].rate` por API = 5 y 3,5.
  - **Recálculo al cambiar un precio (C3, lección P21):** con el IVA al 5 %, se cambia el precio de una línea y el IVA tiene que quedar en el 5 % del nuevo subtotal, redondeado por línea. No al `iva_rate_pct` de la org.
  - **ReteIVA:** se edita el monto del IVA y la reteIVA se recalcula sobre ese monto (R4). Sin la fila de IVA, Liquidar queda bloqueado con el texto del servidor (R4b).
  - **Dos ReteFuente en el catálogo:** el selector muestra un solo «ReteFuente» y no deja una segunda fila (R6).
  - **Salida tipo venta:** ICA 0,966.
  - **Salida tipo abono (C2):** se digita el monto, después se corrige el %, el monto se conserva y al liquidar viajan el monto y el %.
  - **Aviso y bloqueo:** aviso con 25 y bloqueo con 0.
  - **No-regresión de las otras orgs:** en Costa, Liquidar Venta no pinta la tarjeta ni manda `taxes` (registro de red).
- **Plantado:** matriz commiteada antes de plantar. Las filas en vías compartidas (`effectiveTaxAmount`, `buildTaxPayload`) se escriben «≥».
- **Dirigidas:** grep del símbolo **y de los importadores del módulo** (lección de QA 1 en la pasada 2 de la Entrada), más las tres guardas.
- **Golden:** no aplica. Se mide con comando: `git diff --stat 032342a -- backend/app` vacío.

## 6. Fuera de alcance

- La precarga y el borrador (no hay reliquidación; §2).
- `PurchaseLiquidatePage` (compartida), como en la Entrada.
- Cambiar el `iva_rate_pct` de la org.
