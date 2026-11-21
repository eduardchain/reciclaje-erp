# Plan: quitar el reseteo y el alta con clave constante (v1.1)

- **v1.1** (GO de QA 1 sobre v1.0 `f716855`, con 3 condiciones): C1 suma los consumidores del API que D3 rompe, `migrate_org.py` y la skill `/migrate-client` (§1b, D3b, T11). C2 hace que D5 use un predicado APARTE que solo mira orgs activas, sin tocar `get_user_org_count`, que decide el borrado del usuario (D5, T4, T10). C3 fija el patrón de la guarda D4 con límites de dígito, con control positivo sobre el árbol de `161b204` (D4, T8). Además se declara un efecto de D5 (add_member por `user_id`).

Pedido del Coordinador, 20-nov, P2. Daniel lo decidió hoy: es un ciclo propio, **después del deploy 2**.

Es la deuda que #85 dejó escrita: «el ciclo de seguimiento es eliminar el reseteo-a-constante, no rotar claves; #85 es el patrón que debe reemplazarlo».

Nivel propuesto: **lógica**. Cambia el contrato de dos endpoints que usan las 3 orgs cliente, más uno de Sistema, y una pantalla compartida.

## 1. Qué pasa hoy

Hay tres sitios que fijan una clave CONSTANTE (grep sobre `app/` y `frontend/src`):

| Sitio | Quién lo usa | Clave |
|---|---|---|
| `POST /organizations/{org}/members/{user}/reset-password` (`organizations.py:499` → `services/user.py:107`) | cualquier admin de la org | `123456` |
| `POST /organizations/{org}/members/create-user` (`organizations.py:312`) | cualquier admin de la org | crea con `12345678` y la resetea a `123456`, con el comentario «bypass min_length del schema» |
| `POST /system/organizations` (`system.py:88`), cuando el admin inicial no existe | superusuario | `123456` |

**La pantalla lo anuncia:**
- `UsersPage.tsx:447`: «La contraseña por defecto será: 123456».
- `UsersPage.tsx:468`: «… será reseteada a "123456"».
- Los toasts de `useRoles.ts:133` y `:145`.
- `SystemOrganizationsPage.tsx:317`.

**§1b. Consumidores del API fuera de `app/` (C1 de QA, verificado sobre `161b204`).** Ningún test los corre:
- `scripts/migrate_org.py:351` crea la org con `{name, admin_email, admin_full_name}`, SIN clave. Con un admin nuevo, D3 lo convierte en 400 y la migración de un cliente nuevo se cae a mitad del flujo, contra producción. `:356` imprime «password default '123456'».
- `.claude/skills/migrate-client/SKILL.md` l.232 y l.301: «Password inicial: 123456».
- `scripts/MIGRATION.md` l.195: «Password default `123456`».
- `scripts/seed_demo_org.py` y `scripts/seed_sac_org.py` **no se rompen**: pre-registran al admin por `/auth/register` antes de crear la org (`seed_demo_org.py:423`, `seed_sac_org.py:688`), así que el email ya existe y D3 ignora la clave. El comentario de `seed_demo_org.py:419` («crea un User admin con password "123456" hardcoded si el email no existe») queda falso y se corrige.

**Por qué es un riesgo.** La clave es pública por construcción: está en la pantalla. No hay cambio forzado en el primer login (Q1 de #85), y los tokens viven 7 días (#85 D4). Entre el reseteo y el momento en que el usuario cambie la clave, si alguna vez la cambia, cualquiera que conozca la convención entra como él.

- **Desde #129** eso incluye a Ingrid, una usuaria externa con alcance de recolector. Ella no puede administrar miembros (`deny_if_collector_scoped`, que se queda), pero un admin de SAC puede resetearla a `123456`.
- **Hallazgo nuevo de este plan, H1: reseteo entre organizaciones.** El endpoint solo exige que el objetivo sea miembro de ESTA org (`get_user_role_in_org`, l.535). Un usuario puede ser miembro de varias orgs (`get_user_org_count` existe por eso, l.595). El admin de la org X puede resetear la clave de alguien que es admin en la org Y, y entrar a Y como él. Con una clave elegida por el operador el riesgo sigue: el admin de X fija una clave que conoce y entra a Y. D5 lo cierra.

## 2. Medición: cuántos usuarios tienen hoy una clave constante

El hash no se lee desde producción. Se mide sobre una **réplica**: `replicate_prod.sh` restaura un `pg_dump` completo, así que los hashes llegan tal cual.

**El instrumento:** `~/sac-evidencia/2026-11-20/coder-1-plan-clave-constante/medir_claves_constantes.py`, solo lectura.

- Lee `users` y `organization_members` con `docker exec psql`.
- Verifica en memoria con `verify_password`, contra `123456` y `12345678`.
- **No imprime hashes ni emails.** Imprime conteos por org, separando reales de los de prueba `@example.com` y activos de inactivos, más los usuarios en más de una org (H1).

**Corrida 1, sobre mi copia de dev** (`reciclaje_coder_1`, log `medicion_dev_r1.log`):

| Org (dev) | Reales con `123456` | Reales con `12345678` | Reales con otra |
|---|---|---|---|
| Reciclajes de la Costa | 2 | 0 | 5 |
| MetaRecycling | 2 | 0 | 0 |
| SAC | 0 | 5 | 0 |

- Superusuarios con clave constante: 0.
- Miembros de más de una org activa: 1, que es el usuario de prueba `admin.revision@example.com`.

**Esa copia NO es la réplica.** No sirve como número de decisión:
- trae datos y claves de prueba encima de la réplica, y no tiene fecha de replicación;
- en SAC, el seeder `--reset` fuerza las claves de sus usuarios por ORM (`_force_known_passwords`, solo en dev). Los 5 de SAC con `12345678` pueden venir de ahí, no de producción.

**La medición que vale** (propuesta):
1. El Coordinador, dueño de `reciclaje_db`, corre el script **inmediatamente después de `replicate_prod.sh` y ANTES de cualquier corrida del seeder**: `<backend>/venv/bin/python -I medir_claves_constantes.py <backend> reciclaje_dev_db reciclaje_db`.
2. Solo lectura, a archivo, con la hora de la réplica en la primera línea.
3. Lo que viaja al informe y a Daniel son los conteos por org y el conteo de H1, nunca emails ni hashes.
4. Si Daniel decide actuar sobre los usuarios afectados (§6, O1), la lista de ids sale de esa misma corrida y se queda en la máquina.

## 3. Qué cambia (patrón #85)

**D1. Resetear exige la clave nueva, y nunca vuelve.**
- `POST …/reset-password` recibe `{new_password}` con `min_length=6`, calco de `ChangePassword` y de #85.
- La respuesta sigue siendo `{"message": …}`.
- Sin cuerpo da 422. Un frontend viejo cae en 422, y por eso el cambio de pantalla viaja en el mismo deploy.

**D2. Crear un usuario exige su clave.**
- `CreateUserWithMembership` gana `password: str = Field(min_length=8)`. El usuario se crea con `UserCreate`, el mismo schema del registro, que ya exige 8.
- Desaparecen el `12345678` fijo y el reseteo posterior a `123456`, o sea el «bypass».
- Con eso hay dos mínimos: 8 al crear (`UserCreate`) y 6 al resetear (`ChangePassword` y #85). Esa asimetría YA existe en el repo; se declara y no se toca (O2).

**D3. La org nueva de Sistema exige la clave de su admin, si el admin es nuevo.**
- `SystemOrgCreate` gana `admin_password: str | None = Field(None, min_length=8)`.
- Si el email NO existe y falta la clave, 400 en el mismo bloque donde hoy se exige `admin_full_name`.
- Si el email YA existe, la clave se IGNORA: no se pisa la clave de un usuario existente (T7).

**D3b. `migrate_org.py` toma la clave del admin de una variable de entorno (C1).**
- `MIGRATE_ADMIN_PASSWORD`, nunca un argumento de línea de comandos: la regla de credenciales del repo. Se manda como `admin_password` en el `POST /system/organizations`.
- **Se exige SIEMPRE, en `--dry-run` y en `--apply`, y se valida con el mismo mínimo de D3 (8).** Si falta o es corta, el script aborta antes de la fase 0, o sea antes del `--reset-org` y antes de crear la org.
- Por qué siempre y no «solo si el admin es nuevo»: el dry-run es OFFLINE por diseño (#28, `migrate_org.py:1392`, sin login), así que no puede saber si el admin existe. Dos reglas, una por modo, dejarían un dry-run verde y un apply que se cae. Con una sola regla el dry-run avisa lo mismo que va a exigir el apply. Si el admin ya existe, el backend ignora la clave (D3), así que exportarla no cambia nada.
- Se corrigen el print de `:356`, `SKILL.md` (l.232 y l.301: la clave inicial la define el operador en la variable, no viaja por el chat ni por un argumento, y se entrega al cliente por un canal privado), `MIGRATION.md` l.195 y el comentario de `seed_demo_org.py:419`.

**D4. Cero constantes.**
- `services/user.reset_password(db, user_id, new_password)` exige la clave.
- Guarda nueva (C3): un test que recorre `backend/app` y `frontend/src` con el patrón `(^|[^0-9])(123456|12345678)([^0-9]|$)` y exige 0.
  - Con límites de dígito y SIN comillas. Con comillas, sobre `161b204`, encuentra 6 y se salta 5, entre ellos 4 de los sitios de UI que este ciclo quita.
  - **Control positivo sobre el árbol real, no sintético:** la misma función de recorrido, aplicada a `git archive 161b204` de esas dos carpetas, encuentra EXACTAMENTE estos 11 (medido por QA y por mí, `git grep -nE` con el patrón):
    1. `organizations.py:351` (`password="12345678"`)
    2. `organizations.py:354` (comentario «Resetear a 123456»)
    3. `organizations.py:509` (docstring del reseteo)
    4. `system.py:88`
    5. `services/user.py:108` (docstring)
    6. `services/user.py:112`
    7. `useRoles.ts:133`
    8. `useRoles.ts:145`
    9. `UsersPage.tsx:447`
    10. `UsersPage.tsx:468`
    11. `SystemOrganizationsPage.tsx:317`
  - Uno sintético no basta: no muestra que el recorrido de directorios mire lo que tiene que mirar.

**D5. El reseteo entre organizaciones se cierra (H1).**
- El admin de una org NO puede resetear a un miembro que pertenece a OTRA org ACTIVA: 403 con «Este usuario también pertenece a otra organización: el reseteo lo hace soporte (Sistema → Usuarios)».
- **Predicado APARTE (C2):** `user_in_other_active_org(db, user_id, organization_id)`, que es True si hay una membresía del usuario en una org distinta de esta y con `is_active`.
  - **No se usa `get_user_org_count`, y tampoco se cambia.** Hoy cuenta TODAS las membresías, también las de orgs dadas de baja: un miembro de Costa que estuvo en Biogreen (desactivada) recibiría un 403 falso, y por una org inactiva no hay H1, porque sus miembros reciben 403 desde #29.
  - Pero esa misma función decide en `remove_organization_member` (`organizations.py:595-600`) si se BORRA el usuario entero (`org_count <= 1 → delete_user`), y su `org_count` alimenta el diálogo de quitar (`UsersPage.tsx:480`). Cambiarla a «solo activas» haría que quitar a alguien que también está en una org inactiva le borre el usuario. Queda intacta, y un test lo fija (T10).
  - El listado de miembros expone el predicado en un campo nuevo, `in_other_active_org: bool`, calculado con UNA consulta para todos los miembros de la respuesta, no una por miembro. `org_count` sigue igual.
- El camino que queda para esos usuarios es #85 (superusuario).
- Es fail-closed. El costo se mide con el conteo de H1 en la réplica (el instrumento ya cuenta solo orgs activas).
- **Efecto declarado (QA):** un admin de B puede agregar por `user_id` a un miembro de A (`add_member`), y con eso le quita a A la capacidad de resetearlo. Es una molestia, no una toma de cuenta; #85 cubre ese caso. Los otros endpoints de miembros (add, patch del rol, delete) no tocan la clave (verificado por QA).

**D6. Auditoría por log, calco de #85 D5.** `logger.warning` con actor (id y email) → objetivo (id y email) y la org. Jamás el payload; un test lo clava.

**D7. Lo que NO arregla, declarado.**
- Las sesiones ya emitidas siguen válidas hasta 7 días (#85 D4); el diálogo lo dice.
- Los usuarios que HOY tienen una clave constante la siguen teniendo: el ciclo deja de crear casos nuevos y no repara los viejos (O1).

**D8. Lo que queda igual:**
- `deny_if_collector_scoped`: Ingrid no administra miembros;
- el 403 contra superusuarios;
- el 404 si el objetivo no es miembro de esta org;
- y que solo el admin puede resetear y crear.

## 4. Qué ve el admin de org en Usuarios

- **Crear usuario:** el diálogo gana «Contraseña» y «Confirmar contraseña», con mínimo 8.
  - El botón queda deshabilitado si las claves no coinciden o son cortas.
  - Debajo: «Entrégale esta contraseña en persona o por un canal privado. El sistema no la vuelve a mostrar.»
  - Desaparece «La contraseña por defecto será: 123456».
  - El toast dice «Usuario creado», sin clave.
- **Resetear contraseña, miembro solo de esta org:** el botón abre un diálogo con «Nueva contraseña» y «Confirmar», mínimo 6, igual al de Sistema → Usuarios de #85.
  - Texto: «Las sesiones que esa persona tenga abiertas siguen válidas hasta 7 días.»
  - El toast dice «Contraseña actualizada».
  - Reemplaza al `ConfirmDialog` que anunciaba `123456`.
- **Resetear contraseña, miembro de otra org también:** el botón aparece deshabilitado, con la nota «También pertenece a otra organización: el reseteo lo hace soporte».
  - El botón lee `in_other_active_org` del listado (D5), no `org_count`: con `org_count` un miembro que estuvo en una org dada de baja quedaría bloqueado sin razón.
  - El 403 de D5 respalda la pantalla.
- **Superusuarios y usuarios con alcance:** igual que hoy.
- **Sistema → Organizaciones, crear org con admin nuevo:** campo «Contraseña del admin» (mínimo 8), en vez de «la contraseña será 123456».
- **A 390 px:** los diálogos usan `grid-cols-1 sm:grid-cols-2` y botones `w-full sm:w-auto`, el patrón del repo.

## 5. Verificación

**Tests nuevos** (`tests/test_clave_sin_constante.py`):

| T | Qué |
|---|---|
| T1 | resetear con una clave: el login con la nueva da 200 y con `123456` da 401 (efecto real, login de punta a punta) |
| T2 | sin cuerpo da 422; con 5 caracteres da 422 |
| T3 | ni la respuesta ni el log (caplog) contienen la clave (D1, D6) |
| T4 | D5: un miembro de esta org Y de otra ACTIVA da 403 con el texto. **Controles:** un miembro solo de esta org da 200, y un miembro de esta org y de otra INACTIVA da 200 (el que discrimina contra `get_user_org_count`). El listado devuelve `in_other_active_org` True/False/False en los tres casos |
| T5 | crear un usuario con clave: login con ella 200, con `123456` 401 y con `12345678` 401; sin clave 422; con 7 caracteres 422 |
| T6 | Sistema crea una org con admin nuevo y su clave: login 200; sin clave, 400 |
| T7 | Sistema crea una org con un admin YA existente y manda `admin_password`: la clave del existente NO cambia (su login viejo sigue dando 200) |
| T8 | guarda D4: 0 coincidencias del patrón con límites de dígito en `backend/app` y `frontend/src`. **Control positivo:** la misma función sobre `git archive 161b204` de esas carpetas encuentra exactamente los 11 sitios de D4 (archivo y línea) |
| T9 | se conservan los 403 de hoy (no admin, superusuario como objetivo, usuario con alcance), cada uno con su control en 200 |
| T10 | no-regresión del borrado (C2): quitar de esta org a un miembro que también está en una org INACTIVA NO borra el usuario (sigue existiendo, con su membresía en la inactiva). **Control:** quitar a un miembro solo de esta org lo borra, como hoy |
| T11 | `migrate_org.py` (D3b): sin `MIGRATE_ADMIN_PASSWORD`, y con una de 7 caracteres, termina con exit ≠ 0 y el mensaje que nombra la variable, en `--dry-run` y en `--apply`, sin ninguna llamada al API (un cliente falso que falla si lo llaman). **Control:** con la variable, el `POST /system/organizations` del apply lleva `admin_password` |

**Tests existentes que cambian de semántica** (sale del grep de `reset-password` y `create-user` sobre `tests/`): `test_user_management.py` (7 tests, entre ellos `test_created_user_can_login_with_default_password`, que hoy afirma JUSTO lo que se quita), `test_organizations.py:690` y las llamadas de `test_sac_recolector_alcance.py`. La lista exacta, con el antes y el después de cada uno, va en la pasada 1.

**Pantalla:** e2e del alta y del reseteo en Usuarios, y de la org nueva en Sistema, a 1440 y 390. Incluye el botón deshabilitado para un miembro de dos orgs.

**Plantado:**
- defecto «respuesta con la clave» → T3;
- «sin D5» → T4;
- «la constante vuelve al alta» → T5 y T8;
- «Sistema pisa la clave de un existente» → T7;
- «el literal en el front» → T8;
- «D5 con `get_user_org_count`» → el control «otra org inactiva» de T4;
- «`get_user_org_count` cambiado a solo activas» → T10;
- «`migrate_org` sin el chequeo de la variable» → T11;
- «la guarda con comillas» → el control positivo de T8 (encuentra menos de 11).
La matriz se commitea antes de plantar.

**Gates:**
- Golden: no aplica. `golden_capture.py` solo llama a `/auth/login/json`; no captura `/organizations` ni `/system`. Se mide con grep en la pasada 1.
- Parity: no aplica, cero migraciones.
- Dirigidas por grep sobre la superficie (incluye `get_user_org_count`, `org_count`, `migrate_org` y `system/organizations` en `tests/`), más las 3 guardas.

## 6. Decisiones abiertas

- **O1 (Daniel): los usuarios que HOY tienen una clave constante.** El ciclo deja de crearlos y no los repara. Opciones:
  - (a) nada automático: con el conteo de la réplica, cada admin resetea a los suyos con una clave elegida;
  - (b) un ciclo aparte con `must_change_password` (Q1 de #85), que obliga a cambiarla en el siguiente login;
  - (c) soporte resetea por #85 a cada usuario de la lista.

  Recomiendo (b) como siguiente ciclo y, mientras tanto, (a) con la lista. La decisión espera la medición sobre la réplica.
- **O2 (QA, de acuerdo): dos mínimos de longitud**, 8 al crear y 6 al resetear. Es una asimetría heredada, y unificar tocaría también `ChangePassword` y #85. Recomiendo no tocarla en este ciclo.
- **O3 (Daniel; QA de acuerdo): D5 cierra el reseteo de cualquier usuario multi-org desde una org.** La alternativa es permitirlo cuando el admin lo es también en TODAS las orgs del objetivo. Recomiendo cerrar: es simple y fail-closed, y #85 cubre el caso. El costo es el conteo de H1 en la réplica.
- **Fuera de alcance:** `seed_sac_org.py --users-password` (solo en local; contra un remoto no crea usuarios, #115) y la invalidación de sesiones (#85 D4).
