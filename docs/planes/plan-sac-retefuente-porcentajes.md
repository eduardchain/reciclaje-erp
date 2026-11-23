# Plan: retenciones e IVA con porcentaje libre al liquidar una Entrada (v1.4)

- **v1.4** (condiciones de QA 1 sobre la v1.3 `4d72cff`; veredicto en `~/sac-evidencia/2026-11-23/qa-1-retefuente/veredicto_plan_v1.3.md`):
  - C1: P1 predice U1, U2, U5 y E1. U3 queda verde porque «No declarante» ya tiene 3,5; U5 cae porque Barranquilla tiene 0,7 y la guardada es 0,966.
  - C2: cada caso dice si lee el campo de la fila (`row.amount`) o el monto efectivo (`effAmount`).
  - O1: la nota de T2 es una sola, neutra, y sirve igual para la tarifa inactiva y para la de `base_kind='iva'`.
  - O2: el parseo de `MoneyInput` vive en una sola función, que usan el camino vivo y el blur.

- **v1.3** (decisiones de Daniel del 23-nov, vía el Coordinador). El plan cambia de fondo.
  - **D1.** «Hay varios factores que influyen, el tipo de compra, el régimen fiscal del proveedor, el producto, etc. Por eso lo ideal es que la casilla de retención sea libre, que uno simplemente escriba el porcentaje». Y después: «dejemos rete IVA e ICA también libres. O sea, todo lo que sea impuestos, dejémoslo libres».
  - **D3.** La retención por defecto solo se propone al apretar «+ Retención».
  - **Comportamiento** (Daniel): «todos los impuestos y retenciones deben quedar con el mismo comportamiento… la tarifa por defecto que definimos en impuestos y retenciones. Pero si ellos lo quieren editar manual, lo editen manual y que se muestre el monto de una vez». O sea:
    - el % viene de la tarifa del catálogo de Tesorería;
    - se edita a mano;
    - el monto se recalcula **en vivo, mientras se escribe** (T11).
  - **D2** quedó sin objeto, y el Coordinador lo registró en el inventario.
  - **Alcance:** Liquidar Entrada, con las tres retenciones y el IVA de compra. Ventas y Salidas de Plomo también van libres (Daniel lo confirmó), pero en un **plan aparte**, después de esta Entrada (§2).
  - **Lo que se mantiene de la v1.2** (GO de QA 1 en `949a1dc`): T2 y T2b, ahora solo por el TIPO; T3 (default en una función pura con un solo predicado); T6 (el seeder no recrea una tarifa desactivada); la marca en Tesorería → Retenciones.
  - **Lo que sale:** T1 (reconocer la tarifa por la tasa), porque la tasa ahora se restaura tal cual.
- **v1.2** `949a1dc`, **v1.1** `bd1ad80`, **v1.0** `2a97489`. Los veredictos de QA 1 están en `~/sac-evidencia/2026-11-23/qa-1-retefuente/`.
- **Autor:** Eco Coder 1. Rama `coder-1/retefuente-porcentajes` sobre develop `dea2320`.
- **Nivel propuesto: lógica.** La pantalla decide qué tasa y qué monto se guardan.
- **Evidencia:** `~/sac-evidencia/2026-11-23/coder-1-retefuente/` (barrido de consumidores) y `~/sac-evidencia/2026-11-23/retefuente-porcentajes/tarifas.log` (medición del Coordinador sobre prod, solo GET).

## 1. Qué cambia para Johana

En la tarjeta de cada compra, en Liquidar Entrada:

- **Retenciones (ReteFuente, ReteIVA, ICA).**
  - El selector elige solo el **tipo**: «Retención en la Fuente», «ReteIVA» o «ICA — Barranquilla».
  - Al lado aparece una casilla **«% del subtotal»**, precargada con la tasa de esa tarifa (2,5 en la general) y editable.
  - El monto se recalcula como % × subtotal y sigue siendo editable.
- **IVA.** «Con IVA» trae la casilla de % precargada en 19 y editable, con el monto recalculado y editable, igual que las retenciones. **El IVA de compra no tiene fila en el catálogo de Tesorería, así que su valor inicial sigue siendo la constante 19.** No se crea una configuración nueva para eso (indicación del Coordinador).
- **El monto cambia mientras se escribe el %**, no al salir de la casilla (T11).
- **Error de dedo** (25 en lugar de 2,5): aparece un aviso en ámbar junto al %, sin bloquear (T7). El monto está siempre a la vista al lado del %.

**El backend no cambia.**
- `PurchaseRetentionCreate.rate` y `DocumentTaxCreate.rate` ya son libres (`gt=0`, informativos), y el monto es la verdad (#79 F1, #112 D1).
- La entidad de una retención depende solo del tipo, y del municipio en ICA (#78).
- Lo que hoy se guarda en `rate` es la tasa del catálogo. Con este cambio se guarda la que se usó.

**Hoy en prod** (medido): el catálogo tiene una sola ReteFuente, 2,5 %, sin concepto; ReteIVA 2 % y 15 % sobre el IVA; ICA Barranquilla 0,7 %. Hay retenciones en 7 de 146 compras, todas ReteFuente 2,5 %. No escribimos en prod: las tarifas las carga Johana.

## 2. Defectos de hoy que el cambio arregla o vuelve a abrir

1. **La precarga al reliquidar** (`InboundLiquidatePage.tsx:611-617`) busca la tarifa por (tipo, municipio) y manda **su** `rate`, no el guardado. Con % libre se restaura el `rate` guardado y la tarifa solo aporta el tipo (T1').
2. **Una retención cuya tarifa ya no está activa desaparece EN SILENCIO**, por dos caminos: la precarga (`:618`) y el borrador (`:648-653`). Se arregla con T2 y T2b, ahora solo cuando no queda NINGUNA tarifa activa de ese tipo.
3. **El IVA es una constante** (`IVA_RATE_PCT = 19`, `:145`), usada en `:630` (precarga), `:1063` (cálculo), `:1237` (payload), `:1547` y `:1566` (pantalla). La precarga de `:630` marca como «editado» un IVA al 5 % porque lo compara contra 19 fijo. Esto lo arregla T8.

**Ventas y Salidas de Plomo (`DocumentTaxesCard`, #112) van en un plan aparte, con el mismo comportamiento.** Arranca cuando la construcción de esta Entrada tenga el OK de commit (decisión de Daniel, vía el Coordinador). Esta versión no las toca.

## 3. Barrido de consumidores

Los comandos y su salida están en `barrido_consumidores.log`.

| Archivo | Usos | ¿Lo toca el plan? |
|---|---|---|
| `pages/inbound/InboundLiquidatePage.tsx` | 10 | **Sí.** Retenciones (precarga `:611-617`, borrador `:648-653`, cálculo, payload `:1198-1225`, pantalla `:1590-1650`) e IVA (`:145`, `:630`, `:1063`, `:1237`, `:1547`, `:1566`) |
| `pages/treasury/RetentionsPage.tsx` | 13 | **Sí.** La marca «Se propone al liquidar» sale de la misma `defaultRetentionConfig` |
| `pages/purchases/PurchaseLiquidatePage.tsx` (compartida, 7 orgs) | 8 | **No, fuera de alcance.** SAC sí llega a ella: una compra de Entrada desliquidada vuelve a `registered`, y `canLiquidate` (`PurchaseDetailPage.tsx:70`, `PurchasesPage.tsx:67`) solo mira status, DP y permiso. Ese bug lo midió QA 1 y lo tiene el Coordinador. Esa página no tiene precarga |
| `components/shared/DocumentTaxesCard.tsx`, `pages/sales/SaleLiquidatePage.tsx`, `pages/willard/WillardDeliveryDetailPage.tsx` | 8 / 2 / 2 | **No en este plan.** Van en el plan aparte de §2 |
| `hooks/useMasterData.ts`, `services/thirdParties.ts`, `types/third-party.ts` | 3 / 7 / 1 | No (lectura del catálogo) |
| `InboundRetentionDetail` (schema `schemas/inbound_order.py:271`, construido en `endpoints/inbound_orders.py:196`) y `DocumentTaxResponse` | — | No. Ya devuelven `rate`, que es lo que la precarga restaura. El tipo TS `InboundRetentionDetail.rate: number` miente (llega string, trampa #93) y se corrige a `number \| string \| null` |

## 4. Decisiones técnicas (las propongo yo; las revisa QA)

**T1'. La precarga restaura el `rate` guardado; la tarifa solo da el TIPO.**
- Por cada retención guardada, `pickTypeConfig(type, municipality, catalog)` busca una tarifa usable del mismo tipo y municipio (normalizado). Prefiere la que no tiene concepto y, si no hay, toma la primera. La función decide la preferencia: no confía en el orden de la API.
- La fila queda con esa tarifa, `rate = num(saved.rate)`, el monto guardado y `touched: true`.
- Que el concepto sea uno u otro es inocuo: la entidad depende solo del tipo y del municipio (#78), y la tasa ya no sale del catálogo.
- **Si `rate` viene nulo** (hoy 0 filas en prod), se usa el `rate_pct` de la tarifa elegida.
- `num()` en la frontera: `rate` llega como string («3.5000»).

**T2. Si no queda ninguna tarifa usable de ese tipo, la fila NO desaparece.**
- Queda con `config_id: ""`, `staleRate` = la tasa guardada, el monto guardado y `touched: true`.
- Una nota debajo dice: «No hay una tarifa activa de Retención en la Fuente sobre el subtotal: créela o reactívela en Tesorería → Retenciones, o quite la retención». En ICA nombra el municipio. Es un solo texto para los dos casos (O1): la tarifa inactiva (U4, U6) y la tarifa activa pero calculada sobre el IVA (U8), donde «reactívela» no serviría.
- La validación que ya existe («falta elegir la tarifa de una retención») bloquea Liquidar. Es fail-closed.

**T2b. El borrador tampoco la borra.** `reviveDraftRetention(row, catalog)` reemplaza el filtro de `:648-653`:
- **Tarifa de la fila usable:** la fila queda igual.
- **Tarifa ya no usable, pero hay otra usable del mismo tipo y municipio:** la fila pasa a esa (`pickTypeConfig`) y conserva su `rate`, su monto y `touched`. Antes la tarifa daba la tasa; ahora solo da el tipo, así que cambiarla no le cambia nada a Johana.
- **No hay ninguna:** la fila se vuelve T2, con `staleRate` = su `rate`.
- **Fila sin tarifa elegida:** queda igual.
- **Borrador escrito ANTES de este cambio** (sin `rate`): toma el `rate_pct` de su tarifa. `assertDraftShape` acepta `rate` ausente o numérico.

**T3. Un solo predicado y funciones puras** (`utils/taxRows.ts`).
- `isUsableConfig(cfg)`: tiene `config_id`, está activa y su `base_kind` es `'subtotal'`. Es el único lugar donde viven esos chequeos.
- `pickTypeConfig`, `precargaRetention`, `reviveDraftRetention` y `defaultRetentionConfig` reciben `retentionRows` **sin filtrar**.
- `defaultRetentionConfig` da la ReteFuente usable sin concepto, o ninguna. Esa regla es determinista porque el servicio no deja dos generales activas (`find_active_config`, #79 D14).
  - La usan dos pantallas: «+ Retención» en Liquidar Entrada, y la marca «Se propone al liquidar» en Tesorería → Retenciones.
- **D3:** el default solo se propone al apretar «+ Retención». No se agrega solo a ninguna compra.
- El selector sigue listando `retentionConfigs` (filtrada en `:578`) y no ofrece las de `base_kind='iva'` (#112 e). La tarifa por defecto lleva «· por defecto».

**T4. «El último que se tocó gana»** (la regla para el % y el monto).
- **Elegir una tarifa:** `rate = cfg.rate_pct`, `touched = false`. El monto se recalcula.
- **Editar el %:** `rate = v`, `touched = false`. El monto se recalcula.
- **Editar el monto:** `amount = v`, `touched = true`. El monto queda fijo.
- **Cambia el subtotal:** si `touched` es falso, el monto se recalcula; si es verdadero, se conserva, y aparece «Sugerido: $X (r %)» para volver al cálculo (#10).
- Lo mismo vale para el IVA (`ivaRate` / `ivaAmount` / `ivaTouched`).
- **Se guarda el % digitado aunque el monto se haya editado.** El % es la tarifa que Johana aplicó; el monto puede venir redondeado (30.864,18 → 30.864) y sigue siendo la verdad (#79 F1).
- Son funciones puras (`withConfig`, `withRate`, `withAmount`, `effAmount`) para poder probarlas solas.
- Cuando `rate` y el monto no cuadran, no se avisa: es justo lo que pasa con un redondeo.

- **Pasar por la casilla del % sin cambiarlo no cuenta como tocarlo.** `withRate` devuelve la fila igual si el valor nuevo coincide con el actual a 4 decimales. Sin esto, un Tab por el % después de editar el monto pondría `touched` en falso, y el monto editado se perdería (es la familia de C5 de #122). Vale igual para `ivaRate`.

**T5. Rango.** El % tiene que ser mayor que 0 y como mucho 100. Si no, Liquidar se bloquea con «Compra N: el % de X debe estar entre 0 y 100». Con 0, el monto queda en $0 y la validación que ya existe lo bloquea igual. La casilla admite 4 decimales (`rate` es `Numeric(7,4)`; ICA va en por mil, por ejemplo 9,66 ‰ = 0,966 %).

**T6. El seeder no vuelve a crear una tarifa que Johana desactivó** (sin cambios desde la v1.2).
- Hoy `create_retention_configs` (`seed_sac_org.py:1270-1277`) solo tolera el 409, que aparece únicamente con una tarifa **activa**. Si Johana desactiva la general, la próxima provisión la crea de nuevo y el default resucita.
- Antes de cada POST, el seeder lee `GET /third-parties/retention-entities` (que trae también las inactivas). Si ya existe una tarifa con el mismo (tipo, municipio, concepto), normalizados y activa o no, la omite y avisa.
- **Test:** con un API falso que se porte como el backend. Casos: inactiva → no hay POST; activa → 409 tolerado; ausente → 201. **Control positivo:** con el código de `dea2320`, el caso «inactiva» sí hace el POST.

**T7. Defensa contra el error de dedo: un aviso, nunca un bloqueo.**
- `rateWarning(rate, ref)` avisa si el % digitado se aleja **más de 5 veces** de la referencia, por arriba o por abajo (`rate > 5·ref` o `rate < ref/5`). La referencia es la tasa de la tarifa elegida en las retenciones, o 19 en el IVA.
- El aviso, en ámbar junto a la casilla: «25 % es 10 veces la tarifa (2,5 %). Revise que no sea un error de dedo».
- **Por qué relativo y por qué 5:** el error típico es correr la coma, o sea un factor de 10. Con 5 se atrapan el 25 por 2,5, el 1,9 por 19, el 7 por 0,7 de ICA y el 15 por 2 de ReteIVA (el 15 % que va sobre el IVA digitado como si fuera sobre el subtotal). No salta con tasas legítimas: 3,5 por 2,5, 5 % de IVA por 19 (3,8 veces), 0,966 por 0,7 de ICA, u 11 por 2,5 (4,4 veces). Un umbral absoluto no sirve para las dos cosas a la vez: un 10 % atrapa el 25 pero no el 1,9 del IVA.
- El factor es una constante en `taxRows.ts`.
- **El monto queda siempre a la vista al lado del %**, en la misma fila: a 1440 y a 390 van % y monto lado a lado, el % angosto.

**T8. IVA libre.**
- `IVA_RATE_PCT = 19` queda solo como valor inicial y como referencia del aviso.
- La columna gana `ivaRate`: al marcar «Con IVA» vale 19, se edita igual que T4, y va en el payload como `rate` en lugar de la constante.
- **Precarga** (`:630`): `ivaRate = num(iva.rate)`, o 19 si viene nulo. `ivaTouched` compara el monto contra `round(base × ivaRate)/100`, no contra 19.
- **Borrador anterior al cambio** (sin `ivaRate`): toma 19.
- La etiqueta «Con IVA (19%)» pasa a «Con IVA».

**T9. Mobile 390.** El pie de cada compra conserva su forma. Lo nuevo:
- la fila «% | monto», en una grilla de 2 columnas, con el % en un ancho fijo chico;
- el aviso de T7 y la nota de T2, que se parten en varias líneas;
- «· por defecto» en el selector;
- la marca en Tesorería → Retenciones.
Se mide con capturas a 1440 y 390, sin scroll horizontal.

**T11. El monto se actualiza mientras se escribe el %** (pedido de Daniel).
- Hoy `MoneyInput` llama `onChange` solo en el blur (`MoneyInput.tsx:72-86`): mientras se escribe, cambia solo el texto mostrado.
- **Opción:** una prop opcional `liveChange?: boolean`, **apagada por defecto**. Con ella, `handleChange` también llama `onChange` con el valor parseado. El blur no cambia.
- **Un solo parseo** (O2): la normalización, el redondeo a `decimals` y el piso `min` que hoy están dentro de `handleBlur` (`:76-84`) se extraen a una función del módulo, `parseDisplay(display, decimals, min)`, que llaman el blur y el camino vivo. Con la prop apagada el blur da exactamente lo mismo: la extracción no cambia ni una operación.
- La usan solo las casillas de % de esta pantalla.
- `MoneyInput` es compartido: 74 usos en 39 archivos (`grep -rn "<MoneyInput"`), y ninguno pasa la prop nueva. Con la prop apagada, el código que corre es el de hoy: la rama nueva está detrás de un `if (liveChange)`. No se toca la selección al entrar con Tab (#126), que sigue haciendo falta para escribir encima del % precargado.
- **Descarté** un componente `PercentInput` aparte: tendría que copiar la lógica de selección de #126, y una copia de esa lógica es justo cómo volvería el defecto de «13.001.250».
- Mientras se escribe pueden pasar valores intermedios («3,» → 3). Cada uno recalcula el monto, que es lo que se pidió. Una casilla vacía da 0, el monto queda en $0, y la validación lo muestra.

**T10. Alcance de recolector (#129).** Con alcance no hay IVA ni retenciones (S5), así que nada de esto corre para Ingrid.

## 5. Decisiones de Daniel

- **D1** (decidida): % libre en todo impuesto de la Entrada (retenciones e IVA). La forma híbrida es la que se describe arriba.
- **D2:** sin objeto.
- **D3** (decidida): solo se propone al apretar «+ Retención».
- **Ventas y Salidas** (decidido): también van libres, en el plan aparte de §2.
- **No abre decisión nueva.** El factor 5 del aviso (T7) es técnico y lo revisa QA; si Daniel quiere otro, es una constante.
  - Para el Coordinador: Q-68 (ReteIVA sobre el IVA en compras) sigue abierta. Con % libre, la ReteIVA de compras va sobre el SUBTOTAL, como hoy. La casilla lo dice («% del subtotal») y T7 avisa si alguien digita 15.

## 6. Tests

El frontend no tiene infraestructura de tests. Como en #123, las funciones puras se prueban con casos por `node` y la pantalla con e2e de Playwright contra `:8011`/`:5181` y la base `reciclaje_coder_1`. Los datos se crean por API, **solo en local**. Las tasas guardadas van como string, igual que las manda la API. «general» es la ReteFuente 2,5 % sin concepto, activa, con `base_kind` subtotal, salvo que se diga otra cosa.

| # | Caso | Esperado |
|---|---|---|
| U1 | Precarga: guardada ReteFuente «3.5000», $35.000. Catálogo: [general] | general, `rate` 3,5 (número), `row.amount` 35.000, `touched` |
| U2 | La misma guardada. Catálogo: [«Compras» 2,5, general], con Compras primero | general, `rate` 3,5 |
| U3 | La misma. Catálogo: [general **inactiva**, «No declarante» 3,5 activa] | «No declarante», `rate` 3,5 |
| U4 | La misma. Catálogo: [general inactiva] | T2: `config_id ""`, `staleRate` 3,5, `row.amount` 35.000 y `touched` conservados |
| U5 | ICA Barranquilla «0.9660». Catálogo: [ICA Soledad 0,7, ICA Barranquilla 0,7] | Barranquilla, `rate` 0,966 |
| U6 | ICA Barranquilla. Catálogo: [ICA Soledad] | T2 |
| U7 | ReteFuente con `rate` nulo. Catálogo: [general] | general, `rate` 2,5 |
| U8 | ReteFuente «3.5000». Catálogo: [general con `base_kind='iva'`] | T2 |
| U9 | Default con [general] | general; `newRetRow` da `rate` 2,5 y `touched` falso |
| U10 | Default con [general inactiva, «No declarante» activa] | Ninguna |
| U11 | Default con [«Compras» 2,5 activa] | Ninguna |
| U12 | Default con [general `iva`] | Ninguna |
| U13 | Borrador {«No declarante», `rate` 3,5, `row.amount` 0, sin tocar}. Catálogo: [«No declarante» inactiva, general activa] | Fila con general, `rate` 3,5, `row.amount` 0, `touched` falso |
| U14 | Borrador {«No declarante», `rate` 3,5}. Catálogo: [«No declarante» inactiva] | T2 con `staleRate` 3,5 |
| U15 | Borrador con general activa | Igual |
| U16 | Borrador anterior al cambio (sin `rate`), general activa | `rate` 2,5 |
| U17 | Secuencia T4, se lee `effAmount`; base 1.000: `newRetRow`(general) → 25; `withRate` 3,5 → 35; `withAmount` 30 → 30; `withRate` 4 → 40; base 2.000 → 80; `withAmount` 70 → 70; base 3.000 → 70 | Esos montos, en ese orden |
| U18 | Fila con monto editado (`row.amount` 30, `touched`) → `withConfig`(«No declarante» 3,5) | `rate` 3,5, `touched` falso y `effAmount` 35 a base 1.000 |
| U19 | `rateWarning`: (25; 2,5) sí · (3,5; 2,5) no · (12,5; 2,5) no · (12,51; 2,5) sí · (0,5; 2,5) no · (0,49; 2,5) sí · (5; 19) no · (1,9; 19) sí · (15; 2) sí | Esos |
| U20 | Payload de retención: `rate` 3,5, monto editado 30.000, base 1.000.000, general | `{retention_type: "retefuente", config_id: general, rate: 3.5, base: 1000000, amount: 30000}` |
| U21 | Precarga del IVA: {rate «5.0000», base 1.000.000, monto 50.000} | `ivaRate` 5, `ivaAmount` 50.000, `ivaTouched` falso |
| U22 | Precarga del IVA: {rate «19.0000», base 1.000.000, monto 189.000} | `ivaRate` 19, `ivaTouched` verdadero |
| U23 | Precarga del IVA con `rate` nulo, base 1.000.000, monto 190.000 | `ivaRate` 19, `ivaTouched` falso |
| U24 | Payload del IVA con `ivaRate` 5 | `rate: 5` |
| U25 | Borrador anterior al cambio, columna sin `ivaRate` | `ivaRate` 19 |
| U26 | `rateOutOfRange`: 0 sí · −1 sí · 0,0001 no · 100 no · 100,01 sí | Esos |
| U27 | Fila con `rate` 3,5 y monto editado (`row.amount` 30, `touched`) → `withRate`(3,5), el mismo valor | Lee los CAMPOS de la fila, no `effAmount`: `touched` verdadero y `row.amount` 30. Así P16 (que solo cambia `effAmount`) no la toca |

**e2e a 1440 y 390:**
- **E1, reliquidar con % libre.** Se liquida una Entrada con ReteFuente al 3,5 digitado y se desliquida. Al abrir Liquidar, la fila trae «Retención en la Fuente», 3,5 y el mismo monto, sin «Sugerido». Al reliquidar, `rate` = 3,5 (leído por la API, no por el ORM).
- **E2, la única ReteFuente desactivada.** La fila sigue, sin tarifa, con la nota, y Liquidar queda bloqueado. Se quita la retención y Liquidar se habilita.
- **E3, default y «el último gana».**
  - «+ Retención» trae «Retención en la Fuente · por defecto», 2,5 y el monto precalculado.
  - Se digita 3,5 y el monto se recalcula **antes de salir de la casilla** (T11): se lee el monto con el foco todavía en el %.
  - Se edita el monto y se conserva.
  - Se pasa con Tab por la casilla del % sin cambiarla, y el monto editado se conserva.
  - Se digita 4 y el monto se recalcula.
  - Se digita 25: aparece el aviso ámbar y Liquidar sigue habilitado.
- **E4, sin default.** Con la general desactivada y «No declarante» activa, «+ Retención» deja el selector vacío.
- **E5, borrador.** Se agrega una retención «No declarante» con 3,5 y se sale. Se desactiva «No declarante», con la general activa, y se vuelve a abrir. La fila trae la general con 3,5.
- **E6, la marca en Tesorería → Retenciones.** La general la muestra y ninguna otra. Con la general desactivada y «No declarante» activa, ninguna la muestra.
- **E7, IVA libre.** «Con IVA» trae 19. Se digita 5, el monto queda en el 5 % antes de salir de la casilla, y se liquida: `taxes[].rate` = 5. Se desliquida y se reabre: trae 5, sin «Sugerido».
- **E8, ICA libre.** ICA Barranquilla trae 0,7. Se digita 0,966 y el monto se recalcula. Al liquidar, `rate` = 0,966.
- **Capturas a 1440 y 390** del pie de una compra con dos retenciones, el IVA, el aviso y la nota, y de Tesorería → Retenciones.

**Backend:** sin cambios en `app/`. El único test de Python es el del seeder (T6).

## 7. Plantado

La matriz va commiteada antes de plantar y no se reescribe.
- **«Exacta»:** caen esos casos y ningún otro.
- **«≥»:** caen al menos esos, porque el defecto vive en una vía que comparten otros casos.
- Los chequeos de `is_active` y de `base_kind` se plantan una sola vez, en `isUsableConfig`.

| P | Defecto | Debe caer | Tipo |
|---|---|---|---|
| P1 | La precarga toma `cfg.rate_pct` en lugar de la tasa guardada (el código de hoy) | U1, U2, U5, E1 (U3 queda verde: «No declarante» ya tiene 3,5) | exacta |
| P2 | La precarga deja `rate` como string (sin `num()`) | U1, U2, U3, U5 | ≥ |
| P3 | Sin tarifa usable, la fila se descarta (el código de hoy) | U4, U6, U8, E2 | exacta |
| P4 | `pickTypeConfig` sin preferir la general (toma la primera) | U2 | exacta |
| P5 | `pickTypeConfig` ignora el municipio | U5, U6 | exacta |
| P6 | `isUsableConfig` no mira `is_active` | U3, U4, U10, U13, U14, E2, E4, E5, E6 | exacta |
| P7 | `isUsableConfig` no mira `base_kind` | U8, U12 | exacta |
| P8 | El default acepta una tarifa con concepto (se plantea conservando la preferencia por la general, nota de QA 1) | U10, U11, E4, E6 | exacta |
| P9 | `newRetRow` con `touched: true` | U9, E3 | exacta |
| P10 | El seeder vuelve a ignorar las tarifas inactivas (el código de hoy) | caso «inactiva» del test de T6 | exacta |
| P11 | El seeder compara sin normalizar | caso «otra grafía» del test de T6 | exacta |
| P12 | El borrador vuelve al filtro de hoy: la fila queda igual si su tarifa es usable y desaparece si no | U13, U14, U16, E5 | exacta |
| P13 | Tesorería → Retenciones marca con su propio predicado (ReteFuente sin concepto, sin mirar `is_active`) | E6 | exacta |
| P14 | `withRate` no resetea `touched` | U17, E3 | exacta |
| P15 | `withConfig` no resetea `touched` | U18 | exacta |
| P16 | `effAmount` ignora `touched` (siempre recalcula) | U17, E3 | exacta |
| P17 | `rateWarning` nunca avisa | U19, E3 | exacta |
| P18 | `rateWarning` con umbral absoluto (`rate > 10`) | U19 | exacta |
| P19 | El payload de retención manda `cfg.rate_pct` | U20, E1, E8 | exacta |
| P20 | El payload del IVA manda 19 fijo (el código de hoy) | U24, E7 | exacta |
| P21 | La precarga del IVA compara contra 19 fijo (`:630` de hoy) | U21, E7 | exacta |
| P22 | La precarga del IVA ignora la tasa guardada (`ivaRate` = 19) | U21, E7 | exacta |
| P23 | El borrador sin `ivaRate` queda indefinido | U25 | exacta |
| P24 | `rateOutOfRange` acepta 0 | U26 | exacta |
| P25 | `MoneyInput` ignora `liveChange` (llama `onChange` solo en el blur) | E3, E7 | exacta |
| P26 | `withRate` resetea `touched` aunque el valor sea el mismo | U27, E3 | exacta |

## 8. Gates (nivel lógica, flujo del 17-nov)

- **Autor**, todo sobre un sha commiteado:
  - lint, tsc y build;
  - ruff sobre `scripts/` y el test del seeder (T6);
  - los casos puros y el e2e;
  - las tres guardas (`test_reloj_de_negocio.py`, `test_advisory_locks.py`, `test_crucible_charges.py`).
- **Plantado** contra la matriz de §7.
- **Golden:** no aplica, medido (sin cambios en `app/`).
- **Parity:** no aplica (cero migraciones).
- **Suite completa:** diferida al checkpoint.
- **Pantalla:** capturas a 1440 y 390 (T9).
- **`MoneyInput` compartido** (T11 y O2): el e2e de #126 (`~/sac-evidencia/2026-11-20/coder-1-moneyinput-seleccion/e2e_moneyinput.mjs`, commit `a5bea01`), corrido contra la rama, tiene que dar lo mismo que en develop. Es la medida de que la prop apagada no cambió nada.

## 9. Fuera de alcance

- Ventas y Salidas de Plomo (`DocumentTaxesCard`): plan aparte (§2).
- `PurchaseLiquidatePage` (§3).
- ReteIVA sobre el IVA en compras (Q-68): sigue sobre el subtotal.
- Topes de base mínima (en UVT). El monto editable los absorbe.
- Cargar tarifas en prod: lo hace Johana.
