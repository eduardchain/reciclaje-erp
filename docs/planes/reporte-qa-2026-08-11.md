# Reporte a QA — 2026-08-11

Tres asuntos independientes listos para revisión, **sin commitear ni stagear**.
Van como **tres commits separados** porque son tres decisiones distintas y cada
una debe poder revertirse sola.

| # | Asunto | Migraciones | Tabla compartida | Golden |
|---|---|---|---|---|
| A | SAC — Entrada sin proveedor (#93) | `b8c9d0e1f2a3`, `c9d0e1f2a3b4` | sí (`inventory_adjustments`) | **gate duro** |
| B | Fix soft delete de organizaciones | ninguna | sí (código compartido) | gate |
| C | Traslados conscientes de sede (#94) | `d0e1f2a3b4c5`, `f1a2b3c4d5e6` | sí (`warehouses`) | **gate duro** |

## Gates (corridos sobre el árbol completo, los tres asuntos juntos)

| Gate | Resultado |
|---|---|
| Suite backend | ✅ **1562 passed**, 0 fallos (30:25) |
| Parity check modelos ↔ migraciones | ✅ **DIFF CERO** fuera del baseline |
| **Golden ×3 orgs prod** (Costa, Biogreen, MetaRecycling) | ✅ **0 diffs reales** en 45 capturas |
| `tsc --noEmit` | ✅ limpio |
| `npm run build` | ✅ limpio |
| Seeder SAC idempotente (modo prod, sin `--reset`) | ✅ 2ª corrida sin duplicados |

**Protocolo del golden:** BEFORE = worktree de `origin/main` en `:8001`, AFTER =
árbol de trabajo en `:8002`, **ambos contra la misma BD de dev**. Así se mide
solo el delta de código y no se destruyen los datos de dev. Se corrió **dos
veces**: una al cerrar C en su primera forma, y otra completa al final, después
de que C cambiara de diseño. No se reutilizó la captura vieja.

Las 6 "claves aditivas" del resultado son **una sola clave nueva**
(`sede_warehouse_id`) apareciendo una vez por bodega — Costa 4 + Biogreen 1 +
Meta 1 — **todas con valor `None`**. `golden_diff.py` la acepta *solo* con ese
valor exacto: una sede poblada en org cliente saldría como diff real.

---

## A — SAC: Entrada sin proveedor (#93)

Plan `plan-sac-entrada-sin-proveedor.md` v1.4, informe
`informe-code-entrada-sin-proveedor.md` (§9, §10 y §11 cubren las dos rondas de
pruebas de usuario y sus 9 + 8 fixes).

QA ya dio GO a la versión del plan. Lo que llegó **después** de ese GO, y por
tanto es lo que hay que revisar:

1. **Dos bloqueantes de runtime del navegador** que ningún gate atrapó:
   `useMemo` declarado después de un `return` condicional (pantalla en blanco en
   toda liquidación) y `Decimal` serializado como string por FastAPI contra un
   tipo TS que dice `number` ("NaN kg repartidos"). `tsc`, build, suite y golden
   pasaron con ambos vivos **porque ninguno ejecuta la pantalla**.
2. **La regresión del canal único era de CLASE, no de campo.** QA nombró
   `retentions`; la barrida correcta era enumerar `PurchaseLiquidateRequest`
   entero. Quedaban **4** capacidades inalcanzables desde SAC. Resueltas:
   retenciones, comisión del recolector, **pago de contado por proveedor**.
   `commissions` (fletes) queda **diferido por decisión de Daniel**.
3. **Candado anti doble pago** (no reportado por nadie): des-liquidar NO anula el
   pago enlazado — queda como anticipo (#16/#63) — así que re-liquidar marcando
   contado otra vez pagaría dos veces. Ahora 422 con el monto vivo; el rollback
   total de D14 lo respalda.
4. **Guard Willard en el reparto**: el titular de una cuenta kg no puede ser
   proveedor de compra. Rompió 4 tests de #87/#82 que lo usaban por comodidad —
   re-semantizados separando roles, cero cambios de producción. Que fallaran es
   evidencia de que el guard funciona.

**Dónde mirar más duro:**
- La **atomicidad D14** con las capacidades nuevas encima: retenciones + pago de
  contado + comisión, y un 422 tardío. Nada debe persistir.
- El **round-trip liquidar → des-liquidar → re-liquidar** con retenciones: la
  regla es que los eventos del estado de cuenta siguen a la FILA (`reverted_at`),
  no al status de la compra.
- **Consecuencia declarada y aceptada por Daniel**: las retenciones de una
  Entrada **anulada desaparecen del statement** (el annul delega en unliquidate,
  que pone `liquidated_at = NULL`). Es coherente con #41 pero difiere de una
  compra cancelada fuera de una Entrada, que sí muestra su par.

---

## B — Fix soft delete de organizaciones

**No es parte de #93.** Apareció mientras limpiaba datos de dev y resultó ser un
bug de producción que afecta a **las 7 orgs**.

El filtro `is_active` de #29 vivía **solo** en las rutas de superusuario. Faltaba
en las dos que sirven al miembro normal:

- `get_user_organizations` → la org dada de baja seguía en su selector para
  siempre.
- `get_user_role_in_org` → y quitarla del selector **no bastaba**: el `org_id`
  vive en el authStore y en los deep-links, así que **el miembro seguía operando
  dentro de una org dada de baja**. Ahora 403.

Dicho de otro modo: el soft delete era efectivo contra superusuarios e **inerte
contra los usuarios reales**.

**Riesgo de regresión: cero orgs inactivas** entre las 3 orgs cliente al corte,
verificado contra la réplica — el filtro no le quita una entrada a nadie. Golden
45/45. 3 tests (`TestInactiveOrganizationHidden`), incluido el 403 al intentar
operar.

---

## C — Traslados conscientes de sede (#94)

Informe completo: `informe-traslados-por-sede.md`.

**El origen importa para revisarlo.** El pedido era preconfigurar la ruta de
tránsito del molino — dos líneas en el seeder. No se hizo tal cual: con ese
cambio, mover material de Circunvalar a **su propio molino** habría emitido deuda
de plomo intersede y un cargo de maquila **sin error y sin warning**, porque
`is_contributor = formula is not None` decidía por tener fórmula, sin mirar el
recorrido. Johana confirmó en la reunión del 11-ago que Circunvalar y su molino
son un solo inventario.

Se construyó en dos vueltas:

1. `warehouses.sede_warehouse_id` (auto-FK, **NULL = es su propia sede**). La
   emisión de kg/maquila pasa a exigir cruzar de sede.
2. Al ver eso, Daniel cerró la otra mitad: *"para el molino no hace sentido dos
   pasos, es la misma sede; no se pesa al salir y al llegar"*. Un traslado
   intra-sede ahora **nace `received`**, en un salto origen→destino, sin
   tránsito, sin merma y sin discrepancia. `transfers.transit_warehouse_id` pasa
   a nullable (`f1a2b3c4d5e6`; NULL = fue intra-sede).

**Por qué la no-regresión es demostrable y no verificable caso por caso:** con
`sede_warehouse_id` NULL en todas las bodegas —el estado de las 7 orgs— dos
bodegas distintas son siempre dos sedes distintas, así que todo traslado sigue
siendo intersede y de dos pasos, byte a byte. Por eso los 40 tests previos del
archivo pasaron **sin tocarlos**.

**Dónde mirar más duro:**
- La **validación de la cadena de sedes** (`_validate_sede`): un valor malo aquí
  no da error, da números equivocados en silencio. Se cierran las dos puntas —
  la sede apuntada debe ser su propia sede, **y** una bodega que ya es sede de
  otras no puede tener sede.
- El **`annul` de un traslado de un solo salto**. No se tocó: refleja *todos* los
  `InventoryMovement` con `reference_id = transfer.id`, sin importar cuántos
  saltos hubo. Hay un test dedicado, pero es el punto donde un diseño "por
  receta" habría fallado.
- **`TransferLine.effects_emitted` significa "la línea terminó de procesarse",
  NO "emitió kg"** — una línea no aportante también lo marca True. Costó un
  ciclo. Lo que se assertea es `kg_lead_equivalent is None` y el par vacío.

**El test estrella** corre sin bodega de tránsito al molino, sin cuenta intersede
y sin tarifa de maquila: si el traslado intentara ir en dos pasos *o* emitir,
reventaría con 400. El verde prueba que no lo intentó, en vez de assertar un
contador en cero.

15 tests nuevos (archivo 40 → 55).

### Cambio de tooling incluido en C

`schema_parity_check.py` salía **rojo desde #87** con 4 divergencias que ese
ciclo ya había diagnosticado como cosméticas (Postgres renderiza el mismo CHECK
de dos formas) y cuyo arreglo correcto había prescrito: **normalizar el
comparador, no ampliar el baseline**. Se pagó aquí porque no se puede certificar
"DIFF CERO" con un gate que sale rojo siempre.

La normalización es deliberadamente estrecha (dos formas de castear el mismo
array). Meterlas al baseline habría además apagado el guard `E1_MARKERS` sobre
esas tablas.

**Guarda propia** (`tests/test_parity_normalizer.py`, 9 tests): el riesgo no es
esta regex, es la que alguien ensanche mañana — y un comparador que normaliza de
más convierte el gate en decorado, porque el síntoma de un gate roto es que todo
sale verde. Calca el precedente de #92 (`test_el_patron_atrapa_las_formas_
conocidas`): las dos formas conocidas colapsan, y un valor distinto, un valor de
menos, una columna distinta, un operador distinto, un `IS NULL` invertido y un
`ANY` vs `ALL` **siguen reportando**. Verificada **contra el normalizador roto**:
ensanchando la regex a propósito, el test falla con el mensaje que corresponde.

---

## Lo que los gates NO cubren — decirlo explícitamente

**Ningún gate de este repo ejecuta una pantalla React, y `npm run lint` no
corre** (no hay configuración de ESLint en `frontend/`). Los dos bloqueantes de
la primera ronda de pruebas de #93 pasaron verdes por eso. Hasta que exista
ESLint con `react-hooks/rules-of-hooks`, **la única red es abrir la pantalla**.

Montar ESLint queda propuesto como **ciclo propio**.

---

## Detalles de empaquetado a resolver al commitear

Dos archivos tocan más de un asunto y hay que partirlos o asignarlos
conscientemente:

- **`backend/scripts/seed_sac_org.py`** — lleva los 3 proveedores de prueba
  locales (A) y la configuración de sedes (C).
- **`CLAUDE.md`** — decisión #93 (A) y decisión #94 (C).

Además, el árbol tiene material sin trackear que **no debería entrar sin decisión
explícita de Daniel**: los transcripts de reuniones con el cliente
(`docs/soluciones ambientales del caribe/`), la propuesta comercial, las
plantillas Excel de migración, los directorios de evidencia del golden, y los
documentos de **#89 multiproveedor por línea — construido y descartado sin
commit** (`plan-sac-multiproveedor-por-linea.md`,
`informe-code-multiproveedor.md`, `analisis-sac-multiproveedor-por-linea.md`).

---

## Pendiente de producto, no de código

De la reunión con Johana del 11-ago, verificado contra el código: **no existe una
operación de negocio que baje la deuda de plomo con Willard.** Tres servicios
mueven el libro de kg —la entrada Willard, que la *sube*; el traslado intersede;
y el ajuste manual auditado— y de los tres **solo el ajuste manual puede bajarla**
(delta libre, motivo obligatorio, #75 D16).

Esa precisión importa operativamente, no es un matiz: mientras se construye el
abono, **Johana tiene un camino trazable** —con motivo y auditoría— en vez de
quedarse sin nada. Hay que decírselo al comunicar el pendiente.

La venta a Willard sí funciona tal cual (venta regular por kilo desde Juan Mina).
Lo que falta es el **abono al postconsumo**: el material sale de inventario *y*
baja la deuda, sin ingreso. Es el espejo de la entrada y es el corazón del tema
de salidas.

Fuera de alcance de estos tres commits.
