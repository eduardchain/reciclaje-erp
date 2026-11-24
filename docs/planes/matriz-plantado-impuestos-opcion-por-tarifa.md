# Matriz de plantado: una opción por tarifa en Ventas y Salidas (plan v1.1)

- Se commitea ANTES de plantar y no se reescribe.
- **Árbol medido:** el de la pasada 1. `documentTaxRows.ts` c6a20c48… y `DocumentTaxesCard.tsx` 0c6b9cd0…
- **Por cada P se corren:**
  - U nuevos V1–V9 (`u_tarifa.ts`);
  - U de #136 re-semantizados U1–U22 (`u_casos_136r.ts`);
  - e2e completo a 1440 y 390: E1–E8, E13, E14 (solo 1440) y E15.
- **Cómo se lee cada fila:**
  - «exacta» = cae solo lo predicho;
  - «≥» = vía compartida (`taxTypeOptions`, `optionFor`, `serverKeyOf`): puede caer de más, y lo de más se anota con su causa;
  - la dirección peligrosa es un predicho que NO cae;
  - una E sin ancho cae si falla en algún ancho; `E15@1440` se mide por ancho, y si E15 cae a 390 en P12 o P13 se anota como de más, con su causa.
- **Respaldo y cierre:** respaldo por ruta; cierre por sha de los 2 archivos al final.

| P | Defecto plantado | Tiene que tumbar | Tipo |
|---|---|---|---|
| P1 | volver a colapsar a la general (`taxTypeOptions` de `abb414c`, con la clave por tipo) | V1, V3, E13, E15 (≥: todo lo que usa claves `config_id`) | ≥ |
| P2 | clave por tipo (`taxKey`) cuando el grupo tiene varias tarifas; `config_id` solo si hay una | V1, V6 | ≥ |
| P3 | duplicados en `taxRowsProblems` por `source` en vez de `serverKeyOf` | V4, U11 | exacta |
| P4 | `usedByOthers` por `source` en vez de por clave de servidor | E4 | exacta |
| P5 | rótulo sin el concepto en grupos con varias tarifas | V1, E13 | ≥ (E3, E14 y E15 eligen por rótulo) |
| P6 | huérfana que cae a otra tarifa del tipo (`optionFor` con respaldo por `serverKey`) | V6 | ≥ |
| P7 | general NO primero en su grupo (solo el orden del catálogo) | V8, U2 | exacta |
| P8 | `selectTaxType` con el % de la general del grupo | V3, E13 | ≥ (E14) |
| P9 | `buildTaxPayload` con el concepto de la general del grupo | V3, E13 | ≥ (E14) |
| P10 | ICA agrupada sin el municipio (`serverKey` = tipo) | V7 | ≥ (V5) |
| P11 | `orphanTaxText` buscando solo entre las tarifas usables (QA 1) | V6, U21 (su texto nombra «ReteFuente» y «ICA · Bogotá», dos tarifas inactivas) | exacta |
| P12 | sin la pista de base en las filas 2+ (R6) | E15@1440 | exacta. A 390 NO debe caer: si cae, es de más y se anota la causa |
| P13 | la pista de base de las filas 2+ con la base de la fila 1 (R6) | E15@1440 | exacta. A 390 NO debe caer |
| P14 | `orphanTaxText` sin la rama «ya no está en el catálogo»: vuelve al texto viejo «esa tarifa» (opcional de QA 1) | V9 | exacta |
