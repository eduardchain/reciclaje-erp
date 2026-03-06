import { jsPDF } from "jspdf";
import type { PurchaseResponse } from "@/types/purchase";
import type { SaleResponse } from "@/types/sale";
import { formatCurrency, formatDate, formatWeight } from "@/utils/formatters";

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
