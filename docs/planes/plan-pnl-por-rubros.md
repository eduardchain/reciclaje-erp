# Plan: P&L por rubros — Estado de Resultados con secciones Operativo / Financiero / Depreciación (requerimiento C)

**Versión:** v2.1 (2026-07-15) — v2 QA-aprobado + enmienda de pruebas de usuario
(§6.1-bis): el desglose por FUENTE dentro de cada rubro se elimina de la
presentación — el cliente no distingue causado/pagado/provisión, cada gasto cae
en su rubro y punto. 1 línea por rubro con drill-down directo; "Total Comisiones"
eliminado (redundante). Solo display — backend y tests de v2 intactos.
**Requerimiento:** C (reunión 2026-07-06, Reciclajes de la Costa)
**Estado:** IMPLEMENTADO (backend + frontend) — pendiente QA del PR + pruebas
de usuario finales

---

## 1. Contexto y decisiones del usuario

El P&L actual muestra los gastos como una sola bolsa "Gastos Operacionales"
(desglosada por categoría y fuente, decisión #22). El cliente quiere leerlo como
estado de resultados formal: separar gasto **operativo**, **financiero** y
**depreciación** con subtotales escalonados.

Decisiones cerradas con Daniel (2026-07-15):

| # | Pregunta | Decisión |
|---|----------|----------|
| D1 | ¿Qué categorías son financieras? | **Bancaria e Intereses** por ahora — pero **configurable** por categoría |
| D2 | ¿Comisiones y Cargos dentro de operativos? | **Línea propia, como está hoy** (entre bruta y operativos) |
| D3 | ¿% de utilidad bruta? | **Sin porcentajes nuevos en v1** — los que hoy se muestran quedan igual. **BACKLOG (2026-07-15, no urgente)**: el cliente sí quiere % sobre los 4 subtotales; fórmulas acordadas: Bruta Ventas ÷ ventas (existe), Bruta Total ÷ (ventas+servicios), Operacional ÷ (ventas+servicios), Neta ÷ (ventas+servicios) (existe). **Pregunta pendiente al cliente antes de implementar**: ¿la base del % de Bruta Total incluye la facturación Pasa Mano o no? (el margen DP suma al numerador sin facturación en el denominador → el % lee alto en meses de mucho cruce; incluirla haría el % no verificable a mano desde la pantalla). Implementación al resolver: 2 campos backend (`gross_margin_total`, `operating_margin` vía `_safe_pct`), display periodo + Excel, test de las 4 fórmulas |
| D4 | ¿Uno o dos subtotales (EBITDA)? | **Un solo subtotal**: "Utilidad Operacional" después de depreciación |

## 2. Layout final

```
Ingresos por Ventas                          X
(−) Costo de Ventas                          X
= Utilidad Bruta en Ventas                   X
+ Utilidad Pasa Mano / Servicios / Transformaciones /
  Merma / Ajustes / Sobreventa               (líneas actuales, intactas —
                                              Ingresos Financieros YA NO va aquí)
= UTILIDAD BRUTA TOTAL                       X   ← muestra el campo NUEVO
                                                   gross_profit_before_financial
                                                   (= total_gross_profit − interest_income;
                                                   idéntico al actual cuando intereses = 0)
(−) Comisiones y Cargos (Ventas)             X          (línea propia, D2)
(−) Comisiones y Cargos (Pasa Mano)          X          (ídem)
(−) GASTOS OPERATIVOS                        X   ← subtotal nuevo + detalle
(−) DEPRECIACIÓN                             X   ← subtotal nuevo (automático)
= UTILIDAD OPERACIONAL                       X   ← subtotal nuevo (D4)
(+) Ingresos Financieros                     X   ← única aparición (GAP-1 QA)
(−) GASTOS FINANCIEROS                       X   ← subtotal nuevo + detalle
= UTILIDAD NETA                              X          (valor intacto)
```

**Invariante central: la utilidad neta NO cambia ni un peso.** Es re-presentación:
`gastos_operativos + depreciación + gastos_financieros == operating_expenses` actual.

**Cascada visual cerrada (GAP-1 QA)**: cada subtotal impreso es la suma exacta de
las filas visibles que lo preceden — un contador sumando el Excel cuadra siempre:
`Σ(zona bruta) == gross_before_fin`; `gross_before_fin − comisiones − operativos −
depreciación == operacional`; `operacional + ingresos financieros − gastos
financieros == neta`. El campo `total_gross_profit` NO cambia (API/tests/conciliación
#59-#69 intactos); solo el valor MOSTRADO como "Utilidad Bruta Total" baja por
−intereses cuando existan — va en el pantallazo antes/después de R1.

## 3. Diseño: clasificador de 3 niveles (del automático al configurable)

Cada fila de gasto del P&L se clasifica en una sección `operativo | financiero |
depreciacion` con esta **precedencia** (la fuente gana sobre la categoría):

1. **Por source_type (automático)**: `depreciation_expense` → `depreciacion`.
   El módulo de activos fijos es la fuente de verdad — cero configuración.
2. **Por movement_type (automático)**: `obligation_interest_accrual` → `financiero`,
   sin importar bajo qué categoría se causó (el módulo F ya lo identifica; hoy
   entra al pool de gastos por `EXPENSE_MOVEMENT_TYPES`, reports.py:3800 y el
   loop reports.py:834).
3. **Por categoría (lo único que configura el cliente)**: columna nueva
   `pnl_section` en `expense_categories` (`String(20)`, NOT NULL,
   `server_default='operativo'`, valores `operativo|financiero`). Patrón #59
   calcado: el valor vive SOLO en categorías **raíz**; las hijas **heredan en
   LECTURA** (helper espejo de `_get_dp_pct_by_category`, reports.py:3870);
   422 si se intenta setear `financiero` en una hija; **reparentar resetea** a
   `operativo` (espejo del zereo de pct en `expense_category.py:162`).
   Gasto sin categoría → `operativo`.

Notas de alcance del enum:
- `depreciacion` NO es valor configurable de categoría — solo lo asigna el nivel 1.
  Consecuencia documentada: un gasto manual bajo la categoría "Depreciacion de
  equipos" (existe en Costa) cae en OPERATIVO; la depreciación real debe salir
  del módulo de activos. Comunicar al cliente.
- Ingresos (`service_income`, `loan_interest_accrual`) no se clasifican — no son
  gastos; ver §6.1 para el reposicionamiento de display de interest_income.

Mapeo inicial de Costa (validado contra la réplica): solo **Bancaria** e
**Intereses** → `financiero`. Las otras ~42 categorías quedan operativas por
default (server_default, cero backfill). El cliente lo configura en Config, no
nosotros por SQL.

## 4. Migración

Una migración, un ADD COLUMN:

```python
op.add_column("expense_categories", sa.Column("pnl_section", sa.String(20),
              nullable=False, server_default="operativo"))
```

Downgrade: drop. Sin índice (se lee vía mapa en memoria, patrón #59).

## 5. Backend

### 5.1 Modelo + schema + service de categorías

- `ExpenseCategory`: + `pnl_section` mapped_column.
- Schemas (`app/schemas/expense_category.py`): Base + `pnl_section:
  Literal["operativo", "financiero"] = "operativo"`; Update opcional (espejo de
  `double_entry_general_pct`, :22 y :51). Response lo expone.
- Service (`app/services/expense_category.py`): validaciones espejo de #59 —
  en create/update, si `parent_id` presente y `pnl_section == "financiero"` →
  422 "solo en categorías raíz"; al reparentar (update que agrega parent_id)
  forzar `pnl_section = "operativo"` (junto al zereo de pct :162 y al copy de
  is_direct :123). Permiso: el PATCH existente (`treasury.manage_expenses`) —
  sin permiso nuevo.

### 5.2 Clasificador en reports — `_get_pnl_section_by_category`

Helper espejo de `_get_dp_pct_by_category` (reports.py:3870): 1 query a
`expense_categories` de la org → `dict[str(cat_id), str]` con herencia raíz
(`section = own[parent_id] if parent_id else own[id]`). A diferencia del pct,
aquí TODAS las categorías entran al mapa (no solo >0) y las directas también
(un gasto directo puede ser financiero — p.ej. interés de un crédito de
maquinaria; no hay razón para excluirlas). **Calco fiel del original: SIN
filtro `is_active`** (N3 QA) — los gastos históricos bajo categorías
desactivadas conservan su sección; filtrarlas los haría caer silenciosamente
a operativo.

### 5.3 `_calculate_profit` (reports.py:474) — split del pool

En el loop de `mm_rows` (reports.py:825-841), además de acumular
`operating_expenses` (que se MANTIENE como total, compat):

```python
if mt == "depreciation_expense":
    section = "depreciacion"
elif mt == "obligation_interest_accrual":
    section = "financiero"
else:
    section = section_map.get(str(cat_id), "operativo") if cat_id else "operativo"
```

Acumular `expenses_operating / expenses_depreciation / expenses_financial` y
setear `pnl_section=section` en cada `ExpenseCategoryBreakdown` (schema
reports.py:88 gana el campo, default `"operativo"`).

Subtotales nuevos en el return dict:

```python
gross_profit_before_financial = total_gross_profit - interest_income   # GAP-1 QA
operating_result = (gross_profit_before_financial - commissions_paid
                    - expenses_operating - expenses_depreciation)
# invariantes (asserts del test golden):
#   expenses_operating + expenses_depreciation + expenses_financial == operating_expenses
#   gross_profit_before_financial == total_gross_profit - interest_income
#   operating_result == gross_before_fin - commissions_paid - op - dep
#   net_profit == operating_result + interest_income - expenses_financial
```

`gross_profit_before_financial` es la ÚNICA fuente de verdad del subtotal bruto
mostrado — los 3 consumidores (P&L periodo, mensual, Excel) leen el campo en vez
de derivarlo cada uno (evita drift entre vistas).

### 5.4 Response (`ProfitAndLossResponse`, schemas/reports.py:96)

Campos NUEVOS (los existentes no cambian de valor ni de nombre):
`expenses_operating: float = 0`, `expenses_depreciation: float = 0`,
`expenses_financial: float = 0`, `gross_profit_before_financial: float = 0`,
`operating_result: float = 0`;
`ExpenseCategoryBreakdown.pnl_section: str = "operativo"`.
El tab Mensual (#50) los hereda gratis: `ProfitAndLossMonthlyPeriod` extiende
`ProfitAndLossResponse` y el service reusa `get_profit_and_loss` por columna.

### 5.5 Drill-down #49 — param `pnl_section` en el listado de Tesorería ⚠️ (el punto fino)

Problema: hoy los grupos de gasto del P&L (por source_type) linkean a
`/treasury?tab=expense...` y el **test de oro de paridad** exige
`suma(listado) == número del P&L`. Al partir el source `expense` entre
OPERATIVO (Arriendo, Nómina...) y FINANCIERO (Bancaria), el link del grupo
operativo listaría TAMBIÉN los movimientos de Bancaria → paridad rota.

Solución (mismo patrón que `adjustment_class`/`movement_type` CSV de #49):
`GET /money-movements` gana `pnl_section: Optional[str]`
(`^(operativo|financiero|depreciacion)$`, junto a money_movements.py:645-652).
El service filtra con el MISMO clasificador de §5.3 (source overrides +
subquery/join al mapa de categorías — implementación: expr `case()` sobre
movement_type + `IN` de category_ids financieros calculados con el helper).
**N1 QA — restricción implícita**: cuando viene `pnl_section`, el service
agrega `movement_type IN EXPENSE_MOVEMENT_TYPES` como filtro base aunque no
venga filtro de tipo — el param significa "sección de gasto del P&L"; sin la
restricción, un transfer sin categoría matchearía "operativo" (falso positivo
para consumidores directos del API; nuestros links siempre llevan tab, pero la
semántica debe ser correcta por sí sola).
Frontend: los grupos por fuente dentro de cada rubro linkean con
`&pnl_section=...`; `TreasuryPage` lee el param y muestra badge
"Sección: Financieros ×" (patrón badges #49). Paridad por construcción: ambos
lados usan el mismo clasificador.

`depreciation_expense` y `obligation_interest_accrual` quedan cubiertos por el
mismo param (sus tabs actuales no cambian; el param es aditivo).

## 6. Frontend

### 6.1 `ProfitAndLossPeriodView.tsx` — reordenar la escalera

- La zona de ingresos pierde la línea "Ingresos Financieros" y la gana la zona
  post-operacional (entre UTILIDAD OPERACIONAL y GASTOS FINANCIEROS). El
  drill-down de la línea (tab de Tesorería) viaja con ella. La fila "Utilidad
  Bruta Total" pasa a leer **`gross_profit_before_financial`** (GAP-1 QA) — el
  campo `total_gross_profit` queda intacto en el response pero deja de
  mostrarse como subtotal; así cada subtotal impreso suma exactamente las filas
  visibles que lo preceden (cascada verificable a mano en pantalla y Excel).
- **§6.1-bis (enmienda v2.1, pruebas de usuario 2026-07-15)**: el bloque de
  gastos queda con **UNA línea por rubro** — "Gastos Operativos"
  (`expenses_operating`, drill `pnl_section=operativo&status=confirmed` SIN tab:
  la restricción implícita N1 lista los 5 tipos de gasto de la sección),
  "Depreciación de Activos" (`expenses_depreciation`, drill del tab
  depreciation_expense actual) y "Gastos Financieros" (`expenses_financial`,
  drill `pnl_section=financiero`). El desglose por fuente de #22 (Directos /
  Provisiones / Causados / Diferidos) **desaparece del P&L** — el cliente no
  distingue causado/pagado; el detalle por categoría vive en el Reporte de
  Gastos (#44). "Total Comisiones" también se elimina (quedan las 2 líneas
  Ventas / Pasa Mano). Depreciación / Financieros / Ingresos Financieros se
  ocultan si son 0; Gastos Operativos siempre visible. La paridad drill-down
  de la línea única está garantizada por el test
  `test_operativo_parity_excludes_non_expense` (suma del listado == subtotal).
- Nueva fila subtotal "Utilidad Operacional" (`operating_result`), estilo de
  las filas de subtotal existentes. Sin % nuevos (D3).

### 6.2 `ProfitAndLossMonthlyView.tsx` + `excelExport.ts`

Mismas filas nuevas por columna (labels sticky): subtotales de rubro +
Utilidad Operacional + reposicionamiento de Ingresos Financieros + la fila
"Utilidad Bruta Total" lee `gross_profit_before_financial` (los 3 consumidores
leen el MISMO campo, §5.3). Excel del P&L periodo y mensual: filas nuevas en
bold (patrón `currencyColumns` #50).

### 6.3 Config — dialog de categorías

Selector "Sección en el P&L" (Operativo | Financiero) en el dialog, visible
SOLO en categorías raíz (hijas: oculto + nota "hereda del padre", espejo del
input % Pasa Mano #59). Types + service + hook.

### 6.4 `TreasuryPage`

Leer `?pnl_section=` de URL → pasarlo al query + badge con ×.

## 7. Edge cases y reglas

- Gasto sin categoría ("Sin categoría") → operativo. Visible en el detalle como hoy.
- Categoría "Depreciacion de equipos" mapeada financiero por error: NO mueve la
  depreciación real (nivel 1 gana). Documentado en §3.
- `obligation_interest_accrual` bajo categoría operativa → financiero igual
  (nivel 2 gana). El detalle lo muestra bajo su categoría, dentro de FINANCIEROS.
- Retroactividad por diseño (igual que #59): el mapeo se aplica al leer —
  cambiarlo re-presenta períodos viejos. La neta no cambia; solo la distribución
  entre rubros. Avisar al cliente.
- Reparentar una categoría financiera bajo un padre → reset a operativo (hereda
  del padre en lectura). Espejo exacto de G1 de #59.
- `expenses_by_category` conserva orden y contenido actual (solo gana el campo) —
  el Reporte de Gastos #44 y Rentabilidad UN #58/#59 NO se tocan (agrupan por
  UN/categoría, no por rubro; fuera de alcance).

## 8. Tests (~15, en test_api_reports.py + test_api_expense_categories.py)

1. Helper: raíz financiera → hijas heredan financiero; raíz operativa default.
2. 422 al setear financiero en hija (create y update).
3. Reparentar financiera bajo padre → reset operativo.
4. Clasificación: depreciation_expense SIEMPRE depreciacion aunque su categoría
   sea financiera (precedencia nivel 1).
5. obligation_interest_accrual → financiero aunque categoría operativa (nivel 2).
6. Gasto sin categoría → operativo.
7. **Golden de paridad y cascada**: fixture mixto (gasto op + Bancaria +
   depreciación + obligation accrual + **expense_accrual bajo "Intereses"
   financiera — N2 QA: clava que el clasificador cubre los 4 tipos
   por-categoría, no solo `expense`** + venta + préstamo con interés causado
   para que `interest_income > 0`) → `net_profit` y `operating_expenses`
   IDÉNTICOS a los valores pre-cambio; `op + dep + fin == operating_expenses`;
   `gross_profit_before_financial == total_gross_profit − interest_income`;
   `operating_result == gross_before_fin − commissions_paid − op − dep`;
   `net == operating_result + interest_income − expenses_financial`.
8. Breakdown: cada fila con su `pnl_section` correcto.
9. Mensual: subtotales por columna == P&L del período de esa columna.
10. **Drill-down parity nuevo**: `GET /money-movements?movement_type=expense&pnl_section=financiero`
    suma == fila FINANCIEROS-expense del P&L (y operativo análogo) — extensión
    del test de oro #49.
11. `pnl_section` inválido en listado → 422.
12. RBAC: PATCH categoría con pnl_section sin permiso → 403.
13. Compat: response sin tocar categorías → todo operativo, `operating_result`
    presente, guardrail #49 existente sigue verde.

## 9. Criterios de aceptación

1. Config: marcar Bancaria e Intereses como financieras toma 1 minuto y no pide
   soporte técnico.
2. El P&L muestra la escalera de §2 con los 3 rubros y Utilidad Operacional.
3. La utilidad neta de cualquier período es idéntica a la de antes del deploy.
4. Click en un grupo de gasto de cualquier rubro → el listado suma exactamente
   el número del P&L (tolerancia $1).
5. Tab Mensual y Excel muestran las mismas filas nuevas.
6. Cambiar el mapeo re-presenta al instante (sin migrar datos).

## 10. Riesgos

- **R1 — Forma nueva del P&L**: el cliente conoce el layout actual; el
  reposicionamiento de Ingresos Financieros y los subtotales cambian la lectura,
  y el valor mostrado como "Utilidad Bruta Total" baja por −intereses cuando
  existan préstamos activos (GAP-1: es lo que hace cuadrar la cascada).
  Mitigación: pantallazo antes/después al entregar + instructivo corto.
- **R2 — Retroactividad del mapeo**: períodos viejos se re-presentan al cambiar
  la sección de una categoría (neta intacta). Mismo aviso que se dio con el %
  Pasa Mano (#59) — el cliente ya conoce la regla.
- **R3 — Confusión depreciación manual**: si registran depreciación como gasto
  suelto bajo la categoría "Depreciacion de equipos", cae en OPERATIVO. La regla
  "la depreciación sale del módulo de activos" va en el instructivo.
