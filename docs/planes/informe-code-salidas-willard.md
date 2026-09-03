# Informe de construcción — Salidas de plomo a Willard (W1)

**Fecha:** 2026-08-24 · **Plan:** `plan-sac-salidas-willard.md` (GO condicionado de QA, 4 items cerrados)
**Migraciones:** 2 · **Rama:** develop, sin commitear

---

## 1. Lo que se construyó

| Pieza | Dónde |
|---|---|
| `WillardDelivery` + `WillardDeliveryLine` | `models/willard_delivery.py` |
| Servicio: crear → revisar → liquidar → anular | `services/willard_delivery.py` |
| 7 endpoints, router gated por `kg_ledger_enabled` | `api/v1/endpoints/willard_deliveries.py` |
| Tipo `service_income_accrual` (catálogo 47 → 48) | 4 sitios backend |
| Bloque P&L que fragmenta por sede | `services/reports.py` |
| Tarifa `abono_planta_por_kg` + setting `willard_sede_facturacion` | 4 + 2 sitios |
| Permiso `sales.review` (sort 149) | migración + catálogo |
| Frontend: tipos, servicio, 6 hooks, 3 páginas, 6 mapas de etiquetas | `pages/willard/` |
| 26 tests | `tests/test_willard_deliveries.py` |

**Migraciones:** `f9a0b1c2d3e4` (tablas + 2 columnas nullable en tablas compartidas) y
`a5b6c7d8e9f0` (el permiso). Los IDs se grepearon antes de elegirlos — los dos primeros
candidatos estaban tomados (lección de #98).

---

## 2. Los cuatro condicionantes de QA

**MAYOR 1 — resuelto como QA recomendó: fragmenta por sede.** Los números del cliente lo deciden
y quedaron como test (`test_factura_fragmenta_por_sede`): Circunvalar +60, Juan Mina +40,
consolidado +100. Plegado org-level, Circunvalar —la sede que gana— saldría en −40.

**MAYOR 2 — devolución aceptada tras verificarla: la conciliación NO cambia.** QA infirió que
sacar un tipo de `_not_by_sede` obliga a línea propia. `_not_by_sede` es `[false()]` que se agrega
a los filtros **de cada bloque de query** ([reports.py:523](../../backend/app/services/reports.py#L523)),
no a la línea de salida: un segundo bloque sumando al mismo acumulador `service_income` fragmenta
sin tocar schema, frontend ni los dos tests de oro. El precedente de `asset_sale_gain` no se paga.

**MENOR — inventarios completos**, en §2b y D6 del plan. La tarifa toca 4 sitios (el plan decía 1);
el tipo de movimiento toca 6 archivos de frontend (el canon dice "5 mapas", medidos son 6).

**Alcance — declarado** en §2c: W1 factura pero no cobra; el recaudo sigue en W3.

---

## 3. Lo que apareció al construir y no estaba en el plan

**D12 — el abono necesita un vehículo para llevar su costo al P&L.** No es una venta, pero el
inventario que sale sí está valorizado. Sin vehículo el activo baja y nada lo compensa. Se usa un
`decrease` (entra a `adjustment_net`, conserva valor por #66, ya probado) — el mismo camino que #84
usó para la merma. Cuesta una tercera columna `willard_delivery_id` en `inventory_adjustments`,
mismo precedente que `transfer_id` e `inbound_order_id`. Aspereza declarada en el plan: el cliente
verá esas salidas bajo "Ajustes de Inventario".

**Q-A la respondió Hugo en vivo, y destapó algo que ya estaba mal.** Es UN solo cobro y ocurre en
la entrega: *"cuando yo despacho el plomo de la planta se le factura — una parte de los 1500 se le
abonan a planta"*. O sea que la maquila del traslado (#84, `maquila_intersede_cv_jm` = $1.500)
cobra en el momento equivocado: es el mismo hecho económico contado antes de tiempo.

**No cuesta código**: `internal_maquila_enabled` se lee en exactamente dos sitios, los dos en
`transfer.py` — SAC lo apaga y el traslado deja de cobrar. Pero eso solo funciona si el par de la
entrega gatea por su cuenta (**D11**), y por eso el fixture de los tests **deja ese flag en False**:
que todos los tests de efectos pasen así *es* la prueba de D11.

**El `sale` service ya era componible.** `create` y `liquidate` solo hacen `flush()` — el endpoint
commitea. No hizo falta el `commit: bool` que #93 tuvo que agregarle a `purchase`.

---

## 4. Verificación de los tests contra defectos plantados

Los 26 pasaron a la primera, así que se rompió el código a propósito:

| Defecto plantado | Qué falló |
|---|---|
| Gatear el par de la entrega con `internal_maquila_enabled` | 🔴 `test_par_entrega_emite_con_flag_maquila_apagado` — el modo de falla de #94/#99 |
| Quitar `intersede` del abono de batería | `test_abono_bateria_descarga_ambos_mismo_kg` |
| Plegar la factura en `_not_by_sede` (la opción que QA descartó) | `test_factura_fragmenta_por_sede` |
| Volver a hardcodear el mensaje del guard | `test_guard_maquila_nombra_el_modulo_correcto` |
| Drill-down con un solo tipo en vez de la CSV | `test_drilldown_service_income_cuadra_con_pnl` |

### 🔴 Un hueco que el quinto defecto destapó

`test_service_income_parity` (el guardrail de #49) **no ejercita nada de W1**: su escenario no tiene
un `service_income_accrual`, así que el cambio a CSV pasaba verde sin ser probado. El guardrail hay
que ponerlo donde sí hay datos, y por eso existe `test_drilldown_service_income_cuadra_con_pnl` —
verificado: sin la CSV da *listado=0 contra P&L=85.000*.

Es la misma familia que la muestra anti-correlacionada del golden en #96 E: **un gate que no
ejercita el caso se ve idéntico a uno que pasó.**

### 🔴 Un bug que ningún test podía atrapar

Al hacer el smoke contra la BD real, `POST /willard-deliveries` devolvió **500**:

```
NotNullViolation: null value in column "created_at" of relation "willard_deliveries"
```

`TimestampMixin` declara `created_at` con `server_default=func.now()`, pero mi migración escribió
la columna **sin** ese default. Los 26 tests pasaron igual porque **la BD de test se recrea desde
los modelos** (`create_all` en conftest) mientras dev y producción se construyen **desde las
migraciones**. Las dos fuentes divergieron y solo la segunda se rompe.

**Escribí primero que "es exactamente lo que el parity check existe para cazar". Es falso**, y lo
descubrí al correrlo: `schema_parity_check.py` **excluye `server_default` a propósito**
([docstring L14-24](../../backend/scripts/schema_parity_check.py#L14)) porque es una divergencia
pre-existente en todo el repo. Su propio docstring lo advierte: *"por la exclusión anterior, este
gate NO atrapa un default de BD faltante"*.

O sea que el bug vivía en un **punto ciego declarado**, y hay que ser exacto sobre cuál:

| Dirección | Quién lo caza |
|---|---|
| Migración tiene el default, modelo no | la suite (corre contra `create_all`) |
| **Modelo tiene el default, migración no** | **nadie** — solo abrir el camino real |

El mío era el segundo. Corregido en las dos tablas y verificado (`column_default = now()`).

**Propuesta, fuera del alcance de este ciclo:** la exclusión está justificada para tablas viejas —
ahí hay legado que acomodar. Para una tabla **nueva** no hay legado, así que el parity check podría
comparar `server_default` solo en tablas fuera del baseline. Convierte este punto ciego en un
error, y no toca nada de lo que hoy pasa.

Lección práctica: **el smoke contra la base migrada no es opcional**, y no lo reemplaza ninguna
cantidad de tests verdes ni un parity en verde.

### Un test que pasaba por la razón equivocada

`test_annul_abono_devuelve_inventario` mandaba `"x"` como motivo de anulación. El endpoint exige 3
caracteres, así que devolvía **422 y nunca anulaba** — y el test solo lo delató porque le agregué la
aserción de status que le faltaba. Un test que no verifica la respuesta puede pasar por la razón
equivocada. Regla para los que vengan: **assert al status, siempre.**

### 4b. Lo que el parity check sí cazó

Cuatro divergencias más, todas mías y de la misma familia:

- `updated_at` quedó `nullable=True` en la migración y el modelo lo declara `NOT NULL` (×2 tablas)
- faltaban los índices sobre `organization_id` que `OrganizationMixin` declara con `index=True` (×2)

Ninguna rompía nada visible hoy; las cuatro eran deuda silenciosa entre las dos fuentes del schema.
Segunda corrida: **DIFF CERO fuera del baseline** (64 tablas, 284 índices, 334 constraints).

⚠️ Al reaplicar hubo que limpiar a mano: editar una migración ya aplicada deja el `downgrade`
intentando borrar índices que la versión vieja nunca creó. Tablas nuevas sin datos, así que fue
`DROP TABLE` + reset del `alembic_version`. **Cuidado si esto se repite con datos de por medio.**

### 4c. Dos hallazgos del smoke que no eran de código

**Willard estaba sembrado solo como proveedor.** El tipo `venta` deriva una `Sale`, que exige un
tercero cliente (#32/#33) — y el 422 salía desde adentro con *"El tercero no es cliente"*: cierto,
pero sin decir dónde arreglarlo. Willard es las dos cosas: entrega baterías y **compra** plomo.
Corregido en el seeder (dos categorías) y agregada una validación fail-fast en el servicio que
nombra al tercero y manda a Terceros. Test propio.

**El seeder no soportaba más de una categoría por tercero.** `THIRD_PARTIES` era
`(nombre, categoria)` singular. Ahora es una lista.


---

## 5. Gates

| Gate | Estado |
|---|---|
| Tests del ítem | ✅ **29** (27 + 2 de la ronda 2) |
| Suite completa | ✅ **1674 passed** (1645 + 29), 44:19 — 3a corrida, tras el arreglo de la ronda 2. La 2a (1672, 37:34) corrió ENTERA dentro de la franja 19:00–24:00, o sea muestra completa para los tests de reloj (#96 D); esta corrió de día, así que la cobertura de esa clase la da la anterior |
| `ruff check app tests scripts` | ✅ |
| `tsc --noEmit` | ✅ |
| `npm run lint` | ✅ 0 errores, **37 warnings = el presupuesto exacto** (cero nuevos) |
| `npm run build` | ✅ |
| **Smoke contra la BD migrada** | ✅ — y encontró el `created_at` de §4 |
| Parity check | ✅ **DIFF CERO** — pero antes cazó 4 divergencias mías (ver §4b). La ronda 2 no toca el esquema |
| **Golden ×3 orgs** | 🟢 **0 diffs reales**, 48 capturas por lado — **re-corrido tras la ronda 2** (`reports.py` es camino compartido) |

La 2ª corrida arrancó 21:58 y terminó 22:35, o sea **entera dentro de la franja 19:00–24:00**
donde la fecha UTC y la colombiana son días distintos. Es la ventana en la que aparecen los bugs de
reloj (#96 D): correrla ahí es muestra buena, no mala. La 3ª (la de la ronda 2) corrió de día, así
que para esa clase la cobertura buena es la de la 2ª — y el arreglo de la ronda 2 no toca ninguna
fecha.

🔴 **Un error de método en el golden de la ronda 2, que vale registrar.** Reusé el `before` de ayer
razonando que el commit no había cambiado y que el smoke solo había tocado SAC. Dio **30 diffs**: 6
eran `as_of_date` de ayer a hoy —puro artefacto de la captura vieja— y el resto un corrimiento de
índices en `inventory_liquidated` que **no se podía atribuir**. No fue un falso verde (la dirección
segura del error), pero dejó al gate sin poder afirmar nada, que es casi lo mismo que no correrlo.
Rehecho desde el worktree de `0018c02`, hoy, contra la misma BD y verificando que ese lado **no**
tuviera el bloque nuevo: **0 diffs**. O sea que el ruido era deriva de datos de la BD de dev, no
código. Regla: **las dos patas del golden se capturan en la misma sesión**; un `before` viejo mezcla
deriva de datos con efecto de código y no hay forma de separarlos después.

---

## 6. Dónde mirar más duro

1. **El fixture con `internal_maquila_enabled: False`.** Es lo que sostiene D11. Si alguien lo
   "arregla" poniéndolo en True porque "el módulo usa maquila", el test deja de probar lo único que
   prueba y el guard queda sin red.
2. **D12 y la respuesta de Hugo a Q-B.** Si la deuda con Willard resulta ser un pasivo, el `decrease`
   sale y entra otro modelo. Vale no cimentar nada encima hasta esa respuesta.
3. **`_resolve_kg_account` para `willard_baterias`.** Descarga la cuenta de la sede que FACTURA
   (Circunvalar), porque la deuda de postconsumo es de ella aunque el plomo salga de planta. Existe
   también una cuenta de Juan Mina (`WILL-BAT-JM` en el seeder) que este módulo nunca toca — si
   resulta que hay baterías que entran directo a planta, esa rama falta.
4. **El P&L por sede de un abono.** El costo va por `adjustment_net`, que hoy es de los bloques que
   salen $0 por sede (`_not_by_sede`). O sea que en el P&L de Juan Mina el abono muestra el ingreso
   del reparto sin el costo del plomo. Consolidado cierra; por sede queda incompleto hasta que
   exista captura de gasto-por-sede (la deuda E4 que #84 ya declaró).

---

## 7. Ronda 2 de QA — cerrada

**GO condicionado a una sola cosa: fragmentar el costo del abono por sede, en este ciclo. Hecho.**

### Lo que yo tenía mal

Mi §7 de la ronda 1 proponía dejarlo, con este razonamiento: *si Hugo responde que la deuda con
Willard es un pasivo (Q-B), el `decrease` desaparece y la pregunta se disuelve sola*.

QA me lo devolvió con el argumento que faltaba: **eso corta para los dos lados**. Si Hugo dice que
**no** es pasivo —que es el default que yo mismo proponía como deployable— la asimetría queda
permanente. Estaba apostando el reporte a la respuesta menos probable de las dos.

Y con números la magnitud no es una imprecisión, **invierte el signo**:

```
                     antes                con el costo fragmentado
Circunvalar          +100                 +100
Juan Mina             +40                  +40 − 500  =  −460
                    ─────                 ─────
suma por sede        +140                  −360
consolidado          −400                  −400
```

El hueco de $500 no se veía desde ninguna de las dos sedes. Y es el reporte que Hugo va a abrir
primero, porque el P&L por sede es la razón de ser de D5.

Lo que termina de decidirlo es una distinción que yo no había hecho: **todo lo que #84 fragmentó
eran pares completos** —la venta con su COGS, la comisión con su venta, el par de maquila—. Este
era el **primer ingreso sin su costo**. La incompletitud declarada de #84 es *"faltan cosas"*; esto
era *"hay una cosa mal"*.

Una precisión más de QA, y es correcta: **"el `decrease` desaparece" no era exacto**. Si Q-B resulta
ser pasivo, el material sale físicamente igual y el ajuste se queda; lo que se mueve es dónde
aterriza su valor.

### El arreglo

Bloque propio en `_calculate_profit`, misma técnica que D4b: filtrado a `willard_delivery_id IS NOT
NULL` + bodega, sumando al acumulador `adjustment_net`. La conciliación #59 lee ese mismo dict
([reports.py:4675](../../backend/app/services/reports.py#L4675)), así que queda cuadrada por
construcción — igual que el ingreso.

⚠️ **El gate `by_sede` de ese bloque es defensivo, no load-bearing — y yo afirmé lo contrario.**

Lo corrigió QA en la ronda 3 de la forma correcta: plantando el defecto. Sin el gate los 29 tests
pasan igual, porque en consolidado `warehouse_id` es None y SQLAlchemy renderiza `== None` como
**`IS NULL` sobre una columna NOT NULL** → cero filas. El bloque no duplica: queda **inerte**.
Verificado a mano:

```
(IA.warehouse_id == None)  ->  inventory_adjustments.warehouse_id IS NULL
IA.__table__.c.warehouse_id.nullable  ->  False
```

El gate se queda —es barato, y el día que `warehouse_id` se vuelva nullable pasa a importar— pero
etiquetado como lo que es. Lo que **sí** es cierto: este bloque suma ajustes que el consolidado ya
cuenta por su cuenta (`adj_filters` solo los apaga cuando hay sede), a diferencia del hermano de
`service_income`, que suma un `movement_type` que el otro nunca vio.

Y `test_costo_del_abono_no_se_cuenta_dos_veces` **no prueba lo que dice su nombre**. Gana su lugar
igual, por otra cosa: `cv + jm == consolidado` es el invariante real del arreglo —que el costo
aterrice en exactamente una sede y la suma reconcilie— y eso sí lo verifica. Docstring corregido.

🔴 **Es la lección de §5 mordiendo dentro del mismo ciclo que la escribió.** La tabla de defectos
plantados cubre los 5 de la tanda de 26 tests; el gate de D13 nació **después**, como respuesta a la
condición de la ronda 2, y no lo reclamé como verificado. *Un gate que no ejercita el caso se ve
idéntico a uno que pasó* — incluido cuando el gate es mío y lo acabo de escribir.

### Lo demás de la ronda 2

- **MAYOR 2**: QA verificó la cadena entera y confirmó la devolución. La distinción *query separada
  ≠ línea separada* se sostiene, y el costo del precedente de #88 no se paga.
- **Q1**: barrido independiente, sin más acoplamiento. El único candidato —`mm_map.get("service_income")`
  en el Cash Flow— resultó correcto: ahí el tipo *es* la semántica, porque el accrual nace con
  `account_id` NULL y no debe aparecer como plata que entró.
- **MENOR de #84**: corregido en el canon, y eran **dos** frases, no una. La de la tabla de módulos
  (el flag gobierna solo al emisor del traslado) y la del cuerpo de #84 (la lista de bloques que
  salen `false()` por sede, que ahora tiene dos excepciones: `service_income` y `ajustes`).

---

## 8. Lo que sigue abierto

**Q-B** (¿la deuda de plomo con Willard es un pasivo?) y **el número de las tarifas** —qué parte de
los $1.500 se le abona a planta, y el flete—, hoy sembradas con placeholder. Ninguna de las dos
bloquea el deploy: la primera cambia dónde aterriza un valor que ya está bien contado, y la segunda
es un número que se edita en Config sin tocar código.
