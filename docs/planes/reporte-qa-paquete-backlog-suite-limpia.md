# Reporte QA — Paquete backlog "suite limpia" (3 ítems, 3 commits)

**Fecha**: 2026-07-15
**Rama**: develop (working tree, sin commitear — esperando QA)
**Alcance**: 3 ítems de backlog independientes que Daniel pidió resolver "uno a uno, en el orden que prefieras". Orden elegido: 405s → bug #54 → split loans_receivable (suite limpia antes de tocar Balance). Se planean **3 commits separados**, uno por ítem (CLAUDE.md/memoria van con el tercero).

**Resultado global**: la suite pasa de "verdes + 6 fallos pre-existentes conocidos" a **1132/1132 en verde** (primera vez en la historia del proyecto; run completo 21:40 min). Cero migraciones. Cero cambios de comportamiento en producción salvo los 3 descritos. *Nota de conteo: el "1130 total" histórico arrastraba un -1 — HEAD colecta 1131 (verificado: el working tree agrega exactamente 1 def de test vs HEAD, el invariante) → 1131 + 1 = 1132.*

---

## Ítem 1 — Los 5×405 de organizations/auth_with_org

### Diagnóstico (causa raíz definitiva)

El router de organizations declaraba `@router.get("/")` mientras el `POST` vivía en `@router.post("")`. `redirect_slashes` corre con su default `True` (verificado: cero configuración al respecto en el repo) — pero Starlette da **precedencia al match parcial sobre el slash-redirect**: `GET /api/v1/organizations` (sin slash) matcheaba el path `""` registrado solo para POST (path coincide, método no) → **405 Method Not Allowed** directo, sin llegar a intentar el redirect. Los 5 tests llamaban sin slash. *(Corrección QA: la v1 de este reporte atribuía el 405 a un `redirect_slashes` deshabilitado — falso, es el default activo + precedencia del match parcial.)*

**Por qué prod nunca lo sufrió**: el frontend llamaba `GET /api/v1/organizations/` CON slash — matcheaba la ruta declarada. El bug solo era visible desde los tests.

**Ventana de deploy cubierta por el mismo mecanismo**: un frontend viejo cacheado que llame CON slash después del fix ya no matchea ningún path → ahí el match parcial no aplica y sí opera el slash-redirect (307 al path sin slash) → cero riesgo durante el rollout.

### Fix (2 archivos, 2 líneas)

- `backend/app/api/v1/endpoints/organizations.py:60`: `@router.get("/")` → `@router.get("")` — consistente con el resto del router (POST/PUT/DELETE ya usaban `""`).
- `frontend/src/services/organizations.ts:6`: la llamada pierde el slash final (alineada a la nueva declaración; con la declaración `""` el slash-final dejaría de matchear).

### Evidencia

- `tests/test_organizations.py` + `tests/test_auth_with_org.py`: **37/37 verdes** (antes 32 + 5×405).
- Riesgo de regresión: el único consumidor del endpoint es `organizations.ts` (verificado por grep) — actualizado en el mismo commit.

---

## Ítem 2 — Bug conocido #54: edit de compra no bloqueaba con stock insuficiente

### Diagnóstico

`purchase.update()` (revert-and-reapply, decisión #8) debía **bloquear** cuando revertir las líneas deja stock negativo — igual que `cancel()` (guard en `purchase.py:652`) y que exige el test `test_update_insufficient_stock_fails`. En su lugar acumulaba `warnings` (semántica de ventas). `git log -S` confirmó que el warning entró en `62e12fb` ("warnings en español") — un commit de i18n, **no una decisión de producto**. Se restaura el bloqueo con confianza.

### Fix (1 archivo)

`backend/app/services/purchase.py` — Step 3a del update: el loop de warnings se reemplaza por `HTTPException 400` espejo del guard de `cancel()` (mismo formato de mensaje: "No se puede editar: stock insuficiente para {code}. Actual: X, Requerido: Y"). La variable `warnings` sigue declarada y retornada (contrato del endpoint intacto — ventas sí la usan).

### Evidencia

- `tests/test_api_purchases.py`: **68/68 verdes** (el archivo completo, primera vez).
- Coherencia: decisión #8 ("compras bloquean, ventas avisan") + guard de cancel + el test existente apuntaban los tres al mismo comportamiento.

---

## Ítem 3 — Split `loans_receivable` en el Balance (diferido por QA en el módulo F, decisión #69)

### Qué hace

Préstamos activos (obligaciones `receivable` — plata que prestamos) salen de la línea "CxC Inversionistas" a línea propia **"Préstamos por Cobrar"**, en Balance General y Balance Detallado, vivo y as-of. QA lo difirió en la revisión de F estimándolo en "~7 enumeradores + test invariante".

### Criterio de clasificación (cero queries nuevas)

Simétrico al lado pasivo (`investors_obligations`): tercero `investor` cuya categoría contenga **"obligaci"** en el nombre + **saldo positivo** → `loans_receivable`. El módulo F **exige** esa categoría por construcción (decisión #69: "1 tercero investor con categoría cuyo nombre contenga 'obligaci'"), así que el marcador ya existe en los datos — no se agregó columna ni join.

Socio investor sin esa categoría → sigue en `investor_receivable` (sin cambio).

### Enumeradores tocados (backend, `services/reports.py` + `schemas/reports.py`)

1. `_classify_third_party` (clasificador vivo) — rama investor positiva con el split.
2. `_classify_tp_by_balance` (clasificador histórico as-of) — mismo split.
3. `ASSET_SECTIONS` ×2 (vivo + as-of).
4. Balance General vivo: bucket + suma en `total_assets` + campo en response.
5. Balance General as-of: ídem (3 pares aplicados con script validando `assert n==2` por ocurrencia).
6. Balance Detallado vivo + as-of: bucket + tupla `("loans_receivable", "Préstamos por Cobrar", ...)`.
7. `SECTION_BEHAVIORS` (sub-agrupación por categoría #38) + mapa del panel #68 (`"loans_receivable": "investor"` — el préstamo sigue apareciendo en Dinero Inactivo bajo el tab Inversionistas).
8. `BalanceSheetAssets.loans_receivable: float = 0.0` (schema, default 0 → compat con consumidores viejos).
9. Docstring de `financial_obligation.py` actualizado (decía "investor_receivable").

### Frontend (7 sitios, detectados por grep de `investor_receivable`)

- `types/reports.ts` — campo en `BalanceSheetAssets`.
- `BalanceSheetPage.tsx` — línea condicional "Préstamos por Cobrar" (mismo patrón `> 0 &&` de las demás).
- `BalanceDetailedPage.tsx` — `ASSET_SECTION_ORDER` (el label viene del backend).
- `excelExport.ts` ×2 — orden de secciones del Detallado + fila del Balance General.
- `pdfExport.ts` ×2 — ídem.
- `InactiveBalancesPage`: **cero cambios necesarios** (usa `third_party_type`, no `section` — verificado).

### Test invariante (el que QA pidió al diferir)

`test_loans_split_invariant_total_assets` (`test_financial_obligations.py`):
- Prestamista "obligaci" con obligación receivable $12M + socio investor con categoría propia "Socios" y saldo $5M.
- Asserts: `loans_receivable == 12M`, `investor_receivable == 5M` (el socio NO se movió), y **`total == suma exacta de los 9 componentes del response`** — si el split perdiera o duplicara el préstamo, revienta.
- Cubre además el path as-of (`as_of_date=hoy` → mismo split) y el panel #68 (el prestamista sigue listado).

También se actualizó `test_balance_detailed_sections_no_regression`: el préstamo ahora se asserta en `assets["loans_receivable"]["items"]` y **NO** en `investor_receivable`.

### Watch-point que salió en desarrollo

El fixture genérico `create_third_party_with_category(..., "investor")` **reutiliza** cualquier categoría investor existente por behavior_type — en el test tomó "Obligaciones Financieras" y el socio caía en `loans_receivable` (17M). Se corrigió creando la categoría "Socios" explícita por nombre. **Anti-patrón a vigilar en tests futuros del split**: no usar el helper genérico para socios si ya existe la categoría de obligaciones en la org de test.

### Nota de alcance

- El **lado pasivo no cambia** (investors_obligations ya existía desde F).
- **Re-presentación**: el split es retroactivo al leer (clasificador, sin datos nuevos) — un balance histórico consultado hoy muestra el préstamo en la línea nueva. El total de activos no cambia ni un peso (invariante).
- Costa hoy: los 8 prestamistas de F son **payable** (pasivo) — `loans_receivable` saldrá $0 hasta que exista un préstamo otorgado. El caso receivable existe en dev/tests.

---

## Evidencia global

| Verificación | Resultado |
|---|---|
| `test_organizations.py` + `test_auth_with_org.py` | 37/37 ✅ |
| `test_api_purchases.py` | 68/68 ✅ |
| `test_financial_obligations.py` (57 = 56 + invariante nuevo) | 57/57 ✅ |
| `test_balance_historico_fixes.py` + `test_inactive_balances.py` | 39/39 ✅ |
| `test_api_reports.py -k balance` | 15/15 ✅ |
| Suite completa | **1132 passed, 0 failed** (21:40 min) ✅ |
| `tsc --noEmit` + `npm run build` | limpios ✅ |

## Checklist de pruebas de usuario sugerido (sobre dev con réplica prod)

1. **Balance General y Detallado**: sin obligaciones receivable, la línea "Préstamos por Cobrar" NO aparece y los totales son idénticos a prod (split invisible cuando $0).
2. Crear una obligación **receivable** de prueba → la línea aparece en General (activos) y como sección en Detallado; CxC Inversionistas no la incluye; total de activos = mismo valor que antes de este build con el mismo dato.
3. Excel y PDF de ambos balances → la línea/sección sale con el mismo valor que pantalla.
4. Balance con `as_of_date` de ayer → préstamo clasificado igual.
5. Panel Dinero Inactivo → el prestamista aparece bajo tab Inversionistas.
6. **Editar una compra registrada** agregando/subiendo cantidades cuando el stock ya se consumió → error claro "No se puede editar: stock insuficiente..." (antes editaba con warning).
7. Pantalla de organizaciones (selector header + página) carga normal (fix 405 no la afecta — mismo response).

## Adenda (post luz-verde) — simetría en el pasivo del Balance General

Durante sus pruebas, Daniel pidió el espejo del split en el pasivo del General: **"Obligaciones Financieras" como línea separada de "Deuda Inversionistas"** (hoy el General fusionaba socios + obligaciones + legacy en `investor_debt`; el Detallado ya los separaba desde #31).

- **Backend**: `investor_debt = partners + legacy`; nuevo `BalanceSheetLiabilities.obligations_payable = bucket investors_obligations` (default 0.0 → compat), sumado en `total_liabilities`. Aplicado en vivo y as-of (bloques textualmente idénticos, editados con replace-all). **Cero cambios en clasificadores** — reusa el bucket que el Detallado ya producía.
- **Frontend**: types + línea condicional en `BalanceSheetPage` + fila condicional Excel + entrada PDF (el loop del PDF ya omite $0).
- **Test**: `test_loans_split_invariant_total_assets` extendido — obligación payable $20M en línea propia, socio con deuda $3M se queda en `investor_debt`, **invariante de total pasivos == suma de componentes**, y as-of con ambos lados.
- **Evidencia**: invariante + no-regresión + as_of_snapshot + 15 balance de `test_api_reports` = 18/18; `test_balance_historico_fixes.py` + `test_financial_obligations.py` completos = 78/78; tsc + build limpios. `test_bs_liabilities` (investor sin categoría de obligaciones) pasa sin cambios — su investor no se mueve del `investor_debt`.
- Va dentro del **commit 3** (mismo feature).

## Commits planeados (tras luz verde QA + OK de Daniel)

1. `fix(api): organizations GET sin slash final — resuelve los 5x405 historicos`
2. `fix(purchases): update bloquea con stock insuficiente (restaura #8, bug #54)`
3. `feat(reports): split loans_receivable en Balance — linea propia Prestamos por Cobrar (#73)` (incluye CLAUDE.md #73 + memoria)
