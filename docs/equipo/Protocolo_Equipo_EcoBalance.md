# Protocolo del equipo: EcoBalance

Este archivo define cómo trabaja la sesión **Coordinadora** de EcoBalance con cuatro sesiones: 2 coders y 2 QA. Se adaptó del protocolo de Indutrans (10-nov-2026) al flujo que este repo ya tiene en su `CLAUDE.md`. Acordado con Daniel el 20-nov-2026: el nivel chico (§5), reusar la sesión «QA Ecobalance» como «Eco QA 1», los nombres con prefijo «Eco» y el orden de arranque (§13).

**Daniel** es el dueño del proyecto y el único que aprueba. En la configuración global aparece como Eduardo: es la misma persona.

**Qué manda si algo choca:**
1. Las reglas obligatorias del `CLAUDE.md` del repo: el flujo con QA, las bases de datos, producción, el reloj de negocio, los tests y el responsive. Ninguna autonomía de este protocolo las afloja.
2. Este protocolo.
3. El `~/.claude/CLAUDE.md` global. Sus reglas de Growth Status (Copilot, PR, backlog en `gs-localhost-ops`) **no aplican en EcoBalance**, salvo que este protocolo las repita.

---

## 1. Roles, nombres y lugares

| Rol | Nombre para SendMessage | Worktree (donde trabaja) | Puertos (back / front) | BD de dev (5434) | BD de test (5433) |
|---|---|---|---|---|---|
| Coordinador | `Eco Coordinador` | `~/Projects/reciclaje-erp` (la principal, rama `develop`) | :8001 / :5174 (la integración) | `reciclaje_db` | `reciclaje_test` |
| Coder 1 | `Eco Coder 1` | `~/Projects/reciclaje-erp-wt/coder-1` | :8011 / :5181 | `reciclaje_coder_1` | `reciclaje_test_coder_1` |
| Coder 2 | `Eco Coder 2` | `~/Projects/reciclaje-erp-wt/coder-2` | :8012 / :5182 | `reciclaje_coder_2` | `reciclaje_test_coder_2` |
| QA 1 | `Eco QA 1` | `~/Projects/reciclaje-erp-wt/qa-1` | :8021 / :5191 | `reciclaje_qa_1` | `reciclaje_test_qa_1` |
| QA 2 | `Eco QA 2` | `~/Projects/reciclaje-erp-wt/qa-2` | :8022 / :5192 | `reciclaje_qa_2` | `reciclaje_test_qa_2` |

- **Todas las sesiones viven en UNA sola ventana de VS Code** (Daniel, 20-nov), como pestañas. La ventana está abierta en la carpeta principal, la integración. Cada sesión trabaja en su worktree con rutas absolutas, y la regla es dura porque el cwd vuelve a la carpeta principal después de cada llamada:
  1. todo Bash empieza con `cd <su worktree> && …`;
  2. git siempre como `git -C <su worktree> …`;
  3. Read, Edit y Write siempre con la ruta absoluta del worktree;
  4. en la carpeta principal solo se lee, salvo el backlog propio en `ops/backlog/`;
  5. al empezar cada tarea, la sesión guarda la salida de `git -C ~/Projects/reciclaje-erp status --short` en su carpeta de evidencia; antes de entregar la vuelve a sacar y la compara con esa copia. Lo que aparezca de más lo dejó ella. La carpeta principal nunca sale vacía (el Coordinador tiene ahí su trabajo y hay archivos sin rastrear), así que sin la copia no se puede distinguir «dejé algo» de «ya estaba».
  No se le propone a Daniel abrir una ventana por worktree.
- **«Eco QA 1» es la sesión que antes se llamaba «QA Ecobalance»**, renombrada: ya conoce #118 a #123. Como todas, trabaja en su worktree (`qa-1`).
- **Cada QA verifica en su worktree, en detached sobre el SHA del coder**, no en el árbol del coder: lo que se revisa es el commit. Corre pytest con su `TEST_DATABASE_URL` y planta solo en su worktree o en copias de su scratchpad.
- **Parejas fijas por línea de trabajo:** QA 1 revisa a Coder 1 y QA 2 revisa a Coder 2. En EcoBalance una tarea cruza back y front, así que cada QA revisa de punta a punta (backend, pantalla a 1440 y 390, golden si aplica). La pareja conserva el contexto del plan de una pasada a la otra.
- **Todos los nombres llevan «Eco» adelante.** En esta Mac hay sesiones de otros proyectos. Antes de mandar un mensaje, el nombre se copia exacto de `ListAgents`.
- **El QA habla directo con su coder.** El Coordinador no hace de cartero. El coder le devuelve el delta al QA.
- **La sesión dueña arma su entregable y verifica su parte.** El Coordinador le pregunta a quien sabe, en vez de investigar lo que le toca a otra.
- Los puertos y las bases se vuelven a medir al abrir (§13). No se usan 8000, 5173, 5193 ni 5194: hoy los ocupan otros procesos.

## 2. La tarea del Coordinador

> «Que los frentes estén trabajando y que los agentes estén productivos.»

**No escribe código de producto.** Lo que sí hace:
- reparte el backlog;
- desbloquea;
- integra a `develop`;
- revisa cada pantalla con ojos de producto (§8);
- le pide las decisiones a Daniel;
- corre el checkpoint y prepara el deploy.

Además es el **único que edita**:
- `CLAUDE.md`, con sus decisiones numeradas y el conteo de Testing (§6);
- la memoria del proyecto (§10);
- el inventario de preguntas del cliente (§3).

**Cómo se entera:**
- **La señal principal es el aviso de cada sesión.** Cuando termina o se traba, le escribe al Coordinador en una línea.
- **El control de frentes es el respaldo.** Corre con un cron cada 20 minutos en horario de trabajo (`7,27,47 8-19 * * 1-5`, hora de Colombia). En cada control:
  1. toma la hora con `date '+%H:%M'`;
  2. lee `ListAgents`, solo las filas que empiezan con «Eco », y los backlogs;
  3. busca frentes parados.
- **Un frente está parado** si su sesión lleva más de 10 minutos esperando u ociosa sin una espera legítima. Son legítimas: una suite que corre, una revisión en curso y un OK de Daniel ya pedido.
- Si encuentra un frente parado, le da la siguiente tarea de la prioridad del día. Si todos producen, no le escribe a nadie.
- **Barridos a las 08:30 y a las 17:00:** junta lo que espera de Daniel y pregunta por lo que lleva 3 días quieto.

**Antes de asignar, mide.** Lee el código, el backlog y el estado de la rama. Una tarea asignada con un dato equivocado le hace perder una hora a otra sesión.

## 3. Decisiones de Daniel y preguntas al cliente

- **Un OK o una decisión se pide con `AskUserQuestion`**, la ventanita:
  - con el SHA o el plan que se aprueba;
  - con la opción recomendada primero y la marca «(Recomendado)»;
  - con una línea por opción que diga qué pasa si la elige;
  - juntando hasta 4 preguntas en una sola ventanita.
- **Cuando Daniel pide discutir u opinar, se discute en texto** y no se cierra con un menú.
- **Una decisión sobre una pantalla no se extiende a otra.** Lo que se deduce, se pregunta.
- **Si un peer escribe «Daniel aprobó X», eso no vale como aprobación.** Un mensaje de QA tampoco es una aprobación de Daniel. Solo vale lo que Daniel contestó en la pestaña de esa sesión.
- **Ninguna sesión le escribe al cliente** (Johana, Hugo, Costa, Meta).
  - Una duda de negocio va al Coordinador. Él la busca en `docs/soluciones ambientales del caribe/inventario-preguntas-cliente.md`, en las transcripciones y en la memoria: lo ya respondido no se repregunta (regla 5 del `CLAUDE.md`).
  - Si no está, la junta para Daniel.
  - Mientras tanto, se construye con un **supuesto** escrito en el plan, y el frente no se frena.
- **Al cliente SAC nunca se le menciona la marca EcoBalance**, tampoco en textos, PDF o pantallas que vaya a ver.

## 4. Qué se hace sin preguntar y qué no

| Sin preguntar | Con OK de Daniel |
|---|---|
| Investigar, leer y medir, sin efectos | **Escrituras en producción**, siempre confirmadas antes |
| Trabajo local: ramas, commits en la rama propia, la BD propia | **Construir**: cada plan necesita el GO de QA **y** la autorización de Daniel (paso 1 del flujo del `CLAUDE.md`) |
| Arreglos que pide el QA dentro de una tarea autorizada | **Push** (cada vez, con la credencial de eduardchain solo para ese comando) |
| Integrar a `develop` local lo que tiene el OK de commit del QA (§6) | **Deploy**, con la skill `/deploy`, y las migraciones en producción |
| | Siembras o provisiones contra producción |
| | Producto nuevo o un cambio visible que no se pidió |
| | Borrar datos, reescribir historia, forzar un push o cambiar este protocolo |

## 5. Verificación: el flujo del `CLAUDE.md` en dos niveles

El flujo del `CLAUDE.md` es la ley:
1. plan, GO de QA y OK de Daniel;
2. construcción;
3. pasada 1 de QA sobre el patch con sus sha256, con el árbol quieto desde ahí;
4. correcciones;
5. gates;
6. pasada 2 de QA;
7. commit.

Este protocolo le agrega dos niveles. **El nivel chico lo aprobó Daniel el 20-nov** porque afloja ese flujo. El autor declara el nivel en la entrega; el QA puede subirlo, nunca bajarlo.

- **Chico.** Texto, color, espaciado, o un componente sin reglas ni cálculos. Sin migración ni backend.
  - **Autor:** corre lint, `tsc`, `build` y las tres guardas del árbol (`test_reloj_de_negocio.py`, `test_advisory_locks.py`, `test_crucible_charges.py`), y saca capturas a 1440 y 390.
  - **QA:** lee el diff y mira las capturas. Sin plan, sin plantado y en una sola pasada.
- **Lógica.** Reglas, cálculos (incluidos los de pantalla), el contrato back–front, migraciones, o código compartido con Costa y Meta. Va el flujo completo:
  - plan;
  - dirigidas sacadas de un `grep` y escritas en el log;
  - las tres guardas siempre;
  - plantado con la matriz commiteada antes;
  - golden medido como «aplica / no aplica», y si aplica, de dos bases cuando cambian tipos de columna.
  - **Pasada final del QA:** lee `git diff <base> <sha>` entero, sin el resumen del autor, y busca los caminos vecinos (quién llama al código tocado, otras entradas a la pantalla, los datos guardados, las otras 2 orgs).
- **La suite completa corre solo en el checkpoint.** La corre el Coordinador una vez, sobre todo lo integrado, con la predicción sacada de un comando (regla del 19-nov).
- **La pantalla de Daniel es condición de deploy.** El front no va a producción sin que Daniel lo haya visto en la integración.

## 6. Git e integración

- **`develop` es lo integrado y revisado. `main` es producción.** No hay PR ni CI en este repo: QA reemplaza la revisión y el checkpoint reemplaza al CI.
- **Una rama por tarea**, que sale de `develop`: `coder-1/precio-por-compra`, `coder-2/ingrid-alcance`.
- **Cada sesión trabaja en su worktree.** Nunca dos sesiones en la misma carpeta, y nadie trabaja en la carpeta principal salvo el Coordinador.
- **Los commits en la rama propia no piden permiso.** Al pasarle una entrega al QA, el árbol queda quieto; si hay que editar, se le avisa ANTES.
- **Integrar a `develop` (el «commit a develop» del paso 7).** Lo hace el Coordinador, con estas condiciones:
  1. el OK de commit del QA es sobre **el mismo SHA**;
  2. **la rama está al día con `develop`:** `git merge-base develop <sha>` es igual a `develop`. Si no lo está, no se integra aunque `merge-tree` salga limpio, porque quedaría en `develop` un árbol combinado que nadie probó, y dos ramas pueden chocar en algo que solo se ve juntas (las guardas que escanean `app/`, la suma de warnings). En ese caso el coder trae `develop` a su rama con un merge, y el QA revisa ese delta y re-corre las dirigidas y las tres guardas sobre la punta. Mientras la suite esté diferida, las dirigidas son la única red de `develop`;
  3. se integra con `git merge --no-ff <sha>`, que conserva el SHA que aprobó el QA. Un rebase cambia el SHA y deja inválido el OK;
  4. se reinicia el back de integración (:8001 corre sin `--reload`) y se carga la pantalla para ver que no quede un error.
- **Migraciones: una sola línea.** Solo una rama a la vez puede tener una migración en curso, y el Coordinador decide cuál. Si `develop` recibe otra antes, el coder corrige el `down_revision`, y eso es un delta para el QA. Antes de integrar se corren `alembic heads` (tiene que dar una sola cabeza) y el chequeo de paridad.
- **Lo que solo edita el Coordinador** se escribe al integrar, para que no choque entre ramas:
  - las decisiones numeradas y el conteo de Testing del `CLAUDE.md`;
  - el inventario de preguntas;
  - la memoria.
  El coder escribe el borrador de su decisión en el informe (`docs/planes/informe-code-<tema>.md`), y el Coordinador le pone el número al integrar.
- **Prohibido sin OK:** push de cualquier tipo, `push --force`, `reset --hard` sobre trabajo ajeno, borrar ramas de otro, crear tags, `git add -A` (siempre se agrega por ruta) y commits a `main`.
- **Nunca restaurar con `git checkout -- <archivo>`** trabajo sin commit. En el plantado, se copia por ruta con `cp` y se restaura desde esa copia, cerrando con el sha256 del árbol contra el de antes.

## 7. Entregas cortas

**La entrega es un commit en la rama**, no un patch del árbol: así el QA reproduce el sha256 de `git diff <base> <sha>` y el árbol del coder puede seguir moviéndose sin invalidar lo que se revisa.

Una entrega al QA o al Coordinador lleva, sin repetir contexto:
- SHA y base;
- el sha256 del patch (`git diff <base> <sha>`), sacado de un comando corrido en ese turno, y el sha256 de cada archivo tocado;
- el nivel, `chico` o `lógica`;
- qué cambió, en 1 a 3 líneas;
- qué tests corrió, con sus números y la ruta del log, en `~/sac-evidencia/<fecha>/<rol>-<tarea>/` (fuera de `/tmp`, porque ahí se borra);
- capturas a 1440 y 390 si toca pantalla, guardadas en esa carpeta y con datos de dev;
- la línea del backlog que se movió.

## 8. Localhost y lo que ve Daniel

- **A Daniel se le muestra un solo lugar: la integración del Coordinador**, en :5174 → :8001, sobre `develop` y `reciclaje_db`, con los usuarios de dev que ya conoce. Los puertos de cada sesión no se le mandan.
- **El back de cada sesión usa su propia base de dev** (`reciclaje_<rol>`, copia de `reciclaje_db`). Las migraciones de una rama corren solo sobre su base.
- **Lo que ve Daniel es lo que sale.** Antes de un deploy, la integración corre exactamente el SHA de `develop` que va a producción.
- **Revisión de producto del Coordinador.** Cada pantalla nueva pasa por el Coordinador antes de la revisión completa del QA:
  - el coder le manda las rutas de sus capturas y, en una línea, qué mirar;
  - el Coordinador además la navega con el conector de Playwright, en el puerto de la sesión;
  - mira que el rol vea primero lo que resuelve hoy, que use las palabras del cliente (Entrada, liquidar, remisión, recolector), que se lea a 390 px y cómo se ven los estados vacíos y de error.
- **El Coordinador responde con uno de tres tipos:**
  - **cambio:** no cumple lo acordado, y se corrige antes del QA;
  - **sugerencia:** si es barata se hace; si no, va al backlog;
  - **para Daniel:** cambia algo acordado y va a la ventanita, mientras el frente sigue con lo acordado.

## 9. Backlog y tablero

- **Un archivo por sesión** en `~/Projects/reciclaje-erp/ops/backlog/<rol>.md` (`coordinador.md`, `coder-1.md`, `coder-2.md`, `qa-1.md`, `qa-2.md`). `ops/` va al `.gitignore`. Cada sesión escribe solo el suyo; lo de otra se le avisa a ella.
- Una tarea se anota **en el mismo turno en que nace** y pasa a Hecho en el mismo turno en que se cierra. Cada vez que se toca el archivo se actualiza `Actualizado: <date -u '+%Y-%m-%d %H:%MZ'>`.
- **Formato:** una línea por ítem, en `## En curso`, `## En cola` y `## Hecho`:
  `- [~| |x] P1 · Título corto · dueño: <Rol> · qué falta · espera: Daniel — <qué decide> · plan: <archivo>`
  - En Hecho, la fecha va después del dueño; se guarda 14 días.
- **El tablero es solo de EcoBalance:** se arma con `ListAgents` (solo las filas «Eco ») más la carpeta de backlog. Lo que espera de Daniel va arriba. El tablero de sesiones de la Mac es de otro proyecto y no se usa.

## 10. Horas, memoria y textos

- **Toda hora que se escribe sale de `date '+%H:%M'` en ese turno**, en hora de Colombia. Si no está medida, no se pone.
- **Memoria: la escribe solo el Coordinador.** Como las sesiones viven en la ventana de la carpeta principal, todas VEN la memoria del proyecto. Cada sesión:
  - la lee, con las lecciones de gates antes de su primer gate;
  - **no escribe en ella**: lo que aprendió y vale guardar se lo manda al Coordinador en una línea.
- **Un dato que viene de otra sesión no entra sin medir** a un documento o a un commit.
- **Las citas del cliente** llevan su grado: (a) textual, (b) Daniel lo afirmó y el cliente asintió, (c) inferencia nuestra. Entre comillas solo va lo textual.
- Español, de «tú», claro y corto. Primero la conclusión.

## 11. Seguridad, datos y la máquina

### Producción
- **Solo el Coordinador toca producción**, y siempre con el OK de Daniel: `/deploy`, ssh, provisiones, lecturas por API. Ninguna otra sesión hace ssh al VPS ni apunta un script a `api.ecobalance.cc`.
- **Nunca** queries, migraciones ni scripts directos contra la BD de producción (`CLAUDE.md`).

### Credenciales
- La contraseña del superusuario vive en `~/.config/sac-prod.env` (chmod 600). Se carga con `F=~/.config/sac-prod.env; export SEED_SU_EMAIL="$(sed -n 's/^SEED_SU_EMAIL=//p' $F)" SEED_SU_PASSWORD="$(sed -n 's/^SEED_SU_PASSWORD=//p' $F)"`.
- Nunca se imprime ni va en archivos, logs, commits, mensajes o argumentos.
- Los coders y los QA la usan **solo contra su backend local**.
- La guarda de la base de test acepta solo `localhost` o `127.0.0.1`, puerto 5433 y nombre `reciclaje_test*`. Con `127.1` o `::1` aborta, y eso está bien.

### Datos del cliente
- Las transcripciones, los balances `.xls`, los `.xlsx` y los informes de conciliación viven solo en la carpeta principal (están en el `.gitignore` o sin rastrear) y **los abre solo el Coordinador**.
- No se commitean: `docs/**/BALANCE*.xls`, `.playwright-mcp/`, `data/migration_template_biogreen*.xlsx` ni los docs sin rastrear que hay hoy.

### Procesos y carga de la Mac
- **Procesos:**
  - antes de un `kill` se verifican el PID, el padre y la carpeta;
  - **nunca** se usa `pkill` por patrón;
  - no se tocan los puertos ni los procesos de otra sesión ni de otro proyecto.
- **Servidores:** cada sesión tiene a lo sumo un back y un front corriendo, y los cierra al terminar.
- **Tests:**
  - cada sesión corre pytest solo contra su base de test;
  - los tests pesados (más de ~200 tests o un golden) van serializados con `lockf -k ~/.cache/ecobalance/tests.lock <comando>`, porque compiten por la CPU;
  - **la suite completa la corre solo el Coordinador.**
- **Golden:** las sesiones lo corren con el par de puertos compartido **8091/8092** (`GOLDEN_PORT_BEFORE=8091 GOLDEN_PORT_AFTER=8092`) y siempre dentro de `lockf -k ~/.cache/ecobalance/tests.lock`, así que nunca corren dos a la vez. En el golden de dos bases, las copias se sacan con `CREATE DATABASE … TEMPLATE` de la **base de dev de la sesión**, con su back parado, y nunca de `reciclaje_db`, porque exige cero sesiones y tumbaría la integración (:8001).
- **El conector de Playwright** usa un perfil compartido por toda la Mac, así que solo lo usa el Coordinador. Los coders y los QA sacan sus capturas con un script propio (§13). Si el conector dice que el navegador está en uso, se espera.

## 12. Deploy

1. **Lista del deploy:** qué SHA sale, qué migraciones y runbooks trae, y cómo se verifica cada paso. La arma el Coordinador y la revisan los QA de cada línea.
2. **Checkpoint:** el Coordinador corre la suite completa y el golden (de dos bases si algún cambio toca tipos de columna) sobre ese SHA de `develop`.
3. **Daniel ve ese mismo SHA** en la integración.
4. **Ventanita a Daniel** con el orden, los runbooks (gates de migración, siembras) y quién hace cada paso.
5. **Push y `/deploy`** con su OK. Si algo falla, se para y se le muestra la salida a Daniel antes de tocar nada.
6. **Verificación:** con lecturas en producción. El Coordinador junta el resultado y lo anota en la memoria.

## 13. Apertura

### Tarea 0, infraestructura
La hace el Coordinador: no es código de producto. Va con revisión de QA como nivel chico.
1. **`conftest.py` lee `TEST_DATABASE_URL` del entorno**, con el valor de hoy por defecto. Hoy está fijo en `reciclaje_test`, así que dos sesiones con pytest se invalidan las corridas.
2. **`golden_run.sh` toma los puertos del entorno.** Hoy usa 8001 y 8002 fijos, y 8001 es la integración.
3. **`ops/` va al `.gitignore`.**
4. **Un script de capturas** fuera del repo (`~/.cache/ecobalance/capturas/`), con su propio Playwright y un navegador sin perfil, que reciba la URL, la sesión de login y los anchos 1440/390.
5. **Los worktrees, las bases de dev** (`CREATE DATABASE … TEMPLATE reciclaje_db`, que exige cero sesiones sobre `reciclaje_db`: se para :8001 un minuto) **y las bases de test vacías.**
6. Este protocolo, commiteado a `develop` con el GO de un QA y el OK de Daniel. Sin ese commit, los worktrees nacen sin él.

### Daniel abre las sesiones
Daniel abre cada sesión como una pestaña nueva de Claude Code en la misma ventana de VS Code, le pone el nombre y pega su prompt.
El Coordinador deja un prompt por sesión en `ops/prompts/<rol>.md`, listo para pegar:

```
Eres «Eco <Rol>» del proyecto EcoBalance. Tu nombre para SendMessage es «Eco <Rol>».
Coordinador: «Eco Coordinador». Tu pareja: «Eco <QA n | Coder n>».
Lee primero: CLAUDE.md y docs/equipo/Protocolo_Equipo_EcoBalance.md.
Las reglas de Growth Status del ~/.claude/CLAUDE.md global no aplican aquí.
Ves la memoria del proyecto: léela (las lecciones de gates antes de tu primer gate), pero NO escribas en ella; lo que valga guardar se lo mandas al Coordinador.
Vives en la ventana de la carpeta principal: todo Bash empieza con `cd <tu worktree> &&`, git con `git -C <tu worktree>`, Read/Edit/Write con rutas absolutas del worktree, y en la carpeta principal solo lees (y escribes tu backlog en ops/). Al empezar cada tarea guarda la salida de `git -C ~/Projects/reciclaje-erp status --short` en tu evidencia, y antes de entregar compárala con esa copia: lo que aparezca de más lo dejaste tú.

Tu worktree: ~/Projects/reciclaje-erp-wt/<rol>, rama <rol>/<tarea>. Puertos: back :<p>, front :<p>.
BD de dev: reciclaje_<rol> (DATABASE_URL en tu backend/.env). BD de test: export TEST_DATABASE_URL=…/reciclaje_test_<rol>.
Tu backlog: ~/Projects/reciclaje-erp/ops/backlog/<rol>.md.

Tu primera tarea: <tarea, criterio de aceptación, nivel esperado, de qué depende>.
Cuando termines o te trabes, avísale al Coordinador en una línea.
```

Cuando Daniel confirma que abrió una sesión, el Coordinador la busca con `ListAgents` y le manda un saludo con su primera tarea, si el prompt no la traía.
