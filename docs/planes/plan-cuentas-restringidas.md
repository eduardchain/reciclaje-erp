# Plan — Cuentas restringidas por usuario: que la asignación de cuentas también limite lo que se ESCRIBE (v1.0)

**Base:** develop `dda8e38`. Del árbol de `d3c6919` solo cambian docs.
**Nivel:** lógica. Toca código compartido: el embudo de escritura de tesorería, el estado de cuenta, el listado de cuentas y el dashboard de tesorería. Lo ven las 7 orgs.
**Pedido:** decisión 1 de Daniel en el plan de Ingrid (§6): ciclo propio, inmediatamente después de Ingrid.
**Migraciones:** cero. **Permisos nuevos:** cero.

Las decisiones que espera Daniel están en §6. El plan se puede revisar sin ellas, y cada una tiene recomendación.

## 1. El problema, medido

Hoy un usuario puede tener cuentas asignadas (`user_account_assignments`, pantalla Usuarios → «Cuentas Visibles»). El mecanismo es un solo predicado: `accounts_for` en `services/collector_scope.py`, al que delegan las dos copias de `_get_allowed_accounts`.
- Devuelve `None` («todas») para el rol admin de sistema y para un usuario sin asignaciones.
- Para los demás, devuelve las cuentas asignadas.

**Solo lo usan 6 rutas, y todas son GET.** Ninguna escritura mira la asignación. El inventario completo está en `~/sac-evidencia/2026-11-20/coder-2-recolector-alcance/cuentas_insumo.md` (sha `5a4f7a81…0f66`). Sus números (log `cuentas_inventario_87c799f_v2.log`, `43c8fbc0…af53`):

| Clase | Rutas | Miran la asignación | La alcanza el liquidador de Costa | La alcanza el analista de SAC |
|---|---|---|---|---|
| Escritura con cuenta en el cuerpo | 34 | 0 | 28 (29 con `inbound-orders/liquidate`, que es de SAC) | 26 |
| Escritura indirecta (revierte un movimiento con cuenta) | 6 | 0 | 3 | 4 |
| Lectura | 26 | 6 | 14 | 8 |
| Lectura agregada (reportes) | 3 | 0 | 0 | 0 |

**Quién está restringido hoy en producción** (leído por el Coordinador solo con GET, `gate-prod/cuentas_asignadas_costa_prod.log`):
- **Costa:** un admin con 5 de 7 cuentas y un liquidador con 1.
- **SAC:** dos analistas: `cde75cc0` con «Caja Circunvalar», y `d7145ede` (Yurani) con «Caja Circunvalar» y «Caja Juan Mina». Su rol es custom, con 16 permisos `treasury.*` (`gate-prod/rol_analista_sac_prod.log`).
- **Meta:** ninguno.

**Tres mediciones nuevas para este plan**, sobre la copia de dev `reciclaje_coder_2`, solo lectura. Es una réplica sin fecha, y el último movimiento de Costa es del 2026-09-17. Evidencia en `~/sac-evidencia/2026-11-20/coder-2-cuentas-restringidas/`:

1. **El admin restringido opera cuentas que no tiene asignadas, y mucho** (`uso_cuentas_ajenas.log`, `f8576709…accb`):

   | Usuario | Rol | Cuentas asignadas | Movimientos creados | En una cuenta no asignada | Anulados en una cuenta no asignada |
   |---|---|---|---|---|---|
   | `5380ca28` | admin | 5 | 6.585 | **338** | **40** |
   | `ddf32268` | liquidador | 1 | 4.707 | **0** | **0** |

   Si la asignación se volviera obligatoria también para el admin, su operación diaria se rompería. Para el liquidador, la restricción de escritura no cambia nada de lo que hizo hasta esa fecha.
2. **El estado de cuenta por tercero ya está roto para el usuario restringido** (`statement_escondido.log`, `fad1364e…89e0`; script `1abcdfa1…96c2`, con la predicción escrita antes y cumplida):
   - `GET /money-movements/third-party/{id}` filtra los movimientos por cuenta (`money_movements.py:969-978`).
   - El saldo corrido arranca en `initial_balance` y suma solo lo visible (l.1680-1697). Así que un movimiento escondido que movió el saldo del tercero deja el estado de cuenta sin cerrar contra el saldo vivo (#55).
   - Para el liquidador de Costa: **2.172 movimientos escondidos y 256 terceros con un efecto escondido distinto de 0**. El mayor es de $10.213.667.900.
   - **Hoy está latente en Costa:** el liquidador no tiene `treasury.view_statements`.
   - **En SAC está vivo:** el analista sí tiene ese permiso. Cuántos terceros de SAC no cierran para cada analista no lo puedo medir desde aquí; ver §8, G-prod 2.
3. **El estado de cuenta no muestra la cuenta.** Los eventos de movimiento (`_evt`, l.981-988) traen id, fecha, tipo, descripción, monto y estado, pero ni la cuenta ni su nombre. Esconderlos no protege ningún dato de la cuenta: solo rompe el saldo.

## 2. Qué se construye

### 2.1 Escrituras: un solo punto, en el flush

**Mecanismo (D-M):** un listener `before_flush` de SQLAlchemy, en un módulo nuevo `app/services/account_access.py`.
- En la transacción de un usuario restringido, toda fila de `MoneyAccount` o de `MoneyMovement` que se inserta, modifica o borra tiene que ser de una cuenta permitida. Si no, la transacción se corta con **403 «No tienes acceso a la cuenta «X»»**.
- Un movimiento con `account_id NULL` (causaciones, cruces entre terceros, ajustes) pasa siempre: la restricción es sobre cuentas de dinero.
- Un `MoneyAccount` se mira solo si cambió algún atributo (historia de atributos con cambios netos), así que leerlo o asignarle el mismo valor no cuenta.

**Quién es el usuario.** `get_required_org_context` (deps.py) deja el contexto en `db.info["account_actor"]`.
- La sesión es una por request, en producción (`get_db`) y en tests (`override_get_db`, conftest l.153), así que el contexto no se cruza entre requests.
- Sin contexto (scripts, seeds, tests que llaman al servicio directo) el listener no hace nada. Es lo mismo que hoy para esos caminos.

**El conjunto permitido** sale del predicado de siempre, `accounts_for(db, ctx)`, sin una copia nueva (#111):
- admin o superusuario: `None` → el listener no mira nada (decisión D1);
- sin asignaciones: `None`;
- con alcance de recolector (Ingrid): las asignadas, y vacío = ninguna. Así ya es hoy.

Se calcula una sola vez, la primera vez que un flush toca una fila de dinero, y se guarda en `db.info`. Un request que no toca dinero no hace ninguna consulta más. Uno de un admin tampoco, porque `accounts_for` corta en `is_admin` antes de leer.

**Por qué en el flush y no llamada por llamada.** La alternativa era llamar a un helper en cada camino:
- las 50 llamadas a `_create_movement` se cubren con una sola, porque es el único constructor de `MoneyMovement` (26 de esas llamadas llevan cuenta, y todas pasan `user_id`; medido con AST);
- pero las reversas no pasan por ahí. Escriben `current_balance` directo en 7 funciones: `money_movement._reverse_effects` (llamada desde `annul` y desde traslados, crisol y Salidas), `financial_obligation._apply_effects(reverse=True)`, y en `fixed_asset` `cancel`, `annul_sale` y `annul_revaluation`; además `purchase.cancel` y `sale.cancel` con `annul_linked_payments`;
- y además están la evidencia, la clasificación y la edición de cuentas.

Eso son unas 12 llamadas para mantener, y una guarda AST que reconoce las cuentas por el nombre de la variable (`account`, `acc`, `source`, `destination`): una guarda con agujero (#91/#92). El flush, en cambio, ve toda escritura, también la de un camino que se escriba mañana.

El precedente de un listener sobre `Session` es `advisory_locks.py` (#106).

**Riesgos del mecanismo, y cómo se cubren:**
- **El 403 sale en el flush, que puede ser un autoflush dentro de una consulta.** La transacción se descarta igual (`get_db` cierra sin commit). Para que el error salga temprano y con el mensaje del recurso, las rutas por id (§2.2, C1) chequean ANTES con el mismo predicado: 404 si la cuenta del movimiento no es visible. El listener queda como red.
- **Un `except` que se trague el 403.** En `services/` hay un solo `except Exception`, en `user.py:127`, y no toca dinero. El barrido T1 da 403 y no 500 en cada ruta.
- **Archivos en disco antes del flush** (evidencia). El chequeo de visibilidad de C1 corre antes de escribir el archivo, así que no queda un huérfano. Lo prueba T8.

### 2.2 Lecturas

- **C1 — Movimiento por id, por número y su evidencia** (GET, POST y DELETE de evidencia, `annul` y `classification`): **404** si el movimiento tiene una cuenta no visible para el usuario.
  - Hoy `_require_movement_visible` y `_require_movement_owned` (`money_movements.py:164-172`) solo aplican con alcance.
  - Con alcance no cambia nada. Sin alcance, «visible» es: `account_id` NULL, o una cuenta en `accounts_for`.
- **C3 — Listado y resumen** (`GET /money-movements` y `/summary`): **sin cambio**. Siguen pasando las cuenta-NULL (decisión D3).
- **C4 — Estado de cuenta por tercero:** se quita el filtro por cuenta para el usuario sin alcance (decisión D4). Con alcance sigue D-E1 de Ingrid, sin tocar.
- **Dashboard de tesorería** (`GET /reports/treasury-dashboard`, `reports.py:4172`): hoy lista todas las cuentas activas de la org, con su saldo, y los 10 últimos movimientos.
  - Para el usuario restringido se filtran las cuentas, sus totales, el MTD y los movimientos recientes, con el mismo predicado del listado: cuenta permitida o NULL.
  - CxC, CxP y provisiones son de terceros, no de cuentas: no cambian.
  - El endpoint le pasa `ctx` al servicio, con un parámetro nuevo opcional `allowed_account_ids=None`. Ningún otro llamador lo pasa, así que para todos los demás es byte a byte igual.
- **`GET /money-accounts`:** hoy filtra DESPUÉS de paginar (`money_accounts.py:45-62`), así que `total` y la página mienten si la org tiene más cuentas que `limit`. El filtro pasa a la consulta. Hoy está latente: Costa tiene 7 cuentas, SAC 9, y el front pide 500.
- **Sin cambio (decisión D5):**
  - las 10 lecturas de compras y ventas que exponen `payment_account_name` del pago inmediato;
  - el estado de una obligación;
  - las 3 del gasto programado;
  - los 3 reportes agregados, que piden `reports.*` y ningún restringido de hoy alcanza.

**Un solo predicado para las lecturas:** `account_visible(db, ctx, account_id) -> bool` y `account_filter_clause(ctx_allowed) -> ColumnElement`, en `account_access.py`, construidos sobre `accounts_for`.
- `collector_scope.movement_visible` pasa a delegar en ellos para la rama de cuenta. Su rama de cuenta-NULL con alcance (`alc(tp)`) sigue en `collector_scope`.
- `accounts_for` se muda a `account_access.py` (su nombre ya no es de alcance) y `collector_scope` lo importa de ahí. Hoy tiene 3 llamadores: `money_accounts.py:31`, `money_movements.py:150` y el propio `collector_scope`.

### 2.3 Pantalla (Usuarios)

El diálogo «Configurar Usuario» rotula la sección «Cuentas Visibles», con el texto «Dejar vacío para ver todas las cuentas».
- Pasa a **«Cuentas»**, con el texto «Solo podrá ver y mover estas cuentas. Vacío: todas».
- Si el rol elegido en el mismo diálogo es admin: un aviso en ámbar, «Con rol Administrador, las cuentas asignadas no restringen nada» (decisión D1).

Nivel chico dentro del ciclo: lint, `tsc`, `build` y capturas a 1440 y 390.

## 3. Lo que NO cambia (no-regresión, dos argumentos, #98)

**Datos: qué filas devuelve o escribe cada camino.**
- Sin asignaciones, `accounts_for` da `None`. Es el caso de Meta, Pacífico y todo miembro sin cuentas.
- Con rol admin también da `None`, y el superusuario tiene contexto sintético con `is_admin`.
- Con `None`:
  - el listener no mira nada;
  - C1 no corta;
  - el dashboard no filtra;
  - `GET /money-accounts` hace la misma consulta;
  - el estado de cuenta no filtraba antes y no filtra ahora.

  Byte a byte.
- Con alcance (Ingrid), la regla de cuentas ya era fail-closed y no cambia. La sostienen los tests de Ingrid, que van en las dirigidas.

**Llamadores: qué empieza a enviar o ejecutar el código compartido en una org sin la función.**
- El listener se registra para TODA sesión, pero con `account_actor` ausente o con `None` vuelve en la primera línea. No consulta nada.
- `get_required_org_context` hace UNA asignación de diccionario más y ninguna consulta más.
- El dashboard recibe `allowed_account_ids=None` de su único llamador.
- Ninguna pantalla compartida manda un parámetro nuevo.

**Lo que SÍ cambia, y para quién.**

| Usuario | Escrituras con cuenta no asignada | Estado de cuenta por tercero | Dashboard de tesorería | Movimiento por id de otra cuenta |
|---|---|---|---|---|
| Liquidador de Costa | 403 (medido: 0 casos hasta el 17-sep) | sin cambio para él: no tiene el permiso | no tiene el permiso | 404 |
| Analistas de SAC | 403 (**no medido**: ver G-prod 1) | pasan a ver TODOS los eventos del tercero, y su saldo cierra | solo sus cajas | 404 |
| Admin de Costa con 5 cuentas | sin cambio (D1) | sin cambio | sin cambio | sin cambio |

## 4. Tests (archivo nuevo `tests/test_cuentas_restringidas.py`)

Fixture: una org con 3 cuentas (K1, K2, K3) y 4 usuarios:
- un liquidador con K1 asignada;
- un usuario custom con los 16 permisos del analista de SAC y K1, K2;
- un admin con K1 asignada;
- un usuario sin asignaciones.

Los roles son custom con sus permisos: el admin bypassa y no prueba nada (#29). En cada test de permiso va un **control positivo** con la cuenta propia en 2xx (lección de #111).

| # | Qué afirma |
|---|---|
| **T1** | **Barrido de escrituras**, parametrizado sobre la lista del inventario v2 (las 34 con cuenta en el cuerpo, `batch-expenses` incluido). Con K3: **403**, el detalle nombra la cuenta, y nada queda escrito (saldo de K3, saldo del tercero y conteo de `money_movements`, antes y después). Con K1: 2xx. La lista es explícita y lleva un comentario de por qué está completa (#108). |
| **T2** | **Las 6 indirectas.** Cancelar una compra y una venta con `annul_linked_payments=True` cuyo pago es de K3; anular un movimiento de obligación de K3; cancelar un activo, anular su venta y anular una revalorización pagadas desde K3. Todo da **403** y no cambia nada. Con K1: 2xx. |
| **T3** | **Admin con asignación (D1):** escribe en K3 → 2xx. Control: el liquidador, con la misma petición, da 403. |
| **T4** | **Sin asignaciones** escribe en K3 → 2xx (no-regresión). |
| **T5** | **Estado de cuenta (D4):** un tercero con una compra liquidada y un pago desde K3. Para el liquidador con K1, el último `balance_after` == `current_balance` y el pago aparece. **Se escribe primero y se corre contra la base:** tiene que FALLAR ahí (hoy esconde el pago). |
| **T6** | **Dashboard:** el analista con K1 y K2 ve solo K1 y K2, con sus totales, y los recientes solo de K1, K2 o NULL. Control: el admin ve las 3. |
| **T7** | **`GET /money-accounts` con 3 cuentas, `limit=1` y una sola cuenta asignada en la posición 3:** `total == 1` y la página la trae. Hoy da `total` 0 y una página vacía: pagina primero y filtra después (`money_accounts.py:45-62`). |
| **T8** | **C1:** GET por id y por número, evidencia (GET, POST, DELETE), `annul` y `classification` sobre un movimiento de K3 → 404. El POST de evidencia no deja archivo en disco (directorio de uploads de la org, antes y después). Control con K1. |
| **T9** | **Traslado entre cuentas (D2):** K1→K3 y K3→K1 dan 403; K1→K2 con el analista da 201. |
| **T10** | **Movimientos con cuenta NULL** (`expense-accrual`, `tp-transfer`, `tp-adjustment-*`): el liquidador los crea y los anula (D3). |
| **T11** | **Sin contexto:** el servicio llamado directo con `db_session`, sin request, escribe en K3. Fija que el listener no actúa sin contexto, para que nadie lo vuelva fail-closed sin decidirlo (rompería scripts y seeds). |
| **T12** | **Con alcance (Ingrid), el listener coincide con las reglas existentes:** una escritura en una cuenta no asignada da 403 aunque el endpoint estuviera en la lista blanca. Se monta parcheando el chequeo explícito, para ver que la red sola también corta. |
| **T13** | **El listener está registrado y el contexto lo carga** (guarda del mecanismo): sin `account_actor` en `db.info`, T1 no corta. Se afirma leyendo `db.info` en un endpoint de prueba. |

**Dirigidas** (regla del 19-nov):
- el set sale de un `grep` sobre la superficie tocada, escrito en el log con el comando: `accounts_for|_get_allowed_accounts|movement_visible|treasury-dashboard|get_treasury_dashboard|money-accounts|third-party/` en `tests/`;
- más los tests de tesorería, activos, obligaciones, compras y ventas (los dueños de las 40 escrituras);
- más `test_reloj_de_negocio.py`, `test_advisory_locks.py` y `test_crucible_charges.py`.

La predicción del conteo se escribe antes.

## 5. Matriz de plantado

Se commitea ANTES de plantar, con la predicción por fila. Un defecto en una vía compartida se predice como «al menos estos» (#105).

| P | Defecto plantado | Debe caer |
|---|---|---|
| P1 | El listener no se registra | T1, T2, T9, T12, T13 |
| P2 | `get_required_org_context` no deja `account_actor` | T1, T2, T9, T13 |
| P3 | El listener mira solo inserts, no updates ni deletes | T2 (las reversas son updates), T8 si cae al listener |
| P4 | El listener mira `MoneyMovement` pero no `MoneyAccount` | T2 (`fixed_asset` escribe `current_balance` directo) |
| P5 | El listener no corta en admin (D1) | T3 |
| P6 | El listener deja pasar si alguna de las cuentas del flush es permitida (en vez de todas) | T9 |
| P7 | El estado de cuenta conserva el filtro por cuenta | T5 |
| P8 | El dashboard no filtra | T6 |
| P9 | `GET /money-accounts` filtra después de paginar | T7 |
| P10 | C1 solo con alcance (como hoy) | T8 |
| P11 | El listener corta también las cuenta-NULL | T10 |
| P12 | El listener actúa sin contexto (fail-closed) | T11 |

**Dirección peligrosa:** un test que debía caer y no cae. Si aparece, se agrega el test que faltaba antes de seguir (como P24 y P33 en Ingrid).

## 6. Decisiones para Daniel (cada una con recomendación)

**D1 — ¿La asignación de cuentas restringe a un admin?**
- **Recomiendo que no, y que la pantalla lo diga.**
  - El admin de Costa con 5 cuentas creó 338 movimientos y anuló 40 en cuentas que no tiene asignadas: restringirlo rompe su operación.
  - Además, un admin puede cambiar sus propias asignaciones (`PUT …/account-assignments` solo exige `is_admin` y no impide que se asigne a sí mismo), así que la restricción sería decorativa.
- **La otra opción:** que sí restrinja. Exigiría primero reasignarle las 7 cuentas a ese admin, y cerrar la auto-asignación.

**D2 — Traslado entre dos cuentas: ¿tienen que estar asignadas las dos, o solo la de origen?**
- **Recomiendo las dos.** Es la regla uniforme del listener, sin excepciones, y el liquidador tiene 0 movimientos en cuentas no asignadas.
- **Con «solo origen»,** quien tiene la caja podría consignar al banco sin tener el banco asignado. Costaría una excepción explícita en `create_transfer`, y T9 la fijaría.

**D3 — Movimientos sin cuenta** (causaciones, cruces entre terceros, ajustes de terceros): ¿el restringido los ve y los opera?
- **Recomiendo que sí, como hoy.** No son de ninguna cuenta: la restricción es de cuentas de dinero.
- El plan de Ingrid (§6, C3) proponía ocultarlas. Para el usuario sin alcance, eso le escondería operaciones de terceros que ya ve por otros lados (compras, ventas, terceros).

**D4 — Estado de cuenta por tercero: ¿se quita el filtro por cuenta?**
- **Recomiendo que sí.** Hoy no protege nada, porque el evento no muestra la cuenta, y rompe el saldo. Medido para el liquidador de Costa: 256 terceros. En SAC está vivo para los analistas.
- **La otra opción:** mantenerlo y absorber lo escondido en el «Saldo Inicial». Cerraría el número, pero mentiría sobre el inicial.
- Este punto cambia lo que ven hoy los dos analistas de SAC: pasan a ver todos los eventos del tercero.

**D5 — Lecturas que muestran el nombre de la cuenta del pago inmediato** (compras, ventas), el estado de una obligación y el gasto programado: ¿se tocan?
- **Recomiendo que no** en este ciclo. Exponen el nombre de una cuenta, no su saldo ni sus movimientos.

## 7. Gates

1. **Plan** → GO de QA → autorización de Daniel, con D1–D5.
2. **Construcción:** el autor corre solo el lint (ruff y ESLint) y los tests nuevos.
3. **QA pasada 1:** el delta va como patch, con su sha256, la base y el sha256 de cada archivo. Desde ahí el árbol queda quieto.
4. **Correcciones.**
5. **Gates:**
   - **Dirigidas:** el set de §4 a archivo, con la predicción escrita antes.
     - Todo pytest lleva `TEST_DATABASE_URL` exportado hacia `reciclaje_test_coder_2` en el MISMO comando. Lo de más de 200 tests, y el golden, esperan el lock del Coordinador.
   - **Plantado:** P1–P12 contra la matriz commiteada.
   - **Golden: aplica**, porque toca `money_movements.py`, `money_accounts.py`, `reports.py` y un listener sobre toda sesión.
     - `CAPTURES` corre como superusuario, así que por construcción da 0/0 en `/money-accounts`, `/money-movements` y los dos estados de cuenta.
     - Una sola BD alcanza: no hay cambio de esquema.
     - **Prueba de vida y control positivo FUERA de `CAPTURES`** (#110): el mismo script, en los dos lados, como un usuario restringido sembrado en la copia (liquidador con K1). Lee el estado de cuenta de un tercero con un pago desde otra cuenta y el dashboard. Tiene que DIFERIR entre BEFORE y AFTER: así se ve que los dos lados son códigos distintos.
     - Guardas de procedencia de `golden_run.sh`, con lockf y puertos 8091 y 8092.
   - **Suite completa:** diferida al checkpoint.
   - **Parity:** no aplica, porque no hay cambio de esquema; se mide con `git diff --name-only <base> -- backend/alembic backend/app/models` vacío.
6. **QA pasada 2** → OK de commit.
7. **Commit en mi rama.** Integra el Coordinador. Push y deploy, con el OK de Daniel.

## 8. Antes del deploy, en producción (solo lectura, el Coordinador)

- **G-prod 1:** para los dos analistas de SAC y el liquidador de Costa, cuántos movimientos crearon o anularon en una cuenta NO asignada desde su alta.
  - Si alguno da más de 0, el 403 le rompe algo que hace hoy, y Daniel decide antes del deploy: reasignar cuentas, o D2 con «solo origen».
  - Mi medición de dev (0 para el liquidador) es de una copia con corte el 17-sep, y los analistas no existen en ella.
- **G-prod 2:** para cada analista de SAC, cuántos terceros tienen un efecto escondido distinto de 0 en su estado de cuenta. Es el mismo cálculo de `statement_escondido.py` (script `1abcdfa1…96c2`), con los datos de producción. Es lo que D4 arregla para ellos.
- **G-prod 3:** cuántas cuentas activas tiene SAC. El dashboard de hoy se las muestra todas a los analistas.

## 9. Fuera de alcance

- El reseteo de clave desde Usuarios, que fija '123456' (deuda de #85). Va en la nota del informe de Ingrid §6, ya pasada a Daniel.
- La auto-asignación de cuentas de un admin. Solo importa si D1 cambia.
- `assignedAccountIds` en `usePermissions.ts:45` sigue sin consumidor: los selectores se acotan por `GET /money-accounts`, que ya filtra.
