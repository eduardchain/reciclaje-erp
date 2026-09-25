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
| Suite completa | **1908 passed, EXIT=0** (0:55:47), 0 FAILED / 0 ERROR / 0 Traceback en todo el recorrido; 1908 colectados == 1908 pasados; arbol congelado desde el inicio (0 archivos, control positivo 659); el paso 2 del log estampa el sha256 del arbol medido | `suite_cc013_r9.log`, `r9_mtime.log` |
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
| r6 | **La que valia hasta la ronda 2.** 1902 passed, EXIT=0, 0:48:05. Predije el conteo antes de verlo —1896 de la r4 mas los 6 tests de C2— y salio exacto. |
| r7 | Despues de C1–C7 y de la ronda 2 de la pantalla. **1908 passed, EXIT=0**, 1:00:54, arbol congelado. Aca la prediccion **fallo**: ver 9.7. |
| r8 | Despues de la ronda de QA sobre el addendum (C11/C12/C13/C14/O1/O2). **1908 passed, EXIT=0**, 0:54:44, 19:17:01→20:11:52; 0 FAILED / 0 ERROR / 0 Traceback; 1908 colectados == 1908 pasados; arbol congelado (0 archivos en los cinco directorios, control positivo 659). La prediccion **acerto**, y esta vez la base salio de `git diff 9f2ac23 -- backend/tests/` (6 agregados / 0 eliminados, la misma base de la r7) en vez de la memoria: C11/C12/C13 extienden `t10c`, `t10d` y `t10e` y agregan el helper `_adelantar_reversion`, o sea cero tests nuevos. Durante la corrida solo se tocaron `CLAUDE.md` y este informe, los dos fuera de los cinco directorios y fuera del `rglob` de `test_reloj_de_negocio.py`. Artefactos: `suite_cc013_r8.log`, `r8_mtime.log`. |
| r9 | **La vigente**, despues de la condicion C15. **1908 passed, EXIT=0**, 0:55:47, 20:21:57→21:17:52; 0 FAILED / 0 ERROR / 0 Traceback; 1908 colectados == 1908 pasados; arbol congelado (0 archivos, control positivo 659). La prediccion **acerto** y salio de DOS mediciones: el `git diff` contra `9f2ac23` (6 agregados / 0 eliminados) **y** el sha256 de los tests, identico al de la r8 con 0 archivos de `tests/` con mtime posterior — o sea que un docstring no podia mover el numero. El log deja escrito que 5433 estaba libre y **estampa el sha256 del arbol que mide**, que al terminar coincide con el arbol. Artefactos: `suite_cc013_r9.log`, `r9_mtime.log`. |

Ningun log invalido se borro: un artefacto invalido borrado es indistinguible
de uno que nunca existio (#97/#99).

---

## 8. Addendum de la pantalla (2026-09-23) — la base de una tarifa se podia elegir y no corregir

Daniel liquido una venta de $500.000 con IVA y las tres retenciones, y la
reteIVA precalculo **`2 % de $500.000 = $10.000`**. El calculo era correcto
**dado lo que decia la tarifa**: el seeder siembra las tres configs **sin
`base_kind`** (`RETENTION_CONFIGS` solo lleva tipo y `rate_pct`), asi que la
reteIVA nace sobre el `subtotal` por el `server_default`. Lo que estaba mal era
que **no habia forma de corregirla**: el dialogo *Editar Tarifa* mandaba
unicamente el `rate`; el `base_kind` vivia solo en el formulario de CREAR. O
sea, **el paso 6 del runbook del plan —"las tres tarifas sembradas se ajustan
desde la pantalla"— era inejecutable para la base.**

El backend lo aceptaba desde el dia uno (`RetentionConfigUpdate.base_kind`, y
el endpoint lo aplica) y **ese camino no tenia ni un test**: medido con grep,
`base_kind` aparecia en 3 archivos de `tests/` y ninguno hacia PATCH.

**Arreglo**: el Select de base tambien en el dialogo de editar, **precargado**
con lo que la tarifa tenga (sin la precarga, guardar el % pisaria la base con
`subtotal` — peor que el defecto original, porque el usuario cree que
corrigio algo). Mas **4 tests del PATCH**, con tres defectos plantados:

| Plantado | Que se rompe | Prediccion | Resultado | Artefacto |
|---|---|---|---|---|
| P1 | el endpoint ignora `base_kind` | cae solo el test 1 | 1 failed / 2 passed | `plantado_base_editable.log` |
| P2 | `list_retention_rows` deja de emitir la clave | **al menos** el assert del GET (via compartida) | 1 failed / 22 passed en el archivo entero | `plantado_p2_get_sin_base.log` |
| P3 | el PATCH trata el ausente como "poner el default" | caen los DOS de PATCH parcial | 2 failed / 2 passed | `plantado_p3_patch_parcial.log` |

Los tres cierran por sha256 y `backend/app/` queda sin diff contra HEAD.

⚠️ **Los dos PATCH parciales son casos DISTINTOS y los dos tienen test**, porque
`RetentionConfigUpdate` tiene todos los campos `Optional` y eso es contrato del
API: `{is_active}` a secas es lo que manda el boton Desactivar/Reactivar
(`toggleActive`), y `{rate_pct}` a secas hoy no lo manda ninguna pantalla pero
cualquier consumidor puede. P3 tumba los dos, que es la prueba de que ninguno
sobra.

⚠️ **Lo que NO prueba P2.** Que ningun otro test del repo leyera `base_kind` de
una **respuesta HTTP** antes de este ciclo sale de un **grep sobre `tests/`**
—3 archivos lo mencionaban y los tres solo para CREAR—, no de P2, que corrio un
solo archivo de 23 tests. Dos evidencias distintas y conviene no confundirlas.

⚠️ **Lo que los tests SI prueban y lo que NO** (C2 de QA). Prueban que el PATCH
cambia la base, que **los dos** PATCH parciales (`{is_active}` y `{rate_pct}`)
no la pisan, y que una base invalida da 422.
**No prueban el precalculo de la pantalla de ventas, y no pueden**: en ventas el
servidor nunca mira la tarifa — `base_kind` llega en el payload
(`DocumentTaxCreate`) y el frontend lo toma de la fila del GET. Ese eslabon lo
cierra la pantalla, no la suite.

🔴 **C3 — lo que este arreglo abre en OTRO modulo, y hay que decidirlo antes de
prod.** Antes, la unica forma de tener una tarifa sobre el IVA era **crearla**,
y una tarifa nueva nunca habia estado en compras. Ahora una tarifa **existente**
—que las Entradas puedan estar usando— puede cambiarse de base, y al pasar a
`iva` **desaparece de las dos pantallas de compras sin ningun mensaje** (filtro
`base_kind !== "iva"`) y da 422 si alguien la manda por API. El plan ya
argumento que eso es correcto (una compra de chatarra no lleva IVA), pero ese
argumento descansa en que la tarifa diga **"sin uso aun"**, y eso se leyo en
**dev**: prod no se puede consultar desde aca.

**Runbook del paso 6, para Daniel:** antes de corregir la reteIVA en prod,
mirar en *Tesoreria → Retenciones* de SAC si dice **"sin uso aun"**.
- Si dice "sin uso aun": corregirla a **15 % sobre el IVA** y listo.
- Si ya tiene uso: **no tocarla**. Crear una **segunda** reteIVA con concepto
  (p. ej. "Ventas") y base IVA — la clave unica incluye el concepto (#79 D14),
  asi que conviven —, y dejar la de compras como esta. La decision es suya.

  🟠 **Consecuencia de esa rama, tambien decision de Daniel**: la tarjeta
  de impuestos de ventas va a ofrecer **las dos** reteIVA. Se distinguen en la
  etiqueta (lleva el concepto y el "sobre IVA"), pero si el usuario elige la de
  compras reproduce los $10.000 del hallazgo. Si se quiere que ventas no ofrezca
  una reteIVA sobre el subtotal, eso es un filtro nuevo y es decision de
  producto, no un defecto. ⚠️ **El predicado es la CONJUNCION de las dos
  cosas** — ocultar `retention_type == "reteiva" AND base_kind == "subtotal"` —
  y no una sola: solo por tipo esconderia tambien la reteIVA "Ventas" que SI
  corresponde, dejando a ventas sin ninguna; solo por base esconderia la
  retefuente y el ICA, que en ventas van sobre el subtotal y son correctas.

  ⚠️ Y un dato que afina la señal del runbook: **"sin uso aun" mide uso en
  COMPRAS**, porque se calcula contra las entidades `[Retenciones]%`
  (`retention_entities.py`). Las ventas crean entidades `[Impuestos]%`, asi que
  **una venta no apaga ese cartel**. Para lo que el paso 6 necesita saber —si la
  tarifa ya se uso en una compra— es exactamente la señal correcta.

El dialogo avisa en ambar al elegir "El IVA de la factura", en crear y en
editar con el mismo texto, porque la consecuencia cae en una pantalla distinta
de donde se toma la decision.

**Numero de referencia para la pantalla**: venta de $500.000, IVA 19 % =
$95.000, reteIVA al **15 % sobre el IVA** = **$14.250**. Ni $10.000 (2 % del
subtotal, lo sembrado) ni $1.900 (2 % del IVA). Al liquidar, la fila de
`document_taxes` queda con `base_amount = 95.000` y `rate = 15`.

⚠️ **Y tres errores mios de la misma familia en esta sesion**, que es la razon
por la que el addendum existe: le predije a Daniel `$1.900` sin verificar con
que base estaba configurada la tarifa; le dije que "la pantalla deja elegir la
base" porque un `grep base_kind` la encontro en el archivo, **sin distinguir
crear de editar**; y escribi los 3 tests leyendo el ORM, que es el **hueco (c)
de este mismo ciclo** —lo que esta guardado no es lo que el usuario recibe— y
lo corrigio QA pidiendo los asserts por HTTP y sobre la fila del GET, que es de
donde la pantalla precarga. Las tres son *medir una parte y declarar el todo*.

---

## 9. Addendum de la pantalla, ronda 2 (2026-09-23) — el orden del estado de cuenta, y el defecto que estaba en las dos mitades del modulo

Daniel liquido la Salida de Plomo #3 y sus cuatro impuestos aparecieron
**arriba** de la venta que los genera. El bloque 4b se emite despues del de
ventas justamente para que eso no pase (#112), asi que el sintoma decia que la
llave de orden (#96) los estaba subiendo.

### 9.1 Eran DOS campos, no uno, y lo mostro el arreglo a medias

Una Salida tipo venta produce **dos documentos con dos numeraciones propias**:
la Salida (serie Venta, #3) y la venta derivada (#5). El evento de impuesto
salia posicionado con los datos de la SALIDA y la venta con los suyos, o sea que
la llave **comparaba dos secuencias distintas como si fueran la misma escala**.

Mi primer arreglo cambio el numero y **el sintoma no se movio**. La razon esta
en el orden de la llave: el **instante va ANTES que el numero**, y el impuesto
traia `delivery.created_at` (el borrador, 07:29) contra `sale.created_at` (la
liquidacion, 14:52). Un arreglo a medias deja el defecto vivo **con cara de
arreglado**; lo destapo re-consultar el backend vivo, no releer el codigo.

**La regla que queda: un evento satelite hereda la posicion COMPLETA de su
documento visible, no una parte de ella.**

### 9.2 El relato de por que vivio escondido era falso. Lo dijo QA y lo medi.

Yo habia escrito —en un comentario del codigo y en el docstring del test— que
el defecto se escondia porque las dos series venian parejas (#1 → #1) y solo se
manifestaba al divergir. **Falso, y medido** (`c8_relato_refutado.log`): con el
codigo original y los numeros en 1 y 1, los impuestos salen primero igual,
porque **el instante solo ya alcanza** (la captura y la liquidacion son dos
requests distintos, asi que `delivery.created_at < sale.created_at` **siempre**).

Vivio escondido por otra cosa: **ningun test leia el orden del statement de una
Salida**. La unica asercion de orden del modulo era `tipos[0]` en T10, que es
una venta directa.

🔴 **Un comentario que explica mal un defecto guia mal el proximo test** (#97).
Corregido en los dos lugares, con el artefacto citado en el texto.

### 9.3 El orden colgaba del orden de ejecucion interno. Defecto de CLASE.

Al escribir el test del par de cancelacion aparecio que dentro de la clase 2
el desempate era `tax.reverted_at` contra `sale.cancelled_at` — o sea **el
orden en que el servicio ejecuta sus pasos**. Medido: adelantar el paso 5 de
`_reverse_liquidation` sobre el paso 1 invierte el statement (P4d). Y **el
mismo acoplamiento estaba en la venta directa** (`sale.cancelled_at` linea 584
vs `revert_taxes` linea 659), o sea que no era de la Salida: era de clase.

Un orden observable no puede colgar de un detalle que cualquiera reordena en un
refactor. El par ahora hereda el instante del dueno, con fallback a
`reverted_at` para un impuesto revertido con su dueno vivo.

### 9.4 El ABONO tenia el mismo sintoma por una causa distinta: la clase

Un abono no deriva venta (#100 D2): su factura son los dos
`service_income_accrual` de maquila y flete, que son eventos de **tesoreria
(clase 1)**, y el impuesto salia en la clase **comercial (0)**. La clase se
compara **antes** que el instante, asi que los impuestos aterrizaban arriba de
su factura sin que el instante llegara a opinar. Medido antes del arreglo:

```
['document_tax', 'document_tax', 'service_income_accrual', 'service_income_accrual']
```

⚠️ **Ningun test mandaba impuestos en un abono.** Esa mitad del modulo no tenia
ni una asercion encima, y es justo la de la **FE 2118**, la factura de abono
real de Johana.

El impuesto de un abono hereda ahora la clase, el instante y el numero del
**ultimo** de sus dos movimientos — del ultimo y no del primero, porque si no
queda en medio de su propia factura.

### 9.5 Plantado

Matriz de esta ronda. Las predicciones se escribieron en el log **antes** de
correr, y cada linea deja el **motivo** de la caida (`--tb=line`), no solo el
hecho.

| # | Defecto plantado | Prediccion | Resultado | Artefacto |
|---|---|---|---|---|
| P4a | codigo original: instante y numero propios | CAE | `assert 0 > 2` | `plantado_p4c.log` |
| P4b | solo el numero heredado | CAE (el instante va antes) | `assert 0 > 2` | idem |
| P4c | solo el instante heredado | CAE (aca decide el numero) | `assert 0 > 2` | idem |
| control | P4c **sin** la venta suelta (#1 y #1) | **NO cae** | 1 passed | idem |
| P4d | reordenar los pasos del servicio | **ya no cae** (ese es el arreglo) | 1 passed | `plantado_p4d.log` |
| P4e | el par vuelve a su instante propio | CAE | `assert 3 > 5` | idem |
| P4f | clase 0 en el abono | CAE | `assert 0 > 5` | `plantado_p4f.log` |
| P4g | clase 1 pero instante propio | CAE | `assert 0 > 5` | idem |

**El control es la mitad que importa**: P4c sin la venta suelta **pasa**, y eso
es lo que demuestra que la venta suelta no es decoracion del escenario sino la
premisa que hace que el numero llegue a decidir algo. Por eso el guard de
premisa del test es `entrega.delivery_number < venta.sale_number` y no `!=`: el
numero viejo desordena **solo en esa direccion**, y con la contraria el test
pasaria sin discriminar.

⚠️ **El primer intento del control no midio nada**: neutralice la venta suelta
con una regex que partio el archivo y pytest murio con `SyntaxError`. Se vio
solo porque pytest imprime lo que recolecto. Re-hecho sin regex, sobre una
copia del archivo. Es la familia de siempre — *un gate que no corrio se ve
igual que uno que paso* (#97/#99) — y esta vez se cayo del lado ruidoso.

### 9.6 Alcance

`money_movements.py` es camino **compartido**, asi que la suite completa es
gate. **El golden no observa esta superficie**: el cambio solo corre cuando hay
filas en `document_taxes`, y las 6 orgs que no son SAC tienen **cero**. La
corrida de gates de la seccion 5 sigue siendo la vigente para el golden.

---

### 9.7 La suite r7, y una prediccion que fallo por la BASE

**Resultado: 1908 passed, EXIT=0**, 17:46:44 → 18:47:45 (1:00:54), a archivo en
`suite_cc013_r7.log` con el `EXIT=$?` capturado DENTRO del bloque. Arbol
congelado durante la corrida: **0 archivos** con mtime posterior al inicio sobre
los cinco directorios vigilados, con control positivo de **659** (el mismo
`find` con `-newermt "2020-01-01"`, que tiene que dar cientos) y el conteo por
ruta impreso por separado. `DIRS` como arreglo de zsh, no como cadena.

**La prediccion, escrita en el log ANTES de lanzar, decia 1903. Salieron 1908.**

El error no estuvo en el resultado sino en la **base**. Yo sume "1902 de la r6
mas 1 test nuevo". La aritmetica real es 1902 + **6**, y los seis salen
nombrados de un comando, no de la memoria:

```
git diff 9f2ac23 -- backend/tests/ | grep -E "^\+ *(async )?def test_"
```

| Test | Archivo | De donde salio |
|---|---|---|
| `test_el_patch_cambia_la_base_y_el_porcentaje` | `test_purchase_retentions.py` | C1–C7 |
| `test_desactivar_y_reactivar_NO_pisa_la_base` | `test_purchase_retentions.py` | C1–C7 |
| `test_patch_solo_del_porcentaje_NO_pisa_la_base` | `test_purchase_retentions.py` | C1–C7 |
| `test_una_base_invalida_se_rechaza` | `test_purchase_retentions.py` | C1–C7 |
| `test_t10d_el_impuesto_de_una_SALIDA_va_despues_de_su_venta_derivada` | `test_sac_impuestos_ventas.py` | ronda 2 |
| `test_t10e_los_impuestos_de_un_ABONO_van_despues_de_su_factura` | `test_sac_impuestos_ventas.py` | ronda 2 |

Dos equivocaciones, las dos por recordar en vez de medir: di por incluidos en la
r6 los **4 tests de C1–C7** (la r6 corrio antes de ese addendum) y describi
`t10d` como una *extension* de un test existente cuando el diff lo muestra como
un `+def test_` entero.

Dos controles cierran que no falte ni sobre nada:

- **0 tests eliminados** en el mismo diff, o sea que ninguno de los 6 es el
  rename de otro que desaparecio.
- **`pytest --collect-only -q` da 1908**, medicion independiente del diff, e
  igual a los 1908 que pasaron: cero saltados escondidos detras del numero.

**La regla que deja: la base de una prediccion sale de un comando** —
`git diff <commit-del-numero-anterior> -- tests/` — **y no de la memoria de que
se agrego.** Predecir contra una base recordada convierte el ejercicio en un
sorteo: acierta cuando la memoria acierta, y su fallo no dice nada del codigo.

Aun asi la disciplina hizo su trabajo. El numero estaba escrito antes de correr,
asi que la diferencia **obligo a medir de donde salian los 5 antes de tocar
git**, en vez de mirar un 1908 verde, darlo por bueno y descubrir despues que
sobraban tests que nadie sabia de donde venian.

---

## 10. Ronda de QA sobre el addendum (2026-09-23) — cuatro condiciones, y ninguna la vio el plan

QA leyo el addendum de la §9 y devolvio cuatro condiciones. Tres de ellas
—C11, C12, C13— son la misma familia: **un test que dice medir algo y no lo
mide**. La cuarta, C14, es una cita mia sin artefacto.

### 10.1 C13 — P4e no medía la herencia, y mi propio log lo decia

La §9.3 cerro el acoplamiento haciendo que el par de cancelacion herede el
instante de su dueno en vez de usar `tax.reverted_at`. El comentario del test
afirmaba que **P4e** (quitar la herencia) era la plantada que medía ese bloque.

No lo es. Con el orden natural de los pasos, `tax.reverted_at` se estampa
DESPUES de `sale.cancelled_at`, asi que los dos criterios —heredar, o usar el
propio— producen el MISMO statement: el par queda debajo de la cancelacion en
los dos casos y el bloque pasa en verde con la herencia quitada.

Lo mas incomodo es que **el artefacto ya lo decia**: `plantado_p4d.log` muestra
a P4d dejando de caer al poner la herencia, y quitarla no lo devuelve. Tenia el
dato y no saque la conclusion.

**Un test de orden sobre eventos que empatan no mide el desempate.** Para
medirlo hay que separarlos a mano y en la direccion peligrosa. El helper nuevo
`_adelantar_reversion` pone por ORM el `reverted_at` **un segundo antes** del
`cancelled_at` de la venta: es exactamente el estado que dejaria un refactor
que invierta los dos pasos, y es el unico en que los criterios difieren.

Escrito en **t10c** (venta directa, donde el acoplamiento era el mismo por
CLASE: `sale.cancelled_at` en la linea 584 contra `revert_taxes` en la 659) y
en **t10d** (Salida con venta derivada). Medido:

| plantada | prediccion escrita antes | resultado |
|---|---|---|
| P4j — quitar la herencia (`_evt(liq_at, tax.reverted_at, 2, …)`) | caen t10c y t10d | **caen los dos** |
| control — arbol restaurado | pasan | **3 passed** |

La traza de t10c con P4j puesto muestra el defecto sin ambiguedad: los cuatro
`document_tax_cancellation` quedan ANTES del `sale_cancellation` de su propia
venta.

### 10.2 C11 y C12 — el camino de vuelta del abono no lo ejecutaba ningun test

`t10e` liquidaba un abono, miraba el orden y terminaba. Nunca anulaba. O sea
que `_reverse_liquidation` y `revert_taxes` **en la rama del abono** no tenian
una sola asercion encima, que es la misma forma del hueco que la §9.4 ya habia
encontrado en el camino de ida.

El tramo nuevo captura el saldo de Willard ANTES de que exista un impuesto,
liquida, verifica los cuatro saldos de entidad contra su monto (con
`assert monto != 0` por delante, para que la comparacion no pueda ser vacua),
anula, y exige tres cosas: que el par de cancelacion salga, que el orden se
conserve DESPUES de anulada, y que el saldo vuelva al punto de partida. Los
cuatro statements de entidad cierran en cero contra su saldo vivo.

Dos plantadas lo miden, y las dos caen:

| plantada | prediccion escrita antes | resultado |
|---|---|---|
| P4h — filtrar el lookup de la factura por `status` confirmado | cae el orden POST-anulacion | **cae**: `assert 0 > 5`, los 4 impuestos sobre las 2 facturas |
| P4i — no pasarle el cliente a `revert_taxes` | cae el invariante de #55, con corrido 0 contra vivo **3.234.502,74** | **cae con ese numero exacto** |

El numero de P4i se derivo antes de correr, no se recordo: anulado el abono,
maquila y flete SI se revierten en el paso 4, asi que lo que queda pegado al
cliente es `IVA − ReteFuente − ReteIVA − ICA` de la FE 2118 =
`5.638.124,04 − 1.186.973,48 − 845.718,61 − 370.929,21` = **3.234.502,74**. El
assert lo imprime igual.

P4h ademas explica por que el lookup de la factura del abono **no filtra por
status**, que a primera vista parece un olvido: anulada la Salida sus dos
accruals quedan `annulled` pero siguen en el statement, **cada uno como UN
evento anulado de clase 1**. El bloque 1 emite un evento por movimiento con su
propio `status` y no emite par de cancelacion, a diferencia de los bloques
comerciales; la lista post-anulacion del propio artefacto de P4h lo muestra
—dos `service_income_accrual` y ningun par de ellos—. O sea que la factura
sigue visible y el impuesto tiene que seguir debajo de ella. Con el filtro puesto el lookup devuelve None, el impuesto cae al fallback
de clase 0 y se sube por encima de su propia factura anulada. La razon quedo
escrita en el codigo, citando el test que la fija.

### 10.3 C14 — una cita medida de memoria

El docstring de `t10e` afirmaba una lista de eventos "medida antes del
arreglo": dos impuestos sobre dos facturas. Esa lista no salia de ningun log.
El unico artefacto era P4f, que es otra cosa.

Re-medida contra `9f2ac23` con el mismo test (`c14a_codigo_previo.log`), lo que
el codigo previo produce son los **cuatro** impuestos sobre las **dos**
facturas, con `assert 0 > 5`. Corregido, citando el log.

**Corregir una cita es escribir una, y se verifica igual.** Es la misma leccion
de la §9.2 —donde el relato de por que el defecto vivio escondido resulto
falso— aplicada al arreglo de ese mismo relato.

⚠️ Y el script que produjo esa medicion **tenia roto su camino de
restauracion**: un `cd backend` dentro del bloque dejaba sin efecto el `cp`
relativo del cierre mientras el script imprimia "restaurado". El codigo previo
quedo pegado en el arbol cerca de un minuto. Es, otra vez, la familia de
`golden_run.sh`: **el camino de fallo de una guarda solo se ejercita cuando
falla, asi que hay que ejercitarlo a proposito**. Desde esta ronda el cierre de
una ventana de plantadas compara contra un sha256 **escrito antes de plantar**,
y la palabra "restaurado" es el RESULTADO de esa comparacion, no una frase que
el script imprime al terminar.

### 10.4 La ventana de plantadas

Las tres plantadas de esta ronda corrieron en **una sola ventana** con `:8001`
detenido: ese proceso sirve la pantalla de Daniel con `--reload` sobre el arbol
de trabajo, o sea que una plantada viva es codigo ejecutandose en su pantalla.

- Ventana: **19:14:30 → 19:16:08**, un minuto y treinta y ocho segundos.
- Hash del arbol `backend/app` escrito ANTES de plantar:
  `115d5568…9584f93c`. Al cerrar, medido: **identico**, mas `cmp` por archivo y
  `git status` sin rastro.
- Control con el arbol restaurado: **3 passed**.
- `:8001` relanzado con procedencia en el log: PID 15892, arrancado 19:16:08,
  posterior al ultimo cambio en `app/` (19:15:36), `HTTP 200` en health.

Artefacto: `plantado/plantado_c13.log`.

### 10.5 La suite r8, y una prediccion que esta vez salio de un comando

**Resultado: 1908 passed, EXIT=0**, 19:17:01 → 20:11:52 (0:54:44), a archivo en
`suite_cc013_r8.log` con el `EXIT=$?` capturado DENTRO del bloque. En todo el
recorrido, no solo en el resumen: **0 FAILED, 0 ERROR, 0 Traceback**. Y
**1908 colectados == 1908 pasados**, o sea cero saltados escondidos detras del
numero.

Arbol congelado, medido con el arreglo de zsh y su control positivo
(`r8_mtime.log`): 0 archivos tocados despues de las 19:17:01 en `backend/app`,
`backend/tests`, `backend/alembic`, `backend/scripts` y `frontend/src`
—excluyendo `__pycache__`—, contra un control positivo de **659** archivos con
`-newermt 2020-01-01`. Durante la corrida solo se tocaron `CLAUDE.md` y este
informe: los dos estan fuera de los cinco directorios **y** fuera del `rglob`
de `test_reloj_de_negocio.py`, que es el unico test de la suite que mira
`frontend/src` desde afuera.

**La prediccion, escrita en el log ANTES de lanzar, decia 1908. Salieron 1908.**

Lo que vale no es el acierto sino de donde salio la base. La r7 fallo por
sumar contra un numero recordado; esta vez la base salio de un comando:

```
git diff 9f2ac23 -- backend/tests/  ->  6 def test_ agregados, 0 eliminados
```

Esos 6 son los mismos que ya contaba la r7, o sea la **misma base**. C11, C12 y
C13 extienden `t10c`, `t10d` y `t10e` y agregan el helper
`_adelantar_reversion`, que no es un test: cero tests nuevos, luego 1908.

El contraste entre las dos rondas es el punto y por eso las dos quedan escritas:
**mismo numero, y con base medida acierta donde con base recordada habia
fallado**. Un acierto sobre una base recordada no habria probado nada; habria
sido el mismo sorteo, ganado.

### 10.6 C15 — un comentario correcto en su conclusion y falso en su mecanismo

QA leyo el docstring de `_abono_invoice_pos` y encontro que describe un
mecanismo que no existe. Decia:

> al anular la Salida sus dos accruals quedan `annulled` pero SIGUEN en el
> statement **como par de cancelacion**

Es falso. El **bloque 1** del statement (`money_movements.py:925-946`) emite
**UN** evento por movimiento, con su propio `status`:

```python
for m in db.scalars(mm_query).all():
    _evt(m.date, m.created_at, 1, ..., status=m.status, ...)
```

Los pares con `status` anulado salen de los bloques comerciales —2, 2b, 2c, 3,
4, 4b, 5 y 6— y **nunca de un movimiento de tesoreria**. Un accrual anulado
aparece una sola vez, como un evento anulado de clase 1.

**Lo delato mi propio artefacto**, no una relectura: la lista que imprime la
plantada P4h al caer es

```
['document_tax' x4, 'service_income_accrual' x2, 'document_tax_cancellation' x4]
```

Dos `service_income_accrual` y **ningun par de ellos**; los cuatro
`document_tax_cancellation` son del bloque 4b.

**La conclusion del comentario si era correcta** —la factura anulada sigue
visible, luego el impuesto tiene que seguir debajo— y por eso el codigo estaba
bien y ningun test cayo. Lo falso era el **mecanismo**. Eso no es cosmetico en
este ciclo: todo el arreglo de C13 trata del orden **dentro de la clase 2**, y
un comentario que afirma que la factura del abono tiene un par en esa clase
invita al proximo lector a razonar contra un evento que no existe. Es la
familia de #97 por segunda vez en la misma ronda.

**Un comentario correcto en su conclusion puede ser falso en su mecanismo, y el
mecanismo es lo que el proximo lector usa.**

Corregido en los tres sitios: `app/`, `CLAUDE.md` y este informe. La version
nueva nombra el bloque 1 y **cita la lista de P4h**, para que la afirmacion
lleve el artefacto pegado en vez de ser otra descripcion plausible.

**El cambio esta probado como SOLO docstring, y anclado al arbol de la r8** en
vez de a HEAD (artefacto `c15_artefacto.log`):

| Chequeo | Resultado |
|---|---|
| sha256 del archivo de la r8, reconstruido con el reemplazo inverso | `1607ecd1…accac3e2` — **identico** al medido en la r8 y cotejado por QA |
| `ast` sin docstrings, antes vs ahora | identico |
| literales STRING | 516 vs 516, **1** distinto = el docstring editado |
| control positivo: cambio de codigo real inyectado | el mismo comparador da **False** |
| ruff sobre `backend/app` | All checks passed |

⚠️ Dos tropiezos propios en el camino, los dos de la misma clase —medir contra
la referencia equivocada—: el primer intento del artefacto comparo contra
**HEAD**, que trae el ciclo entero y no dice nada sobre C15; y escribi
"archivos de tests tocados por C15: 2" cuando ese 2 tambien era contra HEAD. Lo
correcto son **0** archivos de `backend/tests` con mtime posterior al inicio de
la r8 y `sha256(test_sac_impuestos_ventas.py) = 95fec676…`, el mismo que QA
cotejo. **El ancla de un "no cambio nada" es el arbol que corrio la suite, no
el ultimo commit.**

**La r9 cierra C15: 1908 passed, EXIT=0**, 20:21:57 → 21:17:52 (0:55:47), 0
FAILED / 0 ERROR / 0 Traceback en todo el recorrido, 1908 colectados == 1908
pasados, arbol congelado (0 archivos en los cinco directorios, control positivo
659). La prediccion se escribio antes de lanzar y salio de **dos** mediciones
independientes —el `git diff` contra `9f2ac23` y el sha256 de los tests,
intacto desde la r8— que apuntan al mismo sitio: un docstring no puede mover el
numero, y no lo movio.

Y esta corrida estrena dos cosas en el runbook del log, las dos por lo que
aprendio este ciclo:

- **Deja escrito que 5433 estaba libre** antes de arrancar (`pgrep` con el
  truco del corchete y `pg_stat_activity` en 0), porque la r1 se invalido por
  una colision que yo mismo cause.
- **Estampa el sha256 del arbol que va a medir** en un paso propio. Eso cierra
  la cadena hacia el commit sin depender de la memoria de nadie: al terminar,
  los sha del paso 2 son exactamente los del arbol, y son los mismos contra los
  que QA verifica el commit. Es la version de log de la leccion de C15: **el
  ancla de un "no cambio nada" es el arbol que corrio la suite.**
