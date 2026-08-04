# Plan — Venta de Activos Fijos (contrapartida cuenta o tercero + ganancia/pérdida al P&L)

**Versión**: v1.0 · **Fecha**: 2026-08-04 · **Estado**: para revisión QA
**Origen**: ask del cliente — poder vender un activo y que el valor vaya a una cuenta de plata o a la cuenta de un tercero.
**Respuestas del cliente (Daniel, 2026-08-04)**: (1) comprador = cualquier tercero; (2) venta siempre del activo completo; (3) IVA/facturación fuera de alcance; (4) la diferencia precio vs valor en libros va al P&L como línea propia ("Ganancia/Pérdida por Venta de Activos", como transformaciones) — **de acuerdo**.

---

## 1. Contexto y gap

"Dar de baja" hoy (`fixed_asset.py:387`) es destrucción contable pura: depreciación acelerada del remanente (`depreciation_expense` al P&L) + status `disposed`. **No hay forma de registrar plata de vuelta.** La venta es un evento distinto: el valor en libros se entrega a cambio de un precio, y la diferencia es resultado del período.

Patrones que este plan calca (no inventa nada nuevo):
- **XOR cuenta/tercero**: #21 (asset_payment/asset_purchase) y #67 (los 4 tipos de revalorización). La venta es el espejo exacto de `asset_devaluation_collection`/`asset_devaluation_receivable` pero terminal.
- **Radio "cuenta / contra tercero"**: recién deployado en obligaciones (#86).
- **Línea P&L por columnas persistidas fechadas por el MM**: oversell #65/#66.
- **Anti back-dating**: fecha del evento SIEMPRE HOY, sin input (#62/#67).

## 2. Decisiones de diseño

**D1 — La venta NO expensa el remanente (diferencia clave vs Dar de Baja).** Si reusáramos la mecánica de `dispose` (depreciación acelerada del libro) y además registráramos la ganancia, el P&L quedaría doble-contado: vender en $8M un activo de $5M en libros daría −$5M (depreciación) + $3M (ganancia) = −$2M, cuando el efecto real es +$3M. La venta **da de baja el libro contra el precio**: cero movimientos de depreciación; `current_value` queda **CONGELADO** tal cual (no se toca); status → `disposed`. La única línea P&L es `sale_gain = sale_price − current_value_al_momento` (signed: ganancia > 0, pérdida < 0). El congelamiento hace exacta la reconstrucción as-of por construcción (ver D6).

**D2 — Endpoint y tipos.** `POST /fixed-assets/{id}/sell` (permiso `treasury.manage_fixed_assets`, cero permisos nuevos). Body: `sale_price` (Decimal > 0) + XOR `account_id` / `third_party_id` + `notes?`. **2 tipos MM nuevos** (catálogo 45→47):
- `asset_sale_collection` — cuenta **+**, tercero sin efecto.
- `asset_sale_receivable` — tercero **+** (CxC: nos debe), cuenta sin efecto (`account_id=NULL`).
El MM lleva el **precio** (no la ganancia); fecha = HOY mediodía UTC (anti back-dating, sin input de fecha, igual #67). Descripción: "Venta de activo: {nombre}".

**D3 — Comprador tercero: cualquiera excepto `provision` y `liability`** (espejo de la regla de proveedor de activos #32). "Cualquier tercero" del cliente = sin restricción comercial (customer, generic, supplier, investor, todos sirven); provisiones y pasivos son entidades contables internas — acreditarles una CxC los desclasificaría en `_classify_third_party`. **Cobro posterior por los flujos existentes** según behavior del tercero (`collection_from_client` / `collection_from_generic`) — cero cambios ahí; la CxC aparece en su estado de cuenta y en el panel de Dinero Inactivo (#68) sola, por construcción.

**D4 — Persistencia: 3 columnas en `fixed_assets`** (migración única aditiva, nullable, sin backfill): `sale_price NUMERIC(15,2)`, `sale_gain NUMERIC(15,2)`, `sale_movement_id GUID FK→money_movements RESTRICT`. Sin tabla de eventos: la venta es terminal y única por activo (si se anula y re-vende, las columnas guardan la ÚLTIMA venta; el rastro completo vive en los MMs anulados — mismo criterio que #63). `disposed_at/by` y `disposal_reason` ("Venta") se reutilizan tal cual.

**D5 — Guards de creación**: activo `disposed`/`cancelled` → 400; `sale_price ≤ 0` → 422 (precio 0 = regalar = usar Dar de Baja existente); XOR estricto → 422; **depreciaciones pendientes sin aplicar → WARNING informativo, no bloqueo** (vender congela el libro como está: aplicar los meses pendientes primero da un libro menor y una ganancia mayor — elección consciente del operador, copy en el modal, filosofía #17/#76).

**D6 — P&L: línea "Ganancia/Pérdida por Venta de Activos" (`asset_sale_gain`)**. Fuente: `SUM(fixed_assets.sale_gain)` JOIN `money_movements` por `sale_movement_id` con `MM.status='confirmed'` y `MM.date` en el rango — el status del MM gobierna (anular saca la línea del P&L sin limpiar columnas, patrón oversell). Integración:
- Suma a `total_gross_profit` (reports.py:1006) — un término nuevo en la suma.
- `gross_profit_before_financial` la arrastra sola (NO es línea financiera; la cascada #71 y sus 4 identidades quedan intactas por construcción — solo cambia el upstream).
- **7ª línea de conciliación** (#59): org-level, no atribuible a UN — `PnlReconciliation.asset_sale_gain` + el test de oro `test_reconciliation_residual_zero` se extiende (si no, revienta: ese es su trabajo).
- Frontend: fila condicional ≠0 en P&L periodo y mensual + Excel + línea en el bloque de conciliación de Rentabilidad por UN (patrón exacto de oversell #65).
- Rubros #71: sin impacto (clasifican gastos; esta es línea de ingreso bruto).

**D7 — Terna de signos, sitios** (tabla obligatoria):

| Sitio | `asset_sale_collection` | `asset_sale_receivable` |
|---|---|---|
| `VALID_MOVEMENT_TYPES` (models) | +1 | +1 (catálogo 47) |
| `ACCOUNT_BALANCE_DIRECTION` (reports) | **+1** | NO entra |
| `THIRD_PARTY_BALANCE_DIRECTION` (reports, vivo y as-of) | NO entra | **+1** |
| 2 mapas del statement (money_movements.py) | cuenta +1 | tercero +1 |
| `INFLOW_TYPES` (cash flow + dashboard MTD) | **entra** — campo desglose nuevo `asset_sale_collections` (espejo de `asset_devaluation_collections` #67) | NO entra (sin caja) |
| `EXPENSE_MOVEMENT_TYPES` | NO | NO |
| `ASSET_MOVEMENT_TYPES` guard (money_movement.py:1032) | +1 | +1 → anular desde Tesorería = 422, solo desde el activo |

**D8 — Anulación de la venta** (desde el detalle del activo, no Tesorería): guard defensivo LIFO estilo #67 — assert de que no hay depreciación ni reval activa posterior a `disposed_at` (imposible por construcción: disposed no genera eventos; el assert es barandilla). Efecto: `annul()` del MM revirtiendo su efecto (cuenta − o tercero −), status del activo restaurado **derivado** de `current_value` vs `salvage_value` (`active` | `fully_depreciated`, criterio #67 "estados derivados"), `disposed_at/by/reason` limpiados. `sale_*` columns quedan como rastro (el MM anulado las saca del P&L por D6).

**D9 — Balance vivo y as-of, exactos por construcción**: vivo ya excluye `disposed` (reports.py:1430/1725/2662) → el activo vendido sale del balance y entra la caja o la CxC — cuadre automático módulo la ganancia (que es exactamente la línea P&L, como debe ser). As-of: `_fa_existed_at_cutoff` (#61a) ya incluye disposed con `disposed_at >= corte`, y `_fa_value_at_cutoff = current_value + Σ dep futuras − Σ reval futuras` devuelve el libro congelado (D1: la venta no toca `current_value` ni crea registros de depreciación) → un corte anterior a la venta muestra el activo a su libro exacto, un corte posterior no lo muestra y sí muestra la caja/CxC (el MM ancla diario, mismo boundary que #67 H1). **Cero re-presentación de cortes históricos al deploy** (columnas NULL, línea P&L suma 0 para datos existentes) → golden intacto.

## 3. Frontend

- **`SellAssetModal`** (espejo estructural de `RevalueAssetModal`): `MoneyInput` precio, radios Cuenta / Tercero (sin default, elección explícita #63) con `Select` de cuentas / `EntitySelect` de terceros filtrado (sin provision/liability, sin entidades de sistema), **preview vivo** "Ganancia: $X" / "Pérdida: $X" (emerald/red) = precio − valor en libros, warning ámbar si hay depreciaciones pendientes, copy de contrapartida (tercero con saldo negativo: la CxC primero consume ese saldo, #31).
- **`AssetDetailPage`**: botón "Vender" (gate permiso + status vendible), sección "Venta" (precio, ganancia/pérdida coloreada, link al MM, quién/cuándo), botón anular con `ConfirmDialog`.
- **`AssetsPage`**: badge "Vendido" (disposed + `sale_movement_id` con MM confirmed) diferenciado de "Dado de baja".
- **P&L**: fila condicional + conciliación + Excel (periodo y mensual).
- **Tesorería**: +2 labels en los 5 mapas duplicados + union `MoneyMovementType`; `MovementDetailPage` ya oculta anular por el set de tipos de activo (extender el set frontend +2, nota guía al activo).
- Mobile 390px per CLAUDE.md (el modal base ya es responsive).

## 4. Tests (~22, `test_asset_sale.py`)

1. Happy cuenta: ganancia — caja +precio, activo fuera del balance vivo, `sale_gain` exacto, MM confirmado.
2. Happy tercero: pérdida — CxC +precio, `sale_gain` negativo.
3. Venta a valor en libros exacto → `sale_gain` 0, línea P&L 0.
4. Guards: XOR (ambos/ninguno) 422, precio ≤ 0 422, disposed 400, cancelled 400, tercero provision 400, tercero liability 400.
5. Warning de depreciaciones pendientes presente en el response.
6. **P&L**: línea por rango de fechas (venta dentro/fuera), anulada NO cuenta, suma a `total_gross_profit`.
7. **Golden conciliación**: `test_reconciliation_residual_zero` extendido — residual $0 con una venta con ganancia en el período; cascada #71 (4 identidades) con la línea ≠ 0.
8. **Cash flow**: inflow solo en venta por cuenta; venta por tercero no toca cash flow (before==after).
9. **As-of corte-de-ayer**: venta HOY no reescribe el balance de ayer (activo a libro en el corte, caja sin el precio); corte de mañana lo excluye (patrón golden #67).
10. Estado de cuenta del tercero comprador: evento visible, saldo corrido.
11. Annul round-trip cuenta y tercero: activo restaurado (status derivado correcto en ambos casos: activo a media vida → `active`; totalmente depreciado → `fully_depreciated`), contrapartida devuelta al peso.
12. Anular desde Tesorería → 422 guía.
13. RBAC: sin `treasury.manage_fixed_assets` → 403.

## 5. Migración

Una, aditiva: `ALTER TABLE fixed_assets ADD sale_price / sale_gain / sale_movement_id` (nullable, FK RESTRICT). Espejo en el modelo (paridad D13/E1 — el parity check debe dar diff cero). Aplicar en dev 5434 (5433 se recrea por conftest, no-op).

## 6. Fuera de alcance (acordado con el cliente)

- IVA / facturación electrónica.
- Venta parcial de un activo.
- Precio $0 (donación/chatarra sin plata = "Dar de Baja" existente).
- Recalcular depreciaciones históricas del activo vendido.

## 7. Riesgos y mitigaciones

- **Doble conteo P&L** (el riesgo #1 del diseño): mitigado por D1 (la venta NO genera `depreciation_expense`) + test 7 (residual cero con venta en el período).
- **Descuadre as-of**: mitigado por D1 (libro congelado) + D9 + test 9 (golden corte-de-ayer, la lección de #67 H1).
- **Fuga por Tesorería**: los 2 tipos entran a `ASSET_MOVEMENT_TYPES` (anulación solo con la restauración del activo, nunca suelta).
- Retroactividad: ninguna — todo nace con la venta, datos existentes intactos.
