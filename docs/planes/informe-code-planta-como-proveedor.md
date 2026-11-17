# Informe de código — Planta Juan Mina como proveedor de maquila (SAC)

**Plan:** `docs/planes/plan-sac-planta-como-proveedor.md` v1.2 · **Base:** 07ccd7a · **Nivel:** lógica
**Fecha:** 2026-11-17 · **QA:** «QA Ecobalance» (sesión `d724e9a0…`)

Primer ciclo con el flujo que Daniel fijó ese día: **QA lee código y tests ANTES de los gates** (plantado, suite completa) y la evidencia después.

## 1. Qué cambia

Con el setting `plant_third_party_id` puesto, las cinco maquilas entre sedes se causan como **un** `expense_accrual` a nombre de PLANTA JUAN MINA. Sin el setting, que es como están hoy las siete organizaciones, se emite el par interno de siempre.

| Pieza | Archivo |
|---|---|
| Clave nueva (str UUID o None), validada como UUID en el payload (N4) | `app/schemas/organization.py`, `app/utils/org_settings.py` |
| Un solo punto de emisión, con validación fail-closed (D2, D3) | `app/services/plant_maquila.py` (nuevo) |
| Los cuatro emisores llaman al helper | `transfer.py`, `willard_delivery.py` (×2), `crucible_charge.py` |
| Las anulaciones revierten con `_reverse_effects` y leen el tercero del movimiento (D4) | `transfer.py`, `willard_delivery.py`, `crucible_charge.py` |
| Guard de Tesorería por campo, con lista cerrada (D5) | `app/services/money_movement.py` |
| El seeder no pisa settings ajenos ni editados; exit 3 (D11, H1) | `scripts/seed_sac_org.py` |
| `--modo revisar` informa las claves ajenas (D11) | `scripts/archivar_org_sac.py` |

Sin migración, sin permisos nuevos, sin tipos de movimiento nuevos y sin frontend.

## 2. Producción: lo que Johana ya registró

Daniel lo pidió el 17-nov: Johana ya registra y el cambio tiene que ser inocuo para sus datos. La relectura de producción se hizo **solo con GET**, el 17-nov a las 15:06Z (`~/sac-evidencia/2026-11-17/relectura_prod_6_operaciones.log`):

- **Entradas:** #4 y #5 son Willard y están confirmadas; #6 y #7 son de compra y están revisadas (la #7 se creó a las 09:56 COL). Las #1–#3 están anuladas.
- **Lo que no hay:** traslados, Salidas, crisol, compras, ventas, transformaciones y movimientos de maquila.

Consecuencias:

- **El ciclo no toca ninguna fila existente.** Con el setting vacío, el comportamiento es el de hoy.
- **G7 hoy vale cero:** no hay maquilas nacidas como par que haya que convertir. Hasta el deploy, Johana no debería registrar traslados a planta, Salidas ni crisol.
- **Anular documentos viejos sigue igual:** el par se revierte por la rama `pass` y la factura con el mismo signo. Lo cubren T12, T13 y la respuesta 1 de QA.
- **Poner el setting en producción es una escritura** y espera el OK de Daniel. Se manda el diccionario vivo completo más la clave, porque el endpoint reemplaza todo el JSONB.

## 3. QA pasada 1 (código)

Delta r1: `delta_r1.patch`, sha256 `e11551cf…f83eb`. QA dio el **GO de código para `app/` y los tests**, con un hallazgo:

- **H1** — `merge_settings` trataba una clave del seeder **presente con None** como si faltara, y la escribía. Corregido: solo se escribe si la clave está ausente; un None presente se respeta y entra en DECISIÓN PENDIENTE. Lleva test nuevo (`test_una_clave_del_seeder_en_none_se_respeta`) y su plantado (P13). Delta r1→r2: `delta_r1_a_r2.patch`, sha256 `aa8a344f…3fb5a`.
- **N5** — en C6, QA nombró para P8 las mitades APAGADAS del contraste (`test_venta_puro_sin_flag_sin_par`, `test_dross_return_sin_flag_mueve_kg_sin_par`). Es un error de QA, no de la matriz. La predicción de P8 lo anticipó antes de medir.
- **N6/N7** — la predicción de P8 nombra cada test, y la de P1 suma T9 ×30.
- **N8** — Q-19 del inventario corregido: quién ejecutó el cambio de roles no se puede datar.

## 4. Gates

> Evidencia completa al 17-nov, 12:51 COL.

- **ruff:** limpio en los 11 .py.
- **Tests nuevos:** 67 (`test_sac_planta_proveedor.py` 59, `test_seed_sac_settings.py` 8).
- **Suites dirigidas (r2):** **583 passed, EXIT=0**, 0 FAILED/ERROR/Traceback en todo el recorrido (`dirigidos_r2.log`, 10:26:36→10:42:39 COL). El log estampa al inicio el sha256 de los 11 archivos del ciclo, que son los del delta r2. Corrió 12 archivos: los dos nuevos, los de traslados, Salidas, crisol, Tesorería, ciclo D, P&L por sede, impuestos en ventas, `test_org_settings.py` (N2: pasa sin cambios) y los del seeder y el cargador (`test_archivar_org_sac.py`, `test_load_sac_opening.py`).
  - La r1 quedó **inválida por una colisión en 5433 que causé yo**: lancé los tests del seeder mientras corría. El log se conserva como `dirigidos_r1_INVALIDA_colision.log`. Antes de la r2 se verificó la base libre (sin pytest vivo y `pg_stat_activity` en 0), y otra vez al terminarla.
- **Plantado P1–P13: 13/13**, con cierre absoluto: el sha256 de los 6 archivos plantados quedó igual al de antes (`plantado/resumen.md`; la comparación fila por fila está en `plantado_comparacion.md`). Las predicciones se escribieron antes de correr.
  - **Dirección peligrosa: ninguna.** Todo lo que se predijo que caería, cayó, y todo lo que se predijo que no caería quedó en verde (las mitades apagadas de P8, T8[abono] en P4, T12 en P9, T8b[manual] en P10, org_vacia y T15 en P12).
  - **Exactas, 9 de 13:** P1 (52), P2 (30), P3, P4, P5, P7 (17), P9, P11 y P13.
  - **De más (dirección barata), 4:**
    - **P6 (+T9[dross]×6):** el par viejo se saltea también la validación. Debí predecirlo.
    - **P8 (+3 tests de Salidas):** necesitan el par para afirmar lo suyo; es la vía compartida.
    - **P10 (+`test_cancel_after_manual_annul_noop` de ciclo D):** es la red preexistente del recolector. Estaba en la selección y no la nombré.
    - **P12 (+el test de H1):** ese test nació después de escribir la predicción de P12, y no la actualicé.
  - **Contra la matriz commiteada,** las 12 filas tumban lo que dicen. La única diferencia es la de N5: P8 nombra dos mitades apagadas, que no caen.
- **Suite completa: 2140 passed, EXIT=0**, igual a la predicción escrita antes (`suite_prediccion.md`). Corrió a archivo (`suite_planta.log`, 11:17:05→12:51:15, 1:34:04), con 0 sesiones en 5433 al arrancar. Hubo 0 FAILED/ERROR/Traceback en todo el recorrido.
  - **La base de la predicción salió de comandos:** 1920 (#113, c3260fa) + 64 + 89 (`git diff c3260fa -- backend/tests`: los dos archivos de #114/#115, 0 borrados) + 59 + 8 = 2140. `--collect-only` dio 2140 como medición independiente.
  - **El árbol quedó quieto:** el sha256 fue igual al inicio y al final (`52576e27…7e07`), y el mtime posterior al inicio dio 0 archivos en `app/`, `tests/`, `alembic/`, `scripts/` y `frontend/src/`, con control positivo de 670.
- **Golden:** se aplica la medición, no la corrida (§3 del plan, reproducida por QA).

## 5. Observaciones

- `test_par_reparto_no_mueve_cuentas` (preexistente, `test_willard_deliveries.py`) recorre los movimientos del par con un `for`. Sin par, el `for` queda vacío y el test pasa vacuo. **El plantado lo confirmó:** P8 (no se emite nada) no lo tumba. No es de este ciclo; se reporta para que alguien le agregue un `len(...) == 2` antes del loop.
