import { useState, useEffect, useMemo } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { ArrowLeft, CreditCard, Plus, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import { PageHeader } from "@/components/shared/PageHeader";
import { EntitySelect } from "@/components/shared/EntitySelect";
import { PriceSuggestion } from "@/components/shared/PriceSuggestion";
import { useSale, useLiquidateSale } from "@/hooks/useSales";
import { usePriceSuggestions } from "@/hooks/usePriceSuggestions";
import { useMaterials, useCustomers, useSuppliers, useMoneyAccounts } from "@/hooks/useMasterData";
import { MoneyInput } from "@/components/shared/MoneyInput";
import { formatCurrency, formatDate, formatWeight } from "@/utils/formatters";
import type { SaleCommissionCreate } from "@/types/sale";

interface LiquidationLine {
  line_id: string;
  material_id: string;
  material_name: string;
  material_code: string;
  quantity: number;
  received_quantity: number;
  unit_price: number;
  unit_cost: number;
}

interface CommissionFormData extends SaleCommissionCreate {
  _key: number;
}

let commKeyCounter = 0;

function createEmptyCommission(): CommissionFormData {
  return { _key: ++commKeyCounter, third_party_id: "", concept: "", commission_type: "percentage", commission_value: 0 };
}

export default function SaleLiquidatePage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { data: sale, isLoading } = useSale(id!);
  const { data: materialsData } = useMaterials();
  const { data: customersData } = useCustomers();
  const { data: suppliersData } = useSuppliers();
  const { getSuggestedPrice } = usePriceSuggestions();
  const liquidate = useLiquidateSale();

  const materials = materialsData?.items ?? [];
  const thirdParties = [...(customersData?.items ?? []), ...(suppliersData?.items ?? [])];

  const [lines, setLines] = useState<LiquidationLine[]>([]);
  const [commissions, setCommissions] = useState<CommissionFormData[]>([]);
  const [immediateCollection, setImmediateCollection] = useState(false);
  const [collectionAccountId, setCollectionAccountId] = useState("");
  const { data: accountsData } = useMoneyAccounts();
  const accounts = accountsData?.items ?? (Array.isArray(accountsData) ? accountsData : []);

  // Inicializar líneas y comisiones desde la venta cargada
  useEffect(() => {
    if (sale && lines.length === 0) {
      setLines(
        sale.lines.map((line) => {
          let price = line.unit_price;
          if (price === 0) {
            const suggested = getSuggestedPrice(line.material_id, "sale");
            if (suggested) price = suggested;
          }
          return {
            line_id: line.id,
            material_id: line.material_id,
            material_name: line.material_name,
            material_code: line.material_code,
            quantity: line.quantity,
            received_quantity: line.quantity,
            unit_price: price,
            unit_cost: line.unit_cost,
          };
        }),
      );
      // Pre-poblar comisiones existentes
      if (sale.commissions.length > 0) {
        setCommissions(
          sale.commissions.map((c) => ({
            _key: ++commKeyCounter,
            third_party_id: c.third_party_id,
            concept: c.concept,
            commission_type: c.commission_type,
            commission_value: c.commission_value,
          })),
        );
      }
    }
  }, [sale, getSuggestedPrice, lines.length, materials]);

  // Redirigir si la venta no es liquidable
  useEffect(() => {
    if (sale && (sale.status !== "registered" || sale.double_entry_id)) {
      navigate(`/sales/${id}`, { replace: true });
    }
  }, [sale, id, navigate]);

  const updatePrice = (lineId: string, price: number) => {
    setLines((prev) =>
      prev.map((l) => (l.line_id === lineId ? { ...l, unit_price: price } : l)),
    );
  };

  const updateReceivedQuantity = (lineId: string, qty: number) => {
    setLines((prev) =>
      prev.map((l) => (l.line_id === lineId ? { ...l, received_quantity: qty } : l)),
    );
  };

  // Comisiones helpers
  const addCommission = () => setCommissions((prev) => [...prev, createEmptyCommission()]);
  const removeCommission = (key: number) => setCommissions((prev) => prev.filter((c) => c._key !== key));
  const updateCommission = (key: number, field: keyof SaleCommissionCreate, value: string | number) => {
    setCommissions((prev) =>
      prev.map((c) => (c._key === key ? { ...c, [field]: value } : c)),
    );
  };

  // Cálculos — subtotal usa received_quantity para facturación
  const subtotal = lines.reduce((sum, l) => sum + l.received_quantity * l.unit_price, 0);
  const totalCost = lines.reduce((sum, l) => sum + l.unit_cost * l.quantity, 0);
  const totalProfit = subtotal - totalCost;
  const marginPct = subtotal > 0 ? (totalProfit / subtotal) * 100 : 0;

  // Diferencia de báscula
  const totalQtyDifference = useMemo(() =>
    lines.reduce((sum, l) => sum + (l.received_quantity - l.quantity), 0),
  [lines]);
  const totalAmountDifference = useMemo(() =>
    lines.reduce((sum, l) => sum + (l.received_quantity - l.quantity) * l.unit_price, 0),
  [lines]);
  const hasDifference = Math.abs(totalQtyDifference) > 0.001;

  const commissionAmounts = commissions.map((c) => {
    if (c.commission_type === "percentage") return (subtotal * c.commission_value) / 100;
    return c.commission_value;
  });
  const totalCommissions = commissionAmounts.reduce((sum, a) => sum + a, 0);
  const netProfit = totalProfit - totalCommissions;
  const netMarginPct = subtotal > 0 ? (netProfit / subtotal) * 100 : 0;

  const allPricesValid = lines.every((l) => l.unit_price > 0);
  const allReceivedValid = lines.every((l) => l.received_quantity > 0);
  const canSubmit = allPricesValid && allReceivedValid && lines.length > 0
    && (!immediateCollection || !!collectionAccountId);

  const handleSubmit = () => {
    if (!canSubmit || !id) return;
    liquidate.mutate(
      {
        id,
        data: {
          lines: lines.map((l) => ({
            line_id: l.line_id,
            unit_price: l.unit_price,
            ...(Math.abs(l.received_quantity - l.quantity) > 0.001 && {
              received_quantity: l.received_quantity,
            }),
          })),
          commissions: commissions
            .filter((c) => c.third_party_id && c.commission_value > 0)
            .map(({ _key, ...rest }) => rest),
          ...(immediateCollection && collectionAccountId
            ? { immediate_collection: true, collection_account_id: collectionAccountId }
            : {}),
        },
      },
      { onSuccess: () => navigate(`/sales/${id}`) },
    );
  };

  if (isLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  if (!sale) {
    return <div className="text-center py-12 text-slate-500">Venta no encontrada</div>;
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title={`Liquidar Venta #${sale.sale_number}`}
        description={`Cliente: ${sale.customer_name} | Fecha: ${formatDate(sale.date)}`}
      >
        <Button variant="outline" onClick={() => navigate(`/sales/${id}`)}>
          <ArrowLeft className="h-4 w-4 mr-2" />
          Volver
        </Button>
      </PageHeader>

      {/* Info resumida */}
      <Card className="shadow-sm border-t-[3px] border-t-amber-400">
        <CardContent className="pt-6">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
            <div>
              <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">Cliente</span>
              <p className="font-medium">{sale.customer_name}</p>
            </div>
            <div>
              <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">Fecha</span>
              <p>{formatDate(sale.date)}</p>
            </div>
            {sale.warehouse_name && (
              <div>
                <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">Bodega</span>
                <p>{sale.warehouse_name}</p>
              </div>
            )}
            {sale.vehicle_plate && (
              <div>
                <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">Placa</span>
                <p>{sale.vehicle_plate}</p>
              </div>
            )}
            {sale.invoice_number && (
              <div>
                <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">Factura</span>
                <p>{sale.invoice_number}</p>
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Líneas con precios y cantidad recibida editables */}
      <Card className="shadow-sm">
        <CardHeader>
          <CardTitle className="text-sm font-semibold uppercase tracking-wider text-slate-500">
            Materiales a Cobrar
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-0">
          {lines.map((line, idx) => {
            const lineDiff = line.received_quantity - line.quantity;
            const lineTotal = line.received_quantity * line.unit_price;
            const lineProfit = lineTotal - line.unit_cost * line.quantity;
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
                  {idx === 0 && <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Despachado</Label>}
                  <p className="h-10 flex items-center text-sm tabular-nums">
                    {formatWeight(line.quantity)}
                  </p>
                </div>
                <div className="col-span-2">
                  {idx === 0 && <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Recibido (kg)</Label>}
                  <MoneyInput
                    value={line.received_quantity}
                    onChange={(v) => updateReceivedQuantity(line.line_id, v)}
                    decimals={2}
                    placeholder="0"
                  />
                </div>
                <div className="col-span-1">
                  {idx === 0 && <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Dif.</Label>}
                  <div className="h-10 flex items-center text-sm tabular-nums">
                    {Math.abs(lineDiff) < 0.001 ? (
                      <span className="text-slate-400">&mdash;</span>
                    ) : (
                      <div className={lineDiff > 0 ? "text-emerald-600" : "text-red-600"}>
                        <div>{lineDiff > 0 ? "+" : ""}{lineDiff.toFixed(2)} kg</div>
                        <div className="text-xs">
                          ({lineDiff > 0 ? "+" : ""}{formatCurrency(lineDiff * line.unit_price)})
                        </div>
                      </div>
                    )}
                  </div>
                </div>
                <div className="col-span-2 relative">
                  {idx === 0 && <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Precio/kg *</Label>}
                  <MoneyInput
                    value={line.unit_price}
                    onChange={(v) => updatePrice(line.line_id, v)}
                    placeholder="0"
                    className={line.unit_price <= 0 ? "border-red-300" : ""}
                  />
                  <div className="absolute left-0 w-max" style={{ top: "100%" }}>
                    <PriceSuggestion
                      suggestedPrice={getSuggestedPrice(line.material_id, "sale")}
                      onApply={(p) => updatePrice(line.line_id, p)}
                    />
                    {line.unit_price <= 0 && (
                      <p className="text-xs text-red-500 mt-0.5">El precio debe ser mayor a 0</p>
                    )}
                  </div>
                </div>
                <div className="col-span-2 text-right">
                  {idx === 0 && <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Total</Label>}
                  <p className="h-10 flex items-center justify-end text-sm font-medium tabular-nums">
                    {formatCurrency(lineTotal)}
                  </p>
                </div>
                <div className="col-span-2 text-right">
                  {idx === 0 && <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Util. Bruta</Label>}
                  <p className={`h-10 flex items-center justify-end text-sm font-medium tabular-nums ${lineProfit >= 0 ? "text-emerald-600" : "text-red-600"}`}>
                    {formatCurrency(lineProfit)}
                  </p>
                </div>
              </div>
            );
          })}

        </CardContent>
      </Card>

      {/* Alerta de diferencia de báscula */}
      {hasDifference && (
        <div className={`p-4 rounded-lg border ${totalAmountDifference > 0 ? "bg-emerald-50 border-emerald-200" : "bg-red-50 border-red-200"}`}>
          <div className="flex justify-between items-center">
            <span className="font-medium text-sm">
              {totalAmountDifference > 0 ? "Ganancia" : "Perdida"} por diferencia de bascula:
            </span>
            <span className={`text-lg font-bold ${totalAmountDifference > 0 ? "text-emerald-600" : "text-red-600"}`}>
              {totalAmountDifference > 0 ? "+" : ""}{formatCurrency(totalAmountDifference)}
            </span>
          </div>
          <p className="text-sm text-slate-600 mt-1">
            Diferencia total: {totalQtyDifference > 0 ? "+" : ""}{totalQtyDifference.toFixed(2)} kg
          </p>
        </div>
      )}

      {/* Comisiones */}
      <Card className="shadow-sm">
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle className="text-sm font-semibold uppercase tracking-wider text-slate-500">
            Comisiones
          </CardTitle>
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
                  options={thirdParties.map((tp) => ({ id: tp.id, label: tp.name }))}
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
                <Select
                  value={comm.commission_type}
                  onValueChange={(v) => updateCommission(comm._key, "commission_type", v)}
                >
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="percentage">Porcentaje</SelectItem>
                    <SelectItem value="fixed">Fijo</SelectItem>
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
                <p className="h-10 flex items-center justify-end text-sm tabular-nums">
                  {formatCurrency(commissionAmounts[idx] ?? 0)}
                </p>
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

      {/* Resumen Financiero */}
      <Card className="shadow-sm bg-slate-50/50">
        <CardHeader>
          <CardTitle className="text-sm font-semibold uppercase tracking-wider text-slate-500">Resumen Financiero</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="max-w-sm ml-auto space-y-2">
            <div className="flex justify-between text-sm">
              <span className="text-slate-600">Total Venta</span>
              <span className="font-bold tabular-nums text-base">{formatCurrency(subtotal)}</span>
            </div>
            <div className="border-t border-slate-200 pt-2" />
            <div className="flex justify-between text-sm">
              <span className="text-slate-600">Costo de Venta</span>
              <span className="tabular-nums text-slate-500">{formatCurrency(totalCost)}</span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-slate-600">
                Utilidad Bruta <span className="text-xs text-slate-400">({marginPct.toFixed(1)}%)</span>
              </span>
              <span className={`font-semibold tabular-nums ${totalProfit >= 0 ? "text-emerald-600" : "text-red-600"}`}>
                {formatCurrency(totalProfit)}
              </span>
            </div>
            {totalCommissions > 0 && (
              <>
                <div className="flex justify-between text-sm">
                  <span className="text-slate-600">(-) Comisiones</span>
                  <span className="tabular-nums text-amber-600">-{formatCurrency(totalCommissions)}</span>
                </div>
                <div className="border-t border-dashed border-slate-200" />
                <div className="flex justify-between text-sm">
                  <span className="font-medium text-slate-700">
                    Utilidad Neta <span className="text-xs text-slate-400">({netMarginPct.toFixed(1)}%)</span>
                  </span>
                  <span className={`font-bold tabular-nums ${netProfit >= 0 ? "text-emerald-600" : "text-red-600"}`}>
                    {formatCurrency(netProfit)}
                  </span>
                </div>
              </>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Cobro inmediato */}
      <Card className="shadow-sm">
        <CardContent className="pt-6 space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Registrar cobro inmediato</Label>
              <p className="text-xs text-slate-500 mt-1">Registra el cobro al cliente automaticamente al liquidar.</p>
            </div>
            <Switch checked={immediateCollection} onCheckedChange={setImmediateCollection} />
          </div>
          {immediateCollection && (
            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Cuenta de Cobro *</Label>
              <EntitySelect
                value={collectionAccountId}
                onChange={setCollectionAccountId}
                options={accounts.map((a) => ({ id: a.id, label: `${a.name} (${formatCurrency(a.current_balance)})` }))}
                placeholder="Seleccionar cuenta..."
              />
            </div>
          )}
        </CardContent>
      </Card>

      {/* Acciones */}
      <div className="sticky bottom-0 bg-white/95 backdrop-blur-sm border-t border-slate-100 py-4 -mx-6 px-6 mt-6">
        <div className="flex justify-end gap-2">
          <Button variant="outline" onClick={() => navigate(`/sales/${id}`)}>
            Cancelar
          </Button>
          <Button
            onClick={handleSubmit}
            disabled={!canSubmit || liquidate.isPending}
            className="bg-emerald-600 hover:bg-emerald-700"
          >
            <CreditCard className="h-4 w-4 mr-2" />
            {liquidate.isPending ? "Liquidando..." : "Confirmar Liquidacion"}
          </Button>
        </div>
      </div>
    </div>
  );
}
