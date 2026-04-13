import { useState, useEffect, useMemo } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { ArrowLeft, CheckCircle, Plus, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { PageHeader } from "@/components/shared/PageHeader";
import { EntitySelect } from "@/components/shared/EntitySelect";
import { PriceSuggestion } from "@/components/shared/PriceSuggestion";
import { MoneyInput } from "@/components/shared/MoneyInput";
import { useDoubleEntry, useLiquidateDoubleEntry } from "@/hooks/useDoubleEntries";
import { usePriceSuggestions } from "@/hooks/usePriceSuggestions";
import { usePayableProviders } from "@/hooks/useMasterData";
import { formatCurrency, formatDate, formatWeight } from "@/utils/formatters";
import { usePermissions } from "@/hooks/usePermissions";
import type { SaleCommissionCreate } from "@/types/sale";

interface LiquidationLine {
  line_id: string;
  material_id: string;
  material_name: string;
  material_code: string;
  quantity: number;
  purchase_unit_price: number;
  sale_unit_price: number;
}

interface CommissionFormData extends SaleCommissionCreate {
  _key: number;
}

let commKeyCounter = 0;

function createEmptyCommission(): CommissionFormData {
  return { _key: ++commKeyCounter, third_party_id: "", concept: "", commission_type: "percentage", commission_value: 0 };
}

export default function DoubleEntryLiquidatePage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { data: de, isLoading } = useDoubleEntry(id!);
  const liquidate = useLiquidateDoubleEntry();
  const { getSuggestedPrice } = usePriceSuggestions();
  const { hasPermission } = usePermissions();
  const canViewProfit = hasPermission("double_entries.view_profit");

  const { data: payableData } = usePayableProviders();
  const payableProviders = payableData?.items ?? [];

  const [lines, setLines] = useState<LiquidationLine[]>([]);
  const [commissions, setCommissions] = useState<CommissionFormData[]>([]);
  const [liquidationDate, setLiquidationDate] = useState("");
  const _todayNow = new Date();
  const todayStr = `${_todayNow.getFullYear()}-${String(_todayNow.getMonth() + 1).padStart(2, "0")}-${String(_todayNow.getDate()).padStart(2, "0")}`;
  const docDateStr = de ? (() => { const d = new Date(de.date); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`; })() : "";

  // Inicializar fecha de liquidacion con la fecha del documento
  useEffect(() => {
    if (de && !liquidationDate) {
      const d = new Date(de.date);
      setLiquidationDate(`${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`);
    }
  }, [de, liquidationDate]);

  // Inicializar desde DP cargada
  useEffect(() => {
    if (de && lines.length === 0) {
      setLines(
        de.lines.map((line) => ({
          line_id: line.id,
          material_id: line.material_id,
          material_name: line.material_name,
          material_code: line.material_code,
          quantity: line.quantity,
          purchase_unit_price: line.purchase_unit_price,
          sale_unit_price: line.sale_unit_price,
        })),
      );
      if (de.commissions.length > 0) {
        setCommissions(
          de.commissions.map((c) => ({
            _key: ++commKeyCounter,
            third_party_id: c.third_party_id,
            concept: c.concept,
            commission_type: c.commission_type,
            commission_value: c.commission_value,
          })),
        );
      }
    }
  }, [de, lines.length]);

  // Redirigir si no es liquidable
  useEffect(() => {
    if (de && de.status !== "registered") {
      navigate(`/double-entries/${id}`, { replace: true });
    }
  }, [de, id, navigate]);

  const updateLine = (lineId: string, field: "purchase_unit_price" | "sale_unit_price", value: number) => {
    setLines((prev) => prev.map((l) => (l.line_id === lineId ? { ...l, [field]: value } : l)));
  };

  // Comisiones helpers
  const addCommission = () => setCommissions((prev) => [...prev, createEmptyCommission()]);
  const removeCommission = (key: number) => setCommissions((prev) => prev.filter((c) => c._key !== key));
  const updateCommission = (key: number, field: keyof SaleCommissionCreate, value: string | number) => {
    setCommissions((prev) => prev.map((c) => (c._key === key ? { ...c, [field]: value } : c)));
  };

  // Calculos
  const totalPurchase = useMemo(() => lines.reduce((sum, l) => sum + l.quantity * l.purchase_unit_price, 0), [lines]);
  const totalSale = useMemo(() => lines.reduce((sum, l) => sum + l.quantity * l.sale_unit_price, 0), [lines]);
  const grossProfit = totalSale - totalPurchase;

  const totalQuantity = lines.reduce((sum, l) => sum + (l.quantity || 0), 0);
  const commissionAmounts = commissions.map((c) => {
    if (c.commission_type === "percentage") return (totalSale * c.commission_value) / 100;
    if (c.commission_type === "per_kg") return totalQuantity * c.commission_value;
    return c.commission_value;
  });
  const totalCommissions = commissionAmounts.reduce((sum, a) => sum + a, 0);
  const netProfit = grossProfit - totalCommissions;

  const allPricesValid = lines.every((l) => l.purchase_unit_price > 0 && l.sale_unit_price > 0);
  const canSubmit = allPricesValid && lines.length > 0;

  const handleSubmit = () => {
    if (!canSubmit || !id) return;
    liquidate.mutate(
      {
        id,
        data: {
          lines: lines.map((l) => ({
            line_id: l.line_id,
            purchase_unit_price: l.purchase_unit_price,
            sale_unit_price: l.sale_unit_price,
          })),
          commissions: commissions
            .filter((c) => c.third_party_id && c.commission_value > 0)
            .map(({ _key, ...rest }) => rest),
          ...(liquidationDate ? { liquidation_date: liquidationDate } : {}),
        },
      },
      { onSuccess: () => navigate(`/double-entries/${id}`) },
    );
  };

  if (isLoading) return <div className="space-y-4"><Skeleton className="h-8 w-64" /><Skeleton className="h-64 w-full" /></div>;
  if (!de) return <div className="text-center py-12 text-slate-500">Doble partida no encontrada</div>;

  return (
    <div className="space-y-6">
      <PageHeader
        title={`Liquidar Doble Partida #${de.double_entry_number}`}
        description={`Proveedor: ${de.supplier_name} | Cliente: ${de.customer_name} | ${formatDate(de.date)}`}
      >
        <Button variant="outline" onClick={() => navigate(`/double-entries/${id}`)}>
          <ArrowLeft className="h-4 w-4 mr-2" />Volver
        </Button>
      </PageHeader>

      {/* Info resumida */}
      <Card className="shadow-sm border-t-[3px] border-t-amber-400">
        <CardContent className="pt-6">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
            <div>
              <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">Proveedor</span>
              <p className="font-medium">{de.supplier_name}</p>
            </div>
            <div>
              <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">Cliente</span>
              <p className="font-medium">{de.customer_name}</p>
            </div>
            <div>
              <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">Fecha</span>
              <p>{formatDate(de.date)}</p>
            </div>
            {de.invoice_number && (
              <div>
                <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">Factura</span>
                <p>{de.invoice_number}</p>
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Lineas con precios editables */}
      <Card className="shadow-sm">
        <CardHeader>
          <CardTitle className="text-sm font-semibold uppercase tracking-wider text-slate-500">
            Confirmar Precios
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-0">
          {lines.map((line, idx) => {
            const lineProfit = (line.sale_unit_price - line.purchase_unit_price) * line.quantity;
            return (
              <div
                key={line.line_id}
                className={`grid grid-cols-12 gap-2 items-end pb-8 mb-3 relative ${idx < lines.length - 1 ? "border-b border-slate-100" : ""}`}
              >
                <div className="col-span-2">
                  {idx === 0 && <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Material</Label>}
                  <p className="h-10 flex items-center text-sm">
                    <span className="font-medium">{line.material_name}</span>
                    <span className="text-slate-400 ml-1 text-xs">{line.material_code}</span>
                  </p>
                </div>
                <div className="col-span-1">
                  {idx === 0 && <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Cantidad</Label>}
                  <p className="h-10 flex items-center text-sm tabular-nums">{formatWeight(line.quantity)}</p>
                </div>
                <div className="col-span-2 relative">
                  {idx === 0 && <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">P. Compra *</Label>}
                  <MoneyInput
                    value={line.purchase_unit_price}
                    onChange={(v) => updateLine(line.line_id, "purchase_unit_price", v)}
                    placeholder="0"
                    className={line.purchase_unit_price <= 0 ? "border-red-300" : ""}
                  />
                  <div className="absolute left-0 w-max" style={{ top: "100%" }}>
                    <PriceSuggestion
                      suggestedPrice={getSuggestedPrice(line.material_id, "purchase")}
                      onApply={(p) => updateLine(line.line_id, "purchase_unit_price", p)}
                    />
                  </div>
                </div>
                <div className="col-span-2 relative">
                  {idx === 0 && <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">P. Venta *</Label>}
                  <MoneyInput
                    value={line.sale_unit_price}
                    onChange={(v) => updateLine(line.line_id, "sale_unit_price", v)}
                    placeholder="0"
                    className={line.sale_unit_price <= 0 ? "border-red-300" : ""}
                  />
                  <div className="absolute left-0 w-max" style={{ top: "100%" }}>
                    <PriceSuggestion
                      suggestedPrice={getSuggestedPrice(line.material_id, "sale")}
                      onApply={(p) => updateLine(line.line_id, "sale_unit_price", p)}
                    />
                  </div>
                </div>
                <div className="col-span-2 text-right">
                  {idx === 0 && <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Total Compra</Label>}
                  <p className="h-10 flex items-center justify-end text-sm tabular-nums">{formatCurrency(line.quantity * line.purchase_unit_price)}</p>
                </div>
                <div className="col-span-1 text-right">
                  {idx === 0 && <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Total Venta</Label>}
                  <p className="h-10 flex items-center justify-end text-sm tabular-nums">{formatCurrency(line.quantity * line.sale_unit_price)}</p>
                </div>
                {canViewProfit && <div className="col-span-2 text-right">
                  {idx === 0 && <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Ganancia</Label>}
                  <p className={`h-10 flex items-center justify-end text-sm font-medium tabular-nums ${lineProfit >= 0 ? "text-emerald-600" : "text-red-600"}`}>
                    {formatCurrency(lineProfit)}
                  </p>
                </div>}
              </div>
            );
          })}
        </CardContent>
      </Card>

      {/* Comisiones */}
      <Card className="shadow-sm">
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle className="text-sm font-semibold uppercase tracking-wider text-slate-500">Comisiones</CardTitle>
          <Button type="button" variant="outline" size="sm" onClick={addCommission}>
            <Plus className="h-4 w-4 mr-1" /> Agregar
          </Button>
        </CardHeader>
        <CardContent className="space-y-3">
          {commissions.length === 0 && (
            <p className="text-sm text-slate-400 text-center py-2">Sin comisiones</p>
          )}
          {commissions.map((comm, idx) => (
            <div key={comm._key} className={`grid grid-cols-12 gap-2 items-end pb-3 ${idx < commissions.length - 1 ? "border-b border-slate-100" : ""}`}>
              <div className="col-span-3">
                {idx === 0 && <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Comisionista</Label>}
                <EntitySelect
                  value={comm.third_party_id}
                  onChange={(v) => updateCommission(comm._key, "third_party_id", v)}
                  options={payableProviders.map((tp) => ({ id: tp.id, label: tp.name }))}
                  placeholder="Seleccionar..."
                />
              </div>
              <div className="col-span-3">
                {idx === 0 && <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Concepto</Label>}
                <Input
                  value={comm.concept}
                  onChange={(e) => updateCommission(comm._key, "concept", e.target.value)}
                  placeholder="Concepto"
                />
              </div>
              <div className="col-span-2">
                {idx === 0 && <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Tipo</Label>}
                <Select value={comm.commission_type} onValueChange={(v) => updateCommission(comm._key, "commission_type", v)}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="percentage">Porcentaje</SelectItem>
                    <SelectItem value="fixed">Fijo</SelectItem>
                    <SelectItem value="per_kg">Por Kilo</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="col-span-1">
                {idx === 0 && <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Valor</Label>}
                <Input
                  type="number"
                  min={0}
                  step="0.01"
                  value={comm.commission_value || ""}
                  onChange={(e) => updateCommission(comm._key, "commission_value", parseFloat(e.target.value) || 0)}
                />
              </div>
              <div className="col-span-2 text-right">
                {idx === 0 && <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Monto</Label>}
                <p className="h-10 flex items-center justify-end text-sm tabular-nums">{formatCurrency(commissionAmounts[idx] ?? 0)}</p>
              </div>
              <div className="col-span-1 flex justify-end">
                {idx === 0 && <Label className="text-xs invisible">X</Label>}
                <Button type="button" variant="ghost" size="icon" onClick={() => removeCommission(comm._key)}>
                  <Trash2 className="h-4 w-4 text-red-500" />
                </Button>
              </div>
            </div>
          ))}
        </CardContent>
      </Card>

      {/* Fecha de liquidacion */}
      <Card className="shadow-sm">
        <CardContent className="pt-6">
          <div className="flex items-center gap-4">
            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Fecha de Liquidación</Label>
              <p className="text-xs text-slate-500 mt-0.5">Por defecto usa la fecha del documento.</p>
            </div>
            <Input
              type="date"
              value={liquidationDate}
              min={docDateStr}
              max={todayStr}
              onChange={(e) => setLiquidationDate(e.target.value)}
              className="w-40 h-8 text-xs"
            />
          </div>
        </CardContent>
      </Card>

      {/* Resumen Financiero */}
      <Card className="border-2 border-emerald-200 bg-emerald-50 shadow-sm">
        <CardContent className="pt-6">
          <div className="max-w-sm ml-auto space-y-2">
            <div className="flex justify-between text-sm">
              <span className="text-slate-600">Total Compra</span>
              <span className="tabular-nums">{formatCurrency(totalPurchase)}</span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-slate-600">Total Venta</span>
              <span className="font-bold tabular-nums text-base">{formatCurrency(totalSale)}</span>
            </div>
            {canViewProfit && (
              <>
                <div className="border-t border-slate-200 pt-2" />
                <div className="flex justify-between text-sm">
                  <span className="text-slate-600">Utilidad Bruta</span>
                  <span className={`font-semibold tabular-nums ${grossProfit >= 0 ? "text-emerald-600" : "text-red-600"}`}>{formatCurrency(grossProfit)}</span>
                </div>
                {totalCommissions > 0 && (
                  <>
                    <div className="flex justify-between text-sm">
                      <span className="text-slate-600">(-) Comisiones</span>
                      <span className="tabular-nums text-amber-600">-{formatCurrency(totalCommissions)}</span>
                    </div>
                    <div className="border-t border-dashed border-slate-200" />
                    <div className="flex justify-between text-sm">
                      <span className="font-medium text-slate-700">Utilidad Neta</span>
                      <span className={`font-bold tabular-nums ${netProfit >= 0 ? "text-emerald-600" : "text-red-600"}`}>{formatCurrency(netProfit)}</span>
                    </div>
                  </>
                )}
              </>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Acciones */}
      <div className="sticky bottom-0 bg-white/95 backdrop-blur-sm border-t border-slate-100 py-4 -mx-6 px-6 mt-6">
        <div className="flex justify-end gap-2">
          <Button variant="outline" onClick={() => navigate(`/double-entries/${id}`)}>Cancelar</Button>
          <Button
            onClick={handleSubmit}
            disabled={!canSubmit || liquidate.isPending}
            className="bg-emerald-600 hover:bg-emerald-700"
          >
            <CheckCircle className="h-4 w-4 mr-2" />
            {liquidate.isPending ? "Liquidando..." : "Confirmar Liquidacion"}
          </Button>
        </div>
      </div>
    </div>
  );
}
