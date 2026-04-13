import { useState, useEffect, useMemo } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { ArrowLeft, CheckCircle, Plus, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import { PageHeader } from "@/components/shared/PageHeader";
import { PriceSuggestion } from "@/components/shared/PriceSuggestion";
import { EntitySelect } from "@/components/shared/EntitySelect";
import { usePurchase, useLiquidatePurchase } from "@/hooks/usePurchases";
import { usePriceSuggestions } from "@/hooks/usePriceSuggestions";
import { usePayableProviders, useMoneyAccounts } from "@/hooks/useMasterData";
import { MoneyInput } from "@/components/shared/MoneyInput";
import { formatCurrency, formatDate, formatWeight } from "@/utils/formatters";
import type { PurchaseCommissionCreate } from "@/types/purchase";

interface LiquidationLine {
  line_id: string;
  material_id: string;
  material_name: string;
  material_code: string;
  warehouse_name: string | null;
  quantity: number;
  unit_price: number;
}

interface CommissionFormData extends PurchaseCommissionCreate {
  _key: number;
}

let commKeyCounter = 0;

function createEmptyCommission(): CommissionFormData {
  return { _key: ++commKeyCounter, third_party_id: "", concept: "", commission_type: "percentage", commission_value: 0 };
}

export default function PurchaseLiquidatePage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { data: purchase, isLoading } = usePurchase(id!);
  const { getSuggestedPrice } = usePriceSuggestions();
  const liquidate = useLiquidatePurchase();
  const { data: payableData } = usePayableProviders();
  const payableProviders = payableData?.items ?? [];

  const [lines, setLines] = useState<LiquidationLine[]>([]);
  const [commissions, setCommissions] = useState<CommissionFormData[]>([]);
  const [immediatePayment, setImmediatePayment] = useState(false);
  const [paymentAccountId, setPaymentAccountId] = useState("");
  const [liquidationDate, setLiquidationDate] = useState("");
  const { data: accountsData } = useMoneyAccounts();
  const accounts = accountsData?.items ?? (Array.isArray(accountsData) ? accountsData : []);
  const _todayNow = new Date();
  const todayStr = `${_todayNow.getFullYear()}-${String(_todayNow.getMonth() + 1).padStart(2, "0")}-${String(_todayNow.getDate()).padStart(2, "0")}`;
  const docDateStr = purchase ? (() => { const d = new Date(purchase.date); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`; })() : "";

  // Inicializar fecha de liquidacion con la fecha del documento
  useEffect(() => {
    if (purchase && !liquidationDate) {
      const d = new Date(purchase.date);
      setLiquidationDate(`${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`);
    }
  }, [purchase, liquidationDate]);

  // Inicializar lineas y comisiones desde la compra cargada
  useEffect(() => {
    if (purchase && lines.length === 0) {
      setLines(
        purchase.lines.map((line) => {
          // Si el precio es 0, intentar pre-llenar desde lista de precios
          let price = line.unit_price;
          if (price === 0) {
            const suggested = getSuggestedPrice(line.material_id, "purchase");
            if (suggested) price = suggested;
          }
          return {
            line_id: line.id,
            material_id: line.material_id,
            material_name: line.material_name,
            material_code: line.material_code,
            warehouse_name: line.warehouse_name,
            quantity: line.quantity,
            unit_price: price,
          };
        }),
      );
      if (purchase.commissions?.length > 0) {
        setCommissions(
          purchase.commissions.map((c) => ({
            _key: ++commKeyCounter,
            third_party_id: c.third_party_id,
            concept: c.concept,
            commission_type: c.commission_type,
            commission_value: c.commission_value,
          }))
        );
      }
    }
  }, [purchase, getSuggestedPrice, lines.length]);

  // Redirigir si la compra no es liquidable
  useEffect(() => {
    if (purchase && (purchase.status !== "registered" || purchase.double_entry_id)) {
      navigate(`/purchases/${id}`, { replace: true });
    }
  }, [purchase, id, navigate]);

  const updatePrice = (lineId: string, price: number) => {
    setLines((prev) =>
      prev.map((l) => (l.line_id === lineId ? { ...l, unit_price: price } : l)),
    );
  };

  const updateCommission = (key: number, field: keyof PurchaseCommissionCreate, value: string | number) => {
    setCommissions((prev) => prev.map((c) => (c._key === key ? { ...c, [field]: value } : c)));
  };

  const total = lines.reduce((sum, l) => sum + l.quantity * l.unit_price, 0);
  const totalQuantity = lines.reduce((sum, l) => sum + (l.quantity || 0), 0);
  const totalComm = useMemo(() => commissions.reduce((sum, c) => {
    return sum + (c.commission_type === "percentage" ? (total * c.commission_value) / 100 : c.commission_type === "per_kg" ? totalQuantity * c.commission_value : c.commission_value);
  }, 0), [commissions, total, totalQuantity]);
  const linesCostData = useMemo(() => {
    if (totalComm === 0 || total === 0) return null;
    return lines.map(line => {
      const lineValue = line.quantity * line.unit_price;
      const weight = lineValue / total;
      const lineCommission = totalComm * weight;
      const unitCost = line.quantity > 0
        ? (lineValue + lineCommission) / line.quantity
        : line.unit_price;
      return { materialId: line.material_id, unitCost };
    });
  }, [lines, commissions, total, totalComm]);
  const allPricesValid = lines.every((l) => l.unit_price > 0);
  const selectedAccount = accounts.find((a) => a.id === paymentAccountId);
  const canSubmit = allPricesValid && lines.length > 0
    && (!immediatePayment || (paymentAccountId && (!selectedAccount || selectedAccount.current_balance >= total)))
    && commissions.every((c) => c.third_party_id && c.concept && c.commission_value > 0);

  const handleSubmit = () => {
    if (!canSubmit || !id) return;
    liquidate.mutate(
      {
        id,
        data: {
          lines: lines.map((l) => ({
            line_id: l.line_id,
            unit_price: l.unit_price,
          })),
          commissions: commissions
            .filter((c) => c.third_party_id && c.commission_value > 0)
            .map(({ _key, ...rest }) => rest),
          ...(immediatePayment && paymentAccountId
            ? { immediate_payment: true, payment_account_id: paymentAccountId }
            : {}),
          ...(liquidationDate ? { liquidation_date: liquidationDate } : {}),
        },
      },
      {
        onSuccess: () => {
          navigate(`/purchases/${id}`);
        },
      },
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

  if (!purchase) {
    return <div className="text-center py-12 text-slate-500">Compra no encontrada</div>;
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title={`Liquidar Compra #${purchase.purchase_number}`}
        description={`Proveedor: ${purchase.supplier_name} | Fecha: ${formatDate(purchase.date)}`}
      >
        <Button variant="outline" onClick={() => navigate(`/purchases/${id}`)}>
          <ArrowLeft className="h-4 w-4 mr-2" />
          Volver
        </Button>
      </PageHeader>

      {/* Info resumida */}
      <Card className="shadow-sm border-t-[3px] border-t-amber-400">
        <CardContent className="pt-6">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
            <div>
              <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">Proveedor</span>
              <p className="font-medium">{purchase.supplier_name}</p>
            </div>
            <div>
              <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">Fecha</span>
              <p>{formatDate(purchase.date)}</p>
            </div>
            {purchase.vehicle_plate && (
              <div>
                <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">Placa</span>
                <p>{purchase.vehicle_plate}</p>
              </div>
            )}
            {purchase.invoice_number && (
              <div>
                <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">Factura</span>
                <p>{purchase.invoice_number}</p>
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
          {lines.map((line, idx) => (
            <div
              key={line.line_id}
              className={`grid grid-cols-12 gap-2 items-end pb-8 mb-3 relative ${idx < lines.length - 1 ? "border-b border-slate-100" : ""}`}
            >
              <div className="col-span-3">
                {idx === 0 && <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Material</Label>}
                <p className="h-10 flex items-center text-sm">
                  <span className="font-medium">{line.material_name}</span>
                  <span className="text-slate-400 ml-2 text-xs">{line.material_code}</span>
                </p>
              </div>
              <div className="col-span-2">
                {idx === 0 && <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Bodega</Label>}
                <p className="h-10 flex items-center text-sm text-slate-600">
                  {line.warehouse_name ?? "-"}
                </p>
              </div>
              <div className="col-span-2">
                {idx === 0 && <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Cantidad (kg)</Label>}
                <p className="h-10 flex items-center text-sm tabular-nums">
                  {formatWeight(line.quantity)}
                </p>
              </div>
              <div className={linesCostData ? "col-span-2 relative" : "col-span-3 relative"}>
                {idx === 0 && <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Precio Unit. *</Label>}
                <MoneyInput
                  value={line.unit_price}
                  onChange={(v) => updatePrice(line.line_id, v)}
                  placeholder="0"
                  className={line.unit_price <= 0 ? "border-red-300" : ""}
                />
                <div className="absolute left-0 w-max" style={{ top: "100%" }}>
                  <PriceSuggestion
                    suggestedPrice={getSuggestedPrice(line.material_id, "purchase")}
                    onApply={(p) => updatePrice(line.line_id, p)}
                  />
                  {line.unit_price <= 0 && (
                    <p className="text-xs text-red-500 mt-0.5">El precio debe ser mayor a 0</p>
                  )}
                </div>
              </div>
              {linesCostData && (
              <div className="col-span-1 text-right">
                {idx === 0 && <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Costo Unit*</Label>}
                <p className="h-10 flex items-center justify-end text-sm font-medium tabular-nums text-emerald-600">
                  {formatCurrency(linesCostData.find(c => c.materialId === line.material_id)?.unitCost ?? line.unit_price)}
                </p>
              </div>
              )}
              <div className="col-span-2 text-right">
                {idx === 0 && <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Total</Label>}
                <p className="h-10 flex items-center justify-end text-sm font-medium tabular-nums">
                  {formatCurrency(line.quantity * line.unit_price)}
                </p>
              </div>
            </div>
          ))}

          {linesCostData && (
            <p className="text-xs text-slate-500 mt-2">* Costo incluye comision prorrateada</p>
          )}
          <div className="bg-slate-50 rounded-lg p-3 mt-2">
            <div className="flex justify-end">
              <span className="text-lg font-bold">Total: {formatCurrency(total)}</span>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Comisiones */}
      <Card className="shadow-sm">
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle className="text-sm font-semibold uppercase tracking-wider text-slate-500">Comisiones (Opcional)</CardTitle>
          <Button variant="outline" size="sm" onClick={() => setCommissions((p) => [...p, createEmptyCommission()])}>
            <Plus className="h-4 w-4 mr-1" />Agregar Comision
          </Button>
        </CardHeader>
        {commissions.length > 0 && (
          <CardContent className="space-y-0">
            {commissions.map((comm, idx) => (
              <div key={comm._key} className={`grid grid-cols-12 gap-2 items-end pb-3 mb-3 ${idx < commissions.length - 1 ? "border-b border-slate-100" : ""}`}>
                <div className="col-span-3">
                  {idx === 0 && <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Comisionista *</Label>}
                  <EntitySelect value={comm.third_party_id} onChange={(v) => updateCommission(comm._key, "third_party_id", v)} options={payableProviders.map((tp) => ({ id: tp.id, label: tp.name }))} placeholder="Comisionista..." />
                </div>
                <div className="col-span-3">
                  {idx === 0 && <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Concepto *</Label>}
                  <Input value={comm.concept} onChange={(e) => updateCommission(comm._key, "concept", e.target.value)} placeholder="Concepto..." />
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
                <div className="col-span-2">
                  {idx === 0 && <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Valor *</Label>}
                  <Input type="number" min={0} step="0.01" value={comm.commission_value || ""} onChange={(e) => updateCommission(comm._key, "commission_value", parseFloat(e.target.value) || 0)} placeholder={comm.commission_type === "percentage" ? "%" : comm.commission_type === "per_kg" ? "$/kg" : "$"} />
                </div>
                <div className="col-span-1 text-right">
                  {idx === 0 && <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Monto</Label>}
                  <p className="h-10 flex items-center justify-end text-sm font-medium tabular-nums">
                    {comm.commission_type === "percentage"
                      ? formatCurrency((total * comm.commission_value) / 100)
                      : comm.commission_type === "per_kg"
                      ? formatCurrency(totalQuantity * comm.commission_value)
                      : formatCurrency(comm.commission_value)}
                  </p>
                </div>
                <div className="col-span-1">
                  {idx === 0 && <Label className="text-xs">&nbsp;</Label>}
                  <Button variant="ghost" size="sm" onClick={() => setCommissions((p) => p.filter((c) => c._key !== comm._key))} className="text-red-500 hover:text-red-700"><Trash2 className="h-4 w-4" /></Button>
                </div>
              </div>
            ))}
          </CardContent>
        )}
      </Card>

      {/* Resumen Financiero */}
      <Card className="shadow-sm bg-slate-50/50">
        <CardHeader>
          <CardTitle className="text-sm font-semibold uppercase tracking-wider text-slate-500">Resumen Financiero</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="max-w-sm ml-auto space-y-2">
            <div className="flex justify-between text-sm">
              <span className="text-slate-600">Subtotal Materiales</span>
              <span className="font-medium tabular-nums">{formatCurrency(total)}</span>
            </div>
            {totalComm > 0 && (
            <>
            <div className="flex justify-between text-sm">
              <span className="text-slate-600">(+) Comisiones</span>
              <span className="font-medium tabular-nums text-amber-600">{formatCurrency(totalComm)}</span>
            </div>
            <div className="border-t border-slate-200 pt-2" />
            </>
            )}
            <div className="flex justify-between text-sm">
              <span className="text-slate-600 font-semibold">Costo Total Inventario</span>
              <span className="font-bold tabular-nums text-base">{formatCurrency(total + totalComm)}</span>
            </div>
            {totalComm > 0 && (
            <>
            <div className="border-t border-dashed border-slate-200 pt-2" />
            <div className="flex justify-between text-xs text-slate-500">
              <span>CxP Proveedor</span>
              <span className="tabular-nums">{formatCurrency(total)}</span>
            </div>
            <div className="flex justify-between text-xs text-slate-500">
              <span>CxP Comisionistas</span>
              <span className="tabular-nums">{formatCurrency(totalComm)}</span>
            </div>
            </>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Pago inmediato */}
      <Card className="shadow-sm">
        <CardContent className="pt-6 space-y-4">
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
          <div className="border-t border-slate-100" />
          <div className="flex items-center justify-between">
            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Registrar pago inmediato</Label>
              <p className="text-xs text-slate-500 mt-1">Crea el pago al proveedor automaticamente al liquidar.</p>
            </div>
            <Switch checked={immediatePayment} onCheckedChange={setImmediatePayment} />
          </div>
          {immediatePayment && (
            <div className="space-y-2">
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Cuenta de Pago *</Label>
              <EntitySelect
                value={paymentAccountId}
                onChange={setPaymentAccountId}
                options={accounts.map((a) => ({ id: a.id, label: `${a.name} (${formatCurrency(a.current_balance)})` }))}
                placeholder="Seleccionar cuenta..."
              />
              {selectedAccount && selectedAccount.current_balance < total && (
                <p className="text-xs text-red-500">Fondos insuficientes. Disponible: {formatCurrency(selectedAccount.current_balance)}, Requerido: {formatCurrency(total)}</p>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Acciones */}
      <div className="sticky bottom-0 bg-white/95 backdrop-blur-sm border-t border-slate-100 py-4 -mx-6 px-6 mt-6">
        <div className="flex justify-end gap-2">
          <Button variant="outline" onClick={() => navigate(`/purchases/${id}`)}>
            Cancelar
          </Button>
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
