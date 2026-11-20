# Plan — Cuentas restringidas por usuario: que la asignación de cuentas también limite lo que se ESCRIBE (v1.1)

**v1.1 (20-nov, revisión de QA 2 sobre v1.0, `~/sac-evidencia/2026-11-20/qa-2-cuentas/revision_plan_v1.0.md`, sha `725dc58e…8757`):**
- **C1:** P4 no tumbaba T2, porque las reversas de activos cambian la cuenta Y el movimiento en el mismo flush. Se agrega T14, en la que cambia SOLO la cuenta (`PATCH`/`DELETE /money-accounts/{K3}`).
- **C2:** las 3 escrituras de `/money-accounts` entran a §2.1, §3 y T1/T14.
- **C3:** el estado de cuenta ya no enlaza a un movimiento que el restringido no puede abrir (§2.2, celda nueva en T5, P16).
- **C4:** en un update de `MoneyMovement` se miran la cuenta vieja y la nueva, con cambios netos (§2.1, T15, P14, P15).
- **N1–N9:** en el lugar de cada una.

**Base:** el plan se escribió sobre develop `dda8e38`. La construcción arranca desde develop actualizado (N8: `4006fb8` a las 18:16, el frontend de Entradas y docs, sin cruce con esta superficie), y el patch de la pasada 1 va contra esa base.
**Nivel:** lógica. Toca código compartido: el embudo de escritura de tesorería, el estado de cuenta, el listado de cuentas y el dashboard de tesorería. Lo ven las 7 orgs.
**Pedido:** decisión 1 de Daniel en el plan de Ingrid (§6): ciclo propio, inmediatamente después de Ingrid.
**Migraciones:** cero. **Permisos nuevos:** cero.

Las decisiones que espera Daniel están en §6 (D1–D6). El plan se puede revisar sin ellas, y cada una tiene recomendación.

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
- **Qué cuenta se mira en cada caso (C4):**

  | Fila | Insert | Update | Delete |
  |---|---|---|---|
  | `MoneyMovement` | su `account_id` | la cuenta VIEJA (historia del atributo) y la NUEVA, las dos | su `account_id` |
  | `MoneyAccount` | su `id` (una cuenta nueva nunca está en el conjunto) | su `id` | su `id` |

- **Solo cuentan los cambios netos, en las dos clases** (historia de atributos con `has_changes()`, o `session.is_modified`). Leer una fila o asignarle el mismo valor no cuenta. Importa porque `CRUDBase.update` hace `setattr` genérico (`base.py:307`).
  - Hoy ningún camino cambia el `account_id` de un movimiento (`grep "\.account_id = "` en `app/` da 0). La regla de la cuenta vieja y la nueva es para el camino que se escriba mañana, que es el argumento del listener.
- **Las escrituras de `/money-accounts` también quedan cubiertas (C2):**
  - `POST /money-accounts` da **403 siempre** a un restringido, porque la cuenta nueva no está en su conjunto;
  - `PATCH` y `DELETE /money-accounts/{id}` de una cuenta no asignada dan 403.

  Es la regla uniforme, declarada. Hoy está latente: ningún restringido tiene `treasury.manage_accounts` (ni los 16 permisos del analista de SAC ni el rol liquidador, `role.py:158-177`), y el admin queda afuera por D1. Si Daniel prefiere que un restringido con `manage_accounts` pueda crear cuentas, es una excepción explícita para el insert de `MoneyAccount` (D6).
- **El mensaje del 403 nombra la cuenta** (N7). La elegió el usuario en una creación, y en una reversa el nombre ya es visible por D5 (el pago inmediato de una compra muestra su cuenta). Declarado.

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
- **Un `except` que se trague el 403** (N1). QA 2 lo midió en todo `app/` (`qa-2-cuentas/broad_except_6898bc9.log`, `dd61cc23…9406`, con su script `scripts/broad_except.py`):
  - hay 8 `except` amplios sin un `except HTTPException` antes: `health`, 6 listados GET de compras y ventas, y `user.py:127`;
  - toda ruta de escritura re-lanza el HTTPException antes del `except Exception`;
  - en SQLAlchemy 2.0.25, `_autoflush` solo atrapa `StatementError`, y `before_flush` corre antes del bloque que hace rollback (`verificacion_plan_v1.0_sqla.log`, `3b37d79b…2d3d`).

  El barrido T1 da 403 y no 500 en cada ruta.
- **Que algo se commitee antes del flush de dinero** (N2). QA 2 midió que ninguna función de los caminos de dinero hace dos commits (`multi_commit_6898bc9.log`, `fcd13d5e…ff9f`). Las únicas que los hacen son `update_collector_scope`, `create_user` y `delete_user`. `create` con `auto_liquidate` hace flush y deja el commit a `liquidate`. Esa medición no ve commits anidados entre llamadas, así que T1 y T2 cuentan también el documento de la ruta y el estado de la entidad (§4).
- **Archivos en disco antes del flush** (evidencia). El chequeo de visibilidad de C1 corre antes de escribir el archivo, así que no queda un huérfano. Lo prueba T8.

### 2.2 Lecturas

- **C1 — Movimiento por id, por número y su evidencia** (GET, POST y DELETE de evidencia, `annul` y `classification`): **404** si el movimiento tiene una cuenta no visible para el usuario.
  - Hoy `_require_movement_visible` y `_require_movement_owned` (`money_movements.py:164-172`) solo aplican con alcance.
  - Con alcance no cambia nada. Sin alcance, «visible» es: `account_id` NULL, o una cuenta en `accounts_for`.
- **C3 — Listado y resumen** (`GET /money-movements` y `/summary`): **sin cambio**. Siguen pasando las cuenta-NULL (decisión D3).
- **C4 — Estado de cuenta por tercero:** se quita el filtro por cuenta para el usuario sin alcance (decisión D4). Con alcance sigue D-E1 de Ingrid, sin tocar.
  - **El enlace del evento (C3 de QA 2).** Con D4, el restringido ve los eventos de K3, y la pantalla los enlaza al detalle del movimiento (`AccountStatementPage.resolveSourceLink`, l.171, `case "money_movement"`), que por C1 le da 404.
  - **Lo que se hace:** para el usuario restringido sin alcance, el evento de un movimiento cuya cuenta no le es visible sale con `source="money_movement_restricted"`, y el resto de sus campos igual. El `switch` del frontend lo resuelve explícitamente a `null`, y `EntityLink` con `to=null` pinta texto plano.
  - **Por qué esta opción y no un campo nuevo:**
    - para el superusuario y para todo usuario con `accounts_for` = `None`, el evento sale byte a byte igual, así que el golden no gana una clave aditiva;
    - el único lector de `source == "money_movement"` en el frontend es ese `switch` (grep de `"money_movement"` en `frontend/src`: 1 línea), y el Excel y los PDF del estado de cuenta leen `parent_source_id`, no `source`;
    - se cambia `source` y no solo `source_id`: con `source_id` en null y `source` intacto, el `switch` armaría `/treasury/null`.
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

**Estado de cuenta:** `resolveSourceLink` gana un `case "money_movement_restricted": return null` explícito. El `default` ya devuelve `null`, pero el caso escrito deja claro que es a propósito (C3).

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
- El listener se registra para TODA sesión. Sin `account_actor` (scripts, seeds) vuelve en la primera línea. Un flush que no toca filas de dinero tampoco consulta nada.
- **Con contexto, en el primer flush que toca dinero, `accounts_for` corre una vez** (N4):
  - para el admin y el superusuario corta en `is_admin` sin consultar;
  - para un no-admin sin asignaciones hace UNA consulta para saber que da `None`.

  Los datos salen byte a byte iguales, con una consulta más por request que escribe dinero, y el resultado queda en `db.info` para el resto del request.
- `get_required_org_context` hace UNA asignación de diccionario más y ninguna consulta más.
- El dashboard recibe `allowed_account_ids=None` de su único llamador.
- Ninguna pantalla compartida manda un parámetro nuevo.

**Lo que SÍ cambia, y para quién.**

| Usuario | Escrituras con cuenta no asignada | Estado de cuenta por tercero | Dashboard de tesorería | Movimiento por id de otra cuenta |
|---|---|---|---|---|
| Liquidador de Costa | 403 (medido: 0 casos hasta el 17-sep) | sin cambio para él: no tiene el permiso | no tiene el permiso | 404 |
| Analistas de SAC | 403 (**no medido**: ver G-prod 1) | pasan a ver TODOS los eventos del tercero, y su saldo cierra | solo sus cajas | 404 |
| Admin de Costa con 5 cuentas | sin cambio (D1) | sin cambio | sin cambio | sin cambio |

Además, para cualquier restringido con `treasury.manage_accounts`, `POST /money-accounts` y el `PATCH`/`DELETE` de una cuenta no asignada pasan a dar 403 (C2). Hoy no hay ninguno.

## 4. Tests (archivo nuevo `tests/test_cuentas_restringidas.py`)

Fixture: una org con 3 cuentas (K1, K2, K3) y 4 usuarios:
- un liquidador con K1 asignada;
- un usuario custom con los 16 permisos del analista de SAC y K1, K2;
- un admin con K1 asignada;
- un usuario sin asignaciones.

Los roles son custom con sus permisos: el admin bypassa y no prueba nada (#29). En cada test de permiso va un **control positivo** con la cuenta propia en 2xx (lección de #111).

| # | Qué afirma |
|---|---|
| **T1** | **Barrido de escrituras**, parametrizado sobre una lista explícita, con un comentario de por qué está completa (#108): las 34 con cuenta en el cuerpo del inventario v2 (`batch-expenses` incluido) más las 3 de `/money-accounts` (C2). Con K3: **403**, el detalle nombra la cuenta, y **nada queda escrito** (N2): el saldo de K3, el del tercero, el conteo de `money_movements`, el conteo y el estado del documento de la ruta (compra, venta, activo, obligación, cruce, Entrada, Salida, gasto programado) y el estado de la entidad tocada, antes y después. Con K1: 2xx. |
| **T2** | **Las 6 indirectas.** Cancelar una compra y una venta con `annul_linked_payments=True` cuyo pago es de K3; anular un movimiento de obligación de K3; cancelar un activo, anular su venta y anular una revalorización pagadas desde K3. Todo da **403** y no cambia nada, con el mismo recuento de T1 (N2). Con K1: 2xx. |
| **T3** | **Admin con asignación (D1):** escribe en K3 → 2xx. Control: el liquidador, con la misma petición, da 403. **Orden fijo dentro del mismo test: el request del admin va ANTES que el del liquidador** (N3: un caché a nivel de módulo devolvería al liquidador el `None` del admin, y solo ese orden lo atrapa). |
| **T4** | **Sin asignaciones** escribe en K3 → 2xx (no-regresión). |
| **T5** | **Estado de cuenta (D4):** un tercero con una compra liquidada, un pago desde K3 y otro desde K1. Para el liquidador con K1:<br>• el último `balance_after` == `current_balance`, y el pago de K3 aparece. **Se escribe primero y se corre contra la base:** tiene que FALLAR ahí (hoy esconde el pago);<br>• **el enlace (C3):** el evento de K3 sale con `source == "money_movement_restricted"` y el de K1 con `"money_movement"`;<br>• **control:** para el admin, los dos salen con `"money_movement"`. |
| **T6** | **Dashboard:** el analista con K1 y K2 ve solo K1 y K2, con sus totales, y los recientes solo de K1, K2 o NULL. Control: el admin ve las 3. |
| **T7** | **`GET /money-accounts` con 3 cuentas, `limit=1` y una sola cuenta asignada en la posición 3:** `total == 1` y la página la trae. Hoy da `total` 0 y una página vacía: pagina primero y filtra después (`money_accounts.py:45-62`). |
| **T8** | **C1:** GET por id y por número, evidencia (GET, POST, DELETE), `annul` y `classification` sobre un movimiento de K3 → 404. El POST de evidencia no deja archivo en disco (directorio de uploads de la org, antes y después). Control con K1. |
| **T9** | **Traslado entre cuentas (D2):** K1→K3 y K3→K1 dan 403; K1→K2 con el analista da 201. |
| **T10** | **Movimientos con cuenta NULL** (`expense-accrual`, `tp-transfer`, `tp-adjustment-*`): el liquidador los crea y los anula (D3). |
| **T11** | **Sin contexto:** el servicio llamado directo con `db_session`, sin request, escribe en K3. Fija que el listener no actúa sin contexto, para que nadie lo vuelva fail-closed sin decidirlo (rompería scripts y seeds). |
| **T12** | **Con alcance (Ingrid), el listener coincide con las reglas existentes:** una escritura en una cuenta no asignada da 403 aunque el endpoint estuviera en la lista blanca. Se monta parcheando el chequeo explícito, para ver que la red sola también corta. |
| **T13** | **El contexto lo carga** (guarda del mecanismo, N6). Sin rutas de prueba en `app/`: el test reemplaza `get_db` con `dependency_overrides` por un generador que guarda la sesión que entrega. Después de un request del liquidador, `db.info["account_actor"]` trae su `user_id` y su organización; después de uno del superusuario, `is_admin` es True. |
| **T14** | **Cambia SOLO la cuenta** (C1 de QA 2). Un rol custom con `treasury.manage_accounts` y K1 asignada:<br>• `PATCH /money-accounts/{K3}` (el nombre) y `DELETE /money-accounts/{K3}` → 403, y K3 queda igual (nombre, `is_active`);<br>• `POST /money-accounts` → 403, sin cuenta nueva;<br>• **control:** el mismo `PATCH` sobre K1 → 200. |
| **T15** | **Updates de movimientos, en el listener** (C4). No hay camino HTTP que cambie la cuenta de un movimiento, así que va con una sesión directa y `account_actor` puesto a mano (el liquidador con K1):<br>• cambiar un movimiento de K3 a K1 → 403;<br>• de K1 a K3 → 403;<br>• asignar a un movimiento de K3 el mismo `account_id` y la misma descripción → no hay 403, porque no hay cambio neto;<br>• lo mismo sobre `MoneyAccount` K3 (el mismo nombre) → no hay 403. |

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
| P4 | El listener mira `MoneyMovement` pero no `MoneyAccount` | T14 (PATCH y DELETE de K3). **No tumba T2:** las reversas de activos cambian la cuenta Y el movimiento en el mismo flush (C1 de QA 2) |
| P5 | El listener no corta en admin (D1) | T3 |
| P6 | El listener deja pasar si alguna de las cuentas del flush es permitida (en vez de todas) | T9 |
| P7 | El estado de cuenta conserva el filtro por cuenta | T5 |
| P8 | El dashboard no filtra | T6 |
| P9 | `GET /money-accounts` filtra después de paginar | T7 |
| P10 | C1 solo con alcance (como hoy) | T8 |
| P11 | El listener corta también las cuenta-NULL | T10 |
| P12 | El listener actúa sin contexto (fail-closed) | T11 |
| P13 | El conjunto permitido se cachea a nivel de módulo, no en la sesión | T3, con el orden fijado (N3) |
| P14 | En un update de movimiento se mira solo la cuenta nueva | T15, el caso K3→K1 |
| P15 | Se usa `session.dirty` sin cambios netos | T15, el caso del mismo valor sobre K3 |
| P16 | El evento de una cuenta no visible sale con `source="money_movement"` | T5, la celda del enlace |

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

**D6 — Un restringido con `treasury.manage_accounts`: ¿puede crear cuentas?** (C2 de QA 2)
- **Recomiendo que no, que es la regla uniforme.** Una cuenta nueva no está en su conjunto, así que el listener da 403. Hoy no hay ningún restringido con ese permiso.
- **La otra opción:** una excepción explícita para el insert de `MoneyAccount`, más asignarle automáticamente la cuenta que crea. Es una regla nueva y no la propongo sin un caso real.

## 7. Gates

1. **Plan** → GO de QA → autorización de Daniel, con D1–D6.
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
     - **Prueba de vida y control positivo FUERA de `CAPTURES`** (#110, N5):
       - el usuario restringido (un liquidador con una cuenta) se siembra en la copia ANTES de la captura BEFORE. Con una sola BD, una escritura en un lado cambiaría el otro;
       - el script de control es **solo de lectura**, el mismo en los dos lados, con ese usuario;
       - tres señales, con las predicciones escritas antes:
         - el estado de cuenta de un tercero con un pago desde otra cuenta: en BEFORE no cierra contra el saldo vivo; en AFTER cierra y el pago sale con `money_movement_restricted`;
         - el dashboard: en BEFORE muestra todas las cuentas; en AFTER, solo la suya;
         - `GET /money-movements/{id}` de un movimiento de otra cuenta: 200 en BEFORE y 404 en AFTER.
       - Si no difieren, los dos lados son el mismo código y el golden no probó nada.
     - Guardas de procedencia de `golden_run.sh`, con lockf y puertos 8091 y 8092.
   - **Suite completa:** diferida al checkpoint.
   - **Parity:** no aplica, porque no hay cambio de esquema; se mide con `git diff --name-only <base> -- backend/alembic backend/app/models` vacío.
6. **QA pasada 2** → OK de commit.
7. **Commit en mi rama.** Integra el Coordinador. Push y deploy, con el OK de Daniel.

## 8. Antes del deploy, en producción (solo lectura, el Coordinador)

Las tres lecturas las hace un solo script por API: `~/sac-evidencia/2026-11-20/coder-2-cuentas-restringidas/scripts/gprod_cuentas.py` (sha `99b55ecf…2b4d`).
- Es solo GET: el único POST es el login, y cualquier otro método aborta.
- No imprime nombres ni correos.
- Lee las listas completas, exigiendo `len == total`.
- **Ensayo:** contra `:8012`, sobre la copia de Costa, coincidió exacto con la predicción que salió del SQL (`gprod_cuentas_ensayo_8012.log`, `0946200e…22c4`).
- **Desde qué árbol se corre:** uno con el mismo mapa `THIRD_PARTY_BALANCE_DIRECTION` que `main`. QA 2 verificó que el mapa es idéntico en `main` `7566bf6` y en `6898bc9`: 36 entradas, con el mismo hash (N9).

- **G-prod 1:** para los dos analistas de SAC y el liquidador de Costa, cuántos movimientos crearon o anularon en una cuenta NO asignada desde su alta.
  - Si alguno da más de 0, el 403 le rompe algo que hace hoy, y Daniel decide antes del deploy: reasignar cuentas, o D2 con «solo origen».
  - Mi medición de dev (0 para el liquidador) es de una copia con corte el 17-sep, y los analistas no existen en ella.
- **G-prod 2:** para cada analista de SAC, cuántos terceros tienen un efecto escondido distinto de 0 en su estado de cuenta. Es el cálculo de `statement_escondido.py` (`1abcdfa1…96c2`, SQL sobre la copia), hecho por la API. Es lo que D4 arregla para ellos.
- **G-prod 3:** cuántas cuentas activas tiene SAC. El dashboard de hoy se las muestra todas a los analistas.

## 9. Fuera de alcance

- El reseteo de clave desde Usuarios, que fija '123456' (deuda de #85). Va en la nota del informe de Ingrid §6, ya pasada a Daniel.
- La auto-asignación de cuentas de un admin. Solo importa si D1 cambia.
- `assignedAccountIds` en `usePermissions.ts:45` sigue sin consumidor: los selectores se acotan por `GET /money-accounts`, que ya filtra.
