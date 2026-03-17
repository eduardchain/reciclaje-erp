import * as XLSX from "xlsx";
import type { AccountStatementExportData } from "@/utils/pdfExport";
import type { BalanceDetailedResponse } from "@/types/reports";
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


const ASSET_ORDER = [
  "cash_and_bank", "inventory_liquidated",
  "customers_receivable", "supplier_advances", "service_provider_advances",
  "liability_advances", "investor_receivable",
  "provision_funds", "prepaid_expenses", "fixed_assets",
];

const LIABILITY_ORDER = [
  "suppliers_payable", "service_provider_payable", "liability_debt",
  "investors_partners", "investors_obligations",
  "investors_legacy", "customer_advances", "provision_obligations",
  "generic_payable",
];

function fmtBal(v: number) {
  return v < 0 ? `(${formatCurrency(Math.abs(v))})` : formatCurrency(v);
}

export function exportBalanceDetailedExcel(data: BalanceDetailedResponse) {
  const rows: (string | number | null)[][] = [];

  rows.push([`Balance Detallado — Corte al: ${formatDate(data.as_of_date)}`]);
  rows.push([]);

  // Activos
  rows.push(["ACTIVOS", "", "", fmtBal(data.total_assets)]);
  rows.push(["Seccion", "Detalle", "Nombre", "Valor"]);

  const pushItems = (items: typeof data.assets[string]["items"], defaultDetail?: (item: typeof items[0]) => string) => {
    for (const item of items) {
      let detail = "";
      if (defaultDetail) {
        detail = defaultDetail(item);
      } else if (item.stock != null && item.avg_cost != null) {
        detail = `${item.code ?? ""} | ${item.stock} kg x ${formatCurrency(item.avg_cost)}`;
      } else if (item.purchase_value != null && item.accumulated_depreciation != null) {
        detail = `Costo: ${formatCurrency(item.purchase_value)} | Dep: ${formatCurrency(item.accumulated_depreciation)}`;
      } else if (item.account_type) {
        detail = item.account_type;
      } else if (item.investor_type) {
        detail = item.investor_type;
      }
      rows.push(["", detail, item.name, fmtBal(item.balance)]);
    }
  };

  for (const key of ASSET_ORDER) {
    const section = data.assets[key];
    if (!section) continue;
    rows.push([section.label, "", "", fmtBal(section.total)]);
    if (section.groups && section.groups.length > 0) {
      for (const group of section.groups) {
        rows.push(["", group.label, "", fmtBal(group.total)]);
        for (const item of group.items) {
          rows.push(["", "", item.name, fmtBal(item.balance)]);
        }
      }
    } else {
      pushItems(section.items);
    }
  }

  rows.push([]);

  // Pasivos
  rows.push(["PASIVOS", "", "", fmtBal(data.total_liabilities)]);
  rows.push(["Seccion", "Detalle", "Nombre", "Valor"]);

  for (const key of LIABILITY_ORDER) {
    const section = data.liabilities[key];
    if (!section) continue;
    rows.push([section.label, "", "", fmtBal(section.total)]);
    if (section.groups && section.groups.length > 0) {
      for (const group of section.groups) {
        rows.push(["", group.label, "", fmtBal(group.total)]);
        for (const item of group.items) {
          rows.push(["", "", item.name, fmtBal(item.balance)]);
        }
      }
    } else {
      pushItems(section.items);
    }
  }

  rows.push([]);

  // Patrimonio
  rows.push(["PATRIMONIO", "", "", fmtBal(data.equity)]);
  rows.push([data.equity_label]);

  rows.push([]);
  rows.push([`Verificacion: ${data.verification.formula} = ${fmtBal(data.verification.result)} ${data.verification.is_balanced ? "OK" : "ERROR"}`]);

  const ws = XLSX.utils.aoa_to_sheet(rows);
  ws["!cols"] = [{ wch: 30 }, { wch: 40 }, { wch: 30 }, { wch: 20 }];

  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, ws, "Balance Detallado");
  XLSX.writeFile(wb, `balance_detallado_${data.as_of_date}.xlsx`);
}
