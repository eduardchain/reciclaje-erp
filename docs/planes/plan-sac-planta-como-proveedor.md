# Plan — Planta Juan Mina como proveedor de maquila (SAC)

**Versión**: v1.1 (2026-11-17) · **Cliente**: SAC · **Pedido de**: Daniel, a partir de lo que Johana pide ver en su balance

**Estado**:
- La v1.0 (sha256 `9b3be6f9…`) recibió **NO-GO de QA** (sesión `d724e9a0…`, «QA Ecobalance»). QA dijo que el diseño es correcto, pero puso siete condiciones (C1–C7) y seis observaciones (O1–O6).
- Esta v1.1 las incorpora. Las marcas **[C#]** y **[O#]** indican de dónde sale cada cambio.
- **No se implementa sin el GO de QA y la autorización de Daniel.**

## 0. El pedido

SAC va a operar el sistema con las tres sedes **tal como está construido**: traslados, crisol y Salidas de Plomo. Johana, en cambio, lleva a la planta Juan Mina como un **proveedor**: le debe en pesos las maquilas y le resta lo que le paga.

Al 31-oct esa cuenta era −$639,3 M. Neteada contra Manufacturas Silíceas queda en −$581,2 M (Q-44). Se cargó en producción como el tercero pasivo PLANTA JUAN MINA.

Johana confirmó por WhatsApp el **viernes 13-nov** (Q-61, con sus palabras) qué mueve esa cuenta **[C7]**:
- la maquila de $1.500 por kg de plomo al mandar baterías a planta: *"SI, y se le abona a planta"*;
- los $300/kg del crisol al vender plomo puro: *"SI"*;
- los $1.248/kg del abono de materiales, los $566/kg del abono de baterías, y restarle los pagos: *"SI"*.

Hoy el sistema registra esas maquilas como un **par interno**: un gasto en la sede que paga y un ingreso en planta, los dos sin tercero y sin cuenta. En el consolidado se cancelan. Por eso hoy pasa esto:
- el tercero PLANTA JUAN MINA solo vería los pagos, y su saldo se iría al lado contrario;
- el balance no mostraría la deuda con planta;
- el estado de resultados no mostraría la maquila como gasto de SAC, que es como ella la ve.

Lo que **no** cambia es el inventario. El de ella sí incluye planta y crisol: JUAN MINA, CRISOL y BODEGA J.M. aparecen en el balance del 31-oct, y el 11-ago dijo *"un solo inventario, que es el que yo valorizo"*. Inventario y kilos quedan como están.

## 1. Validación de requisitos (gaps)

| # | Gap | Cómo lo trata el plan |
|---|---|---|
| G1 | **No se le preguntó por la maquila del retorno de dross** ($1.500/kg sobre el plomo, #109), que es la quinta emisora. Es inferencia de grado (c), pero fuerte: #107 dice que el retorno *"genera una nueva maquila"*, la misma del horno, y Q-61 dice que esa *"se le abona a planta"* **[O4]**. | Entra en el alcance. Se le pregunta con una línea antes del deploy. **Si no contesta antes del deploy, se despliega incluida** y se le avisa. Si después dice que no, sale un ciclo chico que saca esa emisora del helper, y los causados de dross ya hechos se corrigen con un cruce entre terceros. |
| G2 | Su último *"SI"* contesta a *"¿Es así, o le entra algo más?"*. Se lee como "es así". | Se asume que no le entra nada más. Si aparece otro concepto, es un ciclo aparte. |
| G3 | La maquila del traslado nace **al recibir** en planta, no al despachar (#84). | No cambia. Alguien tiene que registrar la recepción en planta, que es parte de "operar tal cual". Va en el runbook. |
| G4 | Mientras el setting esté puesto, el resultado por sede (#84) deja de mostrar la maquila: un gasto causado da $0 por sede. | Declarado en D8 y fijado por T11. |
| G5 | Volver al modelo de sedes (fase 2) no convierte lo ya causado. | Declarado en D9. La anulación de un documento viejo sigue funcionando después del cambio (D4, T13). |
| G6 | **Supuesto [O2]:** los gastos propios de planta (nómina, gas, energía de Juan Mina) no se registran en esta organización. | Si se registraran, el consolidado contaría dos veces el costo de planta: una por la maquila y otra por sus gastos. Hay que decírselo a Johana con el runbook. |
| G7 | **Johana ya está registrando en producción.** El 17-nov, entre 09:16 y 09:32, registró dos entradas Willard (confirmadas) y una entrada de compra (revisada), todas del 3-nov. Todavía no hay traslados, Salidas ni documentos de crisol. | Una maquila que nazca **antes** de poner el setting queda como par interno y el setting no la convierte. Hasta el deploy conviene que no registre traslados a planta, Salidas ni crisol. Si alguno se registra, se corrige uno a uno anulándolo y registrándolo de nuevo después del deploy. |

## 2. Decisiones

**D1. Un setting, no un flag más un id: `plant_third_party_id`** (string UUID o `None`) en `OrgSettingsPayload` y `SETTING_DEFAULTS`. La clave va en los dos lugares, porque sin la del backend `get_org_setting` lanza KeyError (#80 F2).
- `None`, que es el valor de hoy en las 7 organizaciones: el par interno de siempre, byte a byte.
- Con un id: las cinco maquilas se causan como deuda con ese tercero.
- Una sola clave hace imposible el estado "prendido sin tercero". El frontend no la necesita.

**D2. Un solo punto de emisión.** Helper nuevo `emit_plant_maquila(...)` en `app/services/plant_maquila.py`. Recibe lo que hoy arma cada emisor: monto, categoría, descripción, `source_type`/`source_id`, tarifa, fecha, bodega del gasto y bodega del ingreso, unidad de negocio y usuario.
- **Sin el setting** crea el par exactamente como hoy, con `transfer_pair_id` cruzado.
- **Con el setting** crea **un** `expense_accrual` vía `money_movement._create_movement`:
  - tercero = planta y cuenta NULL;
  - categoría del lado del gasto, que se conserva ("Maquila Intersede" o "Crisol Refinación");
  - bodega del lado del gasto, que es la sede que factura;
  - la misma firma `source_type`/`source_id`/`tariff_id` que hoy.
- 🔴 **[O1] `_create_movement` no aplica efectos.** El helper hace `planta.current_balance -= amount`, igual que la comisión del recolector (#83, `purchase.py:570`). La reversa ya existe: es la rama `expense_accrual` (`+=`) de `_reverse_effects` (`money_movement.py:1816`). P7 cubre el signo.
- Los cuatro sitios que hoy emiten pasan a llamar al helper:
  - `transfer._emit_maquila_pair`, que cubre `receive` y `resolve`;
  - los dos de `willard_delivery`: el diferencial del crisol, y el reparto de materiales y baterías;
  - `crucible_charge`, para el retorno de dross.
- **Los gates de cada emisor no se tocan.** Siguen igual `internal_maquila_enabled`, el tipo de salida, la sede que factura y la tarifa vigente. El setting cambia la *forma* de la emisión, nunca *si* se emite.
- Hay dos regímenes de gate (F4a de #107), y los dos se prueban **[C4]**:
  - traslado, diferencial del crisol y dross dependen del flag;
  - el reparto de `abono_material` y `abono_bateria` depende del tipo e ignora el flag.
- Números y locks no cambian. QA lo verificó: `_create_movement` ya numera, y los cuatro flujos ya declaran `movement_number` (transfer:327/651, willard:282, crucible:169).

**D3. Validación fail-closed, antes de cualquier commit [C5].** Con el setting puesto, el tercero tiene que cumplir todo esto:
- el valor es un UUID **bien formado**: el payload es `str` strict y acepta cualquier texto, así que un valor malformado tiene que dar 422, no 500;
- existe en la organización, está activo y no es entidad de sistema;
- tiene categoría `liability` o `service_provider`. #83 usa `service_provider`, y PLANTA JUAN MINA se cargó como Pasivo.

Si falla cualquiera, el flujo responde **422** nombrando el setting y el valor, y no escribe nada. **Nunca se vuelve en silencio al par**: eso perdería la deuda sin aviso, el modo de falla de #98 D10 y de #100 D4d.
- La validación corre dentro del helper. Los cuatro flujos hacen **un solo commit al final** y `sale_service` no commitea (QA lo verificó), así que un 422 a mitad del flujo no deja nada escrito.
- **Regla escrita para el futuro:** quien mueva un commit antes de la emisión rompe T9.

**D4. Las anulaciones revierten con `money_movement._reverse_effects` sobre TODOS los movimientos del documento, leyendo `movement.third_party_id` y NUNCA el setting [C3].** Así se anula bien un documento viejo aunque el setting haya cambiado o se haya quitado después (fase 2).
- **Traslados:** hoy llaman `_reverse_effects`, pero filtran por `INTERNAL_MAQUILA_MOVEMENT_TYPES`. El filtro se ensancha a todos los movimientos con su `source_type`/`source_id` en status confirmed.
- **Salidas:** hoy revierten a mano solo `service_income_accrual`, y eso se reemplaza por la llamada genérica. QA verificó que la reversa es idéntica (`money_movement.py:1877` contra `willard_delivery.py:1041-1044`). Se gana una sola copia de la terna (#67). El orden de impuestos de #112 no se mueve, porque `_abono_invoice_pos` filtra por tipo.
- **Crisol:** hoy solo marca anulado. Gana la llamada.
- Para el par interno, `_reverse_effects` es la rama `pass` explícita.

**D5. Guard de Tesorería por CAMPO, con lista cerrada [C2].** `money_movement.annul` rechaza con 422 todo movimiento cuyo `source_type` esté en `_OWNER_MODULE` (`transfer`, `willard_delivery`, `crucible_charge`), sea del tipo que sea, y nombra el módulo dueño.
- **No es "todo `source_type` no nulo".** Siguen anulables desde Tesorería:
  - un `expense_accrual` registrado a mano contra PLANTA, sin `source_type`. Johana va a registrar cosas a mano contra ese tercero;
  - el accrual de `collector_commission`, porque anularlo en Tesorería es condonar (#83).
- Verificado con `grep`: en `MoneyMovement`, esos tres `source_type` los usan solo los pares y la factura de la Salida. QA midió en dev que esos movimientos existen solo en la organización SAC.

**D6. Fechas.** Las mismas que hoy usa el par: recepción del traslado, liquidación de la Salida y fecha del documento de crisol. No hay reloj nuevo.

**D7. Las respuestas no cambian.** `maquila_amount`, `crucible_amount` y `plant_credit_amount` se llenan igual que hoy.

**D8. Efecto en reportes**, solo en SAC y solo con el setting puesto:
- **Balance:** el pasivo con planta sube por cada maquila.
- **Estado de resultados consolidado:** la maquila aparece como gasto operativo en su categoría.
- **Estado de cuenta de PLANTA:** muestra cada maquila y cada pago.
- **Resultado por sede:** $0 para estas maquilas e `internal_maquila_*` en 0, así que Circunvalar + Juan Mina ≠ consolidado por el monto de la maquila **[O5]**.
- `reports.py` **no se toca**.

**D9. Fase 2 (sedes).** Se quita el setting y lo nuevo vuelve al par. Lo ya causado no se convierte.

**D10. Sin migración, sin permisos nuevos, sin tipos de movimiento nuevos y sin frontend.**
- **[O3] Declarado y no arreglado:** `MovementDetailPage` ofrece «Anular» en el causado, porque excluye por tipo y `source_type` no viaja en la respuesta. El clic da 422 con el módulo, que es lo mismo que pasa hoy con la factura de la Salida. Arreglarlo exige agregar la clave a `MoneyMovementResponse`, que es captura del golden. No vale la pena por esto.
- **[O6] Declarado:** `current_balance` se actualiza leyendo y escribiendo en Python, sin bloqueo. Es el patrón de siempre y no es nuevo, pero planta pasa a ser un tercero con mucho movimiento. Queda anotado.

**D11. El seeder no pisa settings que no son suyos ni valores que alguien cambió [C1].** Hoy `patch_settings` (`seed_sac_org.py:876-883`) hace en cada provisión un REPLACE completo con `settings_de_la_org()`, y esa función no conoce `plant_third_party_id`. Una re-provisión borraría la clave en silencio y las maquilas volverían al par: es justo lo que D3 prohíbe, entrando por otra puerta.

Con el cambio, `patch_settings` lee primero los settings vivos y arma el diccionario a mandar así:
- **claves que no son del seeder** (las que no están en `settings_de_la_org`, como `plant_third_party_id`): se conservan tal cual;
- **claves del seeder que faltan:** se escriben. Una org recién creada las recibe todas, así que el flujo de `--org-vacia` sigue igual;
- **claves del seeder presentes con otro valor:** **no se pisan**. Se listan en el bloque **DECISIÓN PENDIENTE** y la corrida sale con **exit 3**, que es el mismo mecanismo de las tarifas (#109). Esto cierra también el pendiente de `willard_distribution_centers`, porque un cambio de Johana desde la pantalla ya no se revierte.
- El PATCH sigue mandando el diccionario completo, porque el endpoint es REPLACE.

`archivar_org_sac.py --modo revisar` (l.405-414) informa las claves ajenas **a sabiendas**, como «la puso alguien fuera del seeder; la organización nueva no la trae y hay que re-aplicarla a mano (si es un tercero, con el id NUEVO)». No las cuenta como diferencia.

## 3. Golden

Aplica **la medición, no la corrida**, y QA la reprodujo:
- `golden_capture.py` tiene 0 ocurrencias de `annul`;
- en dev, los únicos movimientos con esos `source_type` son de la organización SAC;
- los cambios en código compartido son el guard de `money_movement.annul` (D5), que no ve ninguna fila fuera de SAC, y los scripts de SAC.

## 4. Tests (`tests/test_sac_planta_proveedor.py` + `tests/test_seed_sac_settings.py`)

| T | Escenario | Afirma |
|---|---|---|
| T1 | Traslado CV→JM recibido, **sin** setting | Par interno como hoy: 2 movimientos, tercero NULL; el saldo de planta no cambia. |
| T2 | Lo mismo **con** setting | 1 `expense_accrual` con tercero planta; monto = kg × $1.500; saldo de planta −monto; sin par. |
| T3 | Traslado con discrepancia resuelta, con setting | Se causa sobre la cantidad final, una sola vez. |
| T4 | Venta de plomo puro, con setting | El diferencial del crisol se causa a planta; `crucible_amount` igual que hoy. |
| T5 | Abono de materiales y abono de baterías, con setting | Se causa a planta el reparto de $1.248 y de $566. |
| T6 | Retorno de dross, con setting (G1) | La maquila sobre `lead_kg` se causa a planta. |
| T7 | Anular cada documento de T2, T4, T5 y T6 | El saldo de planta vuelve exacto y el movimiento queda anulado. Se cumple el invariante #55 (saldo corrido == saldo vivo) en **PLANTA** y en **WILLARD** (abono con factura) **[O5]**. |
| T8 | Anular desde Tesorería el causado de traslado, de Salida y de crisol | 422 que nombra el módulo. |
| T8b **[C2]** | Desde Tesorería: un `expense_accrual` manual a PLANTA sin `source_type`, y el accrual de `collector_commission` | Los dos **siguen anulables** (200) y la reversa es exacta. |
| T9 **[C5]** | Parametrizado sobre los 5 caminos (`receive`, `resolve`, liquidar venta de puro, liquidar abono, `dross_return`) × setting inválido: UUID malformado, inexistente, de otra org, inactivo, de sistema, sin `liability` ni `service_provider` | 422 sin 500. **Nada escrito**, medido con conteos de kg, `inventory_movements`, MMs y el estado del documento, leídos en una sesión nueva o por HTTP. |
| T10 **[C4]** | Con setting y `internal_maquila_enabled` **apagado** | Traslado, diferencial del crisol y dross no emiten nada. El reparto de `abono_material` y `abono_bateria` **sí** se causa a planta. |
| T11 **[O5]** | Balance y estado de resultados con setting | Pasivos +monto y gasto operativo +monto. `internal_maquila_income/expense` en 0. Por sede, CV + JM ≠ consolidado exactamente por la maquila. |
| T12 | Sin setting, anular una Salida con factura (`service_income_accrual`) | El saldo de Willard vuelve igual que hoy (regresión de D4). |
| T13 **[C3]** | Se causa con setting = planta. Después se quita el setting o se cambia a otro tercero, y se anula el documento | Vuelve exacto el saldo del tercero **original**; el otro tercero no se toca. |
| T14 **[C1]** | `patch_settings` contra un fake que hace REPLACE **de verdad**, como el backend | Conserva `plant_third_party_id`. Escribe las claves del seeder que faltan. No pisa una clave del seeder con otro valor (por ejemplo `willard_distribution_centers` editada), la lista en DECISIÓN PENDIENTE y sale con exit 3. Una org vacía recibe todas las claves. |
| T15 **[C1]** | `archivar_org_sac.py --modo revisar` con una clave ajena | La informa como clave ajena a re-aplicar, no como diferencia. |

**Plantado.** La matriz se commitea ANTES de plantar. Cuando el defecto vive en una vía compartida, la predicción se escribe como "≥ estos".

| P | Defecto plantado | Tiene que tumbar |
|---|---|---|
| P1 | El helper ignora el setting. | T2–T6 |
| P2 | Con un tercero inválido, el helper cae al par. | T9 |
| P3 | La anulación del crisol no revierte. | T7 (crisol) |
| P4 | Se quita el guard de D5. | T8 |
| P5 | Vuelve el filtro viejo por tipo en el annul del traslado. | T7 (traslado) |
| P6 | El retorno de dross no pasa por el helper. | T6 |
| P7 | Signo invertido en el causado. | T2 y T7 |
| P8 **[C6]** | Con `None` no se emite nada. | La mitad "sin setting", que vive en otros archivos y es la red de las 6 orgs: `test_par_emite_en_abono_material`, `test_venta_puro_sin_flag_sin_par`, `test_dross_return_sin_flag_mueve_kg_sin_par`, los tests del par en `test_sac_transfer_two_step.py`, y T1. |
| P9 **[C6]** | Volver a la reversa manual solo de `service_income_accrual` en Salidas. | T7 (Salida) |
| P10 **[C2]** | Guard "todo `source_type` no nulo". | T8b (el `collector_commission`) |
| P11 **[C3]** | La anulación revierte contra el tercero del setting en vez de `movement.third_party_id`. | T13 |
| P12 **[C1]** | `patch_settings` vuelve a mandar solo `settings_de_la_org()`. | T14 |

## 5. Runbook de producción

1. Confirmar G1 con Johana. Si no responde, aplica lo escrito en G1.
2. Pedirle a Johana que no registre traslados a planta, Salidas ni crisol hasta el deploy (G7).
3. Deploy normal. No hay migraciones.
4. Leer, solo lectura, los settings de la SAC 87e5d751 y el id de PLANTA JUAN MINA.
5. Con el OK de Daniel, PATCH a `/system/organizations/{id}` con el **diccionario completo** más `plant_third_party_id`. La semántica es REPLACE (#74).
6. Releer: los settings tienen que quedar idénticos más la clave nueva.
7. **Si alguna vez se recrea la organización** (por ejemplo, una carga final con `--org-vacia`), la org nueva nace sin el setting y PLANTA JUAN MINA tiene otro id. Hay que re-aplicar el setting después de cargar los saldos, con el id NUEVO **[C1]**. `--modo revisar` lo avisa (T15).
8. Avisarle a Johana dos cosas: que la recepción del traslado en planta es la que causa la maquila (G3), y que los gastos propios de planta no se registran en esta organización (G6).

## 6. Fuera de alcance

- Ver el balance "solo de Circunvalar".
- Convertir lo ya causado al volver a sedes.
- Bogotá: ya es un proveedor, y lo que llega se registra como compra sin cambios (Q-35, Q-63).
- Q-37: que la maquila de materiales vaya a la cuenta por pagar Materiales Willard en vez de a ingresos. Es otro ciclo.
- O3: el botón «Anular» en `MovementDetailPage`.
