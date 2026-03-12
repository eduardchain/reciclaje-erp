import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { ArrowLeft } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { PageHeader } from "@/components/shared/PageHeader";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { WarningsList } from "@/components/shared/WarningsList";
import { ConfirmDialog } from "@/components/shared/ConfirmDialog";
import { useAdjustment, useAnnulAdjustment } from "@/hooks/useInventory";
import { formatCurrency, formatDate } from "@/utils/formatters";
import { ROUTES } from "@/utils/constants";

const typeLabels: Record<string, string> = {
  increase: "Aumento",
  decrease: "Disminucion",
  recount: "Conteo Fisico",
  zero_out: "Llevar a Cero",
};

const statusBorderMap: Record<string, string> = {
  completed: "border-t-[3px] border-t-emerald-400",
  annulled: "border-t-[3px] border-t-rose-400",
};

export default function AdjustmentDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { data: adj, isLoading } = useAdjustment(id!);
  const annul = useAnnulAdjustment();
  const [showAnnul, setShowAnnul] = useState(false);
  const [annulReason, setAnnulReason] = useState("");

  if (isLoading) return <div className="p-8 text-center text-slate-500">Cargando...</div>;
  if (!adj) return <div className="p-8 text-center text-slate-500">Ajuste no encontrado</div>;

  return (
    <div className="space-y-6">
      <PageHeader title={`Ajuste #${adj.adjustment_number}`} description={typeLabels[adj.adjustment_type] ?? adj.adjustment_type}>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => navigate(ROUTES.INVENTORY_ADJUSTMENTS)}>
            <ArrowLeft className="h-4 w-4 mr-2" />Volver
          </Button>
          {adj.status === "confirmed" && (
            <Button variant="destructive" onClick={() => setShowAnnul(true)}>Anular</Button>
          )}
        </div>
      </PageHeader>

      {adj.warnings.length > 0 && <WarningsList warnings={adj.warnings} />}

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card className={`shadow-sm ${statusBorderMap[adj.status] ?? ""}`}>
          <CardHeader><CardTitle className="text-sm font-semibold uppercase tracking-wider text-slate-500">Informacion General</CardTitle></CardHeader>
          <CardContent className="space-y-2 text-sm">
            <div className="flex justify-between"><span className="text-xs font-semibold uppercase tracking-wider text-slate-500">Fecha</span><span>{formatDate(adj.date)}</span></div>
            <div className="flex justify-between"><span className="text-xs font-semibold uppercase tracking-wider text-slate-500">Tipo</span><Badge variant="outline">{typeLabels[adj.adjustment_type]}</Badge></div>
            <div className="flex justify-between"><span className="text-xs font-semibold uppercase tracking-wider text-slate-500">Estado</span><StatusBadge status={adj.status} /></div>
            <div className="flex justify-between"><span className="text-xs font-semibold uppercase tracking-wider text-slate-500">Razon</span><span className="text-right max-w-[200px]">{adj.reason}</span></div>
          </CardContent>
        </Card>

        <Card className="shadow-sm">
          <CardHeader><CardTitle className="text-sm font-semibold uppercase tracking-wider text-slate-500">Material y Bodega</CardTitle></CardHeader>
          <CardContent className="space-y-2 text-sm">
            <div className="flex justify-between"><span className="text-xs font-semibold uppercase tracking-wider text-slate-500">Material</span><span>{adj.material_code} - {adj.material_name}</span></div>
            <div className="flex justify-between"><span className="text-xs font-semibold uppercase tracking-wider text-slate-500">Bodega</span><span>{adj.warehouse_name}</span></div>
          </CardContent>
        </Card>

        <Card className="shadow-sm">
          <CardHeader><CardTitle className="text-sm font-semibold uppercase tracking-wider text-slate-500">Cantidades</CardTitle></CardHeader>
          <CardContent className="space-y-2 text-sm">
            <div className="flex justify-between"><span className="text-xs font-semibold uppercase tracking-wider text-slate-500">Stock Anterior</span><span className="tabular-nums">{adj.previous_stock.toFixed(2)}</span></div>
            <div className="flex justify-between"><span className="text-xs font-semibold uppercase tracking-wider text-slate-500">Cantidad</span><span className="font-medium tabular-nums">{adj.quantity >= 0 ? "+" : ""}{adj.quantity.toFixed(2)}</span></div>
            {adj.counted_quantity !== null && <div className="flex justify-between"><span className="text-xs font-semibold uppercase tracking-wider text-slate-500">Conteo</span><span className="tabular-nums">{adj.counted_quantity.toFixed(2)}</span></div>}
            <div className="flex justify-between"><span className="text-xs font-semibold uppercase tracking-wider text-slate-500">Stock Nuevo</span><span className="font-bold tabular-nums">{adj.new_stock.toFixed(2)}</span></div>
            <div className="flex justify-between"><span className="text-xs font-semibold uppercase tracking-wider text-slate-500">Costo Unit.</span><span>{formatCurrency(adj.unit_cost)}</span></div>
            <div className="flex justify-between"><span className="text-xs font-semibold uppercase tracking-wider text-slate-500">Valor Total</span><span className="font-bold">{formatCurrency(adj.total_value)}</span></div>
          </CardContent>
        </Card>
      </div>

      {adj.annulled_reason && (
        <Card className="shadow-sm border-red-200 bg-red-50">
          <CardContent className="pt-6">
            <p className="text-sm text-red-800"><strong>Anulado:</strong> {adj.annulled_reason}</p>
            {adj.annulled_at && <p className="text-xs text-red-600 mt-1">Fecha: {formatDate(adj.annulled_at)}</p>}
          </CardContent>
        </Card>
      )}

      {adj.notes && (
        <Card className="shadow-sm">
          <CardContent className="pt-6">
            <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">Notas</p>
            <p className="text-sm mt-1">{adj.notes}</p>
          </CardContent>
        </Card>
      )}

      <ConfirmDialog
        open={showAnnul}
        onOpenChange={setShowAnnul}
        title="Anular Ajuste"
        description="Esta accion revertira los cambios de stock."
        onConfirm={() => annul.mutate({ id: adj.id, data: { reason: annulReason } }, { onSuccess: () => navigate(ROUTES.INVENTORY_ADJUSTMENTS) })}
        variant="destructive"
        loading={annul.isPending}
        disabled={annulReason.length < 1}
      >
        <div className="space-y-2 mt-2">
          <Label>Razon de anulacion *</Label>
          <Input value={annulReason} onChange={(e) => setAnnulReason(e.target.value)} placeholder="Razon..." />
        </div>
      </ConfirmDialog>
    </div>
  );
}
