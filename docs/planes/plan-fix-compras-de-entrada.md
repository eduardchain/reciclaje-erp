# Plan — la compra de una Entrada: el total viejo al re-liquidar (#130), y las puertas de Compras que la liquidan o la editan por fuera de la Entrada

v1.1 · 23-nov-2026 · Coder 2 · nivel **lógica**: servicio de compras compartido · base `develop` dea2320 · rama `coder-2/bug-total-reliquidar`

**Cambios desde la v1.0** (cf9ee693; veredicto de QA 2 `veredicto_plan_v1.0.md` ff1176e5). Solo se tocan C1, C2 y A2/B2; el arreglo no cambia:
- **C1:** P7 corregido en su mecanismo y en sus columnas. El puente se graba antes de la l.962, así que P7 tumba TODA liquidación de Entrada. T9 dice que re-liquida con el MISMO reparto.
- **C2:** T4 se parte en T4a (contado) y T4b (el tope de la retención, que ahora discrimina).
- **C3:** se suma T3b, un material que ENTRA a una compra que ya existe.
- **P8, hueco propio:** P8 se planta por organización y no «siempre», y T10/T12 llevan una Entrada en su misma organización. Se suma P8b para editar.
- **O1–O3:** en A2 (populate_existing), C1 (T4a cubre el contado) y B2 (texto del 422).
- **Después del GO** (veredicto_plan_v1.1.md 8dafe84e, plan aprobado commiteado en 760aa82): D1 y D2 quedan decididas, se suma la nota O4 en B2 y la precisión O5 en P8. No cambian el arreglo, los tests ni las predicciones.

| Parte | Defecto | Dónde | Evidencia |
|---|---|---|---|
| **A** | Re-liquidar una Entrada con el reparto cambiado deja el total y la deuda del proveedor con el valor viejo (compra #130 de SAC) | `purchase.update(commit=False)` | `~/sac-evidencia/2026-11-23/bug-total-compra-130/` |
| **B** | Una compra de una Entrada desliquidada se puede **liquidar** (QA 1) o **editar** (QA 2) desde Compras, y la Entrada queda trabada o cae en A. Entra al plan por decisión de Daniel | `purchase.liquidate`, `purchase.update` + 3 botones | `…/qa-1-compra-entrada-sola/`, `…/qa-2-bug130/` |

Lo de esta sesión está en `~/sac-evidencia/2026-11-23/bug-total-compra-130/coder2-plan/`, y las rutas de abajo son relativas a esa carpeta.

**Datos:** el plan no corrige datos.
- La #130 la revirtió y re-liquidó Daniel sin cambios a las 11:32, y el Coordinador la verificó por API (`../despues/`).
- De B hay 0 casos en las 182 Entradas de producción (lectura del Coordinador).
- Las lecturas de producción que pide este plan están en §C5.

**Decisiones de Daniel** (23-nov, al autorizar el plan v1.1 con el GO de QA 2 8dafe84e; llegaron por el Coordinador). Las dos, las recomendadas:
- **D1** (B2): una compra de Entrada no se edita desde Compras, ningún campo. Revierte #75 D7b.
- **D2** (B3): ocultar «Cancelar» además de «Liquidar» y «Editar».

---

# Parte A — el total viejo al re-liquidar

## A0. Síntoma y alcance

Johana liquidó la Entrada de la remisión 16376, usó «Revertir liquidación», cambió dos cantidades del reparto (SCR-MOTO 2076→2078 y SCR-SG 1891→1897) y re-liquidó. Las líneas de la compra #130 quedaron con las cantidades nuevas, pero `total_amount` y la deuda con el proveedor quedaron con el valor viejo: $15.542.912 contra $15.559.512 de las líneas, $16.600 de menos en el saldo de FELIPE GOMEZ. El inventario y el costo quedaron bien.

En las 4 organizaciones de producción, la #130 es la única compra con un total distinto de la suma de sus líneas (`../alcance.log`, lectura del Coordinador).

## A1. Causa, medida

**El flujo.** `inbound_order.liquidate` re-sincroniza la compra viva de cada slot. Si la firma del reparto cambió, llama a `purchase_service.update(..., commit=False)` (inbound_order.py:886) y después, en la MISMA transacción, a `purchase_service.liquidate(..., commit=False)` (inbound_order.py:962).

**Lo que hace `purchase.update`** (purchase.py:1306–1373):
1. Borra las líneas y los movimientos con `query(...).delete(synchronize_session=False)`.
2. Crea las nuevas con `db.add(PurchaseLine(purchase_id=...))`, sin pasar por la colección.
3. Deja `total_amount` con el total nuevo, que es correcto.

La colección `purchase.lines`, que ya estaba cargada (la firma de inbound_order.py:857 la recorrió), sigue con los objetos de las filas BORRADAS. Con `commit=True` no pasa nada, porque `commit` + `refresh` la recarga. Con `commit=False` la función devuelve un objeto incoherente con la base.

**Lo que hace `purchase.liquidate`** (purchase.py:414–494):
1. Su consulta con `joinedload(Purchase.lines)` encuentra la compra en el identity map con la colección ya cargada, y **no la reemplaza**.
2. Step 4 calcula `total_amount = Σ líneas` con las líneas viejas y pisa el total correcto que había dejado `update`.
3. Step 4c (`db.flush()` + `db.refresh(purchase)`) graba ese total viejo y lo relee. **El mismo refresh recarga la colección con las líneas nuevas**: esa es la «cosa en medio» que preguntaba el Coordinador.
4. Por eso Steps 5–6 (movimientos de inventario, costo promedio, MCH) ven las líneas nuevas y salen bien.
5. Step 8 (saldo del proveedor) y todo lo que lee `purchase.total_amount` usan el total viejo.

La función lee las líneas de la compra en dos momentos y le tocan dos colecciones distintas. Si no existiera el refresh de 4c, el loop de costo escribiría `cost_adjustment` sobre filas borradas y la liquidación fallaría con un error en vez de cerrar en silencio con un número equivocado.

**Medición.** `medicion/mecanismo.log` (a151bef3…be4) se tomó con un test temporal (`medicion/test_zz_mecanismo_coder2.py` d7d5b321…e6d), que se copió a `tests/`, se corrió y se borró; el árbol quedó limpio. Re-liquidar 100→102 kg a $1.000 da:

```
update(commit=False) SALE: total_amount=102000.000 lines=[Decimal('100.000')]
refresh(Purchase) ANTES: total_amount=100000.00000000000 lines=[Decimal('100.000')]
refresh(Purchase) DESPUES: total_amount=100000.00 lines=[Decimal('102.000')]
_apply_cost_at_liquidation qty=102.000
FINAL: total_amount=100000.00 suma_lineas=102000.00000000000 saldo_proveedor=-100000.00
```

QA 2 llegó al mismo bug por otra puerta (`../../qa-2-bug130/editar_derivada.log`, 67d579e3…e32, su E2). Editó la compra desliquidada 60→70 por `PATCH /purchases/{id}` y re-liquidó con el reparto guardado de 60: la firma difiere, `update` la devuelve a 60 y el total queda en 70.000 contra 60.000 de las líneas. Sin que nadie toque el reparto.

**Qué más lee el total viejo, dentro de la misma liquidación:**
- el saldo del proveedor (Step 8);
- el tope de retenciones (`_apply_retentions`: «debe ser menor al total de la compra»);
- el `subtotal` que recibe `apply_taxes`, que fija el tope del IVA y el `base_amount` que se persiste;
- el neto del pago de contado (Step 10);
- el prorrateo de comisiones de compra #30, que en la Entrada no se usa.

Todo sale bien con el total correcto, así que el arreglo es uno solo.

**Por qué ningún test lo vio — corrijo lo que se dio por hecho.** Se había dicho que ningún test re-liquidaba con el reparto cambiado, y **es falso**. `cobertura/cobertura.log` lo midió con un plugin que registra cada llamada a `PurchaseService.update`, sobre los 41 tests que des-liquidan. La predicción, escrita antes, era 0 llamadas con `commit=False`: dieron **2**, las dos de `test_sac_reparto_por_compra.py::TestSlots::test_t16_slots_son_identidad`.

Ese test re-liquida cambiando 100→150 en los slots 1 y 3, pasa por `update(commit=False)` y entra al bug. Pero solo afirma estados e identidad de slot, nunca el total ni el saldo. **El camino estaba ejercitado; lo que faltaba era mirar lo que el camino calcula.** Por eso T16+ (§C1) le suma los montos.

El control positivo del contador dio 9 llamadas con `commit=True`, de `test_api_purchases -k update` y de `test_inbound_orders`.

## A2. El arreglo

**En `purchase.update`, solo en la rama `commit=False`:** después del `db.flush()` final, expirar las colecciones que la función reescribió con DELETE masivo + `db.add`.

```python
        if commit:
            db.commit()
            db.refresh(purchase)
        else:
            db.flush()
            # (comentario: por qué — DELETE masivo + db.add no tocan la colección
            # ya cargada; sin esto quien compone la transacción lee las filas
            # borradas. commit=True no lo necesita: commit + refresh.)
            reescritas = [
                nombre for nombre, cambio in (
                    ("lines", obj_in.lines is not None),
                    ("commissions", obj_in.commissions is not None),
                ) if cambio
            ]
            if reescritas:
                db.expire(purchase, reescritas)
```

**Por qué aquí y no en `liquidate`:**
1. **El defecto nace en `update`.** Su variante componible (#20/#75) promete los mismos efectos que la no componible dentro de una transacción mayor, y hoy devuelve un objeto distinto: la colección dice una cosa y la base, otra. Arreglarlo en el origen protege a cualquier lector de la compra devuelta, no solo a `liquidate`.
2. **El radio de impacto es exacto.** `update(commit=False)` tiene UN llamador, `inbound_order.py:886` (`golden_aplica.log`), que es SAC y solo la re-liquidación con el reparto cambiado. La rama `commit=True`, por donde pasa `PATCH /purchases/{id}` de Costa y Meta, queda **byte a byte**: el cambio vive en el `else`.
3. **`flush` antes de `expire`, por `autoflush=False`** (app/core/database.py:19). La carga perezosa o el `joinedload` que repueblen la colección tienen que encontrar las filas nuevas ya escritas. Ese `flush` ya existe hoy en el `else`, y el `expire` va después.
4. **Un atributo expirado sí se repuebla.** `joinedload` llena los atributos *no cargados* de un objeto que ya está en el identity map, y uno expirado no está cargado. Así, la consulta de `liquidate` trae las líneas nuevas desde el Step 1, y los Steps 2–6 leen la misma colección. Se mide en la construcción repitiendo `mecanismo.log`, cuyo `refresh ANTES` tiene que dar `lines=[102]`.

**Las comisiones van por contrato, no por el bug.** `update` también las reescribe con DELETE + `db.add` (Step 4b). Hoy ningún lector las ve viejas, porque la Entrada no manda comisiones y `liquidate` las relee después de su refresh de 4c. Se expiran para que «`update(commit=False)` devuelve la compra como está en la base» valga entero. En el plantado no pesan fuera de su test de contrato (P3), y queda declarado.

**Descartado:**
- **Reordenar `liquidate`** (flush + refresh al inicio), o leer las líneas con `select` como ya hace `sale.liquidate`: también sería correcto, pero cambia el camino de TODA liquidación de compra en las 4 organizaciones (Costa tiene 3835 compras, `../alcance.log`) para un defecto que produce un solo componedor. Y no deja coherente el objeto que `update` devuelve.
- **`populate_existing()` en la consulta de `liquidate`:** releería desde la base la compra y lo que trae con `joinedload`, y descartaría lo que no esté grabado.
  - Hoy funcionaría: `update(commit=False)` y cada `liquidate(commit=False)` anterior del loop de la Entrada terminan en `flush` (purchase.py:674–675), así que en ese punto no hay nada sin grabar.
  - Pero ataría la corrección de `liquidate` a que todo lo anterior de la transacción llegue grabado. El `expire` no tiene esa dependencia: `update` graba lo suyo y expira lo suyo en el mismo lugar.
  - Además cambia la consulta de toda liquidación de compra en las 4 organizaciones.
  - La v1.0 ponía de ejemplo «el saldo del proveedor de la compra anterior». Era falso en su mecanismo, porque ese saldo ya está grabado (O1 de QA 2).
- **`synchronize_session="fetch"` en los DELETE:** por lo que recuerdo de la documentación de SQLAlchemy 2.0, sincroniza los objetos que coinciden con el borrado pero no las colecciones de sus padres, así que no arreglaría el bug. Esa sección no está en el venv (el docstring de `Query.delete` remite a `orm_expression_update_delete`), así que no lo afirmo: se mide como plantado P4.
- **Una alarma `total_amount == Σ líneas` en `liquidate`:** desde #120 las líneas llevan 8 decimales y la columna del total, menos. Compararlas exige cuantizar a la escala de la columna, y un error ahí da un 500 en las 4 organizaciones.

## A3. Barrido de la familia

`barrido_deletes.log` (b2890bbc…29e) se hizo sobre dea2320. Buscó los DELETE masivos (`.delete(synchronize_session`, `sa_delete(`, `Query.delete()`) y los borrados ORM (`db.delete(`): **23 + 1 + 6 sitios**. La pregunta para cada uno: ¿alguien lee la colección del padre después del borrado, en la MISMA transacción, antes de un `commit`/`refresh`?

| Sitio | Colección que queda vieja | ¿Commit o refresh antes de leerla? | ¿Lector viejo en la transacción? |
|---|---|---|---|
| **purchase.py:1311/1316** `update` (líneas y movimientos) | `purchase.lines` | `commit=True`: sí. `commit=False`: **no** | **Sí: `liquidate` vía inbound_order.py:962 → el bug** |
| purchase.py:1412 `update` (comisiones) | `purchase.commissions` | `commit=False`: no | No: la Entrada no manda comisiones y `liquidate` relee tras 4c. Se expira igual (A2) |
| purchase.py:483 `liquidate` 4b (comisiones) | `purchase.commissions` | sí: `flush` + `refresh` en 4c, antes de leer | No |
| sale.py:830/835 `update` (líneas y movimientos) | `sale.lines` | `update` no commitea; lo hace el endpoint | No: ningún servicio compone `sale.update` + otra cosa; `sale.liquidate` lee con `select(SaleLine)` |
| sale.py:918 `update` y sale.py:404 `liquidate` (comisiones) | `sale.commissions` | ídem | No: `_pay_commissions` lee con `select` |
| double_entry.py:313, 442–445, 487 (`liquidate` y `edit`) | DP, compra y venta internas | sí: `commit` + `refresh` al final de cada función | No: `liquidate` lee comisiones con `select`; `edit` no relee las colecciones borradas |
| inbound_order.py:792 `liquidate` (asignaciones del reparto) | `line.allocations` | `commit` al final | No: después del borrado solo se lee el *payload* (`pl.allocations`), no el ORM |
| inbound_order.py:1360 `confirm`; 1832/1858/1892 `update` | `order.lines` | `commit` + `refresh` al final | No: se reconstruye desde `lines_in` y los listados antes de borrar |
| willard_delivery.py:1051 `_replace_lines` (`db.delete`) | `delivery.lines` | `commit` + `refresh` justo después (`create`/`update`) | No |
| third_party.py:163 (categorías), role.py:419 (permisos), organization.py:594 (cuentas asignadas), price_list_group.py:276/282 (miembros) | asignaciones | `commit` justo después | No |
| los otros 5 `db.delete`: organizations.py:769 (alcance), role.py:465, organization.py:338 (membresía), user.py:124, attachment.py:269 | ninguna: borran una entidad suelta, no reescriben los hijos de un padre | `commit` en la línea siguiente | No |

**Resultado:** un solo sitio de la familia tiene un lector en la misma transacción, y es este bug.

**Riesgo latente, fuera del arreglo:** `purchase.create(commit=False)` también crea las líneas con `db.add` sin pasar por la colección. Hoy funciona porque nadie toca `purchase.lines` antes del `flush`, así que la colección queda *no cargada* y `liquidate` la carga fresca. La primera liquidación de toda Entrada pasa por ahí y la cubren los tests de Entradas existentes. Se deja anotado, sin tocarlo: si alguien leyera `purchase.lines` dentro de `create`, la colección nacería vacía y el total saldría en 0, en silencio.

---

# Parte B — las puertas de Compras que liquidan o editan una compra de Entrada

## B0. Lo medido

**QA 1** (`../../qa-1-compra-entrada-sola/`: `lectura.md` 9ca7b1a3…620, `medicion_final.log` 9362aa85…0df, script 3582474d…b8f, verifiqué los tres sha):
1. Se liquida una Entrada y se desliquida; las compras vuelven a `registered`.
2. `PATCH /purchases/{p1}/liquidate {}` → **200**. La compra queda liquidada sola: sin el descuadre, sin la comisión del recolector y sin los bloques de IVA, retenciones o contado. La Entrada sigue «Revisada».
3. La Entrada queda trabada: re-liquidar → 409, desliquidar → 400, cancelar la compra → 400 (por el guard de `cancel`).

**QA 2** (`../../qa-2-bug130/editar_derivada.log`, 67d579e3…e32, con su predicción escrita antes):
- **E1:** cambiar el PROVEEDOR de la compra desliquidada por `PATCH /purchases/{id}` → 200. Después, la misma trampa: re-liquidar → 409, desliquidar → 400, cancelar → 400.
- **E2:** cambiar la CANTIDAD → 200, y el tránsito sube sin que la Entrada se entere. Al re-liquidar se entra al bug de A (ver A1).

**El defecto es la asimetría:** `cancel` tiene el guard de la Entrada (#93 D14, purchase.py:744–771) y `liquidate` y `update` no.

## B1. Las puertas (`puertas_compra.log`)

| Puerta | ¿Guard de Entrada hoy? | Qué se hace |
|---|---|---|
| `POST /purchases` (`create`) | No aplica: una compra nueva no tiene Entrada. El enlace (puente) lo escribe solo `inbound_order.liquidate` | nada |
| `PATCH /purchases/{id}` (`update`) | **No → E1/E2 de QA 2** | guard nuevo (B2, D1) |
| `PATCH /purchases/{id}/liquidate` | **No → QA 1** | guard nuevo (B2) |
| `PATCH /purchases/{id}/cancel` | Sí (D14) | se comparte el predicado (B2) |
| `unliquidate` | No tiene endpoint propio: solo `inbound_order` la llama | nada |

## B2. El arreglo en el backend

**Un solo predicado para las tres puertas.**
1. Se extrae el SELECT del guard de `cancel` (puente `inbound_order_purchases` ⋈ `inbound_orders`, Entrada no anulada; purchase.py:751–763) a un helper, `_linked_inbound_number(db, purchase_id) -> Optional[int]`.
2. `cancel` lo llama sin cambiar su comportamiento: mismo SELECT, mismo mensaje y misma excepción `from_inbound`.
3. `liquidate` y `update` ganan `from_inbound: bool = False` y el guard. Va **después** de sus chequeos de estado y de doble partida, así que solo se dispara sobre una compra `registered`, que es justo el caso del bug. Una compra liquidada de una Entrada sigue recibiendo el mismo 400 de estado que hoy.

   > `liquidate`: 400 «Esta compra pertenece a la Entrada #N — liquídela desde la Entrada»
   >
   > `update`: 400 «Esta compra pertenece a la Entrada #N — corrija el reparto desde la Entrada»

4. `inbound_order.py:886` (`update`) e `inbound_order.py:962` (`liquidate`) pasan `from_inbound=True`. La 962 es la misma llamada que toca A.

**Que sea un solo predicado es la razón del helper:** las tres puertas no pueden volver a divergir, que es justo el defecto (#103 D3: un validador, todos los puntos de entrada).

**La excepción va por `from_inbound`, nunca por `commit=False`** (lo pidió QA 2). `commit=False` dice *cómo* se compone una transacción, no *quién* llama: atar el permiso a eso abriría la puerta a cualquier componedor futuro. El plantado P11 lo distingue con un test de servicio que llama con `commit=False` y sin `from_inbound` (T13).

**D1 — editar una compra de Entrada, bloqueado entero. Decide Daniel.** #75 D7b dejó «edit permitido» en la compra derivada para el flujo de Erwin, cuando la compra nacía con la captura. Desde #93 la compra nace al liquidar y todo lo suyo sale de la Entrada:
- el proveedor y las líneas, del reparto;
- la fecha, de D21;
- la factura, del reparto: `invoice_number` de la asignación, que la re-liquidación escribe en la compra;
- la placa, de la Entrada, que la propaga sola (#87e, inbound_order.py, sin pasar por `purchase.update`).

Editar una compra `liquidated` ya da 400 por estado. Lo único que se cierra es editar una compra **desliquidada**, que es un estado de paso. Por eso se recomienda bloquear todos los campos, sin lista de metadatos permitidos.
- **Alternativa, si Daniel la prefiere:** dejar pasar solo `notes`, el único campo sin dueño en la Entrada. Cuesta una regla de campos que hoy no hace falta.

**Qué depende hoy de editar la compra derivada** (`editar_derivada_dependencias.log`):
- `test_edit_derived_purchase_allowed` (test_inbound_orders.py:624) afirma el 200 de D7b. Se re-semantiza a `…_blocked` (T14): esa es la reversión, a la vista.
- El 422 de la Entrada al editar la factura de una compra tipo compra (inbound_order.py:1938) dice «…editela al liquidar (o en la compra del proveedor correspondiente)». Tiene dos problemas: con D1 el paréntesis manda a una puerta cerrada, y «editela al liquidar» no le dice qué hacer a quien ya liquidó la Entrada (el formateador que miente, #97; O3 de QA 2). El texto nuevo dice el camino real:
  > «La factura vive en el reparto de cada compra: escríbala al liquidar. Si la Entrada ya está liquidada, revierta la liquidación y vuelva a liquidar con la factura en el reparto; la liquidación quedará con la fecha del día en que vuelva a liquidar.»

  **O4, nota de QA 2 después del GO.** Re-liquidar pone `liq_dt = business_today_noon()` a TODAS las compras de la Entrada, también a las que se reusan (inbound_order.py:768 y 964, #93 D21).
  - Si la factura se corrige otro día, se mueven la fecha de liquidación y su efecto en los cortes (#61). Por eso el texto lo avisa.
  - Es un costo previo y no lo causa D1: una compra `liquidated` tampoco se podía editar antes (400 por estado), así que corregir la factura de una Entrada liquidada ya obligaba a revertir y re-liquidar.
  - Va como desviación declarada en el informe.

  Ese camino funciona sin tocar las líneas de la compra, porque la firma (l.857–861) no incluye la factura. Al re-liquidar con el mismo reparto, la compra se reusa y la l.892 le escribe `invoice_number`. También cambia «por proveedor» por «de cada compra», porque desde #122 el reparto es por compra.
- En el frontend, nadie lleva a `/purchases/:id/edit` desde las pantallas de Entradas.
- `test_purchase_header_warehouse_forces_lines_direct_api` edita una compra **directa**, no le afecta.

**`auto_liquidate`** (`create` → `self.liquidate`): no se toca. La compra recién creada todavía no tiene fila en la puente, así que el guard pasa.

**Entradas anuladas y el estado ya trabado.** El predicado excluye las Entradas anuladas, igual que hoy en `cancel`. Con el arreglo, el estado trabado de QA 1 ya no se puede producir: las tres puertas quedan cerradas para una Entrada viva, y anular una Entrada cancela todas sus compras.

Si alguno aparece antes del deploy (producción hoy: 0, §C5), **la salida queda escrita para que no se re-derive** (QA 1 Y1/Y2):
1. anular la Entrada: cancela las compras registradas, y la liquidada suelta queda viva;
2. cancelar esa compra suelta con `PATCH /purchases/{id}/cancel`, que el guard deja pasar porque la Entrada está anulada.

Con D2 el botón no aparece, así que el paso 2 lo hace el Coordinador por API, con el OK de Daniel.

**Costa y Meta, byte a byte (lo pidió el Coordinador):**
1. **No pueden tener filas en la puente** (`puente_escritores.log`). La puente la escriben:
   - un solo sitio del código, `inbound_order.py:918`, dentro de `liquidate`, detrás del router `/inbound-orders`, que exige `kg_ledger_enabled` (inbound_orders.py:44);
   - y dos migraciones de backfill (`b8c9d0e1f2a3`, `d6e8f0a2b4c7`) que solo copian Entradas existentes, y una Entrada solo existe con el flag.
2. **Backend:** sin fila en la puente, el helper devuelve None y `liquidate`/`update` siguen su camino de hoy. Lo único nuevo es un SELECT, y la respuesta es la misma.
3. **Frontend (B3):** sin fila en la puente, `inbound_order_id` llega null y los tres `can*` dan lo mismo que hoy.
4. **Lectura de producción** (§C5, G1): la predicción es 0 compras con Entrada en Costa y en Meta.

**La red es el PAR, como en #99 y #104:** con Entrada → 400 y nada escrito; sin Entrada, en la misma organización → 200 como hoy (T9/T10, T11/T12). Sin el contraste, «el guard funciona» y «bloqueé la puerta para todos» se ven idénticos.

## B3. El frontend: no ofrecer lo que el servidor rechaza (clase #97)

En `PurchasesPage.tsx:66–68` y `PurchaseDetailPage.tsx:69–71`, `canEdit`, `canLiquidate` y `canCancel` suman `&& !purchase.inbound_order_id`. El dato ya viene en el response de lista y detalle, por el lookup por página de #80 B1. Además:
- **Queda el enlace a la Entrada** del detalle: el banner «Entrada #N», que ya existe (PurchaseDetailPage.tsx:123).
- **Los deep-links `/purchases/:id/edit` y `/purchases/:id/liquidate`** quedan vivos. Si alguien llega por URL, el 400 sale como toast con el número de la Entrada.
- **D2 — ocultar «Cancelar» también. Decide Daniel.** Recomiendo ocultarlo: para una Entrada viva el servidor lo rechaza siempre (D14). El costo: para una compra viva de una Entrada ANULADA, cancelar sería la salida, y la pantalla no sabe el estado de la Entrada. Ese estado ya no se puede producir con B2 y en producción hay 0 (§C5, G2). Si apareciera, sale por API (B2).
- **La rama legacy 1:1 de Entradas** (InboundOrdersPage.tsx:245–249 e InboundDetailPage.tsx:384–389) navega a `/purchases/{order.purchase_id}/liquidate`. Con el guard, esa navegación daría 400. Solo se toma para una Entrada «Registrada» con `purchase_id` y su compra registrada:
  - el gate G1 de #93 dejó ese estado en 0 al migrar;
  - ningún código vuelve a escribir `inbound_orders.purchase_id` (`legacy_1a1.log`).

  Se mide en producción (§C5, G3) y no se toca. Si G3 no da 0, el plan vuelve a QA antes de construir.

---

# C. Tests, plantado, gates y evidencia (A + B)

## C1. Tests nuevos

Van en la clase `TestReliquidarYPuertasDeLaCompraDeEntrada`, dentro de `tests/test_sac_entrada_sin_proveedor.py`, con sus fixtures y helpers. No va en un archivo aparte que importe con `*`: el `*` arrastra los 93 tests del módulo, medido en `mecanismo.log` (94 passed).

**Parte A**

| Test | Escenario | Qué se afirma |
|---|---|---|
| **T1** | Cambia la cantidad: 100 → 102 kg a $1.000, pesado 100 | Misma compra (id y número); `total_amount` == Σ líneas == 102.000; saldo del proveedor −102.000; estado de cuenta (#55): saldo corrido == saldo vivo == −102.000; movimiento de compra 102 kg a costo 1.000; descuadre −2 valorado; stock liquidado del material |
| **T2** | Cambia el precio: 100 kg, $1.000 → $1.100 | Total 110.000; saldo −110.000; `unit_cost` del movimiento 1.100; promedio; #55 |
| **T3** | Sale una línea de la compra: A y B en el slot 1 del proveedor 1 → B al slot 2 del proveedor 2 | La compra 1 pasa de {A,B} a {A} por `update`; su total = solo A; la compra 2 nace; saldos de los dos proveedores exactos; #55 en los dos |
| **T3b** | Un material ENTRA a una compra que ya existe (el opuesto de T3; C3 de QA 2). Primera liquidación: A al slot 1 del proveedor 1 y B al slot 2 del proveedor 2. Segunda: A y B al slot 1 | La compra 1 pasa de {A} a {A,B} por `update`: misma compra (id y número), total = A + B. La compra 2 queda cancelada (sobrante, `from_inbound`) y el saldo del proveedor 2 en 0. El movimiento de inventario de B queda en la compra 1, a su costo. #55 en los dos proveedores. Con el bug, la colección vieja tiene MENOS líneas y el total queda corto |
| **T4a** | Primera liquidación sin contado; segunda con cantidad cambiada, contado y una retención chica, menor que los dos totales | El `MoneyMovement` de pago == total nuevo − retención (montos a mano); la caja y el proveedor exactos. **Este test cubre el §6 del barrido de QA 2, el contado después del arreglo** (O2): con el arreglo el pago nace con el neto correcto, así que el residuo no puede nacer, y no hace falta un test aparte |
| **T4b** | Solo el tope de la retención (C2 de QA 2). Primera liquidación: 100 kg × $1.000 = 100.000, sin retención. Segunda: 120 kg × $1.000 = 120.000, con una retención de 105.000, que cae estrictamente entre el total viejo y el nuevo | **200**; la fila de retención con 105.000; proveedor −15.000 (−120.000 + 105.000, acreditado neto, #75); la entidad de la retención −105.000; #55 en el proveedor. Con el bug: 422 «debe ser menor al total de la compra ($100000.00)», medido por QA 2 en su S4. Una retención menor que los dos totales pasaría con y sin el arreglo, que es lo que tenía la v1.0 |
| **T5** | Segunda liquidación con cantidad cambiada e IVA | `document_taxes.base_amount` == subtotal nuevo; proveedor −(subtotal + IVA); entidad IVA exacta |
| **T6** | Reuso sin cambios: firma igual | `update` NO se llama (espía); totales y saldos exactos. Control de que A no toca el camino de reuso |
| **T7a** | Contrato, a nivel servicio, sobre una compra DIRECTA: cargar la compra y sus líneas, llamar `update(commit=False)` con líneas nuevas | `p.lines` == líneas nuevas (cantidades y precios); `p.total_amount` == Σ `p.lines` |
| **T7b** | Contrato, comisiones: ídem con `commissions` | `p.commissions` == las nuevas |
| **T8** | Dos compras: el slot 1 cambia y el slot 2 queda igual | La del slot 1 pasa por `update` y la del slot 2 se reusa; los dos totales y saldos exactos |
| **T16+** | Se extiende `test_t16_slots_son_identidad` (test_sac_reparto_por_compra.py) | Además de estados y slots, el total de las compras 1 y 3 == 150 × precio y los saldos de sus proveedores. Es el test que ya pasaba por el bug sin mirarlo (A1) |

**Parte B**, todo leído por HTTP salvo T13:

| Test | Escenario | Qué se afirma |
|---|---|---|
| **T9** | El caso de QA 1: liquidar la Entrada, desliquidarla, `PATCH /purchases/{p1}/liquidate {}` | **400** que nombra «Entrada #N». Nada escrito: compra `registered`, saldo del proveedor 0, tránsito igual que tras desliquidar, Entrada «Revisada». Y re-liquidar la Entrada **con el MISMO reparto** da **200**: no queda trabada. Como el reparto es el mismo, la compra se reusa y `update` no se llama (por eso T9 no cae con P10) |
| **T10** | Par de T9: en una organización con flag que YA tiene una Entrada liquidada con sus compras, una compra DIRECTA registrada | `PATCH /purchases/{id}/liquidate` → 200; total y saldo exactos, como hoy. La Entrada en la misma organización es lo que hace que el par discrimine también un guard que mire la organización en vez de la compra (P8) |
| **T11** | El caso de QA 2: con la Entrada desliquidada, `PATCH /purchases/{p1}` (a) con otro proveedor y (b) con otra cantidad | **400** que nombra «Entrada #N» en los dos. Nada escrito: proveedor, líneas y tránsito iguales. Y re-liquidar la Entrada con el reparto guardado da **200** con el total exacto |
| **T12** | Par de T11: editar una compra DIRECTA registrada, en una organización que YA tiene una Entrada liquidada (como T10) | 200, como hoy |
| **T13a** | Servicio: `purchase_service.liquidate(..., commit=False)` **sin** `from_inbound` sobre una compra de Entrada desliquidada | `HTTPException` 400. Distingue «la excepción es el kwarg» de «la excepción es `commit=False`» |
| **T13b** | ídem con `purchase_service.update(..., commit=False)` | 400 |
| **T14** | Re-semántica de `test_edit_derived_purchase_allowed` → `…_blocked` | El mismo escenario de #75 D7b da 400 que nombra la Entrada. Es la reversión de D7b, a la vista (D1) |

**Notas sobre los asserts:**
- Todos los montos se comparan con números a mano, no con `total_amount`: un `total == Σ` cuadra aunque los dos lados estén viejos.
- T1 y T2 afirman además que el número cambió respecto de la primera liquidación. Es la guarda anti-vacuidad: un test donde lo viejo y lo nuevo valen igual no mide nada (#110).
- Los «nada escrito» de T9 y T11 se leen después del rollback del endpoint, con `expire_all`.

## C2. Plantado

La matriz se commitea con el plan, antes de plantar. Las predicciones van escritas aquí y no se reescriben. «Al menos» marca un defecto en una vía compartida (#105).

| P | Defecto plantado | Caen (predicción) | No caen |
|---|---|---|---|
| P1 | Quitar el `db.expire(...)` entero (el código de hoy) | T1, T2, T3, T3b, T4a, T4b, T5, T7a, T7b, T8, T16+ | T6, T9–T14 |
| P2 | Expirar solo `"commissions"` | T1, T2, T3, T3b, T4a, T4b, T5, T7a, T8, T16+ | T6, T7b, T9–T14 |
| P3 | Expirar solo `"lines"` | T7b | todos los demás (declarado: las comisiones no pesan fuera del contrato) |
| P4 | Quitar el `expire` y poner `synchronize_session="fetch"` en los DELETE de 3c/3d | al menos T1, T2, T3, T3b, T7a (predicción: no arregla la colección) | T6, T10, T12 |
| P5 | Mover el `expire` a la rama `commit=True` (fuera del `else`) | igual que P1 | T6, T9–T14 |
| P6 | Quitar el guard de `liquidate` (el código de hoy) | T9, T13a | todos los demás |
| P7 | `inbound_order.py:962` sin `from_inbound=True` | **toda liquidación de Entrada, también la primera y también en el setup**: T1, T2, T3, T3b, T4a, T4b, T5, T6, T8, T9, T10, T11, T12, T13a, T13b, T14, T16+, y al menos el resto de las suites de Entradas. El puente se graba con el `flush` de la l.925, antes de la l.962, así que el guard encuentra la Entrada desde la primera liquidación (medido por QA 2, `p7_probe.txt` c000a929) | T7a, T7b |
| P8 | El guard de `liquidate` no mira la compra: el helper sin el filtro `purchase_id`, con `.limit(1)`, conservando el mensaje con ese número. En rigor mira la BASE entera, no la organización; en un test es lo mismo, porque conftest recrea el esquema por test (conftest.py:84–131; O5 de QA 2) | T10, y dentro de la matriz solo T10. Al menos: fuera de la matriz, cualquier test que liquide una compra directa en una base que tenga una Entrada | todos los demás. T9 y T13a siguen en 400 con el número correcto, porque su base tiene una sola Entrada |
| P8b | Lo mismo que P8, en el guard de `update` | T12, y dentro de la matriz solo T12 (al menos, igual que P8) | todos los demás. T11, T13b y T14 siguen en 400 |
| P9 | Quitar el guard de `update` | T11, T13b, T14 | todos los demás |
| P10 | `inbound_order.py:886` sin `from_inbound=True` | T1, T2, T3, T3b, T4a, T4b, T5, T8, T16+: toda re-liquidación con el reparto cambiado da 400. Al menos: también los tests existentes que re-liquiden con el reparto cambiado | T6, T7a, T7b, T9, T10, T11, T12, T13a, T13b, T14: no re-liquidan con el reparto cambiado (T9 y T11 re-liquidan con el MISMO) o no pasan por la l.886 |
| P11 | La excepción atada a `commit=False` en vez del kwarg (`if commit and linked: raise`) en `liquidate` y en `update` | **T13a, T13b y solo esos** | todos los demás (por HTTP, el endpoint usa `commit=True` y la Entrada `commit=False`, así que los dos criterios coinciden) |

Además:
- **Contraste (como el P4c de #109):** T1 con el reparto IGUAL en la segunda liquidación pasa también con P1. Eso demuestra que el cambio de cantidad es la premisa del test y no decoración. Se corre una vez con P1 y el log lo muestra.
- **P7 y P8 en la v1.0 estaban mal, y los dos los corrige la v1.1.**
  - P7 decía «toda re-liquidación con compra viva» y ponía T13a y T13b en «No caen» (C1 de QA 2).
  - En P8, mi «400 siempre» perdía el número de la Entrada en el mensaje y habría tumbado también T9, que la v1.0 ponía en «No caen».
  - Además, la variante realista, un guard que mira la organización y no la compra, no la detectaba un T10 sin Entrada en su organización.
  - Por eso T10 y T12 llevan ahora una Entrada liquidada en su misma organización, y P7 también los tumba en el setup. Su «No caen» queda en T7a y T7b, una celda menos que la que escribió QA 2 sobre la v1.0.
- Los defectos se plantan sobre una copia del árbol, respaldada por ruta y con cierre por hash (`PYTHONDONTWRITEBYTECODE=1`, memoria `plantado-pyc-cache`).

## C3. Gates (flujo con QA del repo)

1. Plan → GO de QA 2 → el Coordinador lo lleva a Daniel (D1, D2) → construcción.
2. **Construcción.** El autor corre:
   - ruff sobre lo tocado y los tests nuevos;
   - `mecanismo.log` repetido sobre el árbol arreglado, donde `refresh ANTES` debe dar `lines=[102]`;
   - en el front: `tsc`, eslint (techo 37) y `build`.
3. **QA pasada 1.** El patch con su sha256, la base y el sha de cada archivo. Desde ahí el árbol queda quieto.
4. **Dirigidas, por grep** (regla (a)). El set sale del comando de `dirigidas_set.log`, re-corrido sobre el árbol final y escrito en el log con su comando. Hoy da 19 archivos más `test_purchase_retentions.py`, e incluye `test_sac_reparto_por_compra.py` (guard de `cancel`, T16+) y `test_inbound_orders.py` (T14). Más las 3 guardas del árbol (regla (b)): `test_reloj_de_negocio.py` (escanea `frontend/src`), `test_advisory_locks.py` y `test_crucible_charges.py`. La predicción del conteo se escribe antes, con `--collect-only`.
5. **Plantado** contra la matriz del §C2.
6. **Capturas a 1440 y 390.** El par en `PurchaseDetailPage`: una compra de Entrada desliquidada, sin «Editar», «Liquidar» ni «Cancelar» y con el enlace a la Entrada, y una compra directa registrada, con los tres. Lo mismo en el menú de acciones de `PurchasesPage`, la ruta viva aunque en SAC esté oculta del menú lateral.
7. **Golden: no aplica, medido** (`golden_aplica.log`, 1a21399a…5b2). Las 14 rutas de `CAPTURES` y el estado de cuenta (`/money-movements/third-party/{id}`) son GET.
   - A vive solo en la rama `commit=False` de `purchase.update`, cuyo único llamador es `POST /inbound-orders/{id}/liquidate`, que no se captura.
   - B vive en `PATCH /purchases/{id}` y `PATCH /purchases/{id}/liquidate`, tampoco capturados. En organizaciones sin filas en la puente, su único efecto es un SELECT (B2).

   Un golden aquí daría «0 diffs / 0 aditivas», el resultado que #110 mostró que no distingue nada.
8. **Suite completa:** diferida al checkpoint (regla del 19-nov). Parity check: no aplica, porque no hay cambios de esquema.
9. **Pantalla, para Daniel en localhost:**
   - A: liquidar una Entrada, revertir, cambiar una cantidad, re-liquidar, y ver que el total del detalle de la compra y el saldo en el estado de cuenta del proveedor cuadren con las líneas;
   - B: con la Entrada desliquidada, abrir su compra y ver que no hay «Editar», «Liquidar» ni «Cancelar».
10. **QA pasada 2** → OK de commit → commit en la rama → el Coordinador integra. Push y deploy, con el OK de Daniel.

**Lo que cambia en producción:**
- el `else` de `purchase.update`;
- el guard en `purchase.liquidate` y `purchase.update`, con el helper compartido con `cancel`;
- dos kwargs en las llamadas de la Entrada;
- el texto de un 422 de la Entrada;
- tres condiciones en dos pantallas.

Sin migración y sin datos. Para Costa y Meta, byte a byte (B2).

## C4. Evidencia de este plan

| Archivo | sha256 | Qué es |
|---|---|---|
| `medicion/mecanismo.log` | a151bef3…be4 | El mecanismo de A |
| `medicion/test_zz_mecanismo_coder2.py` | d7d5b321…e6d | El test temporal, ya borrado del árbol |
| `barrido_deletes.log` | b2890bbc…29e | Los 23 + 1 + 6 sitios (A3) |
| `golden_aplica.log` | 1a21399a…5b2 | CAPTURES contra los llamadores (C3) |
| `cobertura/cobertura.log` y `llamadas_update.txt` | (en la entrega) | La predicción de 0 que dio 2 (A1). La r1 quedó interrumpida (~1 h con `tests.lock`) y se conserva como `*_r1_INTERRUMPIDA*` |
| `puertas_compra.log`, `puente_escritores.log`, `editar_derivada_dependencias.log`, `legacy_1a1.log` | (en la entrega) | B1, el byte a byte de B2, D1 y G3 |
| `dirigidas_set.log` | (en la entrega) | El set dirigido de hoy |
| `plan_v1.0_cf9ee693.md` | cf9ee693…2b21 | La v1.0, base del delta de esta v1.1 |
| `lecturas-prod/g1_g3.log` | ae6d2245…510e | G1–G3 del §C5, leídas por el Coordinador |

## C5. Lecturas de producción para el Coordinador, solo GET y antes de construir

| | Qué se lee | Predicción | Si no da la predicción |
|---|---|---|---|
| **G1** | Por organización, cuántas compras tienen `inbound_order_id` no nulo (`GET /purchases`, paginado con `len == total`) | 0 en Costa y en Meta | el argumento byte a byte de B2 se cae: vuelve a QA |
| **G2** | En SAC, compras vivas (`registered`/`liquidated`) cuya Entrada está anulada, y compras `liquidated` cuya Entrada no lo está (el estado de QA 1) | 0 y 0 | se resuelve antes del deploy con la salida de B2 |
| **G3** | En SAC, Entradas tipo compra con `purchase_id` no nulo (legacy 1:1), con su estado y el de su compra | 0, o solo `liquidated`/`annulled` | si hay alguna «Registrada» con compra `registered`, la rama legacy de las pantallas chocaría con el guard: vuelve a QA |

**Resultado** (23-nov, `lecturas-prod/g1_g3.log` ae6d2245, script `g1_g3.py` ab76e220, EXIT=0): las tres dan la predicción.
- G1: Costa 0 de 3838, Meta 0 de 282, Pacífico 0 de 128; SAC 153 de 153.
- G2: 0 y 0. Como control, las 153 compras con Entrada están `liquidated`.
- G3: 0 de 152 Entradas tipo compra, leídas por detalle.
