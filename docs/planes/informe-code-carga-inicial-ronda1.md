# Informe del código — carga inicial de SAC, ronda 1 (corte 31-oct-2026)

Plan: `docs/planes/plan-sac-carga-inicial-ronda1.md`. QA dio GO con tres condiciones (reciclaje-erp-03, sesión d724e9a0).

**Base.** El commit va sobre `develop` c3260fa, pero el plantado y la ronda corrieron con el árbol en `main` 01dfafa. El backend de :8000 levanta desde el árbol, así que la ronda usó el `app/` de main. Que da lo mismo está medido:
- Entre main y develop, `app/` cambia en cuatro archivos: el filtro por bodega del listado de compras y la descripción por lado del cruce entre terceros. El cargador no llama a `/purchases` ni a `/money-movements`. La compra que deriva una entrada pasa por `purchase.create()`, y ese método no cambió.
- Los 76 tests pasan contra el `app/` de develop: lo midió QA con `git archive c3260fa` y yo después del checkout.

Este archivo no lleva cifras ni nombres del cliente. El informe de conciliación con los números reales queda en el scratchpad de la sesión (`ronda1/informe_ronda1.md`), igual que el `.xlsx` exportado del Sheet.

## 1. Qué entra

| Archivo | Estado | sha256 |
|---|---|---|
| `backend/scripts/load_sac_opening.py` | nuevo, 1.546 líneas | `482ab864…68ee6df` |
| `backend/tests/test_load_sac_opening.py` | nuevo, 76 tests | `067dbeb0…e4e50` |
| `backend/scripts/ronda_local.sh` | nuevo | `e686e8cd…e82b6` |
| `backend/scripts/seed_sac_org.py` | flag `--org-vacia` (+39 / −2) | diff `795f74b0…b4239` |
| `docs/planes/plan-sac-carga-inicial-ronda1.md` | nuevo, v1.0 con correcciones en §2, §3, §7 (C3 de QA) y §8 | `97808ad0…2db5862` |

Cero cambios en `app/` y en `frontend/src/`: no aplica golden ni parity check (plan §9). `InboundDetailPage.tsx` y `inventario-preguntas-cliente.md` aparecen modificados en el árbol, pero son de otro trabajo y no entran a este commit.

## 2. Gates

| Gate | Resultado | Artefacto |
|---|---|---|
| Tests del cargador | 76 passed. Corren con `--noconftest` en 1-4 s (son puros), o con el conftest del repo | — |
| `test_reloj_de_negocio.py` (escanea `tests/`) | 15 passed | — |
| ruff | limpio | — |
| Plantado ronda 1, sobre la primera versión | 19/19 en la diagonal | `plantado/plantado_r1b.log`, matriz `377d6b6f…` |
| Plantado ronda 2 (compras por liquidar) | 23/23 | `plantado/plantado_r2b.log`, matriz `88860319…` |
| Plantado ronda 3 (gate y traslados) | 29/29, sobre el archivo final `482ab864…` | `plantado/plantado_r3.log`, matriz `fbaf117f…` |
| Ronda contra la SAC local reseteada | 0 fallas: 462 entidades sin diferencia, 0 saldos sobrantes, los 6 rubros explicados, P&L 0, corte = hoy | `ronda1/ronda1.log`, `ronda1/informe_ronda1.md` |
| Control positivo de la conciliación | libro con +$1.000 en un tercero → 1 falla, exactamente ese tercero, salida 4 | `ronda1/control/` |

Las matrices se congelaron con sha256 antes de plantar, no se commitearon: nada entra al repo antes del GO (plan §8, corregido). Las rutas son relativas al scratchpad de la sesión bc8025bc. Respaldo por ruta y cierre absoluto por sha256 en cada ronda.

## 3. Lo que encontraron los gates, y que el plan no había previsto

1. **Las compras por liquidar se contaban dos veces.** La primera versión mandaba a exclusiones las filas «COMPRAS POR LIQUIDAR» de Inventario y cargaba la bodega bruta. Como la entrada abierta suma su cantidad al liquidarse, el stock quedaba alto justo en esa cantidad.
   - Ahora se descuentan de su bodega.
   - Lo descontado tiene que ser exacto lo que abre la pestaña Entradas, por material y bodega; si no, la carga se detiene.
   - Lo encontró releer el Sheet, cuya nota ya lo decía. Ningún test lo veía.
2. **Lo que viaja y lo que se concilia se calculaban por separado.** `initial_balance` (texto) y `esperado` salían de dos expresiones distintas, y casi todos los tests miraban solo `esperado`. Un signo cambiado en el texto (P17) solo lo habría visto la ronda real. Test de invariante nuevo sobre todo paso con saldo.
3. **El harness de plantado medía el defecto anterior.** P15 y P16 cambian el archivo en el mismo número de caracteres y se escribieron en el mismo segundo. Python validó el `.pyc` por tamaño y mtime, y la corrida de P16 ejecutó el bytecode de P15.
   - Arreglo: se borra el `.pyc` antes de cada corrida y se lanza con `PYTHONDONTWRITEBYTECODE=1`. Las dos rondas se repitieron.
   - Los logs inválidos se conservan renombrados.
4. **Contrato con el backend.** La primera ronda real se cayó en el primer movimiento de kilos: faltaba `description`, y los 55 tests puros pasaban. Test nuevo, `TestContratoConElBackend`: corre las dos fases con un backend falso y valida cada cuerpo contra el schema Pydantic real del endpoint.
   - También exige que el cuerpo no traiga claves que el schema no tenga, porque con `extra` por defecto se pierden sin error.
   - Se verificó plantando el defecto original.
   - Mismo viaje: la tasa de depreciación se manda con 2 decimales, que es lo que guarda `Numeric(5,2)`.
5. **El gate del informe calculaba «Sin explicar» y no lo contaba.** La segunda ronda dio «0 fallas» con dos rubros sin explicar. Ahora suma una falla cada una de estas condiciones:
   - un rubro sin explicar o sin el total de Johana;
   - un cruce que no cuadra;
   - un campo distinto entre el corte y hoy.

   El informe abre con la línea de resultado.
6. **La deuda en plomo se contaba dos veces.** El sistema la muestra dentro de Inventario, pero el informe además la listaba como exclusión que explicaba una diferencia. Las exclusiones ganan `en_el_sistema`:
   - mismo rubro: no explica nada;
   - otro rubro: es un traslado y explica las dos puntas. Es el caso de una caja que el balance lleva como tercero y el sistema como cuenta de dinero.

   Valor nuevo en Terceros, «Ver hoja Cuentas», cruzado contra Cuentas igual que «Ver hoja Créditos».

## 4. Lo que el informe deja visible y decide Daniel

- 40 filas no entran, cada una con su motivo:
  - 6 marcadas «Sí» sin Tipo (G6);
  - las marcadas «Preguntar»;
  - los pasivos marcados «No» (Q-56);
  - los dos inventarios negativos (G5).
- 39 activos se cargan con vida útil provisional, porque el Sheet no trae fecha ni vida (G4, solo en `--ensayo`).
- Inventario cierra con −1 peso de redondeo: costo unitario con 4 decimales, dentro de la tolerancia de 1 peso por rubro.

## 5. Fuera de alcance, para Daniel

- `POST /third-parties/{id}/balance` escribe `current_balance` sin movimiento, con el permiso `third_parties.view_balance`, y rompe el invariante de #55. El frontend no lo usa. El cargador no lo llama, y un test lo fija.
- **Prerrequisito de la carga real (N1 de QA).** `existing_by` del seeder pide `limit=500` y no mira el `total`, así que trunca en silencio. El tope del cargador protege la ronda. Pero la SAC de producción va a pasar de 500 terceros operando, y desde ahí cualquier provisión posterior crearía un segundo «Willard S.A» sin avisar. Las provisiones las corren los runbooks de deploy de SAC. Hay que hacerla fallar fuerte antes de cargar producción.
- **Mensaje más claro (N2 de QA).** Si dos filas de Créditos tienen el mismo acreedor, `_plan_creditos` se queda con la última. El cruce igual falla fuerte, y hoy no hay repetidos: 17 filas, medido en el libro. Un error explícito por acreedor repetido diría mejor qué pasa.

## 6. Qué pedirle a QA

- Leer el diff entero contra `develop`, no este resumen.
- Reproducir el plantado con las tres matrices y `plantar.py`.
- Revisar con atención:
  - el criterio de `en_el_sistema` en `explicar_rubros`;
  - la regla de compras por liquidar (§3 del plan, fila nueva);
  - que `ronda_local.sh` se detenga en la primera falla (`set -euo pipefail`; el seeder sale 3 ante una DECISIÓN PENDIENTE, la conciliación sale 4).
