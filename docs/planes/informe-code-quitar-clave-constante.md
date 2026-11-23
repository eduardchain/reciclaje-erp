# Informe: quitar el reseteo y el alta con clave constante

- Plan: `plan-quitar-clave-constante.md` v1.2 (`062747e`), con GO de QA 1. Versiones anteriores: v1.0 `f716855` y v1.1 `453da28`. La v1.2 cambia D3b por decisión de Daniel, vía el Coordinador.
- Nivel: lógica (contrato del back y permisos).
- Rama `coder-1/clave-constante` sobre develop `161b204`.
  - Código: `635c4b3` (construcción), `1123bce` (C1 y O1–O3 de la pasada 1) y `2ed7bb2` (delta de la v1.2).
  - Matrices: `e28bf7b` (r1, sobre `1123bce`) y `ffd6fbf` (r2, sobre `2ed7bb2`). Cada una se commiteó antes de plantar.
- Cero migraciones.
- Evidencia: `~/sac-evidencia/2026-11-20/coder-1-clave-constante/`.

## 1. Qué cambió

**Backend**
- **D1, el reseteo desde Usuarios** (`POST /organizations/{org}/members/{user}/reset-password`).
  - Recibe `{new_password}` (`ResetMemberPasswordRequest`, mínimo 6, calco de `ChangePassword` y #85).
  - Responde `{"message": "Contraseña actualizada"}` y la clave nunca vuelve.
  - `user_service.reset_password(db, user_id, new_password)` hashea la clave recibida. Se fue la constante `123456`.
- **D2, el alta desde Usuarios.** `CreateUserWithMembership.password` es obligatorio, con mínimo 8 (el de `UserCreate`). El usuario nace con esa clave. Se fueron el `12345678` fijo y el reseteo posterior a `123456`.
- **D3, la org nueva de Sistema.** `SystemOrgCreate.admin_password` es opcional, con mínimo 8 y máximo 100.
  - Si el email del admin es nuevo y falta la clave, responde 400 «admin_password es requerido cuando el email no existe».
  - Si el email ya existe, la clave se ignora y no se pisa.
  - La respuesta (`SystemOrgResponse`) no la lleva.
- **D5, reseteo entre organizaciones (H1).** Si el objetivo también es miembro de otra org ACTIVA, responde 403 «Este usuario también pertenece a otra organización: el reseteo lo hace soporte (Sistema → Usuarios)».
  - El predicado es `user_in_other_active_org`, con su versión de lista `users_in_other_active_org`: una sola consulta con join a `Organization.is_active`.
  - `get_user_org_count` NO se tocó: decide si quitar a un miembro borra al usuario (C2 de QA).
  - El listado de miembros gana `in_other_active_org`, calculado en una sola consulta.
- **D6, auditoría por log.** `logger.warning("member_password_reset org_id=… actor_id=… actor_email=… target_id=… target_email=…")`, sin la clave.
- Orden de los chequeos del reseteo:
  1. alcance de recolector (403);
  2. admin (403);
  3. objetivo superusuario (403);
  4. objetivo que no es miembro (404);
  5. D5 (403);
  6. reseteo.
  Los 403 que existían se conservan (D8).

**`migrate_org.py`, la skill `/migrate-client` y MIGRATION.md (D3b, v1.2)**
- La clave del admin nuevo la genera el script al azar, en memoria, con `secrets.token_urlsafe(32)` (43 caracteres). Va en el `POST /system/organizations`, solo en la rama que hace el POST: ni el dry-run ni una org reusada la generan.
  - No se imprime, no se escribe en archivo ni en log, y no viaja por argumento.
  - El print de error reemplaza la clave por `***`, porque un 422 de FastAPI refleja el payload en `input`.
- El admin nuevo nace sin una clave utilizable. El mensaje del 201 y el reporte final de la skill lo dicen en sus dos ramas:
  - si era nuevo, se le pone la real desde Sistema → Usuarios → Resetear contraseña (#85), y en el reporte de la skill eso va como **PASO PENDIENTE de Daniel**;
  - si el email ya existía, conserva la suya.
- Sale todo lo de la v1.1: `MIGRATE_ADMIN_PASSWORD`, el archivo `~/.ecobalance/migrate_admin_password`, los pasos 6.0 y 8.1 de la skill, `migrate_skill_start` y la excepción declarada a la regla de credenciales. SKILL.md y MIGRATION.md se volvieron a `161b204` y recibieron solo los textos nuevos.
- `seed_demo_org.py`: se corrigió el comentario que describía el «123456 hardcoded».

**Frontend**
- `UsersPage.tsx`:
  - Diálogo de alta con clave y confirmación (mínimo 8) y el texto «Entrégale esta contraseña en persona…».
  - Diálogo de reseteo con el patrón #85: clave, confirmación (mínimo 6) y el aviso de que las sesiones siguen válidas 7 días.
  - Con `in_other_active_org`, el ítem «Resetear Contraseña» sale deshabilitado, con la nota «También pertenece a otra organización: el reseteo lo hace soporte».
- `SystemOrganizationsPage.tsx`: campo de clave del admin («solo si es nuevo», mínimo 8, «si el email ya existe se ignora»). Cerrar el diálogo limpia todos los campos.
- `services/roles.ts`, `hooks/useRoles.ts` y `types/`: los cuerpos nuevos.

## 2. Tests

`tests/test_clave_sin_constante.py`, 16 tests:
- T1–T10 del plan.
- T11a[éxito] y T11a[error]: la clave no se filtra. El falso del error refleja la clave en `input` como FastAPI. Controles: el payload la lleva con longitud 8–100, el mensaje nombra las dos ramas, y el error sale con `***`.
- T11a2: dos corridas dan dos claves distintas.
- T11b: con el backend real, a través de un adaptador del APIClient al TestClient, el admin nuevo da 401 con `123456`, `12345678`, su email y su nombre, y ≠200 con la vacía. Control: después del reseteo #85 de Sistema, da 200.
- T11c: el dry-run sin la variable cae por el Excel, no por una clave.

**Re-semantizados**, por el grep de `reset-password` y `create-user`:
- `test_user_management.py`. Entre ellos, `test_created_user_can_login_with_default_password` pasó a `test_created_user_logs_in_with_chosen_password`: afirmaba justo lo que se quita.
- `test_organizations.py`, `test_sac_recolector_alcance.py` (t1c) y `test_system_endpoints.py`: cuerpos válidos con la clave.

## 3. Gates

Todos sobre el HEAD commiteado `ffd6fbf` (código `2ed7bb2` + la matriz r2), con 0 archivos sin commitear en la primera línea de cada log (O4 de QA 1).

| Gate | Resultado | Log |
|---|---|---|
| ruff (`app`, `tests`, `scripts`) | limpio, EXIT=0 | `ruff.log` |
| ESLint + tsc | 0 errores, 37 warnings (= techo), tsc EXIT=0. El front no cambia desde `1123bce` (0 líneas de diff) | `front_lint_tsc_r3.log` |
| Plantado r2, matriz ENTERA (C1 de QA 1) | **15/15 en la diagonal, exactos.** Ninguna caída de más ni de menos. Cada corrida recolectó los 16. Cierre: sha256 == HEAD en los 6 archivos plantados y `git status` limpio | `plantado_r2.log`, `plantar_r2.py` |
| Dirigidas | **578/578 passed, EXIT=0** (0:15:17), con la predicción (578, de `--collect-only`) escrita antes en la 3.ª línea del log. El set: grep de la superficie (14 archivos) más las 3 guardas | `dirigidas_r1.log`, `dirigidas_set.txt` |
| e2e Usuarios 1440/390 | **8/8 PASS** (E1–E4 × 2 anchos) | `e2e_r5.log`, `capturas/` |
| Golden | **no aplica, medido:** `golden_capture.py` captura 14 rutas (control positivo > 0) y ninguna es de `/organizations` ni de `/system`; solo hace login. 0 migraciones | `golden_no_aplica.log` |
| Parity | no aplica: 0 migraciones y 0 modelos tocados | — |

**Plantado.**
- La r1 (`plantado_r1.log`, sobre `1123bce`) dio 11/11, pero NO se arrastra (C1 de QA 1): el delta de la v1.2 tocó el archivo de tests y `migrate_org.py`.
- La r2 re-plantó las filas vigentes (P1–P7, P9, P11) y las nuevas de migrate:
  - P12: clave fija.
  - P13: el print de éxito imprime la clave.
  - P14: el error sin redactar.
  - P15: el payload sin la clave.
  - P16: el dry-run exige la variable.
  - P17: la constante `12345678`.
- P8 y P10 de la r1 se retiraron, declaradas en la matriz: el código que plantaban ya no existe.
- P17 es el contraste que muestra que T11b mide «sin clave utilizable»: con la constante, el login da 200 y T11b cae.

**e2e** (`e2e.mjs`, contra :8011 y :5181 del worktree, base `reciclaje_coder_1`).
- uvicorn arrancó sin `--reload` a las 20:19:54, después del último cambio en `app/` (`1123bce`, 19:50).
- E1: el miembro de 2 orgs activas ve el ítem deshabilitado con la nota.
- E2: el control. Johana, con 1 activa más archivadas, ve el ítem habilitado; no se la resetea.
- E3: el alta con clave elegida.
  - Corta y distinta deshabilitan el botón.
  - Sin constante en el diálogo y sin scroll horizontal.
  - Login con la elegida da 200, con la constante 401.
- E4: el reseteo con clave elegida.
  - Corta deshabilita y aparece el aviso de 7 días.
  - Login con la nueva da 200, con la vieja 401.
- Los usuarios de prueba se borran al final.
- **Tres corridas inválidas, las tres por el INSTRUMENTO.** Se conservan con su nombre.
  - r1: `getByText(email).first()` agarraba el email del usuario logueado, oculto en el header a 390.
  - r2: el menú de E2 seguía abierto y ponía la página en `aria-hidden`.
  - r3: a 390, el Escape del teclado no cerraba el menú, porque el foco no queda en él; ahora se le manda al menú.
- **La sonda de opacidad** (`sonda_opacidad.log`): las capturas del reseteo salían semitransparentes, y no se supuso que era la animación; se midió. El diálogo pasa de opacidad 0,11 a 1 al terminar sus animaciones, a 1440 y a 390, sin menús abiertos. El e2e ahora espera las animaciones antes de capturar.
- Las capturas son del viewport, con el diálogo o el menú abierto. Caben en pantalla, así que no hacía falta `captura.mjs` (aviso del Coordinador sobre el corte a 390).
- **Limitación declarada:** el diálogo de Sistema (org nueva con clave del admin) no tiene e2e en pantalla. Pide un superusuario y en dev no tengo su clave. Su backend lo cubren T6 y T7, y el campo del front pasó lint y tsc.

## 4. Decisiones de Daniel (vía el Coordinador) y avisos

- **O1:** los usuarios que HOY tienen una clave constante se dejan así. El ciclo deja de crear casos nuevos y no repara los viejos (D7).
- **O2:** la asimetría de mínimos, 8 al crear y 6 al resetear, no se toca.
- **O3:** D5 cierra el reseteo de cualquier usuario multi-org desde una org; lo hace soporte por #85.
- **D3b v1.2:** la clave al azar en memoria. Se rehicieron el plan, la skill, MIGRATION.md, T11 y el plantado.
- **Fuera de alcance, en el backlog del Coordinador (P3):** la clave del SUPERUSUARIO en la skill, que hoy va por AskUserQuestion y como argumento.
- **Deploy:** un frontend viejo contra el backend nuevo cae en 422 al resetear o crear, así que el front y el back viajan en el mismo deploy (D1).
- **Runbook de `/migrate-client` en prod:** tras el apply, Daniel le pone la clave real al admin desde Sistema → Usuarios. Hasta entonces el admin no puede entrar.
- **Suite completa:** diferida al checkpoint (regla del 19-nov).
