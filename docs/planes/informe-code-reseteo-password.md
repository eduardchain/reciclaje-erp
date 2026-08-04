# Informe CODE — Reseteo de contraseña por superusuario

**Fecha:** 2026-07-24. **Plan:** `plan-reseteo-password-superusuario.md` v1.0 (micro-QA 🟢 GO). **Decisión:** #85 en CLAUDE.md. Sin commit (gating: pruebas de Daniel → commit develop).

---

## 1. Qué se construyó

**Backend (2 archivos, cero migraciones):**
- `app/schemas/system.py`: `ResetPasswordRequest` — un campo, `new_password: str = Field(..., min_length=6)`, calco literal de `ChangePassword.new_password`. El docstring deja escrito el compromiso de H4: si la política se endurece, se endurece en **ambos** schemas.
- `app/api/v1/endpoints/system.py`: `POST /users/{user_id}/reset-password` (8º endpoint del router), guard `get_current_superuser` como sus 7 hermanos. Reutiliza `SystemUserResponse` y su serialización de memberships — filtrada al usuario objetivo, no la carga completa del listado.

**Frontend (3 archivos):**
- `services/system.ts`: `resetUserPassword(userId, newPassword)`.
- `hooks/useSystem.ts`: `useResetUserPassword` — **sin invalidación de caché** (el reset no altera ningún listado, solo el hash) y con toast que nombra al usuario pero **jamás la clave**.
- `pages/system/SystemUsersPage.tsx`: botón "Contraseña" en la fila desktop y botón-ícono en la card mobile, ambos **dentro del `!user.is_superuser` que la página ya tenía** — el guard visual es espejo exacto de D2, sin lógica nueva. Diálogo con clave + confirmación, validación en vivo y aviso ámbar de D4.

## 2. Cómo aterrizaron los hallazgos del micro-QA

| # | Aterrizaje |
|---|---|
| **H3** (el que pediste confirmado) | La línea de auditoría es `logger.warning("password_reset actor_id=%s actor_email=%s target_id=%s target_email=%s", ...)` — **cuatro campos, ninguno del payload**. No se loggea `data`, ni el request, ni `new_password`. El comentario en el código dice por qué (loggear el payload desharía D1). **Test dedicado** `test_audit_log_has_actor_and_target_but_no_secret`: captura con `caplog`, exige exactamente 1 línea, verifica que estén actor y objetivo (id + email) y **assert negativo** de que ni la clave ni la cadena `new_password` aparecen. |
| **H1** | Conteo corregido: verifiqué los `@router.` uno a uno — eran **7**, ahora **8**. CLAUDE.md #29 actualizado con la nota del error histórico. |
| **H2** | Runbook §9 reescrito: el paso 2 ahora es **verificar `GET /system/users` antes de resetear**, con la explicación de por qué el origen del usuario puede no ser el hardcode. Además quedó registrado el dato de campo: Daniel confirmó que `hugo@sac.com` **sí** entra con `123456` en prod. |
| **H4** | Sin cambio (así lo pediste). La constancia quedó en el docstring del schema, que es donde la va a leer quien endurezca la política. |
| **Q1** | Deuda declarada en #85, explícitamente emparejada con D4 como "misma familia: ciclo de vida de credencial/sesión". |
| **Q2** | Bloqueo mantenido (D2), con tu racional en el mensaje de error del 403. |

## 3. Evidencia de gates

| Gate | Resultado |
|---|---|
| Tests nuevos | **12/12 verdes** (`test_system_password_reset.py`): efecto real ×3 — incluido **login end-to-end** con la clave nueva devolviendo token + la vieja dando 401 —, validaciones ×2, edge cases ×3 (404 / objetivo superusuario con hash intacto / inactivo que se resetea pero sigue sin entrar), RBAC ×2 (admin de org 403, sin token 401), no-fuga ×2 (response y log). |
| Suite completa | **1407/1407 verdes** en 21:31 (1395 previos + 12 nuevos, exit 0, **cero regresiones**). |
| Migraciones | **Ninguna** — no hay nada que aplicar en dev, test ni prod. |
| Golden ×3 orgs | **No aplica**, y esta vez de verdad: cero columnas, cero cambios de serialización en endpoints existentes, cero endpoints modificados. El golden del 2026-07-23 sigue siendo válido tal cual. |
| tsc / build | Limpios (`tsc --noEmit` exit 0; `vite build` 3.88s). |
| 390px | Diálogo con `DialogContent` base (ya trae `w-[calc(100vw-1.5rem)] max-w-lg sm:w-full` — **no** le puse `max-w-sm`, que es lo que rompe el ajuste mobile), inputs `w-full`, footer `flex-col sm:flex-row` con botones `w-full sm:w-auto`. En la card mobile la acción es botón-ícono con `aria-label` para no reventar el ancho junto a "Agregar". Verificación en DevTools: en las pruebas de Daniel. |

## 4. No-regresión

- **Endpoint nuevo**: ningún endpoint existente cambia de firma, respuesta ni comportamiento. El único archivo de negocio tocado (`system.py`) recibe una función nueva y tres líneas de import/logger.
- **`SystemUserResponse` reutilizado sin modificar** → `GET /system/users` sigue devolviendo byte a byte lo mismo.
- **Sin permisos RBAC nuevos**: el guard de superusuario ya existía. El catálogo de permisos sigue en 88.
- La página sólo es alcanzable por superusuarios; ningún usuario de cliente la ve.

## 5. Limitaciones declaradas (las mismas del plan, ninguna nueva)

- **D4**: las sesiones abiertas sobreviven hasta 7 días al reseteo. Declarado en el código, en el diálogo y en #85.
- **D3**: resetear no reactiva; hay que reactivar aparte.
- **D5**: auditoría por log, no por tabla. Si el cliente pide trazabilidad formal, es una tabla nueva.
- **Q1**: nada obliga al usuario a cambiar la clave temporal.

## 6. Hallazgo de seguridad que excede este ciclo

**No es un residuo histórico: es un mecanismo activo de reseteo-a-constante, vivo hoy en las 3 organizaciones de producción.** (Ampliación exigida por el re-QA; la redacción previa de esta sección subdimensionaba el problema.)

1. **Endpoint vivo y cableado en la UI**: `POST /organizations/{org_id}/members/{user_id}/reset-password` ([organizations.py:426-436](../../backend/app/api/v1/endpoints/organizations.py#L426-L436)) llama a `reset_password()` ([services/user.py:107-115](../../backend/app/services/user.py#L107-L115)), que fija la constante **`"123456"`**. El guard es **cualquier admin de organización** — no superusuario. Expuesto en el frontend: [roles.ts:49-50](../../frontend/src/services/roles.ts#L49-L50) + [useRoles.ts:128](../../frontend/src/hooks/useRoles.ts#L128). O sea: un admin de org puede fijar la clave de **cualquier miembro** a una constante públicamente conocida.
2. **Alta de miembros con bypass declarado**: [organizations.py:281-286](../../backend/app/api/v1/endpoints/organizations.py#L281-L286) crea el usuario con `"12345678"` y acto seguido lo resetea a `"123456"`, con el comentario en el código admitiéndolo — *"Resetear a 123456 (bypass min_length del schema)"*.
3. **Creación de organizaciones**: `POST /system/organizations` nace el admin con la misma constante ([system.py:88](../../backend/app/api/v1/endpoints/system.py#L88)). Daniel **confirmó en producción** que `hugo@sac.com` entra con ella.

**El ciclo de seguimiento no es "rotar claves viejas", es eliminar el reseteo-a-constante.** El diseño de #85 —clave provista por el operador (D1), nunca una constante, nunca devuelta en el response— es justamente el patrón que debería reemplazar los tres puntos de arriba. No se toca aquí: es pre-existente, está fuera del alcance aprobado, y cambiarlo sin avisar dejaría sin acceso a quien hoy dependa de esa clave.

**Corrección de una premisa del plan** (nota de precisión del re-QA, sin consecuencia práctica): el §1 afirmaba que no existía endpoint de reseteo por superusuario; se verificó con `grep` sobre `system.py` y `users.py`, y por eso no vio `organizations.py`. **No invalida #85**: la ruta de org exige membresía, así que un superusuario que no es miembro no puede usarla — el hueco que #85 cierra era real, y su diseño (D1/D2/D5) es estrictamente mejor que el que ya existía.
