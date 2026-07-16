# Plan SAC E1 — "Configuración SAC" (fundaciones de datos + tarifas + fórmulas + flota)

**Versión:** 1.2 — 2026-07-16. **Estado:** ciclo de plan **CERRADO por QA** (2026-07-16): H1/H3/H5 cerrados sobre esta versión, **GO firme para implementar**. **H2 pendiente de ratificación de Daniel** (diferimiento de `transfers` a E3): NO bloquea el arranque de código (el diferimiento solo quita trabajo de E1), **SÍ debe resolverse antes del deploy del viernes 2026-07-24** — si Daniel lo rechaza, `transfers` entra a E1 y cambia el alcance del informe. Contrato del informe post-código exigido por QA: suite completa verde en 5433 con output adjunto, golden comparison diff cero con evidencia adjunta, schema-diff dev↔test cero con índices DESC y UNIQUE NULLS NOT DISTINCT visibles (H3), test round-trip de `transfer_tolerance_pct` verde (H1), verificación frontend §7 + 390px/1280px, migraciones aplicadas en 5434.
**Base canónica:** requerimientos-funcionales.md v0.5 (§11 modelo de datos, §6.3-§6.4 tarifas/fórmulas, §12.1.2-§12.1.3 endpoints, §12.2.3, §14.1 RBAC, §15 migración, Anexo C/D) + plan-ejecucion-fase1.md (E1, §1 no-regresión, §5 ciclo).
**Entrega comprometida:** fin semana 1 (viernes 2026-07-24): deploy + demo + guion de pruebas. "SAC prueba: Johana carga y valida las tarifas y factores reales."
**Historial:** v1.0 borrador → ronda interna adversarial de pre-QA (4 lentes) → v1.1 incorpora sus hallazgos (3 MAYOR + 15 precisiones; 1 refutado: lote develop ya deployado) → **revisión QA formal 2026-07-16: GO condicionado** (14 claims fácticas verificadas, 12/13 TRUE + 1 defecto latente destapado) → v1.2 incorpora H1/H3/H5.

---

## 0. Validación de requerimientos (regla obligatoria CLAUDE.md)

Se validó E1 contra v0.5 completo (6 extracciones paralelas) y contra el código actual. **Se encontraron gaps** — ninguno bloquea E1, pero exigen decisiones que este plan toma explícitamente (D1-D12, abajo) para que QA las confirme o refute. Hallazgos estructurales:

1. **"12 tablas" es nominal.** §11.1 declara "doce" pero el conteo físico especificado es **13**: `InboundOrderLine` no se cuenta (§11.1.12 la menciona como "líneas"), y `FurnaceCharge`/`CrucibleCharge` pueden ser 2 tablas o 1 (`ProcessEvent`, decisión de implementación abierta en §11.1.13).
2. **La tabla `transfers` NO tiene spec.** §7.5/§12.1.6 la asumen ("extensión del transfer existente") pero hoy los traslados son un par de `InventoryMovement` sin documento persistente, y §11 no la especifica. Es una tabla nueva NO contada en las 12.
3. **Los feature flags NO existen en el doc canónico.** `kg_ledger_enabled`, `two_step_transfers_enabled`, `internal_maquila_enabled` son del plan de ejecución (§1.1, estrategia de no-regresión). El doc solo especifica 3 **parámetros de negocio** en `organizations.settings` (§11.2.8): `transfer_tolerance_pct` (0.05), `intersede_stale_days` (30), `aging_buckets` ([30,60,90]). Ambas listas conviven en el mismo JSONB — este plan define el contrato unificado (D3).
4. **Gap interno del doc: `purchases.warehouse_id`.** §12.2.3 exige `warehouse_id` en el HEADER de `PurchaseCreate` ("obligatorio para SAC, inmutable post-registro") y §13.2 lo ubica en el formulario, pero §11.2 (capítulo de ALTERs) lo omite. En código existe solo a nivel de línea (`purchase_lines.warehouse_id`). Resolución: la columna header se agrega en E1 (Migración B — aditiva, simétrica con `sales.warehouse_id` que ya existe); la lógica que la puebla es de E2.
5. **`expense_categories.is_system_entity` no existe** — los 8 seeds de §11.1.8 lo requieren. ADD COLUMN aditivo no declarado por el doc (D10).
6. **`fixed_assets.warehouse_id` no existe** — se confirma el fallback previsto en §11.2.3 ("si el code review detecta que no existe, se agrega nullable").
7. **Permisos Driver/Vehicle sin cerrar** en el doc ("materials.edit reutilizado o config genérico", §11.1.14) — se resuelve con la opción "config genérico" (D5).
8. **Sub-especificaciones** que este plan resuelve declarándolas: shape de `DiscrepancyTask` (§10.3 en prosa), `batch_id` hacia tabla inexistente (`furnace_batches`, Fase 2), discrepancias de tipos §4.2 vs §11 (D6), casing de `willard_account_subtype`, contradicciones del doc sobre el SEC y `terminal_weight_kg` (D6).

**Gaps que NO son de E1 y se registran para el plan que corresponda:**
- **Retenciones ICA/ReteFte/ReteIVA**: §7.2 promete "estructura preparada desde Fase 1" pero no hay tabla/columnas/hoja especificadas en NINGUNA parte del doc. Requiere mini-diseño → plan E2 (compras) con QA. ⚠️ Riesgo de promesa al cliente sin spec.
- `KgLedgerAccount.tolerance_kg` sin vía de carga (no está en hoja `CuentasPlomo` ni en los schemas de §12.1.1) → plan E2.
- Hogar del valor sugerido Green Loop $100/kg → plan E2.
- Administración de `willard_distribution_center` ("extensible sin migración") → plan E2 (InboundOrder).
- `ExpenseAuxiliary` [PENDING-DESIGN] (§11.1.7, 2 alternativas abiertas) → cerrar antes del módulo de gastos.
- **Handoff a E3 — seeds de categorías de gasto**: los pares de maquila (E3, semana 3) consumen las categorías "Maquila Intersede"/"Crisol Refinación" (`is_system_entity=TRUE`), pero el seed de las 8 llega con `/migrate-client` en S4 (semana 4). **El plan E3 debe resolver cómo existen esas 2 categorías antes del template** (seed propio idempotente o adelanto). Registrado aquí para que no se pierda entre planes.
- **Handoff a E3 — contrato del consumidor de `get_org_setting` (watch-point QA, cierre 2026-07-16)**: `transfer_tolerance_pct` viaja como **float** (H1). Cuando el consumidor de E3 lo compare contra cantidades kg (Decimal en todo el repo), debe convertir EN EL PUNTO DE LECTURA — `Decimal(str(valor))` — porque la aritmética `Decimal ± float` lanza `TypeError` (crash real) y `Decimal('0.05') == 0.05` es `False` (representación binaria). Para tolerancia 5% con `<=` el epsilon es irrelevante; el TypeError no.
- **Coordinación previa cerrada**: el lote Costa pendiente de develop (§1.3 del plan de ejecución) fue deployado completo el 2026-07-15 (PRs #6-#9, tags deploy-2026-07-14-1650 y deploy-2026-07-15-*); develop quedó 6 commits detrás de main → primer paso de implementación es fast-forward.

---

## 1. Alcance de E1

### 1.1 Entra

| # | Bloque | Fuente |
|---|---|---|
| 1 | **Migración A**: 13 CREATE TABLE (todas las tablas especificadas de §11.1 + §10.3) | §11.1, §10.3 |
| 2 | **Migración B**: 7 ALTERs aditivos sobre tablas existentes + índices, **con espejo en los modelos SQLAlchemy** | §11.2, §12.2.3 |
| 3 | **Migración C**: 6 permisos nuevos (4 SAC + 2 config flota) | §14.1, D4/D5 |
| 4 | **Infra `organization.settings`**: columna JSONB + schema tipado + helper de lectura + exposición + escritura vía system PATCH (superuser) | §11.2.8, plan-ejecucion §1.1, D3 |
| 5 | **ServiceTariff**: modelo + servicio append-only + 3 endpoints + pantalla `/config/tariffs` | §6.3, §11.1.4, §12.1.3, §13.1 |
| 6 | **MaterialConversionFormula**: modelo + servicio append-only + validación Pydantic por formula_type (Anexo D) + 3 endpoints + pantalla `/config/formulas` | §6.4, §11.1.3, §12.1.2, Anexo C/D, §13.1 |
| 7 | **Driver/Vehicle**: modelos + CRUD + pantalla `/config/fleet` | §11.1.14 |
| 8 | **Frontend flags**: hook `useOrgSettings()` + gating de tabs Y rutas SAC por flag | D3, plan-ejecucion §1.1 |
| 9 | **Guion de pruebas E1** para Johana (viernes) | plan-ejecucion §3 |

### 1.2 NO entra (y por qué)

- **Tabla `transfers`** → plan E3. Sin spec en v0.5 (hallazgo 2); diseñarla ahora, sin el análisis del flujo 2-pasos, arriesga una forma equivocada. Crear tablas después es costo cero bajo la regla aditiva. *Desviación declarada del texto de plan-ejecucion E1 ("modelo de datos completo") — se entrega "todas las tablas especificadas". **H2 QA: conflicto doc-vs-doc escalado — pendiente ratificación de Daniel.***
- **`ExpenseAuxiliary`** → [PENDING-DESIGN] explícito del doc.
- **`memberships.default_warehouse_id`** → §11.2.6b la degradó a "conveniencia de UI" sin lógica; viaja con la entrega de caja menor (E5).
- **Endpoints/CRUD de `KgLedgerAccount`** y las 6 filas de cuentas → E2 (§12.1.1 es del módulo KgLedger; E1 solo crea las tablas vacías).
- **Seeds de negocio** (5 tarifas, fórmulas, cuentas kg, 8 categorías de gasto): E1 NO siembra datos. Johana carga tarifas/fórmulas por UI (ese ES el test de E1); la carga definitiva llega por template en S4 tras `--reset-org`. Las 8 ExpenseCategory: ver handoff a E3 en §0.
- **`GET /reports/factors-tariffs-history`** → E5 con los demás reportes.
- **Tipos `internal_maquila_*`** → E3 (valores String en catálogos de código, sin migración).
- **Desviación cosmética declarada**: el doc dice rutas `/config/drivers` y `/config/vehicles` (§11.1.14); se entrega UNA página `/config/fleet` con 2 sub-secciones — mismo contenido, un tab menos en un ConfigLayout ya saturado.

---

## 2. Decisiones de diseño (para confirmación/refutación QA)

- **D1 — Conteo de tablas**: E1 crea las **13 tablas especificadas**: `kg_ledger_accounts`, `kg_ledger_movements`, `material_conversion_formulas`, `service_tariffs`, `kg_ledger_reconciliation_seals`, `discrepancy_tasks`, `daily_ok_seals`, `inbound_orders`, `inbound_order_lines`, `furnace_charges`, `crucible_charges`, `drivers`, `vehicles`. `transfers` y `expense_auxiliary` diferidas (§1.2).
- **D2 — FurnaceCharge/CrucibleCharge = 2 tablas** (como las especifica §11.1.13 "para claridad"). Sus efectos difieren (el crisol emite par de maquila); 2 tablas evitan un discriminador que todos los queries tendrían que filtrar.
- **D3 — Contrato `organization.settings`**: columna `settings JSONB NULL` en `organizations` (sin server_default; NULL = flags apagados y parámetros en default — los 3 clientes existentes quedan NULL y el código lee con fallback). Claves v1: `kg_ledger_enabled` (bool, false), `two_step_transfers_enabled` (bool, false), `internal_maquila_enabled` (bool, false), `transfer_tolerance_pct` (**float** 0-1, 0.05), `intersede_stale_days` (int, 30), `aging_buckets` (int[], [30,60,90]). **Validación TIPADA con tipos JSON-NATIVOS exclusivamente** (bool/int/float/list[int]): sub-modelo Pydantic `OrgSettingsPayload` (campos opcionales, `extra="forbid"`) — ni claves desconocidas ni tipos basura (`"kg_ledger_enabled": "yes"` → 422). **Resolución H1 (QA)**: el write path es `model_dump()` python-mode + `json.dumps` default del engine (sin `json_serializer`) → un `Decimal` en el payload revienta con 500. Se resuelve a nivel de TIPO: la tolerancia no es dinero — `float` es correcto para un porcentaje de configuración y serializa nativo. No se toca el endpoint genérico ni el engine (menos superficie que las opciones (a)/(b) planteadas por QA, mismo efecto). Test round-trip obligatorio en §8. Helper backend `get_org_setting(db, organization_id, key)` — firma con db + PK lookup `db.get(Organization, id)` (identity map de la Session: llamadas repetidas en el mismo request no re-consultan; verificado que `get_required_org_context` retorna dict con UUID, NO el objeto org — no se toca `deps.py`). **Escritura solo superuser** en E1 (campo `settings` en `SystemOrgUpdate`; el PATCH `/system/organizations/{id}` ya hace setattr genérico). **Semántica REPLACE del JSONB completo, documentada**: el operador manda siempre el dict completo (un PATCH con subset borra el resto — se documenta en el schema y en el runbook post-deploy). Lectura org: `settings` en `OrganizationResponse` (usa `model_validate` — propaga solo) y `SystemOrgResponse` (3 builders campo-a-campo). ⚠️ JSONB sin MutableDict en el repo: toda escritura reasigna el dict completo.
- **D4 — Permisos por entrega, sin wiring a roles de sistema**: E1 siembra SOLO los que sus endpoints exigen (`tariffs.view/manage`, `formulas.view/manage` per §14.1 + los 2 de D5). Los 11 restantes de §14.1 se siembran con su entrega (kg_ledger→E2, maquila/willard→E3/E4, exceptions/dashboard→E5). **No se asignan a roles de sistema**: en E1 Johana es admin (bypass) y los roles SAC finos llegan en E5 — los usuarios de Costa/Biogreen/MetaRecycling no ganan capacidad alguna. Efecto cosmético aceptado y declarado: los módulos `tariffs`/`formulas` aparecen en el RoleEditPage de todas las orgs (catálogo global — precedente #69). **Dual-write triple**: migración (patrón 038bdae40eb3, idempotente) + `PERMISSIONS_CATALOG` + **`MODULE_DISPLAY_NAMES`** en `services/role.py` (entradas "tariffs": "Tarifas", "formulas": "Fórmulas de Conversión" — sin ellas el RoleEditPage muestra el key crudo).
- **D5 — Flota bajo "config genérico"**: 2 permisos nuevos `config.view_fleet` / `config.manage_fleet` (módulo `config`, sort 129-130) — la opción "config genérico" que §11.1.14 deja abierta. Aritmética real de permisos (el "72" de §14 y CLAUDE.md está desactualizado — el catálogo vivo tiene **78**): 78 → 84 tras E1 → **95** al cierre de Fase 1 (15 de §14.1 + 2 flota). Se anota como errata al doc con estos números.
- **D6 — Resolución de discrepancias internas del doc** (donde §4.2/§6.3/§6.5 contradicen a §11, manda §11; excepciones declaradas caso por caso): VARCHAR + `Literal` Pydantic en vez de ENUM de BD (patrón #70); `code VARCHAR(32)`, `display_name VARCHAR(120)`, `unit_price_cop DECIMAL(12,2)`, `notes VARCHAR(500)`; parámetros scrap del Anexo D (`terminal_weight_kg` en kg absolutos). `willard_account_subtype` **normalizado a minúsculas** (input case-insensitive → persiste lower). **Excepciones donde NO manda §11, declaradas**: (a) el ejemplo INSERT de §11.1.3 tipa el SEC como `scrap_with_terminal_to_lead`, pero §6.4 + Anexo C (canónico de fórmulas por declaración propia del doc) lo definen como `drosses_to_lead` 0.56/0.59 — se sigue §6.4/Anexo C; (b) `terminal_weight_kg`: el Anexo D dice "peso real medido por Erwin al recibir — se persiste en el snapshot" (dato de captura), pero §11.1.3 lo persiste en el maestro — se sigue §11 (valor placeholder en el maestro, `ge=0`) y **se registra la consecuencia para E2: el snapshot de la captura debe poder sobreescribir el peso medido**.
- **D7 — `batch_id` sin FK física**: `furnace_charges.batch_id`/`crucible_charges.batch_id` UUID NULL **sin** FOREIGN KEY (la tabla `furnace_batches` es de Fase 2 y no está especificada).
- **D8 — Cero seeds de negocio en E1**. La migración Alembic solo crea estructura y permisos.
- **D9 — Shape de `DiscrepancyTask`** (§10.3 en prosa, sin tipos): campos listados (`discrepancy_type VARCHAR(40)` — catálogo de valores se cierra en plan E5 —, `severity VARCHAR(16)`, `status VARCHAR(16)`, `entity_type VARCHAR(40)`/`entity_id UUID` polimórficos, `description`, `detected_at`, `resolved_at/by`, `resolution_notes`) **más** los campos que la prosa exige: `warehouse_id UUID NULL` FK SET NULL ("sede"), `amount_involved NUMERIC(15,2) NULL`, `kg_involved NUMERIC(14,4) NULL`, `suggested_assignee_role VARCHAR(40) NULL` ("responsable sugerido" — rol, no usuario; los detectores de E5 fijan los valores), `resolution_entity_type VARCHAR(40) NULL`/`resolution_entity_id UUID NULL` ("link al ajuste generado").
- **D10 — ALTERs de E1** (todos nullable, default NULL, cero backfill, **con espejo en los modelos** — ver D13): `organizations.settings JSONB`; `money_movements` +4 (`warehouse_id` FK SET NULL, `tariff_id` FK SET NULL, `source_type VARCHAR(40)` — el doc §11.2.1 dice 32; se unifica con `kg_ledger_movements.source_type` que es 40, desviación menor declarada (H5 QA) —, `source_id UUID`) + 2 índices; `money_accounts.warehouse_id` FK SET NULL; `sales.willard_remission_number VARCHAR(40)` + `sales.willard_target_account VARCHAR(16)`; **`purchases.warehouse_id` FK SET NULL** (header — exigido por §12.2.3, omitido por §11.2; hallazgo 4 de §0); `fixed_assets.warehouse_id` FK SET NULL; `expense_categories.is_system_entity BOOLEAN NULL` (código lee `bool(x)` — NULL≡false; sin server_default, regla "default NULL, cero backfill" al pie de la letra).
- **D11 — Validaciones spec-plus en servicio** (declaradas; QA puede tacharlas): (a) coherencia `tariff_code`↔`unit` (mapa canónico: `flete_willard_bog_baq`→`per_kg_battery`, resto→`per_kg_lead`; 422 — un error aquí factura mal en E4 silenciosamente); (b) `formula_type='custom'` → 422 "no habilitado en Fase 1" (Anexo D; el sanitizer AST se implementa cuando se necesite); (c) coherencia `formula_type`↔`Material.default_unit`: `battery_to_lead`→`unidad`, `drosses_to_lead`→`kg`, **`scrap_with_terminal_to_lead`→`kg`** (Anexo D opera sobre kg); (d) **`willard_account_subtype` permitido solo en `drosses_to_lead` y `scrap_with_terminal_to_lead`** — sobre `battery_to_lead` → 422 (evita vigencias fantasma por (material, subtype) que `get_current` multiplicaría; la UI lo muestra solo en drosses).
- **D12 — Gating por flag: frontend completo, backend diferido**: tabs del ConfigLayout, children del Sidebar **y guards de ruta** evalúan flag + permiso (guard `FlagGate` que envuelve el `P` existente — sin él, un admin de otra org deep-linkea `/config/tariffs` por el bypass de permisos). El backend NO gatea por flag en E1: los CRUDs nuevos son inertes sin consumidores (org-scoped, permission-gated); el gating backend se introduce donde el flag protege código compartido (E2/E3). E1 entrega el helper `get_org_setting` con tests, listo para E2.
- **D13 — Paridad modelos↔migraciones (regla general)**: TODA columna, índice, CHECK y UNIQUE de las migraciones A y B se declara TAMBIÉN en los modelos SQLAlchemy (`__table_args__` para constraints; `postgresql_nulls_not_distinct=True` para el UNIQUE especial; índices DESC con `sa.text("col DESC")` — sin precedente en el repo, se fija la sintaxis aquí). Razón: la BD de test se recrea con `create_all` desde los modelos (conftest) — sin espejo, la Migración B queda sin ejercitar por la suite, los tests de constraints no disparan y un `--autogenerate` futuro propondría DROPs. Implica tocar 6 modelos compartidos (lista completa en §7). El informe de evidencia incluye verificación de paridad (diff de schema dev-migrado vs test-create_all).
- **D14 — Unicidad de maestros flota en SERVICIO, no en BD**: sin `UniqueConstraint` en `vehicles.plate` — el patrón del repo para maestros con soft delete (materials, warehouses, money_accounts: cero UNIQUEs de código en BD). El servicio valida duplicado ACTIVO (409/422 amistoso) y permite reusar placa de un vehículo inactivo (caso real: re-digitación tras error). Test de reuso incluido.

---

## 3. Contratos — Migraciones (3, encadenadas desde head `a4317e2cd050`)

Escritas a mano (patrón `2df40742789a`): `sa.UUID()`, timestamps `server_default=sa.text('now()')`, `comment=` por columna, índices post-create, downgrade completo en orden inverso. **Regla §1.1 plan-ejecucion: solo CREATE TABLE / ADD COLUMN nullable / índices nuevos. Cero RENAME/DROP/ALTER de tipo/backfill.** Índices con orden: `sa.text("created_at DESC")` (D13).

### 3.1 Migración A — `sac_e1_create_tables` (13 CREATE TABLE)

Columnas según §11.1 (tipos resueltos por D6). Puntos no-obvios:

| Tabla | Detalles clave |
|---|---|
| `kg_ledger_accounts` | `code VARCHAR(32)`, `account_type VARCHAR(32)`, `warehouse_id`/`third_party_id` FK RESTRICT NULL, `tolerance_kg NUMERIC(12,4) NULL`, `is_active` default true. UNIQUE `(organization_id, code)`; UNIQUE `(organization_id, account_type, warehouse_id)` **NULLS NOT DISTINCT** (PG15+; dev/test/prod son PG16; SQLAlchemy 2.0.25 soporta `postgresql_nulls_not_distinct` — verificado). CHECKs §11.1.1: willard_* → third_party NOT NULL; willard_baterias → warehouse NOT NULL; intra_horno/crisol → warehouse NOT NULL AND third_party NULL; + intersede → third_party NULL (§4.2 lo exige y §11 lo omite — declarado) |
| `kg_ledger_movements` | `delta_kg NUMERIC(14,4)` + CHECK `delta_kg != 0`, `transaction_date TIMESTAMPTZ` (BusinessDate noon UTC vía schema), `source_type VARCHAR(40)`, `source_id UUID` sin FK, `inventory_movement_id` FK SET NULL, `conversion_formula_snapshot JSONB NULL`, `status VARCHAR(16)` default 'confirmed', `annulled_*`. Índices: `(account_id, transaction_date DESC)`, `(source_type, source_id)`, `(organization_id, status)` |
| `material_conversion_formulas` | `formula_type VARCHAR(40)`, `parameters JSONB NOT NULL`, `willard_account_subtype VARCHAR(16) NULL`, FK material RESTRICT. Índice `(material_id, willard_account_subtype, created_at DESC)`. El `ix_mcf_org` del doc se OMITE declarado: OrganizationMixin ya indexa `organization_id` (duplicado). Append-only: sin is_active, sin valid_from/to |
| `service_tariffs` | `tariff_code VARCHAR(48)`, `unit_price_cop NUMERIC(12,2)` + CHECK `> 0`, `unit VARCHAR(24)`, `created_by` FK. Índice `(organization_id, tariff_code, created_at DESC)`. Append-only puro |
| `kg_ledger_reconciliation_seals` | `week_ending_date DATE`, `saldos_cierre JSONB`, `hash_movements VARCHAR(64)`, `signed_by/at`. UNIQUE `(organization_id, account_id, week_ending_date)` |
| `discrepancy_tasks` | Shape D9. Índices: `(organization_id, status)`, `(entity_type, entity_id)` |
| `daily_ok_seals` | `sealed_date DATE`, UNIQUE `(organization_id, sealed_date)`, `tasks_resolved_count INTEGER` (el JSONB opcional de §11.1.11 se descarta; ampliable aditivo) |
| `inbound_orders` | `order_number INTEGER` + UNIQUE `(organization_id, order_number)` (no especificado — patrón numbering del repo, declarado), `inbound_type VARCHAR(24)`, `warehouse_id` FK NOT NULL, `third_party_id` FK NOT NULL, `date TIMESTAMPTZ`, `driver_id`/`vehicle_id` FK NULL, `willard_distribution_center VARCHAR(24) NULL`, `willard_account_subtype VARCHAR(16) NULL`, `goes_directly_to_jm BOOLEAN NOT NULL default false` (tabla nueva: permitido), `status VARCHAR(16)` default 'draft', `annulled_*`, `created_by` |
| `inbound_order_lines` | (spec laxa — shape declarado): `inbound_order_id` FK CASCADE, `material_id` FK RESTRICT, `quantity NUMERIC(15,4)`, `unit VARCHAR(10) NULL`, `scale_weight_kg NUMERIC(14,4) NULL`, `quality_notes VARCHAR(500) NULL`, `organization_id`, timestamps. Índice `(inbound_order_id)` |
| `furnace_charges` / `crucible_charges` | `event_type VARCHAR(16)`, `date TIMESTAMPTZ`, `material_id` FK RESTRICT, `quantity_kg NUMERIC(14,4)`, `output_material_id` FK NULL, `output_quantity_kg NUMERIC(14,4) NULL`, `batch_id UUID NULL` sin FK (D7), `status/annulled_*`, `created_by`. Índice `(organization_id, date)` |
| `drivers` | `name VARCHAR(150)`, `document_id VARCHAR(30) NULL`, `phone VARCHAR(30) NULL`, `is_active` default true. Sin UNIQUE (D14) |
| `vehicles` | `plate VARCHAR(15)`, `display_name VARCHAR(120) NULL`, `vehicle_type VARCHAR(16) NULL`, `is_active`. Sin UNIQUE en BD — unicidad de placa activa en servicio (D14) |

Todas: `id GUID PK`, `organization_id` FK CASCADE + index (OrganizationMixin), `TimestampMixin` (incluye `updated_at` también en ServiceTariff/MCF — contradicción menor del doc resuelta a favor del mixin; columna inerte en append-only). **Todos los CHECKs/UNIQUEs también en `__table_args__` (D13).**

### 3.2 Migración B — `sac_e1_alter_columns` (7 ALTERs, D10)

Exactamente los de D10, **con espejo simultáneo en los 6 modelos** (D13): `organization.py`, `money_movement.py`, `money_account.py`, `sale.py`, `purchase.py`, `fixed_asset.py`, `expense_category.py`. Columnas inertes (sin exposición en schemas de operaciones — solo `settings` se expone, §4.2). Los 2 índices de `money_movements` con `op.create_index` normal (tabla ~decenas de miles de filas — lock breve aceptable; sin CONCURRENTLY). FK `tariff_id → service_tariffs` depende de Migración A (orden A→B garantizado por la cadena de revisiones).

### 3.3 Migración C — `sac_e1_permissions` (6 permisos)

Patrón `038bdae40eb3`: INSERT idempotente de `tariffs.view/manage` (módulo tariffs), `formulas.view/manage` (módulo formulas), `config.view_fleet/manage_fleet` (módulo config, sort 129-130). **SIN bloque de role_assignments** (D4). Downgrade: DELETE role_permissions → DELETE permissions por code.

**Dual-write triple** (D4): migración + `PERMISSIONS_CATALOG` + `MODULE_DISPLAY_NAMES` en `services/role.py`. NO se agregan a `SYSTEM_ROLES`.

**Orden de ejecución**: dev (5434) → suite en 5433 (conftest recrea desde modelos; correr alembic ahí es no-op — no se reporta como paso) → prod solo vía `/deploy`.

---

## 4. Contratos — Backend

### 4.1 Modelos

**Nuevos** (`backend/app/models/`): `kg_ledger.py` (KgLedgerAccount, KgLedgerMovement, KgLedgerReconciliationSeal), `service_tariff.py`, `material_conversion_formula.py`, `inbound_order.py` (InboundOrder, InboundOrderLine), `plant_process.py` (FurnaceCharge, CrucibleCharge), `exception_task.py` (DiscrepancyTask, DailyOkSeal), `fleet.py` (Driver, Vehicle). Todos `(Base, TimestampMixin, OrganizationMixin)` + registro en `models/__init__.py` (obligatorio: conftest hace create_all desde ahí). **Modificados (espejo Migración B, D13)**: `organization.py` (+settings), `money_movement.py` (+4 cols +2 índices), `money_account.py`, `sale.py`, `purchase.py`, `fixed_asset.py`, `expense_category.py` (+1 col c/u).

### 4.2 Settings (D3)

- `app/schemas/organization.py`: `OrgSettingsPayload` (Pydantic, `extra="forbid"`, campos opcionales con tipos JSON-nativos — H1: `kg_ledger_enabled: bool|None`, `two_step_transfers_enabled: bool|None`, `internal_maquila_enabled: bool|None`, `transfer_tolerance_pct: float|None ge=0 le=1`, `intersede_stale_days: int|None ge=1`, `aging_buckets: list[int]|None`). Prohibido `Decimal` en este payload (viaja por JSONB del PATCH genérico sin json_serializer).
- `app/utils/org_settings.py`: `SETTING_DEFAULTS` + `get_org_setting(db, organization_id, key)` → `db.get(Organization, id)` (identity map: sin costo repetido en el mismo request) → valor del JSONB o default.
- `schemas/system.py::SystemOrgUpdate.settings: OrgSettingsPayload|None` + `SystemOrgResponse.settings` (3 builders campo-a-campo). `schemas/organization.py::OrganizationResponse.settings` (usa `model_validate` — propaga solo). El PATCH system existente persiste sin tocar el service (semántica REPLACE documentada en el docstring del schema).

### 4.3 ServiceTariff (§6.3, §11.1.4, §12.1.3)

- Servicio `services/service_tariff.py` (patrón PriceList): `create` (Literal de 5 códigos, unit, precio>0, coherencia D11a, `created_by`), `get_all` (histórico, filtro `tariff_code?`), `get_current` (DISTINCT ON `tariff_code` ORDER BY **`created_at DESC, id DESC`** — tiebreaker: `func.now()` de PG es transaction-scoped y empata en cargas batch como el template S4). Sin update/delete.
- Endpoints prefix `/service-tariffs`: `GET ""` (`tariffs.view`), `GET "/current"` (`tariffs.view`; ruta literal antes de cualquier `/{id}` futura), `POST ""` (`tariffs.manage`, 201). Response incluye `created_by_name` (JOIN users, patrón PriceList).

### 4.4 MaterialConversionFormula (§6.4, §11.1.3, §12.1.2, Anexo D)

- Schemas de `parameters` (Anexo D, `extra="forbid"`): `BatteryToLeadParams {kg_lead_per_unit: Decimal gt=0, material_reference: Literal['07','08','1','2','3','4','5'] | None = None}` (**opcional** — los ejemplos de §11.1.3 y las filas del template §15.2.1 no lo traen); `DrossesToLeadParams {lead_percentage: Decimal gt=0 le=1}` (el subtype dentro de parameters del ejemplo Anexo D NO se persiste ahí — fuente de verdad es la COLUMNA, duplicado resuelto declarado); `ScrapWithTerminalParams {scrap_factor: Decimal gt=0 le=1, terminal_weight_kg: Decimal ge=0, material_reference: str | None = None}` (**incluye el opcional del Anexo D**). Dispatch por `formula_type` en validator del Create; `custom` → 422 (D11b).
- Servicio: `create` valida material en org (404), default_unit coherente (D11c: battery→unidad, drosses→kg, scrap→kg), subtype lowercase, subtype solo en tipos permitidos (D11d), SEC-rule (mezcla NULL/no-NULL por material → 422 con mensaje claro). `get_all` (filtros `material_id?`, `formula_type?`, `willard_account_subtype?`), `get_current` (DISTINCT ON `(material_id, willard_account_subtype)` ORDER BY `created_at DESC, id DESC`). Sin update/delete.
- Endpoints prefix `/material-conversion-formulas`: `GET ""`, `GET "/current"` (`formulas.view`), `POST ""` (`formulas.manage`, 201).

### 4.5 Driver / Vehicle (§11.1.14)

- CRUD estándar sobre `CRUDBase` (soft delete `is_active`): `GET/POST /drivers`, `PATCH /drivers/{id}`, ídem `/vehicles`. Permisos: GET → `config.view_fleet`; POST/PATCH → `config.manage_fleet`. Placa: unicidad de placa ACTIVA validada en servicio (D14; 422 amistoso; placa de vehículo inactivo reutilizable).
- Routers registrados en `api/v1/__init__.py`.

---

## 5. Contratos — Frontend

### 5.1 Infra de flags

- `types/organization.ts`: `OrganizationResponse.settings?: Record<string, unknown> | null`.
- `hooks/useOrgSettings.ts` (espejo de `usePermissions`): query `["org-settings", organizationId]` → `GET /organizations/{id}` (ya existe; `organizationsService.getById` también), staleTime 5 min, modo sistema → todo false. Expone `{ getSetting(key), flagEnabled(key), isLoading }` con los mismos defaults del backend.
- **Gating**: tabs del ConfigLayout, children del Sidebar Y guards de ruta (D12: componente `FlagGate` que compone con el guard `P`) — visibles/accesibles solo si `flagEnabled("kg_ledger_enabled")` **y** permiso. Racional: un solo flag maestro de visibilidad de módulos SAC en E1-E2 (tarifas/fórmulas alimentan el motor kg/maquila/Willard); los otros 2 flags gatean flujos compartidos en E3.
- **Regla de no-regresión del filtro** (crítica): las entradas SIN `orgFlag` **jamás** dependen del estado del query org-settings — en loading/error/NULL solo se ocultan las entradas CON `orgFlag`. El sidebar de las 3 orgs existentes se renderiza idéntico a hoy, en todo estado del query.

### 5.2 Pantallas (3 tabs nuevos en ConfigLayout, gated por flag)

| Pantalla | Ruta | Contenido |
|---|---|---|
| Tarifas | `/config/tariffs` | Tabla de las 5 vigentes (código legible, precio, unidad, desde cuándo, quién) + "Nueva tarifa" (si `tariffs.manage`): dialog con Select de código (pre-selecciona unidad canónica, read-only), `MoneyInput` precio, notas. Historial por código (modal). Estado vacío: "Sin tarifas — crea la primera" (D8) |
| Fórmulas | `/config/formulas` | Tabla de vigentes por (material, subtype) con parámetros legibles ("53% plomo", "2.5 kg/unidad") + filtro material + "Nueva fórmula": dialog con EntitySelect material, Select tipo, campos dinámicos por tipo, Select subtype (visible solo en drosses; el backend además lo acepta en scrap — D11d), vista JSON colapsable. Historial por material |
| Conductores y Vehículos | `/config/fleet` | 2 sub-secciones (tabs internos): tabla+dialog estándar (patrón WarehousesPage) por maestro. Switch Activo (soft delete) |

- Registro cuádruple: `utils/constants.ts` (ROUTES), `App.tsx` (lazy + `FlagGate`+`P`), `Sidebar.tsx` (children de Configuración con `orgFlag`), `ConfigLayout.tsx` (tabs con flag). ⚠️ Sidebar y ConfigLayout son listas duplicadas — mantener AMBAS.
- `NavChild` gana campo opcional `orgFlag?: string` evaluado con `useOrgSettings` (cambio aditivo al filtro, regla §5.1).
- Servicios/hooks/types por módulo: `services/sacConfig.ts`, `types/sac-config.ts`, `hooks/useSacConfig.ts` (keys `["service-tariffs",...]`, `["conversion-formulas",...]`, `["fleet",...]`). Invalidación inline por key propia (config pura sin side-effects cross-module → NO se toca `queryInvalidation.ts`; conforme decisión #27).
- **Mobile 390px obligatorio**: overflow wrapper del DataTable; dialogs `grid-cols-1 sm:grid-cols-2`; MoneyInput para precio; verificación DevTools antes de cerrar.

---

## 6. Invariantes de negocio (qué debe ser SIEMPRE verdad tras E1)

1. **Append-only**: no existe ruta de mutación para tarifas ni fórmulas — PATCH/DELETE a la colección → 405; a `/{id}` → 404 (la ruta no existe). Vigente = MAX(created_at, id) — sin campo is_current.
2. **Una vigente por clave**: `get_current` retorna exactamente 1 fila por `tariff_code` / por `(material_id, willard_account_subtype)` — el tiebreaker por `id` la hace determinista incluso con `created_at` empatado.
3. **Parámetros válidos por construcción**: toda MCF persistida cumple el JSON schema de su formula_type (Anexo D, incluidos sus campos opcionales); imposible insertar `parameters` vacío o fuera de rango.
4. **Settings NULL ≡ comportamiento actual**: con `settings IS NULL`, `get_org_setting` devuelve defaults y `flagEnabled` false — cero cambio para las 3 orgs existentes, por construcción; y solo payloads tipados válidos pueden persistirse.
5. **Multi-tenancy**: todas las tablas nuevas filtran por `organization_id` vía CRUDBase.
6. **Las migraciones no tocan filas existentes**: solo estructura (golden comparison lo demuestra).
7. **Paridad schema test↔prod**: el schema que `create_all` genera desde los modelos ≡ el schema que las migraciones producen en dev (verificación en el informe, D13).

---

## 7. No-regresión (gate #1)

- **Qué toca tablas compartidas**: solo Migración B (columnas nullable default NULL) + 2 índices en `money_movements`. Ningún flujo existente se modifica. **Archivos compartidos tocados (lista completa)** — backend: `models/organization.py`, `models/money_movement.py`, `models/money_account.py`, `models/sale.py`, `models/purchase.py`, `models/fixed_asset.py`, `models/expense_category.py` (columnas inertes espejo, D13), `models/__init__.py` (+imports), `schemas/organization.py` (+settings), `schemas/system.py` (+settings), `services/role.py` (+6 permisos, +2 module names), `api/v1/__init__.py` (+routers); frontend: `Sidebar.tsx`, `ConfigLayout.tsx`, `constants.ts`, `App.tsx` (+entradas condicionales), `types/organization.ts` (+campo opcional). `deps.py` NO se toca.
- **Flags**: default false/NULL. Post-deploy E1 se enciende **SOLO `kg_ledger_enabled`** en la org SAC (visibilidad de tabs); `two_step_transfers_enabled` e `internal_maquila_enabled` se encienden el viernes de SU entrega (E3) — un flag que se enciende antes de que exista su consumidor deja de ser interruptor. Los 3 clientes existentes ejecutan exactamente el código de hoy; ni sus admins ven/acceden a los módulos nuevos (flag en tabs, sidebar Y rutas — D12).
- **Permisos**: sin asignación a roles de sistema — cero cambio de capacidad para usuarios existentes. Efecto cosmético declarado (D4) con labels correctos (MODULE_DISPLAY_NAMES).
- **Golden comparison (alcance)**: `replicate_prod.sh` → capturar ANTES: P&L del mes corriente, Balance General, Balance Detallado, saldos de cuentas, **Cash Flow del mes y estado de cuenta unificado de 1 tercero caliente por org** (las rutas de lectura más sensibles de `money_movements`, que recibe 4 columnas + 2 índices) para las 3 orgs reales → aplicar migraciones A/B/C + código → recapturar → **diff exactamente cero**. Smoke de listados calientes (compras/ventas/tesorería) con las columnas nuevas en NULL.
- **Verificación frontend de no-regresión** (sin infra de tests frontend — precedente #56/#62): org con settings NULL, usuario admin Y no-admin → sidebar y tabs de /config **idénticos a pre-cambio** (verificación manual documentada en el informe), en los 3 estados del query org-settings (loading/éxito/error).
- **Suite completa** en 5433 (~1132 + las nuevas): CERO fallos.
- **Riesgos específicos**: `NULLS NOT DISTINCT` requiere PG15+ (dev/test/prod = PG16 ✓; SQLAlchemy 2.0.25 lo soporta ✓); paridad D13 verificada en el informe; índices DESC con `sa.text` (sin precedente en el repo — sintaxis fijada en D13).
- **Deploy**: fast-forward `develop` ← `main` (hoy develop está 6 atrás tras el merge del PR #9), rama sobre develop, deploy solo vía `/deploy` el viernes. El lote Costa pendiente ya está en prod (§0) — el deploy E1 no arrastra migraciones ajenas.

## 8. Tests planeados (~45 nuevos, `tests/test_sac_e1_config.py` + `tests/test_org_settings.py`)

**ServiceTariff** (~11): POST 201 caso feliz (5 códigos); GET current retorna la más reciente por código tras 2 INSERTs (y con `created_at` empatado, la de mayor id); histórico ordenado; 422: código inválido, precio ≤ 0, unidad incoherente (D11a); 401 sin token; RBAC: viewer sin permiso → 403 (org_headers2), admin → 200; multi-tenant: org2 con admin propio ve lista VACÍA (⚠️ `org_headers2` es viewer → daría 403 = test de RBAC, no de aislamiento; se crea fixture de admin en org2); PATCH/DELETE a colección → 405, a `/{id}` → 404.

**MaterialConversionFormula** (~15): POST feliz por formula_type (3, con y sin `material_reference` opcional); SEC dual (2 subtypes → get_current retorna ambas; nueva versión de `escurrido` solo reemplaza esa); 422: parameters vacío, lead_percentage>1, kg_lead_per_unit≤0, material_reference fuera del Literal, clave extra en parameters (forbid), custom (D11b), default_unit incoherente por los 3 tipos (D11c), subtype sobre battery_to_lead (D11d), subtype en mayúsculas normaliza a lower (assert persistido); material de otra org → 404; 401; RBAC ±; append-only 405/404.

**Driver/Vehicle** (~10): CRUD feliz ambos; 422 campos obligatorios (name/plate vacíos); placa duplicada ACTIVA misma org → 422; placa de vehículo INACTIVO → 201 (D14); placa igual en otra org → 201; soft delete; 401; RBAC ±; multi-tenant.

**Settings** (~8): system PATCH persiste y GET org retorna; **round-trip completo de `transfer_tolerance_pct` por JSONB** (system PATCH con el payload completo incl. float → persiste sin error → `get_org_setting` retorna el valor — condición H1 del QA: atrapa la regresión de serialización que un payload solo-booleanos no vería); PATCH org normal con `settings` en el body **se ignora en silencio** (Pydantic descarta extras — assert settings INALTERADO tras el PATCH, no 422); clave desconocida → 422; **tipo inválido → 422** (`"kg_ledger_enabled": "yes"`, `aging_buckets: 30`); `get_org_setting` con NULL retorna los 6 defaults; con valor parcial retorna mezcla; no-superuser → 403 en system PATCH.

**Migraciones/modelos** (~4): CHECKs de kg_ledger_accounts vía IntegrityError (willard sin third_party; intersede con third_party); UNIQUE NULLS NOT DISTINCT (dos cuentas mismo type con warehouse NULL); delta_kg=0. (Corren contra el schema de create_all — válidos porque los constraints viven en los modelos, D13.)

**Declarado**: sin tests frontend (`useOrgSettings`, gating) por ausencia de infra (precedente #56/#62) — cobertura por lectura + `tsc` + verificación manual del §7. Side-effects cross-module: N/A — E1 no toca flujos existentes; la evidencia es suite completa + golden comparison.

## 9. Criterios de done + guion de pruebas

**Done técnico**: 3 migraciones aplicadas en dev (5434); **schema-diff dev-migrado vs test-create_all = CERO, adjunto al informe con foco en los índices DESC y el UNIQUE NULLS NOT DISTINCT — condición H3 del QA: sin este diff el informe post-código es NO-GO**; suite completa verde en 5433; `tsc` + `npm run build` limpios; golden comparison diff cero (evidencia adjunta); verificación frontend de no-regresión (§7); pantallas verificadas en 390px y 1280px; informe a QA (paso 5).

**Pre-demo (Code, jueves)**: verificar que los materiales de E0 tengan `default_unit` correcto (baterías en `unidad`, SEC/jamiche en `kg`) — sin esto, la carga de fórmulas de Johana falla con 422 en plena demo (D11c).

**Done funcional (guion para Johana, viernes 24-jul)** — con `kg_ledger_enabled` encendido en la org SAC:
1. Configuración → ver 3 tabs nuevos (Tarifas, Fórmulas, Conductores y Vehículos).
2. Cargar las 5 tarifas reales (2.097 / 1.500 / 300 / 216 / 37) — la unidad se preselecciona sola.
3. Corregir una tarifa (nueva versión) → la vigente cambia, la anterior queda en historial.
4. Cargar fórmulas reales: baterías (kg/unidad por referencia), JAMICHE 53%, SEC escurrido 56% + SEC pinza 59% (mismo material, dos fórmulas) — valores exactos los valida Johana con Erwin (CONFIG-ARRANQUE).
5. Crear 2-3 conductores y vehículos reales.
6. Verificación negativa: David (báscula) NO ve los tabs.
7. Anotar todo lo raro → triage lunes (bug/alcance/backlog).

**Post-deploy (Code, viernes)**: encender SOLO `kg_ledger_enabled: true` en la org SAC vía system PATCH (mandando el payload completo — semántica replace, D3); documentado en el informe.

## 10. Secuencia de implementación

1. Fast-forward `develop` ← `main`; rama de trabajo sobre develop.
2. **Migración A pre-escrita primero** (es el bloque más voluminoso: ~800-1000 líneas al patrón del repo + 13 modelos con constraints espejados) + modelos + registro en `models/__init__.py`; suite temprana para validar create_all y constraints.
3. Migración B + espejo en 6 modelos + Migración C + dual-write triple en role.py.
4. Settings: schema tipado + helper + exposición + tests.
5. Servicios + endpoints ServiceTariff → MCF → Fleet, con tests por bloque.
6. Frontend: useOrgSettings + FlagGate + infra flag en Sidebar/ConfigLayout → 3 pantallas.
7. Golden comparison + suite completa + build + verificación frontend → informe a QA (paso 5).
8. Pruebas manuales Daniel → GO → commit a develop → viernes `/deploy` + demo + guion + encendido de flag.

Estimación: ~2.5-3 días backend (la Migración A + espejos es el punto frágil — comparable en superficie al módulo de obligaciones aunque con mucha menos lógica), ~1.5 días frontend, ~0.5 día evidencia/informe. Cabe en la semana 1 si el GO de QA llega lunes-martes; el colchón es recortar los tests de constraints a smoke (últimos en la secuencia). El plan E2 se escribe en paralelo (ciclos solapados, §5 del plan de ejecución).
