# Matriz de plantado: % libre en Ventas y Salidas de Plomo (plan v1.1)

- **Autor:** Eco Coder 1. **Fecha:** 23-nov-2026.
- **Árbol que se planta:** base `da1ee34` + delta C1, con GO de QA 1 (veredicto `e23f2c5c…`).
  - `frontend/src/utils/documentTaxRows.ts` `aa4dc246…`
  - `frontend/src/components/shared/DocumentTaxesCard.tsx` `d3cd297e…`
- **Regla:** esta matriz se commitea ANTES de plantar y no se reescribe. Si una fila cae distinto, se anota en el log del plantado con su causa.
- «≥» marca las vías compartidas: caen al menos esas pruebas, y una caída de más se explica en el log, no se toma por error.

## Pruebas

- **U1–U21:** casos puros (`u_casos.ts`), los del plan §5 más U21 (C1, la sonda de QA 1).
- **E (Playwright, 1440 y 390, :8011/:5181):**
  - **E1.** Venta SAC (1.000.000).
    - IVA con 5 en el % y el foco todavía en la casilla: monto 50.000 y el texto «5% de $ 1.000.000».
    - ReteFuente con 3,5: 35.000.
    - Al liquidar, la API devuelve `rate` 5 y 3,5 y los montos 50.000 y 35.000.
  - **E2 (C3).** IVA al 5 %, se pasa con Tab por el monto sin cambiarlo, se cambia el precio de una línea, y el IVA es el 5 % del subtotal nuevo, redondeado por línea.
  - **E3 (R4/R4b).** Con una ReteIVA sobre el IVA en el catálogo:
    - el monto del IVA se edita a 100.000, y la ReteIVA con 15 da 15.000 y su rótulo dice «% del IVA»;
    - al quitar la fila de IVA aparece el texto del servidor y Liquidar queda deshabilitado.
  - **E4 (R6).** Con dos ReteFuente activas, el selector muestra un solo «ReteFuente». En una segunda fila, ReteFuente queda deshabilitada.
  - **E5.** Salida tipo venta con ICA Barranquilla al 0,966: la API devuelve `rate` 0,966 y el monto, el 0,966 % del subtotal.
  - **E6 (C2/R8).** Salida tipo abono:
    - se elige ReteFuente, se digita el monto 30.000 y después el % 4: el monto sigue en 30.000;
    - al liquidar, la API devuelve `rate` 4 y `amount` 30.000.
  - **E7 (R5/R6b).**
    - Con 25 en la ReteFuente: aparece el aviso ámbar y Liquidar queda habilitado.
    - Con 0: aparece «El % de un impuesto debe estar entre 0 y 100.» y Liquidar queda deshabilitado.
  - **E8 (no-regresión).** Liquidar Venta de Costa no pinta la tarjeta, y el PATCH de liquidar no lleva `taxes` (registro de red).

## Defectos plantados y predicción

| P | Defecto plantado | Archivo | Caen |
|---|---|---|---|
| P1 | `withTaxRate` nunca destoca: `return { ...row, rate }` después del primer `if` | utils | U6, U15 |
| P2 | Se quita R8 (la línea `base === 0 && row.touched`) | utils | U14, E6 |
| P3 | `suggestedIva` sobre el total y no por línea | utils | U7 |
| P4 | `suggestedTaxAmount` del IVA a 19 fijo en vez de `row.rate` | utils | ≥ U13, E1, E2 |
| P5 | `taxRowBase` sobre el IVA = `suggestedIva(lineAmounts, 19)` (ignora la fila de IVA; la alternativa de A2) | utils | ≥ U8, U15, E3 |
| P6 | Se quita R4b de `taxRowsProblems` | utils | U9, E3 |
| P7 | `taxRateReference` del IVA con `ref: row.rate` | utils | U10 |
| P8 | `taxKey` sin normalizar el municipio | utils | U1, U13 |
| P9 | `taxTypeOptions` sin preferir la general (`cands[0]`) | utils | U2, U13 |
| P10 | `isUsableTaxConfig` sin `is_active` | utils | U1, U21 |
| P11 | `buildTaxPayload` con `rate: cfg.rate_pct` (y el IVA con `_ivaRatePct`) | utils | ≥ U13, E1, E5, E6 |
| P12 | Se quita el problema de repetido | utils | U11 |
| P13 | Se quita el problema de rango | utils | U12, E7 |
| P14 | Se quita el problema de la fila huérfana (C1) | utils | U21 |
| P15 | La casilla de % sin `liveChange` | card | ≥ E1 |
| P16 | El monto marca `touched` en todo `onChange` (sin `v !== amount`) | card | E2 |
| P17 | El selector sin `disabled` para los tipos usados | card | E4 |
| P18 | El texto «r% de $base» con el % de la tarifa (`ref.ref`) en vez del de la fila | card | E1 |
| P19 | `selectTaxType` conserva `touched` y `amount` | utils | U4 |
| P20 | `taxNetDelta` con el signo invertido | utils | U17 |
| P21 | `buildTaxPayload` devuelve `[]` en vez de `undefined` | utils | U18 |
| P22 | `normMunicipality` colapsa los espacios internos | utils | U20 |
| P23 | Se quita «Falta elegir» de `taxRowsProblems` | utils | U19 |
| P24 | `effectiveTaxAmount` ignora `touched` (siempre el sugerido) | utils | ≥ U6, U14, E3, E6 |

## Cómo se corre

- Cada P se aplica sobre el árbol con respaldo por ruta. Después corren U y E, y se restaura.
- Al cerrar, los 2 sha tienen que coincidir con los de arriba.
- Vite sirve el árbol vivo (:5181). El back (:8011) no se toca: ningún P es de backend.
- Cada corrida verifica que vite responda 200 sobre el módulo plantado antes de medir. Un plantado que no compila no mide nada.

## Addendum P24 (23-nov, veredicto `6169c1f5…` de QA 1) — escrito y commiteado ANTES de re-plantar

- **P24 original: PELIGROSA, cayó.** E3 no cayó en dos corridas (18:41 y 18:44). La base de la reteIVA salía de `effectiveIva`, que repetía la regla `touched ? amount : sugerido` en vez de llamar a `effectiveTaxAmount`. Con P24, la tarjeta mostraba un IVA de 190.000 mientras la reteIVA se calculaba sobre 100.000, y E3 solo miraba la reteIVA y el rótulo. Medido en `sonda24_P24_e.log` y `sonda24_control_e.log`. La fila de arriba no se reescribe.
- **Arreglo (a):** `effectiveIva` delega en `effectiveTaxAmount(iva, rows, lineAmounts, [])`. Queda un solo predicado.
- **Arreglo (b):**
  - E3 afirma además el EFECTO: el IVA tocado sigue en pantalla en «100.000» y el neto es +85.000 → 1.085.000, en 1440 y en 390.
  - **U22:** con el IVA tocado a 100.000, `taxRowBase(reteIVA) == effectiveTaxAmount(IVA) == effectiveIva == 100.000` y el sugerido de la reteIVA es 15.000.

| P | Defecto plantado | Archivo | Caen |
|---|---|---|---|
| P24 (re) | `effectiveTaxAmount` ignora `touched` (igual que arriba), con (a) aplicado | utils | ≥ U6, U8, U14, U15, U22, E3, E6 |
| P24b | `effectiveIva` vuelve a `suggestedIva(lineAmounts, iva.rate)` sin mirar `touched` | utils | ≥ U8, U15, U22, E3 |

- Agregué U8 y U15 a lo que pidió QA (U22 y E3) al releer los casos: los dos leen la base de la reteIVA con el IVA tocado. Las dos filas llevan ≥ porque `effectiveIva` es una vía compartida.
- E3 con P24b: el neto pasa a +71.500 (IVA 100.000 en pantalla, reteIVA 28.500 sobre 190.000).
