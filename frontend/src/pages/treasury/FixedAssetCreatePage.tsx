import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowLeft } from "lucide-react";
import { AlertTriangle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { PageHeader } from "@/components/shared/PageHeader";
import { EntitySelect } from "@/components/shared/EntitySelect";
import { MoneyInput } from "@/components/shared/MoneyInput";
import { BusinessUnitAllocationSelector } from "@/components/shared/BusinessUnitAllocationSelector";
import { useCreateFixedAsset } from "@/hooks/useFixedAssets";
import { useExpenseCategoriesFlat, useThirdParties, useMoneyAccounts } from "@/hooks/useMasterData";
import { formatCurrency, toLocalDateInput } from "@/utils/formatters";
import { ROUTES } from "@/utils/constants";

export default function FixedAssetCreatePage() {
  const navigate = useNavigate();
  const create = useCreateFixedAsset();

  const { data: categoriesData } = useExpenseCategoriesFlat();
  const { data: suppliersData } = useThirdParties();
  const { data: accountsData } = useMoneyAccounts();

  const categories = categoriesData?.items ?? [];
  const suppliers = suppliersData?.items ?? [];
  const accounts = accountsData?.items ?? [];

  const [name, setName] = useState("");
  const [assetCode, setAssetCode] = useState("");
  const [purchaseDate, setPurchaseDate] = useState(toLocalDateInput());
  const [purchaseValue, setPurchaseValue] = useState(0);
  const [salvageValue, setSalvageValue] = useState(0);
  const [depreciationRate, setDepreciationRate] = useState(0);
  const [depInputMode, setDepInputMode] = useState<"rate" | "months">("rate");
  const [usefulLifeInput, setUsefulLifeInput] = useState(0);
  const [depreciationStartDate, setDepreciationStartDate] = useState(toLocalDateInput());
  const [paymentSource, setPaymentSource] = useState<"account" | "supplier">("account");
  const [accountId, setAccountId] = useState("");
  const [supplierId, setSupplierId] = useState("");
  const [categoryId, setCategoryId] = useState("");
  const handleCategoryChange = (catId: string) => {
    setCategoryId(catId);
    const cat = categories.find((c) => c.id === catId);
    if (cat) {
      if (cat.default_business_unit_id) {
        setBuAllocationType("direct");
        setBuDirectId(cat.default_business_unit_id);
        setBuSharedIds([]);
      } else if (cat.default_applicable_business_unit_ids?.length) {
        setBuAllocationType("shared");
        setBuDirectId("");
        setBuSharedIds(cat.default_applicable_business_unit_ids);
      } else {
        setBuAllocationType("general");
        setBuDirectId("");
        setBuSharedIds([]);
      }
    }
  };
  const [notes, setNotes] = useState("");
  const [buAllocationType, setBuAllocationType] = useState<"direct" | "shared" | "general">("general");
  const [buDirectId, setBuDirectId] = useState("");
  const [buSharedIds, setBuSharedIds] = useState<string[]>([]);

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
    purchaseValue > 0 &&
    effectiveRate > 0 &&
    effectiveRate <= 100 &&
    purchaseValue > salvageValue &&
    categoryId !== "" &&
    (paymentSource === "account" ? accountId !== "" : supplierId !== "") &&
    !create.isPending;

  const handleSubmit = () => {
    create.mutate(
      {
        name,
        asset_code: assetCode || null,
        purchase_date: purchaseDate,
        purchase_value: purchaseValue,
        salvage_value: salvageValue,
        depreciation_rate: Math.round(effectiveRate * 100) / 100,
        depreciation_start_date: depreciationStartDate,
        expense_category_id: categoryId,
        source_account_id: paymentSource === "account" ? accountId : null,
        supplier_id: paymentSource === "supplier" ? supplierId : null,
        notes: notes || null,
        business_unit_id: buAllocationType === "direct" && buDirectId ? buDirectId : null,
        applicable_business_unit_ids: buAllocationType === "shared" && buSharedIds.length > 0 ? buSharedIds : null,
      },
      {
        onSuccess: () => navigate(ROUTES.TREASURY_FIXED_ASSETS),
      },
    );
  };

  return (
    <div className="space-y-6">
      <PageHeader title="Nuevo Activo Fijo" description="Registrar equipo o bien con depreciacion mensual">
        <Button variant="outline" onClick={() => navigate(ROUTES.TREASURY_FIXED_ASSETS)}>
          <ArrowLeft className="h-4 w-4 mr-2" />Volver
        </Button>
      </PageHeader>

      <Card className="shadow-sm">
        <CardHeader>
          <CardTitle className="text-sm font-semibold uppercase tracking-wider text-slate-500">Datos del Activo</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="md:col-span-2">
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Nombre *</Label>
              <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="Ej: Retroexcavadora CAT 320" />
            </div>

            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Codigo de Activo</Label>
              <Input value={assetCode} onChange={(e) => setAssetCode(e.target.value)} placeholder="Ej: AF-001" />
            </div>

            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Fecha de Compra *</Label>
              <Input type="date" value={purchaseDate} onChange={(e) => setPurchaseDate(e.target.value)} />
            </div>

            <div className="md:col-span-2">
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Fuente de Pago *</Label>
              <div className="flex gap-4 mt-2">
                <label className={`flex items-center gap-2 px-4 py-2 rounded-lg border cursor-pointer transition-colors ${paymentSource === "account" ? "border-emerald-500 bg-emerald-50" : "border-slate-200 hover:bg-slate-50"}`}>
                  <input type="radio" name="paymentSource" checked={paymentSource === "account"} onChange={() => { setPaymentSource("account"); setSupplierId(""); }} className="accent-emerald-600" />
                  <span className="text-sm font-medium">Pago desde Cuenta</span>
                </label>
                <label className={`flex items-center gap-2 px-4 py-2 rounded-lg border cursor-pointer transition-colors ${paymentSource === "supplier" ? "border-emerald-500 bg-emerald-50" : "border-slate-200 hover:bg-slate-50"}`}>
                  <input type="radio" name="paymentSource" checked={paymentSource === "supplier"} onChange={() => { setPaymentSource("supplier"); setAccountId(""); }} className="accent-emerald-600" />
                  <span className="text-sm font-medium">A Credito (Proveedor)</span>
                </label>
              </div>
            </div>

            {paymentSource === "account" ? (
              <div>
                <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Cuenta de Pago *</Label>
                <EntitySelect
                  value={accountId}
                  onChange={setAccountId}
                  options={accounts.map((a) => ({ id: a.id, label: `${a.name} (${formatCurrency(a.current_balance)})` }))}
                  placeholder="Seleccionar cuenta..."
                />
                <p className="text-xs mt-1 text-slate-400">Se descontara el valor de compra de esta cuenta</p>
              </div>
            ) : (
              <div>
                <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Proveedor *</Label>
                <EntitySelect
                  value={supplierId}
                  onChange={setSupplierId}
                  options={suppliers.map((s) => ({ id: s.id, label: s.name }))}
                  placeholder="Seleccionar proveedor..."
                />
                <p className="text-xs mt-1 text-slate-400">El proveedor quedara con deuda pendiente. Pague despues con "Pago a Proveedor"</p>
              </div>
            )}

            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Valor de Compra *</Label>
              <MoneyInput value={purchaseValue} onChange={setPurchaseValue} placeholder="0" />
            </div>

            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Valor Residual</Label>
              <MoneyInput value={salvageValue} onChange={setSalvageValue} placeholder="0" />
              <p className="text-xs mt-1 text-slate-400">Valor al final de la vida util (default 0)</p>
            </div>

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

            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Fecha Inicio Depreciacion *</Label>
              <Input type="date" value={depreciationStartDate} onChange={(e) => setDepreciationStartDate(e.target.value)} />
              <p className="text-xs mt-1 text-slate-400">Debe ser igual o posterior a la fecha de compra</p>
            </div>

            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Categoria de Gasto *</Label>
              <EntitySelect
                value={categoryId}
                onChange={handleCategoryChange}
                options={categories.map((c) => ({ id: c.id, label: c.display_name }))}
                placeholder="Seleccionar categoria..."
              />
            </div>


            <div className="md:col-span-2">
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Notas</Label>
              <Input value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="Observaciones adicionales (opcional)" />
            </div>

            <BusinessUnitAllocationSelector
              businessUnitId={buDirectId}
              setBusinessUnitId={setBuDirectId}
              applicableBusinessUnitIds={buSharedIds}
              setApplicableBusinessUnitIds={setBuSharedIds}
              allocationType={buAllocationType}
              setAllocationType={setBuAllocationType}
            />
          </div>
        </CardContent>
      </Card>

      {usefulLifeMonths > 0 && usefulLifeMonths < 12 && (
        <Alert className="border-amber-300 bg-amber-50">
          <AlertTriangle className="h-4 w-4 text-amber-600" />
          <AlertDescription className="text-amber-800">
            La configuracion resulta en una vida util de <strong>{usefulLifeMonths} meses</strong>. Verifique que la tasa de depreciacion sea correcta.
          </AlertDescription>
        </Alert>
      )}

      {/* Preview */}
      {purchaseValue > 0 && effectiveRate > 0 && (
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
          <Button variant="outline" onClick={() => navigate(ROUTES.TREASURY_FIXED_ASSETS)}>Cancelar</Button>
          <Button
            onClick={handleSubmit}
            disabled={!canSubmit}
            className="bg-emerald-600 hover:bg-emerald-700"
          >
            {create.isPending ? "Creando..." : "Crear Activo Fijo"}
          </Button>
        </div>
      </div>
    </div>
  );
}
