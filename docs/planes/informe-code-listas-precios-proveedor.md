# Informe de construcción — Listas de precios por proveedor (#98, ítem 7)

**Fecha:** 2026-08-14 · **Rama:** develop · **QA: GO** (2026-08-14), pendiente la revisión en pantalla de Daniel
**Plan:** `plan-sac-listas-precios-proveedor.md` v1.2 (GO de QA) + **D10 agregada durante la construcción**
**Migración:** `a2b3c4d5e6f7` (aditiva) · **Golden:** gate duro (toca `price_lists`, tabla compartida) — ✅ **corrido, 0 diffs**

---

## 1. Lo que se construyó

| Pieza | Dónde |
|---|---|
| 2 tablas nuevas + FK nullable en `price_lists` + índice | `a2b3c4d5e6f7` |
| Modelos `PriceListGroup` / `PriceListGroupMember` | `app/models/price_list_group.py` |
| Los 6 puntos de lectura acotados + resolutor | `app/services/price_list.py` |
| CRUD de listas, membresía y sembrado | `app/services/price_list_group.py` |
| Router gateado por flag | `app/api/v1/endpoints/price_list_groups.py` |
| Seam de no-regresión (`?third_party_id=`) | `app/api/v1/endpoints/price_lists.py` |
| Pantalla Config → Listas por Proveedor | `SupplierPriceListsPage.tsx` |
| Hook + lookup imperativo | `usePriceSuggestions.ts` |
| 4 pantallas consumidoras cableadas | 3 de compras + `InboundLiquidatePage` |

---

## 2. 🔴 El defecto que me comí y encontré releyendo, no corriendo

**Habría dejado a las 3 empresas cliente sin ninguna sugerencia de precio en compras.**

Las 3 pantallas de compras son **compartidas**. Al cablearlas para pasar el proveedor al resolutor, Costa/Biogreen/MetaRecycling empezarían a llamar `/current?third_party_id=X`; el resolutor no le encuentra lista a ese proveedor y —por D3, que es la regla correcta *dentro de SAC*— devuelve **cero precios**.

**Por qué ningún gate lo habría atrapado:**
- Los 26 tests del ítem **crean una lista primero**: ninguno ejercita "org sin listas + parámetro presente".
- `tsc` y ESLint no ven semántica.
- El golden **no captura `/price-lists`** (verificado: `CAPTURES` tiene 14 entradas y ninguna lo incluye).
- Abrir la pantalla en SAC tampoco: en SAC sí hay listas.

Lo encontré releyendo el cableado y preguntándome *"¿qué pasa si esta pantalla corre en Costa?"*. Es la misma clase que el ítem (b) de #93: **el daño está en un camino que ninguna prueba recorre**.

**El arreglo (D10) es estructural, no un parche:** si la organización no tiene **ninguna lista activa**, el parámetro es **inerte** y se devuelve la lista general. Con al menos una lista, D3 completo.

Es la semántica correcta —*la funcionalidad está apagada hasta que alguien cree su primera lista*— y es **exactamente lo que ya prometía el copy** que había escrito en el diálogo de creación: *"Es la primera lista. Desde que exista una, a un proveedor sin lista asignada no se le sugiere ningún precio."*

Se resuelve en el backend y **no gateando el frontend por flag**, por el argumento de D4: gatear en la pantalla deja la regla en dos lados y el día que cambie se corrige en uno solo.

---

## 3. Decisiones que se desviaron del plan, y por qué

**`_base_query` lleva el `IS NULL`; `get()` se sobrescribe para saltárselo.** El plan (§4) pedía dos cosas que chocan: que un punto de lectura nuevo herede el filtro seguro, y que `get_or_404` **no** filtre (una fila pedida por su PK es esa fila). Se logran las dos: la base es segura por defecto, y la única lectura que se exceptúa lo dice en su docstring.

**El sembrado NO usa `third_party_service.get_suppliers`.** Ese devuelve una respuesta **paginada con `limit=100`**; una página incompleta no da error — hace que el sembrado se salte proveedores en silencio y que el selector muestre una lista corta que parece completa. Se reusa su filtro de `behavior_type`, que es la parte que importa.

**El sembrado no roba proveedores de otra lista.** Es una red de seguridad para el día uno, no una reasignación masiva que pise trabajo ya hecho. El response dice cuántos omitió.

---

## 4. Verificación de los tests contra defectos plantados

Los 26 pasaron a la primera, así que los verifiqué al revés — rompiendo el código a propósito:

| Defecto plantado | Qué falló |
|---|---|
| El resolutor cae a la lista general sin membresía | los 2 tests de D3 |
| `_base_query` sin el `IS NULL` | el listado genérico mezcla listas |
| El seam de D4 roto (general sin filtro) | 🔴 el guardrail, con el síntoma exacto: la org cliente ve 77777 donde debe ver 1000 |

---

## 5. Gates

| Gate | Estado |
|---|---|
| Tests del ítem | ✅ **29** (26 del plan + 3 de D10) |
| Suite completa | ✅ **1628 passed** (38:54) |
| Parity check modelos↔migración | ✅ **DIFF CERO** (atrapó que el índice faltaba en el modelo) |
| `ruff check app tests scripts` | ✅ |
| `npm run lint` | ✅ **37 warnings, 0 errores** — el presupuesto exacto, sin nuevos |
| `tsc --noEmit` | ✅ (atrapó un uso antes de declaración al cablear el hook) |
| **Golden ×3 orgs** | ✅ **0 diffs reales, 0 claves aditivas** en 48 capturas × 3 orgs |
| Smoke real contra la SAC de dev | ✅ (ver abajo) |
| Abrir las pantallas en el navegador | 🔴 **pendiente — el único gate que no puedo correr yo** |

### El golden, y por qué hay que leerlo con cuidado

Contra `origin/main` salen **72 diffs** y **ninguno es de este ciclo**: están todos en `tp_statement_busy`, la captura que se agregó en #96 E, y son el reordenamiento de #96 B. Se probó por eliminación —`main` vs `develop-HEAD`, las dos SIN este ciclo, dan los mismos 72— y después se corrió el golden **aislado** (`develop-HEAD` vs el árbol de trabajo), que da **0**. O sea: lo que cambia el statement es el commit que ya está en `develop` y que QA aprobó; lo de hoy no toca nada.

De paso quedó comprobado sobre datos reales lo que más importa del reordenamiento: el **saldo final del tercero es idéntico en las tres piernas** (−490.730,35) y coincide con su `current_balance`. Lo que se movió es el `balance_after` de las filas intermedias de un día con varias operaciones, que es exactamente lo que #96 B se propuso arreglar.

### El smoke, y por qué el primero no probaba nada

La primera corrida dio verde comparando `0 == 0`: la SAC de dev **no tenía ningún precio cargado**, así que "el proveedor resuelve lo mismo que la general" era cierto y vacío. Lo dije y escribí un segundo smoke que primero carga 6 precios:

```
1. Precios cargados en la lista GENERAL: 6 materiales (ej. ALU-01 = $1,000)
2. Lista sembrada: 6 precios copiados, 1 asignados, 4 omitidos
3. Q-26 — 'PRUEBA - Chatarreria Bogota' resuelve 6 precios: IDENTICOS a la general ✅
4. Precio propio de la lista (ALU-01 -> $99.999): el proveedor ve $99,999 ✅ · la general sigue en $1,000 ✅ intacta
5. D3 — BAT-G07 puesto en CERO en la lista: ✅ deja de sugerirse y NO hereda el $2,000 de la general
```

El punto 5 es el que más costaba creer sin verlo: un cero en la lista **no** cae de vuelta a la general.

Quedan dos listas de prueba en la SAC de dev a propósito, para la revisión en pantalla.

---

## 6. Dónde mirar más duro

1. **D10.** Es la decisión que no estaba en el plan aprobado y la que evita la regresión. ¿Gatear también el frontend por flag (cinturón y tirantes)? → **QA: no**, y con una razón más fuerte que la mía: un gate en la pantalla **oculta si la regla del backend se cumple**. Hoy el resolutor es lo único que separa a Costa de quedarse sin sugerencias; si además el frontend no lo llamara, esa regla dejaría de ejercitarse y el día que alguien agregue una pantalla nueva —o llame la API directo— el defecto vuelve sin que nada lo haya advertido.
2. **El alcance del cableado.** Toqué 3 pantallas compartidas. → **QA lo verificó: correcto.** Solo las 3 de compras pasan el proveedor; las 3 de ventas y las 3 de cruces siguen llamando `usePriceSuggestions()` sin argumento — coherente con lo que pidió Hugo y sin efecto sobre ventas en ninguna organización.
3. **La lista general en SAC queda huérfana** cuando todos los proveedores estén asignados: la pantalla de Precios la sigue editando (D7) pero nadie la consume — salvo como **origen del sembrado**, que ahora es un consumidor real. Anotado, sin tocar.
4. **`sale_price = 0` en filas de lista** (costo aceptado de D1). Es **inalcanzable por el cableado actual, no por construcción**: ninguna pantalla de ventas resuelve por grupo, y aunque se cablearan, el hook convierte `<= 0` en `null` — el modo de falla sería ausencia de sugerencia, no un precio equivocado. El ciclo que algún día conecte ventas tiene que saber que esos ceros están ahí esperando.
5. **El lookup imperativo** (`useSupplierPriceLookup`) comparte cache con el hook por usar la misma llave. Si alguien cambia la llave en uno y no en el otro, se duplican requests sin que nada falle.

---

## 7. Runbook (notas del GO de QA, no bloqueantes)

**La siembra Q-26 va por el endpoint, no armada a mano por la pantalla.** `POST /price-list-groups`
con `seed_from_general` + `assign_all_suppliers` crea la lista **y** asigna en una sola operación.
Si alguien la arma por la UI en dos pasos, entre el "crear" y el "asignar" la organización ya tiene
una lista activa y nadie tiene membresía todavía → **cero sugerencias durante esa ventana**. Es el
escalón de D10 visto desde adentro: la primera lista cambia el comportamiento de toda la org de
golpe, y por eso la operación que la crea tiene que dejarla ya poblada.

**La premisa de Q-21 se verifica sola en la primera semana.** Si las listas terminan dispersas en
vez de completas con ceros deliberados, el síntoma va a ser **campos vacíos en masa** — hay que
mirarlo explícitamente en la primera revisión con Johana, no esperar a que lo reporten. De eso
depende D3: el "no hay respaldo" solo es correcto si la lista trae todos los materiales.

---

## 8. Lo que este ciclo enseñó sobre los argumentos por construcción

D1 era correcto y su demostración aguanta: recorrida query por query, a toda consulta a
`price_lists` a la que le falte el filtro le devuelven las mismas filas. Pero **cuantifica sobre
qué filas devuelve una consulta**, y D10 entró por el lado opuesto: no cambió las filas, cambió
**qué empieza a pedir el cliente**. Cablear las 3 pantallas compartidas mueve la *rama que se
ejecuta*, no el conjunto de filas — y la prueba de D1 no dice nada sobre los llamadores, ni tenía
por qué.

La regla que queda: **un argumento por construcción protege exactamente la superficie sobre la que
cuantifica. Un ciclo que toca datos y llamadores necesita dos argumentos, no uno.** El segundo se
escribe preguntando *qué va a empezar a enviar esta pantalla compartida cuando corra en una
organización que no tiene la función*.
