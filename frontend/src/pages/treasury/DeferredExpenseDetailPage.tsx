import { useState } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import { ArrowLeft, Play, XCircle, ExternalLink } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { PageHeader } from "@/components/shared/PageHeader";
import { ConfirmDialog } from "@/components/shared/ConfirmDialog";
import { useDeferredExpense, useApplyDeferredExpense, useCancelDeferredExpense } from "@/hooks/useDeferredExpenses";
import { formatCurrency } from "@/utils/formatters";
import { ROUTES } from "@/utils/constants";
import type { DeferredExpenseStatus } from "@/types/deferred-expense";

const statusLabels: Record<DeferredExpenseStatus, string> = {
  active: "Activo",
  completed: "Completado",
  cancelled: "Cancelado",
};

const statusColors: Record<DeferredExpenseStatus, string> = {
  active: "bg-emerald-100 text-emerald-800",
  completed: "bg-blue-100 text-blue-800",
  cancelled: "bg-red-100 text-red-800",
};

export default function DeferredExpenseDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { data: de, isLoading } = useDeferredExpense(id || "");
  const apply = useApplyDeferredExpense();
  const cancel = useCancelDeferredExpense();
  const [showApply, setShowApply] = useState(false);
  const [showCancel, setShowCancel] = useState(false);

  if (isLoading) return <p className="text-center py-12 text-slate-400">Cargando...</p>;
  if (!de) return <p className="text-center py-12 text-slate-400">Gasto programado no encontrado</p>;

  const canApply = de.status === "active" && de.applied_months < de.total_months;
  const canCancel = de.status === "active";
  const progress = (de.applied_months / de.total_months) * 100;

  return (
    <div className="space-y-6">
      <PageHeader title={de.name} description="Detalle de gasto programado">
        <Button variant="outline" onClick={() => navigate(ROUTES.TREASURY_DEFERRED)}>
          <ArrowLeft className="h-4 w-4 mr-2" />Volver
        </Button>
      </PageHeader>

      {/* Info general */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card className="shadow-sm">
          <CardContent className="p-5">
            <p className="text-xs font-semibold uppercase tracking-wider text-slate-500 mb-1">Monto Total</p>
            <p className="text-2xl font-bold text-slate-900 tabular-nums">{formatCurrency(de.total_amount)}</p>
          </CardContent>
        </Card>
        <Card className="shadow-sm">
          <CardContent className="p-5">
            <p className="text-xs font-semibold uppercase tracking-wider text-slate-500 mb-1">Restante</p>
            <p className="text-2xl font-bold text-slate-900 tabular-nums">{formatCurrency(de.remaining_amount)}</p>
          </CardContent>
        </Card>
        <Card className="shadow-sm">
          <CardContent className="p-5">
            <p className="text-xs font-semibold uppercase tracking-wider text-slate-500 mb-1">Siguiente Cuota</p>
            <p className="text-2xl font-bold text-emerald-600 tabular-nums">
              {de.next_amount > 0 ? formatCurrency(de.next_amount) : "—"}
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Detalles */}
      <Card className="shadow-sm">
        <CardHeader>
          <CardTitle className="text-sm font-semibold uppercase tracking-wider text-slate-500">Informacion</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
            <div>
              <span className="text-slate-400">Estado</span>
              <div className="mt-1">
                <Badge variant="secondary" className={statusColors[de.status as DeferredExpenseStatus]}>
                  {statusLabels[de.status as DeferredExpenseStatus]}
                </Badge>
              </div>
            </div>
            <div>
              <span className="text-slate-400">Progreso</span>
              <div className="flex items-center gap-2 mt-1">
                <div className="w-16 bg-slate-100 rounded-full h-2">
                  <div className="bg-emerald-500 h-2 rounded-full" style={{ width: `${progress}%` }} />
                </div>
                <span className="font-medium tabular-nums">{de.applied_months}/{de.total_months}</span>
              </div>
            </div>
            <div>
              <span className="text-slate-400">Cuota Mensual</span>
              <p className="font-medium mt-1 tabular-nums">{formatCurrency(de.monthly_amount)}</p>
            </div>
            <div>
              <span className="text-slate-400">Fecha Inicio</span>
              <p className="font-medium mt-1">{de.start_date}</p>
            </div>
            <div>
              <span className="text-slate-400">Tipo</span>
              <p className="font-medium mt-1">{de.expense_type === "expense" ? "Desde Cuenta" : "Desde Provision"}</p>
            </div>
            <div>
              <span className="text-slate-400">Categoria</span>
              <p className="font-medium mt-1">{de.expense_category_name}</p>
            </div>
            <div>
              <span className="text-slate-400">{de.expense_type === "expense" ? "Cuenta" : "Provision"}</span>
              <p className="font-medium mt-1">{de.account_name || de.provision_name}</p>
            </div>
            {de.description && (
              <div>
                <span className="text-slate-400">Descripcion</span>
                <p className="font-medium mt-1">{de.description}</p>
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Acciones */}
      {(canApply || canCancel) && (
        <div className="flex gap-2">
          {canApply && (
            <Button onClick={() => setShowApply(true)} className="bg-emerald-600 hover:bg-emerald-700">
              <Play className="h-4 w-4 mr-2" />Aplicar Cuota #{de.applied_months + 1}
            </Button>
          )}
          {canCancel && (
            <Button variant="outline" onClick={() => setShowCancel(true)} className="text-red-600 hover:text-red-700">
              <XCircle className="h-4 w-4 mr-2" />Cancelar Gasto Programado
            </Button>
          )}
        </div>
      )}

      {/* Tabla de applications */}
      <Card className="shadow-sm">
        <CardHeader>
          <CardTitle className="text-sm font-semibold uppercase tracking-wider text-slate-500">
            Cuotas Aplicadas ({de.applications?.length || 0})
          </CardTitle>
        </CardHeader>
        <CardContent>
          {(!de.applications || de.applications.length === 0) ? (
            <p className="text-sm text-slate-400 text-center py-4">Sin cuotas aplicadas aun</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>#</TableHead>
                  <TableHead className="text-right">Monto</TableHead>
                  <TableHead>Fecha Aplicacion</TableHead>
                  <TableHead>Movimiento</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {de.applications.map((app) => (
                  <TableRow key={app.id}>
                    <TableCell className="font-medium">Cuota {app.application_number}</TableCell>
                    <TableCell className="text-right tabular-nums">{formatCurrency(app.amount)}</TableCell>
                    <TableCell className="text-sm text-slate-500">
                      {new Date(app.applied_at).toLocaleDateString("es-CO")}
                    </TableCell>
                    <TableCell>
                      <Link
                        to={`/treasury/${app.money_movement_id}`}
                        className="text-emerald-600 hover:underline inline-flex items-center gap-1 text-sm"
                      >
                        Ver movimiento <ExternalLink className="h-3 w-3" />
                      </Link>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {/* Dialogs */}
      <ConfirmDialog
        open={showApply}
        onOpenChange={setShowApply}
        title="Aplicar Cuota"
        description={`Se creara un movimiento de ${formatCurrency(de.next_amount)} (cuota ${de.applied_months + 1} de ${de.total_months}). Esta accion no se puede deshacer.`}
        confirmLabel="Aplicar Cuota"
        onConfirm={() => {
          apply.mutate(de.id, { onSuccess: () => setShowApply(false) });
        }}
      />
      <ConfirmDialog
        open={showCancel}
        onOpenChange={setShowCancel}
        title="Cancelar Gasto Programado"
        description="Se cancelaran las cuotas pendientes. Las cuotas ya aplicadas (movimientos creados) permanecen activas y se pueden anular manualmente."
        confirmLabel="Cancelar Gasto"
        variant="destructive"
        onConfirm={() => {
          cancel.mutate(de.id, { onSuccess: () => setShowCancel(false) });
        }}
      />
    </div>
  );
}
