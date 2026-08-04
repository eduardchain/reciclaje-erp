# Plan — Retenciones v2: catálogo configurable con precálculo editable (CC-006)

**Versión**: v1.1 (QA GO condicionado 2026-07-17 — F1/F2 incorporadas, F3 aceptada con `concept`; cambio de Daniel: **tab propio**, no grupo en Pasivos) · **Ciclo**: corto post-commit del conjunto ampliado (`09794ae`)
**Origen**: walkthrough de Daniel sobre el addendum (§1f del informe paquete UX). Textual: *"debería ser tan sencillo como un botón que diga agregar retención: se define nombre de impuesto, municipio y porcentaje, y esto queda precargado en el selector; el usuario no tiene que hacer nada, salvo modificar manualmente el valor"*. Valida Q-07 de Johana: hay tarifas y bases típicas, el valor SIEMPRE editable.

---

## 1. Objetivo y no-objetivos

**Objetivo**: que las retenciones se configuren UNA vez (tipo + municipio + % tarifa) y al liquidar el usuario solo elija de un selector — el monto se pre-calcula (% × subtotal) y es editable. El botón "Agregar Municipio ICA" (transicional, addendum) desaparece.

**No-objetivos** (fuera de alcance, explícitos):
- Certificados/resumen mensual de retenciones (Q-08: "por ahora está bien estado de cuenta").
- Retenciones en ventas (solo compras, como D9).
- Bases distintas al subtotal de materiales (ver §6 limitaciones).
- Tocar el flujo D9 de entidades/bloques compensatorios (`retention_entities.py`, `_apply_retentions`) — intacto.

## 2. Modelo de datos (LA migración del ciclo)

Tabla nueva **`retention_configs`** (migración aditiva, sin backfill, patrón D13 paridad modelos↔migración):

| Columna | Tipo | Regla |
|---|---|---|
| id | GUID PK | |
| organization_id | GUID FK | OrganizationMixin (CASCADE) |
| retention_type | String(20) | CHECK in ('retefuente','reteiva','ica') — catálogo CERRADO (los 3 de Johana; NO nombre libre, mismo criterio anti-typo del Select de municipio). Un 4º impuesto = extensión de catálogo en ciclo propio |
| municipality | String(60) NULL | obligatorio si `ica`, NULL en los otros (CHECK compuesto) |
| concept | String(60) NULL | **F3 QA (aceptada)**: concepto opcional dentro del tipo (ej. ReteFuente compras 2,5% vs servicios 4% — tarifas colombianas reales varían por concepto). NULL = general. Absorbe Q-10 sin segunda migración |
| rate_pct | Numeric(5,2) | tarifa % (0 < x ≤ 100) |
| is_active | Boolean | soft delete estándar |
| created_at / updated_at | | TimestampMixin |

- **Unicidad en SERVICIO, no BD** (precedente D14-E1): una config activa por (org, tipo, municipio-normalizado, concepto-normalizado — NULL distinto de texto). El matching de municipio usa `normalize_entity_name` de `retention_entities.py` (H4: "bogota" == "Bogotá") — coherencia total con las entidades.
- **Editable in-place** (PATCH `rate_pct`/`is_active`), NO append-only: la auditoría del % usado vive en `purchase_retentions.rate/base` (columnas E2 ya existentes, hoy vacías) que se persisten POR USO en cada liquidación. Cambiar la tarifa afecta solo liquidaciones futuras.

## 3. Backend

**Schemas** (`schemas/third_party.py`, junto a los del addendum):
- `RetentionConfigCreate`: `retention_type: Literal["retefuente","reteiva","ica"]`, `municipality: Optional[str]` (validator: obligatorio si ica, prohibido si no), `rate_pct: Decimal` (gt=0, le=100).
- `RetentionConfigUpdate`: `rate_pct?`, `is_active?`.
- `RetentionEntityResponse` (existente) **gana campos**: `config_id: Optional[UUID]`, `concept: Optional[str]`, `rate_pct: Optional[float]`, y `id` se renombra `entity_id: Optional[UUID]` (una config sin entidad lo trae NULL). **F2 QA: el renombre va ATÓMICO backend+frontend** — los consumidores del addendum (LiabilitiesPage/Liquidate/types/service) se reworkean en este mismo ciclo.

**D-v2-1 — GET unificado (evolución del addendum, no endpoint nuevo)**: `GET /third-parties/retention-entities` retorna la **UNIÓN** de configs y entidades, matcheadas por nombre canónico normalizado:
- Config + entidad → fila completa (config_id, entity_id, %, saldo).
- Config sin entidad (aún no usada) → fila con `entity_id=null`, `current_balance=0.0` — **esto resuelve el pre-crear ReteFuente/ReteIVA**: configurada = visible desde el día uno.
- Entidad sin config (nacida pre-v2 o de una liquidación manual vieja) → fila con `config_id=null`, `rate_pct=null`.
El frontend decide por nulidad: sin `entity_id` no hay Pagar/Estado de Cuenta; sin `config_id` no hay % ni precálculo.

**Endpoints nuevos** (mismo router third_parties, estáticos ANTES de `/{third_party_id}`, ambos `require_org_flag`):
- `POST /third-parties/retention-configs` — permiso `third_parties.create` (patrón F1 del addendum; **cero permisos nuevos**, D4 respetado). Idempotencia: si existe config activa para (tipo, municipio, concepto normalizados) → **409 cuyo detail incluye el `config_id` existente** (refinamiento QA: el frontend ofrece "editar la existente") — a diferencia del POST de entidades que reutilizaba: duplicar config con OTRO % sería ambigüedad de tarifa.
- `PATCH /third-parties/retention-configs/{id}` — permiso `third_parties.create` (gestionar el catálogo es la misma capacidad que crearlo).
- El `POST /retention-entities` del addendum **se elimina** (su único consumidor era el dialog transicional; las entidades siguen naciendo get-or-create al liquidar). Menos superficie.

**Liquidación — corrección F1 del QA**: el passthrough YA EXISTE completo desde el addendum — `PurchaseRetentionCreate.rate/base` (schemas/purchase.py:235-236) y `_apply_retentions` los persiste (purchase.py:1365-1366). **Trabajo backend de rate/base en v2: CERO** — solo el frontend los puebla desde el precálculo. `amount` sigue siendo la única fuente de verdad (sin recomputar server-side; editar el monto es la esencia del requerimiento).

## 4. Frontend

**Tab propio "Retenciones" (cambio de Daniel, supersede el grupo en Pasivos)**: página nueva `RetentionsPage` en Tesorería (ruta `/treasury/retentions`), entrada de sidebar con `orgFlag="kg_ledger_enabled"` (solo SAC la ve) + permiso `third_parties.view` (coherente con el endpoint, F1). El tab **crece a futuro** con informes/certificados (Q-08). Consecuencia limpia: **LiabilitiesPage vuelve a su estado pre-addendum** (se retira el grupo + dialog + hooks — página compartida sin rastro SAC; W5 en MovementCreate se conserva).
- Filas del GET unificado: label amigable (+ concepto si existe) + **columna %** + saldo + badge Sistema. Sin `entity_id` → sin Pagar/Estado (config aún sin uso); sin `config_id` → botón "Configurar %" (dialog pre-llenado con tipo/municipio).
- **"Agregar Retención"**: dialog Tipo (Select 3) → Municipio (Input solo ica — punto de captura del catálogo, dedup H4 en servicio) → Concepto (Input opcional) → % tarifa. Editar % con lápiz → PATCH. Desactivar (soft) → sale del selector de liquidación; la entidad y su saldo siguen visibles si existen.

**PurchaseLiquidatePage — fila de retención**: los DOS campos (tipo + municipio) colapsan en UN Select "Retención" que lista las configs activas (labels: `ReteFuente (2,5%)`, `ICA — Barranquilla (0,7%)`) + item "+ Agregar retención…" (dialog completo, crea config y auto-selecciona). Al elegir: `monto = rate_pct × subtotal materiales / 100` (quantize 0.01) **pre-llenado y editable** — cue visual estilo PriceSuggestion (#10): hint "Sugerido: $X (0,7% de $Y)" clickeable para restaurar si el usuario editó. El payload arma `retention_type`/`municipality` desde la config + `rate`/`base`/`amount` (F1: el backend ya los acepta y persiste — cambio 100% frontend). **El camino manual sin config se elimina de la UI** (visión de Daniel: un solo flujo; la retención no configurada se agrega al catálogo en el momento) — el API sigue aceptando payloads sin rate/base (compat).

## 5. Tests (~12) y gates

- Config CRUD: crear ica/retefuente OK · dup H4 ("bogota" tras "Bogotá") → 409 · rate 0/101 → 422 · municipality faltante en ica / presente en retefuente → 422 · PATCH rate · soft delete.
- GET unificado: config+entidad matcheadas · config sin entidad (balance 0, entity_id null) · entidad huérfana (config_id null) · aislamiento multi-org.
- Flag-off → 403 (GET/POST/PATCH) · RBAC viewer lee, no crea.
- Liquidación: payload con rate/base → persistidos en purchase_retentions · sin rate/base → camino D9 intacto (regresión byte).
- **Gates**: suite completa (~1277) con 16 D9 + 7 addendum intactos · `schema_parity_check.py` (tabla nueva en modelo Y migración) · tsc + build · golden por-construcción (tabla nueva + endpoints flag-gated + passthrough opcional = orgs prod intactas; mecánico re-corre al replicar pre-deploy como siempre).

## 6. Limitaciones conocidas / preguntas

- **Base del precálculo = subtotal de materiales** (antes de comisiones/cargos). Si contabilidad espera otra base (ej. ReteIVA sobre el IVA — que el modelo no discrimina), el monto editable lo absorbe; anotar en la capacitación.
- ~~Un % por (tipo, municipio)~~ **Resuelto por F3**: `concept` opcional modela tarifas múltiples por tipo desde v2 (ReteFuente compras 2,5% + ReteFuente servicios 4% = dos configs). Q-10 queda solo como validación con las tarifas reales de Johana.
- Migración de datos: NO hay — las entidades existentes aparecen como huérfanas hasta que se les configure %; cero backfill.

## 7. Secuencia

1. Migración + modelo + parity check.
2. Schemas + service (unicidad H4) + endpoints + tests backend.
3. GET unificado (evolución) + retirar POST entities + ajustar tests addendum.
4. Frontend Pasivos + Liquidate + tsc/build.
5. Suite completa + informe con evidencia → pruebas manuales Daniel → GO → commit.
