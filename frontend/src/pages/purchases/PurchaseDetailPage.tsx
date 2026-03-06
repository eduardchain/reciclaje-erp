import { useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { ArrowLeft, CreditCard, XCircle, Pencil, FileText } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Skeleton } from "@/components/ui/skeleton";
import { PageHeader } from "@/components/shared/PageHeader";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { ConfirmDialog } from "@/components/shared/ConfirmDialog";
import { EntitySelect } from "@/components/shared/EntitySelect";
import { usePurchase, useLiquidatePurchase, useCancelPurchase } from "@/hooks/usePurchases";
import { useMoneyAccounts } from "@/hooks/useMasterData";
import { formatCurrency, formatDate, formatWeight } from "@/utils/formatters";
import { ROUTES } from "@/utils/constants";
import { exportPurchasePDF } from "@/utils/pdfExport";

const statusBorderMap: Record<string, string> = {
  registered: "border-t-[3px] border-t-amber-400",
  paid: "border-t-[3px] border-t-emerald-400",
  cancelled: "border-t-[3px] border-t-rose-400",
};

export default function PurchaseDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { data: purchase, isLoading } = usePurchase(id!);
  const { data: accountsData } = useMoneyAccounts();
  const liquidate = useLiquidatePurchase();
  const cancel = useCancelPurchase();

  const [showLiquidate, setShowLiquidate] = useState(false);
  const [showCancel, setShowCancel] = useState(false);
  const [paymentAccountId, setPaymentAccountId] = useState("");

  const accounts = accountsData?.items ?? [];

  const handleLiquidate = () => {
    if (!id || !paymentAccountId) return;
    liquidate.mutate(
      { id, data: { payment_account_id: paymentAccountId } },
      {
        onSuccess: () => {
          setShowLiquidate(false);
          setPaymentAccountId("");
        },
      },
    );
  };

  const handleCancel = () => {
    if (!id) return;
    cancel.mutate(id, {
      onSuccess: () => setShowCancel(false),
    });
  };

  if (isLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  if (!purchase) {
    return <div className="text-center py-12 text-slate-500">Compra no encontrada</div>;
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title={`Compra #${purchase.purchase_number}`}
        description={`Proveedor: ${purchase.supplier_name}`}
      >
        <div className="flex items-center gap-2">
          {purchase.status === "registered" && !purchase.double_entry_id && (
            <>
              <Button variant="outline" onClick={() => navigate(`/purchases/${id}/edit`)}>
                <Pencil className="h-4 w-4 mr-2" />
                Editar
              </Button>
              <Button onClick={() => setShowLiquidate(true)} className="bg-emerald-600 hover:bg-emerald-700">
                <CreditCard className="h-4 w-4 mr-2" />
                Liquidar
              </Button>
              <Button variant="outline" onClick={() => setShowCancel(true)} className="text-red-600 border-red-200 hover:bg-red-50">
                <XCircle className="h-4 w-4 mr-2" />
                Cancelar
              </Button>
            </>
          )}
          <Button variant="outline" onClick={() => exportPurchasePDF(purchase)}>
            <FileText className="h-4 w-4 mr-2" />
            PDF
          </Button>
          <Button variant="outline" onClick={() => navigate(ROUTES.PURCHASES)}>
            <ArrowLeft className="h-4 w-4 mr-2" />
            Volver
          </Button>
        </div>
      </PageHeader>

      {/* Info general */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card className={`shadow-sm ${statusBorderMap[purchase.status] ?? ""}`}>
          <CardContent className="pt-6">
            <dl className="space-y-2 text-sm">
              <div className="flex justify-between">
                <dt className="text-xs font-semibold uppercase tracking-wider text-slate-500">Estado</dt>
                <dd><StatusBadge status={purchase.status} /></dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-xs font-semibold uppercase tracking-wider text-slate-500">Fecha</dt>
                <dd>{formatDate(purchase.date)}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-xs font-semibold uppercase tracking-wider text-slate-500">Total</dt>
                <dd className="font-bold text-lg">{formatCurrency(purchase.total_amount)}</dd>
              </div>
            </dl>
          </CardContent>
        </Card>

        <Card className="shadow-sm">
          <CardContent className="pt-6">
            <dl className="space-y-2 text-sm">
              <div className="flex justify-between">
                <dt className="text-xs font-semibold uppercase tracking-wider text-slate-500">Proveedor</dt>
                <dd>{purchase.supplier_name}</dd>
              </div>
              {purchase.vehicle_plate && (
                <div className="flex justify-between">
                  <dt className="text-xs font-semibold uppercase tracking-wider text-slate-500">Placa</dt>
                  <dd>{purchase.vehicle_plate}</dd>
                </div>
              )}
              {purchase.invoice_number && (
                <div className="flex justify-between">
                  <dt className="text-xs font-semibold uppercase tracking-wider text-slate-500">Factura</dt>
                  <dd>{purchase.invoice_number}</dd>
                </div>
              )}
            </dl>
          </CardContent>
        </Card>

        <Card className="shadow-sm">
          <CardContent className="pt-6">
            <dl className="space-y-2 text-sm">
              {purchase.payment_account_name && (
                <div className="flex justify-between">
                  <dt className="text-xs font-semibold uppercase tracking-wider text-slate-500">Cuenta Pago</dt>
                  <dd>{purchase.payment_account_name}</dd>
                </div>
              )}
              {purchase.notes && (
                <div>
                  <dt className="text-xs font-semibold uppercase tracking-wider text-slate-500 mb-1">Notas</dt>
                  <dd className="text-slate-700">{purchase.notes}</dd>
                </div>
              )}
              <div className="flex justify-between">
                <dt className="text-xs font-semibold uppercase tracking-wider text-slate-500">Creada</dt>
                <dd>{formatDate(purchase.created_at)}</dd>
              </div>
            </dl>
          </CardContent>
        </Card>
      </div>

      {/* Lineas */}
      <Card className="shadow-sm">
        <CardHeader>
          <CardTitle className="text-sm font-semibold uppercase tracking-wider text-slate-500">Lineas de Compra</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="rounded-lg border border-slate-200/80 overflow-hidden">
            <Table>
              <TableHeader>
                <TableRow className="bg-slate-50/80 border-b border-slate-200/80">
                  <TableHead className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 h-10">Material</TableHead>
                  <TableHead className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 h-10">Bodega</TableHead>
                  <TableHead className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 h-10 text-right">Cantidad</TableHead>
                  <TableHead className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 h-10 text-right">Precio Unit.</TableHead>
                  <TableHead className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 h-10 text-right">Total</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {purchase.lines.map((line) => (
                  <TableRow key={line.id}>
                    <TableCell>
                      <div>
                        <span className="font-medium">{line.material_name}</span>
                        <span className="text-slate-400 ml-2 text-xs">{line.material_code}</span>
                      </div>
                    </TableCell>
                    <TableCell>{line.warehouse_name ?? "-"}</TableCell>
                    <TableCell className="text-right tabular-nums">{formatWeight(line.quantity)}</TableCell>
                    <TableCell className="text-right tabular-nums">{formatCurrency(line.unit_price)}</TableCell>
                    <TableCell className="text-right tabular-nums font-medium">{formatCurrency(line.total_price)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
          <div className="bg-slate-50 rounded-lg p-3 mt-3">
            <div className="flex justify-end">
              <span className="text-lg font-bold">{formatCurrency(purchase.total_amount)}</span>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Liquidate Dialog */}
      <ConfirmDialog
        open={showLiquidate}
        onOpenChange={setShowLiquidate}
        title="Liquidar Compra"
        description="Seleccione la cuenta de pago para liquidar esta compra."
        confirmLabel="Liquidar"
        onConfirm={handleLiquidate}
        loading={liquidate.isPending}
        disabled={!paymentAccountId}
      >
        <div className="py-2">
          <EntitySelect
            value={paymentAccountId}
            onChange={setPaymentAccountId}
            options={accounts.map((a) => ({ id: a.id, label: a.name }))}
            placeholder="Seleccionar cuenta de pago..."
          />
        </div>
      </ConfirmDialog>

      {/* Cancel Dialog */}
      <ConfirmDialog
        open={showCancel}
        onOpenChange={setShowCancel}
        title="Cancelar Compra"
        description="Esta accion revertira los movimientos de inventario y saldos asociados. Esta seguro?"
        confirmLabel="Si, cancelar"
        variant="destructive"
        onConfirm={handleCancel}
        loading={cancel.isPending}
      />
    </div>
  );
}
