# Informe post-código — SAC E1 "Configuración" (paso 5 del ciclo)

**De:** Code · **Para:** QA · **Fecha:** 2026-07-16
**Plan:** `docs/planes/plan-sac-e1-configuracion.md` v1.2 (ciclo de plan cerrado por QA 2026-07-16, GO firme)
**Estado:** implementación COMPLETA del alcance §1.1 (9 bloques). Sin commit — pendiente GO de QA + pruebas manuales de Daniel (way of work §5).

---

## 1. Qué se entrega (alcance §1.1, bloque por bloque)

| # | Bloque | Estado | Dónde |
|---|---|---|---|
| 1 | Migración A: 13 CREATE TABLE | ✅ | `alembic/versions/b5c8e1a2f3d4_sac_e1_create_tables.py` |
| 2 | Migración B: 7 ALTERs + 2 índices, espejo en 7 modelos | ✅ | `c6d9f2b3a4e5_sac_e1_alter_columns.py` + models |
| 3 | Migración C: 6 permisos SIN role_assignments (D4) | ✅ | `d7e0a3c4b5f6_sac_e1_permissions.py` |
| 4 | Settings D3: JSONB + `OrgSettingsPayload` + `get_org_setting` + exposición | ✅ | `schemas/organization.py`, `utils/org_settings.py`, `schemas/system.py`, `endpoints/system.py` (3 builders) |
| 5 | ServiceTariff: servicio append-only + 3 endpoints + pantalla | ✅ | `services/service_tariff.py`, `endpoints/service_tariffs.py`, `pages/config/TariffsPage.tsx` |
| 6 | MCF: validación Anexo D + servicio + 3 endpoints + pantalla | ✅ | `services/material_conversion_formula.py`, `endpoints/material_conversion_formulas.py`, `FormulasPage.tsx` |
| 7 | Driver/Vehicle: CRUD + D14 + pantalla `/config/fleet` | ✅ | `services/fleet.py`, `endpoints/fleet.py`, `FleetPage.tsx` |
| 8 | Frontend flags: `useOrgSettings` + `FlagGate` + gating tabs/sidebar/rutas | ✅ | `hooks/useOrgSettings.ts`, `components/auth/FlagGate.tsx`, `Sidebar.tsx`, `ConfigLayout.tsx`, `App.tsx` (guard `FP`) |
| 9 | Guion de pruebas E1 para Johana | ✅ | plan §9 "Done funcional" (sin cambios — sigue vigente) |

Nuevos módulos backend: 7 archivos de modelos (13 tablas), 3 schemas, 3 servicios, 3 endpoints, 4 routers (`/service-tariffs`, `/material-conversion-formulas`, `/drivers`, `/vehicles`). Frontend: 2 hooks, 1 guard, 1 types, 1 service, 3 páginas, registro cuádruple (constants/App/Sidebar/ConfigLayout).

---

## 2. Evidencia (contrato exigido por QA en el cierre del plan)

### 2.1 Suite completa en 5433 — CERO fallos

```
$ ./venv/bin/pytest -q -p no:cacheprovider --no-cov
====================== 1179 passed in 1403.20s (0:23:23) =======================
```

Incluye los **47 tests nuevos** de E1: `tests/test_org_settings.py` (11) + `tests/test_sac_e1_config.py` (36: ServiceTariff 10, MCF 12, Fleet 10, constraints kg_ledger 4 — varios con sub-casos internos). Mapeo contra plan §8: caso feliz por bloque, tiebreaker por id con `created_at` empatado, D11a/b/c/d, regla SEC (dual + anti-mezcla), normalización subtype a lower persistida, 401/403 RBAC ± (viewer sin permiso — D4), aislamiento multi-tenant con **admin propio en org2** (advertencia del plan sobre `org_headers2` atendida: fixture `org2_admin_headers`), append-only 405/404, placa activa duplicada/reutilizable/reactivación-colisión, CHECKs por IntegrityError y UNIQUE NULLS NOT DISTINCT.

### 2.2 Condición H1 — round-trip `transfer_tolerance_pct` VERDE

`test_transfer_tolerance_pct_roundtrip_jsonb`: PATCH de sistema con el payload COMPLETO (incluido el float 0.05) → 200 → `get_org_setting` retorna `0.05` como `float` → el JSONB persiste `0.05` y `[30,60,90]`. Refuerzo no pedido: `OrgSettingsPayload` quedó `strict=True` — sin él, el modo lax de Pydantic v2 acepta `"yes"` como bool y el test del plan (`"kg_ledger_enabled": "yes"` → 422) NO pasaría. Verificado: `"yes"`, `"30"`, `aging_buckets: 30`, clave desconocida y `1.5` fuera de rango → todos 422.

### 2.3 Condición H3 — schema-diff dev-migrado vs test-create_all = CERO

Herramienta nueva **reutilizable para E2-E5**: `backend/scripts/schema_parity_check.py` (recrea 5433 con create_all, diffea columnas/índices/constraints contra 5434 vía `pg_indexes`/`pg_get_constraintdef` — definiciones verbatim).

```
=== Indices foco H3 (verbatim, ambos lados identicos) ===
CREATE UNIQUE INDEX ix_kg_ledger_account_org_type ON public.kg_ledger_accounts USING btree (organization_id, account_type, warehouse_id) NULLS NOT DISTINCT
CREATE INDEX ix_kg_movement_account_date ON public.kg_ledger_movements USING btree (account_id, transaction_date DESC)
CREATE INDEX ix_mcf_material_current ON public.material_conversion_formulas USING btree (material_id, willard_account_subtype, created_at DESC)
CREATE INDEX ix_st_code_current ON public.service_tariffs USING btree (organization_id, tariff_code, created_at DESC)

=== ✓ DIFF CERO fuera del baseline === 53 tablas, 238 indices, 250 constraints comparados.
```

**Baseline pre-existente declarado (50 items, CERO de E1)** — divergencias históricas dev↔modelos que E1 no introdujo, codificadas en el script con justificación por categoría: (a) tabla one-shot `backfill_liquidated_at_audit` (decisión #43, solo en dev/prod, nunca en modelos); (b) FKs con nombre explícito en migraciones viejas (`fk_*`) vs default de PG en create_all — misma definición, otro nombre (double_entries, expense_categories, fixed_assets, money_movements, organization_members, profit_distributions, purchases, sales, scheduled_expenses); (c) índices renombrados (double_entry_lines, organization_members); (d) índice `organization_id` del mixin ausente en dev en 3 tablas viejas; (e) `permissions` unique-index style; (f) `uq_obligation_accrual_period` — predicado WHERE semánticamente idéntico, rendering distinto de PG. **Guard anti-abuso**: cualquier divergencia que mencione un objeto E1 (`E1_MARKERS`) NUNCA entra al baseline aunque su tabla esté listada — una divergencia nueva da exit 1. Las migraciones E1 crean FKs SIN nombre (default PG) exactamente para dar paridad con create_all.

### 2.4 Golden comparison — diff EXACTAMENTE CERO

Flujo completo (plan §7): `replicate_prod.sh` (backup fresco de prod, incluye la org SAC de E0) → captura **ANTES con código pre-E1** (git worktree de `main` en puerto 8001 — el código E1 no puede consultar un schema sin migrar, y capturar el "antes" con código nuevo invalidaría la comparación) → `alembic upgrade head` (A/B/C sobre la réplica) → captura DESPUÉS con código E1 (8002) → diff estructural profundo.

```
Orgs comparadas: ['Biogreen SAS', 'MetaRecycling', 'Reciclajes de la Costa']
✓ GOLDEN DIFF EXACTAMENTE CERO — 3 orgs x 10 secciones
```

Secciones por org: P&L del mes corriente (2026-07-01→16), Balance General, Balance Detallado, Cash Flow del mes, saldos de cuentas, **estado de cuenta unificado del tercero más caliente** (el de más MMs confirmados — misma selección determinista en ambas capturas, id incluido en el diff), y smoke de listados calientes (compras/ventas 20 filas + conteo tesorería) con las columnas nuevas en NULL. Snapshots: `golden_before.json` / `golden_after.json` (711 KB c/u) en el scratchpad de la sesión. El delta capturado es EXACTAMENTE el delta del deploy: código+schema viejos → código+schema nuevos, mismos datos.

### 2.5 Migraciones aplicadas en dev (5434)

Aplicadas DOS veces limpiamente: sobre el dev previo y sobre la réplica fresca de prod (a4317e2cd050 → b5c8e1a2f3d4 → c6d9f2b3a4e5 → d7e0a3c4b5f6). 5433 no se migra (conftest recrea por modelos — no se reporta como paso, conforme §3.3). Verificación en BD de la réplica migrada: 7 orgs todas con `settings IS NULL`; 6 permisos sembrados (sort 129-130, 140-143); **`role_permissions` de los 6 permisos = 0 filas** (D4: cero capacidad nueva para clientes existentes, verificado).

### 2.6 Frontend: tsc + build + verificación §7

- `npx tsc --noEmit`: limpio. `npm run build`: limpio (3.65s).
- **No-regresión del filtro (§5.1)** — verificación por construcción, documentada línea por línea: `Sidebar.tsx` solo consulta `flagEnabled` para entradas CON `orgFlag` (`checkFlag = (flag) => !flag || flagEnabled(flag)`); en loading/error/NULL `useOrgSettings` retorna defaults → `flagEnabled=false` → SOLO se ocultan las 3 entradas nuevas; las entradas sin `orgFlag` pasan por el mismo código de siempre. Ídem `ConfigLayout`. El query de settings NO gatea el render del sidebar (no se espera su loading).
- **Estados verificados a nivel API** (réplica): `GET /organizations/{id}` de las 3 orgs reales retorna `settings: null` → tabs/sidebar/rutas nuevos ocultos para TODAS las orgs hoy (el flag se enciende solo en SAC el viernes post-deploy).
- **Ruta protegida (D12)**: guard compuesto `FP` (FlagGate ∘ PermissionGate) en las 3 rutas — un admin de otra org que deep-linkee `/config/tariffs` ve AccessDenied por flag apagado, no la página.
- **⚠️ Pendiente para las pruebas manuales de Daniel (paso 6)** — lo que exige ojos en DevTools y no puedo certificar desde acá: sidebar idéntico pixel-a-pixel pre/post en org sin flag (admin y no-admin), los 3 estados del query en red lenta, y mobile 390x844 de las 3 pantallas nuevas (construidas mobile-first: overflow wrapper en tablas, dialogs `grid-cols-1 sm:grid-cols-2`, botones `w-full sm:w-auto`, MoneyInput con teclado decimal).

### 2.7 Pre-demo (§9)

Materiales de E0 verificados en la réplica: SAC tiene 7 materiales en `unidad` (BAT-*) y 12 en `kg` — la carga de fórmulas de Johana no chocará con D11c.

---

## 3. Decisiones de implementación (desviaciones menores declaradas, way of work §5)

1. **`OrgSettingsPayload` con `strict=True`** (además de `extra="forbid"`): el plan exige `"yes"` → 422 pero el modo lax de Pydantic v2 acepta `"yes"/"on"/"1"` como bool y `"30"` como int. Strict lo garantiza a nivel de tipo; `float` estricto sigue aceptando int (0 y 1 válidos para la tolerancia). Espíritu de D3 ("ni tipos basura"), sin cambio de contrato.
2. **Parámetros MCF: Decimal en el contrato, números JSON-nativos en el JSONB.** El plan §4.4 tipa los params con Decimal (validación exacta) — pero persistirlos tal cual reproduciría el bug H1 (json.dumps del engine). Property `canonical_parameters` en el schema Create convierte Decimal→float SOLO al persistir; el JSONB almacena `{"lead_percentage": 0.53}` como los ejemplos del Anexo D. El consumidor de E2 lee con `Decimal(str(x))` (mismo contrato del watch-point de tolerance registrado para E3).
3. **Normalización de subtype a lower en el SCHEMA** (BeforeValidator), no en el servicio como lista §4.4: el `Literal["escurrido","pinza"]` rechazaría `"ESCURRIDO"` con 422 antes de llegar al servicio. El contrato observable es idéntico (input case-insensitive → persiste lower; test lo asserta contra la BD).
4. **D11b (custom → 422) en el dispatch del schema**, no en el servicio: no existe params-model para custom, el rechazo tiene que ocurrir antes del dispatch. Mismo status y mensaje.
5. **Colisión de placa también en UPDATE** (spec-plus sobre D14): cambiar placa o REACTIVAR un vehículo valida contra los activos (test: crear v2 con la placa del inactivo v1 → reactivar v1 → 422). Sin esto la regla "una placa activa" se rompe por la puerta de atrás.
6. **Estructura de tests**: 47 en 2 archivos (plan estimaba ~45) — `test_org_settings.py` con clase de escritura + clase del helper; constraints kg_ledger con `pytest.raises(IntegrityError, match=<nombre del constraint>)`.

## 4. Incidente de proceso (documentado)

`schema_parity_check.py` hace DROP SCHEMA en 5433 — lo corrí mientras la suite completa corría ahí en background y maté esa corrida (falló por catálogo, no por código). Se relanzó secuencial y limpia; el script quedó con la advertencia "NO correr con pytest en curso" en el docstring. Cero impacto en dev/prod.

## 5. Pendientes del ciclo (no bloquean este informe)

- **H2 — RATIFICADA por Daniel 2026-07-16**: diferimiento de `transfers` a E3 confirmado. Nada bloquea el deploy del viernes 2026-07-24.
- **Viernes post-deploy**: encender SOLO `kg_ledger_enabled: true` en la org SAC vía system PATCH **con el payload completo** (semántica REPLACE, D3) + demo con guion §9.
- **H4 al cierre**: conteos de permisos en CLAUDE.md #25/#26 (se actualizan en el commit de E1: catálogo real 78 → **84**).
- Deploy solo vía `/deploy` (regla); commit a develop tras GO de QA + pruebas de Daniel.

---

## 6. Veredicto QA (paso 5 — cerrado 2026-07-16)

**GO.** Los 6 puntos del contrato verificados de primera mano por el QA (re-run propio de los 47 tests: `47 passed in 52.64s`; diff propio de los snapshots golden: idénticos; re-run propio del parity check: DIFF CERO — 53 tablas, 238 índices, 250 constraints; cadena alembic + BD dev + catálogo 84 confirmados). Las 6 desviaciones de §3 aceptadas. Paso 6 (pruebas manuales de Daniel) autorizado.

Hallazgos del veredicto (ninguno bloquea E1; **reglas para E2-E5**):

1. **MENOR — el gate de paridad excluye `server_default`** (punto ciego declarado en el docstring, pre-existente repo-wide). Aceptado para E1 porque los tests corren contra el schema de create_all y delatarían un default de BD faltante con efecto de comportamiento. **Regla E2-E5**: toda tabla nueva cuyo comportamiento dependa de un default de BD debe declararlo TAMBIÉN en el modelo — el gate no lo atrapará. Anclada en el docstring de `schema_parity_check.py`.
2. **SUGERENCIA — preservar el output completo de la suite**: el log entregado fue solo el tail (el header con `collected`/warnings se perdió en el relanzamiento post-incidente). **Regla E2-E5**: `pytest ... 2>&1 | tee suite.log` desde el inicio.
3. **Nota de proceso**: secuencia de evidencia para E2-E5 = suite completa → después parity check, **nunca en paralelo** (ambos son dueños de 5433).
