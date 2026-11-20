# Plan — SAC: la captura de la Entrada como el formato en papel (v1.1)

**v1.1 (19-nov, noche):** se aplican F1–F8 de QA sobre la v1.0 (sha a628a3f2…). Cada cambio cita su F.

**Pedido:** Johana, vía Daniel, el 19 de noviembre, con una foto del formato «Materiales recolectados»: «quiere que los materiales salgan en este orden para que sea más fácil para ellos digitar».

**Decisión de Daniel (19-nov):** «Pantalla como el papel». La captura muestra los renglones del formato en ese orden, con una casilla de cantidad cada uno, y el mismo orden se usa en edición, liquidación, detalle y PDF.

**Autorizado por Daniel el 19-nov:** plan y construcción, pasando por QA y antes del reparto por compra.

**Base:** el commit del redondeo (develop). Este ciclo no toca columnas de precio.

## 1. El formato

Son 25 renglones. Los cruzo contra los materiales activos de SAC en producción, leídos por GET el 19-nov a las 23:40 (45 activos):

| # | Renglón del papel | Código |
|---|---|---|
| 1–7 | Baterías Grupo 0,7 · 0,8 · 1 · 2 · 3 · 4 · 5 | BAT-G07, BAT-G08, BAT-G1 … BAT-G5 |
| 8 | Batería Húmeda | **no existe** (ni en producción ni en dev) |
| 9 | Scrap Moto | SCR-MOTO |
| 10 | Scrap Seco Grande | SCR-SG |
| 11 | Scrap Seco Pequeño | SCR-SP |
| 12 | Scrap Limpio Sin Borne | SCR-LSB |
| 13 | Scrap Limpio Con Borne | SCR-LCB |
| 14 | Plomo Lingotes | PLO-LIN |
| 15 | Retal | PLO-RET |
| 16 | Cáscara | PLO-CAS |
| 17 | Cajas Plásticas | CAJ-PLA |
| 18 | Acrílicas | CAJ-ACR |
| 19 | Polvoducto | POL-DUC |
| 20 | PP Molido | PP-MOL |
| 21 | Tapas con Borne | TAP-BOR |
| 22 | Guarrú | GUA-RRU |
| 23 | Lodo | LOD-01 |
| 24 | Hierro Chatarra | HIE-CHA |
| 25 | Aluminio | ALU-01 |

**Batería Húmeda (renglón 8)** no se inventa: crear un material nuevo define su unidad, su fórmula de plomo y su clasificación Willard, y nada de eso lo sabemos. Va al inventario como **Q-72** para Johana: ¿es un material distinto de las baterías por grupo, con qué unidad, y entra por compra, por Willard o por los dos? Mientras tanto, el formato queda con el hueco del 8. Cuando ella lo cree, lo agrega al formato desde Configuración, sin código (§3).

⚠️ La foto la transcribí yo. El orden de la tabla sale de esa transcripción, que se guardó en el inventario el mismo día. Si Johana ve un renglón fuera de lugar, se corrige desde la configuración y no hace falta un ciclo.

## 2. Dónde vive el orden

**D1. Columna `material_kg_profiles.form_order`**, entera y nullable. NULL significa que el material no está en el formato.
- `material_kg_profiles` es exclusiva de SAC y su router está detrás del flag, así que el golden no aplica. Se verifica contra `CAPTURES` con un comando, no de memoria.
- Índice único parcial `(organization_id, form_order) WHERE form_order IS NOT NULL`: dos materiales no pueden compartir un renglón, y eso lo garantiza la base.
- Migración aditiva, sin backfill.
- **F8:** el índice parcial se declara también en el modelo (`Index(..., unique=True, postgresql_where=...)` en `__table_args__`), no solo en la migración. Sin eso el parity check da DIFF, como en #98.

**D2. El orden NO viaja por el upsert del perfil.** `MaterialKgProfileUpsert` es `extra="forbid"` y reemplaza el perfil entero. #103 D4 mostró que un campo con default ahí se borra en silencio desde cualquier caller que no lo mande, y la alternativa (sin default) obliga a tocar todos los callers. Por eso el orden tiene su propio endpoint:
- `PUT /material-kg-profiles/form-order` con `{ "material_ids": [...] }`, la lista COMPLETA en orden. **F1:** el router ya tiene `PUT /{material_id}` (`material_kg_profiles.py:53`); la ruta estática se declara ANTES, o FastAPI intenta parsear «form-order» como UUID y responde 422. T1 lo prueba de hecho.
- El servidor asigna `form_order = posición` a esos y NULL al resto de la organización, en una transacción. Es semántica REPLACE de una sola cosa, como los centros Willard (#87 c).
- **F2. Primero NULL a toda la org, `flush`, y recién después se asignan las posiciones.** El índice único no es diferible: asignar fila por fila mientras otra fila todavía tiene ese número da IntegrityError en mitad de la transacción. Es exactamente lo que hace un intercambio de dos renglones con las flechas. T2b lo fija.
- Los huecos se representan con `null` en la lista, para conservar «el 8 vacío» y que los números coincidan con el papel.
- 422 si un material es de otra organización, está inactivo o se repite. El material sin perfil se rechaza y el mensaje dice dónde clasificarlo.
- Permiso `materials.edit`, el mismo del perfil. `require_org_flag("kg_ledger_enabled")`.
- El upsert no conoce el campo: no lo escribe y no lo borra. Un test lo fija con un PUT del perfil después de ordenar.
- `MaterialKgProfileResponse` gana `form_order`, de solo lectura, y **`material_is_active` (F3)**.
- **F3. Material del formato que se desactiva después.** Conserva su `form_order` (desactivar no toca el perfil), así que hay que decidir qué pasa en cada pantalla:
  - **Captura:** no se muestra como renglón. Un material inactivo no se recibe (`_validate_material` lo rechaza), así que ofrecerlo sería ofrecer un 422.
  - **Edición:** si una línea guardada lo tiene, aparece en «Otros materiales» como hoy, sin perder la cantidad.
  - **Configuración:** se pinta en su renglón con la marca «inactivo» y el botón «quitar». Mientras siga en la lista, Guardar queda deshabilitado con el aviso «quite los materiales inactivos», y no se manda una lista que el servidor va a rechazar con 422. Así el usuario siempre tiene una salida.
  - T4b: desactivar un material ordenado → el GET de perfiles lo devuelve con `form_order` y `material_is_active=false`.

**D3. Configuración.** En Config → Materiales (kg) se agrega una sección «Formato de captura»: la lista en orden con flechas subir/bajar, quitar y «Agregar material», más un botón Guardar que manda la lista completa. Mobile: una tarjeta por renglón con las flechas a la derecha. No hay arrastrar y soltar; es más frágil en el celular y no hace falta para 25 renglones.

**D4. Sembrado.** `seed_sac_org.py` gana `FORM_ORDER` con los 24 códigos de la tabla (el 8 vacío).
- **Solo siembra si la organización no tiene NINGÚN material en el formato** (la regla de #109 y #116: el seeder no pisa lo que no puso).
- **F5:** si ya hay formato, no lo toca, imprime UNA línea informativa (cuántos renglones tiene y si coincide o no con `FORM_ORDER`) y sale con exit 0. Aquí un formato distinto es el estado ESPERADO, porque Johana lo corrige desde Configuración. No hay decisión que tomar: su formato gana. Un exit 3 que saldría en cada provisión enseñaría a ignorarlo.
- Producción: la provisión lo escribe en el deploy. Es una escritura en producción y va con el OK de Daniel en el runbook.

## 3. Pantallas

**Captura, solo en tipo compra** (el papel es de recolecciones; Willard no usa este formato):
- Una tarjeta «Formato» con un renglón por material del formato, en orden. Cada renglón tiene el nombre fijo, Cantidad y, solo en materiales por unidad, Peso báscula. Al lado de ese peso queda el mismo aviso de hoy (#95 Q-13).
- Se muestran también los renglones de los materiales que no aplican a compra (Willard puro), deshabilitados y con la razón en gris. La alternativa era esconderlos, pero eso movería el orden contra el papel.
- Debajo, «Otros materiales»: las líneas libres de hoy, para lo que no está en el papel (MR\*, PLO-BAL, ESTIBAS…). El selector de esas líneas excluye los materiales del formato, porque un material en dos lugares sumaría dos líneas que la Entrada rechaza.
- Al guardar se mandan solo los renglones con cantidad > 0, en orden del formato, seguidos de los otros materiales. No cambia nada del payload ni del servidor.
- El precio de referencia y las notas de calidad salen del renglón del formato. El papel no los tiene, y el precio se fija al liquidar (#93). Siguen en las líneas de «Otros materiales».
- Mobile: en cada renglón, el nombre arriba y las casillas en `grid-cols-2` debajo. Probado a 390.

**Edición** (tipo compra, sin efectos): la misma tarjeta, con las cantidades de la Entrada precargadas. Las líneas cuyo material no está en el formato van a «Otros materiales».
- **F6. El renglón conserva y reenvía lo que no muestra.** Una línea guardada puede traer `unit_price` y `quality_notes`, y si cae en un renglón del formato, `toApiLines` reemplaza todas las líneas y esos campos se perderían en silencio. El renglón los guarda en su estado y los manda tal cual. Además, si la línea tiene notas, el renglón muestra un ícono con el texto en el tooltip, para que el dato no quede invisible. Se descartó mandarla a «Otros materiales»: rompería el orden del papel justo en las Entradas que tienen notas. Se verifica en pantalla con una Entrada que tenga notas y precio: se guarda sin tocar nada y el GET devuelve los dos campos iguales.
- **F7. La precarga NO marca `linesDirty`.** El formato se arma desde la Entrada guardada en el mismo `useState` inicial que hoy arma las líneas, no en un efecto que llame al setter que marca la edición. Si no, editar solo la cabecera de una Revisada (sede #118, factura, nota) la devolvería a Registrada por D17 sin que nadie tocara una cantidad. Gate de pantalla: abrir una Revisada, cambiar solo la nota, guardar → sigue Revisada, y el aviso ámbar de `InboundEditPage.tsx:537` no aparece.

**Liquidación, detalle y PDF:** las líneas se ordenan por `form_order`. Las que no tienen orden van al final, alfabéticas por nombre (la regla de 0862891, que pasa a ser solo el desempate).
- Aplica en **todos** los estados. 0862891 ordenaba solo al liquidar para conservar «el orden de captura que ve el pesador», pero con la captura como el papel ese orden ya es el del formato.
- El orden se aplica en un helper de frontend, `sortByFormOrder(lines, profiles)`. Una sola fuente, usada en las cuatro pantallas y en las cards del reparto.
- **PDF de la compra** (`exportPurchasePDF`, código compartido): `purchase_lines` se ordena por `created_at`, y las N compras de una Entrada nacen en UNA transacción, así que hoy el orden de sus líneas no está definido. **F4: tiene DOS llamadores**, `PurchaseDetailPage.tsx:108` y el menú de fila de `PurchasesPage.tsx:106`. Los dos pasan por un envoltorio común, `orderPurchaseLinesForPdf(purchase, profiles, sacEnabled)`, que devuelve una copia ordenada solo cuando la compra viene de una Entrada (`inbound_order_id`) y el flag está prendido; si no, devuelve la misma compra. `exportPurchasePDF` no cambia, y Costa y Meta quedan byte a byte. En el navegador se verifica que el PDF de la misma compra salga igual desde los dos lugares.
- `useKgProfiles` ya existe con `enabled` (F2): sin el flag no hay request.

## 4. Fuera de alcance

- Crear «Batería Húmeda» (Q-72).
- Ordenar el selector de materiales de Willard o de Ventas.
- Ordenar en el backend las líneas de la respuesta. El orden es de presentación, y moverlo al servidor tocaría el enrich compartido de compras.

## 5. Tests (backend)

| T | Caso | Afirma |
|---|---|---|
| T1 | PUT del orden con 3 materiales y un hueco | GET de perfiles: `form_order` 1, 3 y 4, y NULL en el resto |
| T2 | Un segundo PUT con otra lista | Los que salieron quedan en NULL (REPLACE) y los nuevos con su posición |
| T2b | Intercambio de los renglones 3 y 4 (F2) | 200, y el GET devuelve las posiciones intercambiadas |
| T3 | PUT del perfil (upsert) de un material ordenado | Su `form_order` no cambia (D2) |
| T4 | Validaciones | 422 con material repetido, de otra organización, inactivo o sin perfil. Nada se escribe (leído por GET) |
| T4b | Desactivar un material ya ordenado (F3) | El GET de perfiles lo devuelve con su `form_order` y `material_is_active=false` |
| T5 | Permisos | Rol con `materials.view` y sin `materials.edit` → 403; el GET de perfiles da 200 (control positivo). Sin el flag → 403 |
| T6 | Índice único | Dos perfiles con el mismo `form_order` por ORM → IntegrityError (la base lo garantiza, no el servicio) |
| T7 | Seeder (F5) | Contra dev: con el formato vacío, siembra los 24 y sale con exit 0; con un formato distinto, no pisa, imprime la línea informativa («N renglones, distinto de FORM_ORDER») y sale con exit 0. Corre a archivo, con el contraste de las dos ramas |

Frontend sin infraestructura de tests: se verifica abriendo la pantalla a 1440 y a 390 (captura, edición, liquidación, detalle y PDF). Gates de pantalla específicos:
- **F6:** una Entrada con notas y precio en un material del formato; se guarda sin tocar nada y el GET devuelve los dos campos iguales.
- **F7:** una Revisada a la que solo se le cambia la nota sigue Revisada.
- **F4:** el PDF de la misma compra sale igual desde el detalle y desde el listado.
- **F3:** con un material del formato desactivado, Config lo marca, y Guardar no se habilita hasta quitarlo.

## 6. Plantado (predicciones antes, matriz commiteada antes de plantar)

| P | Defecto | Cae |
|---|---|---|
| P1 | El PUT no pone NULL a los que salieron | T2 |
| P2 | El upsert del perfil escribe `form_order = None` | T3 |
| P3 | Se quita la validación de repetidos (el índice queda) | T4[repetido]. Corregido el 20-nov antes de plantar (C2 de QA): la v1.1 decía «500 en vez de 422», pero `[c,c]` asigna dos veces el mismo objeto y gana la última posición, así que da **200**. T4 cae igual porque espera 422 |
| P4 | Se quita el flag del router nuevo | T5, el caso sin flag |
| P5 | El seeder siembra aunque ya haya formato | T7, la rama «no pisa» |
| P6 | Se asigna sin el NULL previo (F2) | **Al menos** T2b y T2, con IntegrityError. Corregido el 19-nov al escribir T2 y antes de plantar: la v1.1 decía que T2 no caía «si su lista no reusa números ya ocupados», y la lista de T2 sí los reusa (D pasa al renglón 1 mientras A lo tiene). T1 no cae: parte de un formato vacío |

## 7. Gates

Dirigidas por grep sobre `material-kg-profiles|kg_profile|MaterialKgProfile`, más las tres guardas del árbol. Parity. Smoke de la migración up/down/up. El golden no aplica, medido contra `CAPTURES`. Pantalla de Daniel como condición de deploy. La suite completa queda para el checkpoint.
