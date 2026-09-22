# Plan — anular un precio de mercado del plomo (ciclo corto, sigue a CC-014 / #110)

**Estado:** v1.1 — incorpora C1–C4 de QA (2026-09-22). GO condicionado dado.
**Base:** `develop` en `a5459b0`.

## 1. Qué problema resuelve, y cómo apareció

Lo encontró Daniel el 2026-09-22 en la revisión en pantalla, **cometiendo el error de verdad**:
cargó $2.000 con vigencia **20/09** en vez de 20/08. Ese precio pasó a ser el vigente, pisó el de
$2.400 del 31/08 y cambió el corte de hoy. No hay forma de corregirlo: `LeadMarketPriceService`
tiene `create` y lecturas, sin `update` y sin `delete`, y el modelo no tiene columna de estado.

La corrección que existe hoy es cargar otra fila con la **misma** `effective_date` y el valor
correcto, porque el desempate `created_at DESC, id DESC` hace ganar a la nueva. Funciona siempre y
es mal remedio por tres razones: no es descubrible (el instinto es cargar con la fecha de hoy, que
deja el error vivo en su ventana); ensucia el histórico con filas que nunca rigieron, sin marca, en
la misma pantalla que existe para que el número sea auditable; y no existe "quitarle la vigencia a
una fecha" — hay que replicar en esa fecha el precio anterior, o sea **corregir por imitación**, y
un lector futuro ve un cambio de precio que nunca ocurrió.

⚠️ **No es un defecto heredado del patrón append-only: nace de apartarse de él.** En tarifas,
fórmulas y listas de precios (#35/#74/#79) la vigencia sale de `created_at`, así que cargar otra
versión SIEMPRE corrige. Acá sale de `effective_date`, que es exactamente lo que hace útil la
función (D1 de #110). Cuando Daniel aprobó el costo de D1 el 21-sep, lo cuantificado era el efecto
sobre balances históricos, **no el error de captura**, que es el caso frecuente.

En dev la fila se borró por SQL contra 5434. **En producción eso no existe.**

## 2. El agujero que QA encontró en mi primer diseño, y que define este plan

Yo escribí que el arreglo era barato porque «el filtro vive en un solo sitio, `_CURRENT_ORDER`».
**Es falso, verificado con grep:** `_CURRENT_ORDER` es el `ORDER BY` (`:24`) y el `WHERE` está
escrito **tres veces** — `get_all` (`:62`), `get_current` (`:82`, el que alimenta el balance por
`reports.py:1577`) y `get_current_response` (`:99`, el que pinta «vigente» en Config).

Modo de falla, y es silencioso: si el filtro de anulados entra en uno y falta en el otro, **el
balance usa el precio bueno y la pantalla de precios muestra como vigente el anulado**, o al revés.
Todo test que mire UNA superficie pasa en verde. Es la lección de #98 otra vez: *un argumento por
construcción protege exactamente la superficie sobre la que cuantifica*.

## 3. Decisiones

**D1 — `POST /{id}/annul`, no `PATCH` ni `DELETE`.** Patrón del repo, verificado en 6 endpoints
(`crucible_charges`, `fixed_assets` ×2, `inbound_orders`, `financial_obligations`,
`inventory_adjustments`). Beneficio lateral: el test existente
`test_t3_sin_patch_ni_delete` **sigue siendo cierto sin tocarlo** — el append-only del recurso no se
afloja, se le agrega un evento.

**D2 — tres columnas de auditoría**, no un `is_active`: `annulled_at`, `annulled_by`,
`annulled_reason`. Es el patrón de `MoneyMovement` y de todo lo que se anula en este repo, y el
motivo es el dato que hace auditable la corrección. *Append-only significa que no se borra, no que
no se pueda invalidar.* Migración aditiva, las tres nullable, sin backfill.

**D3 — un solo selector del vigente, por DELEGACIÓN y no por un helper que se pueda olvidar.**
`get_current` es el único que decide qué fila rige; `get_current_response` pasa a ser
**`get_current` más el nombre del usuario**, no una copia del query. `get_all` queda **sin** el
filtro, a propósito: el histórico tiene que listar los tachados o la anulación deja de ser
auditable. Esto cierra el agujero de §2 por construcción: no hay dos lugares donde poner el filtro,
hay uno.

**D4 — anular es otro back-dating, y se declara.** Reescribe cortes ya impresos igual que D1 de
#110. Es coherente con #41 (lo anulado nunca existió, calco de `735c2c3`) y **el costo que Daniel
aprobó el 21-sep cubre también esto**. El balance sigue imprimiendo `price_date`, así que el corte
queda auditable.

**D5 — motivo obligatorio con `strip`.** `StringConstraints(strip_whitespace=True)` + `min_length`,
como la remisión de #100: sin el strip, `"  "` pasa un `min_length=1` y el motivo queda vacío.

**D6 — `annulled_at` es `now(timezone.utc)`**, timestamp de auditoría, no fecha de negocio (#91):
responde *cuándo exactamente*, no *qué día*. **Nunca entra a la selección del vigente** salvo como
`IS NULL`; `_CURRENT_ORDER` no se toca.

**D7 — anular el único precio deja la línea "sin valorar", no la borra.** Es D6 de #110: con el flag
encendido el balance devuelve SIEMPRE objeto, y sin precio vigente `value`/`price`/`price_date`
quedan en `None` con los kilos visibles. Un cero diría que la deuda no vale nada.

**D8 — permisos y gate sin novedad:** `tariffs.manage` para anular (el mismo que cargar),
`require_org_flag("kg_ledger_enabled")` heredado del router. Cero permisos nuevos.

**D9 — golden NO aplica, verificado con comando y no de memoria:** `CAPTURES` tiene 14 entradas y
ninguna toca `/lead-market-prices`; la migración solo agrega columnas a `lead_market_prices`, tabla
exclusiva de SAC con 0 filas en las tres organizaciones cliente. **Parity check sí corre** (hay
migración nueva).

## 4. Matriz defecto × test

Se commitea **antes** de plantar nada. La columna «esperado» sale de este commit y no se reescribe.

| | T1 dos superficies (HTTP) | **T1b as-of** | T2 no vigente | T3 único precio | T4 histórico | T5 doble | T6 otra org | T7 flag | T8 permiso | T9 motivo | T10 sin PATCH/DELETE | T11 reloj | **G6 pantalla** |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **P1** filtro no entra en `get_current` | **cae** | **cae** | — | **cae** | — | — | — | — | — | — | — | — | cae |
| **P2** `get_current_response` vuelve a ser copia y se le olvida el filtro | **cae** | — | — | — | — | — | — | — | — | — | — | — | cae |
| **P3** `get_all` filtra los anulados | — | — | — | — | **cae** | — | — | — | — | — | — | — | cae |
| **P4** sin guard de doble anulación | — | — | — | — | — | **cae** | — | — | — | — | — | — | — |
| **P5** sin filtro de organización | — | — | — | — | — | — | **cae** | — | — | — | — | — | — |
| **P6** ruta fuera del router con flag | — | — | — | — | — | — | — | **cae** | — | — | — | — | — |
| **P7** `tariffs.view` en vez de `manage` | — | — | — | — | — | — | — | — | **cae** | — | — | — | — |
| **P8** motivo sin `strip` | — | — | — | — | — | — | — | — | — | **cae** | — | — | — |
| **P9** `annulled_at` entra al orden de vigencia | **cae** | **cae** | **cae** | — | — | — | — | — | — | — | — | **cae** | cae |
| **P10** anular el último devuelve ausencia | — | — | — | **cae** | — | — | — | — | — | — | — | — | cae |
| **P11** se implementa como `DELETE` | — | — | — | — | — | — | — | — | — | — | **cae** | — | — |
| 🔴 **P12** la página marca vigente por `items[0]` | — | — | — | — | — | — | — | — | — | — | — | — | **cae — y SOLO acá** |
| **P13** filtro solo dentro de una rama (`cutoff` sí / no) | **cae** si falta sin cutoff | **cae** si falta con cutoff | — | — | — | — | — | — | — | — | — | — | cae |

**T1 es el test estrella y es el que QA pidió**: en un mismo escenario, anular el vigente y leer
**las dos** superficies — `GET /lead-market-prices/current` y el balance. Si alguna de las dos sigue
mostrando el anulado, cae. Es lo único que discrimina P2, que es el defecto que este plan existe
para prevenir.

⚠️ **P9 tumba tres tests y es deliberado que la fila lo diga**: un defecto en una vía compartida
cae de más, y lo que hay que vigilar es la dirección contraria — un test que debía caer y no cayó
(lección de #105).

🔴 **P12 es la fila más importante de la tabla y la única que NINGÚN test automático caza.** Es la
respuesta a la pregunta que le hice a QA («¿falta algún defecto plantable que hoy ninguna fila
cazaría?») y la encontró: **existe una TERCERA definición de "vigente" y vive en la página.** Ver §6.
La cierra el gate de pantalla y nada más, así que ese gate deja de ser una costumbre y pasa a ser
requisito del ciclo, con un paso escrito: anular el vigente y mirar tarjeta, badge y balance **en la
misma sesión**.

**T1 y T1b se leen por HTTP, no llamando al servicio** (C3 de QA). Razón: la delegación de D3 se
puede «deshacer» reescribiendo el select completo dentro del endpoint, y ahí un test que llame al
servicio pasaría igual. Es la trampa de #95 — el endpoint arma respuestas campo por campo.

**T1b existe porque D4 hay que AFIRMARLO, no solo no contradecirlo** (C2 de QA): anular un precio
que rigió un corte pasado y leer el balance as-of a ese corte, que tiene que caer al anterior, o a
«sin valorar» si era el primero. Sin T1b, un filtro que quede dentro de una sola rama de
`get_current` (con o sin `cutoff_dt`) pasa T1 en verde.

## 5. Gates

1. Suite completa a archivo, con `EXIT` capturado dentro del bloque y chequeo de mtime.
2. Parity check (migración nueva) — DIFF CERO esperado.
3. Plantado de defectos contra la matriz de §4, con la matriz ya commiteada.
4. ruff / tsc / build limpios, eslint ≤ 37 (techo, no invariante).
5. Golden: **no aplica**, con la verificación de `CAPTURES` escrita en el informe.
6. 🔴 **Pantalla: requisito del ciclo, no costumbre.** Es el único gate que caza P12. Paso escrito:
   anular el vigente y mirar **tarjeta, badge y balance en la misma sesión**; después anular uno no
   vigente y confirmar que nada se mueve. Las dos cosas que salieron en CC-014 las encontró un
   humano mirando, no un gate.

## 6. Frontend

🔴 **La v1.0 de este plan decía que «la tarjeta Precio vigente se recalcula sola porque sale de
`/current`», y ERA FALSO.** Lo encontró QA y lo verifiqué: `LeadPricePage` se alimenta de
`useLeadPriceHistory()` (o sea `get_all`), define `const vigente = items[0]` y pinta el badge
«vigente» con el fondo verde por **índice** (`i === 0`). Y `useCurrentLeadPrice` existe desde CC-014
**sin un solo consumidor** — `/current` hoy no lo pinta nadie.

Consecuencia con D3, que deja `get_all` sin filtro a propósito: al anular el vigente, **la fila
anulada sigue siendo `items[0]`**, así que la tarjeta y el badge la muestran como vigente mientras
el balance ya usa la correcta. Es el modo de falla de §2 exactamente, en la única superficie donde
ningún test backend mira. **Esa es la tercera definición de "vigente"** que ni mi plan ni mi matriz
veían.

Por eso el frontend no es plomería en este ciclo:

- la tarjeta sale de **`useCurrentLeadPrice`** (`/current`), que es el mismo selector del backend;
- el badge se decide por **`p.id === current?.id`**, nunca por índice;
- la fila anulada se pinta **tachada y con su motivo**, no se esconde;
- botón Anular por fila, gated `tariffs.manage`, con diálogo de motivo.

**Invalidación (C4 de QA, corregido con el código a la vista):** QA dijo que el create de CC-014
invalida solo `["lead-market-prices"]`. **No es así** — `useSacConfig.ts:80` ya invalida también
`["reports"]`, con un comentario que cita #98, y la llave real del balance es
`["reports", "balance-sheet" | "balance-detailed", fecha]`, cubierta por ese prefijo. Verificado en
`useReports.ts:44` y `:90`. Lo que sí hay que hacer es que **la mutación de anular replique las dos
invalidaciones**; el hueco que QA temía no existe en el create.

Archivos: `types/sac-config.ts`, `services/sacConfig.ts`, `hooks/useSacConfig.ts` y la página.

## 7. Pregunta abierta para Daniel

**El aviso antes de guardar, propuesto por QA.** Que al cargar un precio la pantalla diga, antes de
confirmar: *«este precio rige los cortes desde DD/MM hasta DD/MM y reemplaza $X del DD/MM»*.

Es lo que habría atrapado el 20/09 de Daniel **antes** de guardarlo, o sea que ataca la causa y no
la consecuencia. Complementa la anulación, no la reemplaza. Costo: un cálculo en la pantalla con el
histórico que ya tiene cargado, sin backend nuevo. **Decide Daniel si entra en este ciclo.**

## 8. Fuera de alcance

- Editar un precio: no se edita, se anula y se carga otro. El histórico es el registro.
- Anular en cascada o re-imprimir balances: no hay nada que re-imprimir, el balance se recalcula al
  consultarse.
- La deuda de planta con Circunvalar (Q-44) y los impuestos en ventas (Q-41 / CC-013) siguen fuera.
