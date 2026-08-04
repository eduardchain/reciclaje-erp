# Informe post-código — SAC E2: KgLedger vivo + Recepción unificada

**Plan**: [plan-sac-e2-kgledger-inbound.md](plan-sac-e2-kgledger-inbound.md) v1.3 (GO condicionado QA 2026-07-16, condiciones H1-H4 incorporadas).
**Fecha implementación**: 2026-07-16 (paralela a la revisión QA, autorizada por Daniel: "adelantemos lo que más podamos... lo importante es ir validando funcionalmente los módulos").
**Estado**: código completo (backend + frontend), SIN COMMIT (gating: informe → QA → pruebas Daniel → GO → commit).

---

## 1. Qué se construyó (por bloque, orden de implementación)

### Bloque 0 — Migraciones + gating
- **Migración D** `e8f1a2b3c4d5`: 3 `ALTER TYPE ... ADD VALUE IF NOT EXISTS` en `autocommit_block` (D3), `CREATE TABLE purchase_retentions`, ADD COLUMNs a `inbound_orders` (`purchase_id` FK SET NULL, `annul_cost_adjustment` NOT NULL default 0) e `inbound_order_lines` (`unit_price`, `unit_cost` snapshot D8). Aplicada a dev 5434.
- **Migración E** `f9a2b3c4d5e6`: 3 permisos `kg_ledger.*` (sorts 144-146), patrón exacto de `d7e0a3c4b5f6` (sin role_assignments, D4-E1). Catálogo 84 → 87 (dual-write triple: migración + PERMISSIONS_CATALOG + MODULE_DISPLAY_NAMES "Cuentas en Kg").
- **`require_org_flag(flag_key)`** en `api/deps.py` (aditivo) → 403 "Módulo no habilitado" incluso para admins.
- **H2 QA**: routers E1 re-gated (`/service-tariffs`, `/material-conversion-formulas`, `/drivers`, `/vehicles`) — los 36 tests E1 ganaron fixture autouse de flag; test explícito flag-off → 403 en los 4 routers.
- **`schema_parity_check.py` extendido a `pg_enum`** (labels por typname, comparación sorted-set) — era ciego y estos son los primeros valores nuevos post-gate.
- **D12**: `willard_distribution_centers` en `SETTING_DEFAULTS` (backend + espejo frontend) + `OrgSettingsPayload`.

### Bloque 1 — KgLedger (`/kg-ledger`, servicio + 7 endpoints)
- Cuentas: CRUD con coherencia tipo↔FKs re-validada en servicio (422 legible antes del IntegrityError de los CHECKs E1), unicidad amistosa (código; tipo+sede con NULLS org-wide), desactivar con saldo ≠ 0 → 422.
- Statement (D14): saldo corrido in-memory `ORDER BY (transaction_date, created_at)`, **apertura real de la ventana (fix #55 desde el día cero)** — lo confirmado pre-ventana acumula en `opening_balance_kg`; anulados jamás mueven saldo; default 90 días; `date_to` inclusivo fin-de-día (mediodía UTC BusinessDate cabe).
- Summary: saldos por cuenta + `last_movement_at` + totales por tipo (Willard baterías+drosses agrupados) + `as_of` histórico (#41: anulados no cuentan sin importar fecha).
- Movimiento manual (D1/D15): solo `manual_adjustment`, motivo obligatorio (concatenado a descripción), `delta_kg ≠ 0`, fecha no futura, BusinessDate mediodía UTC. Anulación D16: solo manuales (los de negocio → 422 con guía al documento origen), auditoría #48.

### Bloque 2 — InboundOrder Willard (`/inbound-orders`)
- **Create** (`purchases.create` + flag): tipos `postconsumo_baterias`/`drosses` con efectos atómicos por línea:
  - **Identidad D2**: entrada a `incorporate_into_pool(liq, avg, qty, avg)` → adjustment ≡ 0 y avg intacto en las 3 ramas (test guardián sobre pool negativo incluido).
  - Stock a `current_stock_liquidated` + `InventoryMovement('inbound_receipt', reference='inbound')` fechado a `order.date` (la cantidad vive en fecha de negocio).
  - **MCH `transaction_date = HOY` (H1a QA)** en receipt, re-apply de edición y annulment — checkpoint del avg al momento de escribir, nunca backdatear.
  - **Un `KgLedgerMovement` POR LÍNEA (D5)** con snapshot de fórmula propio + `inventory_movement_id`.
  - **Resolución D6**: cuenta (postconsumo → `willard_baterias` de la sede; drosses → `willard_drosses` org-wide; sin cuenta activa → 422 "cree primero la cuenta kg"); fórmula vigente por (material, subtype) con DISTINCT ON + tiebreaker id; `scrap_with_terminal_to_lead` → 422 "no soportado en recepción"; regla de subtype con líneas mixtas (obligatorio si ≥1 línea subtyped, aplica solo a esas; presente sin líneas subtyped → 422).
  - `reventa` → 422 valor muerto (Johana: SAC no hace reventa). `date` no futura. Centro Willard validado contra settings (D12).
- **Annul D8**: remoción ponderada (#66) leyendo `inbound_order_lines.unit_cost` (snapshot del avg de entrada — sin deque); `inbound_reversal` **backdateado a `order.date`** (doctrina #41: la orden anulada desaparece de TODOS los cortes — verificado con orden de hace 5 días); diferencia → `annul_cost_adjustment`; kg movements anulados (#48); warnings sin bloquear.
- **Edit D18** (`purchases.edit` — David corrige sus capturas): Willard → revert-and-reapply (kg viejos anulados + remoción al snapshot + re-entrada al avg de HOY) cuando cambian líneas/fecha/subtipo; cabecera-sin-efectos (conductor/vehículo/centro) no re-aplica. Tipos purchase → solo cabecera; líneas/fecha → 422 con guía a la compra derivada. Anuladas → 404.

### Bloque 3 — Derivación a compras (archivos compartidos, data-gated)
- **Composabilidad D7**: `PurchaseService.create()`/`cancel()` ganaron `commit: bool = True` (default = comportamiento actual byte a byte; guard `auto_liquidate` incompatible con `commit=False`). El inbound crea `Purchase(registered)` en la MISMA transacción; `ruta` = mismo camino (comisión Green Loop es sugerencia de UI al liquidar, no efecto backend).
- **D7b**: cancel directo de compra derivada → 400 "Anule desde la orden de recepción #N" (solo órdenes no anuladas); edit de la derivada permitido (flujo Erwin §7.2). Annul de la orden: derivada `registered` → `cancel(commit=False, from_inbound=True)` atómico; `liquidated` → 400 "Cancele primero la compra #N".
- **D11**: `PurchaseCreate.warehouse_id` header opcional — fuerza el warehouse de todas las líneas en `create()` Y valida/hereda en `update()` (422 si difiere). El inbound lo puebla siempre.
- **ServiceTariff**: Literal +`comision_green_loop`, unidad +`per_kg_material`, mapa canónico +1.
- **P&L**: 8ª fuente de "Ajuste Costo por Sobreventa y Reversiones" = `inbound_orders.annul_cost_adjustment` (status `annulled`, fechada `annulled_at` — solo lado annul, el confirm-side no existe por D2).
- **`_get_inventory_as_of` extensión H2**: rama nueva del predicado `mch_source_is_cancelled` (EXISTS a `inbound_orders.status='annulled'` para `inbound_receipt`) + `inbound_annulment` en `MCH_FASE5_REVERSAL_TYPES`. Verificado por test: orden anulada invisible en corte histórico vía balance-sheet.

### Bloque 4 — Retenciones D9 (último, como se planeó)
- **Schema**: `PurchaseRetentionCreate` (Literal 3 tipos; `municipality` obligatorio iff `ica`, 422 en ambos sentidos; rate/base informativas; amount > 0) + `PurchaseLiquidateRequest.retentions?` (ausente = camino actual byte a byte) + `PurchaseResponse.retentions`.
- **Liquidate**: guard de flag (422 si retentions presentes sin `kg_ledger_enabled`), `Σ < total` (422), **bloques compensatorios ADITIVOS** tras el crédito estándar: proveedor `+Σret` (queda acreditado NETO), entidad `−amount` — pasivo total conservado al peso (test lo verifica: proveedor + entidades == −total). Cero P&L, cero costo de material.
- **Entidades sistema** "[Retenciones] ReteFuente/ReteIVA" (una c/u) + "[Retenciones] ICA {Municipio}" (una por municipio): `is_system_entity=True` + **categoría sistema `Retenciones` behavior_type='liability'** auto-creada idempotente — ancla al pasivo del Balance (`liability_debt`, verificado) y habilita el pago mensual vía `payment_to_supplier` (verificado end-to-end). **Matching sin acentos ni casing (H4)**: "Bogotá" y "bogota" → la MISMA entidad, display bonito de la primera vez.
- **Pago inmediato**: paga el **NETO** (`total − Σret`), validación de fondos incluida; test de regresión del camino bruto sin retenciones.
- **Cancel**: bloque compensatorio inverso + `reverted_at` (auditoría sin delete físico); compatible con `annul_linked_payments` #63.
- **Statement (paridad #55/#61)**: eventos sintéticos `purchase_retention` en `liquidated_at` — lado proveedor `+amount` (compensa el −total del evento compra) y lado entidad `−amount`; pares de cancelación display-only. Tests de oro: saldo corrido == saldo vivo en ambos lados, antes y después de cancelar.
- **Selector**: `GET /third-parties/liabilities?include_system=true` lista las entidades para pagarlas.

### Frontend (gated por `kg_ledger_enabled`) — 13 archivos nuevos + 9 modificados
- **"Plomo (kg)"** (`/kg-ledger` + statement en sub-ruta `/kg-ledger/:id`): KPIs por tipo, tabla de cuentas dual-render mobile, dialogs crear/editar cuenta (PermissionGate `kg_ledger.manage`), statement con fila sintética "Saldo Inicial" (#55) + delta firmado + saldo corrido + DateRangePicker + filtro status, ajuste manual como Dirección (Entrada/Salida) + cantidad positiva (evita tipear negativos, `kg_ledger.manage_adjustments`), anular solo `manual_adjustment` con razón.
- **"Recepción"** (`/inbound` + create/detail/edit): selector de tipo con labels, conductor/vehículo (flota E1), centro Willard desde settings (D12), subtipo, líneas con **preview client-side "Kg Est."** por fórmula vigente (caption "el definitivo lo calcula el sistema"), FormLineGrid + sticky bottom. **Edición D18 con payload mínimo-diff** (solo campos cambiados — mandar `lines` sin cambio dispararía revert-reapply innecesario); tipos purchase muestran solo conductor/vehículo + nota con link a la compra derivada.
- Sidebar: `NavItem` hoja gana `orgFlag`; "Recepción" (PackageOpen) y "Plomo (kg)" (Scale) en OPERACIONES tras Doble Partida — **entradas sin orgFlag intactas** (regla no-regresión §5.1-E1). Rutas con guard compuesto `FP`.
- `queryInvalidation.ts` +2 entradas (D17); `EntityLink` gana `InboundOrderLink`; MovementHistoryPage con labels "Recepción Willard"/"Reversa recepción" + link a la orden.
- **PurchaseCreatePage (D11)**: selector "Bodega *" de cabecera visible SOLO con flag (obligatorio); bodega por línea se oculta; **flag apagado = payload y UI byte-idénticos a hoy**.
- Mobile 390px verificado por construcción (dual render, overflow wrappers, FormLineGrid, sticky bottom, scroll restoration #57).

---

## 2. Desviaciones del plan (declaradas)

1. **`purchase_retentions.third_party_id` (columna adicional, NOT NULL FK RESTRICT)**: el shape D9 del plan no la traía, pero los eventos sintéticos del statement (lado entidad) y el revert exacto del cancel la requieren — sin ella habría que parsear el nombre de la entidad. Aditiva; migración D editada y re-aplicada en dev (downgrade+upgrade, tablas vacías).
2. **Micro-gap de edición D18 con pool negativo** (documentado para QA): si al EDITAR una orden Willard el pool está en hueco y la remoción no puede extraer el valor completo, la diferencia se acumula en `annul_cost_adjustment` de la orden (confirmada) y **solo entra al P&L si la orden se anula después** — la fuente P&L filtra `status='annulled'` (D8). El usuario ve un warning explícito con el monto. La conservación del POOL sí cierra siempre (el stress walk suma `annul_cost_adjustment` de TODAS las órdenes, incluidas confirmadas-editadas, y pasa). Trigger real: editar mientras el material está sobrevendido — raro en el flujo SAC.
3. **Corrección de entendimiento SEC** (atrapada por los tests contra la regla E1): el subtipo `escurrido|pinza` solo existe en fórmulas `drosses_to_lead`/`scrap_*` — SEC es material drosses (kg), NO batería. La regla de subtype con líneas mixtas (D6) opera igual; solo cambió el fixture de test.
4. **Golden ampliado**: se corrió al autorizar Daniel ("correlo ya", 2026-07-16) — resultado DIFF CERO en §4. (Nota: una versión previa de este informe lo marcó "diferido"; quedó reconciliado — corrió con backup 19:24, diff cero.)

## 3. Invariantes verificados (guardrails nuevos)

- **Identidad D2 (test guardián)**: inbound sobre pool NEGATIVO → adjustment 0, avg intacto, línea P&L oversell sin cambio.
- **Conservación D8**: annul con extracción intermedia (avg 100→28) → `annul_cost_adjustment == $3.600 exacto` == delta de la línea P&L.
- **Doctrina #41 / H2**: orden anulada invisible en corte histórico (balance-sheet as_of vuelve al valor pre-orden).
- **Oro statement==summary (D14)**: saldo corrido del statement == summary por cuenta, con ruido (movimiento anulado + pre-ventana).
- **Paridad statement==vivo con retenciones (clase #55)**: proveedor y entidad, antes y después de cancelar.
- **Stress walk extendido**: 60 ops con 3 acciones nuevas (inbound create/annul/edit revert-reapply), I5 +2 términos (valor inbound confirmado + `annul_cost_adjustment` de TODAS las órdenes), **I6 nuevo: libro kg == 0.53 × Σ(qty líneas drosses confirmadas)** — el libro paralelo cierra contra el documento fuente.

## 4. Evidencia

- **Tests nuevos**: 77 (kg_ledger 30 + inbound_orders 31 + purchase_retentions 16) + walk extendido + fixture flag en 36 E1.
- **Regresión dirigida**: test_api_purchases (67) + test_api_money_movements + test_balance_historico_fixes + test_avg_cost_model_l → **176 passed**; roles/E1/settings → 61 passed.
- **Suite completa**: `pytest 2>&1 | tee suite-e2.log` → **1256 passed in 1545.25s (0:25:45)** — exactamente 1179 (baseline E1) + 77 nuevos, cero regresión.
- **Parity check (pg_enum incluido)**: **DIFF CERO fuera del baseline** — 54 tablas / 241 índices / **256 constraints** (el +1 vs E1 es el FK `purchase_retentions.third_party_id`). Corrido DESPUÉS de la suite (secuencial, regla QA E1). La comparación `pg_enum` nueva produjo cero líneas: los valores `inbound_receipt`/`inbound_reversal`/`inbound` coinciden entre dev-migrado y test-create_all (modelo espeja migración). Baseline: 48 líneas `SOLO en` = 24 pares de FKs con nombre de migración vs auto-nombradas (pre-existente, documentado en el script).
- **Golden ampliado**: **DIFF CERO en todos los reportes financieros de las 3 orgs reales** (Costa, Biogreen, MetaRecycling). Mecanismo (mismo de E1): `replicate_prod.sh` (réplica fresca de prod, backup 2026-07-16 19:24) → captura BEFORE con worktree de `main` en :8001 (código pre-E1, lee el schema de prod nativo) → `alembic upgrade head` (E1 A/B/C + E2 D/E sobre la réplica, cadena `a4317e2cd050`→`f9a2b3c4d5e6` limpia) → captura AFTER con código E2 en :8002. Secciones comparadas por org: P&L mes corriente + **P&L mes histórico jun-2026** (Costa `oversell_cost_adjustment=0.0` → la 8ª fuente E2 no aporta a datos existentes) + **P&L mensual 3 columnas**, Balance General + **BG as_of jun-30**, Balance Detallado + **BD as_of jun-30** (12 secciones activo — estresa la extensión H2 de `_get_inventory_as_of`), Cash Flow, saldos de cuentas, estado de cuenta del tercero más caliente. **Única diferencia: `retentions: []` nuevo en la respuesta de compras** (campo `PurchaseResponse.retentions`, vacío en las 3 orgs — aditivo puro, cero cambio de comportamiento). Snapshots `e2_before.json`/`e2_after.json` (1404/1405 KB) + `diff_golden.py` en el scratchpad. El delta capturado es EXACTAMENTE el del deploy: código+schema de prod → código+schema E1+E2, mismos datos. Post-golden: flag `kg_ledger_enabled` re-encendido en la org SAC de dev (payload completo) para reanudar pruebas.
- **tsc + build frontend**: `npx tsc --noEmit` limpio; `npm run build` exitoso (chunks nuevos: KgLedgerPage, KgAccountStatementPage, Inbound*Page). `npm run lint` falla repo-wide por ausencia de config ESLint — pre-existente, no relacionado.

## 5. Runbook pre-demo (jueves 2026-07-30) — org SAC dev

1. Crear las 6 cuentas kg (Willard Baterías por sede + Willard Drosses + Intersede CV-JM + Horno JM + Crisol JM).
2. Fórmulas vigentes de los materiales postconsumo/drosses (Anexo C/D).
3. Tarifa `comision_green_loop` $100 `per_kg_material`.
4. **H3 QA: tercero "Green Loop" con behavior_type `service_provider`** (sin él, la comisión sugerida en la compra de ruta rebota con 400 en el selector de comisionistas, #32).
5. Guion §9 del plan (pasos 1-10 con actores).
