# Matriz de plantado r2: quitar la clave constante (sobre el HEAD final)

- Plan: `plan-quitar-clave-constante.md` v1.2 (062747e, GO de QA 1).
- Código: `2ed7bb2`. Esta matriz se commitea encima y la corrida planta sobre ESE commit, con 0 archivos sin commitear.
- Pedido de QA 1 (C1 de la pasada 2): no se arrastra el 11/11 de la r1 (`matriz-plantado-clave-constante.md`, sobre 1123bce). Las filas vigentes se vuelven a plantar sobre el árbol nuevo, porque el delta tocó `test_clave_sin_constante.py` y `migrate_org.py`.
- Se commitea ANTES de plantar y no se reescribe.

## Cómo se planta

Igual que la r1:
- un defecto por corrida, con respaldo por RUTA y cierre por sha256 contra HEAD y `git status` limpio;
- `PYTHONDONTWRITEBYTECODE=1`, con los `__pycache__` de `backend/app`, `backend/tests` y `backend/scripts` borrados antes de cada corrida;
- `TEST_DATABASE_URL=…/reciclaje_test_coder_1` en el mismo comando;
- la corrida tiene que RECOLECTAR los 16 tests, o la fila es inválida.

## Los 16 tests

- T1–T7.
- T8: el árbol vivo da 0.
- T8c: el control sobre `git archive 161b204`.
- T9, T10.
- T11a[éxito] y T11a[error]: no-fuga en los dos caminos.
- T11a2: dos corridas, dos claves.
- T11b: el admin nuevo no entra con ninguna clave conocida; el control #85 da 200.
- T11c: el dry-run no pide clave.

## Filas retiradas (declaradas)

- **P8** (`admin_password_from_env` sin abortar) y **P10** (el payload pierde `admin_password` en el control con la variable) de la r1: el código que plantaban ya no existe en la v1.2. P10 vuelve con otra forma como P15.

## Matriz

| P | Defecto plantado (exacto) | Cae (predicción exacta) |
|---|---|---|
| P1 | `organizations.py`, reseteo: la respuesta devuelve la clave | T1, T3 |
| P2 | `organizations.py`, reseteo: se borra el bloque D5 (`user_in_other_active_org` → 403) | T4 |
| P3 | `organizations.py`, alta: `password=data.password` → `password="12345678"` | T5, T8 |
| P4 | `system.py`: con el email existente y `admin_password`, se le pisa la clave | T7 |
| P5 | `UsersPage.tsx`: un comentario `// clave 123456` | T8 |
| P6 | `organizations.py`, reseteo: D5 con `get_user_org_count(db, user_id) > 1` | T4 |
| P7 | `services/organization.py`: `get_user_org_count` cuenta solo orgs ACTIVAS | T4, T10 |
| P9 | `test_clave_sin_constante.py`: el patrón de la guarda con comillas | T8c |
| P11 | `organizations.py`, reseteo: el log de auditoría escribe `new_password=%s` | T3 |
| P12 | `migrate_org.py`: `_random_admin_password` devuelve una clave fija no conocida (`"clave-fija-migrate-t11"`) | T11a2 |
| P13 | `migrate_org.py`: el print del 201 agrega ` clave={admin_password}` | T11a[éxito] |
| P14 | `migrate_org.py`: el print de error sin redactar (`{resp}` en vez de `str(resp).replace(...)`) | T11a[error] |
| P15 | `migrate_org.py`: el payload pierde `"admin_password"` | T11a[éxito], T11a[error], T11a2, T11b |
| P16 | `migrate_org.py`: `main` vuelve a exigir `MIGRATE_ADMIN_PASSWORD` antes de leer el Excel | T11c |
| P17 | `migrate_org.py`: `_random_admin_password` devuelve la constante `"12345678"` | T11a2, T11b |

## Por qué cada predicción (filas nuevas)

Las vigentes, P1–P7, P9 y P11, conservan la razón escrita en la r1: sus archivos de código no cambiaron, y sus tests (T1–T10) no los tocó el delta.

- **P12.** Solo T11a2 ve que las dos corridas dan la misma clave. T11b no cae, porque la fija no está entre las conocidas. Esa fila mide que T11a2 discrimina por sí solo.
- **P13.** T11a[éxito] busca la clave en stdout. T11a[error] no pasa por ese print y T11b no mira la salida.
- **P14.** T11a[error]: el 422 falso refleja la clave en `input`.
- **P15.** T11a[éxito] y T11a[error] exigen las 4 claves del payload. T11a2 lee `payload["admin_password"]` (KeyError). En T11b, el servidor real responde 400 sin la clave para un admin nuevo, así que `org_id` es None.
- **P16.** T11c: el dry-run sin la variable cae por la variable y no por el Excel.
- **P17.** T11b: el login con `12345678` da 200. T11a2: las dos corridas dan la misma. T8 no cae, porque no recorre `backend/scripts`. Es el contraste que muestra que T11b mide «sin clave utilizable».

## Dirección peligrosa

Un test que debía caer y no cayó. Una caída de más se explica en el informe, y la matriz no se cambia.
