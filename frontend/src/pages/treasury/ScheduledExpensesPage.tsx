import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Plus } from "lucide-react";
import { usePermissions } from "@/hooks/usePermissions";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { PageHeader } from "@/components/shared/PageHeader";
import { EmptyState } from "@/components/shared/EmptyState";
import { useScheduledExpenses } from "@/hooks/useScheduledExpenses";
import { formatCurrency } from "@/utils/formatters";
import { ROUTES } from "@/utils/constants";
import type { ScheduledExpenseStatus } from "@/types/scheduled-expense";

const statusLabels: Record<ScheduledExpenseStatus, string> = {
  active: "Activo",
  completed: "Completado",
  cancelled: "Cancelado",
};

const statusColors: Record<ScheduledExpenseStatus, string> = {
  active: "bg-emerald-100 text-emerald-800",
  completed: "bg-blue-100 text-blue-800",
  cancelled: "bg-red-100 text-red-800",
};

export default function ScheduledExpensesPage() {
  const navigate = useNavigate();
  const { hasPermission } = usePermissions();
  const [statusFilter, setStatusFilter] = useState<string>("all");

  const filters = statusFilter !== "all" ? { status: statusFilter } : {};
  const { data, isLoading } = useScheduledExpenses(filters);
  const items = data?.items ?? [];

  return (
    <div className="space-y-6">
      <PageHeader title="Gastos Diferidos" description="Pagos grandes distribuidos en cuotas mensuales en P&L">
        <div className="flex gap-2">
          {hasPermission("treasury.manage_expenses") && (
            <Button onClick={() => navigate(ROUTES.TREASURY_SCHEDULED_NEW)} className="bg-emerald-600 hover:bg-emerald-700">
              <Plus className="h-4 w-4 mr-2" />Nuevo Gasto Diferido
            </Button>
          )}
        </div>
      </PageHeader>

      <div className="flex gap-3 items-center">
        <Select value={statusFilter} onValueChange={setStatusFilter}>
          <SelectTrigger className="w-48">
            <SelectValue placeholder="Filtrar por estado" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Todos</SelectItem>
            <SelectItem value="active">Activos</SelectItem>
            <SelectItem value="completed">Completados</SelectItem>
            <SelectItem value="cancelled">Cancelados</SelectItem>
          </SelectContent>
        </Select>
      </div>

      <Card className="shadow-sm">
        <CardContent className="p-0">
          {isLoading ? (
            <p className="text-sm text-slate-400 py-8 text-center">Cargando...</p>
          ) : items.length === 0 ? (
            <div className="p-6">
              <EmptyState
                title="Sin gastos diferidos"
                description="Crea un gasto diferido para distribuir pagos grandes en cuotas mensuales."
              />
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Nombre</TableHead>
                  <TableHead>Cuenta</TableHead>
                  <TableHead>Categoria</TableHead>
                  <TableHead className="text-right">Monto Total</TableHead>
                  <TableHead className="text-right">Cuota Mensual</TableHead>
                  <TableHead className="text-center">Progreso</TableHead>
                  <TableHead>Proxima Fecha</TableHead>
                  <TableHead>Estado</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {items.map((se) => (
                  <TableRow
                    key={se.id}
                    className="cursor-pointer hover:bg-slate-50"
                    onClick={() => navigate(`${ROUTES.TREASURY_SCHEDULED}/${se.id}`)}
                  >
                    <TableCell className="font-medium">{se.name}</TableCell>
                    <TableCell className="text-sm text-slate-500">{se.source_account_name}</TableCell>
                    <TableCell className="text-sm text-slate-600">{se.expense_category_name}</TableCell>
                    <TableCell className="text-right font-medium tabular-nums">{formatCurrency(se.total_amount)}</TableCell>
                    <TableCell className="text-right tabular-nums">{formatCurrency(se.monthly_amount)}</TableCell>
                    <TableCell className="text-center">
                      <div className="flex items-center justify-center gap-2">
                        <div className="w-20 bg-slate-100 rounded-full h-2">
                          <div
                            className="bg-emerald-500 h-2 rounded-full transition-all"
                            style={{ width: `${(se.applied_months / se.total_months) * 100}%` }}
                          />
                        </div>
                        <span className="text-xs text-slate-500 tabular-nums">
                          {se.applied_months}/{se.total_months}
                        </span>
                      </div>
                    </TableCell>
                    <TableCell className="text-sm text-slate-500">{se.next_application_date || "—"}</TableCell>
                    <TableCell>
                      <Badge variant="secondary" className={statusColors[se.status as ScheduledExpenseStatus]}>
                        {statusLabels[se.status as ScheduledExpenseStatus]}
                      </Badge>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
