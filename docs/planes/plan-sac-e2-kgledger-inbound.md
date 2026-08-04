# Plan SAC E2 — "Cuentas en kilogramos" (KgLedger vivo + Recepción unificada InboundOrder)

**Versión:** 1.3 — 2026-07-16. **Estado:** **GO condicionado del QA (2026-07-16, cero bloqueantes, 20/20 claims verificadas TRUE)** — las 3 condiciones incorporadas en esta versión: **H1** (MAYOR, fecha del MCH de inbound → resuelto con la opción (a) recomendada: `transaction_date = HOY`, ver D4), **H2** (re-gatear los routers E1 por flag → decisión declarada en D10 + test), **H3** (Green Loop `service_provider` al pre-demo + test). H4 (sugerencia acentos ICA) adoptada en D9. Código AUTORIZADO por Daniel en paralelo a la revisión (2026-07-16: "adelantemos lo que más podamos") — los bloques se implementan en el orden §10 con retenciones al final.
**Historial:** v1.0 borrador → **ronda adversarial interna de 4 lentes** (no-regresión, fidelidad al canon, arquitectura de costos, operabilidad/tests): 2 BLOQUEANTES (reventa = flujo DP, no compra; atomicidad rota por commits internos de `purchase.create/cancel`), 9 MAYOR y ~20 precisiones — todos incorporados → v1.1 → **respuestas de Johana en vivo (2026-07-16, vía Daniel)**: reventa NO existe en SAC, ICA por municipio, 3 tipos de retención, camión mixto = una remisión, David edita sus propias capturas, Green Loop $100/kg de material — incorporadas → v1.2.
**Base canónica:** requerimientos-funcionales.md v0.5 (§3.2-§3.4, §4.1-§4.4, §6.4-§6.5, §7.1-§7.3, §10.2.1, §11.1.1-.2/.12, §12.1.1/.6, §12.2.3, §13.1-§13.2, §14.1, §15.2.1, §18.2) + plan-ejecucion-fase1.md (E2, §1 no-regresión, §5 ciclo) + handoffs de plan-sac-e1-configuracion.md §0.
**Entrega comprometida:** fin semana 2 (viernes 2026-07-31): deploy + demo + guion. "SAC prueba: entrada de postconsumo en CV → la cuenta Willard se mueve sola; entrada de drosses por JM; compra propia que NO toca cuenta kg."
**Prerequisito:** E1 deployado (viernes 2026-07-24) con `kg_ledger_enabled=true` en la org SAC. Migraciones E2 encadenan desde `d7e0a3c4b5f6`.

---

## 0. Validación de requerimientos (regla obligatoria CLAUDE.md)

Validado E2 contra v0.5 completo, el código actual (incluido E1 en develop `b248c2d`) y ronda adversarial de 4 lentes con verificación en código. Hallazgos que este plan resuelve con decisiones D1-D17:

1. **El costo de entrada del material Willard NO está en §7.3/§11.1.12** — pero SÍ en §6.4 (línea 1132): *"Inventario SAC entra igual en ambos casos (1.000 kg del material SEC **con su costo promedio**)"*. Se resuelve: entra a `current_average_cost` vigente (D2). Verificado contra `inventory_costing.py`: entrar al promedio es **identidad en las TRES ramas del helper** (incluido pool negativo: `adjustment = filled × (avg − avg) = 0`) — el promedio no se mueve y no se genera ajuste al confirmar, por construcción. El único ajuste posible del feature vive en la ANULACIÓN (D8).
2. **`InventoryMovement.movement_type` es ENUM de PostgreSQL** (8 valores), no VARCHAR. Tipo nuevo = `ALTER TYPE ADD VALUE` (aditivo permitido §1.1) **dentro de `autocommit_block`** — `env.py` corre todas las migraciones pendientes en UNA transacción y una migración futura del mismo chain que inserte filas con el valor nuevo reventaría con 55P04 (D3). El gate de paridad H3 es ciego a `pg_enum` → E2 lo extiende (D3).
3. **`reventa` NO es una compra** — errata BLOQUEANTE de la v1.0 cazada por la ronda: el canon (§2.3 L381, §3.3 L483, §11.4 L2239) la define como flujo **Pasa Mano/DP (UN3)** sin inventario (decisión #1). **RESUELTO por Johana (2026-07-16, en vivo): SAC NO hace reventa — "todo pasa por el inventario, solo compras y ventas"** → `inbound_type='reventa'` queda como valor muerto del catálogo (sin UI, 422 en backend), el módulo DP existente se les deja habilitado "por si acaso" (ya existe, permission-gated — cero trabajo), y se registra **errata al canon v0.5**: el flujo 3 (Reventa DP/UN3) no aplica a la operación real de SAC. Si algún día lo activan, es el módulo DP de siempre — no pasa por Recepción.
4. **La pantalla de Recepción no tiene ruta en §13.1** — errata del canon (§11.1.12 la llama "documento central de Fase 1"). Se resuelve: módulo sidebar "Recepción" `/inbound` (D11-frontend). El sidebar actual NO tiene grupo "operaciones" con children — Compras/Ventas/DP son NavItems hoja bajo el section header OPERACIONES → Recepción entra como **NavItem hoja top-level** en ese section, con `orgFlag` (§5).
5. **"bloquea si hay eventos posteriores" (§12.1.6 annul) contradice la filosofía vigente del repo** (#17, #65-PR3, #66 — el doc se escribió pre-Modelo L). Se resuelve a favor del repo: anulación con remoción ponderada + warnings (D8); excepciones duras: Purchase derivada liquidada (400) y cancel directo de la derivada (400 con guía, D7b).
6. **Retenciones (handoff H6)**: §7.2 promete "estructura preparada desde Fase 1"; §18.2 deja las tasas como CONFIG-ARRANQUE. Mini-diseño D9 **endurecido por la ronda**: el tercero sistema necesita categoría `liability` (sin ella `_classify_third_party` lo omite del pasivo del Balance con saldo negativo y `payment_to_supplier` da 400 — verificado en código); el estado de cuenta necesita eventos sintéticos (patrón #70) o el saldo corrido diverge del vivo (la clase de bug de #55); el pago inmediato debe pagar el NETO; y el payload con retenciones exige flag encendido.
7. **`plan-ejecucion` E2 dice "Compras... conectadas a cuenta kg" — impreciso.** El canon §3.4 es explícito: compra propia → KgLedger "—" (NUNCA, ni al liquidar). Lo que E2 conecta es la recepción (InboundOrder). El guion usa la frase correcta.
8. **Handoffs de E1 §0 absorbidos**: `tolerance_kg` (D14: editable en CRUD de cuentas; columna de hoja `CuentasPlomo` → plan S4); Green Loop $100/kg (D7: tarifa `comision_green_loop`); `willard_distribution_center` (D12: lista en org settings — exige agregar la clave a `SETTING_DEFAULTS`, sin ella `get_org_setting` lanza KeyError); `terminal_weight_kg` snapshot (no aplica a E2 — traslados/transformaciones, E3).
9. **Sub-especificaciones resueltas declarándolas**: 1 movimiento kg POR LÍNEA (D5); subtype de header con líneas mixtas (D6 — regla precisada por la ronda); bucket liquidated (D4; BG vivo = `current_stock_liquidated × avg`, reports.py:1292); fórmula `scrap_with_terminal_to_lead` NO soportada en recepción E2 (422 — es fórmula de transformación, E3); `goes_directly_to_jm` **informativo-only en E2** (la sede física la da `warehouse_id`; la validación "drosses siempre JM" no es estructuralmente expresable en un ERP multi-tenant sin semántica de bodega — regla operativa en el guion); `transaction_date`/`date` **no futuras** (canon §11.1.2 L1917 + filosofía #62); orden nace `confirmed` desde la UI E2 (draft reservado a Fase 2 móvil).

**Gaps que NO son de E2, registrados para el plan que corresponde:**
- **E3**: tabla `transfers` (H2 ratificada), source_types `intersede_send/return`, `willard_subbalance_move`, `furnace_*`, `crucible_*` (7 de los **9** restantes de §4.3), par `internal_maquila_*`, seeds categorías Maquila Intersede/Crisol Refinación, contrato `Decimal(str())`.
- **E4**: `willard_delivery` + `intersede_discharge` (los otros 2 de §4.3, en `Sale.liquidate` §7.6/§12.2.5), remisión, facturación por entrega + flete mensual, cuadre + `KgLedgerReconciliationSeal` + `willard.reconcile`/`kg_ledger.edit_after_seal`; **`warehouse_id` header de Ventas y DP** (§12.2.3 L2517-2521 — E2 entrega solo el de compras; cobertura parcial declarada).
- **E5**: `GET /reports/kg-balance` (§10.2.1 — redundante con `summary?as_of_date=`, D14), panel de excepciones (las diferencias Green Loop §7.3 y saldos intersede viejos §7.6 aterrizan ahí), dashboard SAC, roles finos.
- **S4 (migración)**: hojas `CuentasPlomo` (+columna `tolerancia_kg`) / `TarifasServicio` / `FormulasConversion` + `migrate_org.py` con `--kg-tolerance` y `source_type='migration_initial_load'` (§15.2.1, §4.6).

---

## 1. Alcance de E2

### 1.1 Entra

| # | Bloque | Fuente |
|---|---|---|
| 1 | **KgLedger vivo**: CRUD cuentas + estado de cuenta saldo corrido + summary (con as_of) + movimiento manual + anulación | §12.1.1, §4.2-§4.3 |
| 2 | **InboundOrder**: captura única (4 tipos vivos: `purchase`, `postconsumo_baterias`, `drosses`, `ruta`; `reventa` = valor muerto, Johana 2026-07-16), efectos por tipo, **edición por el capturador** (D18) y anulación | §11.1.12, §12.1.6, §7.3 |
| 3 | **Conexión a compras**: `Purchase(registered)` derivada (composabilidad `commit=False`), `purchases.warehouse_id` header poblado + inmutable (header Y líneas), guard de cancel directo | §7.2, §12.2.3 |
| 4 | **Retenciones — estructura Fase 1** (H6): tabla + captura al liquidar + tercero sistema con categoría liability + eventos de statement + pago inmediato neto + reversa en cancel | §7.2, §18.2 |
| 5 | **Migración D (enum + tabla + ALTERs)** + **Migración E (3 permisos)** | §14.1, D3/D13 |
| 6 | **Backend flag gating** (`require_org_flag`) en routers nuevos + guard de retenciones | plan-ejecucion §1.1, D10 |
| 7 | **Tarifa `comision_green_loop`** (código + unidad `per_kg_material`) + sugerencia en flujo ruta | §7.3, handoff E1 |
| 8 | **Frontend**: módulo "Plomo (kg)" + módulo "Recepción" + extensiones (warehouse header compra, retenciones en liquidación, labels de movimientos) — gated por flag | §13.1-§13.2 |
| 9 | **Guion de pruebas E2** (viernes 31) | plan-ejecucion §3 |

### 1.2 NO entra (y por qué)

- **Traslados 2 pasos / intersede / planta** → E3. **`willard_delivery`/`intersede_discharge`/sellos/cuadre** → E4. **`warehouse_id` header de Ventas/DP** → E4 (§0). **kg-balance report / panel / dashboard** → E5.
- **`reventa`** → descartada (Johana 2026-07-16, §0.3): SAC no hace reventa; valor muerto en el catálogo, 422 en backend, módulo DP disponible por si acaso.
- **Auto-cálculo de retenciones por categoría de proveedor** → post CONFIG-ARRANQUE (captura manual por monto en Fase 1).
- **Seeds de cuentas kg**: E2 NO siembra (D8-E1); Johana crea por UI (test del viernes); carga con saldos → template S4.
- **`memberships.default_warehouse_id`, caja menor, warehouse en MoneyMovement UI** → E5.

---

## 2. Decisiones de diseño (para confirmación/refutación QA)

- **D1 — Catálogo `source_type` por entrega**: modelo VARCHAR(40) (E1); el Literal de creación manual de E2 solo permite `manual_adjustment`; `postconsumo_receipt`/`drosses_receipt` los emite SOLO el servicio de inbound; `migration_initial_load` reservado a S4. Los **9** restantes de §4.3: 7 en E3, 2 en E4 (§0). Un source_type no habilitado no puede nacer en E2 por construcción.
- **D2 — Costo de entrada = promedio vigente, identidad TOTAL** (ancla §6.4 L1132; corregido por la ronda): cada línea Willard entra con `unit_cost = material.current_average_cost` vía `incorporate_into_pool(liquidated, avg, qty, avg)` → **adjustment ≡ 0 y avg intacto en las TRES ramas del helper, incluido pool negativo** (`filled × (avg − avg) = 0`; conservación trivial `−H×A + q×A = (q−H)×A`). NO existe columna de ajuste al confirmar ni sub-select confirm-side en P&L (spec muerta de v1.0, eliminada). Material nunca comprado (avg=0) entra a 0 — su margen es la maquila; vende a COGS 0 (`_get_last_known_cost` lee MCH → 0, coherente). Test guardián: inbound sobre pool negativo → adjustment 0, avg intacto (fija la identidad contra "fixes" futuros). Consecuencia Balance declarada: inventario Willard = activo sin contrapartida en pesos (la deuda es en kg, §4.4) — se documenta en el guion.
- **D3 — ENUMs de PG + gate de paridad extendido**: `ALTER TYPE inventory_movement_type ADD VALUE 'inbound_receipt'`/`'inbound_reversal'` + `inventory_reference_type ADD VALUE 'inbound'`, **dentro de `op.get_context().autocommit_block()`** (blindaje contra 55P04 en upgrades multi-migración del mismo chain — `env.py` usa UNA transacción por run) + espejo en el `Enum(...)` del modelo (D13-E1). **`schema_parity_check.py` gana comparación de labels `pg_enum`** — era ciego ahí y estos son los primeros valores nuevos post-gate. Downgrade: no-op documentado (PG no soporta DROP VALUE; valores inertes si se revierte código).
- **D4 — Bucket liquidated + MCH + fechas**: stock a `current_stock` + `current_stock_liquidated` (BG vivo reports.py:1292) + bodega del header. MCH SIEMPRE (patrón increase #65-PR4) con source_types nuevos `inbound_receipt` / `inbound_annulment` (catálogo 8→10). **Fechas — resolución H1 del QA, opción (a)**: `MCH.transaction_date = HOY` en **receipt, re-apply de edición D18 y annulment** (los tres). Razón: la entrada al promedio es identidad (D2) → el MCH es un **checkpoint del avg al momento de ESCRIBIR**, no un cambio en la fecha de negocio; fecharlo a `order.date` con captura tardía o edición D18 insertaría un checkpoint pasado con el avg de hoy y re-presentaría todo corte histórico intermedio (doctrina #61, la clase de re-presentación del incidente Costa). El `InventoryMovement` sí conserva `order.date` para la CANTIDAD (la re-presentación de cantidad al capturar/corregir tarde es el propósito de la corrección — precedente #8).
- **D5 — Un `KgLedgerMovement` POR LÍNEA Willard**: snapshot de fórmula e `inventory_movement_id` propios por línea (referencias mixtas = fórmulas distintas); `source_id = order.id` en todos; description autogenerada.
- **D6 — Resolución de cuenta, fórmula y subtype (422s tempranos)**: `postconsumo_baterias` → cuenta `(willard_baterias, warehouse=header)`; `drosses` → `willard_drosses` org-wide. Sin cuenta activa → 422 "cree primero la cuenta kg". Sin fórmula vigente para el material (± subtype) → 422 (§3.2). Fórmula vigente `scrap_with_terminal_to_lead` → 422 "tipo de fórmula no soportado en recepción" (es de transformación, E3). **Regla de subtype con líneas mixtas (precisada por la ronda; realidad operativa CONFIRMADA por Johana 2026-07-16: el camión Willard puede venir mezclado y es UNA sola remisión)**: `willard_account_subtype` es obligatorio si **≥1 línea** es de material con fórmulas subtyped (SEC), y aplica SOLO a esas líneas — las demás (jamiche, etc.) resuelven su fórmula NULL; subtype presente sin ninguna línea subtyped → 422. `delta_kg = qty × kg_lead_per_unit` (baterías) / `kg × lead_percentage` (drosses). Material/bodega inactivos → 400 (reusa `_validate_material` patrón increase). `date` no futura (422, §0.9).
- **D7 — Tipos con Purchase derivada (`purchase`, `ruta`)**: crean `Purchase(registered)` **en la MISMA transacción** vía refactor de composabilidad: `PurchaseService.create()` y `cancel()` ganan parámetro `commit: bool = True` (aditivo, default preserva el comportamiento actual byte-a-byte — patrón `_create_movement` #20); el inbound llama con `commit=False` y commitea al final. Líneas espejo (material/cantidad/`unit_price` opcional default 0 — §7.2: el precio definitivo lo fija Johana al liquidar); el flujo de compras existente pone tránsito y numera; `inbound_orders.purchase_id` enlaza. **Metodología CONFIRMADA por Daniel (2026-07-16): registrar → liquidar → pagar, idéntica a hoy, con la liquidación inmediata (#20) disponible donde existe hoy (módulo de compras, permiso de liquidar). La Recepción NO ofrece liquidar en línea — deliberado, preserva el flujo §7.2 David captura → Erwin audita → Johana liquida; la derivada queda a un clic de la LiquidatePage.** `ruta` = purchase + comisión Green Loop **sugerida** (tarifa nueva `comision_green_loop`, unidad nueva `per_kg_material` — **CONFIRMADO Johana 2026-07-16: $100 por kg de material recolectado**; pendiente menor: si es parejo para todo material — la sugerencia es editable por compra, así que cualquier respuesta cabe sin cambio de diseño; UI pre-llena `PurchaseCommission` editable, #30 prorratea). **`reventa` → 422, valor muerto** (§0.3 — SAC no hace reventa). KgLedger: estos tipos NO tocan cuentas kg (§3.4). **(D7b) Camino inverso protegido**: `cancel` directo de una Purchase con `inbound_order` enlazada → 400 "Anule desde la orden de recepción #N" (espejo patrón #67 "anular desde el módulo" — evita orden confirmed apuntando a compra cancelada); el **edit** de la derivada se PERMITE (el flujo real §7.2 lo exige: Erwin ajusta referencias antes de liquidar) con divergencia inbound↔purchase declarada: la orden es el documento de captura, la compra es la verdad comercial.
- **D8 — Anulación (tipos Willard)**: anula los `KgLedgerMovement` (#48) + reversa de inventario con **remoción ponderada** (#66) leyendo `inbound_order_lines.unit_cost` (snapshot del avg de entrada persistido al confirmar — sin deque: la precisión `Numeric(15,4)` de la línea vs `(10,3)` del movimiento haría fallar el matching por firma, y el inbound controla sus propios movimientos) + `warnings[]` si el stock queda negativo — **aviso, no bloqueo** (desviación declarada de §12.1.6, pre-#66). El movimiento `inbound_reversal` se **backdatea a `order.date`** (doctrina #41: las órdenes anuladas desaparecen de TODOS los cortes — patrón `adjustment.date`/`purchase.date` vigente). Diferencia de remoción → `inbound_orders.annul_cost_adjustment` (header), **única fuente nueva de la línea P&L** "Ajuste Costo por Sobreventa y Reversiones" (7→8 fuentes, solo lado annul): filtro `status='annulled'`, fecha `annulled_at` (patrón G3 — tabla de fuentes en §4.3). Tipos purchase: derivada `liquidated` → 400 "Cancele primero la compra #N"; `registered` → `purchase.cancel(commit=False)` + anulación de la orden, atómico. Draft → sin efectos. **Balance histórico (`_get_inventory_as_of`) — extensión H2 declarada**: el camino principal excluye MCH `inbound_receipt` de órdenes cancelled/annulled (EXISTS a `inbound_orders.status`, nueva rama del predicado `mch_source_is_cancelled`); `inbound_annulment` entra a `MCH_FASE5_REVERSAL_TYPES` (Fallback 1); Fallback 2 no gana el tipo nuevo (material solo-inbound sin MCH → costo 0, correcto y declarado).
- **D9 — Retenciones (estructura Fase 1, H6 — endurecida por la ronda)**: **CONFIRMADO por Johana (2026-07-16, en vivo vía Daniel): la aplicación es POR PROVEEDOR — a unos se les retiene y a otros no → el diseño es opcional por liquidación, nada se auto-aplica** (la captura manual por monto ya lo garantiza; el auto-cálculo futuro por categoría de proveedor respetará esa opcionalidad). **CONFIRMADO Johana 2026-07-16: aplica las 3 (ReteFuente, ICA, ReteIVA) y el ICA se maneja POR MUNICIPIO.** Tabla `purchase_retentions` (`id`, `organization_id`, `purchase_id` FK CASCADE, `retention_type` Literal `ica|retefuente|reteiva` — filas repetidas del mismo tipo permitidas (bases distintas), **`municipality VARCHAR(60) NULL` — obligatorio (422) cuando `retention_type='ica'`, prohibido en los otros dos**, `rate NUMERIC(7,4) NULL` informativa, `base NUMERIC(15,2) NULL` informativa, `amount NUMERIC(15,2)` CHECK `> 0`, `reverted_at TIMESTAMPTZ NULL` — auditoría del cancel sin delete físico, timestamps). **Resolución de entidad**: ReteFuente y ReteIVA → una entidad cada una ("[Retenciones] ReteFuente", "[Retenciones] ReteIVA" — DIAN); ICA → una entidad POR municipio ("[Retenciones] ICA Barranquilla", "[Retenciones] ICA Bogotá", ... — auto-creadas idempotentes al primer uso; **matching sin acentos ni casing** (H4 QA: "Bogota" y "Bogotá" resuelven a la MISMA entidad; se persiste el display bonito de la primera vez) — duplicación bajo liquidaciones concurrentes declarada aceptable (precedente repo: maestros sin UNIQUE de BD, D14-E1)). La UI muestra el campo municipio solo en filas ICA, con sugerencias de los usados antes. `PurchaseLiquidate.retentions?`: ausente/vacío = **cero efecto** (los 3 clientes ejecutan el camino de hoy); presente exige `kg_ledger_enabled` (422 "módulo no habilitado" — sin el guard, una org no-SAC podría crear terceros sistema indelebles vía API cruda). Validación `Σ amounts < total_amount`. **Efectos como bloques compensatorios ADITIVOS** (las líneas existentes de liquidate/cancel NO se editan): tras el crédito estándar al proveedor (−total), el bloque suma `+Σret` al proveedor y `−Σret` al tercero sistema → pasivo total conservado; cero P&L; cero costo de material. **Tercero sistema "[Retenciones] {ReteFuente|ICA|ReteIVA}"**: `is_system_entity=True` + **categoría sistema `behavior_type='liability'`** auto-creada idempotente y oculta (patrón #33 — sin la categoría, `_classify_third_party` lo omite del pasivo del Balance y `payment_to_supplier` da 400, verificado); aparece en el Balance como `liability_debt` y su pago mensual es `payment_to_supplier` normal (el selector de pasivos gana `include_system=true` para listarlo — cambio declarado). **Estado de cuenta (paridad #55/#61)**: la liquidación con retenciones emite eventos sintéticos en el statement (patrón #70 `purch-commission-{id}`): al proveedor `+Σret` "Retención {tipos} compra #N" en `liquidated_at` (compensa el −total del evento compra) y a la entidad `−amount` por retención — sin ellos el saldo corrido diverge del vivo. **Pago inmediato**: con retenciones paga el **NETO** (`total − Σret`), validación de fondos incluida — única expresión existente condicionada (guarded `if retentions`), con test de regresión del camino bruto. **Cancel**: bloque compensatorio inverso + `reverted_at`; compatible con `annul_linked_payments` #63 (el pago enlazado fue neto → su reversa usa el monto del movimiento, correcto por construcción). Tasas: captura manual por monto en Fase 1; auto-cálculo cuando el contador entregue la tabla.
- **D10 — Backend flag gating**: dependency `require_org_flag(flag_key)` en `api/deps.py` (función ADITIVA) → 403 "Módulo no habilitado" si el flag es false. Aplica a routers `/inbound-orders` y `/kg-ledger` completos + guard de retenciones (D9) **+ los routers E1 (`/service-tariffs`, `/material-conversion-formulas`, `/drivers`, `/vehicles`) — respuesta del QA a la pregunta abierta: SÍ re-gatear** (defensa en profundidad §1.1; riesgo cero: las 3 orgs tienen flag apagado, sin datos ni camino de UI; SAC lo tiene encendido desde el 24; cierra el hueco "admin de otra org escribe tarifas por API cruda"). Test: flag off → 403 en `/service-tariffs`. Verificado: un no-superuser NO puede encenderse el flag (`OrganizationUpdate` no tiene `settings`; solo el PATCH `/system` con `get_current_superuser`).
- **D11 — `purchases.warehouse_id` header**: `PurchaseCreate` acepta opcional; si presente **fuerza** el warehouse de todas las líneas al header — **también en `update()`** (líneas nuevas del full edit heredan/validan contra el header, 422 si difieren; sin esto el revert-and-reapply #8 dejaría header W con movimientos en W'); inmutable post-registro (excluido del update). El inbound lo puebla siempre. UI: selector en Create solo visible con flag (obligatorio ahí); disabled con tooltip en Edit.
- **D12 — `willard_distribution_center` administrable**: clave `willard_distribution_centers: list[str] | None` en `OrgSettingsPayload` **y en `SETTING_DEFAULTS`** (backend + espejo frontend — sin la entrada en defaults, `get_org_setting` lanza KeyError) — default `["baq","bog","monteria","santa_marta","motocosta"]` (§6.5; pereira/medellín por system PATCH al confirmarse). Validación de pertenencia al crear inbound (422); solo en tipos Willard.
- **D13 — Permisos E2**: `kg_ledger.view` (master, 144), `kg_ledger.manage` (145), `kg_ledger.manage_adjustments` (146), módulo `kg_ledger` + MODULE_DISPLAY_NAMES "Cuentas en Kg". InboundOrder reusa `purchases.view/create/edit/cancel` (§12.1.6 fija create; el resto declarado). **CONFIRMADO Johana 2026-07-16: David corrige sus propias capturas** → la corrección se resuelve con **EDICIÓN** (D18, permiso `purchases.edit` — el rol operador/báscula SÍ lo tiene en la tabla canónica §14.2); la **anulación** completa sigue siendo de Johana (`purchases.cancel`), consistente con compras. Dual-write triple + sin wiring a roles (D4-E1). Catálogo 84 → 87.
- **D14 — Statement y summary**: saldo corrido in-memory `ORDER BY transaction_date, created_at` + fila "Saldo Inicial" = apertura real de la ventana (fix #55 desde el día cero); default 90 días. `GET /summary?as_of_date=`: saldo por cuenta + `last_movement_at`, sub-saldos `willard_baterias` agrupados con total lógico; anulados NO cuentan sin importar fecha (#41). **Test de oro de paridad**: saldo corrido del statement al corte X == `summary?as_of_date=X` (dos queries distintas del mismo número — la clase de divergencia de #55/#61). `tolerance_kg` editable en Create/Update (handoff E1; el uso alertante llega con cuadre E4/panel E5).
- **D15 — Numeración y fechas**: `order_number` secuencia por org con lock (patrón `_generate_purchase_number`). `InboundOrder.date` y `transaction_date` con BusinessDate noon UTC + **validación no-futura** (servicio, §11.1.2 L1917 + #62).
- **D16 — Anulación de kg manual**: solo `manual_adjustment` es anulable directo; los emitidos por inbound se anulan desde su orden (422 con guía, patrón #67).
- **D17 — Invalidación de cache**: `queryInvalidation.ts` gana `invalidateAfterInboundOrder` (inbound + kg-ledger + inventory + materials + purchases) e `invalidateAfterKgMovement` (kg-ledger) — cross-module real (#27). Liquidación con retenciones: el mapa existente ya invalida third-parties.
- **D18 — Edición de InboundOrder (respuesta Johana: "él mismo puede editar")**: `PATCH /inbound-orders/{id}` (permiso `purchases.edit` + flag) para órdenes `confirmed`, con **revert-and-reapply** (patrón #8): tipos Willard → anula los kg movements + remueve el inventario (mecánica D8, al `line.unit_cost` snapshot) y re-aplica con las líneas nuevas (nuevo avg de entrada, nuevos snapshots — como si se capturara hoy, con la `date` original conservada salvo que se edite); tipos purchase → **la edición vive en el módulo de compras** (la derivada `registered` ya tiene full edit #8 y David tiene `purchases.edit`) — el PATCH del inbound solo permite campos de cabecera sin efectos (conductor/vehículo/notas/centro Willard) y las líneas se editan en la compra (divergencia D7b declarada; editar líneas en ambos lados sería doble verdad). Header inmutable en todo caso: `warehouse_id`, `inbound_type`, `third_party_id` (cambiarlos = anular y recrear — mismo racional §7.2). Órdenes `annulled` → 404 de edición.

---

## 3. Contratos — Migraciones (2, encadenadas desde `d7e0a3c4b5f6`)

**Regla §1.1 intacta**: ADD VALUE / CREATE TABLE / ADD COLUMN nullable / permisos. Cero RENAME/DROP/backfill.

### 3.1 Migración D — `sac_e2_inbound_kg`

| Cambio | Detalle |
|---|---|
| `ALTER TYPE inventory_movement_type ADD VALUE IF NOT EXISTS 'inbound_receipt'` / `'inbound_reversal'`; `inventory_reference_type ADD VALUE 'inbound'` | En `autocommit_block` (D3). Espejo en el `Enum(...)` del modelo. Downgrade no-op documentado |
| `CREATE TABLE purchase_retentions` | Shape D9 (incl. `reverted_at`) + índice `(purchase_id)` + CHECK `amount > 0`; espejo modelo + `__init__.py` + relación `retentions` en `models/purchase.py` (espejo de `commissions`) |
| `ALTER TABLE inbound_orders ADD purchase_id UUID NULL` FK purchases SET NULL | Enlace D7 |
| `ALTER TABLE inbound_order_lines ADD unit_price NUMERIC(15,2) NULL, ADD unit_cost NUMERIC(15,2) NULL` | Precio de captura (D7) + **snapshot del avg de entrada** (D8 — la reversa exacta lee de acá, sin deque) |
| `ALTER TABLE inbound_orders ADD annul_cost_adjustment NUMERIC(15,2) NOT NULL DEFAULT 0` | Conservación en anulación (D8, patrón #66) |

### 3.2 Migración E — `sac_e2_permissions`

Patrón `d7e0a3c4b5f6`: INSERT idempotente de los 3 `kg_ledger.*` (144-146). SIN role_assignments. Downgrade: DELETE role_permissions → permissions.

**Orden**: dev (5434) → suite (5433, create_all) → prod solo vía `/deploy` el viernes 31.

---

## 4. Contratos — Backend

### 4.1 KgLedger (`services/kg_ledger.py`, endpoints prefix `/kg-ledger`, todos `require_org_flag`)

- `GET /accounts` (`kg_ledger.view`): filtros `account_type?`, `is_active?` default true; `current_balance_kg` con 1 query agregada (sin N+1).
- `POST /accounts` (`kg_ledger.manage`, 201): re-valida los CHECKs de E1 en servicio con 422 amistoso; unicidad legible.
- `PATCH /accounts/{id}` (`kg_ledger.manage`): `{display_name?, tolerance_kg?, is_active?}`; type/FKs inmutables; desactivar con saldo ≠ 0 → 422.
- `GET /accounts/{id}/movements` (`kg_ledger.view`): statement D14.
- `GET /summary` (`kg_ledger.view`): D14.
- `POST /movements` (`kg_ledger.manage_adjustments`, 201): manual con motivo obligatorio, `delta_kg ≠ 0`, fecha no futura.
- `POST /movements/{id}/annul` (`kg_ledger.manage_adjustments`): D16, auditoría #48.

### 4.2 InboundOrder (`services/inbound_order.py`, prefix `/inbound-orders`, `require_org_flag`)

- `POST ""` (`purchases.create`, 201): header D6/D12/D15 + `lines[] {material_id, quantity > 0, unit_price?, scale_weight_kg?, quality_notes?}` (≥1). Efectos atómicos:
  - `postconsumo_baterias`/`drosses`: por línea → `InventoryMovement('inbound_receipt', reference_type='inbound', reference_id=order.id, unit_cost=avg_vigente)` + stock (D4) + MCH + `KgLedgerMovement` (D5/D6) + snapshot `line.unit_cost=avg` (D8).
  - `purchase`/`ruta`: `Purchase(registered)` vía `create(commit=False)` (D7); sin movimientos propios del inbound.
  - `reventa`: 422 (D7).
- `GET ""` / `GET /{id}` (`purchases.view`): listado con filtros + detalle enriquecido (materiales #54, kg emitidos, link a Purchase).
- `PATCH /{id}` (`purchases.edit`): edición D18 — revert-and-reapply para tipos Willard; solo cabecera-sin-efectos para tipos purchase; header estructural inmutable.
- `POST /{id}/annul` (`purchases.cancel`): D8, body `{reason}`, response con `warnings[]`.

### 4.3 Compras (extensiones data-gated — archivos compartidos)

- `create()`/`cancel()` ganan `commit: bool = True` (D7 — aditivo; tests de regresión del default).
- `PurchaseCreate.warehouse_id?` + forzado header→líneas en create Y update (D11); inmutable.
- `PurchaseLiquidate.retentions?` (D9): bloques compensatorios tras los efectos estándar; pago inmediato neto; guard de flag.
- `cancel()`: guard D7b (400 si vino de inbound) + reversa de retenciones con `reverted_at`.
- **Tabla de fuentes de la línea P&L oversell (espejo G3, para el QA)**: fuente nueva #8 = `inbound_orders.annul_cost_adjustment`, filtro `status='annulled'`, fecha `annulled_at` — se suma en el bloque "Reversiones ponderadas Fase 5" de `reports.py` (+1 sub-select; el confirm-side NO existe, D2).
- `ServiceTariff`: Literal +`comision_green_loop`, unidad +`per_kg_material`, mapa canónico +1.
- `_get_inventory_as_of`: extensión H2 (D8) — rama nueva del predicado por `inbound_orders.status` + `inbound_annulment` en `MCH_FASE5_REVERSAL_TYPES`.

### 4.4 Settings

- `OrgSettingsPayload` + `willard_distribution_centers` (D12) + entrada en `SETTING_DEFAULTS` backend y frontend (sincronizados).

## 5. Contratos — Frontend (gated por `kg_ledger_enabled` + permiso)

| Pantalla | Ruta | Contenido |
|---|---|---|
| Plomo (kg) | `/kg-ledger` | Cards por cuenta (saldo `#,##0.####` kg, badge signo, sub-saldos Willard Baterías agrupados con total lógico) → statement (saldo corrido + fila Saldo Inicial + filtros + Excel básico + anular manual). Botones "Nueva cuenta" (`kg_ledger.manage`) y "Movimiento manual" (`kg_ledger.manage_adjustments`). El form de cuenta trae placeholder de códigos sugeridos (§4.2) — el código es libre, lo estructural es (tipo, sede) |
| Recepción | `/inbound` | Listado (DataTable + cards mobile) + Create: tipo (4 vivos), sede, tercero, conductor/vehículo, sección Willard colapsable (centro desde settings, subtype solo si ≥1 línea subtyped, `goes_directly_to_jm` informativo), líneas (`FormLineGrid`), **preview "estimado" de delta_kg** (client-side con refetch de fórmulas al abrir; el número REAL lo muestra el response al confirmar — puede diferir si la fórmula cambió entre carga y submit); tipo ruta muestra comisión Green Loop pre-llenada. Detail con efectos + link a compra + anular |
| Compras (ext.) | — | Selector sede en header (create obligatorio con flag; disabled en edit); bloque "Retenciones" en LiquidatePage (filas tipo/base/monto, neto visible del proveedor, monto del pago inmediato = neto) |
| Inventario (ext.) | — | `MovementHistoryPage`: labels "Recepción (orden)" / "Reversa recepción" para los tipos nuevos + rama de navegación `reference_type='inbound'` → `/inbound/{id}` (hoy caería al string crudo sin link) |

- Sidebar: **`NavItem` hoja gana `orgFlag`** (rama del filtro: `checkPerm(item.permission) && checkFlag(item.orgFlag)` — corto-circuito preserva la regla §5.1-E1: sin orgFlag jamás toca el query). "Plomo (kg)" y "Recepción" = NavItems hoja top-level en el section OPERACIONES.
- Registro cuádruple + hooks con keys propias + D17 en `queryInvalidation.ts`.
- Mobile 390px obligatorio: cards en listados, `FormLineGrid`, preview colapsable.

## 6. Invariantes (qué debe ser SIEMPRE verdad tras E2)

1. `current_balance_kg == SUM(delta_kg) WHERE status='confirmed'` para toda cuenta, tras TODA operación — y statement al corte X == summary as-of X (test de oro D14).
2. Un inbound Willard confirmado **no mueve un peso**: P&L, saldos de terceros, cuentas — idénticos antes/después. Sin excepciones (D2: identidad total; el único ajuste del feature es de anulación).
3. Conservación en anulación: `pool_after == pool_before − qty×unit_cost + annul_cost_adjustment` (helper #66); el ajuste aterriza en la línea P&L por `annulled_at`.
4. Compra propia (directa o derivada) JAMÁS emite `KgLedgerMovement` (§3.4) — ni al registrar ni al liquidar.
5. Retenciones conservan el pasivo: `Δproveedor + Σ Δentidades == −total` al liquidar; el statement del proveedor Y de cada entidad cuadra saldo corrido == saldo vivo (eventos sintéticos D9); cancel devuelve todo exacto; el pasivo retenido aparece en `liability_debt` del Balance.
6. Flag apagado ⇒ 403 en routers nuevos (incluso admin) y 422 si llegan `retentions[]`; sidebar/rutas no exponen nada; las 3 orgs ejecutan el código de hoy byte-a-byte cuando los campos opcionales no vienen.
7. Snapshot inmutable: fórmula y tarifa se resuelven al momento del evento; cambiarlas después NO re-calcula nada (#35).
8. Paridad schema test↔dev = cero **incluyendo labels de enum** (gate extendido D3).
9. Cortes históricos: una orden anulada desaparece de TODO corte (reversal backdateado D8 + extensión H2); el golden as-of no se re-presenta para las 3 orgs.

## 7. No-regresión (gate #1)

- **Archivos compartidos tocados (lista COMPLETA post-ronda)** — backend: `models/inventory_movement.py` (enum +3 valores espejo), `models/purchase.py` (+relación `retentions`), `services/purchase.py` (create/cancel +param `commit`; update forzado warehouse; liquidate/cancel bloques retenciones data-gated; guard D7b), `api/v1/endpoints/purchases.py` (threading de `retentions` + Query annul), `schemas/purchase.py` (+3 campos opcionales), `services/reports.py` (**2 funciones**: línea oversell +1 sub-select annul-side; `_get_inventory_as_of` extensión H2 D8), `services/money_movements` statement (eventos sintéticos de retención, patrón #70), `schemas/organization.py` + `utils/org_settings.py` (+1 clave y default), `schemas/service_tariff.py` (+1 código/+1 unidad), `api/deps.py` (+`require_org_flag`), `services/role.py` (+3 permisos +1 módulo), `api/v1/__init__.py` (+2 routers), `models/__init__.py`, `services/third_party.py` (categoría sistema liability + `include_system` en selector de pasivos); frontend: `Sidebar.tsx` (NavItem orgFlag), `App.tsx`/`constants.ts`, `queryInvalidation.ts` (+2 entradas), `PurchaseCreatePage/EditPage/LiquidatePage`, `MovementHistoryPage` (labels+link), `types/purchase.ts` + `services/purchases.ts`, `useOrgSettings` defaults.
- **Flujos existentes sin flag/datos = byte-a-byte**: los params nuevos tienen defaults que preservan; los bloques de retenciones/inbound solo corren con datos que las 3 orgs no envían; reportes existentes no ven `inbound_receipt` (listas explícitas de tipos — test, no supuesto).
- **Golden comparison (alcance ampliado por la ronda)**: réplica prod → P&L mes corriente **+ P&L de un mes histórico con oversell ≠ 0 conocido** (Costa jul-2026 — cubre los filtros de fecha de las 7 fuentes que el mes corriente no compila), BG, Balance Detallado **+ as_of_date histórico** (cubre `_get_inventory_as_of` H2), saldos, Cash Flow, estado de cuenta tercero caliente, listado movimientos inventario + stock por bodega de 2 materiales calientes × 3 orgs → migrar + código → diff exactamente cero.
- **Tests de regresión de los write-paths compartidos** (el golden es read-only — no los ve): create/cancel con default `commit=True`; liquidate sin retenciones byte-idéntico **en las variantes con `immediate_payment`, con comisiones y con `annul_linked_payments`** (los caminos físicamente adyacentes a los hooks).
- **Secuencia de evidencia** (regla QA-E1): suite completa (log `tee` completo) → DESPUÉS parity check extendido, nunca en paralelo.
- **Riesgos**: ADD VALUE irreversible (declarado); enum modelo↔migración es la paridad más frágil → gate extendido la cubre; `require_org_flag` = 1 `db.get` con identity map (~0 costo).

## 8. Tests planeados (~68, `tests/test_kg_ledger.py` + `tests/test_inbound_orders.py` + `tests/test_purchase_retentions.py`)

**KgLedger (~18)**: CRUD + 422s de coherencia (todas las reglas §11.1.1 vía API) + unicidad legible; PATCH inmutables; desactivar con saldo → 422; manual ± / delta 0 → 422 / **fecha futura → 422**; annul manual + 422 guía para los de inbound (D16); statement: saldo corrido, fila Saldo Inicial con movimiento pre-ventana (#55), orden estable; summary: agrupación sub-saldos + as_of excluye anulados; **oro: statement al corte == summary as-of** (fixture: pre-ventana + anulado + manual); **BusinessDate noon UTC en transaction_date** (payload date-only → persiste 12:00Z, #24); RBAC ± por permiso; flag off → 403 admin; aislamiento.

**InboundOrder (~30)**: postconsumo feliz (100 BAT-07 × 2.5 → +250 kg, snapshot, movimiento enlazado a `order.date`, stock liquidated, avg intacto, **MCH `transaction_date=HOY`** — H1a: checkpoint al escribir, cortes históricos intactos con captura backdateada, `line.unit_cost=avg`); drosses feliz (SEC pinza 0.59); multi-línea mixta (2 snapshots); **SEC+jamiche en una orden** (subtype aplica solo al SEC — D6); subtype faltante/sobrante → 422; sin fórmula → 422; **fórmula scrap vigente → 422**; sin cuenta → 422; wdc fuera de lista → 422; material/bodega inactivos → 400; **fecha futura → 422**; **inbound sobre pool negativo → adjustment 0 y avg intacto** (guardián D2); avg=0 entra a 0; tipo purchase → derivada registered (número, tránsito, cero financiero, cero kg, `purchase_id` enlazado, **misma transacción**: forzar fallo post-create → rollback completo sin Purchase huérfana); ruta = purchase + comisión GL prorrateada (#30); **reventa → 422**; liquidar derivada → efectos estándar y sigue sin kg; **cancel directo de derivada → 400 guía D7b**; edit de derivada permitido (divergencia declarada); annul Willard → kg annulled + remoción al `line.unit_cost` + conservación exacta + warning sin bloqueo + **reversal backdateado a order.date**; **annul tras venta del material → `annul_cost_adjustment ≠ 0` aterrizando en la línea P&L por `annulled_at`** (test estrella); annul purchase-type: registered → cancela ambas atómico / liquidated → 400; **as-of: cortes antes/entre/después de un inbound anulado** (H2 — stock y costo correctos en los 3); **edición D18**: David (fixture con rol báscula: view+create+edit) edita cantidades de su captura Willard → kg y stock re-emitidos exactos (conservación), NO puede anular (403 cancel); edición de tipo purchase → solo cabecera (líneas → 422 guía "edítelas en la compra"); header estructural inmutable (422); numeración; paridad reportes (adjustment_net y listado de ajustes NO cambian con inbound presente); RBAC ±; flag off → 403; aislamiento.

**Retenciones (~16)**: liquidar con 2 retenciones (tipos distintos y repetidos) → proveedor neto + entidades con categoría liability idempotente + conservación; **ICA exige municipio (422 sin él; prohibido en retefuente/reteiva) y resuelve entidad por municipio** ("ICA Barranquilla" ≠ "ICA Bogotá", mismo municipio con casing distinto NO duplica); sin retentions → byte-idéntico (balances + **variantes immediate_payment / comisiones / annul_linked_payments**); **retenciones + immediate_payment → paga NETO** (fondos validados contra neto); **flag off + retentions → 422**; Σ ≥ total → 422; tipo inválido → 422; cancel revierte + `reverted_at` + compatible con annul del pago enlazado (#63); **la entidad aparece en `liability_debt` del Balance Detallado**; **statement del proveedor cuadra con retención** (evento sintético — saldo corrido == vivo, golden #61-style) y statement de la entidad no queda vacío; entidad reutilizada (no duplica); P&L intacto; e2e retención sobre compra derivada de inbound + annul de la orden después (400 por liquidada).

**Settings/tarifa/gating (~6)**: round-trip `willard_distribution_centers`; `comision_green_loop` unidad canónica; get_current; **flag off → 403 en `/service-tariffs` (re-gate E1, H2 QA)**; **comisión GL a receptor sin `service_provider` → 422 (H3)**; **ICA "Bogota"/"Bogotá" resuelven a la misma entidad (H4)**.

**Stress walk (extensión especificada)**: acciones `inbound_receipt`/`inbound_annul` sobre `ml_material` (fixture: flag + cuenta kg + fórmula en la org del walk); **I5 gana 2 términos**: `+Σ(qty × line.unit_cost)` de órdenes confirmed y `+Σ annul_cost_adjustment` de anuladas; counts nuevos (`inb ≥ 2`, `inb_annul ≥ 1`); **invariante 6º nuevo**: saldo kg por cuenta == SUM(confirmed) tras cada op.

**Declarado**: sin tests frontend (precedente E1); preview delta_kg etiquetado "estimado" y verificado manual (§9).

## 9. Criterios de done + guion de pruebas

**Done técnico**: 2 migraciones en dev; suite completa verde en 5433 (~1179 + ~68) con log completo (`tee`); parity check **extendido a pg_enum** = cero fuera de baseline; golden ampliado diff cero (§7); `tsc` + build; 390/1280 de las 2 pantallas + 4 forms extendidos; informe QA con el contrato de evidencia de E1.

**Pre-demo (Code, jueves 30)**: en SAC dev: 6 cuentas kg + fórmulas resuelven (BAT-07 2.5, JAMICHE 0.53, SEC 0.56/0.59) + tarifa `comision_green_loop` vigente + **tercero Green Loop existente con categoría `service_provider`** (H3 QA: sin el behavior, `_process_commissions` rechaza con 422 al liquidar — #32; la clase de incidente que el pre-check D11c de E1 previno).

**Nota de cronograma (QA)**: si Daniel ejerce el colchón de D9 (retenciones → patch de semana 3), el paso 5 del guion se ajusta EN EL MISMO ACTO — no descubrirlo el viernes.

**Done funcional (guion, viernes 31)**:
1. **Johana**: crear las 6 cuentas kg — el form sugiere códigos; lo estructural es tipo+sede (Willard Baterías = 2 filas: CV y BOG).
2. **David**: Recepción → postconsumo 100 BAT-07 en CV → "Plomo (kg)" muestra +250 kg en el sub-saldo BAQ con la fórmula visible.
3. **David**: Recepción → drosses 1.000 kg SEC en JM — elegir PINZA (+590) vs ESCURRIDO (+560) cambia el número; probar ambos.
4. **David**: Recepción → compra propia 500 kg jamiche → aparece en Compras registrada, inventario en tránsito, **cuentas kg quietas**. Verificar en Movimientos de Inventario el label "Recepción (orden)" con link.
5. **Johana**: liquidar fijando precio + una retención ReteFuente → proveedor queda neto, "[Retenciones] ReteFuente" aparece con el monto y sale en el pasivo del Balance Detallado.
6. **Johana**: movimiento manual −10 kg en Willard Drosses con motivo → statement con saldo corrido.
7. **David**: editar su captura del paso 2 (corregir 100 → 95 baterías) → el sub-saldo BAQ queda en +237.5 kg exacto (D18 — él mismo corrige, sin pedirle a Johana).
7b. **Johana**: anular la recepción del paso 3 → saldo kg e inventario vuelven exactos (anular sí es del liquidador, D13).
8. Verificación negativa: org sin flag o usuario sin permiso → módulos no existen, ni por URL.
9. Nota para Johana (esperado, no bug): el inventario Willard aparece valorado en el Balance sin deuda en pesos — la deuda es en kg (D2).
10. Todo lo raro → triage lunes.

**Post-deploy (Code, viernes 31)**: verificar en PROD: flag activo, 3 permisos sembrados, **fórmulas y tarifas vigentes** (sin ellas los pasos 2-3 revientan en 422 en vivo) — checklist en el informe.

## 10. Secuencia de implementación

1. Migración D (autocommit_block) + espejos + extensión parity check pg_enum; suite temprana.
2. `require_org_flag` + KgLedger (cuentas → statement/summary → manual) con tests por bloque.
3. Refactor composabilidad `create/cancel(commit=)` + tests de regresión → InboundOrder Willard (costing D2/D4 + asientos D5/D6) → derivación D7/D7b → annul D8 (+ as-of H2); tests.
4. Retenciones D9 completas (tabla + hooks + tercero/categoría + eventos statement + pago neto) + tests; tarifa GL + settings D12.
5. Migración E + dual-write.
6. Frontend: NavItem orgFlag + Plomo (kg) + Recepción + extensiones compras/inventario; hooks + D17.
7. Stress walk extendido + evidencia (suite → parity → golden ampliado → build) → informe QA → pruebas Daniel → commit → viernes 31 `/deploy` + demo.

Estimación: ~3.5-4 días backend (la ronda agregó el refactor de composabilidad, los eventos de statement y la extensión H2; las respuestas de Johana agregaron la edición D18 y el ICA por municipio — el costing en sí se simplificó y la edición reusa la mecánica del annul+confirm), ~1.5 días frontend, ~0.5 evidencia. Ajustado pero cabe si el GO de QA llega lunes; colchón: retenciones D9 es el bloque más desacoplable (podría deslizarse a un patch de mitad de semana 3 sin tocar el resto — decisión de Daniel si el viernes aprieta). El plan E3 se escribe en paralelo (§5 ciclos solapados).

---

## 11. Respuestas de Johana (2026-07-16, en vivo vía Daniel) — incorporadas en esta versión

| # | Pregunta | Respuesta | Aterrizaje |
|---|---|---|---|
| 1 | Reventa física por báscula | **NO hacen reventa** — todo pasa por inventario, solo compras y ventas; DP queda habilitado por si acaso | §0.3, D7: valor muerto + errata al canon v0.5 (flujo 3/UN3 no aplica a SAC) |
| 2 | ICA por municipio | **Sí — ICA por municipio**; aplica ICA, ReteFuente y ReteIVA | D9: `municipality` obligatorio en ICA, entidad por municipio |
| 3 | Tipos de retención | **Las 3** | D9: Literal confirmado |
| 4 | Camión Willard mixto | **Puede venir mezclado, UNA remisión** (la duda de Daniel sobre multi-línea se aclaró: la orden siempre soportó N líneas como compras — la pregunta era solo por la clasificación escurrido/pinza del SEC) | D6: regla de subtype por línea confirmada |
| 5 | Corrección de capturas | **David edita él mismo** | D13/D18: edición con `purchases.edit` (revert-and-reapply); anular sigue siendo de Johana |
| 6 | Green Loop $100/kg | **Sí, por kg de material recolectado**; **PENDIENTE menor**: si es parejo para todo material | D7: unidad `per_kg_material` confirmada; la sugerencia editable absorbe cualquier respuesta |

**Pendientes menores con Johana (no bloquean QA ni código):** (a) ¿$100 parejo para todo material recolectado? — el diseño lo soporta en ambos casos; (b) confirmar que crear las 6 cuentas kg por UI en la semana 2 (con saldos de juguete, los reales llegan en S4) le funciona operativamente — es el plan por defecto (D8-E1 sin seeds).
