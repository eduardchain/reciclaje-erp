# Plan — Liquidar por peso en la Entrada (precio por kg)

**Origen**: reunión con Hugo 12-ago. Es una **corrección de #95 D8**, no una funcionalidad nueva:
construí el resultado de lo que pidió y me salté el insumo, y con eso se perdió justo lo que él
objetó.

---

## 1. Lo que Hugo pidió, y lo que se construyó

Textual (12-ago, 00:04):

> *"Pero Johana en esa liquidación en específico no le va a pagar 100 unidades, sino que le va a
> pagar **por peso**. […] Me entendí que tú cogerías y **multiplicarías kilos por el valor**. […]
> pero que **no había trazabilidad de lo que yo estoy liquidando**. Estoy colocando el precio total
> de la liquidación, pero **no el peso ni el precio unitario**. […] Habría que ponerle acá peso de
> baterías […] así como vas a colocar la de los proveedores, **que si se va a liquidar por peso o
> por unidad**."*

Y más adelante, sobre cómo aterriza en inventario:

> *"yo voy a liquidar por precio, pero en el inventario van a ingresar por unidades y **se deben
> costear por unidad**"* — con la fórmula *"costo total dividido unidades"*.

**Lo que #95 D8 dejó**: Johana digita el **valor total** y el sistema deriva el unitario. La fórmula
`total ÷ unidades` es correcta y Hugo la confirmó — esa mitad **no se toca**.

**Lo que falta**: el modo en que ella digita **$/kg** y el sistema multiplica por el peso. Hoy tiene
que hacer esa multiplicación de cabeza, y el sistema guarda `$100.000` sin registrar que salió de
`100 kg × $1.000/kg`. Eso es exactamente la falta de trazabilidad que Hugo nombró **antes** de que
yo lo construyera.

**La pieza que ya está esperando**: el peso de báscula se captura por línea y se **certifica al
revisar** (#95 Q-13), y hoy —por decisión explícita, documentada en el canon— **no entra a ningún
cálculo**. Este es su consumidor natural: el total sale de un dato auditado por el revisor, no de
una cuenta a mano.

---

## 2. Decisiones

### D1 — Un tercer modo por asignación, no un reemplazo

`InboundAllocationCreate` pasa de XOR de 2 a **XOR de 3**: `unit_price` | `total_price` |
`price_per_kg`. Exactamente uno.

| Modo | Johana digita | El sistema deriva |
|---|---|---|
| Por unidad | $10.000 c/u | total $100.000 |
| Por valor total | $100.000 | $10.000 c/u |
| **Por kg** *(nuevo)* | **$1.000/kg** | peso 100 kg → total $100.000 → $10.000 c/u |

**El modo nuevo desemboca en el existente**: calcula `total_price` y de ahí cae en la fórmula de #95
sin tocarla. Consecuencia que vale nombrar: la firma de re-liquidación de #93 compara
`(material, cantidad, unit_price)` y el `unit_price` se deriva igual que hoy → **la firma no cambia
y el revert-and-reapply no se dispara de más**. No hay que verificarlo caso por caso; es la misma
salida.

### D2 — El estimador es kg/unidad de la línea, y el peso de la asignación se prorratea

```
estimador   = linea.scale_weight_kg / linea.quantity        (kg por unidad)
peso_asig   = estimador × asignacion.quantity
total       = peso_asig × price_per_kg
unit_price  = total / asignacion.quantity        ← fórmula #95, sin cambios
```

Decisión de Daniel (2026-08-28): **se estima, el prorrateo hace sentido**. El peso se captura por
línea y el precio por asignación, así que cuando una línea se reparte entre dos proveedores hace
falta repartir el peso. La alternativa —pesar cada lote por separado— es el dato correcto pero
cambia lo que hace el pesador, y la operación no lo hace.

⚠️ **El denominador es `linea.quantity` (lo pesado), NO la suma de las asignaciones.**

**El argumento que lo decide es la independencia entre asignaciones**, y aplica al caso normal, no a
un borde (afinado por QA — el mío, el del sobre-reparto, convence menos porque alguien puede decir
*"ese caso no pasa"*):

> Con `sum(allocations)` como denominador, **agregar un segundo proveedor cambia en silencio el pago
> del primero**. Johana asigna 6 unidades a A → suma 6 → A paga `6 × (100/6) = 100 kg`. Después
> agrega 4 a B → suma 10 → A pasa a pagar 60 kg. El pago de A cambió porque apareció B, y A ya tiene
> su compra y su factura.
>
> Con `linea.quantity`, el estimador es una propiedad de la **línea** —un hecho físico: *estas
> baterías pesan 10 kg cada una*— y el pago de cada asignación depende solo de su propia cantidad.
> Eso es lo que permite armar el documento por partes sin reescribir lo ya armado.

Los dos bordes salen solos de ese principio, y siguen siendo buenos tests:

- **Reparto parcial** (10 pesadas, 6 asignadas, 4 declaradas de nadie): el proveedor paga 60 kg. Los
  40 restantes son del descuadre, que ya tiene su propio camino (#93 D6/D7). ✅
- **Sobre-reparto** (10 pesadas, 12 asignadas): cada unidad conserva su peso estimado → 120 kg. Con
  la suma de asignaciones se aprietan dentro de los 100 kg pesados y **el precio por kg deja de
  significar lo que dice**. ✅

Por eso el estimador se escribe como *kg por unidad* y no como *proporción del total*: con esa
lectura, tanto la independencia como los bordes son obvios en vez de sorpresivos.

### D3 — Se persisten el precio por kg y el peso usado (es el punto de todo esto)

Dos columnas nullable en `inbound_line_allocations` (**tabla exclusiva SAC → cero riesgo de golden**):

- `price_per_kg` `Numeric(15,2)` — lo que Johana digitó.
- `weight_kg_used` `Numeric(15,3)` — el peso prorrateado con el que se calculó.

El peso es **derivable**, así que persistirlo parece redundante. No lo es, por dos razones:

1. **Es la trazabilidad que Hugo pidió.** El documento tiene que poder decir *"le pagué 60 kg a
   $1.000"*, no reconstruirlo.
2. **#93 D20 conserva el reparto al des-liquidar.** Si el peso solo se derivara, editar la línea
   después cambiaría en silencio la historia de una liquidación anterior. Es el mismo argumento por
   el que #95 persistió `total_price`.

**El encuadre correcto no es "cachear un derivado"** (afinado por QA): el peso estimado es función de
**dos campos mutables** (`scale_weight_kg` y `quantity` de la línea, los dos editables). Guardarlo es
**registrar un insumo de un documento financiero**, igual que `total_price` en #95 — con ese marco la
pregunta *"¿y si se puede derivar?"* se disuelve sola: el total también se puede derivar y se
persiste por lo mismo.

⚠️ **Modo de falla a cubrir**: si la pantalla **recalcula** en vez de leer lo persistido, va a mostrar
un número distinto al guardado cuando la línea se editó después. Regla de #95: **lo persistido es la
verdad y la pantalla lo lee, no lo re-deriva.**

`total_price` se sigue persistiendo también (queda calculado, no digitado) — así las tres modalidades
dejan el mismo rastro y la pantalla no tiene que saber cuál fue.

### D4 — El modo por kg se ofrece SIEMPRE (corregido por QA)

🟠 **Mi versión anterior tenía un agujero.** Decía: en materiales por kg no se ofrece, porque
`$/kg × peso = precio × cantidad` lo vuelve el modo unitario con otro nombre. Eso vale **solo si
`peso == cantidad`, y el código no lo garantiza**:

```python
if line.scale_weight_kg is not None and line.scale_weight_kg > 0:
    continue                                  # ← un peso digitado se PRESERVA
if unit == "kg":
    line.scale_weight_kg = line.quantity      # solo si faltaba
```

O sea que un material en kg **puede tener peso ≠ cantidad**: se declaran 100 kg y la báscula dice 98.
Eso no es un borde raro — **es la diferencia de báscula, que es precisamente para lo que existe el
peso certificado**. Y ahí los dos modos no dan lo mismo: por unidad se paga sobre 100 declarados, por
kg sobre 98 pesados. El que Hugo pidió (*"no le va a pagar 100 unidades, le va a pagar por peso"*) es
el segundo.

**Se ofrece siempre.** Cuando el peso coincide con la cantidad el resultado es idéntico, así que no
confunde; cuando difiere, es el único modo que expresa lo que Johana quiere pagar. Se descarta la
alternativa de ofrecerlo solo si `scale_weight_kg != quantity`: es más precisa pero hace que el
formulario cambie de opciones según los datos, y eso se explica peor.

### D4b — El guard va en el DENOMINADOR, no en el peso (afinado por QA)

Las líneas de truncamiento (#93 D5) nacen con **`quantity = 0`** y **`scale_weight_kg = NULL`** — son
**dos campos distintos**, y mi versión anterior los confundía en un solo "cantidad pesada 0".

Hoy los dos coinciden, pero **solo por el orden**: esas líneas se crean en la liquidación, después de
la revisión, así que nunca pasan por `_require_scale_weights`. Eso es una propiedad del flujo, no un
invariante — y un guard que descansa en el orden se rompe el día que alguien lo cambia.

**El guard honesto es sobre `line.quantity`**: no se pueden estimar kg por unidad sin unidades. Se
chequean **los dos** (cuesta lo mismo) con el mismo mensaje: **422 que nombra el material** y explica
("no tiene peso de báscula: se agregó en la liquidación"), nunca un 500 por división por cero.

### D5 — Sin sugerencia de precio en modo kg, y es una ausencia deliberada

Las listas por proveedor (#98) guardan precio **por unidad del material**. Para una batería, la
lista sugiere $/unidad, no $/kg. En modo kg **no hay sugerencia** — el campo arranca vacío.

No se resuelve inventando una conversión (dividir la sugerencia por el peso estimado daría un número
plausible que nadie eligió, que es justo lo que #98 D3 decidió no hacer). Si Hugo lo pide, la
respuesta es una lista de precios en kg, y eso es un ciclo propio.

### D6 — El "por proveedor" de Hugo queda como preferencia, no como regla

Hugo dijo *"si se va a liquidar por peso o por unidad"* refiriéndose a una marca en el proveedor.
En v1 el modo se elige **por asignación**, igual que hoy el toggle unitario/total. Recordar el modo
preferido de cada proveedor es una comodidad que se puede agregar después sin cambiar nada de lo de
acá — y hacerlo ahora obligaría a decidir qué pasa cuando la marca y lo que digitó Johana no
coinciden, sin evidencia de que haga falta.

---

## 3. Lo que NO cambia

- El inventario entra **por unidad** y se costea por unidad. (Era la pregunta de Hugo y ya estaba
  bien resuelta.)
- La fórmula `total ÷ unidades`, el redondeo `PRICE_Q` y el aviso ámbar del centavo (#95 D8).
- La firma de re-liquidación, el descuadre y su valoración al precio de referencia, las retenciones,
  el pago de contado, la comisión del recolector.
- `ALLOC_Q` (#95 e): la cuantización a gramos sigue **antes** de cualquier cálculo, y ahora también
  antes del prorrateo del peso.

---

## 4. Tests

1. **El caso de Daniel, al pie de la letra**: 10 baterías, 100 kg, $1.000/kg → total $100.000,
   costo unitario $10.000, inventario +10 unidades a $10.000.
2. **Prorrateo entre dos proveedores**: 10 unidades / 100 kg repartidas 6+4 → 60 kg y 40 kg; los dos
   totales cierran contra el peso de la línea.
3. **Prorrateo con precios distintos** por proveedor (que es el caso real): cada uno paga su peso a
   su precio, y el costo promedio del material sale del total combinado.
4. **Borde: reparto parcial** — 6 de 10 asignadas, 4 intencionales: el proveedor paga 60 kg y el
   descuadre se lleva el resto por su camino de siempre.
5. **Borde: sobre-reparto** — 12 asignadas sobre 10 pesadas: 120 kg (el estimador es kg/unidad).
   Test explícito **porque es el que distingue el denominador correcto del incorrecto**; con la
   suma de asignaciones daría 100 y pasaría desapercibido.
6. **Material sin peso ni cantidad** (truncamiento D5) en modo kg → 422 que nombra el material. Dos
   tests, uno por cada guard de D4b (`quantity = 0` y `scale_weight_kg = NULL`), porque hoy coinciden
   por el orden del flujo y el día que se separen hay que saber cuál falló.
6b. **Material en kg con diferencia de báscula** (D4, el caso que QA destapó): se declaran 100 kg, la
   báscula certifica 98 → en modo kg se paga sobre **98**, en modo unitario sobre 100. Es el test que
   prueba que el modo NO es redundante en materiales por kg — sin él, alguien lo "simplifica" de
   vuelta a mi versión equivocada.
7. **XOR de tres**: dos precios juntos → 422; ninguno → 422.
8. **Trazabilidad persiste**: liquidar → des-liquidar → el reparto conserva `price_per_kg` y
   `weight_kg_used` (#93 D20).
9. **Re-liquidar sin tocar nada no dispara revert-and-reapply**: mismo `unit_price` derivado → misma
   firma. Es la propiedad de D1 y conviene clavarla.
10. **No-regresión**: los modos unitario y total siguen byte a byte (ninguna asignación sin
    `price_per_kg` cambia de comportamiento).

**Defectos a plantar** (disciplina de la ronda 3 de W1 — un guard nuevo se verifica plantando el
defecto, incluso si nació hace diez minutos):
- Cambiar el denominador a `sum(allocations)` → caen el test 5 (**120 vs 100**) y el 4 (**60 vs 100**).
  ⚠️ **Verificado, y mi predicción estaba mal**: dije que caería también el 2 (el de independencia) y
  **no cae** — con el reparto completo (6+4=10) la suma iguala lo pesado y los dos criterios dan lo
  mismo. El test 2 clava los números de negocio del caso normal, no el denominador; su docstring lo
  dice explícito para que nadie le atribuya una cobertura que no tiene (es la falla de W1: un test
  cuyo nombre promete más de lo que prueba).
- Quitar cada guard de D4b por separado → debe caer su test, con 500 en vez de 422.
- No persistir `weight_kg_used` → debe caer el test 8.
- Ofrecer el modo kg solo cuando `unit != "kg"` (mi versión equivocada) → debe caer el 6b.

⚠️ **Verificar que caiga por el NÚMERO esperado, no solo que caiga** (QA, y viene de W1): allí el
test del doble conteo pasaba con el defecto plantado porque el modo de falla no era el que decía su
nombre. En el test 5, confirmar que el valor observado es **120 y no 100** — un test que falla por la
razón equivocada da la misma señal verde que uno que prueba lo correcto.

---

## 5. Gates

Migración aditiva sobre tabla **exclusiva SAC**, ningún reporte cambia de forma ni de valor, ningún
camino compartido se toca. Aun así: suite completa, parity check, ruff/eslint/tsc/build, y **smoke
contra la BD migrada** — que es el único gate que ve un `server_default` faltante (lección de W1).

**Golden**: por el mismo argumento que #87 (tabla exclusiva SAC, cero filas en las orgs cliente,
router flag-gated) **no aplica**. ⚠️ Verificar contra `CAPTURES` antes de afirmarlo, no de memoria —
la v1.1 del plan de #98 dio por captura un endpoint que no lo es.

---

## 6. Ronda 1 de QA — cerrada

**GO condicionado**, tres items, los tres resueltos:

| Item | Dónde quedó |
|---|---|
| 🟠 Q3 — el modo kg en materiales por kg | **D4 reescrita**: se ofrece siempre; el argumento viejo asumía `peso == cantidad` y el código no lo garantiza |
| 🟡 El guard va en el denominador + NULL vs 0 | **D4b** nueva, con los dos chequeos y la razón de por qué el del peso descansa en el orden |
| ⚪ El argumento de D2 | Reemplazado por el de **independencia entre asignaciones**, que aplica al caso normal |

**Lo que QA verificó de forma independiente**: la firma de re-liquidación (la propiedad gratis de D1
es real), el autocompletado del peso, que las líneas de truncamiento nacen sin peso, que `ALLOC_Q`
cuantiza antes de todo cálculo, que las listas de #98 guardan $/unidad, y que **el golden no aplica —
contra `CAPTURES`, no de memoria**.

**Mi error en Q3 vale nombrarlo**, porque es de la misma familia que el de la ronda 3 de W1: afirmé
una equivalencia (*"es el modo unitario con otro nombre"*) sin verificar su premisa. Bastaba leer las
cuatro líneas del autocompletado para ver que un peso digitado se preserva. Y el caso que quedaba
afuera no era exótico: era **la diferencia de báscula**, o sea la razón de ser del peso certificado.

---

## 7. Lo que sigue abierto

Nada bloqueante. D5 (sin sugerencia en modo kg) y D6 (el "por proveedor" de Hugo como preferencia
futura) son ausencias deliberadas; si Hugo pide cualquiera de las dos, cada una es su propio ciclo.
