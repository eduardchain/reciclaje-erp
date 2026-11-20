# Informe: Tesorería, «Impuestos y retenciones» en una página

Autor: Eco Coder 1 · 20-nov-2026 · rama `coder-1/impuestos-retenciones` (base develop `31ba117`)
Plan: `plan-sac-impuestos-y-retenciones.md` v1.2 (`f00e57f`, sha256 `15863757…`). Daniel autorizó construir el 20-nov a las ~14:20.
Nivel: **lógica**.

## 1. Entregas

| SHA | Qué | Revisión |
|---|---|---|
| `f556038` | construcción (backend + página + T1–T9) | QA 1, pasada 1: GO con C1–C3 |
| `3a83a20` | T10 (C2) y el checkbox «Mostrar tarifas inactivas» bajado a la sección 2 (observación cosmética) | avisado antes de editar |

## 2. Addendum a la matriz del plantado (commiteado ANTES de plantar)

La matriz del plan (§4) no se reescribe. Esto la complementa.

### 2.1 Cada fila, con su defecto exacto y la predicción

| P | Defecto plantado (exacto) | Debe caer | No debe caer | Puede caer de más |
|---|---|---|---|---|
| P1 | pertenencia por NOMBRE de la entidad: `ThirdParty.name ILIKE '[Impuestos]%'` en vez del JOIN por `system_code` | T3, T10 | **T4** (ver 2.2) | — |
| P1b *(nueva)* | pertenencia por NOMBRE de la categoría: `ThirdPartyCategory.name == 'Impuestos'` en vez de `system_code` | T4 | T3 | — |
| P2 | sin `require_org_flag` en la ruta | T6 | — | — |
| P3 | sin `third_parties.view`: la ruta usa `get_required_org_context` | T7 | — | — |
| P4 | también incluye las `[Retenciones] X` (se suman las candidatas de `retention_entities`) | T5 | — | T1 |
| P5a *(C1)* | quitar SOLO `ThirdParty.organization_id == org` | **nada** (redundancia declarada) | T8 | — |
| P5b *(C1)* | quitar SOLO `ThirdPartyCategory.organization_id == org` | **nada** (redundancia declarada) | T8 | — |
| P5c *(C1)* | quitar los DOS filtros de org | T8 | — | — |
| P6 | `taxBalanceNature` con el signo invertido | E1, E2 | — | E3 |
| P7 | Pagar en la sección 1 sin mirar el signo | E3 | — | — |
| P8 | CON filtro `ThirdParty.is_active == True` | T9 | — | E7 |
| P9 | el Pagar de la sección 2 gobernado por el signo | E6 | — | — |
| P10 *(C2)* | `label = ""` cuando el nombre no parsea, en vez del nombre | T10 | — | — |

- **Para P10 se planta `""` y no `None`.** `label` es `str` en el response_model, así que `None` revienta la validación con un 500. Eso sería una caída del instrumento, no una medición.
- **Dirección peligrosa:** una fila con «Debe caer» que no cae.
- **P5a y P5b son la excepción:** la predicción es que T8 queda en verde, porque cada filtro alcanza solo. Si alguna de las dos cae, la fila no mide lo que creo y se reporta.

### 2.2 Corrección de una predicción del plan, antes de plantar

La matriz del plan (§4) dice que P1 tumba T3 y T4. **No es así para T4.**
- T4 renombra la CATEGORÍA, y P1 mira el nombre de la ENTIDAD, que no cambia.
- Con P1 plantado, T4 sigue listando las tres entidades y pasa.
- El defecto que T4 sí mide es otro: reconocer por el nombre de la categoría. Por eso se agrega P1b.
- De paso, P1 también tumba T10: «Impuesto heredado» no empieza con `[Impuestos]`.

Se escribe aquí y no se edita el plan: la matriz commiteada no se reescribe.

### 2.3 Cómo se mide
- **Backend (P1–P5c, P8, P10):**
  - `pytest tests/test_tax_entities_listing.py` contra mi `TEST_DATABASE_URL`, con `PYTHONDONTWRITEBYTECODE=1` y sin `.pyc`;
  - la salida por fila va a su log;
  - la copia se respalda por ruta y el cierre se hace por sha256.
- **Frontend (P6, P7, P9) y el «de más» de P8 (E7):**
  - el E2E propio contra :8011/:5181, en mi BD `reciclaje_coder_1`;
  - los datos que el E2E crea van escritos en el log.
- **Cierre:**
  - `git status --short` vacío;
  - `git diff --stat 3a83a20` vacío en `backend/app` y `frontend/src`.

### 2.4 Predicciones exactas por fila (escritas ANTES de plantar)

**Instrumentos:**
- **Backend:** `tests/test_tax_entities_listing.py`, con 10 tests T1–T10.
- **Frontend:** `e2e_impuestos.mjs check` (E1–E7) contra :5181, sobre el estado de datos que dejó el `setup` de `e2e_r4_setup.log`:
  - IVA < 0, en «Por pagar»;
  - «[Impuestos] ReteFuente a Favor» > 0, en «A favor»;
  - «[Retenciones] ReteFuente» > 0, en «A favor».
- Los plantados de backend NO se sirven en :8011, que no tiene `--reload`. Por eso el «de más» E7 de P8 no se mide; la matriz lo deja como «puede».

| P | Caen (predicción) | Pasan |
|---|---|---|
| P1 | T3, T10 | los otros 8, **T4 incluido** (2.2) |
| P1b | T4 | los otros 9 |
| P2 | T6 | los otros 9 |
| P3 | T7 | los otros 9 |
| P4 | T5 | los otros 9 (T1 no tiene retenciones practicadas, así que el «de más» no aplica) |
| P5a | ninguno | los 10 |
| P5b | ninguno | los 10 |
| P5c | T8 | los otros 9 |
| P8 | T9 | los otros 9 |
| P10 | T10 | los otros 9 |
| P6 | E1, E2, E3, **E6** | E4, E5, E7 |
| P7 | E3 | E1, E2, E4, E5, E6, E7 |
| P9 | E6 | E1, E2, E3, E4, E5, E7 |

**E6 bajo P6 no estaba en el addendum.** La etiqueta de la sección 2 sale del mismo `taxBalanceNature` (C1: el helper pone la etiqueta), así que con el signo invertido la retención practicada a favor se ve «Por pagar». La predicción va escrita antes de plantar; la matriz no se reescribe.

**Defectos exactos de frontend:**
- **P6:** `const b = -(Number(balance) || 0);` en `taxBalanceNature`.
- **P7:** quitar `taxBalanceNature(t.current_balance).payable &&` del Pagar de la sección 1.
- **P9:** agregar `taxBalanceNature(r.current_balance).payable &&` al Pagar de la sección 2 (`rowActions`).

## 3. Gates

Evidencia en `~/sac-evidencia/2026-11-20/coder-1-impuestos-retenciones/`. El código de producto no cambia desde `3a83a20`; los commits posteriores son solo del informe.

| Gate | Resultado | Archivo |
|---|---|---|
| Dirigidas (grep sobre la superficie + las 3 guardas) | **398 passed** en 0:49:03, igual a la predicción escrita antes (de `--collect-only`). `EXIT=0` dentro del bloque, 0 FAILED/ERROR/Traceback. `ARBOL_INICIO == ARBOL_FIN` (`be558f678b1411ab`), status vacío | `dirigidas.log` |
| Plantado backend (C0 + 11 filas) | **Todas exactas contra §2.4.** C0 10/10; P1 → T3, T10 (T4 pasa, como corrigió §2.2); P1b → T4; P2 → T6; P3 → T7; P4 → T5; P5a y P5b → ninguno; P5c → T8; P8 → T9; P10 → T10. Cierre: status y diff vacíos | `plantado_back.log`, `plantado/` |
| Plantado frontend (C0 + 3 filas, e2e E1–E7) | **Todas exactas contra §2.4.** C0 7/7; P6 → E1, E2, E3, E6; P7 → E3; P9 → E6. Cierre limpio | `plantado_front.log` |
| tsc / lint / ruff, sobre el árbol final | tsc `EXIT=0`; eslint 0 errores y 37 warnings (= techo); ruff limpio en los 4 archivos de backend | `tsc_final.log`, `lint_final.log`, `ruff_final.log` |
| build | `EXIT=0` | `build.log` |
| Capturas SAC 1440/390 (C3 de QA) | Del árbol final, contra un backend relanzado a las 15:50:12 (PID 3579, el que escucha :8011, sin `address already in use`), posterior a todo cambio de `backend/app` | `capturas_final/`, `capturas_final.log` |

**Sin lockf**, por decisión del Coordinador (20-nov ~14:45): la suite con lock es una confirmación post-deploy. La primera corrida quedó esperando el lock; se conserva como `dirigidas_INVALIDA_esperando_lock.log`.

**Lo que no cubren estos gates:**
- **Golden: no aplica, y se midió** (`golden_aplica.log`). Los tres archivos de `app/` solo agregan: 0 líneas borradas. `/third-parties/tax-entities` es una ruta nueva detrás de `kg_ledger_enabled`, que da 403 sin el flag (T6), y `golden_capture.py` no la llama. `/third-parties`, sin cambios, solo se usa para elegir los terceros del statement, no se escribe.
- La suite completa queda diferida al checkpoint.
- **Estado de datos de la BD de dev** `reciclaje_coder_1`: el e2e dejó en SAC la venta #1, la compra #15 y varios pagos a `[Impuestos] IVA por Pagar`, que quedó en −139.958,37. Son datos de prueba de mi base, no de la principal.
