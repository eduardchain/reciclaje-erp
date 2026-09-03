import { useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, ClipboardCheck, Ban, CheckCircle2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { PageHeader } from "@/components/shared/PageHeader";
import { ConfirmDialog } from "@/components/shared/ConfirmDialog";
import { MoneyInput } from "@/components/shared/MoneyInput";
import { SaleLink, ThirdPartyLink } from "@/components/shared/EntityLink";
import { usePermissions } from "@/hooks/usePermissions";
import {
  useAnnulWillardDelivery, useLiquidateWillardDelivery,
  useReviewWillardDelivery, useWillardDelivery,
} from "@/hooks/useWillardDeliveries";
import { formatCurrency, formatDate, formatDateTime, formatWeight } from "@/utils/formatters";
import { num } from "@/types/willard-delivery";
import { DeliveryStatusBadge, DeliveryTypeBadge } from "./WillardDeliveriesPage";

export default function WillardDeliveryDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { hasPermission } = usePermissions();

  const { data: delivery, isLoading } = useWillardDelivery(id);
  const reviewMutation = useReviewWillardDelivery();
  const liquidateMutation = useLiquidateWillardDelivery();
  const annulMutation = useAnnulWillardDelivery();

  const [prices, setPrices] = useState<Record<string, number>>({});
  const [annulOpen, setAnnulOpen] = useState(false);
  const [annulReason, setAnnulReason] = useState("");

  // ⚠️ Todos los hooks ANTES del primer return condicional (#93 bloqueante a:
  // un useMemo despues de un `return` dejo la pantalla en blanco).
  const isVenta = delivery?.delivery_type === "venta";
  const missingPrice = useMemo(() => {
    if (!delivery || !isVenta) return false;
    return delivery.lines.some((l) => !(prices[l.id] > 0));
  }, [delivery, isVenta, prices]);

  if (isLoading) return <div className="p-8 text-center text-slate-500">Cargando…</div>;
  if (!delivery) return <div className="p-8 text-center text-slate-500">Salida no encontrada</div>;

  const liquidate = () =>
    liquidateMutation.mutate({
      id: delivery.id,
      data: {
        line_prices: isVenta
          ? delivery.lines.map((l) => ({ line_id: l.id, unit_price: String(prices[l.id]) }))
          : [],
      },
    });

  return (
    <div className="space-y-4">
      <PageHeader
        title={`Salida #${delivery.delivery_number}`}
        description={delivery.warehouse_name ?? undefined}
      >
        <Button variant="outline" onClick={() => navigate("/willard-deliveries")} className="w-full sm:w-auto">
          <ArrowLeft className="h-4 w-4 mr-2" /> Volver
        </Button>
      </PageHeader>

      {delivery.status === "draft" && (
        <Card className="border-amber-300 bg-amber-50">
          <CardContent className="p-4 flex flex-col sm:flex-row sm:items-center gap-3">
            <p className="text-sm text-amber-900 flex-1">
              Registrada. Antes de liquidar hay que certificar los pesos de báscula.
            </p>
            {hasPermission("sales.review") && (
              <Button
                onClick={() => reviewMutation.mutate(delivery.id)}
                disabled={reviewMutation.isPending}
                className="w-full sm:w-auto"
              >
                <ClipboardCheck className="h-4 w-4 mr-2" /> Revisar
              </Button>
            )}
          </CardContent>
        </Card>
      )}

      <Card>
        <CardContent className="p-4 grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3 text-sm">
          <div className="flex justify-between gap-3">
            <span className="text-slate-500">Tipo</span>
            <DeliveryTypeBadge type={delivery.delivery_type} />
          </div>
          <div className="flex justify-between gap-3">
            <span className="text-slate-500">Estado</span>
            <DeliveryStatusBadge status={delivery.status} />
          </div>
          <div className="flex justify-between gap-3">
            <span className="text-slate-500">Fecha</span>
            <span>{formatDate(delivery.date)}</span>
          </div>
          <div className="flex flex-col sm:flex-row sm:justify-between gap-0.5 sm:gap-3">
            <span className="text-slate-500">Tercero</span>
            <ThirdPartyLink id={delivery.third_party_id}>{delivery.third_party_name ?? "—"}</ThirdPartyLink>
          </div>
          <div className="flex justify-between gap-3">
            <span className="text-slate-500">Remisión</span>
            <span>{delivery.remission_number ?? "—"}</span>
          </div>
          <div className="flex justify-between gap-3">
            <span className="text-slate-500">Kg plomo</span>
            <span className="tabular-nums">{formatWeight(num(delivery.total_kg_lead), "kg")}</span>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle className="text-base">Materiales</CardTitle></CardHeader>
        <CardContent className="p-0 overflow-x-auto">
          <Table className="min-w-[640px]">
            <TableHeader>
              <TableRow>
                <TableHead>Material</TableHead>
                <TableHead className="text-right">Cantidad</TableHead>
                <TableHead className="text-right">Báscula</TableHead>
                <TableHead className="text-right">Kg plomo</TableHead>
                {isVenta && <TableHead className="text-right">Precio</TableHead>}
              </TableRow>
            </TableHeader>
            <TableBody>
              {delivery.lines.map((l) => (
                <TableRow key={l.id}>
                  <TableCell>{l.material_code} — {l.material_name}</TableCell>
                  <TableCell className="text-right tabular-nums">
                    {formatWeight(num(l.quantity), l.material_unit)}
                  </TableCell>
                  <TableCell className="text-right tabular-nums">
                    {l.scale_weight_kg ? formatWeight(num(l.scale_weight_kg), "kg") : "—"}
                  </TableCell>
                  <TableCell className="text-right tabular-nums">
                    {l.kg_lead_equivalent ? formatWeight(num(l.kg_lead_equivalent), "kg") : "—"}
                  </TableCell>
                  {isVenta && (
                    <TableCell className="text-right">
                      {delivery.status === "reviewed" ? (
                        <MoneyInput
                          value={prices[l.id] ?? 0}
                          onChange={(v) => setPrices((p) => ({ ...p, [l.id]: v }))}
                          className="w-32 ml-auto"
                        />
                      ) : (
                        <span className="tabular-nums">
                          {l.unit_price ? formatCurrency(num(l.unit_price)) : "—"}
                        </span>
                      )}
                    </TableCell>
                  )}
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {delivery.status === "liquidated" && (
        <Card>
          <CardHeader><CardTitle className="text-base">Facturación y reparto</CardTitle></CardHeader>
          <CardContent className="p-4 grid grid-cols-1 sm:grid-cols-2 gap-3 text-sm">
            <div className="flex justify-between gap-3">
              <span className="text-slate-500">Maquila facturada</span>
              <span className="tabular-nums">{formatCurrency(num(delivery.maquila_amount))}</span>
            </div>
            <div className="flex justify-between gap-3">
              <span className="text-slate-500">Flete facturado</span>
              <span className="tabular-nums">{formatCurrency(num(delivery.freight_amount))}</span>
            </div>
            <div className="flex justify-between gap-3">
              <span className="text-slate-500">Abonado a planta</span>
              <span className="tabular-nums">{formatCurrency(num(delivery.plant_credit_amount))}</span>
            </div>
            {delivery.sale_id && (
              <div className="flex justify-between gap-3">
                <span className="text-slate-500">Venta</span>
                <SaleLink id={delivery.sale_id}>#{delivery.sale_number}</SaleLink>
              </div>
            )}
            {delivery.liquidated_ts && (
              <div className="flex justify-between gap-3">
                <span className="text-slate-500">Liquidada</span>
                <span>{formatDateTime(delivery.liquidated_ts)}</span>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      <div className="flex flex-col sm:flex-row sm:justify-end gap-2">
        {delivery.status === "reviewed" && hasPermission("sales.liquidate") && (
          <Button
            onClick={liquidate}
            disabled={missingPrice || liquidateMutation.isPending}
            className="w-full sm:w-auto"
          >
            <CheckCircle2 className="h-4 w-4 mr-2" /> Liquidar
          </Button>
        )}
        {delivery.status !== "annulled" && hasPermission("sales.cancel") && (
          <Button variant="outline" onClick={() => setAnnulOpen(true)} className="w-full sm:w-auto">
            <Ban className="h-4 w-4 mr-2" /> Anular
          </Button>
        )}
      </div>

      <ConfirmDialog
        open={annulOpen}
        onOpenChange={setAnnulOpen}
        title={`Anular salida #${delivery.delivery_number}`}
        description="Se revierte el inventario, la deuda en kg, la factura y el reparto."
        confirmLabel="Anular"
        variant="destructive"
        onConfirm={() => {
          annulMutation.mutate({ id: delivery.id, reason: annulReason });
          setAnnulOpen(false);
        }}
        disabled={annulReason.trim().length < 3}
      >
        <div className="space-y-1">
          <Label>Motivo *</Label>
          <input
            className="w-full border rounded-md px-3 py-2 text-sm"
            value={annulReason}
            onChange={(e) => setAnnulReason(e.target.value)}
            placeholder="Por qué se anula"
          />
        </div>
      </ConfirmDialog>
    </div>
  );
}
