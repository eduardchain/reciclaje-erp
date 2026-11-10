# Plan — Carga inicial de SAC, ronda 1 (ensayo local con el balance del 31-oct)

**Versión:** v1.0 · 2026-11-10 · para Daniel y QA
**Fuente de los datos:** Google Sheet «SAC - Carga inicial (borrador sobre balance al 31-oct-2026)».
**Alcance:** SOLO la base de desarrollo (5434), sobre una SAC recién reseteada. Producción no se toca en este plan.

## 1. Qué es esto

Johana manda un balance cada 7 a 15 días. Cada balance es una ronda, y en cada ronda se hace esto:

1. Se cruza el Sheet contra el balance nuevo (eso ya se hizo con el del 31-oct).
2. Se resetea la SAC local.
3. Se carga todo desde cero con la fecha de ese balance.
4. Sale un informe de conciliación por rubro: Johana / sistema / diferencia / por qué.

Una diferencia que no tiene explicación es lo que se corrige: en el Sheet, en el cargador o en el sistema. Cuando la carga cuadre sola, el paso siguiente (fuera de este plan) es registrar una semana de operación en paralelo y compararla contra el balance siguiente.

La carga no toca el estado de resultados. Es un **invariante**, no un deseo, y el informe lo verifica (§6).

## 2. Cómo corre una ronda

El orden importa: los saldos se cargan **antes** de que el seeder siembre los maestros (G1).

| Paso | Qué | Dónde queda |
|---|---|---|
| 1 | Exportar el Sheet a `.xlsx` (Drive) | scratchpad de la sesión. **No se commitea**: tiene saldos y nómina reales |
| 2 | `seed_sac_org.py --reset --org-vacia`: flag nuevo que crea la org con sus usuarios y se detiene. Solo local: el guard de `--reset` ya rechaza un `--api-url` remoto | BD de dev |
| 3 | `load_sac_opening.py --fase saldos`: terceros y cuentas de dinero con su saldo, incluidos Willard S.A y Caja Circunvalar | BD de dev |
| 4 | `seed_sac_org.py` en modo provisión: siembra el resto (bodegas, materiales, cuentas en kilos, tarifas…) y reutiliza por nombre lo que ya existe | BD de dev |
| 5 | `load_sac_opening.py --fase resto`: inventario, kilos, precio del plomo, activos y entradas | BD de dev |
| 6 | `load_sac_opening.py --conciliar` | informe en el scratchpad; el resumen va a Daniel |

Los pasos 3 y 5 imprimen el plan sin escribir nada salvo que lleven `--apply`. `scripts/ronda_local.sh` corre los pasos 2 a 6 en orden (el 1 es manual) y se detiene en la primera falla. No corre contra un backend remoto: `--reset` y `--ensayo` lo rechazan. Las credenciales van por `SEED_SU_EMAIL` / `SEED_SU_PASSWORD`, nunca en la línea de comandos.

## 3. De cada pestaña al sistema

Solo se cargan las filas con «¿Entra al sistema?» = **Sí**. «No», «Preguntar», «Repartir» y «Ver hoja …» no se cargan y van al informe con su motivo; ninguna fila desaparece en silencio. La única excepción es «Ver hoja Entradas» en Inventario, que se descuenta de su bodega (fila de Entradas, abajo). Todas las fechas de negocio son el corte (31-oct), salvo las entradas, que conservan su fecha propia.

| Pestaña | Va a | Cómo |
|---|---|---|
| Terceros | `POST /third-parties/` con `initial_balance` = columna D (con signo) y la categoría según el Tipo (tabla de §4) | Las filas «Sin saldo» con «Sí» se crean en 0, como maestros |
| Terceros, Tipo «Willard (se suman en un tercero)» | Un solo saldo neto sobre **Willard S.A**, que el cargador crea antes que el seeder | Ver G1 |
| Cuentas | `POST /money-accounts/`; EFECTIVO va a **Caja Circunvalar**, que también se crea antes que el seeder | Ver G1 |
| Inventario | `POST /inventory/adjustments/increase`, una por (material, bodega), con el marcador «Carga inicial migracion …» (#28: el marcador saca el ajuste del P&L) | Las filas del mismo material y bodega se suman; costo = valor/cantidad, o sea que el valor se conserva |
| Inventario, «Crear material nuevo» (5) | Material nuevo + perfil kg (`none`, compra regular, `lead_product='none'`) | Códigos propuestos en G7 |
| Kilos | `POST /kg-ledger/movements` manual, motivo «Saldo inicial al corte»: Willard baterías CV; intersede con etapa `horno` y con etapa `crisol` | Willard drosses va vacío (lo lleva planta): no se carga |
| Kilos, precio | `POST /lead-market-prices` con vigencia desde el corte | El balance muestra la deuda con Willard valorada (#110) |
| Activos fijos | `POST /fixed-assets/` con `historical_load` | Ver G4 |
| Créditos | Un tercero por fila con su saldo, en la categoría Obligaciones Financieras (las líneas de Abdel como «ABDEL BARAKATT - <línea>», decisión de Daniel del 10-nov). **Sin** obligación todavía | Ver G3 y G10 |
| Créditos, filas de intereses | Un tercero por fila con su saldo, en la categoría Pasivo | Decisión de Daniel del 10-nov: es deuda causada, no gasto |
| Entradas por liquidar | `POST /inbound-orders/` tipo compra, sin proveedor (#93), en estado Registrada; el número viejo va en la remisión | No mueve inventario ni saldos hasta liquidarla, igual que en el balance de Johana |
| Inventario, filas «Ver hoja Entradas» (compras por liquidar) | Se **descuentan** de su bodega (columna G, obligatoria en esas filas), no se excluyen | El material ya está en la bodega de Johana pero la compra no: si se carga bruto, la entrada lo vuelve a sumar al liquidarse. Lo que Inventario descuenta tiene que ser **exacto** lo que Entradas abre, por material y bodega; si no, la carga se detiene. Corregido al construir: la v1.0 del cargador lo mandaba a exclusiones |
| Gastos, Catálogo, No se maneja, Preguntas | Nada | Ver §5 |

## 4. Reglas de la carga

- **Tipo → categoría.** Cliente → `Cliente`; Proveedor de material → `Proveedor Material`; Proveedor de servicios → `Proveedor Servicios`; Socio → `Socios`; Empleado → `Empleados` (nueva, ver G2); crédito → `Obligaciones Financieras` (nueva); intereses → `Pasivo`. Un Tipo que no está en esta lista detiene la carga.
- **Se lee por encabezado, no por posición.** Si falta una columna esperada o cambió su nombre, la carga se detiene y dice cuál. Un Sheet reorganizado no puede leerse corrido.
- **Nombres repetidos** entre las filas «Sí» de una pestaña detienen la carga. BODEGA BOGOTA aparece dos veces, pero las dos con «No», así que no cuenta.
- **Los terceros y cuentas que también define el seeder** (Willard S.A, Green Loop y Caja Circunvalar) los crea el cargador, con el nombre, las categorías y el tipo del seeder. Esos datos se importan de `seed_sac_org.py`: hay una sola fuente. Así el seeder los encuentra en el paso 4 y no los duplica. GREENLOOP, del Sheet, es el Green Loop del seeder.
- **Las fases se cuidan el orden.** `saldos` se niega a correr si la org ya tiene algo de lo que siembra el seeder (señal de que el paso 4 ya pasó, y el saldo de esas entidades no se podría poner). `resto` se niega si faltan las bodegas, los materiales o las cuentas en kilos.
- **Una fila «Sí» incompleta** (sin tipo, sin material o sin bodega) se salta y se informa con `--ensayo`. Sin `--ensayo`, detiene la carga.
- **Una org que ya tiene carga** (algún ajuste con el marcador) hace que el cargador se niegue a correr. Así una segunda corrida no duplica nada.
- **`--ensayo` se niega contra un backend que no sea local**: es el mismo criterio del guard de `--reset`. Los valores provisionales (G4) solo existen con `--ensayo`.

## 5. Lo que queda fuera de la ronda 1

| Qué | Por qué | Efecto en la conciliación |
|---|---|---|
| Filas «Sede (no es tercero)»: Bodega Bogotá, Planta Juan Mina | En el sistema son sedes; entre ellas no hay deuda en pesos (#84) | Diferencia de criterio, con nombre propio |
| NÓMINA POR PAGAR, PROVISION IVA, PROVISION RETEFUENTE | Pasivos reales marcados «No». Decide Daniel (Q-56) | Diferencia nombrada en CxP |
| Filas «Preguntar»: TARJETA BBVA (Q-60), CI ACA ALUMINIOS, COMPRAS POSCONSUMO ACOR, CONSIGNACIONES POR IDENTIFICAR, PLANTA B PB-SN (Q-48), FAC 2194-2195 RECIMETALES (Q-59) | Sin respuesta | Diferencia nombrada |
| Los 6 terceros nuevos del 31-oct que no tienen Tipo | No hay a qué categoría mandarlos | Diferencia nombrada (G6) |
| Inventario con saldo neto negativo: SCR-LSB (Q-54), POL-DUC (Q-46) | `increase` exige una cantidad positiva; un saldo inicial negativo no se carga como entrada | Diferencia nombrada (G5) |
| PB LINGOTE POSC | Va por Kilos: el sistema lo muestra como deuda valorada, no como inventario | Se cruza contra la línea `lead_debt_willard` |
| Depreciación acumulada global | Hay que repartirla activo por activo (Q-52) | Diferencia nombrada en activos |
| Tasas de los créditos y causación de intereses | No hay tasas (G3) | Ninguna al corte |
| Pestaña Gastos (categorías) | Es el P&L de octubre, no el balance de apertura | Ninguna |
| Kilos de drosses | Los lleva planta: hay que pedírselos a Hugo | Ninguna en pesos |

La ronda 1 carga **lo que dice el Sheet hoy**. Cuatro decisiones que siguen abiertas pueden cambiar filas que hoy entran: EXPO, CRISOL, ACOR y MATERIALES WILLARD como inventario de Juan Mina; Hornos Aluminio como cuenta por cobrar; ECO ALLOYS NUEVO como el mismo cliente (hoy va separado); y los préstamos de Juan Guillermo Alzate y Reciclaje de la Costa en terceros aparte. Cambiar una es cambiar una celda y volver a correr.

## 6. Vacíos que encontré al validar contra el código

**G1 — Un saldo de apertura no se le puede poner a lo que el seeder ya creó. Resuelto por orden.** `initial_balance` existe solo al crear un tercero o una cuenta (`ThirdPartyUpdate` y `MoneyAccountUpdate` no lo tienen), y el seeder siembra **Willard S.A** y **Caja Circunvalar** en 0.
- «Eliminarlos» no sirve como suena. El sistema solo desactiva, y Willard S.A es por un CHECK el titular de dos cuentas en kilos, que las salidas validan.
- Daniel lo resolvió el 10-nov: lo de la SAC de producción no es real y no hay que conservarlo. Entonces no hace falta crearlos en 0. Se crean **primero, ya con su saldo** (paso 3), y el seeder los reutiliza: `create_accounts`, `create_third_parties` y `create_kg_accounts` buscan por nombre y amarran la cuenta en kilos a ese Willard (verificado en `seed_sac_org.py:794-957`).
- Costo: un flag nuevo en el seeder (`--org-vacia`), cero código en `app/`, y los estados de cuenta arrancan con su saldo inicial, sin líneas de más.
- Hay un endpoint viejo, `POST /third-parties/{id}/balance`, que mueve `current_balance` sin crear un movimiento. Queda descartado: rompe el invariante de #55 (`inicial + movimientos == saldo`), así que el estado de cuenta y el balance histórico dejan de cuadrar.

**G2 — Faltan dos categorías de tercero.** El sistema trae por defecto Proveedor Material, Proveedor Servicios, Cliente, Socios, Genérico, Provisión y Pasivo. No hay **Empleados**, y el módulo de créditos exige un tercero inversionista con una categoría que contenga «obligaci» (`financial_obligation.py:250`). El cargador crea las dos: `Empleados` como genérico (el saldo positivo cae en «otras cuentas por cobrar») y `Obligaciones Financieras` como inversionista.

**G3 — Ningún crédito tiene tasa ni fecha de inicio**, y una obligación las necesita. En la ronda 1 cada crédito entra como tercero con su saldo, ya en la categoría correcta. Cuando lleguen las tasas se convierte con `mode: "from_balance"`, que toma ese saldo como capital. Mientras tanto el sistema no causa intereses. En el ensayo no importa; en producción, la fecha de conversión es la que decide desde qué mes se causan (`accrual_start_period`).

**G4 — Ningún activo tiene fecha de compra, vida útil ni valor residual (Daniel eligió la vida útil provisional el 10-nov).** Son 39, y 38 con «Sí» (PLANTA B PB-SN está en «Preguntar»). Sin vida útil no hay cómo crear un activo. Dejarlos fuera le quita al balance unos $12.600 millones netos, y la comparación de activos y patrimonio deja de decir algo.
- **Propuesta, solo en el ensayo:** se cargan a su valor del balance, con fecha de compra = corte y una vida útil provisional que el nombre del activo marca como «(vida útil provisional)». La depreciación no se aplica en el ensayo. El cargador se niega a usar valores provisionales sin `--ensayo` (§4), así que esto no puede llegar a producción por accidente.
- Para depreciar hace falta una categoría de gasto: el cargador crea «Depreciación».

**G5 — Un saldo inicial negativo no se carga.** SCR-LSB queda en −14 kg y POL-DUC en −33.825 kg netos: este no tiene fila en bodega, solo la de compras por liquidar. Quedan fuera con su motivo. Es la Q-54 y la Q-46.

**G6 — Hay seis filas nuevas del 31-oct con «Sí» y sin Tipo** (LINA RESTREPO, INVERSIONES VIRA, ECONORTE, FABIAN TAVERA, ALBERT ALUMINIO, HAROLD BOHORQUEZ). Se saltan y se informan. Llenar la celda de Tipo basta para la ronda siguiente.

**G7 — Materiales nuevos sin código.** Propuesta: PLO-BAL (plomo balancín), PLO-ANT (plomo antimonial), EST-PLA (estaño planta), TAP-MUP (tapas de moto y UPS), ESC-EST (escoria de estaño). Todos en kg y `lead_product='none'`: marcar uno de más reabre el defecto de #103. La columna «Material en el sistema» del Sheet se corrige con estos códigos.

**G8 — El precio del plomo no tiene fecha.** Se usa el corte, porque el precio sale del lingote de ese mismo balance.

**G9 — La Sede de las cuentas de dinero no se puede fijar por API** (`MoneyAccountCreate` no expone `warehouse_id`). Se ignora: no cambia ningún saldo.

**G10 — Hay nombres del sistema que viven en notas de texto libre, y un cargador no debe leer notas.** En Créditos, el nombre de cada tercero (por ejemplo «ABDEL BARAKATT - Préstamo») está solo en la columna «Nota nuestra». En Cuentas, la columna «Cuenta en el sistema» mezcla un nombre con una instrucción («Crear: Cta Cte BBVA», «Crear cuenta nueva»). Propuesta, que hago yo en el Sheet antes de correr:
- Créditos gana una columna «Tercero en el sistema»;
- en Cuentas, «Cuenta en el sistema» queda con el nombre solo;
- en Inventario, «Crear material nuevo» se reemplaza por los códigos de G7.

Si existe o hay que crearlo lo decide el cargador al buscar el nombre, no el texto de la celda. Con esto las dos filas de intereses de Abdel quedan con nombres distintos y no se suman por accidente.

**Hallazgo fuera de alcance, para Daniel.** `POST /third-parties/{id}/balance` (el del G1) escribe saldos con el permiso **`third_parties.view_balance`**: un permiso de ver que escribe, y lo hace sin movimiento. La pantalla no lo usa (grep vacío en `frontend/src/services`), pero cualquier rol con ese permiso lo alcanza por API, en las tres orgs. No se arregla en este plan.

## 7. El informe de conciliación

Hay dos chequeos, y no hay que confundirlos:

1. **Lo cargado contra el sistema, entidad por entidad.** Se compara con lo que mandó el cargador:
   - el saldo **vivo** de cada tercero y cada cuenta de dinero (`current_balance`);
   - el valor de cada activo;
   - el stock y el valor de cada material, por bodega;
   - cada cuenta en kilos, incluidas las etapas horno y crisol de intersede;
   - el precio vigente del plomo y la deuda en plomo valorada;
   - el número de entradas abiertas.

   **Tiene que dar cero en todas.** Una diferencia acá es un defecto nuestro o del sistema, nunca del Sheet.

   El corte se cubre en agregado y no entidad por entidad. El Balance General al corte (`as_of_date=2026-10-31`) tiene que ser campo por campo igual al de hoy, y cada campo distinto cuenta como falla. Como en la ronda no se registra nada después de la carga, «vivo» y «al corte» dan lo mismo para cada entidad. Ese supuesto es justo lo que verifica la igualdad entre los dos balances.
2. **Johana contra el sistema, por rubro** (los seis del Inicio del Sheet): total de Johana = cargado + excluido, y cada exclusión va con su fila y su motivo (§5). Los rubros del sistema salen del Balance General vivo. **Lo que no se explique tiene que dar cero.**

A eso se le suman dos invariantes que se imprimen con su número:
- el P&L desde 2000-01-01 hasta hoy da $0, o sea que la carga no tocó resultados (cubre el corte y cualquier cosa posterior);
- activos − pasivos = patrimonio.

⚠️ El segundo es tautológico, porque el patrimonio es residual (#110). Se imprime para leerlo, no cuenta como chequeo.

El informe queda en el scratchpad porque tiene cifras reales. A Daniel le llega el resumen por rubro y la lista de diferencias sin explicar.

## 8. Diseño del código

- Archivo nuevo `backend/scripts/load_sac_opening.py`. Reutiliza `APIClient` y los helpers de parseo de `migrate_org.py`, que no se modifica.
- Tres capas:
  - `leer_libro(path)`: lee por encabezado y valida columnas;
  - `armar_plan(filas, corte, ensayo)`: función **pura** que devuelve los pasos (llamada + payload) y las exclusiones con su motivo;
  - `aplicar(plan, api)` y `conciliar(plan, api)`: las únicas que hablan con el backend.
- La simulación imprime el plan, así que toda regla de §4 y §5 se ve antes de escribir nada.
- Tests en `backend/tests/test_load_sac_opening.py`, sobre `armar_plan` y la aritmética de `conciliar`, con un libro sintético en memoria (sin BD):

| # | Qué fija |
|---|---|
| T1 | Solo «Sí» entra; cada otro valor de «¿Entra?» llega a exclusiones con su motivo |
| T2 | El signo: «Por pagar» da saldo negativo |
| T3 | Las filas Willard se suman en un solo saldo neto sobre «Willard S.A», con las categorías que se importan del seeder; ningún paso usa `/balance` |
| T4 | Una fila «Sí» sin tipo: exclusión con `--ensayo`, error sin él |
| T5 | Un nombre «Sí» repetido es un error |
| T6 | Inventario: se agrupa por (material, bodega), el valor se conserva al centavo, y un neto ≤ 0 va a exclusión |
| T7 | Un valor provisional sin `--ensayo` es un error; `--ensayo` contra una URL remota es un error |
| T8 | Crédito → Obligaciones Financieras; intereses → Pasivo; Empleado → Empleados |
| T9 | Un encabezado faltante o renombrado detiene la lectura y nombra la columna |
| T10 | Conciliación: total de Johana = cargado + Σ excluido; y una diferencia sembrada entre cargado y sistema sale como «sin explicar» |
| T11 | Si la org ya tiene el marcador, el cargador se niega a correr |
| T12 | Todos los pasos llevan la fecha del corte (las entradas, la suya), nunca la del reloj: misma regla que `test_reloj_de_negocio` |
| T13 | `saldos` se niega si ya existe una entidad del seeder; `resto` se niega si faltan las del seeder; GREENLOOP sale con el nombre del seeder |

- **Plantado de defectos**: la matriz defecto × test se fija **antes** de plantar. Como nada se commitea antes del GO de QA, se congela con su sha256 en el scratchpad, y el sha256 se cita en el informe. Ejemplos: quitar el marcador, invertir el signo, leer por posición, tragarse una fila «Preguntar».
- **Prueba de verdad:** la ronda 1 corrida contra la SAC local reseteada. El informe tiene que mostrar el chequeo 1 en cero en todas las entidades y el P&L en $0. Con eso, más los tests y el plantado, va a QA.

## 9. No regresión

Este plan **no toca `app/`, ni el frontend, ni migraciones**. Lo que cambia es un script nuevo con su archivo de tests, y el flag `--org-vacia` del seeder: un corte después de crear los usuarios, que solo existe junto con `--reset`, o sea solo en local.
- El golden no aplica, y no por pasar sino porque no hay superficie que observar: ninguna ruta, schema ni consulta cambia.
- Tampoco hace falta la suite completa: corren el archivo nuevo, `test_reloj_de_negocio.py` (escanea `tests/` y el archivo nuevo vive ahí) y `ruff`.
- El modo provisión del seeder, que es el que corre contra producción, no cambia: el flag nuevo se rechaza sin `--reset`.

## 10. Después de esta ronda

- Cada balance nuevo: cruzar el Sheet, resetear, cargar y conciliar. Es el mismo comando.
- Producción, cuando la carga cuadre sola. Como lo de la SAC de producción no es real (Daniel, 10-nov), la limpieza puede dejar de ser «anular lo simulado» y pasar a ser «dar de baja la org SAC y armar una nueva con este mismo orden». La baja es una desactivación: no se borra nada.
  - Eso lo decide Daniel en su momento, con lo que cuesta: cambia el id de la org, hay que volver a amarrar a los cinco usuarios y volver a encender los flags.
  - La carga real lleva dos confirmaciones, como en `/migrate-client`.

  Ese es otro plan.
