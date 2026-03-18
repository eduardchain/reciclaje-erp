import { useState, useRef } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { ArrowLeft, XCircle, Paperclip, Eye, Trash2, Upload, Pencil } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { PageHeader } from "@/components/shared/PageHeader";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { ConfirmDialog } from "@/components/shared/ConfirmDialog";
import { useMoneyMovement, useAnnulMovement, useUpdateClassification, useUploadEvidence, useDeleteEvidence } from "@/hooks/useMoneyMovements";
import { usePermissions } from "@/hooks/usePermissions";
import { EditClassificationModal } from "@/components/treasury/EditClassificationModal";
import { formatCurrency, formatDate } from "@/utils/formatters";
import { ROUTES } from "@/utils/constants";
import apiClient from "@/services/api";

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
  provision_deposit: "Deposito a Provision",
  provision_expense: "Gasto desde Provision",
  advance_payment: "Anticipo a Proveedor",
  advance_collection: "Anticipo de Cliente",
  asset_payment: "Pago Activo Fijo",
  asset_purchase: "Compra Activo (Crédito)",
  expense_accrual: "Gasto Causado (Pasivo)",
  deferred_funding: "Pago Gasto Diferido",
  deferred_expense: "Cuota Gasto Diferido",
  commission_accrual: "Comisión Causada",
  depreciation_expense: "Depreciación Activo",
  profit_distribution: "Repartición Utilidades",
};

const EDITABLE_EXPENSE_TYPES = ["expense", "expense_accrual", "provision_expense", "deferred_expense", "depreciation_expense"];

const statusBorderMap: Record<string, string> = {
  confirmed: "border-t-[3px] border-t-emerald-400",
  annulled: "border-t-[3px] border-t-rose-400",
};

export default function MovementDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { data: movement, isLoading } = useMoneyMovement(id!);
  const annul = useAnnulMovement();
  const updateClassification = useUpdateClassification();
  const uploadEvidence = useUploadEvidence();
  const deleteEvidence = useDeleteEvidence();
  const { hasPermission } = usePermissions();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [showAnnul, setShowAnnul] = useState(false);
  const [annulReason, setAnnulReason] = useState("");
  const [showDeleteEvidence, setShowDeleteEvidence] = useState(false);
  const [showEditClassification, setShowEditClassification] = useState(false);

  if (isLoading) return <div className="space-y-4"><Skeleton className="h-8 w-64" /><Skeleton className="h-64 w-full" /></div>;
  if (!movement) return <div className="text-center py-12 text-slate-500">Movimiento no encontrado</div>;

  const handleAnnul = () => {
    if (!id || !annulReason) return;
    annul.mutate(
      { id, data: { reason: annulReason } },
      { onSuccess: () => { setShowAnnul(false); setAnnulReason(""); } },
    );
  };

  const handleViewEvidence = async () => {
    if (!id) return;
    const response = await apiClient.get(`/api/v1/money-movements/${id}/evidence`, { responseType: "blob" });
    const blob = new Blob([response.data], { type: response.headers["content-type"] });
    const url = URL.createObjectURL(blob);
    window.open(url, "_blank");
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || !id) return;
    uploadEvidence.mutate({ id, file });
    e.target.value = "";
  };

  const handleDeleteEvidence = () => {
    if (!id) return;
    deleteEvidence.mutate(id, { onSuccess: () => setShowDeleteEvidence(false) });
  };

  return (
    <div className="space-y-6">
      <PageHeader title={`Movimiento #${movement.movement_number}`} description={typeLabels[movement.movement_type] ?? movement.movement_type}>
        <div className="flex items-center gap-2">
          {movement.status === "confirmed" && EDITABLE_EXPENSE_TYPES.includes(movement.movement_type) && hasPermission("treasury.edit_classification") && (
            <Button variant="outline" onClick={() => setShowEditClassification(true)}>
              <Pencil className="h-4 w-4 mr-2" />Editar Clasificacion
            </Button>
          )}
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
              <div className="flex justify-between"><dt className="text-xs font-semibold uppercase tracking-wider text-slate-500">Cuenta</dt><dd>{movement.account_name ?? "N/A (provision)"}</dd></div>
              {movement.third_party_name && <div className="flex justify-between"><dt className="text-xs font-semibold uppercase tracking-wider text-slate-500">Tercero</dt><dd>{movement.third_party_name}</dd></div>}
              {movement.expense_category_name && <div className="flex justify-between"><dt className="text-xs font-semibold uppercase tracking-wider text-slate-500">Categoria</dt><dd>{movement.expense_category_name}</dd></div>}
              {EDITABLE_EXPENSE_TYPES.includes(movement.movement_type) && (
                <div className="flex justify-between"><dt className="text-xs font-semibold uppercase tracking-wider text-slate-500">Unidad de Negocio</dt><dd>{movement.business_unit_name ? movement.business_unit_name : movement.applicable_business_unit_names?.length ? movement.applicable_business_unit_names.join(", ") : "General (todas)"}</dd></div>
              )}
              {movement.reference_number && <div className="flex justify-between"><dt className="text-xs font-semibold uppercase tracking-wider text-slate-500">Referencia</dt><dd>{movement.reference_number}</dd></div>}
              {movement.notes && <div><dt className="text-xs font-semibold uppercase tracking-wider text-slate-500 mb-1">Notas</dt><dd>{movement.notes}</dd></div>}
              <div className="flex justify-between"><dt className="text-xs font-semibold uppercase tracking-wider text-slate-500">Creado</dt><dd>{formatDate(movement.created_at)}</dd></div>
            </dl>
          </CardContent>
        </Card>
      </div>

      {/* Comprobante */}
      <Card className="shadow-sm">
        <CardContent className="pt-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Paperclip className="h-4 w-4 text-slate-400" />
              <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">Comprobante</span>
            </div>
            {movement.evidence_url ? (
              <div className="flex items-center gap-2">
                <Button variant="outline" size="sm" onClick={handleViewEvidence}>
                  <Eye className="h-4 w-4 mr-1" />Ver
                </Button>
                {movement.status === "confirmed" && (
                  <>
                    <Button variant="outline" size="sm" onClick={() => fileInputRef.current?.click()} disabled={uploadEvidence.isPending}>
                      <Upload className="h-4 w-4 mr-1" />{uploadEvidence.isPending ? "Subiendo..." : "Reemplazar"}
                    </Button>
                    <Button variant="outline" size="sm" onClick={() => setShowDeleteEvidence(true)} className="text-red-600 border-red-200 hover:bg-red-50" disabled={deleteEvidence.isPending}>
                      <Trash2 className="h-4 w-4 mr-1" />{deleteEvidence.isPending ? "Eliminando..." : "Eliminar"}
                    </Button>
                  </>
                )}
              </div>
            ) : (
              <div>
                {movement.status === "confirmed" ? (
                  <Button variant="outline" size="sm" onClick={() => fileInputRef.current?.click()} disabled={uploadEvidence.isPending}>
                    <Upload className="h-4 w-4 mr-1" />{uploadEvidence.isPending ? "Subiendo..." : "Agregar Comprobante"}
                  </Button>
                ) : (
                  <span className="text-sm text-slate-400">Sin comprobante</span>
                )}
              </div>
            )}
          </div>
          <input ref={fileInputRef} type="file" accept="image/*,.pdf" className="hidden" onChange={handleFileSelect} />
        </CardContent>
      </Card>

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

      <ConfirmDialog
        open={showDeleteEvidence}
        onOpenChange={setShowDeleteEvidence}
        title="Eliminar Comprobante"
        description="Se eliminara el comprobante adjunto de este movimiento. Esta accion no se puede deshacer."
        confirmLabel="Eliminar"
        variant="destructive"
        onConfirm={handleDeleteEvidence}
        loading={deleteEvidence.isPending}
      />

      {movement && (
        <EditClassificationModal
          open={showEditClassification}
          onOpenChange={setShowEditClassification}
          movement={movement}
          onSave={(data) => updateClassification.mutate(
            { id: id!, data },
            { onSuccess: () => setShowEditClassification(false) },
          )}
          loading={updateClassification.isPending}
        />
      )}
    </div>
  );
}
