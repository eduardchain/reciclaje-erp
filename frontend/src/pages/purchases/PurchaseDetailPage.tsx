import { useState } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import { useReturnToBack } from "@/hooks/useReturnToBack";
import { ArrowLeft, CreditCard, XCircle, Pencil, FileText, PackageOpen } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
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
import { LinkedPaymentChoice } from "@/components/shared/LinkedPaymentChoice";
import { ThirdPartyLink } from "@/components/shared/EntityLink";
import { usePurchase, useCancelPurchase } from "@/hooks/usePurchases";
import { useAuthStore } from "@/stores/authStore";
import { formatCurrency, formatDate, formatDateTime, formatWeight } from "@/utils/formatters";
import { CHARGE_TYPE_LABELS } from "@/utils/constants";
import { RETENTION_TYPE_LABELS } from "@/types/purchase";
import { exportPurchasePDF } from "@/utils/pdfExport";
import { usePermissions } from "@/hooks/usePermissions";

const statusBorderMap: Record<string, string> = {
  registered: "border-t-[3px] border-t-amber-400",
  liquidated: "border-t-[3px] border-t-emerald-400",
  cancelled: "border-t-[3px] border-t-rose-400",
};

export default function PurchaseDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const handleBack = useReturnToBack();
  const { data: purchase, isLoading } = usePurchase(id!);
  const cancel = useCancelPurchase();
  const { hasPermission } = usePermissions();
  const canViewPrices = hasPermission("purchases.view_prices");
  const { organizationId, organizations } = useAuthStore();
  const orgName = organizations.find((o) => o.id === organizationId)?.name ?? "";

  const [showCancel, setShowCancel] = useState(false);
  const [annulChoice, setAnnulChoice] = useState<"annul" | "advance" | null>(null);

  const linkedPaymentTotal = purchase?.linked_payment_total ?? 0;
  const hasLinkedPayment = linkedPaymentTotal > 0;

  const handleCancel = () => {
    if (!id) return;
    cancel.mutate(
      { id, annulLinkedPayments: annulChoice === "annul" },
      {
        onSuccess: () => {
          setShowCancel(false);
          setAnnulChoice(null);
        },
      },
    );
  };

  const canEdit = purchase?.status === "registered" && !purchase?.double_entry_id && hasPermission("purchases.edit");
  const canLiquidate = purchase?.status === "registered" && !purchase?.double_entry_id && hasPermission("purchases.liquidate");
  const canCancel = (purchase?.status === "registered" || purchase?.status === "liquidated") && !purchase?.double_entry_id && hasPermission("purchases.cancel");

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
          {canEdit && (
              <Button variant="outline" onClick={() => navigate(`/purchases/${id}/edit`)}>
                <Pencil className="h-4 w-4 mr-2" />
                Editar
              </Button>
          )}
          {canLiquidate && (
              <Button onClick={() => navigate(`/purchases/${id}/liquidate`)} className="bg-emerald-600 hover:bg-emerald-700">
                <CreditCard className="h-4 w-4 mr-2" />
                Liquidar
              </Button>
          )}
          {canCancel && (
            <Button variant="outline" onClick={() => setShowCancel(true)} className="text-red-600 border-red-200 hover:bg-red-50">
              <XCircle className="h-4 w-4 mr-2" />
              Cancelar
            </Button>
          )}
          <Button variant="outline" onClick={() => exportPurchasePDF(purchase, orgName)}>
            <FileText className="h-4 w-4 mr-2" />
            PDF
          </Button>
          <Button variant="outline" onClick={handleBack}>
            <ArrowLeft className="h-4 w-4 mr-2" />
            Volver
          </Button>
        </div>
      </PageHeader>

      {/* Ciclo B (B1): origen inbound — trazabilidad del canal unico */}
      {purchase.inbound_order_number != null && purchase.inbound_order_id && (
        <div className="flex items-center gap-2 rounded-lg border border-indigo-200 bg-indigo-50 px-3 py-2.5 text-sm text-indigo-800">
          <PackageOpen className="h-4 w-4 shrink-0" />
          <span>
            Origen:{" "}
            <Link
              to={`/inbound/${purchase.inbound_order_id}`}
              className="font-medium underline hover:text-indigo-900"
            >
              Entrada #{purchase.inbound_order_number}
            </Link>{" "}
            — esta compra fue derivada desde el patio.
          </span>
        </div>
      )}

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
              {canViewPrices && (
                <div className="flex justify-between">
                  <dt className="text-xs font-semibold uppercase tracking-wider text-slate-500">Total</dt>
                  <dd className="font-bold text-lg">{formatCurrency(purchase.total_amount)}</dd>
                </div>
              )}
            </dl>
          </CardContent>
        </Card>

        <Card className="shadow-sm">
          <CardContent className="pt-6">
            <dl className="space-y-3 text-sm">
              <div className="flex flex-col sm:flex-row sm:justify-between sm:items-center gap-0.5 sm:gap-3">
                <dt className="text-xs font-semibold uppercase tracking-wider text-slate-500">Proveedor</dt>
                <dd className="truncate"><ThirdPartyLink id={purchase.supplier_id}>{purchase.supplier_name}</ThirdPartyLink></dd>
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
          <div className="rounded-lg border border-slate-200/80 overflow-x-auto">
            <Table className="min-w-[640px]">
              <TableHeader>
                <TableRow className="bg-slate-50/80 border-b border-slate-200/80">
                  <TableHead className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 h-10">Material</TableHead>
                  <TableHead className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 h-10">Bodega</TableHead>
                  <TableHead className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 h-10 text-right">Cantidad</TableHead>
                  {canViewPrices && <TableHead className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 h-10 text-right">Precio Unit.</TableHead>}
                  {canViewPrices && <TableHead className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 h-10 text-right">Total</TableHead>}
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
                    <TableCell className="text-right tabular-nums">{formatWeight(line.quantity, line.material_unit)}</TableCell>
                    {canViewPrices && <TableCell className="text-right tabular-nums">{formatCurrency(line.unit_price)}</TableCell>}
                    {canViewPrices && <TableCell className="text-right tabular-nums font-medium">{formatCurrency(line.total_price)}</TableCell>}
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
          {canViewPrices && (
            <div className="bg-slate-50 rounded-lg p-3 mt-3">
              <div className="flex justify-end">
                <span className="text-lg font-bold">{formatCurrency(purchase.total_amount)}</span>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Comisiones */}
      {purchase.commissions?.length > 0 && canViewPrices && (
        <Card className="shadow-sm">
          <CardHeader>
            <CardTitle className="text-sm font-semibold uppercase tracking-wider text-slate-500">Comisiones y Cargos</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="rounded-lg border border-slate-200/80 overflow-x-auto">
              <Table className="min-w-[640px]">
                <TableHeader>
                  <TableRow className="bg-slate-50/80 border-b border-slate-200/80">
                    <TableHead className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 h-10">Receptor</TableHead>
                    <TableHead className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 h-10">Cargo</TableHead>
                    <TableHead className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 h-10">Concepto</TableHead>
                    <TableHead className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 h-10">Cálculo</TableHead>
                    <TableHead className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 h-10 text-right">Valor</TableHead>
                    <TableHead className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 h-10 text-right">Monto</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {purchase.commissions.map((comm) => (
                    <TableRow key={comm.id}>
                      <TableCell className="font-medium"><ThirdPartyLink id={comm.third_party_id}>{comm.third_party_name}</ThirdPartyLink></TableCell>
                      <TableCell><Badge variant="outline">{CHARGE_TYPE_LABELS[comm.charge_type] ?? "Comisión"}</Badge></TableCell>
                      <TableCell>{comm.concept}</TableCell>
                      <TableCell>{comm.commission_type === "percentage" ? "Porcentaje" : comm.commission_type === "per_kg" ? "Por Kilo" : "Fijo"}</TableCell>
                      <TableCell className="text-right tabular-nums">
                        {comm.commission_type === "percentage" ? `${comm.commission_value}%` : comm.commission_type === "per_kg" ? `${formatCurrency(comm.commission_value)}/kg` : formatCurrency(comm.commission_value)}
                      </TableCell>
                      <TableCell className="text-right tabular-nums font-medium">{formatCurrency(comm.commission_amount)}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
            {/* Resumen con comisiones */}
            <div className="bg-slate-50 rounded-lg p-3 mt-3">
              <div className="max-w-sm ml-auto space-y-1">
                <div className="flex justify-between text-sm">
                  <span className="text-slate-600">Subtotal Materiales</span>
                  <span className="tabular-nums">{formatCurrency(purchase.total_amount)}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-slate-600">(+) Comisiones</span>
                  <span className="tabular-nums text-amber-600">
                    {formatCurrency(purchase.commissions.reduce((s, c) => s + c.commission_amount, 0))}
                  </span>
                </div>
                <div className="border-t border-slate-200 pt-1" />
                <div className="flex justify-between text-sm font-semibold">
                  <span>Costo Total Inventario</span>
                  <span className="tabular-nums">
                    {formatCurrency(purchase.total_amount + purchase.commissions.reduce((s, c) => s + c.commission_amount, 0))}
                  </span>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Comisión de recolección (SAC Ciclo D — gasto causado, no prorratea al costo) */}
      {purchase.collector_commission_total != null && canViewPrices && (
        <Card className="shadow-sm">
          <CardHeader>
            <CardTitle className="text-sm font-semibold uppercase tracking-wider text-slate-500">Comisión de Recolección</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
              <div className="text-sm">
                <span className="text-slate-600">Recolector: </span>
                {purchase.collector_id ? (
                  <ThirdPartyLink id={purchase.collector_id}>
                    <span className="font-medium">{purchase.collector_name}</span>
                  </ThirdPartyLink>
                ) : (
                  <span className="font-medium">{purchase.collector_name ?? "—"}</span>
                )}
              </div>
              <div className="text-sm font-semibold tabular-nums">
                {formatCurrency(purchase.collector_commission_total)}
              </div>
            </div>
            <p className="text-xs text-slate-500 mt-2">
              Causada como <strong>gasto</strong> (categoría "Comisiones de recolección") al liquidar —
              no hace parte del costo del material ni del total a pagar al proveedor.
            </p>
          </CardContent>
        </Card>
      )}

      {/* Retenciones aplicadas (SAC D9 — vacío para orgs sin flag) */}
      {purchase.retentions?.length > 0 && canViewPrices && (
        <Card className="shadow-sm">
          <CardHeader>
            <CardTitle className="text-sm font-semibold uppercase tracking-wider text-slate-500">Retenciones Aplicadas</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="rounded-lg border border-slate-200/80 overflow-x-auto">
              <Table className="min-w-[480px]">
                <TableHeader>
                  <TableRow className="bg-slate-50/80 border-b border-slate-200/80">
                    <TableHead className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 h-10">Tipo</TableHead>
                    <TableHead className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 h-10">Municipio</TableHead>
                    <TableHead className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 h-10 text-right">Monto</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {purchase.retentions.map((ret) => (
                    <TableRow key={ret.id} className={ret.reverted_at ? "opacity-60" : ""}>
                      <TableCell>
                        <div className="flex items-center gap-1.5">
                          <ThirdPartyLink id={ret.third_party_id}>
                            {RETENTION_TYPE_LABELS[ret.retention_type] ?? ret.retention_type}
                          </ThirdPartyLink>
                          {ret.reverted_at && (
                            <Badge variant="outline" className="bg-rose-100 text-rose-800">Revertida</Badge>
                          )}
                        </div>
                      </TableCell>
                      <TableCell className="text-slate-600">{ret.municipality ?? "—"}</TableCell>
                      <TableCell className="text-right tabular-nums font-medium">{formatCurrency(ret.amount)}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
            <div className="bg-slate-50 rounded-lg p-3 mt-3">
              <div className="max-w-sm ml-auto space-y-1">
                <div className="flex justify-between text-sm">
                  <span className="text-slate-600">Total Retenciones</span>
                  <span className="tabular-nums text-rose-600">
                    −{formatCurrency(purchase.retentions.reduce((s, r) => s + (r.reverted_at ? 0 : r.amount), 0))}
                  </span>
                </div>
                <div className="flex justify-between text-sm font-semibold">
                  <span>Neto Acreditado al Proveedor</span>
                  <span className="tabular-nums">
                    {formatCurrency(purchase.total_amount - purchase.retentions.reduce((s, r) => s + (r.reverted_at ? 0 : r.amount), 0))}
                  </span>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Auditoria */}
      <Card className="shadow-sm">
        <CardHeader>
          <CardTitle className="text-sm font-semibold uppercase tracking-wider text-slate-500">Auditoria</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
            <div>
              <dt className="text-xs font-semibold uppercase tracking-wider text-slate-500">Creada por</dt>
              <dd className="mt-0.5">{purchase.created_by_name ?? "-"}</dd>
              <dd className="text-xs text-slate-400">{formatDateTime(purchase.created_at)}</dd>
            </div>
            {purchase.liquidated_at && (
              <div>
                <dt className="text-xs font-semibold uppercase tracking-wider text-slate-500">Liquidada por</dt>
                <dd className="mt-0.5">{purchase.liquidated_by_name ?? "-"}</dd>
                <dd className="text-xs text-slate-400">{formatDateTime(purchase.liquidated_at)}</dd>
              </div>
            )}
            {purchase.cancelled_at && (
              <div>
                <dt className="text-xs font-semibold uppercase tracking-wider text-slate-500">Cancelada por</dt>
                <dd className="mt-0.5">{purchase.cancelled_by_name ?? "-"}</dd>
                <dd className="text-xs text-slate-400">{formatDateTime(purchase.cancelled_at)}</dd>
              </div>
            )}
            {purchase.updated_by_name && (
              <div>
                <dt className="text-xs font-semibold uppercase tracking-wider text-slate-500">Editada por</dt>
                <dd className="mt-0.5">{purchase.updated_by_name}</dd>
                <dd className="text-xs text-slate-400">{formatDateTime(purchase.updated_at)}</dd>
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Cancel Dialog */}
      <ConfirmDialog
        open={showCancel}
        onOpenChange={(open) => {
          setShowCancel(open);
          if (!open) setAnnulChoice(null);
        }}
        title="Cancelar Compra"
        description={
          purchase.status === "liquidated"
            ? "Esta accion revertira los movimientos de inventario y saldos del proveedor. Esta seguro?"
            : "Esta accion revertira los movimientos de inventario. Esta seguro?"
        }
        confirmLabel="Si, cancelar"
        variant="destructive"
        onConfirm={handleCancel}
        loading={cancel.isPending}
        disabled={hasLinkedPayment && annulChoice === null}
      >
        <LinkedPaymentChoice
          kind="purchase"
          amount={linkedPaymentTotal}
          value={annulChoice}
          onChange={setAnnulChoice}
        />
      </ConfirmDialog>
    </div>
  );
}
