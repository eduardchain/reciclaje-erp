# Plan — SAC: Ingrid / Green Loop, usuario con alcance de recolector (v1.2)

**v1.2 (20-nov):** cambios después del GO de Eco QA 2 a la v1.1 (`d271135`, revisión `~/sac-evidencia/2026-11-20/qa-2-ingrid/revision_plan_v1.1.md`, sha256 `97a97be2…a92c`).
- **§15.3 decidida** por Daniel, vía el Coordinador: todas las recomendadas. Ninguna fila del cuerpo cambia.
- **Riesgo de S5** (retención o IVA en compras de Green Loop).
- **Notas de QA 2:** N1 (RESTRICT, §10 y T20), N2 (422 si el alcance es para un superusuario, §4 y T16d) y N3 (prefijo «Fuera de tu alcance» en T1 y T1c).
- **Matriz:** P32 y P33.
- **Corrección de un dato:** el «0 de 34 Entradas con recolector» se había medido sobre Entradas de **prueba** de la copia de dev, no de producción (§2.7 y R1).

**v1.1 (20-nov):** responde al NO-GO de Eco QA 2 sobre la v1.0 (`409e857`, revisión `~/sac-evidencia/2026-11-20/qa-2-ingrid/revision_plan_v1.0.md`, sha256 `e918ab25…10f8`) y a la revisión de producto del Coordinador. Verifiqué los cinco hallazgos contra el código antes de aceptarlos.
- **H1:** el alta de terceros con alcance no acepta saldo inicial y las categorías se restringen (§5.2 fila 15).
- **H2:** anular y la evidencia solo valen para sus propios tipos de pago, y una transferencia nunca (filas 28–30).
- **H3:** lista blanca de CAMPOS, nueva §5.7.
- **H4:** las rutas sin contexto de org, nueva §5.0, con T1b y T1c.
- **H5:** los conductores van por `payment-to-generic`, fila 27b.
- **Decisiones nuevas en §15:** D-a (quién fija la comisión) y D-b (compras por marca o por Entrada).
- **Menores:** M1 (el 422 sin nombre), M2 (P22–P29) y M3 (T2 con métodos).
- **Coordinador:** R1 pasa a condición de uso (§14), runbook de deploy (§16) y nota sobre Adalberto (§2.7).

**Autor:** Eco Coder 2 · **Revisa:** Eco QA 2 · **Nivel:** lógica · **Rama:** `coder-2/recolector-alcance` (base `de32530`)
**Evidencia:** `~/sac-evidencia/2026-11-20/coder-2-recolector-alcance/` (inventarios, mediciones y los scripts que los producen).
**Estado:** plan. No se construye nada sin el GO de Eco QA 2 y la autorización de Daniel.

---

## 0. En una línea

Se agregan dos cosas: una **marca** por tercero (`third_parties.collector_id`, «este tercero es de Green Loop») y un **alcance** por usuario (`user_collector_scopes`, «este usuario solo opera Green Loop»). Un usuario con alcance pasa por una **lista blanca de ~30 rutas** en `get_required_org_context` (la cifra exacta la fija T2b), y cada una filtra o rechaza por la marca y recorta los campos que son de SAC (§5.7). Cualquier otra ruta le devuelve 403, aunque su rol tenga el permiso. Lo mismo pasa con las rutas de miembros de la org, que no pasan por ese contexto (§5.0). El balance detallado agrupa a los terceros marcados por aparte.

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
| S2 | La marca va en **cualquier tercero**, no solo en proveedores de material: los conductores reciben anticipos desde la caja de Green Loop (fila «Provisionales de Green Loop a conductores», 11-ago). ⚠️ **Pendiente de Daniel (H5, §15):** un conductor *generic* no se le puede pagar con `supplier-payment` ni con `advance-payment`, porque exigen material_supplier/service_provider/liability (`money_movement.py:105` y `:642`). Hay dos opciones: (a) sumar `payment-to-generic` al alcance (fila 27b, recomendada); (b) sacar los pagos a conductores del alcance de su caja. | En la copia de dev, «DANIEL DE LA HOZ (GREENLOP)» es de la categoría *Empleados* (generic), no proveedor (medido). |
| S3 | El recolector mismo (el tercero «Green Loop», service_provider) **no** entra al alcance de Ingrid: su saldo con SAC (comisiones) es asunto de Johana. | No lo pidió el cliente. |
| S4 | Ingrid **no** crea, revisa, edita, desliquida ni anula Entradas: solo las ve y las liquida. | La captura es de báscula y la revisión de Erwin (Q-19). |
| S5 | En la liquidación de Ingrid **no** van retenciones (#93) ni IVA de compra (#122): si vienen en el payload, da 422. Johana sí los puede poner. | Las entidades `[Retenciones]`/`[Impuestos]` son pasivos de SAC, y su selector expone esos saldos. ⚠️ **Riesgo, se le pregunta a Johana aparte (Coordinador):** si una compra de Green Loop lleva retención o IVA, esa Entrada la tiene que liquidar Johana, no Ingrid. No cambia el plan. |
| S6 (**D-a**, §15, pendiente de Daniel) | **Propuesta recomendada:** la comisión del recolector (#83 D11) la causa la liquidación de Ingrid, pero **el monto lo fija el servidor**: tarifa vigente `comision_green_loop` × la base sugerida de #93 D11 (kg + unidades × `kg_per_unit`). El tercero es siempre su recolector. Si manda un `amount` distinto al calculado → 422. Para Johana (sin alcance) no cambia nada: el monto digitado manda (#79 F1). | Es la deuda de SAC con Green Loop, y la digitaría una empleada de Green Loop: conflicto de interés (QA 2, D-a). La comisión nace en la liquidación y no se agrega después, así que dejarla a Johana exige un camino nuevo. |
| S7 | Desde su caja, Ingrid solo puede hacer pagos a proveedor (`supplier-payment`), anticipos (`advance-payment`) y, si Daniel elige (a) en H5, pagos a terceros generic (`payment-to-generic`, conductores), siempre a terceros de su alcance, y anular **esos mismos** movimientos. Fondear la caja es un `transfer` que hace Johana. | Es lo mínimo que describe «llevar la caja». Gastos de la caja de Green Loop: no se pidieron. |
| S8 (**D-b**, §15) | Una Entrada es de Ingrid **solo si su recolector es el de su alcance**. En cambio, una **compra** es suya si su **proveedor** tiene la marca, así venga de una Entrada sin recolector o sea directa. | Son las dos reglas que asintió el cliente: «Entradas con recolector Green Loop» (L226-229, b) y «las liquidaciones de sus proveedores» (L213-217, b). Alinearlas es la decisión D-b. |

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
7. **Datos de Green Loop en la copia de dev** (`reciclaje_coder_2`, org SAC activa; `medicion_gl_dev.log`). ⚠️ La copia **no es una réplica limpia**: trae las pruebas locales que se hicieron sobre `reciclaje_db` (`medicion_origen_lista.log`). Los 128 terceros de abajo sí vienen de producción: nacieron en la carga del 10-nov 19:05, medido por `created_at`.
   - **124 terceros** con el sufijo `(GREENLOOP)` o `(GREENLOP)` en el nombre. 123 son *Proveedor Material* y 1 es *Empleados* (generic): «DANIEL DE LA HOZ (GREENLOP)».
   - Las dos «excepciones» que nombró Johana **ya llevan el sufijo en esta copia**: «ADALBERTO AVILA (GREENLOOP)» y «DANIEL DE LA HOZ (GREENLOP)». Según el Coordinador, que tiene la transcripción, Johana dijo de Adalberto que «es Greenloop, pero no dice Greenloop» (L51). La cita me llega de otra sesión y no la medí yo. Si es así, alguien ya lo renombró después de la reunión (Daniel le mostró cómo, L56). No cambia nada: lo resuelve la lista que mande Johana (Q-71, 📎).
   - Hay nombres parecidos que **no** llevan el sufijo y que un patrón amplio atraparía: «BIOGREENLOOP» (−$150.000.000), «ASOCIACION BIOGREEN RECYCLING», «ECOGREEN». **La marca inicial no se hace por regex**: va una lista explícita (§9).
   - ~~0 de 34 Entradas tienen recolector~~ **Dato retirado (v1.2):** las 34 Entradas de la copia son en su mayoría **pruebas locales**. Hay remisiones «REM-DEV-ORDEN», «SMOKE-REDONDEO» y «PANTALLA-P6», creadas en dev por johana@sac.com, hugo@sac.com y admin.revision@example.com; johana y hugo también son usuarios de prueba en dev. Artefactos: `medicion_fechas_lista.log` (las Entradas de prueba, con remisión y usuario) y `medicion_origen_lista.log` (34 Entradas en total: 3 con remisión de prueba por patrón y 1 de un usuario @example.com; las demás no se distinguen por esos dos criterios, y por eso el número entero se retira). Así que el número no dice nada sobre producción. Cuántas Entradas de producción tienen recolector lo mide el Coordinador por lectura. R1 sigue en pie como condición de uso.
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
- **Endpoint** `PUT /organizations/{org}/members/{user}/collector-scope` con body `{collector_id: UUID | null}`. Lleva el mismo guard que `account-assignments` (solo admin de la org, más el flag) y `null` borra el alcance. Da 422 en tres casos:
  - si el usuario destino tiene rol admin, porque el admin bypassa permisos y un alcance sobre él sería confuso;
  - **si es superusuario** (N2): `get_required_org_context` le hace un return temprano (`deps.py:119`), así que la fila nunca restringiría nada, y no se escribe un alcance que no restringe;
  - si el recolector no cumple las reglas de §3.
- **Contexto:** `get_required_org_context` lee el alcance con una consulta por índice único y lo deja en `ctx["collector_scope_id"]`. El superusuario sintetizado no tiene alcance.
- **🔴 El alcance lo decide la FILA, no el flag** (patrón #109: «el predicado es el dato»). Si alguien apaga `kg_ledger_enabled`, el alcance sigue restringiendo. **Tampoco lo salta el admin**: si una fila de alcance existe sobre un usuario admin (escrita por ORM o por un cambio de rol posterior), igual restringe. Es fail-closed (test T16c).
- `GET /roles/my-permissions` gana `collector_scope: {id, name} | null`, para que la pantalla lo sepa.

## 5. Dónde se impone: lista blanca en el backend (deny-by-default)

**Mecanismo.** `get_required_org_context` recibe el `Request`. Si el usuario tiene alcance y la función que atiende la ruta (`request.scope["endpoint"]`, identificada como `módulo.función`) no está en `SCOPED_ENDPOINTS` (`app/services/collector_scope.py`), devuelve **403** con un detalle que empieza con «Fuera de tu alcance:» y nombra al recolector.

**Por qué ahí y no ruta por ruta.** Por ese dependency pasan las 300 rutas de org, también las de adjuntos y roles, que no usan `require_permission`. Una ruta nueva que alguien agregue mañana queda **cerrada** para Ingrid hasta que se la agregue a la lista con su filtro y su test.

Que un admin le sume un permiso al rol de Ingrid **no abre** una ruta fuera de la lista: ampliar la lista es un cambio de código. El permiso sigue aplicando dentro de la lista, porque el alcance no da permisos (T14).

### 5.0 Las 27 rutas que NO pasan por `get_required_org_context` (H4)

QA 2 las midió en runtime (`~/sac-evidencia/2026-11-20/qa-2-ingrid/rutas_sin_contexto.txt`). La v1.0 decía que «ninguna sirve datos», y es falso: `GET /organizations/{id}/members` la puede pedir cualquier miembro y devuelve email, nombre, rol y cuentas asignadas de todo el personal de SAC (`organizations.py:253-290`; verificado).

| Grupo | Rutas | Con alcance |
|---|---|---|
| `/auth/*` y `/health` | 7 (`register`, `login`, `login/json`, `change-password`, `me` y los dos `/health`) | sin cambio: no son de una org |
| `/system/*` | 8 | sin cambio: son de superusuario, y el superusuario no tiene alcance |
| `GET /organizations` | 1 | sin cambio: lista las orgs del propio usuario |
| `POST /organizations` | 1 | sin cambio. ⚠️ **Preexistente:** cualquier usuario autenticado crea una org nueva. Con eso no ve nada de SAC; se reporta y queda fuera de alcance |
| `GET /organizations/{id}` | 1 | **permitida**: la pantalla lee de ahí los settings y los flags (`useOrgSettings`). Devuelve la org con sus `settings`: flags, sedes, centros Willard, `plant_third_party_id`. Son ids de configuración, sin saldos; queda declarado |
| las otras 9 de `/organizations/{id}/…` (miembros: listar, crear, editar, borrar, resetear clave, cuentas asignadas; `PATCH` de la org; `leave`) | 9 | **403 «Fuera de tu alcance»**. Lo hace un helper `deny_if_collector_scoped(db, org_id, user)`, llamado al entrar en cada una. Va también en las que ya exigen admin: por T16c, un admin con fila de alcance tampoco administra |

Son 7 + 8 + 1 + 1 + 1 + 9 = **27**. Las tres pruebas:
- **T1b:** el conjunto de rutas montadas **sin** `get_required_org_context` es igual a un **set literal** de esas 27, escrito en el test. Si mañana aparece una ruta que se salta el contexto, T1b la nombra en vez de dejarla fuera de T1 en silencio.
- **T1c:** el usuario con alcance recibe 403 **con el prefijo «Fuera de tu alcance»** (N3) en las 9 rutas de miembros, y 200 en `GET /organizations/{id}`.
- **Control positivo de T1c:** el mismo rol sin alcance recibe 200 en `GET …/members`, que es el comportamiento de hoy y no se toca.

### 5.1 Inventario: a qué llega el rol propuesto

Rol propuesto «Recolector» (12 permisos existentes, **cero permisos nuevos**): `purchases.view`, `purchases.view_prices`, `purchases.liquidate`, `third_parties.view`, `third_parties.create`, `treasury.view_statements`, `treasury.view_accounts`, `treasury.view_movements`, `treasury.create_movements`, `materials.view`, `materials.view_prices`, `tariffs.view`.

`scripts/alcance_rol.py` sobre el inventario AST da **89 rutas** a las que llegan esos permisos (`alcance_rol_ingrid.tsv`). Las **31 filas** de §5.2 están todas dentro de esas 89; la 27b, `payment-to-generic`, depende de H5. Lo medí con un `grep -F` de las 31 contra `alcance_rol_ingrid.tsv`: aparecen las 31, una vez cada una. Las **otras 58 quedan cerradas para el usuario con alcance**. La cifra exacta la fija T2b. Por ejemplo, quedan cerradas:
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
| 2 | `GET /materials` | todos los materiales, **sin** stock ni costo (§5.7) |
| 3 | `GET /materials/{id}` | lo mismo |
| 4 | `GET /material-kg-profiles` | sin filtro: orden del formato (#121) y unidad; los campos de §5.7 |
| 5 | `GET /service-tariffs/current` | **solo** `comision_green_loop` (§5.7) |
| 6 | `GET /price-lists/current` | `third_party_id` **obligatorio** y `alc`: sin él → 422, ajeno → 404. Solo `purchase_price`, sin `sale_price` (§5.7) |
| 7 | `GET /inbound-orders` | se **fuerza** `collector_id = scope`; un `collector_id` del query se ignora |
| 8 | `GET /inbound-orders/{id}` | 404 si `order.collector_id != scope` |
| 9 | `POST /inbound-orders/{id}/liquidate` | Todo se valida **antes de escribir** (D14 de #93): un rechazo no deja nada. Las reglas:<br>• 404 como en la fila 8.<br>• Todo proveedor del reparto tiene que ser `alc`. Si no, 422 **genérico**, «Hay un proveedor fuera de tu alcance»: no nombra a lo ajeno (M1), porque su selector solo ofrece lo suyo y el nombre solo le llegaría a quien arma UUIDs a mano.<br>• Toda cuenta de `supplier_payments` tiene que ser `cta` (si no, 403).<br>• Comisión (S6/D-a): el tercero es su recolector, y el monto lo calcula el servidor. Si viene otro tercero u otro `amount` → 422.<br>• Si vienen `supplier_retentions` o impuestos → 422 (S5). |
| 10 | `GET /third-parties` | se fuerza `alc` |
| 11 | `GET /third-parties/suppliers` | se fuerza `alc` |
| 12 | `GET /third-parties/similar` | se fuerza `alc` (no revela nombres de proveedores de SAC) |
| 13 | `GET /third-parties/payable-providers` | devuelve solo el recolector de su alcance (selector de la comisión, S6) |
| 14 | `GET /third-parties/{id}` | 404 si no `alc` |
| 15 | `POST /third-parties` | `collector_id` = scope, **forzado por el servidor**, con lo que venga en el payload. **H1:** `initial_balance ≠ 0` → 422, porque si no Ingrid podría inventar una CxP sin movimiento (rompe #55) y pagarla desde K1. `category_ids`: cada categoría tiene que tener `behavior_type ∈ {material_supplier, generic}` (proveedor o conductor, S2); cualquier otra (investor/«Socios», customer, liability, provision, service_provider) → 422; vacío → 422 (un tercero sin categoría no sirve en su selector). `ThirdPartyCreate` no cambia para quien no tiene alcance. |
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
| 26 | `POST /money-movements/supplier-payment` | `cta(account)` (si no, 403) y `alc(tp)` (si no, 404). El guard de tipo de tercero existente no se toca |
| 27 | `POST /money-movements/advance-payment` | igual |
| 27b | `POST /money-movements/payment-to-generic` | **Solo si Daniel elige (a) en H5.** Mismas reglas que la fila 26: es el pago o anticipo a un conductor *generic* de su alcance (S2). Si elige (b), esta fila sale; `payment_to_generic` sale también de PROPIOS (fila 28) y `generic` sale de las categorías permitidas en la fila 15 |
| 28 | `POST /money-movements/{id}/annul` | **H2:** cuatro condiciones, todas:<br>• `movement_type ∈ PROPIOS = {payment_to_supplier, advance_payment, payment_to_generic}`;<br>• `alc(tp)`;<br>• `cta(account)`;<br>• `transfer_pair_id IS NULL`.<br>Si falta alguna → 404. Así no anula un `transfer_in` de K1 que hizo Johana (`annul` anula también el par en K2, `money_movement.py:1126-1133`), ni un pago de Johana a B desde K1, ni una causación |
| 29 | `GET /money-movements/{id}/evidence` | el predicado de la fila 25 (solo lectura) |
| 30 | `POST /money-movements/{id}/evidence` | **H2:** el predicado de la fila 28. Así no reemplaza la evidencia de un movimiento de Johana |

Son 31 filas (30 más la 27b, que depende de H5). Las filas 2 y 3, y las 29 y 30, pueden reducirse si la pantalla no las usa; se cierran en la construcción y **la lista final la fija T2b** (doble entrada, §12).

### 5.7 Lista blanca de CAMPOS (H3)

Green Loop es otra empresa: que una ruta esté permitida no quiere decir que todos sus campos lo estén. Con alcance:

| Ruta | Campo de SAC | Con alcance | Por qué |
|---|---|---|---|
| `GET /materials`, `/materials/{id}` | `current_stock`, `current_stock_liquidated`, `current_stock_transit`, `current_average_cost` (`schemas/material.py:83-86`) | **`null`** | Son el inventario y el costo de SAC. Los cuatro campos pasan a `Optional[float]` en `MaterialResponse`. Sin alcance llegan con su número de siempre: el JSON no cambia, porque un `float` no nulo se serializa igual. `/materials` no es captura del golden (se verifica con `grep` sobre `CAPTURES`) |
| `GET /price-lists/current` | `sale_price` | **`null`**, y `third_party_id` obligatorio y `alc` (fila 6) | Son los precios de venta de SAC. Sin `third_party_id` y con #98 D10 (org sin listas activas) devolvería la lista general entera |
| `GET /service-tariffs/current` | las demás tarifas (maquila Willard, abono a planta, flete, crisol, maquila intersede) | **fuera**; solo `comision_green_loop` | Son los precios de SAC con Willard y con su planta |
| `GET /material-kg-profiles` | `willard_world`, `compra_regular`, `lead_product`, `form_order` | se quedan | Es la clasificación de cada material, no tiene montos. La pantalla los usa para el orden del formato (#121). Queda declarado |
| `GET /inbound-orders/{id}` | `discrepancy_adjustments` (valorado al precio de referencia), `liquidated_by_name` y demás nombres de usuarios | se quedan | Es su Entrada; el descuadre lo valoró ella misma al liquidar (#93) |
| `GET /money-movements/third-party/{id}` | nombre de una cuenta de SAC en un pago viejo | se queda (D-E1) | El saldo corrido tiene que cuadrar con el vivo (#55) |
| `GET /third-parties*` | `current_balance` de sus terceros | se queda | Es el saldo de lo suyo |

**Test:** T19, «ausencia de lo de SAC», con usuario con alcance y su control sin alcance en el mismo test:
- en `/materials`, los cuatro campos son `null` en **todas** las filas; el control ve números distintos de 0 en al menos una fila (contra la vacuidad: el fixture siembra stock por API);
- en `/price-lists/current`, no hay ningún `sale_price` distinto de `null`; el control ve al menos uno distinto de 0;
- en `/service-tariffs/current`, el conjunto de `tariff_code` es exactamente `{comision_green_loop}`; el control ve ≥ 2.

### 5.3 Códigos: una regla para cada uno

- **404**: el objeto existe, pero está fuera de su alcance. Aplica a terceros, Entradas, compras, movimientos, adjuntos y al `third_party_id` de precios. No revela que existe.
- **403 «Fuera de tu alcance: …»**: la ruta no está en la lista blanca.
- **403 «No tienes acceso a esta cuenta»**: la cuenta no está asignada, en lectura o en escritura. Es el mensaje que ya existe; se conserva para no partir el código ni cambiarles el mensaje a los usuarios de Costa.
- **422**: un payload que mezcla lo suyo con lo ajeno, por ejemplo un proveedor ajeno en el reparto, la comisión a otro recolector, saldo inicial o una categoría no permitida. El mensaje es **genérico y no nombra lo ajeno** (M1): en su pantalla lo ajeno no aparece, así que el nombre solo le llegaría a quien arma el payload a mano.

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

**C2 cambia lo que pueden hacer hoy los 2 usuarios de Costa:** si hoy registran un pago desde una cuenta no asignada, mañana recibirían 403.

**Decidido por Daniel (20-nov, me lo pasó el Coordinador; decisión 1): CICLO PROPIO, justo después de este. Este ciclo no le cambia nada a Costa.** Para los usuarios sin alcance, `_get_allowed_accounts` y los cuatro caminos C1–C4 quedan como hoy; T18 lo afirma. El helper y los cuatro puntos quedan escritos aquí como insumo de ese ciclo.

## 7. El balance: Green Loop por aparte

- **Balance Detallado, vivo y as-of.** En cada sección de terceros (CxP proveedores, anticipos a proveedores, CxC, etc.), los terceros con `collector_id` van en un grupo «Recolector: <nombre>», que manda sobre el grupo de categoría. Usa el esquema existente `BalanceDetailedGroup` (#38): **cero claves nuevas**.
- **Costo:** una consulta `SELECT id, collector_id WHERE organization_id=? AND collector_id IS NOT NULL`, vacía en las otras 6 orgs, así que el agrupado queda idéntico por construcción.
- **Balance General: no cambia.** Decidido por Daniel (20-nov, vía el Coordinador; decisión 2): solo el Detallado agrupa, sin claves nuevas en el General.
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

**Decidido por Daniel (20-nov, vía el Coordinador; decisión 4):** a Johana se le proponen los **124 con sufijo** `(GREENLOOP)`/`(GREENLOP)`, y ella confirma o corrige. Mientras tanto, la marca inicial es **esa lista explícita**, con los nombres exactos escritos en un archivo, nunca un regex. La lista sale de un `SELECT` sobre la base que se vaya a marcar, y el dry-run la imprime completa. Contra producción la corre solo el Coordinador, con el OK de Daniel (escritura en prod).

## 10. Migración: una sola línea

`e7f9a1b3c5d8_recolector_alcance.py`, `down_revision = d6e8f0a2b4c7` (cabeza actual, `alembic heads`). El id está libre (grep vacío). Cambios:
- `third_parties.collector_id` UUID nullable, FK `third_parties.id` con nombre por defecto (`create_foreign_key(None, …)`, lección de #111), **`ondelete="RESTRICT"` explícito** (N1), e índice `ix_third_parties_collector_id`;
- tabla `user_collector_scopes` con `UNIQUE(organization_id, user_id)` e índice por `organization_id` (lo declara el mixin, lección de #100). Sus tres FKs llevan **`ondelete="RESTRICT"` explícito** (N1). **No se calca el CASCADE de `user_account_assignments`** (`models/user.py:113-119`): con CASCADE, borrar al recolector borra la fila de alcance, y entonces Ingrid **ve todo** (fail-open). Hoy el borrado de un tercero es lógico (`third_parties.py:473`) y no se llega a eso por API; con RESTRICT queda imposible por construcción. El parity check compara el `ondelete` entre modelo y migración.

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

**Fixture:** org con flag; recolectores **GL** y **X** (service_provider); terceros **A** y **A2** (GL), **B** (sin marca), **C** (de X), **D** (conductor generic de GL) y **E** (generic sin marca); Entradas **E_GL**, **E_none** y **E_X**; cuentas **K1**, asignada a Ingrid, y **K2**.

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
| 9 liquidar | 200 con A; si D-a = servidor, la comisión queda en tarifa × base aunque no se mande `amount` | 422 con B, 422 con C (los dos **sin el nombre**, M1), 403 con K2, 422 comisión a X, 422 `amount` distinto del calculado (si D-a = servidor), 422 con retención/IVA; **las 7 tablas sin cambios** | 200 con B; la comisión toma el `amount` digitado |
| 10–13 listados de terceros | solo GL (+ D en 10) | sin B ni C | ven B y C |
| 14 tercero detalle | 200 A | 404 B | 200 B |
| 15 crear tercero | nace con GL aunque el payload diga X; con categoría material_supplier → 201 | `initial_balance` ≠ 0 → 422; categoría investor, customer o liability → 422; sin categoría → 422. **Ninguna fila escrita** | nace sin marca, con su `initial_balance` y cualquier categoría (comportamiento de hoy) |
| 16–17 compras | lista y detalle de A, **también la que nació en E_none** (S8 / D-b tal como está; si Daniel alinea por Entrada, esta celda pasa a 404) | 404 compra de B | ven la de B |
| 18–19 adjuntos | lista y descarga de la compra de A | 404 compra de B y venta | 200 |
| 20 estado de cuenta | A: **corrido == vivo** con un pago desde K2 adentro | 404 B | B 200 |
| 21–23 caja | solo K1; sin asignaciones → **ninguna** | K2 403 | sin asignaciones ve K1 y K2 (comportamiento actual, regresión) |
| 24–25 movimientos | ve K1 y la causación de A | no ve la causación de B (cuenta NULL); detalle de K2 404 | ve todo |
| 26–27 pagar/anticipar | K1→A 201 | K2 403; →B 404; **→D 400 (guard de tipo existente, intacto)** | K2→B 201 |
| 27b pago a generic (si H5 = a) | K1→D 201 | K2 403; →E (generic sin marca) 404 | K2→E 201 |
| 28 anular | su pago K1→A | transferencia K1↔K2 de Johana: **404, y el par en K2 sigue `confirmed`**; pago de Johana K1→B 404; causación de A (cuenta NULL) 404; movimiento de K2 404 | anula todo lo que hoy anula |
| 29–30 evidencia | ver y subir en su pago K1→A | subir en el pago de Johana K1→B 404 (su evidencia no cambia); ver la de un movimiento de K2 404 | 200 |
| §5.0 miembros | `GET /organizations/{id}` 200 (con `settings`) | `GET …/members` 403 y las otras 8 de miembros 403 | `GET …/members` 200 |
| §5.7 campos | ver T19 | ver T19 | ver T19 |

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

- **T1, familia (deny-by-default):** parametrizada sobre las **rutas montadas** (`app.routes`, no una lista a mano) que dependen de `get_required_org_context` y no están en la lista blanca. `ingrid_todo` → 403 **y el detalle empieza con «Fuera de tu alcance»** (N3: `require_org_flag` y los permisos también devuelven 403, y sin el prefijo un 403 que viene por otra puerta pasaría). **Conteo:** la cantidad de casos == rutas con contexto de org − largo de la lista, comparado **antes** del parametrizado (lección de #108). **Control positivo:** en las mismas rutas, `todo_libre` **no** recibe el 403 de alcance; sin eso, un 403 por cualquier otra puerta pasaría el test.
- **T1b y T1c:** las rutas sin contexto de org (§5.0).
- **T2** (M3): cada entrada de `SCOPED_ENDPOINTS` se identifica como `módulo.función` y resuelve a **≥ 1 ruta montada**. Se afirma el conjunto exacto de pares (método, path) de cada entrada, para que una función montada en dos paths no abra el segundo sin que se vea. Nada queda muerto.
- **T19:** la ausencia de lo de SAC (§5.7).
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
  - **T16d** (N2): poner alcance a un superusuario → 422, y no se escribe ninguna fila.
- **T20** (N1): borrar físicamente por ORM al recolector cuando tiene un alcance o terceros marcados → `IntegrityError`. La fila de alcance y la marca siguen ahí.
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
| P22 | el alta de tercero con alcance acepta `initial_balance` | fila 15 (422 y ninguna fila escrita) |
| P23 | el alta de tercero con alcance acepta cualquier categoría | fila 15 (investor y customer) |
| P24 | `annul` sin la condición `transfer_pair_id IS NULL` (plantado **solo** en annul) | fila 28: transferencia de Johana, con el par en K2 todavía `confirmed`. **No debe caer** la fila 30: si cae, el predicado está compartido y P25 no se distingue de P24 |
| P25 | subir evidencia sin el filtro de PROPIOS (plantado **solo** en evidencia) | fila 30, el pago de Johana K1→B. **No debe caer** la fila 28 |
| P26 | `/materials` con alcance devuelve stock y costo | T19, materiales |
| P27 | `/price-lists/current` con alcance acepta la ausencia de `third_party_id`, o devuelve `sale_price` | T19, precios, y fila 6 |
| P28 | `/service-tariffs/current` sin el filtro | T19, tarifas |
| P29 | `GET …/members` sin el `deny_if_collector_scoped` | T1c |
| P30 | una ruta nueva sin contexto de org (se monta una de prueba en el plantado) | T1b |
| P31 | con alcance, se respeta el `amount` digitado de la comisión (D-a = servidor) | fila 9, comisión |
| P32 | `PUT …/collector-scope` acepta a un superusuario | T16d |
| P33 | `ondelete="CASCADE"` en `user_collector_scopes.collector_id` (en modelo y migración) | T20 |

**Dirección peligrosa a buscar celda por celda antes de plantar:** un test que debía caer y no cae. El candidato más probable es P7 si los cuatro listados comparten helper. Por eso el test se parametriza por ruta y el defecto se planta en una sola.

## 14. Riesgos y fuera de alcance

- **R1 — CONDICIÓN DE USO, no solo riesgo** (Coordinador, revisión de producto): sin recolector en la Entrada, Ingrid no ve nada. Cuántas de producción lo tienen hoy lo mide el Coordinador; el «0 de 34» de la v1.1 era de Entradas de prueba (§2.7). **Báscula tiene que poner el recolector en cada Entrada de Green Loop**, y **Daniel se lo comunica a Johana** antes de que Ingrid entre. Johana lo puede corregir mientras la Entrada no esté liquidada (#83/#93). El aviso «¿Recolector?» en la captura queda fuera de este ciclo y es el **primer candidato a v2**.
- **R2 — una consulta más por request** para todo miembro de las 7 orgs (índice único `(org, user)`). Se mide en la construcción con `EXPLAIN ANALYZE` sobre la copia.
- **R3 — el selector de Johana no cambia (S1).** Si en la pantalla Daniel quiere que también a ella, en una Entrada con recolector GL, se le ofrezcan primero los de GL, es un orden visual y va como sugerencia.
- **Fuera de alcance:**
  - gastos de la caja de Green Loop (S7);
  - líneas propias en el Balance General (decisión 2);
  - el aviso de recolector en la captura;
  - un alcance de Ingrid sobre las Willard (Q-02: Green Loop también recolecta postconsumo; con S4 ella no confirma Willard, pero las ve en el listado si tienen su recolector, y su detalle muestra kg).

## 15. Decisiones de Daniel

Las pide el Coordinador; me las pasa él. Se anotan con su fuente: un mensaje de QA no es una decisión de Daniel.

**Decididas (20-nov, vía el Coordinador):**

1. **El hueco de cuentas de §6 para las orgs sin alcance (Costa):** CICLO PROPIO, justo después. Este ciclo no le cambia nada a Costa (T18).
2. **Balance General:** solo el Detallado agrupa a Green Loop, sin claves nuevas en el General (§7).
4. **Lista de la marca inicial:** a Johana se le proponen los 124 con sufijo y ella confirma o corrige. Mientras tanto, la lista es esa, explícita y nunca un regex (§9).

3. **Supuestos S1–S8 y las cuatro decisiones abiertas: Daniel aceptó todas las recomendadas** (20-nov, vía el Coordinador):
   - S1–S8 tal como están; los gastos desde la caja de Ingrid quedan fuera (S7);
   - **D-E2** (§5.6): (a), se declara la fuga;
   - **H5**: (a), `payment-to-generic` entra al alcance con las reglas de la fila 27b;
   - **D-a**: (a), el servidor fija el monto de la comisión;
   - **D-b**: (a), las compras son de Ingrid por la marca del proveedor.

   El cuerpo del plan ya se leía con estas opciones desde la v1.1, así que ninguna fila cambia. Las marcas «pendiente de Daniel» y «solo si Daniel elige (a)» que quedan en S2, S6, la fila 27b y el cuadrante son de la v1.1: hoy se leen como decididas en (a).

## 16. Runbook de deploy

Revisión de producto del Coordinador. Todo lo hace el Coordinador con el OK de Daniel, porque son escrituras en producción.

1. **Migración** `e7f9a1b3c5d8`, vía `/deploy` (aditiva: columna NULL y tabla vacía).
2. **Marca inicial:** primero `scripts/marcar_recolector.py --collector "Green Loop" --lista <archivo> --dry-run` contra producción; se revisa la lista impresa y se compara con la que confirmó Johana. Después, la corrida real. Antes del deploy se verifica en producción que existe el tercero «Green Loop» (service_provider) y que su nombre coincide.
3. **El usuario de Ingrid:**
   - se crea por la vía de superusuario;
   - **su clave se fija solo con el reseteo de #85** (`POST /system/users/{id}/reset-password`), con la clave que defina Daniel, **NUNCA con la clave fija** que dejan las altas de miembros (la deuda de #85);
   - su rol es «Recolector», con los 12 permisos de §5.1, más `payment-to-generic` si H5 = (a), que usa el mismo `treasury.create_movements`. Ningún permiso es nuevo.
4. **Su caja:** `PUT /organizations/{org}/members/{ingrid}/account-assignments` con la cuenta real de la caja de Green Loop (K1 de producción). **Antes** de poner el alcance, para que en ningún momento vea cuentas que no son suyas. Igual, con alcance y sin asignaciones vería cero (fila 21).
5. **Su alcance:** `PUT /organizations/{org}/members/{ingrid}/collector-scope` con el id del tercero «Green Loop».
6. **Verificación**, con lecturas en producción y su usuario:
   - `my-permissions` trae `collector_scope`;
   - `GET /inbound-orders` da solo Entradas con recolector Green Loop (al principio puede ser 0, por R1);
   - `GET /third-parties/suppliers` da solo los marcados;
   - `GET /money-accounts` da solo su caja;
   - `GET /organizations/{org}/members` da 403.
7. **Condición de uso (R1):** Daniel le comunica a Johana que báscula tiene que poner el recolector en las Entradas de Green Loop.
