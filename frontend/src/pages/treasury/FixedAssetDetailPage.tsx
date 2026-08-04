import { useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { ArrowLeft, Play, XCircle, Pencil, TrendingUp, HandCoins } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { PageHeader } from "@/components/shared/PageHeader";
import { ConfirmDialog } from "@/components/shared/ConfirmDialog";
import { RevalueAssetModal } from "@/components/treasury/RevalueAssetModal";
import { SellAssetModal } from "@/components/treasury/SellAssetModal";
import { useFixedAsset, useDepreciateAsset, useDisposeAsset, useCancelFixedAsset, useAnnulRevaluation, useAnnulAssetSale } from "@/hooks/useFixedAssets";
import { formatCurrency } from "@/utils/formatters";
import { ROUTES } from "@/utils/constants";
import { MoneyMovementLink } from "@/components/shared/EntityLink";
import type { AssetRevaluation } from "@/types/fixed-asset";

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

export default function FixedAssetDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { data: asset, isLoading } = useFixedAsset(id || "");
  const depreciate = useDepreciateAsset();
  const dispose = useDisposeAsset();
  const cancelAsset = useCancelFixedAsset();
  const annulRevaluation = useAnnulRevaluation();
  const annulSale = useAnnulAssetSale();
  const [showDepreciate, setShowDepreciate] = useState(false);
  const [showDispose, setShowDispose] = useState(false);
  const [showCancel, setShowCancel] = useState(false);
  const [showRevalue, setShowRevalue] = useState(false);
  const [showSell, setShowSell] = useState(false);
  const [showAnnulSale, setShowAnnulSale] = useState(false);
  const [annulSaleReason, setAnnulSaleReason] = useState("");
  const [disposeReason, setDisposeReason] = useState("");
  const [annulTarget, setAnnulTarget] = useState<AssetRevaluation | null>(null);
  const [annulReason, setAnnulReason] = useState("");

  if (isLoading) return <p className="text-center py-12 text-slate-400">Cargando...</p>;
  if (!asset) return <p className="text-center py-12 text-slate-400">Activo fijo no encontrado</p>;

  const canDepreciate = asset.status === "active";
  const canDispose = !["disposed", "cancelled"].includes(asset.status);
  const canCancel = ["active", "fully_depreciated"].includes(asset.status);
  const canRevalue = ["active", "fully_depreciated"].includes(asset.status);
  const canSell = ["active", "fully_depreciated"].includes(asset.status);
  // Venta vigente = MM confirmado (tras anular, sale_* quedan como rastro no vigente)
  const isSold = asset.status === "disposed" && asset.sale_active;
  const revaluations = asset.revaluations ?? [];
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
            {asset.revalued_total !== 0 && (
              <p className="text-xs text-indigo-600 mt-1 tabular-nums">
                incluye {asset.revalued_total > 0 ? "+" : ""}{formatCurrency(asset.revalued_total)} revalorizado
              </p>
            )}
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
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4 text-sm">
            <div>
              <span className="text-slate-400">Estado</span>
              <div className="mt-1">
                <Badge
                  variant="secondary"
                  className={isSold ? "bg-indigo-100 text-indigo-800" : statusColors[asset.status]}
                >
                  {isSold ? "Vendido" : statusLabels[asset.status]}
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
      <div className="flex flex-wrap gap-2">
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
          {canRevalue && (
            <Button variant="outline" onClick={() => setShowRevalue(true)} className="text-indigo-600 hover:text-indigo-700">
              <TrendingUp className="h-4 w-4 mr-2" />Revalorizar
            </Button>
          )}
          {canSell && (
            <Button variant="outline" onClick={() => setShowSell(true)} className="text-emerald-700 hover:text-emerald-800">
              <HandCoins className="h-4 w-4 mr-2" />Vender
            </Button>
          )}
          {canDispose && (
            <Button variant="outline" onClick={() => setShowDispose(true)} className="text-red-600 hover:text-red-700">
              <XCircle className="h-4 w-4 mr-2" />Dar de Baja
            </Button>
          )}
          {canCancel && (
            <Button variant="outline" onClick={() => setShowCancel(true)} className="text-slate-600 hover:text-slate-700">
              <XCircle className="h-4 w-4 mr-2" />Cancelar Activo
            </Button>
          )}
      </div>

      {/* Venta vigente (solo si el MM enlazado esta confirmado) */}
      {isSold && (
        <Card className="shadow-sm border-indigo-200">
          <CardHeader>
            <CardTitle className="text-sm font-semibold uppercase tracking-wider text-indigo-600">
              Venta
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4 text-sm">
              <div>
                <span className="text-slate-400">Precio de venta</span>
                <p className="font-medium mt-1 tabular-nums">{formatCurrency(asset.sale_price ?? 0)}</p>
              </div>
              <div>
                <span className="text-slate-400">Valor en libros al vender</span>
                <p className="font-medium mt-1 tabular-nums">{formatCurrency(asset.current_value)}</p>
              </div>
              <div>
                <span className="text-slate-400">{(asset.sale_gain ?? 0) >= 0 ? "Ganancia" : "Pérdida"}</span>
                <p className={`font-semibold mt-1 tabular-nums ${(asset.sale_gain ?? 0) >= 0 ? "text-emerald-600" : "text-red-600"}`}>
                  {formatCurrency(Math.abs(asset.sale_gain ?? 0))}
                </p>
              </div>
              <div>
                <span className="text-slate-400">Movimiento</span>
                <p className="mt-1">
                  {asset.sale_movement_id && (
                    <MoneyMovementLink id={asset.sale_movement_id}>Ver movimiento</MoneyMovementLink>
                  )}
                </p>
              </div>
            </div>
            <div className="mt-4">
              <Button
                variant="outline"
                size="sm"
                className="text-red-600 hover:text-red-700"
                onClick={() => { setAnnulSaleReason(""); setShowAnnulSale(true); }}
              >
                <XCircle className="h-4 w-4 mr-2" />Anular Venta
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

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
            <div className="overflow-x-auto -mx-3 sm:mx-0">
            <Table className="min-w-[720px]">
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
                      <MoneyMovementLink id={dep.money_movement_id}>Ver</MoneyMovementLink>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Tabla de revalorizaciones */}
      {revaluations.length > 0 && (
        <Card className="shadow-sm">
          <CardHeader>
            <CardTitle className="text-sm font-semibold uppercase tracking-wider text-slate-500">
              Revalorizaciones ({revaluations.length})
            </CardTitle>
          </CardHeader>
          <CardContent>
            {/* Desktop */}
            <div className="hidden md:block overflow-x-auto">
              <Table className="min-w-[820px]">
                <TableHeader>
                  <TableRow>
                    <TableHead>Tipo</TableHead>
                    <TableHead className="text-right">Monto</TableHead>
                    <TableHead className="text-right">Valor Despues</TableHead>
                    <TableHead className="text-right">Cuota Despues</TableHead>
                    <TableHead>Meses +</TableHead>
                    <TableHead>Fecha</TableHead>
                    <TableHead>Motivo</TableHead>
                    <TableHead>Movimiento</TableHead>
                    <TableHead></TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {revaluations.map((rev) => (
                    <TableRow key={rev.id} className={rev.is_active ? "" : "opacity-50"}>
                      <TableCell>
                        <Badge variant="secondary" className={rev.revaluation_type === "increase" ? "bg-emerald-100 text-emerald-800" : "bg-amber-100 text-amber-800"}>
                          {rev.revaluation_type === "increase" ? "Alza" : "Baja"}
                        </Badge>
                        {!rev.is_active && (
                          <Badge variant="secondary" className="ml-1 bg-slate-100 text-slate-500">Anulada</Badge>
                        )}
                      </TableCell>
                      <TableCell className="text-right tabular-nums">
                        {rev.revaluation_type === "increase" ? "+" : "−"}{formatCurrency(rev.amount)}
                      </TableCell>
                      <TableCell className="text-right tabular-nums">{formatCurrency(rev.value_after)}</TableCell>
                      <TableCell className="text-right tabular-nums">{formatCurrency(rev.monthly_after)}</TableCell>
                      <TableCell className="tabular-nums">{rev.months_extended || "—"}</TableCell>
                      <TableCell className="text-sm text-slate-500">
                        {new Date(rev.applied_at).toLocaleDateString("es-CO")}
                      </TableCell>
                      <TableCell className="text-sm max-w-[160px] truncate" title={rev.reason ?? undefined}>
                        {rev.reason || "—"}
                      </TableCell>
                      <TableCell>
                        <MoneyMovementLink id={rev.money_movement_id}>Ver</MoneyMovementLink>
                      </TableCell>
                      <TableCell>
                        {rev.is_active && canRevalue && (
                          <Button
                            variant="ghost"
                            size="sm"
                            className="text-red-600 hover:text-red-700 h-7 px-2"
                            onClick={() => { setAnnulTarget(rev); setAnnulReason(""); }}
                          >
                            Anular
                          </Button>
                        )}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
            {/* Mobile cards */}
            <div className="md:hidden space-y-2">
              {revaluations.map((rev) => (
                <div key={rev.id} className={`rounded-lg border border-slate-200 p-3 text-sm space-y-1 ${rev.is_active ? "" : "opacity-50"}`}>
                  <div className="flex justify-between gap-3">
                    <span>
                      <Badge variant="secondary" className={rev.revaluation_type === "increase" ? "bg-emerald-100 text-emerald-800" : "bg-amber-100 text-amber-800"}>
                        {rev.revaluation_type === "increase" ? "Alza" : "Baja"}
                      </Badge>
                      {!rev.is_active && (
                        <Badge variant="secondary" className="ml-1 bg-slate-100 text-slate-500">Anulada</Badge>
                      )}
                    </span>
                    <span className="font-medium tabular-nums">
                      {rev.revaluation_type === "increase" ? "+" : "−"}{formatCurrency(rev.amount)}
                    </span>
                  </div>
                  <div className="flex justify-between gap-3 text-slate-500">
                    <span>Valor → {formatCurrency(rev.value_after)}</span>
                    <span>{new Date(rev.applied_at).toLocaleDateString("es-CO")}</span>
                  </div>
                  <div className="flex justify-between gap-3 items-center">
                    <MoneyMovementLink id={rev.money_movement_id}>Ver movimiento</MoneyMovementLink>
                    {rev.is_active && canRevalue && (
                      <Button
                        variant="ghost"
                        size="sm"
                        className="text-red-600 hover:text-red-700 h-7 px-2"
                        onClick={() => { setAnnulTarget(rev); setAnnulReason(""); }}
                      >
                        Anular
                      </Button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Dialogs */}
      <RevalueAssetModal open={showRevalue} onOpenChange={setShowRevalue} asset={asset} />
      <SellAssetModal open={showSell} onOpenChange={setShowSell} asset={asset} />
      <ConfirmDialog
        open={showAnnulSale}
        onOpenChange={setShowAnnulSale}
        title="Anular Venta"
        description={`Se revertirá la contrapartida (${formatCurrency(asset.sale_price ?? 0)} devueltos por la cuenta o el tercero), la ganancia/pérdida sale del Estado de Resultados y el activo vuelve a su estado anterior.`}
        confirmLabel="Anular Venta"
        variant="destructive"
        loading={annulSale.isPending}
        onConfirm={() => {
          if (!annulSaleReason.trim()) return;
          annulSale.mutate(
            { id: asset.id, reason: annulSaleReason },
            { onSuccess: () => setShowAnnulSale(false) },
          );
        }}
      >
        <div className="mt-3">
          <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Razón *</Label>
          <Input
            value={annulSaleReason}
            onChange={(e) => setAnnulSaleReason(e.target.value)}
            placeholder="Ej: Error de captura, la venta no se concretó"
          />
        </div>
      </ConfirmDialog>
      <ConfirmDialog
        open={annulTarget !== null}
        onOpenChange={(open) => { if (!open) setAnnulTarget(null); }}
        title="Anular Revalorización"
        description={
          annulTarget
            ? `Se revertirá exactamente el efecto: valor ${formatCurrency(annulTarget.value_after)} → ${formatCurrency(annulTarget.value_before)}, cuota ${formatCurrency(annulTarget.monthly_after)} → ${formatCurrency(annulTarget.monthly_before)}, y la cuenta o tercero recupera el saldo. Solo se puede anular el evento más reciente del activo.`
            : ""
        }
        confirmLabel="Anular Revalorización"
        variant="destructive"
        loading={annulRevaluation.isPending}
        onConfirm={() => {
          if (!annulTarget || !annulReason.trim()) return;
          annulRevaluation.mutate(
            { id: asset.id, revaluationId: annulTarget.id, reason: annulReason },
            { onSuccess: () => setAnnulTarget(null) },
          );
        }}
      >
        <div className="mt-3">
          <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Razón *</Label>
          <Input
            value={annulReason}
            onChange={(e) => setAnnulReason(e.target.value)}
            placeholder="Ej: Error de captura, monto incorrecto"
          />
        </div>
      </ConfirmDialog>
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
      <ConfirmDialog
        open={showCancel}
        onOpenChange={setShowCancel}
        title="Cancelar Activo Fijo"
        description={`Esto revertira el pago de ${formatCurrency(asset.purchase_value)}${asset.depreciations && asset.depreciations.length > 0 ? ` y las ${asset.depreciations.length} depreciacion(es) aplicadas` : ""}. La cuenta o proveedor recuperara el saldo. Esta accion no se puede deshacer.`}
        confirmLabel="Cancelar Activo"
        variant="destructive"
        loading={cancelAsset.isPending}
        onConfirm={() => {
          cancelAsset.mutate(asset.id, { onSuccess: () => setShowCancel(false) });
        }}
      />
    </div>
  );
}
