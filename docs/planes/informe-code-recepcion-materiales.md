# Informe post-código — Recepción simplificada + maestro de materiales (SAC)

**Conjunto:** `{E2 (sin commitear) − willard_account_subtype + material_kg_profile}` — plegado al working tree de E2.
**Plan:** `plan-sac-recepcion-y-materiales.md` (GO CONDICIONADO §13).
**Control de cambios:** CC-001 (SEC→2 materiales), CC-002 (scrap→%), CC-004 (recepción 4→2 tipos), CC-005 (clasificación en el material).
**Fecha:** 2026-07-16/17. **Estado:** para re-QA del conjunto combinado antes del commit atómico.

---

## 0. Resumen

Se desmontó el `willard_account_subtype` que E2 construyó y se simplificó el modelo de recepción a **2 tipos** con **ruteo de cuenta kg por línea** según la clasificación del material (nueva tabla SAC-only `material_kg_profiles`). Se eliminó el 3er tipo de fórmula (`scrap_with_terminal_to_lead`). Todo el cambio es **aditivo/quirúrgico sobre tablas SAC flag-gated que están VACÍAS para las 3 orgs prod** — cero superficie nueva en paths compartidos.

**Las 4 condiciones vinculantes de QA (§13):**
| # | Condición | Estado |
|---|-----------|--------|
| 1 | Conjunto fusionado va a re-QA antes del commit atómico | ✅ este informe |
| 2 | §12 D1-D7 + D-adj vinculantes | ✅ tabla §5 |
| 3 | **F1**: `grep willard_account_subtype = 0` + test que ejerza el snapshot Willard post-drop | ✅ §3 |
| 4 | Golden 3 orgs diff-cero + `schema_parity_check` BLOQUEANTE | ✅ parity §4; 🟡 golden mecánico requiere autorización (prueba por-construcción en §6) |

---

## 1. Alcance entregado

**Backend**
- `willard_account_subtype` eliminado de fórmulas (modelo/schema/servicio/endpoint) e inbound (modelo/schema/servicio/endpoints). Índice `ix_mcf_material_current` recreado a 2 columnas `(material_id, created_at DESC)`.
- `scrap_with_terminal_to_lead` eliminado (CC-002): `FormulaType` queda `battery_to_lead | drosses_to_lead | custom(bloqueado)`; `ScrapWithTerminalParams`, `SUBTYPE_ALLOWED_FORMULA_TYPES`, `WillardSubtype` borrados. El servicio conserva el guard de coherencia unidad↔tipo.
- **`material_kg_profiles`** (NUEVA, SAC-only, 1:1 opcional): `compra_regular` bool + `willard_world` (`none|postconsumo|drosses`, String+CHECK, no pg_enum) + `UNIQUE(org,material_id)`. Modelo + schema + servicio (upsert/list/get) + endpoints (`/material-kg-profiles`, gated `require_org_flag("kg_ledger_enabled")`, permisos `materials.view/edit`).
- Inbound `inbound_type` colapsado a **`purchase | willard`** (CC-004). Ruteo por-línea `KG_SOURCE_BY_WORLD`/`WORLD_LABELS`: cada línea Willard resuelve su cuenta según el `willard_world` del material (postconsumo→baterías por sede; drosses→drosses org-wide). Una orden puede tocar varias cuentas kg (mundos mixtos). Snapshot de fórmula sin subtype.
- `formula_type` se auto-deriva de la unidad en el frontend (sin elección del usuario); el backend lo mantiene y valida coherencia (decisión de diseño §7).

**Frontend** (tsc + build limpios)
- Types: `sac-config.ts` (fórmulas sin scrap/subtype + `MaterialKgProfile*` + `WillardWorld` + `formulaTypeForUnit`), `inbound-order.ts` (2 tipos, sin subtype).
- Servicio + hooks: `getKgProfiles`/`upsertKgProfile` + `useKgProfiles`/`useUpsertKgProfile`.
- `FormulasPage`: sin selector de tipo ni Presentación ni scrap; tipo derivado de la unidad; **columna Clasificación Willard + diálogo "Clasificar Material"** (co-ubica factor + clasificación en la misma página SAC-only, intención §4.3 sin tocar el maestro compartido).
- Recepción (`InboundCreate/Edit/Detail`): 2 tipos; selector de material **filtrado por clasificación** (Willard→mundo≠none; Compra→compra_regular o sin perfil); Presentación/subtype removidos; nota por tipo actualizada.

---

## 2. Alcance DIFERIDO (declarado, no silencioso)

- **Selector recolector-comisionista** (plan §2.1): la generalización de `ruta`→recolector es un **ciclo propio de productización** (memoria `sac-ruta-generalizar-recolector-comision`: "NO bloquea go-live"). `ruta` colapsó en `purchase` (derivación idéntica) — cero funcionalidad perdida. La comisión del recolector (flow-a #30) + **flow-b Green Loop sobre postconsumo (D-adj/Q-02)** esperan respuesta de Johana; no se implementó una mecánica adivinada ("no supongamos nada").
- **`goes_directly_to_jm`** (Q-03): se conserva como campo informativo, sin lógica (utilidad dudosa pendiente de Johana).
- **F2 doc-only**: CLAUDE.md #74 dice baseline "50"; el real es 19 (parity §4). Se corrige al commitear.

---

## 3. F1 — GATE (evidencia)

**Grep = 0 en código de producción:**
- `rg willard_account_subtype app/` (backend) → **0**.
- `rg willard_account_subtype frontend/src/` → **0**.
- Referencias restantes (permitidas por §10): migración `b5c8e1a2f3d4` (creó la columna, historia), migración `b1c2d3e4f5a6` (la DROPea) y `tests/test_inbound_orders.py` (aserción F1 intencional).
- `rg scrap_with_terminal_to_lead app/` → solo un comentario CC-002 (documenta la remoción); cero código.

**Test que ejerce el snapshot Willard post-drop** (el `inbound_order.py:307` era un `AttributeError` en runtime que ni `tsc` ni `build` ni la compilación atrapan):
- `TestWillardCreate::test_postconsumo_happy_identity` crea una recepción Willard → `_apply_willard_effects` construye el `conversion_formula_snapshot` → aserción explícita `assert "willard_account_subtype" not in movs[0].conversion_formula_snapshot`. **Verde.**

---

## 4. schema_parity_check — GATE BLOQUEANTE

`./venv/bin/python3 scripts/schema_parity_check.py` → **✓ DIFF CERO fuera del baseline** (55 tablas, 245 índices, 262 constraints). `material_kg_profiles` y el índice `ix_mcf_material_current` reconstruido **no aparecen en ninguna lista de divergencia** → idénticos entre la migración y `create_all`. El baseline vivo es de 19 entradas pre-existentes (FKs `fk_*` vs `_fkey`, `ix_org_members`, permissions unique, backfill audit) — ninguna introducida por este cambio (F2: CLAUDE.md #74 dice "50", real 19).

Migración `b1c2d3e4f5a6` (`down_revision = f9a2b3c4d5e6`, head E2): forward-drop de las 2 columnas subtype + recreación del índice 2-col + creación de `material_kg_profiles`. **Aplicada en dev (5434)** `f9a2b3c4d5e6 → b1c2d3e4f5a6` sin error. `downgrade()` completo (restaura columnas + índice 3-col + dropea la tabla). No reescribe historia (E1/E2 ya corrieron en dev+QA, NUNCA prod).

---

## 5. Cumplimiento §12 D1-D7 + D-adj (vinculantes)

| Hallazgo | Manejo |
|---|---|
| **D1** KeyError por colapso 4→2 (`KG_SOURCE_BY_TYPE`/`INBOUND_TYPE_LABELS` lookups literales) | Reescrito a ruteo **por-línea** `KG_SOURCE_BY_WORLD`/`WORLD_LABELS`; `label`/`kg_source`/cuenta resueltos dentro del loop por `willard_world`; `test_avg_cost_model_l.py` actualizado (`inbound_type="willard"` + perfil drosses + query I6). Test nuevo `test_mixed_worlds_route_per_line`. |
| **D2** Factor desacoplado de "es Willard" | El factor (`MaterialConversionFormula`) es independiente del perfil; se permite en cualquier material. El intersede E3 lo consumirá aparte. |
| **D3→F1** Blast radius real de subtype | Probado con `grep=0` (§3), no a mano. |
| **D4** DDL `material_kg_profiles` | PK GUID; FK org CASCADE, material CASCADE, created_by SET NULL; `UNIQUE(org,material_id)`; `willard_world` String+CHECK (no pg_enum); router gated `require_org_flag`; frontend en página SAC-only flag-gated (NO en el `MaterialFormDialog` compartido — desviación §7). |
| **D5** No filtrar `GET /materials` compartido | Correcto: el filtro por mundo es client-side en Recepción (lee `useKgProfiles` + `useMaterials`), y el servicio SAC `list` es endpoint aparte. El maestro compartido intacto. |
| **D6** Índice `ix_mcf_material_current` 2-col + parity bloqueante | Recreado exacto (§4); parity diff-cero. |
| **D7** "sin migración de datos" = de código; datos dev se reseedean | La migración solo toca estructura; datos dev throwaway (reseed pendiente de Q-01). |
| **D-adj** Green Loop flow-b | Diferido a Q-02 (§2), como QA lo adjudicó. |

---

## 6. Golden 3 orgs — prueba por-construcción + estado del run mecánico

**Argumento (riguroso, verificable):** el delta de ESTE cambio sobre E2 no puede alterar ningún reporte de las 3 orgs prod (Costa, Biogreen, MetaRecycling), porque:
1. `material_kg_profiles` nace **vacía** → 0 filas para orgs prod → invisible a todo reporte.
2. El drop de subtype es sobre `material_conversion_formulas`/`inbound_orders`, tablas **con 0 filas para las orgs prod** (no usan SAC; flag NULL).
3. Las queries incondicionales de E2 contra `inbound_orders` en paths compartidos (`_calculate_profit`, `_get_inventory_as_of`, `purchase.cancel`) ya fueron **probadas inertes por el golden de E2** (su BEFORE corrió contra el schema prod-nativo sin la tabla → diff-cero). Este cambio **NO agrega queries nuevas** en paths compartidos: `rg material_kg_profile app/services/{reports,purchase,sale}.py = 0`. `_load_kg_worlds` solo se invoca desde `_apply_willard_effects` (servicio inbound, router flag-gated → 403 para orgs con flag NULL).
4. El reruteo por-línea vive dentro del servicio inbound flag-gated → jamás alcanzable por las orgs prod.

**Proxy fuerte adicional:** la suite completa (§8) ejercita toda la lógica de reportes (P&L/BG/BD/CF/parity) sobre orgs SIN flag — exactamente los mismos paths que corren las 3 orgs prod. Suite verde ⇒ lógica de reportes intacta para no-SAC.

**Run mecánico:** el golden data-a-data (E1/E2) usa `replicate_prod.sh` (réplica fresca + **backup de prod** + worktree de `main` en :8001 para BEFORE + backend E2+cambio en :8002 + diff JSON). Es pesado, borra el estado de dev y requiere backup de prod — igual que E1/E2, que Daniel autorizó caso por caso ("correlo ya"). **Pendiente de tu visto bueno**; se corre naturalmente al replicar para el reseed (Q-01). El delta esperado es el mismo de E2 (diff-cero; la única diferencia previa fue el aditivo `retentions: []`, ajeno a este cambio).

---

## 7. Desviaciones / decisiones tomadas

1. **`formula_type` derivado**: el frontend lo auto-deriva de la unidad (unidad→battery, kg→drosses); el backend lo mantiene en el schema (restringido a 2 tipos) + guard de coherencia existente. Realiza "sin elección del usuario" (§4.2) preservando la validación Pydantic fuerte de parámetros, con mínimo blast radius. Equivalente funcional a derivar en backend (la unidad fija el tipo).
2. **Clasificación en página SAC-only, no en `MaterialFormDialog`**: se entregó la co-ubicación factor+clasificación (§4.3) en `FormulasPage` (SAC-only, ya flag-gated) en vez de plegar al `MaterialFormDialog` **compartido con las 3 orgs prod** — honra D4/D5 y la restricción "no dañar lo construido". Plegar al diálogo compartido queda como mejora opcional.
3. **Nombre de tabla plural** `material_kg_profiles` (convención del repo; el plan usa el concepto singular).
4. **Flake pre-existente de E2 corregido en tests** (no product code): dos archivos de E2 (`test_inbound_orders.py::test_annul_order_with_liquidated_purchase_400` y **los 15 de `test_purchase_retentions.py`**, §8) liquidaban con `datetime.now(utc).date()` mientras el validador de liquidación de compras usa `date.today()` (LOCAL) — en la ventana 00–05 UTC la fecha exigida es imposible (≥ doc UTC=17 y ≤ local=16). Se hicieron tz-robustos con fecha pasada (test-only). Nada que ver con este cambio; el validador de compras (product code, 3 orgs prod) NO se tocó. **Recomendación para E2/QA:** unificar el validador a UTC (o `date.today()` en todos los tests) — es una inconsistencia latente que muerde a cualquiera que corra la suite de noche.

---

## 8. Suite de tests

- **Archivos afectados (verdes):** `test_material_kg_profile.py` (nuevo, 8), `test_sac_e1_config.py` (reescrito), `test_inbound_orders.py` (reescrito) → **69 passed**; `test_avg_cost_model_l.py` (D1) → **36 passed**. Total afectados: 105.
- **Tests nuevos clave:** ruteo por-línea mundos mixtos, material sin perfil→422, aislamiento flag-off→403, RBAC viewer, worlds ortogonales, scrap-rechazado→422, una-vigente-por-material, F1 snapshot.
- **Suite completa (1er run, 01:00–01:30 UTC):** `15 failed, 1243 passed`. **Los 15 fallos = flake pre-existente de E2 en `test_purchase_retentions.py`** (D9), idéntico al de §7 pto 4: los tests liquidaban con fecha UTC (`now(utc).date()`) mientras el validador de compras usa `date.today()` LOCAL → en la ventana 00–05 UTC la fecha exigida es futura. **NADA que ver con este cambio** (retenciones no tocan subtype/profile/worlds). Corregido tz-robusto (helper `_biz_date()` con fecha pasada, test-only, product code intacto) → **`test_purchase_retentions.py` = 16 passed**.
- **Suite completa (re-run limpio tras el fix):** **`1258 passed in 1710.07s (0:28:30)`, 0 failed, exit code 0, coverage 92%** (task `bd3t9tu59`, output limpio confirmado). Verde adjunto para QA.

---

## 9. Prerrequisitos abiertos (no bloquean el código; sí el reseed/una rama)

- **Q-01** (Johana): lista real de materiales (baterías por ref + kg/unidad; drosses/seco-pinza/escurrido + %) con su clasificación de mundos → bloquea el **reseed y las re-pruebas**.
- **Q-02** (Johana): ¿Green Loop recolecta postconsumo Willard? → bloquea la **rama flow-b** de la comisión del recolector.

---

## 10. Próximo paso

Re-QA de este conjunto combinado → (con visto bueno) golden mecánico → commit atómico a develop → reseed con Q-01 → re-pruebas manuales.
