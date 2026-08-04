# Plan — SAC Ciclo B: canal único + sede determinista + guard Willard + limpieza (CC-007)

**Versión**: v1.2 (v1.1 = QA GO condicionado F1/F2/F3; v1.2 = addendum de feedback de pruebas de Daniel, ver informe §0: label "Tipo Willard", tercero Willard fijo al titular de la cuenta kg, TP willard excluido en compra, quick-create conductor/vehículo, `notes` de cabecera — **rompe el "CERO migraciones" con 1 migración aditiva** `d4e5f6a7b8c9`, pedida por el usuario; `inbound_orders` no está en prod → golden intacto) · **Fecha**: 2026-07-17 · **Base**: develop `9eb5ece` (post Retenciones v2)
**Origen**: respuestas Johana Q-03/04/05/06/09 + modelo propuesto por Daniel (2026-07-17). Los 4 ítems van en UN plan (decisión Daniel: todo junto). Guard = bloquear (decisión Daniel).

**Sanity check hecho** (regla CLAUDE.md): verificado contra el código antes de planear — kg accounts (drosses org-wide, postconsumo per-sede), `warehouse_id` de cabecera, guard Willard existente (solo un sentido), `goes_directly_to_jm` sin lógica, `PurchaseResponse` sin origen inbound. Las tensiones Q-10/Q-11 quedaron resueltas por el modelo de Daniel (recepción homogénea).

---

## 0. Regla de oro (3 empresas en productivo)

Todo **aditivo y flag-gated** (`kg_ledger_enabled`). **CERO migraciones** en el ciclo: settings vive en JSONB, el origen inbound es lookup, el flag muerto se deja inerte (regla "migraciones sin DROP"). Golden diff-cero por construcción: las orgs prod no tienen recepciones ni el flag → ninguna rama nueva las toca.

## 1. El modelo (acordado con Daniel)

Recepción con **selector de tipo** (Willard | Compra regular = `inbound_type`, ya existe). Si es **Willard**, aparece un **sub-selector de mundo** (drosses | postconsumo) que:
- filtra el picker de materiales a ese mundo,
- gobierna la bodega:
  - **drosses** → bodega **bloqueada** a Juan Mina (setting), campo deshabilitado. (Cuenta kg drosses es org-wide, así que la bodega es solo dónde aterriza el inventario físico: la planta.)
  - **postconsumo** → el selector de bodega **solo lista las bodegas que tienen cuenta `willard_baterias` activa** (mejora Daniel 2026-07-17): el usuario no puede elegir una sede sin cuenta de baterías (el error de backend deja de ser un camino alcanzable, queda solo como defensa). Default **Circunvalar** (setting) si está en la lista filtrada; editable entre las válidas. (Cada sede tiene su sub-cuenta `willard_baterias` per-sede; la cuenta sigue a la bodega — por eso filtrar por cuenta = filtrar por sede válida.)
  - **compra regular** → bodega **libre** (comportamiento actual).

Camión mixto (drosses + postconsumo, raro): **dos recepciones** (Q-10). El backend valida homogeneidad de mundo por recepción Willard.

**Confirmado en código** (sin suposiciones): `account_type` postconsumo = `willard_baterias` con `warehouse_id` NOT NULL por CHECK ([kg_ledger.py:101](../../backend/app/models/kg_ledger.py#L101)); el frontend ya tiene `useKgAccounts({account_type})` que devuelve `warehouse_id`+`is_active`. Drosses = `willard_drosses` org-wide (warehouse_id NULL) → no aporta al filtro (su bodega es la planta física, fijada por setting).

## 2. B1 — Canal único de compras

**Objetivo**: en SAC, Recepción es la única puerta de creación de compras; Compras es gestión/liquidación. El origen se ve.

**Backend** (aditivo, sin migración):
- `PurchaseResponse` gana `inbound_order_id: Optional[UUID]` + `inbound_order_number: Optional[int]` (o str). Se llenan por **lookup inverso** `InboundOrder.purchase_id == purchase.id`:
  - Listado (**F3 QA — sin JOIN**): la query paginada NO se toca; tras paginar, un segundo query `SELECT purchase_id, order_number FROM inbound_orders WHERE purchase_id IN (ids de la página)` → dict → enrich. Duplicar filas del listado es **imposible por construcción** (el listado no cambia; si un bug creara 2 inbounds por compra, el dict se queda con uno — sin fila fantasma). 1 query extra por página; prod → dict vacío → cero costo real.
  - Detalle: lookup simple (`.first()`).
- **No** se crea endpoint nuevo ni se toca la lógica de compras — solo enriquecimiento de respuesta.

**Frontend** (flag-gated):
- `PurchasesPage`: botón "Nueva Compra" **oculto** cuando `kg_ledger_enabled` (`useOrgSettings`). Nueva columna/badge **"Recepción #N"** (link a `/inbound/:id`) cuando `inbound_order_number` presente — en tabla desktop y card mobile.
- `PurchaseCreatePage`: si `kg_ledger_enabled`, **redirige** a `/inbound/new` con toast "En SAC las compras se crean por Recepción" (defensa en profundidad — sin esto un deep-link entraría). Prod: flag off → comportamiento idéntico.
- `PurchaseDetailPage`: banner/badge "Origen: Recepción #N" con link cuando aplique.

**No-regresión**: los 3 cambios frontend son flag-gated o condicionados a `inbound_order_number != null` → prod idéntico. Los 2 campos de respuesta son nullable aditivos.

## 3. B2 — Sede determinista (mayormente frontend)

**Backend** (aditivo, sin migración):
- **Settings**: 2 claves nuevas en `OrgSettingsPayload` (`schemas/organization.py`) — `willard_sede_drosses: str | None`, `willard_sede_postconsumo_default: str | None` (warehouse IDs; **str**, JSON-nativo — cumple H1, sin Decimal). **F2 QA (trampa D12)**: las 2 claves van TAMBIÉN al `SETTING_DEFAULTS` del **backend** (`app/utils/org_settings.py`, default `None`) — `get_org_setting` valida la clave contra ese dict antes de leer; sin esto, la validación del servicio lanzaría KeyError. Espejo en `SETTING_DEFAULTS` frontend (`useOrgSettings`, ambos null default). REPLACE semantics: el runbook post-deploy manda el payload completo con estas 2 claves seteadas a las bodegas JM/CV de SAC.
- **Validación en el servicio inbound** (`_apply_willard_effects` / `create`), defensa en profundidad, reusa `_load_kg_worlds` que ya se carga:
  - **Homogeneidad**: si una recepción Willard tiene líneas de >1 mundo → 400 "Una recepción Willard es de un solo mundo (drosses o postconsumo). Separe en dos recepciones." (resuelve Q-10; el frontend ya filtra materiales por mundo, esto es el guard).
  - **Drosses → JM**: si el mundo es drosses y `warehouse_id != willard_sede_drosses` (si el setting está configurado) → 400 "Los drosses se reciben en la planta (Juan Mina)." (Si el setting es null, no valida — orgs sin configurar no rompen.)
  - Postconsumo: sin validación de bodega adicional; el error existente "No existe cuenta kg para esta sede" queda como **defensa** (con el filtro del frontend deja de ser un camino normal).

**Frontend** (`InboundCreatePage` + `InboundEditPage`):
- Nuevo estado `willardWorld: "drosses" | "postconsumo" | ""` visible solo si `isWillard`. Sub-selector después del tipo.
- Filtro de materiales: willard → `world === willardWorld` (hoy es `world !== "none"`). Compra → igual que hoy. Al cambiar de mundo se limpian las líneas de materiales que ya no aplican (evita mezclar mundos → respeta la homogeneidad en la UI, no solo en el guard).
- **Bodega gobernada por el sub-selector**:
  - drosses → `setWarehouseId(settings.willard_sede_drosses)`, campo **disabled** (hint "Juan Mina — planta de drosses").
  - **postconsumo → opciones filtradas** (mejora Daniel): `useKgAccounts({ account_type: "willard_baterias" })` → set de `warehouse_id` con cuenta **activa** (`is_active && warehouse_id`) → el `EntitySelect` de bodega solo lista esas. Default = `willard_sede_postconsumo_default` **si está en el set**, si no la primera válida (robusto sin setting). **Empty-state**: si el set está vacío → mensaje "No hay bodegas con cuenta de baterías postconsumo. Créala en Plomo (kg)." + submit deshabilitado (en vez de dropdown vacío + error de backend).
  - compra → libre (hoy).
- `canSubmit` exige `willardWorld` cuando `isWillard`, y bodega válida (no vacía).

**El sub-selector NO se persiste** en `inbound_orders` (cero columna): el backend deriva el mundo de las líneas (homogéneas). Para display "Recepción drosses/postconsumo #N", el frontend/enrich lo deriva del mundo de la primera línea.

## 4. B3 — Guard de material Willard-puro en compras (BLOQUEA)

**Backend** (`purchase.py`, `create`): al armar líneas, si el material es **Willard-puro** (`willard_world != none` AND `compra_regular == false` en su `MaterialKgProfile`) → **400** "El material {code} es Willard (postconsumo/drosses) y no se compra — recíbalo como Willard." Simétrico al guard que YA existe en el path Willard ([inbound_order.py:196](../../backend/app/services/inbound_order.py#L196)).

- **Cubre ambos caminos con un solo guard**: la compra manual (que se oculta en SAC pero el guard defiende el API) Y la Purchase derivada de una recepción tipo compra (se crea vía `purchase.create` con `commit=False` → el guard fía ahí también).
- **Solo aplica con `kg_ledger_enabled`** (el perfil `MaterialKgProfile` es SAC-only; sin flag no hay perfiles → guard inerte → prod byte-idéntico). Materiales sin perfil o con `compra_regular=true` pasan siempre.
- Es un **bloqueo (400)**, no warning: no es stock negativo (estado válido), es error de ruteo que corrompe la conciliación de kg, sin caso de negocio válido (Johana Q-04).

## 5. B4 — Retirar `goes_directly_to_jm` (peso muerto)

Verificado: solo se persiste y se muestra, **cero lógica de ruteo** (grep completo). Q-03 lo mató (drosses siempre a JM).

- **Sin migración** (regla "migraciones sin DROP"): se **deja la columna inerte** en el modelo (`inbound_order.py`, nullable server_default false — inofensiva) y se **retira de la superficie**: fuera de `InboundOrderCreate/Update/Response` (schemas), fuera de `InboundCreatePage/EditPage/DetailPage` (UI) y del enrich del endpoint. La columna queda muerta en la tabla; una limpieza futura podría dropearla si se desea (fuera de alcance).
- `inbound_orders` aún NO está en prod (deploya el viernes) → retirarla de la superficie ahora evita que el flag llegue a prod con significado.

## 6. Migraciones y gates

- **CERO migraciones.** (B1 lookup, B2 settings JSONB, B3 validación, B4 inerte.)
- **Gates**: suite completa (~1269 + nuevos, sin regresión) · `schema_parity_check` (no cambia el schema físico → debe seguir DIFF CERO — de hecho es un buen testigo de que no metimos columna sin querer) · tsc + build · **golden por construcción** (flag off → todas las ramas nuevas inertes; el mecánico corre al replicar pre-deploy).

## 7. Tests (~14, backend)

- **B2 homogeneidad**: recepción Willard con drosses+postconsumo → 400. Recepción drosses con bodega ≠ JM (setting puesto) → 400. Drosses con bodega JM → 201. Postconsumo a cualquier sede con cuenta → 201. Setting null → no valida (compat).
- **B3 guard**: `purchase.create` con material Willard-puro → 400 (manual). Recepción tipo compra con material Willard-puro → 400 (derivada, el guard fía en el path inbound→purchase). Material `compra_regular=true` + `willard_world=postconsumo` (ambos) en compra → 201 (no es Willard-puro). Sin flag → 201 (guard inerte).
- **B1 origen**: Purchase derivada de recepción → `inbound_order_number` presente en detalle y lista. Purchase manual (org sin flag) → null. Listado con LEFT JOIN no rompe orgs sin inbound.
- **B4** (**F1 QA**): `goes_directly_to_jm` fuera del response; enviar el campo en create → **422** (los schemas inbound tienen `extra="forbid"` — [schemas/inbound_order.py:38](../../backend/app/schemas/inbound_order.py#L38) — el campo retirado se rechaza, no se ignora). El frontend deja de enviarlo en lockstep (mismo commit), así que ningún cliente real recibe el 422.
- Frontend: sin infra de test → tsc/build + walkthrough (guía en el informe).

## 8. Secuencia de implementación

1. Backend B4 (retirar de superficie) + B1 (campos response + lookup) + B3 (guard) + B2 (settings + validación). Tests backend.
2. Frontend B2 (sub-selector + bodega gobernada) → B1 (ocultar botón + badge + redirect) → B4 (limpiar UI). tsc/build.
3. Suite completa → parity → informe con evidencia → walkthrough Daniel → GO → commit.

## 9. Fuera de alcance / límites

- No se dropea la columna `goes_directly_to_jm` (limpieza futura opcional).
- El sub-selector de mundo no se persiste (se deriva de líneas homogéneas).
- La bodega de postconsumo queda acotada a sedes con cuenta `willard_baterias` activa — pero ahora el selector **solo muestra esas** y da empty-state si no hay ninguna (ya no es un error de backend alcanzable). **Comunicar a Johana**: para habilitar postconsumo en una sede nueva, primero crear su cuenta de baterías en Plomo (kg).
- Post-deploy: el runbook debe setear `willard_sede_drosses` (Juan Mina) y `willard_sede_postconsumo_default` (Circunvalar) en el payload de settings de SAC prod (REPLACE completo). El default es best-effort: si CV no estuviera en la lista filtrada, el selector cae a la primera bodega válida.
