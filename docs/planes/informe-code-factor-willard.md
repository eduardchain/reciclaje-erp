# Informe: elegir el factor de Willard por línea al liquidar (plan v1.3)

- **Commit:** `b156672` en `coder-1/factor-willard`, sobre la matriz `d3d7817`. Base del plan: `9144c4f`.
- **Diff:** `git diff 9144c4f b156672 -- backend frontend`, 18 archivos, sha256 `9733158cbc1f7e17a894c4620396fe96b951c93b8c26950cba68f7dcbe9b87e1`. Es el mismo parche que verificó QA 1 en la pasada 2 (`veredicto_pasada2.md`, dfb0edd6).
- **Nivel:** lógica (contrato del back, migración y regla de kilos).
- **Evidencia:** `~/sac-evidencia/2026-11-24/coder-1-factor-willard/`.

## 1. Qué hace

- **Config → Materiales (kg).** La fórmula `drosses_to_lead` vigente de un material puede llevar un nombre para su factor por defecto y una lista de alternativas. Para SCR-SG: «Seco pinza» 59 % por defecto y «Seco escurrido» 56 % como alternativa.
  - Al versionar la fórmula, lo que no se manda se copia de la vigente.
  - Un `null` explícito quita el nombre o la lista (D2).
  - Los números anidados quedan como número JSON (`_json_native`).
- **Liquidar una Willard.** Desde el detalle y desde la fila del listado se usa un solo componente, `WillardLiquidateDialog`. Por cada línea con alternativas muestra un selector con el defecto preseleccionado y los kilos estimados en vivo.
  - El `confirm` recibe `conversion_options`.
  - Elegir el defecto guarda NULL; elegir una alternativa guarda su nombre canónico (`inbound_order_lines.conversion_option`, migración `f8b0c2d4e6a9`).
  - Antes de escribir, todas las opciones se validan juntas: una opción desconocida o un material repetido dan 422 y no escriben nada.
- **Snapshot.** El movimiento kg guarda el factor aplicado (`applied`) y la descripción lo nombra, solo si la fórmula tenía alternativas. Sin alternativas, el snapshot sale byte a byte como antes (T2).
- **Respuesta y detalle.** Cada línea trae `conversion_option`, `lead_percentage_applied` y `lead_factor_label_applied`, los tres del snapshot del movimiento kg confirmado; nunca de la fórmula de hoy. El detalle muestra «Seco escurrido · 56 %».
- **Edición D18 de una confirmada.** Conserva la opción guardada. Si la opción ya no existe en la vigente, da 422 y nada cambia (D5).
- **Sin fórmulas en el diálogo.** Si las fórmulas no se pueden leer (un rol sin `formulas.view`, o la red), el diálogo muestra un aviso ámbar y no bloquea. En ese caso cada material usa su defecto (C2 de QA 1).
- **`archivar_org_sac.py --modo revisar`.** Compara cada fórmula por su clave: `kg_lead_per_unit` en baterías y `lead_percentage` en drosses. Antes tomaba «el único valor», así que una fórmula con factores se reportaba como distinta del seeder (C1 de QA 1).

Lo que no cambia (plan §4):
- traslado, Salidas de Plomo y crisol siguen usando el defecto (T10);
- la compra regular y el reparto no se tocan;
- Costa y Meta no tienen filas en estas tablas, y los routers van detrás de `kg_ledger_enabled`.

Un factor mal escogido se corrige anulando la Entrada y registrándola de nuevo. Es D6, aceptado por Daniel con sus tres costos; no se programó nada para corregir.

## 2. Gates

| Gate | Resultado | Archivo |
|---|---|---|
| Dirigidas | 1157 passed, EXIT=0, igual a la predicción escrita antes. Árbol igual al inicio y al final (18 sha) | `dirigidas.log`, `dirigidas_prediccion.txt`, `dirigidas_set.txt` |
| Plantado contra `d3d7817` | 15 de 15 sin dirección peligrosa | `plantado/resultado_plantado.md` |
| e2e E1–E6 a 1440 y 390 | todos PASS, 0 errores de página | `e2e/e2e_base.log`, `e2e/e2e_e1_r2.log`, `e2e/shots/` |
| Arnés U del diálogo | 16 PASS | `u/u_base.log` |
| ruff, tsc, eslint, build | 0, 0, 37 avisos (= techo), OK | `lint_tsc_build_final.log` |
| Guardas del árbol | 52 passed | `guardas_delta1.log` |
| Migración | up, down y up limpios; termina en `f8b0c2d4e6a9` (head) | `smoke_migracion.log` |
| Parity | DIFF CERO (68 tablas, 306 índices, 375 constraints) | `parity.log` |
| Golden | no aplica, medido: ninguna de las 14 entradas de `CAPTURES` toca Entradas, fórmulas ni kg | `medicion_lectores_y_golden.log` |

Del plantado:
- **Exactas:** P2, P3, P5, P10, P11a, P11b, P13, P14 y P15.
- **En la diagonal (≥):** P1, P6, P7 y P12.
- **De más, con su causa** (la dirección barata):
  - P4 cayó también en T6 «material nuevo», porque SCR-SG pierde su escurrido guardado.
  - P8 cayó también en T9 «copia que choca», porque la copia choca justo por un % igual al del defecto. **O1 de QA 1:** el resultado decía que eso estaba «anotado ANTES de plantar». Ni la matriz `d3d7817` ni ningún log lo dejan escrito, así que se corrigió a «de más, con su causa».
- **P9:** 0 caídas, como se predijo. `confirm` hace un solo commit y cada request abre su propia sesión.
- **P14:** se plantó en el `.tsx` recién terminadas las dirigidas, porque `test_reloj_de_negocio.py` recorre `frontend/src`. Con el aviso quitado, E6 falló a 1440 y a 390; con el archivo restaurado pasó en los dos.

La primera corrida de E1 falló por el instrumento: comparaba con `JSON.stringify`, y JSONB reordena las claves. El valor era el mismo. El instrumento ahora compara como objeto y E1 pasa a los dos anchos. Esto es lo que lleva al O1 del runbook.

## 3. Runbook del deploy (plan §8; lo ejecuta el Coordinador por API, con relectura)

**O1 (QA 1), dos condiciones antes del paso 1:**

- **Correrlo solo después de la prueba de vida de producción.** Tiene que mostrar el código nuevo: por ejemplo, un `GET /api/v1/inbound-orders?limit=1` en SAC cuyas líneas traigan la clave `conversion_option`. Si la clave no está, el backend es el viejo y no se escribe nada.
- **Comparar `parameters` como OBJETO, nunca como texto.** JSONB no conserva el orden de las claves, así que una comparación por texto da «distinto» con los mismos valores. Lo vimos en el E1 de este ciclo. Esto vale para los pasos 1, 2 y 3.

El runbook no va en el seeder: el seeder no pisa lo que no puso él, y la lista es dato del cliente. Todo va contra `https://api.ecobalance.cc`, con el token del superusuario y el `X-Organization-ID` de SAC.

1. **Leer** (GET) y guardar las dos respuestas en la evidencia:
   - `GET /api/v1/materials?search=SCR-SG&limit=50`: tomar el `id` del ítem cuyo `code` es exactamente `SCR-SG` y está activo. Si hay más de uno o ninguno, parar.
   - `GET /api/v1/material-conversion-formulas/current`: la fila de `SCR-SG` tiene que ser `drosses_to_lead` con `parameters == {"lead_percentage": 0.59}`, comparado como objeto. Si es otra cosa, parar y avisar: alguien la cambió.
2. **Escribir**, una sola vez: `POST /api/v1/material-conversion-formulas` con este cuerpo, poniendo en `material_id` el id del paso 1:

   ```json
   {
     "material_id": "<id de SCR-SG del paso 1>",
     "formula_type": "drosses_to_lead",
     "parameters": {
       "lead_percentage": 0.59,
       "label": "Seco pinza",
       "alternatives": [{"label": "Seco escurrido", "lead_percentage": 0.56}]
     },
     "notes": "Factores de Willard: Seco pinza 59 % (defecto) y Seco escurrido 56 % (pedido SAC, autorizado por Daniel 24-nov)"
   }
   ```

   Respuesta esperada: 201. El `id` es distinto del de la vigente del paso 1, y `parameters` es igual a lo enviado, comparado como objeto.
3. **Releer** `GET /api/v1/material-conversion-formulas/current`:
   - la fila de `SCR-SG` es la nueva (mismo `id` que el 201) con esos `parameters`;
   - las demás filas son idénticas a las del paso 1 (diff de los dos JSON sin la fila de SCR-SG = vacío, comparando objetos).
4. **Si algo sale mal:** no se borra, porque la tabla es append-only. Se publica otra versión con `{"lead_percentage": 0.59, "label": null, "alternatives": null}`, que quita la lista (D2), y se avisa a Daniel.

Datos de prod (plan §8, Q-76): las 3 Willard con SCR-SG ya liquidadas (remisiones 16272, 16341 y 16391) se quedan al 59 %, sin backfill: su `conversion_option` queda NULL, que es el defecto. Las 3 en Revisada (16300, 16415 y 16436) las liquida SAC cuando exista la opción.

## 4. Migración e integración

- **Migración:** `f8b0c2d4e6a9` cuelga de `e7f9a1b3c5d8`. Agrega `inbound_order_lines.conversion_option String(40) NULL`; es aditiva y sin backfill.
- **Regla del Coordinador (24-nov):** si este cambio se integra segundo, al rebasar sobre develop se le cambia el `down_revision` para que cuelgue de la migración del otro, se vuelven a correr el smoke up/down/up y el parity, y ese delta vuelve a QA 1.
- **Antes del deploy:** Daniel lo ve en localhost (front :5181 contra :8011, org SAC de dev).
- **Suite completa:** diferida al checkpoint.

## 5. Fuera de alcance

Igual que el plan §9:
- factores alternativos en baterías;
- elegir el factor en la captura o en la revisión;
- alternativas en traslado, Salidas o crisol (Q-73);
- partir la cuenta kg por factor (Q-74);
- una acción para corregir el factor de una Willard liquidada.
