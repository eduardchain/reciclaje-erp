import { useState } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import { ArrowLeft, Play, XCircle, ExternalLink, Pencil } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { PageHeader } from "@/components/shared/PageHeader";
import { ConfirmDialog } from "@/components/shared/ConfirmDialog";
import { useFixedAsset, useDepreciateAsset, useDisposeAsset } from "@/hooks/useFixedAssets";
import { formatCurrency } from "@/utils/formatters";
import { ROUTES } from "@/utils/constants";
import type { FixedAssetStatus } from "@/types/fixed-asset";

const statusLabels: Record<FixedAssetStatus, string> = {
  active: "Activo",
  fully_depreciated: "Totalmente Depreciado",
  disposed: "Dado de Baja",
};

const statusColors: Record<FixedAssetStatus, string> = {
  active: "bg-emerald-100 text-emerald-800",
  fully_depreciated: "bg-blue-100 text-blue-800",
  disposed: "bg-red-100 text-red-800",
};

export default function FixedAssetDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { data: asset, isLoading } = useFixedAsset(id || "");
  const depreciate = useDepreciateAsset();
  const dispose = useDisposeAsset();
  const [showDepreciate, setShowDepreciate] = useState(false);
  const [showDispose, setShowDispose] = useState(false);
  const [disposeReason, setDisposeReason] = useState("");

  if (isLoading) return <p className="text-center py-12 text-slate-400">Cargando...</p>;
  if (!asset) return <p className="text-center py-12 text-slate-400">Activo fijo no encontrado</p>;

  const canDepreciate = asset.status === "active";
  const canDispose = asset.status !== "disposed";
  const progress = Math.min(asset.depreciation_progress, 100);
  const remaining = asset.current_value - asset.salvage_value;
  const nextDepreciationAmount = remaining <= asset.monthly_depreciation ? remaining : asset.monthly_depreciation;

  return (
    <div className="space-y-6">
      <PageHeader title={asset.name} description={asset.asset_code ? `Codigo: ${asset.asset_code}` : "Detalle de activo fijo"}>
        <Button variant="outline" onClick={() => navigate(ROUTES.TREASURY_FIXED_ASSETS)}>
          <ArrowLeft className="h-4 w-4 mr-2" />Volver
        </Button>
      </PageHeader>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card className="shadow-sm">
          <CardContent className="p-5">
            <p className="text-xs font-semibold uppercase tracking-wider text-slate-500 mb-1">Valor Original</p>
            <p className="text-2xl font-bold text-slate-900 tabular-nums">{formatCurrency(asset.purchase_value)}</p>
          </CardContent>
        </Card>
        <Card className="shadow-sm">
          <CardContent className="p-5">
            <p className="text-xs font-semibold uppercase tracking-wider text-slate-500 mb-1">Valor Actual</p>
            <p className="text-2xl font-bold text-emerald-600 tabular-nums">{formatCurrency(asset.current_value)}</p>
          </CardContent>
        </Card>
        <Card className="shadow-sm">
          <CardContent className="p-5">
            <p className="text-xs font-semibold uppercase tracking-wider text-slate-500 mb-1">Deprec. Acumulada</p>
            <p className="text-2xl font-bold text-slate-900 tabular-nums">{formatCurrency(asset.accumulated_depreciation)}</p>
          </CardContent>
        </Card>
        <Card className="shadow-sm">
          <CardContent className="p-5">
            <p className="text-xs font-semibold uppercase tracking-wider text-slate-500 mb-1">Cuota Mensual</p>
            <p className="text-2xl font-bold text-slate-900 tabular-nums">{formatCurrency(asset.monthly_depreciation)}</p>
          </CardContent>
        </Card>
      </div>

      {/* Progress bar */}
      <Card className="shadow-sm">
        <CardContent className="p-5">
          <div className="flex items-center justify-between mb-2">
            <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">Progreso de Depreciacion</p>
            <span className="text-sm font-medium tabular-nums">{progress.toFixed(1)}%</span>
          </div>
          <div className="w-full bg-slate-100 rounded-full h-3">
            <div
              className="bg-emerald-500 h-3 rounded-full transition-all"
              style={{ width: `${progress}%` }}
            />
          </div>
          <div className="flex justify-between mt-2 text-xs text-slate-400">
            <span>{formatCurrency(asset.accumulated_depreciation)} depreciado</span>
            <span>{asset.remaining_months} meses restantes</span>
          </div>
        </CardContent>
      </Card>

      {/* Info */}
      <Card className="shadow-sm">
        <CardHeader>
          <CardTitle className="text-sm font-semibold uppercase tracking-wider text-slate-500">Informacion</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
            <div>
              <span className="text-slate-400">Estado</span>
              <div className="mt-1">
                <Badge variant="secondary" className={statusColors[asset.status]}>
                  {statusLabels[asset.status]}
                </Badge>
              </div>
            </div>
            <div>
              <span className="text-slate-400">Tasa Mensual</span>
              <p className="font-medium mt-1 tabular-nums">{asset.depreciation_rate}%</p>
            </div>
            <div>
              <span className="text-slate-400">Vida Util</span>
              <p className="font-medium mt-1 tabular-nums">{asset.useful_life_months} meses</p>
            </div>
            <div>
              <span className="text-slate-400">Valor Residual</span>
              <p className="font-medium mt-1 tabular-nums">{formatCurrency(asset.salvage_value)}</p>
            </div>
            <div>
              <span className="text-slate-400">Fecha Compra</span>
              <p className="font-medium mt-1">{asset.purchase_date}</p>
            </div>
            <div>
              <span className="text-slate-400">Inicio Depreciacion</span>
              <p className="font-medium mt-1">{asset.depreciation_start_date}</p>
            </div>
            <div>
              <span className="text-slate-400">Categoria</span>
              <p className="font-medium mt-1">{asset.expense_category_name || "—"}</p>
            </div>
            <div>
              <span className="text-slate-400">Proveedor</span>
              <p className="font-medium mt-1">{asset.third_party_name || "—"}</p>
            </div>
            {asset.notes && (
              <div className="col-span-2">
                <span className="text-slate-400">Notas</span>
                <p className="font-medium mt-1">{asset.notes}</p>
              </div>
            )}
            {asset.disposal_reason && (
              <div className="col-span-2">
                <span className="text-slate-400">Razon de Baja</span>
                <p className="font-medium mt-1 text-red-600">{asset.disposal_reason}</p>
              </div>
            )}
            {asset.disposed_at && (
              <div>
                <span className="text-slate-400">Fecha de Baja</span>
                <p className="font-medium mt-1">{new Date(asset.disposed_at).toLocaleDateString("es-CO")}</p>
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Acciones */}
      <div className="flex gap-2">
          {asset.status !== "disposed" && (
            <Button variant="outline" onClick={() => navigate(`/treasury/fixed-assets/${asset.id}/edit`)}>
              <Pencil className="h-4 w-4 mr-2" />Editar
            </Button>
          )}
          {canDepreciate && (
            <Button onClick={() => setShowDepreciate(true)} className="bg-emerald-600 hover:bg-emerald-700">
              <Play className="h-4 w-4 mr-2" />Aplicar Depreciacion
            </Button>
          )}
          {canDispose && (
            <Button variant="outline" onClick={() => setShowDispose(true)} className="text-red-600 hover:text-red-700">
              <XCircle className="h-4 w-4 mr-2" />Dar de Baja
            </Button>
          )}
      </div>

      {/* Tabla de depreciaciones */}
      <Card className="shadow-sm">
        <CardHeader>
          <CardTitle className="text-sm font-semibold uppercase tracking-wider text-slate-500">
            Depreciaciones Aplicadas ({asset.depreciations?.length || 0})
          </CardTitle>
        </CardHeader>
        <CardContent>
          {(!asset.depreciations || asset.depreciations.length === 0) ? (
            <p className="text-sm text-slate-400 text-center py-4">Sin depreciaciones aplicadas aun</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>#</TableHead>
                  <TableHead>Periodo</TableHead>
                  <TableHead className="text-right">Monto</TableHead>
                  <TableHead className="text-right">Acumulado</TableHead>
                  <TableHead className="text-right">Valor Despues</TableHead>
                  <TableHead>Fecha</TableHead>
                  <TableHead>Movimiento</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {asset.depreciations.map((dep) => (
                  <TableRow key={dep.id}>
                    <TableCell className="font-medium">{dep.depreciation_number}</TableCell>
                    <TableCell className="text-sm">{dep.period}</TableCell>
                    <TableCell className="text-right tabular-nums">{formatCurrency(dep.amount)}</TableCell>
                    <TableCell className="text-right tabular-nums">{formatCurrency(dep.accumulated_after)}</TableCell>
                    <TableCell className="text-right tabular-nums">{formatCurrency(dep.current_value_after)}</TableCell>
                    <TableCell className="text-sm text-slate-500">
                      {new Date(dep.applied_at).toLocaleDateString("es-CO")}
                    </TableCell>
                    <TableCell>
                      <Link
                        to={`/treasury/${dep.money_movement_id}`}
                        className="text-emerald-600 hover:underline inline-flex items-center gap-1 text-sm"
                      >
                        Ver <ExternalLink className="h-3 w-3" />
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
        open={showDepreciate}
        onOpenChange={setShowDepreciate}
        title="Aplicar Depreciacion"
        description={`Se creará un movimiento de depreciación por ${formatCurrency(nextDepreciationAmount)} para el mes actual. Esta acción no se puede deshacer.`}
        confirmLabel="Aplicar Depreciacion"
        loading={depreciate.isPending}
        onConfirm={() => {
          depreciate.mutate(asset.id, { onSuccess: () => setShowDepreciate(false) });
        }}
      />
      <ConfirmDialog
        open={showDispose}
        onOpenChange={setShowDispose}
        title="Dar de Baja Activo"
        description={
          asset.current_value > asset.salvage_value
            ? `El activo tiene ${formatCurrency(asset.current_value - asset.salvage_value)} pendiente de depreciacion. Se aplicara depreciacion acelerada por ese monto.`
            : "Se marcara el activo como dado de baja."
        }
        confirmLabel="Dar de Baja"
        variant="destructive"
        loading={dispose.isPending}
        onConfirm={() => {
          if (!disposeReason.trim()) return;
          dispose.mutate({ id: asset.id, reason: disposeReason }, { onSuccess: () => setShowDispose(false) });
        }}
      >
        <div className="mt-3">
          <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Razon de Baja *</Label>
          <Input
            value={disposeReason}
            onChange={(e) => setDisposeReason(e.target.value)}
            placeholder="Ej: Equipo obsoleto, venta, daño irreparable"
          />
        </div>
      </ConfirmDialog>
    </div>
  );
}
