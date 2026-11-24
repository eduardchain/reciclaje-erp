# Plan: elegir el factor de conversión de Willard al liquidar (v1.0)

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
- Abierta: **Q-76** (§8).

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
- `canonical_parameters` convierte a float también **dentro** de `alternatives`. Hoy solo convierte el primer nivel, y un `Decimal` anidado revienta el JSONB con 500 (racional H1).

### D2 — Ningún escritor borra la lista sin querer (lección de #103 D4)

FormulasPage arma `{lead_percentage}` solo (l.253) y el seeder igual (l.1041): al versionar, borrarían la lista en silencio.

- **Servidor:** al crear una versión, si el cuerpo **no trae** `label`/`alternatives` (clave ausente, `model_fields_set`) y la vigente sí los tiene, se **copian** de la vigente. Para quitarlas hay que mandarlas explícitas en `null`. Así ningún escritor actual ni futuro las pierde por omisión. Si la copia choca con la validación de D1 (por ejemplo, el defecto nuevo es igual a una alternativa), da 422 y dice que se edite la lista.
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
- Se resuelve en **un solo helper**, `_resolve_lead_factor(formula, option) -> (pct, label)`. Lo usan `_apply_willard_effects` y la corrección (D6). Errores 422, todos antes de escribir:
  - opción para un material cuya fórmula no tiene alternativas;
  - opción que no está en la lista (el mensaje nombra el material y las opciones válidas);
  - material que no está en la Entrada;
  - opción en una línea de baterías.
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

### D6 — Corregir el factor de una Entrada ya liquidada

`POST /inbound-orders/{id}/conversion-options`:

- **Acceso:** permiso `purchases.liquidate`, el mismo de liquidar; el router ya va detrás de `kg_ledger_enabled`.
- **Cuerpo:** las mismas opciones de D3 más `reason`, obligatorio (mínimo 3 caracteres).
- **Solo Willard confirmada.** Si no lo es, 400. Si nada cambia, 422.
- **Qué hace, por cada línea que cambia de opción:**
  1. anula su `KgLedgerMovement` (ubicado por `inventory_movement_id`), con el motivo;
  2. escribe uno nuevo con `add_kg_movement` (#107, escritor único): misma cuenta, `transaction_date = order.date`, snapshot con la opción nueva;
  3. actualiza `line.conversion_option`.

  Todo en una transacción.
- **No toca** inventario, costo promedio ni historial de costo (MCH). El factor solo mueve kilos.
- **Por qué no reusar el revert-and-reapply de D18:** sacaría y volvería a meter el inventario, escribiría historial de costo y podría dejar la diferencia de costo de un pool negativo (micro-gap de E2) para cambiar un número que no es de inventario. El cálculo y el snapshot sí son los mismos: salen del helper de D3 y del mismo constructor del snapshot que usa `_apply_willard_effects`.
- **Fecha:** el movimiento corregido queda en `order.date`, porque la deuda era esa desde ese día. Los cortes del libro kg anteriores a hoy cambian por la diferencia. Eso es una corrección, igual que una edición D18, y queda auditada en el movimiento anulado.
- **Anular después** anula todo lo vivo por `source_id` (l.1658); no cambia nada.

### D7 — Pantalla

- **Config → Materiales (kg):** en el diálogo de un material en kg con mundo Willard, una sección «Factores de Willard»: el nombre del factor por defecto y la lista de alternativas (nombre y %), con agregar y quitar. Guardar crea versión solo si algo cambió. La tabla muestra «59 % plomo · +1 factor».
- **Diálogo de liquidar Willard** (detalle de la Entrada y fila del listado de Entradas): si alguna línea tiene un material con alternativas, por cada una muestra un selector con el defecto preseleccionado y los kilos estimados en vivo. Sin alternativas, el diálogo queda como hoy.
  - Hoy los dos puntos de entrada son diálogos separados (`InboundDetailPage:1083` e `InboundOrdersPage:625`). Pasan a un componente compartido.
  - El listado necesita las fórmulas: `useCurrentFormulas(undefined, enabled)` (F2, ya existe).
- **Detalle de la Entrada:** cada línea de Willard muestra el factor usado («Seco escurrido · 56 %»), leído de la respuesta. Una Willard confirmada con alguna línea con alternativas muestra «Corregir factor» (`purchases.liquidate`), con motivo obligatorio.
- **Estado de cuenta kg:** se ve en la descripción (D4) y en el movimiento anulado de la corrección.
- **Responsive:** el selector por línea es `w-full sm:w-auto` y el diálogo usa el base de shadcn (CLAUDE.md, responsive).

### D8 — Respuesta

- `InboundOrderLineResponse` gana `conversion_option` y `lead_percentage_applied`. El segundo sale del snapshot del movimiento kg de la línea (`applied`, o `parameters.lead_percentage` si no hay), no de la fórmula de hoy, que pudo cambiar.
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
| T5 | Los 422 de D3, cada uno sin escribir nada: la Entrada sigue `reviewed`, 0 movimientos kg y 0 de inventario |
| T6 | Edición D18 (cambia la cantidad) de una confirmada con escurrido: conserva escurrido; kilos = cantidad nueva × 0,56 |
| T7 | Edición D18 cuando la opción ya no está en la vigente: 422 y nada cambia |
| T8 | Corrección pinza → escurrido: el movimiento viejo queda anulado, el nuevo en `order.date` con 0,56; inventario, costo promedio y MCH iguales (conteos y valores); el saldo de la cuenta baja cantidad × 0,03; saldo corrido == saldo vivo (#55) |
| T9 | Corrección: sobre una no confirmada da 400; sin cambios, 422; sin motivo, 422 |
| T10 | Anular después de corregir: la cuenta vuelve a 0 |
| T11 | Con alternativas en la fórmula, traslado y retorno de dross usan el defecto |
| T12 | D2: versión nueva sin `label`/`alternatives` las copia de la vigente; con `null` explícito las quita |
| T13 | Permiso: un rol con `purchases.view` y sin `purchases.liquidate` recibe 403 en la corrección, con un GET en 200 como control positivo |
| T14 | Sin el flag, la corrección da 403 |

Front (sin infra de test): casos puros del helper de opciones en un arnés `node` y e2e a 1440 y 390:

| E | Qué recorre |
|---|---|
| E1 | Config: agregar «Seco escurrido 56 %» a SCR-SG |
| E2 | Liquidar desde el detalle escogiendo escurrido; los kilos estimados cambian |
| E3 | Liquidar desde la fila del listado; el selector aparece |
| E4 | El detalle muestra el factor usado |
| E5 | Corregir el factor con motivo; el estado de cuenta kg muestra el anulado y el nuevo |
| E6 | Entrada sin materiales con alternativas: el diálogo queda como hoy |

## 8. Q-76 (abierta): supuesto

- **Supuesto:** las 3 Entradas de Willard con SCR-SG ya liquidadas al 59 % (remisiones 16272, 16341, 16391) **quedan en pinza**, que es el defecto y lo que tienen hoy. Sin backfill: su `conversion_option` queda NULL = defecto.
- Si Johana dice que alguna era escurrido, se corrige **desde la pantalla** con D6, en producción, por quien tenga `purchases.liquidate`. Es una escritura de negocio con motivo, no un script nuestro contra prod.
- Las 3 en Revisada (16300, 16415, 16436): si se liquidan antes del deploy, quedan en 59 % y se corrigen igual. Después del deploy, Johana escoge al liquidar.
- **Tamaño del error si alguna era escurrido:** el 3 % de sus kilos. La 16272 (8.452 kg) daría 253,56 kg de plomo de más en la deuda con Willard.
- **Runbook del deploy:** después del deploy, alguien con permiso agrega en Config → Materiales (kg) la alternativa «Seco escurrido 56 %» a SCR-SG y le pone nombre «Seco pinza» al defecto. No va en el seeder: el seeder no pisa lo que no puso él, y la lista es dato del cliente. Decide Daniel quién lo hace.

## 9. Fuera de alcance

- Factores alternativos en materiales de baterías (`battery_to_lead`).
- Elegir el factor en la captura o en la revisión.
- Que el traslado, las Salidas o el crisol usen una alternativa (Q-73: no aplica).
- Partir la cuenta kg por factor (Q-74).

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
   | P6 | D6 a una fecha distinta de `order.date` |
   | P7 | D6 sin anular el movimiento viejo |
   | P8 | D6 tocando inventario |
   | P9 | `canonical_parameters` sin convertir lo anidado |
   | P10 | La respuesta sin los campos nuevos (trampa #95) |
   | P11 | La corrección sin permiso |
   | P12 | Validación sin el «distinto del defecto» |

5. Dirigidas desde el grep de los símbolos tocados y de sus importadores, más las 3 guardas, con la predicción escrita antes.
6. e2e a 1440 y 390.
7. Smoke de migración, parity y golden medido.
8. Pasada 2 de QA y commit en la rama.
