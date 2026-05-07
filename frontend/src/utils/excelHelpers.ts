import * as XLSX from "xlsx";

export const CURRENCY_FMT = '"$"#,##0;("$"#,##0)';

export function applyCurrencyFormat(ws: XLSX.WorkSheet, currencyCols: number[]) {
  if (!ws["!ref"]) return;
  const range = XLSX.utils.decode_range(ws["!ref"]);
  for (let R = range.s.r; R <= range.e.r; R++) {
    for (const C of currencyCols) {
      const ref = XLSX.utils.encode_cell({ r: R, c: C });
      const cell = ws[ref];
      if (cell && typeof cell.v === "number") {
        cell.t = "n";
        cell.z = CURRENCY_FMT;
      }
    }
  }
}
