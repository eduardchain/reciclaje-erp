# Informe de construcción — SAC: Ingrid / Green Loop, usuario con alcance de recolector

- **Plan:** `docs/planes/plan-sac-recolector-alcance.md` v1.12.
- **Rama:** `coder-2/recolector-alcance`, nivel lógica. Base de integración: develop `87c799f`.
- **Pareja de QA:** Eco QA 2.
- **Evidencia del autor:** `~/sac-evidencia/2026-11-20/coder-2-recolector-alcance/` (en adelante `EV/`).
- **Revisiones de QA 2:** `~/sac-evidencia/2026-11-20/qa-2-ingrid/` (en adelante `QA/`).
- **Estado al escribir este informe:** las dirigidas de QA sobre `c0ef770` están en curso. Este informe no cita su resultado ni el OK final de la pasada 2.

## 1. Qué se construyó

Es lo que pide el §0 del plan, sin cambios de alcance:

- **Marca por tercero.** Columna `third_parties.collector_id`: «este tercero es de Green Loop».
- **Alcance por usuario.** Tabla `user_collector_scopes`: «este usuario solo opera Green Loop».
  - Las tres FKs llevan `ondelete="RESTRICT"` (N1). Con CASCADE, borrar al recolector borraría la fila de alcance, y el usuario pasaría a ver TODO (fail-open).
- **Lista blanca deny-by-default.** `SCOPED_ENDPOINTS` tiene 32 rutas (`app/services/collector_scope.py`) y se impone en `get_required_org_context`.
  - Para un usuario con alcance, cualquier otra ruta da 403 «Fuera de tu alcance», aunque su rol tenga el permiso.
  - Lo mismo vale para las rutas de miembros de la org, que no pasan por ese contexto (§5.0).
  - Cada ruta de la lista filtra o rechaza por la marca y recorta los campos de SAC (stock, costo y precios de material, §5.7).
- **Reglas de Entrada para quien tiene alcance:**
  - **9e/9f:** Entradas que ya existen y re-liquidaciones (`last_liquidation_batch`).
  - **9g:** no se liquida con descuadre (decisión de Daniel, O1).
  - **D-E2(b):** aviso al liquidar si hay proveedores sin la marca de este recolector.
- **Balance Detallado:** los terceros marcados se agrupan en «Recolector: X» (§7). El Balance General no cambia.
- **Frontend.** Solo cambia cuando el usuario tiene alcance; para los demás queda igual byte a byte:
  - el menú muestra solo `SCOPE_PATHS` (5 rutas);
  - selectores de recolector en Usuarios y Terceros;
  - pantallas de Entradas sin «Sin proveedor» ni el bloque de báscula.
- **Script de la marca inicial:** `scripts/marcar_recolector.py` (§9). Dry-run por defecto, `--apply`, `--esperado N` y exit 3 ante cualquier sorpresa sin escribir nada.
- **Migración:** `e7f9a1b3c5d8_recolector_alcance.py`. Es aditiva: columna NULL y tabla vacía en las 7 orgs.

**Commits de la rama, en orden, desde la construcción.** Antes hay 10 commits del plan, de `409e857` (v1.0) a `71c3fde` (v1.9).

| Commit | Qué es |
|---|---|
| `9d8cc33` | construcción, plan v1.9 |
| `69a4378` | merge de develop 31ba117 |
| `e6ac14e` | plan v1.10 |
| `ab645b4` | 9g |
| `41940cf` | plan v1.11 |
| `c00a133` | tests P24/P33, plan v1.12 |
| `5216969` | merge de develop 1aacc2f (MoneyInput + Ocultar Listas) |
| `598558d` | merge de develop 87c799f (Impuestos y retenciones, #126–#128) |
| `c0ef770` | test: la ruta nueva `GET /third-parties/tax-entities` da 403 a Ingrid |

Este informe va en un commit propio sobre `c0ef770`.

## 2. Borrador de la decisión (la numera el Coordinador al integrar)

**SAC — usuario con alcance de recolector (Ingrid / Green Loop).**

Un tercero puede llevar la marca de un recolector (`third_parties.collector_id`, FK autorreferente NO ACTION) y un miembro puede llevar un alcance (`user_collector_scopes`, una fila por org y usuario, FKs RESTRICT).

Con alcance, `get_required_org_context` deja pasar solo una **lista blanca de 32 rutas** (`SCOPED_ENDPOINTS`, deny-by-default). Cualquier otra ruta da 403 «Fuera de tu alcance», aunque el rol tenga el permiso, y lo mismo las rutas de miembros.

**Un solo predicado decide qué es «propio».** Un tercero es propio si lleva la marca; un movimiento, si cumple `movement_owned`: tipo propio, sin `transfer_pair_id`, en una cuenta asignada y con un tercero en alcance. Ese predicado sirve para anular y para la evidencia (H2).

En la Entrada: 9e/9f para las que ya existen, 9g (con alcance no se liquida con descuadre) y el aviso D-E2(b) al liquidar.

El Balance Detallado agrupa los terceros marcados en «Recolector: X»; el General no cambia.

**No-regresión demostrable:** sin fila de alcance el contexto no consulta nada más (la consulta usa el índice único, R2) y el front no cambia. Golden 0/0 en los dos goldens (bases 31ba117 y 87c799f), cada uno con UNA sola BD: la migración es aditiva (columna NULL y tabla nueva) y el código base no las lee.

**Marca inicial por regla, nunca por lista** (decisión 4 de Daniel): nombre normalizado con `greenloop`/`greenlop`, menos el recolector y «BIOGREENLOOP».

**Lección:**
- Una condición que ningún camino HTTP alcanza (`transfer_pair_id` en un tipo propio) solo se mide si se la fuerza por ORM.
- Una FK autorreferente con otras referencias no se mide borrando, sin un caso aislado (P24, P33).

## 3. Gates y artefactos

| Gate | Resultado | Artefacto |
|---|---|---|
| Plantado r1, P1–P59, matriz de `41940cf` | 55 en la diagonal.<br>P24 y P33: dirección peligrosa, reales (§4).<br>P31: dirección peligrosa por el instrumento.<br>P43: salió en la diagonal, pero inválido por un import roto.<br>Final, mandando la r2 donde la hay: 59/60. | `EV/plantado/plantado.log`<br>`predicciones.tsv` `28bf0b36…58ae` |
| Plantado r2 (P24, P24b, P33, P43) | 4/4 en la diagonal.<br>El árbol de la r2 es el de `c00a133` (`878b89b61150015f`, recalculado). | `EV/plantado/plantado_r2.log`<br>`predicciones_r2.tsv` `23dd8b0d…8e47`<br>`resumen.md` `02be7513…7fe9` |
| Plantado PTX (la ruta nueva de develop) | Meter `tax-entities` en `SCOPED_ENDPOINTS` tumba el test nuevo (200) y T2b, como se predijo.<br>T2 y T1 familia caen de más, en la dirección barata. | `EV/plantado_tax_entities.log` `0d110427…7219` |
| Golden 1 (`31ba117` vs `c00a133`, una BD) | 0 diffs reales y 0 aditivas en 32+32 capturas, con manifiesto en los dos lados.<br>Guardas de procedencia 1–3.<br>**Vida:** PUT collector-scope sin token da 404 en la base y 401 en la rama.<br>**Control positivo** (fuera de CAPTURES): «Recolector: Green Loop» 0 veces en la base y 3 en la rama, sobre los mismos PID. | `EV/golden/` (predicción `d23cbee1…7270`; addendum con la BD y las 124 marcas, `72a3e343…9235`, escrito antes del lock) |
| Golden 2 (`87c799f` vs `c0ef770`) | Lo mismo: 0/0, vida 404/401, control 0/3 y 32+32 capturas. | `EV/golden2/` (predicción `34e23493…579b`) |
| Merge 1aacc2f (`5216969`) | Cruce único en `Sidebar.tsx`: `checkHide` y `checkScope` quedan en AND.<br>lint 37, build 0, guardas + tope 53/53. | `EV/merge2_gates.log`<br>`EV/sondeo_menu_merge2.log` (vale solo la 3.ª medición)<br>`QA/revision_merge2_5216969.md` `8dd4ca14…2241` |
| Merge 87c799f (`598558d`) + test (`c0ef770`) | Sin conflictos de texto ni migraciones.<br>En los 6 archivos que cruzan, lo que agrega la rama es idéntico antes y después del merge.<br>ruff limpio, lint 37, build 0.<br>Guardas + `test_tax_entities_listing.py` + el archivo de la rama + tope: 142/142. | `EV/merge3_cruces.log`<br>`EV/merge3_gates.log` `190b1a0d…`<br>`QA/revision_merge3_c0ef770.md` `b83973db…5111` |
| Menú en pantalla, árbol del merge 3 | **SAC** (Johana y el superusuario): «Impuestos y retenciones» sí, «Listas Precios» no.<br>**Costa:** al revés, con «Listas Precios» en el menú y en la pestaña «Precios».<br>**Ingrid:** los mismos 5 enlaces. | `EV/sondeo_menu_merge3.log` `0ece464f…` |
| Red por pantalla (QA 2, su entorno) | **Costa:** 69 requests en develop y 69 en `c0ef770`, el mismo multiconjunto, 0 respuestas ≥ 400.<br>**Johana:** 95 → 97 (los dos `payable-providers` de los selectores de recolector), 0 ≥ 400. | `QA/revision_merge3_c0ef770.md` |
| Sondeos del autor (construcción, r3) | **Ingrid:** 106 requests, 0 ≥ 400, con la predicción escrita antes.<br>**Johana:** 97 requests, el mismo multiconjunto predicho, 0 ≥ 400.<br>**Costa:** 69 requests, 0 ≥ 400. | `EV/sondeo_red_r3.log`<br>`EV/johana_red_despues_r3.log`<br>`EV/costa_red_despues_r3.log` |
| Parity | DIFF CERO fuera del baseline: 68 tablas, 306 índices, 375 constraints. | `EV/parity_final.log` |
| Migración up/down/up en `reciclaje_coder_2` | Normalizado, el antes y el después son idénticos (`ae3e13d7…`); solo cambia el token aleatorio `\restrict` de pg_dump.<br>Control positivo: antes vs medio difieren en 80 líneas.<br>Datos restaurados: 124 marcas y 1 alcance. | `EV/migracion_updownup/ciclo.log` |
| R2 (una consulta más por request) | Index Scan por `uq_user_collector_scopes_org_user` en los cuatro casos, entre 0,04 y 2 ms de ejecución. | `EV/r2_explain.log` |
| Ensayo del script de la marca contra `:8012` | Ver §5. | `EV/ensayo_marcar_recolector.log` `4c260031…ae1d` |
| Pasada 1 y deltas, QA 2 | Pasada 1 OK; deltas OK; OK al incidente del plantado. | `QA/pasada1_9d8cc33.md` `89cb33e8…4ffc`<br>`QA/revision_deltas_41940cf.md` `5e6a8df4…a968`<br>`QA/evaluacion_incidente_plantado.md` `03d5ef8a…e54c`<br>`QA/revision_delta_c00a133.md` `4b90bd1e…a0fe` |
| Dirigidas de QA sobre `c0ef770` | **En curso** al escribir este informe. | — |

Suite completa: **diferida al checkpoint** (regla del 19-nov). Este ciclo no cita una suite que no corrió.

## 4. Hallazgos

### Reales, cerrados con tests

- **P24.** La condición `transfer_pair_id IS NULL` de `movement_owned` no tenía ningún caso por HTTP. Los cuatro sitios que asignan `transfer_pair_id` crean otros tipos (grep de QA 2).
  - Se cerró con `test_filas_28_30_pago_propio_con_par_forzado[anular|evidencia]`: un pago propio al que se le fuerza el par por ORM (precedente #109 C3). Afirma que el pago es propio en todo menos en el par, que tanto el pago como el par siguen `confirmed`, y tiene control positivo.
  - Además se agregó P24b: el defecto plantado en el predicado compartido.
- **P33.** T20 no aislaba la FK del alcance, porque a Green Loop también lo retienen los terceros marcados y la Entrada.
  - Se cerró con T20b: un recolector sin ninguna otra referencia. Control positivo: al borrar la fila de alcance, el borrado pasa.

### Ruta nueva de develop contra la lista blanca

`GET /third-parties/tax-entities` (#128) pide `third_parties.view`, que Ingrid tiene.
- Por deny-by-default ya le daba 403, y T1 ya la recorría.
- No cayó al mergear porque su conteo es una cota (`>= 200`), no un número exacto.
- Quedó nombrada en `test_t1_ruta_nueva_de_develop_tax_entities`, con control positivo (`ingrid_libre`, 200).
- **Regla para el próximo merge que traiga rutas:** que el conteo de T1 no caiga no quiere decir que la ruta no esté cubierta. El bucle de T1 la recorre igual, y la ruta se nombra aparte.

### Del instrumento, no de la matriz

- **P31.** Traduje la fila 9 («respetar lo digitado») a `feliz`, que no manda comisión. El que la manda (9999) es `rechazos`, y ese cae (QA 2 lo verificó en `P31_a.out`).
- **P43, r1.** El defecto plantado traía un import roto (`ThirdPartyCategory` vive en `third_party_category`), y T23/T24 cayeron por el ImportError. En la r2, con el import corregido, cae T23 en el alta y no en el flat.
- **P56.** El endpoint pasa el kwarg explícito, así que un default `True` no le llega a Johana. Se plantó en la condición (`if disc != 0`).
- **Corrida accidental del plantado (15:59).**
  - Qué pasó: un parche encadenado con `plantado.py verificar`, un modo que aún no existía, corrió el plantado real. P1–P8 corrieron con `:8012` encendido, y P9 se cortó con el defecto puesto.
  - Restauración: `purchases.py` volvió del respaldo (hash-object == HEAD), con 0 pedidos a `:8012` en esa ventana. La carpeta quedó como `EV/plantado_INVALIDO_corrida_accidental/`.
  - Desde entonces el arnés tiene modos explícitos y aborta ante uno desconocido.
- **n17/n18 de QA 2, aplicadas al arnés:**
  - cada corrida lleva sufijo, y si un xml u out ya existe aborta en vez de pisarlo;
  - una caída por ImportError, NameError o SyntaxError sale «INVÁLIDO». Control positivo: P43 r1. Control negativo: 0 de 61 `.out`.
- **Golden y merges, tropiezos propios** (anotados en sus logs):
  - el primer intento de capturas del merge 2 usó una variable `path`, que en zsh es `PATH`, y no escribió nada;
  - las dos primeras mediciones de las pestañas de Configuración fueron vacuas: la pestaña se llama «Precios» y los selectores no la veían;
  - el nodeid del test del tope se escribió con una clase inventada y se corrigió antes de lanzar;
  - en la entrega del merge 3 escribí «16 archivos» y el `name-only` tiene 14. El txt adjunto estaba bien; el número del mensaje no salió de ningún comando.
- **Ensayo del script, corrida 5.**
  - **El primer intento (13:34:36) es inválido:** `$DB` no se separó en palabras en zsh, el UPDATE no corrió y el script, sin sorpresa, salió 0. Se conserva en el log con la marca de inválido.
  - **Se rehízo con un arreglo (13:34:48):** con YEICO marcado con otro recolector, el script salió 3.
  - **No escribió nada:** el `max updated_at` de los terceros sigue en 13:34:02 antes y después del script.

## 5. Runbook del deploy 2 (lo ejecuta el Coordinador con el OK de Daniel)

Completa el §16 del plan. El orden y las condiciones de allí se mantienen.

### 1. Turno de migración

- `e7f9a1b3c5d8` con `down_revision = d6e8f0a2b4c7`, la migración de #122.
- En `c0ef770`, `alembic heads` da un solo head, `e7f9a1b3c5d8`.
- **Antes del deploy:** el Coordinador confirma que producción está en `d6e8f0a2b4c7`.
- Si `develop` recibe otra migración antes de integrar, hay que cambiar el `down_revision`, y ese cambio es un delta para QA.
- Se aplica vía `/deploy`. Es aditiva: columna NULL y tabla vacía.

### 2. Marca inicial

- **Antes de correr nada:** se leen en producción el id de la SAC activa y el del tercero «Green Loop», que tiene que ser service_provider y estar activo. Los dos ids se escriben en el log; nunca se resuelven por nombre.
- **Predicción:** se escribe en el log cuántos se espera marcar (N). Se cuenta con una lectura de producción que aplique la misma regla de §9.

**Dry-run:**

```
scripts/marcar_recolector.py --api-url <prod> --org-id <id> --collector-id <id> --esperado <N>
```

En el dry-run hay que verificar:
- **«ADALBERTO AVILA (GREENLOOP)» y «DANIEL DE LA HOZ (GREENLOP)» están en «a marcar».** Son las dos «excepciones» que nombró Johana (L49 y L51 de la transcripción, citadas en el plan, línea 135). En la copia de dev ya llevan el sufijo (plan, líneas 164–165). Daniel de la Hoz es *Empleados* (generic): la marca va en cualquier tercero (S2). Si alguno de los dos falta, se detiene y decide Daniel.
- **Excluidos con su motivo:** el recolector («Green Loop») y «BIOGREENLOOP». Si alguno no aparece, el script sale con exit 3.
- **Exit ≠ 0** detiene todo, y decide Daniel.

Referencia, el ensayo en la copia de dev (`EV/ensayo_marcar_recolector.log`):
- cumplían la regla 126; excluidos 2 (el recolector y BIOGREENLOOP); a marcar 124, con los dos nombres arriba (corrida 1);
- con `--esperado 123`, salió con exit 3 sin escribir (corrida 2);
- con `--esperado 124` marcó 124 (corrida 3);
- re-correr dio 0 a marcar y exit 0 (corrida 4);
- un tercero marcado con OTRO recolector dio exit 3 sin escribir (corrida 5).

**En producción:**
- **Corrida real:** la misma línea con `--apply`, con el OK de Daniel.
- **Re-corrida:** tiene que dar 0 a marcar y exit 0.

### 3. Usuario de Ingrid, su caja, su alcance y la verificación

**Qué está ensayado y qué no.** QA 2 ensayó el runbook en su backend local (`:8022`, BD `reciclaje_qa_2`, árbol `c00a133`; `QA/ensayo_runbook/ensayo.log`, sha `f4f02c35…02f9`):
- **Ensayados:**
  - la marca, corridas 1–4;
  - los pasos 4–6: rol de 13 permisos, caja K1 antes que el alcance, collector-scope y `my-permissions` con `collector_scope`;
  - la verificación: suppliers con 123, todos marcados; una sola cuenta; categorías «Empleados» y «Proveedor Material»; `members` en 403, con Johana en 200 como control.
- **Por qué hubo un desvío:** la membresía se dio por admin de org, porque en esa BD no había un superusuario con clave conocida.
- **Lo que NO es el comportamiento final:** en ese ensayo `tax-entities` dio 422, porque `c00a133` todavía no tenía la ruta y la petición caía en `/{third_party_id}`. Sobre `c0ef770` da 403 con el prefijo de alcance, como muestran el test nuevo y `QA/red/ingrid_sondeo_c0ef770.log` (sha `bf850683…aaba`).
- **El alta por `/system` y el reseteo de #85:** QA 2 no los ensayó. Se ensayaron después de integrar, en la demo de la dev principal: `:8001`, BD `reciclaje_db` (`demo_ingrid_8001.log`, sha `b200b3e4…77ed`). Ahí corrió el runbook entero:
  - la marca: 124, y la re-corrida 0;
  - el registro con una clave temporal descartada;
  - el reseteo de #85;
  - `POST /system/users/{id}/add-to-org`;
  - la caja y el alcance;
  - la verificación con el usuario de demo.
- **La comparación de Entradas del paso 6 corrió vacía en la demo** (C3 de QA 2):
  - a las 17:52, rehecha con el filtro del lado del cliente, dio `0 == 0` (línea 480: las 34 Entradas eran «sin recolector»);
  - después de crear las 2 Entradas de demo solo se miró que Ingrid tuviera `total= 2` (línea 493), sin comparar su conjunto con el del superusuario.
  - **Re-corrida con datos a las 17:59** (`EV/paso6_paginado_8001.log`, sha `e4299a76…3857`; script `paso6_paginado_8001.py`, sha `97a5ad5b…bbf4`), con el método de C1 y la predicción escrita antes, cumplida:
    - Entradas: el conjunto de Ingrid (DEMO-GL-1 y DEMO-GL-2) es igual al subconjunto Green Loop de las 36 del superusuario;
    - proveedores: los 123 de Ingrid son iguales al subconjunto Green Loop de los 211 del superusuario;
    - control positivo de la paginación: con páginas de 10, las mismas 36 Entradas (4 páginas) y los mismos 211 proveedores (22 páginas).
  - **Lo que solo existe en producción:** más de 100 Entradas (148 a las 13:58) y 25 de Green Loop. La primera comparación con ese volumen es la del deploy.
- **Dos correcciones que salieron de esa demo** (plan v1.13):
  - **Entradas:** `GET /inbound-orders` no tiene el parámetro `collector_id` y lo ignora en silencio (devolvió las 34). La comparación del paso 6 filtra del lado del cliente.
  - **La clave va al final:** entre el alta en la org y el alcance, Ingrid es «Recolector» sin alcance. Por eso la clave final se fija DESPUÉS del alcance.

Siguen el §16 del plan (v1.13), pasos 3 a 7, en este orden:
1. **Registro** con una clave temporal aleatoria que no se guarda.
2. **Membresía** con `POST /system/users/{id}/add-to-org`, con el rol «Recolector» y sus 13 permisos de §5.1. Nunca por el alta de miembros, que deja la clave fija.
3. **La caja**, antes del alcance.
4. **Antes del alcance,** se lee que exista la categoría «Empleados».
5. **El alcance.**
6. **La clave final**, solo con el reseteo de #85 y DESPUÉS del alcance. Hasta acá nadie conoce la clave, así que nadie puede entrar en la ventana sin alcance.
   - **Nunca desde Usuarios** (C2 de QA 2): el botón de reseteo de Usuarios fija '123456' y lo puede usar cualquier admin de SAC. Ni durante el runbook ni después.
7. **Verificación con su usuario:**
   - **toda lectura de lista** con el límite máximo del endpoint (`/inbound-orders` 1000, `/suppliers` 5000, `/money-accounts` 500), exigiendo `len(items) == total` (si no, se pagina con `skip`), y comparando conjuntos de ids, no conteos (C1 de QA 2: con el límite de 100 por defecto, la lectura de Johana se trunca y la de Ingrid mira 100 de 123);
   - `my-permissions` trae `collector_scope`;
   - las Entradas son solo las de Green Loop: su conjunto se compara con una lectura de Johana filtrada del lado del cliente por `collector_id`, nunca con `?collector_id=`;
   - los proveedores son solo los marcados, con la misma comparación;
   - `members` le da 403.
- **Condición de uso R1:** báscula tiene que poner el recolector en cada Entrada de Green Loop. Daniel se lo comunica a Johana.

## 6. Notas para Daniel o para ciclos propios (no bloquean)

- **Desfase preexistente del catálogo de permisos** (`EV/catalogo_vs_bd.log`):
  - `PERMISSIONS_CATALOG` tiene 90 y la tabla `permissions` de la copia de dev tiene 92.
  - Los que están solo en la BD son `treasury.manage_distributions` (migración `a1b2c3d4e5f7`) y `treasury.view_all_movements` (migración `3771a60dccbe`). El rol «Recolector» usa el segundo, y existe porque los permisos se leen de la tabla.
  - Es preexistente y este ciclo no lo toca.
- **Defecto preexistente, corregido de paso (plan v1.7, c1 de QA 2).**
  - **Qué pasaba:** la precarga de retenciones al re-liquidar tomaba «las vivas, o el lote revertido más reciente que exista». Una liquidación sin retenciones no deja filas, así que la precarga resucitaba las de un lote anterior.
  - **Cómo quedó:** ahora la precarga y la regla 9f usan la misma función, `last_liquidation_batch`, que mira la ÚLTIMA liquidación.
  - **Alcance:** la precarga es de todos, así que Johana también ve el cambio en ese caso.
- **Nit de QA 2** (`QA/revision_plan_v1.4.md`, líneas 17–20):
  - En una ruta flag-gated que no está en la lista blanca, el usuario con alcance recibe «Fuera de tu alcance» y no el 403 del flag, porque el contexto corre primero.
  - El flag sí corre antes que el 404 por objeto.
  - T1 afirma el prefijo de alcance. Que nadie lo «arregle» esperando el detalle del flag.
- **n16** (`QA/revision_delta_c00a133.md`, línea 22): el mensaje de 9g dice «faltan 2 unidad por repartir», sin plural.
- **n20 y n21,** que QA 2 adelantó por mensaje durante la pasada 2 (todavía no tienen archivo):
  - en Terceros, Ingrid ve pestañas que para ella siempre están vacías (Servicios, Clientes, Inversionistas, Pasivos, Provisiones);
  - el banner del detalle de la Entrada le habla de «valorar el descuadre» a quien, por 9g, no puede dejarlo.
  - Las dos son cosméticas y las decide Daniel.
- **El reseteo de Usuarios sobre una usuaria externa** (C2 de QA 2, la deuda de #85):
  - Después del deploy, un clic de Johana (o de cualquier admin de SAC) en «Resetear contraseña» deja la cuenta de Ingrid, que es de Green Loop y no de SAC, con la clave constante '123456' (`organizations.py:500`, `services/user.py:107`).
  - El alcance sigue aplicando, pero cualquiera que sepa su correo entra como ella.
  - Es la deuda de #85 (eliminar el reseteo-a-constante), que ahora cae sobre una usuaria externa. Lo decide Daniel.
- **Siguiente ciclo, decidido por Daniel:** el hueco de cuentas restringidas para orgs sin alcance (Costa, §6 del plan). El insumo, cuántas lecturas y escrituras de cuentas no miran `account_ids`, se saca por grep antes de planear.
