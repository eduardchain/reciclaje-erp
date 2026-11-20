# Informe de código — PDF de SAC: encabezado «SAC» y «Entrada #remisión»

**Plan:** `docs/planes/plan-sac-entrada-editar-sede.md` §7 (addendum PDF, D3–D5, A1–A4) · **Base:** 85b0d07 (commit de la sede, A1) · **Nivel:** lógica
**Fecha:** 2026-11-19 · **QA:** «QA Ecobalance»

Johana: «cambiar ese encabezado que solamente diga SAC y que donde dice compra número tal no diga sino entrada número tal y que el número sea el que yo coloco en remisión».

Decisiones de Daniel, por la ventanita:
- **D3.** Todos los PDF, solo en SAC (`kg_ledger_enabled`).
- **D4.** Si no hay remisión, el título dice «Entrada (sin remisión)».
- **D5.** Primero el PDF no llevaba el número de compra. Daniel lo revirtió el mismo día, después de ver el PDF: «una remisión puede tener varias compras». Ahora lleva «Compra #N» debajo del título.

## 1. Qué cambia

| Pieza | Archivo |
|---|---|
| `_inbound_origin_map` suma `InboundOrder.remission_number` en la MISMA consulta (5.º elemento de la tupla); `_enrich_purchase_response` lo pone en `inbound_remission_number` dentro de `if inbound_map is not None` | `app/api/v1/endpoints/purchases.py` |
| `PurchaseResponse.inbound_remission_number: Optional[str] = None` | `app/schemas/purchase.py`, `types/purchase.ts` |
| `pdfTitle(orgName, isSac)` (pura) y `purchaseDocTitle` (privada). Las 6 funciones reciben el título armado. El título largo se ajusta al ancho libre | `utils/pdfExport.ts` |
| `usePdfTitle()`: authStore + `flagEnabled("kg_ledger_enabled")` | `hooks/usePdfTitle.ts` (nuevo) |
| Los 10 llamadores de 9 páginas pasan `usePdfTitle()` | compras, ventas, DP, tesorería ×2, balances ×2 |
| 3 tests | `tests/test_sac_pdf_remision_compra.py` (nuevo) |

**Sin migración y sin permisos nuevos.** El endpoint de compras es compartido: solo lo arman list y detail, que son los que pasan el mapa. Los otros 8 llamadores del enrich no lo pasan y el campo cae al default None.

En Costa y Meta el mapa no encuentra Entradas, así que la clave nueva viaja en null. Sin el flag, el título es el de siempre. Mientras cargan los settings, `flagEnabled` da false y sale el título de hoy, que es la dirección segura.

**Título:**
- Compra sin Entrada: «Compra #N», archivo `compra_N.pdf`.
- Con Entrada: la remisión con trim. Si queda vacía: «Entrada (sin remisión)», archivo `entrada_sin_remision_compra_<N>.pdf`. Si no: «Entrada #rem», archivo `entrada_<rem saneada a [A-Za-z0-9_], 30 car.>_compra_<N>.pdf`.
- **Debajo del título** va «Compra #N», en gris 110 a 10 pt, a 5,5 mm de la base de la ÚLTIMA línea del título. El color se restaura a negro antes de cualquier otro texto. La compra directa no entra en esa rama.

**Título largo** (hallazgo de A3; la edición tuvo el GO de QA antes de hacerla). La remisión es texto libre de hasta 50 caracteres. Con 50, el título a 14 pt bold tapaba la etiqueta de estado, que va alineada a la derecha. Ahora:
- el ancho libre se mide con cada texto en su fuente: el estado a 10 pt normal, el título en bold al tamaño que se prueba;
- el título se achica de a 0,5 pt hasta 9;
- si aun así no entra, se parte con `splitTextToSize` y la `y` corre por las líneas extra;
- si entra a 14 pt, se pinta con la misma llamada de antes.

**Nombre largo en la fila de «Fecha:»** (Daniel lo vio en pantalla y pidió arreglarlo en este deploy, por la ventanita; QA dio el OK antes de editar). Era preexistente: «ABRAHAM CABARCAS (GREENLOOP)» se montaba sobre «Fecha:».

`textInColumn(doc, value, x, y, maxWidth)` mide con la fuente puesta (10 pt normal, la misma con que se pinta). Si entra, hace la misma llamada de siempre; si no, parte el nombre en líneas dentro de la columna (57 mm, de x=55 a `pageWidth/2 + 10 − 3`) y la fila siguiente baja. Aplica a las tres filas que comparten con «Fecha:»: proveedor de compra, cliente de venta y proveedor de DP.

**No va detrás del flag, y cambia PDF de Costa y Meta**, solo cuando el nombre no cabe. En el replica de dev, medido con el mismo `getTextWidth` en node (`b_conteo_terceros.log`), no caben 14 de 484 terceros activos de Costa y 2 de 117 de Meta. Es una cota superior: cuenta todos los terceros activos, no solo los que figuran como proveedor o cliente.

## 2. Gates

Logs en `~/sac-evidencia/2026-11-19/pdf/`.

- **Estáticos:** ruff limpio, tsc 0, eslint 37 = techo.
- **Plantado** (`plantado_run.log`; predicciones escritas antes, a las 19:40:55): **2 de 2 en la diagonal**, con el sha del endpoint igual antes y después.
  - P1, sin seleccionar la columna: caen T1 y T2 por `ValueError` del desempaque. T3 no cae porque no tiene origen.
  - P2, `origin[3]` en lugar de `origin[4]`: cae solo T1. T2 pasa por coincidencia (None == None), y por eso T1 lleva una remisión real.
- **A2** (`a3_run.log`, contra el `pdfExport.ts` final): 4/4.
- **A3:** `exportPurchasePDF` real, empaquetado con esbuild y ejecutado en node, con `save` interceptado en el evento `initialized` de jsPDF. Leído con pypdf (`a3_run.log`, `a3_pypdf.log`):
  - «  » y null dan `entrada_sin_remision.pdf` / «Entrada (sin remisión)», con la tilde legible;
  - « 16254 » da «Entrada #16254»;
  - «R-12/3» da `entrada_R_12_3.pdf`;
  - una de 50 da un nombre de 30 caracteres y el título completo;
  - 50 «W» se parte en dos líneas y «Liquidada» queda aparte;
  - los dos rasterizados están en `r_*.png`.
- **Comparación de content streams** (`a3_comparacion.log`, pypdf `get_contents().get_data()`; los bytes crudos no sirven porque CreationDate e ID cambian en cada corrida):
  - SAC, antes de la edición contra ahora: IGUAL en «Compra #77», «#16254», «R-12/3» y «sin remisión»; DISTINTO en las dos de 50, que son el control positivo.
  - Sin flag, contra el código de 85b0d07: la compra directa sale IGUAL.
- **A4, navegador real** (`a4_navegador/`, `a4_pypdf.log`): front :5174 contra :8001. El :8001 se reinició con el código nuevo (pid 62773, a las 19:46:47, después del último cambio de `app/`), y el PID que escucha es el lanzado.
  - SAC: detalle y listado en los tres casos, más el Balance General con «SAC».
  - Costa: detalle y listado con «EcoBalance ERP - Reciclajes de la Costa» / «Compra #3173», más una venta. El usuario de prueba no tiene permiso de balance.
- **Nombre largo** (`b_comparacion.log`, content streams contra `pdfExport.ts` e61bfff1):
  - el nombre corto sale IGUAL en compra, venta y DP;
  - «ABRAHAM CABARCAS (GREENLOOP)» y un nombre de 3 líneas salen DISTINTO en las tres, que es el control positivo;
  - pypdf lee el nombre en líneas separadas de «Fecha:», y Placa, Bodega o Cliente salen en su fila;
  - rasterizados en `b_*.png`;
  - los casos de A3 contra e61bfff1 salen IGUAL (`a3_comparacion_r2.log`), y A2/A3 dan 11/11 (`a3_run_r2.log`).
  - Navegador r2 (`a4_navegador_r2/`, `a4_pypdf_r2.log`): SAC con «(GREENLOOP)» en su propia línea; Costa con compra y venta iguales.
  - Dos intentos de bajar el PDF justo después del login no dispararon descarga: no hubo error, y la función llamada desde la página sí descargaba. Con navegación limpia bajó, y tres recargas con clic dieron 3/3. No se reprodujo. En el navegador de Daniel bajó al primer clic después del login: «si, con un clic».
- **Dirigidas:** ver §4.
- **Suite completa:** ver §4.
- **Golden: no aplica, medido.** `grep -c purchases backend/scripts/golden_capture.py` = 0. La clave nueva viaja en null en list y detail de Costa y Meta.

**Compra #N debajo del título** (`c_comparacion.log`, content streams contra `pdfExport.ts` 7d553f90):
- La compra directa sale IGUAL, en SAC y sin flag.
- Venta, DP y compra con nombres corto y largos salen IGUAL; no se tocaron.
- Las compras de Entrada salen DISTINTO, que es el control positivo.
- pypdf lee «Compra #77» como línea propia debajo del título, también con el título de 50 W en dos líneas.
- Rasterizados `c_*.png`: el gris queda solo en esa línea.
- A2/A3 con los nombres nuevos: 11/11 (`a3_run_r3.log`).
- Para la pantalla se creó en dev la Entrada #25, remisión 16300, repartida en las compras #5 y #6 (`c_entrada_2_proveedores.log`).

**Pantalla de Daniel en localhost (19-nov):**
- Sede como selector en Editar: «Correcto».
- PDF de SAC, compra #2: «lo veo bien» (antes de revertir D5; el PDF con «Compra #N» se vuelve a mirar).
- PDF de Costa, compra #3173: «lo veo bien».
- El PDF de SAC bajó al primer clic después del login.
- Con «Compra #N» debajo del título (D5 revertida): Entrada #25 (remisión 16300), compras #5 y #6: «lo veo bien, ya las revise».

## 3. Observaciones (sin acción)

- **`services/purchase.py:1801`** tiene su propia consulta de origen. Arma la descripción de la comisión del recolector de una compra DIRECTA y lee la columna vieja `InboundOrder.purchase_id`, que desde #93 nadie escribe. Es preexistente, está fuera de alcance y no afecta al PDF.
- **Resuelto al revertir D5:** el estado de cuenta y Tesorería nombran el documento «Compra #N», y ahora el PDF también lo lleva, así que se cruzan. Una remisión con varios proveedores da un PDF por compra, cada uno con su número y su archivo.
- Las notas y los demás valores de la columna (Placa, Factura, Cuenta) no comparten fila con nada y no se tocaron. Una nota muy larga puede pasarse del margen derecho, como siempre.

## 4. Dirigidas y suite completa

- **Dirigidas** (`dirigidos.log`, 19:41:41→19:57:56): 6 archivos, **229 passed, EXIT=0**, con la predicción tomada de `--collect-only` antes de correr. Los archivos: test_api_purchases, test_sac_ciclo_b, test_sac_ciclo_d, test_sac_ciclo_c, test_sac_entrada_sin_proveedor y el nuevo. Después de esa corrida el backend no cambió; solo cambiaron `pdfExport.ts` y los documentos.
- **Guardas que recorren el árbol** (`guardas_arbol.log`, contra `pdfExport.ts` fa32b69c): `test_reloj_de_negocio.py`, `test_advisory_locks.py` y `test_crucible_charges.py`, **52 passed, EXIT=0**.
- **Suite completa: diferida al checkpoint** por decisión de Daniel (19-nov). La r1 y la r2 se detuvieron por cambios que él pidió a mitad de corrida y se conservan como `suite_pdf_r1_INVALIDA_cambio_daniel.log` y `suite_pdf_r2_INVALIDA_D5.log`.
  - `grep -rlE '/api/v1/purchases|PURCHASES_URL' backend/tests` da 26 archivos y las dirigidas corrieron 6. Los otros 20 quedan para el checkpoint; QA lo aceptó porque no hay push.
  - La predicción del checkpoint se deriva de `git diff --name-only 85b0d07 -- backend/tests` contra el 2161 medido en el árbol de 85b0d07. Hoy da 2164.
