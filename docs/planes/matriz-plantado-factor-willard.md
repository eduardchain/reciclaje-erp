# Matriz de plantado: factor de Willard por línea (plan v1.3)

- Se commitea ANTES de plantar y no se reescribe. Si una fila cae en la dirección peligrosa, se agrega una adenda; la matriz no se toca.
- **Árbol medido:** el del delta de la pasada 1 (C1, C2, O1–O4), con base 9144c4f. El sha de cada archivo va en el commit de esta matriz.
- **Por cada P se corre** `tests/test_sac_factor_willard.py` entero (32 tests; T1 inválidos ×7 y T5 ×5 son parametrizados) más `tests/test_archivar_org_sac.py` (66), con `--tb=line`. P14 se mide con el e2e.
- **Cómo se lee cada fila:**
  - «exacta»: cae solo lo predicho.
  - «≥»: el defecto vive en una vía compartida (`_resolve_lead_factor`, `canonical_parameters`, `_enrich`). Puede caer de más; lo que caiga de más se anota con su causa.
  - Dirección peligrosa: un test predicho que NO cae.
- **Respaldo y cierre:** respaldo por ruta (nunca por basename), borrar `__pycache__` del archivo plantado y correr con `PYTHONDONTWRITEBYTECODE=1`. Al final se cierra con el sha de cada archivo tocado contra los del delta de la pasada 1 (`delta1_shas.txt`).
- **:8011 se para mientras se planta** (no tiene `--reload`, pero así nada sirve código plantado).

| P | Defecto plantado | Tiene que tumbar | Tipo |
|---|---|---|---|
| P1 | `_resolve_lead_factor` ignora la opción y devuelve siempre el defecto | T3; T5[sin_alternativas, desconocida, bateria]; T5b; T5c; T6 conserva; T6 solo la fecha; T6 material nuevo; T7 | ≥ |
| P2 | `applied` en el snapshot y el sufijo de la descripción se escriben aunque la fórmula no tenga alternativas | T2 | exacta |
| P3 | D2 sin copiar la lista: `_carry_over_factors` no hace nada | T9 ausente copia; T9 copia que choca 422 | exacta |
| P4 | D5: la edición vuelve al defecto (old/new lines sin `conversion_option`) | T6 conserva; T6 solo la fecha; T7 (sin opción guardada no hay 422) | exacta |
| P5 | D5 sin el 422 de opción desaparecida: con `from_saved` y la opción fuera de la lista vuelve al defecto | T7 | exacta |
| P6 | `canonical_parameters` convierte solo el primer nivel (el `alternatives` anidado queda en Decimal) | T1 válido; y todo test que use el fixture `scr`, que crea su fórmula por la API (500 al serializar el JSONB) | ≥ |
| P7 | `_enrich` sin los tres campos nuevos (trampa #95: quedan en None) | T2 (lead_percentage_applied 0.5); T3; T4; T5b (alternativa); T5c; T6 conserva; T6 solo la fecha; T6 material nuevo | ≥ |
| P8 | Validación sin «distinto del defecto» | T1 inválidos[igual al defecto] | exacta |
| P9 | `confirm` sin `_preflight_lead_factors` y la resolución por línea dentro del loop, después de escribir las líneas anteriores | **Ninguno, y es lo que se predice.** `confirm` hace UN commit al final y cada request abre su propia sesión (`override_get_db`), así que un 422 a mitad de la transacción se descarta entero y T5 sigue viendo «sin efectos». Aquí el preflight protege el orden del mensaje y es la red ante un commit intermedio; la atomicidad no depende de él. Si algo cae, la premisa está mal y se anota. | ninguno |
| P10 | Sin el 422 del material repetido (A1): el mapa se queda con la última | T5[repetido] | exacta |
| P11a | Elegir el defecto por su nombre guarda el nombre en vez de NULL (A2) | T5b | exacta |
| P11b | Una alternativa guarda el texto escrito en vez del canónico (A2) | T5b | exacta |
| P12 | `lead_percentage_applied` leído de la fórmula vigente (su `lead_percentage`, el defecto) en vez del snapshot (A3) | T5c (anulada espera None; el listado espera 0.56); T3 (espera 0.56 con la vigente en 0.59). T2 no cae: su vigente ES la que usó (0.5). (M1 de QA 1) | ≥ |
| P13 | O1: `applied_lead_label` devuelve siempre None (el nombre del factor deja de salir del snapshot) | T3; T4; T6 solo la fecha; T6 material nuevo | exacta |
| P14 | C2: `WillardLiquidateDialog` sin el aviso ámbar de `isError` | e2e del diálogo con `/material-conversion-formulas/current` respondiendo 403 (a 1440 y 390) | exacta |
| P15 | C1: `archivar_org_sac.py` vuelve a «el único valor» (el código de 9144c4f) | TestRevisarFormulas ×2 (los otros 64 de archivar pasan: el fake es neutral) | exacta |
