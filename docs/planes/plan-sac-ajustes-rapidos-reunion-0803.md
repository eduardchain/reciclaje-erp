# Plan — Ajustes rápidos de la reunión SAC del 3 de agosto

**Versión 1.2 — 2026-08-04.** Ciclo: plan → micro-QA → GO → código+tests → informe → QA → pruebas Daniel → commit develop.

Fuente: `docs/soluciones ambientales del caribe/Reunión iniciada a las 2026_08_03 13_59 GMT-05_00 - Notas de Gemini.md` (Johana Vesga, Erwin Beleño, Daniel).

**v1.1** incorporó las 5 respuestas de Daniel (§8): autoservicio SÍ · hora en TODAS las organizaciones · el bug de la placa se arregla acá · factura también en Willard · consecutivo fuera. Y sumó un hallazgo que cambia el diseño de la hora (**Q6**).

**v1.2 incorpora el micro-QA** (que revisó la v1.0, antes de que existieran las respuestas de Daniel): se adoptan **H1+H2** (se elimina el GET del endpoint de centros — el frontend ya lee la lista por `useOrgSettings`), **H3** (watch-point del outer join en el buscador), **H4** (el JSONB se reasigna, nunca se muta, y el test relee desde BD) y la asimetría de `vehicle_id` señalada en Q4. Ver §10 para la reconciliación completa entre las recomendaciones de QA y las decisiones de producto.

De los 8 compromisos de esa reunión, este plan cubre los **4 rápidos** + 1 bug. Los otros 3 (multi-proveedor por línea, estado "revisada", vencimientos de obligaciones) son ciclos propios y quedan **fuera** — ver §2.

---

## 1. Por qué

| # | Quién lo pidió | Cita | Estado hoy |
|---|---|---|---|
| **A** | Johana (min 23:00) | *"Faltaría como colocarle el número de la factura en caso de que la tenga"* | `Purchase.invoice_number` existe hace tiempo; la Entrada no lo expone ni lo propaga, y Willard no tiene dónde guardarlo |
| **B** | Daniel, en vivo (min 14:20) | *"Creo que me falta aquí agregarle la hora"* | Los bloques de auditoría renderizan los timestamps con `formatDate` (sin hora) |
| **C** | Johana (min 09:00) | *"¿Se puede ahí donde dice centro de distribución se pueden adicionar?"* — Daniel: *"sí, ahorita los adicionamos"* | `willard_distribution_centers` es un setting de org; **solo lo escribe un superusuario**. Johana no puede |
| **D** | Daniel, en vivo (min 48:19) | *"Deberíamos crear una categoría que se llame gastos financieros"* | Ninguna org SAC tiene una categoría `pnl_section='financiero'` |
| **E** | Hallazgo del código (no de la reunión) | — | Editar el vehículo de una Entrada tipo compra **no** re-sincroniza `purchase.vehicle_plate`; el listado de Compras filtra y muestra la placa vieja |

### Corrección al framing inicial (verificada en código)

En la discusión previa dije que la categoría financiera hacía que *"los intereses caigan solos en la sección correcta del P&L"*. **Eso ya pasa hoy sin la categoría**: el clasificador de 3 niveles de #71 hace ganar la FUENTE sobre la categoría — [reports.py:909-910](../../backend/app/services/reports.py#L909-L910) fuerza `obligation_interest_accrual → financiero` sin mirar qué categoría se eligió.

El valor real de **D** es más estrecho y sigue siendo legítimo:
1. **Reporte de Gastos (#44)** agrupa por categoría: hoy los intereses caen en la categoría al azar que se eligió (Daniel en la demo: *"vamos a mandarlo aquí a lo que sea"*).
2. **Gastos financieros manuales** (comisión bancaria, 4×1000 registrados como `expense` suelto) SÍ dependen de la categoría para llegar a la sección financiera — ahí no hay fuente que los salve.

---

## 2. Alcance

**DENTRO:**
- **A** — `invoice_number` en la Entrada, **ambos tipos** (compra y Willard). Migración aditiva.
- **B** — Hora en los timestamps de auditoría **de todas las organizaciones** (páginas compartidas incluidas), con la restricción de Q6.
- **C** — Autoservicio de centros de distribución Willard (endpoint estrecho + permiso nuevo + UI en Config).
- **D** — Categoría raíz "Gastos Financieros" (`pnl_section='financiero'`, indirecta) en el seeder SAC + alta en la org de producción.
- **E** — Fix: propagar placa (y conductor) a la compra derivada al editar la Entrada.

**FUERA (declarado, no silencioso):**
- Multi-proveedor por línea (Green Loop / ruta) — ciclo propio, cambia la cardinalidad entrada→compra.
- Estado "revisada" — ciclo propio; además exige crear al usuario David y repartir el rol de Erwin.
- Fechas de vencimiento / calendario de cuotas en obligaciones financieras — no existe nada en el modelo (`financial_obligation.py:13` lo dice literal: *"Abonos libres (sin plazo ni cuota)"*).
- **Consecutivo configurable de arranque** — Daniel (2026-08-04): *"deja eso fuera por ahora, al momento de la puesta en marcha lo tomamos de nuevo"*.
- Carga inicial de saldos y activos fijos de SAC.
- **Timestamp real de liquidación** — ver Q6; si se aprueba es su propio ciclo con golden.

---

## 3. Diseño

### A — Número de factura en la Entrada (ambos tipos)

**Migración aditiva** (Daniel confirmó Q1 = sí): `inbound_orders.invoice_number String(50) NULL`. Constraint calcado de `PurchaseCreate.invoice_number` ([purchase.py:102](../../backend/app/schemas/purchase.py#L102)) — cero drift.

**Regla de oro: una sola fuente de verdad POR TIPO, jamás dos para la misma fila.**

| Tipo | Dónde vive la factura | Por qué |
|---|---|---|
| `purchase` | `purchases.invoice_number` (la columna nueva queda **NULL**) | La factura es del documento comercial. El módulo de Compras ya la muestra, la busca y la exporta; duplicarla desincronizaría al editar la compra por su propia ruta |
| `willard` | `inbound_orders.invoice_number` | No hay compra derivada. La captura de patio es el único documento |

- **Create**: tipo compra → la derivación D7 ([inbound_order.py:144-157](../../backend/app/services/inbound_order.py#L144-L157)) suma `invoice_number=obj_in.invoice_number` al `PurchaseCreate`, y la columna del inbound queda NULL. Tipo Willard → se persiste en la columna propia.
- **Update**: `if "invoice_number" in fields_set:` → escribe en el destino que corresponde al tipo. `exclude_unset` distingue ausente de `None` explícito (patrón de `notes`), así que mandar `null` **borra** la factura.
- **Response**: `invoice_number = purchase.invoice_number if order.purchase else order.invoice_number`. El enrich B1 **ya trae** la compra derivada por página → cero queries nuevas. La lectura condicional hace la desincronización **imposible por construcción**, en vez de depender de que los dos lados se mantengan a mano.
- **Invariante defendido en el servicio**: una orden tipo compra nunca escribe su columna propia. Un test lo clava (§6.6).
- **Editable después de liquidar: SÍ.** `invoice_number` NO entra al set bloqueado D7b (`{lines, date, willard_distribution_center}`). Es un dato de referencia sin efecto financiero — mismo criterio que `notes`. La factura del proveedor llega tarde con frecuencia; bloquearla obligaría a anular una compra liquidada para escribir un número.

### B — Hora en la auditoría (todas las organizaciones)

**Frontend puro. Cero backend, cero migración.** Los responses ya exponen los timestamps completos; el dato viaja y se está descartando al pintar.

**⚠️ La restricción que descubrió la implementación** — no todos los campos con nombre de timestamp lo son:

| Campo | Qué es | Origen | Hora |
|---|---|---|---|
| `created_at` | Timestamp real de captura | `TimestampMixin`, `now()` de PG | **CON hora** |
| `cancelled_at` / `annulled_at` | Timestamp real de anulación | `datetime.now(timezone.utc)` ([purchase.py:746](../../backend/app/services/purchase.py#L746), [sale.py:541](../../backend/app/services/sale.py#L541), [inbound_order.py:588](../../backend/app/services/inbound_order.py#L588)) | **CON hora** |
| `liquidated_at` | **Fecha de negocio elegida por el liquidador** | `liquidation_date or document.date` ([purchase.py:586](../../backend/app/services/purchase.py#L586), [sale.py:396](../../backend/app/services/sale.py#L396)) → **mediodía UTC** (#42, #62) | **SIN hora** |
| `date` de cualquier documento | `BusinessDate` normalizado | `BeforeValidator` de `utils/dates.py` → mediodía UTC | **SIN hora** |

Pintar `liquidated_at` con hora imprimiría **"12:00 p.m." en toda liquidación del sistema** — una hora inventada, y encima confundiría "cuándo tuvo efecto" con "cuándo se hizo el clic". La hora real del clic **no se persiste hoy en ninguna parte** (ver Q6).

**Regla del repo que este ciclo establece:** *fecha de negocio → `formatDate`; timestamp de auditoría → `formatDateTime`*. Cualquier campo cuyo valor provenga de un `BusinessDate` se queda sin hora, se llame como se llame.

**Páginas (6):**
- SAC: `InboundDetailPage`, `TransferDetailPage`, `TariffsPage`, `FormulasPage` (en las dos últimas la hora es especialmente útil: son append-only y `vigente = max(created_at, id)` — dos versiones del mismo día son hoy indistinguibles).
- Compartidas (Daniel aprobó Q3 = todas las orgs): `PurchaseDetailPage`, `SaleDetailPage`. Se revisa además `DoubleEntryDetailPage` durante la implementación (el grep inicial no lo listó; si tiene bloque de auditoría, entra).

En cada una: `formatDate → formatDateTime` **solo** en las filas de `created_at` / `cancelled_at` / `annulled_at`. Las filas de `date` y `liquidated_at` **no se tocan**.

### C — Centros de distribución en autoservicio

**El problema real no es el CRUD, es el guard.** `organization.settings` es un JSONB con **semántica REPLACE** que contiene, en el mismo dict, los 3 feature flags. Hoy solo lo escribe `PATCH /system/organizations/{id}` con `get_current_superuser`. Dejar que un admin de org escriba settings completo le permitiría **encender `internal_maquila_enabled` o `two_step_transfers_enabled`** — inaceptable.

Diseño: **endpoint estrecho que solo puede tocar una clave.**

```
PUT /api/v1/organizations/settings/willard-distribution-centers
Guards: require_org_flag("kg_ledger_enabled")  +  require_permission("config.manage_sac_settings")
Body:   { "centers": ["baq", "bog", "monteria", "santa_marta", "motocosta", "sincelejo"] }
Resp:   { "centers": [...], "warnings": [...] }
```

**Solo PUT — no hay GET (H2 del micro-QA).** El frontend ya lee la lista: `useOrgSettings()` la obtiene vía `GET /organizations/{id}` y el selector de la Entrada ya la consume con `getSetting("willard_distribution_centers")` ([InboundCreatePage.tsx:124](../../frontend/src/pages/inbound/InboundCreatePage.tsx#L124)). La tarjeta de Config usa el mismo hook. Menos superficie, y de paso desaparece **H1**: el borrador especificaba `require_permission("config.view")`, un permiso que **no existe** (el módulo `config` tiene exactamente 4: `view/manage_business_units`, `view/manage_fleet`) — el GET habría dado 403 a todos salvo admin por bypass.

**Requisito explícito**: tras el PUT, invalidar `["org-settings", organizationId]` — es la key que alimenta **tanto la tarjeta de Config como el selector de la Entrada**. Sin eso, el centro nuevo no aparece hasta recargar.

- **Read-modify-write de UNA clave**: lee `org.settings` (o `{}`), **copia el dict**, reemplaza **solo** `willard_distribution_centers`, y **reasigna `org.settings = nuevo_dict`**. Los flags y los demás parámetros pasan intactos por construcción. **Este es el invariante que QA debe atacar.**
- ⚠️ **H4 — el modo de falla es silencioso.** La columna **no** usa `MutableDict`, y el propio modelo lo documenta ([organization.py:53-54](../../backend/app/models/organization.py#L53-L54): *"Sin MutableDict: toda escritura reasigna el dict completo"*). Mutar in-place (`org.settings["k"] = v`) **no persiste** — y el test del invariante pasaría igual, porque los flags quedan intactos… por no haberse escrito nada. Por eso el test de efecto **relee desde BD**, no desde el response (§6.7).
- **Normalización**: `strip()`, minúsculas, sin acentos (reusa `normalize_entity_name` de `services/retention_entities.py`, dueño del formato canónico desde #78), espacios → `_`. Valida 1–24 caracteres (calco de `willard_distribution_center: max_length=24` del schema de la Entrada) y deduplica preservando orden.
- **Lista vacía → 422.** Rompería la validación de pertenencia del consumidor ([inbound_order.py:99](../../backend/app/services/inbound_order.py#L99)) y ninguna entrada Willard podría declarar centro.
- **Quitar un centro en uso: se permite con warning.** El histórico guarda el string en la fila, no una FK — no hay integridad que proteger; solo deja de poder elegirse. Response: `warnings: ["'monteria' se usó en 34 entradas; el histórico no cambia, pero ya no podrá elegirse"]`. Coherente con "avisar, no bloquear" (#17, #76).

**Permiso nuevo `config.manage_sac_settings`** (módulo `config`, sort 131): migración + dual-write triple (migración + `PERMISSIONS_CATALOG` + `MODULE_DISPLAY_NAMES`). **SIN asignar a roles de sistema** — política D4 de E1: viewer/liquidador no ganan capacidad; en SAC lo tienen los 4 admins por bypass. Catálogo 88 → 89.

### D — Categoría "Gastos Financieros"

- `EXPENSE_CATEGORIES` del seeder pasa de tuplas `(name, is_direct)` a `(name, is_direct, pnl_section)`; se suma `("Gastos Financieros", False, "financiero")`. Las 8 existentes quedan `"operativo"` explícito.
- Alta en la org SAC de producción vía API (`POST /expense-categories`), igual que el resto de la provisión.
- **Cero código compartido**: `create_organization` **no siembra categorías de gasto** (verificado), así que no hay path por defecto que tocar y ninguna org existente se ve afectada.
- Es categoría **raíz** e **indirecta**: `pnl_section` solo vive en raíces (#71) y un gasto financiero jamás es costo directo de material.

### E — Fix: la placa editada no llega a la compra derivada

Al editar una Entrada tipo compra, la rama de cabecera ([inbound_order.py:719-723](../../backend/app/services/inbound_order.py#L719-L723)) escribe `order.driver_id` / `order.vehicle_id` y **no toca la compra**. La compra conserva el `vehicle_plate` capturado en el create — y el listado de Compras (#72) **filtra y muestra por esa placa**, así que la corrección del operador no se ve donde importa.

Fix: en la rama de cabecera, si cambió el vehículo **y** existe compra derivada, resolver la placa y asignar `order.purchase.vehicle_plate`. Sin guard de estado: la placa es dato de referencia sin efecto financiero (mismo criterio que D2 para la factura), y una compra liquidada con la placa equivocada es justamente el caso que hay que poder corregir.

**Asimetría hermana que se alinea de paso** (señalada por el micro-QA en Q4): la condición actual es `if obj_in.vehicle_id is not None`, así que **hoy no se puede quitar** el vehículo de una entrada — mandar `null` no hace nada. `notes` ya usa el patrón correcto (`if "notes" in fields_set`, que distingue ausente de `null` explícito). Se alinean `vehicle_id` y `driver_id` a `fields_set`, y `vehicle_id = None` explícito deja `purchase.vehicle_plate = None`. El conductor no existe en `Purchase`, así que no hay nada que propagar de ese lado.

---

## 4. Decisiones y racional

| # | Decisión | Racional |
|---|---|---|
| **D1** | **Una fuente de verdad por tipo**: compra → `purchases`, Willard → `inbound_orders`; la lectura es condicional | Con la factura en ambos tipos hacía falta una columna, pero escribirla **también** para el tipo compra crearía dos copias del mismo dato que hay que sincronizar en 3 caminos (create de entrada, update de entrada, update directo de la compra). La lectura condicional hace la desincronización imposible en vez de vigilarla. |
| **D2** | **Factura editable después de liquidar** | Dato de referencia sin efecto financiero (como `notes`). La factura del proveedor llega tarde con frecuencia; bloquearla obligaría a anular una compra liquidada para escribir un número. |
| **D3** | **`liquidated_at` se queda SIN hora** | No es un timestamp: es la fecha de negocio que el liquidador eligió (#42, y #62 lo obliga a elegirla). Mostrar "12:00 p.m." sería inventar una hora y confundir efecto financiero con momento de captura. |
| **D4** | **Regla general fecha-vs-timestamp** | El repo mezcla ambos en campos con nombres parecidos. Se fija: *valor derivado de `BusinessDate` → `formatDate`; valor de `now()` → `formatDateTime`*. Aplica a todo desarrollo futuro. |
| **D5** | **B toca páginas compartidas** (decisión de Daniel, Q3) | Cambio visual en Costa, MetaRecycling y Biogreen. Es aditivo (agrega precisión, no quita información) y no altera ningún dato ni reporte. Se declara explícito porque es un cambio no pedido por esos clientes. |
| **D6** | **C con endpoint estrecho, no PATCH de settings** | Los feature flags viven en el mismo JSONB con semántica REPLACE. Un endpoint genérico de settings para admins de org sería escalada de privilegios: podrían encender maquila o traslados. El endpoint estrecho hace **imposible** tocar otra clave. |
| **D7** | **Quitar un centro en uso avisa, no bloquea** | El histórico guarda el string en la fila, no una FK. Bloquear obligaría a mantener para siempre un centro que ya no operan. |
| **D8** | **Permiso nuevo en vez de reusar uno existente** | `config.manage_fleet` o `config.manage_business_units` significan otra cosa; reusarlos ata dos capacidades sin relación. Un permiso propio es 1 migración y deja el modelo legible. |
| **D9** | **D no toca `create_organization`** | Sembrar la categoría para todas las orgs nuevas es código compartido sin pedido del cliente. SAC la necesita hoy; si aparece una segunda org con obligaciones, se decide entonces. |
| **D10** | **E sin guard de estado** | Una compra liquidada con la placa equivocada es exactamente el caso que hay que poder corregir. Cero efecto financiero. |

---

## 5. Frontend

**A** — `InboundCreatePage` / `InboundEditPage`: `<Input>` "N° Factura" en la cabecera, visible en **ambos** tipos. `InboundDetailPage`: `InfoRow` condicional (oculto si vacío). `EntradasPage`: la factura entra al buscador existente (el param `search` ya barre # / placa / conductor / tercero / material — se suma factura como `OR` de las dos ramas, `purchases.invoice_number` para tipo compra y la columna propia para Willard, coherente con la lectura condicional de D1).

> ⚠️ **H3 — el watch-point del buscador.** Alcanzar `Purchase` desde la query de entradas **debe seguir siendo `outerjoin`**. Las Willard no tienen compra (`Purchase.id IS NULL`); convertirlo en `join` haría **desaparecer todas las Willard del buscador en silencio**. Sumar el `ILIKE` a la cadena `OR` sobre el outer join existente es seguro (NULL no matchea). Es exactamente la familia del bug que atrapó el test de paridad de Ciclo C — por eso §6.7 lo cubre con un test propio.

**B** — Cambios de una palabra en 6 páginas (`formatDate → formatDateTime`), **solo** en filas de `created_at` / `cancelled_at` / `annulled_at`.

**C** — Config → tarjeta "Centros de Distribución Willard", gated por `FlagGate("kg_ledger_enabled")` + `PermissionGate("config.manage_sac_settings")`: chips con × y un input "+ Agregar centro". **Lee con `useOrgSettings()`** (sin endpoint de lectura propio, H2) y guarda la lista completa (el endpoint es PUT, no PATCH incremental). Al guardar invalida `["org-settings", organizationId]` → se refrescan la tarjeta **y** el selector de la Entrada, que beben del mismo hook.

**Mobile-first** (regla obligatoria): input de factura `w-full`; chips en `flex flex-wrap gap-2`; input de alta `w-full sm:w-64`. Verificación en 390px antes de cerrar la tarea.

---

## 6. Tests (`tests/test_sac_ajustes_0803.py`)

**A — factura**
1. Entrada tipo compra con factura → la **compra derivada** la tiene; `inbound_orders.invoice_number` queda **NULL** (invariante D1).
2. Entrada Willard con factura → se persiste en la **columna propia**; no hay compra.
3. Editar la factura en ambos tipos → se propaga al destino correcto.
4. `invoice_number: null` explícito → borra el valor (distinción `exclude_unset`).
5. Editar la factura con la compra **ya liquidada** → 200 (D2); el resto del set bloqueado D7b sigue dando 400.
6. **Invariante estrella de A**: el response expone la factura correcta en list **y** detail para los dos tipos, **sin queries extra** (assert sobre el conteo de queries con el listener de SQLAlchemy, patrón del enrich B1).
7. **H3 — buscador**: búsqueda por número de factura encuentra ambos tipos; y con un término que **no** matchea la factura, las Willard **siguen apareciendo** (atrapa la degradación de `outerjoin` a `join`).

**C — centros de distribución**
8. PUT válido → lista normalizada, deduplicada y en orden.
9. **Invariante estrella de C**: tras el PUT, los 3 flags y los 5 parámetros restantes **siguen idénticos** — **releídos desde BD** (`db.refresh(org)` o query nueva), no del response (H4: mutar in-place no persiste y el assert contra el response no lo detectaría). Protege D6.
10. **H4 — efecto real**: el centro nuevo está en BD tras el commit (mismo relectura). Sin este test, un in-place silencioso dejaría el ciclo verde y la funcionalidad muerta.
11. Lista vacía → 422.
12. Centro de 25 caracteres → 422; "Montería" → `monteria`.
13. Quitar un centro en uso → 200 + warning con el conteo; la entrada histórica conserva su valor.
14. Sin el flag → **403 incluso para admin** (patrón `require_org_flag` de #75).
15. Sin el permiso → 403; con el permiso → 200.
16. Un centro nuevo queda inmediatamente elegible al crear una Entrada Willard (integración con el consumidor de `inbound_order.py:99`).

**E — placa**
17. Editar el vehículo de una Entrada tipo compra → `purchase.vehicle_plate` queda con la placa nueva.
18. Quitar el vehículo (`null` explícito) → `order.vehicle_id` y `purchase.vehicle_plate` quedan en `None` (la asimetría de `fields_set` alineada).
19. Con la compra **liquidada** → también propaga (D10).

**B y D — sin tests.** B es frontend puro (el repo no tiene infra de test de frontend; precedente #62: verificación por lectura + `tsc`). D es data de seeder; la mecánica de `pnl_section` ya está cubierta por los 15 tests de #71.

---

## 7. No-regresión

- **El golden ×3 orgs NO es gate de este ciclo.** Justificación por ítem:
  - **A** — la migración toca `inbound_orders`, tabla **exclusiva de SAC**: las 3 orgs cliente tienen cero filas y el router está `require_org_flag`-gated. `PurchaseCreate.invoice_number` ya existía → sin cambio de firma en el módulo compartido.
  - **B** — frontend puro; ningún endpoint cambia.
  - **C** — endpoint nuevo doblemente gated. La migración agrega **una fila a `permissions`**; las capturas golden son de reportes y saldos, no del catálogo RBAC. Cambia `GET /permissions` en un ítem para todas las orgs, sin efecto funcional (nadie lo tiene asignado).
  - **D** — seeder.
  - **E** — servicio de inbound, flag-gated.
  - **Ningún reporte cambia de forma ni de valor.** Si QA discrepa del argumento, se corre el golden — pero el argumento tiene que romperse primero.
- **`schema_parity_check.py`** tras la migración de A (gate reutilizable desde E1). ⚠️ No correrlo con pytest en curso: ambos son dueños de 5433.
- **Suite completa verde** antes del commit (1407 actuales + 19 nuevos).
- `tsc` limpio.
- Smoke manual en dev con la org SAC sembrada, y **verificación explícita en un documento de una org cliente** (una compra de Costa en la réplica) de que la fila de liquidación sigue **sin** hora y la de creación **con** hora.

---

## 8. Preguntas

### Resueltas por Daniel (2026-08-04)

- **Q1 — ¿Factura también en Willard?** → **Sí.** Incorporado con migración aditiva y fuente única por tipo (D1).
- **Q2 — ¿Autoservicio de centros o a pedido?** → **Autoservicio.** Se asume el costo de migración + permiso nuevo.
- **Q3 — ¿Hora también en Compras y Ventas?** → **Sí, todas las organizaciones.** Declarado como D5.
- **Q4 — ¿El bug de la placa se arregla acá?** → **Sí.** Es el ítem E.
- **Q5 — Consecutivo de arranque** → **Fuera por ahora**, se retoma en la puesta en marcha.

### Abierta

- **Q6 — ¿Queremos el timestamp real de la liquidación?** Descubierto al implementar B: `liquidated_at` **no es** la hora del clic, es la fecha de efecto que el liquidador elige (#42/#62). El momento real en que Johana liquidó **no se guarda en ninguna parte** — lo más cercano es `updated_at`, que cualquier edición posterior pisa.

  **Mi recomendación: no ahora.** Cuesta una columna nueva en `purchases`, `sales` y `double_entries` — **tres tablas compartidas por las 3 orgs cliente**, y una columna nullable que los list endpoints serializan es exactamente el patrón de claves aditivas que apareció en el último golden. Deja de ser un ajuste rápido y **el golden vuelve a ser gate**. Además solo se llenaría hacia adelante: todo el histórico quedaría en NULL.

  Lo que sí queda con este plan: **quién** liquidó (ya está), **con qué fecha de efecto** (ya está), y **cuándo se capturó** con hora exacta (lo agrega B). Si el equipo de SAC pide "a qué hora se liquidó esto" durante las pruebas, se hace como ciclo propio con su golden.

---

## 9. Runbook post-deploy

1. Deploy del ciclo.
2. **D**: crear "Gastos Financieros" en la org SAC de producción (`POST /expense-categories`, `is_direct_expense=false`, `pnl_section=financiero`). Idempotente si se re-corre el seeder.
3. **C**: asignar `config.manage_sac_settings` al rol admin de SAC — los 4 admins ya lo tienen por bypass, pero dejarlo explícito documenta la intención.
4. Avisar a Johana los 4 cambios y pedirle que pruebe: capturar una compra con factura, editarla después de liquidar, corregir la placa de una entrada ya liquidada y verificar que la compra la refleja, y agregar un centro de distribución.

---

## 10. Reconciliación con el micro-QA

El micro-QA revisó la **v1.0**, es decir **antes** de que existieran las respuestas de Daniel de §8. Verificó de primera mano las 8 premisas del plan (todas ✅), **intentó romper el argumento del golden y no pudo**, y emitió 🟢 GO con condiciones.

**Hallazgos técnicos: los 4 adoptados sin reservas.** H1 (permiso inexistente) y H2 (el GET es redundante) se resuelven juntos eliminando el GET. H3 (outer join del buscador) y H4 (JSONB reasignado + test que relee de BD) entran con test propio cada uno. La asimetría de `vehicle_id` señalada en Q4 se alinea también. Los cuatro son mejoras reales al diseño.

**Tres recomendaciones de QA que las decisiones de producto de Daniel dejan sin efecto** — se declaran para que quede rastro, no se silencian:

| Q | QA recomendó | Daniel decidió | Consecuencia |
|---|---|---|---|
| **Q1** | No agregar la factura a Willard (precedente `goes_directly_to_jm`, peso muerto retirado en #80 B4) | **Sí** | El ciclo gana **una migración aditiva** en `inbound_orders`. Mitigado con la fuente única por tipo (D1): la columna queda NULL en tipo compra, la lectura es condicional |
| **Q2** | Dejar C a pedido — "los centros son ciudades, cambian una vez al año; construir autoservicio cuesta migración + permiso + endpoint + UI + 8 tests para una operación anual" | **Autoservicio** | El ciclo gana **un permiso nuevo** (`config.manage_sac_settings`, catálogo 88→89) |
| **Q3** | No tocar `PurchaseDetailPage` / `SaleDetailPage` — cambio visual no solicitado en las 3 orgs cliente | **Sí, todas las orgs** | Declarado como **D5**. Es aditivo (agrega precisión, no quita información) y no altera dato ni reporte |

**Lo que QA todavía no ha visto** (delta v1.0 → v1.2, si se quiere una segunda pasada): la migración de `inbound_orders.invoice_number`, el permiso nuevo, el cambio en páginas compartidas, el hallazgo **Q6** (`liquidated_at` es fecha de negocio, no timestamp) y el ítem **E**.

**El argumento del golden se sostiene con el alcance ampliado**, y esta es la parte que merece el escrutinio de la segunda pasada: `inbound_orders` es una tabla **exclusiva de SAC** — las 3 orgs cliente tienen cero filas y el router está `require_org_flag`-gated, así que una columna nullable ahí no puede aparecer en ninguna captura. La fila nueva en `permissions` ya fue verificada por QA como inocua (las capturas son reportes y saldos, no catálogo RBAC). B es frontend puro: ningún endpoint cambia. **Ningún reporte cambia de forma ni de valor.**
