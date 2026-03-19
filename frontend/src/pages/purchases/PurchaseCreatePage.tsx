import { useState, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowLeft, Plus, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Switch } from "@/components/ui/switch";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { PageHeader } from "@/components/shared/PageHeader";
import { EntitySelect } from "@/components/shared/EntitySelect";
import { PriceSuggestion } from "@/components/shared/PriceSuggestion";
import { ConfirmDialog } from "@/components/shared/ConfirmDialog";
import { useCreatePurchase } from "@/hooks/usePurchases";
import { usePriceSuggestions } from "@/hooks/usePriceSuggestions";
import { useSuppliers, usePayableProviders, useMaterials, useWarehouses, useMoneyAccounts } from "@/hooks/useMasterData";
import { purchaseService } from "@/services/purchases";
import { MoneyInput } from "@/components/shared/MoneyInput";
import { formatCurrency, toLocalDateInput } from "@/utils/formatters";
import { ROUTES } from "@/utils/constants";
import { usePermissions } from "@/hooks/usePermissions";
import type { PurchaseLineCreate, PurchaseCommissionCreate } from "@/types/purchase";

interface LineFormData extends PurchaseLineCreate {
  _key: number;
}

interface CommissionFormData extends PurchaseCommissionCreate {
  _key: number;
}

let lineKeyCounter = 0;
let commKeyCounter = 0;

function createEmptyLine(): LineFormData {
  return {
    _key: ++lineKeyCounter,
    material_id: "",
    quantity: 0,
    unit_price: 0,
    warehouse_id: null,
  };
}

function createEmptyCommission(): CommissionFormData {
  return { _key: ++commKeyCounter, third_party_id: "", concept: "", commission_type: "percentage", commission_value: 0 };
}

export default function PurchaseCreatePage() {
  const navigate = useNavigate();
  const createPurchase = useCreatePurchase();

  const { data: suppliersData } = useSuppliers();
  const { data: payableData } = usePayableProviders();
  const { data: materialsData } = useMaterials();
  const { data: warehousesData } = useWarehouses();

  const { data: accountsData } = useMoneyAccounts();

  const suppliers = suppliersData?.items ?? [];
  const payableProviders = payableData?.items ?? [];
  const materials = materialsData?.items ?? [];
  const warehouses = warehousesData?.items ?? [];
  const accounts = accountsData?.items ?? [];
  const { getSuggestedPrice } = usePriceSuggestions();
  const { hasPermission } = usePermissions();
  const canLiquidate = hasPermission("purchases.liquidate");
  const canViewPrices = hasPermission("purchases.view_prices");
  const canEditPrices = hasPermission("purchases.edit_prices");

  const [supplierId, setSupplierId] = useState("");
  const [date, setDate] = useState(toLocalDateInput());
  const [vehiclePlate, setVehiclePlate] = useState("");
  const [invoiceNumber, setInvoiceNumber] = useState("");
  const [notes, setNotes] = useState("");
  const [autoLiquidate, setAutoLiquidate] = useState(false);
  const [immediatePayment, setImmediatePayment] = useState(false);
  const [paymentAccountId, setPaymentAccountId] = useState("");
  const [lines, setLines] = useState<LineFormData[]>([createEmptyLine()]);
  const [commissions, setCommissions] = useState<CommissionFormData[]>([]);
  const [duplicateOpen, setDuplicateOpen] = useState(false);
  const [duplicateCount, setDuplicateCount] = useState(0);
  const [checkingDuplicate, setCheckingDuplicate] = useState(false);

  const updateLine = (key: number, field: keyof PurchaseLineCreate, value: string | number | null) => {
    setLines((prev) =>
      prev.map((l) => (l._key === key ? { ...l, [field]: value } : l)),
    );
  };

  const handleMaterialChange = (key: number, materialId: string) => {
    updateLine(key, "material_id", materialId);
    if (canEditPrices) {
      const line = lines.find((l) => l._key === key);
      if (line && line.unit_price === 0) {
        const suggested = getSuggestedPrice(materialId, "purchase");
        if (suggested) updateLine(key, "unit_price", suggested);
      }
    }
  };

  const removeLine = (key: number) => {
    setLines((prev) => prev.filter((l) => l._key !== key));
  };

  const addLine = () => {
    setLines((prev) => [...prev, createEmptyLine()]);
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
  const isFutureDate = date ? new Date(date) > new Date() : false;

  const canSubmit =
    supplierId &&
    date &&
    !isFutureDate &&
    lines.length > 0 &&
    lines.every((l) => l.material_id && l.quantity > 0 && l.unit_price >= 0) &&
    (!autoLiquidate || lines.every((l) => l.unit_price > 0)) &&
    (!immediatePayment || paymentAccountId !== "") &&
    commissions.every((c) => c.third_party_id && c.concept && c.commission_value > 0);

  const doCreate = () => {
    createPurchase.mutate(
      {
        supplier_id: supplierId,
        date,
        vehicle_plate: vehiclePlate || null,
        invoice_number: invoiceNumber || null,
        notes: notes || null,
        auto_liquidate: autoLiquidate,
        immediate_payment: immediatePayment,
        payment_account_id: immediatePayment ? paymentAccountId : null,
        lines: lines.map(({ _key, ...rest }) => rest),
        commissions: commissions.map(({ _key, ...rest }) => rest),
      },
      {
        onSuccess: (purchase) => {
          navigate(`/purchases/${purchase.id}`);
        },
      },
    );
  };

  const handleSubmit = async () => {
    if (!canSubmit) return;
    setCheckingDuplicate(true);
    try {
      const totalQuantity = lines.reduce((sum, l) => sum + (Number(l.quantity) || 0), 0);
      const { count } = await purchaseService.checkDuplicate(supplierId, date, totalQuantity);
      if (count > 0) {
        setDuplicateCount(count);
        setDuplicateOpen(true);
      } else {
        doCreate();
      }
    } catch {
      doCreate();
    } finally {
      setCheckingDuplicate(false);
    }
  };

  return (
    <div className="space-y-6">
      <PageHeader title="Nueva Compra" description="Registrar una compra de material">
        <Button variant="outline" onClick={() => navigate(ROUTES.PURCHASES)}>
          <ArrowLeft className="h-4 w-4 mr-2" />
          Volver
        </Button>
      </PageHeader>

      {/* Datos generales */}
      <Card className="shadow-sm">
        <CardHeader>
          <CardTitle className="text-sm font-semibold uppercase tracking-wider text-slate-500">Datos Generales</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Proveedor *</Label>
              <EntitySelect
                value={supplierId}
                onChange={setSupplierId}
                options={suppliers.map((s) => ({ id: s.id, label: s.name }))}
                placeholder="Seleccionar proveedor..."
              />
            </div>
            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Fecha *</Label>
              <Input
                type="date"
                value={date}
                onChange={(e) => setDate(e.target.value)}
                className={isFutureDate ? "border-red-300" : ""}
              />
              {isFutureDate && (
                <p className="text-xs text-red-500 mt-0.5">La fecha no puede ser futura</p>
              )}
            </div>
            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Placa Vehiculo</Label>
              <Input
                value={vehiclePlate}
                onChange={(e) => setVehiclePlate(e.target.value)}
                placeholder="ABC-123"
              />
            </div>
            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Numero Factura</Label>
              <Input
                value={invoiceNumber}
                onChange={(e) => setInvoiceNumber(e.target.value)}
                placeholder="FV-001"
              />
            </div>
            <div className="md:col-span-2">
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Notas</Label>
              <Textarea
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                placeholder="Observaciones..."
                rows={2}
              />
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Lineas */}
      <Card className="shadow-sm">
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle className="text-sm font-semibold uppercase tracking-wider text-slate-500">Lineas de Compra</CardTitle>
          <Button variant="outline" size="sm" onClick={addLine}>
            <Plus className="h-4 w-4 mr-1" />
            Agregar Linea
          </Button>
        </CardHeader>
        <CardContent className="space-y-0">
          {lines.map((line, idx) => (
            <div
              key={line._key}
              className={`grid grid-cols-12 gap-2 items-end pb-8 mb-3 relative ${idx < lines.length - 1 ? "border-b border-slate-100" : ""}`}
            >
              <div className={canViewPrices ? "col-span-3" : "col-span-4"}>
                {idx === 0 && <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Material *</Label>}
                <EntitySelect
                  value={line.material_id}
                  onChange={(v) => handleMaterialChange(line._key, v)}
                  options={materials.map((m) => ({ id: m.id, label: `${m.code} - ${m.name}` }))}
                  placeholder="Material..."
                />
              </div>
              <div className={canViewPrices ? "col-span-3" : "col-span-4"}>
                {idx === 0 && <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Bodega</Label>}
                <EntitySelect
                  value={line.warehouse_id ?? ""}
                  onChange={(v) => updateLine(line._key, "warehouse_id", v || null)}
                  options={warehouses.map((w) => ({ id: w.id, label: w.name }))}
                  placeholder="Bodega..."
                />
              </div>
              <div className={canViewPrices ? "col-span-2" : "col-span-3"}>
                {idx === 0 && <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Cantidad (kg) *</Label>}
                <MoneyInput
                  value={line.quantity}
                  onChange={(v) => updateLine(line._key, "quantity", v)}
                  decimals={2}
                  placeholder="0,00"
                />
              </div>
              {canViewPrices && (
              <div className={linesCostData ? "col-span-1 relative" : "col-span-2 relative"}>
                {idx === 0 && <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Precio Unit. {canEditPrices ? "*" : ""}</Label>}
                <MoneyInput
                  value={line.unit_price}
                  onChange={(v) => updateLine(line._key, "unit_price", v)}
                  placeholder="0"
                  disabled={!canEditPrices}
                />
                {canEditPrices && (
                <div className="absolute left-0 w-max" style={{ top: "100%" }}>
                  <PriceSuggestion
                    suggestedPrice={getSuggestedPrice(line.material_id, "purchase")}
                    onApply={(p) => updateLine(line._key, "unit_price", p)}
                  />
                </div>
                )}
              </div>
              )}
              {canViewPrices && linesCostData && (
              <div className="col-span-1 text-right">
                {idx === 0 && <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Costo Unit*</Label>}
                <p className="h-10 flex items-center justify-end text-sm font-medium tabular-nums text-emerald-600">
                  {formatCurrency(linesCostData.find(c => c.materialId === line.material_id)?.unitCost ?? line.unit_price)}
                </p>
              </div>
              )}
              {canViewPrices && (
              <div className="col-span-1 text-right">
                {idx === 0 && <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Total</Label>}
                <p className="h-10 flex items-center justify-end text-sm font-medium tabular-nums">
                  {formatCurrency(line.quantity * line.unit_price)}
                </p>
              </div>
              )}
              <div className="col-span-1">
                {idx === 0 && <Label className="text-xs">&nbsp;</Label>}
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => removeLine(line._key)}
                  disabled={lines.length === 1}
                  className="text-red-500 hover:text-red-700"
                >
                  <Trash2 className="h-4 w-4" />
                </Button>
              </div>
            </div>
          ))}

          {canViewPrices && linesCostData && (
            <p className="text-xs text-slate-500 mt-2">* Costo incluye comision prorrateada</p>
          )}
          {canViewPrices && (
          <div className="bg-slate-50 rounded-lg p-3 mt-2">
            <div className="flex justify-end">
              <span className="text-lg font-bold">Total: {formatCurrency(total)}</span>
            </div>
          </div>
          )}
        </CardContent>
      </Card>

      {/* Comisiones */}
      {canViewPrices && (
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
      )}

      {/* Resumen Financiero */}
      {canViewPrices && (
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
      )}

      {/* Liquidacion */}
      {canLiquidate && (
      <Card className="shadow-sm">
        <CardContent className="pt-6">
          <div className="flex items-center justify-between">
            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Liquidar inmediatamente</Label>
              <p className="text-xs text-slate-500 mt-1">Confirma precios y mueve stock a liquidado. Requiere precios &gt; 0.</p>
            </div>
            <Switch checked={autoLiquidate} onCheckedChange={(v) => { setAutoLiquidate(v); if (!v) { setImmediatePayment(false); setPaymentAccountId(""); } }} />
          </div>
          {autoLiquidate && lines.some((l) => l.unit_price <= 0) && (
            <p className="text-xs text-amber-600 mt-2">Todos los precios deben ser mayores a 0 para liquidar inmediatamente.</p>
          )}
          {autoLiquidate && (
            <div className="flex items-center gap-4 mt-3 p-3 bg-amber-50 rounded-lg border border-amber-200">
              <div className="flex items-center gap-2">
                <Switch
                  checked={immediatePayment}
                  onCheckedChange={(v) => { setImmediatePayment(v); if (!v) setPaymentAccountId(""); }}
                />
                <Label className="text-sm font-medium">Pagar de contado</Label>
              </div>
              {immediatePayment && (
                <div className="flex-1 max-w-xs">
                  <EntitySelect
                    value={paymentAccountId}
                    onChange={setPaymentAccountId}
                    options={accounts.map((a) => ({ id: a.id, label: `${a.name} (${formatCurrency(a.current_balance)})` }))}
                    placeholder="Cuenta de pago..."
                  />
                </div>
              )}
            </div>
          )}
        </CardContent>
      </Card>
      )}

      {/* Acciones */}
      <div className="sticky bottom-0 bg-white/95 backdrop-blur-sm border-t border-slate-100 py-4 -mx-6 px-6 mt-6">
        <div className="flex justify-end gap-2">
          <Button variant="outline" onClick={() => navigate(ROUTES.PURCHASES)}>
            Cancelar
          </Button>
          <Button
            onClick={handleSubmit}
            disabled={!canSubmit || createPurchase.isPending || checkingDuplicate}
            className="bg-emerald-600 hover:bg-emerald-700"
          >
            {checkingDuplicate ? "Verificando..." : createPurchase.isPending ? "Creando..." : "Crear Compra"}
          </Button>
        </div>
      </div>

      <ConfirmDialog
        open={duplicateOpen}
        onOpenChange={setDuplicateOpen}
        title="Posible compra duplicada"
        description={`Ya existen ${duplicateCount} compra(s) del mismo proveedor en esta fecha. ¿Desea crear la compra de todas formas?`}
        confirmLabel="Si, crear"
        variant="default"
        onConfirm={() => {
          setDuplicateOpen(false);
          doCreate();
        }}
      />
    </div>
  );
}
