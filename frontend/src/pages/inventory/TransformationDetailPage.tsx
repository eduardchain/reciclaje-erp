import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { ArrowLeft } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { PageHeader } from "@/components/shared/PageHeader";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { WarningsList } from "@/components/shared/WarningsList";
import { ConfirmDialog } from "@/components/shared/ConfirmDialog";
import { useTransformation, useAnnulTransformation } from "@/hooks/useInventory";
import { formatCurrency, formatDate } from "@/utils/formatters";
import { ROUTES } from "@/utils/constants";

const statusBorderMap: Record<string, string> = {
  completed: "border-t-[3px] border-t-emerald-400",
  annulled: "border-t-[3px] border-t-rose-400",
};

export default function TransformationDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { data: t, isLoading } = useTransformation(id!);
  const annul = useAnnulTransformation();
  const [showAnnul, setShowAnnul] = useState(false);
  const [annulReason, setAnnulReason] = useState("");

  if (isLoading) return <div className="p-8 text-center text-slate-500">Cargando...</div>;
  if (!t) return <div className="p-8 text-center text-slate-500">Transformacion no encontrada</div>;

  return (
    <div className="space-y-6">
      <PageHeader title={`Transformacion #${t.transformation_number}`} description={`${t.source_material_code} - ${t.source_material_name}`}>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => navigate(ROUTES.INVENTORY_TRANSFORMATIONS)}>
            <ArrowLeft className="h-4 w-4 mr-2" />Volver
          </Button>
          {t.status === "confirmed" && (
            <Button variant="destructive" onClick={() => setShowAnnul(true)}>Anular</Button>
          )}
        </div>
      </PageHeader>

      {t.warnings.length > 0 && <WarningsList warnings={t.warnings} />}

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card className="shadow-sm">
          <CardHeader><CardTitle className="text-sm font-semibold uppercase tracking-wider text-slate-500">Origen</CardTitle></CardHeader>
          <CardContent className="space-y-2 text-sm">
            <div className="flex justify-between"><span className="text-xs font-semibold uppercase tracking-wider text-slate-500">Material</span><span>{t.source_material_code} - {t.source_material_name}</span></div>
            <div className="flex justify-between"><span className="text-xs font-semibold uppercase tracking-wider text-slate-500">Bodega</span><span>{t.source_warehouse_name}</span></div>
            <div className="flex justify-between"><span className="text-xs font-semibold uppercase tracking-wider text-slate-500">Cantidad</span><span className="font-medium tabular-nums">{t.source_quantity.toFixed(2)}</span></div>
            <div className="flex justify-between"><span className="text-xs font-semibold uppercase tracking-wider text-slate-500">Costo Unit.</span><span>{formatCurrency(t.source_unit_cost)}</span></div>
            <div className="flex justify-between"><span className="text-xs font-semibold uppercase tracking-wider text-slate-500">Valor Total</span><span className="font-bold">{formatCurrency(t.source_total_value)}</span></div>
          </CardContent>
        </Card>

        <Card className="shadow-sm">
          <CardHeader><CardTitle className="text-sm font-semibold uppercase tracking-wider text-slate-500">Merma y Distribucion</CardTitle></CardHeader>
          <CardContent className="space-y-2 text-sm">
            <div className="flex justify-between"><span className="text-xs font-semibold uppercase tracking-wider text-slate-500">Merma</span><span className="tabular-nums text-orange-600">{t.waste_quantity.toFixed(2)}</span></div>
            <div className="flex justify-between"><span className="text-xs font-semibold uppercase tracking-wider text-slate-500">Valor Merma</span><span>{formatCurrency(t.waste_value)}</span></div>
            <div className="flex justify-between"><span className="text-xs font-semibold uppercase tracking-wider text-slate-500">Distribucion</span><span>{t.cost_distribution === "average_cost" ? "Costo Promedio" : t.cost_distribution === "proportional_weight" ? "Proporcional" : "Manual"}</span></div>
          </CardContent>
        </Card>

        <Card className={`shadow-sm ${statusBorderMap[t.status] ?? ""}`}>
          <CardHeader><CardTitle className="text-sm font-semibold uppercase tracking-wider text-slate-500">Estado</CardTitle></CardHeader>
          <CardContent className="space-y-2 text-sm">
            <div className="flex justify-between"><span className="text-xs font-semibold uppercase tracking-wider text-slate-500">Fecha</span><span>{formatDate(t.date)}</span></div>
            <div className="flex justify-between"><span className="text-xs font-semibold uppercase tracking-wider text-slate-500">Estado</span><StatusBadge status={t.status} /></div>
            <div className="flex justify-between"><span className="text-xs font-semibold uppercase tracking-wider text-slate-500">Razon</span><span className="text-right max-w-[200px]">{t.reason}</span></div>
          </CardContent>
        </Card>
      </div>

      {/* Lineas de destino */}
      <Card className="shadow-sm">
        <CardHeader><CardTitle className="text-sm font-semibold uppercase tracking-wider text-slate-500">Materiales Destino</CardTitle></CardHeader>
        <CardContent>
          <div className="rounded-lg border border-slate-200/80 overflow-hidden">
            <Table>
              <TableHeader>
                <TableRow className="bg-slate-50/80 border-b border-slate-200/80">
                  <TableHead className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 h-10">Material</TableHead>
                  <TableHead className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 h-10">Bodega</TableHead>
                  <TableHead className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 h-10 text-right">Cantidad</TableHead>
                  <TableHead className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 h-10 text-right">Costo Unit.</TableHead>
                  <TableHead className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 h-10 text-right">Total</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {t.lines.map((line) => (
                  <TableRow key={line.id}>
                    <TableCell>{line.destination_material_code} - {line.destination_material_name}</TableCell>
                    <TableCell>{line.destination_warehouse_name}</TableCell>
                    <TableCell className="text-right tabular-nums">{line.quantity.toFixed(2)}</TableCell>
                    <TableCell className="text-right">{formatCurrency(line.unit_cost)}</TableCell>
                    <TableCell className="text-right font-medium">{formatCurrency(line.total_cost)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
          <div className="bg-slate-50 rounded-lg p-3 mt-3">
            <div className="flex justify-between items-center">
              {t.value_difference != null && t.value_difference !== 0 ? (
                <div className={`px-3 py-1 rounded-md text-sm font-medium ${t.value_difference > 0 ? "bg-green-100 text-green-700" : "bg-red-100 text-red-700"}`}>
                  {t.value_difference > 0 ? "Ganancia" : "Perdida"} por Valorizacion: {formatCurrency(Math.abs(t.value_difference))}
                </div>
              ) : <div />}
              <span className="text-lg font-bold">{formatCurrency(t.source_total_value)}</span>
            </div>
          </div>
        </CardContent>
      </Card>

      {t.annulled_reason && (
        <Card className="shadow-sm border-red-200 bg-red-50">
          <CardContent className="pt-6">
            <p className="text-sm text-red-800"><strong>Anulado:</strong> {t.annulled_reason}</p>
            {t.annulled_at && <p className="text-xs text-red-600 mt-1">Fecha: {formatDate(t.annulled_at)}</p>}
          </CardContent>
        </Card>
      )}

      {t.notes && (
        <Card className="shadow-sm">
          <CardContent className="pt-6">
            <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">Notas</p>
            <p className="text-sm mt-1">{t.notes}</p>
          </CardContent>
        </Card>
      )}

      <ConfirmDialog
        open={showAnnul}
        onOpenChange={setShowAnnul}
        title="Anular Transformacion"
        description="Se revertiran todos los movimientos de stock."
        onConfirm={() => annul.mutate({ id: t.id, data: { reason: annulReason } }, { onSuccess: () => navigate(ROUTES.INVENTORY_TRANSFORMATIONS) })}
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
