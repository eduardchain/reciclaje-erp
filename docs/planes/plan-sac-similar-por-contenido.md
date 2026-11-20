# Plan: aviso de proveedor parecido por contenido (v1.0)

Pedido del Coordinador (20-nov). Sale de la revisión en pantalla de #122.

Al crear un proveedor desde Liquidar Entrada (`CreateSupplierDialog` → `GET /third-parties/similar`), hoy solo se detectan nombres idénticos sin tildes ni mayúsculas, o la misma identificación. Así se puede crear «GREEN LOOP - MAQUILA» aunque ya exista «Green Loop Maquila».

- **Base:** develop `87c799f`. Coder 2 (Ingrid, `coder-2/recolector-alcance` `c0ef770`) **todavía no integró**; el cruce está en §4.
- **Nivel:** lógica (contrato del back y regla nueva).
- **Evidencia:** `~/sac-evidencia/2026-11-20/coder-1-similar-contenido/`.

## 1. Qué pasa hoy

**`third_party.find_similar`** (`services/third_party.py:171`):
- Toma los candidatos: terceros ACTIVOS de la org, sin entidades de sistema.
- Devuelve los que tienen el mismo `normalize_entity_name` (#78: NFKD, sin tildes, minúsculas, `strip`) o la misma identificación sin puntos, guiones ni espacios.
- La tabla no tiene unicidad, así que esto es el único freno a un duplicado.

**El endpoint** (`endpoints/third_parties.py:265`):
- Está detrás de `kg_ledger_enabled` y `third_parties.view`, así que solo lo usa SAC.
- Su único consumidor es el diálogo (grep: solo `services/thirdParties.ts:118`).

**El diálogo** (`CreateSupplierDialog.tsx:99` y `:253`):
- Si `/similar` devuelve algo, **bloquea «Crear proveedor»** y ofrece «Usar este» o «Agregar categoría y usar».
- No ofrece «crear igual» a propósito: hoy un match es el mismo tercero.
- **Por eso el criterio nuevo no puede entrar en la misma bolsa:** un falso positivo bloquearía crear un proveedor real.

## 2. Medición: el criterio de #123 tal cual NO sirve aquí

`medir_criterio.py` corre sobre la BD de dev (`reciclaje_coder_1`): SAC tiene 383 terceros activos y Costa 484. Para cada tercero X, cuenta cuántos OTROS terceros marcaría el criterio si X se creara de nuevo (falsos positivos o duplicados que ya existen). Mide también el recall sobre variantes de X. Logs: `medicion_r1.log` y `medicion_r2.log`.

| Criterio | SAC: nombres con ≥1 aviso | Costa | Máx. avisos por nombre | Recall (guion+mayúsculas, sufijo S.A.S, sin espacios) | «green» (nombre corto) | «GREEN LOOP - MAQUILA» |
|---|---|---|---|---|---|---|
| hoy (exacto) | 0 | 2 | 1 | 5 / 0 / 19 en SAC | 0 | **0** |
| #123 literal (lo escrito como búsqueda dentro del existente) | 14 (144 pares) | 18 (142 pares) | **6+** («Rutas» → 102) | 364 / **0** / 383 | **128** | **0** |
| **propuesta (regla A + regla B 2/8)** | **24 (26 pares)** | **24 (28 pares)** | **3** | **364/364 · 383/383 · 383/383** | **0** | **1** |

El buscador de #123 contesta otra pregunta: «¿qué nombre CONTIENE lo que voy escribiendo?». Va en una sola dirección y está pensado para lo escrito a medias. Aquí el nombre nuevo suele ser **más largo** que el existente («ADALBERTO AVILA (GREENLOOP)» frente a «Adalberto Avila»), y el criterio literal no lo ve. Con nombres cortos, en cambio, se dispara: «green» trae 128 terceros en SAC.

**Decisión:** el selector de #123 (`utils/searchMatch.ts`) no se toca. La detección de duplicados es una regla aparte, y vive **solo en el servidor**.

## 3. Qué cambia

### D1. El criterio vive en el servidor, en una función pura

`app/utils/name_match.py::name_match_kind(new, old) -> "exact" | "similar" | None`. Es pura, sin BD, y es la única regla. `find_similar` la aplica **sobre la misma lista de candidatos de hoy** (§4).

- **exact:** igual que hoy, sin cambiar nada. El mismo `normalize_entity_name`, o la misma identificación limpia.
- **similar, regla A:** iguales después de quitar palabras vacías y separadores. Las palabras vacías son una lista fija: `sas s a sa ltda de la el los las y e del cia co inc srl eu`. Las palabras salen de partir por todo lo que no es `[a-z0-9]`. Atrapa «GREEN LOOP - MAQUILA» = «Green Loop Maquila» y «Aluica S.A.S» = «Aluica».
- **similar, regla B:** las palabras significativas de un nombre están **todas** dentro de las del otro, en cualquier dirección. El lado contenido tiene que tener **al menos 2 palabras o al menos 8 letras**. Atrapa «Edwin Garcia (Greenloop)» ↔ «Edwin (Greenloop)» y «Carlos Andres Paez» ↔ «Ventas Carlos Andres Paez».
- **El umbral 2/8 es el freno a los nombres cortos.** Sin él (variante 1/0 en la medición), Costa sube de 22 a 141 nombres con aviso y «jorge» avisa 6. Con él, «ana», «jorge» y «green» dan 0.

### D2. La respuesta dice qué tipo de coincidencia es, y tiene tope

`SimilarThirdParty` gana `match: "exact" | "similar"`. Es aditivo: el resto de los campos no cambia.

- Orden: primero los exact, después los similar; dentro de cada grupo, por nombre normalizado y por id, como hoy.
- **Tope:** los exact van todos (comportamiento de hoy). Los similar, **5 como máximo**; la medición dio 3 como peor caso.
- Si un tercero es exact y además similar, cuenta como exact y no se duplica.

### D3. La pantalla: lo idéntico bloquea, lo parecido avisa

- **Hay algún exact:** igual que hoy. Ámbar «Ya existe», «Crear proveedor» deshabilitado y sin «crear igual».
- **Solo similar:**
  - Aviso con «Se parece a:» y las mismas acciones por fila («Usar este» o «Agregar categoría y usar»).
  - El botón principal pasa a **«Crear igual»** y está habilitado.
  - Crear igual no vuelve a preguntar a `/similar`: el usuario ya vio los parecidos.
  - Editar el nombre o la identificación limpia el aviso, igual que hoy.
- Mobile-first: las filas ya son `flex-col sm:flex-row` y los botones `w-full sm:w-auto`. Se capturan 1440 y 390.

### D4. La identificación queda como hoy

Una identificación igual sigue siendo exact y bloquea. No se agrega «identificación parecida».

## 4. Cruce con Coder 2 (alcance del recolector en `/similar`)

Medido en `c0ef770` (`git diff 87c799f c0ef770 -- services/third_party.py endpoints/third_parties.py`):

- La fila 12 de su plan dice: «se fuerza `alc` (no revela nombres de proveedores de SAC)».
- El endpoint pasa `collector_id=scope_of(org_context)`.
- `find_similar` agrega `ThirdParty.collector_id == collector_id` **a la consulta de candidatos** (`cand_q`), antes de comparar.

**Cómo se combinan:** el criterio nuevo **solo reemplaza la comprensión `matches = [...]`**, que recorre esos candidatos ya filtrados. No abre una consulta propia ni un segundo recorrido de la tabla. Así, el alcance se respeta por construcción: un tercero fuera del alcance de Ingrid no llega a compararse.

- Lo sostiene **T11**, con su control positivo: el mismo parecido, dentro del alcance, sí aparece.
- El plantado **P1** (similar sobre una consulta sin el filtro) lo tumba.

Consecuencia declarada, y es de su diseño, no de este: con alcance, Ingrid puede crear un duplicado de un proveedor de SAC fuera de su alcance, porque ni el exact ni el similar se lo muestran. Es lo que pide M1 de su plan («no revelar lo ajeno»).

**Orden:**
- **Construir DESPUÉS de que Ingrid integre.** Los dos tocan `find_similar` en bloques adyacentes (la firma, `cand_q` y la comprensión), así que construir sobre `87c799f` deja un conflicto seguro y un merge a mano sobre el filtro de alcance, que es justo lo que no se puede romper.
- Si Ingrid no entra antes, construyo sobre `87c799f` sin T11 y la integración la hace el que entre segundo, con T11 obligatorio en ese merge.

## 5. Lo que NO cambia

- `utils/searchMatch.ts` y `EntitySelect` (#123).
- El flag, el permiso y la ruta estática de `/similar`.
- El listado de terceros.
- El bloqueo por exact (nombre o identificación).
- `pickExisting`, incluido el «Agregar categoría» que Ingrid oculta con alcance.

## 6. Verificación

### Tests nuevos (`tests/test_similar_por_contenido.py`)

| T | Qué | Dato |
|---|---|---|
| T1 | `name_match_kind` puro, tabla de casos: regla A, regla B en las dos direcciones, umbral 2/8, palabras vacías, tildes y mayúsculas | sin BD |
| T2 | «GREEN LOOP - MAQUILA» con «Green Loop Maquila» existente → 1 resultado `match="similar"` | regla A |
| T3 | Nombre nuevo MÁS LARGO: «Edwin Garcia (Greenloop)» encuentra «Edwin (Greenloop)» | regla B, dirección que #123 no ve |
| T4 | Nombre nuevo MÁS CORTO: «Carlos Andres Paez» encuentra «Ventas Carlos Andres Paez» | regla B, la otra dirección |
| **T5** | **CONTROL: un nombre que NO se parece no avisa.** «Ferretería El Tornillo» con «Tornillos y Tuercas» y «El Tornillo Feliz» existentes → `[]`. «Ana» con «Ana María López» → `[]` | comparten una sola palabra; nombre corto |
| T6 | Tope: 7 terceros parecidos y 1 idéntico → 1 exact y 5 similar, con el exact primero | D2 |
| T7 | Exact sigue exact: los casos de `test_t11` de #122, que quedan verdes sin cambios, más `match="exact"` | regresión |
| T8 | Inactivos y entidades de sistema no aparecen como similar | mismos candidatos de hoy |
| T9 | Otra org no aparece como similar | aislamiento |
| T10 | Un tercero exact y similar a la vez sale UNA vez, como exact | D2 |
| T11 | *(tras Ingrid)* Con alcance, un parecido fuera de su recolector no aparece. **Control positivo:** el mismo parecido marcado con su recolector sí aparece | §4 |

### Pantalla (script e2e contra mi front, 1440 y 390)

| E | Qué |
|---|---|
| E1 | Exact: «Ya existe», «Crear proveedor» deshabilitado y sin «Crear igual» |
| E2 | Solo similar: «Se parece a:», «Crear igual» habilitado; al pulsarlo crea UN tercero (lo cuenta la API antes y después) |
| E3 | Editar el nombre después del aviso lo limpia y el botón vuelve a «Crear proveedor» |
| E4 | 390 px: sin scroll horizontal y botones de ancho completo |

### Plantado (matriz commiteada antes de plantar)

| P | Defecto | Cae |
|---|---|---|
| P1 | similar sobre una consulta propia sin el filtro de candidatos | T11 (y T8) |
| P2 | regla B sin el umbral 2/8 | T5 |
| P3 | regla B en una sola dirección (nuevo ⊂ existente, como #123) | T3 |
| P4 | sin tope de similares | T6 |
| P5 | sin la regla A | T2 |
| P6 | los similar salen como `exact` | T2, T3, T4 (al menos); E2 |
| P7 | la pantalla trata los similar como exact (sin «Crear igual») | E2 |
| P8 | la pantalla ofrece «Crear igual» también con exact | E1 |

### Gates

- **Dirigidas:** el set sale de grep sobre la superficie (`find_similar|/similar|SimilarThirdParty`): `test_sac_reparto_por_compra.py`, `test_sac_recolector_alcance.py` (tras Ingrid), el archivo nuevo, más las 3 guardas. La predicción va escrita antes.
- **Frontend:** lint, tsc y build.
- **Golden: no aplica, medido** (`golden_no_aplica.log`): `CAPTURES` tiene 14 entradas en 11 rutas, ninguna empieza con `/third-parties`, y no hay ninguna mención de «similar» en `golden_capture.py` ni en `golden_diff.py`. Además, la ruta está detrás de `kg_ledger_enabled`, así que Costa y Meta no la pueden llamar.
- **Parity:** no aplica (cero migraciones).

## 7. Decisiones abiertas (para Daniel)

- **O1. ¿La regla A bloquea o avisa?** Iguales sin palabras vacías ni separadores son casi siempre el mismo tercero («Aluica» = «SAS Aluica»).
  - **Recomiendo que avise (similar):** si bloquea, ante un falso positivo la única salida es deformar el nombre de un proveedor real para que pase («cambie el nombre para distinguirlo»), y eso ensucia el maestro.
  - Lo que bloquea queda como está hoy.
- **O2. El umbral 2/8 y el tope de 5** salen de la medición. Si Johana ve ruido en la primera semana, se ajusta el umbral sin cambiar la forma.
