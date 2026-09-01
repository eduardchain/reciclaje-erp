# Informe de código — Adjuntos múltiples (compras, ventas, transformaciones)

**Plan**: `plan-adjuntos-multiples-operaciones.md` v1.1 (QA GO)
**Fecha**: 2026-09-01

---

## 1. Qué se construyó

**Backend** (5 archivos nuevos, 2 registros):

| Archivo | Qué |
|---|---|
| `alembic/versions/d3e4f5a6b7c8_attachments.py` | Tabla nueva. Cero columnas en tablas existentes. |
| `app/models/attachment.py` | FKs nullables + CHECK de dueño único (D1). |
| `app/schemas/attachment.py` | Response / list / update de etiqueta. |
| `app/services/attachment.py` | Validaciones, disco, tope. |
| `app/api/v1/endpoints/attachments.py` | 5 endpoints con el guard dinámico (N1). |

**Frontend** (5 archivos nuevos, 3 páginas tocadas): `types/attachment.ts`, `services/attachments.ts`, `hooks/useAttachments.ts`, `utils/imageCompression.ts`, `components/shared/AttachmentsPanel.tsx`; integrado en `PurchaseDetailPage`, `SaleDetailPage` y `TransformationDetailPage`.

**Infraestructura**: `uploads/` entró al backup de producción (sección 4).

---

## 2. Las 5 notas de QA, dónde quedaron

| Nota | Resolución |
|---|---|
| **N1** — el guard no puede ser dependency estática | `_check(org_context, owner_type, action)` dentro del endpoint, leyendo `OWNER_PERMISSIONS`; replica `require_any_permission` con el bypass de admin. **Tiene test propio** (§3): un usuario con ventas y sin compras adjunta a su venta y recibe 403 en una compra. |
| **N2** — HEIC tiene segunda mitad | `heic`/`heif` aceptados en el backend; `isRenderable()` en el panel excluye HEIC del `<img>` y cae al ícono, que es el mismo fallback que los PDF ya necesitaban. |
| **N3** — `capture` mata la galería | `multiple` sí, `capture` **no**. Comentado en el JSX para que no lo "arreglen" después. |
| **N4** — el DELETE borra el archivo | `os.remove` con `try/except` (si ya no está, la fila se borra igual: el estado deseado es "no existe"). **Tiene assert propio**: el test cuenta los archivos del directorio antes y después. |
| **N5** — carrera del tope de 10 | Documentada en el servicio, sin fix (un pesador, un celular). |

**GAP-1** aplicado tal cual: subir = `.create` OR `.edit`; borrar = `.edit`. En transformaciones ambos verbos son `.create` porque el catálogo no tiene `transformations.edit`.

---

## 3. Los tests muerden — 5 defectos plantados, 5 caídas

No basta con que 17 tests pasen: hay que probar que fallan cuando el código está mal. Cada defecto se plantó, se corrió **el test que debía atraparlo**, y se revirtió.

| Defecto plantado | Test que cae |
|---|---|
| Borrar exige `.create` en vez de `.edit` (mata GAP-1) | `test_gap1_bascula_sube_pero_no_borra` |
| Tope con `>` en vez de `>=` (deja entrar el 11º) | `test_tope_de_diez` |
| Guard fijo al permiso de compras (el atajo de N1) | `test_n1_el_guard_es_por_modulo_no_uno_fijo` |
| El DELETE no borra el archivo del disco | `test_purchase_upload_list_download_delete` |
| El nombre del usuario va a la ruta en disco (D5) | `test_path_traversal_no_escapa_del_directorio` |

**Dos de esos tests nacieron de revisar mis propios huecos, no del plan**: el original de borrado solo verificaba que la lista quedara en cero — un DELETE que borrara la fila y dejara el archivo huérfano habría pasado en verde. Y ningún test cubría N1: todos los demás usan admin (que bypassa) o roles que tienen los dos permisos, así que el atajo estático habría pasado los 16 tests felices. Es exactamente lo que QA advirtió al escribir la nota.

---

## 3.b Tres cosas que arreglé revisando mi propio código

Ninguna la habría marcado un gate; las tres son de la familia "solo se ve al usar la pantalla".

1. **La descarga se cancelaba en Safari.** Yo revocaba la object URL en la misma vuelta del event loop que el `a.click()`, cuando el navegador todavía no leyó el blob. Movido a un helper único en el servicio, con la revocación diferida. (El patrón que ya vive en producción para las evidencias de Tesorería usa `window.open` y **nunca** revoca — funciona, pero filtra; el helper nuevo no hace ninguna de las dos cosas mal.)
2. **La UI mostraba una etiqueta que nadie podía escribir.** El campo `description` existía en el modelo y el panel lo renderizaba, pero no había forma de ponerlo: el `PATCH` quedaba inalcanzable desde la aplicación. Ahora la nota se edita en línea (clic → input → Enter), así el campo se usa de punta a punta. Resuelve además la pregunta abierta #1 del plan por el lado barato: existe y se usa, sin taxonomía cerrada.
3. **El `PATCH` no tenía test.** Un endpoint sin test es un endpoint que nadie prometió mantener. Agregado, incluida la limpieza de la nota a `null`.
4. **Retiré un helper que nadie llamaba.** Había escrito `count_for_owners` (D7, el conteo por página para un clip en el listado) anticipando algo que el plan dejó explícitamente fuera de v1: código sin uso y sin test es deuda. La **regla** queda escrita como comentario donde estaba — que ese conteo se hace con `IN (ids de la página)` y jamás con un outerjoin — porque lo que hay que conservar es el criterio, no las ocho líneas.

---

## 3.c Cambios pedidos por la revisión de QA

| Pedido | Resolución |
|---|---|
| 🟡 **`description` sin tope en el POST** → una nota de 201+ caracteres pasaba la validación y reventaba en el INSERT: **500 por un dato del usuario**. Inalcanzable desde la UI (el input tiene `maxLength`), pero el endpoint es API pública de la app. | `Form(None, max_length=200)` espejando `String(200)`, con test (201 chars → 422). |
| El aviso de la duplicación de `_check` debe estar **en el lado que se edita** | Nota en el docstring de `require_any_permission` (`deps.py`): si cambia la *lógica*, hay que cambiarla en los dos lados. Las *llaves* del contexto no son el riesgo — las consumen ~181 endpoints. |
| Que la consecuencia del `PATCH` con verbo `upload` sea **decisión escrita, no accidente del mapa** | Comentado sobre `OWNER_PERMISSIONS`: la báscula puede corregir la nota de un adjunto del liquidador y viceversa. Es metadato de la subida, no destrucción; con la cámara en el patio, poder etiquetar lo que uno ve vale más que la exclusividad. |
| Un archivo que falla no debe llevarse el lote | `try/catch` por archivo en `handleFiles`: quien sube 5 fotos espera que entren las 4 que sí podían. |
| Los scripts del VPS quedaban fuera de control de versiones | Copiados a `ops/vps/` con README. **Verificados idénticos al servidor por md5.** Se versionan porque el único registro de un cambio era un `.bak` en el propio servidor — y es justo el script del que depende deshacer cualquier otro error. |

---

## 4. Backup de `uploads/` (decisión del cliente: sí)

Un `pg_dump` no incluye los archivos en disco: hasta hoy, restaurar devolvía las filas y perdía las evidencias.

- **`backup-database.sh`**: paso nuevo con `aws s3 sync` incremental a `s3://ecobalance-backups/uploads/`. Dos decisiones: (a) **prefijo `uploads/`, no el raíz** — la limpieza por antigüedad borra todo lo que hay en el raíz, así que ahí los adjuntos durarían 30 días; de paso ese loop se acotó a `ecobalance_*.sql.gz`, porque antes habría borrado cualquier objeto viejo; (b) **`sync` sin `--delete`** — un adjunto borrado desde la UI conserva su copia.
- **`restore-database.sh uploads`**: modo nuevo, aditivo (sin ese argumento el script se comporta igual). También sin `--delete`.

Verificado end-to-end: 107 archivos / 3.2 MB subidos, 2ª corrida transfiere **0** (incremental real), restore trae los 107, y `list` sin regresión. Los originales quedaron como `.bak-20260901`.

---

## 5. Gates

| Gate | Resultado |
|---|---|
| `pytest tests/test_attachments.py` | **17 passed** |
| Suite completa | (corriendo al cierre del informe) |
| `schema_parity_check.py` | **DIFF CERO fuera del baseline** — 65 tablas, 289 índices, 341 constraints |
| `ruff` | All checks passed |
| `tsc --noEmit` | 0 |
| `eslint` | **exit 0**, 37 warnings — el techo de #97, sin sumar ninguno |
| `npm run build` | ✓ |
| **Golden ×3 orgs** | **No aplica** — verificado contra `CAPTURES`: `/purchases`, `/sales` y `/material-transformations` no se capturan, la migración no toca tablas compartidas y ningún reporte cambia. |
| **`server_default` en la migración** | Verificado a mano (`created_at`/`updated_at` con `sa.func.now()`): es lo que ningún gate ve y fue el 500 de #100. |

---

## 6. Lo que falta

1. **Abrir la pantalla** — ningún gate ejecuta React. Subir desde el celular, ver la miniatura, borrar, y probar en 390px.
2. **Commit**: `app/models/__init__.py` y `app/api/v1/__init__.py` tienen cambios del otro agente (W1), así que este ciclo hereda el mismo orden: W1 primero.
3. **Decisión en CLAUDE.md**: pendiente por lo mismo — el archivo ya trae las decisiones #100 y #101 sin commitear.
