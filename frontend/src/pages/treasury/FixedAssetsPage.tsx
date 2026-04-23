import { useState } from "react";
import { useNavigate, useSearchParams, useLocation } from "react-router-dom";
import { saveScroll, useScrollRestoration } from "@/hooks/useScrollRestoration";
import { Plus, Play } from "lucide-react";
import { usePermissions } from "@/hooks/usePermissions";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { PageHeader } from "@/components/shared/PageHeader";
import { EmptyState } from "@/components/shared/EmptyState";
import { ConfirmDialog } from "@/components/shared/ConfirmDialog";
import { useFixedAssets, useApplyPendingDepreciations } from "@/hooks/useFixedAssets";
import { formatCurrency } from "@/utils/formatters";
import { ROUTES } from "@/utils/constants";

const statusLabels: Record<string, string> = {
  active: "Activo",
  fully_depreciated: "Totalmente Depreciado",
  disposed: "Dado de Baja",
  cancelled: "Cancelado",
};

const statusColors: Record<string, string> = {
  active: "bg-emerald-100 text-emerald-800",
  fully_depreciated: "bg-blue-100 text-blue-800",
  disposed: "bg-red-100 text-red-800",
  cancelled: "bg-slate-100 text-slate-800",
};

export default function FixedAssetsPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const [searchParams, setSearchParams] = useSearchParams();
  const { hasPermission } = usePermissions();
  const [showApplyPending, setShowApplyPending] = useState(false);
  const applyPending = useApplyPendingDepreciations();

  const statusFilter = searchParams.get("status") || "all";
  const setStatusFilter = (v: string) => {
    setSearchParams(v === "all" ? {} : { status: v }, { replace: true });
  };

  const filters = statusFilter !== "all" ? { status: statusFilter } : {};
  const { data, isLoading } = useFixedAssets(filters);
  const items = data?.items ?? [];

  useScrollRestoration(!isLoading);

  return (
    <div className="space-y-6">
      <PageHeader title="Activos Fijos" description="Equipos y bienes con depreciacion mensual">
        <div className="flex gap-2">
          {hasPermission("treasury.manage_fixed_assets") && (
            <Button variant="outline" onClick={() => setShowApplyPending(true)}>
              <Play className="h-4 w-4 mr-2" />Aplicar Depreciaciones
            </Button>
          )}
          {hasPermission("treasury.manage_fixed_assets") && (
            <Button onClick={() => navigate(ROUTES.TREASURY_FIXED_ASSETS_NEW)} className="bg-emerald-600 hover:bg-emerald-700">
              <Plus className="h-4 w-4 mr-2" />Nuevo Activo
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
            <SelectItem value="fully_depreciated">Totalmente Depreciados</SelectItem>
            <SelectItem value="disposed">Dados de Baja</SelectItem>
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
                title="Sin activos fijos"
                description="Registra equipos y bienes para controlar su depreciacion mensual."
              />
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Codigo</TableHead>
                  <TableHead>Nombre</TableHead>
                  <TableHead className="text-right">Valor Original</TableHead>
                  <TableHead className="text-right">Valor Actual</TableHead>
                  <TableHead className="text-right">Deprec. Acum.</TableHead>
                  <TableHead className="text-center">Progreso</TableHead>
                  <TableHead>Estado</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {items.map((asset) => (
                  <TableRow
                    key={asset.id}
                    className="cursor-pointer hover:bg-slate-50"
                    onClick={() => { saveScroll(location.pathname + location.search); navigate(`${ROUTES.TREASURY_FIXED_ASSETS}/${asset.id}`); }}
                  >
                    <TableCell className="font-medium text-slate-500">{asset.asset_code || "—"}</TableCell>
                    <TableCell className="font-medium">{asset.name}</TableCell>
                    <TableCell className="text-right tabular-nums">{formatCurrency(asset.purchase_value)}</TableCell>
                    <TableCell className="text-right font-medium tabular-nums">{formatCurrency(asset.current_value)}</TableCell>
                    <TableCell className="text-right tabular-nums">{formatCurrency(asset.accumulated_depreciation)}</TableCell>
                    <TableCell className="text-center">
                      <div className="flex items-center justify-center gap-2">
                        <div className="w-20 bg-slate-100 rounded-full h-2">
                          <div
                            className="bg-emerald-500 h-2 rounded-full transition-all"
                            style={{ width: `${Math.min(asset.depreciation_progress, 100)}%` }}
                          />
                        </div>
                        <span className="text-xs text-slate-500 tabular-nums">
                          {asset.depreciation_progress.toFixed(0)}%
                        </span>
                      </div>
                    </TableCell>
                    <TableCell>
                      <Badge variant="secondary" className={statusColors[asset.status]}>
                        {statusLabels[asset.status]}
                      </Badge>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <ConfirmDialog
        open={showApplyPending}
        onOpenChange={setShowApplyPending}
        title="Aplicar Depreciaciones Pendientes"
        description="Se aplicara la depreciacion del mes actual a todos los activos activos que aun no la tengan. Esta accion no se puede deshacer."
        confirmLabel="Aplicar Depreciaciones"
        loading={applyPending.isPending}
        onConfirm={() => {
          applyPending.mutate(undefined, { onSuccess: () => setShowApplyPending(false) });
        }}
      />
    </div>
  );
}
