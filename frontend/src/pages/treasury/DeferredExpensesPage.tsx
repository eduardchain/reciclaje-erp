import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { PageHeader } from "@/components/shared/PageHeader";
import { EmptyState } from "@/components/shared/EmptyState";
import { useDeferredExpenses } from "@/hooks/useDeferredExpenses";
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

export default function DeferredExpensesPage() {
  const navigate = useNavigate();
  const [statusFilter, setStatusFilter] = useState<string>("all");

  const filters = statusFilter !== "all" ? { status: statusFilter } : {};
  const { data, isLoading } = useDeferredExpenses(filters);
  const items = data?.items ?? [];

  return (
    <div className="space-y-6">
      <PageHeader title="Gastos Programados" description="Gastos grandes distribuidos en cuotas mensuales">
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => navigate(ROUTES.TREASURY)}>
            Volver a Tesoreria
          </Button>
          <Button onClick={() => navigate(ROUTES.TREASURY_DEFERRED_NEW)} className="bg-emerald-600 hover:bg-emerald-700">
            <Plus className="h-4 w-4 mr-2" />Nuevo Gasto Programado
          </Button>
        </div>
      </PageHeader>

      {/* Filtro por estado */}
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
                title="Sin gastos programados"
                description="Crea un gasto programado para distribuir gastos grandes en cuotas mensuales."
              />
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Nombre</TableHead>
                  <TableHead>Tipo</TableHead>
                  <TableHead>Categoria</TableHead>
                  <TableHead className="text-right">Monto Total</TableHead>
                  <TableHead className="text-right">Cuota Mensual</TableHead>
                  <TableHead className="text-center">Progreso</TableHead>
                  <TableHead>Estado</TableHead>
                  <TableHead>Inicio</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {items.map((de) => (
                  <TableRow
                    key={de.id}
                    className="cursor-pointer hover:bg-slate-50"
                    onClick={() => navigate(`${ROUTES.TREASURY_DEFERRED}/${de.id}`)}
                  >
                    <TableCell className="font-medium">{de.name}</TableCell>
                    <TableCell>
                      <span className="text-xs text-slate-500">
                        {de.expense_type === "expense" ? "Cuenta" : "Provision"}
                      </span>
                    </TableCell>
                    <TableCell className="text-sm text-slate-600">{de.expense_category_name}</TableCell>
                    <TableCell className="text-right font-medium tabular-nums">{formatCurrency(de.total_amount)}</TableCell>
                    <TableCell className="text-right tabular-nums">{formatCurrency(de.monthly_amount)}</TableCell>
                    <TableCell className="text-center">
                      <div className="flex items-center justify-center gap-2">
                        <div className="w-20 bg-slate-100 rounded-full h-2">
                          <div
                            className="bg-emerald-500 h-2 rounded-full transition-all"
                            style={{ width: `${(de.applied_months / de.total_months) * 100}%` }}
                          />
                        </div>
                        <span className="text-xs text-slate-500 tabular-nums">
                          {de.applied_months}/{de.total_months}
                        </span>
                      </div>
                    </TableCell>
                    <TableCell>
                      <Badge variant="secondary" className={statusColors[de.status as DeferredExpenseStatus]}>
                        {statusLabels[de.status as DeferredExpenseStatus]}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-sm text-slate-500">{de.start_date}</TableCell>
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
