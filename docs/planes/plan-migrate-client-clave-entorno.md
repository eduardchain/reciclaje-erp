# Plan — /migrate-client: la clave del superusuario sale del entorno, nunca del chat ni de argv

- **v1.3** (23-nov). GO condicionado de QA 2 sobre la v1.2 `2b2b50a4` (veredicto `veredicto_plan_v1.2_2b2b50a4.md`, 9f32554f). C5: `seed_demo_org` no tiene `--api-url`, su flag es `--base-url`; QA 2 lo midió con el parser real en `seed_demo_org_url.log` (e4fc47b2). Con `--api-url`, argparse corta con exit 2 antes de D1. Se corrigen T5, su control y T6b, y queda escrito que ningún test de ese script corre sin `--base-url`. P8 suma T6b a lo que predice que cae (nota de QA 2).
- **v1.2** (23-nov). GO condicionado de QA 2 sobre la v1.1 `607773e2` (veredicto `veredicto_plan_v1.1_607773e2.md`, e2058ce2).
  - C3, §6.2: el control positivo exige la muestra del PYTHON, porque un subshell `( … ) &` sale en `pgrep` con el texto del comando (`pgrep_padre.log`, 02b8b88a).
  - C4, §5: P7 deja el helper y le vacía el cuerpo, en vez de borrarlo, y la caída de T5 se clasifica por su causa.
  - O1–O3: T6 en proceso afirma `SystemExit.code` y una fila en subprocess afirma el exit 1; filas «falta solo el email» y «faltan las dos», con su texto en §4.4; la fila de `seed_demo_org` en T5 no pasa `--superuser-email`.
- **v1.1** (23-nov). GO condicionado de QA 2 sobre la v1.0 `d7106867` (veredicto `veredicto_plan_v1.0_d7106867.md`, 3b7205a7). C1: §7 declara los dos casos en que argparse repite el valor antes de D1. C2: §6.2 dice cómo se mide la ausencia de la clave en el argv. Se aplican también sus observaciones 1–4: D6 con `--skip-phase`, qué agrega el paso 6, `monkeypatch.delenv` en T2 y el mensaje de D1 de usted. **D4 = (b), decisión del Coordinador**: la clave tiene una sola fuente, el entorno, en todos los scripts que llaman al API. §4.4 escribe el texto que verá quien corra `seed_demo_org` sin la variable, y T6 y P9 lo cubren.
- **v1.0** (23-nov, Eco Coder 2). Rama `coder-2/migrate-client-clave-entorno` sobre develop `d7c2af9`. Nivel **lógica** (asignado por el Coordinador): cambia scripts que corren contra producción.
- **Origen:** hallazgo de QA 1 en la pasada 1 de `635c4b3`. La skill pide la clave del superusuario por AskUserQuestion y la pasa como `--superuser-password` en los pasos 4, 6 y 8. Así queda escrita en el chat y en la línea de comandos, que `ps` muestra a cualquier usuario de la máquina.
- **Objetivo (Coordinador):** que la clave salga del entorno (`SEED_SU_EMAIL`/`SEED_SU_PASSWORD`, cargados de `~/.config/sac-prod.env` como hacen los otros scripts) y nunca del chat ni de argv, sin romper el flujo de la skill ni el `--dry-run` sin login.
- **Nada contra producción.** Las pruebas y la verificación corren contra mi backend local (:8012, BD `reciclaje_coder_2`).
- Evidencia: `~/sac-evidencia/2026-11-23/migrate-client-clave/`.

## 1. Barrido de consumidores

Comando (sobre `d7c2af9`, en `barrido.log`): `git grep -n -I -e '--superuser-password'`.

**Conteo: 11 archivos, 25 líneas.** Cada uno, con su arreglo o su razón:

| Archivo | Líneas | Qué hace hoy | Arreglo |
|---|---|---|---|
| `.claude/skills/migrate-client/SKILL.md` | 147, 212, 267 | pasos 4, 6 y 8: la clave viene de un AskUserQuestion y va por argv | §4.2 |
| `backend/scripts/migrate_org.py` | 34 (docstring), 1341 (argumento), 1413 (mensaje) | la clave SOLO entra por argv | §4.1 |
| `backend/scripts/MIGRATION.md` | 31 | el ejemplo de `--apply` la pasa por argv | §4.3 |
| `backend/scripts/seed_sac_org.py` | 23–24 (docstring), 1437, 1468 | default del entorno, pero acepta argv | D4 |
| `backend/scripts/archivar_org_sac.py` | 454 | default del entorno, acepta argv | D4 |
| `backend/scripts/load_sac_opening.py` | 1544 | default del entorno, acepta argv | D4 |
| `backend/scripts/seed_demo_org.py` | 13–15 (docstring), 1324 | `required=True`: SOLO por argv | D4 |
| `backend/tests/test_archivar_org_sac.py` | 343, 597 | `"--superuser-password", "x"` contra `seed.main()` | D4: pasan a `monkeypatch.setenv` |
| `backend/tests/test_seed_sac_settings.py` | 155 | ídem | D4: ídem |
| `backend/scripts/archive/migrate_metarecycling.py` | 15, 993, 1042 | script retirado (`archive/README.md`) | **No se toca**: no se corre, y reescribir lo archivado no protege nada |
| `backend/scripts/archive/MIGRATION_METARECYCLING.md` | 77, 116 | documentación del retirado | **No se toca**, misma razón |

Los otros consumidores que leen la clave **solo** del entorno y no cambian: `golden_capture.py`, `marcar_recolector.py`, `ronda_local.sh` y `ronda_remota.sh`. `docs/equipo/Protocolo_Equipo_EcoBalance.md:211` documenta la carga del archivo y no cambia.

El CLI de `migrate_org` no lo llama ningún otro script ni test con credenciales: `git grep migrate_org` da la skill, `MIGRATION.md`, `audit_migration_excel.py` (solo lo nombra en un docstring) y `test_clave_sin_constante.py` (T11, que corre el dry-run y la creación con un API falso, sin `--superuser-*`).

Sin otras skills afectadas: `git grep -e 'superuser-password' -e SEED_SU_PASSWORD -e sac-prod.env -- .claude/` fuera de esta skill da 0 líneas.

## 2. Lo que se midió antes de decidir

1. **argparse repite el valor de un argumento desconocido** (`argparse_eco.log`). Si se quita `--superuser-password` del parser, una invocación vieja imprime `unrecognized arguments: --superuser-password <VALOR>` en stderr, con exit 2. La skill guarda esa salida con `tee /tmp/migration-*.log`. **Quitar el argumento filtra la clave al log**, que es justo lo que se quiere evitar.
2. **El error del login no repite la clave** (`login_422_eco.log`, contra :8012 con un centinela). `/auth/login/json` con email inválido devuelve 422 con `input` = el email. Con `password: null` devuelve `input: null`, y con JSON roto, `input: {}`. Mi predicción para el JSON roto fue que repetiría el body y **falló**: devuelve `{}`. Ninguno de los tres repitió el centinela.
3. **El dry-run no toca la red ni necesita credenciales** (`dryrun_offline.log`). La plantilla `data/migration_template.xlsx` contra `127.0.0.1:9`, donde nada escucha, y sin `SEED_SU_*` en el entorno: 29 creados, 0 errores, `EXIT=0`, 0 errores de conexión y sin `Autenticando`. Mi predicción falló en el texto: el script termina con `Done.`, **no** con `DRY-RUN COMPLETADO` (ver D6).
4. **En dev el superusuario es la misma cuenta que la de `sac-prod.env`.** Medido en mi copia `reciclaje_coder_2`: un solo superusuario activo, `admin@ecobalance.com`, que es el email del archivo. Dev es una réplica de producción (`replicate_prod.sh`), así que la clave coincide hasta que alguien la cambie en producción y no se vuelva a replicar.
5. **El Bash del harness no conserva variables entre llamadas**, así que un `export` en una llamada no llega a la siguiente. La skill tiene que cargar las variables en el MISMO comando que corre el script.

## 3. Decisiones

**D1 — El argumento viejo NO se quita: se rechaza sin repetir el valor.** `--superuser-password` queda en el parser con `help=argparse.SUPPRESS` y `default=None`. Justo después de `parse_args()`, antes de leer el Excel y antes de cualquier llamada de red, si vino con valor:
- imprime en stderr `ERROR: --superuser-password ya no se acepta: en la línea de comandos la clave queda a la vista de ps y en el historial. Cárguela en SEED_SU_PASSWORD (ver ~/.config/sac-prod.env).`;
- sale con exit 2, la convención de argparse para un uso inválido;
- el mensaje **no incluye el valor**, en ninguna de las formas en que argparse lo acepta: `--superuser-password X`, `--superuser-password=X` y la abreviatura `--superuser-pass X` (`allow_abbrev` viene activo).
Que lo mande sin valor ya lo corta argparse con `expected one argument`, que no tiene valor que repetir.

**D2 — Las credenciales salen de `SEED_SU_EMAIL`/`SEED_SU_PASSWORD`.**
- La clave se lee de `os.environ` y de ningún otro lado.
- `--superuser-email` queda como override con default `os.environ.get("SEED_SU_EMAIL")`: el email no es secreto, y hoy el script ya lo imprime (`Autenticando como superuser '<email>'`).
- Con `--apply` y sin alguna de las dos, el mensaje nombra la que falta, sin valores, y sale con exit 1 como hoy.
- El dry-run no las pide ni las lee (§2.3).

**D3 — La skill no pide la clave ni el email del superusuario.**
- **Paso 1:** sale la pregunta «Email del superuser EcoBalance» (4 → 3 preguntas) y, con ella, el email personal que la skill deja escrito como valor habitual.
- **Paso 2, pre-flight:** se suma un chequeo de que el archivo exista y tenga la clave, sin mostrarla: `test -r ~/.config/sac-prod.env && grep -c '^SEED_SU_PASSWORD=.' ~/.config/sac-prod.env` debe dar `1`. Se muestra el email (`sed -n 's/^SEED_SU_EMAIL=//p'`) para que el operador vea con qué cuenta va a entrar.
- **Pasos 4 y 8:** salen el AskUserQuestion y `--superuser-email/--superuser-password`. Las variables se cargan en el mismo comando (§2.5):
  ```bash
  cd /Users/daniel.chain/Projects/reciclaje-erp/backend
  set -o pipefail
  F=~/.config/sac-prod.env
  SEED_SU_EMAIL="$(sed -n 's/^SEED_SU_EMAIL=//p' "$F")" \
  SEED_SU_PASSWORD="$(sed -n 's/^SEED_SU_PASSWORD=//p' "$F")" \
  ./venv/bin/python scripts/migrate_org.py \
    --file "$EXCEL_PATH" … --apply … 2>&1 | tee /tmp/migration-apply-….log
  echo "EXIT=$?"
  ```
  El prefijo `VAR=… cmd` pone las variables en el entorno de `migrate_org` y de nadie más: ni `tee` ni el shell que sigue las reciben. En `ps` se ven los dos `sed` con la ruta del archivo, nunca el valor.
- **Paso 4 (dev)** usa el mismo archivo por §2.4. Si dev no tiene esa cuenta, el login da 401 y el paso aborta. La skill dice entonces qué hacer: replicar o crear el superusuario local, **nunca** pedir la clave por el chat.
- **Paso 6** deja de pedir la clave y quita `--superuser-*` del comando: el dry-run es offline (§2.3, y ya lo dice la regla 8 de la propia skill). Se conserva la pregunta que confirma el nombre de la org. El título pasa de «Dry-run en PROD (validación contra DB real)» a «Dry-run final con los datos reales (offline)». Se corrige «Errores típicos: email del admin ya existe…»: un dry-run offline no lo detecta, y desde #132 D3 un email existente ya no es un error (el admin conserva su clave).
- **Qué agrega el paso 6 sobre el 3** (observación 2 de QA 2). Los dos son el mismo dry-run offline. El 6 corre sobre el Excel tal como está justo antes de producción, que el cliente puede haber tocado durante los pasos 4 y 5, y con el nombre de la org recién confirmado. Para que eso se vea, los pasos 3 y 6 imprimen el `shasum -a 256` del Excel. Si el sha no cambió, el resultado es el mismo y la skill lo dice en una línea. Si cambió, el paso 6 exige volver a la auditoría 2.5 antes de seguir, que es la regla 8 de la propia skill. No se unen porque la confirmación del nombre y el chequeo del Excel tienen que quedar inmediatamente antes de la confirmación crítica del paso 7.

**D4 — Alcance: la misma regla en los otros cuatro scripts que la aceptan por argv.** **Decidido: (b)**, por el Coordinador el 23-nov. La lectura técnica de QA 2 también fue (b).
- **(b) Elegida.** `seed_sac_org`, `archivar_org_sac`, `load_sac_opening` y `seed_demo_org` aplican D1 y D2:
  - el rechazo vive UNA vez en `seed_sac_org` (`rechazar_clave_en_argv(args)`), y `archivar_org_sac` y `load_sac_opening` ya importan `seed`;
  - `seed_demo_org` y `migrate_org` llevan su copia de 5 líneas: son scripts sueltos, y acoplar la migración genérica al seeder de SAC por un guard no vale la pena;
  - los docstrings de `seed_sac_org` y `seed_demo_org` pasan a mostrar el entorno;
  - los 3 tests de §1 cambian `--superuser-password x` por `monkeypatch.setenv(...)`. El argparse de esos scripts se arma dentro de `main()`, así que el default del entorno se evalúa en cada llamada y el `setenv` alcanza.
  Razón: el objetivo dice «nunca de argv», y un docstring que todavía enseña `--superuser-password <pwd>` invita al mismo error en los scripts que tocan producción (`seed_sac_org` en provisión, `seed_demo_org --target prod`). Ninguno de los flujos documentados pasa la clave por argv: `ronda_local.sh` y `ronda_remota.sh` usan el entorno. Así que (b) no rompe un flujo en uso.
- **(a) Mínima, descartada.** Solo `migrate_org`, la skill y `MIGRATION.md`. Los otros cuatro quedaban para un ciclo propio.

**D5 — El mensaje de error del login no cambia** (recomendado). Imprime `resp.text`. §2.2 midió las tres formas en que puede fallar y ninguna repite la clave; solo el email. Enmascararlo sería defensa en profundidad sin una fuga medida que la pida. Si QA 2 lo quiere igual: imprimir el status y el `detail` cuando sea un string, sin `input`.

**D6 — Los textos que la skill espera no existen en el script** (preexistente; recomendado arreglarlo en este ciclo). La skill espera cuatro textos que `migrate_org.py` nunca imprime (`textos_skill_vs_script.log`):
- el paso 3 y el 6 esperan `DRY-RUN COMPLETADO`;
- el 4 y el 8, `MIGRACION COMPLETADA EXITOSAMENTE`, `Balance Sheet diff: $0.00` y `9/9 OK`.
`git grep -e COMPLETAD -e EXITOSAMENTE -e '9/9' -- backend/scripts/migrate_org.py` da 0 líneas, y `balance sheet` solo aparece como la clave `is_balanced`. El script termina con `Done.` (§2.3). Con `--apply` además imprime `OK    Balance General cuadra: … (diff=…)` y `Verificacion: N OK, M FAIL`.

Además, con `… | tee log` el exit que ve el shell es el de `tee`, no el del script.

Como los pasos 3, 4, 6 y 8 se reescriben igual por D3, el criterio pasa a ser:
- `EXIT=0` con `set -o pipefail`, que vale en zsh y en bash;
- `Errores:  0`;
- en el apply, además, `OK    Balance General cuadra` y `Verificacion: N OK, 0 FAIL`.

QA 2 verificó que el script sale con 1 si hay errores o algún FAIL, así que `EXIT=0` con pipefail es un criterio real.

**Con `--skip-phase`** (observación 1 de QA 2): la verificación final solo corre si no se saltó ninguna fase (l.1600), así que no aparecen ni `Verificacion` ni `Balance General cuadra`. La skill ofrece `--skip-phase` cuando un apply falla a medias (l.282). En ese camino el criterio es `EXIT=0` + `Errores:  0`. El reporte final dice «Verificación final NO corrió (--skip-phase X): los conteos y el cuadre del balance no se comprobaron» en vez de «N OK, 0 FAIL».
Los dos modelos de reporte (líneas 166–178 y 301–319) cambian «9/9 OK» por «N OK, 0 FAIL».

Si QA 2 prefiere no tocarlo, queda como observación y los pasos conservan los textos de hoy.

## 4. Cambios por archivo

### 4.1 `backend/scripts/migrate_org.py`
- **`--superuser-password`:** `help=argparse.SUPPRESS`; rechazo de D1 inmediatamente después de `parse_args()`.
- **`--superuser-email`:** `default=os.environ.get("SEED_SU_EMAIL")`, con help «Override del email; por defecto SEED_SU_EMAIL».
- **Bloque de login:** la clave sale de `os.environ.get("SEED_SU_PASSWORD")`. El mensaje de faltante nombra `SEED_SU_EMAIL`/`SEED_SU_PASSWORD`. El orden no cambia: Excel → chequeo → login.
- **Docstring (l.25–40):** el ejemplo carga el entorno desde el archivo y sale `--superuser-password '<pwd>'`.
- **`import os`:** hoy no está (el script importa solo `sys`).

### 4.2 `.claude/skills/migrate-client/SKILL.md`
Pasos 1, 2, 4, 6 y 8 según D3, y pasos 3, 4, 6 y 8 según D6. No cambia nada más: las dos confirmaciones críticas, «nunca `--reset-org` en prod» y la clave del admin (#132 D3b) quedan como están.

Se suma una regla estricta 9: «La clave del superusuario nunca se pide por el chat ni va en un argumento. Sale de `~/.config/sac-prod.env` en el mismo comando que corre el script».

### 4.3 `backend/scripts/MIGRATION.md`
El ejemplo de `--apply` (l.24–33) carga el entorno como en D3.

De paso, el mismo bloque (l.26) y el del dry-run (l.18) dicen `--excel`, y el flag es `--file`. Con `--excel` argparse corta con `the following arguments are required: --file`. Es un preexistente, en los bloques que se reescriben. Más abajo (l.37) dice `https://api.ecobalance.com`, y el dominio es `.cc`. Se corrigen los tres y se declaran (`textos_skill_vs_script.log`, `excel_flag.log`).

### 4.4 D4 = (b): los otros cuatro scripts
- `seed_sac_org.py`: helper `rechazar_clave_en_argv(args)`. `--superuser-password` con `SUPPRESS`/`None`, y la clave se lee de `os.environ`. Docstring l.23–24.
- `archivar_org_sac.py` y `load_sac_opening.py` llaman al helper después de `parse_args()`.
- `seed_demo_org.py`: los dos argumentos dejan de ser `required=True`. Copia del rechazo, el email con default del entorno y la clave del entorno, con el mensaje de faltante. Docstring l.13–15.
- Los 3 tests de §1.

**El cambio de hábito real es `seed_demo_org`** (Coordinador). Hoy la clave es obligatoria por argv, y el script hace login también en dry-run (l.1354: `api.login(...)` corre siempre, antes de `seeder.run`), así que sin la variable no hay ningún modo que funcione. Quien lo corra como antes va a ver uno de estos dos textos, los dos con exit distinto de 0 y antes de cualquier llamada de red.

1. Con el flag viejo (`--superuser-password X`, con espacio o con «=», o su abreviatura), exit 2, sin el valor:
   ```
   ERROR: --superuser-password ya no se acepta: en la línea de comandos la clave queda a la vista de ps y en el historial. Cárguela en SEED_SU_PASSWORD (ver ~/.config/sac-prod.env).
   ```
2. Sin el flag y sin la variable, exit 1. La primera línea nombra solo lo que falta: `SEED_SU_EMAIL` cuenta como faltante si tampoco vino `--superuser-email`. Las otras líneas son iguales en los tres casos.
   - falta solo la clave: `ERROR: falta SEED_SU_PASSWORD en el entorno. La clave del superusuario ya no va por la línea de comandos.`
   - falta solo el email: `ERROR: falta SEED_SU_EMAIL en el entorno (o --superuser-email). La clave del superusuario ya no va por la línea de comandos.`
   - faltan las dos: `ERROR: faltan SEED_SU_EMAIL y SEED_SU_PASSWORD en el entorno. La clave del superusuario ya no va por la línea de comandos.`
   ```
   Córralo así, en un solo comando:
     F=~/.config/sac-prod.env
     SEED_SU_EMAIL="$(sed -n 's/^SEED_SU_EMAIL=//p' "$F")" SEED_SU_PASSWORD="$(sed -n 's/^SEED_SU_PASSWORD=//p' "$F")" ./venv/bin/python scripts/seed_demo_org.py --target dev [--apply]
   ```
El chequeo va justo después del rechazo de D1, antes de las salvaguardas de `--target prod` y de crear el `APIClient`. Usa `raise SystemExit(mensaje)`, como el resto de ese script. El ejemplo lleva `--target dev` porque es el default. La línea del docstring muestra la misma forma.

## 5. Tests

En un archivo nuevo, `backend/tests/test_migrate_org_clave_entorno.py`, con el patrón de T11 (`importlib` sobre la ruta del script, y `subprocess` donde importa la salida real de argparse). Todos llevan **control positivo**. El centinela es `CENTINELA-CLAVE-7f3a` y nunca puede aparecer en stdout ni en stderr.

| Test | Qué afirma | Control positivo |
|---|---|---|
| **T1** rechazo sin eco, `migrate_org` (subprocess, `--apply`, port 9, Excel inexistente) | parametrizado en las 3 formas de D1 (`X`, `=X`, abreviatura): exit 2, el mensaje nombra `SEED_SU_PASSWORD`, 0 centinelas; **no** imprime `no encontrado` (el rechazo va antes del Excel) | el mismo comando sin el flag llega a `no encontrado` (exit 1): sin esto, «rechaza» y «muere antes por otra causa» se verían igual |
| **T2** `--apply` sin entorno (in-process, xlsx mínimo en `tmp_path`, `monkeypatch.delenv` de las dos variables) | exit 1, el mensaje nombra la variable que falta; `APIClient.login` no se llama (monkeypatch que revienta) | con las dos variables, `login` sí se llama |
| **T3** el login usa el entorno y no lo imprime (in-process, `login` capturando y devolviendo False) | `login` recibe exactamente los valores del entorno; 0 centinelas en `capsys` | `--superuser-email otro@x` en argv gana sobre el entorno; la clave sigue saliendo del entorno |
| **T4** el dry-run no necesita entorno (in-process, la plantilla real, sin `SEED_SU_*`, `login` monkeypatcheado para reventar) | termina con `Done.`, sin llamar a `login` | — (es el control de que D2 no exige el entorno en el dry-run; T11c ya cubre el dry-run sin el flag) |
| **T5** rechazo en los otros 4 scripts (subprocess, parametrizado, con los obligatorios de cada uno: `--modo revisar`, `--file x --corte 2026-10-31 --fase saldos`, etc., y `--api-url http://127.0.0.1:9`). **En la fila de `seed_demo_org` y en su control va `--base-url http://127.0.0.1:9`**: ese script no tiene `--api-url`, y argparse cortaría con «unrecognized arguments» (exit 2) antes de D1 (C5 de QA 2). **La fila de `seed_demo_org` NO pasa `--superuser-email`** (O3 de QA 2): con `required=True` y los dos flags presentes, argparse no cortaría, el rechazo correría y P8 no se mediría | exit 2, el mensaje, 0 centinelas | el mismo comando sin el flag no imprime el mensaje de rechazo |
| **T6** `seed_demo_org` sin la variable (in-process, `monkeypatch.delenv`, `APIClient.login` monkeypatcheado para reventar), parametrizado en tres filas: falta solo la clave / falta solo el email (sin `--superuser-email`) / faltan las dos | `SystemExit.code` es el mensaje (in-process, `raise SystemExit(msg)` deja el string, no el 1; O1 de QA 2). Con una sola faltante, el mensaje nombra esa y **no** la otra; la fila «falta solo el email» atrapa un mensaje que nombre siempre `SEED_SU_PASSWORD`. Con las dos faltantes, nombra las dos. En las tres trae la línea `SEED_SU_EMAIL="$(sed …` del ejemplo y `login` no se llama | con las dos variables, `login` se llama con esos valores (capturados) y 0 centinelas en la salida |
| **T6b** `seed_demo_org` sin la variable (subprocess, sin `SEED_SU_*`, `--base-url http://127.0.0.1:9`) | exit **1** del intérprete y el texto en stderr; no hay error de conexión, porque el chequeo va antes del `APIClient` | — (T6 ya tiene el control positivo; esta fila mide lo que el in-process no puede: el código de salida real) |

**Ningún test de `seed_demo_org` corre sin `--base-url http://127.0.0.1:9`** (T5, su control, T6 y T6b). Sin el flag, el target por defecto es `dev` = `localhost:8000`, que es el backend de otra sesión.

Los 3 tests existentes que pasaban `--superuser-password x` (§1) quedan verdes con `setenv`. Es la medida de que (b) no rompe a sus llamadores.

**Plantado** (la matriz se commitea ANTES de plantar, con la predicción por fila):
- P1: el rechazo deja de cortar (sigue de largo) → cae T1.
- P2: el mensaje incluye el valor → cae T1 (centinela).
- P3: se quita el argumento del parser → cae T1 (argparse repite el valor).
- P4: el login vuelve a leer `args.superuser_password`, o sea `None` → cae T3.
- P5: el dry-run exige el entorno → cae T4.
- P6: el rechazo va DESPUÉS de leer el Excel → cae T1 por `no encontrado`.
- P7: el helper de `seed_sac_org` sigue existiendo pero no rechaza (su cuerpo queda en `return`) → cae T5 en los 3 scripts que lo usan, porque el valor se acepta y falta el mensaje (C4 de QA 2). Borrar el helper haría caer T5 por AttributeError o NameError (exit 1), o sea por un import roto, sin medir que el rechazo haga falta. El log del plantado clasifica la causa de cada caída de T5: mensaje ausente, exit ≠ 2 o traceback. **Una caída por traceback no cuenta como diagonal.**
- P8: `seed_demo_org` vuelve a `required=True` → cae T5 en su fila (argparse corta con «required» antes del rechazo), T6 y T6b (exit 2 en vez de 1; una caída de más, en la dirección barata).
- P9: `seed_demo_org` sin el chequeo de faltante (llama a `login` con `None`) → cae T6.
Respaldo por ruta y cierre con `git diff --stat` contra la base, como en los ciclos anteriores.

## 6. Verificación local (nada contra producción)

1. **El comando literal del paso 4 de la skill**, con dos cambios declarados: `--api-url http://localhost:8012` (mi backend; :8000 es de otra sesión) y la plantilla como Excel. Va contra mi BD, con `--reset-org` y una org `Plantilla TEST <fecha>`.
   - Predicción escrita antes en el log: `EXIT=0`, `Errores:  0`, `Verificacion: N OK, 0 FAIL`, `Done.`.
2. **La clave no está en el argv** (C2 de QA 2). Se mide así, en este orden:
   - **Muestreo.** El apply del punto 1 se lanza en segundo plano en el mismo comando. Mientras el python vive, un loop guarda cada 0,2 s `ps -ww -o pid=,args=` de los PID que da `pgrep -f 'scripts/migrate_[o]rg.py'` en `argv_muestras.log`. El corchete es para que `pgrep` no se encuentre a sí mismo.
   - **Control positivo, la muestra del python** (C3 de QA 2). Al menos una línea donde el primer token termina en `Python` o `python`, el segundo es `scripts/migrate_org.py` y la línea lleva `--org-name`: `grep -cE '^ *[0-9]+ +[^ ]*[Pp]ython[0-9.]* scripts/migrate_org\.py .*--org-name' argv_muestras.log` ≥ 1. Sin eso, «0 apariciones» pasa igual aunque el loop nunca haya agarrado el proceso, y el resultado no vale.
     - No basta con «una línea que traiga `migrate_org.py` y `--org-name`». Un subshell `( … ) &`, que es la forma natural de capturar `EXIT=$?` dentro del bloque, sale en `pgrep` (no es ancestro suyo) como un `/bin/zsh` cuyo argv trae el texto entero del comando, y cumpliría el control sin que el python se haya muestreado nunca (`pgrep_padre.log` de QA 2).
     - macOS reescribe el argv[0] del python del venv como `…/Python.app/Contents/MacOS/Python`, con mayúscula. Por eso el patrón no busca `venv/bin/python`, que nunca aparecería.
   - **Control de que el patrón no esté vacío.** `sed -n 's/^SEED_SU_PASSWORD=//p' ~/.config/sac-prod.env | wc -c` tiene que dar ≥ 2. Con un archivo de patrones vacío, `grep -f` no encuentra nada, y el conteo daría 0 en el vacío.
   - **El conteo, DESPUÉS del loop** y con la clave fuera de todo argv: `grep -cFf <(sed -n 's/^SEED_SU_PASSWORD=//p' ~/.config/sac-prod.env) argv_muestras.log` → 0. Por la sustitución de procesos, en el argv del `grep` queda la ruta `/dev/fd/N`, no el valor. Un `grep -F "$CLAVE"` mientras corre el loop haría que `ps` capturara la clave en el argv del propio `grep`.
   - El mismo conteo sobre el log del `tee` del punto 1 → 0.
   - **`ps -E` NO se corre**: escribiría al log el entorno del proceso, con la clave.

   El entorno del proceso lo ven el mismo usuario y root. El mismo usuario ya puede leer `~/.config/sac-prod.env` (chmod 600, suyo), así que no le muestra nada nuevo. Se declara en §7.
3. **Una invocación vieja**, con `--superuser-password <centinela>`, contra :8012: exit 2 y 0 centinelas en el log del `tee`.
4. **El paso 6 nuevo**, sin credenciales: `EXIT=0`.
5. **Limpieza:** la org TEST se da de baja con `DELETE /system/organizations/{id}`, con log y conteo antes/después. Es una escritura en mi BD local, y se revierte.

## 7. Lo que no cubre

- **Dos formas mal escritas que argparse corta ANTES de D1 repitiendo el valor** (C1 de QA 2, medido en su `argparse_bordes.log` con el parser reducido, `SUPPRESS` y un centinela):
  - un typo del flag, por ejemplo `--superuser-pasword X` o `--superuser-pasword=X`: `unrecognized arguments: --superuser-pasword <VALOR>`, exit 2;
  - el prefijo ambiguo con «=», `--superuser=X`: `ambiguous option: --superuser=<VALOR> could match …`, exit 2. Sin «=» (`--superuser X`) no lo repite.
  Es el mismo eco de §2.1. Con `tee`, va al log. D1 cubre la forma exacta y la abreviatura, con espacio y con «=» (0 centinelas en las cuatro), y los dos casos sin valor (`expected one argument`, `required: --file`) tampoco lo repiten.
  No se cierra en este ciclo porque ninguno de los dos llega desde un flujo documentado: después de este cambio la skill, `MIGRATION.md` y los docstrings ya no escriben ningún `--superuser-*` con clave, así que solo pasa si alguien la tipea a mano mal escrita. Cerrarlo exige reemplazar `parser.error` por uno que no imprima los argumentos, en los cinco scripts. Queda como opción: si se hace, va con su fila en T1 y su plantado.
- **El entorno del proceso** lo ven el mismo usuario (`ps -E`) y root. Es lo mismo que pasa con el archivo. Lo que se cierra es argv, que `ps` muestra a **todos** los usuarios, y el chat.
- **Los logs `/tmp/migration-*.log`** quedan donde están. No llevan la clave: §2.2 y T3.
- **Producción:** si alguien cambia ahí la clave del superusuario y no vuelve a replicar, dev conserva la vieja y el paso 4 da 401 hasta replicar. Es el comportamiento correcto: la skill aborta y nadie pide la clave por el chat.
- **`archive/`** no se toca (§1).

## 8. Gates (nivel lógica)

- **Lint:** `ruff` de los archivos tocados.
- **Dirigidas por grep**, con el comando en el log: los tests que importan o corren alguno de los scripts tocados (`git grep -l -e migrate_org -e seed_sac_org -e archivar_org_sac -e load_sac_opening -e seed_demo_org -- backend/tests`), más el archivo nuevo. Las guardas `test_reloj_de_negocio.py`, `test_advisory_locks.py` y `test_crucible_charges.py` corren igual, aunque `app/` y `frontend/src` no se tocan.
- **Plantado** con la matriz de §5.
- **Verificación local** de §6, a archivo.
- **Golden, parity y capturas: no aplican.** No se toca `app/`, ni modelos, migraciones o frontend.
- **Suite completa:** diferida al checkpoint. Hoy corre la de `d7c2af9` y nada entra a develop hasta después del deploy.
