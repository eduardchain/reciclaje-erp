import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, Ban, BookOpen, Pencil } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { PageHeader } from "@/components/shared/PageHeader";
import { ConfirmDialog } from "@/components/shared/ConfirmDialog";
import { usePermissions } from "@/hooks/usePermissions";
import { useAnnulControlDispatch, useControlDispatch } from "@/hooks/useControlDispatches";
import { buildRoute, ROUTES } from "@/utils/constants";
import { formatDate, formatDateTime, formatWeight } from "@/utils/formatters";
import { ControlDispatchStatusBadge } from "./ControlDispatchesPage";

export default function ControlDispatchDetailPage() {
  const navigate = useNavigate();
  const { id } = useParams<{ id: string }>();
  const { hasPermission } = usePermissions();
  const { data: d, isLoading } = useControlDispatch(id);
  const annulMutation = useAnnulControlDispatch();
  const [annulOpen, setAnnulOpen] = useState(false);
  const [annulReason, setAnnulReason] = useState("");

  if (isLoading) return <div className="p-8 text-center text-slate-500">Cargando…</div>;
  if (!d) return <div className="p-8 text-center text-slate-500">Salida de control no encontrada</div>;

  const registered = d.status === "registered";

  return (
    <div className="space-y-4">
      <PageHeader
        title={`Salida de control #${d.dispatch_number}`}
        description="Sin precio, sin inventario ni plata: queda el número y la remisión"
      >
        <Button variant="outline" onClick={() => navigate(ROUTES.CONTROL_DISPATCHES)} className="w-full sm:w-auto">
          <ArrowLeft className="h-4 w-4 mr-2" /> Volver
        </Button>
      </PageHeader>

      {!registered && (
        <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">
          Anulada{d.annulled_reason ? `: ${d.annulled_reason}` : ""}. Su remisión sigue ocupando su número en el talonario.
        </div>
      )}

      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base flex items-center gap-2">
            Documento <ControlDispatchStatusBadge status={d.status} />
          </CardTitle>
        </CardHeader>
        <CardContent>
          <dl className="grid grid-cols-1 md:grid-cols-2 gap-x-8 gap-y-2 text-sm">
            <div className="flex justify-between gap-3">
              <dt className="text-slate-500">Remisión</dt>
              <dd className="font-medium">{d.remission_number}</dd>
            </div>
            <div className="flex justify-between gap-3">
              <dt className="text-slate-500">Fecha</dt>
              <dd>{formatDate(d.date)}</dd>
            </div>
            <div className="flex flex-col sm:flex-row sm:justify-between gap-0.5 sm:gap-3">
              <dt className="text-slate-500">Bodega de donde sale</dt>
              <dd>{d.warehouse_name ?? "—"}</dd>
            </div>
            <div className="flex flex-col sm:flex-row sm:justify-between gap-0.5 sm:gap-3">
              <dt className="text-slate-500">Tercero</dt>
              <dd>{d.third_party_name ?? "—"}</dd>
            </div>
            {d.notes && (
              <div className="flex flex-col sm:flex-row sm:justify-between gap-0.5 sm:gap-3 md:col-span-2">
                <dt className="text-slate-500">Notas</dt>
                <dd>{d.notes}</dd>
              </div>
            )}
            <div className="flex flex-col sm:flex-row sm:justify-between gap-0.5 sm:gap-3">
              <dt className="text-slate-500">Registrada por</dt>
              <dd>{d.created_by_name ?? "—"} · {formatDateTime(d.created_at)}</dd>
            </div>
            {d.annulled_at && (
              <div className="flex flex-col sm:flex-row sm:justify-between gap-0.5 sm:gap-3">
                <dt className="text-slate-500">Anulada por</dt>
                <dd>{d.annulled_by_name ?? "—"} · {formatDateTime(d.annulled_at)}</dd>
              </div>
            )}
          </dl>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-2"><CardTitle className="text-base">Materiales</CardTitle></CardHeader>
        <CardContent className="p-0">
          <div className="hidden md:block">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Material</TableHead>
                  <TableHead className="text-right">Cantidad</TableHead>
                  <TableHead className="text-right">Báscula</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {d.lines.map((l) => (
                  <TableRow key={l.id}>
                    <TableCell>{l.material_code} - {l.material_name}</TableCell>
                    <TableCell className="text-right tabular-nums">{formatWeight(l.quantity, l.material_unit)}</TableCell>
                    <TableCell className="text-right tabular-nums">
                      {l.scale_weight_kg != null ? formatWeight(l.scale_weight_kg, "kg") : "—"}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
          <div className="md:hidden divide-y">
            {d.lines.map((l) => (
              <div key={l.id} className="p-3 text-sm space-y-0.5">
                <p className="font-medium">{l.material_code} - {l.material_name}</p>
                <div className="flex justify-between gap-3">
                  <span className="text-slate-500">Cantidad</span>
                  <span className="tabular-nums">{formatWeight(l.quantity, l.material_unit)}</span>
                </div>
                {l.scale_weight_kg != null && (
                  <div className="flex justify-between gap-3">
                    <span className="text-slate-500">Báscula</span>
                    <span className="tabular-nums">{formatWeight(l.scale_weight_kg, "kg")}</span>
                  </div>
                )}
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      <div className="flex flex-col sm:flex-row sm:flex-wrap gap-2">
        {hasPermission("purchases.view") && hasPermission("sales.view") && (
          <Button variant="outline" onClick={() => navigate(ROUTES.REMISSION_BOOK)} className="w-full sm:w-auto">
            <BookOpen className="h-4 w-4 mr-2" /> Talonario de remisiones
          </Button>
        )}
        {registered && hasPermission("sales.edit") && (
          <Button
            variant="outline"
            onClick={() => navigate(buildRoute(ROUTES.CONTROL_DISPATCH_EDIT, { id: d.id }))}
            className="w-full sm:w-auto"
          >
            <Pencil className="h-4 w-4 mr-2" /> Editar
          </Button>
        )}
        {registered && hasPermission("sales.cancel") && (
          <Button variant="outline" onClick={() => setAnnulOpen(true)} className="w-full sm:w-auto">
            <Ban className="h-4 w-4 mr-2" /> Anular
          </Button>
        )}
      </div>

      <ConfirmDialog
        open={annulOpen}
        onOpenChange={setAnnulOpen}
        title={`Anular la Salida de control #${d.dispatch_number}`}
        description="No hay efectos que revertir: el documento queda anulado y su remisión sigue ocupando su número en el talonario."
        confirmLabel="Anular"
        variant="destructive"
        loading={annulMutation.isPending}
        onConfirm={() =>
          annulMutation.mutate(
            { id: d.id, reason: annulReason.trim() },
            { onSuccess: () => setAnnulOpen(false) },
          )
        }
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
