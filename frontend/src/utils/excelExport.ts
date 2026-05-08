import * as XLSX from "xlsx";
import type { AccountStatementExportData } from "@/utils/pdfExport";
import type {
  BalanceDetailedResponse,
  ProfitAndLossResponse,
  CashFlowResponse,
  BalanceSheetResponse,
  PurchaseReportResponse,
  SalesReportResponse,
  MarginAnalysisResponse,
  ThirdPartyBalancesResponse,
  ProfitabilityByBUResponse,
  RealCostByMaterialResponse,
  ExpensesReportResponse,
  ExpenseGroupNode,
  ExpenseDetailResponse,
} from "@/types/reports";
import type { StockItem } from "@/types/inventory";
import { formatCurrency, formatDate } from "@/utils/formatters";
import { applyCurrencyFormat } from "@/utils/excelHelpers";

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
    rows.push(["Fecha", "Concepto", "Material", "Peso", "Precio", "Dif Peso", "Debito", "Credito", "Saldo"]);
    if (data.dateFrom) {
      rows.push(["", "Saldo de apertura", "", "", "", "", "", "", data.openingBalance]);
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
    rows.push(["#", "Fecha", "Tipo", "Descripcion", "Debe", "Haber", "Saldo"]);
    if (data.dateFrom) {
      rows.push(["", "", "Saldo de apertura", "", "", "", data.openingBalance]);
    }
    for (const m of data.movements) {
      const isAnnulled = m.status === "annulled";
      const typeText = isAnnulled ? `${m.typeLabel} (Anulado)` : m.typeLabel;
      rows.push([
        m.movement_number,
        formatDate(m.date),
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
    { wch: 12 }, { wch: 18 }, { wch: 25 }, { wch: 12 }, { wch: 14 },
    { wch: 12 }, { wch: 16 }, { wch: 16 }, { wch: 16 },
  ] : [
    { wch: 8 }, { wch: 12 }, { wch: 28 }, { wch: 30 },
    { wch: 16 }, { wch: 16 }, { wch: 16 },
  ];

  // Apply currency format
  if (isOps) {
    // Resumen row (cols 0,1,2) + Precio (4), Dif Peso (5), Debito (6), Credito (7), Saldo (8)
    applyCurrencyFormat(ws, [0, 1, 2, 4, 5, 6, 7, 8]);
  } else {
    // Resumen (0,1,2) + Debe (4), Haber (5), Saldo (6)
    applyCurrencyFormat(ws, [0, 1, 2, 4, 5, 6]);
  }

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

export function exportBalanceDetailedExcel(data: BalanceDetailedResponse) {
  const rows: (string | number | null)[][] = [];

  rows.push([`Balance Detallado — Corte al: ${formatDate(data.as_of_date)}`]);
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
      rows.push(["", detail, item.name, item.balance]);
    }
  };

  for (const key of ASSET_ORDER) {
    const section = data.assets[key];
    if (!section) continue;
    rows.push([section.label, "", "", section.total]);
    if (section.groups && section.groups.length > 0) {
      for (const group of section.groups) {
        rows.push(["", group.label, "", group.total]);
        for (const item of group.items) {
          rows.push(["", "", item.name, item.balance]);
        }
      }
    } else {
      pushItems(section.items);
    }
  }

  rows.push([]);

  // Pasivos
  rows.push(["PASIVOS", "", "", data.total_liabilities]);
  rows.push(["Seccion", "Detalle", "Nombre", "Valor"]);

  for (const key of LIABILITY_ORDER) {
    const section = data.liabilities[key];
    if (!section) continue;
    rows.push([section.label, "", "", section.total]);
    if (section.groups && section.groups.length > 0) {
      for (const group of section.groups) {
        rows.push(["", group.label, "", group.total]);
        for (const item of group.items) {
          rows.push(["", "", item.name, item.balance]);
        }
      }
    } else {
      pushItems(section.items);
    }
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

  // Totales
  rows.push([]);
  const t = data.totals;
  rows.push([
    "TOTAL", t.purchases_total, "100%",
    t.sales_revenue, t.sales_cogs, t.total_gross_profit,
    t.direct_expenses, t.shared_expenses, t.general_expenses,
    t.sale_commissions, t.net_profit, `${t.net_margin.toFixed(1)}%`,
  ]);

  const ws = XLSX.utils.aoa_to_sheet(rows);
  ws["!cols"] = [{ wch: 25 }, { wch: 15 }, { wch: 15 }, { wch: 15 }, { wch: 15 }, { wch: 15 }, { wch: 15 }, { wch: 15 }, { wch: 15 }, { wch: 10 }];

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
) {
  const ALLOC_LABEL: Record<string, string> = {
    direct: "Directo",
    shared: "Compartido",
    general: "General",
  };
  const rows: (string | number | null)[][] = [];

  rows.push(["Reporte de Gastos - Detalle"]);
  rows.push([`Periodo: ${periodFrom} - ${periodTo}`]);
  rows.push([]);
  rows.push(["Total movimientos", data.total_count]);
  rows.push(["Total", data.total_allocated]);
  rows.push([]);
  rows.push(["Fecha", "#", "Tipo", "Tercero", "UN", "Categoria", "Descripcion", "Monto", "Asignacion"]);

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
    { wch: 16 }, // Monto
    { wch: 14 }, // Asignacion
  ];

  // Total cell + columna Monto
  applyCurrencyFormat(ws, [7]);

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
  rows.push(["Ingresos por Servicios", data.service_income]);
  rows.push(["Costo de Ventas (COGS)", data.cost_of_goods_sold]);
  rows.push(["Utilidad Bruta Ventas", data.gross_profit_sales]);
  rows.push(["Utilidad Pasa Mano", data.double_entry_profit]);
  if (data.transformation_profit !== 0) rows.push(["Gan/Perd Transformaciones", data.transformation_profit]);
  if (data.waste_loss > 0) rows.push(["Perdida por Merma", -data.waste_loss]);
  if (data.adjustment_net !== 0) rows.push(["Ajustes de Inventario", data.adjustment_net]);
  if (data.tp_adjustment_gain > 0) rows.push(["+ Ganancia Ajuste Terceros", data.tp_adjustment_gain]);
  if (data.tp_adjustment_loss > 0) rows.push(["- Perdida Ajuste Terceros", -data.tp_adjustment_loss]);
  rows.push(["Utilidad Bruta Total", data.total_gross_profit]);
  rows.push([]);
  rows.push(["Gastos Operativos", data.operating_expenses]);
  for (const cat of data.expenses_by_category) {
    rows.push([`  ${cat.category_name}`, cat.total_amount]);
  }
  rows.push(["Comisiones Pagadas", data.commissions_paid]);
  rows.push([]);
  rows.push(["Utilidad Neta", data.net_profit]);
  rows.push(["Margen Neto", `${(data.net_margin * 100).toFixed(1)}%`]);

  const ws = XLSX.utils.aoa_to_sheet(rows);
  ws["!cols"] = [{ wch: 35 }, { wch: 20 }];

  // Valor column (1) is currency
  applyCurrencyFormat(ws, [1]);

  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, ws, "P&L");
  XLSX.writeFile(wb, `estado_resultados_${data.period_from}_${data.period_to}.xlsx`);
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
  if (data.assets.prepaid_expenses > 0) rows.push(["Gastos Prepagados", data.assets.prepaid_expenses]);
  if (data.assets.provision_funds > 0) rows.push(["Fondos Provision", data.assets.provision_funds]);
  if (data.assets.fixed_assets > 0) rows.push(["Activos Fijos", data.assets.fixed_assets]);
  rows.push(["Total Activos", data.total_assets]);
  rows.push([]);
  rows.push(["PASIVOS", ""]);
  rows.push(["Cuentas por Pagar", data.liabilities.accounts_payable]);
  rows.push(["Deuda Inversionistas", data.liabilities.investor_debt]);
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
  rows.push(["Utilidad", data.total_profit]);
  rows.push(["Margen", `${data.overall_margin.toFixed(1)}%`]);
  rows.push(["Operaciones", data.sale_count]);
  rows.push([]);
  rows.push(["POR CLIENTE", "", "", "", ""]);
  rows.push(["Cliente", "Total", "Cantidad", "# Ventas", "Utilidad"]);
  for (const c of data.by_customer) {
    rows.push([c.customer_name, c.total_amount, c.total_quantity, c.sale_count, c.total_profit]);
  }
  rows.push([]);
  rows.push(["POR MATERIAL", "", "", "", ""]);
  rows.push(["Material", "Ventas", "Costo", "Utilidad", "Margen"]);
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


export function exportStockExcel(items: StockItem[], canViewValues: boolean) {
  const rows: (string | number)[][] = [];
  rows.push(["Inventario - Stock Consolidado"]);
  rows.push([`Generado: ${new Date().toLocaleDateString("es-CO")}`]);
  rows.push([]);

  const headers: string[] = ["Codigo", "Material", "Categoria", "Unidad", "Stock Liq.", "Stock Trans.", "Total"];
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
  if (canViewValues) {
    totalsRow.push("", items.reduce((s, i) => s + i.total_value, 0));
  }
  rows.push(totalsRow);

  const ws = XLSX.utils.aoa_to_sheet(rows);
  ws["!cols"] = [
    { wch: 12 }, { wch: 30 }, { wch: 20 }, { wch: 8 },
    { wch: 14 }, { wch: 14 }, { wch: 14 }, { wch: 14 }, { wch: 16 },
  ];

  // Currency cols (only when canViewValues): 7 (Costo Prom), 8 (Valor Total)
  if (canViewValues) {
    applyCurrencyFormat(ws, [7, 8]);
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
