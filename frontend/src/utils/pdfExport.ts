import { jsPDF } from "jspdf";
import type { PurchaseResponse } from "@/types/purchase";
import type { SaleResponse } from "@/types/sale";
import type { DoubleEntryResponse } from "@/types/double-entry";
import type { BalanceSheetResponse, BalanceDetailedResponse } from "@/types/reports";
import { formatCurrency, formatDate, formatWeight, formatPercentage } from "@/utils/formatters";

export interface AccountStatementExportData {
  thirdPartyName: string;
  dateFrom?: string;
  dateTo?: string;
  currentBalance: number;
  totalDebit: number;
  totalCredit: number;
  openingBalance: number;
  viewMode?: "financial" | "operations";
  movements: Array<{
    movement_number: string | number;
    date: string;
    movement_type: string;
    typeLabel: string;
    description: string;
    amount: number;
    status: string;
    balance_after: number | null;
    isDebit: boolean;
    vehicle_plate?: string | null;
    invoice_number?: string | null;
    material_code?: string | null;
    material_name?: string | null;
    quantity?: number | null;
    unit_price?: number | null;
    received_quantity?: number | null;
    is_line_item?: boolean;
    parent_source_id?: string | null;
    source_number?: number | string | null;
  }>;
}

const STATUS_LABELS: Record<string, string> = {
  registered: "Registrada",
  liquidated: "Liquidada",
  cancelled: "Cancelada",
};

export function exportPurchasePDF(purchase: PurchaseResponse, orgName?: string) {
  const doc = new jsPDF();
  const pageWidth = doc.internal.pageSize.getWidth();
  let y = 20;

  // Header
  doc.setFontSize(18);
  doc.setFont("helvetica", "bold");
  doc.text(orgName || "EcoBalance ERP", 14, y);
  y += 8;

  doc.setFontSize(14);
  doc.text(`Compra #${purchase.purchase_number}`, 14, y);

  // Estado badge (derecha)
  doc.setFontSize(10);
  doc.setFont("helvetica", "normal");
  const statusText = STATUS_LABELS[purchase.status] ?? purchase.status;
  doc.text(statusText, pageWidth - 14, y, { align: "right" });
  y += 12;

  // Linea separadora
  doc.setDrawColor(200);
  doc.line(14, y, pageWidth - 14, y);
  y += 8;

  // Info general
  doc.setFontSize(10);
  doc.setFont("helvetica", "bold");
  doc.text("Proveedor:", 14, y);
  doc.setFont("helvetica", "normal");
  doc.text(purchase.supplier_name, 55, y);

  doc.setFont("helvetica", "bold");
  doc.text("Fecha:", pageWidth / 2 + 10, y);
  doc.setFont("helvetica", "normal");
  doc.text(formatDate(purchase.date), pageWidth / 2 + 35, y);
  y += 6;

  if (purchase.vehicle_plate) {
    doc.setFont("helvetica", "bold");
    doc.text("Placa:", 14, y);
    doc.setFont("helvetica", "normal");
    doc.text(purchase.vehicle_plate, 55, y);
    y += 6;
  }

  if (purchase.invoice_number) {
    doc.setFont("helvetica", "bold");
    doc.text("Factura:", 14, y);
    doc.setFont("helvetica", "normal");
    doc.text(purchase.invoice_number, 55, y);
    y += 6;
  }

  if (purchase.payment_account_name) {
    doc.setFont("helvetica", "bold");
    doc.text("Cuenta Pago:", 14, y);
    doc.setFont("helvetica", "normal");
    doc.text(purchase.payment_account_name, 55, y);
    y += 6;
  }

  if (purchase.notes) {
    doc.setFont("helvetica", "bold");
    doc.text("Notas:", 14, y);
    doc.setFont("helvetica", "normal");
    doc.text(purchase.notes, 55, y);
    y += 6;
  }

  y += 6;

  // Tabla de lineas - Header
  const colX = { material: 14, warehouse: 80, qty: 120, price: 148, total: 176 };
  doc.setFillColor(245, 245, 245);
  doc.rect(14, y - 4, pageWidth - 28, 8, "F");
  doc.setFont("helvetica", "bold");
  doc.setFontSize(9);
  doc.text("Material", colX.material, y);
  doc.text("Bodega", colX.warehouse, y);
  doc.text("Cantidad", colX.qty, y, { align: "right" });
  doc.text("Precio Unit.", colX.price, y, { align: "right" });
  doc.text("Total", pageWidth - 14, y, { align: "right" });
  y += 7;

  // Tabla de lineas - Rows
  doc.setFont("helvetica", "normal");
  doc.setFontSize(9);
  for (const line of purchase.lines) {
    if (y > 270) {
      doc.addPage();
      y = 20;
    }
    doc.text(`${line.material_code} - ${line.material_name}`.substring(0, 35), colX.material, y);
    doc.text((line.warehouse_name ?? "-").substring(0, 18), colX.warehouse, y);
    doc.text(formatWeight(line.quantity), colX.qty, y, { align: "right" });
    doc.text(formatCurrency(line.unit_price), colX.price, y, { align: "right" });
    doc.text(formatCurrency(line.total_price), pageWidth - 14, y, { align: "right" });
    y += 6;
  }

  // Total
  y += 4;
  doc.setDrawColor(200);
  doc.line(colX.price - 10, y - 3, pageWidth - 14, y - 3);
  doc.setFontSize(12);
  doc.setFont("helvetica", "bold");
  doc.text(`Total: ${formatCurrency(purchase.total_amount)}`, pageWidth - 14, y + 2, { align: "right" });

  // Descargar
  doc.save(`compra_${purchase.purchase_number}.pdf`);
}

const SALE_STATUS_LABELS: Record<string, string> = {
  registered: "Registrada",
  liquidated: "Liquidada",
  cancelled: "Cancelada",
};

export function exportSalePDF(sale: SaleResponse, orgName?: string, options?: { showPrices?: boolean; showProfit?: boolean }) {
  const showPrices = options?.showPrices !== false;
  const showProfit = options?.showProfit !== false;
  const doc = new jsPDF();
  const pageWidth = doc.internal.pageSize.getWidth();
  let y = 20;

  // Header
  doc.setFontSize(18);
  doc.setFont("helvetica", "bold");
  doc.text(orgName || "EcoBalance ERP", 14, y);
  y += 8;

  doc.setFontSize(14);
  doc.text(`Venta #${sale.sale_number}`, 14, y);

  doc.setFontSize(10);
  doc.setFont("helvetica", "normal");
  const statusText = SALE_STATUS_LABELS[sale.status] ?? sale.status;
  doc.text(statusText, pageWidth - 14, y, { align: "right" });
  y += 12;

  doc.setDrawColor(200);
  doc.line(14, y, pageWidth - 14, y);
  y += 8;

  // Info general
  doc.setFontSize(10);
  doc.setFont("helvetica", "bold");
  doc.text("Cliente:", 14, y);
  doc.setFont("helvetica", "normal");
  doc.text(sale.customer_name, 55, y);

  doc.setFont("helvetica", "bold");
  doc.text("Fecha:", pageWidth / 2 + 10, y);
  doc.setFont("helvetica", "normal");
  doc.text(formatDate(sale.date), pageWidth / 2 + 35, y);
  y += 6;

  if (sale.warehouse_name) {
    doc.setFont("helvetica", "bold");
    doc.text("Bodega:", 14, y);
    doc.setFont("helvetica", "normal");
    doc.text(sale.warehouse_name, 55, y);
    y += 6;
  }

  if (sale.vehicle_plate) {
    doc.setFont("helvetica", "bold");
    doc.text("Placa:", 14, y);
    doc.setFont("helvetica", "normal");
    doc.text(sale.vehicle_plate, 55, y);
    y += 6;
  }

  if (sale.invoice_number) {
    doc.setFont("helvetica", "bold");
    doc.text("Factura:", 14, y);
    doc.setFont("helvetica", "normal");
    doc.text(sale.invoice_number, 55, y);
    y += 6;
  }

  if (sale.payment_account_name) {
    doc.setFont("helvetica", "bold");
    doc.text("Cuenta Cobro:", 14, y);
    doc.setFont("helvetica", "normal");
    doc.text(sale.payment_account_name, 55, y);
    y += 6;
  }

  if (sale.notes) {
    doc.setFont("helvetica", "bold");
    doc.text("Notas:", 14, y);
    doc.setFont("helvetica", "normal");
    doc.text(sale.notes, 55, y);
    y += 6;
  }

  y += 6;

  // Tabla de lineas - Header
  const colX = { material: 14, qty: 90, price: 118, cost: 146, total: 170, profit: 196 };
  doc.setFillColor(245, 245, 245);
  doc.rect(14, y - 4, pageWidth - 28, 8, "F");
  doc.setFont("helvetica", "bold");
  doc.setFontSize(9);
  doc.text("Material", colX.material, y);
  doc.text("Cantidad", colX.qty, y, { align: "right" });
  if (showPrices) {
    doc.text("Precio U.", colX.price, y, { align: "right" });
    doc.text("Costo U.", colX.cost, y, { align: "right" });
    doc.text("Total", colX.total, y, { align: "right" });
  }
  if (showProfit) doc.text("Utilidad", pageWidth - 14, y, { align: "right" });
  y += 7;

  // Tabla de lineas - Rows
  doc.setFont("helvetica", "normal");
  doc.setFontSize(9);
  for (const line of sale.lines) {
    if (y > 270) {
      doc.addPage();
      y = 20;
    }
    doc.text(`${line.material_code} - ${line.material_name}`.substring(0, 40), colX.material, y);
    doc.text(formatWeight(line.quantity), colX.qty, y, { align: "right" });
    if (showPrices) {
      doc.text(formatCurrency(line.unit_price), colX.price, y, { align: "right" });
      doc.text(formatCurrency(line.unit_cost), colX.cost, y, { align: "right" });
      doc.text(formatCurrency(line.total_price), colX.total, y, { align: "right" });
    }
    if (showProfit) doc.text(formatCurrency(line.profit), pageWidth - 14, y, { align: "right" });
    y += 6;
  }

  // Comisiones (solo si puede ver profit)
  if (showProfit && sale.commissions.length > 0) {
    y += 6;
    doc.setFont("helvetica", "bold");
    doc.setFontSize(10);
    doc.text("Comisiones", 14, y);
    y += 6;

    doc.setFillColor(245, 245, 245);
    doc.rect(14, y - 4, pageWidth - 28, 8, "F");
    doc.setFontSize(9);
    doc.text("Comisionista", 14, y);
    doc.text("Concepto", 70, y);
    doc.text("Tipo", 120, y);
    doc.text("Valor", 150, y, { align: "right" });
    doc.text("Monto", pageWidth - 14, y, { align: "right" });
    y += 7;

    doc.setFont("helvetica", "normal");
    for (const comm of sale.commissions) {
      if (y > 270) {
        doc.addPage();
        y = 20;
      }
      doc.text(comm.third_party_name.substring(0, 28), 14, y);
      doc.text(comm.concept.substring(0, 24), 70, y);
      doc.text(comm.commission_type === "percentage" ? "%" : "Fijo", 120, y);
      doc.text(String(comm.commission_value), 150, y, { align: "right" });
      doc.text(formatCurrency(comm.commission_amount), pageWidth - 14, y, { align: "right" });
      y += 6;
    }
  }

  // Footer totales
  y += 6;
  doc.setDrawColor(200);
  doc.line(colX.total - 10, y - 3, pageWidth - 14, y - 3);
  doc.setFontSize(12);
  doc.setFont("helvetica", "bold");
  if (showPrices) {
    doc.text(`Total: ${formatCurrency(sale.total_amount)}`, pageWidth - 14, y + 2, { align: "right" });
    y += 8;
  }
  if (showProfit) {
    doc.setFontSize(10);
    doc.text(`Utilidad: ${formatCurrency(sale.total_profit)}`, pageWidth - 14, y + 2, { align: "right" });
  }

  doc.save(`venta_${sale.sale_number}.pdf`);
}

const DE_STATUS_LABELS: Record<string, string> = {
  registered: "Registrada",
  liquidated: "Liquidada",
  cancelled: "Cancelada",
};

export function exportDoubleEntryPDF(de: DoubleEntryResponse, orgName?: string, options?: { showProfit?: boolean }) {
  const showProfit = options?.showProfit !== false;
  const doc = new jsPDF();
  const pageWidth = doc.internal.pageSize.getWidth();
  let y = 20;

  // Header
  doc.setFontSize(18);
  doc.setFont("helvetica", "bold");
  doc.text(orgName || "EcoBalance ERP", 14, y);
  y += 8;

  doc.setFontSize(14);
  doc.text(`Doble Partida #${de.double_entry_number}`, 14, y);

  doc.setFontSize(10);
  doc.setFont("helvetica", "normal");
  const statusText = DE_STATUS_LABELS[de.status] ?? de.status;
  doc.text(statusText, pageWidth - 14, y, { align: "right" });
  y += 12;

  doc.setDrawColor(200);
  doc.line(14, y, pageWidth - 14, y);
  y += 8;

  // Info general — Proveedor y Cliente
  doc.setFontSize(10);
  doc.setFont("helvetica", "bold");
  doc.text("Proveedor:", 14, y);
  doc.setFont("helvetica", "normal");
  doc.text(de.supplier_name, 55, y);

  doc.setFont("helvetica", "bold");
  doc.text("Fecha:", pageWidth / 2 + 10, y);
  doc.setFont("helvetica", "normal");
  doc.text(formatDate(de.date), pageWidth / 2 + 35, y);
  y += 6;

  doc.setFont("helvetica", "bold");
  doc.text("Cliente:", 14, y);
  doc.setFont("helvetica", "normal");
  doc.text(de.customer_name, 55, y);
  y += 6;

  if (de.vehicle_plate) {
    doc.setFont("helvetica", "bold");
    doc.text("Placa:", 14, y);
    doc.setFont("helvetica", "normal");
    doc.text(de.vehicle_plate, 55, y);
    y += 6;
  }

  if (de.invoice_number) {
    doc.setFont("helvetica", "bold");
    doc.text("Factura:", 14, y);
    doc.setFont("helvetica", "normal");
    doc.text(de.invoice_number, 55, y);
    y += 6;
  }

  if (de.notes) {
    doc.setFont("helvetica", "bold");
    doc.text("Notas:", 14, y);
    doc.setFont("helvetica", "normal");
    doc.text(de.notes, 55, y);
    y += 6;
  }

  y += 6;

  // Tabla de materiales — Header
  const colX = { material: 14, qty: 72, pCompra: 98, pVenta: 124, tCompra: 150, tVenta: 172 };
  doc.setFillColor(245, 245, 245);
  doc.rect(14, y - 4, pageWidth - 28, 8, "F");
  doc.setFont("helvetica", "bold");
  doc.setFontSize(9);
  doc.text("Material", colX.material, y);
  doc.text("Cantidad", colX.qty, y, { align: "right" });
  doc.text("P. Compra", colX.pCompra, y, { align: "right" });
  doc.text("P. Venta", colX.pVenta, y, { align: "right" });
  doc.text("T. Compra", colX.tCompra, y, { align: "right" });
  doc.text("T. Venta", colX.tVenta, y, { align: "right" });
  if (showProfit) doc.text("Ganancia", pageWidth - 14, y, { align: "right" });
  y += 7;

  // Tabla de materiales — Rows
  doc.setFont("helvetica", "normal");
  doc.setFontSize(9);
  for (const line of de.lines) {
    if (y > 270) {
      doc.addPage();
      y = 20;
    }
    doc.text(`${line.material_code} - ${line.material_name}`.substring(0, 28), colX.material, y);
    doc.text(formatWeight(line.quantity), colX.qty, y, { align: "right" });
    doc.text(formatCurrency(line.purchase_unit_price), colX.pCompra, y, { align: "right" });
    doc.text(formatCurrency(line.sale_unit_price), colX.pVenta, y, { align: "right" });
    doc.text(formatCurrency(line.total_purchase), colX.tCompra, y, { align: "right" });
    doc.text(formatCurrency(line.total_sale), colX.tVenta, y, { align: "right" });
    if (showProfit) doc.text(formatCurrency(line.profit), pageWidth - 14, y, { align: "right" });
    y += 6;
  }

  // Comisiones
  if (showProfit && de.commissions.length > 0) {
    y += 6;
    doc.setFont("helvetica", "bold");
    doc.setFontSize(10);
    doc.text("Comisiones", 14, y);
    y += 6;

    doc.setFillColor(245, 245, 245);
    doc.rect(14, y - 4, pageWidth - 28, 8, "F");
    doc.setFontSize(9);
    doc.text("Comisionista", 14, y);
    doc.text("Concepto", 70, y);
    doc.text("Tipo", 120, y);
    doc.text("Valor", 150, y, { align: "right" });
    doc.text("Monto", pageWidth - 14, y, { align: "right" });
    y += 7;

    doc.setFont("helvetica", "normal");
    for (const comm of de.commissions) {
      if (y > 270) {
        doc.addPage();
        y = 20;
      }
      doc.text(comm.third_party_name.substring(0, 28), 14, y);
      doc.text(comm.concept.substring(0, 24), 70, y);
      doc.text(comm.commission_type === "percentage" ? "%" : "Fijo", 120, y);
      doc.text(String(comm.commission_value), 150, y, { align: "right" });
      doc.text(formatCurrency(comm.commission_amount), pageWidth - 14, y, { align: "right" });
      y += 6;
    }
  }

  // Resumen final
  y += 6;
  doc.setDrawColor(200);
  doc.line(colX.tCompra - 10, y - 3, pageWidth - 14, y - 3);

  const totalCommissions = de.commissions.reduce((sum, c) => sum + c.commission_amount, 0);
  const netProfit = de.profit - totalCommissions;

  doc.setFontSize(10);
  doc.setFont("helvetica", "normal");
  doc.text(`Total Compra: ${formatCurrency(de.total_purchase_cost)}`, pageWidth - 14, y + 2, { align: "right" });
  y += 6;
  doc.text(`Total Venta: ${formatCurrency(de.total_sale_amount)}`, pageWidth - 14, y + 2, { align: "right" });

  if (showProfit) {
    if (totalCommissions > 0) {
      y += 6;
      doc.text(`Comisiones: -${formatCurrency(totalCommissions)}`, pageWidth - 14, y + 2, { align: "right" });
    }

    y += 8;
    doc.setFontSize(12);
    doc.setFont("helvetica", "bold");
    doc.text(
      `Ganancia Neta: ${formatCurrency(totalCommissions > 0 ? netProfit : de.profit)}  (${formatPercentage(de.profit_margin)})`,
      pageWidth - 14,
      y + 2,
      { align: "right" },
    );
  }

  // Footer
  y += 14;
  doc.setFontSize(8);
  doc.setFont("helvetica", "normal");
  doc.setTextColor(150);
  doc.text(`Generado: ${new Date().toLocaleString("es-CO")}`, 14, y);
  doc.setTextColor(0);

  doc.save(`doble_partida_${de.double_entry_number}.pdf`);
}

export function exportAccountStatementPDF(data: AccountStatementExportData, orgName?: string) {
  const doc = new jsPDF();
  const pageWidth = doc.internal.pageSize.getWidth();
  let y = 20;

  // Header
  doc.setFontSize(18);
  doc.setFont("helvetica", "bold");
  doc.text(orgName || "EcoBalance ERP", 14, y);
  y += 8;

  doc.setFontSize(14);
  doc.text("Estado de Cuenta", 14, y);
  y += 8;

  doc.setFontSize(12);
  doc.setFont("helvetica", "normal");
  doc.text(data.thirdPartyName, 14, y);
  y += 8;

  // Periodo
  doc.setFontSize(10);
  if (data.dateFrom || data.dateTo) {
    const from = data.dateFrom || "...";
    const to = data.dateTo || "...";
    doc.text(`Periodo: ${from} - ${to}`, 14, y);
  } else if (data.movements.length > 0) {
    const firstDate = formatDate(data.movements[0].date);
    const lastDate = formatDate(data.movements[data.movements.length - 1].date);
    doc.text(`Periodo: ${firstDate} - ${lastDate}`, 14, y);
  }
  y += 6;

  // Linea separadora
  doc.setDrawColor(200);
  doc.line(14, y, pageWidth - 14, y);
  y += 8;

  // Resumen
  doc.setFontSize(10);
  doc.setFont("helvetica", "bold");
  doc.text("Saldo Actual:", 14, y);
  doc.setFont("helvetica", "normal");
  doc.text(formatCurrency(data.currentBalance), 60, y);

  doc.setFont("helvetica", "bold");
  doc.text("Total Debe:", pageWidth / 2, y);
  doc.setFont("helvetica", "normal");
  doc.text(formatCurrency(data.totalDebit), pageWidth / 2 + 40, y);
  y += 6;

  doc.setFont("helvetica", "bold");
  doc.text("Total Haber:", 14, y);
  doc.setFont("helvetica", "normal");
  doc.text(formatCurrency(data.totalCredit), 60, y);
  y += 10;

  const isOps = data.viewMode === "operations";

  if (isOps) {
    // Vista Operaciones: Fecha, Concepto, Material, Peso, Precio, Dif $, Debito, Credito, Saldo
    const colO = { date: 14, concept: 34, material: 72, weight: 108, price: 128, difPeso: 148, debit: 168, credit: 186 };
    doc.setFillColor(245, 245, 245);
    doc.rect(14, y - 4, pageWidth - 28, 8, "F");
    doc.setFont("helvetica", "bold");
    doc.setFontSize(7);
    doc.text("Fecha", colO.date, y);
    doc.text("Concepto", colO.concept, y);
    doc.text("Material", colO.material, y);
    doc.text("Peso", colO.weight, y, { align: "right" });
    doc.text("Precio", colO.price, y, { align: "right" });
    doc.text("Dif $", colO.difPeso, y, { align: "right" });
    doc.text("Debito", colO.debit, y, { align: "right" });
    doc.text("Credito", colO.credit, y, { align: "right" });
    doc.text("Saldo", pageWidth - 14, y, { align: "right" });
    y += 7;

    doc.setFont("helvetica", "normal");
    doc.setFontSize(7);

    if (data.dateFrom) {
      doc.setFont("helvetica", "italic");
      doc.text("Saldo de apertura", colO.date, y);
      doc.setFont("helvetica", "normal");
      doc.text(formatCurrency(data.openingBalance), pageWidth - 14, y, { align: "right" });
      y += 5;
    }

    // Build last-in-group set for balance display
    const lastByGroup = new Map<string, number>();
    data.movements.forEach((m, i) => {
      if (m.parent_source_id) lastByGroup.set(m.parent_source_id, i);
    });

    data.movements.forEach((m, idx) => {
      if (y > 270) { doc.addPage(); y = 20; }
      const concepto = m.is_line_item
        ? (m.vehicle_plate || m.invoice_number || `${m.movement_type?.includes("purchase") ? "Compra" : m.movement_type?.includes("sale") ? "Venta" : "DP"} #${m.source_number || ""}`)
        : (m.description || m.vehicle_plate || m.invoice_number || `#${m.source_number || ""}`);
      doc.text(formatDate(m.date), colO.date, y);
      doc.text(concepto.substring(0, 18), colO.concept, y);
      if (m.is_line_item && m.material_code) {
        doc.text(`${m.material_code}`.substring(0, 16), colO.material, y);
        if (m.quantity) doc.text(formatWeight(m.quantity), colO.weight, y, { align: "right" });
        if (m.unit_price) doc.text(formatCurrency(m.unit_price), colO.price, y, { align: "right" });
        const diffPesoMoney = m.received_quantity && m.quantity && m.unit_price && m.received_quantity !== m.quantity
          ? (m.received_quantity - m.quantity) * m.unit_price : null;
        if (diffPesoMoney != null) doc.text(formatCurrency(diffPesoMoney), colO.difPeso, y, { align: "right" });
      }
      if (m.isDebit) doc.text(formatCurrency(m.amount), colO.debit, y, { align: "right" });
      else doc.text(formatCurrency(m.amount), colO.credit, y, { align: "right" });
      // Show balance only on last item of group or non-grouped items
      const showBalance = !m.parent_source_id
        ? m.balance_after != null
        : lastByGroup.get(m.parent_source_id) === idx && m.balance_after != null;
      if (showBalance) doc.text(formatCurrency(m.balance_after!), pageWidth - 14, y, { align: "right" });
      y += 5;
    });
  } else {
    // Vista Financiera (original)
    const colX = { num: 14, date: 22, type: 44, desc: 84, debit: 148, credit: 172, balance: 196 };
    doc.setFillColor(245, 245, 245);
    doc.rect(14, y - 4, pageWidth - 28, 8, "F");
    doc.setFont("helvetica", "bold");
    doc.setFontSize(8);
    doc.text("#", colX.num, y);
    doc.text("Fecha", colX.date, y);
    doc.text("Tipo", colX.type, y);
    doc.text("Descripcion", colX.desc, y);
    doc.text("Debe", colX.debit, y, { align: "right" });
    doc.text("Haber", colX.credit, y, { align: "right" });
    doc.text("Saldo", pageWidth - 14, y, { align: "right" });
    y += 7;

    doc.setFont("helvetica", "normal");
    doc.setFontSize(8);

    if (data.dateFrom) {
      doc.setFont("helvetica", "italic");
      doc.text("Saldo de apertura", colX.date, y);
      doc.setFont("helvetica", "normal");
      doc.text(formatCurrency(data.openingBalance), pageWidth - 14, y, { align: "right" });
      y += 6;
    }

    for (const m of data.movements) {
      if (y > 270) { doc.addPage(); y = 20; }
      const isAnnulled = m.status === "annulled";
      const typeText = isAnnulled ? `${m.typeLabel} (Anulado)` : m.typeLabel;
      doc.text(String(m.movement_number), colX.num, y);
      doc.text(formatDate(m.date), colX.date, y);
      doc.text(typeText.substring(0, 22), colX.type, y);
      doc.text((m.description || "-").substring(0, 30), colX.desc, y);
      if (m.isDebit) doc.text(formatCurrency(m.amount), colX.debit, y, { align: "right" });
      else doc.text(formatCurrency(m.amount), colX.credit, y, { align: "right" });
      if (m.balance_after != null) doc.text(formatCurrency(m.balance_after), pageWidth - 14, y, { align: "right" });
      y += 5.5;
    }
  }

  // Footer
  y += 8;
  doc.setFontSize(8);
  doc.setTextColor(150);
  doc.text(`Generado: ${new Date().toLocaleString("es-CO")}`, 14, y);
  doc.setTextColor(0);

  const safeName = data.thirdPartyName.replace(/[^a-zA-Z0-9]/g, "_").substring(0, 30);
  doc.save(`estado_cuenta_${safeName}.pdf`);
}

export function exportBalanceSheetPDF(data: BalanceSheetResponse, orgName?: string) {
  const doc = new jsPDF();
  const pageWidth = doc.internal.pageSize.getWidth();
  let y = 20;

  // Header
  doc.setFontSize(18);
  doc.setFont("helvetica", "bold");
  doc.text(orgName || "EcoBalance ERP", 14, y);
  y += 8;

  doc.setFontSize(14);
  doc.text("Balance General", 14, y);
  y += 8;

  doc.setFontSize(10);
  doc.setFont("helvetica", "normal");
  doc.text(`Corte al: ${formatDate(data.as_of_date)}`, 14, y);
  y += 6;

  doc.setDrawColor(200);
  doc.line(14, y, pageWidth - 14, y);
  y += 10;

  // ACTIVOS
  doc.setFontSize(12);
  doc.setFont("helvetica", "bold");
  doc.setTextColor(30, 64, 175); // blue
  doc.text("ACTIVOS", 14, y);
  doc.setTextColor(0);
  y += 8;

  doc.setFontSize(10);
  doc.setFont("helvetica", "normal");

  const assetItems: [string, number][] = [
    ["Caja y Bancos", data.assets.cash_and_bank],
    ["Cuentas por Cobrar", data.assets.accounts_receivable],
    ["Inventario", data.assets.inventory],
    ["Anticipos", data.assets.advances],
    ["CxC Inversionistas", data.assets.investor_receivable],
    ["Gastos Prepagados", data.assets.prepaid_expenses],
    ["Fondos de Provisión", data.assets.provision_funds],
    ["Activos Fijos", data.assets.fixed_assets],
  ];

  for (const [label, value] of assetItems) {
    if (value === 0) continue;
    doc.text(label, 20, y);
    doc.text(formatCurrency(value), pageWidth - 14, y, { align: "right" });
    y += 6;
  }

  y += 2;
  doc.setDrawColor(200);
  doc.line(14, y - 3, pageWidth - 14, y - 3);
  doc.setFont("helvetica", "bold");
  doc.text("Total Activos", 20, y + 2);
  doc.text(formatCurrency(data.total_assets), pageWidth - 14, y + 2, { align: "right" });
  y += 14;

  // PASIVOS
  doc.setFontSize(12);
  doc.setFont("helvetica", "bold");
  doc.setTextColor(185, 28, 28); // red
  doc.text("PASIVOS", 14, y);
  doc.setTextColor(0);
  y += 8;

  doc.setFontSize(10);
  doc.setFont("helvetica", "normal");

  const liabilityItems: [string, number][] = [
    ["Cuentas por Pagar", data.liabilities.accounts_payable],
    ["Deuda Inversionistas", data.liabilities.investor_debt],
    ["Pasivos", data.liabilities.liability_debt],
    ["Proveedores Servicios", data.liabilities.service_provider_payable],
    ["Anticipos de Clientes", data.liabilities.customer_advances],
    ["Obligaciones Provisión", data.liabilities.provision_obligations],
    ["Otros Pasivos", data.liabilities.generic_payable],
  ];

  for (const [label, value] of liabilityItems) {
    if (value === 0) continue;
    doc.text(label, 20, y);
    doc.text(formatCurrency(value), pageWidth - 14, y, { align: "right" });
    y += 6;
  }

  y += 2;
  doc.setDrawColor(200);
  doc.line(14, y - 3, pageWidth - 14, y - 3);
  doc.setFont("helvetica", "bold");
  doc.text("Total Pasivos", 20, y + 2);
  doc.text(formatCurrency(data.total_liabilities), pageWidth - 14, y + 2, { align: "right" });
  y += 14;

  // PATRIMONIO
  doc.setFontSize(12);
  doc.setFont("helvetica", "bold");
  doc.setTextColor(4, 120, 87); // emerald
  doc.text("PATRIMONIO", 14, y);
  doc.setTextColor(0);
  y += 8;

  doc.setFontSize(10);
  doc.setFont("helvetica", "normal");

  if (data.accumulated_profit !== 0 || data.distributed_profit !== 0) {
    doc.text("Utilidad Acumulada", 20, y);
    doc.text(formatCurrency(data.accumulated_profit), pageWidth - 14, y, { align: "right" });
    y += 6;
    doc.text("(-) Utilidades Distribuidas", 20, y);
    doc.text(formatCurrency(data.distributed_profit), pageWidth - 14, y, { align: "right" });
    y += 6;
  }

  y += 2;
  doc.setDrawColor(200);
  doc.line(14, y - 3, pageWidth - 14, y - 3);
  doc.setFont("helvetica", "bold");
  doc.text("Patrimonio Neto", 20, y + 2);
  doc.text(formatCurrency(data.equity), pageWidth - 14, y + 2, { align: "right" });

  // Footer
  y += 14;
  doc.setFontSize(8);
  doc.setFont("helvetica", "normal");
  doc.setTextColor(150);
  doc.text(`Generado: ${new Date().toLocaleString("es-CO")}`, 14, y);
  doc.setTextColor(0);

  doc.save("balance_general.pdf");
}

export function exportBalanceDetailedPDF(data: BalanceDetailedResponse, orgName?: string) {
  const doc = new jsPDF();
  const pageWidth = doc.internal.pageSize.getWidth();
  let y = 20;

  const ASSET_ORDER = [
    "cash_and_bank", "inventory_liquidated",
    "customers_receivable", "supplier_advances", "service_provider_advances",
    "liability_advances", "investor_receivable",
    "provision_funds", "prepaid_expenses", "generic_receivable", "fixed_assets",
  ];

  const LIABILITY_ORDER = [
    "suppliers_payable", "service_provider_payable", "liability_debt",
    "investors_partners", "investors_obligations",
    "investors_legacy", "customer_advances", "provision_obligations",
    "generic_payable",
  ];

  function fmtBal(value: number) {
    if (value < 0) return `(${formatCurrency(Math.abs(value))})`;
    return formatCurrency(value);
  }

  function checkPageBreak() {
    if (y > 270) {
      doc.addPage();
      y = 20;
    }
  }

  // Header
  doc.setFontSize(16);
  doc.setFont("helvetica", "bold");
  doc.text(orgName || "EcoBalance ERP", 14, y);
  y += 7;

  doc.setFontSize(13);
  doc.text("Balance Detallado", 14, y);
  y += 7;

  doc.setFontSize(9);
  doc.setFont("helvetica", "normal");
  doc.text(`Corte al: ${formatDate(data.as_of_date)}`, 14, y);
  y += 5;

  doc.setDrawColor(200);
  doc.line(14, y, pageWidth - 14, y);
  y += 8;

  function renderSections(
    sections: Record<string, { label: string; total: number; items: Array<{ name: string; balance: number }>; groups?: Array<{ label: string; total: number; items: Array<{ name: string; balance: number }> }> | null }>,
    order: string[],
    titleColor: [number, number, number],
    title: string,
    totalValue: number,
  ) {
    // Main title
    doc.setFontSize(11);
    doc.setFont("helvetica", "bold");
    doc.setTextColor(...titleColor);
    doc.text(title, 14, y);
    doc.text(fmtBal(totalValue), pageWidth - 14, y, { align: "right" });
    doc.setTextColor(0);
    y += 7;

    for (const key of order) {
      const section = sections[key];
      if (!section || section.total === 0) continue;

      checkPageBreak();

      // Section header
      doc.setFontSize(8);
      doc.setFont("helvetica", "bold");
      doc.setFillColor(245, 245, 245);
      doc.rect(14, y - 3.5, pageWidth - 28, 6, "F");
      doc.text(section.label, 16, y);
      doc.text(fmtBal(section.total), pageWidth - 16, y, { align: "right" });
      y += 6;

      // Items (grouped or flat)
      doc.setFontSize(7);
      doc.setFont("helvetica", "normal");

      if (section.groups && section.groups.length > 0) {
        for (const group of section.groups) {
          checkPageBreak();
          // Group header
          doc.setFont("helvetica", "bold");
          doc.setFontSize(7);
          doc.text(`  ${group.label}`, 16, y);
          doc.text(fmtBal(group.total), pageWidth - 16, y, { align: "right" });
          y += 5;
          doc.setFont("helvetica", "normal");

          for (const item of group.items) {
            checkPageBreak();
            doc.text(`    ${item.name}`, 16, y);
            doc.text(fmtBal(item.balance), pageWidth - 16, y, { align: "right" });
            y += 4.5;
          }
        }
      } else {
        for (const item of section.items) {
          checkPageBreak();
          doc.text(`  ${item.name}`, 16, y);
          doc.text(fmtBal(item.balance), pageWidth - 16, y, { align: "right" });
          y += 4.5;
        }
      }

      y += 2;
    }

    // Total line
    checkPageBreak();
    doc.setDrawColor(200);
    doc.line(14, y - 1, pageWidth - 14, y - 1);
    doc.setFontSize(9);
    doc.setFont("helvetica", "bold");
    doc.text(`Total ${title}`, 16, y + 3);
    doc.text(fmtBal(totalValue), pageWidth - 16, y + 3, { align: "right" });
    y += 10;
  }

  // Activos
  renderSections(data.assets, ASSET_ORDER, [30, 64, 175], "ACTIVOS", data.total_assets);

  // Pasivos
  renderSections(data.liabilities, LIABILITY_ORDER, [185, 28, 28], "PASIVOS", data.total_liabilities);

  // Patrimonio
  checkPageBreak();
  doc.setFontSize(11);
  doc.setFont("helvetica", "bold");
  doc.setTextColor(4, 120, 87);
  doc.text("PATRIMONIO", 14, y);
  doc.setTextColor(0);
  y += 7;

  doc.setFontSize(8);
  doc.setFont("helvetica", "normal");

  if (data.accumulated_profit !== 0 || data.distributed_profit !== 0) {
    doc.text("Utilidad Acumulada", 20, y);
    doc.text(fmtBal(data.accumulated_profit), pageWidth - 16, y, { align: "right" });
    y += 5;
    doc.text("(-) Utilidades Distribuidas", 20, y);
    doc.text(fmtBal(data.distributed_profit), pageWidth - 16, y, { align: "right" });
    y += 5;
  }

  doc.setDrawColor(200);
  doc.line(14, y - 1, pageWidth - 14, y - 1);
  doc.setFontSize(9);
  doc.setFont("helvetica", "bold");
  doc.text("Patrimonio Neto", 20, y + 3);
  doc.text(fmtBal(data.equity), pageWidth - 16, y + 3, { align: "right" });
  y += 12;

  // Footer
  doc.setFontSize(7);
  doc.setFont("helvetica", "normal");
  doc.setTextColor(150);
  doc.text(`Generado: ${new Date().toLocaleString("es-CO")}`, 14, y);
  doc.setTextColor(0);

  doc.save("balance_detallado.pdf");
}
