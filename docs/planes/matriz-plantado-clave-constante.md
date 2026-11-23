# Matriz de plantado: quitar la clave constante

- Plan: `plan-quitar-clave-constante.md` v1.1 (453da28).
- Código: `1123bce`.
- Se commitea ANTES de plantar y no se reescribe.

## Cómo se planta

- Un defecto por corrida, sobre el árbol de `1123bce`.
- El respaldo es por RUTA. El cierre se verifica con el sha256 de cada archivo contra HEAD y con `git status` limpio.
- `PYTHONDONTWRITEBYTECODE=1`. Antes de cada corrida se borran los `__pycache__` de `backend/app`, `backend/tests` y `backend/scripts`.
- Cada corrida: `pytest tests/test_clave_sin_constante.py` con `TEST_DATABASE_URL=…/reciclaje_test_coder_1` en el mismo comando. La primera línea del log lleva la base y el HEAD.
- La corrida tiene que RECOLECTAR los 16 tests. Si no, la fila es inválida.
- P5 planta un comentario en un `.tsx`. El servidor de :5181 lo sirve, pero es solo un comentario: no cambia nada en pantalla ni escribe en dev.

## Los 16 tests

- T1, T2, T3, T4, T5, T6, T7.
- T8: el árbol vivo da 0.
- T8c: el control positivo sobre `git archive 161b204`.
- T9, T10.
- T11[a–d]: el script sin clave o con clave corta, en `--dry-run` y en `--apply`.
- T11c: el control con clave, que verifica que el POST lleva `admin_password`.

## Matriz

| P | Defecto plantado (exacto) | Cae (predicción exacta) |
|---|---|---|
| P1 | `organizations.py`, reseteo: la respuesta devuelve la clave (`{"message": …, "new_password": data.new_password}`) | T1, T3 |
| P2 | `organizations.py`, reseteo: se borra el bloque `if user_in_other_active_org(...): raise 403` (sin D5) | T4 |
| P3 | `organizations.py`, alta: `password=data.password` → `password="12345678"` (vuelve la constante) | T5, T8 |
| P4 | `system.py`: con el email existente y `admin_password`, se le pisa la clave (`admin_user.hashed_password = get_password_hash(data.admin_password)`) | T7 |
| P5 | `UsersPage.tsx`: un comentario `// clave 123456` (el literal en el front) | T8 |
| P6 | `organizations.py`, reseteo: D5 con `get_user_org_count(db, user_id) > 1` en vez del predicado de orgs activas | T4 |
| P7 | `services/organization.py`: `get_user_org_count` cuenta solo orgs ACTIVAS (join a `Organization.is_active`) | T4, T10 |
| P8 | `migrate_org.py`: `admin_password_from_env` devuelve `environ.get(...) or ""` sin abortar | T11[a], T11[b], T11[c], T11[d] |
| P9 | `test_clave_sin_constante.py`: el patrón de la guarda con comillas, `["'](123456\|12345678)["']`, en vez de límites de dígito | T8c |
| P10 | `migrate_org.py`: el payload del POST pierde `admin_password` | T11c |
| P11 | `organizations.py`, reseteo: el log de auditoría escribe `new_password=%s` con la clave | T3 |

## Por qué cada predicción

- **P1.** T3 ve el secreto en la respuesta. T1 compara la respuesta exacta (`== {"message": …}`).
- **P2.** T4 espera el 403 sobre el miembro de otra org activa. Los demás tests no tienen un objetivo multi-org.
- **P3.**
  - T5: el login con la clave elegida da 401.
  - T8: el literal «12345678» queda en `backend/app`.
  - T8c no cae, porque el árbol de 161b204 no cambia.
- **P4.** T7 exige que el admin existente siga entrando con la suya. T6 no cae: crea un admin nuevo.
- **P5.** Solo T8, que recorre `frontend/src`.
- **P6.** En T4, el control «otra org INACTIVA → 200» da 403. El listado de T4 sigue bien, porque usa la versión de lista. Es el control que discrimina contra `get_user_org_count`.
- **P7.**
  - T10: quitar a quien sigue en una org inactiva lo BORRA, porque cuenta 1.
  - T4: afirma `org_count == 2` para el miembro con org inactiva, y da 1.
- **P8.** Los 4 casos de T11 siguen de largo: imprimen el banner «MIGRACION» y caen por el Excel que no existe, sin nombrar la variable. T11c llama a la función con una clave válida, así que pasa.
- **P9.** Con comillas, el control sobre 161b204 encuentra menos de 11. T8 sobre el árbol vivo sigue en 0.
- **P10.** T11c compara el payload exacto.
- **P11.** T3 busca el secreto en todos los mensajes del log.

## Dirección peligrosa

Un test que debía caer y no cayó. Una caída de más se explica en el informe, y la matriz no se cambia.
