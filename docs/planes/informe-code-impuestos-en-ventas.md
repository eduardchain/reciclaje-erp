# Informe de construccion — CC-013: IVA y retenciones en lo que SAC factura

Plan: `plan-sac-impuestos-en-ventas.md` v1.4 (GO). Matriz defecto x test
commiteada en `e971c5e` **antes** de plantar nada.

---

## 1. Que se construyo

`document_taxes`, una fila por impuesto de un documento de venta, con **dueno
unico** por FKs nullables y CHECK (`sale_id` XOR `willard_delivery_id`) — el
precedente del repo, no un par polimorfico. El sistema **registra lo que Siigo
emitio**, no emite: los montos se capturan al liquidar con precalculo editable
(patron #79) y el numero de factura amarra los dos mundos.

Los signos viven en **un mapa**, `TAX_SIGN_ON_CUSTOMER`, y no en un `if` por
consumidor: el IVA acredita al cliente y las retenciones lo debitan, o sea que
son opuestos, y es exactamente la clase de cosa que la terna de signos
(#67/#69/#86) enseño a escribir una sola vez. Con la FE 2127 el cliente termina
debiendo **$119.335.609,11**, que es el "Total a Pagar" impreso en la factura:
conservacion por construccion, igual que en las retenciones de compra (#75 D9).

Dos superficies lo consumen — la venta normal y la Salida de Plomo — con **un
solo punto que aplica y uno que revierte**.

---

## 2. Cuatro desviaciones del plan. Las cuatro se declaran.

**(a) `base_amount` paso a derivarse en el SERVIDOR; el payload lleva
`base_kind`.** El plan (D5) asumia que la pantalla manda la base. En una Salida
tipo **abono** la base es maquila mas flete, que salen de tarifas resueltas AL
liquidar: la pantalla no puede conocerla. La correccion es estrictamente mas
fuerte — una sola fuente, imposible de mandar mal — y resuelve el abono entero.
Trajo un 422 nuevo: una reteIVA sobre una factura sin IVA.

**(b) D4c: la exclusion del panel de cobro es por OMISION, no por predicado.**
El plan decia ampliarla "con el mismo predicado". Medido: el panel ya excluye
por AUSENCIA de la seccion en `_INACTIVE_SECTION_TYPE`, que es el mismo
mecanismo con el que trata a `prepaid_expenses`. Agregar un predicado seria un
segundo mecanismo para una sola regla. Queda escrito en el codigo, donde se
lee.

**(c) El golden son 4 capturas con clave aditiva, no 2.** El plan conto las dos
del Balance General. Medido: el Detallado tambien emite sus secciones vacias,
asi que ganan la suya `balance_detailed` y `balance_detailed_asof`.

⚠️ **Y mi control positivo estaba escrito en la unidad equivocada.** Lo escribi
como "EXACTAMENTE 4 claves aditivas" contando CAPTURAS; el comparador cuenta por
(organizacion, captura) y reporto **12** — que son las mismas 4 capturas por las
3 organizaciones, 1 clave cada una. El contenido coincidio exacto; la unidad no.
Lo que importa es que el resultado NO fue *"0 diffs y 0 aditivas"*, que es el
resultado vacuo que #110 enseño a no aceptar.

**(d) T9 no tiene hogar automatizado en el frontend** (no hay vitest): quedo
como test de backend de "montos redondeados por linea se aceptan y conservan".
El defecto P9 se verifico midiendo el NUMERO, no la caida.

---

## 3. El plantado: 21 defectos, y los SEIS huecos que destaparon los gates

18 de los 19 de backend cayeron sobre su test. Los dos de frontend se
verificaron aparte. Pero lo que el ciclo produjo de valor no son los 18 verdes:
son los seis huecos que destaparon los gates — dos el plantado, uno el smoke,
uno la suite completa, uno QA y uno releer la guarda que QA me hizo escribir.
**Ninguno lo habia previsto el plan.**

### 🔴 P14 no tumbaba NADA. 30 passed.

Es la unica caida en la direccion peligrosa del ciclo: un defecto real que
ningun test veia. Predije "al menos T5" y la realidad fue **cero**.

La causa: ningun test RENOMBRABA la categoria y despues liquidaba. T14d la
renombra a "Tributos" y ahi termina. Y el defecto es caro justamente porque
renombrar esta **permitido por diseño** — es la asimetria de #58, y el motivo
entero de reconocer por `system_code` y no por texto. Con reconocimiento por
nombre, la factura siguiente no encuentra la categoria renombrada, intenta
crear otra con el mismo codigo y choca contra el indice unico parcial: un 500
en la cara del usuario.

O sea que la decision D4b **no tenia guardian, se documentaba a si misma**.
→ **T14f**: renombrar y volver a facturar, afirmando que la entidad nueva cae
en la MISMA categoria y que sigue habiendo UNA sola. Replantado P14: cae T14f.

### 🔴 T10c prometia mas cobertura de la que tenia.

Predije que P6 (la reversion no revierte) tumbaria T6 y T10. Tumbo T6 y T6b,
**no T10c**. T10c comparaba el saldo corrido contra la constante `0` en vez de
contra el saldo VIVO del tercero. Con el defecto, `reverted_at` igual se
estampa, el statement emite su par de cancelacion y el corrido baja a cero
mientras el saldo vivo se queda con los impuestos pegados: los dos lados se
separan y el `== 0` pasa igual. Es el `0 == 0` de #98 con otra cara.

El invariante de #55 es **corrido == vivo**, y eso es lo que hay que afirmar;
el `== 0` es el contenido del caso y va despues, no en su lugar. T10 y T10b si
lo hacian. → corregido; replantado P6: ahora cae T10c.

### 🔴 La respuesta del PATCH de liquidar declaraba `taxes` y llegaba vacia.

Esto no lo encontro el plantado sino el **smoke con POST real**. `SaleResponse`
declara `taxes` y el endpoint arma el response campo por campo, asi que
declararlo en el schema no basta (trampa de #95). Los 31 tests leian los
impuestos de la BD o del GET de detalle — **ninguno preguntaba lo que el
usuario recibe**, que es la leccion de #100 con el warning que se calculaba y
nadie entregaba.

Arreglado en `liquidate` y en `cancel`. El barrido de la familia se hizo con
`grep` sobre los 12 constructores de `SaleResponse` y no de memoria (#108): los
que quedan devolviendo `[]` lo hacen por ESTADO —una venta recien creada no
tiene impuestos, y `update` rechaza todo lo que no este `registered`— o por la
decision detail-only escrita en `_tax_rows`. → **T1d** lee `taxes` de la
respuesta HTTP del PATCH, y tambien del cancel, donde las filas siguen viniendo
con su `reverted_at` poblado. Replantado: cae T1d y solo T1d.

**Regla que deja el ciclo: un test que lee el efecto de la BD no prueba que el
usuario lo reciba.** Son dos preguntas distintas y hacen falta las dos.

### 🔴 Declarar la clave aditiva revienta la guarda que la vigila.

Lo encontro la **suite completa**, en la ronda 3. `TestClaveAditivaCC014`
afirma la igualdad EXACTA del dict de permisos del comparador del golden, asi
que agregar `tax_advances` a `ALLOWED_ADDED` la tumbo — que es exactamente para
lo que esa guarda existe: **obligarme a venir a declarar la clave nueva donde
se lee**, en vez de ampliarla en silencio.

Su assert `== {}` para el Detallado era de CC-014, donde el item viaja dentro
de una seccion existente; CC-013 lo cambio legitimamente porque su seccion SI
es nueva. Lo que CC-014 protege no es el vacio sino que `lead_debt_willard` no
este ahi, y ahora eso se afirma **por nombre** al lado de la igualdad exacta.
→ `TestClaveAditivaCC013`, espejo: **la clave que introduce un ciclo necesita
su propio test, o es una clave que nadie vigila.**

### 🔴 El filtro de la tarifa sobre-IVA vivia en la pantalla que SAC no usa.

Lo encontro QA, no yo. Una retencion de COMPRA puede tener `base_kind='iva'` en
su tarifa, y una compra no lleva IVA: esa tarifa no cabe ahi. Yo puse el filtro
del selector en `PurchaseLiquidatePage` y lo di por cerrado. Pero desde el canal
unico (#80 B1) **SAC no liquida por esa pantalla** — liquida por
`InboundLiquidatePage`, donde el reparto por proveedor lleva sus propios bloques
de retencion (#93). O sea: el filtro estaba puesto exactamente donde la
organizacion que lo necesita no pasa.

Y el remedio no es copiar el filtro a la segunda pantalla. Es la leccion de
#103 D3 —**un validador, todos los puntos de entrada**—: el guard va en
`_apply_retentions`, que es el punto UNICO por el que pasan la compra directa,
la Entrada y el API cruda. El payload gana `config_id` **opcional y sin
persistir**, que sirve para una sola cosa: que el servidor pueda identificar la
tarifa y rechazarla con 422. Ausente = camino de siempre byte a byte, porque
ningun payload previo lo manda.

⚠️ El servidor **solo juzga lo que puede identificar**: sin `config_id` no hay
rechazo. No es un hueco sino la unica forma de que el guard sea aditivo; la
pantalla lo manda siempre y por eso el camino humano queda cubierto.

→ Seis tests: rechazo y control positivo en compra directa, y en la Entrada el
422 **leido por HTTP** con la atomicidad afirmada (la entrada sigue `reviewed`,
cero compras, saldo del proveedor en cero) mas su control positivo. El plantado
PC2 los tumba: 3 de 6, que son justo los que afirman el rechazo.

### 🔴 La guarda que nacio de C1 tenia roto su camino de fallo.

Salio de releerla antes de mandarsela a QA. `golden_run.sh` termina con la
cadena `captura && captura && diff` seguida de `EXIT=$?` — y el script lleva
`set -euo pipefail`, que **mata una cadena `a && b && c` cuando el ultimo
falla**. O sea que si el golden encontraba diffs, el script se iba ahi mismo:
sin imprimir el `EXIT`, sin quitar el worktree y con la limpieza a medias.

**Funcionaba solo cuando el golden pasaba.** En el unico caso que importa —que
encuentre una diferencia— la guarda no reportaba. Es la misma clase de C1: el
camino de FALLO sin probar.

Y hay un efecto de segundo orden que lo hace peor: abortar dejando dos uvicorn
vivos **reproduce, en la corrida siguiente, el puerto ocupado que este script
existe para atrapar**. La guarda se sabotea sola.

Arreglado con `set +e` alrededor de la cadena y la limpieza como **una sola
fuente** (el `trap`, que cubre tambien el camino de aborto de las tres guardas).
⚠️ Y el primer control positivo que escribi **no replicaba el caso**: usaba un
`exit 3` dentro de la cadena, que corta el script, mientras `golden_diff.py` es
un proceso externo que *devuelve* 3 y deja la cadena seguir — justo el tramo
que habia que probar. Re-hecho fiel en `golden_run_camino_de_fallo.log`, con el
contraste del "antes" al lado.

---

## 4. Cuatro defectos PRE-EXISTENTES encontrados midiendo. Reportados, NO arreglados.

**(1) El Excel del Balance Detallado omite `generic_receivable`.** `ASSET_ORDER`
en `frontend/src/utils/excelExport.ts` es una lista blanca estricta y esa clave
no esta, aunque el backend la emite como seccion de activo ("Otras Cuentas por
Cobrar"). Medido contra la replica: **$821.638.247 en Costa** y **$5.518.078 en
Biogreen** faltan de las filas exportadas mientras `total_assets` si los
incluye. **El Excel no suma.** Este ciclo si agrego `tax_advances` a esa lista;
`generic_receivable` sigue afuera y es anterior.

**(2) `PurchaseRetention` no es fuente de `_get_tp_balances_as_of`** (desde
#75). El corte historico reparte mal entre el proveedor y la entidad
`[Retenciones] X`, aunque los dos errores se cancelan en el total — la clase
P19 en otro lugar. Medido: **0 filas en las 7 organizaciones**, o sea cero
impacto vivo hoy. CC-013 si agrego `DocumentTax` como sexta fuente, y lo
encontro T5 fallando.

**(3) La precarga del reparto reconoce la tarifa por `(tipo, municipio)`, sin
el concepto.** Salio de revisar mi propio barrido de C2.
`InboundLiquidatePage` reconstruye las filas de retencion al volver a liquidar
una Entrada des-liquidada (#93 D20 conserva el reparto), y busca la tarifa con
`retention_type` + `municipality` — pero el catalogo lleva **concepto** desde
#79 D14, y ahi esta la clave de unicidad. Con dos ReteFuente del mismo tipo y
distinto concepto elige la primera, asi que el `rate` que se persiste puede ser
el de la otra. El `amount` queda bien (viene precargado y es la verdad, #79
F1); lo que se corrompe es el dato de auditoria. `PurchaseLiquidatePage` no lo
sufre: arranca vacia, no precarga.

Es de #93 y no de este ciclo — pero **CC-013 documenta exactamente el escenario
que lo dispara**: el mismo cliente retiene 2,5 % por un bien y 4 % por un
servicio, o sea dos ReteFuente que solo se distinguen por concepto. Hoy no
existe: medido, **0 grupos con conceptos distintos en las 7 organizaciones**.
Aparece el dia que Johana cree la segunda.

⚠️ **Y la primera medicion que hice de esto estaba MAL**: conte 3 pares de
tarifas "duplicadas" en SAC. Eran dos organizaciones llamadas SAC, una inactiva
de un `--reset` anterior, y mi query joineaba por nombre sin filtrar
`is_active` — la trampa que #93 dejo escrita y que pise igual. Con el filtro:
cero duplicados, la unicidad del servicio funciona.

**(4) `replicate_prod.sh` borra el dump de produccion solo en el camino
feliz.** Salio del barrido de la familia del hallazgo (f): busque en el repo
otros scripts con `set -e` cuya limpieza dependa de que todo salga bien. Los
otros tres no tienen el patron de la cadena, pero este tiene **`set -e` y
ningun `trap`**, y sus dos limpiezas —`rm -rf /tmp/ecobalance-replicate` y el
`rm -f /tmp/restore.sql` dentro del contenedor— son las ultimas lineas. Si el
`psql -f` del restore falla, el script se va y **queda un dump completo de
produccion en `/tmp`**, en la maquina local y dentro del contenedor,
indefinidamente.

Medido: **cero residuos hoy** (la ultima replica termino bien). Se reporta sin
arreglar: es de otro ciclo. El arreglo es el mismo de (f), un `trap limpiar
EXIT` declarado antes de la primera descarga.

---

## 5. Gates

| Gate | Resultado | Artefacto |
|---|---|---|
| Plantado ronda 1 | 19/19, cierre sha256 en los 11 archivos | `plantado.log` |
| Plantado ronda 2 | 4/4 exactos (PC2, P6, P14, P20), cierre sha256 | `plantado_ronda2.log` |
| P9 | medido por su NUMERO, no por la caida | `p9_numero.log` |
| Golden x3 orgs | **0 diffs reales**, 12 claves aditivas, 48 capturas por lado | `golden_final.log` |
| Guardas de procedencia | **solo la guarda 1 quedo ejercitada** (puerto ocupado → aborta). Las 2 y 3 NO: el intruso que levante para probarlas no llego a abrir el puerto (`OSError 48`), asi que nunca hubo un PID ajeno escuchando que cotejar. La 1 es justo la que habria cazado el incidente que motivo C1 | `golden_control_positivo.log`, `intruso.log` |
| Camino de fallo de la guarda | llega a `EXIT=3`, lo imprime y limpia una vez | `golden_run_camino_de_fallo.log` |
| Parity check | **DIFF CERO** — 67 tablas, 300 indices, 367 constraints | `parity_cc013.log` |
| Migracion | up/down/up limpia en dev; esquema re-creado identico | `migracion_cc013.log` |
| Smoke POST real | 200, los 4 impuestos EN LA RESPUESTA, delta del cliente exacto. ⚠️ **El PRIMERO devolvio `impuestos devueltos: 0`** porque corrio contra un backend arrancado 5 min ANTES del fix; ese log queda como `smoke_post_real.log` y es el que origino C3 | `smoke_c3.log` (bueno), `smoke_post_real.log` (el vacuo) |
| Suite completa | **1902 passed, EXIT=0** (0:48:05), 0 FAILED / 0 ERROR / 0 Traceback en todo el recorrido; arbol congelado desde el inicio (0 archivos, control positivo 659) | `suite_cc013_r6.log` |
| ruff | All checks passed | |
| tsc | limpio | |
| eslint | 37 = el techo exacto | `frontend_c2.log` |
| build | OK | `frontend_c2.log` |

⚠️ **Nota de runbook que salio de verificar la migracion: el downgrade deja
saldos aplicados sin las filas que los explican.** El `DROP TABLE` se lleva los
`document_taxes` pero no revierte el efecto que esas filas tuvieron sobre el
cliente y sobre las entidades de impuestos — en dev quedaron cinco terceros con
saldo y cero documentos detras. **En un rollback de produccion con impuestos ya
capturados hay que des-liquidar esos documentos ANTES de bajar la migracion.**

🔴 **Y hay una SEGUNDA mitad del daño que yo no habia visto y encontro QA:
el downgrade tambien deja HUERFANA la categoria de sistema, y volver a subir NO
la repara.** El `DROP COLUMN system_code` se lleva el codigo; el upgrade
re-crea la columna **vacia**, asi que la categoria `Impuestos` queda con
`system_code` NULL y las entidades `[Impuestos]` siguen asignadas a ella. El
efecto no es un error: `resolve_tax_entity` encuentra la entidad **por nombre**
y la devuelve sin mirar la categoria, asi que la siguiente factura mueve saldos
con normalidad hacia entidades **que el clasificador ya no reconoce** — las
retenciones a favor aterrizan en Gastos Prepagados en vez de en la seccion
`tax_advances`, que es literalmente el defecto que D4b existe para impedir. Y
una entidad nueva (otro municipio de ICA) crearia una **segunda** categoria
`Impuestos`, porque no hay unicidad por nombre. Medido y reparado en dev el
2026-09-23 (`d1_reparacion_dev.log`: antes NULL con las 4 entidades colgando,
despues `taxes`, y el control de que las otras 6 orgs siguen en 0). **En el
runbook de rollback: despues de re-subir hay que devolverle el `system_code` a
la categoria, o el sintoma es silencioso.**

⚠️ **Backlog escrito, no bloqueante (recomendacion de QA):** que
`resolve_tax_entity` asegure tambien la asignacion cuando ENCUENTRA la entidad
—hoy solo la crea en el camino de alta (`tax_entities.py`, el `return tp` del
match sale antes)—, para que una asignacion perdida se repare sola. No se hizo
en este ciclo porque es codigo y obligaria a una septima corrida de la suite
por algo que no bloquea, y porque tiene una decision de diseño que no conviene
tomar de apuro: verificar la asignacion en cada llamada agrega una consulta por
entidad en cada factura, y puede que el lugar correcto sea el arranque o el
propio `get_or_create_tax_category`.

🔴 Y **no se le pone un gate al downgrade a proposito**: el patron del repo
(#93 G1/G2, #106 D5) pone los gates de datos en el **upgrade**, que es una
operacion planeada. Un gate en el downgrade puede impedir un rollback de
emergencia, que es exactamente el momento en que no se puede negociar con una
barrera.

⚠️ **Y la fila "Migracion" de esa tabla estaba citando un artefacto que no
existia.** La verificacion se habia hecho, pero no a archivo, y yo escribi la
cita igual — el error de C3 cometido dentro de la tabla donde lo estaba
documentando. Se re-corrio entera: `alembic current` → `downgrade -1` →
`upgrade head`, con el esquema verificado despues (4 CHECK, el indice unico
parcial de `system_code`, `base_kind` con su `server_default='subtotal'` y las
6 filas viejas todas en `subtotal`, sin backfill que revisar).

**Golden.** 12 claves aditivas = las 4 capturas predichas por las 3
organizaciones, 1 cada una; las otras 36 byte-identicas, **incluidos los seis
`tp_statement`**, que es la superficie que mas toco el ciclo: sin filas en
`document_taxes` el bloque nuevo emite cero eventos, y eso queda medido y no
argumentado.

**Prueba de vida.** Antes de capturar se escribio en el log que `:8001`
(develop-HEAD) **no** trae `tax_advances` y `:8002` (arbol de trabajo) **si**.
Sin eso, un golden cuyos dos lados no se distinguen da "0 diffs" y no prueba
nada — que es lo que le paso a la primera corrida de CC-014.

🔴 **Y aun asi la primera corrida de ESTE golden estaba mal, por el lado que la
prueba de vida no mira.** QA lo encontro: el log del lado BEFORE decia `address
already in use` y quien contestaba en `:8001` era un backend de horas antes,
pid 12149. La prueba de vida pregunta *"¿los dos lados son distintos?"* y esa
respuesta era **si** — porque el proceso viejo tampoco tenia `tax_advances`. O
sea que un golden puede pasar la prueba de vida de #110 y aun asi no comparar
lo que uno cree.

**Son dos preguntas distintas: que los dos lados DIFIERAN, y que cada lado sea
el codigo que uno declaro.** La segunda es procedencia y necesita su propia
guarda. Quedo escrita en `scripts/golden_run.sh`, con tres cortes fail-closed
antes de capturar: los puertos tienen que estar libres, el log del servidor no
puede decir `address already in use`, y **el PID que escucha tiene que ser el
que se lanzo** (o su hijo).

⚠️ Ese script encontro su propio defecto al primer intento: dejaba los backends
vivos porque `$!` capturaba el PID del **subshell** y no el de uvicorn, asi que
el `kill` del final mataba un proceso ya muerto. Es literalmente la causa de lo
que QA reporto, reproducida por la herramienta escrita para impedirla. Se
arreglo con `exec` dentro del subshell mas un `trap ... EXIT`; el control
positivo (`golden_control_positivo.log`) muestra la guarda abortando sobre el
caso real de puerto ocupado.

⚠️ **La suite r3 CAYO con 2 fallas** —`test_golden_completeness.py::TestClaveAditivaCC014::test_el_corte_asof_tambien_la_perdona` y `::test_el_detallado_NO_la_perdona`— y por eso hubo una r4. Arriba las cuento como hallazgo, que lo son, pero el hecho crudo es ese: **la ronda 3 fallo**. Las dos eran de la guarda del comparador del golden, no del codigo de produccion, y corregirla cambio `tests/`, lo que obligo a relanzar.

⚠️ **La suite r1 quedo INVALIDADA por colision PROPIA** y el log se conserva
como `suite_cc013_r1_INVALIDA_colision_propia.log`. Lance una corrida dirigida
mientras la suite completa estaba viva contra la misma base de test y le meti 5
errores en `test_api_inventory_views.py`; la evidencia esta en el log propio,
no en testimonio. La regla del repo es **un solo dueño de 5433 a la vez** y la
rompi yo. El log no se borra: un artefacto invalido borrado es indistinguible
de uno que nunca existio (#97/#99).

---

## 6. Las cuatro condiciones de QA

QA dio **NO-GO** con cuatro condiciones. Las cuatro eran correctas y las cuatro
tienen artefacto.

**C1 — el lado BEFORE del golden no era el proceso declarado.** Arriba, con la
distincion entre prueba de vida y procedencia. Guarda permanente en
`scripts/golden_run.sh`; corrida limpia en `golden_final.log` con los PIDs
verificados, los puertos libres al terminar y `EXIT=0`.

**C2 — el filtro de la tarifa sobre-IVA estaba en la pantalla equivocada.**
Arriba, en la seccion 3. Guard en `_apply_retentions` (un validador, todos los
puntos de entrada), filtro tambien en `InboundLiquidatePage`, 6 tests, plantado
PC2 en `plantado_ronda2.log`.

⚠️ **Una eleccion declarada dentro de C2: el guard nuevo corre ANTES del guard
de flag, y se deja asi.** La doctrina del repo es que el flag corta en la
primera linea (#110 F3), y mover 25 lineas es barato — pero el camino es
**inalcanzable**: los tres endpoints de `/retention-configs` estan gateados por
`require_org_flag` (#79), asi que una organizacion sin bandera no puede tener
ninguna tarifa, menos aun una `base_kind='iva'`; y el guard ademas filtra por
`organization_id`, o sea que no alcanza las de otra. Verificado contra dev: cero
tarifas con esa base en las 7 organizaciones. Se declara en vez de editarse
porque el cambio no lo pidio nadie y habria invalidado la suite en curso — que
es justo el error que costo las rondas r1 y r2.

**C3 — el smoke no decia lo que este informe afirmaba.** Era cierto y era grave:
el smoke corrio a las 22:11:52 contra un backend arrancado a las 22:11:48, y el
fix de `endpoints/sales.py` es de las 22:16:53. Su log dice `impuestos
devueltos: 0` y el informe afirmaba lo contrario. **Una afirmacion sin artefacto
es una afirmacion inventada, aunque resulte cierta despues.** Re-corrido en
`smoke_c3.log` contra un backend arrancado 14 minutos DESPUES del ultimo cambio
de `app/`, con la procedencia impresa en el log (PID que escucha + fecha del
ultimo archivo tocado): `liquidar -> 200`, los 4 impuestos en la respuesta del
PATCH con su `base_kind` y su `base_amount`, la reteIVA calculada sobre los
$19.000 de IVA y no sobre los $100.000 de subtotal, y el saldo del cliente
pasando de $462.950 a $575.900 — delta $112.950, exactamente subtotal mas IVA
menos las tres retenciones.

**C4 — los re-plantados no tenian artefacto.** `plantado_ronda2.log`, con la
diagonal exacta en los cuatro y cierre por sha256; `p9_numero.log` para P9, que
se mide por su numero.

---

## 7. Rondas de la suite

Fueron **seis**, y las cinco primeras no sirven. Cada una por su motivo, y
cuatro de los cinco motivos son mios:

| Ronda | Que paso |
|---|---|
| r1 | **Colision PROPIA.** Lance una corrida dirigida contra la misma base de test con la suite viva y le meti 5 errores en `test_api_inventory_views.py`. La regla es un solo dueño de 5433 y la rompi yo. Log conservado como `suite_cc013_r1_INVALIDA_colision_propia.log`. |
| r2 | **Edite un `.tsx` durante la corrida.** `test_reloj_de_negocio.py::TestFrontend` escanea `frontend/src` con `rglob`: un `.tsx` SI esta en el alcance de la suite. Conservada como `suite_cc013_r2_INVALIDA_edite_un_tsx_durante.log`. |
| r3 | **CAYO con 2 fallas**, las dos en `TestClaveAditivaCC014`. Cambiar `ALLOWED_ADDED` rompe la guarda que vigila esa lista, que es exactamente para lo que existe. Hallazgo legitimo del gate. |
| r4 | Verde, pero **C2 toco `app/` y dos `.tsx` despues**, asi que dejo de medir el arbol actual. |
| r5 | **La mate yo.** A mitad de corrida encontre que el camino de FALLO de `golden_run.sh` estaba roto (`set -e` mata una cadena `a && b && c` cuando el ultimo falla, asi que nunca se llegaba al `EXIT=$?` justo cuando el golden encontraba diffs). Arreglarlo toca `scripts/`, uno de los cinco directorios vigilados. Conservada como `suite_cc013_r5_INVALIDA_arregle_golden_run.log`. |
| r6 | **La que vale.** 1902 passed, EXIT=0, 0:48:05. Predije el conteo antes de verlo —1896 de la r4 mas los 6 tests de C2— y salio exacto. |

Ningun log invalido se borro: un artefacto invalido borrado es indistinguible
de uno que nunca existio (#97/#99).
