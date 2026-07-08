# Plan A.2 — % de gastos generales atribuido a Pasa Mano (por categoría de gasto)

**Fecha**: 2026-07-08 · **Estado**: v2 IMPLEMENTADO (2026-07-08, decisión #59) — pendiente QA del código antes de commit · **Requiere**: decisión #58 implementada (UN sistema Pasa Mano)

**Historial**: v1 revisada por QA 2026-07-08 → OK con G1 obligatorio (zerar pct al reparentar), G2 recomendado (quantize), G3 decisión de producto (detalle padre/hija separado — v1 lo deja así), G4 cubierto por G1. v2 agrega además el **bloque de conciliación con P&L** (aprobado por Daniel tras el reporte de "no me cuadra" del 2026-07-08: delta $32.26M = 4 líneas no-UN, conciliado al peso).

---

## 1. Contexto y problema

Tras la decisión #58, la sección Pasa Mano del reporte Rentabilidad por UN recibe SOLO:
comisiones DP + gastos **directos** explícitamente asignados a la UN sistema. Los gastos
**generales** (arriendo, contadora, servicios) se prorratean 100% entre las UNs de bodega
por $ compras — Pasa Mano recibe $0 de overhead.

Eso infla la utilidad neta Pasa Mano y castiga a las bodegas: la operación DP también
consume administración. El cliente quiere atribuir un **% gerencial** de los gastos
generales a Pasa Mano.

**Decisiones ya tomadas con Daniel (2026-07-08):**
1. El % es **por categoría de gasto** (no global): "el arriendo sí, la papelería no".
   Un % global se logra poniendo el mismo número en todas las categorías padre.
2. Se aplica **al leer el reporte** (no per-movimiento): cambiar el % recalcula
   retroactivamente todos los períodos. Aceptado explícitamente.
3. Config **persistida en backend** (números oficiales iguales para todos los usuarios
   y para el Excel), editable desde Config y con acceso rápido desde el reporte.
4. El cliente decide los números; default **0%** = comportamiento actual intacto.

## 2. Alcance

| Incluido | Excluido |
|---|---|
| Columna `double_entry_general_pct` en `expense_categories` + migración | % versionado por fechas (retroactividad aceptada) |
| Slice de generales → sección Pasa Mano en `get_profitability_by_business_unit` | Cambios a gastos directos o compartidos (intactos) |
| Sync en `_compute_expense_allocations` (Reporte de Gastos + drill-down detail) | Cambios al P&L (`_calculate_profit` no se toca) |
| Exclusión del slice en `get_real_cost_by_material` (overhead de material) | UI nueva en Reporte de Gastos (el grupo Pasa Mano aparece solo) |
| Campo % en dialog de categorías + línea nueva en `PasaManoCard` + Excel | Nuevo permiso RBAC (reutiliza `treasury.manage_expenses`) |
| **Bloque de conciliación con P&L** en Rentabilidad por UN (§3.7) | Rollup padre/hija en el detalle de generales (G3 — v1 muestra líneas separadas) |

## 3. Backend

### 3.1 Modelo + migración

`ExpenseCategory` ([models/expense_category.py](../../backend/app/models/expense_category.py)) gana:

```python
double_entry_general_pct: Mapped[Decimal] = mapped_column(
    Numeric(5, 2), nullable=False, server_default="0",
    comment="% de los gastos GENERALES de esta categoria atribuido a la UN sistema Pasa Mano (0-100). Solo aplica a categorias raiz indirectas; hijas heredan en lectura.",
)
```

Migración: `add column` con `server_default '0'`, sin backfill (0 = comportamiento actual).
Naming por `system_code` (`double_entry`), NO por el display name (la UN es renombrable).
⚠️ Generar revision ID único con `uuid.uuid4().hex[:12]` (colisión previa documentada).
Aplicar en dev (5434) y test (5433). NUNCA prod (va via `/deploy`).

### 3.2 Semántica del % — reglas exactas

1. **Solo categorías raíz e indirectas**: el % vive en categorías con `parent_id IS NULL`
   y `is_direct_expense=False`.
   - Subcategorías: **heredan en LECTURA** (el % efectivo de una hija = % del padre).
     ⚠️ Distinto al patrón copy-on-create de `is_direct_expense` (decisión #36) — a
     propósito: verificado que editar el padre HOY no propaga a hijas existentes
     ([expense_category.py:124](../../backend/app/services/expense_category.py) solo copia
     al crear/reparentar). Para un número que el cliente va a ajustar en el tiempo, la
     copia crearía hijas desincronizadas silenciosamente. Resolución en lectura = cambiar
     el padre aplica a todo, siempre.
   - Validación en service create/update: `parent_id != None AND double_entry_general_pct > 0`
     → 422 "El % Pasa Mano se configura en la categoría padre". Igual para
     `is_direct_expense=True AND pct > 0` → 422 (sus movimientos generales nunca llegan
     al prorrateo: caen al edge legacy "unassigned directo", ver 3.3).
   - **G1 (QA, obligatorio) — reparent zerea el pct**: al reparentar una categoría raíz
     con pct > 0, el payload no trae pct → la validación del punto anterior no lo atrapa
     y quedaría una hija con pct huérfano en DB (dato muerto que resurge al re-promoverla
     a raíz). Fix espejo del patrón existente: en el branch de reparent del service update
     ([expense_category.py:124](../../backend/app/services/expense_category.py)), junto al
     copy de `is_direct_expense`, setear `update_data["double_entry_general_pct"] = 0`.
     Esto además cubre G4 (el dialog frontend no necesita mandar pct=0 explícito).
   - Rango: Pydantic `ge=0, le=100`.
2. **Solo alocación GENERAL**: directos y compartidos intactos. Gastos generales sin
   categoría (`expense_category_id NULL`) → 0%.
3. **Mecánica** (G2 — quantización especificada): para cada gasto general con % efectivo `p`:
   `slice = (amt × p / 100).quantize(Decimal("0.01"))` → acumulador Pasa Mano;
   el remanente es el literal `amt − slice` → `_prorate_expense(...)` entre bodegas como
   hoy. Conservación exacta al centavo por construcción (`slice + remanente == amt`),
   sin importar el redondeo del slice.
4. **Guard defensivo**: si la org no tiene UN sistema (`system_bu_id is None`), `p` se
   trata como 0 — el slice NUNCA se descarta a la nada (no se pierde plata).

### 3.3 Helper compartido de % efectivo

Nuevo helper en `services/reports.py` (privado, una query):

```python
def _get_dp_pct_by_category(self, db, organization_id) -> dict[str, Decimal]:
    """% efectivo Pasa Mano por categoria: raiz usa el propio, hija hereda del padre.
    Key: str(cat_id). Categorias sin % o directas -> ausentes (getdefault 0)."""
```

Implementación: 1 query de `(id, parent_id, double_entry_general_pct, is_direct_expense)`;
efectivo = `pct[parent_id] if parent_id else pct propio`; filtrar `is_direct_expense=True`
(por si un dato legacy tiene % > 0 en una directa: no aplica).

### 3.4 Los 3 consumidores del prorrateo general (todos se tocan)

| Consumidor | Ubicación actual | Cambio |
|---|---|---|
| `get_profitability_by_business_unit` | branch general [reports.py:~3425](../../backend/app/services/reports.py#L3425) (`_prorate_expense(amt, None, ...)`) | slice → nuevos acumuladores `pasamano_general` + `pasamano_general_detail[cat] = {pct, amount}`; resto prorratea igual. La sección 8 resta el slice en `pasamano_net` y lo expone en el schema. El select de expense_rows ya trae `expense_category_id` ✓ |
| `_compute_expense_allocations` | branch general [reports.py:~3895](../../backend/app/services/reports.py#L3895) | slice → alocación normal `{bu_id: system_bu_id, allocation_type: "general"}` (bu_names AQUÍ SÍ incluye la UN sistema, decisión #58) → el grupo Pasa Mano del Reporte de Gastos y el drill-down detail lo muestran sin tocar `_build_expense_tree` ni el endpoint detail. Requiere lookup de `system_bu_id` (hoy este helper no lee `system_code`) |
| `get_real_cost_by_material` | branch general [reports.py:~3680](../../backend/app/services/reports.py#L3680) | slice se **descarta** del overhead (es costo DP, no de material — mismo criterio que sus gastos directos, decisión #58). ⚠️ Su select de expense_rows HOY NO trae `expense_category_id` — agregarlo |

⚠️ La nota de la decisión #58 "NO sincronizar `_compute_expense_allocations`" aplicaba a la
**exclusión de la UN sistema de bu_names** (fuga de directos), NO a esto. El % SÍ se
sincroniza en los 3 — de lo contrario se rompen los tests de paridad
`test_total_matches_pnl` y `test_total_matches_profitability_bu_sum`
([test_api_reports.py:3068/3084](../../backend/tests/test_api_reports.py#L3068)).
Actualizar los comentarios ⚠️ existentes para reflejar la distinción.

### 3.5 Schemas / API

- `ExpenseCategoryCreate/Update/Response` + `double_entry_general_pct` (`Decimal`, `ge=0 le=100`).
  El endpoint flat (selectores) NO lo necesita.
- `DoubleEntryProfitability` (schemas/reports.py) gana:
  - `general_expenses: float = 0`
  - `general_expenses_detail: list[DoubleEntryGeneralExpenseItem]` — nuevo schema
    `{category_name: str, pct: float, amount: float}`
  - `net_profit` pasa a `gross_profit − commissions − direct_expenses − general_expenses`.
- Sin endpoints nuevos: el % se edita via PUT categoría existente
  (permiso `treasury.manage_expenses`, mismo del CRUD — sin migración de permisos).

### 3.6 Invariantes que NO deben romperse

1. **Paridad P&L**: el slice solo MUEVE plata del bucket generales-bodega al bucket
   Pasa Mano dentro del mismo reporte — `grand_total_net` NO cambia. Ojo con la
   semántica exacta: `grand_total_net == pnl.net_profit` SOLO cuando no hay líneas
   no atribuibles a UN (servicios, transformaciones, ajustes de inventario/terceros);
   en datos reales `pnl.net == grand_total + esas 4 líneas` (conciliado al peso contra
   prod replica 2026-07-08, delta $32.26M explicado completo). Los tests de paridad
   (integración 11, fixtures con esas líneas en 0) deben seguir verdes + variante
   nueva con % ≠ 0.
2. **Default 0 = cero cambio**: toda la suite actual (904 verdes) debe pasar SIN tocar
   fixtures — es la red de regresión del rollout (deploy sin configurar % = números idénticos).
3. **Conservación**: `Σ slice + Σ prorrateado == Σ generales` (nada se pierde ni duplica,
   incluso con base de compras $0 — ver riesgo R2).
4. ⚠️ `de_profit` local de `_calculate_profit` (P&L): intocable, como siempre.

### 3.7 Bloque de conciliación con P&L (aprobado por Daniel 2026-07-08)

**Motivación**: el TOTAL GENERAL del reporte NO es la utilidad del P&L — difieren en las
líneas no atribuibles a UN. Caso real que disparó la duda (Costa, jun 4 – jul 3):
grand_total $77.446.374 vs P&L $109.707.436; delta $32.261.062 = servicios $15.253.643
+ transformaciones $3.193.325 + ajustes inventario $186.355 + ajustes terceros neto
$13.627.739 (conciliado al peso). Sin el bloque, cada usuario que compare ambos reportes
va a reportar "no me cuadra".

**Diseño**:
- `ProfitabilityByBUResponse` gana `pnl_reconciliation: PnlReconciliation`:
  ```python
  class PnlReconciliation(BaseModel):
      service_income: float = 0          # Ingresos por Servicios
      transformation_net: float = 0      # Ganancia/Pérdida por Transformaciones (neto, como lo define el P&L)
      inventory_adjustment_net: float = 0
      tp_adjustment_net: float = 0       # gain − loss
      pnl_net_profit: float = 0          # Utilidad Neta P&L del mismo período
  ```
- **Fuente: reusar `_calculate_profit`** (una llamada extra dentro de
  `get_profitability_by_business_unit`), NO duplicar queries. Razón: el propósito del
  bloque es atar EXACTO con el tab P&L; derivar de la misma función lo garantiza para
  siempre (cambios futuros al P&L se propagan solos). Costo: ~15 queries extra por
  render — aceptable (el P&L completo corre en <1s en dev con datos reales).
  ⚠️ Al implementar, verificar si `_calculate_profit` expone la merma
  (`waste_value`) como línea separada de `transformation_profit` — si sí, incluirla
  en `transformation_net` (neto) para que la suma cierre.
- **Test de oro anti-drift** (`test_reconciliation_residual_zero`): asserta
  `pnl_net_profit − grand_total_net − Σ(las 4 líneas) == 0` (tolerancia $1). Si mañana
  el P&L gana una línea nueva y nadie actualiza el bloque, este test revienta — es el
  guardrail que convierte la conciliación en promesa contractual (mismo espíritu que
  el test de oro del drill-down, decisión #49).

**UI** (en `PasaManoCard`, debajo del TOTAL GENERAL): sección colapsada por default
"Conciliación con Estado de Resultados" (chevron, patrón de Gastos Directos). Expandida
muestra las 4 líneas (todas, aunque valgan $0 — más claro que aparecer/desaparecer) y la
fila final bold "= Utilidad Neta P&L". Excel: mismas líneas al final del bloque Pasa Mano.

## 4. Frontend

| Archivo | Cambio |
|---|---|
| `types/config.ts` | `double_entry_general_pct` en ExpenseCategory types |
| `types/reports.ts` | `general_expenses` + `general_expenses_detail` en `DoubleEntryProfitability`; nueva interface `PnlReconciliation` + campo en `ProfitabilityByBUResponse` |
| `pages/config/ExpenseCategoriesPage.tsx` (dialog) | Input "% Pasa Mano (gastos generales)" 0–100. **Oculto** si: tiene padre (hint "hereda de {padre}") o `is_direct_expense=true`. Mobile: mismo grid del dialog existente |
| `pages/reports/ProfitabilityBUPage.tsx` (`PasaManoCard`) | Línea "Gastos Generales asignados" expandible (patrón idéntico a Gastos Directos), detalle "Arriendo (20%): $X". Botón/icono ⚙ (permission-gated `treasury.manage_expenses`) que navega a Config → Categorías (acceso rápido acordado con Daniel). Sección colapsada "Conciliación con Estado de Resultados" bajo el TOTAL GENERAL (§3.7) |
| `utils/excelExport.ts` | Línea + detalle de generales y bloque de conciliación en el bloque Pasa Mano |

Responsive: sin layouts nuevos — reutiliza los patrones ya verificados de la card (390px).

## 5. Tests (≥18 nuevos)

**Fixture**: extender `bu_data` (o fixture propio) con categoría "Arriendo" `pct=20`,
subcategoría "Arriendo Bodega Norte" (hereda), gasto general $1M en Arriendo, gasto
general $500K en subcategoría, gasto general $300K sin categoría.

1. `test_pct_slice_to_pasamano` — general $1M al 20% → `double_entry.general_expenses == 200_000`; generales bodega prorratean $800K (valores exactos por UN, mismo patrón blindaje que `test_general_expenses_prorated`).
2. `test_pct_child_inherits_parent` — gasto en subcategoría usa % del padre.
3. `test_pct_zero_default_unchanged` — categoría sin % → números idénticos a hoy (los asserts exactos existentes de `test_proration_unchanged_with_dp_present` siguen verdes sin editar).
4. `test_pct_100_percent` — todo el gasto al Pasa Mano, bodegas $0 de esa categoría.
5. `test_pct_uncategorized_general_ignored` — sin categoría → 0%.
6. `test_pct_direct_and_shared_untouched` — % NO aplica a directos ni compartidos de la misma categoría.
7. `test_pct_net_and_grand_total_parity` — `pasamano_net` resta el slice y `grand_total_net == P&L` con % ≠ 0 (paridad, bloqueante).
8. `test_pct_expenses_report_shows_pasamano_general` — grupo Pasa Mano en Reporte de Gastos con `allocation_type=general`; `test_total_matches_pnl` y `test_total_matches_profitability_bu_sum` siguen verdes.
9. `test_pct_expenses_detail_drilldown` — endpoint detail del grupo Pasa Mano lista el movimiento con `allocated_amount == slice`.
10. `test_pct_real_cost_excludes_slice` — overhead por material NO incluye el slice (valor exacto).
11. `test_pct_validation_range` — pct −1 y 101 → 422.
12. `test_pct_on_subcategory_rejected` — crear/editar hija con pct > 0 → 422.
13. `test_pct_on_direct_category_rejected` — categoría directa con pct > 0 → 422.
14. `test_pct_no_system_bu_fallback` — fixture con `system_code=NULL` → % ignorado, nada se pierde (Σ generales prorrateados == total).
15. RBAC: editar pct sin `treasury.manage_expenses` → 403 (si el CRUD ya lo cubre, referenciar el test existente).
16. `test_pct_cleared_on_reparent` (G1, pedido por QA) — categoría raíz pct=20 se reparenta → `double_entry_general_pct == 0` en DB y el reporte usa el % del nuevo padre.
17. `test_reconciliation_residual_zero` (§3.7, bloqueante) — con datos que pueblan las 4 líneas no-UN: `pnl_net_profit − grand_total_net − Σ(4 líneas) == 0` (tolerancia $1).
18. `test_reconciliation_zero_case` — sin servicios/transformaciones/ajustes: las 4 líneas en 0 y `pnl_net_profit == grand_total_net`.

## 6. Criterios de aceptación

1. Con % configurado, la `PasaManoCard` muestra la línea de generales y su neta baja en exactamente el slice; el TOTAL GENERAL no cambia.
2. Con todos los % en 0 (estado post-deploy), ningún número de ningún reporte cambia.
3. Reporte de Gastos y Rentabilidad por UN cuentan la misma plata (tests de paridad verdes).
4. Costo Real por Material no absorbe el slice.
5. El % se edita solo con `treasury.manage_expenses`; subcategorías y categorías directas no lo aceptan; reparentar zerea el % (G1).
6. El bloque de conciliación cierra al peso: TOTAL GENERAL + las 4 líneas = Utilidad Neta P&L, para cualquier período (test 17 es el guardrail).

## 7. Riesgos y notas

- **R1 — Retroactividad**: % aplica a cualquier período al leer. Comunicado y aceptado por Daniel; decírselo al cliente al entregar (si cambian 10→15%, los meses viejos se re-presentan con 15%).
- **R2 — Base de compras $0**: `_prorate_expense` retorna `{}` cuando no hay compras en el período (comportamiento actual: los generales no se muestran por UN). El slice Pasa Mano NO depende de la base → con % > 0 y compras $0, el slice SÍ aparece en la sección y el resto sigue sin prorratearse (consistente con hoy). Cubierto por el invariante 3 solo sobre lo prorrateable.
- **R3 — Doble conteo con gasto directo a Pasa Mano**: un gasto DIRECTO a la UN sistema nunca pasa por el branch general → imposible contarlo dos veces. Sin riesgo real; test 6 lo cubre.
- **R4 — `_fa`/`ScheduledExpense`/depreciación**: sus movimientos generados entran al pool por `EXPENSE_MOVEMENT_TYPES` con su categoría → el % les aplica igual. Deseado (la depreciación general también puede tocarle a DP si el cliente lo decide vía su categoría).
- **G3 (QA, decisión de producto — v1 lo deja así)**: `general_expenses_detail` agrupa por `category_name` → padre e hija con gasto general aparecen como líneas separadas con el mismo % ("Arriendo (20%): $X" + "Arriendo Bodega Norte (20%): $Y"). Es preciso y transparente; si al cliente le confunde, un rollup bajo el padre efectivo es un cambio menor de presentación (no toca números).
- **Post-implementación**: actualizar el conteo de tests en CLAUDE.md (sección Testing) — QA notó que dice 877 y la suite real ya va en 910 (904 verdes + 6 pre-existentes).
