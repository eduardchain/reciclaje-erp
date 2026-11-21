# Matriz de plantado: aviso de proveedor parecido por contenido

Plan: `plan-sac-similar-por-contenido.md` v1.1, §6. Este archivo se commitea ANTES de plantar y no se reescribe; lo que cambie después va como addendum al final.

- Árbol medido: rama `coder-1/aviso-similar`, `c92c9fd` (merge de develop `693a85f` en `4926ee9` + el caso «Ana Paz» de T1).
- Los plantados del backend se miden con `tests/test_similar_por_contenido.py` contra `reciclaje_test_coder_1`, con `PYTHONDONTWRITEBYTECODE=1` y sin `__pycache__`. El respaldo es por RUTA, y el cierre se comprueba con el sha256 de cada archivo contra `c92c9fd`.
- Los del frontend (P7, P8) se miden con el e2e E1–E4 contra mi front :5181, que sirve el árbol.
- «Exacta» significa que cae ESE conjunto y nada más; una caída de más se reporta.
- T1 es un test parametrizado: `T1[x]` es el caso cuya descripción empieza por x.

## De dónde salen las predicciones

- **Defectos de la función pura** (P2, P3, P5, P5b, P9a, P9b): calculados sin plantar con `prediccion_matriz.py` (log `prediccion_matriz.log`, en `~/sac-evidencia/2026-11-20/coder-1-similar-contenido/`). El script evalúa cada variante sobre los 19 casos de T1 en las dos direcciones y sobre los pares (consulta, candidato) de T2–T11.
- **Defectos del endpoint** (P1, P4, P6): razonados sobre `find_similar` y los fixtures. La org de test no siembra terceros (`conftest.py`, `test_organization`), así que los candidatos son exactamente los que crea cada test.

## Matriz

| P | Archivo | Defecto (reemplazo de texto) | Predicción |
|---|---|---|---|
| P1 | third_party.py | el bucle de clasificación y la lista de similar corren sobre una consulta PROPIA, `select(ThirdParty).where(organization_id == …)`, sin `is_active`, sin `is_system_entity` y sin alcance | **exacta: T8, T11.** T9 verde (el filtro de org sigue) |
| P2 | name_match.py | regla B sin el umbral 2/8 (la condición pasa a `True`) | **exacta: T1[B frontera: 1 palabra de 7], T1[B: 1 palabra corta NO], T1[B: nombre corto «green»], T5** |
| P3 | name_match.py | regla B en una sola dirección: `((a, b),)`, nuevo ⊂ existente | **exacta: T1[B frontera: 1 palabra de 8], T1[B frontera: 2 palabras cortas], T1[B frontera: 2 palabras de 6], T1[B: nuevo más corto], T1[B: nuevo más largo], T1[B: ñ y tildes], T3** |
| P4 | third_party.py | sin `[:SIMILAR_LIMIT]` | **exacta: T6** |
| P5 | name_match.py | sin la regla A (`if False:`) | **exacta: T1[A: sufijo S.A.S]** |
| P5b | name_match.py | sin el camino C (`if False:`) | **exacta: T1[C: solo vacías], T1[C: vacías pegadas]** |
| P6 | third_party.py | los similar salen como exact: `kind = "exact" if name_match_kind(...) else None` | **exacta: T2, T3, T4, T5, T6, T8, T9, T11.** T5, T8, T9 y T11 caen en su control positivo, que espera `similar`; T6 cae porque los 8 salen exact y sin tope |
| P7 | CreateSupplierDialog.tsx | la pantalla trata los similar como exact: `hasExact = (matches ?? []).length > 0` | **E2** (sin «Se parece a:» y sin «Crear igual») |
| P8 | CreateSupplierDialog.tsx | la pantalla ofrece «Crear igual» también con exact: `onlySimilar` sin `&& !hasExact` y `disabled` sin `hasExact` | **E1** (el botón queda habilitado y dice «Crear igual») |
| P9a | name_match.py | `len(small) > MIN_CONTAINED_WORDS` | **exacta: T1[B frontera: 2 palabras de 6 letras]** |
| P9b | name_match.py | `> MIN_CONTAINED_LETTERS` | **exacta: T1[B frontera: 1 palabra de 8 letras]** |

## Correcciones a las predicciones del plan v1.1

El plan con GO no se reescribe; las correcciones van aquí, con su medición.

1. **P9a:** el plan predecía «al menos T1 (caso Ana Maria)». Es falso: «anamaria» tiene 8 letras y el caso pasa también por el umbral de letras, así que con `> 2` palabras no cae nada (`prediccion_frontera.log`: 0 diferencias). Con QA 1 se agregó a T1 el caso «Ana Paz» ⊂ «Ana Paz Lopez» (2 palabras, 6 letras), y ahora P9a tumba exactamente ese (`prediccion_frontera_r2.log`). El error venía de la condición C3, que proponía «Ana Maria» como caso de dos palabras.
2. **P5:** el plan predecía T2. Es falso: «GREEN LOOP - MAQUILA» y «Green Loop Maquila» tienen el mismo conjunto de palabras, así que la regla B los marca sin la A. El único caso que decide SOLO la regla A es T1[A: sufijo S.A.S], porque «sas» es palabra vacía y «aluica», de una palabra y 6 letras, no pasa el umbral de B (`prediccion_matriz.log`). La regla A no tiene un test de endpoint que la necesite; la cubre T1, que llama a la misma función que usa `find_similar`.
3. **P5b (fila nueva):** el plan no plantaba el camino C. Se agrega porque dos casos de T1 los decide solo C.
