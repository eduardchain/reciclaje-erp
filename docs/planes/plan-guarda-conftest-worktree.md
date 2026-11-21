# Plan: pytest desde un worktree sin `TEST_DATABASE_URL` aborta (v1.1)

- **v1.1** (GO de QA 1 sobre v1.0 `2498040`, con 2 condiciones): C1 hace que `schema_parity_check.py` use la MISMA regla (D5, D6, T9, P7). C2: T8 corre con `PGHOSTADDR` no ruteable, medido (D7). Además: O1 queda como condición del merge, confirmada por el Coordinador, y §5 declara el riesgo residual.

Pedido del Coordinador, 20-nov, P2. Nace de la colisión de hoy: corrí un pytest en `coder-1` sin la variable, cayó en `reciclaje_test` y les hizo DROP SCHEMA a las tablas de la suite del checkpoint (r1 del deploy 2, INVÁLIDA). Nivel: **lógica** (acordado con QA 1), porque `conftest.py` lo importan todas las corridas de todas las sesiones. Toca `backend/tests/` y `backend/scripts/schema_parity_check.py`; `app/` no se toca.

## 1. Qué pasa hoy

`backend/tests/conftest.py:54-61`, a nivel de módulo:

- `TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL") or _DEFAULT_TEST_DATABASE_URL`, que es `reciclaje_test`.
- Una guarda fail-closed rechaza las URL que no sean `localhost` o `127.0.0.1`, puerto 5433, con base `reciclaje_test*`.

La guarda protege contra **dónde** apunta la URL, no contra **quién** la usa: sin la variable, cualquier checkout cae en `reciclaje_test`.

## 2. Un hecho que cambia el pedido (medido antes de diseñar)

El pedido dice que «desde la carpeta principal, sin la variable, sigue siendo `reciclaje_test`». Pero **la suite del checkpoint NO corre desde la principal**: corre desde el worktree `~/Projects/reciclaje-erp-wt/checkpoint` y sin la variable.

- `~/sac-evidencia/2026-11-20/checkpoint-deploy2/suite.sh`: `cd $WT/backend` con `WT=…/reciclaje-erp-wt/checkpoint`, y el log escribe «BD de test: reciclaje_test (default)».
- La r3 viva, PIDs 59657/59658: cwd `…/reciclaje-erp-wt/checkpoint/backend`, sin `TEST_DATABASE_URL` en su entorno.

Una regla «worktree sin variable → aborta», sin más, tumba la próxima suite del checkpoint. El plan lo resuelve en D3.

## 3. Qué cambia

### D1. Cómo se detecta el worktree

Por el **checkout del propio `conftest.py`**, no por la cwd del shell:

- Desde `Path(__file__).resolve()` se sube por los padres hasta el primer `.git`.
- Si `.git` es un **archivo** (`gitdir: …/.git/worktrees/<nombre>`), el checkout es un worktree, y su nombre es el de la carpeta que contiene ese `.git` (`coder-1`, `qa-1`, `checkpoint`).
- Si `.git` es un **directorio**, es la carpeta principal.

Medido: `reciclaje-erp-wt/coder-1/.git` es un archivo de 74 bytes con `gitdir: …/.git/worktrees/coder-1`, y `reciclaje-erp/.git` es un directorio.

**Por qué el archivo del conftest y no el rootdir de pytest ni la cwd:**

- La guarda tiene que correr al importar el conftest, igual que la de hoy, antes de que exista el engine. Ahí todavía no hay objeto `config`.
- `__file__` es siempre el checkout que se está probando, con cualquier cwd y cualquier ruta que se le pase a pytest. Desde la principal, `pytest ../reciclaje-erp-wt/coder-1/backend/tests` carga el conftest del worktree, y ese es el que decide.
- Una carpeta llamada `reciclaje-erp-wt` sería un nombre; el `.git` de archivo es la estructura de git. Un worktree creado en otra carpeta también queda cubierto.

### D2. La regla

| Checkout | `TEST_DATABASE_URL` | Resultado |
|---|---|---|
| principal (`.git` directorio) | ausente o vacía | `reciclaje_test`, como hoy |
| principal | presente | la variable, como hoy |
| worktree (`.git` archivo) | **ausente o vacía** | **ABORTA** |
| worktree | presente | la variable, como hoy |
| sin `.git` en ningún padre | ausente | `reciclaje_test`, como hoy (O2) |

Después de resolver la URL, la guarda de hoy corre igual, sin cambios: host, puerto y prefijo `reciclaje_test`.

**El mensaje de aborto** nombra la variable, el worktree y la base de la sesión según el protocolo (§1, tabla de sesiones: `reciclaje_test_<rol>` con el guion como guion bajo). Por ejemplo:

```
Este pytest corre desde el worktree «coder-1» y no tiene TEST_DATABASE_URL: sin la variable caería en
reciclaje_test, la base de la suite del checkpoint, y la recrearía con DROP SCHEMA.
Exporta la de tu sesión en el mismo comando:
  TEST_DATABASE_URL=postgresql://admin:test_password@localhost:5433/reciclaje_test_coder_1
```

Es un `RuntimeError` al importar el conftest, como la guarda de hoy. pytest lo muestra como «ImportError while loading conftest» con el mensaje, y sale con código 4.

### D3. El checkpoint declara su base

El worktree `checkpoint` es el dueño legítimo de `reciclaje_test`, así que lo dice en voz alta: `suite.sh` exporta `TEST_DATABASE_URL=postgresql://admin:test_password@localhost:5433/reciclaje_test` antes del pytest. Es una línea en el script del Coordinador, que no está en el repo.

- La regla queda **una sola**: desde un worktree se nombra la base, siempre. No hay excepción por nombre de carpeta.
- Si el arreglo entra antes que la línea, la próxima suite del checkpoint aborta en el primer segundo, con el mensaje, y **sin tocar ninguna base**. Es fail-closed y barato.
- La alternativa descartada era una excepción para la carpeta `checkpoint`: un nombre mágico más en el conftest, y cualquier sesión que se llamara igual heredaría el permiso.

### D4. `--collect-only` también aborta

La guarda corre al importar el conftest, y `--collect-only` lo importa. Que aborte también ahí es deliberado:

- Es una regla sin ramas. Distinguir `--collect-only` exigiría mover la guarda a un hook (`pytest_sessionstart` o el fixture `db_session`) y dejar el engine creado con la base equivocada mientras tanto.
- `--collect-only` no toca la base, pero el conteo de una predicción lo corre la misma sesión que después corre los tests. Si falta la variable al contar, va a faltar al correr: mejor enterarse al contar.
- Costo: contar tests desde un worktree exige la variable, que el protocolo ya exige para todo pytest (línea 265).

### D5. Una sola definición de la regla, con dos consumidores (C1)

La regla va en un módulo nuevo, `backend/tests/_test_db_url.py`, con una función `resolve_test_database_url(environ: Mapping[str, str], anchor: Path) -> str`:

1. Busca el checkout subiendo desde `anchor` hasta el primer `.git` (D1).
2. Aplica la tabla de D2. Si aborta, `RuntimeError` con el mensaje de D2.
3. Aplica la guarda de hoy (localhost o 127.0.0.1, puerto 5433, prefijo `reciclaje_test`), que se MUDA aquí. Hoy existe dos veces: `conftest.py:56-61` y `schema_parity_check.py:236-241`.

Consumidores, los dos con una sola línea:

- `conftest.py`: `TEST_DATABASE_URL = resolve_test_database_url(os.environ, Path(__file__))` reemplaza las líneas 54-61.
- `schema_parity_check.py`: lo mismo con su propio `__file__`. Reemplaza las líneas 62-65 y la guarda de 236-241. Así, desde un worktree sin la variable, aborta al importar, antes de crear ningún engine.

Por qué `tests/` y con guion bajo:

- El parity ya pone `backend/` en `sys.path` (línea 51) e importa `app`, así que `from tests._test_db_url import …` resuelve sin tocar nada más. `tests/` ya es un paquete (`__init__.py`).
- `pytest.ini` tiene `python_files = test_*.py`, así que `_test_db_url.py` no se recolecta como test.
- No va en `app/`: es infraestructura de test, y `app/` es lo que va a producción.

### D6. Por qué el parity entra en este ciclo (C1)

El parity hace DROP SCHEMA + `create_all` sobre la base de test, y hoy resuelve la URL con el mismo `environ.get(...) or default`. Corrido desde un worktree sin la variable, le borra la base a la suite del checkpoint: la misma clase de la colisión de hoy, y peor, porque es un DROP SCHEMA directo. Dejarlo fuera serían dos copias de la regla, una con el agujero (#102).

Medido con `git grep` (lo verificó QA 1): ningún otro archivo de `tests/` ni de `scripts/` arma una conexión a la base de test. Los consumidores son exactamente estos dos.

### D7. Ningún test conecta a `reciclaje_test`, ni por accidente (C2)

T8 y T9 ejecutan el conftest y el parity REALES en un subprocess, y su caso «principal» resuelve al default, `reciclaje_test`, que es la base del checkpoint.

- Hoy eso es inocuo: a nivel de módulo, el conftest solo hace `create_engine` (perezoso) y `sessionmaker`, y los DROP SCHEMA viven en fixtures (`conftest.py:105` y `:134`). Pero si mañana alguien agrega a nivel de módulo algo que conecte, T8 tocaría la base del checkpoint desde cualquier sesión.
- Por eso los subprocess de T8 y T9 corren con `PGHOSTADDR=0.0.0.1 PGCONNECT_TIMEOUT=1`, en los dos casos, worktree y principal. Se mantiene la ejecución completa del conftest real en los dos casos, y ninguna conexión puede salir de la máquina hacia 5433.
- **Medido** (`~/sac-evidencia/2026-11-20/coder-1-plan-guarda-conftest/medir_pghostaddr.log`): libpq respeta `PGHOSTADDR` aunque la URL de SQLAlchemy traiga `localhost` explícito.
  - Sin variables, conecta a `reciclaje_test_coder_1` en 0,08 s (control).
  - Con `PGHOSTADDR=10.255.255.1`: «timeout expired», 2,03 s.
  - Con `PGHOSTADDR=0.0.0.1`: «No route to host», 0,04 s.
  - La medición conectó solo a la base de esta sesión.
- Se elige esta vía y no la otra que proponía QA (comprobar solo el VALOR en la principal) porque prueba más: el cableado real se ejecuta en los dos casos, y una conexión a nivel de módulo deja de ser silenciosa (el control de T8 fallaría con `OperationalError` hacia 0.0.0.1, sin tocar ninguna base).

## 4. Tests (`tests/test_conftest_guarda_worktree.py`)

La función (`tests._test_db_url.resolve_test_database_url`) se prueba con árboles falsos en `tmp_path`: `<tmp>/wt/coder-9/.git` como **archivo** y `<tmp>/main/.git` como **directorio**, cada uno con `backend/tests/conftest.py` vacío. No depende del checkout real ni de la variable del entorno que corre el test, así que pasa igual desde la principal, desde el checkpoint y desde mi worktree.

| T | Caso | Espera |
|---|---|---|
| T1 | worktree `coder-9`, sin variable | `RuntimeError`; el mensaje contiene `TEST_DATABASE_URL`, `coder-9` y `reciclaje_test_coder_9` |
| T2 | **CONTROL POSITIVO:** principal, sin variable | devuelve `…/reciclaje_test`. Sin T2, «la guarda funciona» y «aborta todo» se ven iguales |
| T3 | worktree con `TEST_DATABASE_URL=…/reciclaje_test_coder_9` | devuelve esa URL |
| T4 | worktree `checkpoint` con `TEST_DATABASE_URL=…/reciclaje_test`, explícita (D3) | devuelve esa URL |
| T5 | worktree con `TEST_DATABASE_URL=""` | aborta, igual que sin variable (el `or` de hoy trata el vacío como ausente) |
| T6 | worktree con nombre con guion y dígitos (`qa-2`) | el mensaje propone `reciclaje_test_qa_2` |
| T7 | sin `.git` en ningún padre | devuelve `…/reciclaje_test` (O2) |
| T8 | **el cableado real del conftest:** el `conftest.py` REAL se copia a `<tmp>/wt/coder-9/backend/tests/` (con `.git` de archivo) y a `<tmp>/main/backend/tests/` (con `.git` de directorio), y se ejecuta con `runpy.run_path` en un subprocess SIN la variable, con `PYTHONPATH` al `backend/` real y `PGHOSTADDR=0.0.0.1 PGCONNECT_TIMEOUT=1` (D7) | worktree: `RuntimeError` que nombra `coder-9`. **Control en el mismo test:** principal, termina sin error. El docstring dice que el control depende de que el módulo no conecte, y que `PGHOSTADDR` hace que, si un día conecta, falle hacia 0.0.0.1 y no toque `reciclaje_test` |
| T9 | **el cableado real del parity (C1):** `schema_parity_check.py` REAL se copia a `<tmp>/wt/coder-9/backend/scripts/` y a `<tmp>/main/backend/scripts/`, y se ejecuta en un subprocess SIN la variable, con el mismo `PYTHONPATH` y el mismo `PGHOSTADDR` | worktree: sale con error y el mensaje de D2 (`coder-9`), **antes** de crear un engine (en la salida no hay `OperationalError` ni la línea «Test (create_all):»). **Control:** principal, pasa la resolución y llega a conectar; falla con `OperationalError` hacia 0.0.0.1. Eso prueba que la resolución NO abortó, y que nada salió hacia 5433 |
| T10 | la guarda que se muda (D5): con variable a `localhost:5434/reciclaje_db`, a `127.0.0.1:5433/otra` y a `otrohost:5433/reciclaje_test`, desde la principal y desde un worktree | `RuntimeError` del mensaje de hoy en los 6 casos. Control: `localhost:5433/reciclaje_test_coder_9` pasa |

**Gate end-to-end** (evidencia, no test), con subprocess desde mi worktree:

- sin la variable: `env -u TEST_DATABASE_URL ./venv/bin/pytest --collect-only -q tests/test_conftest_guarda_worktree.py` → exit 4 y el mensaje en la salida;
- **control:** el mismo comando con la variable → exit 0 y el conteo.

Sin el control, un exit 4 podría venir de cualquier error de import. El gate repite lo que T8 prueba, pero con pytest de verdad y el código de salida que va a ver una sesión.

Desde la carpeta principal **no** corro nada: es la integración del Coordinador. Lo cubren T2 y T7.

**Plantado** (la matriz se commitea antes de plantar):

| P | Defecto | Cae |
|---|---|---|
| P1 | la función ignora el worktree, como hoy | T1, T5, T6 |
| P2 | aborta siempre que falte la variable, también en la principal | T2, T7 |
| P3 | detecta el worktree por `Path.cwd()` en vez de por `conftest_path` | depende de la cwd, que es el `backend/` del checkout que corre. **Desde mi worktree**, que es donde planto: todo parece worktree «coder-1», así que caen al menos T1 y T6 (el nombre sale «coder-1», no «coder-9»), T2, T7 y los controles de T8 y T9. La predicción exacta se escribe en la matriz antes de plantar |
| P4 | `.git` de archivo y de directorio intercambiados | al menos T1, T2, T8 y T9 |
| P5 | el vacío cuenta como variable presente | T5 |
| P6 | el conftest sigue con `os.environ.get(...) or default` en vez de llamar a la función | T8, y solo T8: es el único que ejecuta el conftest real |
| P7 | el parity sigue con `os.environ.get(...) or default` (sus líneas 62-65 de hoy) | T9, y solo T9 |
| P8 | `_test_db_url` pierde la guarda de host, puerto y prefijo (la que se muda en D5) | T10 |

**Dirigidas:** el archivo nuevo, más una corrida corta de cualquier otro archivo para mostrar que el conftest sigue cargando (`test_org_context_dependency.py`), más las 3 guardas. Todo con la variable. Además, el parity real corrido una vez desde mi worktree CON la variable, que tiene que dar DIFF CERO como hoy. Golden: no aplica (cero `app/`, cero migraciones).

## 5. Lo que NO cambia, y el riesgo que queda

- La guarda de host, puerto y prefijo: se muda a `_test_db_url.py` sin cambiar su regla (T10).
- La carpeta principal: sin variable sigue en `reciclaje_test`.
- `app/` y el frontend.
- **Riesgo residual, deliberado (D3):** la guarda exige NOMBRAR una base, no que sea la PROPIA. Desde `qa-1` se puede exportar `…/reciclaje_test`, o la base de otra sesión, y pasa. Es el precio de no tener excepciones por carpeta. Lo que cierra es el olvido, el caso de hoy; no cierra un error de tipeo en el nombre ni una decisión deliberada.

## 6. Decisiones

- **O1, resuelta. CONDICIÓN DEL MERGE:** antes de integrar el arreglo, `suite.sh` del checkpoint exporta `TEST_DATABASE_URL=postgresql://admin:test_password@localhost:5433/reciclaje_test` de forma explícita. El Coordinador lo aceptó (20-nov), lo cumple antes de integrar y lo confirma por escrito al hacerlo. No toca el script de la r3 mientras corre. Sugerencia de QA 1: que haga además un grep de sus otros scripts que lancen pytest o el parity desde un worktree.
- **O2, resuelta con QA 1:** sin `.git` en ningún padre, devuelve el default de hoy. Aquí no hay CI ni copias sin git, y fail-closed ahí no protege nada real.
- **P3:** su predicción exacta se escribe en la matriz antes de plantar, porque depende de la cwd.
