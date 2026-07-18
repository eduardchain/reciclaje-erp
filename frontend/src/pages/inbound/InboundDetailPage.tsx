import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, CheckCircle2, Clock, Pencil } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
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
import { PageHeader } from "@/components/shared/PageHeader";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { ConfirmDialog } from "@/components/shared/ConfirmDialog";
import { PurchaseLink } from "@/components/shared/EntityLink";
import { useReturnToBack } from "@/hooks/useReturnToBack";
import { usePermissions } from "@/hooks/usePermissions";
import { useAnnulInboundOrder, useConfirmInboundOrder, useInboundOrder } from "@/hooks/useInboundOrders";
import { useCurrentFormulas } from "@/hooks/useSacConfig";
import { formatCurrency, formatDate, formatWeight } from "@/utils/formatters";
import { buildRoute, ROUTES } from "@/utils/constants";
import { estimateKgLead, willardCenterLabel } from "./InboundCreatePage";
import {
  INBOUND_TYPE_LABELS,
  PURCHASE_INBOUND_TYPES,
  WILLARD_INBOUND_TYPES,
} from "@/types/inbound-order";

const statusBorderMap: Record<string, string> = {
  draft: "border-t-[3px] border-t-amber-400",
  confirmed: "border-t-[3px] border-t-emerald-400",
  annulled: "border-t-[3px] border-t-rose-400",
};

function InfoRow({ label, value, long = false }: { label: string; value: React.ReactNode; long?: boolean }) {
  return (
    <div className={long ? "flex flex-col sm:flex-row sm:justify-between gap-0.5 sm:gap-3" : "flex justify-between gap-3"}>
      <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">{label}</span>
      <span className="text-sm text-slate-800 sm:text-right">{value}</span>
    </div>
  );
}

export default function InboundDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const handleBack = useReturnToBack(ROUTES.INBOUND);
  const { hasPermission } = usePermissions();
  const canEdit = hasPermission("purchases.edit");
  const canCancel = hasPermission("purchases.cancel");
  const canConfirm = hasPermission("purchases.liquidate");

  const { data: order, isLoading } = useInboundOrder(id!);
  const annulOrder = useAnnulInboundOrder();
  const confirmOrder = useConfirmInboundOrder();
  const [annulOpen, setAnnulOpen] = useState(false);
  const [annulReason, setAnnulReason] = useState("");
  const [confirmOpen, setConfirmOpen] = useState(false);

  // B.2: kg estimados client-side para drafts (los definitivos nacen al confirmar)
  const { data: formulasData } = useCurrentFormulas();
  const formulas = formulasData?.items ?? [];

  if (isLoading) return <div className="p-8 text-center text-slate-500">Cargando...</div>;
  if (!order) return <div className="p-8 text-center text-slate-500">Recepción no encontrada</div>;

  const isWillard = WILLARD_INBOUND_TYPES.includes(order.inbound_type);
  const isPurchaseType = PURCHASE_INBOUND_TYPES.includes(order.inbound_type);
  const isDraft = order.status === "draft";
  const estimatedTotalKg = isDraft && isWillard
    ? order.lines.reduce((acc, l) => acc + (estimateKgLead(formulas, l.material_id, l.quantity) ?? 0), 0)
    : null;

  const confirmAnnul = () => {
    if (!annulReason.trim()) return;
    annulOrder.mutate(
      { id: order.id, reason: annulReason.trim() },
      { onSuccess: () => { setAnnulOpen(false); setAnnulReason(""); } }
    );
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title={`Recepción #${order.order_number}`}
        description={INBOUND_TYPE_LABELS[order.inbound_type] ?? order.inbound_type}
      >
        <Button variant="outline" onClick={handleBack}>
          <ArrowLeft className="h-4 w-4 mr-2" />
          Volver
        </Button>
        {canEdit && order.status !== "annulled" && (
          <Button
            variant="outline"
            onClick={() => navigate(buildRoute(ROUTES.INBOUND_EDIT, { id: order.id }))}
          >
            <Pencil className="h-4 w-4 mr-2" />
            Editar
          </Button>
        )}
        {isDraft && isWillard && canConfirm && (
          <Button
            onClick={() => setConfirmOpen(true)}
            className="bg-emerald-600 hover:bg-emerald-700"
          >
            <CheckCircle2 className="h-4 w-4 mr-2" />
            Confirmar Recepción
          </Button>
        )}
        {canCancel && order.status !== "annulled" && (
          <Button variant="destructive" onClick={() => setAnnulOpen(true)}>
            Anular
          </Button>
        )}
      </PageHeader>

      {isDraft && isWillard && (
        <div className="flex items-start gap-2.5 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
          <Clock className="h-4 w-4 mt-0.5 shrink-0" />
          <div>
            <span className="font-semibold">Registrada — pendiente de confirmar.</span>{" "}
            El material entrará al inventario y moverá el libro kg al confirmar. Los kg mostrados
            son estimados con la fórmula vigente; los definitivos se calculan al confirmar.
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Informacion general */}
        <Card className={`shadow-sm ${statusBorderMap[order.status] ?? ""}`}>
          <CardHeader>
            <CardTitle className="text-sm font-semibold uppercase tracking-wider text-slate-500">Información General</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            <InfoRow label="Estado" value={<StatusBadge status={order.status} />} />
            <InfoRow label="Fecha" value={formatDate(order.date)} />
            <InfoRow
              label="Tipo"
              value={<Badge variant="outline">{INBOUND_TYPE_LABELS[order.inbound_type] ?? order.inbound_type}</Badge>}
            />
            <InfoRow label="Tercero" value={order.third_party_name ?? "—"} long />
            <InfoRow label="Sede" value={order.warehouse_name ?? "—"} long />
          </CardContent>
        </Card>

        {/* Transporte + Willard */}
        <Card className="shadow-sm">
          <CardHeader>
            <CardTitle className="text-sm font-semibold uppercase tracking-wider text-slate-500">Transporte y Detalle</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            <InfoRow label="Conductor" value={order.driver_name ?? "—"} long />
            <InfoRow label="Vehículo" value={order.vehicle_plate ? order.vehicle_plate.toUpperCase() : "—"} />
            {isWillard && (
              <InfoRow
                label="Centro Willard"
                value={order.willard_distribution_center ? willardCenterLabel(order.willard_distribution_center) : "—"}
              />
            )}
            {order.notes && <InfoRow label="Notas" value={order.notes} long />}
          </CardContent>
        </Card>

        {/* Efectos */}
        <Card className="shadow-sm">
          <CardHeader>
            <CardTitle className="text-sm font-semibold uppercase tracking-wider text-slate-500">Efectos</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            {isWillard && (
              <InfoRow
                label={isDraft ? "Kg Plomo (estimado)" : "Total Kg Plomo"}
                value={
                  isDraft ? (
                    <span className="font-semibold tabular-nums text-amber-700">
                      {estimatedTotalKg != null && estimatedTotalKg > 0
                        ? `~${formatWeight(estimatedTotalKg)}`
                        : "—"}
                    </span>
                  ) : (
                    <span className="font-semibold tabular-nums text-emerald-700">
                      {order.total_kg_lead != null ? `+${formatWeight(order.total_kg_lead)}` : "—"}
                    </span>
                  )
                }
              />
            )}
            {isPurchaseType && (
              <>
                <InfoRow
                  label="Compra Derivada"
                  value={
                    order.purchase_id ? (
                      <PurchaseLink id={order.purchase_id}>Compra #{order.purchase_number}</PurchaseLink>
                    ) : (
                      "—"
                    )
                  }
                />
                {order.purchase_status && (
                  <InfoRow label="Estado Compra" value={<StatusBadge status={order.purchase_status} />} />
                )}
              </>
            )}
            {order.status === "annulled" && (
              <>
                <InfoRow label="Anulada" value={order.annulled_at ? formatDate(order.annulled_at) : "—"} />
                <InfoRow label="Motivo" value={order.annulled_reason ?? "—"} long />
              </>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Lineas */}
      <Card className="shadow-sm">
        <CardHeader>
          <CardTitle className="text-sm font-semibold uppercase tracking-wider text-slate-500">Líneas</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto -mx-3 sm:mx-0">
            <Table className="min-w-[640px]">
              <TableHeader>
                <TableRow>
                  <TableHead>Material</TableHead>
                  <TableHead className="text-right">Cantidad</TableHead>
                  {isPurchaseType && <TableHead className="text-right">Precio Unit.</TableHead>}
                  <TableHead className="text-right">Peso Báscula</TableHead>
                  {isWillard && <TableHead className="text-right">Kg Plomo</TableHead>}
                  <TableHead>Notas</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {order.lines.map((line) => (
                  <TableRow key={line.id}>
                    <TableCell>
                      <span className="font-medium">{line.material_code}</span>
                      <span className="text-slate-500"> — {line.material_name}</span>
                    </TableCell>
                    <TableCell className="text-right tabular-nums">
                      {formatWeight(line.quantity, line.material_unit || "kg")}
                    </TableCell>
                    {isPurchaseType && (
                      <TableCell className="text-right tabular-nums">
                        {line.unit_price != null ? formatCurrency(line.unit_price) : "—"}
                      </TableCell>
                    )}
                    <TableCell className="text-right tabular-nums">
                      {line.scale_weight_kg != null ? formatWeight(line.scale_weight_kg) : "—"}
                    </TableCell>
                    {isWillard && (
                      <TableCell className="text-right">
                        {isDraft ? (
                          <span className="font-medium tabular-nums text-amber-700">
                            {(() => {
                              const est = estimateKgLead(formulas, line.material_id, line.quantity);
                              return est != null ? `~${formatWeight(est)}` : "—";
                            })()}
                          </span>
                        ) : (
                          <span className="font-medium tabular-nums text-emerald-700">
                            {line.kg_lead != null ? `+${formatWeight(line.kg_lead)}` : "—"}
                          </span>
                        )}
                      </TableCell>
                    )}
                    <TableCell className="text-sm text-slate-500 max-w-[220px]">
                      <span className="truncate block">{line.quality_notes ?? "—"}</span>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
          {isWillard && order.total_kg_lead != null && (
            <div className="bg-slate-50 rounded-lg p-3 mt-3 flex justify-end">
              <span className="text-base font-bold tabular-nums text-emerald-700">
                Total: +{formatWeight(order.total_kg_lead)}
              </span>
            </div>
          )}
          {isDraft && isWillard && estimatedTotalKg != null && estimatedTotalKg > 0 && (
            <div className="bg-amber-50 rounded-lg p-3 mt-3 flex justify-end">
              <span className="text-base font-bold tabular-nums text-amber-700">
                Estimado: ~{formatWeight(estimatedTotalKg)}
              </span>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Confirmar (B.2) */}
      <ConfirmDialog
        open={confirmOpen}
        onOpenChange={setConfirmOpen}
        title={`Confirmar Recepción #${order.order_number}`}
        description="El material entra al inventario y mueve el libro kg con la fórmula vigente. Esta acción registra los efectos definitivos."
        confirmLabel="Confirmar"
        loading={confirmOrder.isPending}
        onConfirm={() =>
          confirmOrder.mutate(order.id, { onSuccess: () => setConfirmOpen(false) })
        }
      />

      {/* Anular */}
      <ConfirmDialog
        open={annulOpen}
        onOpenChange={(o) => { setAnnulOpen(o); if (!o) setAnnulReason(""); }}
        title={`Anular Recepción #${order.order_number}`}
        description={
          isWillard
            ? isDraft
              ? "La recepción está Registrada y no ha movido inventario ni libro kg — solo se marcará como anulada."
              : "Se revertirán los movimientos de inventario y de la cuenta kg. Si el stock queda negativo, se avisará sin bloquear."
            : order.purchase_status === "liquidated"
              ? `La compra derivada #${order.purchase_number} está liquidada — debe cancelarla primero en el módulo de compras.`
              : `Se cancelará también la compra derivada #${order.purchase_number ?? ""} (registrada) en el mismo acto.`
        }
        confirmLabel="Anular"
        variant="destructive"
        loading={annulOrder.isPending}
        disabled={!annulReason.trim()}
        onConfirm={confirmAnnul}
      >
        <div>
          <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Razón *</Label>
          <Input
            value={annulReason}
            onChange={(e) => setAnnulReason(e.target.value)}
            maxLength={500}
            placeholder="Motivo de la anulación..."
          />
        </div>
      </ConfirmDialog>
    </div>
  );
}
