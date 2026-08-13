import { Fragment, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, CheckCircle2, ClipboardCheck, Clock, Pencil, Undo2 } from "lucide-react";
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
import { AdjustmentLink, PurchaseLink, ThirdPartyLink } from "@/components/shared/EntityLink";
import { cn } from "@/utils";
import { useReturnToBack } from "@/hooks/useReturnToBack";
import { usePermissions } from "@/hooks/usePermissions";
import {
  useAnnulInboundOrder,
  useConfirmInboundOrder,
  useInboundOrder,
  useReviewInboundOrder,
  useUnliquidateInboundOrder,
} from "@/hooks/useInboundOrders";
import { useCurrentFormulas } from "@/hooks/useSacConfig";
import { formatCurrency, formatDate, formatDateTime, formatTime, formatWeight } from "@/utils/formatters";
import { buildRoute, ROUTES } from "@/utils/constants";
import { estimateKgLead, willardCenterLabel } from "./InboundCreatePage";
import { EntradaStatusBadge, EntradaTypeBadge } from "./InboundOrdersPage";
import {
  INBOUND_TYPE_LABELS,
  PURCHASE_INBOUND_TYPES,
  WILLARD_INBOUND_TYPES,
} from "@/types/inbound-order";

// #93: el borde sigue el estado UNICO visible (columna-driven)
const statusBorderMap: Record<string, string> = {
  registered: "border-t-[3px] border-t-amber-400",
  reviewed: "border-t-[3px] border-t-sky-400",
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
  const canReview = hasPermission("purchases.review");
  const canViewPrices = hasPermission("purchases.view_prices");

  const { data: order, isLoading } = useInboundOrder(id!);
  const annulOrder = useAnnulInboundOrder();
  const confirmOrder = useConfirmInboundOrder();
  const reviewOrder = useReviewInboundOrder();
  const unliquidateOrder = useUnliquidateInboundOrder();
  const [annulOpen, setAnnulOpen] = useState(false);
  const [annulReason, setAnnulReason] = useState("");
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [reviewOpen, setReviewOpen] = useState(false);
  const [unliquidateOpen, setUnliquidateOpen] = useState(false);

  // B.2: kg estimados client-side para drafts (los definitivos nacen al confirmar)
  const { data: formulasData } = useCurrentFormulas();
  const formulas = formulasData?.items ?? [];

  if (isLoading) return <div className="p-8 text-center text-slate-500">Cargando...</div>;
  if (!order) return <div className="p-8 text-center text-slate-500">Entrada no encontrada</div>;

  const isWillard = WILLARD_INBOUND_TYPES.includes(order.inbound_type);
  const isPurchaseType = PURCHASE_INBOUND_TYPES.includes(order.inbound_type);
  const isDraft = order.status === "draft";
  const isReviewed = order.display_status === "reviewed";
  const isLiquidated = order.display_status === "liquidated";
  const isRegistered = order.display_status === "registered";
  // #93: legacy 1:1 (ciclos B-D) — la fila vieja tiene purchase_id y su cara
  // financiera se maneja en la compra derivada, no con el reparto nuevo
  const isLegacy = isPurchaseType && !!order.purchase_id;
  const estimatedTotalKg = isDraft && isWillard
    ? order.lines.reduce((acc, l) => acc + (estimateKgLead(formulas, l.material_id, l.quantity) ?? 0), 0)
    : null;
  const purchaseTotal = isPurchaseType
    ? order.lines.reduce((acc, l) => acc + l.quantity * (l.unit_price ?? 0), 0)
    : 0;
  const liquidatedTotal = order.purchases
    .filter((p) => p.status !== "cancelled")
    .reduce((acc, p) => acc + p.total_amount, 0);
  // Descuadre neto que llegó a resultados (solo ajustes vigentes: los
  // anulados ya no cuentan, igual que en el P&L)
  const discrepancyAdjustments = (order.discrepancy_adjustments ?? []).filter(
    (a) => a.status === "confirmed"
  );
  const discrepancyNet = discrepancyAdjustments.reduce(
    (acc, a) => acc + Number(a.total_value), 0
  );

  const goLiquidateEntrada = () => {
    navigate(buildRoute(ROUTES.INBOUND_LIQUIDATE, { id: order.id }));
  };

  const goLiquidateLegacyPurchase = () => {
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
        {canEdit && order.status !== "annulled" && !isLiquidated && (
          <Button
            variant="outline"
            onClick={() => navigate(buildRoute(ROUTES.INBOUND_EDIT, { id: order.id }))}
          >
            <Pencil className="h-4 w-4 mr-2" />
            Editar
          </Button>
        )}
        {/* #93 D10: registrada -> revisada (permiso propio). Ítem 4: Willard
            también pasa por revisión — el revisor certifica el peso de
            báscula, que es la carta con la que Hugo renegocia el kg/unidad
            con Willard. La compra legacy 1:1 conserva su flujo viejo. */}
        {isRegistered && !isLegacy && canReview && (
          <Button
            onClick={() => setReviewOpen(true)}
            className="bg-sky-600 hover:bg-sky-700"
          >
            <ClipboardCheck className="h-4 w-4 mr-2" />
            Marcar Revisada
          </Button>
        )}
        {/* Liquidar: willard REVISADA -> confirm; compra revisada -> reparto;
            legacy 1:1 -> liquidacion de la compra derivada */}
        {canConfirm && (
          (isWillard && isReviewed) ? (
            <Button onClick={() => setConfirmOpen(true)} className="bg-emerald-600 hover:bg-emerald-700">
              <CheckCircle2 className="h-4 w-4 mr-2" />
              Liquidar
            </Button>
          ) : isLegacy && isRegistered ? (
            <Button onClick={goLiquidateLegacyPurchase} className="bg-emerald-600 hover:bg-emerald-700">
              <CheckCircle2 className="h-4 w-4 mr-2" />
              Liquidar
            </Button>
          ) : isPurchaseType && !isLegacy && isReviewed ? (
            <Button onClick={goLiquidateEntrada} className="bg-emerald-600 hover:bg-emerald-700">
              <CheckCircle2 className="h-4 w-4 mr-2" />
              Liquidar
            </Button>
          ) : null
        )}
        {/* #93 D20: revertir la liquidacion (vuelve a Revisada, conserva reparto) */}
        {isLiquidated && isPurchaseType && !isLegacy && canCancel && (
          <Button variant="outline" onClick={() => setUnliquidateOpen(true)}>
            <Undo2 className="h-4 w-4 mr-2" />
            Revertir Liquidación
          </Button>
        )}
        {canCancel && order.status !== "annulled" && order.display_status !== "annulled" && (
          <Button variant="destructive" onClick={() => setAnnulOpen(true)}>
            Anular
          </Button>
        )}
      </PageHeader>

      {isRegistered && (
        <div className="flex items-start gap-2.5 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
          <Clock className="h-4 w-4 mt-0.5 shrink-0" />
          <div>
            <span className="font-semibold">Registrada — pendiente.</span>{" "}
            {isWillard
              ? "El siguiente paso es la revisión: alguien con permiso certifica el peso de báscula y la marca Revisada. Al liquidar, el material entra al inventario y mueve el libro kg — los kg mostrados son estimados con la fórmula vigente."
              : isLegacy
                ? "Al liquidar se confirman los precios y la compra tiene efecto financiero (saldo del proveedor, costo promedio, retenciones)."
                : "El siguiente paso es la revisión: alguien con permiso valida lo pesado y la marca Revisada. Después se liquida con el reparto de proveedores."}
          </div>
        </div>
      )}

      {isReviewed && (
        <div className="flex items-start gap-2.5 rounded-lg border border-sky-200 bg-sky-50 px-4 py-3 text-sm text-sky-800">
          <ClipboardCheck className="h-4 w-4 mt-0.5 shrink-0" />
          <div>
            <span className="font-semibold">Revisada — lista para liquidar.</span>{" "}
            {isWillard
              ? "Al liquidar, el material entra al inventario al costo promedio vigente y se emite la deuda en kg de plomo con Willard."
              : "Al liquidar se reparte cada material entre sus proveedores: nacen las compras, se valora el descuadre contra lo pesado y se causa la comisión del recolector."}
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
            {/* #93: en tipo compra el proveedor vive en el reparto (tarjetas
                de la cara financiera) — la cabecera no tiene tercero */}
            {(isWillard || isLegacy || order.third_party_name) && (
              <InfoRow label="Tercero" value={order.third_party_name ?? "—"} long />
            )}
            <InfoRow label="Sede" value={order.warehouse_name ?? "—"} long />
            {order.remission_number && (
              <InfoRow label="N° Remisión" value={order.remission_number} long />
            )}
            {order.invoice_number && (
              <InfoRow label="N° Factura" value={order.invoice_number} long />
            )}
            {/* Ciclo C (C-5): quien hizo que — capa de confianza del flujo a 2 personas */}
            {order.created_by_name && (
              <InfoRow
                label="Registrada por"
                value={`${order.created_by_name} · ${formatDateTime(order.created_at)}`}
                long
              />
            )}
            {/* #93 D10: auditoria de la revision */}
            {order.reviewed_by_name && order.display_status !== "annulled" && (
              <InfoRow
                label="Revisada por"
                value={`${order.reviewed_by_name}${order.reviewed_at ? ` · ${formatDateTime(order.reviewed_at)}` : ""}`}
                long
              />
            )}
            {order.liquidated_by_name && order.display_status !== "annulled" && (
              <InfoRow
                label="Liquidada por"
                // liquidated_at es fecha de NEGOCIO → formatDate (#87); la hora
                // real del clic vive aparte en liquidated_ts (null en entradas
                // liquidadas antes de que existiera la columna)
                value={`${order.liquidated_by_name}${
                  order.liquidated_at ? ` · ${formatDate(order.liquidated_at)}` : ""
                }${order.liquidated_ts ? ` a las ${formatTime(order.liquidated_ts)}` : ""}`}
                long
              />
            )}
            {order.display_status === "annulled" && (order.annulled_by_name || order.annulled_at) && (
              <InfoRow
                label="Anulada por"
                value={`${order.annulled_by_name ?? "—"}${order.annulled_at ? ` · ${formatDateTime(order.annulled_at)}` : ""}`}
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
            {order.collector_name && (
              <InfoRow
                label="Recolector"
                value={
                  order.collector_id ? (
                    <ThirdPartyLink id={order.collector_id}>{order.collector_name}</ThirdPartyLink>
                  ) : (
                    order.collector_name
                  )
                }
                long
              />
            )}
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
                {canViewPrices && purchaseTotal > 0 && (
                  <InfoRow
                    label="Total Capturado (ref.)"
                    value={
                      <span className="font-semibold tabular-nums">{formatCurrency(purchaseTotal)}</span>
                    }
                  />
                )}
                {canViewPrices && order.purchases.length > 0 && (
                  <InfoRow
                    label="Total Liquidado"
                    value={
                      <span className="font-semibold tabular-nums">{formatCurrency(liquidatedTotal)}</span>
                    }
                  />
                )}
                {/* Legacy 1:1 (ciclos B-D): la cara financiera es la derivada */}
                {isLegacy && (
                  <>
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
                {order.collector_commission_total != null && canViewPrices && (
                  <InfoRow
                    label="Comisión Recolección"
                    value={
                      <span className="font-semibold tabular-nums">
                        {formatCurrency(order.collector_commission_total)}
                        <span className="ml-1.5 font-normal text-xs text-slate-500">(gasto)</span>
                      </span>
                    }
                  />
                )}
                {/* La plata del descuadre: sin esto solo se veía yendo a
                    Reportes o a Inventario (hallazgo de pruebas de usuario) */}
                {canViewPrices && discrepancyNet !== 0 && (
                  <InfoRow
                    label="Descuadre a Resultados"
                    value={
                      <span
                        className={cn(
                          "font-semibold tabular-nums",
                          discrepancyNet > 0 ? "text-emerald-700" : "text-rose-700"
                        )}
                      >
                        {discrepancyNet > 0 ? "+" : ""}
                        {formatCurrency(discrepancyNet)}
                        <span className="ml-1.5 font-normal text-xs text-slate-500">
                          ({discrepancyNet > 0 ? "ganancia" : "pérdida"})
                        </span>
                      </span>
                    }
                  />
                )}
              </>
            )}
            {order.status === "annulled" && (
              <>
                <InfoRow label="Anulada" value={order.annulled_at ? formatDateTime(order.annulled_at) : "—"} />
                <InfoRow label="Motivo" value={order.annulled_reason ?? "—"} long />
              </>
            )}
          </CardContent>
        </Card>
      </div>

      {/* #93: cara financiera — una tarjeta por proveedor del reparto */}
      {isPurchaseType && order.purchases.length > 0 && (
        <Card className="shadow-sm">
          <CardHeader>
            <CardTitle className="text-sm font-semibold uppercase tracking-wider text-slate-500">
              Compras por Proveedor ({order.purchases.length})
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
              {order.purchases.map((p) => (
                <div
                  key={p.purchase_id}
                  className={`rounded-lg border p-3 space-y-1 ${
                    p.status === "cancelled" ? "border-rose-200 bg-rose-50/50 opacity-70" : "border-slate-200"
                  }`}
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-medium text-sm truncate">
                      <ThirdPartyLink id={p.supplier_id}>{p.supplier_name ?? "—"}</ThirdPartyLink>
                    </span>
                    <StatusBadge status={p.status} />
                  </div>
                  <div className="flex items-center justify-between gap-2 text-sm">
                    <PurchaseLink id={p.purchase_id}>Compra #{p.purchase_number}</PurchaseLink>
                    {canViewPrices && (
                      <span className="font-semibold tabular-nums">{formatCurrency(p.total_amount)}</span>
                    )}
                  </div>
                  {p.invoice_number && (
                    <div className="text-xs text-slate-500">Factura: {p.invoice_number}</div>
                  )}
                  {p.retentions_total != null && p.retentions_total > 0 && canViewPrices && (
                    <div className="text-xs text-slate-500">
                      Retenciones: {formatCurrency(p.retentions_total)} · Neto:{" "}
                      <span className="font-medium text-slate-700">
                        {formatCurrency(p.total_amount - p.retentions_total)}
                      </span>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* #93 D7: los ajustes del descuadre — la plata que la Entrada mandó a
          resultados, con link a cada ajuste (antes solo se veía en Reportes) */}
      {discrepancyAdjustments.length > 0 && canViewPrices && (
        <Card className="shadow-sm">
          <CardHeader>
            <CardTitle className="text-sm font-semibold uppercase tracking-wider text-slate-500">
              Descuadre a Resultados ({discrepancyAdjustments.length})
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {discrepancyAdjustments.map((a) => (
                <div
                  key={a.adjustment_id}
                  className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-1 sm:gap-3 text-sm border-b border-slate-100 last:border-0 pb-2 last:pb-0"
                >
                  <div className="flex items-center gap-2 min-w-0">
                    <AdjustmentLink id={a.adjustment_id}>
                      {a.material_code ?? "—"}
                    </AdjustmentLink>
                    <span className="text-slate-500 text-xs">
                      {a.adjustment_type === "increase" ? "sobrante" : "faltante"}{" "}
                      {formatWeight(a.quantity, a.material_unit)}
                      {a.unit_cost != null && ` × ${formatCurrency(a.unit_cost)}`}
                    </span>
                  </div>
                  <span
                    className={cn(
                      "font-semibold tabular-nums shrink-0",
                      a.total_value > 0 ? "text-emerald-700" : "text-rose-700"
                    )}
                  >
                    {a.total_value > 0 ? "+" : ""}
                    {formatCurrency(a.total_value)}
                  </span>
                </div>
              ))}
              <div className="flex justify-between pt-1 text-sm font-semibold">
                <span className="text-slate-500">Neto</span>
                <span
                  className={cn(
                    "tabular-nums",
                    discrepancyNet > 0 ? "text-emerald-700" : "text-rose-700"
                  )}
                >
                  {discrepancyNet > 0 ? "+" : ""}
                  {formatCurrency(discrepancyNet)}
                </span>
              </div>
            </div>
            <p className="mt-3 text-xs text-slate-500">
              Diferencia entre lo pesado y lo repartido, valorada al precio de
              referencia. Entra al inventario y al Estado de Resultados como
              ganancia o pérdida. Para deshacerlo, use «Revertir Liquidación».
            </p>
          </CardContent>
        </Card>
      )}

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
                  {isPurchaseType && <TableHead className="text-right">Precio (ref.)</TableHead>}
                  {isPurchaseType && !isLegacy && (
                    <>
                      <TableHead className="text-right">Repartido</TableHead>
                      <TableHead className="text-right">Descuadre</TableHead>
                    </>
                  )}
                  <TableHead className="text-right">Peso Báscula</TableHead>
                  {isWillard && <TableHead className="text-right">Kg Plomo</TableHead>}
                  <TableHead>Notas</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {order.lines.map((line) => {
                  const hasAllocs = line.allocations.length > 0;
                  const disc = line.discrepancy;
                  return (
                    <Fragment key={line.id}>
                      <TableRow>
                        <TableCell>
                          <span className="font-medium">{line.material_code}</span>
                          <span className="text-slate-500"> — {line.material_name}</span>
                          {line.unallocated_intentional && (
                            <span className="ml-2 text-xs text-slate-400">(sin proveedor, intencional)</span>
                          )}
                        </TableCell>
                        <TableCell className="text-right tabular-nums">
                          {formatWeight(line.quantity, line.material_unit || "kg")}
                        </TableCell>
                        {isPurchaseType && (
                          <TableCell className="text-right tabular-nums">
                            {line.reference_unit_price != null
                              ? formatCurrency(line.reference_unit_price)
                              : line.unit_price != null
                                ? formatCurrency(line.unit_price)
                                : "—"}
                          </TableCell>
                        )}
                        {isPurchaseType && !isLegacy && (
                          <>
                            <TableCell className="text-right tabular-nums">
                              {line.allocated_quantity != null
                                ? formatWeight(line.allocated_quantity, line.material_unit || "kg")
                                : "—"}
                            </TableCell>
                            <TableCell className="text-right">
                              {disc == null || !hasAllocs && disc === 0 ? (
                                <span className="text-slate-400">—</span>
                              ) : disc === 0 ? (
                                <span className="text-emerald-600 tabular-nums font-medium">0</span>
                              ) : (
                                <span
                                  className={`tabular-nums font-medium ${disc > 0 ? "text-emerald-700" : "text-rose-700"}`}
                                  title={disc > 0 ? "Sobrante (entra como ganancia)" : "Faltante (sale como pérdida)"}
                                >
                                  {disc > 0 ? "+" : ""}
                                  {formatWeight(disc, line.material_unit || "kg")}
                                </span>
                              )}
                            </TableCell>
                          </>
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
                      {/* #93: el reparto de la linea — proveedor x cantidad x precio */}
                      {hasAllocs && (
                        <TableRow className="bg-slate-50/60 hover:bg-slate-50/60">
                          <TableCell colSpan={isWillard ? 5 : isLegacy ? 5 : 7} className="py-2">
                            <div className="pl-4 space-y-0.5">
                              {line.allocations.map((a) => (
                                <div key={a.id} className="text-xs text-slate-600 flex flex-wrap gap-x-2">
                                  <span className="font-medium">{a.third_party_name ?? "—"}</span>
                                  <span className="tabular-nums">
                                    {formatWeight(a.quantity, line.material_unit || "kg")}
                                    {canViewPrices ? ` × ${formatCurrency(a.unit_price)}` : ""}
                                  </span>
                                  {a.invoice_number && (
                                    <span className="text-slate-400">Fact. {a.invoice_number}</span>
                                  )}
                                </div>
                              ))}
                            </div>
                          </TableCell>
                        </TableRow>
                      )}
                    </Fragment>
                  );
                })}
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

      {/* #93 D10: marcar revisada */}
      <ConfirmDialog
        open={reviewOpen}
        onOpenChange={setReviewOpen}
        title={`Marcar Revisada — Entrada #${order.order_number}`}
        description={
          isWillard
            ? "Certifica el peso de báscula de cada línea. Si a alguna le falta, la revisión se rechaza indicando el material. Después la entrada queda lista para liquidar."
            : "Confirma que lo pesado en patio fue validado — sin peso de báscula la revisión se rechaza. La entrada pasa a Revisada y queda lista para liquidar con el reparto de proveedores."
        }
        confirmLabel="Marcar Revisada"
        loading={reviewOrder.isPending}
        onConfirm={() =>
          reviewOrder.mutate(order.id, { onSuccess: () => setReviewOpen(false) })
        }
      />

      {/* #93 D20: revertir la liquidacion */}
      <ConfirmDialog
        open={unliquidateOpen}
        onOpenChange={setUnliquidateOpen}
        title={`Revertir Liquidación — Entrada #${order.order_number}`}
        description={`Se revierten las ${order.purchases.filter((p) => p.status === "liquidated").length} compras (vuelven a registradas, con sus mismos números), los ajustes de descuadre y la comisión del recolector. La entrada vuelve a Revisada CONSERVANDO el reparto — corrija lo necesario y liquide de nuevo. Un pago ya registrado queda como anticipo del proveedor (se avisa).`}
        confirmLabel="Revertir Liquidación"
        loading={unliquidateOrder.isPending}
        onConfirm={() =>
          unliquidateOrder.mutate(order.id, { onSuccess: () => setUnliquidateOpen(false) })
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
            : isLiquidated
              ? `Se revierte TODO el evento: las ${order.purchases.filter((p) => p.status !== "cancelled").length} compras del reparto se cancelan, los ajustes de descuadre y la comisión se anulan, y la entrada queda Anulada. Pagos ya registrados quedan como anticipos (se avisa).`
              : "La entrada no ha tenido efectos (el reparto llega al liquidar) — solo se marcará como anulada."
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
