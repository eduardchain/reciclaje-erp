import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowLeft, Plus, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Switch } from "@/components/ui/switch";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { PageHeader } from "@/components/shared/PageHeader";
import { EntitySelect } from "@/components/shared/EntitySelect";
import { PriceSuggestion } from "@/components/shared/PriceSuggestion";
import { ConfirmDialog } from "@/components/shared/ConfirmDialog";
import { useCreatePurchase } from "@/hooks/usePurchases";
import { usePriceSuggestions } from "@/hooks/usePriceSuggestions";
import { useSuppliers, useMaterials, useWarehouses, useMoneyAccounts } from "@/hooks/useMasterData";
import { purchaseService } from "@/services/purchases";
import { MoneyInput } from "@/components/shared/MoneyInput";
import { formatCurrency, toLocalDateInput } from "@/utils/formatters";
import { ROUTES } from "@/utils/constants";
import type { PurchaseLineCreate } from "@/types/purchase";

interface LineFormData extends PurchaseLineCreate {
  _key: number;
}

let lineKeyCounter = 0;

function createEmptyLine(): LineFormData {
  return {
    _key: ++lineKeyCounter,
    material_id: "",
    quantity: 0,
    unit_price: 0,
    warehouse_id: null,
  };
}

export default function PurchaseCreatePage() {
  const navigate = useNavigate();
  const createPurchase = useCreatePurchase();

  const { data: suppliersData } = useSuppliers();
  const { data: materialsData } = useMaterials();
  const { data: warehousesData } = useWarehouses();

  const { data: accountsData } = useMoneyAccounts();

  const suppliers = suppliersData?.items ?? [];
  const materials = materialsData?.items ?? [];
  const warehouses = warehousesData?.items ?? [];
  const accounts = accountsData?.items ?? [];
  const { getSuggestedPrice } = usePriceSuggestions();

  const [supplierId, setSupplierId] = useState("");
  const [date, setDate] = useState(toLocalDateInput());
  const [vehiclePlate, setVehiclePlate] = useState("");
  const [invoiceNumber, setInvoiceNumber] = useState("");
  const [notes, setNotes] = useState("");
  const [autoLiquidate, setAutoLiquidate] = useState(false);
  const [immediatePayment, setImmediatePayment] = useState(false);
  const [paymentAccountId, setPaymentAccountId] = useState("");
  const [lines, setLines] = useState<LineFormData[]>([createEmptyLine()]);
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
    const line = lines.find((l) => l._key === key);
    if (line && line.unit_price === 0) {
      const suggested = getSuggestedPrice(materialId, "purchase");
      if (suggested) updateLine(key, "unit_price", suggested);
    }
  };

  const removeLine = (key: number) => {
    setLines((prev) => prev.filter((l) => l._key !== key));
  };

  const addLine = () => {
    setLines((prev) => [...prev, createEmptyLine()]);
  };

  const total = lines.reduce((sum, l) => sum + l.quantity * l.unit_price, 0);
  const isFutureDate = date ? new Date(date) > new Date() : false;

  const canSubmit =
    supplierId &&
    date &&
    !isFutureDate &&
    lines.length > 0 &&
    lines.every((l) => l.material_id && l.quantity > 0 && l.unit_price >= 0) &&
    (!autoLiquidate || lines.every((l) => l.unit_price > 0)) &&
    (!immediatePayment || paymentAccountId !== "");

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
              <div className="col-span-3">
                {idx === 0 && <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Material *</Label>}
                <EntitySelect
                  value={line.material_id}
                  onChange={(v) => handleMaterialChange(line._key, v)}
                  options={materials.map((m) => ({ id: m.id, label: `${m.code} - ${m.name}` }))}
                  placeholder="Material..."
                />
              </div>
              <div className="col-span-3">
                {idx === 0 && <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Bodega</Label>}
                <EntitySelect
                  value={line.warehouse_id ?? ""}
                  onChange={(v) => updateLine(line._key, "warehouse_id", v || null)}
                  options={warehouses.map((w) => ({ id: w.id, label: w.name }))}
                  placeholder="Bodega..."
                />
              </div>
              <div className="col-span-2">
                {idx === 0 && <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Cantidad (kg) *</Label>}
                <MoneyInput
                  value={line.quantity}
                  onChange={(v) => updateLine(line._key, "quantity", v)}
                  decimals={2}
                  placeholder="0,00"
                />
              </div>
              <div className="col-span-2 relative">
                {idx === 0 && <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Precio Unit. *</Label>}
                <MoneyInput
                  value={line.unit_price}
                  onChange={(v) => updateLine(line._key, "unit_price", v)}
                  placeholder="0"
                />
                <div className="absolute left-0 w-max" style={{ top: "100%" }}>
                  <PriceSuggestion
                    suggestedPrice={getSuggestedPrice(line.material_id, "purchase")}
                    onApply={(p) => updateLine(line._key, "unit_price", p)}
                  />
                </div>
              </div>
              <div className="col-span-1 text-right">
                {idx === 0 && <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Total</Label>}
                <p className="h-10 flex items-center justify-end text-sm font-medium tabular-nums">
                  {formatCurrency(line.quantity * line.unit_price)}
                </p>
              </div>
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

          <div className="bg-slate-50 rounded-lg p-3 mt-2">
            <div className="flex justify-end">
              <span className="text-lg font-bold">Total: {formatCurrency(total)}</span>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Liquidacion */}
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
