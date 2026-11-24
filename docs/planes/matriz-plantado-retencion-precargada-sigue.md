# Matriz de plantado: retención e IVA precargados siguen al subtotal (plan v1.3)

- **Autor:** Eco Coder 1. **Fecha:** 23-nov-2026.
- **Árbol que se planta:** base `db844dd` + pasada 1, con GO de QA 1 a gates (veredicto `bf023a88…`).
  - `frontend/src/utils/taxRows.ts` `5663e3b4…`
  - `frontend/src/pages/inbound/InboundLiquidatePage.tsx` `f7b9bd99…`
- **Regla:** esta matriz se commitea ANTES de plantar y no se reescribe. Si una fila cae distinto, se anota en el log del plantado con su causa.
- «≥» marca las vías compartidas (`followsSubtotal`, `effAmount`, `effIva`, `colStats`): caen al menos esas pruebas, y una caída de más se explica en el log.

## Pruebas

- **S1–S12:** casos puros nuevos de `taxRows.ts` (`u_sigue.ts`).
- **U135r:** el arnés de #135 (U1–U29) con U21 y U23 re-semantizados al EFECTO (D1 de QA 1).
  - Se corre entero como control.
  - Abajo solo se predicen U21 y U23; cualquier otra caída del arnés se anota como de más.
- **E (Playwright, 1440 y 390, :8011/:5181):** cada E crea su propia Entrada por API.
  - **E9.** Al reabrir, la cantidad de una celda pasa de 500 a 400. El IVA y la ReteFuente siguen al subtotal nuevo, no hay «Sugerido» y la API devuelve lo mismo al re-liquidar.
  - **E10.** Tres modos de precio con varias líneas. Se reabre sin cambiar nada: los montos a mano quedan, con «Sugerido» a la vista, y la API devuelve lo mismo.
  - **E12.** Se cambia la cantidad y se recarga la página (borrador). El monto sigue al subtotal nuevo.

## Cambio de comportamiento declarado (C1 de QA 1)

- Un IVA guardado **sin `rate`** antes seguía al subtotal, si su monto daba el 19 % de `base_amount` (#135 T8). Ahora queda FIJO (R6).
  - Lo fijan S9 y U23 (re-semantizado).
  - Impacto medido: 0 IVA de compra con `rate` nulo en dev (`reciclaje_coder_1` 0/73, `reciclaje_db` 0/7).
  - `ivaPayload` manda siempre `rate`, así que esa fila solo puede entrar por la API cruda.

## Defectos plantados y predicción

| P | Defecto plantado | Archivo | Caen |
|---|---|---|---|
| P1 | `followsSubtotal` siempre `false` (lo de hoy: lo guardado queda fijo) | utils | ≥ S1, S2, S5, S10, S11, S12, U21, E9, E12 |
| P2 | `followsSubtotal` siempre `true` (recalcular siempre, sin mirar la apertura) | utils | ≥ S3, S4, S5, S6, S7, S8, S9, S10, S11, S12, U23, E9, E10 |
| P3 | Comparación sin redondeo a centavos (`subtotal !== openSubtotal`) | utils | S5 |
| P4 | `withAmount` conserva `fromSaved` | utils | S7 |
| P5 | El IVA compara contra `base_amount` en vez de contra la apertura (C1 de v1.2): `precargaIva` guarda `base_amount` y `effIva` lo usa | utils | ≥ S6, S8 |
| P6 | R6 ignorado: `fromSaved`/`ivaFromSaved` en `true` aunque no haya `rate` | utils | S9, U23 |
| P7 | El borrador recalcula `openSubtotal` sobre su reparto (`colSubtotal(d.lines, c)`) | página | E12 |
| P8 | `reviveDraftRetention` pierde `fromSaved` | utils | S10, E12 |
| P9 | `colStats` con el IVA en línea (`ivaTouched ? ivaAmount : pctOf`) en vez de `effIva` | página | ≥ E9, E12 |
| P10 | La apertura es el subtotal actual: `effRetAmount` y `colStats` pasan `subtotal` como apertura | página | ≥ E9, E12 |
| P11 | `assertDraftShape` rechaza un `openSubtotal` numérico (el borrador se descarta) | página | E12 |

## Cómo se corre

- Cada P se aplica sobre el árbol con respaldo por ruta y cada reemplazo exige exactamente 1 ocurrencia.
- Después corren S, U135r y E, y se restaura.
- Al cerrar, los 2 sha tienen que coincidir con los de arriba.
- Vite sirve el árbol vivo (:5181) y el back (:8011) no se toca: ningún P es de backend.
- Cada corrida espera a que vite sirva el módulo plantado con 200 antes de medir. Un plantado que no compila no mide nada.
- Una corrida que no cierra con su resumen es INVÁLIDA.
