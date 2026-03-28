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
} from "@/types/reports";
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

  const isOps = data.viewMode === "operations";

  if (isOps) {
    rows.push(["Fecha", "Concepto", "Material", "Peso", "Precio", "Dif Peso", "Debito", "Credito", "Saldo"]);
    if (data.dateFrom) {
      rows.push(["", "Saldo de apertura", "", "", "", "", "", "", formatCurrency(data.openingBalance)]);
    }
    for (const m of data.movements) {
      const concepto = m.vehicle_plate || m.invoice_number || m.description || "-";
      const diffPesoMoney = m.received_quantity && m.quantity && m.unit_price && m.received_quantity !== m.quantity
        ? (m.received_quantity - m.quantity) * m.unit_price : null;
      rows.push([
        formatDate(m.date),
        concepto,
        m.is_line_item && m.material_code ? `${m.material_code} - ${m.material_name || ""}` : "",
        m.is_line_item && m.quantity ? m.quantity : "",
        m.is_line_item && m.unit_price ? formatCurrency(m.unit_price) : "",
        diffPesoMoney != null ? formatCurrency(diffPesoMoney) : "",
        m.isDebit ? formatCurrency(m.amount) : "",
        !m.isDebit ? formatCurrency(m.amount) : "",
        m.balance_after != null ? formatCurrency(m.balance_after) : "",
      ]);
    }
  } else {
    rows.push(["#", "Fecha", "Tipo", "Descripcion", "Debe", "Haber", "Saldo"]);
    if (data.dateFrom) {
      rows.push(["", "", "Saldo de apertura", "", "", "", formatCurrency(data.openingBalance)]);
    }
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


export function exportProfitabilityBUExcel(data: ProfitabilityByBUResponse) {
  const fmt = (n: number) => formatCurrency(n);
  const rows: (string | number | null)[][] = [];

  rows.push(["Rentabilidad por Unidad de Negocio"]);
  rows.push([`Periodo: ${data.period_from} - ${data.period_to}`]);
  rows.push([]);

  // Header
  rows.push(["Unidad de Negocio", "Compras", "Peso %", "Ventas", "COGS", "Ut. Bruta", "G. Directos", "G. Compartidos", "G. Generales", "Comisiones", "Ut. Neta", "Margen %"]);

  // UNs
  for (const bu of data.business_units) {
    rows.push([
      bu.business_unit_name, fmt(bu.purchases_total), `${bu.purchases_weight_pct.toFixed(1)}%`,
      fmt(bu.sales_revenue), fmt(bu.sales_cogs),
      fmt(bu.total_gross_profit), fmt(bu.direct_expenses), fmt(bu.shared_expenses),
      fmt(bu.general_expenses), fmt(bu.sale_commissions), fmt(bu.net_profit),
      `${bu.net_margin.toFixed(1)}%`,
    ]);
    // Desglose directos
    for (const d of bu.direct_expenses_detail) {
      rows.push(["  " + d.category_name, "", "", "", fmt(d.amount), "", "", "", "", ""]);
    }
  }

  // Totales
  rows.push([]);
  const t = data.totals;
  rows.push([
    "TOTAL", fmt(t.purchases_total), "100%",
    fmt(t.sales_revenue), fmt(t.sales_cogs), fmt(t.total_gross_profit),
    fmt(t.direct_expenses), fmt(t.shared_expenses), fmt(t.general_expenses),
    fmt(t.sale_commissions), fmt(t.net_profit), `${t.net_margin.toFixed(1)}%`,
  ]);

  const ws = XLSX.utils.aoa_to_sheet(rows);
  ws["!cols"] = [{ wch: 25 }, { wch: 15 }, { wch: 15 }, { wch: 15 }, { wch: 15 }, { wch: 15 }, { wch: 15 }, { wch: 15 }, { wch: 15 }, { wch: 10 }];

  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, ws, "Rentabilidad UN");
  XLSX.writeFile(wb, `rentabilidad_un_${data.period_from}_${data.period_to}.xlsx`);
}


export function exportRealCostMaterialExcel(data: RealCostByMaterialResponse) {
  const fmt = (n: number) => formatCurrency(n);
  const rows: (string | number | null)[][] = [];

  rows.push(["Costo Real por Material"]);
  rows.push([`Periodo: ${data.period_from} - ${data.period_to}`]);
  rows.push([]);

  for (const bu of data.business_units) {
    rows.push([bu.business_unit_name, `Gastos: ${fmt(bu.total_expenses)}`, `Kg: ${bu.kg_purchased.toLocaleString()}`, `Overhead: ${fmt(bu.overhead_rate)}/kg`]);
    rows.push(["Codigo", "Material", "Costo Promedio", "Overhead", "Costo Real"]);
    for (const m of bu.materials) {
      rows.push([m.material_code, m.material_name, fmt(m.average_cost), fmt(m.overhead_rate), fmt(m.real_cost)]);
    }
    rows.push([]);
  }

  const ws = XLSX.utils.aoa_to_sheet(rows);
  ws["!cols"] = [{ wch: 15 }, { wch: 25 }, { wch: 18 }, { wch: 15 }, { wch: 15 }];

  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, ws, "Costo Real");
  XLSX.writeFile(wb, `costo_real_material_${data.period_from}_${data.period_to}.xlsx`);
}


export function exportPnlExcel(data: ProfitAndLossResponse) {
  const fmt = (n: number) => formatCurrency(n);
  const rows: (string | number)[][] = [];
  rows.push(["Estado de Resultados"]);
  rows.push([`Periodo: ${data.period_from} - ${data.period_to}`]);
  rows.push([]);
  rows.push(["Concepto", "Valor"]);
  rows.push(["Ingresos por Ventas", fmt(data.sales_revenue)]);
  rows.push(["Ingresos por Servicios", fmt(data.service_income)]);
  rows.push(["Costo de Ventas (COGS)", fmt(data.cost_of_goods_sold)]);
  rows.push(["Utilidad Bruta Ventas", fmt(data.gross_profit_sales)]);
  rows.push(["Utilidad Pasa Mano", fmt(data.double_entry_profit)]);
  if (data.transformation_profit !== 0) rows.push(["Gan/Perd Transformaciones", fmt(data.transformation_profit)]);
  if (data.waste_loss > 0) rows.push(["Perdida por Merma", fmt(-data.waste_loss)]);
  if (data.adjustment_net !== 0) rows.push(["Ajustes de Inventario", fmt(data.adjustment_net)]);
  if (data.tp_adjustment_gain > 0) rows.push(["+ Ganancia Ajuste Terceros", fmt(data.tp_adjustment_gain)]);
  if (data.tp_adjustment_loss > 0) rows.push(["- Perdida Ajuste Terceros", fmt(-data.tp_adjustment_loss)]);
  rows.push(["Utilidad Bruta Total", fmt(data.total_gross_profit)]);
  rows.push([]);
  rows.push(["Gastos Operativos", fmt(data.operating_expenses)]);
  for (const cat of data.expenses_by_category) {
    rows.push([`  ${cat.category_name}`, fmt(cat.total_amount)]);
  }
  rows.push(["Comisiones Pagadas", fmt(data.commissions_paid)]);
  rows.push([]);
  rows.push(["Utilidad Neta", fmt(data.net_profit)]);
  rows.push(["Margen Neto", `${(data.net_margin * 100).toFixed(1)}%`]);

  const ws = XLSX.utils.aoa_to_sheet(rows);
  ws["!cols"] = [{ wch: 35 }, { wch: 20 }];
  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, ws, "P&L");
  XLSX.writeFile(wb, `estado_resultados_${data.period_from}_${data.period_to}.xlsx`);
}


export function exportCashFlowExcel(data: CashFlowResponse) {
  const fmt = (n: number) => formatCurrency(n);
  const rows: (string | number)[][] = [];
  rows.push(["Flujo de Caja"]);
  rows.push([`Periodo: ${data.period_from} - ${data.period_to}`]);
  rows.push([]);
  rows.push(["Saldo Inicial", fmt(data.opening_balance)]);
  rows.push([]);
  rows.push(["INGRESOS", ""]);
  // sale_collections removido (phantom — ya capturado por collection_from_client)
  rows.push(["Cobros a Clientes (Tesoreria)", fmt(data.inflows.customer_collections)]);
  rows.push(["Ingresos por Servicios", fmt(data.inflows.service_income)]);
  rows.push(["Aportes de Capital", fmt(data.inflows.capital_injections)]);
  if (data.inflows.advance_collections > 0) rows.push(["Anticipos de Clientes", fmt(data.inflows.advance_collections)]);
  if (data.inflows.generic_collections > 0) rows.push(["Cobros Genericos", fmt(data.inflows.generic_collections)]);
  rows.push(["Total Ingresos", fmt(data.total_inflows)]);
  rows.push([]);
  rows.push(["EGRESOS", ""]);
  // purchase_payments removido (phantom — ya capturado por payment_to_supplier)
  rows.push(["Pagos a Proveedores (Tesoreria)", fmt(data.outflows.supplier_payments)]);
  rows.push(["Gastos", fmt(data.outflows.expenses)]);
  rows.push(["Comisiones", fmt(data.outflows.commission_payments)]);
  rows.push(["Devolucion de Capital", fmt(data.outflows.capital_returns)]);
  if (data.outflows.provision_deposits > 0) rows.push(["Depositos a Provisiones", fmt(data.outflows.provision_deposits)]);
  if (data.outflows.deferred_fundings > 0) rows.push(["Gastos Diferidos", fmt(data.outflows.deferred_fundings)]);
  if (data.outflows.advance_payments > 0) rows.push(["Anticipos a Proveedores", fmt(data.outflows.advance_payments)]);
  if (data.outflows.asset_payments > 0) rows.push(["Activos Fijos", fmt(data.outflows.asset_payments)]);
  if (data.outflows.generic_payments > 0) rows.push(["Pagos Genericos", fmt(data.outflows.generic_payments)]);
  rows.push(["Total Egresos", fmt(data.total_outflows)]);
  rows.push([]);
  rows.push(["Flujo Neto", fmt(data.net_flow)]);
  rows.push(["Saldo Final", fmt(data.closing_balance)]);

  const ws = XLSX.utils.aoa_to_sheet(rows);
  ws["!cols"] = [{ wch: 35 }, { wch: 20 }];
  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, ws, "Flujo Caja");
  XLSX.writeFile(wb, `flujo_caja_${data.period_from}_${data.period_to}.xlsx`);
}


export function exportBalanceSheetExcel(data: BalanceSheetResponse) {
  const fmt = (n: number) => formatCurrency(n);
  const rows: (string | number)[][] = [];
  rows.push(["Balance General"]);
  rows.push([`Fecha: ${data.as_of_date}`]);
  rows.push([]);
  rows.push(["ACTIVOS", ""]);
  rows.push(["Efectivo y Bancos", fmt(data.assets.cash_and_bank)]);
  rows.push(["Cuentas por Cobrar", fmt(data.assets.accounts_receivable)]);
  rows.push(["Inventario", fmt(data.assets.inventory)]);
  rows.push(["Anticipos", fmt(data.assets.advances)]);
  if (data.assets.investor_receivable > 0) rows.push(["CxC Inversionistas", fmt(data.assets.investor_receivable)]);
  if (data.assets.prepaid_expenses > 0) rows.push(["Gastos Prepagados", fmt(data.assets.prepaid_expenses)]);
  if (data.assets.provision_funds > 0) rows.push(["Fondos Provision", fmt(data.assets.provision_funds)]);
  if (data.assets.fixed_assets > 0) rows.push(["Activos Fijos", fmt(data.assets.fixed_assets)]);
  rows.push(["Total Activos", fmt(data.total_assets)]);
  rows.push([]);
  rows.push(["PASIVOS", ""]);
  rows.push(["Cuentas por Pagar", fmt(data.liabilities.accounts_payable)]);
  rows.push(["Deuda Inversionistas", fmt(data.liabilities.investor_debt)]);
  if (data.liabilities.liability_debt > 0) rows.push(["Pasivos", fmt(data.liabilities.liability_debt)]);
  if (data.liabilities.customer_advances > 0) rows.push(["Anticipos Clientes", fmt(data.liabilities.customer_advances)]);
  if (data.liabilities.provision_obligations > 0) rows.push(["Obligaciones Provision", fmt(data.liabilities.provision_obligations)]);
  rows.push(["Total Pasivos", fmt(data.total_liabilities)]);
  rows.push([]);
  rows.push(["PATRIMONIO", ""]);
  rows.push(["Patrimonio", fmt(data.equity)]);
  rows.push(["Utilidad Acumulada", fmt(data.accumulated_profit)]);
  rows.push(["Utilidad Distribuida", fmt(data.distributed_profit)]);

  const ws = XLSX.utils.aoa_to_sheet(rows);
  ws["!cols"] = [{ wch: 30 }, { wch: 20 }];
  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, ws, "Balance General");
  XLSX.writeFile(wb, `balance_general_${data.as_of_date}.xlsx`);
}


export function exportPurchaseReportExcel(data: PurchaseReportResponse) {
  const fmt = (n: number) => formatCurrency(n);
  const rows: (string | number)[][] = [];
  rows.push(["Reporte de Compras"]);
  rows.push([`Periodo: ${data.period_from} - ${data.period_to}`]);
  rows.push([]);
  rows.push(["Total Compras", fmt(data.total_amount)]);
  rows.push(["Operaciones", data.purchase_count]);
  rows.push(["Kg Totales", data.total_quantity]);
  rows.push(["Promedio por Compra", fmt(data.average_per_purchase)]);
  rows.push([]);
  rows.push(["POR PROVEEDOR", "", "", ""]);
  rows.push(["Proveedor", "Total", "Cantidad", "# Compras"]);
  for (const s of data.by_supplier) {
    rows.push([s.supplier_name, fmt(s.total_amount), s.total_quantity, s.purchase_count]);
  }
  rows.push([]);
  rows.push(["POR MATERIAL", "", "", ""]);
  rows.push(["Material", "Total", "Cantidad", "Precio Promedio"]);
  for (const m of data.by_material) {
    rows.push([`${m.material_code} - ${m.material_name}`, fmt(m.total_amount), m.total_quantity, fmt(m.average_unit_price)]);
  }

  const ws = XLSX.utils.aoa_to_sheet(rows);
  ws["!cols"] = [{ wch: 30 }, { wch: 18 }, { wch: 15 }, { wch: 18 }];
  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, ws, "Compras");
  XLSX.writeFile(wb, `reporte_compras_${data.period_from}_${data.period_to}.xlsx`);
}


export function exportSalesReportExcel(data: SalesReportResponse) {
  const fmt = (n: number) => formatCurrency(n);
  const rows: (string | number)[][] = [];
  rows.push(["Reporte de Ventas"]);
  rows.push([`Periodo: ${data.period_from} - ${data.period_to}`]);
  rows.push([]);
  rows.push(["Total Ventas", fmt(data.total_revenue)]);
  rows.push(["Costo", fmt(data.total_cost)]);
  rows.push(["Utilidad", fmt(data.total_profit)]);
  rows.push(["Margen", `${data.overall_margin.toFixed(1)}%`]);
  rows.push(["Operaciones", data.sale_count]);
  rows.push([]);
  rows.push(["POR CLIENTE", "", "", "", ""]);
  rows.push(["Cliente", "Total", "Cantidad", "# Ventas", "Utilidad"]);
  for (const c of data.by_customer) {
    rows.push([c.customer_name, fmt(c.total_amount), c.total_quantity, c.sale_count, fmt(c.total_profit)]);
  }
  rows.push([]);
  rows.push(["POR MATERIAL", "", "", "", ""]);
  rows.push(["Material", "Ventas", "Costo", "Utilidad", "Margen"]);
  for (const m of data.by_material) {
    rows.push([`${m.material_code} - ${m.material_name}`, fmt(m.total_amount), fmt(m.total_cost), fmt(m.total_profit), `${m.margin_percentage.toFixed(1)}%`]);
  }

  const ws = XLSX.utils.aoa_to_sheet(rows);
  ws["!cols"] = [{ wch: 30 }, { wch: 18 }, { wch: 18 }, { wch: 18 }, { wch: 12 }];
  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, ws, "Ventas");
  XLSX.writeFile(wb, `reporte_ventas_${data.period_from}_${data.period_to}.xlsx`);
}


export function exportMarginAnalysisExcel(data: MarginAnalysisResponse) {
  const fmt = (n: number) => formatCurrency(n);
  const rows: (string | number)[][] = [];
  rows.push(["Analisis de Margenes"]);
  rows.push([`Periodo: ${data.period_from} - ${data.period_to}`]);
  rows.push([`Margen Global: ${data.overall_margin.toFixed(1)}%`]);
  rows.push([]);
  rows.push(["Codigo", "Material", "Categoria", "Kg Compra", "$ Compra", "Precio Compra", "Kg Venta", "$ Venta", "Precio Venta", "Utilidad", "Margen %"]);
  for (const m of data.materials) {
    rows.push([
      m.material_code, m.material_name, m.category_name || "-",
      m.total_purchased_qty, fmt(m.total_purchased_amount), fmt(m.avg_purchase_price),
      m.total_sold_qty, fmt(m.total_sold_revenue), fmt(m.avg_sale_price),
      fmt(m.gross_profit), `${m.margin_percentage.toFixed(1)}%`,
    ]);
  }

  const ws = XLSX.utils.aoa_to_sheet(rows);
  ws["!cols"] = [{ wch: 10 }, { wch: 20 }, { wch: 15 }, { wch: 12 }, { wch: 15 }, { wch: 15 }, { wch: 12 }, { wch: 15 }, { wch: 15 }, { wch: 15 }, { wch: 10 }];
  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, ws, "Margenes");
  XLSX.writeFile(wb, `margenes_${data.period_from}_${data.period_to}.xlsx`);
}


export function exportThirdPartyBalancesExcel(data: ThirdPartyBalancesResponse) {
  const fmt = (n: number) => formatCurrency(n);
  const rows: (string | number)[][] = [];
  rows.push(["Saldos de Terceros"]);
  rows.push([]);
  rows.push(["Total por Pagar", fmt(data.total_payable)]);
  rows.push(["Total por Cobrar", fmt(data.total_receivable)]);
  rows.push(["Posicion Neta", fmt(data.net_position)]);
  rows.push([]);
  rows.push(["PROVEEDORES (CxP)", ""]);
  rows.push(["Nombre", "Saldo"]);
  for (const s of data.suppliers) {
    rows.push([s.name, fmt(s.balance)]);
  }
  rows.push([]);
  rows.push(["CLIENTES (CxC)", ""]);
  rows.push(["Nombre", "Saldo"]);
  for (const c of data.customers) {
    rows.push([c.name, fmt(c.balance)]);
  }

  const ws = XLSX.utils.aoa_to_sheet(rows);
  ws["!cols"] = [{ wch: 30 }, { wch: 18 }, { wch: 20 }];
  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, ws, "Saldos Terceros");
  XLSX.writeFile(wb, "saldos_terceros.xlsx");
}
