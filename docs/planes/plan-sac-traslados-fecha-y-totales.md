# Plan — Traslados: la fecha de recepción arranca en la del despacho, y la tabla «Líneas» suma kg de plomo y maquila (SAC)

Versión 1.1 · 26-nov-2026 · autor: Eco Coder 2 · **nivel: lógica** · base: `75f621a` (rama `coder-2/traslados-fecha-totales`)
Pedido: SAC, vía Daniel, alcance confirmado por Daniel el 26-nov y relayado por el Coordinador (memoria `traslados-pedido-sac-26nov.md`).
Estado: **solo plan. No se construye hasta el GO de QA 2 y la autorización de Daniel confirmada por el Coordinador.**
Si llegan más pedidos de Traslados antes del GO, el Coordinador los suma a esta versión.

**Adenda 1 (§10, al final):** GO de QA 2 sobre la v1.1 (`d16af57d…455d`) con una condición de texto y tres observaciones; se resuelven **solo en la adenda**, sin v1.2. El diseño y los números de la v1.1 no cambian; donde la v1.1 dice otra cosa, manda §10. Delta: `plan_v1.1_a_adenda1.diff` (con su sha256 en el mensaje de entrega).

**v1.1:** aplica C1–C4 y las observaciones O-a…O-e del veredicto de QA 2 sobre la v1.0 (`fa299fda…c8b8`; `~/sac-evidencia/2026-11-26/qa-2-traslados-fecha-totales/veredicto_plan_v10.md`). El diseño (D-a…D-m, O1–O3) no cambia. Qué cambió:
- **C1:** §2.2 trae el **código de referencia** de `transferTotals.ts` y §6.1 el **diff textual de cada mutante** de ese archivo. Se probó en un prototipo **fuera del repo** (`prototipo/` de la carpeta de evidencia; no se construye nada en el árbol): la referencia pasa U1–U10 y cada mutante cae donde §6 predice (`prototipo/plantar_u.log`). P9 pasa a «se suma el valor crudo, sin escala ni `num()`»; **P9b** («`num()` sobra con la escala») y P19 quedan declarados equivalentes.
- **C2:** P21 (el pie pinta el valor sin mirar `null` → «0 kg» / «$ 0») y E7 afirma los dos «—» y la ausencia de «0». Se agrega P22 (el cero real tratado como ausencia).
- **C3:** E2 despacha 100 y recibe 98 (2 % contra el 5 % de la org): existe la merma y se afirma la fecha en los **cuatro** efectos.
- **C4:** §0 y P11 corrigen la razón (recibir 0 queda retenido **y** no se puede resolver: defecto previo, §0 y §8).
- **Observaciones:** P16 pasa a `≥ {E5}` (O-a); E10 con control sobre el árbol base (O-b); E12 escribe cómo se navega y con guarda anti-vacuidad (O-c); E13 se declara en la entrega (O-d); **O4** en §1.3 es la decisión de Daniel sobre el pie sin aportantes (O-e).
- Comparado con la v1.0: `~/sac-evidencia/2026-11-26/coder-2-traslados-fecha-totales/plan_v1.0_a_v1.1.diff` (con su sha256 en el mensaje de entrega).

Evidencia de este plan: `~/sac-evidencia/2026-11-26/coder-2-traslados-fecha-totales/` (`dirigidas_grep.log`, `dirigidas_prediccion.log`, `golden_no_aplica.log`).

---

## 0. Lo que se verificó antes de planear

| Pregunta | Hallazgo (leído en el código, no de memoria) |
|---|---|
| ¿Qué pasa hoy con la fecha de recepción? | `TransferDetailPage.tsx:103` → `useState(toLocalDateInput(new Date()))`: arranca en **hoy**. El estado se crea antes de cargar el traslado (el componente hace `return` temprano en `:124`), así que no puede leer `t.dispatch_date`. El input tiene `max` = hoy (`:293`) y **no tiene `min`**. El payload es `receipt_date: \`${receiptDate}T12:00:00\`` (`:146`). |
| ¿Qué valida el backend? | `transfer.py:299-306`: sin `receipt_date` usa hoy; `> business_today()` → 400 «La fecha de recepción no puede ser futura»; `< dispatch_date` → 400 «no puede ser anterior al despacho». El servidor es el árbitro, la pantalla solo ayuda. |
| ¿Para qué se usa esa fecha? | `receipt_date` fecha **cuatro** cosas: los dos movimientos de inventario (tránsito → destino), la merma (`decrease` sobre tránsito), el libro kg `intersede_send` y el par de maquila (`transfer.py:401-423`, `:465-479`, `:547`, `:597`). Se guarda en `transfers.received_date`, y **`resolve` la reutiliza** (`:641`): una fecha mala en la recepción viaja a la resolución. **No hay edición de fechas** (el PATCH solo corrige la remisión): corregirla es anular y volver a registrar. |
| ¿Qué tipo es `dispatch_date`? | `BusinessDate` (mediodía UTC, `schemas/transfer.py:35`; el servicio lo acuña con `business_today_noon()`, `:167`). El helper para volverlo valor de `<input type="date">` ya existe y se usa igual en 4 pantallas de edición: `utcToLocalDateInput` (`formatters.ts:139`; `PurchaseEditPage`, `SaleEditPage`, `InboundEditPage`, `DoubleEntryEditPage`). |
| ¿Los intra-sede tienen formulario de recepción? | No: nacen `received` con `received_date = dispatch_date` (`transfer.py:178`) y la tarjeta de recepción solo sale con `status === "dispatched" && canReceive`. Este cambio no los toca. |
| ¿Cuándo llegan `kg_lead_equivalent` y `maquila_amount`? | Se asignan **solo** en `_emit_line_effects` (`transfer.py:505-583`), y solo a líneas **aportantes** (`is_contributor`). Despachado: todo `null`. Recibido dentro de tolerancia: se emiten. En discrepancia retenida (fuera de tolerancia, o recibido > despachado): la línea retenida queda con `effects_emitted = false` y valores `null`, mientras las demás ya los tienen. **Los dos campos pueden diferir en una línea ya emitida:** `maquila_amount` queda `null` si la tarifa/flag no está o si `kg × tarifa ≤ 0` (`:578-583`), con `kg_lead_equivalent` puesto. |
| ¿Qué pasa si una línea aportante se recibe en **0**? (C4, medido por QA 2) | Queda **retenida** (variación 100 % > tolerancia) y **no se puede resolver**: sobre la base `75f621a`, resolver con `justify` o con `correct` en 0 da `IntegrityError` (`ck_kg_ledger_movements_delta_nonzero`), porque `_emit_line_effects` manda `delta_kg = 0` al libro (500 en producción). Sonda: `~/sac-evidencia/2026-11-26/qa-2-traslados-fecha-totales/sonda_resolve_cero/sonda.log`. **Es un defecto previo y fuera de este plan** (§8): está en el backlog del Coordinador. Consecuencia aquí: el pie hace bien en decir «parcial» sobre esa línea, y el caso U5 (emitida con kg `"0.0000"` y maquila `null`) es **defensivo**: producción no lo produce. |
| ¿Anular borra esos valores de las líneas? | No (leído en **toda** la función `annul`, `transfer.py:838-975`): `annul` revierte movimientos pero no toca `kg_lead_equivalent`, `maquila_amount` ni `effects_emitted` de las líneas. Un traslado anulado sigue pintando los valores de lo que se **revirtió**. |
| ¿Cómo llegan los Decimal al navegador? | Como **string** en el JSON (`TransferLineResponse` declara `Decimal`; el tipo TS dice `number`; #93/#107). `services/transfers.ts` no coacciona. `LineRow` los pasa tal cual a los formateadores (Intl los acepta); una **suma** con `+` los concatenaría. |
| ¿Hay `TableFooter`? ¿Tests de frontend? | `components/ui/table.tsx:39` ya exporta `TableFooter`. El frontend no tiene vitest ni test runner: los casos se corren como en los ciclos anteriores (esbuild + node para las funciones puras; Playwright contra mi localhost para la pantalla). |
| Datos de mi BD (`reciclaje_coder_2`, leídos hoy) | Flags `kg_ledger_enabled`, `two_step_transfers_enabled`, `internal_maquila_enabled` en true; `plant_third_party_id` None (maquila como par interno); tarifa de maquila $1.500. Materiales aportantes: BAT-G1 (7,3 kg/u), BAT-G2 (9,3) y otros 18 con fórmula; no aportantes: ALU-01, CAJ-PLA, GUA-RRU…; bodegas Circunvalar, Molino, Juan Mina y sus tránsitos; **0 traslados**. |

---

## 1. Alcance y decisiones

### 1.1 Del pedido (ya tomadas por Daniel)

1. **Fecha de recepción:** arranca igual a la fecha de despacho y SAC la puede editar. Sigue con `max` = hoy y gana una pista «Fecha del despacho» bajo el campo.
2. **Totales:** la tabla «Líneas» del **detalle** suma los kg de plomo y la maquila, en una fila de totales. La lista de traslados no gana columnas.
3. Solo frontend, sin migración. El riesgo de (1) está aceptado por Daniel: si el material llega otro día y no se edita, la recepción queda **con la fecha del despacho**, y esa fecha mueve inventario, merma, kg intersede y el par de maquila. Caso concreto para que quede escrito: despachado el 31-oct y recibido el 3-nov sin tocar la fecha → los cuatro efectos caen en **octubre** (el P&L por sede mensual y el balance al 31-oct los ven allí).

### 1.2 Del plan (las juzga QA; las marcadas «O» las puede revertir Daniel)

- **D-a — La fecha por defecto es un valor derivado, no un estado inicial.** Estado `receiptEdit: { id, value } | null`; `null` = «sigue al despacho». El valor mostrado es `receiptEdit?.id === t.id ? receiptEdit.value : utcToLocalDateInput(t.dispatch_date)`. Dos razones de fondo: (1) el estado se crea antes de cargar el traslado; (2) **amarrar al id**: la fecha editada de un traslado no puede aplicarse a otro si React Router reutiliza el componente al cambiar `:id` (ir de un detalle a otro por el historial). Esa fecha tiene efecto financiero; la regla cuesta tres líneas. Los otros estados de la página ya tienen este problema (`remValue`, `annulReason`) y no se tocan.
- **D-b — Qué valida la pantalla y qué el servidor.** Solo el formato: la fecha vacía o incompleta deshabilita «Confirmar Recepción» (hoy un campo vaciado manda `T12:00:00` y devuelve un 422 de Pydantic ilegible). `min`/`max` se ponen como **atributos del input** (ayuda del selector), pero el botón **no** compara contra ellos: la regla vive en el servidor, que ya responde con mensajes claros (toast por `onError`). Razón: si el reloj del navegador no es el de Colombia, un gate local podría dejar el botón muerto sin salida, y eso es peor que un 400 legible.
- **D-c (O1) — `min` = fecha del despacho.** El pedido pide `max`; el `min` es del plan: la fecha por defecto es justamente el mínimo válido, y sin `min` el selector deja elegir días que el servidor rechaza. Es una sola prop; si Daniel no lo quiere, sale sin tocar nada más. **Recomendado: dejarlo.**
- **D-d — La pista.** Texto fijo bajo el campo: «Fecha del despacho: {dd/mm/aaaa}. Cámbiala si el material llegó otro día.» Es el aviso que aceptó Daniel; no explica los cuatro efectos (para eso está el riesgo de §1.1, que se comunica al cliente, no se pinta en pantalla).
- **D-e — Los totales son una función pura**, `utils/transferTotals.ts` (nueva), que recibe las líneas y devuelve por columna `{ value, pending, contributors, partial, emptyLabel }`. La pantalla solo pinta. La función es la que se prueba con casos U.
- **D-f — Qué cuenta como «tiene valor» y cómo se suma.** «Tiene valor» = `!= null` **antes** de coaccionar, porque `num(null)` da 0 y un cero fabricado es lo que el pedido prohíbe (un `"0.0000"` real, en cambio, **sí** es un valor). Se coacciona con el `num()` existente (`types/willard-delivery.ts`, ya exportado; no se crea una sexta copia). **Se suma en enteros**: cada valor se pasa a la escala de su columna (kg × 10⁴, pesos × 10²), se suman los enteros y se divide al final; así 0,1 + 0,2 da exactamente 0,3 y la suma queda «a centavos». Medido por QA 2 y confirmado en el prototipo: la multiplicación por la escala **ya** vuelve número al string, así que quitar `num()` conservando la escala no cambia el resultado (mutante equivalente **P9b**, declarado); `num()` se deja por contrato (una sola función conocida hace la coerción de la frontera). Lo que sí concatena strings es sumar el valor **crudo, sin escala** (P9). Se suman **todas** las líneas que muestran un valor: el total es exactamente lo que se ve en la columna.
- **D-g — «Parcial» se decide por líneas PENDIENTES, no por nulos.** `pending` = líneas **aportantes** con `!effects_emitted` (retenidas por discrepancia, o sin recibir). Hay marca parcial si hay suma **y** `pending > 0`: «parcial: faltan N de M líneas» (M = aportantes), en texto pequeño ámbar bajo la cifra, con `title` «Las líneas pendientes de resolver no están en la suma». Por qué no por nulos: una línea ya emitida con `maquila_amount = null` (porque `kg × tarifa ≤ 0`) es legítimamente cero, y marcarla como parcial sería una alarma falsa (caso U5, defensivo: ver §0 sobre la recepción en 0). Una línea no aportante (sin fórmula, o intra-sede) nunca cuenta como faltante.
- **D-h — Qué se pinta cuando no hay suma.** Misma regla que ya usa cada celda de línea: kg → **«N/A»** si el traslado no tiene ninguna línea aportante y **«—»** si las tiene pero ninguna tiene valor (despachado, o todas retenidas); maquila → siempre **«—»** (su celda de línea hoy no distingue). Nunca «0».
- **D-i — No se suman Despachado ni Recibido** (mezclan kg y unidades, #54): la fila de totales es `Total` (`colSpan=3`) + kg plomo + maquila.
- **D-j (O2) — Anulado: sin fila de totales.** Las líneas conservan los valores de lo que se revirtió; un «Total» ahí diría que existe una deuda y una maquila que ya no existen. El encabezado ya dice «Anulado el …». **Recomendado: ocultarla.** Las celdas de cada línea no se tocan (comportamiento de hoy).
- **D-k (O3) — Texto de la marca parcial** (D-g): «parcial: faltan 1 de 2 líneas». Puro copy; QA/Daniel lo ajustan sin afectar la lógica.
- **D-l — Formato.** kg con `formatWeight(v, "kg")` y maquila con `formatCurrency(v)`, **los mismos que usan las líneas**. Costo declarado: las líneas guardan hasta 4 decimales de kg y centavos de pesos y se muestran con 2 y 0; el total es la suma **exacta** y puede diferir en 0,01 kg o $1 de la suma de lo que se ve (U6 lo mide). Se descartó pintar el total con centavos: mezcla escalas dentro de la misma columna.
- **D-m — Sin hooks nuevos después del `return` temprano.** Los totales se calculan con una llamada simple después de `const t = transfer`, no con `useMemo`: un hook declarado después de `if (isLoading || !transfer) return …` es el bloqueante (a) de #93 (pantalla en blanco). La fila `P20` de la matriz lo planta.

### 1.3 Pendiente de confirmar (no frena el GO de QA; el Coordinador las pasa a Daniel si quiere)

| # | Decisión | Recomendada | Si Daniel elige otra |
|---|---|---|---|
| O1 | `min` = fecha del despacho en el input (D-c) | Dejarlo | Se quita la prop `min`; P6 deja de aplicar |
| O2 | Anulado sin fila de totales (D-j) | Ocultarla | Se pinta igual que en los demás estados, con una nota «anulado» |
| O3 | Texto de la marca parcial (D-k) | «parcial: faltan N de M líneas» | Cambia el texto, nada más |
| O4 | Pie en un traslado **sin ninguna línea aportante** (intra-sede, o materiales sin fórmula): hoy diría «Total — N/A — —», que es ruido (O-e de QA 2) | Mostrarlo, como lo pide el pedido («—» o «N/A», nunca cero) | El pie solo se pinta si `contributors > 0`: es **una condición** en la página (`showFooter`). Efecto en el plan: la etiqueta «N/A» del kg deja de aparecer en el pie, E8-TF y E11 pasan a afirmar que **no hay `<tfoot>`**, y P15 y P21 pierden su caída en E8-TF/E11 |

---

## 2. Diseño

### 2.1 `frontend/src/pages/transfers/TransferDetailPage.tsx` (editar, ~35 líneas)

- Se reemplaza `useState(toLocalDateInput(new Date()))` (`:103`) por `useState<{ id: string; value: string } | null>(null)`. El `useState` queda **arriba del `return` temprano**.
- Después de `const t = transfer`: `dispatchDateInput = utcToLocalDateInput(t.dispatch_date)`, `receiptDate = receiptEdit?.id === t.id ? receiptEdit.value : dispatchDateInput` (D-a), `receiptDateValid = /^\d{4}-\d{2}-\d{2}$/.test(receiptDate)` (D-b).
- `submitReceive` sigue mandando `receipt_date: \`${receiptDate}T12:00:00\`` (formato y semántica **idénticos** a los de hoy; solo cambia de dónde sale el valor).
- El `<Input type="date">` gana `min={dispatchDateInput}` (O1); `max` queda como hoy; `onChange` → `setReceiptEdit({ id: t.id, value: e.target.value })`. Bajo el campo, la pista de D-d.
- `receiveReady` suma `&& receiptDateValid`.
- Tabla «Líneas»: `<TableFooter>` con la fila de totales (D-h, D-i), **dentro del mismo `overflow-x-auto`** (a 390 se desplaza con la tabla). Se omite si `t.status === "annulled"` (O2).

### 2.2 `frontend/src/utils/transferTotals.ts` (nuevo, ~50 líneas)

**Código de referencia** (el que se construye, salvo un comentario de cabecera; es lo que los diffs de §6.1 mutan). Medido en un prototipo fuera del repo: `~/sac-evidencia/2026-11-26/coder-2-traslados-fecha-totales/prototipo/` (`transferTotals.ts`, `u_casos.ts`, `plantar_u.py`, `plantar_u.log`).

```ts
import { num } from "@/types/willard-delivery";
import type { TransferLineResponse } from "@/types/transfer";

export type TotalLine = Pick<
  TransferLineResponse,
  "is_contributor" | "effects_emitted" | "kg_lead_equivalent" | "maquila_amount"
>;

export interface ColumnTotal {
  value: number | null; // null = ninguna línea tiene valor
  pending: number; // aportantes con !effects_emitted
  contributors: number; // aportantes en total
  partial: boolean; // hay suma Y pending > 0
  emptyLabel: "—" | "N/A"; // lo que se pinta si value es null (D-h)
}

const KG_SCALE = 10_000;
const COP_SCALE = 100;

function column(
  lines: TotalLine[],
  pick: (l: TotalLine) => string | number | null | undefined,
  scale: number,
  noContributorLabel: "—" | "N/A"
): ColumnTotal {
  const contributors = lines.filter((l) => l.is_contributor).length;
  const pending = lines.filter((l) => l.is_contributor && !l.effects_emitted).length;
  let units = 0;
  let withValue = 0;
  for (const l of lines) {
    const raw = pick(l);
    if (raw == null) continue;
    units += Math.round(num(raw) * scale);
    withValue += 1;
  }
  if (withValue === 0) {
    return {
      value: null,
      pending,
      contributors,
      partial: false,
      emptyLabel: contributors === 0 ? noContributorLabel : "—",
    };
  }
  return { value: units / scale, pending, contributors, partial: pending > 0, emptyLabel: "—" };
}

export function transferTotals(lines: TotalLine[]): { kg: ColumnTotal; maquila: ColumnTotal } {
  return {
    kg: column(lines, (l) => l.kg_lead_equivalent, KG_SCALE, "N/A"),
    maquila: column(lines, (l) => l.maquila_amount, COP_SCALE, "—"),
  };
}
```

Sin dependencias de React ni de la red: se importa en node con esbuild para los casos U. La página pinta con `formatWeight(v, "kg")` / `formatCurrency(v)` **solo** cuando `value != null`; si es `null` pinta `emptyLabel` (D-h; P21 planta lo contrario).

### 2.3 Lo que NO cambia

Backend, migraciones, `services/transfers.ts`, `types/transfer.ts`, la lista de traslados, `TransferCreatePage` (su fecha de despacho sigue arrancando en hoy), la resolución de discrepancias, el diálogo de remisión, el Talonario. `LineRow` conserva sus celdas tal cual (incluida la coerción implícita por Intl).

---

## 3. Riesgos y caminos vecinos

| Riesgo | Cómo se cubre |
|---|---|
| El usuario confirma sin ver la fecha y la recepción cae en el día del despacho (aceptado, §1.1) | La pista bajo el campo (D-d) y E1/E3 miden qué fecha viaja. Se comunica al cliente con el ejemplo del cambio de mes. |
| Una fecha editada de un traslado se aplica a otro | D-a (amarrada al id). Caso E12; mutante P3. |
| Campo de fecha vaciado → 422 ilegible | D-b: botón deshabilitado. Caso E4; mutante P7. |
| `dispatch_date` mal convertido a `yyyy-mm-dd` | Se usa el helper existente (el mismo de 4 pantallas de edición); U10 fija el contrato con `TZ=America/Bogota` y `TZ=UTC` y con las tres formas de ISO (`…Z`, `+00:00`, sin zona). Límite conocido, igual que en esas pantallas: un navegador en UTC+12 o más correría el día; SAC opera en Colombia. |
| Un total que inventa ceros o concatena strings | D-f; U1, U2, U7; mutantes P9, P10, P22 y, **en la pantalla**, P21 (`formatWeight(null)` da «0 kg»; E7 afirma los dos «—» y la ausencia de «0»). |
| Alarma falsa de «parcial» | D-g (por pendientes); U5; mutantes P11, P13. |
| Total de un traslado anulado | O2; E9; mutante P14. |
| Hook declarado después del `return` temprano | D-m; mutante P20 (debe romper eslint y la pantalla). |
| Desborde a 390 | Pie dentro del contenedor con scroll; E10 mide `scrollWidth`; mutante P19. |
| Caminos vecinos de `TransferDetailPage` | Una sola ruta (`App.tsx:200`); se llega desde la lista, el Talonario y el redirect del despacho, y los tres pasan por el mismo componente. `resolve` lee `received_date` ya guardado: no cambia. Datos guardados: ninguno nuevo; lo ya recibido no se reescribe. |

---

## 4. Casos

### 4.1 Funciones puras — `u_casos.ts` (esbuild + node, en la carpeta de evidencia)

| # | Caso | Esperado |
|---|---|---|
| U1 | Todas las líneas aportantes emitidas, valores como **string** (`"73.0000"`, `"37.2000"`; `"109500.00"`, `"55800.00"`) | kg 110,2; maquila 165.300; `partial = false` |
| U2 | Aportantes sin recibir (todo `null`, `effects_emitted = false`) | `value = null`, kg `—`, maquila `—`, `partial = false` (no hay suma que marcar) |
| U3 | Ninguna línea aportante (`is_contributor = false`, `null`) | kg `N/A`, maquila `—` |
| U4 | Una emitida con valor + una aportante retenida (`effects_emitted = false`, `null`) | suma de la emitida; `pending = 1`, `contributors = 2`, `partial = true` |
| U5 | **Defensivo** (producción no lo produce, §0): dos aportantes emitidas; una con `kg = "0.0000"` y `maquila_amount = null` (`kg × tarifa ≤ 0`) | kg suma (el `"0.0000"` cuenta como valor); maquila = la otra línea; **`partial = false`** |
| U6 | Redondeo, se verifica el **valor** (no el texto formateado). **U6a** `"0.1000" + "0.2000"`; **U6b** `"1000.50" + "1000.50"`; **U6c** `"0.1111" + "0.2222" + "0.3333" + "0.4444"` | exactamente 0,3 (en flotante daría 0,30000000000000004); 2001; 1,111 (en flotante daría 1,1110000000000002) |
| U7 | `null` ≠ 0. **U7a** una sola línea con `"0.0000"`; **U7b** `"0.0000"` y `null` | el cero real cuenta como valor: `value = 0`, no `null` (U7a y U7b) |
| U8 | Mezcla: aportante emitida + no aportante emitida (`null`) | suma solo de la aportante; `contributors = 1`; `partial = false` |
| U9 | Una sola línea | el total es la línea |
| U10 | `utcToLocalDateInput` con `2026-11-23T12:00:00Z`, `…+00:00`, `…T12:00:00` (sin zona) | `"2026-11-23"` en las tres, con `TZ=America/Bogota` y con `TZ=UTC` |

**Medido sobre el prototipo** (`prototipo/`): la referencia de §2.2 pasa **13/13** (U1, U2, U3, U4, U5, U6a-c, U7a-b, U8, U9, U10) con `TZ=America/Bogota`, y U10 también con `TZ=UTC`.

### 4.2 Pantalla — `e2e_traslados_fecha_totales.cjs` (Playwright, **mi** :5182 → :8012 → `reciclaje_coder_2`)

Datos: se crean por la API y se revierten al final (§9). Usuario admin de SAC creado con `usuario.py crear` (clave en archivo 600, nunca en argv ni en el chat). **Se miden efectos, no pistas** (memoria `test-mide-efecto-no-pista`): la fecha se afirma en el cuerpo del `POST /receive` capturado **y** en lo que el servidor escribió.

| # | Caso | Datos | Qué se afirma |
|---|---|---|---|
| E1 | **Fecha por defecto = despacho** | TA: Circunvalar → Juan Mina, BAT-G1 × 5, **despachado hace 3 días** | El campo muestra la fecha del despacho (no hoy); la pista la nombra; al confirmar **sin tocar**, el cuerpo trae `receipt_date = "{despacho}T12:00:00"` y `received_date` del servidor tiene ese día |
| E2 | **Editarla y recibir con la elegida, y que el cambio llegue a los cuatro efectos fechados** (C3) | TA2: Circunvalar → Juan Mina, BAT-G1 × **100**, despachado hace 3 días; se **recibe 98** (variación 2 % contra el 5 % de la org: dentro de tolerancia, merma de 2) | Se elige despacho + 2 días: el cuerpo trae esa fecha, y **las cuatro** familias de filas que el traslado escribió tienen ese día: (1) los movimientos de inventario (tránsito → destino, `inventory_movements` por `reference_id`); (2) el ajuste **«Merma traslado #N»** (`inventory_adjustments` por `transfer_id`, campo `date`; cantidad 2); (3) el movimiento kg intersede (98 × 7,3 = 715,4 kg); (4) el par de maquila (`money_movements` por `source_type = 'transfer'`/`source_id`; 715,4 × 1.500 = $ 1.073.100); más `received_date`. Ninguna fila de las cuatro cae en el día del despacho ni en hoy. **Control anti-vacuidad:** cada una de las cuatro familias tiene al menos una fila (si no existiera, «ninguna en otro día» pasaría sola) |
| E3 | **Despachado hoy** | TB: BAT-G1 × 5, despachado hoy | Default = hoy = despacho; el cuerpo trae hoy; `max` del input = hoy |
| E4 | **Límites y servidor árbitro** | TA3: despachado hace 3 días | `min` = despacho y `max` = hoy (atributos del DOM); vaciar el campo **deshabilita** el botón; forzando una fecha anterior al despacho, el servidor responde 400 y el toast dice «no puede ser anterior al despacho»; el traslado sigue `dispatched` y **no se escribió ninguna fila** (conteos antes/después) |
| E5 | **Totales con todas las líneas** | TC: BAT-G1 × 10 + BAT-G2 × 4, recibido 10 y 4 (dentro de tolerancia) | La fila de pie dice exactamente `Total · 110,2 kg · $ 165.300` (tres celdas; **sin** Despachado/Recibido sumados), sin marca «parcial» |
| E6 | **Totales parciales** | TD: BAT-G1 × 10 + BAT-G2 × 4, recibido 10 y **6** (recibido > despachado → línea retenida) | Estado «En discrepancia»; pie = suma de la línea emitida (73 kg, $ 109.500) **más** «parcial: faltan 1 de 2 líneas» |
| E7 | **Ninguna línea con valor** | TB (despachado, sin recibir) | kg `—` y maquila `—` (los **dos** textos exactos) y **ningún «0»** en el pie: ni «0 kg» ni «$ 0» (C2) |
| E8 | **No aportantes** | **E8-TF:** solo ALU-01, cruzado, recibido · **E8-TE:** BAT-G1 + ALU-01, recibido | TF: kg `N/A`, maquila `—`, y ni «0 kg» ni «$ 0» (C2). TE: el pie suma solo BAT-G1 y **no** pinta «parcial» |
| E9 | **Anulado** | TG: copia de TC, anulado | No hay `<tfoot>`; las celdas de línea siguen como hoy |
| E10 | **A 390** | TC y TD, **y su control sobre el árbol base** | El pie se ve **dentro** del scroll de la tabla; `document.documentElement.scrollWidth ≤ 390`; la tarjeta de recepción se completa sin desborde. **Control (O-b):** antes de construir se mide `scrollWidth` a 390 de esos dos detalles con el front de `75f621a` (sin pie); si ya desbordaban, el caso mide solo el delta (ancho con pie − ancho base) y se declara |
| E11 | **Intra-sede** | TH: Circunvalar → Molino, recibido al nacer | No hay tarjeta de recepción; pie `N/A` / `—` (con O4 = no pintarlo: no hay `<tfoot>`); `received_date == dispatch_date` |
| E12 | **Estado amarrado al traslado** (O-c) | TA (despachado −3 d) y TI (despachado −5 d) | Se edita la fecha en TA y se navega a TI **sin recargar y sin pasar por la lista**: `history.pushState(null, "", "/transfers/<TI>")` + `window.dispatchEvent(new PopStateEvent("popstate"))` (React Router escucha `popstate` y **reutiliza** el componente). TI muestra **su** fecha de despacho, no la editada. **Guardas anti-vacuidad:** antes de editar se toma un `ElementHandle` del input de fecha de TA y tras navegar su `isConnected` sigue en `true` (el componente se reutilizó; si se hubiera desmontado, el estado se reiniciaría solo y el caso no probaría D-a), y la URL ya trae el id de TI. **P3 debe tumbarlo** (§6): si no cae, el caso era vacuo |
| E13 | **Sin permiso de recibir** (control de no regresión) | usuario con `inventory.view` y sin `inventory.transfer_receive`, si el aprovisionamiento existente (`aprovisionar.py`) lo permite sin código nuevo | No hay tarjeta de recepción; el pie sí aparece. **La entrega dice si E13 corrió o no** (O-d) |

Capturas a **1440 y 390** de E1, E3, E5, E6, E7 y E9, con datos de dev.

---

## 5. Set dirigido (por grep, no de memoria) y guardas

Medido el 26-nov sobre `75f621a` (`dirigidas_grep.log`):

- Tests de backend que **leen** `frontend/src`: `test_reloj_de_negocio.py` (rglob sobre todo `frontend/src`), `test_clave_sin_constante.py` (recorre `frontend/src` entero) y `test_third_parties.py` (solo `services/thirdParties.ts`; no toca este cambio).
- Nadie nombra `TransferDetailPage`, `utcToLocalDateInput` ni `transferTotals` en `backend/tests` ni `backend/scripts`.
- En el frontend, `TransferDetailPage` solo se importa en `App.tsx:106`; `receipt_date` solo está en `types/transfer.ts` y en la página; `utcToLocalDateInput` no se modifica.

Más las guardas que van **siempre** (CLAUDE.md, regla (b)): `test_reloj_de_negocio.py`, `test_advisory_locks.py`, `test_crucible_charges.py`.

**Comando** (mi BD de test, con los dos locks de siempre; lista en `dirigidas_archivos.txt`):

```
lockf -k ~/.cache/ecobalance/tests.lock lockf -k ~/.cache/ecobalance/coder2.lock \
  env TEST_DATABASE_URL=postgresql://admin:***@localhost:5433/reciclaje_test_coder_2 \
  ./venv/bin/pytest -q --no-cov -p no:cacheprovider \
  tests/test_reloj_de_negocio.py tests/test_advisory_locks.py \
  tests/test_crucible_charges.py tests/test_clave_sin_constante.py
```

**Predicción escrita antes: 68 passed** (`--collect-only` sobre los 4 archivos, `dirigidas_prediccion.log`), con **0 tests backend nuevos** (no hay cambio de backend). El reloj del frontend dice que un instante es `Date.now()`, nunca `new Date().toISOString()`; este cambio no agrega ninguna de las dos formas (solo usa `utcToLocalDateInput` y deja `toLocalDateInput(new Date())` donde ya estaba).

**Golden: no aplica, medido** (`golden_no_aplica.log`): `CAPTURES` = 14 entradas / 11 rutas, **ninguna** toca traslados, Entradas, remisiones ni kg; `git diff --name-only 75f621a -- backend/app backend/alembic` = vacío. Se re-mide con el comando sobre el SHA final de la entrega.

---

## 6. Matriz de plantado (escrita ANTES de plantar; no se reescribe — lo que falte va en una adenda)

Predicción: `=` es el conjunto exacto de casos que deben caer; `≥` es «al menos estos» (el defecto vive en una vía compartida y puede tumbar más; la prediccion no se afloja después). Cada fila se mide con el **número/texto** que cae, no solo con que caiga, y se clasifica cada caída por su causa (memoria `plantado-por-script-exige-exit`).

| # | Archivo | Defecto plantado | Predicción |
|---|---|---|---|
| P1 | `TransferDetailPage.tsx` | El estado vuelve a `useState(toLocalDateInput(new Date()))` (hoy) | = {E1, E12}; E3 **no** cae (despachado hoy: hoy = despacho) y es el control |
| P2 | `TransferDetailPage.tsx` | El valor por defecto sale de `created_at` en lugar de `dispatch_date` | = {E1, E12}; E3 no cae |
| P3 | `TransferDetailPage.tsx` | El estado editado no se amarra al id (`{value}` sin `id`) | = {E12}. **Si E12 no cae, el caso era vacuo** (O-c) |
| P4 | `TransferDetailPage.tsx` | El payload manda siempre el valor por defecto e ignora lo editado | = {E2} |
| P5 | `TransferDetailPage.tsx` | El payload **omite** `receipt_date` cuando no se editó (el servidor usa hoy) | ≥ {E1, E3} |
| P6 | `TransferDetailPage.tsx` | Se quita `min` del input | = {E4} |
| P7 | `TransferDetailPage.tsx` | Se quita `&& receiptDateValid` de `receiveReady` | = {E4} |
| P8 | `TransferDetailPage.tsx` | El valor del input es `formatDate(...)` (dd/mm/aaaa) en vez de `yyyy-mm-dd` | ≥ {E1, E3, E12} |
| P9 | `transferTotals.ts` | **Se suma el valor crudo, sin escala ni `num()`** (diff en §6.1; los strings se concatenan: «073.000037.2000») | ≥ {U1, U6, E5}. Medido en el prototipo: cae {U1, U4, U5, U6a, U6b, U6c, U7a, U7b, U8, U9} |
| P9b | `transferTotals.ts` | Se quita `num()` **conservando la escala** (`(raw as number) * scale`): la multiplicación ya vuelve número al string | **Mutante equivalente declarado** (C1 de QA 2): medido, no cae ningún caso. No se planta |
| P10 | `transferTotals.ts` | `null` cuenta como valor: se quita el `if (raw == null) continue;` (diff en §6.1) | ≥ {U2, U3, E7, E8-TF}. Medido: cae {U2, U3} |
| P11 | `transferTotals.ts` | Parcial = «con valor < aportantes» en vez de «pendientes > 0» (diff en §6.1) | = {U5}. **E2E no lo alcanza, y por dos razones** (C4): una recepción en 0 queda retenida por tolerancia **y** no se puede resolver (500 por `delta_kg != 0`, defecto previo de §0), así que no hay forma de llegar por la API a una línea emitida con maquila `null`. Medido: cae {U5} |
| P12 | `transferTotals.ts` | La marca parcial nunca se activa (`partial: false`) | ≥ {U4, E6}. Medido: cae {U4} |
| P13 | `transferTotals.ts` | La marca parcial se activa siempre que haya aportantes (`partial: contributors > 0`) | ≥ {U1, U5, U8, E5, E8-TE}. Medido: cae {U1, U5, U8} |
| P14 | `TransferDetailPage.tsx` | La fila de totales también sale en anulado | = {E9} |
| P15 | `transferTotals.ts` | Se intercambian `N/A` y `—` en kg (diff en §6.1) | ≥ {U2, U3, E7, E8-TF, E11}. Medido: cae {U2, U3} |
| P16 | `TransferDetailPage.tsx` | El pie suma también Despachado/Recibido (tres celdas en vez del `colSpan=3`) | ≥ {E5} (O-a: E6–E9 también leen el pie; si alguno mira las celdas, cae de más) |
| P17 | `transferTotals.ts` | Suma en flotante con `num()`, sin pasar a enteros (diff en §6.1) | = {U6} (U6a y U6c; U6b y U1 pasan porque ahí el flotante es exacto). En pantalla es invisible: el formateo a 2 / 0 decimales lo esconde; queda declarado. Medido: cae {U6a, U6c} |
| P18 | `TransferDetailPage.tsx` | El pie se pinta **fuera** del contenedor `overflow-x-auto` con ancho fijo | = {E10} |
| P19 | `transferTotals.ts` | Un valor `NaN` (string no numérico) se suma como número: `num(raw)` → `Number(raw)` | **Mutante equivalente declarado**: la API no manda esos valores y ningún caso los usa. Medido: no cae ninguno. No se planta |
| P20 | `TransferDetailPage.tsx` | El cálculo de totales va en un `useMemo` **después** del `return` temprano | eslint **sale distinto de 0** (`rules-of-hooks`; techo 37 → error) y ≥ {E1…E13} (pantalla en blanco al cargar) |
| P21 | `TransferDetailPage.tsx` | **El pie pinta `formatWeight(totals.kg.value, "kg")` y `formatCurrency(totals.maquila.value)` sin mirar `value == null`**: `formatWeight(null)` da «0 kg» y `formatCurrency(null)` da «$ 0» (`formatters.ts:20-22, :35-37`), o sea el cero fabricado que el pedido prohíbe (C2). Ninguna U lo ve: `transferTotals` queda bien y el defecto está en la pantalla | ≥ {E7, E8-TF, E11}; E7 afirma los dos «—» y la ausencia de «0» |
| P22 | `transferTotals.ts` | El cero real se trata como ausencia: `if (raw == null \|\| num(raw) === 0) continue;` (diff en §6.1) | = {U7}. Medido: cae {U7a, U7b} |

Notas: P9b y P19 se listan para que su ausencia no se lea como olvido (equivalentes declarados, sin plantar). Los «medido» de las filas de `transferTotals.ts` salen del prototipo (`prototipo/plantar_u.log`); los de pantalla se miden al plantar. Si una fila sale distinta de lo predicho, se explica y se agrega una adenda; no se edita esta tabla.

### 6.1 Diffs textuales de los mutantes de `transferTotals.ts` (C1 de QA 2)

Cada diff es contra el código de referencia de §2.2: reemplazo de texto exacto, con **una sola coincidencia** por reemplazo (`prototipo/plantar_u.py` aborta si no, porque un mutante que no se aplicó no mide nada). Los `.diff` completos con su numeración de línea están en `prototipo/mut/`; la salida de la corrida, en `prototipo/plantar_u.log`.

```diff
# P9
-    units += Math.round(num(raw) * scale);
+    units += raw as unknown as number;
-  return { value: units / scale, pending, contributors, partial: pending > 0, emptyLabel: "—" };
+  return { value: units, pending, contributors, partial: pending > 0, emptyLabel: "—" };

# P9b (equivalente: no se planta)
-    units += Math.round(num(raw) * scale);
+    units += Math.round((raw as unknown as number) * scale);

# P10
-    if (raw == null) continue;

# P11
-  return { value: units / scale, pending, contributors, partial: pending > 0, emptyLabel: "—" };
+  return { value: units / scale, pending, contributors, partial: withValue < contributors, emptyLabel: "—" };

# P12
-  return { value: units / scale, pending, contributors, partial: pending > 0, emptyLabel: "—" };
+  return { value: units / scale, pending, contributors, partial: false, emptyLabel: "—" };

# P13
-  return { value: units / scale, pending, contributors, partial: pending > 0, emptyLabel: "—" };
+  return { value: units / scale, pending, contributors, partial: contributors > 0, emptyLabel: "—" };

# P15
-      emptyLabel: contributors === 0 ? noContributorLabel : "—",
+      emptyLabel: contributors === 0 ? "—" : noContributorLabel,

# P17
-    units += Math.round(num(raw) * scale);
+    units += num(raw);
-  return { value: units / scale, pending, contributors, partial: pending > 0, emptyLabel: "—" };
+  return { value: units, pending, contributors, partial: pending > 0, emptyLabel: "—" };

# P19 (equivalente: no se planta)
-    units += Math.round(num(raw) * scale);
+    units += Math.round(Number(raw) * scale);

# P22
-    if (raw == null) continue;
+    if (raw == null || num(raw) === 0) continue;
```

---

## 7. Gates, en el orden del flujo con QA (CLAUDE.md del repo, 17-nov)

1. **Este plan → GO de QA 2 → autorización de Daniel** (la confirma el Coordinador). Un mensaje de QA no es una aprobación de Daniel.
2. **Construcción:** los dos archivos de §2. Autor corre solo: `tsc`, `eslint` (techo **37**, sin warnings nuevos), `build`, los casos U y E de §4. Sin push.
3. **QA pasada 1:** el delta como patch con su sha256, la base `75f621a` y el sha256 de cada archivo; el árbol queda quieto (si hay que editar, el aviso va antes).
4. Correcciones; QA relee el delta.
5. **Gates:** las dirigidas de §5 (68), el plantado de §6 con la predicción escrita (restauración por ruta y cierre por sha256 contra el árbol entregado; los defectos se plantan **con :8012 y :5182 parados o avisados**, memoria `plantar-con-pantalla-viva`), golden «no aplica» re-medido, capturas a 1440 y 390.
   **Suite completa diferida al checkpoint** (regla del 19-nov): este plan no cita una suite que no corrió.
6. **QA pasada 2:** evidencia y cualquier delta → OK de commit.
7. Commit a la rama `coder-2/traslados-fecha-totales`. Push y deploy solo con el OK de Daniel; **la integración a develop la hace el Coordinador**.

**Nivel: lógica** (no chico), aunque no toque el backend: el valor por defecto de la fecha decide el día en que caen inventario, merma, kg intersede y maquila. Los totales solos serían nivel chico.

---

## 8. Fuera de este ciclo (se anota, no se hace)

- Columnas de kg plomo y maquila en la **lista** de traslados (el pedido es solo del detalle).
- Coerción de los `Decimal` en la frontera de `services/transfers.ts` (la regla de #107): hoy la absorbe el helper de totales; llevar la coerción al servicio es un ciclo propio que toca todo consumidor de `TransferResponse`.
- Que `TransferCreatePage` ofrezca la fecha de despacho a partir de otra cosa (sigue en hoy).
- Un campo para **corregir la fecha de recepción** después de confirmar: hoy se anula y se vuelve a registrar. Si SAC lo pide después de ver el cambio, es un PATCH con efectos (mueve cuatro tipos de fila) y exige su propio plan.
- Totales por unidad de Despachado y Recibido.
- **Defecto previo, fuera de este plan** (medido por QA 2, `~/sac-evidencia/2026-11-26/qa-2-traslados-fecha-totales/sonda_resolve_cero/sonda.log`): recibir 0 en una línea aportante y resolverla (`justify` o `correct` con 0) revienta con 500 por `ck_kg_ledger_movements_delta_nonzero`, y la línea queda retenida para siempre. Está en el backlog del Coordinador; este plan no lo toca.
- El caso `transfer_formula_missing` (línea aportante sin snapshot de fórmula: `receive` la marca emitida sin kg y el pie no la cuenta como pendiente): previo e inalcanzable por construcción (O-f de QA 2). No hay nada que hacer aquí.

---

## 9. Datos y localhost del ciclo

- Backend `:8012` y front `:5182`, **solo** de mi worktree y mi BD `reciclaje_coder_2`; nunca `:8001` ni `:5174`. Antes de levantarlos se verifica que los puertos estén libres; el PID que escucha tiene que ser el que lancé y su `cwd` dentro de mi worktree. El front se verifica contra `VITE_API_URL` (que apunte a :8012), no se da por hablado con este backend.
- Línea base antes de crear datos: **0 traslados**, 8647 `inventory_movements`, hash de stock `3318df5b…` (los mismos del ciclo anterior). Se re-miden al empezar.
- Los traslados de E1–E13 se crean por la API con las remisiones `E2E-…` y **se revierten** al final con el mismo procedimiento que ya usé (`anular_todo.cjs` → `limpiar_datos.py aplicar` → `usuario.py quitar` → bajar los dos puertos), con el assert de conteos == línea base. La limpieza del ciclo anterior queda como precedente (`~/sac-evidencia/2026-11-25/traslados-remision/localhost/limpieza_final_*.log`).
- Evidencia: `~/sac-evidencia/2026-11-26/coder-2-traslados-fecha-totales/`.

---

## 10. Adenda 1 — E12 sin guarda falsa, E2 solo sobre las filas de la recepción, los mutantes de pantalla, y una cita corregida (sobre la v1.1 `d16af57d…455d`; veredicto de QA 2: `~/sac-evidencia/2026-11-26/qa-2-traslados-fecha-totales/veredicto_plan_v11.md`)

### A1.1 — C1 de QA 2: el orden de E12 que conserva el nodo (reemplaza la fila E12 de §4.2)

La guarda `isConnected` de la v1.1 estaba mal planteada: `useTransfer` no usa `keepPreviousData`, así que al navegar a un traslado que **no** está en la caché de React Query, `isLoading` es `true`, la página devuelve «Cargando…» (`TransferDetailPage.tsx:124`) y la tarjeta de recepción con su input se **desmontan** y se vuelven a crear al cargar, mientras el componente de la página y su estado siguen montados. Entonces `isConnected` daría `false` aunque D-a sea justo lo que se prueba.

**E12, orden nuevo** (par propio **TJ** −3 días y **TI** −5 días, ambos despachados; **E12 no recibe nada**, así que no se consumen):
1. Abrir **TI** (`page.goto`): queda en la caché de React Query.
2. Navegar a **TJ** con `history.pushState(null, "", "/transfers/<TJ>")` + `window.dispatchEvent(new PopStateEvent("popstate"))`. TJ no está en caché: pasa por «Cargando…» y carga. **Ahí** se toma el `ElementHandle` del input de fecha de TJ y se edita la fecha a **despacho de TJ + 1 día** (distinta del default de TJ, del de TI y de hoy).
3. Volver a **TI** con `pushState` + `popstate`. TI sí está en caché: se pinta de inmediato, sin «Cargando…».
4. Se afirma: la URL trae el id de TI; **`handle.isConnected === true`** (la tarjeta no se desmontó mientras el estado de TJ persistía: es la **precondición** que hace significativo el caso); y el input muestra **la fecha de despacho de TI**, no la editada en TJ.

Si `isConnected` da `false`, E12 se reporta **«no concluyente»**, nunca como PASA. **El criterio final no es la guarda sino P3:** P3 (el estado sin amarrar al id) **debe tumbar E12** (con P3 el input de TI mostraría la fecha editada de TJ). Si P3 no cae, E12 era vacuo y se corrige antes de seguir.

### A1.2 — O-1: en E2, «ninguna fila en el día del despacho» solo aplica a las filas de la recepción

Los movimientos de inventario del **despacho** (origen → tránsito) llevan el mismo `reference_id` del traslado y la **fecha del despacho**, y deben seguir así. Corrección a E2 (§4.2):
- La aserción «ninguna fila en el día del despacho ni en hoy» va **solo** sobre las filas de la recepción: los `inventory_movements` con `reference_id` = el traslado y `notes` = `Recepción traslado #N` (los dos: sale del tránsito y entra al destino), el ajuste «Merma traslado #N» (`inventory_adjustments.transfer_id`, campo `date`), el movimiento kg intersede y el par de maquila.
- **Control de no retroactividad:** los movimientos del despacho (los que tienen `notes` `Traslado #N → …` y `Traslado #N desde …`) **siguen con la fecha del despacho**. Se afirma: si la recepción reescribiera el despacho, caería.
- Anti-vacuidad (de la v1.1, se conserva): cada una de las cuatro familias de la recepción tiene al menos una fila.

### A1.3 — O-2: los mutantes de pantalla llegan como diff textual contra el código construido, antes de plantar

Los mutantes de `TransferDetailPage.tsx` (P1–P8, P14, P16, P18, P20, P21) siguen en prosa porque el código no existe. El diff textual contra el código construido solo puede escribirse **después de construir**, y la matriz no se reescribe después de plantar. Por eso, **dos entregas**: esta adenda 1 (texto, ahora) y una **adenda 2** con esos diffs, que va **junto con el patch de la pasada 1** y **antes de plantar**, con el sha256 de cada diff y el de la página construida. Condición de QA, que queda escrita aquí: **P18 usa un ancho fijo mayor que 390 px** (el pie va en su propia `<Table className="min-w-[560px]">` **fuera** del contenedor `overflow-x-auto`), porque con menos E10 no puede caer.

### A1.4 — O-3: una cita corregida

En §3, la fila «Desborde a 390» dice «mutante P19»: léase **P18**. P19 es el mutante del `NaN`, equivalente y sin caso (§6).

---

## 11. Adenda 2 — diffs textuales de los mutantes de pantalla contra el código construido, y lo que la lectura del código obliga a afinar (sobre v1.1 + adenda 1 `dddaaed9…0ee0ad`; base `75f621a`)

**Se escribe ANTES de plantar y no se edita después.** Si el plantado da distinto de lo aquí escrito, se explica en una adenda 3; esta no se toca.

### A2.1 — Qué código es «el construido»

| Archivo | sha256 |
|---|---|
| `frontend/src/pages/transfers/TransferDetailPage.tsx` (construida) | `586f5d5bbf089b8f4c7c8d1a5d330d3e9066ad0e4e69c790b44428be070552f3` |
| `frontend/src/utils/transferTotals.ts` (construida) | `6699bfb9b3fd688670aec102ea7b82ed47629659ca12fc7c373e130dbfb18a3b` |

Los mutantes salen de `pantalla_mut/plantar_pantalla.py`, que parte de una copia de esa página (`base/`, mismo sha256 que el repo), exige **exactamente una coincidencia por reemplazo** (si no, muere: un mutante que no se aplicó no mide nada) y escribe los `.diff` con numeración de línea y el `.tsx` de cada mutante. **Los 13 compilan** (`esbuild`, `compila_mutantes.log`; con control positivo: una copia con `<TableFooterX` falla, o sea que el chequeo discrimina). Todo en `~/sac-evidencia/2026-11-26/coder-2-traslados-fecha-totales/pantalla_mut/` (`SHA256SUMS` lista también el sha256 de cada `.tsx`). El plantado real usa ese mismo script sobre la ruta del repo, con respaldo por ruta y cierre por sha256 contra `586f5d5b…`.

### A2.2 — Los diffs (sin numeración, para leerlos; los numerados están en `mut/Pn.diff`, con su sha256)

```diff
# P1  (sha256 del .diff: 52738a3e1a4f564410e9285010b08b755108956bd50d66e087ab5f99e89046b5)
-  const receiptDate = receiptEdit?.id === t.id ? receiptEdit.value : dispatchDateInput;
+  const receiptDate = receiptEdit?.id === t.id ? receiptEdit.value : toLocalDateInput(new Date());

# P2  (5cb64d02443bef90614ea2d013c18554c4b3b5b6fb6e5468f08c13a7b43edecc)
-  const receiptDate = receiptEdit?.id === t.id ? receiptEdit.value : dispatchDateInput;
+  const receiptDate = receiptEdit?.id === t.id ? receiptEdit.value : utcToLocalDateInput(t.created_at);

# P3  (e457dad8e21742974beeccfe2a4b24fa0c29e0a3a5308151263c4c0ce4d216de)
-  const receiptDate = receiptEdit?.id === t.id ? receiptEdit.value : dispatchDateInput;
+  const receiptDate = receiptEdit ? receiptEdit.value : dispatchDateInput;

# P4  (6c95f11982031777c05dfb716055c9e9851b150aefc6d296338d5364959cd654)
-        receipt_date: `${receiptDate}T12:00:00`,
+        receipt_date: `${dispatchDateInput}T12:00:00`,

# P5  (08bb4c993776f0bf35ee56196f30de5fa169cc104cb2922ac44bfd2b8fdc098a)
-        receipt_date: `${receiptDate}T12:00:00`,
+        receipt_date: receiptEdit?.id === t.id ? `${receiptDate}T12:00:00` : undefined,

# P6  (bf2abac0709991c8d9bd6ae2564aba312fc36a53ea822f8edae5839588c845b2)
-                  min={dispatchDateInput}

# P7  (aa5f4dc1c426a352625b4d8482729f51c212757161c702a622a8814de9fc9f5b)
-  const receiveReady = t.lines.every((ln) => recvQty[ln.id] != null) && receiptDateValid;
+  const receiveReady = t.lines.every((ln) => recvQty[ln.id] != null);

# P8  (b96ab49d95e0eb63b9799f89679268045c817088d1b1b770dca0a68f6e0165fb)
-                  value={receiptDate}
+                  value={formatDate(receiptDate)}

# P14 (b66bdd60d1a1af5ae4654d48293fca2948c3ecaf2472aa67805419e81e0e6361)
-              {t.status !== "annulled" && (
+              {true && (
                 <TableFooter>

# P16 (5a668e981a85bf381c8816ef835625994d84963eba1497daec0f2ee0ab875888)
-                    <TableCell colSpan={3}>Total</TableCell>
+                    <TableCell>Total</TableCell>
+                    <TableCell className="text-right">{t.lines.reduce((a, l) => a + Number(l.quantity_dispatched), 0)}</TableCell>
+                    <TableCell className="text-right">{t.lines.reduce((a, l) => a + Number(l.quantity_received ?? 0), 0)}</TableCell>

# P18 (61338f21c94aa2001658eb7ef3017b5e432dba9efebd0af00b4f8ec53fca7164)
# el pie sale del <Table> (y del contenedor overflow-x-auto) a un <table> HTML CRUDO de 600 px
-              {t.status !== "annulled" && (
-                <TableFooter>
-                  <TableRow>
-                    <TableCell colSpan={3}>Total</TableCell>
-                    <TableCell className="text-right"> … TotalValue kg … </TableCell>
-                    <TableCell className="text-right"> … TotalValue maquila … </TableCell>
-                  </TableRow>
-                </TableFooter>
-              )}
             </Table>
           </div>
+          {t.status !== "annulled" && (
+            <table className="w-[600px] text-sm">
+              <tfoot>
+                <tr>
+                  <td colSpan={3}>Total</td>
+                  <td className="text-right"> … TotalValue kg … </td>
+                  <td className="text-right"> … TotalValue maquila … </td>
+                </tr>
+              </tfoot>
+            </table>
+          )}

# P20 (b5285012f700bfa62d6506b87b2c28b8fb544015f477c0cc1694319d1b8db21b)
-  const totals = transferTotals(t.lines);
+  const totals = useMemo(() => transferTotals(t.lines), [t.lines]);

# P21 (4e070c728ab857718f8776bf6493ae960d080915cc22b6f924a602f957a2f244)
-                      <TotalValue total={totals.kg} render={(v) => formatWeight(v, "kg")} />
+                      {formatWeight(totals.kg.value, "kg")}
-                      <TotalValue total={totals.maquila} render={formatCurrency} />
+                      {formatCurrency(totals.maquila.value)}
```

En P18 las `…` abrevian el cuerpo idéntico de cada celda; el `.diff` numerado trae el texto completo. P18 es, como pidió QA 2, un elemento **crudo** de ancho fijo mayor que 390 fuera del contenedor, **no** un `<Table>` de shadcn (ese lleva dentro su propio `div.overflow-auto` y no podría ensanchar nada).

### A2.3 — Lo que se afina al leer el código construido (predicciones escritas antes de plantar)

La matriz de §6 no se reescribe; estas son **precisiones de predicción** y de casos, fechadas antes de plantar, que salen de leer la página construida:

1. **P2 muta solo el valor por defecto, no `min`.** Si el mutante cambiara `dispatchDateInput` (la variable), también movería `min` y E4 caería de más; la fila de §6 dice «el valor por defecto sale de `created_at`» y eso es lo que se planta. Predicción de §6 intacta: **= {E1, E12}**, E3 no cae (despachado hoy: `created_at` y despacho son el mismo día).
2. **P4 cae también en E4: predicción = {E2, E4}, no {E2}.** En la página construida el payload de P4 ignora **todo** lo editado, y E4 fuerza una fecha anterior al despacho justamente editando el input: con P4 el cuerpo llevaría la fecha por defecto, el servidor respondería 200 y E4 (que afirma 400, toast y traslado aún `dispatched`) caería. La fila de §6 estaba incompleta; se corrige aquí, antes de plantar, y E1/E3 siguen sin caer (no se edita).
3. **E4 debe llenar las cantidades antes de vaciar la fecha.** Si el botón ya estuviera deshabilitado por falta de cantidades, «vaciar el campo deshabilita el botón» pasaría sola y **P7 no caería** (el caso sería vacuo). E4 afirma: con cantidades llenas y la fecha presente el botón está **habilitado** (control positivo), y con la fecha vaciada está **deshabilitado**. Predicción de §6 intacta: P7 = {E4}.
4. **E10 mide tres cosas, no una.** `main#main-scroll` es `overflow-y-auto`, y en CSS un `overflow-y` distinto de `visible` vuelve `overflow-x: visible` en `auto`: cualquier elemento que desborde hace **scroll dentro de `main`** y `document.documentElement.scrollWidth` se queda en 390. Con solo ese número P18 pasaría. E10 afirma, a 390: (a) `tfoot.closest(".overflow-x-auto")` **no es null** (la condición de QA 2); (b) `document.documentElement.scrollWidth ≤ 390` **y** `main#main-scroll.scrollWidth ≤ main#main-scroll.clientWidth`; (c) la tarjeta de recepción se completa sin desborde. Al plantar P18 se reportan los tres **números** (el `scrollWidth` y el `clientWidth` de `main`, el del documento y si `closest` dio null), no solo que cae. Predicción: P18 = {E10}.
5. **E11 también afirma la ausencia de «0 kg» y «$ 0».** El pie de un traslado intra-sede (sin aportantes) dice `N/A` y `—`; sin esa aserción de ausencia P21 no caería en E11 y la predicción `≥ {E7, E8-TF, E11}` sería falsa. Se afirma en E7, E8-TF y E11.
6. **Orden de datos del plantado.** E1, E2, E4, E5, E6 y E8 **consumen** traslados (los reciben). Cada corrida del e2e crea sus propios traslados por la API (remisiones `E2E-<corrida>-…`) y la limpieza (`anular_todo.cjs` → `limpiar_datos.py aplicar`) los revierte al final; el plantado de cada mutante usa datos frescos, así un traslado ya recibido por una corrida anterior no la contamina.
7. **P9b y P19 siguen sin plantarse** (equivalentes declarados en §6). P20 se mide además con `eslint --max-warnings 37` (debe salir distinto de 0, error `react-hooks/rules-of-hooks`).

### A2.4 — Lo que NO cambia

Alcance, decisiones D-a…D-m y O1–O4, set dirigido (68), golden «no aplica» (se re-mide sobre el SHA final) y flujo de gates: igual que v1.1 + adenda 1. Los 13 mutantes de pantalla de esta adenda son los mismos de §6 (P1–P8, P14, P16, P18, P20, P21); solo cambió que ahora existe el código contra el cual escribirlos.
