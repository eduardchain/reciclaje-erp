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

## 3. Gates
*(se llenan después)*
