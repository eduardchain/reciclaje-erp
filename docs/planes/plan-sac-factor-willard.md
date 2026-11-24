# Plan: elegir el factor de conversión de Willard al liquidar (v1.2)

> **v1.1 (24-nov):** Q-76 respondida por Daniel («está bien al 59»). Sale la acción propia de corregir una Willard liquidada (era D6 en v1.0). Un factor mal escogido se corrige por el camino que ya existe: anular y registrar de nuevo (D6 nuevo, medido). Cambian §1, D3, D5, D6, D7, §7, §8 y §10. **v1.2:** C1 y O1 del veredicto de QA 1 sobre la v1.1 (`veredicto_plan_v1.1.md`): los dos costos que faltaban en D6 y T8 con valores esperados. Entran también las notas de QA 1 sobre la v1.0 (`~/sac-evidencia/2026-11-24/qa-1-factor-willard/notas_plan_v1.0.md`): A1 y A2 en D3, A3 en D8, A4 en D5, A5 en D6, O1 en D1 y O2 en D1 y D2.

- **Pedido:** SAC, 24-nov, autorizado por Daniel («esos dos, dale»). Inventario, sección D, filas del 24-nov.
- **Nivel:** lógica (contrato del back, migración, regla de kilos).
- **Base:** develop `5139940`. Rama `coder-1/factor-willard`.
- **Evidencia:** `~/sac-evidencia/2026-11-24/coder-1-factor-willard/` (`medicion_lectores_y_golden.log`) y la lectura de prod del Coordinador (`~/sac-evidencia/2026-11-24/coordinador-control/leer_seco*.log`, solo GET).

## 1. Qué se pide y qué ya está respondido

- SCRAP SECO GRANDE (SCR-SG) es **un** material y **una** cuenta con Willard. Willard lo parte en seco escurrido (56 %) y seco pinza (59 %).
- Al liquidar una Entrada de Willard, SAC quiere escoger el factor **línea por línea**, de una lista de factores del material, con uno por defecto.
- Respondido, no se repregunta:
  - Solo en Entradas de **Willard**; la compra regular no maneja factor.
  - Q-73 sin objeto: ese seco no llega a planta. Traslados, maquila y deuda intersede no cambian.
  - Q-74: una sola cuenta. El libro en kilos no se parte; basta guardar el factor escogido en cada línea.
- **Q-76**, respondida por Daniel el 24-nov: «está bien al 59» (§8).

Contexto: CC-001 (16-jul, #77) resolvió escurrido y pinza como **dos materiales**. La respuesta del 24-nov lo cambia a **un material con dos factores**. Este plan no revive el `subtype` que #77 borró ni crea una segunda fórmula vigente.

## 2. Lo que hay hoy

- `material_conversion_formulas` es append-only. La vigente es `max(created_at, id)` por material (`DISTINCT ON`). `drosses_to_lead` guarda `{lead_percentage}`.
- La Entrada de Willard se «liquida» con `POST /inbound-orders/{id}/confirm`, sin cuerpo (`inbound_order.py:1305`). `confirm` borra las líneas de la captura y las recrea en `_apply_willard_effects` (l.1481). Ahí:
  - `_compute_kg_lead` (l.2590) multiplica por la fórmula vigente;
  - cada línea escribe un `KgLedgerMovement` con `conversion_formula_snapshot` (l.1576).
- La edición D18 de una confirmada (`update`, l.1846) hace revert-and-reapply con la fórmula vigente.
- La anulación (`_revert_willard_effects`, l.1587) anula los movimientos kg por `source_id`, sin recalcular nada.

**Lectores de la fórmula vigente** (medidos con grep, `medicion_lectores_y_golden.log`). Todos leen `parameters["lead_percentage"]` y deben seguir viendo el factor por defecto:

| Lector | Dónde |
|---|---|
| Entrada de Willard | `inbound_order.py` `_compute_kg_lead` |
| Traslado (snapshot al despachar) | `transfer.py:1125` |
| Salidas de Plomo | `willard_delivery.py:422` |
| Documento de crisol | `crucible_charge.py:532` |
| Front: kg estimados | `InboundCreatePage` (`estimateKgLead`), `InboundDetailPage`, `StockPage`, `CrucibleChargeCreatePage:97` |
| Config → Materiales (kg) | `FormulasPage` (pinta, edita y compara) |
| Seeder | `seed_sac_org.py:1041` (escribe `{lead_percentage}`) |
| Revisión de archivo | `archivar_org_sac.py:345-349` |

⚠️ `archivar_org_sac.py --modo revisar` compara la fórmula **solo si `parameters` tiene una clave** (`len(valores) == 1`). Con la lista de factores, avisaría «fórmula distinta» en falso. Se corrige en este ciclo (D2).

## 3. Decisiones

### D1 — La lista vive DENTRO de la fórmula vigente

`drosses_to_lead` gana dos claves opcionales:

```json
{
  "lead_percentage": 0.59,
  "label": "Seco pinza",
  "alternatives": [{"label": "Seco escurrido", "lead_percentage": 0.56}]
}
```

- **`lead_percentage` sigue siendo el factor por defecto**, y es lo único que leen los lectores de §2. Ninguno cambia: sigue habiendo **una** fórmula vigente por material, y el valor que leen no se mueve.
- La lista se versiona con la fórmula (append-only, #35): cambiar un factor es una versión nueva, y el historial de Config la muestra.
- **Por qué no una tabla aparte:** el factor por defecto quedaría en dos sitios (la fórmula y la tabla), y dos copias de una regla se separan. **Por qué no una segunda fórmula vigente:** la vigente es una por material por construcción (`DISTINCT ON`), y todos los lectores de §2 tomarían la que tenga el `created_at` mayor.
- **Validación** en `DrossesToLeadParams` (`extra="forbid"` se mantiene), con 422:
  - `alternatives` solo en `drosses_to_lead`; en `battery_to_lead` no existe (fuera de alcance, §9).
  - Con `alternatives`, `label` es obligatorio: el factor por defecto necesita nombre para mostrarse en la lista.
  - Entre 1 y 5 alternativas. Cada `label` de 1 a 40 caracteres, sin espacios a los lados.
  - Los nombres no se repiten, comparados con `normalize_entity_name` (#78), contando el del defecto.
  - Cada `lead_percentage` en (0, 1], distinto del defecto y de las demás: una opción que no cambia el número no es una opción.
- `canonical_parameters` convierte a float de forma **recursiva**, también dentro de `alternatives` (O2). Hoy solo convierte el primer nivel, y un `Decimal` anidado revienta el JSONB con 500 (racional H1).
- **Declarado (O1):** el servidor acepta `alternatives` en cualquier `drosses_to_lead`, también en un material que no es de Willard (por ejemplo DROSS-CRI). Ahí son inertes: el único lector de la lista es la confirmación de una Willard (D3), y los demás leen `lead_percentage`. La pantalla solo ofrece el editor en materiales con mundo Willard (D7).

### D2 — Ningún escritor borra la lista sin querer (lección de #103 D4)

FormulasPage arma `{lead_percentage}` solo (l.253) y el seeder igual (l.1041): al versionar, borrarían la lista en silencio.

- **Servidor:** al crear una versión, si el cuerpo **no trae** `label`/`alternatives` (clave ausente según `model_fields_set` del submodelo `DrossesToLeadParams`, O2) y la vigente sí los tiene, se **copian** de la vigente. Para quitarlas hay que mandarlas explícitas en `null`: `canonical_parameters` usa `exclude_none`, así que un `null` explícito no llega al JSONB. Así ningún escritor actual ni futuro las pierde por omisión. Si la copia choca con la validación de D1 (por ejemplo, el defecto nuevo es igual a una alternativa), da 422 y dice que se edite la lista.
- **FormulasPage:** edita la lista y siempre la manda; `changed()` (l.279) compara también la lista.
- **Seeder:** no se toca. Compara solo `lead_percentage` (l.1043-1046), y si versiona, el servidor copia la lista.
- **`archivar_org_sac.py`:** compara `parameters["lead_percentage"]` (o `kg_lead_per_unit`) por nombre, no «el único valor».

### D3 — Se elige al liquidar y queda en la línea

- `POST /inbound-orders/{id}/confirm` acepta un cuerpo **opcional**:

  ```json
  {"conversion_options": [{"material_id": "…", "option": "Seco escurrido"}]}
  ```

  - **Sin cuerpo, o un material que no viene:** factor por defecto. Es el comportamiento de hoy, byte a byte (T2).
  - La llave es `material_id` porque hay una línea por material (UNIQUE, #93 D3) y `confirm` recrea las líneas: el id de línea no sobrevive.
- Columna nueva `inbound_order_lines.conversion_option` (`String(40)`, nullable; NULL = el defecto). `inbound_order_lines` es tabla exclusiva de SAC.
- Se resuelve en **un solo helper**, `_resolve_lead_factor(formula, option) -> (pct, label)`. Lo usa `_apply_willard_effects`, que es el camino de efectos de la confirmación y del revert-and-reapply de D18. Errores 422, todos antes de escribir:
  - opción para un material cuya fórmula no tiene alternativas;
  - opción que no está en la lista (el mensaje nombra el material y las opciones válidas);
  - material que no está en la Entrada;
  - opción en una línea de baterías;
  - un `material_id` repetido en `conversion_options` (A1).
- **Cómo se compara y qué se guarda (A2):** la opción se compara con `normalize_entity_name` (#78), el mismo criterio de la unicidad de D1, contra el nombre del defecto y los de las alternativas de la vigente.
  - Si coincide con el **defecto**, se guarda **NULL**. NULL siempre es el defecto; nunca queda guardado el nombre del defecto.
  - Si coincide con una **alternativa**, se guarda su nombre **canónico**, tal como está en la fórmula, no lo que se escribió («seco ESCURRIDO» se guarda «Seco escurrido»).
- **Por qué al liquidar y no al capturar:** es el pedido, y quien liquida es quien sabe qué mandó Willard. La captura (David) y la revisión no cambian: sus schemas no ganan el campo.
- **Kilos estimados del borrador:** siguen con el defecto. El diálogo de liquidar muestra el estimado con la opción escogida.

### D4 — El snapshot dice qué factor se usó

- Si la fórmula **tiene** alternativas, el snapshot gana `"applied": {"label": "...", "lead_percentage": 0.56}`. `parameters` sigue siendo la fórmula completa, como hoy.
- Si **no** tiene alternativas, el snapshot queda **byte a byte igual** que hoy (T2 lo compara entero).
- La descripción del movimiento kg (la que se ve en el estado de cuenta de la cuenta kg) suma `· Seco escurrido 56 %` solo cuando la fórmula tiene alternativas.
- Nadie recalcula kilos desde el snapshot de una Entrada (grep: el único lector de snapshots que recalcula es `transfer.py:496-521`, y lee el de la línea del traslado, no el de la Entrada).

### D5 — Edición D18 de una confirmada: la opción se conserva

- `InboundOrderUpdate.lines` **no gana** el campo. Ninguna pantalla puede reiniciar el factor al reenviar las líneas.
- En el revert-and-reapply, cada material conserva la opción que tenía su línea vieja. Un material nuevo entra con el defecto.
- Si la opción guardada ya no está en la lista vigente, da 422 («el factor X ya no está en la lista de SCR-SG; corríjalo primero») y no escribe nada. Volver al defecto en silencio cambiaría la deuda con Willard sin que nadie lo decida.
- El borrador (draft/reviewed) no tiene opción: se escoge al liquidar.
- **Declarado (A4):** la opción se guarda por **nombre**. Si una versión nueva de la fórmula cambia el % de una alternativa conservando el nombre, una re-aplicación D18 toma el % nuevo sin avisar. Es lo mismo que hoy pasa con el defecto: D18 re-aplica con la vigente (#35).
- Hoy D18 no tiene botón: el detalle oculta «Editar» en todo lo liquidado (`InboundDetailPage.tsx:431`, desde #93) y solo se llega por URL o API. D5 existe para que ese camino no cambie la deuda en silencio, no para corregir factores (eso es D6).

### D6 — Un factor mal escogido: anular y registrar de nuevo (sin código nuevo)

Pedido del Coordinador (24-nov): con Q-76 respondida, la acción propia de corregir se queda sin caso. Para un error futuro, medir si basta el camino que ya existe.

**Basta, y es anular.** Lo medido sobre `5139940`:

- «Anular» está en el detalle de una Willard liquidada (`InboundDetailPage.tsx:480`, `purchases.cancel`). `_revert_willard_effects` (l.1587) devuelve el inventario y anula los movimientos kg por `source_id` (l.1656-1669), sin recalcular nada. La Entrada anulada desaparece de todos los cortes (#41), así que la deuda con Willard queda como si no hubiera existido.
- Registrar de nuevo con la **misma remisión** y la **fecha original** está permitido: la remisión no tiene unicidad (solo se busca y ordena, `inbound_order.py:2125`, `:2231`) y la fecha solo no puede ser futura (`schemas/inbound_order.py:79`). Después se revisa y se liquida escogiendo el factor bueno (D3).
- **Costos, todos (C1 de QA 1):**
  1. **Trabajo:** volver a capturar las líneas y pasar otra vez por revisión.
  2. **Lo que queda a la vista (C1 a):** la misma remisión dos veces en Entradas, una anulada y una viva, y la viva con otro número interno.
  3. **No mueve solo kilos (C1 b):**
     - La anulación saca cada línea del inventario al costo guardado en la línea (`line.unit_cost`, remoción ponderada #66).
     - Si el pool del material estaba negativo, la diferencia va a `annul_cost_adjustment`, la 8.ª fuente de la línea de sobreventa del P&L (#75).
     - La Entrada nueva entra al costo promedio de ESE día (identidad D2), con su MCH de hoy.
     - Por eso el costo promedio y el valor del inventario de SCR-SG pueden cambiar aunque los kilos vuelvan iguales: si entre la liquidación y la anulación entró material a otro costo, o si el pool estaba negativo. Es el mismo argumento que la v1.0 usó para no reusar D18.
  - Es la misma regla que ya rige para cambiar la sede de una liquidada (#118: «anúlela y regístrela de nuevo»).
- **Este costo lo acepta o no Daniel (A5):** va en la ventanita de autorización junto con el runbook de §8. Si no lo acepta, la alternativa es un plan aparte (último párrafo de D6).

**Editar con revert-and-reapply (#75 D18) no sirve hoy** como camino del usuario:

- no tiene botón para una liquidada (D5);
- habilitarlo abriría también la edición de cantidades y fecha de una Willard liquidada, que es una decisión de producto aparte;
- y agregaría el factor al cuerpo del PATCH de las líneas, justo la trampa de #103 D4 que D5 evita.

Si Daniel lo quiere, va en otro plan.

### D7 — Pantalla

- **Config → Materiales (kg):** en el diálogo de un material en kg con mundo Willard, una sección «Factores de Willard»: el nombre del factor por defecto y la lista de alternativas (nombre y %), con agregar y quitar. Guardar crea versión solo si algo cambió. La tabla muestra «59 % plomo · +1 factor».
- **Diálogo de liquidar Willard** (detalle de la Entrada y fila del listado de Entradas): si alguna línea tiene un material con alternativas, por cada una muestra un selector con el defecto preseleccionado y los kilos estimados en vivo. Sin alternativas, el diálogo queda como hoy.
  - Hoy los dos puntos de entrada son diálogos separados (`InboundDetailPage:1083` e `InboundOrdersPage:625`). Pasan a un componente compartido.
  - El listado necesita las fórmulas: `useCurrentFormulas(undefined, enabled)` (F2, ya existe).
- **Detalle de la Entrada:** cada línea de Willard muestra el factor usado («Seco escurrido · 56 %»), leído de la respuesta. No hay acción de corregir (D6).
- **Estado de cuenta kg:** el factor se ve en la descripción del movimiento (D4).
- **Responsive:** el selector por línea es `w-full sm:w-auto` y el diálogo usa el base de shadcn (CLAUDE.md, responsive).

### D8 — Respuesta

- `InboundOrderLineResponse` gana `conversion_option` y `lead_percentage_applied`.
- `lead_percentage_applied` sale del snapshot del movimiento kg **confirmado** de la línea, por el mismo camino de `kg_lead` (A3): `kg_deltas_by_movement` (`inbound_order.py:2468`, ya filtra `confirmed`) trae también el snapshot. No es una query nueva por orden: el listado (`inbound_orders.py:459`) sigue con una sola. Se usa `applied.lead_percentage`, o `parameters.lead_percentage` si no hay `applied`. No se lee de la fórmula de hoy, que pudo cambiar.
- **Declarado:** en una Entrada anulada todo su kg está anulado, así que `lead_percentage_applied` da None (igual que `kg_lead` hoy). `conversion_option` sí se sigue viendo, porque vive en la línea.
- El endpoint arma las líneas **campo por campo** (`inbound_orders.py:147`, trampa #95), así que los dos campos se agregan ahí y los tests los leen por HTTP.

## 4. Lo que no cambia

- Los 8 lectores de §2 leen el mismo `lead_percentage` (T11 lo afirma en back para traslado y crisol).
- Compra regular, reparto y `liquidate()` de la Entrada tipo compra: no se tocan. Eco Coder 2 trabaja ahí; este plan toca otras funciones de `inbound_order.py` (`confirm`, `_apply_willard_effects`, la rama Willard de `update`, el endpoint nuevo) y el diálogo de Willard de las dos pantallas de Entradas.
- Costa y Meta: ni la tabla de fórmulas ni las Entradas tienen filas fuera de SAC, y los dos routers van detrás de `kg_ledger_enabled`.

## 5. Migración

- Una sola: `inbound_order_lines.conversion_option String(40) NULL`. Aditiva, sin backfill (NULL = el defecto, que es lo que tienen las 3 liquidadas).
- La fórmula no cambia de esquema: es JSONB.
- Gates: smoke up/down/up y parity check.

## 6. Golden: no aplica (medido)

- Las 14 entradas de `CAPTURES` (11 rutas) no incluyen inbound, fórmulas ni kg (`medicion_lectores_y_golden.log`).
- Las tablas tocadas son exclusivas de SAC, con los routers detrás del flag.
- Ningún lector compartido cambia de valor (§4).
- La medición se repite con comando sobre el diff final, en el gate.

## 7. Tests

Nuevo archivo `backend/tests/test_sac_factor_willard.py`:

| T | Qué afirma |
|---|---|
| T1 | Schema de D1: válido; sin `label` con alternativas, nombres repetidos (normalizados), % fuera de rango, igual al defecto y alternativas en baterías dan 422; los números anidados quedan como número JSON |
| T2 | Confirmar sin cuerpo, con fórmula sin alternativas: kilos y snapshot byte a byte los de hoy (dict completo) |
| T3 | Confirmar con «Seco escurrido»: kilos = cantidad × 0,56; `conversion_option` y `lead_percentage_applied` leídos por HTTP; snapshot con `applied`; la descripción del estado de cuenta kg lo nombra |
| T4 | Fórmula con alternativas y sin elección: defecto 0,59 y `applied` con el nombre del defecto |
| T5 | Los 422 de D3, incluido el material repetido (A1), cada uno sin escribir nada: la Entrada sigue `reviewed`, 0 movimientos kg y 0 de inventario |
| T5b | A2: escoger el defecto por su nombre guarda NULL; escoger «seco ESCURRIDO» guarda «Seco escurrido» y da 0,56 |
| T5c | A3: `lead_percentage_applied` por HTTP en el detalle y en el listado; en una Entrada anulada da None y `conversion_option` se sigue viendo |
| T6 | Edición D18 (cambia la cantidad) de una confirmada con escurrido: conserva escurrido; kilos = cantidad nueva × 0,56 |
| T7 | Edición D18 cuando la opción ya no está en la vigente: 422 y nada cambia |
| T8 | D6 medido con el camino que existe: anular una confirmada con escurrido, registrarla de nuevo con la misma remisión y la fecha original, revisarla y liquidarla con pinza. Afirma: la cuenta kg queda en cantidad × 0,59 en la fecha original; la remisión aparece dos veces (una anulada); y el costo promedio y el valor del inventario de SCR-SG antes y después, con los **valores esperados escritos en el test** (no «igual»), en tres casos: (a) nada entra entre medio: promedio y valor sin cambio; (b) entre la liquidación y la anulación se liquida una compra de SCR-SG a otro precio: promedio y valor esperados calculados a mano (remoción a `line.unit_cost`, reingreso al promedio de ese día); (c) pool negativo al anular: `annul_cost_adjustment` esperado escrito y su efecto en la línea de sobreventa del P&L |
| T9 | D2: versión nueva sin `label`/`alternatives` las copia de la vigente; con `null` explícito las quita |
| T10 | Con alternativas en la fórmula, traslado y retorno de dross usan el defecto |
| T11 | El cuerpo de `confirm` no cambia el permiso: un rol con `purchases.view` y sin `purchases.liquidate` recibe 403 con cuerpo, con un GET en 200 como control positivo |

Front (sin infra de test): casos puros del helper de opciones en un arnés `node` y e2e a 1440 y 390:

| E | Qué recorre |
|---|---|
| E1 | Config: agregar «Seco escurrido 56 %» a SCR-SG |
| E2 | Liquidar desde el detalle escogiendo escurrido; los kilos estimados cambian |
| E3 | Liquidar desde la fila del listado; el selector aparece |
| E4 | El detalle muestra el factor usado |
| E5 | Entrada sin materiales con alternativas: el diálogo queda como hoy |

## 8. Q-76: respondida

- Daniel, 24-nov: «está bien al 59». Las 3 Willard con SCR-SG ya liquidadas (remisiones 16272, 16341, 16391) **se quedan al 59 %** (pinza, el defecto). No hay datos que corregir ni backfill: su `conversion_option` queda NULL = defecto.
- Las 3 en Revisada (16300, 16415, 16436) las liquida SAC cuando exista la opción.
- **Runbook del deploy, abierto para la autorización de Daniel:** quién agrega en producción, en Configuración → Materiales (kg), la alternativa «Seco escurrido 56 %» a SCR-SG y el nombre «Seco pinza» al defecto. No va en el seeder: el seeder no pisa lo que no puso él, y la lista es dato del cliente.

## 9. Fuera de alcance

- Factores alternativos en materiales de baterías (`battery_to_lead`).
- Elegir el factor en la captura o en la revisión.
- Que el traslado, las Salidas o el crisol usen una alternativa (Q-73: no aplica).
- Partir la cuenta kg por factor (Q-74).
- Una acción para corregir el factor de una Willard liquidada, y habilitar «Editar» en una Willard liquidada (D6).

## 10. Gates (flujo QA)

1. GO de QA 1 a este plan, y autorización de Daniel por el Coordinador.
2. Construcción: lint y tests nuevos.
3. Pasada 1 de QA con patch, sha y base.
4. Matriz de plantado commiteada antes de plantar. Borrador de filas:

   | P | Defecto plantado |
   |---|---|
   | P1 | `_resolve_lead_factor` ignora la opción |
   | P2 | La descripción y el snapshot se escriben aunque no haya alternativas (rompe T2) |
   | P3 | D2 sin copiar la lista |
   | P4 | D5 vuelve al defecto en lugar de conservar |
   | P5 | D5 sin el 422 de opción desaparecida |
   | P6 | `canonical_parameters` sin convertir lo anidado |
   | P7 | La respuesta sin los campos nuevos (trampa #95) |
   | P8 | Validación sin el «distinto del defecto» |
   | P9 | `confirm` aplica la opción después de escribir (un 422 deja movimientos escritos; rompe T5) |
   | P10 | Sin el 422 del material repetido (A1) |
   | P11 | Guardar el nombre del defecto en lugar de NULL, o el texto escrito en lugar del canónico (A2) |
   | P12 | `lead_percentage_applied` leído de la fórmula de hoy en vez del snapshot (A3) |

5. Dirigidas desde el grep de los símbolos tocados y de sus importadores, más las 3 guardas, con la predicción escrita antes.
6. e2e a 1440 y 390.
7. Smoke de migración, parity y golden medido.
8. Pasada 2 de QA y commit en la rama.
