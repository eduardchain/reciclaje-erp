import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, CheckCircle2, Clock, Pencil } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

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
import { EntradaStatusBadge, EntradaTypeBadge } from "./InboundOrdersPage";
import {
  INBOUND_TYPE_LABELS,
  PURCHASE_INBOUND_TYPES,
  WILLARD_INBOUND_TYPES,
} from "@/types/inbound-order";

// Ciclo C: el borde sigue el estado DERIVADO (unico visible)
const statusBorderMap: Record<string, string> = {
  registered: "border-t-[3px] border-t-amber-400",
  liquidated: "border-t-[3px] border-t-emerald-400",
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
  const canViewPrices = hasPermission("purchases.view_prices");

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
  if (!order) return <div className="p-8 text-center text-slate-500">Entrada no encontrada</div>;

  const isWillard = WILLARD_INBOUND_TYPES.includes(order.inbound_type);
  const isPurchaseType = PURCHASE_INBOUND_TYPES.includes(order.inbound_type);
  const isDraft = order.status === "draft";
  // Ciclo C: pendiente de liquidar en el sentido DERIVADO (ambos tipos)
  const isPendingLiquidation = order.display_status === "registered";
  const estimatedTotalKg = isDraft && isWillard
    ? order.lines.reduce((acc, l) => acc + (estimateKgLead(formulas, l.material_id, l.quantity) ?? 0), 0)
    : null;
  const purchaseTotal = isPurchaseType
    ? order.lines.reduce((acc, l) => acc + l.quantity * (l.unit_price ?? 0), 0)
    : 0;

  const goLiquidatePurchase = () => {
    if (!order.purchase_id) return;
    navigate(
      `/purchases/${order.purchase_id}/liquidate?returnTo=${encodeURIComponent(`/inbound/${order.id}`)}`
    );
  };

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
        title={`Entrada #${order.order_number}`}
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
        {isPendingLiquidation && canConfirm && (
          <Button
            onClick={() => (isWillard ? setConfirmOpen(true) : goLiquidatePurchase())}
            className="bg-emerald-600 hover:bg-emerald-700"
          >
            <CheckCircle2 className="h-4 w-4 mr-2" />
            Liquidar
          </Button>
        )}
        {canCancel && order.status !== "annulled" && order.display_status !== "annulled" && (
          <Button variant="destructive" onClick={() => setAnnulOpen(true)}>
            Anular
          </Button>
        )}
      </PageHeader>

      {isPendingLiquidation && (
        <div className="flex items-start gap-2.5 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
          <Clock className="h-4 w-4 mt-0.5 shrink-0" />
          <div>
            <span className="font-semibold">Registrada — pendiente de liquidar.</span>{" "}
            {isWillard
              ? "Al liquidar, el material entra al inventario y mueve el libro kg. Los kg mostrados son estimados con la fórmula vigente; los definitivos se calculan al liquidar."
              : "Al liquidar se confirman los precios y la compra tiene efecto financiero (saldo del proveedor, costo promedio, retenciones)."}
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Informacion general */}
        <Card className={`shadow-sm ${statusBorderMap[order.display_status] ?? ""}`}>
          <CardHeader>
            <CardTitle className="text-sm font-semibold uppercase tracking-wider text-slate-500">Información General</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            <InfoRow label="Estado" value={<EntradaStatusBadge status={order.display_status} />} />
            <InfoRow label="Fecha" value={formatDate(order.date)} />
            <InfoRow label="Tipo" value={<EntradaTypeBadge order={order} />} />
            <InfoRow label="Tercero" value={order.third_party_name ?? "—"} long />
            <InfoRow label="Sede" value={order.warehouse_name ?? "—"} long />
            {/* Ciclo C (C-5): quien hizo que — capa de confianza del flujo a 2 personas */}
            {order.created_by_name && (
              <InfoRow
                label="Registrada por"
                value={`${order.created_by_name} · ${formatDate(order.created_at)}`}
                long
              />
            )}
            {order.liquidated_by_name && order.display_status !== "annulled" && (
              <InfoRow
                label="Liquidada por"
                value={`${order.liquidated_by_name}${order.liquidated_at ? ` · ${formatDate(order.liquidated_at)}` : ""}`}
                long
              />
            )}
            {order.display_status === "annulled" && (order.annulled_by_name || order.annulled_at) && (
              <InfoRow
                label="Anulada por"
                value={`${order.annulled_by_name ?? "—"}${order.annulled_at ? ` · ${formatDate(order.annulled_at)}` : ""}`}
                long
              />
            )}
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
                {canViewPrices && (
                  <InfoRow
                    label="Total Capturado"
                    value={
                      <span className="font-semibold tabular-nums">{formatCurrency(purchaseTotal)}</span>
                    }
                  />
                )}
                <InfoRow
                  label="Cara Financiera"
                  value={
                    order.purchase_id ? (
                      <PurchaseLink id={order.purchase_id}>Ver compra #{order.purchase_number}</PurchaseLink>
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

      {/* Liquidar willard (verbo unico Ciclo C — el efecto es el confirm B.2) */}
      <ConfirmDialog
        open={confirmOpen}
        onOpenChange={setConfirmOpen}
        title={`Liquidar Entrada #${order.order_number}`}
        description="El material entra al inventario y mueve el libro kg con la fórmula vigente (sin efecto financiero — entrada Willard). Esta acción registra los efectos definitivos."
        confirmLabel="Liquidar"
        loading={confirmOrder.isPending}
        onConfirm={() =>
          confirmOrder.mutate(order.id, { onSuccess: () => setConfirmOpen(false) })
        }
      />

      {/* Anular */}
      <ConfirmDialog
        open={annulOpen}
        onOpenChange={(o) => { setAnnulOpen(o); if (!o) setAnnulReason(""); }}
        title={`Anular Entrada #${order.order_number}`}
        description={
          isWillard
            ? isDraft
              ? "La entrada está Registrada y no ha movido inventario ni libro kg — solo se marcará como anulada."
              : "Se revertirán los movimientos de inventario y de la cuenta kg. Si el stock queda negativo, se avisará sin bloquear."
            : order.purchase_status === "liquidated"
              ? `La compra #${order.purchase_number} está liquidada (movió saldos y costos) — anúlela desde su cara financiera: "Ver compra #${order.purchase_number}", donde se decide qué pasa con el pago enlazado.`
              : `Se cancelará también la compra #${order.purchase_number ?? ""} (registrada) en el mismo acto.`
        }
        confirmLabel="Anular"
        variant="destructive"
        loading={annulOrder.isPending}
        disabled={!annulReason.trim() || (isPurchaseType && order.purchase_status === "liquidated")}
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
