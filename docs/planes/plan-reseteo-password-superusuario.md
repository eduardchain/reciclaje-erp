# Plan — Reseteo de contraseña por superusuario

**Versión 1.0 — 2026-07-24.** Ciclo: plan → micro-QA → GO → código+tests → informe → commit develop.

---

## 1. Por qué (el hueco real)

Hoy **no existe forma de que un usuario recupere su acceso**:

- `POST /auth/change-password` exige `current_password` ([schemas/user.py:36-39](../../backend/app/schemas/user.py#L36-L39)) — sirve solo si la recuerdas.
- No hay flujo de "olvidé mi contraseña" (los 5 endpoints de `auth` son register / login / login-json / change-password / me).
- No hay endpoint de superusuario para resetear a otro (`grep` sobre `system.py` y `users.py`: cero).
- La única salida hoy es escribir el hash directo en la BD — **prohibido en producción** (regla de BD de CLAUDE.md).

**Detonante inmediato:** SAC va a probar en producción con sus propios usuarios. `hugo@sac.com` y `johana@sac.com` **ya existen en prod** con una contraseña que nadie del equipo conoce (nacieron con la clave hardcodeada `"123456"` de [system.py:85](../../backend/app/api/v1/endpoints/system.py#L85) y pudieron haberla cambiado). Si esa clave no funciona, hoy no hay manera de darles acceso.

**Y el hueco sobrevive al detonante:** en operación, el día que Johana olvide su clave, nadie puede ayudarla.

## 2. Alcance

**DENTRO:**
1. `POST /api/v1/system/users/{user_id}/reset-password` — el superusuario fija la contraseña de otro usuario.
2. Botón + diálogo en `SystemUsersPage` (la página ya existe, con render desktop y cards mobile).
3. Tests (regla obligatoria de CLAUDE.md).

**FUERA (declarado, no silencioso):**
- Flujo self-service de "olvidé mi contraseña" (requiere envío de correo — no hay infraestructura de mail en el proyecto).
- Forzar cambio de clave en el primer login (requiere columna `must_change_password` + guard en frontend) → **Q1**.
- Invalidación de sesiones activas → **D4**, deuda declarada.
- Tabla de auditoría formal → **D5**.

## 3. Diseño

**Endpoint** — hermano de `add-to-org`, mismo archivo y mismo guard:

```
POST /api/v1/system/users/{user_id}/reset-password
Guard: _su: User = Depends(get_current_superuser)   # patrón de los 6 endpoints de /system/
Body:  { "new_password": str }                      # min_length=6
Resp:  SystemUserResponse (200)                     # id, email, full_name, is_active, is_superuser, memberships
```

**Schema** `ResetPasswordRequest` en `schemas/system.py`:
```python
class ResetPasswordRequest(BaseModel):
    """Reseteo por superusuario: NO exige la clave actual (ese es el punto)."""
    new_password: str = Field(..., min_length=6)
```
`min_length=6` es **calco literal** de `ChangePassword.new_password` — misma política, cero drift.

**Efecto:** `user.hashed_password = get_password_hash(data.new_password)` + commit. Nada más: ni reactiva, ni toca memberships, ni roles.

**Códigos de respuesta:** 200 ok · 422 clave corta o body inválido · 404 usuario inexistente · **403 el objetivo es superusuario** (D2) · 403 quien llama no es superusuario (guard existente) · 401 sin token.

## 4. Decisiones y racional (lo que QA va a cuestionar)

| # | Decisión | Racional |
|---|---|---|
| **D1** | La contraseña **la provee el operador**, el servidor NO la genera | Si el servidor la generara tendría que **devolverla en el body** → el secreto queda en logs de acceso, en el caché de React Query y en cualquier proxy. Provista = el secreto **nunca viaja de vuelta**. El superusuario tiene que comunicarla de todos modos. |
| **D2** | **403 si el objetivo es superusuario** (sin excepciones, tampoco a sí mismo) | Superusuario→superusuario es **toma de cuenta lateral**. Un superusuario que quiere cambiar su propia clave ya tiene `/auth/change-password` (la conoce, está autenticado). Regla de una línea, sin ramas ni casos especiales. Relajable después si aparece la necesidad. |
| **D3** | **Se permite resetear usuarios inactivos**; el reset **no** los reactiva | Son cosas distintas: la reactivación pasa por su propio camino. La secuencia real (resetear → reactivar) queda disponible. El response expone `is_active` para que el operador vea que todavía no puede entrar. |
| **D4** | **NO se invalidan las sesiones ya emitidas** | No existe `token_version` ni lista negra de JWT; agregarlo es columna + migración + cambio en `get_current_user`. Con `ACCESS_TOKEN_EXPIRE_MINUTES = 60*24*7` ([security.py:14](../../backend/app/core/security.py#L14)), **una sesión previa sigue viva hasta 7 días** después del reset. Aceptable para el caso "olvidé mi clave"; **insuficiente para "me robaron la cuenta"** — declarado como deuda, y el copy de la UI lo dice. |
| **D5** | Auditoría = **línea de log estructurada**, no tabla | El sistema no tiene tabla de auditoría de usuarios (sí `created_by`/`annulled_by` en entidades de negocio, no en `users`). Se registra actor (id+email) → objetivo (id+email). Cero migración. Si el cliente exige trazabilidad formal, es una tabla nueva en otro ciclo. |
| **D6** | Vive en `/system/`, no en `/auth/` | `/system/` ya es el espacio del superusuario, con su guard propio (`get_current_superuser`) separado del RBAC por org. Poner un reseteo sin `current_password` en `/auth/` invitaría a confundirlo con el self-service. |

## 5. Frontend

`SystemUsersPage.tsx` (317 líneas, ya tiene tabla desktop + cards mobile + un diálogo de "Agregar a Organización" — se calca ese patrón):

- Botón **"Resetear contraseña"** por fila (desktop y card mobile).
- Diálogo: input de contraseña nueva + confirmación (deben coincidir), mínimo 6, botón deshabilitado hasta que sea válido.
- **Copy honesto** (D4): *"La sesión activa del usuario seguirá siendo válida hasta 7 días. Pídele que cierre sesión si la cuenta está comprometida."*
- Toast de éxito **sin** la contraseña. El operador la comunica por su canal.
- `hooks/useSystem.ts` gana `useResetUserPassword`; `services/system.ts` el método. Sin invalidación de caché cruzada: el reset no cambia listados (solo el hash).
- Responsive: el diálogo base de shadcn ya trae `w-[calc(100vw-1.5rem)]`; inputs `w-full` (regla mobile-first de CLAUDE.md).

## 6. Tests (`tests/test_system_password_reset.py`)

**Caso feliz y efecto real**
1. Superusuario resetea → 200; el hash nuevo **verifica** contra la clave nueva.
2. La clave **vieja ya no verifica**.
3. **Login end-to-end** con la clave nueva → 200 y token válido.

**Validaciones**
4. Clave de 5 caracteres → 422.
5. Body sin `new_password` → 422.

**Edge cases**
6. `user_id` inexistente → 404.
7. Objetivo **superusuario** → 403 (D2), y su hash **no cambió**.
8. Usuario **inactivo** → 200, `is_active: false` en el response, sigue sin poder entrar (D3).

**RBAC**
9. Admin de organización (no superusuario) → **403**.
10. Sin token → 401.

**Fuga de secretos**
11. El body de respuesta **no contiene** `password` ni `hashed_password` (assert sobre las claves del JSON).

## 7. No-regresión

- **Endpoint nuevo, cero superficie compartida**: ningún endpoint existente cambia de firma ni de comportamiento.
- **Cero migraciones** → sin columnas nuevas, sin cambios de serialización → **el golden ×3 orgs no se toca** (a diferencia de E1/E3.1, que sí sumaron claves). Las 3 organizaciones en producción no ven absolutamente nada.
- `SystemUserResponse` se **reutiliza tal cual** (ya lo devuelve `GET /system/users`) — sin schema nuevo de salida.
- Frontend: la página sólo existe para superusuarios; ningún usuario de cliente la alcanza.

## 8. Preguntas abiertas

- **Q1 — ¿Forzar cambio de contraseña en el primer login?** Sería lo correcto para claves temporales (hoy el usuario puede quedarse con la que le dieron). Cuesta columna `must_change_password` + guard en el frontend. ¿Lo quieren ya o queda para después?
- **Q2 — ¿Alguna vez habrá que resetear a otro superusuario?** Hoy lo bloqueo (D2). Si el equipo crece y aparece el caso, se relaja.

## 9. Runbook (el uso inmediato, post-deploy)

1. Deploy del tren.
2. **Verificar primero qué usuarios existen realmente en prod** (`GET /system/users` o el panel Sistema → Usuarios) — **H2 del micro-QA**: no asumir los dos correos. La clave hardcodeada de [system.py:85](../../backend/app/api/v1/endpoints/system.py#L85) solo aplica al `admin_email` con el que se creó la organización; quien haya entrado por otra vía (seeder, `add-to-org` sobre un usuario ya existente) tiene otro origen. El reset funciona igual sea cual sea el origen — esto es para no resetear a ciegas.
3. Resetear los que hagan falta desde el panel.
4. `erwin@sac.com` y `yurani@sac.com` **no necesitan reseteo**: los crea el seeder con la clave que se le pase.
5. Comunicar las claves temporales por canal privado; pedirles que la cambien en Perfil al entrar.

> **Verificado en prod 2026-07-24 (Daniel):** `hugo@sac.com` **sí** entra con la clave por defecto `123456`. Destraba el acceso inmediato — y confirma el riesgo de seguridad de fondo que documenta la decisión #85.
