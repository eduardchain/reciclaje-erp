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
import { EntitySelect } from "@/components/shared/EntitySelect";
import { WarningsList } from "@/components/shared/WarningsList";
import { useSale, useLiquidateSale, useCancelSale } from "@/hooks/useSales";
import { useMoneyAccounts } from "@/hooks/useMasterData";
import { formatCurrency, formatDate, formatWeight, formatPercentage } from "@/utils/formatters";
import { ROUTES } from "@/utils/constants";
import { exportSalePDF } from "@/utils/pdfExport";

const statusBorderMap: Record<string, string> = {
  registered: "border-t-[3px] border-t-amber-400",
  paid: "border-t-[3px] border-t-emerald-400",
  cancelled: "border-t-[3px] border-t-rose-400",
};

export default function SaleDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { data: sale, isLoading } = useSale(id!);
  const { data: accountsData } = useMoneyAccounts();
  const liquidate = useLiquidateSale();
  const cancel = useCancelSale();

  const [showLiquidate, setShowLiquidate] = useState(false);
  const [showCancel, setShowCancel] = useState(false);
  const [paymentAccountId, setPaymentAccountId] = useState("");

  const accounts = accountsData?.items ?? [];

  const handleLiquidate = () => {
    if (!id || !paymentAccountId) return;
    liquidate.mutate(
      { id, data: { payment_account_id: paymentAccountId } },
      { onSuccess: () => { setShowLiquidate(false); setPaymentAccountId(""); } },
    );
  };

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

  return (
    <div className="space-y-6">
      <PageHeader title={`Venta #${sale.sale_number}`} description={`Cliente: ${sale.customer_name}`}>
        <div className="flex items-center gap-2">
          {sale.status === "registered" && !sale.double_entry_id && (
            <>
              <Button variant="outline" onClick={() => navigate(`/sales/${id}/edit`)}>
                <Pencil className="h-4 w-4 mr-2" />Editar
              </Button>
              <Button onClick={() => setShowLiquidate(true)} className="bg-emerald-600 hover:bg-emerald-700">
                <CreditCard className="h-4 w-4 mr-2" />Cobrar
              </Button>
              <Button variant="outline" onClick={() => setShowCancel(true)} className="text-red-600 border-red-200 hover:bg-red-50">
                <XCircle className="h-4 w-4 mr-2" />Cancelar
              </Button>
            </>
          )}
          <Button variant="outline" onClick={() => exportSalePDF(sale)}>
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
              <div className="flex justify-between"><dt className="text-xs font-semibold uppercase tracking-wider text-slate-500">Utilidad</dt><dd className={`font-bold ${sale.total_profit >= 0 ? "text-emerald-700" : "text-red-700"}`}>{formatCurrency(sale.total_profit)}</dd></div>
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
              <div className="flex justify-between"><dt className="text-xs font-semibold uppercase tracking-wider text-slate-500">Creada</dt><dd>{formatDate(sale.created_at)}</dd></div>
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
                  <TableHead className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 h-10 text-right">Cantidad</TableHead>
                  <TableHead className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 h-10 text-right">Precio Unit.</TableHead>
                  <TableHead className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 h-10 text-right">Costo Unit.</TableHead>
                  <TableHead className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 h-10 text-right">Total</TableHead>
                  <TableHead className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 h-10 text-right">Utilidad</TableHead>
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
                    <TableCell className="text-right tabular-nums">{formatCurrency(line.unit_price)}</TableCell>
                    <TableCell className="text-right tabular-nums text-slate-500">{formatCurrency(line.unit_cost)}</TableCell>
                    <TableCell className="text-right tabular-nums font-medium">{formatCurrency(line.total_price)}</TableCell>
                    <TableCell className={`text-right tabular-nums font-medium ${line.profit >= 0 ? "text-emerald-700" : "text-red-700"}`}>{formatCurrency(line.profit)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
          <div className="bg-slate-50 rounded-lg p-3 mt-3">
            <div className="flex justify-end gap-8">
              <span className="text-lg font-bold">Total: {formatCurrency(sale.total_amount)}</span>
              <span className={`text-lg font-bold ${sale.total_profit >= 0 ? "text-emerald-700" : "text-red-700"}`}>Utilidad: {formatCurrency(sale.total_profit)}</span>
            </div>
          </div>
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

      {/* Liquidate Dialog */}
      <ConfirmDialog
        open={showLiquidate}
        onOpenChange={setShowLiquidate}
        title="Cobrar Venta"
        description="Seleccione la cuenta donde se recibira el pago."
        confirmLabel="Cobrar"
        onConfirm={handleLiquidate}
        loading={liquidate.isPending}
        disabled={!paymentAccountId}
      >
        <div className="py-2">
          <EntitySelect
            value={paymentAccountId}
            onChange={setPaymentAccountId}
            options={accounts.map((a) => ({ id: a.id, label: a.name }))}
            placeholder="Seleccionar cuenta..."
          />
        </div>
      </ConfirmDialog>

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
