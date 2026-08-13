# Informe de código — Ciclo Entradas: peso, revisión Willard y liquidación por valor total

**Plan:** `docs/planes/plan-sac-ciclo-entradas-peso-listas.md` v1.1 (QA: GO condicionado — dictámenes aplicados)
**Alcance construido:** ítems 1, 2, 3, 4, 5 + D17. **Fuera:** ítem 6 (diferido con su consumidor) e ítem 7 (listas de precios, ciclo propio).
**Migraciones:** 1, exclusiva SAC (`f8a9b0c1d2e3`). **Golden:** no aplica — ver §6.

---

## 1. Qué quedó construido

| # | Ítem | Dónde vive | Efecto |
|---|---|---|---|
| 1 | David con rol `revisor_inventario` | `scripts/seed_sac_org.py` | Existe la persona que Hugo designó como revisor |
| 2 | "Un solo proveedor" | `InboundLiquidatePage.tsx` | Pre-llena el reparto con lo pesado. **Cero backend** |
| 3 | Peso obligatorio al revisar | `services/inbound_order.py` (`_require_scale_weights`) | Un solo punto de validación; autocompleta si el material se mide en kg |
| 4 | Willard pasa por revisión | `review()` / `confirm()` + 3 pantallas | `draft → reviewed → confirmed` |
| 5 | Liquidar por valor total | `schemas`/`models`/`services` + migración | `unit_price = total / cantidad`, cuantizado |
| — | D17 | `_decertify_if_reviewed` | Editar **líneas** des-certifica; **cabecera** no |
| — | Cuantización a 3 decimales | `liquidate()` (`ALLOC_Q`) | Cierra la identidad "pesado = repartido + descuadre" |

## 2. Las decisiones que un revisor debe mirar con lupa

**El peso se valida en `review()` y en ningún otro lado.** No se endureció el schema de captura (D1: el pesador es el eslabón apurado y trabarlo tiene costo operativo real). Consecuencia deliberada: una entrada puede vivir en `draft` sin peso indefinidamente. El camino de salida existe y está probado (`test_entrada_vieja_sin_peso_se_edita_y_se_revisa`) — importa porque **hay entradas SAC ya capturadas sin peso** en dev y, cuando se despliegue, en producción.

**D2 autocompleta, no exige.** Si `Material.default_unit == "kg"`, `review()` copia `quantity` a `scale_weight_kg` y persiste. Pedir dos veces el mismo número sería fricción pura. La consecuencia a vigilar: el peso de un material en kg **nunca es un segundo pesaje** — es el mismo dato. Para el informe de kg/unidad que viene después, solo los materiales por unidad aportan información nueva.

**El peso NO entra a ningún cálculo.** Ni al precio (D5: Johana digita el total, el peso solo la ayuda a decidirlo), ni al descuadre (que se calcula contra `quantity`), ni al inventario. Es un dato certificado que hoy solo se muestra. Quien lo conecte después debe saber que hasta ahora nadie depende de él.

**El centavo de D8 es visible, no silencioso.** $200.000 ÷ 3 = 66.666,67 → la compra nace en $200.000,01. Verificado en dev: compra #3 por $1.790.000,01. La pantalla lo muestra en ámbar antes de guardar (`66.666,67 c/u → $200.000,01`). Hacerlo exacto exigiría persistir un total en `purchase_lines`, que es **tabla compartida**, por un centavo.

> **Límite de esa promesa (QA).** La vista previa deriva el unitario en JS con `Math.round(x*100)/100` y el backend con `Decimal.quantize(PRICE_Q)`, que es HALF_EVEN: en un empate exacto discrepan un centavo (total `2,03` ÷ 2 → la pantalla dice `1,01`, se persiste `1,02`). **Se acepta ±1 centavo en la vista previa**, y no se intenta igualar el modo de redondeo porque no lo arreglaría: float y Decimal difieren en la *representación*, no solo en el redondeo — un `2.03/2` en float ni siquiera cae exactamente en el empate. La alternativa honesta sería pintar el número que devuelve el servidor, y eso exige un round-trip que antes de guardar no existe. Con montos en pesos colombianos (miles a millones, casi siempre enteros) el empate al medio centavo no aparece en la operación real.

**`ALLOC_Q = 0.001` no es una precaución: es un arreglo.** `InboundLineAllocation.quantity` es `Numeric(15,4)` y `PurchaseLine.quantity` es `Numeric(10,3)`: el descuadre se calculaba con la del reparto y al inventario entraba la de la compra, así que la identidad "pesado = repartido + descuadre" se rompía hasta 0,0005 kg por asignación **sin warning**.

**Y de paso cerró un defecto latente que el informe v1 no vio (QA).** La firma de re-liquidación de #93 cuantiza ambos lados a `QTY_Q = 0.0001`: lo que entra y lo persistido. Antes de este cambio una asignación de `100.5004` firmaba como `100.5004`, mientras la BD devolvía `100.500` → `100.5000` en `PurchaseLine` — **distintas**, y cada re-liquidación disparaba un revert-and-reapply innecesario, en silencio. Con la cantidad ya en 3 decimales, llevarla a 4 da el mismo número de ambos lados. `ALLOC_Q` no protegió la firma: la reparó.

**El modo de precio es parte del reparto, no de la sesión.** `total_price` se persiste (D7). Sin eso, des-liquidar y re-liquidar (#93 D20 conserva el reparto) mostraría un unitario derivado en vez de lo que Johana escribió, y el modo se perdería en silencio. Cubierto por `test_round_trip_conserva_el_modo_y_no_recrea_compras`, que además verifica que **no se recrean las compras** (la firma cuantizada coincide).

**D17 distingue líneas de cabecera.** La revisión certifica pesos y cantidades — o sea, líneas. `_decertify_if_reviewed` corre después de `_persist_mirror_lines` en **las dos ramas** de `update()` (tipo compra y willard-draft) y devuelve un warning que el hook ya toastea. Cambiar factura, nota o vehículo no toca lo certificado y no des-certifica.

## 3. Lo que se tocó y por qué no rompe lo de antes

- **`display_status_of` y su espejo SQL: sin cambios.** Desde #93 el estado es columna y `reviewed` se mapea sin mirar el tipo. Willard entra al nuevo estado por la puerta que ya existía. `test_filter_parity_with_field` sigue verde por construcción.
- **`total_price` en la respuesta.** El endpoint arma `InboundAllocationResponse` **campo por campo** — agregar la columna al modelo y al schema no bastaba, el campo volvía `None`. Es la trampa de #89 ("el campo no rompía, MENTÍA"); se cerró en `endpoints/inbound_orders.py`.
- **La compra legacy 1:1** (ciclos B–D, filas con `purchase_id`) conserva su flujo viejo en las tres pantallas: liquida directo desde Registrada, sin revisión.

## 4. Re-semantización de tests

Seis suites se movieron por el cambio de flujo, con dos helpers en vez de edición test por test:

- `_weighed(line)` agrega `scale_weight_kg` a las líneas de las fixtures.
- `_confirm(...)` hace review→confirm.

Los tests que validan **la captura** quedaron intactos a propósito, y los negativos pasan `scale_weight_kg=None` explícito — que la ausencia de peso sea deliberada y no un descuido de la fixture.

**22 tests nuevos:** `TestPesoObligatorioAlRevisar` (6), `TestD17Descertificacion` (3), `TestLiquidarPorValorTotal` (8), `TestWillardRevision` (5).

## 5. Gates

| Gate | Resultado |
|---|---|
| Suite completa | **1592 passed** en 41:31 (0 fallos) |
| Re-corrida de las 6 suites de Entradas tras el fix de §9.3 | 204 passed |
| Parity check | DIFF CERO (60 tablas, 267 índices, 304 constraints) |
| `tsc --noEmit` | limpio |
| `npm run build` | limpio |
| **Smoke real contra dev** | ✅ los 15 asserts — ver §7 |

## 6. Por qué el golden no aplica

**El argumento es el gating, y solo el gating.** El router de Entradas está gated por `kg_ledger_enabled`, y las 3 orgs cliente tienen **cero filas en `inbound_orders`** — el código que toca `purchase_lines` no se ejecuta jamás para ellas. La migración, por su parte, agrega una columna nullable a `inbound_line_allocations`, que es tabla exclusiva SAC. Esa pata es hermética y alcanza sola.

> ⚠️ **Corrección de QA a la v1 de esta sección.** La v1 se apoyaba además en una segunda pata que es **falsa**: *"`purchase_lines` recibe una cantidad cuantizada a 3 decimales, que es la escala que la columna ya tenía, no hay valor nuevo posible"*. `Decimal.quantize()` usa el contexto por defecto (**ROUND_HALF_EVEN**) y Postgres `Numeric(10,3)` redondea **half away from zero**: en un empate exacto divergen — `100.5005` da `100.500` en Python y `100.501` en PG. O sea, sí hay un valor nuevo posible.
>
> Se borra la frase, y no por cosmética: *"cuantizar a la escala que la columna ya tenía no puede cambiar nada"* es un razonamiento que se copia y pega, y el día que se aplique en un camino que las orgs cliente **sí** ejecutan, va a ser falso ahí también.

Para SAC, HALF_EVEN pasa a ser el **único** redondeo que ocurre (PG ya no redondea nada porque el valor le llega en su escala), que es justo la propiedad de "el mismo número en todos lados" que persigue la normalización. Pero eso es una consecuencia del cambio, no una razón para no correr el golden.

El ítem 7 (listas de precios) sí toca tablas compartidas y por eso salió a ciclo propio con golden propio.

## 7. Smoke ejecutado contra la base de desarrollo

No es sustituto de la suite: es la verificación de que el camino **completo** funciona sobre datos reales de la org SAC, incluida la pantalla.

```
captura sin peso                -> 201  (pesos: BAT-G07=None, ALU-01=None)
revisar sin peso                -> 400  "Falta el peso de bascula en: BAT-G07"
   nombra el de unidad, NO el de kg     (D2 autocompleta ese)
revisar con peso                -> 200  reviewed | ALU-01 autocompletado a 530
editar LINEAS de una revisada   -> draft + warning
editar CABECERA de una revisada -> sigue reviewed
liquidar por valor total        -> 200
   BAT-G07  3 x total 200.000  -> unit 66.666,67   (compra: $1.790.000,01)
   BAT-G07 58 x unit  65.000   -> total_price NULL (modo unitario intacto)
unitario Y total juntos         -> 422
willard: confirmar sin revisar  -> 400  "Revise la recepcion antes de confirmarla"
willard: revisar sin peso       -> 400
willard: revisar -> confirmar   -> 200  kg plomo 204 | peso bascula 352,4 conservado
```

## 8. Deuda declarada de este ciclo

- **La pantalla se abrió con smoke de API, no con ojos en el navegador.** `InboundLiquidatePage.tsx` es el archivo con el peor historial del repo (dos bloqueantes de runtime en #93 pasaron tsc, build, 1533 tests y golden). El riesgo estructural sigue: **no hay ESLint en `frontend/`**, así que `react-hooks/rules-of-hooks` no corre. Montarlo es ciclo propio pendiente. Mitigación aplicada acá: los dos hooks nuevos (`bulkSupplier`) quedaron con los demás `useState`, antes de todo guard, y las dos funciones nuevas son planas; y todo valor que viene del API pasa por `num()` — las dos clases de bug de #93.
- **Ítem 6 (% de plomo por material)** queda diseñado y sin construir; la pregunta a Hugo sigue viva (Q-17).
- **Ítem 7 (listas de precios)** es el único con riesgo hacia afuera y sale con plan y ronda de QA propios.

## 9. Dos defectos encontrados después de la suite, ambos corregidos

### 9.1 El rol del revisor no podía revisar de verdad

Yo había planteado esto como una pregunta operativa —"¿quién corrige si falta el peso?"— con un argumento de separación de funciones a favor de dejar a David sin edición. **Daniel lo rebatió en una línea: editar una entrada registrada antes de certificarla es el flujo normal**, y tenía razón. El argumento además era hueco: el control que yo decía proteger ya lo da D17, que des-certifica ante cualquier cambio de líneas **sea quien sea** el que edite.

Verificado contra los guards reales, al rol le faltaban **cuatro** permisos, no uno:

| Permiso | Lo pide | Sin él |
|---|---|---|
| `purchases.edit` | `PATCH /inbound-orders/{id}` | no puede corregir nada |
| `config.view_fleet` | `/drivers`, `/vehicles` | selectores de conductor y placa vacíos |
| `config.manage_fleet` | crear conductor/placa al vuelo (#80) | los botones **no están gated**: error al clickear |
| `formulas.view` | `useCurrentFormulas` en el detalle | no ve los kg estimados de la Willard que certifica |

`REVISOR_ROLE` queda = `BASCULA_ROLE` − `purchases.create` + `purchases.review`: **trabaja sobre las mismas pantallas que Erwin, no captura, y certifica.**

### 9.2 🔴 El sembrado era create-only para roles — el arreglo anterior no habría llegado

Al aplicar 9.1 apareció el defecto de verdad: `create_users_and_roles` hacía `if custom_role["name"] not in by_role_name: create`. **Un rol que ya existe nunca se tocaba**, así que cambiar `permission_codes` en el script no tenía ningún efecto sobre una org ya provisionada — el rol se quedaba con lo que tuviera el día que nació, **en silencio**. La provisión idempotente ya hacía esto bien para bodegas (#28); roles se había quedado atrás.

Ahora compara contra `GET /roles/{id}` y hace `PATCH` solo si difiere, registrando el delta. Verificado en dev en dos corridas seguidas:

```
1ª: Rol revisor_inventario: permisos alineados (+['config.manage_fleet',
    'config.view_fleet', 'formulas.view', 'purchases.edit'] -[])
    Usuario creado: david@sac.com -> rol revisor_inventario
2ª: Rol bascula_sac: permisos al dia
    Rol revisor_inventario: permisos al dia      <- no-op que se lee como no-op
```

**Consecuencia para producción:** `revisor_inventario` todavía no existe allá (nace con el deploy de #93, que trae `purchases.review`), así que la primera provisión lo crea ya correcto. Lo que este arreglo evita es que el **siguiente** ajuste de permisos se pierda sin que nadie lo note.

**Guard pedido por QA:** `update_role` **no** tiene chequeo de `is_system_role` (el que existe es del `delete`), así que lo único que impedía pisar un rol de sistema era que las constantes se llamaran distinto — y el rol de sistema `bascula` está a un sufijo de `bascula_sac`. El sembrado ahora aborta si el nombre resuelve a un rol de sistema: convierte la convención de nombres en un invariante.

**Para el runbook, no para el código:** `usePermissions()` cachea 5 minutos (#26). Si se provisiona a David con la sesión abierta, ve sus permisos viejos hasta refrescar o re-loguear. No merece mecanismo nuevo; merece que quien provisione lo sepa.

### 9.3 Un 500 que era un 422

`InboundAllocationCreate.quantity` valida `gt=0` **antes** de cuantizar: `0,0004` pasa el `Field` y queda en `0,000`, y la derivación del unitario dividía por cero. Guarda + test (`test_cantidad_que_desaparece_al_cuantizar_explica`).

## 10. El flujo de las tres personas, probado con los permisos reales

No con superusuario —que bypassa todo y no prueba nada— sino con las tres sesiones:

```
Erwin (bascula_sac)  captura sin peso              -> 201
David (revisor)      la ve                         -> 200
David                revisa sin peso               -> 400  "Falta el peso de bascula en: BAT-G07"
David                CORRIGE el peso               -> 200  <- lo que antes no podia
David                lee conductores/vehiculos/materiales/formulas -> 200 x4
David                certifica                     -> 200  reviewed, por David
David                liquidar                      -> 403
David                anular                        -> 403
Erwin                revisar                       -> 403
Johana (admin)       liquida lo certificado        -> 200  compra #5 por $2.475.000
```
