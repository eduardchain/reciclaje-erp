import * as XLSX from "xlsx";
import type { AccountStatementExportData } from "@/utils/pdfExport";
import { formatCurrency, formatDate } from "@/utils/formatters";

export function exportAccountStatementExcel(data: AccountStatementExportData) {
  const rows: (string | number | null)[][] = [];

  // Header
  rows.push([`Estado de Cuenta - ${data.thirdPartyName}`]);
  if (data.dateFrom || data.dateTo) {
    rows.push([`Periodo: ${data.dateFrom || "..."} - ${data.dateTo || "..."}`]);
  } else if (data.movements.length > 0) {
    const firstDate = formatDate(data.movements[0].date);
    const lastDate = formatDate(data.movements[data.movements.length - 1].date);
    rows.push([`Periodo: ${firstDate} - ${lastDate}`]);
  }
  rows.push([]);

  // Resumen
  rows.push(["Saldo Actual", "Total Debe", "Total Haber"]);
  rows.push([formatCurrency(data.currentBalance), formatCurrency(data.totalDebit), formatCurrency(data.totalCredit)]);
  rows.push([]);

  // Tabla header
  rows.push(["#", "Fecha", "Tipo", "Descripcion", "Debe", "Haber", "Saldo"]);

  // Saldo de apertura
  if (data.dateFrom) {
    rows.push(["", "", "Saldo de apertura", "", "", "", formatCurrency(data.openingBalance)]);
  }

  // Movimientos
  for (const m of data.movements) {
    const isAnnulled = m.status === "annulled";
    const typeText = isAnnulled ? `${m.typeLabel} (Anulado)` : m.typeLabel;
    rows.push([
      m.movement_number,
      formatDate(m.date),
      typeText,
      m.description || "-",
      m.isDebit ? formatCurrency(m.amount) : "",
      !m.isDebit ? formatCurrency(m.amount) : "",
      m.balance_after != null ? formatCurrency(m.balance_after) : "",
    ]);
  }

  const ws = XLSX.utils.aoa_to_sheet(rows);

  // Column widths
  ws["!cols"] = [
    { wch: 8 },   // #
    { wch: 12 },  // Fecha
    { wch: 28 },  // Tipo
    { wch: 30 },  // Descripcion
    { wch: 16 },  // Debe
    { wch: 16 },  // Haber
    { wch: 16 },  // Saldo
  ];

  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, ws, "Estado de Cuenta");

  const safeName = data.thirdPartyName.replace(/[^a-zA-Z0-9]/g, "_").substring(0, 30);
  XLSX.writeFile(wb, `estado_cuenta_${safeName}.xlsx`);
}
