import { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { ArrowLeft } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { PageHeader } from "@/components/shared/PageHeader";
import { EntitySelect } from "@/components/shared/EntitySelect";
import { MoneyInput } from "@/components/shared/MoneyInput";
import { useFixedAsset, useUpdateFixedAsset } from "@/hooks/useFixedAssets";
import { useExpenseCategories } from "@/hooks/useMasterData";
import { formatCurrency } from "@/utils/formatters";

export default function FixedAssetEditPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { data: asset, isLoading } = useFixedAsset(id || "");
  const update = useUpdateFixedAsset();
  const { data: categoriesData } = useExpenseCategories();
  const categories = categoriesData?.items ?? [];

  const [name, setName] = useState("");
  const [assetCode, setAssetCode] = useState("");
  const [purchaseValue, setPurchaseValue] = useState(0);
  const [salvageValue, setSalvageValue] = useState(0);
  const [depreciationRate, setDepreciationRate] = useState(0);
  const [categoryId, setCategoryId] = useState("");
  const [notes, setNotes] = useState("");

  const hasDepreciations = (asset?.depreciations?.length ?? 0) > 0;

  useEffect(() => {
    if (asset) {
      setName(asset.name);
      setAssetCode(asset.asset_code || "");
      setPurchaseValue(asset.purchase_value);
      setSalvageValue(asset.salvage_value);
      setDepreciationRate(asset.depreciation_rate);
      setCategoryId(asset.expense_category_id);
      setNotes(asset.notes || "");
    }
  }, [asset]);

  if (isLoading) return <p className="text-center py-12 text-slate-400">Cargando...</p>;
  if (!asset) return <p className="text-center py-12 text-slate-400">Activo fijo no encontrado</p>;

  // Calculos en vivo (solo si campos financieros editables)
  const monthlyDepreciation = purchaseValue > 0 && depreciationRate > 0
    ? Math.round(purchaseValue * (depreciationRate / 100) * 100) / 100
    : 0;
  const depreciable = purchaseValue - salvageValue;
  const usefulLifeMonths = monthlyDepreciation > 0 && depreciable > 0
    ? Math.ceil(depreciable / monthlyDepreciation)
    : 0;

  const canSubmit =
    name.trim() !== "" &&
    categoryId !== "" &&
    (!hasDepreciations || true) &&
    (hasDepreciations || (purchaseValue > 0 && depreciationRate > 0 && purchaseValue > salvageValue)) &&
    !update.isPending;

  const handleSubmit = () => {
    const payload: Record<string, unknown> = {
      name,
      asset_code: assetCode || null,
      notes: notes || null,
      expense_category_id: categoryId,
    };
    if (!hasDepreciations) {
      payload.purchase_value = purchaseValue;
      payload.salvage_value = salvageValue;
      payload.depreciation_rate = depreciationRate;
    }
    update.mutate(
      { id: asset.id, data: payload },
      { onSuccess: () => navigate(`/treasury/fixed-assets/${asset.id}`) },
    );
  };

  return (
    <div className="space-y-6">
      <PageHeader title="Editar Activo Fijo" description={asset.name}>
        <Button variant="outline" onClick={() => navigate(`/treasury/fixed-assets/${asset.id}`)}>
          <ArrowLeft className="h-4 w-4 mr-2" />Volver
        </Button>
      </PageHeader>

      {hasDepreciations && (
        <Card className="border-amber-200 bg-amber-50 shadow-sm">
          <CardContent className="p-4">
            <p className="text-sm text-amber-800">
              Este activo ya tiene depreciaciones aplicadas. Solo se pueden editar nombre, codigo, categoria y notas.
              Los campos financieros (valor, tasa, valor residual) estan bloqueados.
            </p>
          </CardContent>
        </Card>
      )}

      <Card className="shadow-sm">
        <CardHeader>
          <CardTitle className="text-sm font-semibold uppercase tracking-wider text-slate-500">Datos del Activo</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="md:col-span-2">
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Nombre *</Label>
              <Input value={name} onChange={(e) => setName(e.target.value)} />
            </div>

            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Codigo de Activo</Label>
              <Input value={assetCode} onChange={(e) => setAssetCode(e.target.value)} />
            </div>

            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Categoria de Gasto *</Label>
              <EntitySelect
                value={categoryId}
                onChange={setCategoryId}
                options={categories.map((c) => ({ id: c.id, label: c.name }))}
                placeholder="Seleccionar categoria..."
              />
            </div>

            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Valor de Compra *</Label>
              <MoneyInput value={purchaseValue} onChange={setPurchaseValue} disabled={hasDepreciations} />
            </div>

            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Valor Residual</Label>
              <MoneyInput value={salvageValue} onChange={setSalvageValue} disabled={hasDepreciations} />
            </div>

            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Tasa Depreciacion Mensual (%)</Label>
              <Input
                type="number"
                min={0.01}
                max={100}
                step={0.01}
                value={depreciationRate || ""}
                onChange={(e) => setDepreciationRate(parseFloat(e.target.value) || 0)}
                disabled={hasDepreciations}
              />
            </div>

            <div className="md:col-span-2">
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Notas</Label>
              <Input value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="Observaciones adicionales (opcional)" />
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Preview (solo si campos financieros editables) */}
      {!hasDepreciations && purchaseValue > 0 && depreciationRate > 0 && (
        <Card className="shadow-sm border-t-[3px] border-t-emerald-500">
          <CardContent className="p-5">
            <p className="text-xs font-semibold uppercase tracking-wider text-slate-500 mb-3">Vista Previa Depreciacion</p>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div>
                <p className="text-xs text-slate-400">Cuota Mensual</p>
                <p className="text-lg font-bold text-slate-900 tabular-nums">{formatCurrency(monthlyDepreciation)}</p>
              </div>
              <div>
                <p className="text-xs text-slate-400">Vida Util</p>
                <p className="text-lg font-bold text-slate-900 tabular-nums">{usefulLifeMonths} meses</p>
              </div>
              <div>
                <p className="text-xs text-slate-400">Valor Depreciable</p>
                <p className="text-lg font-bold text-slate-900 tabular-nums">{formatCurrency(depreciable)}</p>
              </div>
              <div>
                <p className="text-xs text-slate-400">Valor Residual</p>
                <p className="text-lg font-bold text-slate-900 tabular-nums">{formatCurrency(salvageValue)}</p>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      <div className="sticky bottom-0 bg-white/95 backdrop-blur-sm border-t border-slate-100 py-4 -mx-6 px-6 mt-6">
        <div className="flex justify-end gap-2">
          <Button variant="outline" onClick={() => navigate(`/treasury/fixed-assets/${asset.id}`)}>Cancelar</Button>
          <Button
            onClick={handleSubmit}
            disabled={!canSubmit}
            className="bg-emerald-600 hover:bg-emerald-700"
          >
            {update.isPending ? "Guardando..." : "Guardar Cambios"}
          </Button>
        </div>
      </div>
    </div>
  );
}
