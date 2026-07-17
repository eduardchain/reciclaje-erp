# Informe post-código — Retenciones v2: catálogo con precálculo (CC-006)

**Plan**: `plan-retenciones-v2.md` v1.1 (QA GO condicionado 2026-07-17, F1/F2/F3 incorporadas + cambio de Daniel: tab propio) · **Base**: develop `09794ae`

## 0. Resumen

Catálogo configurable de retenciones (tipo + municipio + concepto opcional + % tarifa) con precálculo editable al liquidar. Tab propio **Tesorería → Retenciones** (solo SAC, crece a futuro con informes Q-08); LiabilitiesPage **restaurada byte a byte a su estado pre-addendum** (`git show d11a5ed` — cero rastro SAC en página compartida). 1 migración aditiva. Las 3 condiciones del QA aplicadas.

## 1. Archivos

**Backend (7):**
- `models/retention_config.py` (NUEVO) + registro en `models/__init__.py`: tabla `retention_configs` — String+CHECK (no pg_enum), CHECK `(type='ica') = (municipality IS NOT NULL)`, rate 0<x≤100, `concept` String(60) NULL (**F3**), soft delete.
- `alembic/versions/c2d3e4f5a6b7_retention_configs.py` (NUEVO): la migración del ciclo — create_table + índice org (espejo exacto del modelo, D13). Aplicada en dev 5434; prod via /deploy.
- `services/retention_entities.py`: `list_retention_rows()` (GET unificado D-v2-1: configs ∪ entidades matcheadas por tipo+municipio normalizado H4; los 3 sabores de fila) + `find_active_config()` (unicidad en servicio, D14) + `_parse_entity()`. `resolve_retention_entity` y `normalize_entity_name` **intactos** (F3 del addendum).
- `schemas/third_party.py`: `RetentionConfigCreate` (Literal 3 tipos, validator municipio⟺ica, concept opcional) / `RetentionConfigUpdate` / `RetentionRowResponse` (**F2**: `id` → `entity_id` nullable, atómico con el frontend). `RetentionEntityCreate/Response` eliminados.
- `endpoints/third_parties.py`: GET `/retention-entities` evolucionado al unificado · `POST /retention-configs` (409 con `config_id` en el detail — refinamiento QA) · `PATCH /retention-configs/{id}` (rate/is_active; reactivar con colisión → 409) · **POST `/retention-entities` eliminado** (menos superficie). Permisos F1 (`third_parties.view`/`create`), `require_org_flag` en los 3.
- `tests/test_retention_entities.py` (reescrito, 10 tests) + `tests/test_purchase_retentions.py` (+1: `test_rate_base_passthrough_persisted` — rate/base auditados, amount NO recalculado server-side).

**Frontend (9):**
- `pages/treasury/RetentionsPage.tsx` (NUEVO): el tab — tabla (Retención+badges / % Tarifa / Saldo / Acciones), filas de los 3 sabores (Sin uso aún · Sin tarifa · Inactiva), Agregar Retención (tipo/municipio/concepto/%), editar % (con nota "aplica a futuras"), desactivar/reactivar, Pagar y Estado de Cuenta (solo con entidad), search + mostrar inactivas, mobile cards. Exporta `retentionRowLabel()` (label canónico compartido).
- `App.tsx` + `Sidebar.tsx` + `constants.ts`: ruta `/treasury/retentions` con guard `FP` (flag + `third_parties.view`) y entrada "Retenciones" (ícono %, `orgFlag`) bajo Tesorería — orgs prod jamás la ven.
- `pages/treasury/LiabilitiesPage.tsx`: **restaurada de `d11a5ed`** (pre-addendum exacto).
- `pages/purchases/PurchaseLiquidatePage.tsx`: la fila de retención colapsa a **UN Select** de tarifas (`ReteFuente (2,5%)`, `ICA — Barranquilla · Compras (0,7%)`) + "+ Agregar retención…" (dialog completo, crea y auto-selecciona). Monto = precálculo vivo (`% × subtotal`, se re-deriva si cambian precios mientras no se toque) + editable; al editar aparece hint "Sugerido: $X (r%)" clickeable que restaura (patrón #10). Payload arma tipo/municipio desde la config + `rate`/`base` (F1: backend ya los persistía — cambio 100% frontend). Camino manual sin config eliminado de la UI; API compat intacta.
- `types/third-party.ts` / `services/thirdParties.ts` / `hooks/useMasterData.ts`: `RetentionRow`/`RetentionConfigCreate`/`Update`, `getRetentionRows`/`createRetentionConfig`/`updateRetentionConfig`, `useRetentionRows(enabled)` (**F2 preservado**: PurchaseLiquidatePage es compartida → `enabled=flag`; RetentionsPage va tras FP) + mutaciones con invalidación `["third-parties"]`.

## 2. Decisiones de implementación (margen del plan)

1. **Precálculo con re-derivación viva**: mientras el usuario no edite el monto (`touched=false`), el sugerido se recalcula si cambian los precios de las líneas — evita montos obsoletos. Editado → se conserva y el hint permite restaurar.
2. **409 con config_id como texto** en el detail (`[config_id=…]`): suficiente para el mensaje al usuario; un detail estructurado (dict) rompería `getApiErrorMessage`. El flujo "editar la existente" vive en el tab.
3. **Filas con misma entidad** (dos conceptos de ReteFuente): ambas muestran el saldo de SU entidad — el acreedor es uno, la tarifa varía (documentado en el service).
4. **Reactivar config desactivada** valida colisión contra las activas (409) — sin esto, desactivar+crear+reactivar duplicaría tarifas.
5. El endpoint PATCH devuelve la fila SIN resolver entidad (entity_id null) — el refetch del GET unificado la trae completa; evita duplicar el matching en dos lugares.

## 3. Gates

| Gate | Resultado |
|---|---|
| Dominio retenciones (17 D9+nuevo + 10 catálogo v2) | ✅ `27 passed in 43.13s` |
| `npx tsc --noEmit` | ✅ exit 0 |
| `npm run build` | ✅ built in 3.89s |
| Referencias huérfanas del contrato viejo (F2) | ✅ grep `useRetentionEntities\|RetentionEntityResponse\|createRetentionEntity` = 0 |
| Migración aplicada en dev + espejo modelo | ✅ `c2d3e4f5a6b7` — `\d retention_configs` verificado columna a columna |
| Smoke live (dev, datos reales de Daniel) | ✅ POST configs · **GET unificado matcheó las entidades reales del walkthrough** (ReteFuente −$5.000, ICA Barranquilla −$25.000 vía H4) · dup "barranquilla" → 409 |
| **Suite completa** | ✅ **`1269 passed in 1830.93s (0:30:30)`, exit 0** — reconcilia exacto: 1265 baseline − 7 (tests viejos del addendum reescritos) + 10 (catálogo v2) + 1 (rate/base) = 1269. Cero regresiones |
| `schema_parity_check.py` (secuencial, tras la suite) | ✅ **DIFF CERO fuera del baseline** — 56 tablas, 247 índices, 267 constraints; `retention_configs` modelo ≡ migración |

**Incidente de proceso (transparencia)**: la primera corrida de la suite completa se invalidó — lancé en paralelo el test nuevo de rate/base y su conftest hizo DROP SCHEMA sobre el 5433 que la suite ocupaba (la regla "un solo dueño de 5433" aplica a TODO pytest, no solo al parity check). Se detuvo la corrida envenenada y se relanzó limpia; el resultado reportado será el de la corrida limpia.

## 4. Guía de walkthrough (Daniel) — ✅ CHECKED 2026-07-17

**Pruebas manuales de Daniel: GO ("se ve bien, de mi lado pruebas manuales checked").** Los 9 pasos ejercitados sobre dev con las tarifas sembradas del smoke.

Quedaron sembradas del smoke: ReteFuente 2,5% e ICA Barranquilla 0,7% (matcheadas a tus entidades con saldo real).

1. **Tab nuevo** — Tesorería → **Retenciones**: ves las 2 tarifas con su % y los saldos reales (−$5.000 / −$25.000), badges Sistema. Pasivos ya NO tiene el grupo (volvió a su estado de siempre).
2. **Agregar** — "Agregar Retención": ICA + "Soledad" + 0,5% → aparece con badge "Sin uso aún" y saldo "—". Repetir con "barranquilla" (minúscula) → error claro de duplicado (H4).
3. **Concepto (F3)** — agregar ReteFuente + concepto "Servicios" + 4% → dos filas ReteFuente (la general 2,5% y la de Servicios 4%).
4. **Editar %** — lápiz sobre ReteFuente 2,5% → cambiar a 3,5% → guarda; la nota aclara que aplica a liquidaciones futuras. Probar desactivar/reactivar.
5. **Liquidación** — nueva compra (ej. 500 kg @ $2.000) → Liquidar → Retenciones: **UN selector** con las tarifas; elegir "ICA — Barranquilla (0,7%)" → monto pre-llenado ($7.000 = 0,7% de $1.000.000) con nota gris "0,7% de $1.000.000 — editable".
6. **Editar el monto** → aparece "Sugerido: $7.000 (0,7%)" en índigo; clic lo restaura. Probar también "+ Agregar retención…" desde el selector.
7. **Confirmar** → detalle de la compra con las retenciones y el neto; el tab Retenciones muestra los saldos crecidos; **Pagar** desde ahí funciona como antes.
8. **Regresión Costa** — org sin flag: sidebar SIN "Retenciones", Pasivos idéntica, liquidación sin sección, Network sin requests a retention-*.
9. **Mobile 390px** — tab y dialogs usables (cards, botones full-width).

## 5. Fuera de alcance (sin cambios)

Certificados/resumen mensual (Q-08) · retenciones en ventas · bases distintas al subtotal (el monto editable las absorbe; anotar en capacitación) · Q-10 queda como validación con las tarifas reales de Johana (el modelo ya las soporta via concept).
