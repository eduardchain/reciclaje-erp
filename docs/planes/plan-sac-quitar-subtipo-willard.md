# Plan — Quitar el subtipo `willard_account_subtype` (escurrido/pinza) del modelo SAC

> **⛔ SUPERSEDED (2026-07-16) por [plan-sac-recepcion-y-materiales.md](plan-sac-recepcion-y-materiales.md).** Tras consultar a Hugo/Johana, la remoción del subtipo quedó contenida en un cambio más amplio (recepción a 2 tipos + maestro de materiales con clasificación). Este doc se conserva solo como referencia del blast radius del subtipo (§3), reutilizado por el plan nuevo.

**Estado:** propuesto, pendiente QA-GO.
**Autor:** sesión pruebas manuales E2, 2026-07-16.
**Alcance temporal:** ejecutar ANTES de la demo con el cliente, plegado al trabajo E2 (aún sin commitear).

---

## 1. Contexto y decisión

Durante las pruebas manuales de E2, Daniel consultó a **Hugo y Johana** (fuentes autoritativas del modelo Willard). Corrección de concepto de raíz:

> Escurrido y pinza (y los "drosses tipo 1/2/3") **NO son un subtipo/presentación** de un material. Son **materiales/referencias distintos**, cada uno con su propia tasa de conversión, como cualquier otro material. Willard tiene una referencia "seco pinza"; "escurrido" es otra referencia.

E2 (y E1) modelaron esto como una dimensión extra `willard_account_subtype` que discrimina DOS fórmulas vigentes sobre el MISMO material (caso "SEC"). Eso es sobre-modelado: cada referencia debe ser un material normal con **una** fórmula vigente.

**Objetivo:** eliminar por completo `willard_account_subtype` (fórmulas, recepción, resolución, UI). Cada material tiene una fórmula vigente (append-only, patrón #35). El material dev "SEC (escurrido/pinza)" con 2 fórmulas se reemplaza por 2 materiales (dato, no código).

**Beneficio colateral:** el problema "SEC llega mixto en una entrada" (que se había planteado como "subtipo por línea") **se disuelve solo**: un camión con varias referencias = una recepción con varias líneas de material, ya soportado. No se necesita subtipo por línea — se necesita NO tener subtipo.

---

## 2. Validación de requisitos (regla CLAUDE.md)

Revisado contra el código actual. Gaps / edge cases / side-effects encontrados (todos manejados en el plan, ninguno bloqueante):

1. **Dato dev "SEC" queda ambiguo.** Al quitar el subtipo, SEC queda con 2 fórmulas `subtype=NULL` → `DISTINCT ON (material_id)` resuelve a la más reciente (pinza 0.65) y descarta la otra en silencio. **No es problema de prod** (dato de prueba, ninguno en prod). Resolución: reseed de materiales Willard desde la lista real de Johana (§8). El código NO migra este dato.
2. **Orden inbound dev #2 y su snapshot** tienen `subtype=escurrido`. Al dropear la columna de `inbound_orders`, se pierde el campo (inocuo). El JSONB `conversion_formula_snapshot` conserva la clave histórica (inocuo, sin backfill). El `delta_kg=600` ya asentado no cambia.
3. **Migración: ambas columnas están en E1** (`b5c8e1a2f3d4`, committed a develop, corrido en dev+QA, **NO deployado a prod**). Estrategia forward-drop (§5) — no reescribir historia.
4. **Índice `ix_mcf_material_current`** incluye la columna → se recrea sin ella (§5). La recreación debe coincidir EXACTO con lo que produce `create_all` (verificar con `schema_parity_check.py`).
5. **`goes_directly_to_jm`** (Daniel cuestionó su utilidad, punto 1 de la sesión) queda **FUERA de alcance** — es otra decisión. Se anota como pregunta a Johana (§8), no se toca aquí.
6. **Reseed de materiales reales** es prerrequisito de RE-PRUEBAS, no del cambio de código (el código es material-agnóstico).
7. **Docs a actualizar:** decisión CLAUDE.md #74 y #75 mencionan el subtype; `informe-code-e2-kgledger-inbound.md` también. Corregir (§7.5).
8. **RBAC:** sin cambios (mismos permisos `formulas.manage`, inbound vía permisos de compras). Sin permisos nuevos.

**Contradicciones con patrones existentes:** ninguna. Es una simplificación alineada con "los materiales son materiales"; preserva el append-only vigente (#35) por material en vez de por (material, subtype).

---

## 3. Blast radius (verificado por grep + lectura, no de memoria)

### Backend
| Archivo | Qué tiene | Acción |
|---|---|---|
| `models/material_conversion_formula.py` | columna (52-57), índice `ix_mcf_material_current` con subtype (74-79), `__repr__` (88), docstrings | quitar columna, recrear índice `(material_id, created_at DESC)`, limpiar repr/docstring |
| `models/inbound_order.py` | columna (89-92) | quitar |
| `schemas/material_conversion_formula.py` | `_lowercase_str`+`WillardSubtype` (26-31), `SUBTYPE_ALLOWED_FORMULA_TYPES` (43), campo Create (85), campo Response (122) | quitar todo |
| `schemas/inbound_order.py` | Create campo (46)+validator (58-61); Update campo (73)+validator (84-87); Response (129) | quitar todo |
| `services/material_conversion_formula.py` | valid. subtype-solo-drosses/scrap (62-70), valid. anti-mezcla NULL/no-NULL (72-94), pasar al modelo (101), filtro `get_all` (116,124-128), `get_current` DISTINCT ON (144-157) | quitar validaciones y filtro; `get_current` → DISTINCT ON `(material_id)` |
| `services/inbound_order.py` | valid. subtype-solo-willard (103-104), set en order (116), `has_subtyped_line`+valid. (191,196-205), pick subtype por línea (217-221), snapshot (307), edit D18 (478,506,542-543), `_load_current_formulas` (694-714) | quitar subtype; `_load_current_formulas` → keyed por `material_id`; snapshot sin la clave; quitar de edit D18 |
| `endpoints/inbound_orders.py` | enrich (87) | quitar |
| `endpoints/material_conversion_formulas.py` | query param subtype en `get_all` (27,37) | quitar |
| `alembic/versions/b5c8e1a2f3d4_*.py` | crea las 2 columnas + índice | **NO tocar** (forward-drop, §5) |

### Frontend
| Archivo | Qué tiene | Acción |
|---|---|---|
| `types/sac-config.ts` | `WillardSubtype` (72), campos Response (89)+Create (100) | quitar |
| `types/inbound-order.ts` | `WillardAccountSubtype` (6), `WILLARD_SUBTYPE_LABELS` (15-17), campos (40,55,90) | quitar |
| `pages/config/FormulasPage.tsx` | state (57), payload (111), columnas tabla "Presentación" (156,174-176,405,414), selector diálogo (305-311), import (19) | quitar selector + columnas |
| `pages/inbound/InboundCreatePage.tsx` | state (127), selectedSubtype (145), payload (192), selector (310-316), `estimateKgLead` rama subtype (76,80-85), imports (31,33) | quitar; `estimateKgLead` → material→fórmula directo |
| `pages/inbound/InboundEditPage.tsx` | state (78), init (89), diff D18 (137-145), selector (281-287), imports (32,35) | quitar |
| `pages/inbound/InboundDetailPage.tsx` | InfoRow "Presentación" (134-135), import (31) | quitar |

### Tests
- `tests/test_sac_e1_config.py`: **borrar** los tests de SEC-2-fórmulas-por-subtype, coherencia `SUBTYPE_ALLOWED`, anti-mezcla NULL/no-NULL. **Mantener/añadir:** material con una fórmula vigente (append-only reemplaza); vigente = último por `created_at,id` por material.
- `tests/test_inbound_orders.py`: **borrar** tests de subtype (has_subtyped_line, header obligatorio/prohibido). **Añadir:** recepción drosses multi-línea con materiales DISTINTOS, cada uno resuelve su fórmula (reemplaza el escenario "mixto", ahora es solo multi-material).

---

## 4. Cambio semántico central

- **Antes:** vigente = último por `(material_id, willard_account_subtype)`. Un material podía tener 2 vigentes (escurrido/pinza).
- **Después:** vigente = último por `(material_id)`. Un material tiene 1 vigente. Cada presentación/referencia es su propio material.
- **Recepción:** ya no hay selector "Presentación". `_load_current_formulas` retorna `{material_id: formula}`. El snapshot ya no lleva `willard_account_subtype`. Multi-referencia en un camión = multi-línea.

---

## 5. Estrategia de migración — forward-drop (recomendada)

Ambas columnas + el índice viven en E1 `b5c8e1a2f3d4` (committed a develop, corrido en dev+QA, NO en prod).

**Nueva migración** `down_revision = "f9a2b3c4d5e6"` (head actual), que:
1. `DROP INDEX ix_mcf_material_current`; recrea `CREATE INDEX ix_mcf_material_current ON material_conversion_formulas (material_id, created_at DESC)`.
2. `DROP COLUMN material_conversion_formulas.willard_account_subtype`.
3. `DROP COLUMN inbound_orders.willard_account_subtype`.
   `downgrade()` reañade columnas (nullable) + índice viejo.

**Por qué forward-drop y NO amend de E1:**
- Amend de `b5c8e1a2f3d4` reescribe historia committeada y corrida en dev+QA → esas BDs quedan con columnas que la migración enmendada no explica (drift; exige reset por entorno).
- Forward-drop es seguro: en dev/QA (corrieron E1) dropea lo existente; en prod (deploy fresco) corre E1(add)→…→cleanup(drop). Ligeramente redundante en prod, funcionalmente correcto, **cero reescritura de historia**.
- **Paridad:** `create_all` (modelos sin columna) y cadena-migración (E1 add + cleanup drop) convergen al mismo esquema final. La BD de test (5433, conftest recrea con `create_all`) nace sin columna. Verificar con `schema_parity_check.py` que el índice recreado coincide EXACTO.

**Columna NO es pg_enum** (es `String(16)` + `Literal` Pydantic) → no hay enum que dropear.

---

## 6. Datos

- **Prod:** cero impacto (no tiene E1/E2 ni estas columnas).
- **Dev (5434):** el cleanup dropea las columnas. Queda "SEC" con 2 fórmulas NULL (vigente ambiguo). Se limpia con el **reseed** de materiales reales (§8) — throwaway.
- **Snapshots kg dev:** conservan la clave histórica en JSONB (inocuo). Sin backfill.

---

## 7. Cambios detallados

### 7.1 Modelo fórmulas
Quitar columna; índice → `("material_id", text("created_at DESC"))`; limpiar `__repr__` y docstring.

### 7.2 Servicio fórmulas
Borrar las 2 validaciones (subtype-solo-drosses/scrap, anti-mezcla). `create` sin el campo. `get_all` sin el filtro `willard_account_subtype`. `get_current` → `DISTINCT ON (material_id) ORDER BY material_id, created_at DESC, id DESC`.

### 7.3 Servicio inbound
`_load_current_formulas` → `DISTINCT ON (material_id)`, retorna `{material_id: formula}` (sin set `subtyped`). Borrar el bloque `has_subtyped_line` (196-205) y el pick por línea (217-221) → la fórmula es `formulas[material_id]`. Snapshot sin `willard_account_subtype`. Quitar de los sets de edit D18 (478, 506, 542-543) y de la validación willard-only (103-104, 116).

### 7.4 Schemas + endpoints
Quitar campo/validators de Create/Update/Response inbound; quitar `WillardSubtype`, `SUBTYPE_ALLOWED_FORMULA_TYPES`, `_lowercase_str` y campos de fórmulas; quitar query param del endpoint `get_all`; quitar del enrich inbound.

### 7.5 Frontend + docs
Quitar tipos, selectores, columnas y helpers listados en §3. `tsc --noEmit` + `npm run build` limpios. Actualizar CLAUDE.md #74/#75 (texto del subtype) y `informe-code-e2-kgledger-inbound.md`.

---

## 8. Fuera de alcance (anotado, no se toca aquí)

1. **Reseed de materiales Willard reales** — prerrequisito de RE-PRUEBAS. **Pregunta a Johana:** lista completa de referencias de dross (¿tipo 1/2/3? ¿seco pinza? ¿escurrido?) + su tasa de conversión, y las 7 referencias de batería + kg/unidad. Sin esa lista no se siembra bien.
2. **`goes_directly_to_jm`** — Daniel cuestionó su utilidad. **Pregunta a Johana:** ¿un dross alguna vez entra por CV en vez de directo a JM? Si nunca, es peso muerto (candidato a quitar en otra iteración).
3. **Generalización de `ruta`/Green Loop** — memoria [[sac-ruta-generalizar-recolector-comision]], productización aparte.

---

## 9. Riesgos

| Riesgo | Mitigación |
|---|---|
| Índice recreado no coincide con `create_all` → parity flag | `schema_parity_check.py` obligatorio post-cambio |
| Referencia colgante al subtype (backend/front) rompe build | grep de §3 como checklist; `pytest` + `tsc` + `build` |
| Re-abre QA de E2 (ya tenía GO) | el delta es una REMOCIÓN (simplificación); re-QA focalizado: remoción completa, vigente-por-material, multi-material drosses, suite/parity/golden |

---

## 10. Evidencia esperada (para el informe)

- Suite completa verde (los tests de subtype borrados; nuevos de vigente-por-material y multi-material drosses). Conteo se ajusta (baja por los borrados).
- `schema_parity_check.py`: DIFF fuera del baseline = 0 (incluye el índice recreado; columnas fuera del esquema).
- Golden ampliado: DIFF CERO en las 3 orgs reales (prod no tiene nada de esto → invariante por construcción).
- `tsc --noEmit` + `npm run build` limpios.

---

## 11. Secuenciación

E2 está **sin commitear** y tenía QA-GO (con subtype). Se **pliega la remoción al working tree de E2** antes del primer commit — develop nunca recibe el concepto equivocado. La migración cleanup + E2 se commitean juntos tras **re-QA** del conjunto. Nada committeado se reescribe. Después: reseed con lista de Johana → repetir pruebas manuales (Test #1 baterías, #2 drosses multi-referencia, #3 compra, #4 ruta, retenciones).
