# Plan — Guards de sede y tránsito en transformaciones (T0')

**Fecha:** 2026-08-18 · **Estado:** para QA · **Migraciones:** ninguna
**Origen:** `plan-cierre-entradas-traslados-transformaciones.md` §2 (T0', declarado *"prerequisito real, no higiene"*)
**Golden:** 🔴 **gate duro** — `material_transformations` es camino compartido con las 7 orgs

---

## 1. El agujero, verificado hoy contra el código

Una transformación **ya mueve material entre bodegas**: `source_warehouse_id` en la cabecera
([models/material_transformation.py:85](../../backend/app/models/material_transformation.py#L85)) y
`destination_warehouse_id` **por línea** ([:283](../../backend/app/models/material_transformation.py#L283)).

Su `_validate_warehouse`
([services/material_transformation.py:651](../../backend/app/services/material_transformation.py#L651))
comprueba tres cosas: que exista, que sea de la organización y que esté activa. **Nada más.**

De ahí salen dos huecos:

**H1 — tránsito.** `validate_not_transit_warehouse` existe
([services/transfer.py:54](../../backend/app/services/transfer.py#L54)) y la llaman ajustes (1),
compras (2) y ventas (2). **Transformaciones no la llama.** La bodega de tránsito guarda material
*en vuelo* — salió del origen y nadie lo ha recibido. Transformarlo ahí rompe la recepción, que
compara contra lo despachado.

**H2 — sede.** Una transformación con origen en Circunvalar y destino en Juan Mina mueve material
entre sedes **sin tránsito, sin pesaje de recepción, sin deuda de plomo intersede y sin maquila**.
Es el mismo agujero que #94 cerró para traslados, entrando por la otra puerta. Sin error y sin
warning: el resultado no es un fallo, son números equivocados en silencio.

**Por qué ahora:** el deploy de hoy dejó el molino configurado en producción como parte de
Circunvalar, o sea que ya es la bodega natural para transformar. La probabilidad de que alguien
pise el hueco subió.

---

## 2. Lo que dijo el cliente, que es lo que hace correcta la respuesta

No es una preferencia de ingeniería. **Johana y Hugo describieron el mismo modelo, por separado.**

Johana, 11-ago (16:07):

> **Daniel:** de la bodega de Circunvalar puede haber un traslado al molino… ahí se trasladan
> algunos materiales que luego **el molino transforma** y salen otros materiales
> **Johana:** el lodo, el plomo fino, el plomo grueso, esos materiales **se trasladan a planta**
> **Daniel:** cuando se trasladan del molino a Juan Mina **también se genera la misma maquila**

Hugo, 12-ago, cuando se propuso separar los módulos:

> **Hugo:** ese traslado es como traslado intersede, pero faltaría el traslado de material,
> **la transformación, mejor**

El ciclo que describen es de tres tiempos y cada uno tiene su documento:

1. **Traslado** Circunvalar → Molino — misma sede, sin maquila (#94 ya lo resuelve en un paso)
2. **Transformación** en el molino — baterías → PE, plomo fino, plomo grueso, lodo
3. **Traslado** Molino → Juan Mina — cruza sede → **maquila + deuda de plomo** (#94, dos pasos)

**La maquila nace en el traslado, no en la transformación.** Por eso una transformación que cruza
sedes no es "otra forma de hacerlo": es saltarse el paso donde se pesa y se cobra.

Y es coherente con la invariante ya declarada en #84 B1 — *un traslado NUNCA cambia el costo
promedio* — cuyo espejo es el que este plan escribe: **una transformación nunca cruza sedes.**

---

## 3. Decisiones

**D1 — Tránsito prohibido, en origen y en destino.** Se llama `validate_not_transit_warehouse`
desde `_validate_warehouse` de transformaciones. Calco literal de lo que ya hacen los otros tres
servicios, sin parámetros nuevos.

**Inerte por datos fuera de SAC** (medido: SAC tiene 2 bodegas de tránsito, las otras 6
organizaciones tienen **cero**), y además el propio guard cortocircuita dos veces — primero por
`is_transit`, después por el flag. Aplica a las 7 y es correcto para las 7: nadie debe transformar
material en vuelo.

**D2 — Una transformación no cruza sedes.** Si la sede del origen difiere de la de algún destino →
**400** con un mensaje que dice qué hacer: *"…pertenecen a sedes distintas. Muévalo primero con un
traslado y transfórmelo en la sede de destino."* Guiar, no solo negar.

**D3 — 🔴 El guard de sede va detrás de `two_step_transfers_enabled`.** Esta es la decisión que
evita repetir el casi-accidente de #98.

`sede_warehouse_id` es NULL en las 6 organizaciones que no son SAC, y `_sede_of` devuelve
`sede_warehouse_id or id` — o sea que **dos bodegas distintas son siempre dos sedes distintas**. Un
guard escrito de la forma obvia le prohibiría a Costa transformar de una bodega a otra, y **lo
hacen**: 1 de sus 83 líneas de transformación cruza bodega. Sería un 400 en la cara de un usuario
que hoy trabaja bien.

Con el flag apagado el guard **no corre**, así que el comportamiento de las 6 organizaciones es
byte a byte el de hoy. Y el flag es el correcto y no uno cualquiera: sin traslados de dos pasos, el
consejo *"haga primero el traslado"* ni siquiera tendría a dónde apuntar.

**D4 — La regla vive en un solo lugar.** Se agrega `validate_same_sede(db, organization_id, origin,
dest)` como función de módulo en `transfer.py`, al lado de `validate_not_transit_warehouse` y con la
misma forma (flag adentro, cortocircuito barato primero). Reusa `_crosses_sede`/`_sede_of`, que ya
existen ([transfer.py:953-968](../../backend/app/services/transfer.py#L953-L968)). **No se copia la
lógica de sede a transformaciones** — mismo criterio que D4 de #98.

**D5 — Solo en `create`.** El servicio expone `create` y `annul`, no hay edición. `annul` **no**
valida: revierte algo que ya existe, y bloquear ahí dejaría inanulable una transformación vieja.

**D6 — Cero migraciones y cero toques a datos.** Las transformaciones históricas no se revisan ni
se marcan. El guard aplica de aquí en adelante.

---

## 4. No regresión — el test que no existiría sin haber mirado los datos

Obligatorio y explícito:

**`test_org_sin_flag_transforma_entre_bodegas`** — organización sin `two_step_transfers_enabled`,
dos bodegas cualesquiera, transformación con origen en una y destino en la otra → **201**. Es el
caso que Costa ya ejecutó una vez y que un guard ingenuo rompería.

Y su hermano, que prueba que la regla no está simplemente apagada:

**`test_con_flag_cruzar_sedes_bloquea`** — misma forma, con el flag encendido y sedes distintas →
**400**.

El par es lo que distingue *"el guard funciona"* de *"lo apagué para todos"*. Es la misma lección
que dejó el traslado intra-sede de #94: sin el contraste, los dos casos se ven idénticos.

---

## 5. Tests

| Test | Qué fija |
|---|---|
| `test_org_sin_flag_transforma_entre_bodegas` | 🔴 **no regresión de las 6 orgs** |
| `test_con_flag_cruzar_sedes_bloquea` | el guard de sede muerde (D2/D3) |
| `test_con_flag_misma_sede_pasa` | Circunvalar → Molino sigue siendo válido: es el flujo real del cliente |
| `test_origen_en_transito_bloquea` | H1, origen (D1) |
| `test_destino_en_transito_bloquea` | H1, destino por línea (D1) |
| `test_transito_sin_flag_no_bloquea` | el cortocircuito del guard existente sigue vivo |
| `test_annul_de_transformacion_vieja_no_valida` | D5: no se vuelve inanulable |
| `test_mensaje_nombra_las_bodegas` | el 400 guía en vez de solo negar |

---

## 6. Gates

- Suite completa
- **Golden ×3 orgs — gate duro.** `material_transformations` alimenta tres líneas del P&L
  (`value_difference`, `waste_value` y el `cost_adjustment` de línea que entra a oversell). Este
  ciclo no toca esa matemática, solo agrega validaciones de entrada, así que el golden debe dar
  **0 diffs**; si diera alguno, algo se rompió que no estaba en el plan.
- `ruff` y `eslint`
- Parity check no aplica (sin migraciones), pero se corre igual por costar nada

---

## 7. Lo que este plan NO hace, a propósito

- **No decide qué es el molino.** Ese es T0/T1 y depende de la tabla de estándares que todavía no
  se le pidió a Johana. Este guard hay que ponerlo igual, cualquiera sea la respuesta.
- **No emite kg ni maquila desde una transformación.** Se descartó explícitamente: si una
  transformación intersede emitiera como un traslado, existirían dos caminos para el mismo hecho
  económico y se saltaría el pesaje de recepción, que es donde el cliente verifica.
- **No toca el frontend** más allá de mostrar el error que devuelva el backend. Si la operación se
  vuelve frecuente, avisar antes de guardar es un ciclo aparte.

---

## 8. Pregunta para QA

La única que vale: **¿bloquear es la respuesta correcta, o en SAC una transformación que cruza
sedes debería emitir plomo y maquila como lo hace un traslado?**

La recomendación es bloquear, por las citas de §2 y por la invariante de #84. Pero el que decide
esto es el modelo de negocio, no el código.
