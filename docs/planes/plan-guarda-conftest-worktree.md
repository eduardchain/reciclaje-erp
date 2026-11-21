# Plan: pytest desde un worktree sin `TEST_DATABASE_URL` aborta (v1.0)

Pedido del Coordinador, 20-nov, P2. Nace de la colisión de hoy: corrí un pytest en `coder-1` sin la variable, cayó en `reciclaje_test` y les hizo DROP SCHEMA a las tablas de la suite del checkpoint (r1 del deploy 2, INVÁLIDA). Nivel propuesto: **lógica**, porque `conftest.py` lo importan todas las corridas de todas las sesiones. Solo toca `backend/tests/`; `app/` no se toca.

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

### D5. Implementación

- Una función pura nueva en el conftest: `_resolve_test_database_url(environ: Mapping[str, str], conftest_path: Path) -> str`, con la regla D2 y el mensaje.
- `TEST_DATABASE_URL = _resolve_test_database_url(os.environ, Path(__file__))` reemplaza la línea 55.
- La guarda de hoy (líneas 56-61) no cambia.

## 4. Tests (`tests/test_conftest_guarda_worktree.py`)

La función se prueba con árboles falsos en `tmp_path`: `<tmp>/wt/coder-9/.git` como **archivo** y `<tmp>/main/.git` como **directorio**, cada uno con `backend/tests/conftest.py` vacío. No depende del checkout real ni de la variable del entorno que corre el test, así que pasa igual desde la principal, desde el checkpoint y desde mi worktree.

| T | Caso | Espera |
|---|---|---|
| T1 | worktree `coder-9`, sin variable | `RuntimeError`; el mensaje contiene `TEST_DATABASE_URL`, `coder-9` y `reciclaje_test_coder_9` |
| T2 | **CONTROL POSITIVO:** principal, sin variable | devuelve `…/reciclaje_test`. Sin T2, «la guarda funciona» y «aborta todo» se ven iguales |
| T3 | worktree con `TEST_DATABASE_URL=…/reciclaje_test_coder_9` | devuelve esa URL |
| T4 | worktree `checkpoint` con `TEST_DATABASE_URL=…/reciclaje_test`, explícita (D3) | devuelve esa URL |
| T5 | worktree con `TEST_DATABASE_URL=""` | aborta, igual que sin variable (el `or` de hoy trata el vacío como ausente) |
| T6 | worktree con nombre con guion y dígitos (`qa-2`) | el mensaje propone `reciclaje_test_qa_2` |
| T7 | sin `.git` en ningún padre | devuelve `…/reciclaje_test` (O2) |
| T8 | **el cableado real:** el `conftest.py` REAL se copia a `<tmp>/wt/coder-9/backend/tests/` (con `.git` de archivo) y a `<tmp>/main/backend/tests/` (con `.git` de directorio), y se ejecuta con `runpy.run_path` en un subprocess SIN la variable, con `PYTHONPATH` al `backend/` real para que importe `app` | worktree: termina con `RuntimeError` que nombra `coder-9`. **Control en el mismo test:** principal, termina sin error (crear el engine no conecta). Así T8 prueba la línea del módulo desde cualquier carpeta, también desde la principal y desde el checkpoint |

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
| P3 | detecta el worktree por `Path.cwd()` en vez de por `conftest_path` | depende de la cwd, que es el `backend/` del checkout que corre. **Desde mi worktree**, que es donde planto: todo parece worktree «coder-1», así que caen al menos T1 y T6 (el nombre sale «coder-1», no «coder-9»), T2, T7 y el control de T8. La predicción exacta se escribe en la matriz antes de plantar |
| P4 | `.git` de archivo y de directorio intercambiados | al menos T1, T2 y T8 |
| P5 | el vacío cuenta como variable presente | T5 |
| P6 | la línea del módulo sigue con `os.environ.get(...) or default` en vez de llamar a la función | T8, y solo T8: es el único que ejecuta el conftest real |

**Dirigidas:** el archivo nuevo, más una corrida corta de cualquier otro archivo para mostrar que el conftest sigue cargando (`test_org_context_dependency.py`), más las 3 guardas. Todo con la variable. Golden y parity: no aplican (cero `app/`, cero migraciones).

## 5. Lo que NO cambia

- La guarda de host, puerto y prefijo.
- La carpeta principal: sin variable sigue en `reciclaje_test`.
- `app/`, los scripts y el frontend.

## 6. Decisiones abiertas

- **O1 (Coordinador):** D3 exige agregar `export TEST_DATABASE_URL=…/reciclaje_test` a `suite.sh` antes del próximo checkpoint. Recomiendo que la línea entre antes que el merge, o en el mismo turno.
- **O2:** sin `.git` en ningún padre (una copia sin git), la regla devuelve el default de hoy. Aquí no hay CI ni copias así, y abortar no protegería nada real. Si QA prefiere fail-closed también ahí, es una línea.
