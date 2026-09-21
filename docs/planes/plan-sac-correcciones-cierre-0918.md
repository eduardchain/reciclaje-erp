# Plan — Correcciones del cierre con SAC (reuniones 16-sep y 18-sep): reparto de los abonos, retorno de dross al 70 %, crisol que mueve inventario

**Versión 1.1 — 2026-09-18 — QA: GO (re-verificada el mismo día; un residuo de texto en D3 corregido en este commit).** QA de SAC (sesión `reciclaje-erp-93` hoy; el nombre se reasigna al reiniciar, lo estable es el transcript `d724e9a0…`): **GO CONDICIONADO** sobre la v1.0 con F1–F6 + O1–O3, todas recogidas aquí (sección 6). Cero código escrito; árbol quieto hasta la re-verificación. Pedido de Daniel: "itera con QA también, antes de codear, el plan".

⚠️ Todo lo del 18-sep es "Johana, vía Daniel", registrado por mí desde el chat: es testimonio relevado, y Daniel tiene veto sobre cualquier fila de la tabla de abajo.

> **ERRATA 2026-09-19 — este plan NO se reescribe; es el registro de lo que se creía el 18.** Ese día apareció la transcripción de la reunión (`Reunión iniciada a las 2026_09_18 13_08 GMT-05_00 - Notas de Gemini.md`, local y en `.gitignore`) y se verificó todo contra ella. **Lo que este plan construye (D1–D6) coincide con lo que Johana dijo**, varias veces con sus palabras y corrigiendo a Daniel (566 / 1.531, 1.248 / 749, crisol 1:1, retorno crisol −20 / horno +14 / total −6). Tres frases de este plan dicen MÁS de lo que ella dijo y no deben citarse: (1) la sección 3 presenta «la asume Circunvalar» entre comillas como si fuera del cliente — `grep asume` en la transcripción da 0; es glosa nuestra sobre los kilos; (2) la sección 8 (CC-013) dice retenciones «cualquiera» e IVA sobre «venta» — «cualquiera» no está en la transcripción y «venta» lo dijo Daniel; el insumo real es la factura de ejemplo que Johana ofreció (L653); (3) la sección 8 (CC-014) y la sección 1 extienden la valoración a precio de mercado a la deuda de planta con Circunvalar y dicen «solo Green Loop como cargo de compra» — Johana solo habló de la deuda con Willard (L599-605), y sobre los cargos dijo que existen y se pasan como gasto aparte de Circunvalar (L621). «La respuesta del 4-sep queda sin efecto» es conclusión nuestra (la frase la dijo Daniel, L375), y por eso la frase del encabezado «la regla de #100 está cumplida… POR ESCRITO» dice de más: fue una videollamada, las cifras de materiales las dictó Johana dos veces (16-sep con Hugo presente, 18-sep sin él) y a Hugo nadie le ha dicho que su 1.500 / 597 del 4-sep quedó reemplazado. Y «"Materiales Willard" es un nombre interno… No hay entidad, ni pasivo» (fila 2 de la sección 0 y D2) es decisión NUESTRA de construcción: la opción B no dice que no sea una cuenta, y Johana la llama «cuenta» cinco veces con sus palabras (L323, L335, L347, L361, L373) — es una cuenta interna con saldo en sus libros; lo que B descarta es un acreedor externo (Q-37, Q-43). Error inverso: la fila 5 de la tabla de la sección 0 atribuye a «Daniel 18-sep» la frase «salen 20 del crisol, entran 14 al horno grande», que es TEXTUAL de Johana (L649). El registro corregido vive en `inventario-preguntas-cliente.md`.

> Regla del ciclo (CLAUDE.md, validación de requerimientos, punto 5): se leyó `inventario-preguntas-cliente.md`. **No queda ninguna pregunta abierta con el cliente para este ciclo**: Q-27, Q-33, Q-36 a Q-40 quedaron respondidas el 18-sep (Daniel en reunión con Johana, relevadas por chat y registradas el mismo día en el inventario, en CC-012 y en `preguntas-cierre-2026-09-17.md`). La regla de #100 ("lo que contradice una respuesta confirmada se confirma POR ESCRITO antes de codificar") está cumplida para los dos puntos que contradecían a Hugo (Q-27 y CC-009 fila 4).

---

## 0. Qué se construye, en una pantalla

| # | Pieza | Hoy | Después de este ciclo | Fuente |
|---|---|---|---|---|
| 1 | Abono a BATERÍAS — reparto a planta | No emite par (CC-009: "la maquila ya se causó al trasladar") | Par `internal_maquila_*` de **$566/kg FIJOS** (tarifa nueva) además de los $1.500 del traslado. Circunvalar se queda 2.097 − 566 = 1.531 y el flete entero | Johana 16-sep 00:24:10; confirmado 18-sep: "la de Johana", "valor fijo por kilo", flete "sí, entero en Circunvalar" |
| 2 | Abono a MATERIALES — reparto a planta | Par de $1.500/kg | Par de **$1.248/kg**. Circunvalar se queda 2.097 − 1.248 = 849 (los 749 + los 100 "de utilidad") y el flete entero. **Solo cambia el valor de la tarifa** | Johana 16-sep 00:29:35; 18-sep: la del 4-sep "queda sin efecto"; "Materiales Willard" = nombre interno de Circunvalar, nadie externo la cobra |
| 3 | Retorno de dross | Los kg digitados se toman como plomo: crisol −20 / horno +20, maquila 20 × 1.500 | Se digitan **kg de DROSS**. Crisol **−20** (dross), horno **+14** (20 × 70 %), maquila **14 × 1.500 = $21.000**. La deuda total baja 6 kg (**confirmado intencional** 18-sep) | Hugo 16-sep 00:38:25–00:39:30; Daniel 18-sep |
| 4 | Traslado a crisoles — inventario | No mueve inventario (D2 de #107); crudo → puro era transformación manual (D6) | **Convierte inventario 1:1**: crudo −200 / puro +200 al costo del crudo, en el mismo documento | Johana 18-sep: "no hay transformación, si entran 200 de crudo salen 200 de puro" |
| 5 | Retorno de dross — inventario | No mueve inventario | **puro −20 / crudo +14**, 6 kg de merma | Daniel 18-sep: "salen 20 del crisol, entran 14 al horno grande" |
| 6 | Selector del retorno de dross | Todos los materiales | Solo materiales con fórmula `drosses_to_lead` vigente (es de donde sale el 70 %) | Daniel 16-sep 00:38:25 |
| 7 | Resumen por tipo de salida | No existe | Card en Salidas de Plomo: kg, maquila, flete, abono a planta y neto Circunvalar **por tipo** en el período. Es el "que el reporte separe el ingreso por materiales" | Johana 18-sep, opción b de la pregunta 3 |

**Lo que NO cambia (respondido, sin código):** el flete de $37 se factura en los dos abonos y queda entero en Circunvalar; un solo inventario (Q-34 sin objeto); solo Green Loop como cargo de compra.

**Lo que NO entra (ciclos propios, sección 8):** IVA 19 % + retenciones en salidas de plomo (CC-013) y deudas en plomo valoradas a precio de mercado en el balance (CC-014).

---

## 1. Decisiones

### D1. El par del abono se elige por TIPO con un mapa, y cada tipo tiene su tarifa

`PLANT_CREDIT_TARIFF_BY_TYPE = {"abono_material": "abono_planta_por_kg", "abono_bateria": "abono_planta_bateria_por_kg"}` en `willard_delivery.py`. `_bill_and_split` deja de preguntar `delivery_type != "abono_material"` y pregunta por el mapa; la venta ya corta arriba. **El régimen de gate no cambia**: por TIPO, ignora `internal_maquila_enabled` (F4a de #107 sigue valiendo: dos regímenes, no se unifican).

- Código nuevo de tarifa `abono_planta_bateria_por_kg` (`per_kg_lead`): `TariffCode` + `CANONICAL_UNIT_BY_CODE` (backend) y `sac-config.ts` (frontend).
- 🔴 **Hallazgo al leer**: el frontend **nunca tuvo** `abono_planta_por_kg` en `TARIFF_CODE_LABELS` — `TariffsPage` arma su selector con `Object.keys(TARIFF_CODE_LABELS)`, así que hoy esa tarifa **no se puede versionar desde la pantalla** (solo por seeder/API). Se agregan los dos códigos. Sin esto, el cambio 1.500 → 1.248 no es autoservicio.
- ¿Por qué tarifa propia y no `2.097 − 1.531`? Johana 18-sep: "es un valor fijo por kilo". Cuando Willard cambie los 2.097, los 566 no se mueven.
- **Aviso nuevo (D4d)**: abono sin la tarifa de reparto de SU tipo → warning en la respuesta ("no se repartió a planta; configúrela en Config → Tarifas"). Hoy `plant_credit <= 0` retorna en silencio. Se lee de la RESPUESTA HTTP en el test (lección #100).
- El invariante "el abono a planta no supera la maquila facturada" (aviso) se conserva para los dos tipos.
- Docstrings de `_bill_and_split`/`_emit_split_pair`: CC-009 queda como historia; se escribe la respuesta del 18-sep con fecha y fuente. **No se borra el texto viejo** — se marca superseded (misma convención de CLAUDE.md).

### D2. Abono a materiales: es SOLO un valor de tarifa

Seeder: `abono_planta_por_kg` 1500 → **1248** (append-only: el seeder compara contra la vigente y versiona). Cero código de servicio. Los 849 de Circunvalar salen por resta, como hoy salían los 597. No hay entidad, ni pasivo, ni tipo de movimiento nuevo: "Materiales Willard" es un nombre interno (18-sep).

### D3. Retorno de dross: dos cantidades, y el documento deja de ser neto cero

- `quantity_kg` pasa a significar **kg físicos del material del documento** (que es lo que el comentario del mixin ya decía: "Kg físicos del evento"). Columna nueva `crucible_charges.lead_kg` Numeric(14,4): kg de plomo. `charge`: `lead_kg = quantity_kg`. `dross_return`: `lead_kg = quantity_kg × lead_percentage` de la fórmula `drosses_to_lead` **vigente** del material, leída con `material_conversion_formula.get_current` — **NO vía `_compute_lead_kg`** (ver F2 abajo) — y cuantizado a `CRUCIBLE_Q` (ver F1 abajo).
- Efectos del `dross_return`: crisol **−quantity_kg**, horno **+lead_kg**, maquila `lead_kg × maquila_intersede_cv_jm`. El snapshot de la fórmula viaja en el movimiento kg del horno (`conversion_formula_snapshot`, parámetro que `add_kg_movement` ya tiene).
- 🔴 **F1 — una sola escala, antes de cualquier cálculo.** `CRUCIBLE_Q = Decimal("0.001")`: `quantity_kg` y `lead_kg` se cuantizan a esa constante ANTES de tocar nada, y `waste = quantity_kg − lead_kg` se calcula sobre los cuantizados. Razón: `inventory_movements.quantity` es **Numeric(10,3)** mientras el libro kg (14,4), la transformación (15,4) y `materials.current_stock*` (15,4) guardan cuatro decimales — y este ciclo FABRICA cuartos decimales por multiplicación (33,333 × 0,70 = 23,3331): el stock del material diría 23,3331 y el movimiento 23,333, o sea `stock ≠ Σ movimientos` sin aviso. Es #95 (e) (`ALLOC_Q`) otra vez. Guarda hermana: `gt=0` valida antes de cuantizar, así que 0,0004 quedaría en 0 → **422 que explica**, no un 500.
- 🔴 **F2 — sin fórmula NO hay 1:1.** `_compute_lead_kg` de Salidas cae a 1:1 cuando falta la fórmula (es cálculo, y ahí el clasificador es `lead_product`). Aquí la fórmula ES el clasificador, así que heredar esa rama sería el defecto de #103 por la otra puerta. No se reusa esa función: se lee la fórmula vigente y su ausencia es error.
- Material sin fórmula `drosses_to_lead` vigente → **422** que lo nombra y dice dónde crearla. Ese mismo predicado es el filtro del selector (pieza 6): una sola regla, en servidor y en pantalla.
- ⚠️ **Se rompe a propósito un invariante escrito**: #107 dice "neto cero sobre intersede por construcción" para los documentos de crisol. Pasa a valer solo para `charge`. `intersede == horno + crisol` **sigue siendo por construcción** (es `SUM GROUP BY stage`). Se actualizan: docstring del servicio, Key Pattern de CLAUDE.md, hint y vista previa del frontend ("Deuda total (no cambia)" → muestra −6).
- Decisión del cliente registrada tal cual: la fracción no-plomo del dross **deja de deberse** (la merma del reproceso la asume Circunvalar). Lo señalé y Daniel confirmó "Correcto" el 18-sep.

### D4. El inventario del crisol se mueve con el MOTOR DE TRANSFORMACIONES, no con código nuevo

Johana dice "no hay transformación" desde donde ella lo ve: **no hay un segundo paso**. Por dentro, crudo −200 / puro +200 al costo del crudo ES una transformación `proportional_weight` de un destino, y el motor ya resuelve todo lo que un escritor nuevo tendría que volver a resolver: MCH `transformation_in/out`, `incorporate_into_pool` con `cost_adjustment` ya cableado a la línea de sobreventa del P&L (#65), anulación por remoción ponderada (#66), inventario as-of (#61), avisos de stock negativo (#17/#76), guards de sede y tránsito (#99), links en el historial de movimientos.

| Documento | Origen | Destino | Merma | Costo |
|---|---|---|---|---|
| `charge` 200 kg | crudo (el `material_id` del documento) −200 | puro +200 | 0 | puro entra a `avg` del crudo; `value_difference = 0` |
| `dross_return` 20 kg | puro −20 | crudo +14 | 6 | crudo entra a `avg` del puro; `waste_value = 6 × avg puro` → línea de merma del P&L (org-level, $0 por sede — declarado) |

- `material_transformation.create()` y `annul()` ganan `commit: bool = True` (patrón #20/#75/#84: aditivo, ningún caller previo lo pasa → byte-idéntico). El documento de crisol llama con `commit=False` y hace UN commit.
- Enlace en la tabla **exclusiva SAC**: `crucible_charges.transformation_id` (FK nullable). **No se toca el esquema de `material_transformations`** (tabla compartida).
- **Guard de anulación directa**: `annul(..., from_module=False)` busca `crucible_charges WHERE transformation_id = :id AND status = 'confirmed'` → **400** "anule desde Salidas de Plomo → Crisol" (calco de D7b de #82 y del `from_module` de ajustes en #84). Para las 6 orgs sin SAC es un SELECT sobre una tabla con cero filas que no devuelve nada; `transformation_id` lleva **índice declarado en modelo y migración** (una FK en PG no lo crea — F6). **Va SIN flag (respuesta 2 de QA)**: el predicado "existe un documento confirmado que la enlaza" se auto-configura sin falsos positivos, y detrás de `kg_ledger_enabled` sería PEOR — apagar el flag liberaría la anulación directa y desincronizaría etapa e inventario. 🔴 **Segundo argumento (lección #98 D10), porque esto toca un camino compartido**: ¿qué empieza a pasar en una org sin la función? Una consulta más al anular una transformación, cero cambio de comportamiento, cero campos nuevos en ninguna respuesta.
- ¿Qué material es "el puro" y "el crudo"? Se resuelve por `lead_product` (#103): el único activo marcado. Cero candidatos → 422 que dice dónde marcarlo. Más de uno → el payload acepta `puro_material_id` / `crudo_material_id` opcionales y sin ellos 422 que los lista (SAC tiene uno de cada uno; la pantalla solo muestra el selector si hay más de uno).
- **Lo que el reuso trae consigo, declarado (respuesta 1 de QA):** (i) un usuario con `sales.create` crea transformaciones sin tener `transformations.create` — aceptado, mismo criterio que O2 de #107; (ii) el documento aparece en Inventario → Transformaciones con su botón Anular vivo (la respuesta de transformaciones no lleva el enlace): por eso el 400 **nombra el documento** — "anule desde Salidas de Plomo → Crisol, documento Crisol #n" (patrón D17 de #93) y T13 aserta el número; (iii) `annul` del motor no devuelve warnings → el servicio de crisol calcula el suyo ANTES de anular ("el plomo puro de este traslado ya salió: el stock queda en −X") y `annul` del documento pasa a devolver `(charge, warnings)`, entregados en la respuesta HTTP (T19); (iv) un documento con fecha pasada escribe MCH con `transaction_date` pasada y re-presenta cortes (#61) — es lo que ya hace una transformación manual, y kg, pesos e inventario quedan en UN reloj (la fecha del documento). Se acepta y queda escrito.
- **Consecuencias de costo declaradas (respuesta 5):** la merma del retorno (6 × avg puro) cae en la línea de transformaciones del P&L, org-level = **$0 por sede**, aunque el cliente dijo "la asume Circunvalar" (coherente con M1 de #84); y el avg del crudo se mueve hacia el del puro con cada retorno (hoy casi iguales: el puro entra al costo del crudo y los $300 no son costo de inventario).
- **Orden dentro de `dross_return` (O1):** número del documento (14) → movimientos kg → par de maquila (30) → transformación (41). El orden natural YA es ascendente, así que `lock_sequences` ahí es **defensiva, no load-bearing** — se deja porque es barata y fija el orden si alguien reordena; el informe lo dirá así y no al revés (lección del gate `by_sede` de #100 D13).
- Locks (#106 D4): `charge` declara `(crucible 14, transformation 41)`; `dross_return` declara `(crucible 14, movement 30, transformation 41)`. Orden ascendente en los dos.
- Anular el documento: kg + par + transformación (`from_module=True, commit=False`), un commit. Documentos anteriores al ciclo (`transformation_id` NULL; solo existen en dev) anulan como hoy.
- Respuesta del documento (armada **campo por campo** en el endpoint — trampa #95): `lead_kg`, `transformation_id`, `transformation_number`, y `inventory_out` / `inventory_in` `{code, quantity}`; más los `warnings` del motor.

### D5. Puerta de la transformación manual (ENTRA — promovida por QA: D4 sin D5 abre el agujero que D4 crea)

Con D4, una transformación MANUAL crudo↔puro movería inventario sin mover la etapa. Guard en `material_transformation.create`, **detrás de `kg_ledger_enabled` con cortocircuito primero** (sin flag: inerte, las 6 orgs byte a byte): origen con `lead_product ∈ {crudo, puro}` **y** algún destino con `lead_product ∈ {crudo, puro}` → 400 que manda a Salidas de Plomo → Crisol; el llamado del documento lo salta con `from_crucible=True` keyword-only (calco de `from_willard_delivery` de #104). La fundición del horno grande (aportantes → crudo) **no** cae: su origen es `none`. Red: el PAR con-flag / sin-flag (#99). El guard vive **solo en `create`** (anular no valida, #99).

⚠️ **Hueco que D5 no cubre y no puede cubrir por predicado**: una manual DROSS-CRI → crudo (origen `none`); bloquear por fórmula `drosses_to_lead` tumbaría la fundición legítima de MR01/scrap en el horno grande. Se resuelve en **runbook + docs**: el runbook de #107 ("la conversión física crudo → puro es manual", y "dross → crudo" de D6) queda **SUPERSEDED** — si se sigue haciendo, el inventario se duplica (+200 puro dos veces, +14 crudo dos veces). Señal natural que ayuda: bajo el modelo nuevo DROSS-CRI nunca tiene stock, así que esa manual avisa "stock insuficiente".

### D6. Resumen por tipo (pieza 7, ENTRA condicionado a F4)

`GET /willard-deliveries/summary?date_from&date_to` (router flag-gated, permiso `sales.view`): por `delivery_type`, solo `liquidated` y por fecha de liquidación: documentos, kg de plomo, maquila, flete, abono a planta y diferencial crisol. 🔴 **F4 — sin columna "neto"**: `maquila + flete − abono a planta` sería engañoso en `abono_bateria` y `venta`, porque Circunvalar ya le pagó a planta $1.500/kg al trasladar y esa suma no lo ve (mostraría 1.568/kg donde el económico es 68/kg). La columna se llama lo que es — **"Queda en Circunvalar de lo facturado"** — con la nota fija "no incluye la maquila del traslado". Entra: es pedido del cliente ("que el reporte separe el ingreso por materiales"). Card en `WillardDeliveriesPage` con el rango de fechas de la página. Suma columnas que ya se persisten; no toca reportes compartidos.

### D7. Migración (una, tabla exclusiva SAC)

`crucible_charges`: `lead_kg Numeric(14,4)` por el patrón `series` de #105 — nullable → `UPDATE lead_kg = quantity_kg` → **NOT NULL** — + CHECK `lead_kg > 0 AND lead_kg <= quantity_kg` **en migración Y modelo** (parity compara CHECKs verbatim); un `None × tarifa` en `_emit_dross_pair` sería un 500 esperando. `transformation_id GUID NULL` FK a `material_transformations(id)` sin nombre (paridad con `create_all`) **+ índice declarado en los dos lados**. Backfill exacto: en los documentos previos las dos cantidades coinciden (**dev: 0 filas, contado el 18-sep con `select count(*) from crucible_charges`** — la réplica del 17-sep se llevó las del gate 6 de #107; prod SAC: 0). Como el backfill correría vacío en los dos ambientes, el smoke de la migración **inserta una fila de prueba ANTES de migrar** (downgrade → insert → upgrade) para que la rama UPDATE + NOT NULL + CHECK se ejecute de verdad: una rama que no corrió se ve idéntica a una que pasó (#105 d). `down_revision = e2f3a4b5c6d7` (verificar con `alembic heads` antes; grepear el ID nuevo — lección #98).

---

## 2. Archivos

| Archivo | Cambio |
|---|---|
| `app/schemas/service_tariff.py` | +1 código, +1 unidad canónica |
| `app/services/willard_delivery.py` | D1: mapa por tipo, aviso de tarifa faltante, docstrings |
| `app/schemas/crucible_charge.py` | `quantity_kg` = kg físicos; `puro_material_id`/`crudo_material_id` opcionales; response +5 campos |
| `app/models/plant_process.py` | +2 columnas en `CrucibleCharge` |
| `app/services/crucible_charge.py` | D3 + D4: factor, dos cantidades, transformación enlazada, anulación, locks |
| `app/api/v1/endpoints/` (crisol y willard) | response campo por campo; endpoint `summary` |
| `app/services/material_transformation.py` | `commit`, `from_module`, guard de anulación, D5 |
| `alembic/versions/<nuevo>.py` | D7 |
| `scripts/seed_sac_org.py` | tarifas 1248 y 566; fórmula `drosses_to_lead` 0.70 en DROSS-CRI |
| Frontend | `sac-config.ts` (+2 códigos), `types/crucible-charge.ts`, `services/` de crisol (**coerción `num()` en la frontera**, regla de #107), `CrucibleChargeCreatePage` (label "Kg de dross", filtro por fórmula, vista previa: etapas −20/+14, total −6, maquila sobre 14, inventario), `CrucibleChargeDetailPage`, `WillardDeliveriesPage` (card), `WillardDeliveryDetailPage` (sin cambio de forma: "Abono a planta" ya existe); 🔴 **F3 — `queryInvalidation.ts`**: `invalidateAfterCrucibleCharge` hoy invalida `crucible-charges`, `kg-ledger`, `money-movements`, `reports` y su comentario dice "sin inventario". Se suman `["inventory"]` (cubre por prefijo stock, movimientos, valuación Y transformaciones — verificado por grep: la llave de transformaciones es `["inventory","transformations",…]`) y `["materials"]`. Sin eso StockPage muestra el puro viejo tras un traslado: no falla, MIENTE (clase #98). Va al mapa #27 de CLAUDE.md |
| Docs | CLAUDE.md #109 + Key Pattern del libro kg; guía de pruebas del cliente regenerada con `md2gdoc.py` y **recorrida por API** contra dev antes de publicarla (lección: verificar la aritmética no es verificar el sistema) |

---

## 3. Tests — matriz defecto × test (se commitea ANTES de plantar)

Tests nuevos (T) y re-semantizados (R):

| ID | Test | Qué fija |
|---|---|---|
| T1 | `test_abono_bateria_emite_par_566` | 300 kg → par $169.800, gasto en sede que factura / ingreso en planta, `plant_credit_amount` persistido, flag OFF (gate por tipo) |
| T2 | `test_abono_bateria_no_toca_factura_ni_flete` | Willard debe 629.100 + 11.100; `cv + jm == consolidado` |
| T3 | `test_abono_material_usa_su_tarifa_no_la_de_bateria` | con las dos tarifas sembradas a valores distintos, cada tipo lee la suya (1.248 vs 566) |
| T4 | `test_abono_sin_tarifa_de_reparto_avisa_en_la_respuesta` | warning leído del HTTP, kg descargados igual |
| T5 | `test_venta_sigue_sin_par` | contraste: la venta no reparte |
| R1 | `test_par_no_emite_en_venta_ni_abono_bateria` → se parte en T5 + T1 | la mitad de batería se invierte |
| R2 | `test_abono_bateria_con_puro_descarga_crisol_sin_par` | "sin par" era del diferencial de crisol; se re-lee: sigue sin diferencial, ahora CON par de 566 |
| T6 | `test_dross_return_mueve_dross_y_plomo` | 20 kg al 70 %: crisol −20, horno +14, total intersede −6, y **`lead_kg == 14` leído de la RESPUESTA HTTP**, no del ORM (trampa #95) |
| T7 | `test_dross_return_maquila_sobre_plomo` | $21.000, no $30.000 |
| T8 | `test_dross_return_sin_formula_422` | nombra el material |
| T9 | `test_dross_return_snapshot_de_formula` | cambiar la fórmula después no cambia el documento |
| T10 | `test_charge_convierte_inventario_1_a_1` | crudo −200 / puro +200, puro entra al avg del crudo, valor conservado, `value_difference == 0`, transformación enlazada |
| T11 | `test_dross_return_mueve_inventario_con_merma` | puro −20 / crudo +14, `waste_value == 6 × avg puro` |
| T12 | `test_anular_documento_revierte_inventario` | round-trip: stock y valor vuelven; transformación `annulled` |
| T13 | `test_transformacion_de_crisol_no_se_anula_directo` | 400 que **nombra "Crisol #n"**; y una transformación normal SÍ se anula (contraste) |
| T14 | `test_charge_sin_material_puro_marcado_422` / ambiguo con 2 → 422 que lista; con `puro_material_id` → 201 |
| T15 | `test_locks_en_orden` | el flujo no levanta `LockOrderError` (corre bajo el helper real) |
| T16 | PAR D5: `..._sin_flag_transforma_crudo_a_puro` (201) / `..._con_flag_bloquea` (400) / `..._horno_grande_pasa` (201) |
| T17 | `test_summary_por_tipo` | suma por tipo, excluye anuladas y draft, RBAC 403 |
| T18 | `test_cantidad_fea_cierra_en_todas_las_escalas` (F1) | retorno de 33,333 kg al 70 %: `lead_kg == 23.333`; `Σ InventoryMovement == Δ stock del material == lead_kg`; crisol −33,333 / horno +23,333 en el libro kg; y 0,0004 kg → 422 que explica |
| T19 | `test_anular_charge_con_puro_vendido_avisa_en_la_respuesta` | warning leído del HTTP, anulación no bloquea |
| R3 | `test_traslado_a_crisoles_mueve_etapas_no_deuda` | conserva etapas; su assert "no crea InventoryMovement" se INVIERTE (T10 lo cubre) |
| R4 | `test_dross_return_emite_par_con_flag` / `_sin_flag_...` | montos sobre plomo; fixture gana fórmula en el dross |

Defectos a plantar (P) — la matriz se commitea ANTES de plantar (O3). Predicción **"≥ estos"** en las filas de vía compartida: **P1, P5 y P7**.

| P | Defecto | Debe tumbar |
|---|---|---|
| P1 | el mapa devuelve la tarifa de material para batería | ≥ T3, T1 |
| P2 | par de batería detrás de `internal_maquila_enabled` | T1 |
| P3 | sin aviso de tarifa faltante | T4 |
| P4 | horno sube `quantity_kg` en vez de `lead_kg` | T6 |
| P5 | maquila sobre `quantity_kg` | ≥ T7, R4 |
| P6 | (O2, definido) el endpoint arma `lead_kg` re-derivándolo de la fórmula VIGENTE en vez de leer la columna — es el único sitio donde una re-lectura es posible | T9 |
| P7 | puro entra a su propio avg (`average_cost`) en vez del costo del crudo | ≥ T10 |
| P8 | anular no anula la transformación | T12 |
| P9 | quitar el guard de anulación directa | T13 |
| P10 | quitar el cortocircuito por flag de D5 | T16 (el de sin-flag) |
| P11 | summary incluye anuladas | T17 |
| P12 | (F2) material sin fórmula cae a 1:1 en vez de 422 | T8 |
| P13 | (F2) el endpoint no mapea `lead_kg` (campo por campo) | T6 |
| P14 | (F1) `lead_kg` sin cuantizar a la escala del inventario | T18 |
| P15 | (O1) quitar `lock_sequences` de `dross_return` | **predicción: no tumba nada** — el orden natural ya es ascendente; confirma que la declaración es defensiva |
| P15b | mover la transformación (41) ANTES del par (30) sin declaración | T15 (`LockOrderError`) |
| P16 | el aviso de anulación se calcula y no viaja en la respuesta | T19 |

---

## 4. Gates

1. Suite completa **a archivo**, `EXIT=$?` dentro del bloque tee'd, chequeo de mtime. Aviso previo: un solo dueño de 5433.
2. `schema_parity_check.py` DIFF CERO (nunca con pytest en curso).
3. Smoke de la migración contra dev (5434) a archivo: backfill de las 7 filas, FK viva.
4. ruff, tsc, build, eslint ≤ 37.
5. **Golden**: verificado contra `CAPTURES` **con comando** hoy — 11 rutas, ninguna toca willard, tarifas, crisol ni `/material-transformations`. Aun así se corre **aislado ×3 orgs** (develop-HEAD vs working tree, misma BD, manifest en los dos lados): se toca un servicio compartido (`material_transformation`) y la regla de Daniel es "golden gate siempre".
6. Plantado de defectos con respaldo **por ruta** y cierre con `git status`/`diff --stat` contra HEAD (lección del plantado de #106).
7. **Pantalla** (Daniel): abono a batería con par, retorno de dross con vista previa −20/+14, traslado a crisoles y stock de puro, anular y ver el inventario volver, card de resumen. Condición de commit, no de deploy: la clase Decimal→string de #107 solo se ve abriendo.
8. Recorrido de la guía del cliente por API con los números nuevos, a archivo.

---

## 5. Preguntas para QA

1. **D4**: ¿reusar el motor de transformaciones (el documento queda visible también en Inventario → Transformaciones, con su razón "Traslado a crisoles — Crisol #n") o un escritor propio? Mi lectura: el motor, porque un escritor nuevo de inventario valorizado es exactamente donde nacieron #64–#66.
2. **D4**: el enlace vive en `crucible_charges` para no tocar el esquema compartido. ¿El SELECT extra en `annul` de transformaciones te alcanza como "inerte", o lo querés detrás del flag con cortocircuito?
3. **D3**: ¿`quantity_kg` re-semantizado + `lead_kg` nuevo, o al revés (`quantity_kg` sigue siendo plomo y la columna nueva es `material_kg`)? Elegí lo primero porque en `charge` las dos coinciden y el comentario del mixin ya decía "kg físicos".
4. **D5 y D6**: ¿entran o se cortan?
5. **Dross y costo**: el crudo que vuelve al horno entra al avg del PURO (más caro que el crudo de horno). Es conservación de valor estricta; la alternativa (entrar al avg del crudo con `value_difference`) inventa una pérdida contable. ¿Objeción?

---

## 6. Cambios v1.0 → v1.1 (veredicto de QA: GO condicionado)

| Condición | Dónde quedó |
|---|---|
| F1 escalas (`CRUCIBLE_Q = 0.001`, cuantizar antes de calcular, 422 en vez de 500) | D3; T18; P14 |
| F2 sin fórmula no hay 1:1; `lead_kg` leído de la respuesta | D3; T8/P12; T6/P13 |
| F3 invalidación de caché | tabla de archivos (sección 2); mapa #27 |
| F4 sin "neto" en el resumen | D6 |
| F5 re-semantización por grep | sección 7 |
| F6 `lead_kg` NOT NULL + CHECK, índice declarado, consumidores de `quantity_kg` por grep | D7; sección 7 |
| Respuesta 1 (i)–(iv), respuesta 5 | D4 |
| Respuesta 2: guard de anulación SIN flag | D4 |
| Respuesta 4: D5 promovida, hueco DROSS-CRI → crudo a runbook | D5 |
| O1 declaración defensiva, O2 P6 definido, O3 "≥" | D4; matriz |

⚠️ **Infraestructura (resuelto 18-sep)**: Docker estaba apagado tras el reinicio de la máquina. Levantado: `reciclaje_dev_db` healthy, `alembic_version = e2f3a4b5c6d7`, org SAC `09fdd35c…` activa; `reciclaje-test-db` arrancada. El backend de :8001 sigue abajo y se levanta recién para los gates de pantalla y el recorrido por API.

---

## 7. Evidencia por grep (F5 y F6) — comandos y salida, 2026-09-18

**F5 — tests que tocan lo que cambia.** `grep -rln -E "abono_bateria|dross_return|crucible" backend/tests` → 3 archivos: `test_willard_deliveries.py`, `test_crucible_charges.py`, `test_advisory_locks.py`.

`awk` de los tests que usan `abono_bateria` en `test_willard_deliveries.py` (10): `:301 test_abono_bateria_descarga_ambos_mismo_kg`, `:338 test_abono_no_deriva_sale`, `:402 test_par_emite_en_abono_material` (solo docstring), `:424 test_par_no_emite_en_venta_ni_abono_bateria`, `:441 test_factura_solo_en_los_abonos`, `:666 test_peso_obligatorio_al_liquidar`, `:1475 test_series_independientes`, `:1494 test_unicidad_por_serie`, `:1539 test_label_en_descripciones_y_notas`, `:1552 test_lista_ordena_por_fecha`, `:1767 test_abono_bateria_con_puro_descarga_crisol_sin_par`.

| Test | Por qué se toca | Qué se hace |
|---|---|---|
| `:424` (parametrizado venta / abono_bateria, assert `:436 plant_credit_amount == 0`) | la mitad de batería se invierte | se parte: venta → T5; batería → T1 |
| `:1767` | "sin par" era del diferencial; ahora hay par de 566 | R2 |
| `:301`, `:338`, `:441`, `:666`, `:1475`, `:1494`, `:1539`, `:1552` | usan el fixture `tarifas` o ninguno; si alguno aserta `warnings == []` o cuenta `internal_maquila_*`, el aviso nuevo de D1 o el par lo tumban | **el fixture `tarifas` (`:150-165`) gana `abono_planta_bateria_por_kg`** → con él ninguno avisa; `:1539` (descripciones) se revisa porque ahora nace un par más con su descripción |
| `:486 plant_credit_amount == 0` (test de sede de facturación None, `abono_material`) | QA lo señaló: no cambia de sentido (sin sede no hay par en NINGÚN tipo), pero se le suma el caso batería para que la regla quede fijada en los dos |
| asserts `warnings == []`: `:895` (venta, sin fixture — intacto: la venta corta antes), `:950` (abono_material con tarifas sanas — intacto), `:1696` (venta de puro — intacto) | verificados uno por uno, ninguno es abono_bateria |
| `test_crucible_charges.py`: `:218` (assert `:238` "no crea InventoryMovement") → R3; `:284`/`:313` dross → R4 (fixture gana fórmula 0,70 y materiales puro/crudo marcados); `:335` anular → gana la transformación; `:245`, `:271`, `:378` charge → fixture necesita un material `puro` marcado o caen en el 422 de T14 |
| `test_advisory_locks.py`: `:328 test_dross_return_pide_crisol_y_despues_movimiento` (declara 2 secuencias → 3) y `TestMapa :211-223` (el generador no cambia; se verifica) |

**F6 — consumidores de `quantity_kg` del crisol que asumen plomo.** `find app -name '*.py' | xargs grep -n quantity_kg` (sin furnace/output):

| Sitio | Hoy | Cambio |
|---|---|---|
| `schemas/crucible_charge.py:10,:32` | docstring y description "kg de PLOMO que cambian de etapa" | kg físicos del material |
| `services/crucible_charge.py:88` | aviso de etapa negativa con `quantity_kg` | correcto para la etapa que BAJA (crisol baja `quantity_kg`); se deja y se comenta |
| `:123` y `:295` | descripciones "… kg plomo" — **el formateador que miente**: en un retorno serían kg de dross | "20 kg dross → 14 kg plomo" en retorno; "kg plomo" en charge |
| `:130` | los DOS movimientos usan `quantity_kg` | baja `quantity_kg`, sube `lead_kg` |
| `:286` | maquila `quantity_kg × tarifa` | `lead_kg × tarifa` |
| `endpoints/crucible_charges.py:50` | response campo por campo | + `lead_kg` y los demás campos nuevos |
| Frontend: `CrucibleChargeDetailPage:27,:67` ("Kg de plomo"), `CrucibleChargeCreatePage:103,:188`, `CrucibleChargesSection:125,:152`, `types/crucible-charge.ts:44,:70` | una sola cantidad rotulada plomo | lista y detalle muestran las dos en el retorno; label por tipo de documento |

---

## 8. Fuera de alcance — ciclos propios, en este orden

- **CC-013 — IVA 19 % y retenciones en salidas de plomo.** Definido por el cliente: IVA sobre maquila, flete y venta; retenciones "cualquiera" (catálogo configurable como #79, opcionales por salida); nacen al liquidar; el reparto a planta va sobre la base SIN IVA. Primer modelo de impuestos del sistema: la CxC a Willard = base + IVA − retenciones; IVA generado = pasivo; retención practicada = activo a favor. La venta derivada vive en `sales` (compartida) → plan, QA y golden propios.
- **CC-014 — deudas en plomo valoradas a precio de mercado en el balance**, como valor negativo que resta del inventario. Precio de mercado por kg versionado + línea en Balance General/Detallado (`reports.py`, captura del golden → gate duro). Intersede consolidada es neta cero: solo por sede.
- Deploy: este ciclo se suma al tren pendiente (#105 ×2, #106, #107 ya migradas sobre réplica de prod el 17-sep con cero duplicados en el gate de #106) + seeder en provisión contra prod. Decisión de Daniel.
