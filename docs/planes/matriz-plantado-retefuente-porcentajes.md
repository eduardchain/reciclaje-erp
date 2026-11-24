# Matriz de plantado: impuestos con % libre en Liquidar Entrada

- **Plan:** `plan-sac-retefuente-porcentajes.md` v1.5 (`cb0aff9`), §7.
- **Árbol que se planta:** pasada 1 (patch `2f3684d4`) más el delta C1 (`9f4bc48b`), los dos con GO de QA 1. El sha de cada archivo está en `autor_arbol_c1.log`.
- Esta matriz se commitea ANTES de plantar y no se reescribe. Si una predicción falla, se registra como falló y se explica en el log; no se corrige acá (#105).

## Reglas

- **«Exacta»:** caen esos casos y ningún otro.
- **«≥»:** caen al menos esos, porque el defecto vive en una vía que comparten otros casos.
- Los chequeos de `is_active` y de `base_kind` se plantan una sola vez, en `isUsableConfig`.
- Cada fila se corre sobre el árbol restaurado. Al terminar se cierra con el sha256 de los 10 archivos contra `autor_arbol_c1.log`.

## Casos

| Grupo | Qué son | Dónde viven | Cómo se corren |
|---|---|---|---|
| U1–U29 | casos puros | `~/sac-evidencia/2026-11-23/coder-1-retefuente/u/u_casos.ts` | `u/correr_u.sh` |
| B1–B5 | por HTTP, ids `[1000-desborda]`, `[100.01-fuera]`, `[100-borde]` | `backend/tests/test_tax_rate_tope.py` | `TestB1CompraDirecta::test_retencion`, `TestB2B3Entrada::test_b2_supplier_retentions`, `TestB2B3Entrada::test_b3_purchase_taxes`, `TestB4Venta::test_taxes`, `TestB5SalidaDePlomo::test_taxes` |
| Seeder | ver la lista de abajo | `backend/tests/test_seed_sac_retention_configs.py` | por nombre de test |
| E1–E8 | e2e de Playwright contra :8011/:5181 | evidencia `e2e/` | — |

Casos del seeder:
- «vacío» = `test_catalogo_vacio_crea_las_tres`
- «inactiva» = `test_retefuente_inactiva_no_se_vuelve_a_crear`
- «activa» = `test_activa_no_duplica_ni_revienta`
- «otra grafía» = `test_ica_inactiva_con_otra_grafia_se_reconoce`
- «concepto» = `test_tarifa_con_concepto_no_tapa_a_la_general`
- «otro municipio» = `test_ica_de_otro_municipio_no_tapa_a_barranquilla`
- «dry-run» = `test_dry_run_no_consulta`

## Matriz

| P | Defecto | Debe caer | Tipo |
|---|---|---|---|
| P1 | La precarga toma `cfg.rate_pct` en lugar de la tasa guardada (el código de hoy) | U1, U2, U5, E1. U3 queda verde porque «No declarante» ya tiene 3,5 | exacta |
| P2 | La precarga deja `rate` como string (sin `num()`) | U1, U2, U3, U5 | ≥ |
| P3 | Sin tarifa usable, la fila se descarta (el código de hoy) | U4, U6, U8, E2 | exacta |
| P4 | `pickTypeConfig` no prefiere la general (toma la primera) | U2 | exacta |
| P5 | `pickTypeConfig` ignora el municipio | U5, U6 | exacta |
| P6 | `isUsableConfig` no mira `is_active` | U3, U4, U10, U13, U14, E2, E4, E5, E6 | exacta |
| P7 | `isUsableConfig` no mira `base_kind` | U8, U12 | exacta |
| P8 | El default acepta una tarifa con concepto, conservando la preferencia por la general (nota de QA 1) | U10, U11, E4, E6 | exacta |
| P9 | `newRetRow` con `touched: true` | U9, E3 | exacta |
| P10 | El seeder vuelve al código de hoy (sin lectura previa: solo tolera el 409) | seeder «inactiva», «activa», «otra grafía» | exacta |
| P11 | El seeder compara sin normalizar | seeder «otra grafía» | exacta |
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
| P27 | `PurchaseRetentionCreate.rate` sin `le=100` (el de hoy) | B1 y B2, en `[1000-desborda]` y `[100.01-fuera]`; con 1000 vuelve el 500. B3, B4 y B5 quedan verdes | exacta |
| P28 | `DocumentTaxCreate.rate` sin `le=100` (el de hoy) | B3, B4 y B5, en `[1000-desborda]` y `[100.01-fuera]`. B1 y B2 quedan verdes | exacta |
| P29 | `precargaRetentions` sin el guard de alcance (C1) | U28 | exacta |
| P30 | `reviveDraftRetentions` sin el guard de alcance (C1) | U29 | exacta |

## Notas de las predicciones

**P10.** El plan decía «caso inactiva». Con el desvío 1 aceptado en la pasada 1, el seeder lee el catálogo y omite ANTES del POST tanto la tarifa inactiva como la activa. El test lo exige con «sin POST y sin conflicto».
- El código de hoy no hace esa lectura.
- Con la tarifa activa, el POST sale y el falso da 409. Por eso «activa» cae.
- «Otra grafía» usa una tarifa INACTIVA a propósito: la normalización solo pesa con inactivas, porque con una activa el backend da 409 igual. Sin lectura previa, también cae.

**P11.** Solo cae «otra grafía». En «inactiva» la grafía es idéntica.

**E.** Los e2e cubren E1–E8 a 1440 y 390. Una fila E cae si falla en cualquiera de los dos anchos.
