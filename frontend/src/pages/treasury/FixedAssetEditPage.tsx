import { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { ArrowLeft, AlertTriangle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { PageHeader } from "@/components/shared/PageHeader";
import { EntitySelect } from "@/components/shared/EntitySelect";
import { MoneyInput } from "@/components/shared/MoneyInput";
import { useFixedAsset, useUpdateFixedAsset } from "@/hooks/useFixedAssets";
import { useExpenseCategoriesFlat } from "@/hooks/useMasterData";
import { formatCurrency } from "@/utils/formatters";

export default function FixedAssetEditPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { data: asset, isLoading } = useFixedAsset(id || "");
  const update = useUpdateFixedAsset();
  const { data: categoriesData } = useExpenseCategoriesFlat();
  const categories = categoriesData?.items ?? [];

  const [name, setName] = useState("");
  const [assetCode, setAssetCode] = useState("");
  const [purchaseValue, setPurchaseValue] = useState(0);
  const [salvageValue, setSalvageValue] = useState(0);
  const [depreciationRate, setDepreciationRate] = useState(0);
  const [depInputMode, setDepInputMode] = useState<"rate" | "months">("rate");
  const [usefulLifeInput, setUsefulLifeInput] = useState(0);
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

  // Calculo bidireccional tasa <-> meses
  const depreciable = purchaseValue - salvageValue;
  const effectiveRate = depInputMode === "months" && usefulLifeInput > 0 && purchaseValue > 0 && depreciable > 0
    ? (depreciable / (usefulLifeInput * purchaseValue)) * 100
    : depreciationRate;
  const monthlyDepreciation = purchaseValue > 0 && effectiveRate > 0
    ? Math.round(purchaseValue * (effectiveRate / 100) * 100) / 100
    : 0;
  const usefulLifeMonths = monthlyDepreciation > 0 && depreciable > 0
    ? Math.ceil(depreciable / monthlyDepreciation)
    : 0;

  const canSubmit =
    name.trim() !== "" &&
    categoryId !== "" &&
    (!hasDepreciations || true) &&
    (hasDepreciations || (purchaseValue > 0 && effectiveRate > 0 && purchaseValue > salvageValue)) &&
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
      payload.depreciation_rate = Math.round(effectiveRate * 100) / 100;
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
                options={categories.map((c) => ({ id: c.id, label: c.display_name }))}
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

            {hasDepreciations ? (
              <div>
                <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Tasa Depreciacion Mensual (%)</Label>
                <Input type="number" value={depreciationRate || ""} disabled />
              </div>
            ) : (
              <div className="md:col-span-2">
                <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Depreciacion *</Label>
                <div className="flex gap-2 mt-1 mb-2">
                  <label className={`flex items-center gap-2 px-3 py-1.5 rounded-lg border cursor-pointer transition-colors text-sm ${depInputMode === "rate" ? "border-emerald-500 bg-emerald-50 font-medium" : "border-slate-200 hover:bg-slate-50"}`}>
                    <input type="radio" name="depMode" checked={depInputMode === "rate"} onChange={() => { setDepInputMode("rate"); setUsefulLifeInput(0); }} className="accent-emerald-600" />
                    Ingresar tasa (%)
                  </label>
                  <label className={`flex items-center gap-2 px-3 py-1.5 rounded-lg border cursor-pointer transition-colors text-sm ${depInputMode === "months" ? "border-emerald-500 bg-emerald-50 font-medium" : "border-slate-200 hover:bg-slate-50"}`}>
                    <input type="radio" name="depMode" checked={depInputMode === "months"} onChange={() => { setDepInputMode("months"); setDepreciationRate(0); }} className="accent-emerald-600" />
                    Ingresar vida util (meses)
                  </label>
                </div>
                <div className="grid grid-cols-2 gap-4">
                  {depInputMode === "rate" ? (
                    <div>
                      <Input type="number" min={0.01} max={100} step={0.01} value={depreciationRate || ""} onChange={(e) => setDepreciationRate(parseFloat(e.target.value) || 0)} placeholder="Ej: 2.78" />
                      <p className="text-xs mt-1 text-slate-400">Porcentaje mensual sobre valor de compra</p>
                    </div>
                  ) : (
                    <div>
                      <Input type="number" min={1} max={600} step={1} value={usefulLifeInput || ""} onChange={(e) => setUsefulLifeInput(parseInt(e.target.value) || 0)} placeholder="Ej: 36" />
                      <p className="text-xs mt-1 text-slate-400">Numero de meses de vida util</p>
                    </div>
                  )}
                  <div className="flex items-center text-sm text-slate-500">
                    {depInputMode === "rate" && usefulLifeMonths > 0 && (
                      <span>= {usefulLifeMonths} meses de vida util</span>
                    )}
                    {depInputMode === "months" && effectiveRate > 0 && (
                      <span>= {effectiveRate.toFixed(2)}% tasa mensual</span>
                    )}
                  </div>
                </div>
              </div>
            )}

            <div className="md:col-span-2">
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Notas</Label>
              <Input value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="Observaciones adicionales (opcional)" />
            </div>
          </div>
        </CardContent>
      </Card>

      {!hasDepreciations && usefulLifeMonths > 0 && usefulLifeMonths < 12 && (
        <Alert className="border-amber-300 bg-amber-50">
          <AlertTriangle className="h-4 w-4 text-amber-600" />
          <AlertDescription className="text-amber-800">
            La configuracion resulta en una vida util de <strong>{usefulLifeMonths} meses</strong>. Verifique que la tasa de depreciacion sea correcta.
          </AlertDescription>
        </Alert>
      )}

      {/* Preview (solo si campos financieros editables) */}
      {!hasDepreciations && purchaseValue > 0 && effectiveRate > 0 && (
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
