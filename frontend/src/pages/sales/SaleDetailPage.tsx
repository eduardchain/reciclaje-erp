import { useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { ArrowLeft, CreditCard, XCircle, Pencil, FileText } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { Skeleton } from "@/components/ui/skeleton";
import { PageHeader } from "@/components/shared/PageHeader";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { ConfirmDialog } from "@/components/shared/ConfirmDialog";
import { WarningsList } from "@/components/shared/WarningsList";
import { useSale, useCancelSale } from "@/hooks/useSales";
import { formatCurrency, formatDate, formatDateTime, formatWeight, formatPercentage } from "@/utils/formatters";
import { useAuthStore } from "@/stores/authStore";
import { ROUTES } from "@/utils/constants";
import { exportSalePDF } from "@/utils/pdfExport";

const statusBorderMap: Record<string, string> = {
  registered: "border-t-[3px] border-t-amber-400",
  liquidated: "border-t-[3px] border-t-emerald-400",
  cancelled: "border-t-[3px] border-t-rose-400",
};

export default function SaleDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { data: sale, isLoading } = useSale(id!);
  const { organizationId, organizations } = useAuthStore();
  const orgName = organizations.find((o) => o.id === organizationId)?.name ?? "";
  const cancel = useCancelSale();

  const [showCancel, setShowCancel] = useState(false);

  const handleCancel = () => {
    if (!id) return;
    cancel.mutate(id, { onSuccess: () => setShowCancel(false) });
  };

  if (isLoading) {
    return <div className="space-y-4"><Skeleton className="h-8 w-64" /><Skeleton className="h-64 w-full" /></div>;
  }

  if (!sale) {
    return <div className="text-center py-12 text-slate-500">Venta no encontrada</div>;
  }

  const totalCommissions = sale.commissions.reduce((sum, c) => sum + c.commission_amount, 0);
  const totalCost = sale.total_amount - sale.total_profit;
  const marginPct = sale.total_amount > 0 ? (sale.total_profit / sale.total_amount) * 100 : 0;
  const netProfit = sale.total_profit - totalCommissions;
  const netMarginPct = sale.total_amount > 0 ? (netProfit / sale.total_amount) * 100 : 0;

  return (
    <div className="space-y-6">
      <PageHeader title={`Venta #${sale.sale_number}`} description={`Cliente: ${sale.customer_name}`}>
        <div className="flex items-center gap-2">
          {sale.status === "registered" && !sale.double_entry_id && (
            <>
              <Button variant="outline" onClick={() => navigate(`/sales/${id}/edit`)}>
                <Pencil className="h-4 w-4 mr-2" />Editar
              </Button>
              <Button onClick={() => navigate(`/sales/${id}/liquidate`)} className="bg-emerald-600 hover:bg-emerald-700">
                <CreditCard className="h-4 w-4 mr-2" />Liquidar
              </Button>
            </>
          )}
          {(sale.status === "registered" || sale.status === "liquidated") && !sale.double_entry_id && (
            <Button variant="outline" onClick={() => setShowCancel(true)} className="text-red-600 border-red-200 hover:bg-red-50">
              <XCircle className="h-4 w-4 mr-2" />Cancelar
            </Button>
          )}
          <Button variant="outline" onClick={() => exportSalePDF(sale, orgName)}>
            <FileText className="h-4 w-4 mr-2" />PDF
          </Button>
          <Button variant="outline" onClick={() => navigate(ROUTES.SALES)}>
            <ArrowLeft className="h-4 w-4 mr-2" />Volver
          </Button>
        </div>
      </PageHeader>

      {sale.warnings.length > 0 && <WarningsList warnings={sale.warnings} />}

      {/* Info general */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card className={`shadow-sm ${statusBorderMap[sale.status] ?? ""}`}>
          <CardContent className="pt-6">
            <dl className="space-y-2 text-sm">
              <div className="flex justify-between"><dt className="text-xs font-semibold uppercase tracking-wider text-slate-500">Estado</dt><dd><StatusBadge status={sale.status} /></dd></div>
              <div className="flex justify-between"><dt className="text-xs font-semibold uppercase tracking-wider text-slate-500">Fecha</dt><dd>{formatDate(sale.date)}</dd></div>
              <div className="flex justify-between"><dt className="text-xs font-semibold uppercase tracking-wider text-slate-500">Total</dt><dd className="font-bold text-lg">{formatCurrency(sale.total_amount)}</dd></div>
              <div className="flex justify-between"><dt className="text-xs font-semibold uppercase tracking-wider text-slate-500">{totalCommissions > 0 ? "Utilidad Neta" : "Utilidad Bruta"}</dt><dd className={`font-bold ${(totalCommissions > 0 ? netProfit : sale.total_profit) >= 0 ? "text-emerald-700" : "text-red-700"}`}>{formatCurrency(totalCommissions > 0 ? netProfit : sale.total_profit)}</dd></div>
            </dl>
          </CardContent>
        </Card>

        <Card className="shadow-sm">
          <CardContent className="pt-6">
            <dl className="space-y-2 text-sm">
              <div className="flex justify-between"><dt className="text-xs font-semibold uppercase tracking-wider text-slate-500">Cliente</dt><dd>{sale.customer_name}</dd></div>
              {sale.warehouse_name && <div className="flex justify-between"><dt className="text-xs font-semibold uppercase tracking-wider text-slate-500">Bodega</dt><dd>{sale.warehouse_name}</dd></div>}
              {sale.vehicle_plate && <div className="flex justify-between"><dt className="text-xs font-semibold uppercase tracking-wider text-slate-500">Placa</dt><dd>{sale.vehicle_plate}</dd></div>}
              {sale.invoice_number && <div className="flex justify-between"><dt className="text-xs font-semibold uppercase tracking-wider text-slate-500">Factura</dt><dd>{sale.invoice_number}</dd></div>}
            </dl>
          </CardContent>
        </Card>

        <Card className="shadow-sm">
          <CardContent className="pt-6">
            <dl className="space-y-2 text-sm">
              {sale.payment_account_name && <div className="flex justify-between"><dt className="text-xs font-semibold uppercase tracking-wider text-slate-500">Cuenta Cobro</dt><dd>{sale.payment_account_name}</dd></div>}
              {sale.notes && <div><dt className="text-xs font-semibold uppercase tracking-wider text-slate-500 mb-1">Notas</dt><dd className="text-slate-700">{sale.notes}</dd></div>}
            </dl>
          </CardContent>
        </Card>
      </div>

      {/* Lineas */}
      <Card className="shadow-sm">
        <CardHeader><CardTitle className="text-sm font-semibold uppercase tracking-wider text-slate-500">Lineas de Venta</CardTitle></CardHeader>
        <CardContent>
          <div className="rounded-lg border border-slate-200/80 overflow-hidden">
            <Table>
              <TableHeader>
                <TableRow className="bg-slate-50/80 border-b border-slate-200/80">
                  <TableHead className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 h-10">Material</TableHead>
                  <TableHead className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 h-10 text-right">Despachado</TableHead>
                  {sale.lines.some((l) => l.received_quantity !== null) && (
                    <>
                      <TableHead className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 h-10 text-right">Recibido</TableHead>
                      <TableHead className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 h-10 text-right">Dif.</TableHead>
                    </>
                  )}
                  <TableHead className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 h-10 text-right">Precio Unit.</TableHead>
                  <TableHead className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 h-10 text-right">Costo Unit.</TableHead>
                  <TableHead className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 h-10 text-right">Total</TableHead>
                  <TableHead className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 h-10 text-right">Util. Bruta</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {sale.lines.map((line) => (
                  <TableRow key={line.id}>
                    <TableCell>
                      <span className="font-medium">{line.material_name}</span>
                      <span className="text-slate-400 ml-2 text-xs">{line.material_code}</span>
                    </TableCell>
                    <TableCell className="text-right tabular-nums">{formatWeight(line.quantity)}</TableCell>
                    {sale.lines.some((l) => l.received_quantity !== null) && (
                      <>
                        <TableCell className="text-right tabular-nums">
                          {line.received_quantity != null ? formatWeight(line.received_quantity) : <span className="text-slate-400">&mdash;</span>}
                        </TableCell>
                        <TableCell className="text-right tabular-nums">
                          {line.quantity_difference != null && Math.abs(line.quantity_difference) > 0.001 ? (
                            <div className={line.quantity_difference > 0 ? "text-emerald-600" : "text-red-600"}>
                              <div>{line.quantity_difference > 0 ? "+" : ""}{line.quantity_difference.toFixed(2)} kg</div>
                              {line.amount_difference != null && (
                                <div className="text-xs">
                                  ({line.amount_difference > 0 ? "+" : ""}{formatCurrency(line.amount_difference)})
                                </div>
                              )}
                            </div>
                          ) : (
                            <span className="text-slate-400">&mdash;</span>
                          )}
                        </TableCell>
                      </>
                    )}
                    <TableCell className="text-right tabular-nums">{formatCurrency(line.unit_price)}</TableCell>
                    <TableCell className="text-right tabular-nums text-slate-500">{formatCurrency(line.unit_cost)}</TableCell>
                    <TableCell className="text-right tabular-nums font-medium">{formatCurrency(line.total_price)}</TableCell>
                    <TableCell className={`text-right tabular-nums font-medium ${line.profit >= 0 ? "text-emerald-700" : "text-red-700"}`}>{formatCurrency(line.profit)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
          {sale.total_amount_difference != null && Math.abs(sale.total_amount_difference) > 0.01 && (
            <div className={`p-3 rounded-lg mt-3 ${sale.total_amount_difference > 0 ? "bg-emerald-50" : "bg-red-50"}`}>
              <div className="flex justify-between items-center text-sm">
                <span className="font-medium">
                  {sale.total_amount_difference > 0 ? "Ganancia" : "Perdida"} por diferencia de bascula:
                </span>
                <div className="text-right">
                  <span className={`font-bold ${sale.total_amount_difference > 0 ? "text-emerald-600" : "text-red-600"}`}>
                    {sale.total_amount_difference > 0 ? "+" : ""}{formatCurrency(sale.total_amount_difference)}
                  </span>
                  {sale.total_quantity_difference != null && (
                    <span className="text-slate-500 ml-2 text-xs">
                      ({sale.total_quantity_difference > 0 ? "+" : ""}{sale.total_quantity_difference.toFixed(2)} kg)
                    </span>
                  )}
                </div>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Comisiones */}
      {sale.commissions.length > 0 && (
        <Card className="shadow-sm">
          <CardHeader><CardTitle className="text-sm font-semibold uppercase tracking-wider text-slate-500">Comisiones</CardTitle></CardHeader>
          <CardContent>
            <div className="rounded-lg border border-slate-200/80 overflow-hidden">
              <Table>
                <TableHeader>
                  <TableRow className="bg-slate-50/80 border-b border-slate-200/80">
                    <TableHead className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 h-10">Comisionista</TableHead>
                    <TableHead className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 h-10">Concepto</TableHead>
                    <TableHead className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 h-10">Tipo</TableHead>
                    <TableHead className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 h-10 text-right">Valor</TableHead>
                    <TableHead className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 h-10 text-right">Monto</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {sale.commissions.map((c) => (
                    <TableRow key={c.id}>
                      <TableCell className="font-medium">{c.third_party_name}</TableCell>
                      <TableCell>{c.concept}</TableCell>
                      <TableCell>{c.commission_type === "percentage" ? "Porcentaje" : "Fijo"}</TableCell>
                      <TableCell className="text-right tabular-nums">
                        {c.commission_type === "percentage" ? formatPercentage(c.commission_value) : formatCurrency(c.commission_value)}
                      </TableCell>
                      <TableCell className="text-right tabular-nums font-medium">{formatCurrency(c.commission_amount)}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Resumen Financiero */}
      <Card className="shadow-sm">
        <CardHeader>
          <CardTitle className="text-sm font-semibold uppercase tracking-wider text-slate-500">Resumen Financiero</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="max-w-sm ml-auto space-y-2">
            <div className="flex justify-between text-sm">
              <span className="text-slate-600">Total Venta</span>
              <span className="font-bold tabular-nums text-base">{formatCurrency(sale.total_amount)}</span>
            </div>
            <div className="border-t border-slate-200 pt-2" />
            <div className="flex justify-between text-sm">
              <span className="text-slate-600">Costo de Venta</span>
              <span className="tabular-nums text-slate-500">{formatCurrency(totalCost)}</span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-slate-600">
                Utilidad Bruta <span className="text-xs text-slate-400">({marginPct.toFixed(1)}%)</span>
              </span>
              <span className={`font-semibold tabular-nums ${sale.total_profit >= 0 ? "text-emerald-600" : "text-red-600"}`}>
                {formatCurrency(sale.total_profit)}
              </span>
            </div>
            {totalCommissions > 0 && (
              <>
                <div className="flex justify-between text-sm">
                  <span className="text-slate-600">(-) Comisiones</span>
                  <span className="tabular-nums text-amber-600">-{formatCurrency(totalCommissions)}</span>
                </div>
                <div className="border-t border-dashed border-slate-200" />
                <div className="flex justify-between text-sm">
                  <span className="font-medium text-slate-700">
                    Utilidad Neta <span className="text-xs text-slate-400">({netMarginPct.toFixed(1)}%)</span>
                  </span>
                  <span className={`font-bold tabular-nums ${netProfit >= 0 ? "text-emerald-600" : "text-red-600"}`}>
                    {formatCurrency(netProfit)}
                  </span>
                </div>
              </>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Auditoria */}
      <Card className="shadow-sm">
        <CardHeader><CardTitle className="text-sm font-semibold uppercase tracking-wider text-slate-500">Auditoria</CardTitle></CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
            <div>
              <dt className="text-xs font-semibold uppercase tracking-wider text-slate-500">Creada por</dt>
              <dd className="mt-0.5">{sale.created_by_name ?? "-"}</dd>
              <dd className="text-xs text-slate-400">{formatDateTime(sale.created_at)}</dd>
            </div>
            {sale.liquidated_at && (
              <div>
                <dt className="text-xs font-semibold uppercase tracking-wider text-slate-500">Cobrada por</dt>
                <dd className="mt-0.5">{sale.liquidated_by_name ?? "-"}</dd>
                <dd className="text-xs text-slate-400">{formatDateTime(sale.liquidated_at)}</dd>
              </div>
            )}
            {sale.updated_by_name && (
              <div>
                <dt className="text-xs font-semibold uppercase tracking-wider text-slate-500">Editada por</dt>
                <dd className="mt-0.5">{sale.updated_by_name}</dd>
                <dd className="text-xs text-slate-400">{formatDateTime(sale.updated_at)}</dd>
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Cancel Dialog */}
      <ConfirmDialog
        open={showCancel}
        onOpenChange={setShowCancel}
        title="Cancelar Venta"
        description="Esta accion revertira los movimientos de inventario y saldos asociados. Esta seguro?"
        confirmLabel="Si, cancelar"
        variant="destructive"
        onConfirm={handleCancel}
        loading={cancel.isPending}
      />
    </div>
  );
}
