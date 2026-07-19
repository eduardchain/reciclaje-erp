import * as XLSX from "xlsx";
import type { AccountStatementExportData } from "@/utils/pdfExport";
import type {
  BalanceDetailedResponse,
  ProfitAndLossResponse,
  ProfitAndLossMonthlyResponse,
  CashFlowResponse,
  BalanceSheetResponse,
  PurchaseReportResponse,
  SalesReportResponse,
  MarginAnalysisResponse,
  ThirdPartyBalancesResponse,
  InactiveBalancesResponse,
  ProfitabilityByBUResponse,
  RealCostByMaterialResponse,
  ExpensesReportResponse,
  ExpenseGroupNode,
  ExpenseDetailResponse,
} from "@/types/reports";
import type { StockItem } from "@/types/inventory";
import type { PurchaseResponse } from "@/types/purchase";
import type { SaleResponse } from "@/types/sale";
import type { DoubleEntryResponse } from "@/types/double-entry";
import { formatCurrency, formatDate, formatWeight } from "@/utils/formatters";
import { totalLinesQuantity } from "@/utils/operationLines";
import { applyCurrencyFormat } from "@/utils/excelHelpers";

const docDateOf = (m: { date: string; document_date?: string | null }): string | null =>
  m.document_date && m.document_date.slice(0, 10) !== m.date?.slice(0, 10) ? m.document_date : null;

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
  rows.push([data.currentBalance, data.totalDebit, data.totalCredit]);
  rows.push([]);

  const isOps = data.viewMode === "operations";

  if (isOps) {
    rows.push(["Fecha", "Fecha Doc", "Concepto", "Material", "Peso", "Precio", "Dif Peso", "Debito", "Credito", "Saldo"]);
    if (data.dateFrom) {
      rows.push(["", "", "Saldo de apertura", "", "", "", "", "", "", data.openingBalance]);
    }
    // Build last-in-group set for balance display
    const lastByGroup = new Map<string, number>();
    data.movements.forEach((m, i) => {
      if (m.parent_source_id) lastByGroup.set(m.parent_source_id, i);
    });
    data.movements.forEach((m, idx) => {
      const concepto = m.is_line_item
        ? (m.vehicle_plate || m.invoice_number || `${m.movement_type?.includes("purchase") ? "Compra" : m.movement_type?.includes("sale") ? "Venta" : "DP"} #${m.source_number || ""}`)
        : (m.description || m.vehicle_plate || m.invoice_number || `#${m.source_number || ""}`);
      const diffPesoMoney = m.received_quantity && m.quantity && m.unit_price && m.received_quantity !== m.quantity
        ? (m.received_quantity - m.quantity) * m.unit_price : null;
      // Show balance only on last item of group or non-grouped items
      const showBalance = !m.parent_source_id
        ? m.balance_after != null
        : lastByGroup.get(m.parent_source_id) === idx && m.balance_after != null;
      rows.push([
        formatDate(m.date),
        docDateOf(m) ? formatDate(docDateOf(m)!) : "",
        concepto,
        m.is_line_item && m.material_code ? `${m.material_code} - ${m.material_name || ""}` : "",
        m.is_line_item && m.quantity ? m.quantity : "",
        m.is_line_item && m.unit_price ? m.unit_price : "",
        diffPesoMoney != null ? diffPesoMoney : "",
        m.isDebit ? m.amount : "",
        !m.isDebit ? m.amount : "",
        showBalance ? m.balance_after! : "",
      ]);
    });
  } else {
    rows.push(["#", "Fecha", "Fecha Doc", "Tipo", "Descripcion", "Debe", "Haber", "Saldo"]);
    if (data.dateFrom) {
      rows.push(["", "", "", "Saldo de apertura", "", "", "", data.openingBalance]);
    }
    for (const m of data.movements) {
      const isAnnulled = m.status === "annulled";
      const typeText = isAnnulled ? `${m.typeLabel} (Anulado)` : m.typeLabel;
      rows.push([
        m.movement_number,
        formatDate(m.date),
        docDateOf(m) ? formatDate(docDateOf(m)!) : "",
        typeText,
        m.description || "-",
        m.isDebit ? m.amount : "",
        !m.isDebit ? m.amount : "",
        m.balance_after != null ? m.balance_after : "",
      ]);
    }
  }

  const ws = XLSX.utils.aoa_to_sheet(rows);

  // Column widths
  ws["!cols"] = isOps ? [
    { wch: 12 }, { wch: 12 }, { wch: 18 }, { wch: 25 }, { wch: 12 }, { wch: 14 },
    { wch: 12 }, { wch: 16 }, { wch: 16 }, { wch: 16 },
  ] : [
    { wch: 8 }, { wch: 12 }, { wch: 12 }, { wch: 28 }, { wch: 30 },
    { wch: 16 }, { wch: 16 }, { wch: 16 },
  ];

  // Apply currency format (columnas corridas +1 por "Fecha Doc")
  if (isOps) {
    // Resumen row (cols 0,1,2) + Precio (5), Dif Peso (6), Debito (7), Credito (8), Saldo (9)
    applyCurrencyFormat(ws, [0, 1, 2, 5, 6, 7, 8, 9]);
  } else {
    // Resumen (0,1,2) + Debe (5), Haber (6), Saldo (7)
    applyCurrencyFormat(ws, [0, 1, 2, 5, 6, 7]);
  }

  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, ws, "Estado de Cuenta");

  const safeName = data.thirdPartyName.replace(/[^a-zA-Z0-9]/g, "_").substring(0, 30);
  XLSX.writeFile(wb, `estado_cuenta_${safeName}.xlsx`);
}


const ASSET_ORDER = [
  "cash_and_bank", "inventory_liquidated",
  "customers_receivable", "supplier_advances", "service_provider_advances",
  "liability_advances", "investor_receivable", "loans_receivable",
  "provision_funds", "prepaid_expenses", "fixed_assets",
];

const LIABILITY_ORDER = [
  "suppliers_payable", "service_provider_payable", "liability_debt",
  "investors_partners", "investors_obligations",
  "investors_legacy", "customer_advances", "provision_obligations",
  "generic_payable",
];

export function exportBalanceDetailedExcel(data: BalanceDetailedResponse, filtersLabel?: string) {
  const rows: (string | number | null)[][] = [];

  rows.push([`Balance Detallado — Corte al: ${formatDate(data.as_of_date)}`]);
  if (filtersLabel) rows.push([filtersLabel]);
  rows.push([]);

  // Activos
  rows.push(["ACTIVOS", "", "", data.total_assets]);
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
      rows.push(["", detail, item.is_inactive ? `${item.name} (inactivo)` : item.name, item.balance]);
    }
  };

  const pushHiddenNote = (count?: number, total?: number) => {
    if (!count || count <= 0) return;
    const totalStr = total != null && total !== 0 ? ` (suma: ${formatCurrency(total)})` : "";
    rows.push(["", "", `${count} ${count === 1 ? "item" : "items"} por debajo del umbral no mostrado${count === 1 ? "" : "s"}${totalStr}`, null]);
  };

  const pushSection = (section: BalanceDetailedResponse["assets"][string]) => {
    rows.push([section.label, "", "", section.total]);
    if (section.groups && section.groups.length > 0) {
      for (const group of section.groups) {
        rows.push(["", group.label, "", group.total]);
        for (const item of group.items) {
          rows.push(["", "", item.is_inactive ? `${item.name} (inactivo)` : item.name, item.balance]);
        }
        pushHiddenNote(group.hidden_count, group.hidden_total);
      }
      // Items ocultos por grupos enteramente saltados (delta vs notas por-grupo)
      const groupsHiddenCount = section.groups.reduce((sum, g) => sum + (g.hidden_count ?? 0), 0);
      const groupsHiddenTotal = section.groups.reduce((sum, g) => sum + (g.hidden_total ?? 0), 0);
      pushHiddenNote((section.hidden_count ?? 0) - groupsHiddenCount, (section.hidden_total ?? 0) - groupsHiddenTotal);
    } else {
      pushItems(section.items);
      pushHiddenNote(section.hidden_count, section.hidden_total);
    }
  };

  for (const key of ASSET_ORDER) {
    const section = data.assets[key];
    if (!section) continue;
    pushSection(section);
  }

  rows.push([]);

  // Pasivos
  rows.push(["PASIVOS", "", "", data.total_liabilities]);
  rows.push(["Seccion", "Detalle", "Nombre", "Valor"]);

  for (const key of LIABILITY_ORDER) {
    const section = data.liabilities[key];
    if (!section) continue;
    pushSection(section);
  }

  rows.push([]);

  // Patrimonio
  rows.push(["PATRIMONIO", "", "", data.equity]);
  rows.push([data.equity_label]);

  rows.push([]);
  rows.push([`Verificacion: ${data.verification.formula} = ${formatCurrency(data.verification.result)} ${data.verification.is_balanced ? "OK" : "ERROR"}`]);

  const ws = XLSX.utils.aoa_to_sheet(rows);
  ws["!cols"] = [{ wch: 30 }, { wch: 40 }, { wch: 30 }, { wch: 20 }];

  // Valor column (3) is currency
  applyCurrencyFormat(ws, [3]);

  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, ws, "Balance Detallado");
  XLSX.writeFile(wb, `balance_detallado_${data.as_of_date}.xlsx`);
}


export function exportProfitabilityBUExcel(data: ProfitabilityByBUResponse) {
  const rows: (string | number | null)[][] = [];

  rows.push(["Rentabilidad por Unidad de Negocio"]);
  rows.push([`Periodo: ${data.period_from} - ${data.period_to}`]);
  rows.push([]);

  // Header
  rows.push(["Unidad de Negocio", "Compras", "Peso %", "Ventas", "COGS", "Ut. Bruta", "G. Directos", "G. Compartidos", "G. Generales", "Comisiones", "Ut. Neta", "Margen %"]);

  // UNs
  for (const bu of data.business_units) {
    rows.push([
      bu.business_unit_name, bu.purchases_total, `${bu.purchases_weight_pct.toFixed(1)}%`,
      bu.sales_revenue, bu.sales_cogs,
      bu.total_gross_profit, bu.direct_expenses, bu.shared_expenses,
      bu.general_expenses, bu.sale_commissions, bu.net_profit,
      `${bu.net_margin.toFixed(1)}%`,
    ]);
    // Desglose directos
    for (const d of bu.direct_expenses_detail) {
      rows.push(["  " + d.category_name, "", "", "", d.amount, "", "", "", "", ""]);
    }
  }

  // Totales (solo bodega)
  rows.push([]);
  const t = data.totals;
  rows.push([
    "TOTAL BODEGA", t.purchases_total, "100%",
    t.sales_revenue, t.sales_cogs, t.total_gross_profit,
    t.direct_expenses, t.shared_expenses, t.general_expenses,
    t.sale_commissions, t.net_profit, `${t.net_margin.toFixed(1)}%`,
  ]);

  // Seccion Pasa Mano (doble partida) — logica propia
  const de = data.double_entry;
  rows.push([]);
  rows.push([`${de.label} (Doble Partida)`]);
  rows.push(["Ventas Pasa Mano", de.sales_total]);
  rows.push(["Compras Pasa Mano", de.purchases_total]);
  rows.push(["Margen Bruto", de.gross_profit]);
  rows.push(["Comisiones y Cargos", -de.commissions]);
  rows.push(["Gastos Directos", -de.direct_expenses]);
  for (const d of de.direct_expenses_detail) {
    rows.push(["  " + d.category_name, -d.amount]);
  }
  rows.push(["Gastos Generales asignados (% por categoria)", -de.general_expenses]);
  for (const d of de.general_expenses_detail) {
    rows.push([`  ${d.category_name} (${d.pct.toFixed(1)}%)`, -d.amount]);
  }
  rows.push(["Utilidad Neta Pasa Mano", de.net_profit, `${de.net_margin.toFixed(1)}%`]);
  rows.push([]);
  rows.push(["TOTAL GENERAL (Bodega + Pasa Mano)", data.grand_total_net]);

  // Conciliacion con P&L: lineas no atribuibles a UN
  const rec = data.pnl_reconciliation;
  rows.push([]);
  rows.push(["Conciliacion con Estado de Resultados"]);
  rows.push(["Ingresos por Servicios", rec.service_income]);
  rows.push(["Ingresos Financieros (Intereses)", rec.interest_income ?? 0]);
  rows.push(["Transformaciones (neto)", rec.transformation_net]);
  rows.push(["Ajustes de Inventario (neto)", rec.inventory_adjustment_net]);
  rows.push(["Ajustes de Terceros (neto)", rec.tp_adjustment_net]);
  rows.push(["Ajuste Costo por Sobreventa y Reversiones", rec.oversell_cost_adjustment]);
  rows.push(["= Utilidad Neta P&L", rec.pnl_net_profit]);

  const ws = XLSX.utils.aoa_to_sheet(rows);
  ws["!cols"] = [{ wch: 32 }, { wch: 15 }, { wch: 15 }, { wch: 15 }, { wch: 15 }, { wch: 15 }, { wch: 15 }, { wch: 15 }, { wch: 15 }, { wch: 10 }];

  // Currency cols: 1, 3, 4, 5, 6, 7, 8, 9, 10
  applyCurrencyFormat(ws, [1, 3, 4, 5, 6, 7, 8, 9, 10]);

  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, ws, "Rentabilidad UN");
  XLSX.writeFile(wb, `rentabilidad_un_${data.period_from}_${data.period_to}.xlsx`);
}


export function exportExpensesReportExcel(data: ExpensesReportResponse) {
  const rows: (string | number | null)[][] = [];

  rows.push(["Reporte de Gastos"]);
  rows.push([`Periodo: ${data.period_from} - ${data.period_to}`]);
  rows.push([`Agrupacion: ${data.group_by}`]);
  rows.push([]);
  rows.push(["Total", data.total]);
  rows.push(["Directos", data.total_direct]);
  rows.push(["Compartidos", data.total_shared]);
  rows.push(["Generales", data.total_general]);
  rows.push(["Movimientos", data.movement_count]);
  rows.push([]);
  rows.push(["Grupo", "Total"]);

  const flatten = (nodes: ExpenseGroupNode[], depth: number) => {
    for (const n of nodes) {
      const indent = "  ".repeat(depth);
      rows.push([indent + n.label, n.total]);
      if (n.children && n.children.length > 0) {
        flatten(n.children, depth + 1);
      }
    }
  };
  flatten(data.groups, 0);

  const ws = XLSX.utils.aoa_to_sheet(rows);
  ws["!cols"] = [{ wch: 45 }, { wch: 18 }];

  applyCurrencyFormat(ws, [1]);

  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, ws, "Gastos");
  XLSX.writeFile(wb, `gastos_${data.period_from}_${data.period_to}.xlsx`);
}


export function exportExpensesFlatExcel(
  data: ExpenseDetailResponse,
  periodFrom: string,
  periodTo: string,
  context?: { buLabel?: string; catLabel?: string },
) {
  const ALLOC_LABEL: Record<string, string> = {
    direct: "Directo",
    shared: "Compartido",
    general: "General",
  };
  const rows: (string | number | null)[][] = [];

  rows.push(["Reporte de Gastos - Detalle"]);
  rows.push([`Periodo: ${periodFrom} - ${periodTo}`]);
  if (context?.buLabel) rows.push([`UN: ${context.buLabel}`]);
  if (context?.catLabel) rows.push([`Categoria: ${context.catLabel}`]);
  rows.push([]);
  rows.push(["Total movimientos", data.total_count]);
  rows.push(["Total asignado", data.total_allocated]);
  rows.push([]);
  rows.push(["Fecha", "#", "Tipo", "Tercero", "UN", "Categoria", "Descripcion", "Monto Original", "Asignado", "Asignacion"]);

  for (const item of data.items) {
    rows.push([
      formatDate(item.date),
      item.movement_number,
      item.movement_type,
      item.third_party_name ?? "—",
      item.business_unit_name ?? "Sin Asignar",
      item.expense_category_name ?? "Sin Categoria",
      item.description ?? "",
      item.amount,
      item.allocated_amount,
      ALLOC_LABEL[item.allocation_type] ?? item.allocation_type,
    ]);
  }

  const ws = XLSX.utils.aoa_to_sheet(rows);
  ws["!cols"] = [
    { wch: 12 }, // Fecha
    { wch: 8 },  // #
    { wch: 22 }, // Tipo
    { wch: 28 }, // Tercero
    { wch: 18 }, // UN
    { wch: 24 }, // Categoria
    { wch: 40 }, // Descripcion
    { wch: 16 }, // Monto Original
    { wch: 16 }, // Asignado
    { wch: 14 }, // Asignacion
  ];

  // Columnas Monto Original + Asignado
  applyCurrencyFormat(ws, [7, 8]);

  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, ws, "Gastos detalle");
  XLSX.writeFile(wb, `gastos_detalle_${periodFrom}_${periodTo}.xlsx`);
}


export function exportRealCostMaterialExcel(data: RealCostByMaterialResponse) {
  const rows: (string | number | null)[][] = [];

  rows.push(["Costo Real por Material"]);
  rows.push([`Periodo: ${data.period_from} - ${data.period_to}`]);
  rows.push([]);

  for (const bu of data.business_units) {
    rows.push([bu.business_unit_name, `Gastos: ${formatCurrency(bu.total_expenses)}`, `Kg: ${bu.kg_purchased.toLocaleString()}`, `Overhead: ${formatCurrency(bu.overhead_rate)}/kg`]);
    rows.push(["Codigo", "Material", "Costo Promedio", "Overhead", "Costo Real"]);
    for (const m of bu.materials) {
      rows.push([m.material_code, m.material_name, m.average_cost, m.overhead_rate, m.real_cost]);
    }
    rows.push([]);
  }

  const ws = XLSX.utils.aoa_to_sheet(rows);
  ws["!cols"] = [{ wch: 15 }, { wch: 25 }, { wch: 18 }, { wch: 15 }, { wch: 15 }];

  // Currency cols: 2, 3, 4
  applyCurrencyFormat(ws, [2, 3, 4]);

  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, ws, "Costo Real");
  XLSX.writeFile(wb, `costo_real_material_${data.period_from}_${data.period_to}.xlsx`);
}


export function exportPnlExcel(data: ProfitAndLossResponse) {
  const rows: (string | number)[][] = [];
  rows.push(["Estado de Resultados"]);
  rows.push([`Periodo: ${data.period_from} - ${data.period_to}`]);
  rows.push([]);
  rows.push(["Concepto", "Valor"]);
  rows.push(["Ingresos por Ventas", data.sales_revenue]);
  rows.push(["Costo de Ventas (COGS)", data.cost_of_goods_sold]);
  rows.push(["Utilidad Bruta Ventas", data.gross_profit_sales]);
  rows.push(["Ingresos por Servicios", data.service_income]);
  rows.push(["Utilidad Pasa Mano", data.double_entry_profit]);
  if (data.transformation_profit !== 0) rows.push(["Gan/Perd Transformaciones", data.transformation_profit]);
  if (data.waste_loss > 0) rows.push(["Perdida por Merma", -data.waste_loss]);
  if (data.adjustment_net !== 0) rows.push(["Ajustes de Inventario", data.adjustment_net]);
  if (data.oversell_cost_adjustment !== 0) rows.push(["Ajuste Costo por Sobreventa y Reversiones", data.oversell_cost_adjustment]);
  if (data.tp_adjustment_gain > 0) rows.push(["+ Ganancia Ajuste Terceros", data.tp_adjustment_gain]);
  if (data.tp_adjustment_loss > 0) rows.push(["- Perdida Ajuste Terceros", -data.tp_adjustment_loss]);
  // GAP-1 QA: subtotal bruto SIN intereses — la cascada suma leyendo de arriba abajo
  rows.push(["Utilidad Bruta Total", data.gross_profit_before_financial]);
  rows.push([]);
  rows.push(["Comisiones y Cargos (Ventas)", data.commissions_paid_sales]);
  rows.push(["Comisiones y Cargos (Pasa Mano)", data.commissions_paid_dp]);
  // Rubros de gasto: una linea por rubro, SIN desglose por fuente ni categoria
  // (el detalle por categoria vive en el Reporte de Gastos). Paridad pantalla/Excel (#51).
  rows.push(["Gastos Operativos", data.expenses_operating]);
  if (data.expenses_depreciation !== 0) rows.push(["Depreciación de Activos", data.expenses_depreciation]);
  rows.push(["Utilidad Operacional", data.operating_result]);
  if ((data.interest_income ?? 0) !== 0) rows.push(["Ingresos Financieros (Intereses)", data.interest_income]);
  if (data.expenses_financial !== 0) rows.push(["Gastos Financieros", data.expenses_financial]);
  rows.push([]);
  rows.push(["Utilidad Neta", data.net_profit]);
  rows.push(["Margen Neto", `${data.net_margin.toFixed(1)}%`]);

  const ws = XLSX.utils.aoa_to_sheet(rows);
  ws["!cols"] = [{ wch: 35 }, { wch: 20 }];

  // Valor column (1) is currency
  applyCurrencyFormat(ws, [1]);

  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, ws, "P&L");
  XLSX.writeFile(wb, `estado_resultados_${data.period_from}_${data.period_to}.xlsx`);
}


export function exportPnlMonthlyExcel(
  data: ProfitAndLossMonthlyResponse,
  _rows: unknown[] = [],
) {
  // Decision #50: filas = lineas P&L, columnas = meses + Total. Numeros como
  // number (sumables en Excel) con currency format aplicado.
  const periodLabels = data.periods.map((p) => p.label);
  const header = ["Linea", ...periodLabels, "Total"];

  const rows: (string | number)[][] = [];
  rows.push(["Estado de Resultados — Mensual"]);
  rows.push([`Rango: ${data.range_from} – ${data.range_to}`]);
  rows.push([`Cutoff day: ${data.cutoff_day}`]);
  rows.push([]);
  rows.push(header);

  const pushRow = (label: string, getter: (p: { [k: string]: number }) => number, opts: { prefix?: "-"; bold?: boolean; indent?: boolean } = {}) => {
    const sign = opts.prefix === "-" ? -1 : 1;
    const cells: (string | number)[] = [opts.indent ? `  ${label}` : label];
    for (const p of data.periods) cells.push(sign * getter(p as unknown as Record<string, number>));
    cells.push(sign * getter(data.totals as unknown as Record<string, number>));
    rows.push(cells);
  };

  pushRow("Ingresos por Ventas", (p) => p.sales_revenue);
  pushRow("Costo de Ventas (COGS)", (p) => p.cost_of_goods_sold, { prefix: "-" });
  pushRow("Utilidad Bruta Ventas", (p) => p.gross_profit_sales, { bold: true });
  pushRow("Ingresos por Servicios", (p) => p.service_income);
  pushRow("Utilidad Pasa Mano", (p) => p.double_entry_profit);

  if (data.periods.some((p) => Math.abs(p.transformation_profit) > 0.01) || Math.abs(data.totals.transformation_profit) > 0.01) {
    pushRow("Ganancia/Perdida Transformaciones", (p) => p.transformation_profit);
  }
  if (data.periods.some((p) => p.waste_loss > 0) || data.totals.waste_loss > 0) {
    pushRow("Perdida por Merma", (p) => p.waste_loss, { prefix: "-" });
  }
  if (data.periods.some((p) => Math.abs(p.adjustment_net) > 0.01) || Math.abs(data.totals.adjustment_net) > 0.01) {
    pushRow("Ajustes de Inventario", (p) => p.adjustment_net);
  }
  if (data.periods.some((p) => Math.abs(p.oversell_cost_adjustment) > 0.01) || Math.abs(data.totals.oversell_cost_adjustment) > 0.01) {
    pushRow("Ajuste Costo por Sobreventa y Reversiones", (p) => p.oversell_cost_adjustment);
  }
  if (data.periods.some((p) => p.tp_adjustment_gain > 0) || data.totals.tp_adjustment_gain > 0) {
    pushRow("+ Ganancia Ajuste Terceros", (p) => p.tp_adjustment_gain);
  }
  if (data.periods.some((p) => p.tp_adjustment_loss > 0) || data.totals.tp_adjustment_loss > 0) {
    pushRow("- Perdida Ajuste Terceros", (p) => p.tp_adjustment_loss, { prefix: "-" });
  }

  // GAP-1 QA: subtotal bruto SIN intereses (mismo campo que el tab Periodo)
  pushRow("Utilidad Bruta Total", (p) => p.gross_profit_before_financial, { bold: true });

  // Comisiones — linea propia entre bruta y gastos (D2)
  pushRow("Comisiones y Cargos (Ventas)", (p) => p.commissions_paid_sales, { prefix: "-" });
  pushRow("Comisiones y Cargos (Pasa Mano)", (p) => p.commissions_paid_dp, { prefix: "-" });

  // Rubros de gasto: una linea por rubro, SIN desglose por fuente ni categoria
  // (el detalle por categoria vive en el Reporte de Gastos). Paridad pantalla/Excel (#51).
  pushRow("Gastos Operativos", (p) => p.expenses_operating, { prefix: "-" });
  if (data.periods.some((p) => p.expenses_depreciation !== 0) || data.totals.expenses_depreciation !== 0) {
    pushRow("Depreciación de Activos", (p) => p.expenses_depreciation, { prefix: "-" });
  }

  pushRow("Utilidad Operacional", (p) => p.operating_result, { bold: true });

  // Ingresos Financieros — unica aparicion, despues de Utilidad Operacional (GAP-1)
  if (data.periods.some((p) => Math.abs(p.interest_income ?? 0) > 0.01) || Math.abs(data.totals.interest_income ?? 0) > 0.01) {
    pushRow("Ingresos Financieros (Intereses)", (p) => p.interest_income ?? 0);
  }

  if (data.periods.some((p) => p.expenses_financial !== 0) || data.totals.expenses_financial !== 0) {
    pushRow("Gastos Financieros", (p) => p.expenses_financial, { prefix: "-" });
  }

  pushRow("Utilidad Neta", (p) => p.net_profit, { bold: true });

  const ws = XLSX.utils.aoa_to_sheet(rows);
  const labelWidth = 36;
  const periodWidth = 18;
  ws["!cols"] = [
    { wch: labelWidth },
    ...periodLabels.map(() => ({ wch: periodWidth })),
    { wch: periodWidth },
  ];

  // Currency format en todas las columnas de valores (1..N+1).
  const valueCols: number[] = [];
  for (let i = 1; i <= data.periods.length + 1; i++) valueCols.push(i);
  applyCurrencyFormat(ws, valueCols);

  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, ws, "P&L Mensual");
  XLSX.writeFile(wb, `estado_resultados_mensual_${data.range_from}_${data.range_to}.xlsx`);
}


export function exportCashFlowExcel(data: CashFlowResponse) {
  const rows: (string | number)[][] = [];
  rows.push(["Flujo de Caja"]);
  rows.push([`Periodo: ${data.period_from} - ${data.period_to}`]);
  rows.push([]);
  rows.push(["Saldo Inicial", data.opening_balance]);
  rows.push([]);
  rows.push(["INGRESOS", ""]);
  rows.push(["Cobros a Clientes (Tesoreria)", data.inflows.customer_collections]);
  rows.push(["Ingresos por Servicios", data.inflows.service_income]);
  rows.push(["Aportes de Capital", data.inflows.capital_injections]);
  if (data.inflows.advance_collections > 0) rows.push(["Anticipos de Clientes", data.inflows.advance_collections]);
  if (data.inflows.generic_collections > 0) rows.push(["Cobros Genericos", data.inflows.generic_collections]);
  if (data.inflows.asset_devaluation_collections > 0) rows.push(["Devaluacion de Activos (Reembolso)", data.inflows.asset_devaluation_collections]);
  if ((data.inflows.obligation_disbursements ?? 0) > 0) rows.push(["Desembolsos de Obligaciones", data.inflows.obligation_disbursements]);
  if ((data.inflows.loan_interest_collections ?? 0) > 0) rows.push(["Recaudo Intereses Prestamos", data.inflows.loan_interest_collections]);
  if ((data.inflows.loan_capital_collections ?? 0) > 0) rows.push(["Recaudo Capital Prestamos", data.inflows.loan_capital_collections]);
  rows.push(["Total Ingresos", data.total_inflows]);
  rows.push([]);
  rows.push(["EGRESOS", ""]);
  rows.push(["Pagos a Proveedores (Tesoreria)", data.outflows.supplier_payments]);
  rows.push(["Gastos", data.outflows.expenses]);
  rows.push(["Comisiones", data.outflows.commission_payments]);
  rows.push(["Devolucion de Capital", data.outflows.capital_returns]);
  if (data.outflows.provision_deposits > 0) rows.push(["Depositos a Provisiones", data.outflows.provision_deposits]);
  if (data.outflows.deferred_fundings > 0) rows.push(["Gastos Diferidos", data.outflows.deferred_fundings]);
  if (data.outflows.advance_payments > 0) rows.push(["Anticipos a Proveedores", data.outflows.advance_payments]);
  if (data.outflows.asset_payments > 0) rows.push(["Activos Fijos", data.outflows.asset_payments]);
  if (data.outflows.generic_payments > 0) rows.push(["Pagos Genericos", data.outflows.generic_payments]);
  if ((data.outflows.loan_disbursements ?? 0) > 0) rows.push(["Prestamos Otorgados", data.outflows.loan_disbursements]);
  if ((data.outflows.obligation_interest_payments ?? 0) > 0) rows.push(["Pago Intereses Obligaciones", data.outflows.obligation_interest_payments]);
  if ((data.outflows.obligation_capital_payments ?? 0) > 0) rows.push(["Abonos Capital Obligaciones", data.outflows.obligation_capital_payments]);
  rows.push(["Total Egresos", data.total_outflows]);
  rows.push([]);
  rows.push(["Flujo Neto", data.net_flow]);
  rows.push(["Saldo Final", data.closing_balance]);

  const ws = XLSX.utils.aoa_to_sheet(rows);
  ws["!cols"] = [{ wch: 35 }, { wch: 20 }];

  // Valor column (1) is currency
  applyCurrencyFormat(ws, [1]);

  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, ws, "Flujo Caja");
  XLSX.writeFile(wb, `flujo_caja_${data.period_from}_${data.period_to}.xlsx`);
}


export function exportBalanceSheetExcel(data: BalanceSheetResponse) {
  const rows: (string | number)[][] = [];
  rows.push(["Balance General"]);
  rows.push([`Fecha: ${data.as_of_date}`]);
  rows.push([]);
  rows.push(["ACTIVOS", ""]);
  rows.push(["Efectivo y Bancos", data.assets.cash_and_bank]);
  rows.push(["Cuentas por Cobrar", data.assets.accounts_receivable]);
  rows.push(["Inventario", data.assets.inventory]);
  rows.push(["Anticipos", data.assets.advances]);
  if (data.assets.investor_receivable > 0) rows.push(["CxC Inversionistas", data.assets.investor_receivable]);
  if (data.assets.loans_receivable > 0) rows.push(["Préstamos por Cobrar", data.assets.loans_receivable]);
  if (data.assets.prepaid_expenses > 0) rows.push(["Gastos Prepagados", data.assets.prepaid_expenses]);
  if (data.assets.provision_funds > 0) rows.push(["Fondos Provision", data.assets.provision_funds]);
  if (data.assets.fixed_assets > 0) rows.push(["Activos Fijos", data.assets.fixed_assets]);
  rows.push(["Total Activos", data.total_assets]);
  rows.push([]);
  rows.push(["PASIVOS", ""]);
  rows.push(["Cuentas por Pagar", data.liabilities.accounts_payable]);
  rows.push(["Deuda Inversionistas", data.liabilities.investor_debt]);
  if (data.liabilities.obligations_payable > 0) rows.push(["Obligaciones Financieras", data.liabilities.obligations_payable]);
  if (data.liabilities.liability_debt > 0) rows.push(["Pasivos", data.liabilities.liability_debt]);
  if (data.liabilities.customer_advances > 0) rows.push(["Anticipos Clientes", data.liabilities.customer_advances]);
  if (data.liabilities.provision_obligations > 0) rows.push(["Obligaciones Provision", data.liabilities.provision_obligations]);
  rows.push(["Total Pasivos", data.total_liabilities]);
  rows.push([]);
  rows.push(["PATRIMONIO", ""]);
  rows.push(["Patrimonio", data.equity]);
  rows.push(["Utilidad Acumulada", data.accumulated_profit]);
  rows.push(["Utilidad Distribuida", data.distributed_profit]);

  const ws = XLSX.utils.aoa_to_sheet(rows);
  ws["!cols"] = [{ wch: 30 }, { wch: 20 }];

  // Valor column (1) is currency
  applyCurrencyFormat(ws, [1]);

  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, ws, "Balance General");
  XLSX.writeFile(wb, `balance_general_${data.as_of_date}.xlsx`);
}


export function exportPurchaseReportExcel(data: PurchaseReportResponse, dpFilterLabel: string = "Todas") {
  const rows: (string | number)[][] = [];
  rows.push(["Reporte de Compras"]);
  rows.push([`Periodo: ${data.period_from} - ${data.period_to}`]);
  rows.push([`Operaciones: ${dpFilterLabel}`]);
  rows.push([]);
  rows.push(["Total Compras", data.total_amount]);
  rows.push(["Operaciones", data.purchase_count]);
  rows.push(["Kg Totales", data.total_quantity]);
  rows.push(["Promedio por Compra", data.average_per_purchase]);
  rows.push([]);
  rows.push(["POR PROVEEDOR", "", "", ""]);
  rows.push(["Proveedor", "Total", "Cantidad", "# Compras"]);
  for (const s of data.by_supplier) {
    rows.push([s.supplier_name, s.total_amount, s.total_quantity, s.purchase_count]);
  }
  rows.push([]);
  rows.push(["POR MATERIAL", "", "", ""]);
  rows.push(["Material", "Total", "Cantidad", "Precio Promedio"]);
  for (const m of data.by_material) {
    rows.push([`${m.material_code} - ${m.material_name}`, m.total_amount, m.total_quantity, m.average_unit_price]);
  }

  const ws = XLSX.utils.aoa_to_sheet(rows);
  ws["!cols"] = [{ wch: 30 }, { wch: 18 }, { wch: 15 }, { wch: 18 }];

  // Currency cols: 1 (Total), 3 (Precio Promedio in by_material section)
  applyCurrencyFormat(ws, [1, 3]);

  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, ws, "Compras");
  XLSX.writeFile(wb, `reporte_compras_${data.period_from}_${data.period_to}.xlsx`);
}


export function exportSalesReportExcel(data: SalesReportResponse, dpFilterLabel: string = "Todas") {
  const rows: (string | number)[][] = [];
  rows.push(["Reporte de Ventas"]);
  rows.push([`Periodo: ${data.period_from} - ${data.period_to}`]);
  rows.push([`Operaciones: ${dpFilterLabel}`]);
  rows.push([]);
  rows.push(["Total Ventas", data.total_revenue]);
  rows.push(["Costo", data.total_cost]);
  rows.push(["Utilidad Bruta", data.total_profit]);
  rows.push(["Margen Bruto", `${data.overall_margin.toFixed(1)}%`]);
  rows.push(["Operaciones", data.sale_count]);
  rows.push([]);
  rows.push(["POR CLIENTE", "", "", "", ""]);
  rows.push(["Cliente", "Total", "Cantidad", "# Ventas", "Ut. Bruta"]);
  for (const c of data.by_customer) {
    rows.push([c.customer_name, c.total_amount, c.total_quantity, c.sale_count, c.total_profit]);
  }
  rows.push([]);
  rows.push(["POR MATERIAL", "", "", "", ""]);
  rows.push(["Material", "Ventas", "Costo", "Ut. Bruta", "Margen Bruto"]);
  for (const m of data.by_material) {
    rows.push([`${m.material_code} - ${m.material_name}`, m.total_amount, m.total_cost, m.total_profit, `${m.margin_percentage.toFixed(1)}%`]);
  }

  const ws = XLSX.utils.aoa_to_sheet(rows);
  ws["!cols"] = [{ wch: 30 }, { wch: 18 }, { wch: 18 }, { wch: 18 }, { wch: 12 }];

  // Currency cols: 1, 2, 3, 4 — all numeric data cells; helper checks `typeof v === 'number'` so non-money numbers (count, qty) are also formatted as currency.
  // To avoid that, only apply to cells we know are money: col 1 (Total/Ventas), col 4 (Utilidad in by_customer/Margen in by_material — last is %).
  // Apply to col 1, 2, 3; col 4 is mixed (number Utilidad in by_customer, string % in by_material) — helper safely skips strings.
  applyCurrencyFormat(ws, [1, 2, 3, 4]);

  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, ws, "Ventas");
  XLSX.writeFile(wb, `reporte_ventas_${data.period_from}_${data.period_to}.xlsx`);
}


export function exportMarginAnalysisExcel(data: MarginAnalysisResponse) {
  const rows: (string | number)[][] = [];
  rows.push(["Analisis de Margenes"]);
  rows.push([`Periodo: ${data.period_from} - ${data.period_to}`]);
  rows.push([`Margen Global: ${data.overall_margin.toFixed(1)}%`]);
  rows.push([]);
  rows.push(["Codigo", "Material", "Categoria", "Kg Compra", "$ Compra", "Precio Compra", "Kg Venta", "$ Venta", "Precio Venta", "Utilidad", "Margen %"]);
  for (const m of data.materials) {
    rows.push([
      m.material_code, m.material_name, m.category_name || "-",
      m.total_purchased_qty, m.total_purchased_amount, m.avg_purchase_price,
      m.total_sold_qty, m.total_sold_revenue, m.avg_sale_price,
      m.gross_profit, `${m.margin_percentage.toFixed(1)}%`,
    ]);
  }

  const ws = XLSX.utils.aoa_to_sheet(rows);
  ws["!cols"] = [{ wch: 10 }, { wch: 20 }, { wch: 15 }, { wch: 12 }, { wch: 15 }, { wch: 15 }, { wch: 12 }, { wch: 15 }, { wch: 15 }, { wch: 15 }, { wch: 10 }];

  // Currency cols: 4 ($ Compra), 5 (Precio Compra), 7 ($ Venta), 8 (Precio Venta), 9 (Utilidad)
  applyCurrencyFormat(ws, [4, 5, 7, 8, 9]);

  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, ws, "Margenes");
  XLSX.writeFile(wb, `margenes_${data.period_from}_${data.period_to}.xlsx`);
}


export function exportStockExcel(
  items: StockItem[],
  canViewValues: boolean,
  // SAC: kg de plomo que representa el stock (formula vigente) — paridad con
  // la columna en pantalla. Solo materiales con formula; undefined = sin columna
  kgLeadByMaterial?: Map<string, number>,
) {
  const hasKgLead = kgLeadByMaterial !== undefined;
  const rows: (string | number)[][] = [];
  rows.push(["Inventario - Stock Consolidado"]);
  rows.push([`Generado: ${new Date().toLocaleDateString("es-CO")}`]);
  rows.push([]);

  const headers: string[] = ["Codigo", "Material", "Categoria", "Unidad", "Stock Liq.", "Stock Trans.", "Total"];
  if (hasKgLead) headers.push("Kg Plomo");
  if (canViewValues) headers.push("Costo Prom.", "Valor Total");
  rows.push(headers);

  for (const item of items) {
    const row: (string | number)[] = [
      item.material_code,
      item.material_name,
      item.category_name ?? "",
      item.default_unit,
      item.current_stock_liquidated,
      item.current_stock_transit,
      item.current_stock_total,
    ];
    if (hasKgLead) {
      const kg = kgLeadByMaterial!.get(item.material_id);
      row.push(kg != null ? kg : "");
    }
    if (canViewValues) {
      row.push(item.current_average_cost, item.total_value);
    }
    rows.push(row);
  }

  rows.push([]);
  const totalsRow: (string | number)[] = [
    "", "", "", "TOTAL",
    items.reduce((s, i) => s + i.current_stock_liquidated, 0),
    items.reduce((s, i) => s + i.current_stock_transit, 0),
    items.reduce((s, i) => s + i.current_stock_total, 0),
  ];
  if (hasKgLead) {
    let kgTotal = 0;
    kgLeadByMaterial!.forEach((v) => { kgTotal += v; });
    totalsRow.push(kgTotal);
  }
  if (canViewValues) {
    totalsRow.push("", items.reduce((s, i) => s + i.total_value, 0));
  }
  rows.push(totalsRow);

  const ws = XLSX.utils.aoa_to_sheet(rows);
  ws["!cols"] = [
    { wch: 12 }, { wch: 30 }, { wch: 20 }, { wch: 8 },
    { wch: 14 }, { wch: 14 }, { wch: 14 },
    ...(hasKgLead ? [{ wch: 12 }] : []),
    { wch: 14 }, { wch: 16 },
  ];

  // Currency cols (only when canViewValues) — shift si hay columna Kg Plomo
  if (canViewValues) {
    const base = hasKgLead ? 8 : 7;
    applyCurrencyFormat(ws, [base, base + 1]);
  }

  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, ws, "Stock");
  XLSX.writeFile(wb, `inventario_stock_${new Date().toISOString().split("T")[0]}.xlsx`);
}

export function exportThirdPartyBalancesExcel(data: ThirdPartyBalancesResponse) {
  const rows: (string | number)[][] = [];
  rows.push(["Saldos de Terceros"]);
  rows.push([]);
  rows.push(["Total por Pagar", data.total_payable]);
  rows.push(["Total por Cobrar", data.total_receivable]);
  rows.push(["Posicion Neta", data.net_position]);
  rows.push([]);
  rows.push(["PROVEEDORES (CxP)", ""]);
  rows.push(["Nombre", "Saldo"]);
  for (const s of data.suppliers) {
    rows.push([s.name, s.balance]);
  }
  rows.push([]);
  rows.push(["CLIENTES (CxC)", ""]);
  rows.push(["Nombre", "Saldo"]);
  for (const c of data.customers) {
    rows.push([c.name, c.balance]);
  }

  const ws = XLSX.utils.aoa_to_sheet(rows);
  ws["!cols"] = [{ wch: 30 }, { wch: 18 }, { wch: 20 }];

  // Saldo column (1) is currency
  applyCurrencyFormat(ws, [1]);

  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, ws, "Saldos Terceros");
  XLSX.writeFile(wb, "saldos_terceros.xlsx");
}

// ============================================================================
// Export de operaciones (Compras / Ventas / Doble Partida) con detalle de
// lineas — workbook multi-hoja: "Resumen" (1 fila por operacion, igual que la
// tabla en pantalla) + "Detalle" (1 fila por material con kg, para analisis y
// liquidacion de comisiones). Decision del cliente: kg como numero sumable.
// ============================================================================

const WEIGHT_FMT = "#,##0.####";

// Compras/ventas/DPs comparten estados (decision #2). Etiquetas en femenino
// (sirven para compra/venta/doble partida).
const OP_STATUS_LABELS: Record<string, string> = {
  registered: "Registrada",
  liquidated: "Liquidada",
  cancelled: "Cancelada",
};
const opStatus = (s: string) => OP_STATUS_LABELS[s] ?? s;

// Backend serializa Decimal como string ("100000.00"). Coercer a numero para
// que Excel lo reconozca como numerico (sumable/sorteable).
const num = (v: unknown): number => {
  if (typeof v === "number") return v;
  if (typeof v === "string" && v.trim() !== "" && !Number.isNaN(Number(v))) return Number(v);
  return 0;
};

// Aplica un formato numerico (z) a columnas por indice, solo a celdas numericas.
function applyNumberFormat(ws: XLSX.WorkSheet, cols: number[], fmt: string) {
  if (!ws["!ref"]) return;
  const range = XLSX.utils.decode_range(ws["!ref"]);
  for (let R = range.s.r; R <= range.e.r; R++) {
    for (const C of cols) {
      const cell = ws[XLSX.utils.encode_cell({ r: R, c: C })];
      if (cell && typeof cell.v === "number") {
        cell.t = "n";
        cell.z = fmt;
      }
    }
  }
}

const materialsText = (lines: { material_code: string; quantity: number; material_unit?: string }[]) =>
  lines.map((l) => `${l.material_code} (${formatWeight(num(l.quantity), l.material_unit || "kg")})`).join(", ");

export function exportPurchasesDetailExcel(
  purchases: PurchaseResponse[],
  opts: { canViewPrices: boolean },
) {
  const { canViewPrices } = opts;
  const wb = XLSX.utils.book_new();

  // --- Hoja Resumen (1 fila por compra) ---
  // "Cantidad Total" es numerica sumable (sin sufijo de unidad); la unidad
  // por linea vive en la hoja Detalle (decision #54).
  const resumenHeader = [
    "#", "Factura", "Fecha", "Proveedor", "Placa", "Detalle", "Cantidad Total",
    ...(canViewPrices ? ["Total"] : []),
    "Pasa Mano", "Estado",
  ];
  const resumenRows = purchases.map((p) => [
    p.purchase_number,
    p.invoice_number || "",
    formatDate(p.date),
    p.supplier_name,
    p.vehicle_plate || "—",
    materialsText(p.lines),
    totalLinesQuantity(p.lines),
    ...(canViewPrices ? [num(p.total_amount)] : []),
    p.double_entry_id ? "Sí" : "No",
    opStatus(p.status),
  ]);
  const wsResumen = XLSX.utils.aoa_to_sheet([resumenHeader, ...resumenRows]);
  wsResumen["!cols"] = [
    { wch: 8 }, { wch: 14 }, { wch: 12 }, { wch: 28 }, { wch: 10 }, { wch: 40 }, { wch: 14 },
    ...(canViewPrices ? [{ wch: 16 }] : []),
    { wch: 10 }, { wch: 12 },
  ];
  applyNumberFormat(wsResumen, [6], WEIGHT_FMT);
  if (canViewPrices) applyCurrencyFormat(wsResumen, [7]);
  XLSX.utils.book_append_sheet(wb, wsResumen, "Resumen");

  // --- Hoja Detalle (1 fila por material) ---
  const detalleHeader = [
    "# Compra", "Fecha", "Proveedor", "Factura", "Material", "Bodega", "Cantidad", "Unidad",
    ...(canViewPrices ? ["Precio Unit", "Total Línea"] : []),
    "Estado",
  ];
  const detalleRows: (string | number)[][] = [];
  for (const p of purchases) {
    for (const l of p.lines) {
      detalleRows.push([
        p.purchase_number,
        formatDate(p.date),
        p.supplier_name,
        p.invoice_number || "",
        `${l.material_code} - ${l.material_name}`,
        l.warehouse_name || "",
        num(l.quantity),
        l.material_unit || "kg",
        ...(canViewPrices ? [num(l.unit_price), num(l.total_price)] : []),
        opStatus(p.status),
      ]);
    }
  }
  const wsDetalle = XLSX.utils.aoa_to_sheet([detalleHeader, ...detalleRows]);
  wsDetalle["!cols"] = [
    { wch: 10 }, { wch: 12 }, { wch: 28 }, { wch: 14 }, { wch: 34 }, { wch: 18 }, { wch: 12 }, { wch: 10 },
    ...(canViewPrices ? [{ wch: 16 }, { wch: 16 }] : []),
    { wch: 12 },
  ];
  applyNumberFormat(wsDetalle, [6], WEIGHT_FMT);
  if (canViewPrices) applyCurrencyFormat(wsDetalle, [8, 9]);
  XLSX.utils.book_append_sheet(wb, wsDetalle, "Detalle");

  XLSX.writeFile(wb, "ecobalance_compras.xlsx");
}

export function exportSalesDetailExcel(
  sales: SaleResponse[],
  opts: { canViewPrices: boolean; canViewProfit: boolean },
) {
  const { canViewPrices, canViewProfit } = opts;
  const wb = XLSX.utils.book_new();

  // --- Hoja Resumen (1 fila por venta) ---
  // "Cantidad Total" suma `quantity` original (NO received_quantity, decision
  // #18), numerica sumable sin sufijo de unidad (decision #54).
  const resumenHeader = [
    "#", "Factura", "Fecha", "Cliente", "Placa", "Detalle", "Cantidad Total",
    ...(canViewPrices ? ["Total"] : []),
    ...(canViewProfit ? ["COGS", "Utilidad Bruta"] : []),
    "Pasa Mano", "Estado",
  ];
  const resumenRows = sales.map((s) => {
    const total = num(s.total_amount);
    const profit = num(s.total_profit);
    return [
      s.sale_number,
      s.invoice_number || "",
      formatDate(s.date),
      s.customer_name,
      s.vehicle_plate || "—",
      materialsText(s.lines),
      totalLinesQuantity(s.lines),
      ...(canViewPrices ? [total] : []),
      ...(canViewProfit ? [total - profit, profit] : []),
      s.double_entry_id ? "Sí" : "No",
      opStatus(s.status),
    ];
  });
  const wsResumen = XLSX.utils.aoa_to_sheet([resumenHeader, ...resumenRows]);
  const baseCols = [{ wch: 8 }, { wch: 14 }, { wch: 12 }, { wch: 28 }, { wch: 10 }, { wch: 40 }, { wch: 14 }];
  wsResumen["!cols"] = [
    ...baseCols,
    ...(canViewPrices ? [{ wch: 16 }] : []),
    ...(canViewProfit ? [{ wch: 16 }, { wch: 16 }] : []),
    { wch: 10 }, { wch: 12 },
  ];
  applyNumberFormat(wsResumen, [6], WEIGHT_FMT);
  {
    const currencyCols: number[] = [];
    let idx = 7;
    if (canViewPrices) currencyCols.push(idx++);
    if (canViewProfit) { currencyCols.push(idx++, idx++); }
    if (currencyCols.length) applyCurrencyFormat(wsResumen, currencyCols);
  }
  XLSX.utils.book_append_sheet(wb, wsResumen, "Resumen");

  // --- Hoja Detalle (1 fila por material) ---
  const detalleHeader = [
    "# Venta", "Fecha", "Cliente", "Factura", "Material", "Cantidad", "Unidad", "Cantidad Recibida",
    ...(canViewPrices ? ["Precio Unit", "Total Línea"] : []),
    ...(canViewProfit ? ["Costo Unit", "Utilidad"] : []),
    "Estado",
  ];
  const detalleRows: (string | number)[][] = [];
  for (const s of sales) {
    for (const l of s.lines) {
      detalleRows.push([
        s.sale_number,
        formatDate(s.date),
        s.customer_name,
        s.invoice_number || "",
        `${l.material_code} - ${l.material_name}`,
        num(l.quantity),
        l.material_unit || "kg",
        l.received_quantity != null ? num(l.received_quantity) : "",
        ...(canViewPrices ? [num(l.unit_price), num(l.total_price)] : []),
        ...(canViewProfit ? [num(l.unit_cost), num(l.profit)] : []),
        opStatus(s.status),
      ]);
    }
  }
  const wsDetalle = XLSX.utils.aoa_to_sheet([detalleHeader, ...detalleRows]);
  wsDetalle["!cols"] = [
    { wch: 10 }, { wch: 12 }, { wch: 28 }, { wch: 14 }, { wch: 34 }, { wch: 12 }, { wch: 10 }, { wch: 14 },
    ...(canViewPrices ? [{ wch: 16 }, { wch: 16 }] : []),
    ...(canViewProfit ? [{ wch: 16 }, { wch: 16 }] : []),
    { wch: 12 },
  ];
  applyNumberFormat(wsDetalle, [5, 7], WEIGHT_FMT);
  {
    const currencyCols: number[] = [];
    let idx = 8;
    if (canViewPrices) currencyCols.push(idx++, idx++);
    if (canViewProfit) currencyCols.push(idx++, idx++);
    if (currencyCols.length) applyCurrencyFormat(wsDetalle, currencyCols);
  }
  XLSX.utils.book_append_sheet(wb, wsDetalle, "Detalle");

  XLSX.writeFile(wb, "ecobalance_ventas.xlsx");
}

export function exportDoubleEntriesDetailExcel(
  entries: DoubleEntryResponse[],
  opts: { canViewValues: boolean; canViewProfit: boolean },
) {
  const { canViewValues, canViewProfit } = opts;
  const wb = XLSX.utils.book_new();

  // --- Hoja Resumen (1 fila por DP) ---
  const resumenHeader = [
    "#", "Factura", "Fecha", "Proveedor", "Cliente", "Detalle",
    ...(canViewValues ? ["Total"] : []),
    ...(canViewProfit ? ["Utilidad Bruta"] : []),
    "Estado",
  ];
  const resumenRows = entries.map((d) => [
    d.double_entry_number,
    d.invoice_number || "",
    formatDate(d.date),
    d.supplier_name,
    d.customer_name,
    d.materials_summary,
    ...(canViewValues ? [num(d.total_sale_amount)] : []),
    ...(canViewProfit ? [num(d.profit)] : []),
    opStatus(d.status),
  ]);
  const wsResumen = XLSX.utils.aoa_to_sheet([resumenHeader, ...resumenRows]);
  wsResumen["!cols"] = [
    { wch: 8 }, { wch: 14 }, { wch: 12 }, { wch: 26 }, { wch: 26 }, { wch: 40 },
    ...(canViewValues ? [{ wch: 16 }] : []),
    ...(canViewProfit ? [{ wch: 16 }] : []),
    { wch: 12 },
  ];
  {
    const currencyCols: number[] = [];
    let idx = 6;
    if (canViewValues) currencyCols.push(idx++);
    if (canViewProfit) currencyCols.push(idx++);
    if (currencyCols.length) applyCurrencyFormat(wsResumen, currencyCols);
  }
  XLSX.utils.book_append_sheet(wb, wsResumen, "Resumen");

  // --- Hoja Detalle (1 fila por material) ---
  const detalleHeader = [
    "# DP", "Fecha", "Proveedor", "Cliente", "Factura", "Material", "Cantidad", "Unidad",
    ...(canViewValues ? ["Precio Compra", "Precio Venta", "Total Compra", "Total Venta"] : []),
    ...(canViewProfit ? ["Utilidad"] : []),
    "Estado",
  ];
  const detalleRows: (string | number)[][] = [];
  for (const d of entries) {
    for (const l of d.lines) {
      detalleRows.push([
        d.double_entry_number,
        formatDate(d.date),
        d.supplier_name,
        d.customer_name,
        d.invoice_number || "",
        `${l.material_code} - ${l.material_name}`,
        num(l.quantity),
        l.material_unit || "kg",
        ...(canViewValues ? [num(l.purchase_unit_price), num(l.sale_unit_price), num(l.total_purchase), num(l.total_sale)] : []),
        ...(canViewProfit ? [num(l.profit)] : []),
        opStatus(d.status),
      ]);
    }
  }
  const wsDetalle = XLSX.utils.aoa_to_sheet([detalleHeader, ...detalleRows]);
  wsDetalle["!cols"] = [
    { wch: 10 }, { wch: 12 }, { wch: 26 }, { wch: 26 }, { wch: 14 }, { wch: 34 }, { wch: 12 }, { wch: 10 },
    ...(canViewValues ? [{ wch: 15 }, { wch: 15 }, { wch: 16 }, { wch: 16 }] : []),
    ...(canViewProfit ? [{ wch: 16 }] : []),
    { wch: 12 },
  ];
  applyNumberFormat(wsDetalle, [6], WEIGHT_FMT);
  {
    const currencyCols: number[] = [];
    let idx = 8;
    if (canViewValues) currencyCols.push(idx++, idx++, idx++, idx++);
    if (canViewProfit) currencyCols.push(idx++);
    if (currencyCols.length) applyCurrencyFormat(wsDetalle, currencyCols);
  }
  XLSX.utils.book_append_sheet(wb, wsDetalle, "Detalle");

  XLSX.writeFile(wb, "ecobalance_doble-partidas.xlsx");
}

// Dinero Inactivo (R1) — respeta el tab activo (items ya vienen filtrados)
export function exportInactiveBalancesExcel(data: InactiveBalancesResponse, contextLabel?: string) {
  const TYPE_LABEL: Record<string, string> = {
    customer: "Cliente", material_supplier: "Proveedor", service_provider: "Servicio",
    provision: "Provisión", investor: "Inversionista", liability: "Pasivo", generic: "Genérico",
  };
  const rows: (string | number | null)[][] = [];
  rows.push(["Dinero Inactivo"]);
  rows.push([`Umbral: ${data.min_days} días sin movimiento${data.min_amount > 0 ? ` · desde $${data.min_amount.toLocaleString("es-CO")}` : ""}`]);
  if (contextLabel) rows.push([`Tipo: ${contextLabel}`]);
  const total = data.items.reduce((s, i) => s + i.amount_inactive, 0);
  rows.push(["Total parado", total]);
  rows.push([]);
  rows.push(["Tercero", "Tipo", "Dias inactivos", "Monto", "Ultima actividad", "Telefono"]);
  for (const it of data.items) {
    rows.push([
      it.third_party_name,
      TYPE_LABEL[it.third_party_type] ?? it.third_party_type,
      it.days_inactive,
      it.amount_inactive,
      it.has_movements && it.last_activity_date ? it.last_activity_date.slice(0, 10) : "Sin movimientos",
      it.phone ?? "",
    ]);
  }
  const ws = XLSX.utils.aoa_to_sheet(rows);
  ws["!cols"] = [{ wch: 32 }, { wch: 14 }, { wch: 14 }, { wch: 16 }, { wch: 18 }, { wch: 16 }];
  applyCurrencyFormat(ws, [1, 3]); // total (col 1, solo su fila numérica) + montos (col 3)
  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, ws, "Dinero Inactivo");
  XLSX.writeFile(wb, `dinero_inactivo_${data.as_of.slice(0, 10)}.xlsx`);
}

// --- Materiales (kg) — catálogo SAC con clasificación y factor (paquete UX W2) ---

export interface MaterialKgExportRow {
  code: string;
  name: string;
  unit: string;
  category: string;
  businessUnit: string;
  classification: string;
  alsoCompra: boolean;
  factor: string;
  since: string;
  by: string;
  description: string;
}

export function exportMaterialsKgExcel(rows: MaterialKgExportRow[]) {
  const data: (string | number | null)[][] = [];
  data.push(["Materiales (kg) — Catálogo con clasificación y factores"]);
  data.push([`Generado: ${formatDate(new Date().toISOString())}`]);
  data.push([]);
  data.push([
    "Código", "Nombre", "Unidad", "Categoría", "Unidad de Negocio",
    "Clasificación", "También Compra", "Factor Vigente", "Desde", "Por", "Descripción",
  ]);
  for (const r of rows) {
    data.push([
      r.code, r.name, r.unit, r.category, r.businessUnit,
      r.classification, r.alsoCompra ? "Sí" : "", r.factor, r.since, r.by, r.description,
    ]);
  }
  const ws = XLSX.utils.aoa_to_sheet(data);
  ws["!cols"] = [
    { wch: 12 }, { wch: 28 }, { wch: 8 }, { wch: 16 }, { wch: 22 },
    { wch: 22 }, { wch: 14 }, { wch: 20 }, { wch: 12 }, { wch: 16 }, { wch: 30 },
  ];
  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, ws, "Materiales (kg)");
  XLSX.writeFile(wb, "materiales_kg.xlsx");
}
