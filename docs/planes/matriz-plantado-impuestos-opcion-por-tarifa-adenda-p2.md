# Adenda a la matriz de plantado de «una opción por tarifa» (62fb584): P2 y V10

- **Falla de predicción en la dirección peligrosa:** P2 se predijo «tumba V1, V6» y **V6 no cayó** (`plantado/P2_v.log`: «PASS V6», RESUMEN_V 4/9).
  - Causa: P2 cambia la clave solo en grupos con varias tarifas, y V6 desactiva la ReteIVA Ventas. En su catálogo la ReteIVA queda con una tarifa, así que P2 no actúa.
  - V6 mide R4 (la huérfana), no la estabilidad de la clave.
  - El hueco que deja: el primer argumento de R2 («si la clave dependiera de cuántas tarifas tiene el grupo, un cambio en el catálogo cambiaría la clave de una fila ya elegida») no tenía test.
- La matriz 62fb584 NO se reescribe. Esta adenda suma V10 (pedido de QA 1, en las dos direcciones) y su fila.
- **Orden (QA 1):**
  1. esta adenda y el archivo de V10 se commitean ANTES de correrlos;
  2. V10 se corre sobre el árbol limpio, donde tiene que pasar;
  3. se re-planta P2 con V10, que tiene que caer;
  4. cierre por sha y anotación en `plantado.log`.
- **Archivo:** `u/u_tarifa_v10.ts` (sha256 `e95bd8e23c99b5529597ee30139a01979c751cad3c72d26f693af339cd17f87c`), copiado abajo tal cual.

| P | Defecto plantado | Tiene que tumbar | Tipo |
|---|---|---|---|
| P2' | P2 (clave por tipo cuando el grupo tiene varias tarifas; config_id si hay una) | V10a, V10b | exacta (sobre V10) |

```ts
/* V10 (hallazgo del plantado P2, fuera de la matriz 62fb584): R2 — la clave de una fila elegida
 * NO cambia cuando el catálogo gana una segunda tarifa del mismo tipo.
 * Base: V1–V8 de plan-sac-impuestos-opcion-por-tarifa v1.0 §4 — casos puros de utils/documentTaxRows.ts.
 * Cada ok va dentro de un try: una excepción es FAIL del caso, no muerte del arnés. */
import {
  IVA_KEY, buildTaxPayload, createEmptyTax, isOrphanTaxRow, orphanTaxText, selectTaxType, serverKeyOf,
  suggestedTaxAmount, taxRowBase, taxRowsProblems, taxRowsValid, taxTypeOptions, withTaxAmount,
} from "/Users/daniel.chain/Projects/reciclaje-erp-wt/coder-1/frontend/src/utils/documentTaxRows";
import type { TaxFormRow } from "/Users/daniel.chain/Projects/reciclaje-erp-wt/coder-1/frontend/src/utils/documentTaxRows";
import type { RetentionRow } from "/Users/daniel.chain/Projects/reciclaje-erp-wt/coder-1/frontend/src/types/third-party";

type T = "retefuente" | "reteiva" | "ica";
const cfg = (id: string | null, type: T, rate: number, o: { muni?: string; concept?: string; active?: boolean; base?: string } = {}): RetentionRow => ({
  config_id: id, entity_id: null, retention_type: type, municipality: o.muni ?? null,
  concept: o.concept ?? null, rate_pct: rate, base_kind: o.base ?? "subtotal", name: null,
  current_balance: 0, is_active: o.active ?? true,
} as unknown as RetentionRow);

// El catálogo de producción SAC (tarifas_prod.log, solo GET), en su orden
const rf = cfg("95c9625d", "retefuente", 2.5);
const ri2 = cfg("e2971e4d", "reteiva", 2.0);
const riV = cfg("0e3100f9", "reteiva", 15, { concept: "Ventas", base: "iva" });
const icaB = cfg("77f22815", "ica", 0.7, { muni: "Barranquilla" });
const PROD = [rf, ri2, riV, icaB];

let fails = 0;
const ok = (id: string, fn: () => [boolean, unknown]) => {
  let cond = false; let got: unknown;
  try { [cond, got] = fn(); } catch (e) { got = "EXCEPCION " + (e as Error).message; }
  console.log(`${cond ? "PASS" : "FAIL"} ${id}${cond ? "" : "  got=" + JSON.stringify(got)}`);
  if (!cond) fails++;
};
const row = (source: string, rate: number, extra: Partial<TaxFormRow> = {}): TaxFormRow =>
  ({ ...createEmptyTax(), source, rate, ...extra });
const J = (x: unknown) => JSON.stringify(x);

// V10 R2 (QA 1: en las dos direcciones): la clave de una fila elegida NO depende del tamaño de su grupo.
// La clave se toma de la OPCIÓN que ofrece la pantalla en ese momento, no se escribe a mano.
const keyOf = (cat: RetentionRow[], configId: string) => taxTypeOptions(cat).find((o) => o.cfg?.config_id === configId)?.key ?? "";
const sigue = (antes: RetentionRow[], despues: RetentionRow[]): [boolean, unknown] => {
  const L = [1_000_000]; const iva = row(IVA_KEY, 19);
  const ri = selectTaxType(createEmptyTax(), keyOf(antes, "e2971e4d"), antes, 19); const rows = [iva, ri];
  const p = buildTaxPayload(rows, L, 19, despues) ?? []; const r = p.find((x) => x.tax_type === "reteiva");
  return [!!ri.source && !isOrphanTaxRow(ri, despues) && taxRowsValid(rows, L, 19, despues)
    && !!r && r.rate === 2 && r.concept === undefined && r.base_kind === "subtotal" && r.amount === 20_000,
    { ri, p }];
};
// V10a: elegida con UNA ReteIVA; el catálogo crece al de producción (aparece la ReteIVA Ventas)
ok("V10a", () => sigue([rf, ri2], PROD));
// V10b: elegida con las DOS ReteIVA de producción; después se desactiva la Ventas
ok("V10b", () => sigue(PROD, [rf, ri2, cfg("0e3100f9", "reteiva", 15, { concept: "Ventas", base: "iva", active: false }), icaB]));

const TOTAL = 2;
console.log(`RESUMEN_V10: ${TOTAL - fails}/${TOTAL} PASS, ${fails} FAIL`);
process.exit(fails ? 1 : 0);
```
