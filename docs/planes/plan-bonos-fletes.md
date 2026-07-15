# Plan: Bonos y Fletes como cargos de operación (requerimiento B)

**Versión:** v2 (2026-07-15) — v1 QA-APROBADO + addendum DP tras respuestas del cliente (§11)
**Requerimiento:** B (fletes/bonos como items de liquidación) — Reciclajes de la Costa
**Estado:** IMPLEMENTADO v1 + extensión DP (incluye nice-to-have de QA: label del cargo
de compra en estado de cuenta, y nicety de schemas Base) — pendiente QA del PR + pruebas
de usuario

---

## 1. Contexto y respuestas del cliente

El cliente paga fletes (transportadores) y bonos (vendedores) asociados a operaciones
concretas. Hoy los registra como gastos sueltos de tesorería, perdiendo el vínculo con
la operación: el flete de compra no encarece el material y el bono de venta no baja el
margen de la venta que lo generó.

Las 4 preguntas enviadas (2026-07-10) y sus respuestas (2026-07-14):

| # | Pregunta | Respuesta del cliente |
|---|----------|----------------------|
| P1 | Flete de COMPRA: ¿al costo del material o gasto del mes? | **Al costo del material** (opción A) |
| P2 | Bono/flete de VENTA: ¿amarrado a la venta bajando su margen o gasto general? | **Amarrado a la venta bajando su margen** |
| P3 | Bonos: ¿a quién y en qué operaciones? | **A vendedores, por vender → venta → gasto amarrado** (se comporta como P2) |
| P4 | ¿Pago inmediato o solo causar? | **Igual que las comisiones** (causar; pago aparte) |

**Consecuencia de diseño**: las respuestas mapean 1:1 a los DOS mecanismos de comisión
que ya existen y están battle-tested. No se inventa mecánica nueva — se **generaliza**:

- Flete de compra ≡ comisión de compra (#30): prorrateo al costo del material, sin MM,
  solo balance del tercero. `adjusted_unit_cost = unit_price + (prorrateo / quantity)`.
- Flete/bono de venta ≡ comisión de venta (#23): `commission_accrual` al liquidar
  (P&L devengado, tercero+, account_id NULL), pago aparte via **`commission_payment`**
  (tipo MM dedicado, endpoint `POST /money-movements/commission-payment` —
  money_movements.py:338, servicio `pay_commission`). Los cargos se pagan por ahí
  mismo sin cambio alguno (P4).

## 2. Diseño: `charge_type` sobre las tablas de comisiones

Columna nueva `charge_type` (String(20), NOT NULL, `server_default='commission'`) en
`purchase_commissions` y `sale_commissions`:

| Tabla | Valores permitidos | Validación |
|-------|--------------------|-----------|
| `purchase_commissions` | `commission` \| `freight` | servicio (no enum de BD) |
| `sale_commissions` | `commission` \| `freight` \| `bonus` | servicio (no enum de BD) |

Decisiones estructurales (la parte importante):

- **D1 — CERO tipos de MoneyMovement nuevos.** Los cargos de venta viajan en el MISMO
  `commission_accrual` existente. Implicación: la terna de signos (6 sitios, #67/#69)
  NO se toca, el P&L no gana líneas, la conciliación #59 no cambia, el drill-down #49
  (`tab=commission_accrual`) sigue cuadrando por construcción, el estado de cuenta y el
  panel #68 tratan los cargos exactamente como comisiones. El costo de esta decisión:
  en el P&L los bonos/fletes de venta se suman a la línea de comisiones (ver D4).
- **D2 — `String` con validación en servicio, NO extender el enum `commission_type`
  de Postgres.** `commission_type` (percentage|fixed|per_kg) es el CÓMO se calcula;
  `charge_type` es el QUÉ es. Ortogonales: un flete puede ser fijo o por kg; un bono
  puede ser % de la venta. No se restringe ninguna combinación.
- **D3 — Regla de destinatario #32 uniforme**: el recipient de cualquier cargo debe
  tener behavior_type `service_provider` (transportadores y vendedores lo son; si un
  proveedor de material también fletea, se le agrega la categoría — M:N ya lo permite).
  Sin excepciones nuevas = un solo selector (`payable-providers`) y una sola regla de
  clasificación en balances.
- **D4 — Etiquetas visibles, campo del P&L intacto.** El campo `commissions_paid_sales`
  del response NO se renombra (compat). Los labels de UI pasan de "Comisiones Pagadas
  (Ventas)" a **"Comisiones y Cargos (Ventas)"** (P&L periodo, mensual, Excel, tab de
  Tesorería "Com. Causadas"). El desglose por charge_type en reportes queda FUERA de v1
  (ver §8) — el detalle por operación sí lo muestra siempre.
- **D5 — Descripción del MM parametrizada**: el `commission_accrual` de un cargo lleva
  descripción "Flete venta V-00123 — {tercero}" / "Bono venta V-00123 — {tercero}"
  (hoy dice "Comisión..."). Es lo que el usuario ve en Tesorería y estado de cuenta —
  con D1, la descripción es el diferenciador visible.
- **D6 — DP (Pasa Mano) FUERA de alcance.** Las respuestas cubren compras y ventas.
  Los fletes de DP ya tienen su camino: gasto directo asignado a la UN sistema (#58).
  `DoubleEntryCommission`/`_create_commission_records` no se tocan. Si el cliente pide
  bonos en DP después, la misma columna se agrega con el mismo patrón.

## 3. Migración

Una migración, dos `ADD COLUMN`:

```python
op.add_column("purchase_commissions", sa.Column("charge_type", sa.String(20),
              nullable=False, server_default="commission"))
op.add_column("sale_commissions", sa.Column("charge_type", sa.String(20),
              nullable=False, server_default="commission"))
```

`server_default='commission'` → todas las comisiones históricas quedan correctamente
tipadas sin backfill. Downgrade: drop de ambas columnas. Sin índices (no hay queries
por charge_type en v1 fuera de reportes futuros).

## 4. Backend

### 4.1 Modelos

- `PurchaseCommission` (purchase.py:349): + `charge_type` mapped_column.
- `SaleCommission` (sale.py:397): + `charge_type` mapped_column.
- ⚠️ Nota pre-existente detectada: `commission_type` usa `Enum(..., create_type=False)`
  en purchase.py:382 pero sin `create_type=False` en sale.py:436 — no se toca en este
  plan (el tipo ya existe en BD), solo se documenta.

### 4.2 Schemas

- `PurchaseCommissionCreate` / `SaleCommissionCreate`: + `charge_type:
  Literal["commission", "freight"] = "commission"` (purchase) y
  `Literal["commission", "freight", "bonus"] = "commission"` (sale). El default
  preserva compatibilidad total con requests existentes.
- Responses: + `charge_type: str = "commission"`.

### 4.3 Servicio de compras — `_process_commissions` (purchase.py:1369)

- Persistir `charge_type` en el record (constructor `PurchaseCommission` :1404).
- Validación de recipient #32 en :1387 (`has_behavior_type(["service_provider"])`) —
  intacta; solo se generaliza el copy del error: "El comisionista '{name}' debe ser
  proveedor de servicios" → "El receptor del cargo '{name}' debe ser proveedor de
  servicios" (aplica a transportadores y vendedores por igual).
- **El prorrateo NO se toca**: ocurre en la liquidación (purchase.py:432-505) —
  `commission_prorate` ponderado por peso de línea (:432-437), `adjusted_unit_cost =
  unit_price + line_commission/quantity` (:466), aplicado a `inv_movement.unit_cost`
  (:472) y al costo promedio (:481). El flete viaja por el mismo túnel, incluida la
  lectura del costo ajustado que hace la remoción ponderada (#66 H1) y el edit
  revert-and-reapply (delete de PurchaseCommission en :413-414).
- Valores permitidos (`commission|freight`) → 422 por `Literal` en schema.

### 4.4 Servicio de ventas — `_process_commissions` (sale.py:1184) + `_pay_commissions` (sale.py:1310)

- Persistir `charge_type` (constructor `SaleCommission` :1236).
- Validación #32 en :1215 — mismo ajuste de copy que compras.
- `_pay_commissions` crea los `commission_accrual` al liquidar: **descripción según
  charge_type (D5) en :1336** — hoy `f"Comisión venta #{sale.sale_number} - {concept}"`,
  pasa a `f"{label} venta #{...} - {concept}"` con label ∈ {Comisión, Flete, Bono}.
  Fecha `liquidated_at` (:1335, #61), `sale_id` (:1338), balance del recipient (:1342)
  — intactos.
- Auto-annul al cancelar venta (sale.py:607-620: anula los `commission_accrual` por
  `sale_id` + revierte balances :623+) — los cargos viajan igual, cero cambio.

### 4.5 Puntos que se verifican pero NO se tocan (por D1)

- Estado de cuenta unificado (#16): las comisiones de venta viajan como MMs
  `commission_accrual` (el label visible ES la descripción del MM → D5 lo cubre);
  las de compra se enumeran como eventos sintéticos `purchase_commission`
  (money_movements.py:976-993) — el label ahí usa el `concept` del record, que el
  usuario escribe ("Flete Cartagena") — suficiente en v1, sin cambio.
- Filtro `commission_source` (sale|double_entry, money_movements.py:653) del
  drill-down #58: agrupa por origen, no por tipo — cargos entran solos.
- P&L `_calculate_profit`: `commission_accrual` ya sumado — cargos entran solos.
- Rentabilidad por UN (#58): split por `sale_id`/DP ya existente.
- Panel Dinero Inactivo (#68): rama de comisiones sin cambio.
- Costo Real por material: el flete de compra entra via `unit_cost` ajustado — gratis.
- Modelo L (#64/#65/#66): el costo ajustado por cargos viaja en
  `InventoryMovement.unit_cost` — la remoción ponderada (H1) ya lee de ahí.

## 5. Frontend

- **No existe componente compartido de comisiones** — el editor vive inline en cada
  página: `PurchaseCreatePage` / `PurchaseEditPage` / `SaleCreatePage` / `SaleEditPage`
  (edición), `PurchaseLiquidatePage` / `SaleLiquidatePage` / `PurchaseDetailPage` /
  `SaleDetailPage` (visualización). En cada editor: + selector "Tipo" por línea —
  Compras: Comisión | Flete; Ventas: Comisión | Flete | Bono. Default Comisión. La
  sección se renombra "Comisiones y Cargos". (Extraer un componente compartido es
  tentador pero NO es parte de este plan — 8 páginas tocadas con el mismo patrón
  puntual es menos riesgoso que un refactor + feature en el mismo PR.)
- **Liquidate/Detail pages**: mostrar el tipo por línea (badge o prefijo en el
  concepto). PDF/Excel de la operación: columna/label de tipo si aplica.
- **Labels P&L** (D4): ProfitAndLossPeriodView, ProfitAndLossMonthlyView, excelExport,
  TreasuryPage tab.
- **Types**: `charge_type` en los types de comisión + labels es-CO
  (`CHARGE_TYPE_LABELS = { commission: "Comisión", freight: "Flete", bonus: "Bono" }`).
- Mobile: el selector entra en el grid existente del editor (`grid-cols-1` →
  `sm:grid-cols-N`), verificación 390px obligatoria.

## 6. Edge cases y reglas

- **E1 — base per_kg asimétrica (verificada, correcta, se hereda)**: en VENTAS per_kg
  usa `coalesce(received_quantity, quantity)` (sale.py:1225 — la cantidad de báscula,
  consistente con el revenue #18); en COMPRAS usa la cantidad original
  (purchase.py:1397). Fletes/bonos heredan la misma base que las comisiones de su
  operación — documentado, sin cambio.
- **E2 — per_kg con unidades mixtas (#54)**: limitación pre-existente de comisiones
  (suma kg + unidades) — aplica igual a fletes/bonos; se hereda documentada, no se
  arregla acá.
- **E3 — percentage sobre flete**: permitido (D2) — no hay razón para bloquear un
  flete pactado como % del total.
- **E4 — Compra cancelada / venta cancelada**: reversión de balance del recipient y
  auto-annul del accrual ya existen — los cargos viajan igual. Tests explícitos.
- **E5 — Edit de operación registrada**: revert-and-reapply (#8) reconstruye
  comisiones — charge_type debe sobrevivir el ciclo (test).
- **E6 — Migración de datos**: N/A — no hay cargos históricos que migrar (hoy son
  gastos sueltos). Si el cliente quiere reclasificar gastos viejos, es manual y fuera
  de alcance.

## 7. Tests (~19)

- **Compras** (6): crear con flete fijo/per_kg → `adjusted_unit_cost` correcto y
  balance del transportador; mezclado comisión+flete misma compra; validación 422
  charge_type inválido (`bonus` en compra); recipient sin service_provider → 400 (#32);
  cancel revierte balance; edit preserva charge_type.
- **Ventas** (8): crear+liquidar con bono % → accrual con descripción "Bono", P&L
  sube `commissions_paid_sales`, margen de Rentabilidad UN baja; flete per_kg (base =
  cantidad recibida si existe, E1); mezcla comisión+bono+flete; cancel auto-anula
  accruals de cargos; charge_type inválido 422; balance del vendedor; estado de cuenta
  muestra el cargo con su descripción; **pago del cargo vía `commission_payment`
  existente** (baja deuda del vendedor/transportador, sin cambio de flujo).
- **Regresión/paridad** (5): drill-down parity #49 (`commission_accrual`) sigue verde
  con cargos mezclados; residual-zero #59; golden #61; default `commission` en request
  sin charge_type (compat); response expone charge_type en históricas (server_default).

## 8. Fuera de alcance (v1)

- Desglose por charge_type en P&L/reportes (líneas separadas "Fletes de Venta", "Bonos")
  — requiere JOIN de accruals→sale_commissions; se propone como v1.1 si el cliente lo
  pide al ver la línea combinada.
- DP/Pasa Mano (D6).
- Reclasificación de gastos históricos (E6).
- Flete de compra como gasto del mes (el cliente eligió costo — no se construye el
  camino alternativo).

## 9. Criterios de aceptación

1. Una compra con flete de $300.000 y 1.000 kg sube el costo unitario del material en
   $300/kg y deja el saldo del transportador en -$300.000 al liquidar.
2. Una venta con bono del 2% liquidada en $10M genera accrual de $200.000 con
   descripción "Bono...", visible en Tesorería, y la utilidad neta de esa venta en
   Rentabilidad UN baja $200.000.
3. El pago del flete/bono se hace igual que una comisión (`commission_payment` desde
   Tesorería, endpoint existente) — sin flujo nuevo.
4. Cancelar la operación revierte el efecto del cargo (balance/accrual) — igual que
   comisiones.
5. Las operaciones históricas siguen mostrando sus comisiones sin cambio alguno.
6. Test de oro #49 (drill-down parity) verde sin modificación.

## 10. Riesgos

- **R1 — Línea P&L combinada**: el cliente podría esperar ver "Fletes" separado en el
  P&L. Mitigación: labels "Comisiones y Cargos (Ventas)" + detalle por operación;
  v1.1 con desglose si lo pide (§8).
- **R2 — Costo retroactivo NO**: el flete solo afecta compras nuevas; el costo
  promedio histórico no se recalcula (coherente con #61/#64 "el pasado no se
  reescribe"). Comunicar al cliente.
- **R3 — Confusión comisión vs flete en captura**: mismo formulario, un select más.
  Mitigación: default Comisión + labels claros.

## 11. Addendum v2 — cargos en cruces Pasa Mano (respuestas del cliente 2026-07-15)

El cliente respondió el paquete de preguntas post-v1:

| # | Pregunta | Respuesta |
|---|----------|-----------|
| P1 | ¿Línea P&L combinada o desglose? | **Combinada** — R1 cerrado, desglose descartado por ahora |
| P2 | ¿Fletes de cruces DP amarrados o gasto de la UN? | **Amarrados** — el gasto-a-UN (#58) queda solo para costos DP no atribuibles a un cruce |
| P3 | ¿Bonos en cruces? | **Sí — ganan por ambos** (ventas y cruces) |
| P4 | ¿Históricos? | **Hacia adelante solamente** |

**Esto SUPERSEDE la decisión D6** (DP fuera de alcance) y confirma que el gasto-directo-a-UN
de #58 era el workaround disponible cuando los cargos amarrados no existían.

Alcance de la extensión (el "cambio chico" pre-anunciado en D6 — el patrón es idéntico):

- **Backend**: `_create_commission_records` (double_entry.py:834) persiste
  `charge_type` (la columna YA existía — DP usa `SaleCommission`); copy #32
  generalizado (:829); descripción del accrual DP parametrizada (:344):
  "Flete DP #7 - …" / "Bono DP #7 - …" (D5). Los 3 valores permitidos
  (`commission|freight|bonus`) — DP reusa `SaleCommissionCreate`, cero schema nuevo.
- **Sin migración**: la columna de v1 cubre DP.
- **Reportes — nada que tocar por D1**: los accruals DP ya se desvían a la sección
  Pasa Mano de Rentabilidad por UN (join por `sale.double_entry_id`, #58) y a la
  línea DP del P&L (`commission_source=double_entry`); los cargos viajan igual.
  Solo cambia el label visible: "Comisiones de Pasa Mano" → "Comisiones y Cargos
  (Pasa Mano)" (P&L periodo/mensual/Excel + Rentabilidad UN).
- **Frontend**: selector "Cargo" (3 opciones) en editores DP + badge en detail.
- **Regla anti doble registro (operativa, comunicar al cliente)**: el flete de un
  cruce va AMARRADO al cruce; el gasto-directo-a-UN Pasa Mano queda SOLO para
  costos del negocio DP sin cruce concreto (ej: arriendo de oficina DP). No se
  fuerza en código — no hay forma de detectar la intención; es regla de captura.
- **Tests** (6, `TestDoubleEntryCharges` en test_api_double_entries.py — verdes):
  crear DP con flete+bono → records con charge_type + accruals con label al liquidar
  y receptor -$500; Rentabilidad UN sección Pasa Mano: `commissions` incluye el cargo
  y la neta baja; cancel DP anula accruals de cargos y restaura balance; compat sin
  charge_type → commission con label "Comisión DP #N"; 422 charge_type inválido;
  400 "receptor del cargo" si el receptor no es service_provider (#32).
