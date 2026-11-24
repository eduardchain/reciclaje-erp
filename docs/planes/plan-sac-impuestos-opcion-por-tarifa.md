# Plan: Ventas y Salidas, una opción por tarifa cuando un tipo tiene varias (v1.1)

- **Autor:** Eco Coder 1. **Fecha:** 23-nov-2026.
- **Autorización:** Daniel, ventanita de las 20:19, vía el Coordinador: «Mostrar las dos (Recomendado)». Bug de #136, en develop y todavía no en producción; el deploy 5 lo espera.
- **Nivel:** lógica. Cambia qué tarifa se puede elegir y, con ella, la base, el % y el concepto que viajan en el payload.
- **Base:** develop `abb414c`; rama nueva `coder-1/impuestos-opcion-por-tarifa`.
- **Alcance:** solo frontend, en `frontend/src/utils/documentTaxRows.ts` y `frontend/src/components/shared/DocumentTaxesCard.tsx`. Backend sin cambios.
- Escrito fuera del worktree; se commitea en `docs/planes/` antes de construir.
- **v1.0 → v1.1** (GO de QA 1 a v1.0, `f537bd86…`; pedido del Coordinador sobre el recorrido de Coder 2, `informe_recorrido_deploy5.md` 90ece8ca §1):
  - suma **R6**, el rótulo de la base en CADA fila a 1440, con su e2e **E15**;
  - suma a la matriz la fila que pidió QA 1: `orphanTaxText` buscando solo entre las usables (V6);
  - suma V9: una huérfana cuya tarifa ya no está en el catálogo lo dice sin nombrar una tarifa inventada. Es el texto de R4 con «esa tarifa» reescrito, porque «No hay una tarifa activa de esa tarifa» se leía mal.

## 1. El defecto, medido

- **Producción SAC** (solo GET, `reteiva-ventas-prod/tarifas_prod.log`) tiene dos ReteIVA activas:
  - la general, sin concepto, al 2 % sobre el subtotal (`e2971e4d`);
  - «Ventas», al 15 % sobre el IVA (`0e3100f9`), la de la FE 2127.
- **El código** (`documentTaxRows.ts:63-80`): `taxTypeOptions` agrupa por (tipo, municipio) y se queda con `cands.find(c => !c.concept) ?? cands[0]`. Con dos tarifas del mismo tipo solo se ofrece la general. Por eso la de 15 % sobre el IVA no se puede elegir en Ventas ni en Salidas de Plomo.
- **Regresión:** la tarjeta de `main` (`f67ff16`, `DocumentTaxesCard` l.242-256) lista cada tarifa por su `config_id`, con su concepto y «sobre IVA». Es lo que Johana usa hoy.
- **Dev lo reproduce:** en `reciclaje_coder_1`, SAC tiene ReteIVA general al 2 % sobre el subtotal y «Sobre IVA E2E» al 15 % sobre el IVA.
- 🔴 **Por qué #136 no lo vio:**
  - su E3 **desactivaba la ReteIVA general** para poder elegir la de 15 % (`coder-1-ventas-libres/e2e/e2e_ventas.mjs:144`);
  - su E4 afirmaba **una sola** opción «ReteFuente» con «No declarante» activa;
  - U2 y U11 afirman el colapso.

  La prueba rodeó el caso de producción en vez de medirlo. El colapso venía de la regla O4 del plan de #136, y nadie lo contrastó contra la tarjeta de `main`.

## 2. La regla

- **R1. Opciones.**
  - IVA, siempre.
  - Las tarifas usables (`isUsableTaxConfig`, sin cambios) se agrupan por (tipo, municipio normalizado en ICA), la misma clave del servidor:
    - grupo con **una** tarifa → una opción, con el mismo rótulo que hoy (tipo, municipio en ICA, «(sobre el IVA)»);
    - grupo con **más de una** → una opción por tarifa. El rótulo es tipo [· municipio] [· concepto] [(sobre el IVA)].
  - En producción: «ReteIVA» y «ReteIVA · Ventas (sobre el IVA)».
  - Dentro de un grupo va primero la general (sin concepto) y después las demás, en el orden del catálogo. El orden entre grupos no cambia.
- **R2. La clave de la opción (`source` de la fila) pasa a ser la tarifa: `config_id`**, como en `main`, en toda retención, aunque su grupo tenga una sola. El IVA sigue con `"iva"`. Tiene que ser uniforme, por dos razones:
  - si la clave dependiera de cuántas tarifas tiene el grupo, crear una segunda tarifa en otra pestaña cambiaría la clave de una fila ya elegida;
  - con la clave por tipo de hoy, desactivar la tarifa elegida pasa la fila **en silencio** a otra del mismo tipo, que puede ir sobre otra base. Con la clave por tarifa, la fila queda huérfana y bloquea (C1 de #136).

  En pantalla, con una sola tarifa, no cambia nada.
- **R3. Los duplicados siguen por (tipo, municipio)**, la clave del servidor (`document_tax.py:99-111`, 422 «viene dos veces»).
  - Nuevo `serverKeyOf(row, configs)`:
    - IVA → `"iva"`;
    - fila con tarifa → `taxKey(tipo, municipio)` de esa tarifa;
    - fila huérfana → su `source`, que ya bloquea por sí sola.
  - Lo usan `taxRowsProblems` y el `disabled` del Select. El `used` de la tarjeta pasa a ser el conjunto de claves de servidor de las OTRAS filas.
  - Así, elegir «ReteIVA» en una fila deshabilita también «ReteIVA · Ventas» en la otra.
- **R4. El texto de la huérfana nombra la tarifa.**
  - `orphanTaxText` busca el `config_id` en el catálogo completo, que trae también las inactivas (`list_retention_rows` no filtra `is_active`, `retention_entities.py:146-150`), y arma el rótulo con tipo · municipio · concepto.
  - Si no está, dice «esa tarifa».
  - Cambia la firma: recibe `configs`. Sus únicos lectores están en este módulo.
- **R6. El rótulo de la base es correcto en CADA fila a 1440** (pedido del Coordinador, sobre el recorrido de Coder 2).
  - Hoy, en escritorio, `lineLabelClass(idx)` oculta (`md:hidden`) los rótulos de las filas 2 en adelante: el de la primera fila hace de encabezado de columna.
  - Por eso una ReteIVA sobre el IVA en la fila 2 o 3 queda bajo el encabezado «% del subtotal» de la fila 1. Antes no se veía porque esa tarifa no se podía elegir.
  - Arreglo: en las filas 2 en adelante, debajo de la casilla del %, una pista con la base de ESA fila («% del IVA» o «% del subtotal»), solo en escritorio (`hidden md:block`). En móvil cada fila ya muestra su rótulo.
  - Debajo y no en el rótulo: un rótulo visible en las filas 2+ correría hacia abajo solo esa casilla, que no quedaría alineada con las demás. Debajo del input ya es el lugar de la pista del monto.
  - La fila 1 no cambia: su rótulo es el encabezado.
- **R5. El resto de #136 no cambia:**
  - `selectTaxType` trae el % de la tarifa ELEGIDA;
  - la base sale del `base_kind` de esa tarifa: «% del IVA», y como base el IVA efectivo de la fila (A2);
  - `buildTaxPayload` manda el concepto y el `base_kind` de la tarifa elegida;
  - A1 (la fila nueva arranca vacía), R8 y la regla de duplicados del servidor quedan igual.

## 3. Lectores, por grep (`lectores_grep.log`)

| Lector | Qué hace con la opción |
|---|---|
| `DocumentTaxesCard.tsx:71` | `taxTypeOptions`: las opciones del Select (key y rótulo) |
| `DocumentTaxesCard.tsx:72` y `:135` | `used` y `disabled`: pasan a la clave de servidor (R3) |
| `DocumentTaxesCard.tsx:102` | `optionFor`: el rótulo «% del IVA» |
| `DocumentTaxesCard.tsx:126` | `isOrphanTaxRow`: el borde rojo |
| `documentTaxRows.ts:83-91` | `optionFor` y `selectTaxType`: el % de la tarifa elegida |
| `documentTaxRows.ts:125-131` | `basedOnIva` y `taxRowBase` |
| `documentTaxRows.ts:154` | `taxRateReference`: el aviso ×5 |
| `documentTaxRows.ts:170` | `buildTaxPayload`: tipo, municipio, concepto y `base_kind` |
| `documentTaxRows.ts:194` | `taxNetDelta`: el signo por tipo |
| `documentTaxRows.ts:203-213` y `:233` | huérfana y su texto (R4) |
| `documentTaxRows.ts:230-231` | duplicados (R3) |

Las dos páginas que usan la tarjeta (`SaleLiquidatePage`, `WillardDeliveryDetailPage`) solo pasan `rows` y `configs` y llaman a `buildTaxPayload`, `taxRowsValid` y `taxNetDelta`. No leen `source` y no cambian.

## 4. Pruebas

### U nuevos (arnés de #136)

- **V1, caso de producción.** Con las 4 tarifas de prod salen 5 opciones: IVA, ReteFuente, ReteIVA, «ReteIVA · Ventas (sobre el IVA)» e ICA · Barranquilla. Las claves son los `config_id`.
- **V2.** Con una tarifa por tipo, los rótulos son los de hoy, también para una tarifa con concepto que está sola en su grupo.
- **V3.** Elegir «Ventas»:
  - trae el % 15 y la base es el IVA efectivo de la fila de IVA;
  - el payload lleva `{tax_type: reteiva, concept: "Ventas", base_kind: "iva", rate: 15}`.
- **V4.** Las filas ReteIVA general + ReteIVA Ventas dan «impuesto repetido».
- **V5.** Con «ReteIVA» elegido en otra fila, las dos opciones de ReteIVA quedan con la misma clave de servidor (`used`). Lo que se prueba es la función que alimenta el `disabled`.
- **V6.** La tarifa elegida se desactiva:
  - la fila queda huérfana, bloquea y el texto nombra «ReteIVA · Ventas»;
  - no pasa a la general.
- **V7.** Dos tarifas de ICA en el mismo municipio dan dos opciones. Municipios distintos siguen siendo grupos aparte.
- **V8.** Dentro del grupo, la general va primero aunque venga después en el catálogo.
- **V9.** Una huérfana cuya tarifa ya no está en el catálogo da «La tarifa de esta fila ya no está en el catálogo…» y bloquea.

### U de #136 re-semantizados (declarados)

- Las filas armadas con `source: "retefuente"`, `"reteiva"` o `"ica:bogota"` pasan a usar el `config_id` de su tarifa, con un helper del arnés. Es mecánico: la regla que prueban no cambia.
- **U1** (claves `["iva","retefuente","reteiva","ica:bogota"]`) pasa a afirmar los `config_id`.
- **U2** (la general le gana a la del concepto; sin general, la primera) y **U11** (dos ReteFuente colapsan en una) **afirman el colapso**, que es justo lo que cambia: se reescriben con R1 (V1/V8).

### e2e (Playwright, en el e2e de #136)

- **E13, a 1440 y 390.** Venta, con las dos ReteIVA activas como en producción: el e2e ya no desactiva la general.
  - Se agrega el IVA y se edita a 100.000.
  - El Select muestra «ReteIVA» y «ReteIVA · Sobre IVA E2E (sobre el IVA)».
  - Se elige la de 15 %. El rótulo es «% del IVA», el monto 15.000 y el neto +85.000.
  - Se liquida, y la API devuelve la reteIVA con concepto «Sobre IVA E2E», `base_kind` iva, `base_amount` 100.000 y `amount` 15.000.
- **E14, a 1440.** Lo mismo en una Salida tipo venta: la tarjeta es la misma, pero la página es otra.
- **E15 (R6), a 1440 y 390.** Venta con tres filas: IVA, ReteFuente y la ReteIVA sobre el IVA en la fila 3.
  - En cada fila, el texto VISIBLE de la columna del % dice su base: «% del subtotal» en las filas 1 y 2 y «% del IVA» en la 3. En ninguna aparece la otra base.
  - Después se mueve la ReteIVA a la fila 2, borrando la ReteFuente, y se mide de nuevo.
  - Se usa la tarifa de mi BD de dev («Sobre IVA E2E», 15 %, iva). La espejo de Coder 2 («Ventas (PRUEBA deploy5)», b114d899) está en otra base.
- **#136 re-semantizado:**
  - E3 deja de desactivar la general y elige por el rótulo nuevo;
  - E4, con «No declarante» activa, ahora espera DOS opciones de ReteFuente. Las dos quedan deshabilitadas en la segunda fila después de elegir una (R3).
  - El resto, E1-E8, se corre igual.

### Plantado (matriz commiteada antes de plantar; en las vías compartidas, «≥»)

| Defecto plantado | Tiene que tumbar |
|---|---|
| volver a colapsar a la general (el código de hoy) | V1, V3, E13 |
| clave por tipo cuando el grupo tiene varias | ≥ V1, V6 |
| duplicados por `source` en vez de por clave de servidor | V4 |
| `used`/`disabled` por `source` | V5, E4 |
| rótulo sin el concepto | V1, E13 |
| huérfana que cae a otra tarifa del tipo | V6 |
| general no primero en su grupo | V8 |
| `selectTaxType` con el % de la general del grupo | V3, E13 |
| payload con el concepto de la general | V3, E13 |
| ICA agrupada sin el municipio | V7 |
| `orphanTaxText` buscando solo entre las tarifas usables (QA 1) | V6 |
| sin la pista de base en las filas 2+ (R6) | E15 |
| la pista de base de las filas 2+ con la base de la fila 1 (R6) | E15 |

### Otras verificaciones

- **Dirigidas:** grep del contrato en backend (tests de `document_tax`, `retention-configs`, impuestos de ventas y de Salidas) y las 3 guardas, en `reciclaje_test_coder_1`, dentro de tests.lock, con la predicción escrita antes. No se corre la suite completa (5433 la ocupa el checkpoint).
- **Golden:** no aplica; se mide con `git diff --stat abb414c -- backend` vacío.

## 5. Fuera de alcance (hallazgo, no se arranca)

- **Liquidar Entrada** (`taxRows.ts:105-114`, `pickTypeConfig`) también elige UNA tarifa por tipo. Es la decisión de #135 («el selector elige el TIPO»).
- Allí no se ofrecen tarifas sobre el IVA (`isUsableConfig`), así que lo que se pierde es el concepto de la tarifa, no la base.
- Si se quiere el mismo criterio, va como pedido aparte, con OK de Daniel.
