# Informe de construcción — Liquidar por peso en la Entrada (precio por kg)

Plan: `plan-sac-precio-por-kg-entrada.md` (GO condicionado en ronda 1, tres items resueltos antes de
construir).

---

## 1. Lo que se construyó

**Backend**
- `inbound_line_allocations` gana `price_per_kg` `Numeric(15,2)` y `weight_kg_used` `Numeric(15,3)`,
  las dos nullable (migración `b1c2d3e4f5a7`). NULL en ambas = la asignación se digitó por unitario o
  por total, o sea el comportamiento previo byte a byte.
- `InboundAllocationCreate` pasa a **XOR de tres** precios.
- `_total_desde_kg()` — el estimador es **kg por unidad de la línea**, con los dos guards de D4b.
- La rama nueva **desemboca** en la de `total_price`: un solo camino hacia `unit_price`.

**Frontend**
- El toggle de modo pasa de dos a tres y rota `unitario → total → por kg`, **salteando el modo kg**
  cuando la línea no tiene con qué prorratear (sin peso certificado o sin cantidad pesada) —
  ofrecerlo ahí sería ofrecer un 422.
- Cambiar de modo **no pierde el número**: se convierte con la cantidad y el peso vigentes.
- Vista previa en vivo: `60 kg × $1.000 = $60.000 · $10.000 c/u`. Es la trazabilidad de Hugo **antes**
  de guardar.
- El detalle de la Entrada muestra `(60 kg × $1.000)` junto a la asignación, **leyendo lo persistido**.

---

## 2. Lo que apareció al construir y no estaba en el plan

**El mapa de líneas se movió de lugar.** `lines_by_material` se armaba en la fase de validación, que
corre **después** de la normalización de precios. El modo kg necesita el peso y la cantidad de la
línea para prorratear **antes** de que exista un `unit_price`, así que el mapa subió. Es un
movimiento, no una copia: sigue habiendo un solo mapa.

**El peso derivado no se puede colgar del payload.** `InboundAllocationCreate` tiene
`extra="forbid"`, así que asignarle un campo no declarado revienta. Viaja en un dict local con clave
de negocio `(material_id, third_party_id)` — única por D3 (el material aparece una vez) más el
UNIQUE `(línea, tercero)`. No uso `id()` del objeto a propósito: una clave de negocio sobrevive a que
alguien copie la lista.

**La trampa de #95 estaba esperando.** `InboundAllocationResponse` se arma **campo por campo** en el
endpoint: agregar la columna al modelo y al schema **no basta**, el campo llega en `None` a la
pantalla. Por eso el helper de tests lee **por la API** y no por el ORM — con el ORM los tests
pasarían y la pantalla mentiría.

**Dónde NO se precarga el peso.** En el editor de liquidación se precarga `price_per_kg` pero **no**
`weight_kg_used`: ahí el peso tiene que derivarse en vivo porque Johana está cambiando las
cantidades justo en esa pantalla. Lo persistido es la verdad de lo **guardado**, y eso se lee en el
**detalle**. Es la distinción que pidió QA, aplicada a los dos lugares con criterios opuestos y a
propósito.

---

## 3. Verificación contra defectos plantados

Los tres, con el número a la vista — no solo "falla":

| Defecto plantado | Test que cae | Cómo cae |
|---|---|---|
| Denominador = `sum(allocations)` | `test_sobre_reparto...` | `Decimal('100.000') == Decimal('120.000')` ❌ |
| ídem | `test_reparto_parcial` | 100 donde deben ir 60 ❌ |
| Sin el guard del denominador | `test_truncamiento_sin_cantidad_pesada` | `AttributeError` (500) en vez de 422 ❌ |
| No persistir `weight_kg_used` | `test_trazabilidad_sobrevive_el_round_trip` | el peso vuelve `None` ❌ |

### 🔴 Una predicción mía que salió mal, y es la lección de W1 otra vez

El plan decía que el defecto del denominador haría caer *"el test 5 **y el 2**"* (el de
independencia). **No cae.** Con el reparto completo (6+4=10) la suma de asignaciones **iguala** lo
pesado, así que los dos criterios dan exactamente lo mismo y el test pasa con el defecto puesto.

Es la misma forma del error de la ronda 3 de W1: **un test cuyo nombre promete más cobertura de la
que tiene**. Lo encontré porque QA insistió en verificar el número, no la caída — y la instrucción
resultó atrapar algo distinto de lo que buscaba.

Resuelto en el lugar correcto: el docstring del test dice ahora, explícito, que **no discrimina el
denominador** y nombra a los dos que sí (`test_reparto_parcial` y `test_sobre_reparto...`). El test
se queda porque clava los números de negocio del caso normal, que es otra cosa y también hace falta.

---

## 4. Gates

| Gate | Estado |
|---|---|
| Tests del ítem | ✅ **12** (`TestPrecioPorKg`) |
| Parity check | ✅ **DIFF CERO fuera del baseline** |
| `ruff` | ✅ |
| `tsc --noEmit` | ✅ |
| `npm run lint` | ✅ 0 errores, 37 warnings = presupuesto exacto, 0 nuevos |
| `npm run build` | ✅ |
| Suite completa | ✅ **1686 passed** (1674 + 12) — la cuenta cierra exacta: ningún test existente se movió |
| Smoke contra BD migrada | ✅ — el ejemplo de Daniel end-to-end en la SAC de dev: 10 unidades de `BAT-G07`, 100 kg, $1.000/kg → `weight_kg_used=100.000`, `unit_price=10000.00`, compra por $100.000. Leído **por la API**, que es donde vive la trampa de #95 |
| **Golden** | **No aplica** — verificado contra `CAPTURES`: las 14 entradas son reportes y listados, y `inbound_line_allocations` no aparece ni directa ni indirectamente. Tabla exclusiva SAC, router flag-gated, cero filas en las 3 orgs cliente |

---

## 5. Dónde mirar más duro

1. **El denominador.** Es la decisión de fondo de todo el ciclo y está en una línea. El comentario del
   helper escribe el argumento de independencia completo, porque el error se ve razonable: prorratear
   sobre lo repartido *suena* más correcto que sobre lo pesado.
2. **El salteo del modo kg en el toggle.** Depende de `weightKg` y `weighed` de la línea. Si alguien
   agrega un camino que deje una línea con peso pero sin cantidad, el toggle ofrecería un 422.
3. **Los dos guards de D4b.** Hoy se disparan juntos; existen por separado porque coinciden **por el
   orden del flujo**, no por un invariante.

---

## 6. La pregunta para QA

**¿El modo kg debería ofrecerse también al capturar el precio en la Entrada** (`InboundOrderLine.unit_price`,
el precio orientativo del patio) **o queda bien solo en la liquidación?**

Hoy queda solo en la liquidación, que es donde Hugo lo pidió y donde está el proveedor. Pero el
capturador también digita un precio, y si en la práctica ya lo piensa por kilo, tener el modo en un
lado y no en el otro se va a sentir arbitrario. No lo agregué porque no tengo evidencia de que pase
—y agregar un modo "por si acaso" a la pantalla del patio, que es la del eslabón apurado, tiene su
propio costo.
