import { useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { ArrowLeft, FileText, XCircle, Pencil, CheckCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Table, TableBody, TableCell, TableFooter, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Skeleton } from "@/components/ui/skeleton";
import { PageHeader } from "@/components/shared/PageHeader";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { ConfirmDialog } from "@/components/shared/ConfirmDialog";
import { useDoubleEntry, useCancelDoubleEntry } from "@/hooks/useDoubleEntries";
import { formatCurrency, formatDate, formatWeight, formatPercentage } from "@/utils/formatters";
import { exportDoubleEntryPDF } from "@/utils/pdfExport";
import { useAuthStore } from "@/stores/authStore";
import { ROUTES } from "@/utils/constants";
import { usePermissions } from "@/hooks/usePermissions";

const statusBorderMap: Record<string, string> = {
  registered: "border-t-[3px] border-t-amber-400",
  liquidated: "border-t-[3px] border-t-emerald-400",
  cancelled: "border-t-[3px] border-t-rose-400",
};

export default function DoubleEntryDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { data: de, isLoading } = useDoubleEntry(id!);
  const cancel = useCancelDoubleEntry();
  const { hasPermission } = usePermissions();
  const canViewProfit = hasPermission("double_entries.view_profit");
  const [showCancel, setShowCancel] = useState(false);
  const { organizationId, organizations } = useAuthStore();
  const orgName = organizations.find((o) => o.id === organizationId)?.name ?? "";

  if (isLoading) return <div className="space-y-4"><Skeleton className="h-8 w-64" /><Skeleton className="h-64 w-full" /></div>;
  if (!de) return <div className="text-center py-12 text-slate-500">Doble partida no encontrada</div>;

  return (
    <div className="space-y-6">
      <PageHeader title={`Doble Partida #${de.double_entry_number}`} description={de.materials_summary}>
        <div className="flex items-center gap-2">
          {de.status === "registered" && hasPermission("double_entries.edit") && (
              <Button onClick={() => navigate(`/double-entries/${de.id}/edit`)} variant="outline">
                <Pencil className="h-4 w-4 mr-2" />Editar
              </Button>
          )}
          {de.status === "registered" && hasPermission("double_entries.liquidate") && (
              <Button onClick={() => navigate(`/double-entries/${de.id}/liquidate`)} className="bg-emerald-600 hover:bg-emerald-700">
                <CheckCircle className="h-4 w-4 mr-2" />Liquidar
              </Button>
          )}
          {de.status === "liquidated" && (
            <Button variant="outline" onClick={() => exportDoubleEntryPDF(de, orgName, { showProfit: canViewProfit })}>
              <FileText className="h-4 w-4 mr-2" />Exportar PDF
            </Button>
          )}
          {(de.status === "registered" || de.status === "liquidated") && hasPermission("double_entries.cancel") && (
            <Button variant="outline" onClick={() => setShowCancel(true)} className="text-red-600 border-red-200 hover:bg-red-50">
              <XCircle className="h-4 w-4 mr-2" />Cancelar
            </Button>
          )}
          <Button variant="outline" onClick={() => navigate(-1)}>
            <ArrowLeft className="h-4 w-4 mr-2" />Volver
          </Button>
        </div>
      </PageHeader>

      {/* Info general + Proveedor + Cliente */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card className={`shadow-sm ${statusBorderMap[de.status] ?? ""}`}>
          <CardContent className="pt-6">
            <dl className="space-y-2 text-sm">
              <div className="flex justify-between"><dt className="text-xs font-semibold uppercase tracking-wider text-slate-500">Estado</dt><dd><StatusBadge status={de.status} /></dd></div>
              <div className="flex justify-between"><dt className="text-xs font-semibold uppercase tracking-wider text-slate-500">Fecha</dt><dd>{formatDate(de.date)}</dd></div>
              {de.invoice_number && <div className="flex justify-between"><dt className="text-xs font-semibold uppercase tracking-wider text-slate-500">Factura</dt><dd>{de.invoice_number}</dd></div>}
              {de.vehicle_plate && <div className="flex justify-between"><dt className="text-xs font-semibold uppercase tracking-wider text-slate-500">Placa</dt><dd>{de.vehicle_plate}</dd></div>}
              {de.liquidated_at && <div className="flex justify-between"><dt className="text-xs font-semibold uppercase tracking-wider text-slate-500">Liquidada</dt><dd>{formatDate(de.liquidated_at)}</dd></div>}
              {de.cancelled_at && <div className="flex justify-between"><dt className="text-xs font-semibold uppercase tracking-wider text-slate-500">Cancelada</dt><dd>{formatDate(de.cancelled_at)}</dd></div>}
            </dl>
          </CardContent>
        </Card>

        <Card className="border-l-[3px] border-l-blue-500 shadow-sm">
          <CardHeader className="pb-2"><CardTitle className="text-sm font-semibold uppercase tracking-wider text-blue-700">Compra</CardTitle></CardHeader>
          <CardContent>
            <dl className="space-y-2 text-sm">
              <div className="flex justify-between"><dt className="text-xs font-semibold uppercase tracking-wider text-slate-500">Proveedor</dt><dd>{de.supplier_name}</dd></div>
              <div className="flex justify-between"><dt className="text-xs font-semibold uppercase tracking-wider text-slate-500">Total</dt><dd className="font-bold">{formatCurrency(de.total_purchase_cost)}</dd></div>
            </dl>
          </CardContent>
        </Card>

        <Card className="border-l-[3px] border-l-emerald-500 shadow-sm">
          <CardHeader className="pb-2"><CardTitle className="text-sm font-semibold uppercase tracking-wider text-emerald-700">Venta</CardTitle></CardHeader>
          <CardContent>
            <dl className="space-y-2 text-sm">
              <div className="flex justify-between"><dt className="text-xs font-semibold uppercase tracking-wider text-slate-500">Cliente</dt><dd>{de.customer_name}</dd></div>
              <div className="flex justify-between"><dt className="text-xs font-semibold uppercase tracking-wider text-slate-500">Total</dt><dd className="font-bold">{formatCurrency(de.total_sale_amount)}</dd></div>
            </dl>
          </CardContent>
        </Card>
      </div>

      {/* Tabla de Materiales (lineas) */}
      <Card className="shadow-sm">
        <CardHeader><CardTitle className="text-sm font-semibold uppercase tracking-wider text-slate-500">Materiales</CardTitle></CardHeader>
        <CardContent>
          <div className="rounded-lg border border-slate-200/80 overflow-hidden">
            <Table>
              <TableHeader>
                <TableRow className="bg-slate-50/80 border-b border-slate-200/80">
                  <TableHead className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 h-10">Material</TableHead>
                  <TableHead className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 h-10 text-right">Cantidad</TableHead>
                  <TableHead className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 h-10 text-right">P. Compra</TableHead>
                  <TableHead className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 h-10 text-right">P. Venta</TableHead>
                  <TableHead className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 h-10 text-right">Total Compra</TableHead>
                  <TableHead className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 h-10 text-right">Total Venta</TableHead>
                  {canViewProfit && <TableHead className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 h-10 text-right">Ganancia</TableHead>}
                </TableRow>
              </TableHeader>
              <TableBody>
                {de.lines.map((line) => (
                  <TableRow key={line.id}>
                    <TableCell><span className="font-medium">{line.material_name}</span> <span className="text-slate-400 text-xs">{line.material_code}</span></TableCell>
                    <TableCell className="text-right tabular-nums">{formatWeight(line.quantity)}</TableCell>
                    <TableCell className="text-right tabular-nums">{formatCurrency(line.purchase_unit_price)}</TableCell>
                    <TableCell className="text-right tabular-nums">{formatCurrency(line.sale_unit_price)}</TableCell>
                    <TableCell className="text-right tabular-nums">{formatCurrency(line.total_purchase)}</TableCell>
                    <TableCell className="text-right tabular-nums">{formatCurrency(line.total_sale)}</TableCell>
                    {canViewProfit && <TableCell className={`text-right tabular-nums font-medium ${line.profit >= 0 ? "text-emerald-700" : "text-red-700"}`}>{formatCurrency(line.profit)}</TableCell>}
                  </TableRow>
                ))}
              </TableBody>
              <TableFooter>
                <TableRow className="bg-slate-50/80 font-bold">
                  <TableCell colSpan={4}>Totales</TableCell>
                  <TableCell className="text-right tabular-nums">{formatCurrency(de.total_purchase_cost)}</TableCell>
                  <TableCell className="text-right tabular-nums">{formatCurrency(de.total_sale_amount)}</TableCell>
                  {canViewProfit && <TableCell className={`text-right tabular-nums ${de.profit >= 0 ? "text-emerald-700" : "text-red-700"}`}>{formatCurrency(de.profit)}</TableCell>}
                </TableRow>
              </TableFooter>
            </Table>
          </div>
        </CardContent>
      </Card>

      {/* Resumen Utilidad */}
      {canViewProfit && (
        <Card className="border-2 border-emerald-200 bg-emerald-50 shadow-sm">
          <CardContent className="pt-6 flex justify-between items-center">
            <div className="text-sm space-y-1">
              <div>Compra: {formatCurrency(de.total_purchase_cost)}</div>
              <div>Venta: {formatCurrency(de.total_sale_amount)}</div>
              <div>Margen: {formatPercentage(de.profit_margin)}</div>
            </div>
            <div className="text-right">
              <p className="text-sm text-slate-500">Utilidad</p>
              <p className={`text-3xl font-bold ${de.profit >= 0 ? "text-emerald-700" : "text-red-700"}`}>{formatCurrency(de.profit)}</p>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Comisiones */}
      {de.commissions.length > 0 && (
        <Card className="shadow-sm">
          <CardHeader><CardTitle className="text-sm font-semibold uppercase tracking-wider text-slate-500">Comisiones</CardTitle></CardHeader>
          <CardContent>
            <div className="rounded-lg border border-slate-200/80 overflow-hidden">
              <Table>
                <TableHeader>
                  <TableRow className="bg-slate-50/80 border-b border-slate-200/80">
                    <TableHead className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 h-10">Comisionista</TableHead>
                    <TableHead className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 h-10">Concepto</TableHead>
                    <TableHead className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 h-10 text-right">Monto</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {de.commissions.map((c) => (
                    <TableRow key={c.id}><TableCell>{c.third_party_name}</TableCell><TableCell>{c.concept}</TableCell><TableCell className="text-right font-medium">{formatCurrency(c.commission_amount)}</TableCell></TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          </CardContent>
        </Card>
      )}

      {de.notes && (
        <Card className="shadow-sm"><CardContent className="pt-6"><Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Notas</Label><p className="mt-1 text-sm">{de.notes}</p></CardContent></Card>
      )}

      <ConfirmDialog
        open={showCancel}
        onOpenChange={setShowCancel}
        title="Cancelar Doble Partida"
        description={`Esto ${de.status === "liquidated" ? "revertira los saldos y " : ""}cancelara la doble partida. Esta seguro?`}
        confirmLabel="Si, cancelar"
        variant="destructive"
        onConfirm={() => cancel.mutate(id!, { onSuccess: () => setShowCancel(false) })}
        loading={cancel.isPending}
      />
    </div>
  );
}
