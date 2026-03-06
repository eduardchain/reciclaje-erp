import { useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { ArrowLeft, XCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { PageHeader } from "@/components/shared/PageHeader";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { ConfirmDialog } from "@/components/shared/ConfirmDialog";
import { useMoneyMovement, useAnnulMovement } from "@/hooks/useMoneyMovements";
import { formatCurrency, formatDate } from "@/utils/formatters";
import { ROUTES } from "@/utils/constants";

const typeLabels: Record<string, string> = {
  payment_to_supplier: "Pago a Proveedor",
  collection_from_client: "Cobro a Cliente",
  expense: "Gasto",
  service_income: "Ingreso por Servicio",
  transfer_out: "Transferencia Salida",
  transfer_in: "Transferencia Entrada",
  capital_injection: "Aporte de Capital",
  capital_return: "Devolucion de Capital",
  commission_payment: "Pago de Comision",
};

const statusBorderMap: Record<string, string> = {
  confirmed: "border-t-[3px] border-t-emerald-400",
  annulled: "border-t-[3px] border-t-rose-400",
};

export default function MovementDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { data: movement, isLoading } = useMoneyMovement(id!);
  const annul = useAnnulMovement();

  const [showAnnul, setShowAnnul] = useState(false);
  const [annulReason, setAnnulReason] = useState("");

  if (isLoading) return <div className="space-y-4"><Skeleton className="h-8 w-64" /><Skeleton className="h-64 w-full" /></div>;
  if (!movement) return <div className="text-center py-12 text-slate-500">Movimiento no encontrado</div>;

  const handleAnnul = () => {
    if (!id || !annulReason) return;
    annul.mutate(
      { id, data: { reason: annulReason } },
      { onSuccess: () => { setShowAnnul(false); setAnnulReason(""); } },
    );
  };

  return (
    <div className="space-y-6">
      <PageHeader title={`Movimiento #${movement.movement_number}`} description={typeLabels[movement.movement_type] ?? movement.movement_type}>
        <div className="flex items-center gap-2">
          {movement.status === "confirmed" && (
            <Button variant="outline" onClick={() => setShowAnnul(true)} className="text-red-600 border-red-200 hover:bg-red-50">
              <XCircle className="h-4 w-4 mr-2" />Anular
            </Button>
          )}
          <Button variant="outline" onClick={() => navigate(ROUTES.TREASURY)}>
            <ArrowLeft className="h-4 w-4 mr-2" />Volver
          </Button>
        </div>
      </PageHeader>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Card className={`shadow-sm ${statusBorderMap[movement.status] ?? ""}`}>
          <CardContent className="pt-6">
            <dl className="space-y-3 text-sm">
              <div className="flex justify-between"><dt className="text-xs font-semibold uppercase tracking-wider text-slate-500">Estado</dt><dd><StatusBadge status={movement.status} /></dd></div>
              <div className="flex justify-between"><dt className="text-xs font-semibold uppercase tracking-wider text-slate-500">Tipo</dt><dd><Badge variant="outline">{typeLabels[movement.movement_type]}</Badge></dd></div>
              <div className="flex justify-between"><dt className="text-xs font-semibold uppercase tracking-wider text-slate-500">Fecha</dt><dd>{formatDate(movement.date)}</dd></div>
              <div className="flex justify-between"><dt className="text-xs font-semibold uppercase tracking-wider text-slate-500">Monto</dt><dd className="font-bold text-lg">{formatCurrency(movement.amount)}</dd></div>
              <div className="flex justify-between"><dt className="text-xs font-semibold uppercase tracking-wider text-slate-500">Descripcion</dt><dd>{movement.description}</dd></div>
            </dl>
          </CardContent>
        </Card>

        <Card className="shadow-sm">
          <CardContent className="pt-6">
            <dl className="space-y-3 text-sm">
              <div className="flex justify-between"><dt className="text-xs font-semibold uppercase tracking-wider text-slate-500">Cuenta</dt><dd>{movement.account_name}</dd></div>
              {movement.third_party_name && <div className="flex justify-between"><dt className="text-xs font-semibold uppercase tracking-wider text-slate-500">Tercero</dt><dd>{movement.third_party_name}</dd></div>}
              {movement.expense_category_name && <div className="flex justify-between"><dt className="text-xs font-semibold uppercase tracking-wider text-slate-500">Categoria</dt><dd>{movement.expense_category_name}</dd></div>}
              {movement.reference_number && <div className="flex justify-between"><dt className="text-xs font-semibold uppercase tracking-wider text-slate-500">Referencia</dt><dd>{movement.reference_number}</dd></div>}
              {movement.notes && <div><dt className="text-xs font-semibold uppercase tracking-wider text-slate-500 mb-1">Notas</dt><dd>{movement.notes}</dd></div>}
              <div className="flex justify-between"><dt className="text-xs font-semibold uppercase tracking-wider text-slate-500">Creado</dt><dd>{formatDate(movement.created_at)}</dd></div>
            </dl>
          </CardContent>
        </Card>
      </div>

      {movement.status === "annulled" && (
        <Card className="shadow-sm border-red-200 bg-red-50">
          <CardContent className="pt-6">
            <dl className="space-y-2 text-sm">
              <div className="flex justify-between"><dt className="text-xs font-semibold uppercase tracking-wider text-red-600">Razon de anulacion</dt><dd className="text-red-800">{movement.annulled_reason}</dd></div>
              {movement.annulled_at && <div className="flex justify-between"><dt className="text-xs font-semibold uppercase tracking-wider text-red-600">Anulado el</dt><dd className="text-red-800">{formatDate(movement.annulled_at)}</dd></div>}
            </dl>
          </CardContent>
        </Card>
      )}

      <ConfirmDialog
        open={showAnnul}
        onOpenChange={setShowAnnul}
        title="Anular Movimiento"
        description="Ingrese la razon para anular este movimiento. Se revertiran los saldos afectados."
        confirmLabel="Anular"
        variant="destructive"
        onConfirm={handleAnnul}
        loading={annul.isPending}
        disabled={!annulReason.trim()}
      >
        <div className="py-2">
          <Label>Razon de anulacion *</Label>
          <Input value={annulReason} onChange={(e) => setAnnulReason(e.target.value)} placeholder="Ingrese la razon..." />
        </div>
      </ConfirmDialog>
    </div>
  );
}
