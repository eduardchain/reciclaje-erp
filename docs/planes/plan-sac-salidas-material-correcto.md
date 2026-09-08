# Plan — Salidas a Willard: el material correcto y los campos determinados

**Estado:** v1.2 — GO condicionado del QA de SAC plegado · **Fecha:** 2026-09-08
**Origen:** recorrido manual guiado sobre la SAC de desarrollo (`docs/planes/backlog-recorrido-sac.md`, 10 hallazgos)
**Alcance:** SAC exclusivamente. Ninguna tabla ni camino compartido con las 6 orgs restantes (ver §7).

> **Delta v1.0 → v1.1.** QA dio GO condicionado con 2 condiciones y 4 notas; todas plegadas.
> **C1** — §5 no discriminaba el atajo que D4 prohíbe: se suma el test de CAJ-PLA, el único que
> cae con las dos variantes del atajo. **C2** — el guard quedaba solo en la liquidación: pasa a
> validador único que corre también en captura, edición y revisión (D2). **N1/N2** — el conteo de
> mapas baja de 5 a 4 y se corrige una imprecisión de QA sobre TypeScript (D10). **N3** — el
> tercero se deriva de la cuenta que la salida descarga, no del conjunto (D7). **N4** — se declara
> el puente operativo hasta que exista el circuito (D5).
> **Orden del ciclo:** CC-009 se commitea **antes** que este código — comparten archivos y el campo
> `warnings` de la respuesta HTTP, del que depende D3, solo existe ahí.
>
> **Delta v1.1 → v1.2.** Revisión del **QA de SAC** (el que dio el GO a CC-009): GO condicionado con
> 5 condiciones, las 5 verificadas por mí contra el código antes de plegarlas. **C1** — D7 era
> *inimplementable* para la venta: `DISCHARGE_MAP["venta"] = ("intersede",)` y esa cuenta **no puede
> tener titular** (CHECK); la regla se parte por tipo. **C2** — el aviso de D3 moría en la captura:
> solo `liquidate` devuelve `warnings`. **C3** — los 38 tests existentes revientan con fail-closed y
> el plan no lo declaraba. **C4** — al cuadrante de §5 le faltaba una celda; tercera vez en este
> plan que declaro cubierto lo que no lo está. **C5** — el PUT del perfil **borraría la marca** en
> silencio desde la misma pantalla a la que D2 manda al usuario.

---

## 1. El detonante, en una línea

Daniel, durante el recorrido: *"Johana dijo que a Willard solo se le abona plomo crudo o plomo
fino, ¿cómo es posible que tengamos una salida con otros materiales si no es venta regular?"*

Reproducido en dev: 1.000 kg de GUARRÚ SECO entraron de Willard y **el mismo material salió
como abono**. SAC no fundió nada, y el sistema facturó $1.509.840 de maquila *por fundir*,
$26.640 de flete y abonó $1.080.000 a planta por un trabajo que no ocurrió. Sin un solo aviso.

**La causa es una heurística de cálculo usada como clasificador.** `_compute_lead_kg`
(`willard_delivery.py:278`) dice: *"Sin fórmula el material YA es plomo: la cantidad es el kg."*
Eso es correcto para **calcular** y falso para **clasificar**.

Medido contra la SAC de dev — materiales activos **sin fórmula**, que hoy el sistema trata
como plomo puro 1:1:

```
15 materiales pasan como plomo hoy. De esos, NO son plomo:
  ALU-01   ALUMINIO            CAJ-PLA  CAJAS PLÁSTICAS     PP-MOL   PP MOLIDO
  HIE-CHA  HIERRO CHATARRA     CAJ-ACR  CAJAS ACRÍLICAS     GUA-RRU  GUARRÚ
  LOD-01   LODO                POL-DUC  POLVODUCTO          TAP-BOR  TAPAS CON BORNE
```

Se puede saldar la deuda de plomo de Willard **con cajas plásticas, kilo por kilo**. La
aritmética queda perversa: pagar con plástico rinde 1:1 y pagar con guarru seco rinde 0,72 —
**el sistema premia usar el material equivocado**.

**Y la categoría tampoco sirve como atajo:** la categoría "Plomo" de SAC contiene CAJAS
PLÁSTICAS, CAJAS ACRÍLICAS y PP MOLIDO. Ni la fórmula ni la categoría clasifican. Hace falta
una marca explícita.

### Fuente del cliente — cita textual confirmada

Hugo Armando Bedoya, transcripción del **2026-08-28** (la demo del módulo de Salidas), línea 369:

> *"yo cojo un plomo de esos y lo refino, que le hago un proceso adicional y otro lo entrego
> directamente como crudo. El crudo lo entrego o por venta o por abono, eh por batería,
> materiales o venta, **pero el crudo es el que se entrega por eso**"*
>
> *"El puro... yo para hacer el puro necesito tomar de ese plomo crudo, llevarlo a otro proceso,
> hacer un proceso de refinación, sacarle impurezas y ahí sí entregarlo **a la venta**"*

O sea: **crudo → las tres modalidades; puro → solo venta.** Coincide con `diagrama 1.jpeg`
("Cuenta Plomo a Devolver (Abono)" como destino del crudo).

---

## 2. Por qué esto NO espera al circuito de hornos

Daniel planteó, con razón, que el módulo de Salidas no se puede terminar sin el circuito de
planta. Separando qué depende de qué:

| Falta en Salidas | ¿Necesita el circuito de hornos? |
|---|---|
| Validar que solo se entregue plomo (hallazgo 10) | **No** — necesita que el crudo **exista**, no el circuito |
| Tercero fijo a Willard (hallazgos 5, 9) | No |
| Bodega de origen fija (hallazgos 8, 9) | No |
| Editar salida registrada (hallazgo 6) | No |
| Quitar el paso "Revisada" (hallazgo 7) | No — pero espera confirmación escrita de Johana |
| Etiquetas de maquila en español (hallazgos 1, 2) | No |
| **Salida a crisoles** (4º tipo que pidió Hugo) | **Sí** |
| **Venta de puro descarga deuda + diferencial $300** | **Sí** |

Seis de ocho no lo necesitan. Este ciclo toma esos seis (uno condicionado) y deja los dos que
sí, para el ciclo del circuito de planta — que además tiene **6 preguntas abiertas con el
cliente sin responder** desde el 28-ago, más el invariante de Johana (`intersede = horno +
crisol`) que no cierra, más que Henry —el que sabe de fundición— nunca participó. Arrancar eso
hoy sería construir sobre notas de reunión sin especificación, que es exactamente lo que falló
en W1.

⚠️ **Trampa de este recorte, declarada:** al terminar, Salidas va a *parecer* completo mientras
las cuentas HORNO y CRISOL siguen en cero (hallazgo 4). Hay que decirlo explícitamente en
pantalla, no dejar que la ausencia de error lo sugiera. Ver D8.

---

## 3. Decisiones

### D1 — La marca vive en `material_kg_profiles`, columna nueva `lead_product`

Valores `none | crudo | puro`, `NOT NULL`, `server_default='none'`, String+CHECK (no `pg_enum`,
por el `schema_parity_check`, calco de `willard_world`).

**Por qué ahí:** es tabla **SAC-exclusiva**, flag-gated, ya 1:1 por material, y ya es el hogar
de la clasificación Willard (`willard_world`, `compra_regular`). Cero filas en las 3 orgs
cliente ⇒ golden no aplica (§7).

**Por qué enum y no booleano:** un booleano no puede expresar la regla de Hugo. Crudo va a las
tres modalidades; puro **solo a venta**. Esa distinción es testimonio confirmado, no inferencia,
y el circuito de planta la va a necesitar tal cual.

🔴 **El camino de escritura, o la marca se borra sola.** `MaterialKgProfileUpsert` es
`extra="forbid"` **con defaults**, y `FormulasPage:328` manda solo `{compra_regular,
willard_world}`. Si `lead_product` entra al schema **con default**, pasa esto: Johana marca CRUDO,
después edita el mundo de ese material desde Config, y **la marca vuelve a `none` en silencio** —
en la misma pantalla a la que D2 y D6 la mandan.

**`lead_product` va al Upsert SIN default** ⇒ 422 si falta. Obliga a la página y al seeder a
mandarlo siempre, y ningún caller parcial puede borrar la marca. Es el `NOT NULL` de la columna
aplicado al camino de escritura: hacer imposible lo incorrecto en vez de vigilarlo (#94/#102).
Consecuencia buscada: olvidarlo **revienta el seeder en dev**, que es donde queremos enterarnos.
El seeder suma un 9º campo a la tupla `MATERIALS` (`:175`) y al payload del PUT (`:745`).

### D2 — El guard: solo plomo entregable sale hacia Willard

**Dónde corre — y no es donde decía la v1.0.** `_compute_lead_kg` se llama desde **un solo
lugar**, la línea 218, que está dentro de `liquidate` (verificado). O sea que el guard puesto ahí
aceptaría el plástico en la captura y en la revisión, y solo reventaría al liquidar: Johana se
entera días después, con el camión ido.

El guard vive en un **validador único** `_validate_lead_products(lines)` invocado desde
`create`, `update`, `review` **y** `liquidate` — calco del patrón `_validate_willard_capture` de
#81 (que hoy corre desde 3 puntos por la misma razón). Una sola función, fail-fast en el primer
punto donde el dato existe, cero divergencia entre caminos.

⚠️ **`annul` queda fuera a propósito**, y hay que dejarlo escrito: anular no valida (#99) — una
salida vieja tiene que poder anularse siempre, incluso si su material hoy no pasaría el guard.

Cada línea exige `lead_product != 'none'`. Si no, **400** que nombra el material y dice qué hacer:

> *"'CAJ-PLA CAJAS PLÁSTICAS' no está marcado como plomo entregable a Willard. Solo el plomo
> crudo o puro salda la deuda. Márquelo en Config → Materiales (kg) si corresponde."*

Aplica a **los tres tipos**, venta incluida: la venta también descarga `intersede` por kg, así
que la misma aritmética perversa la afecta. Vender no-plomo a Willard, si algún día pasa, es
una Venta normal — no una salida de plomo.

### D3 — Puro en un abono: **avisa, no bloquea**

Hugo dice que el crudo es lo que se entrega por abono. Pero entregar puro por abono no es una
mentira del sistema (no fabrica un servicio): es una rareza de negocio — regalar producto
refinado a precio de crudo. Filosofía #17/#76: se avisa.

> *"Está abonando con PLOMO PURO. El puro normalmente se vende; el abono se hace con crudo."*

El criterio *"el sistema miente ⇒ bloquea / el negocio es raro ⇒ avisa"* es mío; los dos QA lo
endosaron. El de SAC lo reforzó con la cita: Hugo (`:377`) dice que el puro *"no debe restar la
deuda… solamente debe afectar un valor de maquila diferente"* — o sea que puro-por-abono es un caso
que **no contempla**, no uno que prohíbe. Avisar es proporcional.

🔴 **Pero el aviso hoy muere en la captura, y eso lo invalida.** Solo `liquidate` devuelve
`warnings` (`endpoints/willard_deliveries.py:225-229`); `create`, `update` y `review` **no tienen el
campo cableado**. Si el validador de D2 corre en `create` y ahí genera el aviso, se descarta — y
Johana se entera al liquidar, que es exactamente el *"días después, con el camión ido"* que D2 vino
a eliminar. D2 y D3 son hermanos: el mismo argumento de fail-fast sostiene a los dos.

**Se cablea `warnings` en los cuatro endpoints** (el campo ya existe en el response desde CC-009) y
el test del aviso lo lee de la respuesta de **`create`**, no de `liquidate`.

### D4 — La heurística de cálculo se queda; su comentario cambia

`kg = quantity` cuando no hay fórmula **es correcto** para el plomo: PLOMO CRUDO no tiene
fórmula porque *ya es plomo*. Lo que estaba mal era usar esa ausencia para decidir **qué**
puede salir. El comentario de `:278` pasa a decir que la clasificación es de `lead_product` y
que la ausencia de fórmula solo significa 1:1.

⚠️ **La trampa a no repetir:** no reutilizar "sin fórmula" ni la categoría para clasificar.
Las dos dejan pasar el plástico. Es exactamente el atajo que causó el defecto.

### D5 — Crear PLOMO CRUDO y PLOMO PURO en el seeder

Hoy **no existen**: los dos productos que Hugo describe como lo que se entrega no están en el
catálogo. Unidad kg, sin fórmula, `lead_product='crudo'` / `'puro'`, `willard_world='none'`,
`compra_regular=false`.

El seeder también marca `lead_product='crudo'` en los que ya son plomo entregable de verdad
(candidatos: `PLO-CAS`, `PLO-LIN`, `PLO-RET`). 🟠 **Pregunta al cliente (Q-31)** — ver §6.

⚠️ **El puente operativo, hasta que exista el circuito de planta.** Crear el material no crea el
stock: **nada produce PLOMO CRUDO** todavía. Mientras tanto Johana lo genera con el módulo de
**transformaciones** que ya existe (GUARRÚ SECO → PLOMO CRUDO), que además es el escalón natural
hacia el circuito. Sin decirlo, la primera salida de crudo sale con **stock negativo** — válido
por #76, pero tiene que ser una elección informada y no una sorpresa. Va en el mensaje de entrega,
no solo en el plan.

### D6 — Fail-closed, y es deliberado

Con `server_default='none'`, al desplegar **ninguna salida funciona hasta que alguien marque
los materiales**. Ese es el modo de falla correcto: bloquea con un mensaje que dice qué hacer,
en vez de seguir calculando mal en silencio. El seeder deja SAC operativa desde el minuto uno;
el mensaje de D2 cubre cualquier material nuevo que se cree después.

### D7 — Tercero fijo al titular de la cuenta kg (hallazgos 5 y 9)

Hoy `_validate_third_party` (`:840`) valida existe / es de la org / está activo, **y nada más**.
Las cuentas kg se resuelven por `account_type`, no por el tercero del documento, así que una
salida contra Green Loop **descarga la deuda de Willard y le factura a Green Loop**. Plata de
por medio, sin aviso.

Verificado en dev: las tres cuentas Willard (`willard_baterias` ×2 sedes + `willard_drosses`)
tienen el mismo titular, **Willard S.A**; `intersede` no tiene titular (lo prohíbe un CHECK).

**La regla se parte por tipo, y la v1.1 estaba mal.** `DISCHARGE_MAP` (`:61`) dice
`venta → ("intersede",)` y **solo eso**; y `intersede` **no puede tener titular** — lo prohíbe un
CHECK (`models/kg_ledger.py:110`), verificado también en la BD de dev. O sea que *"el titular de la
cuenta que la salida descarga"* es **indefinible para la venta**: la regla como estaba escrita no
se puede implementar.

| Tipo | Cuentas que descarga | Regla del tercero |
|---|---|---|
| `abono_bateria` | `willard_baterias` + `intersede` | **Titular de la cuenta Willard que descarga**; 422 si no |
| `abono_material` | `willard_drosses` | idem |
| `venta` | `intersede` (sin titular) | **Cualquier `customer`, como hoy** — sin cambio |

La venta **ya tiene semántica propia** que la v1.1 ignoraba: `_require_customer` (`:828`) exige
behavior `customer`, y `test_venta_a_no_cliente_avisa_donde_arreglarlo` la fija. Vender plomo a un
tercero que no es Willard es una venta legítima.

Se ata a la **cuenta que se descarga**, no al conjunto de "las cuentas Willard": *"todos los
titulares son iguales"* es cierto hoy y **nadie lo vigila** — atarlo al conjunto crearía una
invariante nueva que se rompe en silencio el día que alguien cree una cuenta con otro titular.

⚠️ **Y el hallazgo 5 del backlog exagera en un punto:** dice que una salida contra Green Loop
*"pondría a Green Loop como cliente de la Sale"*. Para la **venta** eso no es un defecto — es una
venta a Green Loop, y desde CC-009 la venta no factura maquila ni flete a nadie. El daño financiero
silencioso existe **solo en los abonos** (maquila y flete al tercero equivocado, `:534`).

- Backend: 422 que nombra al tercero correcto.
- Frontend: derivado y **deshabilitado**, espejo de lo que Entradas ya hace (#80 addendum).

El frontend solo no alcanza — la API queda abierta.

### D8 — Bodega de origen fija (hallazgo 8) y tarjetas HORNO/CRISOL (hallazgo 4)

La bodega **ya está defendida** en backend (`_validate_plant_origin`, `:805`, los tres tipos,
400 con instrucción). Lo que falla es pedirle al usuario que descubra por ensayo y error un
valor que el sistema ya conoce: seis opciones, cinco llevan a error. Se deriva y se
deshabilita — **solo frontend**, la defensa se queda.

Tarjetas HORNO y CRISOL: se **ocultan** hasta que el circuito de planta exista. Hoy dicen 0 y
siempre lo harán (`plant_process.py` solo lo importa `models/__init__.py`, para crear tablas).
La lectura natural de Johana sería *"todavía no hemos cargado el horno"*, no *"esto no existe"*.
🟠 Decisión de producto: ocultar vs. marcar "no disponible". Propongo ocultar.

### D9 — Editar una salida registrada (hallazgo 6)

El backend **ya lo permite** (`update`, `:114`, mientras no sea `liquidated`/`annulled`). Es un
hueco de pantalla: el detalle solo ofrece *Revisar* y *Anular*, así que quien registra sin peso
queda en un callejón sin salida. Se agrega *Editar*, espejo de la Entrada equivalente.

### D10 — Etiquetas de maquila (hallazgos 1 y 2)

`internal_maquila_expense` / `internal_maquila_income` aparecen **en inglés y con guiones bajos**
en el listado de Tesorería. Las etiquetas existen, pero **solo** en `MovementDetailPage` — así
que el detalle muestra español y el listado el código crudo.

Medido: hay **6 mapas** en el repo, los dos tipos están en **1** y hay que sumarlos a **4**:
`TreasuryPage`, `TreasuryDashboardPage`, `AccountMovementsPage`, `AccountStatementPage`.
El sexto, `ObligationDetailPage`, **queda fuera**: es un mapa de verbos de obligación
(`Record<string,string>` con `obligation_*`), y un movimiento de maquila jamás lleva
`financial_obligation_id`. De los cuatro, los que de verdad se ven son `TreasuryPage` y
`TreasuryDashboardPage`; los dos de cuenta no los mostrarán nunca (el par tiene cuenta y tercero
en NULL), pero se agregan por convención.

Más la unión `MoneyMovementType` en `types/money-movement.ts`, que **no los declara** aunque el
backend los devuelve — el tipo miente sobre el runtime, misma familia del bloqueante (b) de #93.

⚠️ **Corrección a la nota N2 de QA (verificada, no me fío de la afirmación).** QA advirtió que
ampliar la unión rompería *"los subconjuntos deliberados (typeLabels de MovementCreatePage)"* y
propuso `Partial<>`. **No hace falta**: `MovementCreatePage:19` declara su propio
`type MovementType` — una unión local de 19 tipos **creables**, independiente de
`MoneyMovementType`. Su mapa no se toca. En todo el frontend hay **un solo**
`Record<MoneyMovementType, string>`: `TreasuryPage:55`, que es justo uno de los dos load-bearing.
O sea que ampliar la unión hace que `tsc` **exija** la etiqueta exactamente donde la queremos —
es una red, no un problema, y meter `Partial<>` la apagaría.

Barrer de paso si hay otros tipos del catálogo sin etiqueta: el `?? tipo` los oculta a todos por
igual.

### D11 — Fuera de este ciclo, con razón escrita

- **Paso "Revisada" en salidas (hallazgo 7).** Johana dijo en el recorrido que las salidas van
  de registro a liquidación, sin revisión — **reportado verbalmente, sin confirmar por escrito**.
  Quitar un estado es cambio de modelo; espera la confirmación. Va con la pregunta de si el peso
  de báscula debe alimentar algo (hoy no lo consume nadie: `_compute_lead_kg` usa
  `cantidad × factor`, el peso no entra).
- **KPI "Total movimientos" suma las dos patas del par interno (hallazgo 3).** Es superficie
  **compartida** — el KPI es genérico para los 48 tipos y lo ven las 7 orgs. Cualquier cambio
  ahí necesita golden. Alternativa barata para otro ciclo: dejar el total y aclarar que incluye
  causaciones sin cuenta.
- **Salida a crisoles** y **venta de puro con diferencial $300**: circuito de planta.

---

## 4. Migración

Una sola, aditiva, sobre tabla SAC-exclusiva. Cabeza actual `d3e4f5a6b7c8`.
⚠️ Elegir el ID **grepeando primero** — `a1b2c3d4e5f6` ya está tomado y alembic responde
"Cycle is detected" (lección #101).

```sql
ALTER TABLE material_kg_profiles
  ADD COLUMN lead_product VARCHAR(16) NOT NULL DEFAULT 'none';
ALTER TABLE material_kg_profiles
  ADD CONSTRAINT ck_material_kg_profiles_lead_product
  CHECK (lead_product IN ('none','crudo','puro'));
```

Correr en dev (5434). La BD de test se recrea desde los modelos, así que alembic contra 5433 es
no-op — pero el modelo y la migración deben quedar espejados o `schema_parity_check.py` lo canta.

⚠️ **`server_default` es obligatorio en la migración, no solo en el modelo.** La BD de test nace
de los modelos y la de producción de las migraciones; esa asimetría **no la cubre ningún gate**
(el parity check excluye `server_default` a propósito) — es el bug (a) de #100, que solo apareció
en el smoke.

---

## 5. Tests

Obligatorio el **par de contraste** en el guard de D2 — sin las dos mitades, *"el guard funciona"*
y *"lo rompí para todos"* se ven idénticos (lección #94/#99):

1. `test_abono_con_material_que_no_es_plomo_bloquea` — GUARRÚ SECO por abono → 400 que **nombra
   el material**. Es la reproducción exacta del hallazgo 10.
2. `test_abono_con_plomo_crudo_pasa` — la otra mitad: el camino bueno sigue vivo.
3. `test_venta_tambien_exige_plomo` — el guard cubre los tres tipos.
4. `test_puro_en_abono_avisa_y_no_bloquea` — assert sobre **el texto del warning**, leído de la
   **respuesta HTTP**, no del retorno del servicio (lección de #100 D4d: el warning de la maquila
   se calculaba y se tiraba a la basura porque ningún test lo leyó de la respuesta).
5. `test_tercero_ajeno_rechazado` / `test_titular_de_la_cuenta_kg_pasa` — par de contraste de D7,
   con un tercero activo de la org que **no** sea Willard.
6. `test_material_sin_perfil_kg_bloquea` — fail-closed de D6.
7. 🔴 `test_material_sin_formula_que_no_es_plomo_bloquea` — **CAJ-PLA CAJAS PLÁSTICAS por abono
   → 400**. Es el test que faltaba y sin él el ciclo no cierra (ver abajo).
8. `test_guard_corre_al_capturar` — el plástico se rechaza en `create`, no recién al liquidar.
9. 🔴 `test_plomo_marcado_con_formula_pasa_y_convierte` — la **cuarta celda** del cuadrante: material
   marcado `crudo` **con** fórmula → pasa el guard **y** `kg = qty × factor`. Pinta dos cosas de una:
   que el guard lee **solo** `lead_product`, y que la heurística de cálculo de D4 sigue viva.
10. `test_aviso_de_puro_llega_al_capturar` — el aviso de D3 leído de la respuesta de `create` (C2).
11. 🔴 `test_guard_corre_al_editar` — crear con CRUDO (pasa) y `update` cambiando la línea a
    CAJ-PLA → **400 en la respuesta del `update`**, no después. Fija la etapa igual que el 8.

### Re-semantización obligatoria de los 38 tests existentes

Con fail-closed, **todos los abonos de `test_willard_deliveries.py` revientan**: usan la fixture
`plomo` (`:170`, *"PB-01 Plomo Fino"*), que **no tiene perfil kg** — 400 en `create`. Y
`test_peso_obligatorio_al_revisar` (`:626`) crea `BAT-9` sin perfil y espera llegar a `review`.

**No es un efecto colateral: es trabajo declarado del ciclo**, mecánico con un helper (patrón #95).
Lo que no puede pasar es que aparezca como sorpresa en la primera corrida.

⚠️ **Y hay una decisión escondida en la fixture.** *"Plomo Fino"* es **puro** por su nombre. Si se
marca `puro`, ~20 tests de abono empiezan a disparar el aviso de D3 y el ruido tapa lo que cada uno
prueba. **Se marca `crudo`** y se renombra la fixture; si hace falta el puro, va en fixture aparte.

### Por qué el test 7 es condición dura, y no una más

La tabla de defectos de la v1.0 predecía que *"volver a la heurística sin fórmula"* tumbaba el
test 1. **Es falso para una de las dos variantes del atajo**, y en esa variante **la suite entera
queda verde con el hallazgo 10 reimplementado**:

| Variante del atajo | test 1 (GUARRÚ, con fórmula) | test 2 (crudo, sin fórmula) | CAJ-PLA (sin fórmula) |
|---|---|---|---|
| `sin fórmula ⇒ entregable, con fórmula ⇒ 400` | 400 → **pasa** | **pasa** | **entra 1:1, sin testigo** |
| `con fórmula ⇒ convertir` (el de hoy) | **cae** | pasa | **entra 1:1, sin testigo** |

El test 7 es **el único que cae en las dos**.

### El cuadrante tiene cuatro celdas, y la v1.1 declaró cubiertas tres

La v1.1 decía *"con 1 + 2 + 7 el cuadrante queda cubierto"* y **le faltaba `con-fórmula/plomo`**.
Hoy no hay instancia real (`PLO-CAS/LIN/RET` no tienen fórmula), pero un guard *belt and suspenders*
— `lead_product != 'none' AND sin fórmula` — **pasa 1, 2 y 7** y bloquearía un PLO-RET con fórmula
de rendimiento el día que alguien la cree. El test 9 es su único testigo.

| | plomo marcado | no plomo |
|---|---|---|
| **sin fórmula** | test 2 (crudo) | 🔴 test 7 (CAJ-PLA) |
| **con fórmula** | 🔴 test 9 (crudo + fórmula) | test 1 (GUARRÚ) |

**Tercera vez en este mismo plan** que declaro cubierto un cuadrante con una celda sin testigo — la
primera la atrapó el QA de Costa, la segunda el de SAC. La lección operativa ya no es *"verificar el
cuadrante"* sino **dibujarlo**: mientras fue prosa, las dos veces se me escapó la celda; en tabla,
el hueco se ve solo.

### Especificación de los tests — la matriz obliga a fijarla

Sin esto, media matriz es ambigua:

- **1, 3, 6, 7** son de **flujo completo**: afirman el 400 sin importar en qué etapa salga.
- **8** y **11** son los que **fijan la etapa**: el rechazo ocurre en `create` y en `update`
  respectivamente, no después.
- **4** lee el aviso de la respuesta de `liquidate`; **10** de la de `create`. Ese par es lo que
  separa "el aviso existe" de "el aviso llega a tiempo".
- Materiales: **1** usa GUARRÚ (con fórmula, `none`) · **3, 7, 8** usan CAJ-PLA (sin fórmula,
  `none`) · **2** PLOMO CRUDO · **4, 10** PLOMO PURO · **9** PLOMO CRUDO **con** fórmula.

### Matriz defecto × test — 9 × 11, una marca por celda

🔴 = el test debe caer · · = debe seguir pasando. Esta tabla es el **artefacto contra el que se
compara la corrida real**, celda por celda, sin margen para *"bueno, ese también tenía sentido"*.

| Defecto plantado | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 |
|---|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|
| **a.** Eliminar `_validate_lead_products` y sus 4 llamadas | 🔴 | · | 🔴 | 🔴 | · | 🔴 | 🔴 | 🔴 | · | 🔴 | 🔴 |
| **b.** Clasificar por fórmula, var. A (`sin fórmula ⇒ entregable`) | · | · | 🔴 | 🔴 | · | 🔴 | 🔴 | 🔴 | 🔴 | 🔴 | 🔴 |
| **c.** Clasificar por fórmula, var. B (`con fórmula ⇒ convertir` = hoy) | 🔴 | · | 🔴 | 🔴 | · | 🔴 | 🔴 | 🔴 | · | 🔴 | 🔴 |
| **d.** Dejar el validador solo en `liquidate` | · | · | · | · | · | · | · | 🔴 | · | 🔴 | 🔴 |
| **e.** *Belt and suspenders* (`marcado AND sin fórmula`) | · | · | · | · | · | · | · | · | 🔴 | · | · |
| **f.** No cablear `warnings` en `create` | · | · | · | · | · | · | · | · | · | 🔴 | · |
| **g.** Quitar la validación de tercero (D7) | · | · | · | · | 🔴 | · | · | · | · | · | · |
| **h.** Comparación invertida (`== 'none'`) | 🔴 | 🔴 | 🔴 | 🔴 | · | 🔴 | 🔴 | 🔴 | 🔴 | 🔴 | 🔴 |
| **i.** Validador **sin la llamada en `update`** | · | · | · | · | · | · | · | · | · | · | 🔴 |

**Lo que la matriz mostró y la lista escondía** — tres cosas, ninguna visible en prosa:

1. **Las dos predicciones de la v1.2 estaban incompletas**, y por el mismo mecanismo de #101: se
   escribieron desde el caso que cada defecto tenía en mente, sin caminar los 10 tests.
   *"Quitar el guard → 1, 3, 7, 8"* **omitía el 6** (el fail-closed sale del mismo validador: sin
   validador no hay búsqueda de perfil ni 400) y **el 4 y el 10** (el aviso de D3 lo genera ese
   mismo validador). *"Solo 8"* para el defecto **d** **omitía el 10**, que ni existía cuando se
   escribió esa fila.
2. **Los defectos `a` y `c` tienen firma idéntica** — la suite no los distingue. No importa
   (los dos caen), pero conviene saberlo antes de plantarlos y confundirse.
3. 🟠 **El test 2 solo lo atrapa el defecto `h`.** Es el testigo de la no-regresión —que el guard
   no bloquee lo bueno— y sin `h` ningún defecto lo ejercitaba. ⚠️ Y `h` **no** es un defecto
   rebuscado, como decía una versión anterior de esta línea: `!=` por `==` es de los typos más
   frecuentes que existen, y su firma de 10-de-11 es la más ruidosa de la tabla. Es el más
   plausible de los nueve, no el menos.

### 🔴 La fila `i`: el defecto que la matriz de 8×10 no podía mostrar

Al caminar las 80 celdas, el QA de SAC encontró lo que una matriz existe para encontrar: **un
defecto con firma completamente vacía**. D2 invoca el validador desde cuatro puntos, el test 8
fijaba la etapa de `create`… y **nada fijaba la de `update`**.

Con el validador en `create`, `review` y `liquidate` pero **sin la llamada en `update`**, los diez
tests de la matriz vieja pasan: los de flujo completo reciben su 400 igual (sale en `liquidate`),
el 8 valida `create`, que sí valida, y los avisos siguen cableados. **Once puntos, cero celdas
rojas.** Alguien olvida esa llamada y entrega con la suite verde.

Y es el camino **más realista de los cuatro**: Johana registra bien, edita después, y cambia una
línea por CAJ-PLA sin querer. Sin validador ahí se entera al liquidar — literalmente el *"días
después, con el camión ido"* que C2 vino a eliminar, entrando por la puerta que C2 no miró.

🟢 **`review` NO lleva testigo propio, y es correcto** — dejarlo escrito para que nadie agregue un
test vacío: `review` **no cambia líneas** (D17: editar líneas devuelve a `draft`), así que toda
línea que ve ya pasó por `create` o `update`. Su llamada al validador es defensiva por
construcción y un defecto "sin llamada en `review`" tiene firma vacía **legítimamente**: no hay
comportamiento observable que perder. Es la diferencia con `update`, donde sí lo hay.

**Con la fila `i`, cada punto de entrada que puede meter un material tiene su testigo de etapa.**

### Coda de método — la prosa falló tres veces, y la tercera fue en la corrección

La secuencia completa, porque el patrón importa más que el resultado:

| Momento | Quién lo vio | Qué escondía la prosa |
|---|---|---|
| v1.0, cuadrante de tests | QA de Costa | una variante del atajo dejaba la suite entera verde |
| v1.1, cuadrante de tests | QA de SAC | faltaba la celda `con-fórmula/plomo` |
| v1.2, tabla de plantados | yo, al dibujarla | *"quitar el guard → 1,3,7,8"* omitía **4, 6 y 10** |
| v1.2, **la corrección** | QA de SAC, sobre sí mismo | su N1 dijo *"falta el 6"* — **faltaban 4, 6 y 10** |
| matriz 8×10 | QA de SAC, caminándola | la fila `i`, con firma vacía |

La cuarta fila es la que más enseña y la aportó el propio revisor: **su corrección tenía el mismo
defecto que corregía** — escrita desde el caso que tenía en la cabeza, sin caminar los avisos. Si
esto se resume como *"QA encontró dos huecos"*, se lee como que a la prosa le faltaba cuidado. No
era cuidado: **ninguna de las dos revisiones de la lista fue completa hasta que la lista se volvió
tabla**.

Suite completa antes de entregar. Recordar: **un solo dueño del puerto 5433** y **no editar
código del backend con la suite corriendo**.

---

## 6. Preguntas al cliente

**Q-31 (bloquea D5 parcialmente).** ¿Cuáles de los materiales de plomo que ya existen son
*entregables a Willard*? Concretamente `PLO-CAS` (PLOMO CÁSCARA), `PLO-LIN` (PLOMO LINGOTES),
`PLO-RET` (PLOMO RETAL) — ¿alguno de esos ES el crudo o el puro con otro nombre, o son cosas
distintas y hay que crear los dos productos aparte?

*No bloquea el ciclo:* si no hay respuesta a tiempo, se crean PLOMO CRUDO y PLOMO PURO y los
PLO-* quedan en `none`, que es el default seguro. Marcar uno de más es el único error caro.

**Q-32 (confirma D11).** ¿Las salidas van de *Registrada* directo a *Liquidada*, sin el paso de
*Revisada*? Y si el peso de báscula se queda, ¿debería alimentar algo o es solo constancia de lo
despachado?

---

## 7. Golden y no-regresión

**Golden NO aplica.** Verificado **contra `CAPTURES`** en `golden_capture.py`, no de memoria
(lección #98):

- La migración toca `material_kg_profiles`, tabla **SAC-exclusiva**, cero filas en las 3 orgs
  cliente, router flag-gated (403 sin `kg_ledger_enabled` incluso para admin).
- Ninguna de las rutas capturadas toca willard / kg / tarifas / perfiles de material.
- Los 5 mapas de etiquetas y la unión TS son frontend puro: no cambian ninguna respuesta HTTP.

⚠️ **El segundo argumento, el que faltó en #98 D10:** ¿qué empieza a **enviar** una pantalla
compartida al correr en una org sin la función? Repasado campo por campo — este ciclo **no
cablea ningún parámetro nuevo desde pantallas compartidas**. Las pantallas que se tocan son:
las de Salida (SAC-only, flag-gated), Config → Materiales (kg) (SAC-only), y los 5 mapas de
etiquetas, que solo **leen** y hoy caen a `?? tipo`. Nada nuevo viaja hacia el backend.

Gates que sí corren: suite completa, `schema_parity_check.py`, `ruff`, `eslint`, `tsc`, `build`.

⚠️ Y el que ningún gate cubre: **abrir la pantalla**. Los toasts de warning de D3 y el campo
deshabilitado de D7 no los ejecuta ningún test.

---

## 8. Riesgos

| Riesgo | Mitigación |
|---|---|
| Marcar de más un material (ej. GUARRÚ como crudo) reabre el defecto | La marca es explícita y por material; el seeder solo toca los PLO-* y espera Q-31 |
| Fail-closed bloquea a Johana si nace un material nuevo sin marcar | El 400 de D2 nombra el material y la pantalla donde marcarlo |
| Salidas parece terminado sin el circuito de planta | D8 oculta HORNO/CRISOL; decirlo explícitamente al entregar |
| La ventana fail-closed entre migrar y marcar | **Runbook:** `/deploy` (migración) → seeder en modo provisión contra prod (marca los `PLO-*` según Q-31 y crea CRUDO/PURO) → verificar en Config. SAC prod tiene **cero transacciones**: la ventana no le cuesta a nadie |
| El criterio bloquea-vs-avisa de D3 es mío, no del cliente | QA lo endosó con razón más fuerte: entregar puro **no fabrica un servicio** (la fundición ocurrió, la maquila es trabajo real); lo raro es regalar el margen de refinación |
| El aviso de D3 no llega a pantalla | El campo `warnings` de la respuesta HTTP **solo existe en CC-009**, sin commitear ⇒ **CC-009 va primero**; además comparten archivos |
