import { useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { ArrowLeft, CreditCard, XCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
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
    return <div className="text-center py-12 text-gray-500">Compra no encontrada</div>;
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title={`Compra #${purchase.purchase_number}`}
        description={`Proveedor: ${purchase.supplier_name}`}
      >
        <div className="flex items-center gap-2">
          {purchase.status === "registered" && (
            <>
              <Button onClick={() => setShowLiquidate(true)} className="bg-green-600 hover:bg-green-700">
                <CreditCard className="h-4 w-4 mr-2" />
                Liquidar
              </Button>
              <Button variant="outline" onClick={() => setShowCancel(true)} className="text-red-600 border-red-200 hover:bg-red-50">
                <XCircle className="h-4 w-4 mr-2" />
                Cancelar
              </Button>
            </>
          )}
          <Button variant="outline" onClick={() => navigate(ROUTES.PURCHASES)}>
            <ArrowLeft className="h-4 w-4 mr-2" />
            Volver
          </Button>
        </div>
      </PageHeader>

      {/* Info general */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card>
          <CardContent className="pt-6">
            <dl className="space-y-2 text-sm">
              <div className="flex justify-between">
                <dt className="text-gray-500">Estado</dt>
                <dd><StatusBadge status={purchase.status} /></dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-gray-500">Fecha</dt>
                <dd>{formatDate(purchase.date)}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-gray-500">Total</dt>
                <dd className="font-bold text-lg">{formatCurrency(purchase.total_amount)}</dd>
              </div>
            </dl>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-6">
            <dl className="space-y-2 text-sm">
              <div className="flex justify-between">
                <dt className="text-gray-500">Proveedor</dt>
                <dd>{purchase.supplier_name}</dd>
              </div>
              {purchase.vehicle_plate && (
                <div className="flex justify-between">
                  <dt className="text-gray-500">Placa</dt>
                  <dd>{purchase.vehicle_plate}</dd>
                </div>
              )}
              {purchase.invoice_number && (
                <div className="flex justify-between">
                  <dt className="text-gray-500">Factura</dt>
                  <dd>{purchase.invoice_number}</dd>
                </div>
              )}
            </dl>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-6">
            <dl className="space-y-2 text-sm">
              {purchase.payment_account_name && (
                <div className="flex justify-between">
                  <dt className="text-gray-500">Cuenta Pago</dt>
                  <dd>{purchase.payment_account_name}</dd>
                </div>
              )}
              {purchase.notes && (
                <div>
                  <dt className="text-gray-500 mb-1">Notas</dt>
                  <dd className="text-gray-700">{purchase.notes}</dd>
                </div>
              )}
              <div className="flex justify-between">
                <dt className="text-gray-500">Creada</dt>
                <dd>{formatDate(purchase.created_at)}</dd>
              </div>
            </dl>
          </CardContent>
        </Card>
      </div>

      {/* Lineas */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Lineas de Compra</CardTitle>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Material</TableHead>
                <TableHead>Bodega</TableHead>
                <TableHead className="text-right">Cantidad</TableHead>
                <TableHead className="text-right">Precio Unit.</TableHead>
                <TableHead className="text-right">Total</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {purchase.lines.map((line) => (
                <TableRow key={line.id}>
                  <TableCell>
                    <div>
                      <span className="font-medium">{line.material_name}</span>
                      <span className="text-gray-400 ml-2 text-xs">{line.material_code}</span>
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
          <Separator className="my-2" />
          <div className="flex justify-end px-4 py-2">
            <span className="text-lg font-bold">{formatCurrency(purchase.total_amount)}</span>
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
