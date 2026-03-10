import { jsPDF } from "jspdf";
import type { PurchaseResponse } from "@/types/purchase";
import type { SaleResponse } from "@/types/sale";
import type { DoubleEntryResponse } from "@/types/double-entry";
import { formatCurrency, formatDate, formatWeight, formatPercentage } from "@/utils/formatters";

export interface AccountStatementExportData {
  thirdPartyName: string;
  dateFrom?: string;
  dateTo?: string;
  currentBalance: number;
  totalDebit: number;
  totalCredit: number;
  openingBalance: number;
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

export function exportSalePDF(sale: SaleResponse, orgName?: string) {
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
  doc.text("Precio U.", colX.price, y, { align: "right" });
  doc.text("Costo U.", colX.cost, y, { align: "right" });
  doc.text("Total", colX.total, y, { align: "right" });
  doc.text("Utilidad", pageWidth - 14, y, { align: "right" });
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
    doc.text(formatCurrency(line.unit_price), colX.price, y, { align: "right" });
    doc.text(formatCurrency(line.unit_cost), colX.cost, y, { align: "right" });
    doc.text(formatCurrency(line.total_price), colX.total, y, { align: "right" });
    doc.text(formatCurrency(line.profit), pageWidth - 14, y, { align: "right" });
    y += 6;
  }

  // Comisiones
  if (sale.commissions.length > 0) {
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
  doc.text(`Total: ${formatCurrency(sale.total_amount)}`, pageWidth - 14, y + 2, { align: "right" });
  y += 8;
  doc.setFontSize(10);
  doc.text(`Utilidad: ${formatCurrency(sale.total_profit)}`, pageWidth - 14, y + 2, { align: "right" });

  doc.save(`venta_${sale.sale_number}.pdf`);
}

const DE_STATUS_LABELS: Record<string, string> = {
  completed: "Completada",
  cancelled: "Cancelada",
};

export function exportDoubleEntryPDF(de: DoubleEntryResponse, orgName?: string) {
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
  doc.text("Ganancia", pageWidth - 14, y, { align: "right" });
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
    doc.text(formatCurrency(line.profit), pageWidth - 14, y, { align: "right" });
    y += 6;
  }

  // Comisiones
  if (de.commissions.length > 0) {
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

  // Tabla Header
  const colX = { num: 14, date: 28, type: 58, desc: 118, debit: 152, credit: 174, balance: 196 };
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

  // Saldo de apertura
  if (data.dateFrom) {
    doc.setFont("helvetica", "italic");
    doc.text("Saldo de apertura", colX.date, y);
    doc.setFont("helvetica", "normal");
    doc.text(formatCurrency(data.openingBalance), pageWidth - 14, y, { align: "right" });
    y += 6;
  }

  // Movimientos
  for (const m of data.movements) {
    if (y > 270) {
      doc.addPage();
      y = 20;
    }
    const isAnnulled = m.status === "annulled";
    const typeText = isAnnulled ? `${m.typeLabel} (Anulado)` : m.typeLabel;

    doc.text(String(m.movement_number), colX.num, y);
    doc.text(formatDate(m.date), colX.date, y);
    doc.text(typeText.substring(0, 32), colX.type, y);
    doc.text((m.description || "-").substring(0, 16), colX.desc, y);

    if (m.isDebit) {
      doc.text(formatCurrency(m.amount), colX.debit, y, { align: "right" });
    } else {
      doc.text(formatCurrency(m.amount), colX.credit, y, { align: "right" });
    }

    if (m.balance_after != null) {
      doc.text(formatCurrency(m.balance_after), pageWidth - 14, y, { align: "right" });
    }
    y += 5.5;
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
