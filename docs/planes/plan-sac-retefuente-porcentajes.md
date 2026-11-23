# Plan: elegir el % de ReteFuente al liquidar una Entrada, con uno por defecto (v1.0)

- **Pedido** (Johana, vía Daniel, 23-nov): en ReteFuente maneja porcentajes distintos. Quiere elegir el porcentaje al liquidar una Entrada, y que venga uno por defecto, el de hoy.
- **Autor:** Eco Coder 1. Rama `coder-1/retefuente-porcentajes` sobre develop `dea2320`.
- **Nivel propuesto: lógica.** La precarga decide qué tasa se guarda en `purchase_retentions.rate` al reliquidar.
- **Evidencia:** `~/sac-evidencia/2026-11-23/coder-1-retefuente/` (barrido de consumidores) y `~/sac-evidencia/2026-11-23/retefuente-porcentajes/tarifas.log` (medición del Coordinador sobre prod, solo GET).

## 1. Qué ya existe y qué no

**Ya existe, sin código nuevo:**
- **Varias tarifas por tipo.** El catálogo (#79) admite una fila por (tipo, municipio, concepto), con los textos normalizados. Para tener una segunda ReteFuente hace falta un concepto distinto (p. ej. «No declarante 3,5 %»). Johana la crea en Tesorería → Retenciones, que ya tiene el campo «Concepto (opcional)» y el texto que lo explica (`RetentionsPage.tsx:393-395`).
- **Elegir la tarifa al liquidar.** En Liquidar Entrada, cada compra tiene «+ Retención». La fila nueva trae un selector con todas las tarifas activas (`Retención en la Fuente · Concepto (2,5%)`) y el monto precalculado, que se puede editar (#79 F1).
- **El catálogo de SAC en prod** (medido): una sola ReteFuente, 2,5 %, sin concepto; ReteIVA 2 % y 15 % sobre el IVA; ICA Barranquilla 0,7 %. Hay 7 retenciones vivas en las compras, todas ReteFuente 2,5 %, en **7 de 146 compras**.
- **No escribimos en prod.** Las tarifas las carga Johana.

**Falta:**
1. **El defecto de la precarga** (pre-existente, registrado en #112 como defecto 3). Al reliquidar una Entrada desliquidada (#93 D20), `InboundLiquidatePage.tsx:611-617` reconoce la tarifa guardada solo por (tipo, municipio). Con dos ReteFuente toma **la primera del catálogo**, y al liquidar manda **su** `rate`. El monto queda bien, porque la fila llega con `touched: true` (#79 F1). Lo que se corrompe es la tasa de auditoría, y el «Sugerido» muestra otra tasa. Hoy no muerde: hay una sola ReteFuente. **Empieza a morder el día que Johana cree la segunda**, que es justo lo que pide este cambio. Por eso va primero.
2. **Una tarifa guardada que ya no está en el catálogo desaparece de la precarga EN SILENCIO** (`:618`, `if (!cfg) return null`). Si Johana reliquida sin notarlo, la compra nace sin la retención y al proveedor se le debe de más. Es la misma familia que el punto 1, y aparece en cuanto haya que desactivar una tarifa.
3. **Ninguna tarifa viene por defecto.** «+ Retención» agrega la fila con el selector vacío y en rojo.

## 2. Barrido de consumidores

Comandos y salida en `barrido_consumidores.log`.

| Archivo | Usos | ¿Lo toca el plan? |
|---|---|---|
| `pages/inbound/InboundLiquidatePage.tsx` | 10 | **Sí.** Es la única precarga que reconoce una tarifa guardada (grep `retentionConfigs.find`: un solo resultado, `:613`) |
| `pages/treasury/RetentionsPage.tsx` | 13 | Solo con D1-B, para mostrar cuál es la tarifa por defecto. Con D1-C, también la marca |
| `pages/purchases/PurchaseLiquidatePage.tsx` (compartida, 7 orgs) | 8 | **No.** Arranca vacía, sin precarga. Para SAC es inalcanzable desde el canal único (#80 B1), y en las otras orgs las retenciones están detrás del flag. El default no se agrega acá: nadie de SAC llega |
| `components/shared/DocumentTaxesCard.tsx`, `pages/sales/SaleLiquidatePage.tsx`, `pages/willard/WillardDeliveryDetailPage.tsx` | 8 / 2 / 2 | **No.** Son impuestos de venta y salidas (#112), con otro selector y otras entidades |
| `hooks/useMasterData.ts`, `services/thirdParties.ts`, `types/third-party.ts` | 3 / 7 / 1 | No (lectura del catálogo, sin cambios de contrato) |
| `backend/.../inbound_orders.py:196` (`InboundRetentionDetail`) | 1 | No. Ya devuelve `rate`, que es lo que la precarga necesita |

## 3. Decisiones técnicas (las propongo yo; las revisa QA)

**T1. La precarga reconoce la tarifa por (tipo, municipio, TASA), no por `config_id`.**
- Lo que se guarda en `purchase_retentions` es `rate`. El concepto y el `config_id` no se guardan (#112 e: `config_id` viaja sin persistir). Si se reconoce por la tasa, la reliquidación vuelve a guardar **la misma tasa** que tenía. Esa es la invariante que importa.
- Cómo se compara: `rate` es `Numeric(7,4)` y llega como **string** («2.5000», trampa #93). `rate_pct` es `Numeric(5,2)` y llega como float. Se comparan `Math.round(num(x) × 10000)` de cada lado, con `num()` en la frontera. El tipo `InboundRetentionDetail.rate: number` miente y se corrige a `number | string | null`.
- **Si hay varias con la misma tasa** (dos conceptos al 2,5 %): se prefiere la que no tiene concepto, y si no la hay, la primera del catálogo. Es inocuo, porque lo que se guarda es idéntico. Se declara.
- **Sin tasa guardada** (filas viejas con `rate` nulo; hoy son 0 en prod): si hay exactamente una tarifa de ese (tipo, municipio), se usa esa, como hoy. Si hay varias, se aplica T2.
- **Descartado:** guardar `config_id` en `purchase_retentions`. Costaría una migración en una tabla compartida y no mejora nada. Si Johana edita la tasa de una tarifa en el catálogo (el PATCH lo permite), reconocer por `config_id` mostraría la tasa NUEVA con el monto viejo y guardaría esa mezcla. Reconocer por la tasa deja la fila sin tarifa y le pide elegir, que es lo correcto: la tasa cambió.

**T2. Una retención guardada que no encuentra su tarifa NO desaparece** (arreglo del punto 2 de §1).
- Queda la fila con `config_id: ""`, su monto guardado y `touched: true`, y una nota debajo: «La tarifa de 3,5 % ya no está activa: elija otra o quite la retención».
- La validación que ya existe («falta elegir la tarifa de una retención») bloquea el Liquidar hasta que se elija o se quite. Fail-closed: lo peor que pasa es un clic de más, nunca una compra sin la retención que tenía.
- La tasa vieja que muestra la nota se guarda en un campo opcional de la fila (`staleRate?: number`). `assertDraftShape` lo acepta si es número o si falta, así que un borrador escrito antes del cambio sigue siendo válido.

**T3. El default vive en una función pura y solo se usa al apretar «+ Retención».**
- Las dos funciones van en `utils/retentionDefaults.ts`: `matchSavedRetention(saved, configs)` (T1/T2) y `defaultRetentionConfig(configs, …)` (D1). Las usa solo `InboundLiquidatePage`.
- Con default, la fila nueva nace con esa tarifa elegida y `touched: false`, o sea con el monto precalculado. Cambiarla es el mismo selector de hoy.
- El default **nunca** es una tarifa inactiva ni una `base_kind='iva'`: el servidor la rechaza en compras (#112 e), y ofrecerla por defecto sería ofrecer un 422.
- En el selector, la tarifa por defecto lleva «· por defecto», para que se vea por qué vino elegida.

**T4. Mobile 390.** El bloque de retenciones vive en la tarjeta de cada compra y no cambia de forma. Lo nuevo es la nota de T2 (texto que se parte en varias líneas, sin ancho fijo) y el «· por defecto» dentro del item del selector. Se mide con captura a 1440 y a 390 y sin scroll horizontal.

**T6. El seeder no vuelve a crear una tarifa que Johana desactivó** (lo encontré verificando el plan; con A es necesario).
- Hoy `create_retention_configs` (`seed_sac_org.py:1270-1277`) hace POST de cada tarifa de `RETENTION_CONFIGS` y solo tolera el 409, que el servicio devuelve únicamente si hay una tarifa **activa** igual (`find_active_config`). Si Johana desactiva la ReteFuente general, la próxima provisión la crea de nuevo, activa al 2,5 %, y con A **el default resucita** sin que nadie lo decida. Es la familia de «el seeder no pisa lo que no puso él» (#109, #116).
- El arreglo: antes de cada POST, el seeder lee `GET /third-parties/retention-entities`, que también lista las tarifas inactivas, y **omite** la tarifa si ya existe una con el mismo (tipo, municipio, concepto) normalizados, activa o no, avisando «existe (inactiva): no se recrea». Sin catálogo (org nueva), siembra igual que hoy.
- Test puro en `test_seed_sac_settings.py` (o un archivo hermano), con un API falso que **se porta como el backend**: lista activas e inactivas y responde 409 solo ante una activa. Casos: inactiva → sin POST; activa → POST con 409 tolerado (como hoy); ausente → POST 201. **Control positivo:** con el código de `dea2320`, el caso inactiva hace el POST.
- Con B o C también aplica: un default que resucita en una provisión es el mismo defecto.

**T5. Alcance de recolector (#129).** Con alcance no hay catálogo de retenciones (S5), así que nada de esto corre para Ingrid. Si D1-C agrega un endpoint, queda **fuera** de `SCOPED_ENDPOINTS`: 403 para un usuario con alcance, y la página no lo llama.

## 4. Decisiones de Daniel

### D1. ¿De qué depende el porcentaje que viene por defecto?

| Opción | Qué pasa | Costo |
|---|---|---|
| **A (recomendada): un solo default, por regla.** Por defecto viene la ReteFuente general, la que **no tiene concepto**. | Hoy es la de 2,5 %, o sea «el de hoy». Las otras (con concepto) se eligen en el selector. Para cambiar el default, Johana edita la tasa de la general. Si la desactiva, no hay default y el selector arranca vacío, como hoy. | Solo frontend, cero migraciones. La regla es determinista: el servicio no deja tener dos ReteFuente activas sin concepto (`find_active_config`, #79 D14). Tesorería → Retenciones muestra «Se propone al liquidar» junto a esa fila |
| **B: el del proveedor.** «+ Retención» trae la tasa de ReteFuente de la última compra liquidada de ese proveedor, y si no tiene, la de la opción A. | Si a un proveedor siempre se le retiene 3,5 %, viene 3,5 %. | Un endpoint nuevo de solo lectura (`GET /inbound-orders/supplier-last-retefuente?third_party_id=`, detrás del flag y fuera del alcance) y su test. Sin migración. Reconoce la tarifa con el mismo T1 |
| **C: marcar en el catálogo cuál es la de por defecto.** | Igual que A, pero se elige cuál con un interruptor en Tesorería → Retenciones. | Migración en `retention_configs` (tabla solo de SAC; golden no aplica), un índice único parcial (una por org) y el toggle. Es más explícito que A, a cambio de una migración |

**Por qué recomiendo A:** «uno por defecto, el de hoy» es literalmente A, y A no cuesta migración. B tiene sentido si el porcentaje depende del proveedor; eso lo responde D2, y se puede agregar después sin tocar nada de A, porque B cae a A cuando no hay historia. C solo aporta sobre A si Johana quiere que el default sea una tarifa con concepto. Inferencia nuestra (c), sin confirmar con ella: en Colombia la ReteFuente de compras suele cambiar según si el proveedor declara renta, lo que apuntaría a B. Por eso D2 se lo pregunta.

### D2. Qué porcentajes usa, y de qué depende cuál

- **Los carga Johana** en Tesorería → Retenciones. El plan **no los siembra en prod**: `RETENTION_CONFIGS` del seeder no cambia, y con T6 el seeder tampoco recrea una tarifa que ella desactivó.
- **No está en el inventario de preguntas.** Q-07 (✅) respondió «opcionales; tarifas típicas, monto editable». Q-66 a Q-68 son de IVA. La fila 📎 «tabla de retenciones por tipo de proveedor» sigue sin recibir. Una sola pregunta para Johana, vía Daniel:
  > «¿Qué porcentajes de retención en la fuente usa en las compras, y qué decide cuál aplica: el proveedor (siempre el mismo para él), el material o el monto?»
- Su respuesta decide entre A y B y se registra en el inventario el mismo día. Ese registro lo hace el Coordinador.
- **No bloquea el arreglo de §1.1 y §1.2**, que hace falta con cualquier respuesta.

### D3. ¿El default se agrega solo a cada compra?

**Recomendación: no.** Solo propone la tarifa cuando Johana aprieta «+ Retención». Hoy se retiene en 7 de 146 compras: si se agregara sola, habría que quitarla en las 139 restantes, y una que se olvide de quitar le resta plata al proveedor. Si Daniel prefiere que se agregue sola, sería solo en las compras de proveedores que la tuvieron la última vez, y eso es D1-B.

## 5. Tests

El frontend no tiene infraestructura de tests. Como en #123, las funciones puras se prueban con casos por `node`, y la pantalla con e2e de Playwright contra `:8011`/`:5181` y la base `reciclaje_coder_1`. Los datos de prueba se crean por API **solo en local**.

**Casos puros** (`utils/retentionDefaults.ts`):

| # | Caso | Esperado |
|---|---|---|
| U1 | Guardada «2.5000» (string). Catálogo: general 2,5 y «No declarante» 3,5 | La general |
| U2 | Guardada «3.5000», mismo catálogo | «No declarante». **Es el defecto de hoy**: el código actual da la general |
| U3 | Guardada 3,5. Catálogo: solo la general 2,5 | Sin tarifa, con `staleRate: 3.5` (T2) |
| U4 | Dos tarifas al 2,5 (general y «Compras») | La general |
| U5 | Dos al 2,5, las dos con concepto | La primera del catálogo |
| U6 | ICA: guardada «Barranquilla» 0,7, catálogo con ICA Barranquilla 0,7 y Soledad 0,7 | Barranquilla (el municipio también decide) |
| U7 | `rate` nulo y una sola tarifa de ese tipo | Esa |
| U8 | `rate` nulo y dos | Sin tarifa (T2) |
| U9 | `defaultRetentionConfig`: general activa, `base_kind=subtotal` | La general |
| U10 | La general inactiva | Ninguna |
| U11 | Solo hay ReteFuente con concepto | Ninguna (con A) |
| U12 | La general con `base_kind='iva'` | Ninguna |

**e2e a 1440 y 390:**
- **E1, reliquidar.** Una Entrada liquidada con ReteFuente 3,5 «No declarante» se desliquida y se abre Liquidar. La fila precarga «No declarante (3,5 %)», con el mismo monto y sin «Sugerido». Al liquidar, `purchase_retentions.rate` = 3,5 (se lee por la API, no por el ORM).
- **E2, tarifa desactivada.** Se desactiva «No declarante» y se reabre Liquidar. La fila sigue ahí, sin tarifa, con la nota y con Liquidar bloqueado («falta elegir la tarifa»). Se elige la general, y Liquidar se habilita.
- **E3, default.** «+ Retención» en una compra nueva trae «Retención en la Fuente · por defecto (2,5 %)» y el monto precalculado. Se elige otra tarifa, y el monto se recalcula.
- **E4, sin default.** Con la general desactivada, «+ Retención» deja el selector vacío, como hoy.
- **Control positivo de E1:** con el código de `dea2320`, E1 guarda 2,5. Esa es la diagonal del plantado P1.

**Backend:** con A, cero cambios en `app/`. El único test de Python es el del seeder (T6). Con B: el endpoint (feliz, sin historia, compra revertida que no cuenta, 403 sin flag, 403 con alcance, y RBAC con control positivo).

## 6. Plantado

La matriz va commiteada antes de plantar y no se reescribe.

| P | Defecto | Debe caer |
|---|---|---|
| P1 | Volver a reconocer por (tipo, municipio): el código de hoy | U2, E1 |
| P2 | Comparar `rate` sin `num()` (string contra número) | U1, U2, U4 (≥) |
| P3 | Tarifa no encontrada → se descarta la fila (el código de hoy) | U3, U8, E2 |
| P4 | Empate de tasa sin preferir la general | U4 |
| P5 | Ignorar el municipio en el reconocimiento | U6 |
| P6 | El default no mira `is_active` | U10, E4 |
| P7 | El default no mira `base_kind` | U12 |
| P8 | El default acepta una tarifa con concepto | U11 |
| P9 | «+ Retención» con `touched: true` (el monto no se precalcula) | E3 |
| P10 | El seeder vuelve a ignorar las tarifas inactivas (el código de hoy) | el test de T6, caso inactiva |
| P11 | El seeder compara sin normalizar el concepto | el test de T6 con concepto en otra grafía (≥) |

## 7. Gates (nivel lógica, flujo del 17-nov)

- **Autor:** lint, tsc, build, ruff sobre `scripts/` y el test del seeder (T6), los casos puros, el e2e y las tres guardas (`test_reloj_de_negocio.py`, `test_advisory_locks.py`, `test_crucible_charges.py`), todo sobre un sha commiteado.
- **Plantado** contra la matriz de §6.
- **Golden: no aplica, medido** (sin cambios en `app/` con A).
- **Parity:** no aplica (cero migraciones con A).
- **Suite completa:** diferida al checkpoint.
- **Pantalla:** capturas a 1440 y 390 de la tarjeta de la compra (precarga, nota de T2, default) y de Tesorería → Retenciones con la marca de A.

## 8. Fuera de alcance

- `PurchaseLiquidatePage` (§2).
- Topes de base mínima (en UVT). El sistema no los aplica y el monto editable los absorbe.
- Defaults para ReteIVA e ICA. El pedido es de ReteFuente, y la ReteIVA sobre IVA sigue esperando Q-68.
- Cargar las tarifas en prod: lo hace Johana.
