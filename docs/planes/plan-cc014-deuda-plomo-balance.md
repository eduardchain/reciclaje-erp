# Plan CC-014 — la deuda en plomo con Willard, valorada en pesos dentro del balance

**Estado:** v1.3 — GO de QA con sus diez puntos y la corrección de D6 incorporados, y las dos decisiones de Daniel tomadas el 2026-09-21: F1 se resolvió commiteando #109 (`23074ad`), F8 aprobó la fecha de vigencia. Autorizado a construir.

🔴 **Condición de proceso antes de escribir una línea (F1 de QA).** El árbol tiene 31 archivos de #109 sin commitear, esperando la revisión en pantalla de Daniel. CC-014 **no se construye encima**: o se commitea #109 primero, o este ciclo va en un `git worktree` aparte. Con dos ciclos en un mismo árbol, el golden aislado, el chequeo de paridad y el control de fechas de archivo dejan de poder atribuirle nada a ninguno de los dos.
**Origen:** Q-B, reunión Daniel + Johana del 2026-09-18, 00:28:28.
**Alcance corto:** un precio de mercado del plomo por kilo, versionado y con fecha de vigencia, y una línea negativa dentro del inventario en el Balance General y en el Detallado, en vivo y a fecha de corte.

---

## 1. Qué pidió el cliente

Daniel preguntó si la deuda en plomo con Willard la convierten a pesos de cara al balance o la mantienen siempre en kilos. Johana, con sus palabras (grado a). ⚠️ La cita es **COMPUESTA**: son dos turnos suyos (L603 y L609-611) con una pregunta de Daniel en medio, «¿qué valor le das?» (L607):

> «yo siempre la coloco pues negativo en el balance, en pesos. le doy un valor de acuerdo al precio del mercado en ese momento y la tengo como un valor negativo, o sea, restando dentro de mi inventario»

Es su práctica de hoy, que hace a mano fuera del sistema. El precio como **parámetro del sistema** fue propuesta de Daniel y ella contestó «Mhm» (L607-617): grado b débil. De dónde sale el precio y quién lo actualiza **no se habló** (hueco H1, §8).

🔴 **No incluye la deuda de planta con Circunvalar.** Esa pregunta Daniel la saltó en voz alta antes de terminarla (L585-595) y quedó como Q-44. Ver D9.

---

## 2. Decisiones

**D1 — Una tabla propia, append-only, con fecha de vigencia de NEGOCIO.**
`lead_market_prices`: una fila es un precio por kilo con la fecha desde la que rige. El vigente es el de mayor `effective_date`, con `created_at DESC, id DESC` como desempate (patrón `ServiceTariff`, [service_tariff.py:83-104](backend/app/services/service_tariff.py#L83-L104); el desempate por `id` es obligatorio porque `now()` de PG es transaccional y empata en cargas batch).

Por qué una tabla y no una clave de `organizations.settings`: un setting **no tiene historia**. El día que el precio cambie, todos los cortes históricos ya impresos cambian solos y nadie se entera. Es exactamente lo que la regla de no reescribir el pasado (#61) nos ha costado antes.

Por qué `effective_date` y no solo `created_at`, que es lo que hacen tarifas, fórmulas y listas de precios: el balance de fin de mes **siempre se calcula después**. Si Johana carga el precio de septiembre el 2 de octubre y el vigente se resuelve por `created_at`, el corte del 30 de septiembre no encuentra precio y la línea sale vacía justo en el caso que motivó el requerimiento. `KgLedgerMovement.transaction_date` ya es el precedente de fecha de negocio en este repo ([kg_ledger.py:155-159](backend/app/models/kg_ledger.py#L155-L159)), con el tipo `BusinessDate` a mediodía UTC.

🔴 **Lo que esto cuesta, y es una decisión de Daniel, no una nota al pie:** cargar un precio con fecha anterior **cambia cortes históricos ya impresos**. Es la #61 al revés, a propósito: allá el pasado no se reescribe; acá el precio es un dato de negocio fechado y su corrección debe alcanzar al día que corrige. **Decidido por Daniel el 2026-09-21**, con las dos opciones y sus costos a la vista: o fecha de vigencia con cortes que pueden cambiar, o vigencia por fecha de carga y el cierre de septiembre sin valorar para siempre. Eligió la fecha de vigencia. Queda auditable: el balance muestra siempre qué precio usó y de qué fecha, y eso es lo que lo separa de la #61 — allá el pasado cambiaba sin que nadie lo viera.

**D2 — Un solo precio, no uno por material.**
La deuda vive en kilos de **plomo**: el libro ya convierte baterías y drosses con las fórmulas. Así que es un número por organización, no una lista por material.

**D3 — Qué se valora: `willard_baterias` + `willard_drosses`, nada más.**
Es lo que el servicio ya llama `_WILLARD_TYPES` ([kg_ledger.py:35](backend/app/services/kg_ledger.py#L35)) y lo que el resumen agrega como `total_willard_kg` ([kg_ledger.py:426-427](backend/app/services/kg_ledger.py#L426-L427)). `intersede`, `intra_horno` y `crisol` son internas y quedan fuera (D9).

**D4 — El signo se respeta, no se fuerza.**
Saldo positivo del libro significa que SAC le debe plomo a Willard: está documentado en la columna (`positivo = acumula deuda`, [kg_ledger.py:140-144](backend/app/models/kg_ledger.py#L140-L144)) y probado en dos tests, entrada ([test_inbound_orders.py:291-294](backend/tests/test_inbound_orders.py#L291-L294)) y salida ([test_willard_deliveries.py:309-317](backend/tests/test_willard_deliveries.py#L309-L317)). El valor que entra al balance es `-(kg × precio)`. Si algún día el saldo quedara negativo, la línea sale positiva sola. No se usa `abs()` en ningún punto.

**D5 — Un solo campo nuevo en el Balance General, y es un objeto.**
`BalanceSheetAssets.lead_debt_willard: LeadDebtValuation | None`, con `kg`, `price`, `price_date` y `value`. Un objeto y no cuatro campos sueltos por dos razones: la pantalla necesita decir «1.234 kg × $2.400, precio del 5 de septiembre» para que el número sea auditable, y el comparador que protege a las otras tres empresas perdona **una** clave nueva por captura solo si su valor es exactamente el declarado ([golden_diff.py:48-60](backend/scripts/golden_diff.py#L48-L60)). Un objeto = una entrada en la lista de claves permitidas.

**D6 — `None` si y solo si el flag está apagado.**
El predicado es el flag y nada más: sin `kg_ledger_enabled` el campo llega `None`; con el flag encendido llega **siempre** un objeto, aunque no haya cuentas Willard, aunque no haya kilos y aunque no haya precio. Así el predicado de T9 es el mismo que el corte del helper en F3, y no hay un segundo camino que también devuelva `None`. Así las tres empresas cliente ven exactamente lo que ven hoy. Hay precedentes de campos que llegan `None` cuando no aplican: `revalued_amount` ([reports.py:1891-1893](backend/app/services/reports.py#L1891-L1893)) y `groups` ([reports.py:2256-2259](backend/app/services/reports.py#L2256-L2259)).

⚠️ Con el flag encendido y kilos en el libro pero **sin precio vigente a esa fecha**, el objeto llega con `kg` lleno y `price`, `price_date` y `value` en `None`. La pantalla avisa «hay X kg sin valorar». No se inventa un cero: un cero diría que la deuda no vale nada.

⚠️ **Deuda en cero (F7 de QA):** el objeto **se devuelve igual**, con `kg` en 0 y `value` en 0, tanto si hay cuentas Willard sin saldo como si no hay ninguna cuenta. Que la línea exista en $0 le dice a SAC que el mecanismo está vivo y que hoy no deben nada; hacerla desaparecer se confunde con que nunca se configuró. `None` queda reservado para «esta organización no tiene el flag», y punto — corregido en v1.2 tras la lectura de QA, que encontró el caso «flag encendido y cero cuentas Willard» con dos respuestas.

**D7 — En el Balance Detallado es un ítem dentro de la sección de inventario, no una sección nueva.**
Es literal lo que ella describe, «restando dentro de mi inventario», y el helper `_section` suma `i.balance` ([reports.py:1810](backend/app/services/reports.py#L1810)), así que un ítem negativo baja el total de la sección solo. Además evita tocar las **tres** copias divergentes de `ASSET_ORDER` que ya existen en el frontend ([BalanceDetailedPage.tsx:31-36](frontend/src/pages/reports/BalanceDetailedPage.tsx#L31-L36), [excelExport.ts:134-140](frontend/src/utils/excelExport.ts#L134-L140), [pdfExport.ts:1030-1036](frontend/src/utils/pdfExport.ts#L1030-L1036)).

El ítem reutiliza los campos que la sección ya pinta: `stock` = kilos, `avg_cost` = precio, `balance` = el valor negativo. Cero campos nuevos en el Detallado, o sea cero claves nuevas en esa captura del golden.

⚠️ **Esos dos campos se pintan como «{code} | {stock} kg x {avg_cost}»** en la página ([BalanceDetailedPage.tsx:63-64](frontend/src/pages/reports/BalanceDetailedPage.tsx#L63-L64)) y en el Excel ([excelExport.ts:164-165](frontend/src/utils/excelExport.ts#L164-L165)), que es el formato del costo promedio. Para que no se lea como un costo: `code` = `WILLARD` y `name` = «Deuda en plomo con Willard — precio de mercado del DD/MM/AAAA». QA verificó además que `hideBelow` usa el valor absoluto ([balanceTransform.ts:43](frontend/src/utils/balanceTransform.ts#L43)), así que el filtro no lo esconde.

⚠️ Su `id` es sintético, `lead-debt-willard`. La página linkea cada ítem de esa sección a `/inventory/movements?material_id={id}` ([BalanceDetailedPage.tsx:52](frontend/src/pages/reports/BalanceDetailedPage.tsx#L52)): hay que excluirlo del link. No se agrega la clave a `SECTION_BEHAVIORS`, porque `_group_by_category` hace `UUID(item.id)` ([reports.py:2263](backend/app/services/reports.py#L2263)) y reventaría con un id que no es UUID.

**D8 — El corte histórico usa los kilos de esa fecha y el precio vigente de esa fecha.**
Los kilos ya se saben pedir a una fecha: `balances(db, org, as_of)` filtra `transaction_date <= as_of` ([kg_ledger.py:113-127](backend/app/services/kg_ledger.py#L113-L127)). El balance construye su corte como `cutoff_dt = 00:00 del día siguiente` ([reports.py:1674](backend/app/services/reports.py#L1674)) y compara con `<`; como las fechas del libro se guardan a mediodía UTC, pasarle `cutoff_dt` da el mismo conjunto.

⚠️ Se usa `balances()` y no `summary()`, porque `summary()` recorre solo cuentas activas ([kg_ledger.py:378-381](backend/app/services/kg_ledger.py#L378-L381)) y un corte viejo podría omitir una cuenta que hoy está inactiva pero que a esa fecha tenía saldo. `balances()` no filtra por `is_active`.

⚠️ **Y eso no alcanza (F4 de QA):** `balances()` devuelve kilos por `account_id`, así que para saber cuáles son de Willard hay que listar las CUENTAS, y esa lista también va **sin** filtro de `is_active`. Si se filtra ahí, el agujero que `balances()` evitó vuelve a entrar por la otra puerta.

**La frontera del corte se escribe UNA vez, en el helper:** kilos con `transaction_date <= cutoff_dt` (que es lo que hace `balances()`) y precio con `effective_date < cutoff_dt`, donde `cutoff_dt` son las 00:00 del día siguiente. Como las dos fechas se guardan a mediodía UTC, el conjunto es el mismo; lo que importa es que la regla no viva en dos sitios.

**D9 — La deuda intersede queda FUERA, y no por falta de tiempo.**
El balance no tiene vista por sede: solo acepta fecha de corte ([reports.py:1520-1528](backend/app/services/reports.py#L1520-L1528)). La deuda entre planta y Circunvalar es interna, así que en el balance de la empresa se anula. Valorarla hoy construye un número que no aparece en ninguna pantalla. Cuando exista un balance por sede, valorarla es reusar todo esto y solo cambia de dónde salen los kilos. Q-44 sigue abierta y **no la desbloquea este ciclo**.

**D10 — Costo y mercado conviven, separados a la vista.**
El inventario está al costo promedio y la deuda va a precio de mercado. En el General quedan dos líneas, `Inventario` y `(-) Deuda en plomo con Willard`, y el neto es el total de activos. No se netean en una sola cifra: esa línea tendría dos criterios y nadie podría explicarla.

🔴 **Dónde aterriza contablemente, dicho explícito (F2 de QA):** la valoración **no pasa por resultados**. `equity` es residual en los cuatro caminos, `total_assets − total_liabilities` ([reports.py:1628](backend/app/services/reports.py#L1628), 1750, 1984, 2145), así que el patrimonio absorbe la valoración a mercado entera. El P&L, la utilidad acumulada y la distribuida no se mueven ni un peso, y eso es justo lo que T13 prueba.

---

## 3. Modelo de datos

Tabla `lead_market_prices`, con `OrganizationMixin` y `TimestampMixin` ([base.py:49-74](backend/app/models/base.py#L49-L74)):

| columna | tipo | nota |
|---|---|---|
| `id` | GUID PK | `default=uuid4` |
| `organization_id` | GUID FK organizations CASCADE | del mixin, `index=True` |
| `price_per_kg` | Numeric(12,2) NOT NULL | CHECK `> 0` |
| `effective_date` | DateTime(timezone=True) NOT NULL | fecha de negocio, mediodía UTC vía `BusinessDate` |
| `notes` | String(500) NULL | de dónde salió el precio |
| `created_by` | GUID FK users RESTRICT NOT NULL | patrón `ServiceTariff` |
| `created_at` / `updated_at` | DateTime(timezone=True) NOT NULL | `server_default=now()` **también en la migración** |

- CHECK con nombre: `ck_lead_market_prices_price_positive`.
- Índice: `ix_lmp_org_effective` sobre `(organization_id, text("effective_date DESC"))`.
- Índice del mixin creado a mano en la migración: `ix_lead_market_prices_organization_id`.
- Registrar el modelo en [models/__init__.py](backend/app/models/__init__.py): sin eso la tabla no existe en la base de tests y el chequeo de paridad saca todo como divergencia.

**Migración** `<hex>_cc014_lead_market_prices.py`, `down_revision = "f3a4b5c6d7e9"`, que hoy es la única cabeza. Aditiva pura: una tabla nueva, cero cambios a tablas compartidas, sin backfill.

🔴 La migración **repite** `server_default=sa.text('now()')` en `created_at` y `updated_at`. El chequeo de paridad excluye `server_default` a propósito, así que esta dirección no la cubre ningún gate: es el defecto que costó un 500 en el primer POST de las salidas de plomo ([schema_parity_check.py:26-31](backend/scripts/schema_parity_check.py#L26-L31)).

---

## 4. Backend

**Servicio nuevo** `services/lead_market_price.py`, calcado de `service_tariff.py`: `create`, `get_all` histórico, `get_current(org)` y `get_current_as_of(org, cutoff)`. Sin update ni delete.

**Endpoints** `api/v1/endpoints/lead_market_prices.py`, router con `dependencies=[Depends(require_org_flag("kg_ledger_enabled"))]`:

| verbo | ruta | permiso |
|---|---|---|
| GET | `""` histórico | `tariffs.view` |
| GET | `"/current"` | `tariffs.view` |
| POST | `""` → 201 | `tariffs.manage` |

Sin PATCH ni DELETE: la ruta no existe, así que la colección da 405 y `/{id}` da 404, igual que tarifas ([test_sac_e1_config.py:235-245](backend/tests/test_sac_e1_config.py#L235-L245)). `/current` se declara antes de cualquier ruta paramétrica.

⚠️ **Permisos reutilizados, no nuevos.** `tariffs.view` / `tariffs.manage` ya existen, están gateados por el mismo flag y los administra la misma gente. La alternativa, dos permisos propios, cuesta migración más catálogo más rótulo de módulo por una pantalla de un campo. **Aprobado por QA**; ver el residuo en H3, §8.

**Validaciones**: `price_per_kg > 0` por schema; `effective_date` no futura, comparada contra `business_today()` — nunca `date.today()` ni `now(utc).date()`, por la regla del reloj único; `notes` máximo 500.

**Reportes**, cuatro puntos, dos en vivo y dos en histórico:

1. `_get_balance_sheet_current`: calcular después del bloque de inventario ([reports.py:1546-1557](backend/app/services/reports.py#L1546-L1557)), sumar al total explícito de 9 términos ([reports.py:1613-1614](backend/app/services/reports.py#L1613-L1614)) y pasar el objeto al constructor ([reports.py:1637-1648](backend/app/services/reports.py#L1637-L1648)).
2. `_get_balance_sheet_historical`: lo mismo tras [reports.py:1681-1682](backend/app/services/reports.py#L1681-L1682), total en [1733-1734](backend/app/services/reports.py#L1733-L1734), constructor en [1761-1772](backend/app/services/reports.py#L1761-L1772).
3. `get_balance_detailed`: ítem extra en `inv_liq_items` tras [reports.py:1854](backend/app/services/reports.py#L1854). El total de activos ya agrega por sección ([reports.py:1964](backend/app/services/reports.py#L1964)), no se toca.
4. `_get_balance_detailed_historical`: espejo tras [reports.py:2077](backend/app/services/reports.py#L2077).

Un helper único `_get_lead_debt_valuation(db, organization_id, cutoff_dt=None) -> LeadDebtValuation | None` alimenta los cuatro. Es el mismo criterio de un solo punto de decisión que se usó en los traslados por sede: si hay dos copias, se desincronizan.

🔴 **El helper corta por FLAG en su primera línea (F3 de QA).** Lee `get_org_setting(db, org, "kg_ledger_enabled")` y, si está apagado, devuelve `None` **sin ejecutar una sola consulta** contra `kg_ledger_*`. D6 promete que las otras seis organizaciones ven lo que ven hoy, y eso incluye no crear la dependencia reportes→libro de kilos en sus balances. T9 lo asserta con un `monkeypatch` de `balances()` que revienta si alguien la llama.

⚠️ `reports.py` no importa nada de `kg_ledger` hoy: un grep da cero. Este ciclo crea esa dependencia, y por eso el golden es gate duro.

---

## 5. Frontend

**Pantalla** `frontend/src/pages/config/LeadPricePage.tsx`, calcada de `TariffsPage.tsx`: tabla del histórico, diálogo de creación con `MoneyInput` y selector de fecha, vigente marcado, `EmptyState` cuando no hay ninguno. Ruta `/config/lead-price` declarada con el guard compuesto `FP` de [App.tsx:126-134](frontend/src/App.tsx#L126-L134), flag más permiso. Entrada en **las dos** listas que el propio código pide mantener a la par: `ConfigLayout` y `Sidebar`, ambas con `orgFlag: "kg_ledger_enabled"`.

Servicio y hook con el patrón chico: `services/sacConfig.ts` y `useSacConfig.ts`, invalidación por llave propia, sin tocar `queryInvalidation.ts`. El precio llega como string porque el backend serializa `Decimal` así: se convierte con `Number()` en la frontera del servicio, no en la pantalla.

**Balance General** ([BalanceSheetPage.tsx:45](frontend/src/pages/reports/BalanceSheetPage.tsx#L45)): línea nueva bajo Inventario, con el sub-texto del precio y su fecha. ⚠️ Las líneas vecinas usan el guard `{data.assets.X > 0 && ...}`, que escondería un valor negativo: esta usa `!= null`.

**Exportaciones**: `exportBalanceSheetExcel` ([excelExport.ts:650](frontend/src/utils/excelExport.ts#L650)) y `exportBalanceSheetPDF` ([pdfExport.ts:923-932](frontend/src/utils/pdfExport.ts#L923-L932)). El Detallado no necesita cambios en sus exportaciones porque el ítem viaja dentro de una sección que ya se pinta.

**Mobile primero**: la pantalla nueva se construye usable en 390px al mismo tiempo que la de escritorio.

---

## 6. Gates

| gate | por qué |
|---|---|
| **golden ×3 orgs** | 🔴 gate duro: `reports.py` es compartido. El campo nuevo debe llegar `None` en las tres |
| golden: harness | 🔴 regla exacta de QA (F5): `classify()` mapea **solo** `balance_sheet` y `balance_sheet_asof` a `{"lead_debt_willard": None}`. `balance_detailed` y `balance_detailed_asof` **NO entran**: D7 promete cero claves nuevas y la misma longitud de lista en las tres orgs, así que si ahí aparece algo es un diff real y debe romper. El comparador busca la clave por nombre a cualquier profundidad ([golden_diff.py:48-56](backend/scripts/golden_diff.py#L48-L56)), así que funciona estando dentro de `assets` |
| golden: guarda de la guarda | test nuevo en `test_golden_completeness.py`, que hoy no menciona `ALLOWED_ADDED` ni `classify`: la clave con un valor distinto de `None` tiene que caer como CLAVE NUEVA. Y en el informe, el diff del harness va **separado** del diff de producto, con la frase «el gate se amplió en UNA clave con valor None» |
| parity check | tabla nueva, no está en el baseline: cualquier divergencia lo rompe |
| ruff, eslint 37, tsc, build | |
| suite completa | el conteo se actualiza en CLAUDE.md con el número de la corrida |
| pantalla | abrir el balance de SAC con precio y sin precio; ningún gate ejecuta una pantalla |

---

## 7. Tests

Archivo nuevo `backend/tests/test_lead_debt_valuation.py`.

| # | qué prueba |
|---|---|
| T1 | feliz: 100 kg y precio 2.400 dan una línea de −240.000 y el total de activos baja exactamente eso |
| T2 | el Detallado trae el ítem dentro de la sección de inventario y el total de la sección baja lo mismo |
| T3 | append-only: PATCH y DELETE dan 405 en la colección y 404 en `/{id}` |
| T4 | `price_per_kg <= 0` da 422; fecha futura da 422 |
| T5 | dos precios el mismo día: gana el último por `created_at, id` |
| T6 | corte histórico: precio viejo para el corte viejo, nuevo para el de hoy, kilos de cada fecha |
| T7 | corte anterior al primer precio: `value` en `None`, `kg` lleno, el total de activos no cambia |
| T8 | con kilos y sin precio vigente: mismo resultado que T7, con el aviso |
| T9 | 🔴 no-regresión: organización sin `kg_ledger_enabled` recibe `lead_debt_willard` en `None`, el resto del balance byte a byte igual, y **`monkeypatch` de `balances()` que revienta si se la llama** (F3: sin flag no se toca el libro de kilos) |
| T10 | signo: saldo del libro negativo produce línea positiva, sin `abs()` |
| T11 | RBAC: sin `tariffs.manage` el POST da 403; sin flag, 403 aunque sea admin |
| T12 | as-of: cuenta con saldo al corte y **desactivada ANTES de pedir el corte** sigue contando, tanto en los kilos como en la lista de cuentas (F4) |
| T13 | 🔴 la valoración **no toca resultados**: `accumulated_profit` y `distributed_profit` idénticos con y sin precio, y `equity` baja exactamente `value`. (La versión anterior de este test, «activos = pasivos + patrimonio», era TAUTOLÓGICA: `equity` es residual en los 4 caminos, así que cuadra con cualquier número, incluido uno mal. Hallazgo F2 de QA.) |

Y un test de la guarda del golden en `test_golden_completeness.py`: la clave nueva se perdona solo con valor `None`.

---

## 8. Huecos y preguntas abiertas

**H1 — De dónde sale el precio y cada cuánto se actualiza.** No se habló. No bloquea: se construye el campo y ella lo llena. Va junto a la pregunta de Materiales Willard (Q-37).

**H2 — Back-dating.** Elevado a decisión en D1 por F8 de QA: no es una nota al pie, es un cambio de regla que Daniel aprueba explícitamente y que conviene decirle a Johana en una frase, porque es el mismo tipo de sorpresa que la #61.

**H3 — Permisos reutilizados.** `tariffs.view` / `tariffs.manage`, aprobado por QA. ⚠️ Dato que hay que escribir y no descubrir después (F10): **ningún rol custom del seeder los tiene**, así que la pantalla del precio queda solo para administradores por bypass. Hoy Johana es administradora, así que funciona; el día que quieran delegarlo hay que asignar el permiso a un rol.

**H4 — Qué pasa si Willard le debe plomo a SAC.** El signo lo cubre D10 y T10, pero el rótulo «Deuda en plomo con Willard» quedaría raro en positivo. Propuesta: el rótulo cambia a «Plomo por recibir de Willard» cuando el valor es positivo.

**H5 — Fuera de alcance explícito.** La deuda intersede (Q-44), el balance por sede, y valorar `intra_horno` y `crisol`.

---

## 9. Orden de trabajo

0. 🔴 Resolver F1: commitear #109 tras la pantalla de Daniel, o abrir un `git worktree` para este ciclo. Sin eso no se empieza.
1. Modelo, migración y servicio, con el chequeo de paridad corriendo antes de seguir.
2. Endpoints y sus tests de contrato.
3. El helper de valoración y los cuatro puntos de reportes, con T1, T2, T9 y T13.
4. El resto de los tests.
5. Frontend: pantalla de Config, línea del General y exportaciones.
6. Gates: golden antes y después, parity, linters, build, suite.
7. Pantalla con Daniel y commit.
