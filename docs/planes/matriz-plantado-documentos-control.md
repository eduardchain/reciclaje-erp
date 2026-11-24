# Matriz de plantado — documentos de control (P1–P29)

Plan: `plan-sac-documentos-control.md` v1.2, §8. Esta matriz va commiteada ANTES de plantar y no se reescribe después (#105): la columna «Debe caer» es la predicción.

**Dónde se planta:** en una copia del backend sacada con `git archive` del commit de esta matriz, no en el worktree. El árbol que revisa QA no se toca, y el servidor de :8012 tampoco.

**Cómo se mide cada fila:**
- Se aplica UN defecto (reemplazo exacto, con el conteo de ocurrencias afirmado).
- Se corre el archivo entero `tests/test_sac_documentos_control.py` (54 tests), así se ve también lo que cae de más.
- Se restaura el archivo desde el original, y se verifica su sha256 contra el del commit.
- `PYTHONDONTWRITEBYTECODE=1`, para que un `.pyc` viejo no mida el defecto anterior.

**Lectura de la predicción:**
- «= {…}» es exacto.
- «≥ {…}» es «al menos estos»: el defecto vive en una vía compartida y puede tumbar más (regla de #105).
- La dirección peligrosa es un test predicho que NO cae.

Los nombres van sin el prefijo `test_`.

| P | Defecto (archivo · cambio) | Debe caer |
|---|---|---|
| P1 | `services/inbound_order.py` · `display_status_of`: se quita la rama `if order.status == "closed": return "closed"` (cae al fallback «liquidated») | ≥ {t5_paridad_del_filtro_con_el_campo, t3_cerrar_desde_reviewed_y_desde_draft_sin_efectos} |
| P2 | `services/inbound_order.py` · `status_map`: se quita `"closed": ["closed"]` | = {t5_paridad_del_filtro_con_el_campo} |
| P3 | `services/inbound_order.py` · completitud de `liquidate`: se quita `and l.material_id not in control_ids` (vuelve a exigir el reparto de las líneas de control) | ≥ {t6_liquidar_sin_las_lineas_de_control} |
| P4 | `services/inbound_order.py` · `close`: `if valued:` → `if False and valued:` (acepta una mixta) | = {t4_cerrar_una_mixta_da_422_que_nombra_el_material_con_valor} |
| P5 | `services/inbound_order.py` · `close`: antes de `order.status = "closed"` se agrega un `InventoryMovement` de la primera línea (una fila de efectos) | = {t3_cerrar_desde_reviewed_y_desde_draft_sin_efectos} |
| P6 | `services/inbound_order.py` · comisión sugerida: `if qty <= 0 or line.material_id in control:` → `if qty <= 0:` | = {t7_comision_sin_el_control} |
| P7 | `services/inbound_order.py` · `reopen`: siempre a `"draft"` | = {t8_reabrir_vuelve_al_estado_de_antes} |
| P8 | `services/material_kg_profile.py` · `upsert`: después de `profile.lead_product = ...` se agrega `profile.control_only = False` (el upsert borra la marca) | ≥ {t2_el_upsert_no_borra_la_marca} |
| P9 | `services/material_kg_profile.py` · `upsert`: `if profile is not None and profile.control_only:` → `if False:` (la coherencia solo al marcar) | = {t2_upsert_con_mundo_willard_sobre_marcado_da_422} |
| P10 | `services/control_dispatch.py` · `_validate_lines`: `if not_control:` → `if False and not_control:` | = {t12_material_sin_marca_da_422_que_lo_nombra} |
| P11 | `services/control_dispatch.py` · `next_number(..., "control_dispatch_number")` → `"inbound_order_number"` (comparte la secuencia de las Entradas) | ≥ {t12_crear_y_leer_numero_propio} |
| P12 | `services/inbound_order.py` · `_require_scale_weights`: se quita `if line.material_id in control: continue` | ≥ {t10_bascula_no_se_exige_al_control, t3_cerrar_desde_reviewed_y_desde_draft_sin_efectos} |
| P13 | `services/collector_scope.py` · `SCOPED_ENDPOINTS` gana `inbound_orders.close_inbound_order` | = {t11_ingrid_no_cierra_ni_reabre_ni_ve_salidas} |
| P14 | `services/material_kg_profile.py` · `guard_no_control_materials`: se quita el corte por flag | = {t16_sin_flag_el_guard_es_inerte} |
| P15 | `api/v1/endpoints/inbound_orders.py` · el permiso de `close` pasa de `purchases.liquidate` a `purchases.view` | = {t17_permisos_con_control_positivo} |
| P16 | `services/inbound_order.py` · `close`: `if live:` → `if False and live:` (no mira el puente de compras) | = {t18_desliquidada_con_compras_vivas_no_se_cierra} |
| P17 | `schemas/control_dispatch.py` · `RemissionStr`: `strip_whitespace=True` → `False` (pasa `"  "`) | ≥ {t19_remision_obligatoria, t19_el_patch_no_la_deja_vaciar} |
| P18a | `services/control_dispatch.py` · `create`: se quita `warnings.append(dup)` (se calcula y no llega) | ≥ {t20_salida_con_la_remision_de_una_entrada_avisa_por_http, t20_contra_una_anulada_no_avisa_y_un_update_igual_tampoco, t23_paridad_de_la_llave_en_el_conjunto_de_frontera} |
| P18b | `services/inbound_order.py` · `update` de la Entrada: se quita `warnings.append(dup)` (C1 de QA 2) | = {t20_update_de_la_entrada_avisa_por_http} |
| P18c | `services/inbound_order.py` · `create` de la Entrada: se quita `warnings.append(dup)` | = {t20_entrada_con_la_remision_de_una_salida_avisa} |
| P18d | `services/control_dispatch.py` · `update` de la Salida: se quita `warnings.append(dup)` | = {t20_contra_una_anulada_no_avisa_y_un_update_igual_tampoco} |
| P19 | `services/remission_book.py` · `duplicate_remission_warning`: las dos comparaciones `*_key == key_new` pasan a `lower(trim(col)) == remission.strip().lower()` (sin normalizar «0016300» ≠ «16300») | ≥ {t20_salida_con_la_remision_de_una_entrada_avisa_por_http, t20_update_de_la_entrada_avisa_por_http, t23_paridad_de_la_llave_en_el_conjunto_de_frontera} |
| P20 | `services/remission_book.py` · `base` de la vista agrega `t.c.status != "annulled"` (la vista excluye las anuladas) | ≥ {t21_vista_intercalada_con_hueco_anulada_texto_y_repetida} |
| P21 | `services/remission_book.py` · huecos por página: `rows` se corta a `[skip:skip+limit]` antes de intercalar y la página es `items` entera | = {t22_el_hueco_entre_paginas_sale_igual} |
| P22 | `services/remission_book.py` · `duplicate_remission_warning`: se quitan los dos `status != "annulled"` (el aviso cuenta a las anuladas) | ≥ {t20_contra_una_anulada_no_avisa_y_un_update_igual_tampoco} |
| P23a | `services/remission_book.py` · `remission_key`: regex sin anclas, `"^[0-9]+$"` → `"[0-9]+"` («012a» se castea a NUMERIC: DataError) | ≥ {t23_paridad_de_la_llave_en_el_conjunto_de_frontera} |
| P23b | `services/remission_book.py` · `duplicate_remission_warning`: `isdigit()` en Python antes del aviso; si da True, la llave es `'n:' + str(int(r))` («١٢».isdigit() es True e int da 12: se cruza con «12») | ≥ {t23_paridad_de_la_llave_en_el_conjunto_de_frontera} |
| P24 | `services/remission_book.py` · `all_nums` sale de las filas FILTRADAS y no de toda la org | = {t24_hueco_medido_contra_la_org} |
| P25 | `services/remission_book.py` · se quita `not searching and` (con búsqueda se intercalan huecos) | = {t25_busqueda_sin_huecos_y_rango_numerico} |
| P26 (O7) | `services/control_dispatch.py` · `_validate_lines`: `<= 0` de la cantidad cuantizada → `< 0` (0,00004 llega a la columna y el CHECK da 500) | = {o7_cantidad_que_redondea_a_cero_da_422_no_500} |
| P27 (O5) | `api/v1/endpoints/control_dispatches.py` · `_day_end` usa `dt_time.min` (hasta = 00:00 del día) | ≥ {o5_date_to_con_la_fecha_sola_incluye_ese_dia, t24_hueco_medido_contra_la_org} |
| P28 (O1) | `services/remission_book.py` · la vista vuelve a `remission_order(...)` (texto arriba en desc) | = {t21_vista_intercalada_con_hueco_anulada_texto_y_repetida} |
| P29 (2^53) | `services/remission_book.py` + `schemas/control_dispatch.py` · los huecos vuelven a `int` (servicio y schema) | ≥ {t25b_remision_de_20_digitos_exacta, t21_vista_intercalada_con_hueco_anulada_texto_y_repetida, t22_el_hueco_entre_paginas_sale_igual, t24_hueco_medido_contra_la_org, t25_busqueda_sin_huecos_y_rango_numerico} |

**P23 concreta** (punto 2 de los gates de QA 2): la fila del plan decía «isdigit() en Python, o regex sin anclas» y no tenía dónde plantarse, porque la llave vive solo en SQL. Se parte en P23a, el regex sin anclas, y P23b, un `isdigit()` previo al aviso.

**Control de la corrida base:** antes de plantar, el archivo corre sin defectos en la copia: 54 passed.
