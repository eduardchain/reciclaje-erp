# Backlog — recorrido manual SAC (2026-09-08)

Hallazgos de la prueba manual guiada sobre la SAC de desarrollo, con la base reseteada a
maestros y cero transacciones (`seed_sac_org.py --reset --apply`). Se anotan a medida que
aparecen; ninguno se corrige durante el recorrido.

Convención: 🔴 defecto · 🟠 duda de diseño · 🔵 observación

---

## 1. 🔴 El listado de Tesorería muestra el código crudo del tipo de movimiento

**Qué se ve.** En la lista de movimientos, la columna *Tipo* dice `internal_maquila_income` y
`internal_maquila_expense` — el identificador interno, en inglés y con guiones bajos.

**Diagnóstico — las etiquetas SÍ existen, en el lugar equivocado.**

```
frontend/src/pages/treasury/MovementDetailPage.tsx:23-24
  internal_maquila_expense: "Maquila Intersede (Gasto sede origen)"
  internal_maquila_income:  "Maquila Intersede (Ingreso sede destino)"

frontend/src/types/money-movement.ts
  → 0 ocurrencias de internal_maquila
```

O sea que abrir el detalle del movimiento muestra una etiqueta correcta en español y volver
al listado muestra el código crudo. La diferencia es de dónde lee cada pantalla:
`TreasuryPage.tsx:150` hace `typeLabels[tipo] ?? tipo` contra el mapa **compartido**, que no
los tiene; el detalle define los suyos **localmente**.

**Causa.** Los dos tipos entraron con #84 (traslados E3.1) y no se agregaron al mapa
compartido. La convención del repo es sumar la etiqueta en los **5 mapas duplicados** — #86
y #88 lo hicieron para sus tipos nuevos; #84 lo hizo solo en el detalle.

**Alcance.** Solo afecta a SAC: son los únicos dos tipos sin etiqueta compartida y solo se
emiten con `two_step_transfers_enabled`. Las otras seis organizaciones no los ven nunca.

**Arreglo.** Mover las dos etiquetas al mapa compartido y borrar las locales del detalle
(si quedan las dos copias, vuelven a divergir). Verificar de paso si hay otros tipos del
catálogo sin etiqueta — el `?? tipo` los oculta a todos por igual.

---

## 2. 🔴 `MoneyMovementType` no incluye los dos tipos de maquila

**Qué pasa.** La unión de TypeScript en `types/money-movement.ts` declara el conjunto cerrado
de tipos válidos y **no contiene** `internal_maquila_expense` ni `internal_maquila_income`,
aunque el backend los devuelve.

**Por qué importa más que la etiqueta.** El tipo *miente sobre el runtime*: promete un
conjunto que la API excede. `tsc` pasa en verde porque nadie hace un `switch` exhaustivo
sobre esa unión — o sea que la protección que el tipo aparenta dar no existe. Es la misma
familia del bloqueante (b) de #93 (`Decimal` serializado como string mientras el tipo decía
`number`), que ningún gate atrapa.

**Arreglo.** Sumar los dos a la unión junto con las etiquetas del punto 1.

---

## 3. 🟠 El KPI "Total movimientos" suma las dos patas del par interno

**Qué se ve.** Tras recibir un traslado que cruza sede, el KPI dice **$91.800** con 2
operaciones — las dos patas de un par de $45.900 que **netea cero**. Ningún peso se movió:
las dos tienen `account_id = NULL`.

**Por qué es dudoso y no claramente un defecto.** El KPI se llama "Total movimientos" y hace
literalmente eso: suma los montos de la lista. La pregunta es si un par interno debería
contar dos veces en un total que un usuario lee como *"cuánta plata se movió"*.

**Cuidado antes de tocarlo.** El KPI es genérico para los 48 tipos del catálogo y lo ven las
siete organizaciones. Cualquier cambio ahí es superficie compartida y necesita golden.
Alternativa barata: dejar el total y agregar la aclaración de que incluye causaciones sin
cuenta.

---

## 4. 🔵 Las tarjetas HORNO y CRISOL de Plomo (kg) muestran 0 y siempre lo harán

**Qué se ve.** La página Plomo (kg) muestra cuatro tarjetas: `WILLARD`, `INTERSEDE`, `HORNO`
y `CRISOL`. Las dos últimas dicen 0 kg.

**Por qué es un riesgo de expectativa.** No hay servicio, endpoint ni siembra que escriba en
esas cuentas — verificado: `plant_process.py` lo importa **solo** `models/__init__.py`, o sea
únicamente para crear las tablas. Las tarjetas van a decir 0 para siempre.

Puesto en los zapatos de Johana entrando por primera vez, la lectura natural es *"todavía no
hemos cargado el horno"*, no *"esto no existe"*. Ya está registrado en el canon como
superficie configurable sin consumidor; se anota acá porque el recorrido lo hizo visible en
pantalla, que es distinto a saberlo por documentación.

**Opciones.** Ocultar las dos tarjetas hasta que el circuito de planta exista, o marcarlas
explícitamente como no disponibles. La decisión es de producto, no técnica.

---

## 5. 🔴 La salida a Willard acepta cualquier tercero — y el backend tampoco lo valida

**Qué se ve.** El selector *Tercero (Willard)* de una salida lista **todos** los terceros
activos: Green Loop, los PRUEBA-*, y Willard. En Entradas esto ya está resuelto — el tercero
queda **fijo al titular de la cuenta kg** y el campo va deshabilitado (#80, addendum).

**Y no es solo la pantalla.** `_validate_third_party` (`willard_delivery.py:840`) valida
únicamente que el tercero exista, sea de la organización y esté activo. No comprueba que sea
el titular de la cuenta kg.

**Consecuencia con plata de por medio.** Las cuentas en kg se resuelven por
`account_type` (`_discharge_kg` → `_resolve_kg_account`), **no** por el tercero del
documento. Entonces una salida registrada contra Green Loop:

- descarga la deuda en kg **de Willard** (cuentas correctas),
- factura la maquila y el flete **a Green Loop** (`third_party_id=delivery.third_party_id`,
  línea 534),
- y en una venta pondría a Green Loop como cliente de la `Sale` derivada.

⚠️ **Corregido al planear (QA de SAC):** ese tercer punto **no es defecto**. Una venta a Green Loop
es una venta legítima —`_require_customer` ya exige behavior `customer`— y desde CC-009 la venta no
factura maquila ni flete a nadie. **El daño financiero silencioso existe solo en los dos abonos.**

O sea: se salda la deuda de uno y se le cobra a otro, sin ningún aviso.

**Arreglo.** Espejo de lo que ya se hizo en Entradas: derivar el tercero del titular de la
cuenta kg, deshabilitar el campo, y defender en el backend con un 422 que nombre al tercero
correcto. El frontend solo no alcanza — la API queda abierta.

---

## 6. 🔴 Una salida registrada no se puede editar desde la pantalla, solo anular

**Qué pasa.** Si se registra una salida sin peso de báscula, *Revisar* la rechaza — correcto.
Pero el detalle **no ofrece botón Editar**: las únicas acciones son *Revisar* y *Anular*. El
usuario queda en un callejón sin salida y tiene que anular y volver a capturar.

**Y el backend sí lo permite.** `willard_delivery.update` (`:114`) acepta la edición mientras
el estado no sea `liquidated` ni `annulled` — o sea que una `registered` es perfectamente
editable por API. Es un hueco de la pantalla, no del modelo.

**Comparación.** La Entrada equivalente sí tiene *Editar* en el mismo estado. Las dos
superficies deberían comportarse igual.

---

## 7. 🟠 El paso "Revisada" en salidas certifica un peso que ningún cálculo usa

**Dos cosas que apuntan al mismo lugar.**

**(a) Johana dijo que las salidas no necesitan revisión** — de registro directo a liquidación
(reportado por Daniel en el recorrido del 8-sep; **pendiente de confirmar por escrito**).
W1 construyó tres pasos espejando Entradas, sin que esa decisión esté documentada.

**(b) El peso de báscula no alimenta nada.** `_compute_lead_kg` (`:278`) calcula los kg de
plomo como `cantidad × factor de la fórmula`. El peso de báscula **no entra**: ni al kg, ni al
inventario, ni a la factura. Es un dato certificado sin consumidor, igual que en Entradas
(#95 lo dice explícitamente), pero acá el paso que lo exige es el único motivo de existir de
ese estado.

**Por qué el argumento de Entradas no se traslada.** Ahí el revisor certifica **lo que llegó
de un tercero** y eso da paso a crear deuda y plata. En una salida SAC es quien despacha: no
hay reclamo de contraparte que certificar en ese momento. El peso sí tiene sentido **de
negocio** (prueba de lo despachado ante Willard), pero hoy no lo consume nadie.

**Decisión de producto, no técnica.** Si Johana confirma, el paso se elimina y el peso pasa a
ser opcional en la liquidación. Va junto con la pregunta de si el peso debe alimentar algo.

---

## 8. 🔴 La bodega de origen de una salida siempre es la planta, y el selector ofrece las seis

**Qué se ve.** El campo *Bodega de origen* lista las seis bodegas de la organización. Solo
una es válida.

**El backend sí defiende.** `_validate_plant_origin` (`:805`) corre en `create` **y** en
`update`, para **los tres tipos** de salida, y exige que el origen sea exactamente
`willard_sede_drosses` (Juan Mina en SAC). Cualquier otra da 400 con un mensaje que además
explica qué hacer: *"Trasládelo primero y despache desde allí"*.

**Por qué sigue siendo un defecto.** Que la regla sea constante y esté defendida es
justamente el argumento para no preguntarla: se le está pidiendo al usuario que descubra por
ensayo y error un valor que el sistema ya conoce. Con seis opciones, cinco llevan a un error.

---

## 9. 🟠 El patrón: Salidas no aplica el "campo determinado = campo bloqueado" que Entradas sí usa

Los hallazgos 5 y 8 no son dos defectos sueltos — son el mismo. El formulario de Salida tiene
**dos campos cuyo valor correcto está determinado por la configuración de la organización** y
los presenta como selectores libres:

| Campo | Valor correcto | ¿Backend defiende? | Si el usuario se equivoca |
|---|---|---|---|
| Tercero (Willard) | Titular de la cuenta kg | **No** (hallazgo 5) | Descarga la deuda de Willard y factura a otro |
| Bodega de origen | `willard_sede_drosses` | Sí, 400 (hallazgo 8) | Fricción: error que se entiende |

**Entradas ya resolvió esto** en #80 (B2 + addendum): la sede se deriva del mundo Willard y el
tercero queda fijo al titular de la cuenta kg, ambos deshabilitados en pantalla y defendidos
en backend. Salidas se construyó después y no heredó el patrón.

**Cómo abordarlo.** Como un solo trabajo sobre el formulario de Salida, no como dos parches.
El de la bodega es cosmético (molesta); el del tercero necesita además la defensa de backend
(es el único con consecuencia financiera silenciosa).

---

## 10. 🔴🔴 EL MÁS GRAVE — una salida a Willard acepta cualquier material, y se factura maquila por fundir lo que no se fundió

**Detonante.** Daniel, durante el recorrido: *"Johana dijo que a Willard solo se le abona
plomo crudo o plomo fino, ¿cómo es posible que tengamos una salida con otros materiales si no
es venta regular?"*. Pregunta hecha desde el modelo del negocio, no desde la pantalla.

**Reproducción exacta (Entrada #2 → Salida #4 de la SAC de dev):**

```
Entró   1.000 kg de MR02 GUARRU SECO de Willard   →  deuda drosses  +720 kg
Salió   1.000 kg de MR02 GUARRU SECO como abono   →  deuda drosses  −720 kg
```

El mismo material entró y salió sin transformarse. **SAC no fundió nada.** Y aun así el
sistema emitió:

- `service_income_accrual` **$1.509.840** de maquila a Willard — el cobro *por fundir*
- `service_income_accrual` **$26.640** de flete
- par `internal_maquila_*` de **$1.080.000** abonado a planta *por el trabajo que no hizo*

**Se facturó un servicio que no ocurrió**, sin un solo aviso.

**Por qué el sistema lo permite — la heurística está invertida.** `_compute_lead_kg` (`:278`):

> *"Sin fórmula el material YA es plomo: la cantidad es el kg."*

Esa regla sirve para **calcular** y se está usando para **clasificar**. Un material con
fórmula `drosses_to_lead` es, por definición, algo de lo que *se extrae* plomo — o sea
justamente lo que **no** puede pagar la deuda. En vez de rechazarlo, el sistema lo convierte.

**Y el reverso es peor.** Materiales activos de SAC **sin fórmula**, que el sistema por lo
tanto trata como plomo puro 1:1:

```
PLO-LIN  PLOMO LINGOTES    ✓        ALU-01   ALUMINIO           ✗
PLO-RET  PLOMO RETAL       ✓        HIE-CHA  HIERRO CHATARRA    ✗
SCR-LCB  SCRAP C/BORNE     ✗ ← se FUNDE, no se entrega        CAJ-PLA  CAJAS PLÁSTICAS    ✗
                                    PP-MOL   PP MOLIDO          ✗
```

Se puede saldar la deuda de plomo de Willard **con cajas plásticas, kilo por kilo**, y
facturarle $2.097/kg de maquila. La aritmética queda perversa: **pagar con plástico rinde
1:1 y pagar con guarru seco rinde 0,72** — el sistema premia usar el material equivocado.

**Fuente — CONFIRMADA con cita textual del cliente.** Hugo Armando Bedoya, transcripción del
**2026-08-28** (la demo donde se le mostró la primera versión del módulo de Salidas), línea
369:

> *"yo cojo un plomo de esos y lo refino, que le hago un proceso adicional y otro lo entrego
> directamente como crudo. El crudo lo entrego o por venta o por abono, eh por batería,
> materiales o venta, **pero el crudo es el que se entrega por eso**"*
>
> *"El puro... yo para hacer el puro necesito tomar de ese plomo crudo, llevarlo a otro
> proceso, hacer un proceso de refinación, sacarle impurezas y ahí sí entregarlo **a la
> venta**"*

O sea: **el plomo crudo es lo que se entrega en las tres modalidades; el puro solo va a
venta.** Coincide con `diagrama 1.jpeg`, que muestra *"Cuenta Plomo a Devolver (Abono)"* como
uno de los cuatro destinos del crudo.

⚠️ **Nota de método.** Una primera búsqueda dio "no encontrado" y se reportó como tal; Daniel
insistió con la reunión exacta y la cita apareció. El grep exigía `(willard|devol|abon)` **y**
`(fino|crudo)` en la misma ventana de 220 caracteres — o sea que **solo podía encontrar lo que
ya se imaginaba que iba a decir**. Tercera vez en el mes que un grep estrecho produce un
"no existe" falso (ver #92, #96 y `verificacion-artefacto-vs-testimonio`). Si el usuario se
hubiera quedado con la primera respuesta, este hallazgo quedaba archivado como "sin fuente"
teniendo cita textual.

**Y en el mismo párrafo Hugo describe tres cosas más que no existen en el código:**

- *"Te faltaría hacer un ítem ahí que sería **salida a crisoles**"* — un cuarto tipo de salida.
- *"cuando Johana te dice que resta la deuda, **no debe restar la deuda**"* — el paso al crisol
  no toca la deuda con Willard (está corrigiendo a Johana en vivo).
- *"cuando se vende el puro **no se afecta ninguna maquila**, se afecta solamente el
  diferencial de 300 pesos"* — la tarifa `maquila_crisol` que hoy no tiene consumidor.

**Dirección del arreglo, con su trampa.** Hace falta una marca explícita de *"este material
es plomo entregable"* — el lugar natural es `material_kg_profiles`, que ya existe por
material. ⚠️ **No reutilizar la heurística de "sin fórmula"**: el aluminio y el plástico
tampoco tienen fórmula. Es exactamente el atajo que causó el defecto.

**Relación con el circuito de planta.** El canon ya sabía que W1 no distingue crudo de puro y
saca del inventario genérico. Esto es un grado más abajo: no distingue **plomo de no-plomo**.
Arreglarlo no requiere esperar al circuito de planta — la marca por material es independiente
y mucho más barata.

---

## Lo que se verificó y está correcto

Se anota para que un ciclo futuro no lo re-pruebe:

| Paso | Verificado |
|---|---|
| Entrada Willard registrada | Estado *Registrada*, sin inventario, sin kg, sin pesos |
| Guard del peso de báscula | Bloquea *Marcar Revisada* sin peso, nombrando el material |
| Liquidación de la entrada | +51 kg en `willard_baterias/CV`, inventario a **costo $0**, cero movimientos de dinero |
| Traslado intra-sede (CV → Molino) | Un solo paso, nace *Recibido*, `Kg plomo: N/A`, maquila `—` |
| Despacho a otra sede | Solo movimiento físico a tránsito: **cero kg, cero pesos** |
| Recepción | 6 u × 5,1 = **30,6 kg** a intersede, maquila **$45.900**, par gasto/ingreso sin cuenta ni tercero |
| Aislamiento | `willard_baterias` intacto en 51 kg durante todo el traslado |
