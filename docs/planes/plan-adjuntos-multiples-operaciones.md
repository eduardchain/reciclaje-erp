# Plan — Adjuntos multiples en Compras, Ventas y Transformaciones

**Version**: 1.1 (QA GO — 5 notas plegadas)
**Fecha**: 2026-09-01
**Origen**: pedido del cliente via Bascula — *"compras, ventas y transformaciones podamos adjuntarle archivos, si es posible varios, en donde podamos incluir evidencias de la calidad del material y remisiones importantes"*
**Respuestas del cliente** (ya dadas, no re-preguntar):
1. Se puede adjuntar **despues** de liquidar → SI.
2. Borra **quien puede editar**; los adjuntos **NO se borran** al cancelar la operacion → correcto.
3. Limites: **5MB por archivo** y **tope 10 por operacion** → *"mantenlos"*.
4. Las evidencias de Tesoreria (`evidence_url`, 1 archivo) **conviven** con el sistema nuevo → *"ok, que convivan las dos y unificamos despues"*.

---

## 1. Validacion de requisitos (regla obligatoria) — 1 gap y 2 precisiones

### 🔴 GAP-1 — El rol que tiene la camara no tiene el permiso

La regla *"borra quien puede editar"* es clara para **borrar**. Aplicada tambien a **subir**, rompe el caso de uso principal:

| Rol | `purchases.create` | `purchases.edit` |
|---|---|---|
| `bascula` | ✅ | ❌ |
| `liquidador` | ✅ | ✅ |

Verificado en [role.py:146-168](backend/app/services/role.py#L146). La bascula es **justo quien esta en el patio con el material enfrente y el celular en la mano** — es quien toma la foto de la calidad del material. Con `.edit` como guard de subida, no podria adjuntarla.

**Propuesta (D6)**: separar los dos verbos. **Subir** = `.create` OR `.edit`; **borrar** = `.edit` (la regla del cliente, literal). No inventa permisos ni contradice lo que dijo: solo reconoce que *subir* y *borrar* no son el mismo acto.

### Precision-1 — Transformaciones no tiene `.edit`
El catalogo solo tiene `transformations.view` y `transformations.create` (una transformacion no se edita: se anula). Ahi subir y borrar caen los dos en `transformations.create`, y la regla del cliente se cumple de forma degenerada (quien crea es quien borra).

### Precision-2 — "No se borran al cancelar" es **no hacer nada**
Es la mejor noticia del ciclo: **los tres servicios de negocio (`purchase.py`, `sale.py`, `material_transformation.py`) NO se tocan**. Cancelar/anular ya no sabe de adjuntos y debe seguir sin saber. Cero riesgo de regresion en la maquinaria de costo promedio, reversiones o P&L.

---

## 2. Modelo de datos

### Tabla nueva `attachments` (migracion aditiva, **cero columnas en tablas existentes**)

```
id                UUID PK
organization_id   UUID NOT NULL FK -> organizations (OrganizationMixin)
purchase_id       UUID NULL FK -> purchases (CASCADE)
sale_id           UUID NULL FK -> sales (CASCADE)
transformation_id UUID NULL FK -> material_transformations (CASCADE)
file_path         String(500) NOT NULL   -- relativo a UPLOAD_DIR
original_filename String(255) NOT NULL   -- lo que el usuario ve
content_type      String(100) NOT NULL
size_bytes        Integer NOT NULL
description       String(200) NULL       -- "Remision 4471", "Foto humedad"
uploaded_by       UUID NOT NULL FK -> users
created_at/updated_at (TimestampMixin)

CHECK: exactamente UNA de las 3 FKs no nula
INDEX: (purchase_id), (sale_id), (transformation_id), (organization_id)
```

### D1 — FKs nullables + CHECK, **no** polimorfismo `(entity_type, entity_id)`

Es el precedente del repo: `inventory_adjustments` gano `transfer_id` (#84), `inbound_order_id` (#93) y `willard_delivery_id` (#100) como FKs nullables explicitas, no como par polimorfico. Se gana integridad referencial real (imposible un adjunto huerfano) y el CHECK hace que *"exactamente un dueno"* sea **imposible de violar por construccion**, no algo que se vigile (patron #94/#98 D1). El costo — una columna por modulo futuro — es exactamente lo que costo la unificacion de Tesoreria: **una** columna `money_movement_id` el dia que se unifique.

### D2 — El nombre original se persiste (mejora sobre el sistema viejo)
Tesoreria guarda solo `evidence_url` y el archivo en disco se llama `{movement_id}_{timestamp}.ext`: **el nombre original se pierde**. Para *"remisiones importantes"* el nombre ES el dato (`remision-4471.pdf`). Por eso `original_filename` + `content_type` + `size_bytes` + `uploaded_by`. Esto es parte de por que la convivencia de la respuesta 4 del cliente es sana: el sistema nuevo no es el viejo con N filas, es mejor.

### D3 — `description` como texto libre, no taxonomia cerrada
El cliente nombro dos usos (calidad / remisiones), pero no pidio filtrar ni reportar por tipo. Un enum ahora es deuda prematura; si mañana quiere filtrar, un enum se deriva de los textos reales. Campo opcional, 200 chars.

---

## 3. Backend

### Router propio `/api/v1/attachments` (D4)
Un solo router en vez de tres bloques calcados dentro de `purchases.py` / `sales.py` / `material_transformations.py`. Los 3 modulos comparten el 100% de la logica (validar extension, tamano, tope, escribir disco); triplicarla garantiza que diverjan (es exactamente lo que paso con la celda de precios del requerimiento 1, que tenia dos copias ya divergidas).

| Metodo | Ruta | Permiso |
|---|---|---|
| `GET` | `/attachments?purchase_id=` \| `?sale_id=` \| `?transformation_id=` | `<mod>.view` |
| `POST` | `/attachments` (multipart: file + owner + description?) | `<mod>.create` OR `<mod>.edit` |
| `GET` | `/attachments/{id}/download` | `<mod>.view` |
| `DELETE` | `/attachments/{id}` | `<mod>.edit` (transformaciones: `.create`) |

El permiso se resuelve **por el dueno del adjunto** (el modulo al que pertenece). Sin permisos nuevos → **sin migracion de permisos, sin wiring a roles**.

> **N1 — el guard NO puede ser una dependency estatica.** `require_permission(...)` se evalua al declarar la ruta, pero aca el modulo se conoce recien despues de leer el query param (GET/POST) o de cargar la fila (DELETE/download). El chequeo va **dentro del endpoint**, contra el contexto de org que ya inyecta `get_required_org_context()`, y **debe conservar el bypass de admin** (`org_context["permissions"]` ya lo trae sintetizado, #29). Escrito explicito porque el atajo natural — poner un `require_permission("purchases.view")` en el decorador — dejaria los otros dos modulos gobernados por el permiso de compras, y eso pasa los tests felices sin que nadie lo note.

### Validaciones (servicio `services/attachment.py`)
- Extension en `ALLOWED_ATTACHMENT_EXTENSIONS` (reusa el set de Tesoreria + se le agregan `heic`/`heif`: **iPhone fotografia en HEIC por defecto** y hoy seria rechazado, que es justo el dispositivo del patio).
  > **N2 — HEIC tiene una segunda mitad.** Si D9 funciona, Safari decodifica el HEIC en canvas y **lo que sube es JPEG** (la extension casi nunca se usa). Si D9 falla y el HEIC crudo llega al servidor, **Chrome y Firefox de escritorio no lo renderizan**: la miniatura le sale rota a Johana aunque el archivo este intacto. Por eso el panel necesita **fallback de miniatura** (icono de archivo + nombre + boton descargar) para todo tipo no renderizable — que ademas es lo que ya hace falta para los PDF.
- `size > settings.MAX_UPLOAD_SIZE` (5MB) → 400.
- `COUNT(adjuntos del dueno) >= 10` → 400 con el conteo en el mensaje.
- Dueno inexistente o de otra org → 404 (multi-tenancy por `get_or_404` del modulo dueno).
- **N4 — el `DELETE` borra la fila Y el archivo del disco** (Tesoreria ya lo hace al reemplazar, [money_movements.py:1512](backend/app/api/v1/endpoints/money_movements.py#L1512)). Sin esto el disco se llena de huerfanos invisibles, que es justo el recurso que la seccion 5 dimensiona. Si el `os.remove` falla (archivo ya ausente), la fila se borra igual: el estado deseado es "no existe".
- **N5 — carrera del tope de 10** (nota, no fix): dos subidas simultaneas con 9 adjuntos pasan ambas el `COUNT` y dejan 11. El flujo real es un pesador con un celular; un `UNIQUE` o un lock por dueno costaria mas de lo que protege. Queda escrito para que el dia que aparezca un 11 nadie lo lea como corrupcion.
- **Sin guard de estado**: liquidada, cancelada o anulada aceptan adjuntos (respuesta 1 del cliente). El *cancel* de los 3 modulos no se toca (Precision-2).

### D5 — El nombre en disco lo genera el servidor, nunca el usuario
`{UPLOAD_DIR}/attachments/{org_id}/{uuid4}.{ext}` — el `original_filename` viaja en la BD y solo se usa como `filename=` del `FileResponse`. Cierra path traversal por construccion (`../../etc/passwd` como nombre no puede escapar porque nunca toca la ruta). Es el mismo criterio que ya usa Tesoreria (nombra con el `movement_id`), escrito explicito para que no se pierda al copiar.

### D7 — Conteo en el listado: **lookup por pagina, JAMAS outerjoin**
Si el listado de compras/ventas muestra un clip con el numero de adjuntos, el conteo se resuelve con una **segunda query** `WHERE purchase_id IN (ids de la pagina)` → dict → enrich. Un `outerjoin` sobre una relacion 1:N **duplica filas y rompe la paginacion** (trampa (a) de #89, re-aprendida en #93 R2). La query paginada no se toca.

---

## 4. Frontend

### Componente compartido `<AttachmentsPanel>` (`components/shared/`)
```tsx
<AttachmentsPanel
  owner={{ type: "purchase" | "sale" | "transformation", id }}
  canUpload={boolean}
  canDelete={boolean}
/>
```
Usado tal cual en [PurchaseDetailPage.tsx](frontend/src/pages/purchases/PurchaseDetailPage.tsx), [SaleDetailPage.tsx](frontend/src/pages/sales/SaleDetailPage.tsx) y [TransformationDetailPage.tsx](frontend/src/pages/inventory/TransformationDetailPage.tsx).

### D8 — Las imagenes se muestran via **blob**, no `<img src={url}>`
El endpoint exige `Authorization` + `X-Organization-ID`, headers que el navegador **no manda** en un `<img>`/`<a href>`. Hoy Tesoreria ya lo resuelve asi ([MovementDetailPage.tsx:121](frontend/src/pages/treasury/MovementDetailPage.tsx#L121), `responseType: "blob"`). El panel hace `URL.createObjectURL` **con su `revokeObjectURL` en el cleanup del efecto** — sin eso, abrir 20 detalles con fotos deja los blobs vivos en memoria de la pestana.

### D9 — Compresion en el navegador antes de subir (la decision de mayor impacto)
Una foto de celular sin comprimir pesa 2–5 MB. Redimensionar a max 1920px y re-encodear a JPEG 0.8 en un `<canvas>` la deja en ~300 KB: **10x menos**, sin perder legibilidad de una evidencia de calidad. Impacto medido sobre datos reales (seccion 5). Ademas mejora la subida en el patio, que es donde peor esta la senal. Los PDF no se tocan.

### Mobile (obligatorio por CLAUDE.md)
- **N3 — `multiple` si, `capture` NO.** `capture="environment"` fuerza la camara y **suprime la galeria**: una foto por vez y sin poder adjuntar la que se tomo hace un rato, que es la mitad del flujo real. El picker nativo del celular ya ofrece "Camara" como primera opcion sin el atributo, asi que se omite y se gana la galeria y la multi-seleccion.
- Grid `grid-cols-2 sm:grid-cols-3 md:grid-cols-4`; nombre de archivo con `truncate`.
- Borrar detras de `ConfirmDialog`.
- Verificacion en DevTools 390px antes de cerrar.

---

## 5. Riesgo de infraestructura (medido, con numeros reales)

Estado del VPS al 2026-09-01 (solo lectura, sin tocar la BD):

| | Hoy |
|---|---|
| Disco | 6.5 GB usados / 96 GB (7%) → **~89 GB libres** |
| `uploads/` | **3.8 MB** en 107 archivos (~36 KB c/u) |

Proyeccion con 20 operaciones/dia x 3 fotos:

| Escenario | Por mes | 12 meses |
|---|---|---|
| Sin comprimir (3 MB/foto) | **5.4 GB** | **65 GB** → el disco queda al limite |
| Con D9 (~300 KB/foto) | **0.54 GB** | **6.5 GB** → sin problema |

**D9 no es cosmetica: es lo que separa "sin problema" de "llenar el disco en ~16 meses".**

### 🔴 Condicion que este ciclo hace urgente (ya levantada, sin respuesta del cliente)
**Los backups de produccion NO incluyen `uploads/`** — solo `pg_dump`. Hoy eso arriesga 3.8 MB de comprobantes; con este ciclo pasa a arriesgar **las fotos que prueban la calidad del material en una disputa con un proveedor o un cliente**, que es literalmente para lo que el cliente las pide. La BD quedaria con la fila y el disco sin el archivo.

**Recomendacion (elevada a condicion del tren, avalada por QA)**: sumar `uploads/` al script de backup (rsync incremental a Backblaze) **en el mismo deploy**. Es chico y no toca la aplicacion. El argumento para subirlo de "recomendado" a condicion es el proposito declarado del feature: deployar la captura de fotos **sabiendo que un restore las pierde** crea exactamente la expectativa que el backup no honra — el cliente creeria tener respaldada la prueba de una disputa que en realidad vive en un solo disco. **La decision es de Daniel**, tomada viendo esta frase.

---

## 6. Gates

| Gate | Aplica | Por que |
|---|---|---|
| **Golden ×3 orgs** | **NO** | Verificado contra `CAPTURES` ([golden_capture.py:36-58](backend/scripts/golden_capture.py#L36)), **no leerlo de memoria** (leccion #98): son **16 capturas — 14 estaticas** (reportes + `money_accounts` + `warehouses` + `money_movements`) **+ 2 estados de cuenta armados dinamicamente** (`hot`/`busy`, #96 E). `/purchases`, `/sales` y `/material-transformations` **no se capturan**, y este ciclo no agrega ni una columna a tabla compartida ni toca ningun reporte. |
| **Parity check** | SI | Migracion nueva → `schema_parity_check.py` debe dar DIFF CERO. |
| **`server_default` en la migracion** | SI, a mano | `TimestampMixin` trae `server_default` y **ningun gate compara eso** (la BD de test nace de los modelos, prod de las migraciones; el parity check lo excluye a proposito). Es exactamente el 500 del primer POST de #100. **Copiar el `server_default` de `created_at`/`updated_at` a la migracion y hacer smoke contra dev migrada.** |
| Suite pytest | SI | + los tests nuevos de la seccion 7. |
| ruff / eslint / tsc / build | SI | eslint al ras en 37 (#97): el panel nuevo **no puede sumar warnings**. |
| **Abrir la pantalla** | SI | Ningun gate ejecuta React. Subir, ver miniatura, borrar y probar en 390px es parte de terminar. |

---

## 7. Tests (`backend/tests/test_attachments.py`)

**Caso feliz** (x3 modulos): subir → listar → descargar → borrar.
**Validaciones**: extension invalida → 400; >5MB → 400; **el 11º adjunto → 400** con el conteo; dueno de otra org → 404; sin dueno o con dos duenos → 422.
**Reglas del cliente** (las 3, con test propio cada una):
- adjuntar a una operacion **liquidada** → 201;
- **cancelar la compra NO borra sus adjuntos** (siguen listandose y descargandose);
- **RBAC del GAP-1**: rol con solo `.create` **sube** (201) y **no borra** (403); rol con `.view` lista pero no sube (403).
**Seguridad**: `original_filename = "../../../etc/passwd"` se guarda como nombre en BD y el archivo en disco queda dentro de `attachments/{org}/` (D5).
**Multi-tenancy**: adjunto de la org A invisible/no descargable desde la org B.

---

## 8. Fuera de alcance (declarado)

- **Unificar las evidencias de Tesoreria** — el cliente pidio explicitamente convivencia (*"unificamos despues"*). `evidence_url` queda intacto; la migracion futura es una columna `money_movement_id` + un script que mueva las 107 filas.
- Adjuntos en Entradas (SAC), Traslados, Activos Fijos y Obligaciones: mismo componente el dia que se pidan, una columna cada uno.
- Versionado de adjuntos, OCR, previsualizacion de PDF embebida.

---

## 9. Preguntas abiertas (no bloquean la implementacion)

1. **`description` por adjunto**: ¿lo quiere el cliente o alcanza con el nombre del archivo? Default del plan: campo opcional (D3). Si sobra, se oculta en UI sin tocar el modelo.
2. **Clip con el conteo en los listados** de compras/ventas (D7 ya resuelve el como). ¿Lo quiere o solo en el detalle? Default: **solo detalle** en v1, el listado se agrega despues sin migracion.
