# Plan — Modelo de recepción simplificado + maestro de materiales con clasificación (SAC)

**Estado:** ✅ **GO CONDICIONADO por QA** (2026-07-16, ver §13). Listo para ejecutar → informe post-código combinado → re-QA → commit atómico `{E2 + este cambio}`. **B1/B2 superan requisitos cerrados de junio** (CC-001/CC-002 en `control-cambios-requerimientos.md`; actualizar `requerimientos-funcionales.md`).
**Origen:** sesión de pruebas manuales E2 (2026-07-16) + consultas a Hugo y Johana.
**Reemplaza:** `plan-sac-quitar-subtipo-willard.md` (la remoción del subtipo queda contenida aquí).
**Sin presión de demo** (Daniel: "hagámoslo bien desde el principio, estamos holgados").

---

## 1. Contexto y decisión

Las pruebas manuales de E2 destaparon que el modelo de configuración/recepción tiene sobre-modelado. Hugo y Johana (fuentes autoritativas) cerraron el modelo correcto:

- **Escurrido/pinza/dross-tipo-N NO son subtipos** — son materiales normales, cada uno con su factor. Se elimina `willard_account_subtype`.
- **Scrap con borne es un material más con su factor** (Hugo) — no necesita la 3ª fórmula `scrap_with_terminal_to_lead` (2 parámetros). El factor se deriva de la unidad.
- **La cuenta postconsumo mezcla materiales `unidad` y `kg`; drosses siempre `kg`** (Hugo) → la unidad NO determina la cuenta; el **tag de clasificación del material es necesario**.
- **Recepción mixta baterías+dross es posible pero rara → se hacen separadas** (Hugo) → ruteo por línea según el tag; sin subtipo de encabezado.

**Objetivo:** simplificar recepción a **2 tipos** y mover la "inteligencia" al **material** (clasificación de mundos + factor a kg con snapshots), aislado del maestro compartido.

---

## 2. Modelo objetivo

### 2.1 Recepción — 2 tipos
| Tipo | Muestra materiales | Efecto |
|---|---|---|
| **Compra regular** | `compra_regular = true` | Deriva `Purchase(registered)` (D7). Sin factor kg. **Selector opcional recolector-comisionista** (service_provider, comisión #30) — absorbe `ruta`/Green Loop |
| **Willard** | `willard_world ≠ none` | Por línea: factor aplicado (por unidad), kg → cuenta según `willard_world` (postconsumo→baterías por sede; drosses→drosses org-wide). Inventario a costo identidad (D2). Cero pesos |

`reventa` desaparece (ya era 422). `postconsumo_baterias`+`drosses`+`ruta` colapsan.

### 2.2 Material (extensión SAC, aislada del maestro compartido)
```
material (tabla compartida, SIN cambios): code, name, default_unit (unidad|kg), ...
material_kg_profile (NUEVA, SAC-only, 1:1, flag-gated):
  - compra_regular: bool
  - willard_world: enum(none | postconsumo | drosses)   # postconsumo XOR drosses
MaterialConversionFormula (EXISTE, simplificada): factor append-only por material
  - drop willard_account_subtype (B1: seco escurrido/pinza son 2 materiales, no 1 con subtipo)
  - ELIMINAR scrap_with_terminal_to_lead (B2: Hugo simplificó a % único; se pierde terminal_weight_kg por decisión de negocio)
  - formula_type derivado de la unidad AHORA sin ambigüedad (unidad→kg/unidad; kg→%); columna se queda (valor derivado al guardar)
  - parameters: {kg_lead_per_unit} o {lead_percentage}
```
- **Factor requerido si** `willard_world ≠ none`; **permitido** en cualquier material (D2: el intersede de E3 lo necesita para aportantes UN1 propios que no son deuda Willard). No atar "tiene factor" solo a Willard.
- **Forma del factor derivada de la unidad** (2 formas, ya sin el 3er tipo).
- **Snapshots**: los da el append-only de `MaterialConversionFormula` (patrón #35). Se surfacan en el maestro de materiales.

### 2.3 Constraint clave
`willard_world` es **single-valued** (none | postconsumo | drosses) — los kg de un material rutean a UNA cuenta. `compra_regular` es ortogonal (una batería = `compra_regular=true, willard_world=postconsumo`; un dross = `willard_world=drosses` sin compra_regular).

---

## 3. Validación de requisitos (regla CLAUDE.md)

| # | Gap / edge / side-effect | Manejo |
|---|---|---|
| 1 | **Maestro `materials` es COMPARTIDO (3 orgs prod, no flag-gated)** | Clasificación + factor en tablas SAC-only (`material_kg_profile` + `MaterialConversionFormula`), 1:1 opcional. `materials` NO se toca → otros 3 clientes cero impacto |
| 2 | Datos dev: "SEC" 2 fórmulas por subtipo | Reseed desde lista real de Johana (§8). Throwaway, no prod |
| 3 | Fórmulas existentes dev (battery/drosses) | `formula_type` derivable de unidad → mapean limpio (batería=unidad, dross=kg). Sin migración de datos |
| 4 | `inbound_type` cambia de semántica (4→2) | Órdenes dev #1/#2 se reseedean. Enum: colapsar a `purchase`+`willard` (o mapear). Dev-only |
| 5 | Cambiar la unidad de un material invalida su factor | Guard: bloquear cambio de unidad si hay factor vigente, o forzar re-captura |
| 6 | Postconsumo en sede sin sub-saldo (ej. JM) | `_resolve_kg_account` ya erra si no hay cuenta baterías para la sede — validación existente sirve |
| 7 | Columnas `willard_account_subtype` en migración E1 (committed, no prod) | Forward-drop (§7), no reescribir historia |
| 8 | Docs: CLAUDE.md #74/#75 + informe E2 mencionan subtype/3 fórmulas | Actualizar |

**Contradicciones con patrones:** ninguna. Preserva append-only (#35), comisión de compra (#30), gating por flag (#74), aislamiento SAC aditivo (E1/E2).
**RBAC:** sin permisos nuevos (`materials.*` para el maestro; recepción reusa permisos de compras).

---

## 4. Decisiones de diseño (tomadas, revisables por Daniel/QA)

1. **Aislamiento por tablas SAC-only** (no columnas en `materials`). Cero contaminación al maestro compartido.
2. **`formula_type` derivado de la unidad**, columna conservada (sin migración de datos, sin elección de usuario).
3. **Página "Fórmulas" se pliega al maestro de materiales** (crear/editar referencia + factor juntos). Historial de factor = vista read-only.
4. **`ruta` → selector recolector-comisionista** (service_provider). **B3 RESUELTO:** la comisión **prorratea al costo** (afecta el costo promedio, mecanismo #30). **Edge pendiente (D-adj):** si Green Loop recolecta postconsumo Willard (identidad, sin Purchase ni costo en pesos), la comisión no tiene dónde prorratear — confirmar con Johana si ese flujo existe; el caso compra-regular queda resuelto.
5. **`willard_world` como enum single-valued** + `compra_regular` bool ortogonal (constraint postconsumo XOR drosses).

---

## 5. Blast radius / cambios

### Backend
- **NUEVO** `models/material_kg_profile.py` + schema + service + endpoints (CRUD SAC-only, flag-gated `require_org_flag("kg_ledger_enabled")`).
- `models/material_conversion_formula.py`: drop columna subtype + índice sin subtype; `formula_type` derivado al guardar.
- `services/material_conversion_formula.py`: quitar validaciones de subtype + anti-mezcla; `get_current` DISTINCT ON `(material_id)`; derivar `formula_type` de la unidad.
- `models/inbound_order.py` + `schemas/inbound_order.py`: drop `willard_account_subtype`; `inbound_type` colapsa a 2 (+ campo recolector opcional en compra).
- `services/inbound_order.py`: `_load_current_formulas` keyed por `material_id`; ruteo de cuenta por `willard_world` del material (no por header subtype); quitar `has_subtyped_line`; snapshot sin subtype; recolector→comisión #30 en la Purchase derivada.
- `endpoints/inbound_orders.py`, `endpoints/material_conversion_formulas.py`: quitar subtype; filtrar materiales por clasificación.
- **Filtro de materiales por mundo**: endpoint(s) que alimentan los selectores de recepción (`compra_regular` / `willard_world`).

### Migración (§7)
Forward-drop de las 2 columnas subtype + **crear `material_kg_profile`** + seed/backfill de perfiles para materiales SAC existentes (dev; prod no aplica).

### Frontend
- **Maestro de materiales** (SAC): al crear/editar, sección flag-gated con clasificación (checkboxes compra_regular / radio willard_world) + factor (una entrada, forma según unidad) + historial de factor.
- **Recepción**: 2 tipos; selector de material filtrado por tipo; quitar selector "Presentación"; selector recolector en compra regular.
- Quitar la página "Fórmulas" standalone (o volverla read-only del historial).
- Quitar tipos/labels de subtype (`WillardSubtype`, `WILLARD_SUBTYPE_LABELS`, etc. — lista en el plan narrow §3, se conserva ese detalle).
- `tsc --noEmit` + `npm run build` limpios.

### Tests
- Borrar tests de subtype (E1 config + inbound). Añadir: clasificación (worlds, constraint XOR), factor derivado de unidad, recepción Willard multi-material ruteando a cuentas correctas por tag, compra regular con recolector→comisión, guard de cambio de unidad, aislamiento (material sin perfil en org no-SAC).

---

## 6. Datos
- **Prod:** cero impacto (no tiene E1/E2 ni estas tablas/columnas).
- **Dev:** reseed de materiales Willard desde lista real de Johana (§8). SEC 2-fórmulas y órdenes #1/#2 son throwaway.
- **Otros 3 orgs:** sin `material_kg_profile`, sin factor, recepción flag-gated → operan idéntico a hoy.

---

## 7. Estrategia de migración
1. **Forward-drop** `willard_account_subtype` (fórmulas + inbound) — están en E1 `b5c8e1a2f3d4` (committed, corrido en dev+QA, NO prod). Nueva migración `down_revision = "f9a2b3c4d5e6"` (head). Recrear índice `ix_mcf_material_current (material_id, created_at DESC)`. No reescribir historia (dev/QA ya corrieron E1). Paridad: `create_all` (modelos) y cadena convergen; verificar con `schema_parity_check.py`.
2. **Crear `material_kg_profile`** en la misma migración nueva.
3. `inbound_type` enum: colapsar a `purchase`+`willard` (dev reseed; ningún dato prod).

---

## 8. Fuera de alcance (anotado)
1. **Reseed de materiales reales** — prerrequisito de RE-PRUEBAS. **Johana:** lista completa de referencias (baterías por ref + kg/unidad; drosses tipo/seco-pinza/escurrido + %) y su clasificación de mundos.
2. **Mecánica de comisión del recolector** (#30 prorrateo vs gasto) — cerrar antes de esa sub-parte.
3. **`goes_directly_to_jm`** — utilidad dudosa (Johana: ¿un dross entra alguna vez por CV?). Otra iteración.
4. **E3** (intersede/horno/crisol, maquila interna, cuadre semanal) — su factor scrap→plomo, si se necesita, es mecanismo aparte.

---

## 9. Riesgos
| Riesgo | Mitigación |
|---|---|
| Tocar (aunque sea vía tabla aparte) el flujo de materiales de 3 orgs prod | Tablas SAC-only 1:1 opcional; `materials` intacto; golden diff-cero de las 3 orgs |
| Colapso de `inbound_type` rompe órdenes dev | Reseed dev; ningún dato prod |
| Índice recreado no coincide con create_all | `schema_parity_check.py` obligatorio |
| Reabre QA de E2 (sin commitear) | El conjunto (E2 + este cambio) va a re-QA antes del commit |

---

## 10. Evidencia esperada (vinculante, para el informe post-código combinado)
- Suite verde (subtype borrado; nuevos de clasificación/ruteo/aislamiento).
- **F1 (GATE, no advisory):** `grep -rn willard_account_subtype backend/ frontend/` = **0** (salvo comentarios de migración) — el footprint real supera lo que enumera §12 D3, así que la exhaustividad se prueba con grep, no a mano.
- **F1 (GATE):** un **test que ejecute el path de snapshot Willard** tras el drop — `tsc`/`build`/suite NO atrapan el `AttributeError` de `inbound_order.py:307` (acceso a atributo Python en runtime).
- `schema_parity_check.py` DIFF fuera de baseline = **0** — **gate BLOQUEANTE, no "riesgo"** (la migración forward-drop solo se ejercita aquí; conftest recrea con `create_all`).
- **Golden 3 orgs DIFF CERO** (BEFORE contra el schema real de prod, sin `inbound_orders`).
- `tsc` + `build` limpios.

---

## 11. Secuenciación
0. **BLOQUEANTE (§12):** reconciliar B1 (SEC ¿un material o dos?) y B2 (scrap-borne ¿2 parámetros o %?) con Hugo/Erwin. El modelo puede cambiar de raíz según las respuestas.
1. Cerrar sub-preguntas §8.1 (lista Johana) y §4.4 (comisión recolector, incl. caso Green Loop sobre postconsumo Willard — §12 D-adj).
2. Re-planear con B1/B2 resueltos → plegar al working tree de E2 → re-QA → commit.
3. Reseed con lista real → repetir pruebas manuales.

---

## 12. Revisión adversarial (2026-07-16, 3 agentes) — hallazgos

### ✅ BLOQUEANTES RESUELTOS (Hugo, 2026-07-16) — ambas decisiones SUPERAN el requisito de junio

> La revisión atrapó dos contradicciones con requisitos cerrados; Hugo las resolvió hacia la simplificación. **Estas decisiones supersedan `requerimientos-funcionales.md` §11.1 (SEC) y Anexo D Tipo 3 (scrap)** — actualizar el doc de requerimientos en su momento.

- **B1 — RESUELTO: SON MATERIALES DISTINTOS.** Hugo (última reunión): seco escurrido y seco pinza se guardan como **2 materiales separados**, cada uno con su factor. Se quita `willard_account_subtype`. **No rompe el costo promedio móvil**: dos materiales distintos = dos pools separados = modelo per-material normal (#64-66), no fragmenta un pool existente; además es reseed dev greenfield. (La cita "#5" del requerimiento es su numeración interna, no CLAUDE.md #5 — QA F-nota; la sustancia se sostiene.) El requisito de junio (L1124/L1132: "mismo material físico") queda **superseded**.

- **B2 — RESUELTO: se SIMPLIFICA.** Hugo: scrap-con-borne es "un material más con un factor de conversión". Se **elimina** el 3er `formula_type` (`scrap_with_terminal_to_lead`) y `terminal_weight_kg` — decisión de negocio de perder el término absoluto del borne a cambio de un % único. "Derivar de la unidad" ahora es **válido** (2 formas: unidad→kg/unidad, kg→%). El Anexo D Tipo 3 queda **superseded**.

- **B3 — RESUELTO: la comisión del recolector afecta el costo promedio** (prorratea al costo, mecanismo #30). Ver §4 punto 4 y el edge D-adj (Green Loop sobre postconsumo).

### 🟠 DISEÑO — reales, secundarios (resolver DESPUÉS de B1/B2)

- **D1** Colapso `inbound_type` 4→2: `KG_SOURCE_BY_TYPE[]`/`INBOUND_TYPE_LABELS[]` son lookups literales → **KeyError**; `_resolve_kg_account` rutea con `== "postconsumo_baterias"`. Reescribir ruteo **por-línea** (`KG_SOURCE_BY_WORLD`), mover `label`/`kg_source` al loop, reseed dev ANTES del código, actualizar `test_avg_cost_model_l.py`.
- **D2** Factor acoplado a `willard_world`: el `scrap_factor` también lo usa el **intersede** (E3) para aportantes UN1 propios que **NO** son deuda Willard (req L1322). Desacoplar "tiene factor kg" de "es Willard".
- **D3 → elevado a F1 (GATE mecánico).** Blast radius de `willard_account_subtype` mayor de lo que se enumeró: ~10 sitios en `inbound_order.py` (validaciones 103-104, construcción 116, `subtyped_mats`/`has_subtyped_line` 191-226, resolución `formulas.get((mat, subtype))` 216-222, **snapshot 307 = AttributeError runtime**, set de campos bloqueados del EDIT D18 478/506) + schema (5 campos + 2 `field_validator` de lower) + columna header (`inbound_order.py` modelo:89) + **4 páginas frontend** (`InboundCreatePage`, `InboundEditPage`, `InboundDetailPage`, `FormulasPage` — NO `InboundOrdersPage`, que usa `inbound_type`/label y cae en D1) + endpoint E1 `material_conversion_formulas.py` (Query param + `get_all`) + `get_current` DISTINCT ON + `test_avg_cost_model_l.py`. **La exhaustividad se prueba con `grep = 0` (§10), no a mano.**
- **D4** `material_kg_profile` DDL: PK GUID; FK org CASCADE; FK material (decidir ondelete); **`UNIQUE(org, material_id)`** (evita `MultipleResultsFound`, cf #58); `willard_world` como **`String`+CHECK, NO pg_enum** (por el parity check); sección del maestro envuelta en `<FlagGate>` con fetch `enabled:flag` (#74, componente `MaterialFormDialog` es compartido).
- **D5** NO filtrar el `GET /materials` compartido (INNER JOIN a profile vaciaría el maestro de las 3 orgs). Filtro client-side (patrón actual) o endpoint SAC-only.
- **D6** Índice `ix_mcf_material_current`: recrear exacto **2 cols** + quitarlo del `Index()` del modelo; `schema_parity_check.py` **bloqueante**. `downgrade()` completo. Reseed **NO** como migración de datos encadenada (55P04 por los `ADD VALUE` de E2). Commit atómico `{E2 + migración nueva}`.
- **D7** "sin migración de datos" → "sin migración de CÓDIGO; datos dev de fórmulas se reseedean". SEC dev queda ambiguo tras el drop (advertencia heredada del narrow, se había perdido).
- **D-adj** Green Loop tiene DOS flujos de ruta: (a) compra chatarra propia → Purchase + comisión #30; (b) recolecta postconsumo Willard → InboundOrder Willard (cero pesos, **sin Purchase donde colgar la comisión #30**). El selector recolector solo cubre (a). Definir dónde vive la comisión $100/kg del caso (b).

### 🟢 NO-BLOQUEANTES verificados (aislamiento)

- Queries incondicionales de **E2** contra `inbound_orders` en paths compartidos (`_calculate_profit`, `_get_inventory_as_of`, `purchase.cancel`): pre-existentes de E2, **probadas inofensivas por el golden** (su BEFORE corrió contra el schema real de prod sin la tabla → diff-cero) + la **cadena de migraciones impide E2-sin-E1**. Hardening opcional (gate por flag) sobre código ya probado — NO se bundlea aquí.
- `inbound_type` es `String(24)`, NO pg_enum → colapso sin `ALTER TYPE`, cero riesgo de migración prod.
- Routers SAC bien gated (`require_org_flag` a nivel router). Aislamiento por tabla SAC-only = decisión correcta.
- **Corrección factual (F2):** el baseline vivo de `schema_parity_check.py` es de **19 entradas** (QA lo adjudicó ejecutando el módulo; el "18" del plan era ~correcto), NO 50. **Code corrige el "50" de CLAUDE.md #74 al commitear.**

---

## 13. Veredicto QA — GO CONDICIONADO (2026-07-16)

Cero bloqueantes (B1/B2/B3 resueltos por Hugo). Todos los claims de código verificados TRUE por QA. **El GO de E2 queda SUSPENDIDO (no revocado):** lo que va a commit es el conjunto fusionado `{E2 − subtype + material_kg_profile}`, no E2 ni este cambio por separado.

**Condiciones vinculantes:**
1. El conjunto fusionado va a **re-QA (informe post-código combinado)** antes del **commit atómico** `{E2 + este cambio}`.
2. **§12 D1-D7 + D-adj son requisitos vinculantes**, no checklist advisory.
3. **F1 (gate):** evidencia con `grep willard_account_subtype = 0` (backend+frontend) **+ test que ejerza el snapshot Willard post-drop** (el `:307` no lo atrapa build ni tsc). Ver §10.
4. **Golden 3 orgs diff-cero + `schema_parity_check.py` como gate BLOQUEANTE** (no "riesgo") en el informe combinado.

**Adjudicaciones QA:** aislamiento sólido; queries incondicionales de E2 = **inertes por construcción** (único write path gateado + 3 orgs con flag NULL → cero filas → lecturas org-scoped escanean 0) → **NO exige gate por flag**. F2 doc-only (Code lo corrige). F3 (Green Loop sobre postconsumo) correctamente diferido a Johana Q-02 — **su respuesta entra al plan antes de implementar esa rama**. §12-como-spec-vinculante es suficiente; NO exige fundir D1/D3-D6 en §5/§7.

**Próximo artefacto que revisa QA:** el informe post-código del conjunto combinado.
