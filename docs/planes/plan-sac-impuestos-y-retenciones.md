# Plan — Tesorería: «Impuestos y retenciones» en una sola página (v1.0)

Autor: Eco Coder 1 · 20-nov-2026 · rama `coder-1/impuestos-retenciones` (base develop `31ba117`)
Nivel: **lógica**. Lleva un endpoint nuevo y la naturaleza de cada saldo sale de su signo.
Pedido: el Coordinador, 20-nov: que Tesorería → Retenciones muestre también «[Impuestos] IVA por Pagar» y las demás entidades de impuestos, cada una con su saldo y su estado de cuenta.

## 1. Qué pasa hoy

- `RetentionsPage` (#79, ruta `/treasury/retentions` detrás de `FP flag=kg_ledger_enabled` + `third_parties.view`) lista **solo** las entidades `[Retenciones] X`, a través de `GET /third-parties/retention-entities` (`list_retention_rows`). Son las retenciones que SAC **practica** al liquidar compras: un pasivo con la DIAN.
- Las entidades `[Impuestos] X` (#112, #122) no aparecen en ninguna pantalla de Tesorería:
  - el IVA por Pagar de lo que SAC factura, al que desde #122 se le descuenta el IVA de las compras;
  - la ReteFuente, ReteIVA e ICA que **le practican** a SAC: anticipos, activos.

  Solo se llega a ellas desde el link del detalle de una venta o compra. El estado de cuenta ya las muestra desde #125.
- Son dos familias **separadas a propósito** (`tax_entities.py`, docstring): netear la retefuente que SAC practica con la que le practican es un error contable. Esta página las muestra **juntas pero en secciones distintas**, nunca sumadas.

## 2. Qué cambia

### D1 — Endpoint `GET /third-parties/tax-entities`
- Usa el mismo patrón que `retention-entities`: `require_org_flag("kg_ledger_enabled")` (403 sin flag, también para admin), permiso `third_parties.view` y ruta estática declarada **antes** de `/{third_party_id}`.
- **Reconoce las entidades por CÓDIGO, nunca por texto** (#112 D4b): las que tienen asignada la categoría con `system_code='taxes'` (`TAX_CATEGORY_CODE`). Un tercero que se llame «[Impuestos] lo que sea» sin esa categoría no aparece. Tampoco aparecen las `[Retenciones] X`, que van en su sección de siempre.
- Cada fila trae `entity_id`, `name`, `tax_type` (iva/retefuente/reteiva/ica, o `null` si el nombre no sigue el formato), `municipality`, `current_balance` e `is_active`.
  - El tipo se lee del nombre con un parser nuevo en `tax_entities.py` (el módulo dueño del formato), hermano de `_parse_entity` de retenciones. **El tipo es solo para el rótulo; la pertenencia la decide el código.**
- Orden: IVA, ReteFuente, ReteIVA, ICA por municipio, y al final los que no parsean.
- Servicio `list_tax_entity_rows(db, org_id)` en `tax_entities.py`. Sin migración y sin cambios en ninguna tabla.

### D2 — La página: dos secciones, el signo decide la naturaleza
- El título pasa a **«Impuestos y retenciones»**, igual en el sidebar. La ruta no cambia.
- **Sección 1, «Impuestos de lo que facturamos»** (nueva): las filas de D1, con nombre, saldo y una etiqueta de naturaleza.
- **Sección 2, «Retenciones que practicamos»**: la tabla de hoy, sin cambios de lógica (tarifas, Editar, Configurar %, Pagar).
- 🔴 **La naturaleza sale del SIGNO del saldo, no del tipo** (#112 D4c y P19). En la convención de terceros, saldo < 0 = le debemos (pasivo) y saldo > 0 = nos debe (activo).

  | Saldo | Etiqueta | Pagar |
  |---|---|---|
  | < 0 | **Por pagar** | se ofrece (`liability_payment`, como hoy en retenciones) |
  | > 0 | **A favor** | NO se ofrece: un saldo a favor se cruza en la declaración, no se paga |
  | = 0 | — | no se ofrece |

  - El IVA puede quedar **a favor**. Medido en mi BD: «[Impuestos] IVA por Pagar» de SAC está en **+236.041,63** porque solo tiene IVA de compras (#122), que es descontable. Etiquetarlo «Por pagar» por su nombre sería mentir.
  - Una retención que nos practican es normalmente positiva («A favor»). Si un día queda negativa, la fila lo dice tal cual, sin `abs()` (D4 de #110).
  - Un solo helper `taxBalanceNature(balance)` alimenta la tabla de escritorio y las tarjetas de 390. La sección 2 también lo usa para su etiqueta (sus saldos son negativos = Por pagar). No hay una segunda copia del criterio.
- Cada fila de la sección 1 lleva **Estado de Cuenta** (`?third_party_id=&returnTo=/treasury/retentions`, funciona para entidades de sistema desde #125) y **Pagar** según la tabla de arriba.
- **No hay totales por sección ni un total general**: sumar IVA con anticipos es justo el neteo que #112 prohíbe.
- Sin entidades de impuestos (ninguna factura con IVA todavía), la sección 1 muestra «Aún no hay impuestos registrados. Aparecen al liquidar una venta, una Salida de Plomo o una compra con IVA.».

### D3 — Orgs sin flag: idénticas por construcción
- La ruta, la entrada del sidebar y los dos endpoints siguen detrás de `kg_ledger_enabled`. Costa y Meta no tienen ni la página ni el endpoint.
- Nada compartido cambia: `list_retention_rows` y su endpoint quedan byte a byte, y `useRetentionRows` se usa igual en las otras pantallas (#79 F2).

## 3. Lo que NO cambia
- Los saldos, la terna de signos (`TAX_SIGN_ON_PARTY`), el balance (`_is_tax_entity`) y el panel de dinero inactivo.
- El flujo de pago: «Pagar» abre el mismo `liability_payment` de hoy. `payment_to_supplier` ya acepta `liability`, que es el `behavior_type` de la categoría `taxes`.

## 4. Verificación

**Backend** (archivo nuevo `tests/test_tax_entities_listing.py`, dirigidas por grep sobre `third_parties.py` y `tax_entities.py`):

| T | Caso | Esperado |
|---|---|---|
| T1 | venta con IVA + ReteFuente + ICA Bogotá liquidada | 3 filas: IVA saldo < 0, ReteFuente > 0, ICA > 0, con tipo y municipio |
| T2 | más una compra con IVA (#122) | el IVA sube por el monto exacto del IVA de compra |
| T3 | un tercero normal llamado «[Impuestos] IVA por Pagar» sin la categoría | no aparece |
| T4 | renombrar la categoría `Impuestos` a «Otra cosa» | las entidades siguen apareciendo (código, no texto) |
| T5 | existe `[Retenciones] ReteFuente` (compra con retención) | no aparece aquí; sí en `retention-entities`, igual que antes |
| T6 | org sin `kg_ledger_enabled` | 403, también para admin |
| T7 | rol con `third_parties.view` / rol sin él | 200 / 403 (control positivo, regla de los tests de permiso) |
| T8 | dos orgs con IVA | cada una ve solo el suyo |

Corren las dirigidas que salen del grep (el comando y su resultado van en el log), más las tres guardas.

**Frontend**, E2E con Playwright propio contra :8011/:5181 en mi BD:

| E | Caso | Esperado |
|---|---|---|
| E1 | SAC, la página | dos secciones; el IVA con su saldo real y «A favor» si es > 0 (hoy +236.041,63) |
| E2 | una venta con IVA liquidada que deje el IVA < 0 | la fila dice «Por pagar» y ofrece Pagar |
| E3 | una fila «A favor» | sin botón Pagar |
| E4 | Estado de Cuenta de la fila IVA | abre con la entidad en el selector (#125) |
| E5 | Costa | sin entrada en el sidebar; `/treasury/retentions` responde como hoy (FP) |

**Plantado** (la matriz va commiteada con el plan, antes de plantar; copia por ruta y cierre por sha256):

| P | Defecto plantado | Debe caer | Puede caer de más |
|---|---|---|---|
| P1 | reconocer por nombre (`ilike '[Impuestos]%'`) en vez de por código | T3, T4 | — |
| P2 | sin `require_org_flag` | T6 | — |
| P3 | sin `third_parties.view` | T7 | — |
| P4 | incluir también `[Retenciones]` | T5 | T1 |
| P5 | sin filtro de org | T8 | — |
| P6 | `taxBalanceNature` con el signo invertido | E1, E2 | E3 |
| P7 | Pagar en toda fila con entidad, sin mirar el signo | E3 | — |

**Capturas** de SAC a 1440 y 390.

**Golden:** no aplica. El endpoint es nuevo y flag-gated; `/third-parties` no está en `CAPTURES`, y ninguna captura del golden cambia.

## 5. Supuestos
- S1: «Impuestos de lo que facturamos» incluye el IVA de compras (#122) dentro de la misma entidad de IVA. Así lo modeló #122 (una sola entidad, el IVA de compra descuenta), y la página muestra ese neto: el IVA por pagar del período a la DIAN.
- S2: el título de la página y del sidebar cambia a «Impuestos y retenciones». Si Daniel prefiere conservar «Retenciones», es un rótulo.
