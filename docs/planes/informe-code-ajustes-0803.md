# Informe de implementación — Ajustes rápidos de la reunión SAC del 3 de agosto

**2026-08-04.** Plan: [plan-sac-ajustes-rapidos-reunion-0803.md](plan-sac-ajustes-rapidos-reunion-0803.md) v1.2 (micro-QA 🟢 GO sobre v1.0 + las 5 respuestas de Daniel + los 4 hallazgos adoptados).

---

## 1. Qué se entregó

| Ítem | Estado | Migración |
|---|---|---|
| **A** — Factura en la Entrada, ambos tipos, fuente única por tipo | ✅ | `d5e6f7a8b9c0` (aditiva, nullable) |
| **B** — Hora en auditoría + **fix de un defecto vivo en producción** | ✅ | — |
| **C** — Autoservicio de centros de distribución Willard | ✅ | `c4d5e6f7a8b9` (1 permiso) |
| **D** — Categoría "Gastos Financieros" | ✅ | — (seeder) |
| **E** — La placa editada llega a la compra derivada | ✅ | — |

**18 tests nuevos** (`tests/test_sac_ajustes_0803.py`), todos verdes. El plan preveía 19: los tests 9 y 10 quedaron **fusionados** — el assert que relee los centros desde BD *es* la verificación de efecto real, así que separarlos habría sido el mismo assert dos veces.

---

## 2. Los cuatro hallazgos del micro-QA: cómo se resolvieron

**H1 + H2 — el GET desapareció.** El plan especificaba `require_permission("config.view")`, un permiso inexistente. QA propuso eliminar el GET porque `useOrgSettings()` ya trae la lista vía `GET /organizations/{id}` — la misma query que alimenta el selector de la Entrada. Adoptado: **solo PUT**. La página de Config lee con ese hook y al guardar invalida `["org-settings", organizationId]`, con lo que se refrescan la tarjeta y el selector de una vez. Menos superficie, un permiso menos, y H1 se evapora.

**H3 — resuelto de forma más fuerte que lo planeado.** El plan decía "sumar el `ILIKE` a la cadena `OR` sobre el outer join existente". Al implementarlo apareció que ese outer join a `Purchase` es **condicional**: solo se agrega dentro de `if display_status:` ([inbound_order.py:794](../../backend/app/services/inbound_order.py#L794)). Reusarlo habría roto al buscar sin filtro de estado y lo habría **duplicado** al buscar con filtro. Se usó **`EXISTS`** —el mismo patrón que ya emplean `material_match` y `world_match`— con lo que el modo de falla que H3 señalaba (degradar `outerjoin` a `join` y desaparecer todas las Willard en silencio) queda **estructuralmente imposible**, no solamente evitado. El test lo cubre igual.

**H4 — el test relee desde BD.** La columna `settings` no usa `MutableDict` y el modelo lo documenta: *"toda escritura reasigna el dict completo"*. El servicio copia el dict, reemplaza una clave y **reasigna**. El test del invariante hace `db_session.expire_all()` y relee la organización: si alguien cambiara la reasignación por una mutación in-place, el assert de los centros fallaría — mientras que un assert contra el response habría pasado con los flags "intactos"… por no haberse escrito nada.

**Q4 — la asimetría hermana, alineada.** QA señaló que `if obj_in.vehicle_id is not None` impedía **quitar** el vehículo. `driver_id` y `vehicle_id` pasan a `fields_set` (patrón de `notes`), así que mandar `null` ahora sí lo borra — y en tipo compra deja `purchase.vehicle_plate = None`. Hay test.

---

## 3. Desviaciones del plan (declaradas)

**3.1 — El status del set bloqueado D7b es 422, no 400.** El plan decía que editar `date` en una entrada tipo compra seguiría dando 400. El módulo inbound responde **422**; es la convención establecida en #80 (*"los status siguen el idioma de cada módulo: inbound 422, compras 400"*). Se corrigió la expectativa del test, no el código.

**3.2 — Colisión de revision id.** La primera migración nació como `b3c4d5e6f7a8`, que **ya existe** (`config_module_permissions`) — alembic detectó "Cycle in revisions". Renombrada a `d5e6f7a8b9c0`. Lección para el próximo ciclo: los ids "bonitos" tipo `aXbYcZ` están casi agotados en este repo; conviene verificar antes de escribir.

**3.3 — La página de centros es un tab propio de Config, no una tarjeta suelta.** El plan decía "tarjeta en la página de configuración SAC". Se hizo como tab propio (`/config/centros-willard`, `permission: config.manage_sac_settings`, `orgFlag: kg_ledger_enabled`) porque es exactamente el patrón que siguen los otros 9 tabs y queda discoverable para Johana, que fue quien lo pidió.

---

## 4. El hallazgo que cambia lo que B significa

**Compras y Ventas no necesitaban la hora: ya la tenían — y era falsa.**

`PurchaseDetailPage` y `SaleDetailPage` ya usaban `formatDateTime` en las tres filas de auditoría, incluida la de liquidación. Pero `liquidated_at` **no es un timestamp**: es `liquidation_date or document.date` ([purchase.py:586](../../backend/app/services/purchase.py#L586), [sale.py:396](../../backend/app/services/sale.py#L396)), una `BusinessDate` normalizada a **mediodía UTC**. Renderizada en Bogotá (UTC−5) eso da:

```
04/08/2026, 07:00 a. m.
```

Es decir: **toda liquidación de las 3 organizaciones cliente muestra hoy, en producción, que se liquidó a las 7:00 de la mañana.** No es un `12:00` obviamente sintético que uno descarta — es una hora plausible, de aspecto operativo, que un auditor podría creerse.

Corregido a `formatDate` en ambas páginas. **La consecuencia visible para Costa, MetaRecycling y Biogreen no es que ganen una hora: es que pierden una hora falsa.** Vale comunicarlo así al cliente si alguien nota el cambio.

> **Matiz para el aviso al cliente (N1 del re-QA)** — la frase de arriba vale para los registros actuales, pero **no uniformemente para el histórico**. Según la decisión #43, las compras/ventas anteriores al commit `bdc0791` (2026-04-13) nacieron con `liquidated_at = now()`, o sea un timestamp **real**; el backfill que las corrige se aplicó en dev y para producción quedó condicionado a backup + aprobación del cliente, **sin registro de haberse corrido**. Si nunca se corrió, esos documentos viejos de prod sí tenían una hora real y a partir de este cambio deja de mostrarse. El fix sigue siendo el correcto —la semántica canónica del campo es fecha de negocio, no momento de captura— pero si alguien de Costa nota el cambio en un documento antiguo, esa es la explicación honesta.

`DoubleEntryDetailPage` ya usaba `formatDate` en esa fila — estaba bien; solo se le agregó la hora a `cancelled_at`, que sí es un timestamp real.

**Regla que este ciclo deja escrita**: *valor derivado de `BusinessDate` → `formatDate`; valor de `now()` → `formatDateTime`*. Los campos con nombre de timestamp que en realidad son fechas de negocio (`liquidated_at`, `date`, `dispatch_date`, `received_date`) se quedan sin hora.

Mapa de lo tocado:

| Página | Campo | Antes | Después |
|---|---|---|---|
| InboundDetail | `created_at`, `annulled_at` (×2) | `formatDate` | `formatDateTime` |
| InboundDetail | `liquidated_at` | `formatDate` | **sin cambio** (fecha de negocio) |
| TransferDetail | `annulled_at` | `formatDate` | `formatDateTime` |
| Tariffs / Formulas | `created_at` del **historial** | `formatDate` | `formatDateTime` |
| PurchaseDetail / SaleDetail | `liquidated_at` | `formatDateTime` | **`formatDate`** ← fix |
| DoubleEntryDetail | `cancelled_at` | `formatDate` | `formatDateTime` |

En Tarifas y Fórmulas la hora se agregó **solo en los modales de historial**, que es donde resuelve algo real: son append-only y `vigente = max(created_at, id)`, así que dos versiones del mismo día son hoy indistinguibles. En las tablas principales, que muestran una sola versión vigente, la hora sería ruido.

---

## 5. Decisiones de implementación que merecen mirada

**A — la lectura condicional es el corazón.** El response hace `order.purchase.invoice_number if order.purchase else order.invoice_number`, y la escritura usa **la misma condición**. Escritura y lectura simétricas significan que no existe un estado en el que las dos copias discrepen: en tipo compra la columna del inbound se queda en `NULL` por construcción, y hay un test que lo afirma explícitamente. `order.purchase` ya viene cargado del enrich B1 por página → cero queries nuevas.

**C — la superficie estrecha es la decisión de seguridad.** El endpoint no recibe un dict de settings: recibe una lista de centros. No hay forma de que un admin de organización toque un feature flag por esta vía, ni por error ni a propósito. El test del invariante fija los 9 settings, hace el PUT y relee los 8 restantes.

**E — sin guard de estado, deliberadamente.** Se propaga la placa incluso con la compra liquidada. Una compra liquidada con la placa equivocada es exactamente el caso que hay que poder corregir, y no hay efecto financiero.

---

## 6. Gates

- **Suite completa**: **1445 passed** en 23:22, cero fallos (1427 previos + 18 nuevos).
- **18 tests nuevos** verdes.
- **`tsc --noEmit`**: limpio.
- **Migraciones** aplicadas en dev (5434) → head `c4d5e6f7a8b9`.
- **`schema_parity_check.py`**: **mis migraciones espejan los modelos exactamente**, probado por experimento en vez de por afirmación:

  | Estado de dev | Divergencias fuera del baseline |
  |---|---|
  | Con mis 2 migraciones | **4** |
  | Revertidas (`downgrade a7b8c9d0e1f2`) | **5** |

  La quinta que aparece al revertir es `[columna] inbound_orders.invoice_number: SOLO en test-create_all` — justo lo esperable cuando el modelo tiene la columna y la BD migrada no. O sea: este ciclo **no suma ni una** divergencia.

  Las 4 restantes son **preexistentes y cosméticas**: PostgreSQL renderiza el mismo `CHECK` de dos formas (`ARRAY[(x)::text, …]` vs `(ARRAY[x, …])::text[]`) en `kg_ledger_accounts` ×2, `material_kg_profiles` y `retention_configs`. El texto de la constraint es **byte-idéntico** entre modelo y migración (verificado), ambas bases son PG 16.11, y ninguna de mis migraciones menciona esas tablas. Aparecen en el gate —en vez de quedar silenciadas— porque el `E1_MARKERS` del script prohíbe allowlistear cualquier objeto SAC: el guard anti-abuso haciendo su trabajo. **El arreglo correcto no es ampliar el baseline sino normalizar el comparador** (N2 del re-QA): colapsar paréntesis y casting del texto del `CHECK` antes de comparar. Un baseline las silenciaría para siempre y erosionaría el guard `E1_MARKERS`, que aquí hizo exactamente su trabajo.
- **Golden ×3 orgs**: **no aplica** (argumento de §7 del plan, aceptado por QA tras intentar romperlo). Ningún reporte cambia de forma ni de valor: `inbound_orders` es tabla exclusiva de SAC con cero filas en las orgs cliente y router flag-gated; el permiso nuevo no está asignado a ningún rol; B es frontend puro.
- **390px**: los campos nuevos siguen los patrones obligatorios **verificados por lectura**: el input de factura vive en un `grid grid-cols-1 md:grid-cols-2` con `w-full`; los chips de centros en `flex flex-wrap gap-2`; el input de alta `w-full sm:w-64` y los botones `w-full sm:w-auto`. **La verificación visual en DevTools no la hice** — queda para las pruebas de Daniel.
- **`npm run build`**: compila (valida en el bundler real el lazy import de la página nueva).

---

## 7. Runbook post-deploy

1. Deploy.
2. Crear "Gastos Financieros" en la org SAC de producción (`POST /expense-categories`: `is_direct_expense=false`, `pnl_section=financiero`). El seeder ya la incluye si se re-corre.
3. Asignar `config.manage_sac_settings` al rol admin de SAC (los 4 admins ya lo tienen por bypass; asignarlo documenta la intención).
4. Pedirle a Johana que pruebe: capturar una compra con factura, editarla **después** de liquidar, corregir la placa de una entrada liquidada y verificar que la compra la refleja, y agregar un centro de distribución.

---

## 8. Addendum — hallazgos de las pruebas de Daniel (2026-08-04)

**8.1 — El quick-create de flota faltaba en la página de editar.** Reportado con captura: al editar una entrada liquidada, el selector de Vehículo mostraba "Sin resultados" y no había forma de crear uno. Causa: el quick-create inline que agregó el Ciclo B (diálogo de solo-placa / solo-nombre contra el CRUD de flota) se implementó **únicamente en `InboundCreatePage`**; `InboundEditPage` nunca lo tuvo. Con la lista de vehículos vacía —el caso de una org recién sembrada— el operador quedaba atrapado sin salida dentro del formulario.

Portado tal cual: mismo diálogo, mismos hooks (`useCreateDriver` / `useCreateVehicle`), mismo botón `+` junto al selector, para conductor **y** vehículo. Barrido de las demás pantallas: la única otra que usa esos hooks es `FleetPage`, que es el CRUD completo — ahí no aplica.

**8.2 — Mi fix de E estaba a medias.** El backend ya aceptaba borrar el vehículo (`fields_set` en vez de `is not None`), pero el frontend **nunca mandaba el vacío**: `if (vehicleId && vehicleId !== …)` descartaba el caso en el que el valor nuevo es `""`. Corregido a `if (vehicleId !== …) payload.vehicle_id = vehicleId || null`, ídem conductor. El tipo `InboundOrderUpdate` declaraba `driver_id?: string` sin `null` mientras `collector_id` sí lo permitía — alineado, y `tsc` fue quien lo atrapó.

Lección: cuando el arreglo cruza backend y frontend, la asimetría puede estar **en los dos lados** con la misma forma. Arreglé uno y di el ítem por cerrado; la prueba manual encontró el otro.

Sin tests nuevos: 8.1 es frontend puro y 8.2 ya está cubierto por el test 18 (`test_clearing_vehicle_clears_plate`), que probaba el backend y pasaba — justamente por eso no delató el hueco del frontend. `tsc` limpio, `npm run build` OK.

---

## 9. Re-QA

🟢 **GO sin condiciones**, cero hallazgos nuevos. Verificó de primera mano el defecto de §4, la simetría lectura/escritura de A, el `EXISTS` de H3, el encadenamiento de las dos migraciones y —con grep— que ninguna menciona las tres tablas de las divergencias cosméticas. Las 3 notas (todas no bloqueantes) quedan incorporadas: **N1** en §4 (matiz del histórico pre-`bdc0791` para el aviso al cliente), **N2** en §6 (normalizar el comparador del parity, no ampliar el baseline) y **N3** es el gate de 390px, que sigue abierto y declarado.

Por pedido explícito del re-QA, la regla *`BusinessDate` → `formatDate` / `now()` → `formatDateTime`* subió a **convención del repo** en la sección Key Patterns de CLAUDE.md (bullet de `BusinessDate`), no solo como decisión del ciclo.

---

## 10. Lo que queda anotado

- **Q6 del plan** — el timestamp real de la liquidación sigue sin existir. Recomendación mantenida: no construirlo ahora (columna en 3 tablas compartidas → el golden vuelve a ser gate, y solo se llenaría hacia adelante). Con el fix de §4, al menos ya no se muestra una hora inventada en su lugar.
- Los **3 ciclos grandes** de la reunión siguen pendientes: multi-proveedor por línea, estado "revisada" (bloqueado hasta que existan David e Ingrid como usuarios) y vencimientos de obligaciones (postergado por Daniel).
