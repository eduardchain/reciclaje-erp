# Plan — SAC: Ingrid / Green Loop, usuario con alcance de recolector (v1.0)

**Autor:** Eco Coder 2 · **Revisa:** Eco QA 2 · **Nivel:** lógica · **Rama:** `coder-2/recolector-alcance` (base `de32530`)
**Evidencia:** `~/sac-evidencia/2026-11-20/coder-2-recolector-alcance/` (inventarios, mediciones y los scripts que los producen).
**Estado:** plan. No se construye nada sin el GO de Eco QA 2 y la autorización de Daniel.

---

## 0. En una línea

Se agregan dos cosas: una **marca** por tercero (`third_parties.collector_id`, «este tercero es de Green Loop») y un **alcance** por usuario (`user_collector_scopes`, «este usuario solo opera Green Loop»). Un usuario con alcance pasa por una **lista blanca de ~30 rutas** en `get_required_org_context` (la cifra exacta la fija T2b), y cada una filtra o rechaza por la marca. Cualquier otra ruta le devuelve 403, aunque su rol tenga el permiso. El balance detallado agrupa a los terceros marcados por aparte.

## 1. Qué pidió el cliente

Las citas llevan su grado: (a) textual, (b) Daniel lo afirmó y el cliente asintió, (c) inferencia nuestra. La fuente es `inventario-preguntas-cliente.md`, sección G (Q-69, Q-70, Q-71 y la fila «Proveedores de Green Loop aparte»), reunión del 20-nov.

- Ingrid «es la persona encargada de hacer las liquidaciones y llevar la caja de Green Loop», y la idea es que «sea la que liquide directamente las entradas de ellos» (L38-40, a).
- Al liquidar, que «solamente le aparezcan los proveedores de ellos» (L74, a).
- Ingrid ve los proveedores de Green Loop, sus estados de cuenta, las liquidaciones de sus proveedores y su caja (L213-217 + «Es correcto. Así es», b).
- Ve las Entradas que tienen recolector Green Loop: lo propuso Daniel (L226) y ella respondió «Correcto. Así es» (L229, b).
- En el informe, «que aparezcan pues divididos los proveedores de nosotros de los proveedores que son de Green Look… en las cuentas por cobrar y por pagar» (L76-80, a).
- Marca de los proveedores: «los que dicen Green Look, pues son de él. Hay como dos que no» (L49, a): Adalberto Ávila y «Daniel de la OS» (L51, a). Daniel: «con el nombre no alcanza» (L58).

### Supuestos (se construye con ellos; los decide Daniel en §12)

| # | Supuesto | Por qué así |
|---|---|---|
| **S1 (Q-70)** | Un tercero marcado de Green Loop sigue siéndolo aunque alguna vez le venda directo a SAC. El filtro es **estricto para Ingrid** y **no cambia nada para quien no tiene alcance**: Johana sigue viendo todos los proveedores en todas las Entradas. | Con esto, la respuesta de Q-70 no cambia el modelo. Si es «sí, venden directo», Johana igual los ve; si es «no», tampoco cambia nada. |
| S2 | La marca va en **cualquier tercero**, no solo en proveedores de material: los conductores reciben anticipos desde la caja de Green Loop (fila «Provisionales de Green Loop a conductores», 11-ago). | En la copia de dev, «DANIEL DE LA HOZ (GREENLOP)» es de la categoría *Empleados* (generic), no proveedor (medido). |
| S3 | El recolector mismo (el tercero «Green Loop», service_provider) **no** entra al alcance de Ingrid: su saldo con SAC (comisiones) es asunto de Johana. | No lo pidió el cliente. |
| S4 | Ingrid **no** crea, revisa, edita, desliquida ni anula Entradas: solo las ve y las liquida. | La captura es de báscula y la revisión de Erwin (Q-19). |
| S5 | En la liquidación de Ingrid **no** van retenciones (#93) ni IVA de compra (#122): si vienen en el payload, da 422. Johana sí los puede poner. | Las entidades `[Retenciones]`/`[Impuestos]` son pasivos de SAC, y su selector expone esos saldos. |
| S6 | La comisión del recolector (#83 D11) sí la puede mandar Ingrid, pero su tercero tiene que ser el recolector de su alcance. | La comisión nace en la liquidación y no se puede agregar después. |
| S7 | Desde su caja, Ingrid solo puede hacer pagos a proveedor (`supplier-payment`) y anticipos (`advance-payment`) a terceros de su alcance, más anular los suyos. Fondear la caja es un `transfer` que hace Johana. | Es lo mínimo que describe «llevar la caja». Gastos de la caja de Green Loop: no se pidieron. |
| S8 | Una Entrada es de Ingrid **solo si su recolector es el de su alcance**, aunque todos sus proveedores sean de Green Loop. | La regla que el cliente asintió es «Entradas con recolector Green Loop» (L226-229, b). |

## 2. Lo medido (cada dato con su artefacto)

1. **La restricción de cuentas es por USUARIO, no por rol.** Vive en la tabla `user_account_assignments` (modelo `UserAccountAssignment`, `app/models/user.py:106`) y se edita con `PUT /organizations/{org}/members/{user}/account-assignments`, solo para admins. `RoleResponse` no tiene cuentas: `assigned_account_ids` sale en `my-permissions` y se lee del usuario. El brief decía «account_ids del rol», y está corregido aquí.
2. **Con la lista vacía el usuario ve todo** (fail-open): `_get_allowed_accounts` devuelve `None` si no hay asignaciones (`money_accounts.py:26-31`, `money_movements.py:137-142`). Para un usuario con alcance tiene que ser al revés.
3. **La restricción de cuentas solo se aplica en 4 lecturas:** `GET /money-accounts`, `GET /money-accounts/{id}`, `GET /money-movements` (más `/summary`) y los dos estados de cuenta, por cuenta y por tercero (`money_movements.py:673,719,759,926`). **No** la miran:
   - `GET /money-movements/{id}`;
   - `GET /money-movements/by-number/{n}`;
   - la evidencia (GET, POST y DELETE);
   - **ninguno de los 17 POST de creación**.
   Eco QA 2 llegó a lo mismo por su cuenta (inventario de 301 rutas en `~/sac-evidencia/2026-11-20/qa-2-ingrid/`).
4. **El listado de movimientos con cuentas restringidas filtra mal:** deja pasar todo movimiento con `account_id IS NULL` (`services/money_movement.py:1328-1331`). Eso incluye todas las causaciones de la org (`expense_accrual`, `commission_accrual`, intereses…), de cualquier tercero.
5. **El estado de cuenta de un tercero, para un usuario restringido, rompe el invariante de #55.** Filtra los movimientos por cuenta (`money_movements.py:926-934`) pero sigue cerrando contra el saldo vivo del tercero, así que el saldo corrido deja de cuadrar.
6. **Costa tiene hoy 2 usuarios con cuentas restringidas (6 asignaciones).** Lo midió el Coordinador en dev y lo re-medí en mi copia (`medicion_asignaciones_dev.log`). Los defectos 3 a 5 ya afectan a un cliente.
7. **Datos de Green Loop en la copia de dev** (`reciclaje_coder_2`, réplica de prod; `medicion_gl_dev.log`), org SAC activa:
   - **124 terceros** con el sufijo `(GREENLOOP)` o `(GREENLOP)` en el nombre. 123 son *Proveedor Material* y 1 es *Empleados* (generic): «DANIEL DE LA HOZ (GREENLOP)».
   - Las dos «excepciones» que nombró Johana **ya llevan el sufijo en esta copia**: «ADALBERTO AVILA (GREENLOOP)» y «DANIEL DE LA HOZ (GREENLOP)». No interpreto si es porque las renombraron después de la reunión (Daniel le mostró cómo, L56) o porque eran las que *no* son de Green Loop. Lo resuelve la lista que mande Johana (Q-71, 📎).
   - Hay nombres parecidos que **no** llevan el sufijo y que un patrón amplio atraparía: «BIOGREENLOOP» (−$150.000.000), «ASOCIACION BIOGREEN RECYCLING», «ECOGREEN». **La marca inicial no se hace por regex**: va una lista explícita (§9).
   - **0 de 34 Entradas tienen recolector** (`inbound_orders.collector_id`). Hoy Ingrid no vería ninguna. Ver riesgo R1.
8. **La agrupación por categoría del balance detallado (#38) no sirve para esto.** `_load_tp_behavior_map` guarda «la primera categoría por behavior_type» de una consulta **sin ORDER BY** (`services/reports.py:222-266`), así que un proveedor con dos categorías de material cae en un grupo arbitrario.
9. **Inventario de rutas:** hay **300 rutas montadas** en `/api/v1`, más `/health`. Mi conteo por decoradores da 306; las 6 de diferencia son de `endpoints/deferred_expenses.py`, que **no está montado**. Conciliado contra el de QA 2 con `comm` (`inventario_endpoints_todos.tsv`).

## 3. Cómo se marca un tercero: vínculo vs. categoría de sistema

| Criterio | (A) Vínculo `third_parties.collector_id` → recolector | (B) Categoría de sistema por código (patrón #112 D4b) |
|---|---|---|
| Qué expresa | «es de **este** recolector» | «es de Green Loop» |
| Un segundo recolector | gratis: es otro valor de la columna | otra categoría más un mapa categoría→recolector (otra columna igual) |
| ¿La puede borrar el formulario de terceros? | no: el formulario de categorías no la toca | **sí**: `_sync_category_assignments` borra y recrea, y hacen falta los guards de dos direcciones de #112 D4d. Un admin que edita categorías desmarcaría al proveedor y, en silencio, se lo quitaría a Ingrid |
| ¿Cambia la clasificación del balance? | **no** | **sí**: una categoría lleva `behavior_type`; marcar a un *Empleado* con una categoría `material_supplier` lo vuelve proveedor y cambia su sección en `_classify_third_party` (S2 lo exige) |
| Agrupación del balance | código nuevo, determinista | igual hace falta código nuevo (§2.8) |
| Predicado de filtro | `tp.collector_id = :scope` | `EXISTS` por asignaciones en cada listado |
| Tabla compartida | sí (`third_parties`), NULL en las otras orgs | no (filas solo en SAC), pero lee la tabla compartida de asignaciones |

**Recomendación: (A).** La razón que decide es la cuarta fila: con (B), marcar a un tercero cambia cómo lo clasifica el balance, y con (A) no cambia nada. Además, (A) no se puede deshacer desde el formulario de categorías por accidente.

**Reglas de la marca (422 que nombra el motivo):**
- el recolector es de la misma org, está activo y tiene `service_provider` (#32, el mismo criterio de `inbound_orders.collector_id`, #83);
- no puede ser el mismo tercero;
- **un solo nivel en las dos puntas** (como #94): un tercero que es recolector de otros no puede tener recolector, y no se le puede poner recolector a un tercero que lo es de otros;
- se escribe solo con el flag `kg_ledger_enabled` encendido. En otra org da 422, y el PAR con/sin flag es la red (#99);
- quitarla (`null`) está permitido (patrón `fields_set` de #87).

Se escribe por `PATCH /third-parties/{id}` (permiso `third_parties.edit`, ya existente). `ThirdPartyResponse` gana `collector_id` y `collector_name`, que viajan `null` en las otras orgs.

## 4. Cómo se le da el alcance a un usuario

- **Tabla nueva `user_collector_scopes`** (`id`, `organization_id`, `user_id`, `collector_id`, `created_at` con `server_default=now()` en el modelo **y** en la migración, por la lección de #100), con **UNIQUE (`organization_id`, `user_id`)**: un usuario tiene un solo alcance por org. Calca `user_account_assignments`, que también es por usuario. No se toca `organization_members`, que es el corazón del login de las 7 orgs.
- **Endpoint** `PUT /organizations/{org}/members/{user}/collector-scope` con body `{collector_id: UUID | null}`. Lleva el mismo guard que `account-assignments` (solo admin de la org, más el flag) y `null` borra el alcance. Da 422 si el usuario destino tiene rol admin, porque el admin bypassa permisos y un alcance sobre él sería confuso, o si el recolector no cumple las reglas de §3.
- **Contexto:** `get_required_org_context` lee el alcance con una consulta por índice único y lo deja en `ctx["collector_scope_id"]`. El superusuario sintetizado no tiene alcance.
- **🔴 El alcance lo decide la FILA, no el flag** (patrón #109: «el predicado es el dato»). Si alguien apaga `kg_ledger_enabled`, el alcance sigue restringiendo. **Tampoco lo salta el admin**: si una fila de alcance existe sobre un usuario admin (escrita por ORM o por un cambio de rol posterior), igual restringe. Es fail-closed (test T16c).
- `GET /roles/my-permissions` gana `collector_scope: {id, name} | null`, para que la pantalla lo sepa.

## 5. Dónde se impone: lista blanca en el backend (deny-by-default)

**Mecanismo.** `get_required_org_context` recibe el `Request`. Si el usuario tiene alcance y la función que atiende la ruta (`request.scope["endpoint"]`, identificada como `módulo.función`) no está en `SCOPED_ENDPOINTS` (`app/services/collector_scope.py`), devuelve **403** con un detalle que empieza con «Fuera de tu alcance:» y nombra al recolector.

**Por qué ahí y no ruta por ruta.** Por ese dependency pasan las 300 rutas de org, también las de adjuntos y roles, que no usan `require_permission`. Una ruta nueva que alguien agregue mañana queda **cerrada** para Ingrid hasta que se la agregue a la lista con su filtro y su test.

Que un admin le sume un permiso al rol de Ingrid **no abre** una ruta fuera de la lista: ampliar la lista es un cambio de código. El permiso sigue aplicando dentro de la lista, porque el alcance no da permisos (T14).

Las rutas que no pasan por el contexto de org no cambian: `/auth/*`, `GET /organizations` y `GET /organizations/{id}` (que la pantalla usa para los settings), y las de `/system`. Ninguna sirve terceros, compras ni movimientos.

### 5.1 Inventario: a qué llega el rol propuesto

Rol propuesto «Recolector» (12 permisos existentes, **cero permisos nuevos**): `purchases.view`, `purchases.view_prices`, `purchases.liquidate`, `third_parties.view`, `third_parties.create`, `treasury.view_statements`, `treasury.view_accounts`, `treasury.view_movements`, `treasury.create_movements`, `materials.view`, `materials.view_prices`, `tariffs.view`.

`scripts/alcance_rol.py` sobre el inventario AST da **89 rutas** a las que llegan esos permisos (`alcance_rol_ingrid.tsv`). De esas, **27 van a la lista blanca** y **62 quedan cerradas para el usuario con alcance**. Por ejemplo, quedan cerradas:
- los 15 POST de tesorería fuera de S7;
- `PATCH /purchases/{id}/liquidate`, la liquidación directa sin pasar por la Entrada;
- `POST /inbound-orders/{id}/confirm`, que confirma una Willard;
- `/third-parties/customers`, `/investors`, `/liabilities`, `/provisions`, `/generic` y `/payable-suppliers`;
- `/third-parties/retention-entities` y `retention-configs` (S5);
- las categorías de terceros;
- las listas de precios por proveedor (`/price-list-groups/*`, que revelan la membresía de los proveedores de SAC);
- `/purchases/pending`, `/by-number`, `/supplier/{id}`, `check-duplicate` y `check-invoice`;
- `/money-movements/summary` y `/by-number`;
- el PATCH y el DELETE de adjuntos;
- `GET /roles` y `GET /roles/{id}`.

### 5.2 La lista blanca y la regla de cada ruta

Notación: `alc(tp)` = `tp.collector_id == scope`; `cta(k)` = `k ∈ cuentas asignadas` (con alcance, lista vacía = ninguna); fuera de alcance → **404** (no revela que existe).

| # | Ruta | Regla con alcance |
|---|---|---|
| 1 | `GET /roles/my-permissions` | sin filtro; devuelve `collector_scope` |
| 2 | `GET /materials` | sin filtro (no hay terceros) |
| 3 | `GET /materials/{id}` | sin filtro |
| 4 | `GET /material-kg-profiles` | sin filtro (orden del formato, #121) |
| 5 | `GET /service-tariffs/current` | sin filtro (sugerido de la comisión) |
| 6 | `GET /price-lists/current` | con `third_party_id`, tiene que ser `alc`; si no, 404. Sin el parámetro devuelve la lista general (precios, sin terceros) |
| 7 | `GET /inbound-orders` | se **fuerza** `collector_id = scope`; un `collector_id` del query se ignora |
| 8 | `GET /inbound-orders/{id}` | 404 si `order.collector_id != scope` |
| 9 | `POST /inbound-orders/{id}/liquidate` | 404 como en la fila 8; todo proveedor del reparto `alc` (si no, 422 que lo nombra); toda cuenta de `supplier_payments` `cta` (403); `collector_commission.third_party_id == scope` (422); `supplier_retentions` o impuestos presentes → 422 (S5). Todo se valida antes de escribir (D14 de #93): un rechazo no deja nada |
| 10 | `GET /third-parties` | se fuerza `alc` |
| 11 | `GET /third-parties/suppliers` | se fuerza `alc` |
| 12 | `GET /third-parties/similar` | se fuerza `alc` (no revela nombres de proveedores de SAC) |
| 13 | `GET /third-parties/payable-providers` | devuelve solo el recolector de su alcance (selector de la comisión, S6) |
| 14 | `GET /third-parties/{id}` | 404 si no `alc` |
| 15 | `POST /third-parties` | `collector_id` = scope, **forzado por el servidor**, con lo que venga en el payload |
| 16 | `GET /purchases` | se fuerza `alc(purchase.supplier)` |
| 17 | `GET /purchases/{id}` | 404 si no `alc(supplier)` |
| 18 | `GET /attachments` | solo dueño compra con `alc(supplier)`; venta y transformación → 404 |
| 19 | `GET /attachments/{id}/download` | igual que la fila 18 |
| 20 | `GET /money-movements/third-party/{id}` | 404 si no `alc`; si es `alc`, **historia completa sin filtro de cuentas** (D-E1) |
| 21 | `GET /money-accounts` | solo `cta`; lista vacía = **ninguna** |
| 22 | `GET /money-accounts/{id}` | 403 si no `cta` (comportamiento actual) |
| 23 | `GET /money-movements/account/{id}` | 403 si no `cta` (actual) |
| 24 | `GET /money-movements` | `cta(account)` **o** (`account IS NULL` **y** `alc(tp)`) |
| 25 | `GET /money-movements/{id}` | el mismo predicado; si no, 404 |
| 26 | `POST /money-movements/supplier-payment` | `cta(account)` (403) y `alc(tp)` (404) |
| 27 | `POST /money-movements/advance-payment` | igual |
| 28 | `POST /money-movements/{id}/annul` | el movimiento cumple la fila 25 **y** su cuenta es `cta` (no anula causaciones) |
| 29 | `GET /money-movements/{id}/evidence` | el predicado de la fila 25 |
| 30 | `POST /money-movements/{id}/evidence` | filas 25 y 28 |

Son 30 filas. Las filas 2 y 3, y las 29 y 30, pueden reducirse si la pantalla no las usa; se cierran en la construcción y **la lista final la fija T2b** (doble entrada, §12).

### 5.3 Códigos: una regla para cada uno

- **404**: el objeto existe, pero está fuera de su alcance. Aplica a terceros, Entradas, compras, movimientos, adjuntos y al `third_party_id` de precios. No revela que existe.
- **403 «Fuera de tu alcance: …»**: la ruta no está en la lista blanca.
- **403 «No tienes acceso a esta cuenta»**: la cuenta no está asignada, en lectura o en escritura. Es el mensaje que ya existe; se conserva para no partir el código ni cambiarles el mensaje a los usuarios de Costa.
- **422**: un payload que mezcla lo suyo con lo ajeno, por ejemplo un proveedor ajeno en el reparto o la comisión a otro recolector. Va con el nombre de lo ajeno, porque ella misma lo eligió en pantalla.

### 5.4 Por número, export, PDF, búsqueda y contadores (QA 2, punto 2)

- **Por número:** `GET /purchases/by-number/{n}` y `GET /money-movements/by-number/{n}` quedan **fuera** de la lista: 403 de ruta, con test en T1. Ninguna pantalla de Ingrid los necesita.
- **Export a Excel y PDF:** son client-side (#52, #119) y se arman con lo que devuelven el listado y el detalle, ya filtrados. No hay endpoint de export que filtrar. `fetchAllPages` (#72) pagina sobre el mismo listado.
- **Búsqueda de Entradas** (`search`, que usa EXISTS sobre tercero, material y placa, y el `third_party_id` del query): corre **dentro** del filtro forzado por recolector, así que solo acota lo suyo. Test: `search` con el nombre de B → 0 resultados para Ingrid y ≥ 1 para el control.
- **Contadores:** el badge de Entradas del sidebar (`usePendingEntriesCount` / `useEntriesStatusCounts`) sale del mismo `GET /inbound-orders`, así que cuenta solo lo suyo. Test: el `total` del listado con alcance es 1, y con el mismo rol sin alcance es 3.
- **`amount_sum` / `total`** de los listados de compras y movimientos se calculan **después** del filtro (test: suma igual a la de sus filas).

### 5.5 Escrituras que podrían ampliar el alcance (QA 2, punto 4)

| Escritura | Con alcance | Test |
|---|---|---|
| Cambiar el `collector_id` de una Entrada (`PATCH /inbound-orders/{id}`) | fuera de la lista → 403 (S4) | T1 + caso explícito |
| Crear una Entrada (`POST /inbound-orders`) | fuera de la lista → 403 | T1 |
| Crear un tercero | nace con su recolector, **forzado** (fila 15) | fila 15 |
| Editar un tercero (`PATCH /third-parties/{id}`), o sea poner o quitar la marca | fuera de la lista → 403 | T1 + caso explícito |
| Poner o quitar el alcance (`PUT /organizations/…/collector-scope`) | no pasa por el contexto de org: guard `is_admin`, y Ingrid no es admin → 403 | T16 |
| Asignarse cuentas (`PUT …/account-assignments`) | mismo guard admin → 403 | T16 |
| Editar roles (`/roles` POST, PATCH y DELETE) | fuera de la lista → 403 (además, `admin.manage_roles`) | T1 |
| Liquidar con un proveedor ajeno | 422 (fila 9) | fila 9 |
| Pagar o anticipar a un tercero ajeno | 404 (fila 26) | fila 26 |

### 5.6 Fugas laterales que quedan, declaradas

- **D-E2, una Entrada suya con un proveedor ajeno adentro.** Si Johana (sin alcance, S1) liquida E_GL con el proveedor B, Ingrid ve en el detalle de E_GL el nombre de B y el resumen de su compra, porque la Entrada es de ella (S8). La compra de B, en cambio, le da 404. Para cerrarlo hay dos opciones: (a) declararlo como está (recomendado: es la Entrada de Green Loop y lo puso alguien de SAC a propósito); (b) en una Entrada con recolector GL, que Johana reciba un **aviso** (no un bloqueo) al repartir a un proveedor sin la marca. Lo decide Daniel junto con Q-70 (decisión 3).
- **Su caja muestra todo lo que pasa por su caja.** Si Johana paga a B desde K1, Ingrid ve ese movimiento con el nombre de B, porque la cuenta es suya (fila 24). Es correcto por definición de «su caja».
- **D-E1:** en el estado de cuenta de un proveedor suyo puede aparecer el nombre de una cuenta de SAC (§5.2).

**D-E1, la historia completa del estado de cuenta en alcance.** Si se filtrara por cuenta, el saldo corrido de un proveedor de Green Loop no cerraría contra su saldo vivo (§2.5), justo en los proveedores que tienen saldo inicial o pagos hechos desde una cuenta de SAC. El tercero ya es suyo; lo que le restringe la cuenta es la **caja que opera**, no la historia que lee. Costo: Ingrid ve el nombre de la cuenta de SAC desde la que se pagó a uno de sus proveedores.

## 6. El hueco preexistente de cuentas (Costa ya lo tiene)

Para el usuario con alcance, el hueco se cierra **en este ciclo**, decida lo que decida Daniel sobre Costa. Su caja queda cerrada por dos razones independientes:
- todas las rutas de tesorería que él puede tocar (filas 21 a 30) llevan el chequeo de cuenta escrito en su regla;
- todas las demás (by-number, los otros 15 POST de creación, el DELETE de evidencia) están **fuera de la lista blanca** y le dan 403 antes de llegar al código.

Ninguna ruta que mueva o muestre dinero queda sin una de las dos, y lo prueban T1 más las filas 21 a 30. Para el usuario restringido **sin** alcance (los 2 de Costa), propongo un helper único `account_access(db, ctx)` que aplicarían todos los caminos:

- **C1** `GET /money-movements/{id}`, `/by-number/{n}` y la evidencia → 404 si la cuenta no está asignada.
- **C2** los 17 POST de creación, más `transfer` (las dos cuentas) y los pagos inmediatos al liquidar compra, venta o Entrada → 403 si la cuenta no está asignada.
- **C3** listado: el `account_id IS NULL` deja de pasar entero. Opción a decidir: o se ocultan las causaciones, o pasan solo las de terceros con los que el usuario tiene movimientos.
- **C4** estado de cuenta por tercero: se deja como está (D-E1 aplica solo con alcance).

**C2 cambia lo que pueden hacer hoy los 2 usuarios de Costa:** si hoy registran un pago desde una cuenta no asignada, mañana reciben 403. Por eso **lo decide Daniel** (§12, decisión 1): (a) entra en este ciclo con el golden como gate y un aviso a Costa; (b) va en un ciclo propio, recomendado, porque mezcla un pedido de SAC con un cambio de comportamiento para Costa. En cualquiera de los dos casos, este plan deja escrito el helper y los cuatro puntos.

## 7. El balance: Green Loop por aparte

- **Balance Detallado, vivo y as-of.** En cada sección de terceros (CxP proveedores, anticipos a proveedores, CxC, etc.), los terceros con `collector_id` van en un grupo «Recolector: <nombre>», que manda sobre el grupo de categoría. Usa el esquema existente `BalanceDetailedGroup` (#38): **cero claves nuevas**.
- **Costo:** una consulta `SELECT id, collector_id WHERE organization_id=? AND collector_id IS NOT NULL`, vacía en las otras 6 orgs, así que el agrupado queda idéntico por construcción.
- **Balance General: no cambia** en v1. Johana habló del «informe», y el documento que ella exporta es el Detallado (#110 C1). Si Daniel quiere líneas propias en el General, son claves nuevas en `BalanceSheetAssets` y `BalanceSheetLiabilities`, aditivas en el golden (§12, decisión 2).
- **Terceros:** filtro y columna «Recolector» en `ThirdPartiesPage` (`GET /third-parties?collector_id=`, gated por el flag). Es el «estado de las cuentas… por aparte» de la fila del 19-nov.

## 8. Pantalla

Va con capturas a 1440 y 390; la de Daniel es condición de deploy.

- **Config → Usuarios:** selector «Alcance: recolector» junto a la asignación de cuentas, gated por flag y admin.
- **Terceros:** en el formulario, selector «Recolector», gated por el flag y `third_parties.edit`; en el listado, columna y filtro.
- **Con alcance**, la pantalla deja de pedir lo que el backend le niega:
  - en la liquidación, sin `useKgAccounts` (hoy excluye al titular Willard del selector; con alcance, el servidor ya filtra), sin `useRetentionRows` y sin el bloque de IVA;
  - la comisión, con el recolector fijo;
  - en Entradas, sin el filtro de sede ni la pestaña de crear.
  Todo es `enabled: !scope` en los hooks, para que no salgan 403 en la consola.
- **Barra superior:** chip «Green Loop» para que Ingrid sepa por qué ve menos.
- **Sin alcance**, ninguna pantalla compartida cambia: el selector de Johana sigue igual (S1).

## 9. Marca inicial (carga)

`scripts/marcar_recolector.py --collector "Green Loop" --lista <archivo> [--dry-run]`:
- lee una **lista explícita de nombres**, la que mande Johana (Q-71);
- resuelve cada nombre exacto y aborta si hay ambiguos o faltantes;
- imprime la lista y marca vía `PATCH`.

La propuesta de lista sale del sufijo `(GREENLOOP|GREENLOP)` (124 en la copia de dev) y **se la revisa Johana**, no un regex. Contra producción la corre solo el Coordinador, con el OK de Daniel (escritura en prod).

## 10. Migración: una sola línea

`e7f9a1b3c5d8_recolector_alcance.py`, `down_revision = d6e8f0a2b4c7` (cabeza actual, `alembic heads`). El id está libre (grep vacío). Cambios:
- `third_parties.collector_id` UUID nullable, FK `third_parties.id` con nombre por defecto (`create_foreign_key(None, …)`, lección de #111), e índice `ix_third_parties_collector_id`;
- tabla `user_collector_scopes` con sus FKs, `UNIQUE(organization_id, user_id)` e índice por `organization_id` (lo declara el mixin, lección de #100).

El modelo declara lo mismo, y la paridad se verifica con `schema_parity_check.py`. Es aditiva pura: NULL y tabla vacía en las 7 orgs.

**Downgrade:** borra las marcas y los alcances. Después de re-subir, hay que volver a marcar y volver a asignar.

Turno de migración: lo asigna el Coordinador. Si `develop` recibe otra antes, cambio el `down_revision` y eso es un delta para QA.

## 11. Golden: **aplica**

- **Por qué aplica:**
  - columna nueva en tabla compartida (`third_parties`);
  - código en el camino de **todas** las orgs: `get_required_org_context` (cada request), los listados de terceros, compras y movimientos, y `reports.py` (balance detallado).
  - Cinco de las capturas pasan por lo tocado: `balance_detailed`, `balance_detailed_asof`, `money_accounts`, `money_movements` y los dos `tp_statement`.
- **Qué se espera:** **0 diffs y 0 claves aditivas.** `ThirdPartyResponse` no es captura: `/third-parties` solo se llama para *elegir* el tercero del statement, y se re-verifica con un `grep` sobre `CAPTURES` antes de correr. Y en las 3 orgs no hay marcas ni alcances.
- **Como «0/0» no distingue nada de nada (#110), lleva dos pruebas propias:**
  - **Prueba de vida:** `PUT …/collector-scope` da 404/405 en la base y 401/403/200 en la rama.
  - **Control positivo fuera de CAPTURES (smoke):** en mi BD de dev, marcar 3 proveedores de SAC y pedir el detallado de SAC en los dos procesos. El grupo «Recolector: Green Loop» aparece solo en la rama.
- **Forma:** una sola BD (la migración es aditiva). Se corre con `golden_run.sh` (procedencia: PID y log), puertos 8091/8092 y `lockf`.

## 12. Tests

Archivo nuevo `tests/test_sac_recolector_alcance.py`.

**Fixture:** org con flag; recolectores **GL** y **X** (service_provider); terceros **A** y **A2** (GL), **B** (sin marca), **C** (de X) y **D** (conductor generic de GL); Entradas **E_GL**, **E_none** y **E_X**; cuentas **K1**, asignada a Ingrid, y **K2**.

**Usuarios** (nunca admin, que bypassa, #29):
- `ingrid`: rol Recolector, alcance GL, K1;
- `ingrid_libre`: el **mismo rol sin alcance**, que es el control positivo de cada filtro;
- `ingrid_todo`: rol con **todos** los permisos del catálogo y alcance GL;
- `todo_libre`: todos los permisos, sin alcance;
- `johana`: admin.

**El cuadrante, dibujado** (lección de *dibujar-el-cuadrante*). Cada fila de §5.2 tiene sus tres celdas:

| Ruta (fila §5.2) | con alcance, objeto en alcance | con alcance, objeto fuera | sin alcance, mismo rol (control) |
|---|---|---|---|
| 7 Entradas lista | ve E_GL | no ve E_none ni E_X; con `?collector_id=X` sigue viendo solo E_GL | ve las 3 |
| 8 Entrada detalle | 200 | 404 (E_none, E_X) | 200 |
| 9 liquidar | 200 con A | 422 con B, 422 con C, 403 con K2, 422 comisión a X, 422 con retención/IVA; **las 7 tablas sin cambios** | 200 con B |
| 10–13 listados de terceros | solo GL (+ D en 10) | sin B ni C | ven B y C |
| 14 tercero detalle | 200 A | 404 B | 200 B |
| 15 crear tercero | nace con GL aunque el payload diga X | — | nace sin marca |
| 16–17 compras | lista y detalle de A | 404 compra de B | ven la de B |
| 18–19 adjuntos | lista y descarga de la compra de A | 404 compra de B y venta | 200 |
| 20 estado de cuenta | A: **corrido == vivo** con un pago desde K2 adentro | 404 B | B 200 |
| 21–23 caja | solo K1; sin asignaciones → **ninguna** | K2 403 | sin asignaciones ve K1 y K2 (comportamiento actual, regresión) |
| 24–25 movimientos | ve K1 y la causación de A | no ve la causación de B (cuenta NULL); detalle de K2 404 | ve todo |
| 26–27 pagar/anticipar | K1→A 201, K1→D 201 | K2 403; →B 404 | K2→B 201 |
| 28–30 anular/evidencia | el suyo, K1 | causación de A (cuenta NULL) 404; movimiento de K2 404 | 200 |

**El cuadrante de quién × flag × recurso** (QA 2, punto 7). Ruta de muestra: `GET /inbound-orders/{id}`; la misma tabla vale para la familia T1 cambiando «200/404» por «pasa / 403 de ruta».

| Usuario | Flag | Recurso propio (E_GL) | Recurso ajeno (E_none) | Test |
|---|---|---|---|---|
| con alcance (rol Recolector) | on | 200 | 404 | fila 8 |
| con alcance | **off** (apagado después) | **200** | **404**: el alcance sigue | T16b |
| sin alcance, mismo rol | on | 200 | 200 | control de la fila 8 |
| sin alcance, mismo rol | off | 403 (router flag-gated, comportamiento de hoy) | 403 | T18 |
| admin sin fila de alcance | on | 200 | 200 | T16 (control) |
| admin sin fila de alcance | off | 403 (el flag no lo salta el admin, #75) | 403 | existente (`test_inbound_orders`) |
| admin **con** fila de alcance (puesta por ORM) | on | 200 | **404**: fail-closed | T16c |
| admin con fila de alcance | off | 403 (router) | 403 | T16c, segunda mitad |

En las rutas que no tienen flag (`/purchases`, `/third-parties`, `/money-movements`, `/money-accounts`), «off» no cambia nada para el usuario sin alcance (T18). Para el usuario con alcance aplica la fila de T16b.

**Además:**

- **T1, familia (deny-by-default):** parametrizada sobre las **rutas montadas** (`app.routes`, no una lista a mano) que dependen de `get_required_org_context` y no están en la lista blanca. `ingrid_todo` → 403 «Fuera de tu alcance». **Conteo:** la cantidad de casos == rutas con contexto de org − largo de la lista, comparado **antes** del parametrizado (lección de #108). **Control positivo:** en las mismas rutas, `todo_libre` **no** recibe el 403 de alcance; sin eso, un 403 por cualquier otra puerta pasaría el test.
- **T2:** cada entrada de `SCOPED_ENDPOINTS` resuelve a una ruta montada (nada muerto).
- **T2b, doble entrada:** `SCOPED_ENDPOINTS` == un set literal escrito en el test. Ampliar la lista obliga a venir a declararla donde se lee, como `TestClaveAditiva` (#112).
- **T14, permisos con control positivo** (memoria *test-de-permiso…*). Un rol con alcance y `purchases.view` pero **sin** `purchases.liquidate` → `GET /inbound-orders/{E_GL}` 200 (control) y `POST …/liquidate` 403 «Permisos insuficientes»: el alcance no da permisos. Lo mismo con `third_parties.view` sin `treasury.view_statements` (la lista de terceros da 200 y el estado de cuenta 403). Y el barrido por `grep` de los dos permisos de escritura del rol (`purchases.liquidate`, `treasury.create_movements`) sobre la lista blanca: cada uno con su par 200/403.
- **T15, la marca:**
  - válida → 200;
  - el recolector no es service_provider → 422;
  - el recolector es de otra org → 422;
  - el tercero se marca a sí mismo → 422;
  - en las dos puntas del nivel único → 422;
  - org sin flag → 422, y el par con flag → 200;
  - **regresión de (B):** editar las categorías del tercero no le toca `collector_id`.
- **T16, el alcance:**
  - un no-admin pone el alcance → 403;
  - alcance sobre un usuario admin → 422;
  - org sin flag → 422;
  - `my-permissions` con alcance y con `null`;
  - **T16b:** con el flag apagado después, el alcance **sigue** restringiendo;
  - **T16c:** una fila de alcance sobre un admin, puesta por ORM, **sigue** restringiendo (fail-closed).
- **T17, el balance:** en el detallado vivo y as-of, A y A2 van en el grupo «Recolector: GL» dentro de CxP y de anticipos, con totales iguales a los de antes de marcar. Contra la vacuidad: se exige `total != 0` y `grupos ≥ 2` **antes** de comparar (#110). Y en una org sin marcas, el response es igual campo por campo al de sin código, con cero claves nuevas.
- **T18, no-regresión de la otra org:** una org sin flag y sin alcances; un usuario restringido por cuentas sigue viendo lo que ve hoy en las 4 lecturas, salvo lo que decida Daniel en §6.

**Dirigidas.** Son la única red de develop hasta el checkpoint. El comando queda fijo aquí, se re-corre igual en la entrega y se escribe en el log. Eco QA 2 corre esa misma lista.

```bash
cd /Users/daniel.chain/Projects/reciclaje-erp-wt/coder-2/backend
grep -lE '/api/v1/(third-parties|purchases|inbound-orders|money-movements|money-accounts|attachments|roles|organizations)|/api/v1/reports/balance-detailed|collector_id|account_assignments|UserAccountAssignment' tests/*.py | sort > $EV/dirigidas.txt
printf '%s\n' tests/test_reloj_de_negocio.py tests/test_advisory_locks.py tests/test_crucible_charges.py tests/test_sac_recolector_alcance.py >> $EV/dirigidas.txt
sort -u -o $EV/dirigidas.txt $EV/dirigidas.txt
TEST_DATABASE_URL=postgresql://admin:test_password@localhost:5433/reciclaje_test_coder_2 \
  lockf -k ~/.cache/ecobalance/tests.lock ./venv/bin/pytest $(cat $EV/dirigidas.txt) -q -p no:cacheprovider > $EV/dirigidas.log 2>&1; echo "EXIT=$?" >> $EV/dirigidas.log
```

`$EV` = `~/sac-evidencia/<fecha>/coder-2-recolector-alcance`.

- Medido hoy sobre la base `de32530`: el grep da **59 de 95** archivos de `tests/` (`dirigidas_grep_plan.txt`). Ya incluye `test_reloj_de_negocio.py` y `test_crucible_charges.py`; el `printf` agrega la guarda de locks y el archivo nuevo.
- Se esperan muchos archivos: el cambio de `deps.py` pasa por toda ruta de org, y los nueve prefijos son los que se tocan.
- La predicción del conteo se escribe en el log **antes** de correr: `--collect-only -q` sobre la misma lista.
- La suite completa queda diferida al checkpoint («suite diferida al checkpoint»).

## 13. Matriz de plantado

Se commitea **antes** de plantar. Las filas que tocan una vía compartida (marcadas «vía») predicen «al menos estos».

| P | Defecto plantado | Debe caer |
|---|---|---|
| P1 | se quita la lista blanca en `deps.py` | T1 (todas sus filas) — vía |
| P2 | se agrega `GET /purchases/pending` a la lista sin filtro | T2b |
| P3 | el listado de Entradas no fuerza el recolector | fila 7 (incluido el `?collector_id=X`) |
| P4 | el detalle de Entrada sin el 404 | fila 8 |
| P5 | liquidar sin validar el proveedor en alcance | fila 9 B y C |
| P6 | liquidar sin validar la cuenta de contado | fila 9 K2 |
| P7 | `/third-parties/suppliers` sin el filtro (los otros 3 con él) | fila 11 (prueba que la familia está parametrizada) |
| P8 | `POST /third-parties` usa el `collector_id` del payload | fila 15 |
| P9 | el listado de compras sin el filtro | fila 16 |
| P10 | el estado de cuenta en alcance filtra por cuentas (como hoy) | fila 20 (corrido ≠ vivo) |
| P11 | con alcance, lista vacía de cuentas = todas | fila 21 |
| P12 | el listado de movimientos deja pasar `account IS NULL` de cualquier tercero | fila 24 |
| P13 | la marca se valida sin mirar el flag | T15 sin flag |
| P14 | el balance agrupa por categoría, ignorando `collector_id` | T17 |
| P15 | el alcance se impone solo con el flag encendido | T16b |
| P16 | `is_admin` sale antes del chequeo de alcance | T16c |
| P17 | descarga de adjuntos sin el chequeo | fila 19 |
| P18 | `annul` acepta una causación (cuenta NULL) | fila 28 |
| P19 | la búsqueda de Entradas se aplica en OR con el filtro de recolector (precedencia) | §5.4: `search` B → 0 |
| P20 | se agrega `GET /money-movements/by-number/{n}` a la lista | T2b y T1 |
| P21 | el listado de compras calcula `amount_sum` antes del filtro | §5.4: suma == filas |

**Dirección peligrosa a buscar celda por celda antes de plantar:** un test que debía caer y no cae. El candidato más probable es P7 si los cuatro listados comparten helper. Por eso el test se parametriza por ruta y el defecto se planta en una sola.

## 14. Riesgos y fuera de alcance

- **R1 — hoy 0 de 34 Entradas tienen recolector.** Si báscula no lo pone, Ingrid no ve la Entrada. Johana lo puede corregir mientras no esté liquidada (#83/#93), pero hay que comunicarlo. Un aviso «¿Recolector?» en la captura queda como sugerencia y se decide aparte.
- **R2 — una consulta más por request** para todo miembro de las 7 orgs (índice único `(org, user)`). Se mide en la construcción con `EXPLAIN ANALYZE` sobre la copia.
- **R3 — el selector de Johana no cambia (S1).** Si en la pantalla Daniel quiere que también a ella, en una Entrada con recolector GL, se le ofrezcan primero los de GL, es un orden visual y va como sugerencia.
- **Fuera de alcance:**
  - gastos de la caja de Green Loop (S7);
  - líneas propias en el Balance General (decisión 2);
  - el aviso de recolector en la captura;
  - un alcance de Ingrid sobre las Willard (Q-02: Green Loop también recolecta postconsumo; con S4 ella no confirma Willard, pero las ve en el listado si tienen su recolector, y su detalle muestra kg).

## 15. Decisiones para Daniel (las pide el Coordinador)

1. **El hueco de cuentas de §6 para las orgs sin alcance** (Costa: 2 usuarios). (a) Ciclo propio (recomendado); (b) entra en este.
2. **Balance General.** (a) Solo el Detallado agrupa (recomendado); (b) además, líneas propias en el General (claves nuevas).
3. **Supuestos S1–S8** tal como están (recomendado), o cuál cambia. En particular:
   - S5: Ingrid sin retenciones ni IVA;
   - S7: sin gastos desde su caja;
   - D-E2 (§5.6): declarar la fuga, o avisarle a Johana cuando reparte una Entrada de Green Loop a un proveedor sin la marca.
4. **La lista de proveedores de Green Loop** para la marca inicial: la manda Johana (Q-71 📎). Mientras no llegue, la propuesta son los 124 con sufijo.
