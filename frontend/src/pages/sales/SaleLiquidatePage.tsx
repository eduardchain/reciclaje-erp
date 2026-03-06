import { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { ArrowLeft, CreditCard, Plus, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { PageHeader } from "@/components/shared/PageHeader";
import { EntitySelect } from "@/components/shared/EntitySelect";
import { PriceSuggestion } from "@/components/shared/PriceSuggestion";
import { useSale, useLiquidateSale } from "@/hooks/useSales";
import { usePriceSuggestions } from "@/hooks/usePriceSuggestions";
import { useMoneyAccounts, useMaterials, useCustomers, useSuppliers } from "@/hooks/useMasterData";
import { formatCurrency, formatDate, formatWeight } from "@/utils/formatters";
import type { SaleCommissionCreate } from "@/types/sale";

interface LiquidationLine {
  line_id: string;
  material_id: string;
  material_name: string;
  material_code: string;
  quantity: number;
  unit_price: number;
  unit_cost: number;
  current_avg_cost: number;
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
  const { data: accountsData } = useMoneyAccounts();
  const { data: materialsData } = useMaterials();
  const { data: customersData } = useCustomers();
  const { data: suppliersData } = useSuppliers();
  const { getSuggestedPrice } = usePriceSuggestions();
  const liquidate = useLiquidateSale();

  const accounts = accountsData?.items ?? [];
  const materials = materialsData?.items ?? [];
  const thirdParties = [...(customersData?.items ?? []), ...(suppliersData?.items ?? [])];

  const [paymentAccountId, setPaymentAccountId] = useState("");
  const [lines, setLines] = useState<LiquidationLine[]>([]);
  const [commissions, setCommissions] = useState<CommissionFormData[]>([]);

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
          const mat = materials.find((m) => m.id === line.material_id);
          return {
            line_id: line.id,
            material_id: line.material_id,
            material_name: line.material_name,
            material_code: line.material_code,
            quantity: line.quantity,
            unit_price: price,
            unit_cost: line.unit_cost,
            current_avg_cost: mat?.current_average_cost ?? line.unit_cost,
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

  // Comisiones helpers
  const addCommission = () => setCommissions((prev) => [...prev, createEmptyCommission()]);
  const removeCommission = (key: number) => setCommissions((prev) => prev.filter((c) => c._key !== key));
  const updateCommission = (key: number, field: keyof SaleCommissionCreate, value: string | number) => {
    setCommissions((prev) =>
      prev.map((c) => (c._key === key ? { ...c, [field]: value } : c)),
    );
  };

  // Cálculos
  const subtotal = lines.reduce((sum, l) => sum + l.quantity * l.unit_price, 0);
  const totalProfit = lines.reduce((sum, l) => sum + (l.unit_price - l.unit_cost) * l.quantity, 0);
  const marginPct = subtotal > 0 ? (totalProfit / subtotal) * 100 : 0;

  const commissionAmounts = commissions.map((c) => {
    if (c.commission_type === "percentage") return (subtotal * c.commission_value) / 100;
    return c.commission_value;
  });
  const totalCommissions = commissionAmounts.reduce((sum, a) => sum + a, 0);
  const netTotal = subtotal - totalCommissions;

  const allPricesValid = lines.every((l) => l.unit_price > 0);
  const canSubmit = paymentAccountId && allPricesValid && lines.length > 0;

  const handleSubmit = () => {
    if (!canSubmit || !id) return;
    liquidate.mutate(
      {
        id,
        data: {
          payment_account_id: paymentAccountId,
          lines: lines.map((l) => ({
            line_id: l.line_id,
            unit_price: l.unit_price,
          })),
          commissions: commissions
            .filter((c) => c.third_party_id && c.commission_value > 0)
            .map(({ _key, ...rest }) => rest),
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
        title={`Cobrar Venta #${sale.sale_number}`}
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

      {/* Líneas con precios editables */}
      <Card className="shadow-sm">
        <CardHeader>
          <CardTitle className="text-sm font-semibold uppercase tracking-wider text-slate-500">
            Materiales a Cobrar
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-0">
          {lines.map((line, idx) => {
            const lineProfit = (line.unit_price - line.unit_cost) * line.quantity;
            return (
              <div
                key={line.line_id}
                className={`grid grid-cols-12 gap-2 items-end pb-3 mb-3 ${idx < lines.length - 1 ? "border-b border-slate-100" : ""}`}
              >
                <div className="col-span-3">
                  {idx === 0 && <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Material</Label>}
                  <p className="h-10 flex items-center text-sm">
                    <span className="font-medium">{line.material_name}</span>
                    <span className="text-slate-400 ml-2 text-xs">{line.material_code}</span>
                  </p>
                </div>
                <div className="col-span-1">
                  {idx === 0 && <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Cant. (kg)</Label>}
                  <p className="h-10 flex items-center text-sm tabular-nums">
                    {formatWeight(line.quantity)}
                  </p>
                </div>
                <div className="col-span-2">
                  {idx === 0 && <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Costo Prom.</Label>}
                  <p className="h-10 flex items-center text-sm tabular-nums text-slate-400">
                    {formatCurrency(line.current_avg_cost)}
                  </p>
                </div>
                <div className="col-span-2">
                  {idx === 0 && <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Precio/kg *</Label>}
                  <Input
                    type="number"
                    min={0}
                    step="1"
                    value={line.unit_price || ""}
                    onChange={(e) => updatePrice(line.line_id, parseFloat(e.target.value) || 0)}
                    placeholder="0"
                    className={line.unit_price <= 0 ? "border-red-300" : ""}
                  />
                  <PriceSuggestion
                    suggestedPrice={getSuggestedPrice(line.material_id, "sale")}
                    onApply={(p) => updatePrice(line.line_id, p)}
                  />
                  {line.unit_price <= 0 && (
                    <p className="text-xs text-red-500 mt-0.5">El precio debe ser mayor a 0</p>
                  )}
                </div>
                <div className="col-span-2 text-right">
                  {idx === 0 && <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Total</Label>}
                  <p className="h-10 flex items-center justify-end text-sm font-medium tabular-nums">
                    {formatCurrency(line.quantity * line.unit_price)}
                  </p>
                </div>
                <div className="col-span-2 text-right">
                  {idx === 0 && <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Utilidad</Label>}
                  <p className={`h-10 flex items-center justify-end text-sm font-medium tabular-nums ${lineProfit >= 0 ? "text-emerald-600" : "text-red-600"}`}>
                    {formatCurrency(lineProfit)}
                  </p>
                </div>
              </div>
            );
          })}

          <div className="bg-slate-50 rounded-lg p-3 mt-2">
            <div className="flex justify-between items-center">
              <span className="text-sm text-slate-600">Subtotal</span>
              <span className="text-lg font-bold">{formatCurrency(subtotal)}</span>
            </div>
          </div>
        </CardContent>
      </Card>

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

      {/* Cuenta de cobro */}
      <Card className="shadow-sm">
        <CardContent className="pt-6">
          <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Cuenta de Cobro *</Label>
          <EntitySelect
            value={paymentAccountId}
            onChange={setPaymentAccountId}
            options={accounts.map((a) => ({
              id: a.id,
              label: `${a.name} (${formatCurrency(a.current_balance)})`,
            }))}
            placeholder="Seleccionar cuenta de cobro..."
          />
        </CardContent>
      </Card>

      {/* Resumen y acciones */}
      <div className="sticky bottom-0 bg-white/95 backdrop-blur-sm border-t border-slate-100 py-4 -mx-6 px-6 mt-6">
        <div className="flex items-center justify-between">
          <div className="space-y-1 text-sm">
            <div className="flex gap-6">
              <span>Subtotal: <strong>{formatCurrency(subtotal)}</strong></span>
              {totalCommissions > 0 && (
                <span>Comisiones: <strong className="text-amber-600">-{formatCurrency(totalCommissions)}</strong></span>
              )}
              {totalCommissions > 0 && (
                <span>Neto: <strong>{formatCurrency(netTotal)}</strong></span>
              )}
            </div>
            <div className="flex gap-6">
              <span className={totalProfit >= 0 ? "text-emerald-600" : "text-red-600"}>
                Utilidad Bruta: <strong>{formatCurrency(totalProfit)}</strong>
              </span>
              <span className="text-slate-500">
                Margen: <strong>{marginPct.toFixed(1)}%</strong>
              </span>
            </div>
          </div>
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => navigate(`/sales/${id}`)}>
              Cancelar
            </Button>
            <Button
              onClick={handleSubmit}
              disabled={!canSubmit || liquidate.isPending}
              className="bg-emerald-600 hover:bg-emerald-700"
            >
              <CreditCard className="h-4 w-4 mr-2" />
              {liquidate.isPending ? "Cobrando..." : "Confirmar Cobro"}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
