# Informe de código — Afinado de Salidas de Plomo (#105)

**Plan:** `plan-sac-afinado-salidas.md` v1.1 (QA GO condicionado → condiciones cumplidas) · **Fecha:** 2026-09-09 · **Alcance:** consecutivo por serie (punto 17), báscula solo-pantalla (punto 20), `sales.review` fuera del catálogo, WILL-BAT-JM fuera del seeder (punto 19 reducido), venta por valor total (pantalla).

## 1. Qué cambió

**Backend**
- `models/willard_delivery.py`: `SERIES_OF_TYPE` (única fuente) → `series_of()`, `series_check_sql()`, `SERIES_LABELS`; columna `series` NOT NULL; `UniqueConstraint(org, series, delivery_number)` reemplaza al único global; `CheckConstraint(series_check_sql())`; `@property label`.
- `services/willard_delivery.py`: `_lock_key(org, series)` con `zlib.crc32` (D3); `_next_number(db, org, series)` filtra por serie; `create()` estampa `series`; las 7 descripciones generadas llevan `Salida de Plomo — {label}` (D5). Cero `delivery.delivery_number` sueltos en f-strings (assert en el script de edición).
- `api/v1/endpoints/willard_deliveries.py`: response gana `series` y `label` (campo por campo); lista ordena por `date desc, created_at desc`.
- `schemas/willard_delivery.py`: `series: Literal["venta","abono"]`, `label: str`.
- `services/role.py`: sale `sales.review` del `PERMISSIONS_CATALOG`.
- Migraciones: `a7b8c9d0e1f3_willard_delivery_series` (columna + backfill desde el tipo + NOT NULL + CHECK + swap del único; **congela** números; downgrade recrea el global y solo renumera si hay colisión, LOSSY declarado) y `b8c9d0e1f2a4_drop_sales_review_permission` (DELETE idempotente; downgrade reinserta la fila sin asignaciones, F7).
- `scripts/seed_sac_org.py`: `KG_ACCOUNTS` sin JM; `OBSOLETE_KG_ACCOUNTS = ["WILL-BAT-JM"]` → PATCH `is_active=false` en provisión solo si está activa (422 con saldo → warning sin abortar).

**Frontend**
- `types/willard-delivery.ts`: `series`, `label`.
- `WillardDeliveriesPage`: columna # y card mobile muestran `label`.
- `WillardDeliveryDetailPage`: título y diálogo de anular con `label`; precio por línea con conmutador **Unitario/Total** + vista previa; el payload manda `unit_price` XOR `total_price`.
- `WillardDeliveryCreatePage` / `EditPage`: la casilla Báscula solo se renderiza cuando `unitOf(material) !== "kg"` (en kg el servidor la llena: `_auto_weight`); título de Edit con `label`.

**Docs**: control de cambios punto 19 reducido + **Q-35** (sub-saldo de Bogotá ¿es deuda?) + corrección del punto 20 (el servidor ya autocompletaba); plan v1.1 con la grilla corregida (P3 fuera de la diagonal, nota P8).

## 2. Verificación de la migración en dev (5434), con artefacto

`alembic upgrade head`: `[a7b8c9d0e1f3] series llenada desde el tipo en 26 salida(s); numeros intactos` (26 = todas las orgs SAC de dev, incluidas las inactivas de resets anteriores) · `[b8c9d0e1f2a4] sales.review: 1 fila(s) del catalogo borrada(s); 4 asignacion(es) en role_permissions cayeron por CASCADE`. SAC activa (`4da68d64`), `psql` después: `1 | abono | abono_bateria | liquidated`, `2 | abono | abono_material | annulled`, `3 | venta | venta | liquidated` — **números intactos, serie llena**. Constraints en PG: `ck_willard_delivery_series` = `((delivery_type = 'venta' AND series = 'venta') OR (delivery_type = ANY('{abono_bateria,abono_material}') AND series = 'abono'))`, `uq_willard_delivery_series_number` = `UNIQUE (organization_id, series, delivery_number)`. `permissions` con `sales.review`: **0**. El texto del CHECK del modelo (`series_check_sql()`) == el literal congelado de la migración (comparado por script: `IGUAL`).

## 3. Gates (artefactos en el scratchpad de la sesión)

| Gate | Artefacto | Resultado |
|---|---|---|
| Tests nuevos (11) + re-semantizado | `afinado_nuevos.log` | 12 passed, EXIT=0 |
| Parity (modelos vs 5434 migrada) | `afinado_parity.log` | **DIFF CERO** (65 tablas, 289 índices, 343 constraints), EXIT=0 |
| ruff backend | consola | limpio |
| eslint (techo 37) | `afinado_eslint.log` | 0 errores, 37 warnings (= techo, cero nuevas), EXIT=0 |
| tsc | consola | EXIT=0 |
| build | `afinado_build.log` | EXIT=0 |
| Suite completa a archivo | `afinado_full.log` (+ `afinado_full_start.txt`) | **1749 passed** en 1:06:05, `EXIT=0` como última línea; mtime fuerte: ningún `.py` de `app/` ni `tests/` posterior al arranque (13:57:10). 1738 + 11 nuevos = 1749 |
| Golden | — | **No aplica**, verificado hoy contra `CAPTURES` con comando (14 entradas / 11 rutas: `/money-accounts`, `/money-movements`, `/reports/*` ×8, `/warehouses`; ni willard, ni roles, ni kg). Las migraciones tocan `willard_deliveries` (exclusiva SAC) y una fila de `permissions` sin asignación en orgs cliente |

## 4. Defectos plantados (grilla §6 del plan)

Un log por defecto (`plant_P1.log` … `plant_P10.log`, cada uno con `EXIT=`), resumen en `plantado_resumen.txt`; el árbol se restauró por `cmp` contra los respaldos (4 archivos `== respaldo`) y `git status` muestra solo los cambios del ciclo. Selector: el archivo entero `test_willard_deliveries.py` filtrado a las 11 clases/tests de la grilla + `test_peso_se_autocompleta_en_kg` + `test_la_venta_derivada_de_la_salida_sigue_pasando` (13 tests por corrida).

| Defecto | Predicción (grilla v1.1) | Cayeron | Veredicto |
|---|---|---|---|
| P1 `_next_number` sin filtro por serie | T1 | T1, T6, T7 | principal ✓; +2 colaterales por la misma vía que P3 (todo test que lee un `label` ve la numeración) |
| P2 `_next_number` salta anuladas | T2 | T2 | exacto |
| P3 único global (org, número) | T1, T3, T6, T7 | T1, T3, T6, T7 | exacto (la corrección de QA, confirmada) |
| P4 CHECK sin mapping tipo↔serie | T4, T5 (T8 secundario) | T4, T5 | exacto; T8 no cae, como se declaró |
| P5 descripciones con `delivery_number` a secas | T6 (+ el re-semantizado de #104) | T6, `test_la_venta_derivada…` | exacto |
| P6 lista ordena por número | T7 | T7 | exacto |
| P7 endpoint arma `label` viejo | T8 | T8, T1, T2, T7, `test_la_venta_derivada…` | principal ✓; +4 colaterales: los helpers leen `label` de la respuesta |
| P8 `_auto_weight` fuera de `_replace_lines` | T9 + `test_peso_se_autocompleta_en_kg` | T9, `test_peso_se_autocompleta_en_kg`, T6, `test_la_venta_derivada…` | principal ✓; +2 colaterales: flujos que capturan kg sin báscula y liquidan (422 "sin peso") |
| P9 `sales.review` en el catálogo | T10 | T10 | exacto |
| P10 llave del lock con `hash()` | T11 | T11 | exacto |

**Diagonal 10/10**: cada defecto tumba su test principal y ninguno pasó en verde. Siete filas exactas; tres (P1, P7, P8) con caídas colaterales que la grilla no predijo — las tres por la misma razón que QA ya había señalado en P3: un defecto en un camino COMPARTIDO (numeración, `label` del response, autocompletado del peso) tumba todo test que pase por ese camino, no solo el que lo asserta. Los colaterales van todos en la dirección BARATA (caen de más); la grilla existe para atrapar la dirección peligrosa — un test que debía caer y no cayó — y en este ciclo no hubo ninguna.

**Regla (QA, al dar el GO)**: cuando el defecto vive en una **vía compartida**, la predicción de la fila se escribe como "≥ estos" y la fila se marca "vía compartida"; así la sub-predicción queda declarada en vez de aparecer como sorpresa. Aplica a la próxima grilla, no a esta (ya commiteada como compromiso previo).

## 5. Seeder en dev (org SAC activa `4da68d64`, backend :8001)

| Corrida | Artefacto | Qué pasó |
|---|---|---|
| Dry-run | `afinado_seed_dry.log` | EXIT=0; `[11] Cuentas kg (Willard x2 + INTERSEDE)`; resumen "3 cuentas kg" |
| Apply #1 y #2 | `afinado_seed_apply1.log`, `…apply2.log` | EXIT=0 ambas; roles `bascula_sac`/`revisor_inventario` "permisos al dia"; JM ya estaba inactiva (sesión del 9-sep) → la rama de desactivación **no corrió** |
| Apply #3 y #4 | `…apply3.log`, `…apply4.log` | dos no-op más (EXIT=0): una reactivación de JM por `psql` no había corrido por un error de shell (zsh no parte una variable con espacios), así que valen solo como idempotencia extra |
| **Apply con JM activa** | `afinado_seed_apply_rama.log` | JM reactivada a mano (`UPDATE … is_active=true`, simula prod, donde sigue activa) → el seeder imprime `cuenta kg obsoleta desactivada: WILL-BAT-JM`, EXIT=0; `psql` después: `WILL-BAT-JM \| f`, las otras 3 en `t` |

La rama que el runbook de prod necesita corrió al menos una vez y dejó el estado esperado. Ningún material, tercero, tarifa ni fórmula cambió en las cinco corridas (conteos idénticos: 38/8/5/22).

## 6. Pantalla

Pendiente de Daniel: lista con `Venta #n` / `Abono #n` y tabs, detalle, liquidar una venta por **Total**, Create/Edit sin casilla de báscula en material kg.

## 7. Proceso
- La grilla se corrigió ANTES de plantar por observación de QA (P3 tumba T1/T6/T7 además de T3; P8 tumba también el test preexistente).
- Primera corrida del plantado: **"no tests ran" ×10** por un selector con la clase equivocada (`TestWillardTwoStep` en vez de `TestGuards`). Se vio en el resumen (`ERROR: 1`, `no tests ran`) y se repitió con el selector arreglado. Es la clase de #99/#100: un gate que no corrió se parece a uno que pasó, salvo que el resumen imprima lo que corrió.
- El registro del punto 20 decía "sin autocompletar" y era falso; corregido en control de cambios, memoria y plan.

## 8. Runbook de deploy (condición C2 de QA)

1. `/deploy` aplica las dos migraciones (`a7b8c9d0e1f3` congela números y llena `series`; `b8c9d0e1f2a4` borra `sales.review` — en prod tiene 0 asignaciones que importen: el permiso nunca estuvo en un rol de sistema y el seeder ya no lo pide).
2. **Seeder en provisión contra prod** (`--apply --api-url https://api.ecobalance.cc`, SIN `--reset`) para desactivar `WILL-BAT-JM`. En prod esa cuenta está **ACTIVA** y **su saldo no es verificable desde aquí**. Dos salidas posibles:
   - Saldo 0 (lo esperado: la SAC de prod no tiene transacciones) → el backend acepta el PATCH y el log dice `cuenta kg obsoleta desactivada: WILL-BAT-JM`. Verificar en pantalla (Plomo (kg): JM no aparece entre las activas).
   - Saldo ≠ 0 → el backend responde 422, el seeder deja `No se pudo desactivar la cuenta kg 'WILL-BAT-JM'` y **sigue** (no aborta). **Quién decide: Daniel con Johana**, no el operador del deploy. Las opciones son (a) mover ese saldo a la cuenta correcta con un movimiento manual auditado en Plomo (kg) (motivo obligatorio, #75) y re-correr el seeder, o (b) dejarla activa hasta resolver Q-35 (Bogotá). Ninguna de las dos se toma en caliente durante el deploy.
3. Sigue vigente la condición de #100: SAC no opera hasta que el circuito de planta esté corregido; este ciclo no la cambia. Y la condición **C3 de QA (pantalla, testimonio de Daniel)** es condición de deploy, no de commit: lista con `Venta #n` / `Abono #n` y tabs, detalle, liquidar una venta por Total, Create/Edit sin casilla de báscula en material kg.
