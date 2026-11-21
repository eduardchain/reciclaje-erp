# Plan: aviso de proveedor parecido por contenido (v1.1)

Pedido del Coordinador (20-nov). Sale de la revisión en pantalla de #122.

**v1.1:** GO de QA 1 sobre v1.0 (`f0423ed`) con 4 condiciones y 4 observaciones.
- C1: D1 especifica exactamente la función medida, incluido el camino C.
- C2: §6, gate de paridad función ↔ medición.
- C3: T1 con la frontera del umbral, más P9.
- C4: P1 con su predicción por escenario.
- O1: volcado y clasificación de los pares (§2).
- O2: se declara que los datos vienen de la copia de dev (§2).
- O3: T7 como predicción (§6).
- O4: front viejo en caché (§3, D3).

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

**Datos (O2):** la BD es `reciclaje_coder_1`, una copia de dev: la réplica de producción con datos de PRUEBA encima (Entradas y terceros de las sesiones de prueba). No es la foto de producción. Los conteos sirven para fijar el umbral; no son la tasa que va a ver Johana.

- **Conteo:** «nombres con ≥1 aviso» cuenta TERCEROS. En Costa son 24 terceros y 23 nombres distintos, porque «Douglas Rodriguez» está dos veces y hoy ya es un exact. Los pares son dirigidos (X→Y y Y→X cuentan por separado): 26 y 28, o sea 13 y 14 pares no dirigidos.
- **Por camino** (`medicion_r3.log`):
  - SAC: los 26 pares por B.
  - Costa: 24 por B, 2 por A («Aluica» ~ «SAS Aluica») y 2 exact.
  - El camino C (§3, D1) **no decide ningún par real**: es 0 en las dos orgs.

**Los 27 pares no dirigidos, clasificados (O1).** El volcado completo está en `medicion_r3.log`. Ningún par tiene identificación en los dos lados (todos «sin dato»), así que la precisión **no se puede medir por identificación**. Esta clasificación es una **inferencia nuestra hecha solo con el nombre**; ni Johana ni Daniel la han confirmado.

| Clase | SAC (13) | Costa (14) | Ejemplos |
|---|---|---|---|
| El mismo tercero con una cuenta aparte A PROPÓSITO (sufijo Préstamo, Intereses, ADICIONAL, «negocios puntuales», «x pagar») | **9** | 5 | «JUAN GUILLERMO ALZATE» ~ «… - Préstamo»; «Ecoalloys» ~ «Ecoalloys 3%» |
| Posible duplicado real | 3 | 4 | «EDWIN (GREENLOOP)» ~ «EDWIN GARCIA (GREENLOOP)»; «Luis Perez» ~ «Luis Alberto Perez»; «Aluica» ~ «SAS Aluica» |
| Distintos (comparten un tramo del nombre) | 1 | 4 | «Balance Anterior» ~ «Jeison Velandia - JAC Balance anterior» |
| Exact de hoy | 0 | 1 | «Douglas Rodriguez» ×2 |

**Lectura:**
- En SAC, 9 de 13 avisos caen sobre cuentas que alguien separó a propósito. Si lo parecido **bloqueara**, ese flujo legítimo quedaría trabado; por eso lo parecido avisa y deja crear igual (D3).
- La regla A, la única candidata razonable a bloquear (O1 de §7), decide 2 pares en total (1 no dirigido, «Aluica» ~ «SAS Aluica»), y es un posible duplicado.

El buscador de #123 contesta otra pregunta: «¿qué nombre CONTIENE lo que voy escribiendo?». Va en una sola dirección y está pensado para lo escrito a medias. Aquí el nombre nuevo suele ser **más largo** que el existente («ADALBERTO AVILA (GREENLOOP)» frente a «Adalberto Avila»), y el criterio literal no lo ve. Con nombres cortos, en cambio, se dispara: «green» trae 128 terceros en SAC.

**Decisión:** el selector de #123 (`utils/searchMatch.ts`) no se toca. La detección de duplicados es una regla aparte, y vive **solo en el servidor**.

## 3. Qué cambia

### D1. El criterio vive en el servidor, en una función pura

`app/utils/name_match.py::name_match_kind(new: str, old: str) -> "exact" | "similar" | None` compara solo nombres. Es pura, sin BD, y es la única regla.

`find_similar` la aplica **sobre la misma lista de candidatos de hoy** (§4) y conserva su chequeo de identificación: misma identificación limpia ⇒ `exact`, como hoy.

**La especificación es la función medida, `c_final` de `medir_criterio.py` (C1).** Se escribe con estas definiciones y en este orden:

- **Normalizar:** `norm(s) = normalize_entity_name(s)`, o sea NFKD → ASCII ignorando lo que no cabe → minúsculas → `strip`. La «ñ» queda «n» y las tildes caen.
- **Palabras:** `palabras(s)` = partir `norm(s)` por toda secuencia de caracteres que no sea `[a-z0-9]`, descartando las vacías. Así, «CHATARRERÍA MUÑOZ - SAS» da `[chatarreria, munoz, sas]`.
- **Significativas:** `signif(s)` = `palabras(s)` sin las palabras vacías de una lista fija: `sas s a sa ltda de la el los las y e del cia co inc srl eu`.
- **Orden de decisión:**
  1. **exact:** `norm(new) == norm(old)`. Es la comparación de hoy, sin cambios.
  2. **similar por regla A:** la **CONCATENACIÓN** de las significativas es igual y no está vacía, `"".join(signif(new)) == "".join(signif(old))`. Se compara la concatenación y no la lista, a propósito: así «GreenLoop» = «Green Loop», y «Aluica S.A.S» = «Aluica».
  3. **similar por camino C (entra, decisión de v1.1):** la concatenación CRUDA, sin quitar vacías, es igual y no está vacía, `"".join(palabras(new)) == "".join(palabras(old))`. Es lo que medía `c_tokens_sym`.
     - En los datos reales no decide ningún par (0 en las dos orgs).
     - Atrapa las vacías pegadas, «Dela Rosa» = «de la Rosa», que la regla A no ve: da `delarosa` frente a `rosa`.
     - Entra porque es exactamente lo medido, no agrega ruido medido y cubre ese caso. Quitarlo exigiría re-medir.
  4. **similar por regla B:** se comparan **CONJUNTOS** de significativas DISTINTAS, `a = set(signif(new))`, `b = set(signif(old))`, los dos no vacíos. Hay match si para el lado contenido `chico ⊆ grande` (probando `a ⊆ b` y `b ⊆ a`) se cumple **`len(chico) >= 2`** o **`len("".join(chico)) >= 8`**. Las dos comparaciones son `>=`. Las letras se cuentan sobre la concatenación de las palabras distintas del lado contenido; el orden del conjunto no cambia el largo.
  5. Si no, `None`.
- **Simétrica por construcción:** `kind(a, b) == kind(b, a)`. T1 lo afirma.
- **El umbral 2/8 es el freno a los nombres cortos.** Sin él (variante 1/0 en la medición), Costa sube de 22 a 141 nombres con aviso y «jorge» avisa 6. Con él, «ana», «jorge» y «green» dan 0.
- **Un nombre hecho solo de palabras vacías** («S.A.S») no avisa por A ni por B, porque su conjunto está vacío. Sí avisa por C contra otro que tenga las mismas letras («SAS»): es el mismo texto con otros separadores.

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
- **Front viejo en caché (O4):** después del deploy, un navegador con el front anterior ignora `match` y trata cualquier resultado como hoy, o sea que **bloquea también lo parecido** hasta que se recargue. Es la dirección conservadora (no deja crear un duplicado) y no se mitiga.

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
| T1 | `name_match_kind` puro, tabla de casos, cada uno en las DOS direcciones (simetría). Incluye la **frontera del umbral (C3)**: una sola palabra contenida de **7** letras NO avisa («Ferrosa» ⊂ «Ferrosa Industrial») y de **8** SÍ («Ferrosas» ⊂ «Ferrosas Industrial»); **dos palabras cortas** contenidas SÍ («Ana Maria» ⊂ «Ana Maria Lopez»); una sola palabra corta NO («Ana»); un nombre **solo de palabras vacías** no avisa por B («S.A.S» ~ «S.A.S Aluica») y sí por C («S.A.S» ~ «SAS»); **ñ y tildes** por A («CHATARRERÍA MUÑOZ - SAS» ~ «Chatarreria Munoz») y por B («Muñoz Peña» ⊂ «Carlos Munoz Pena»); concatenación por A («GreenLoop» ~ «Green Loop»); vacías pegadas por C («Dela Rosa» ~ «de la Rosa»). Los 12 casos ya corren contra `c_final` (`medicion_r3.log`, 12/12) | sin BD |
| T2 | «GREEN LOOP - MAQUILA» con «Green Loop Maquila» existente → 1 resultado `match="similar"` | regla A |
| T3 | Nombre nuevo MÁS LARGO: «Edwin Garcia (Greenloop)» encuentra «Edwin (Greenloop)» | regla B, dirección que #123 no ve |
| T4 | Nombre nuevo MÁS CORTO: «Carlos Andres Paez» encuentra «Ventas Carlos Andres Paez» | regla B, la otra dirección |
| **T5** | **CONTROL: un nombre que NO se parece no avisa.** «Ferretería El Tornillo» con «Tornillos y Tuercas» y «El Tornillo Feliz» existentes → `[]`. «Ana» con «Ana María López» → `[]` | comparten una sola palabra; nombre corto |
| T6 | Tope: 7 terceros parecidos y 1 idéntico → 1 exact y 5 similar, con el exact primero | D2 |
| T7 | Exact sigue exact: los casos de `test_t11` de #122 más `match="exact"`. **Que `test_t11` quede verde sin cambios es una PREDICCIÓN (O3)**: `:703` compara la lista EXACTA de nombres. Sus fixtures («Chatarrería Muñoz», «Cliente Lopez», «Inactivo SA» inactivo) no se parecen entre sí con la regla, pero se mide al correr. Si algún fixture pasa a similar, es una **re-semantización que se declara** en el informe, no un ajuste silencioso | regresión |
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
| P1 | similar sobre una consulta PROPIA, filtrada solo por `organization_id`: sin activos, sin entidades de sistema y sin el alcance de `cand_q` | **por escenario (C4):** sobre `87c799f`, sin T11, cae **al menos T8** y **T9 queda verde** (el filtro de org sigue). Después de Ingrid, cae **al menos T8 y T11**, y T9 queda verde |
| P2 | regla B sin el umbral 2/8 | T5 |
| P3 | regla B en una sola dirección (nuevo ⊂ existente, como #123) | T3 |
| P4 | sin tope de similares | T6 |
| P5 | sin la regla A | T2 |
| P6 | los similar salen como `exact` | T2, T3, T4 (al menos); E2 |
| P7 | la pantalla trata los similar como exact (sin «Crear igual») | E2 |
| P8 | la pantalla ofrece «Crear igual» también con exact | E1 |
| P9a | frontera: `len(chico) > 2` en vez de `>= 2` | **al menos T1** (caso «Ana Maria»). T3 y T4 quedan verdes: el lado contenido de T3 pasa por letras (14) y el de T4 tiene 3 palabras. La predicción final de T6 se escribe con sus fixtures, antes de plantar |
| P9b | frontera: `> 8` en vez de `>= 8` letras | **al menos T1** (caso «Ferrosas») |

### Gates

- **Paridad función ↔ medición (C2), antes de las dirigidas.** Los umbrales se justificaron con `c_final` del script, no con la función que se va a construir. El gate corre `medir_r3.py --impl`, un modo que se agrega al construir: carga `app.utils.name_match.name_match_kind` y la compara **PAR POR PAR** contra `c_final`, sobre los mismos terceros activos de SAC y Costa leídos en esa corrida.
  - Exige el MISMO conjunto de pares dirigidos y la misma clase (exact o similar) por par.
  - Exige además los 12 casos de frontera iguales.
  - Sobre la foto de hoy eso es SAC 24 terceros / 26 pares y Costa 24 / 28. Si la copia de dev cambió para entonces, el gate es la **igualdad** entre las dos funciones, y los conteos se reportan.
  - Cualquier diferencia se explica antes de seguir.
- **Dirigidas:** el set sale de grep sobre la superficie (`find_similar|/similar|SimilarThirdParty`): `test_sac_reparto_por_compra.py`, `test_sac_recolector_alcance.py` (tras Ingrid), el archivo nuevo, más las 3 guardas. La predicción va escrita antes.
- **Frontend:** lint, tsc y build.
- **Golden: no aplica, medido** (`golden_no_aplica.log`): `CAPTURES` tiene 14 entradas en 11 rutas, ninguna empieza con `/third-parties`, y no hay ninguna mención de «similar» en `golden_capture.py` ni en `golden_diff.py`. Además, la ruta está detrás de `kg_ledger_enabled`, así que Costa y Meta no la pueden llamar.
- **Parity:** no aplica (cero migraciones).

## 7. Decisiones abiertas (para Daniel)

- **O1. ¿La regla A bloquea o avisa?** Iguales sin palabras vacías ni separadores son casi siempre el mismo tercero («Aluica» = «SAS Aluica»).
  - **Recomiendo que avise (similar):** si bloquea, ante un falso positivo la única salida es deformar el nombre de un proveedor real para que pase («cambie el nombre para distinguirlo»), y eso ensucia el maestro.
  - Lo que bloquea queda como está hoy.
- **O2. El umbral 2/8 y el tope de 5** salen de la medición. Si Johana ve ruido en la primera semana, se ajusta el umbral sin cambiar la forma.
