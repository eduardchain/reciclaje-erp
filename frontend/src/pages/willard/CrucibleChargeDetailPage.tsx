import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, Ban } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { PageHeader } from "@/components/shared/PageHeader";
import { ConfirmDialog } from "@/components/shared/ConfirmDialog";
import { usePermissions } from "@/hooks/usePermissions";
import { useAnnulCrucibleCharge, useCrucibleCharge } from "@/hooks/useCrucibleCharges";
import { formatCurrency, formatDate, formatDateTime, formatWeight } from "@/utils/formatters";
import { CRUCIBLE_EVENT_LABELS, num } from "@/types/crucible-charge";
import { CrucibleEventBadge, CrucibleStatusBadge } from "./CrucibleChargesSection";

export default function CrucibleChargeDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { hasPermission } = usePermissions();
  const { data: charge, isLoading } = useCrucibleCharge(id);
  const annulMutation = useAnnulCrucibleCharge();
  const [annulOpen, setAnnulOpen] = useState(false);
  const [annulReason, setAnnulReason] = useState("");

  if (isLoading) return <div className="p-8 text-center text-slate-500">Cargando…</div>;
  if (!charge) return <div className="p-8 text-center text-slate-500">Documento no encontrado</div>;

  const kg = num(charge.quantity_kg);
  const isCharge = charge.event_type === "charge";
  // Lo que hizo el documento sobre las dos etapas (D2): el neto es cero.
  const effect = isCharge
    ? [["En horno (crudo)", -kg], ["En crisol", +kg]]
    : [["En crisol", -kg], ["En horno (crudo)", +kg]];

  return (
    <div className="space-y-4">
      <PageHeader
        title={charge.label}
        description={CRUCIBLE_EVENT_LABELS[charge.event_type]}
      >
        <Button variant="outline" onClick={() => navigate("/willard-deliveries?type=crisol")} className="w-full sm:w-auto">
          <ArrowLeft className="h-4 w-4 mr-2" /> Volver
        </Button>
      </PageHeader>

      <div className="flex flex-wrap gap-2">
        <CrucibleEventBadge type={charge.event_type} />
        <CrucibleStatusBadge status={charge.status} />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Card>
          <CardHeader><CardTitle className="text-base">Documento</CardTitle></CardHeader>
          <CardContent className="p-4 text-sm space-y-2">
            <div className="flex justify-between gap-3">
              <span className="text-slate-500">Fecha</span>
              <span>{formatDate(charge.date)}</span>
            </div>
            <div className="flex justify-between gap-3">
              <span className="text-slate-500">Planta</span>
              <span>{charge.warehouse_name ?? "—"}</span>
            </div>
            <div className="flex flex-col sm:flex-row sm:justify-between gap-0.5 sm:gap-3">
              <span className="text-slate-500">Material</span>
              <span>{charge.material_code ?? "—"}{charge.material_name ? ` - ${charge.material_name}` : ""}</span>
            </div>
            <div className="flex justify-between gap-3">
              <span className="text-slate-500">Kg de plomo</span>
              <span className="tabular-nums font-medium">{formatWeight(kg, "kg")}</span>
            </div>
            {charge.notes && (
              <div className="flex flex-col sm:flex-row sm:justify-between gap-0.5 sm:gap-3">
                <span className="text-slate-500">Notas</span>
                <span className="sm:text-right">{charge.notes}</span>
              </div>
            )}
            <div className="flex justify-between gap-3">
              <span className="text-slate-500">Registrado</span>
              <span>{formatDateTime(charge.created_at)}{charge.created_by_name ? ` · ${charge.created_by_name}` : ""}</span>
            </div>
            {charge.status === "annulled" && (
              <div className="flex flex-col sm:flex-row sm:justify-between gap-0.5 sm:gap-3 text-red-700">
                <span>Anulado</span>
                <span className="sm:text-right">
                  {charge.annulled_at ? formatDateTime(charge.annulled_at) : ""}
                  {charge.annulled_by_name ? ` · ${charge.annulled_by_name}` : ""}
                  {charge.annulled_reason ? ` — ${charge.annulled_reason}` : ""}
                </span>
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader><CardTitle className="text-base">Efecto sobre la deuda intersede</CardTitle></CardHeader>
          <CardContent className="p-4 text-sm space-y-2">
            {effect.map(([label, delta]) => (
              <div key={String(label)} className="flex justify-between gap-3">
                <span className="text-slate-500">{label}</span>
                <span className={num(delta) < 0 ? "text-red-600 tabular-nums" : "text-emerald-700 tabular-nums"}>
                  {num(delta) > 0 ? "+" : ""}{formatWeight(num(delta), "kg")}
                </span>
              </div>
            ))}
            <div className="flex justify-between gap-3 border-t pt-2">
              <span className="text-slate-500">Deuda total</span>
              <span className="tabular-nums">sin cambio</span>
            </div>
            {!isCharge && (
              <div className="flex justify-between gap-3 border-t pt-2">
                <span className="text-slate-500">Maquila del reproceso (planta → sede que factura)</span>
                <span className="tabular-nums">
                  {num(charge.maquila_amount) > 0 ? formatCurrency(num(charge.maquila_amount)) : "—"}
                </span>
              </div>
            )}
            <p className="text-xs text-slate-500 pt-1">
              Este documento no mueve inventario: la conversión física del material se registra como transformación.
            </p>
          </CardContent>
        </Card>
      </div>

      {charge.status !== "annulled" && hasPermission("sales.cancel") && (
        <div className="flex flex-col sm:flex-row sm:justify-end gap-2">
          <Button variant="outline" onClick={() => setAnnulOpen(true)} className="w-full sm:w-auto">
            <Ban className="h-4 w-4 mr-2" /> Anular
          </Button>
        </div>
      )}

      <ConfirmDialog
        open={annulOpen}
        onOpenChange={setAnnulOpen}
        title={`Anular ${charge.label}`}
        description="Se revierten los kg entre etapas y, si la hubo, la maquila del reproceso."
        confirmLabel="Anular"
        variant="destructive"
        onConfirm={() => {
          annulMutation.mutate({ id: charge.id, reason: annulReason });
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
