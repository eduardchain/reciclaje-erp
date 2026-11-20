# Informe — Reparto por compra en la Entrada + IVA en compras (SAC)

**Plan:** `plan-sac-reparto-por-compra.md` v1.2 (GO de QA, commit `81b3f13`)
**Base:** `81b3f13` · **Nivel:** lógica · **Matriz de plantado:** `601d2f9` + addendum P2b `348614c`
**Evidencia:** `~/sac-evidencia/2026-11-20/reparto/`

## 1. Qué cambió

La unidad del reparto deja de ser el proveedor y pasa a ser la **compra de la Entrada** (`purchase_slot`). Con eso, el mismo proveedor puede tener dos compras en una Entrada (Q-65). Además:
- la liquidación se llena como la hoja de Johana: columnas = compras y filas = materiales, con un precio por fila;
- el proveedor se crea sin salir de la pantalla;
- la compra lleva IVA y lo manda a la MISMA entidad `[Impuestos] IVA por Pagar` de las ventas.

**Backend:**
- migración `d6e8f0a2b4c7`:
  - `purchase_slot` en asignaciones y puente;
  - UNIQUE (línea, slot);
  - `document_taxes.purchase_id` con el CHECK de dueño único ampliado a tres;
  - backfill determinista con gate.
- liquidación agrupada y reusada por slot, con tres defensas duras 409:
  - el puente contradice al reparto;
  - dos compras vivas en un mismo slot;
  - una compra viva sin slot (C1).
- `TAX_SIGN_ON_PARTY` por clase de dueño. En la compra, el IVA da proveedor −IVA y entidad +IVA. Lo leen:
  - `apply_taxes` y `revert_taxes`;
  - el as-of (`_get_tp_balances_as_of`, tercera rama);
  - el estado de cuenta (`_tax_owner` con rama compra).
- `PurchaseResponse.taxes` / `total_with_taxes`, solo en el detalle.
- `GET /third-parties/similar`.
- el aviso de duplicado excluye las compras de la MISMA Entrada.

**Frontend:**
- `InboundLiquidatePage` reescrita, con un borrador en `localStorage` validado por forma y firma.
- `CreateSupplierDialog`.
- Detalle de la Entrada con «Compras (N)».
- Detalle de la compra y PDF con IVA. El PDF sin impuestos sale igual que antes.

## 2. Desviaciones del plan, declaradas

- **T9b (R4):** la premisa del plan, «una derivada LIQUIDADA se cancela directo desde Compras», no se sostiene desde #93 D14, porque el guard bloquea el cancel directo. El test fija dos cosas: el 400 del cancel directo, y que anular la Entrada (desliquidar + cancelar) devuelve el IVA. Por eso P10 es equivalente en lo alcanzable (§4).
- **QA pasada 1 (C1–C10):** aplicadas, con el delta `65ed9673` y el completo `8a40ce44`.
  - C1: la compra viva sin slot da 409, en vez de cancelarse en silencio. Lo cubre T18b.
  - C2–C9: pantalla y borrador.
  - C10: `numTax` en el detalle de la compra.
- **T3b (nuevo, después del plantado):** P2 dio 0 caídas porque ningún test intercambiaba proveedores entre compras. Con el OK de QA se agregó T3b, que también afirma el puente: una compra viva por slot y del proveedor correcto. P2b quedó con la predicción commiteada antes de re-plantar.
- **`savedAt` del borrador (lo encontró la guarda del reloj en la r2):** escribí `savedAt: new Date().toISOString()`, que es literalmente el token que persigue `test_reloj_de_negocio.py:302`. No era una fecha de negocio (es el instante del guardado y solo se pinta con `formatDateTime`), pero la guarda no juzga la intención y no se tocó. El arreglo, con OK de QA antes de editar:
  - `savedAt: number` con `Date.now()`;
  - `recoveredAt: number | null`;
  - el banner pinta `formatDateTime(new Date(recoveredAt).toISOString())`;
  - `assertDraftShape` exige `typeof savedAt === "number"`: un borrador viejo con string se descarta por forma (C3).
  - Lección: las 3 guardas van en los gates de AUTOR de todo cambio que toque `frontend/src` o `app/`, no solo en las dirigidas. Acá la vi recién en la corrida de 58 rutas.

## 3. Observaciones aceptadas por QA (pasada 1)

1. «Usar este» sobre el titular de una cuenta kg: la pantalla lo ofrece y el backend lo rechaza con el 422 de #93 al liquidar. No se pierde nada, pero el aviso llega tarde.
2. La llave del borrador: sin `userId` no se guarda borrador, y `orgId` puede ir vacío en la llave.
3. La precarga de retenciones reconoce la tarifa sin concepto: es el defecto (3) de #112, preexistente.

## 4. Gates

| Gate | Resultado | Archivo |
|---|---|---|
| ruff · tsc · eslint · build | limpios; eslint 37 = techo | — |
| Tests nuevos | 30 passed (`test_sac_reparto_por_compra.py`) | `plantado/P2b_control.log` |
| Plantado P1–P15 + P2b | ninguna caída en la dirección peligrosa; detalle abajo | `plantado/` |
| Dirigidas por grep + 3 guardas | r2 1598 passed + 1 guarda (arreglada); r3 acotada 82 passed | `dirigidas.log`, `dirigidas_r3_acotada.log` |
| Golden (una BD, R10) | 0 diffs reales y 0 aditivas, 32 + 32 capturas, con prueba de vida | `golden.log` |
| Smoke de migración | up/down/up limpio en la copia B; POST real con delta exacto | `smoke_migracion_*.log`, `smoke_post.log` |
| PDF con pypdf | iguales donde corresponde; control positivo distinto | `pdf/comparacion.log` (copiado de `.playwright-mcp/pdf_reparto/`, que no está rastreado y se limpia) |
| Parity | DIFF CERO (67 / 302 / 369) | `parity.log` |

**Plantado** (respaldo por ruta; cierre sha256 por ruta: OK en las dos tandas):

| P | Predicción | Cayó | Nota |
|---|---|---|---|
| P1 agrupar por proveedor | ≥ T1, T3, T13 | T1, T3, T13, **T17** | **De más:** yo había escrito «T17 NO». Causa medida (`:350`): al agrupar, la primera compra queda en 200 kg y la segunda Entrada, de 100, sale del ±20 % del aviso, así que no avisa |
| P2 reuso por proveedor | 0, hueco | 0 | Hueco confirmado → T3b |
| P2b (P2 contra T3b) | T3b solo | T3b | `:277`, las compras viejas siguen `liquidated` en sus slots originales |
| P3 signo del IVA invertido | ≥ T7, T8, T8b, T9, T9b, T10 | esas + T10b | De más en T10b: `total_with_taxes` 81.000 |
| P4 as-of sin rama Purchase | T10 | T10 | exacto |
| P5 aviso sin suprimir | T1, T17 | T1, T17 | exacto |
| P6 aviso apagado para todo `from_inbound` | T17 | T17 | exacto |
| P7 `_tax_owner` sin rama compra | ≥ T8, T9 | T8, T9 | T9b no, como estaba predicho |
| P8 `added`/`withheld` con el mapa de venta | 0, equivalente | 0 | equivalente hoy |
| P9 contado sin IVA | T7 | T7 | Causa medida: `:419`, el **saldo del proveedor** quedó en −19.000 (`assert _bal(sup_a) == 0`, la línea del archivo de la pasada 1), porque el contado pagó sin IVA. La caja, que era la primera falla predicha, viene después y no llegó a evaluarse |
| P10 reversa solo en la Entrada | 0, equivalente | 0 | equivalente en lo alcanzable |
| P11 backfill sin puente | T14 | T14 | `:792`, slot None |
| P12 C1 revertido | T18b | T18b | `:152`: `_liq` recibió 200 y esperaba 409, antes de mirar el status |
| P13 sin defensa dura | T18 | T18 | `:152`, 200 en vez de 409 |
| P14 PATCH solo con la categoría nueva (pantalla) | 0 tests; pantalla | — | Control: el PATCH lleva 2 ids. Plantado: lleva 1 y ALBERTO ESTAÑO pierde «Cliente». En dev se le devolvió por SQL |
| P15 renumerar slots (pantalla) | 0 tests; pantalla | — | Control: al quitar la 2 quedan «1, 3». Plantado: quedan «1, 2» |

**Golden:** las predicciones (0 y 0, porque las claves nuevas no están en CAPTURES) se escribieron a las 02:19:57. La prueba de vida fue a las 02:20:04: `/third-parties/similar` dio 422 en `:8001` (pid 10864, worktree `81b3f13`) y 200 en `:8002` (pid 10865, el árbol). Los dos procesos los lanzó `golden_run.sh` a las 02:20:00, y sus guardas 1–3 pasaron.
⚠️ La prueba de vida corrió en paralelo con el arranque de la captura, no estrictamente antes, porque `golden_run.sh` captura apenas responden los dos y el script no se tocó (árbol quieto).
El 0/0 no prueba la rama nueva: su control positivo es el smoke.

**Smoke de migración**, sobre COPIAS de la BD de dev:
- **Copia A, con los datos de dev tal cual:** el **downgrade falla**. La Entrada #27, creada en pantalla en este ciclo, tiene al mismo proveedor dos veces en una línea (Q-65) y la UNIQUE vieja (línea, proveedor) no se puede recrear. Es transaccional: no aplica nada.
- **Copia B:** se anula la #27 por API y se quita por SQL su asignación del slot 2 (simula un dev sin datos Q-65). Up/down/up limpio.
  - Los slots de todas las demás Entradas quedan idénticos tras el re-up, incluidas la #25 (dos proveedores) y la #31 (desliquidada).
  - Las dos compras canceladas de la #27 quedan las dos en slot 1, válido para canceladas (R5).
- **POST real** contra `:8003` sobre la copia B, arrancado a las 02:22:09, después del último cambio de `app/` (01:53:38):
  - nacen #12 (IVA 28.500, `total_with_taxes` 178.500) y #13 (sin IVA), del mismo proveedor, sin aviso de duplicado;
  - delta del proveedor −343.500 y del IVA +28.500, exactos.

**PDF**, descargados en navegador real desde la base (`:5175`, worktree `81b3f13`) y el árbol (`:5174`), por detalle Y por listado, contra el mismo backend:
- Costa #3173, directa: **IGUAL** en los dos llamadores.
- SAC #10, Entrada sin IVA: **IGUAL** en los dos llamadores.
- SAC #11, Entrada con IVA (control positivo): **DISTINTO** solo en los totales. La base pinta `Total: $ 1.050.324`; el árbol pinta `Subtotal`, `IVA: $ 199.562` y `Total con IVA: $ 1.249.886`.

## 5. Dirigidas y parity

**Dirigidas r2** (`dirigidas.log`): set por `grep` sobre la superficie tocada más las 3 guardas, 58 rutas (`dirigidas_comando.txt`, `dirigidas_archivos.txt`). Predicción escrita antes: 1599.
- Resultado: **1 failed, 1598 passed**. ARBOL_INICIO == ARBOL_FIN `995a63dc5efa35a3`; mtime 0, con control positivo de 686.
- La única falla fue `test_reloj_de_negocio.py::TestFrontend::test_ningun_formulario_deriva_su_fecha_del_dia_utc`, por `InboundLiquidatePage.tsx:612` (ver §2, `savedAt`).
- La r1 quedó inválida: la detuve yo con TaskStop. Se conserva como `dirigidas_r1_INVALIDA_detenida_por_mi.log`.

**Dirigidas r3 acotada** (`dirigidas_r3_acotada.log`, con OK de QA): las 3 guardas completas más `test_sac_reparto_por_compra.py`. Predicción escrita antes: 82.
- Resultado: **82 passed, EXIT=0**. ARBOL_INICIO == ARBOL_FIN `84da9f2f630c89b8`; mtime 0, con control positivo de 686.
- El argumento de por qué alcanza quedó en el propio log como artefacto:
  - `grep -l frontend` sobre el set da SOLO `test_reloj_de_negocio.py`, el único que el cambio de un `.tsx` puede mover;
  - el árbol de la r3 con SOLO `InboundLiquidatePage.tsx` reconstruido a su versión previa da exactamente `995a63dc5efa35a3`, el de la r2. O sea que la r2 sigue midiendo el backend;
  - `git diff --stat` de ese reconstruido contra el árbol: 1 archivo, +8 −5.

**Pantalla** (`pantalla_savedat.log`, Entrada #33 de SAC en dev):
- un borrador nuevo guarda `savedAt` como número y, al recargar, el banner muestra «20/11/2026, 02:55 a. m.»;
- el mismo borrador con `savedAt` string: al recargar no hay banner, la factura queda vacía y la llave se borra.

**Parity** (`parity.log`): DIFF CERO fuera del baseline, con 67 tablas, 302 índices y 369 constraints, contra dev en `d6e8f0a2b4c7`.

## 6. Runbook

- **Downgrade de `d6e8f0a2b4c7`:**
  - con una Entrada que tenga al mismo proveedor en dos compras de una línea, falla (UniqueViolation, sin aplicar nada); hay que anularla y consolidar su reparto antes de bajar;
  - además borra las filas de IVA de compra y no revierte su efecto en los saldos. Es la misma regla que #112: des-liquidar antes de bajar.
- **Upgrade en producción:** el gate de backfill se detiene si hubiera dos compras vivas del mismo proveedor en una Entrada. Antes de este ciclo eso era imposible.
