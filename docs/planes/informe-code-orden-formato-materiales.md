# Informe de código — La captura de la Entrada como el formato en papel

**Plan:** `docs/planes/plan-sac-orden-formato-materiales.md` v1.1. La matriz de plantado §6 se commiteó sola en `331307b`, antes de plantar, con la fila P3 ya corregida (C2 de QA) · **Base:** `7963e9f` · **Nivel:** lógica
**Fecha:** 2026-11-20 · **QA:** «QA Ecobalance»

Johana, por Daniel, pidió el 19-nov que los materiales salgan en el orden del formato en papel «Materiales recolectados», para digitar más fácil. Daniel eligió «pantalla como el papel».

## 1. Qué cambia

| Pieza | Archivo |
|---|---|
| Migración `c5d7e9f1a3b6`: `material_kg_profiles.form_order` (entero, nullable) e índice único parcial `uq_material_kg_profiles_org_form_order (organization_id, form_order) WHERE form_order IS NOT NULL` | `alembic/versions/c5d7e9f1a3b6_orden_formato_materiales.py` (nuevo) |
| Modelo con la columna y el índice en `__table_args__` (F8) | `app/models/material_kg_profile.py` |
| `MaterialFormOrderUpdate`; el response gana `form_order` y `material_is_active` (F3) | `app/schemas/material_kg_profile.py` |
| `set_form_order`: valida todo antes de escribir, NULL a toda la org + `flush` y recién después las posiciones (F2) | `app/services/material_kg_profile.py` |
| `PUT /material-kg-profiles/form-order`, declarado ANTES de `PUT /{material_id}` (F1); permiso `materials.edit`; flag del router | `app/api/v1/endpoints/material_kg_profiles.py` |
| `FORM_ORDER` (24 códigos, el 8 vacío) y `create_form_order`: siembra solo si la org no tiene formato (F5) | `scripts/seed_sac_org.py` |
| Renglones del formato en la captura y la edición (tipo compra) | `components/inbound/FormatoMateriales.tsx` (nuevo), `InboundCreatePage.tsx`, `InboundEditPage.tsx` |
| Config → «Formato de captura» | `pages/config/FormatoCapturaSection.tsx` (nuevo), `FormulasPage.tsx` |
| Orden por `form_order` en liquidación, detalle y PDF (F4) | `utils/formOrder.ts` (nuevo), `hooks/usePurchasePdfOrder.ts` (nuevo), `InboundLiquidatePage.tsx`, `InboundDetailPage.tsx`, `PurchaseDetailPage.tsx`, `PurchasesPage.tsx` |
| Servicio, hook y tipos | `services/sacConfig.ts`, `hooks/useSacConfig.ts`, `types/sac-config.ts` |
| T1–T6 | `tests/test_sac_orden_formato.py` (nuevo, 12 tests) |

Sin permisos nuevos. `material_kg_profiles` es exclusiva de SAC y su router está detrás de `kg_ledger_enabled`: el golden no aplica, medido (§2).

## 2. Gates

Logs en `~/sac-evidencia/2026-11-19/orden/`.

**Base:** los 10 archivos del redondeo son iguales entre el árbol y `7963e9f` (`base_vs_7963e9f.log`).

**Estáticos** (`estaticos.log`): ruff limpio en los 7 archivos de backend; tsc 0; eslint 37 avisos, igual al techo, con exit 0.

**QA pasada 1:** `orden_p1.patch` (sha `3de0ffe9…`). Delta C1/C2/C3: `orden_c1c3.patch` (sha `0a97bf64…`), con el sha de cada archivo en `orden_c1c3_archivos.sha256`.

**Tests nuevos** (`tests_nuevos.log`). La r1 no colectó: `TypeError: 'function' object is not subscriptable`. Dentro de una clase que tiene un método `list`, la anotación `list[...]` resuelve al método. Se usa `typing.List`; ruff no lo ve. La r2 dio 12 passed.

**Smoke de migración en dev** (`smoke_migracion.log`): `upgrade` → `downgrade` → `upgrade`. Imprime la columna, el `indexdef` del índice parcial y 0 columnas tras el downgrade.

**T7, seeder contra dev** (`t7_seeder.log`):
- Formato vacío: «sembrado (24 renglones)», EXIT=0.
- Johana cambia el formato (24↔25): «la org ya tiene uno (24 renglones, DISTINTO de FORM_ORDER) — no se toca», EXIT=0, y su orden se conserva.

**Golden: no aplica, medido** (`golden_no_aplica.log`). `grep -nE 'kg-profiles|kg_profile|form.order|inbound' backend/scripts/golden_capture.py` da 0 coincidencias.

**Dirigidas por grep** (`dirigidas.log`). El comando está en su primera línea y en `dirigidas_comando.txt`; la lista son 22 archivos, incluidas las tres guardas del árbol, en `dirigidas_archivos.txt`. De 00:37:46 a 00:54:32.
- **730 passed, EXIT=0**, capturado dentro del bloque. Cero FAILED, ERROR o Traceback en todo el log.
- La predicción de 730 se escribió antes (`dirigidas_prediccion.txt`). El primer intento fue vacuo y quedó marcado INVALIDA: el bash 3.2 de macOS no tiene `mapfile`, el arreglo quedó con 0 rutas y `--collect-only` colectó la suite entera (2187 contra los 730 esperados).
- `ARBOL_INICIO == ARBOL_FIN` (`1c0bb761…`). Archivos con mtime posterior al inicio, sin `__pycache__`: 0, con control positivo de 682. 5433 terminó con 0 sesiones.

**Plantado** (`plantado_run.log`; matriz en `331307b`). Respaldo por ruta, `.pyc` borrado, `PYTHONDONTWRITEBYTECODE=1`, cierre por sha256 de los tres archivos tocados (iguales al inicio y al final, e iguales a los que leyó QA).

| P | Defecto | Predicción | Cayeron | Nota |
|---|---|---|---|---|
| P1 | el PUT no pone NULL a los que salieron | T2 | T2 | `UniqueViolation`: D toma el 1 mientras A lo conserva |
| P2 | el upsert escribe `form_order = None` | T3 | T3 | `assert None == 1` |
| P3 | sin la validación de repetidos | T4[repetido], **200** en vez de 422 | T4[repetido] | **`assert 200 == 422`**. El índice no se entera: `[c,c]` asigna dos veces el mismo objeto |
| P4 | sin el flag del router | T5 sin flag | T5 sin flag + `test_isolation_flag_off_403` de `test_material_kg_profile.py` | el de más es la misma regla vista desde el otro archivo; dirección barata |
| P5 | el seeder siembra aunque ya haya formato | T7 «no pisa» | ver nota | ver nota |
| P6 | sin el NULL previo (F2) | al menos T2b y T2 | T2b y T2 | `UniqueViolation` en los dos |

**P5 corrió dos veces y la primera no sirve.** El seeder salió con EXIT=1 en las dos ramas: «Faltan credenciales», porque en T7 las cargué desde `~/.config/sac-prod.env` y en el plantado no. «Formato de Johana conservado: True» salió en las dos ramas sin que el seeder decidiera nada. Quedó escrita en el log como INVALIDA, con el motivo.
- El script ahora aborta si el seeder no sale con 0.
- La segunda corrida tiene las credenciales cargadas. Con el defecto: «sembrado (24 renglones)», y el formato de Johana vuelve al canónico. En el control: «no se toca», y su formato se conserva. Al final dev queda en el canónico.

Ninguna caída en la dirección peligrosa: todo test que la matriz decía que caía, cayó.

**Parity check** (`parity.log`): **DIFF CERO** fuera del baseline. 67 tablas, 301 índices (uno más que en #120: el índice parcial nuevo) y 367 constraints.

**Pantalla:** 1440 y 390, contra :8001 (PID 55473) y el Vite de :5174.

| Gate | Log | Resultado |
|---|---|---|
| Captura | `pantalla_captura.log` | Entrada #28 digitada en desorden (ALU-01, SCR-SG, BAT-G1 con peso; PLO-BAL en «Otros»): las líneas llegan en el orden del formato y PLO-BAL al final |
| F3, primer tramo (1440) | `pantalla_f3_c3.log` | TAP-BOR (renglón 21) desactivado en dev por SQL. Config lo marca «Inactivo — vacíe su renglón» y Guardar queda deshabilitado. «Vaciar renglón» deja el 21 vacío, el 22 sigue siendo GUA-RRU y Guardar se habilita. Guardado: la base tiene 19, 20, 22–25 y TAP-BOR en NULL |
| F3, segundo tramo (390) | `pantalla_f3_c3.log` | «Eliminar renglón» sobre el hueco corre GUA-RRU al 21. No guardado. Dev se restauró (TAP-BOR activo, PUT con `FORM_ORDER`) y el diff contra el «antes» da vacío |
| F4 | `pantalla_f4.log` | Compra #8 (de la Entrada #29): el content stream del PDF es idéntico desde el detalle y desde el listado, con BAT-G1 antes que SCR-SG aunque la API las devuelve al revés |
| F6 (1440) | `pantalla_f6_c1.log` | Entrada #32: ícono con la nota; se cambia solo SCR-SG; el GET conserva el precio 2000 y la nota de BAT-G1 |
| F7 (390) | `pantalla_f7_c1.log` | Entrada #33 Revisada: ámbar 0 al abrir; cambiar solo la nota la deja Revisada. Control: tocar HIE-CHA en el formato → ámbar 1 |
| C1 (1440 y 390) | `pantalla_c1.log`, `c1_preparacion.log` | Ver §3 |

## 3. Decisiones y observaciones

**C1 de QA — la línea en 0 no entra al formato.** Al desliquidar una Entrada, un material repartido sin pesar deja una línea con cantidad 0 (#93 D5). Si caía en su renglón, `formatoLines` la descartaba y el guardado la borraba sin aviso. Ahora `splitLinesForFormato` manda al formato solo las líneas con `quantity > 0`, y la de 0 queda en «Otros», visible, bloqueando el guardado como siempre.
- En pantalla (Entrada #31, HIE-CHA en 0), Guardar sigue deshabilitado incluso con la nota cambiada.
- Control: quitar la línea lo habilita, con el aviso ámbar de «vuelve a Registrada».
- No se guardó; el GET final muestra la Entrada intacta.

**El material de C1 aparece dos veces, y no se agrega código.** HIE-CHA queda en «Otros» con 0 y también en su renglón vacío del formato. Si Johana pone cantidad en los dos, el servidor responde **422 «El material HIE-CHA aparece en mas de una linea — una fila por material (D3)»**. Medido por pantalla en dev (`pantalla_c1_duplicado.log`: el payload lleva HIE-CHA dos veces, el toast muestra el mismo texto y el GET no cambia). Con la línea en 0 el payload no llega a salir. Deshabilitar el renglón sería una regla dinámica para un caso que hoy ya bloquea solo y que solo nace de desliquidar (decisión de QA).

**C3 — «Vaciar renglón» y «Eliminar renglón».** Es una decisión de producto nuestra, no un pedido del cliente; Daniel la ve en localhost.
- Con un solo «Quitar», quitar un material corría los renglones de abajo y los números dejaban de coincidir con el papel, en silencio.
- Ahora sobre un material el botón es «Vaciar renglón»: deja el número como hueco.
- Sobre un hueco el botón es «Eliminar renglón», y ese sí corre los de abajo.
- El texto, el `aria-label` y el `title` dicen lo mismo. A 390 queda solo el ícono, distinto en cada caso: borrador ámbar o papelera roja.
- **Vaciar el último renglón equivale a eliminarlo**, porque el guardado recorta los vacíos del final; un hueco al final no existe en el papel.
- Si Daniel prefiere renumerar, se revierte en una línea, en `remove`.

**(a) Los renglones se congelan mientras se digita.** En la captura, `pinnedSlots` se fija con el primer input; en la edición, al inicializar. Si alguien cambia el formato en Config mientras Johana digita, sus renglones no se mueven bajo el cursor. Aceptada por QA en la pasada 1.

**(b) «Agregar renglón vacío» en Config.** El plan D3 listaba flechas, quitar y agregar material. Sin este botón no hay forma de recrear un hueco como el del renglón 8 (Batería Húmeda, Q-72) si alguien lo elimina. Aceptada por QA en la pasada 1.

**Batería Húmeda (Q-72)** no se crea: el formato queda con el hueco del 8 hasta que Johana responda.

**Archivos nuevos** (no entran en el `ARBOL_SHA` de las dirigidas, que cubre solo lo rastreado por git):
- `14d03d07…` `backend/alembic/versions/c5d7e9f1a3b6_orden_formato_materiales.py`
- `c1a0fe08…` `backend/tests/test_sac_orden_formato.py`
- `ec689f6f…` `frontend/src/components/inbound/FormatoMateriales.tsx`
- `6eef24a8…` `frontend/src/hooks/usePurchasePdfOrder.ts`
- `a6cc2993…` `frontend/src/pages/config/FormatoCapturaSection.tsx`
- `3c24ce9f…` `frontend/src/utils/formOrder.ts`

## 4. Suite completa

Diferida al checkpoint (regla del 19-nov). La predicción del checkpoint sale de `git diff --name-only 85b0d07 -- backend/tests`.

## 5. Condiciones de deploy (abiertas)

1. **Pantalla de Daniel en localhost:** la captura de una Entrada como el papel, y Config → «Formato de captura» con C3 (vaciar contra eliminar).
2. **Producción:** la provisión siembra el formato en el deploy solo si SAC no tiene uno. Es una escritura en producción, con el OK de Daniel en el runbook.
3. **Suite completa en el checkpoint.**
