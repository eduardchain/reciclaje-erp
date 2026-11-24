# Matriz de plantado — /migrate-client: la clave del superusuario sale del entorno

- Plan: `plan-migrate-client-clave-entorno.md` v1.3 (`c7100ef`, sha b9703154), con GO de QA 2 y autorización de Daniel (vía el Coordinador, 23-nov).
- Se commitea ANTES de construir y de plantar. La columna «cae» es la predicción y no se reescribe: si una fila difiere, se anota debajo con su causa.
- Tests: `backend/tests/test_migrate_org_clave_entorno.py`, archivo nuevo. Se corren además los tres archivos que el ciclo modifica o que corren estos scripts: `test_clave_sin_constante.py` (T11), `test_archivar_org_sac.py` y `test_seed_sac_settings.py`. Bajo ningún P se predice que caiga uno de esos tres.
- Respaldo por ruta. El cierre es absoluto: `git diff --stat` y sha256 de cada archivo contra el árbol construido, no contra el respaldo.

## Nombres de los tests

| Id | Test |
|---|---|
| T1×3 | `test_t1_rechazo_sin_eco[espacio]`, `[igual]`, `[abreviatura]` |
| T1c | `test_t1_control_sin_flag_llega_al_excel` |
| T2×3 | `test_t2_apply_sin_entorno[falta_clave]`, `[falta_email]`, `[faltan_las_dos]` |
| T2c | `test_t2_control_con_entorno_llama_login` |
| T3a | `test_t3_login_usa_el_entorno_sin_imprimirlo` |
| T3b | `test_t3_email_por_argv_gana_y_la_clave_sigue_del_entorno` |
| T4 | `test_t4_dry_run_sin_entorno_no_llama_login` |
| T5×4 | `test_t5_rechazo_en_los_otros_scripts[seed_sac_org]`, `[archivar_org_sac]`, `[load_sac_opening]`, `[seed_demo_org]` |
| T5c×4 | `test_t5_control_sin_flag_no_rechaza[...]`, los mismos cuatro |
| T6×3 | `test_t6_seed_demo_sin_variable[falta_clave]`, `[falta_email]`, `[faltan_las_dos]` |
| T6c | `test_t6_control_con_entorno_llama_login` |
| T6b | `test_t6b_seed_demo_exit_1_real` |

Las filas de T5 corren sin `SEED_SU_*` en el entorno. La de `seed_demo_org` usa `--base-url http://127.0.0.1:9` y no pasa `--superuser-email` (C5 y O3 del plan).

## Predicción

| P | Defecto plantado | Cae | Causa esperada |
|---|---|---|---|
| P1 | `migrate_org`: el rechazo de D1 no corta (`pass` en vez de `sys.exit(2)`) | T1×3 | mensaje ausente; sigue al Excel inexistente: `no encontrado`, exit 1 |
| P2 | `migrate_org`: el mensaje del rechazo incluye el valor | T1×3 | centinela en stderr (1 por fila) |
| P3 | `migrate_org`: se quitan el `add_argument("--superuser-password")` y el bloque del rechazo | T1×3 | argparse: `unrecognized arguments: … <centinela>`, exit 2, mensaje ausente y centinela presente |
| P4 | `migrate_org`: la clave del login sale de `args.superuser_password` (None) y no del entorno | T2[falta_email], T2c, T3a, T3b | con la clave en el entorno igual sale por «falta SEED_SU_PASSWORD» y `login` no se llama; en T2[falta_email] el mensaje nombra también la clave, que esa fila exige que NO nombre |
| P5 | `migrate_org`: el dry-run también exige el entorno | T4 | exit 1 por credenciales faltantes, sin `Done.` |
| P6 | `migrate_org`: el rechazo va DESPUÉS de leer el Excel | T1×3 | `no encontrado`, exit 1, mensaje ausente |
| P7 | `seed_sac_org.rechazar_clave_en_argv`: existe y su cuerpo es `return` (C4) | T5[seed_sac_org], T5[archivar_org_sac], T5[load_sac_opening] | mensaje ausente: el valor se acepta y el script sigue. Salidas: `seed_sac_org` y `archivar_org_sac`, «Faltan credenciales», exit 1; `load_sac_opening`, `FileNotFoundError` al leer `--file`, exit 1 |
| P8 | `seed_demo_org`: los dos `--superuser-*` vuelven a `required=True` | T5[seed_demo_org], T6×3, T6c, T6b | argparse `the following arguments are required`, exit 2, antes de D1 y del chequeo; T6b cae de más (exit 2 en vez de 1, dirección barata) |
| P9 | `seed_demo_org`: sin el chequeo de faltantes (llama a `login` con None) | T6×3, T6b | T6: el `login` monkeypatcheado revienta («no debía llamarse»); T6b cae de más (nota de QA 2 sobre la v1.3): `login` va contra 127.0.0.1:9, revienta con un error de conexión (exit 1 con traceback) y falta el texto en stderr |

## Cómo se clasifica cada caída (C4 del plan)

El log del plantado imprime, por cada test caído, la línea de `--tb=line` y una de tres causas:
- **mensaje ausente**: el texto esperado no está. El script siguió de largo o cortó por otro lado: argparse, otra validación, o un traceback **posterior** que no nombra el código plantado, como el `FileNotFoundError` de `load_sac_opening` bajo P7.
- **exit ≠ esperado**, con el mensaje presente.
- **traceback del plantado**: `AttributeError`, `NameError`, `ImportError` o `SyntaxError` que nombra la función o el módulo tocado. **Esta no cuenta como diagonal**: es un import roto, no la falta del comportamiento.

Una fila es diagonal si cae exactamente lo predicho, por la causa predicha y ninguna por «traceback del plantado». Lo que caiga de más se anota con su causa; lo que no caiga y estaba predicho es la dirección peligrosa y se reporta antes de seguir.
