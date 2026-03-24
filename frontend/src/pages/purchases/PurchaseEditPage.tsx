import { useState, useEffect, useMemo } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, Plus, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { PageHeader } from "@/components/shared/PageHeader";
import { EntitySelect } from "@/components/shared/EntitySelect";
import { PriceSuggestion } from "@/components/shared/PriceSuggestion";
import { usePurchase, useUpdatePurchase } from "@/hooks/usePurchases";
import { usePriceSuggestions } from "@/hooks/usePriceSuggestions";
import { useSuppliers, usePayableProviders, useMaterials, useWarehouses } from "@/hooks/useMasterData";
import { MoneyInput } from "@/components/shared/MoneyInput";
import { ConfirmDialog } from "@/components/shared/ConfirmDialog";
import { formatCurrency, utcToLocalDateInput } from "@/utils/formatters";
import { purchaseService } from "@/services/purchases";
import type { PurchaseLineCreate, PurchaseCommissionCreate } from "@/types/purchase";

interface LineFormData extends PurchaseLineCreate {
  _key: number;
}

interface CommissionFormData extends PurchaseCommissionCreate {
  _key: number;
}

let lineKeyCounter = 1000;
let commKeyCounter = 1000;

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

export default function PurchaseEditPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const updatePurchase = useUpdatePurchase();

  const { data: purchase, isLoading: loadingPurchase } = usePurchase(id!);
  const { data: suppliersData } = useSuppliers();
  const { data: payableData } = usePayableProviders();
  const { data: materialsData } = useMaterials();
  const { data: warehousesData } = useWarehouses();

  const suppliers = suppliersData?.items ?? [];
  const payableProviders = payableData?.items ?? [];
  const materials = materialsData?.items ?? [];
  const warehouses = warehousesData?.items ?? [];
  const { getSuggestedPrice } = usePriceSuggestions();

  const [supplierId, setSupplierId] = useState("");
  const [date, setDate] = useState("");
  const [vehiclePlate, setVehiclePlate] = useState("");
  const [invoiceNumber, setInvoiceNumber] = useState("");
  const [notes, setNotes] = useState("");
  const [lines, setLines] = useState<LineFormData[]>([]);
  const [commissions, setCommissions] = useState<CommissionFormData[]>([]);
  const [initialized, setInitialized] = useState(false);

  // Pre-populate form with purchase data
  useEffect(() => {
    if (purchase && !initialized) {
      setSupplierId(purchase.supplier_id);
      setDate(utcToLocalDateInput(purchase.date));
      setVehiclePlate(purchase.vehicle_plate ?? "");
      setInvoiceNumber(purchase.invoice_number ?? "");
      setNotes(purchase.notes ?? "");
      setLines(
        purchase.lines.map((line) => ({
          _key: ++lineKeyCounter,
          material_id: line.material_id,
          quantity: line.quantity,
          unit_price: line.unit_price,
          warehouse_id: line.warehouse_id,
        }))
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
      setInitialized(true);
    }
  }, [purchase, initialized]);

  // Redirect si no se puede editar
  useEffect(() => {
    if (purchase && (purchase.status !== "registered" || purchase.double_entry_id)) {
      navigate(`/purchases/${id}`, { replace: true });
    }
  }, [purchase, id, navigate]);

  const updateLine = (key: number, field: keyof PurchaseLineCreate, value: string | number | null) => {
    setLines((prev) =>
      prev.map((l) => (l._key === key ? { ...l, [field]: value } : l))
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
    commissions.every((c) => c.third_party_id && c.concept && c.commission_value > 0);

  const [invoiceOpen, setInvoiceOpen] = useState(false);
  const [invoiceMatches, setInvoiceMatches] = useState<Array<{ id: string; number: number; date: string; status: string; third_party_name: string; total_amount: number }>>([]);

  const doUpdate = () => {
    if (!id) return;
    updatePurchase.mutate(
      {
        id,
        data: {
          supplier_id: supplierId,
          date,
          vehicle_plate: vehiclePlate || null,
          invoice_number: invoiceNumber || null,
          notes: notes || null,
          lines: lines.map(({ _key, ...rest }) => rest),
          commissions: commissions.map(({ _key, ...rest }) => rest),
        },
      },
      { onSuccess: () => navigate(`/purchases/${id}`) }
    );
  };

  const handleSubmit = async () => {
    if (!canSubmit || !id) return;
    if (invoiceNumber.trim()) {
      try {
        const { matches } = await purchaseService.checkInvoice(invoiceNumber.trim(), id);
        if (matches.length > 0) {
          setInvoiceMatches(matches);
          setInvoiceOpen(true);
          return;
        }
      } catch { /* continuar */ }
    }
    doUpdate();
  };

  if (loadingPurchase) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-10 w-64" />
        <Skeleton className="h-64 rounded-lg" />
        <Skeleton className="h-48 rounded-lg" />
      </div>
    );
  }

  if (!purchase) return null;

  return (
    <div className="space-y-6">
      <PageHeader
        title={`Editar Compra #${purchase.purchase_number}`}
        description="Modificar datos y lineas de la compra"
      >
        <Button variant="outline" onClick={() => navigate(`/purchases/${id}`)}>
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
              <div className={linesCostData ? "col-span-1 relative" : "col-span-2 relative"}>
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
              {linesCostData && (
              <div className="col-span-1 text-right">
                {idx === 0 && <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Costo Unit*</Label>}
                <p className="h-10 flex items-center justify-end text-sm font-medium tabular-nums text-emerald-600">
                  {formatCurrency(linesCostData.find(c => c.materialId === line.material_id)?.unitCost ?? line.unit_price)}
                </p>
              </div>
              )}
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
            <div className="flex justify-between text-sm">
              <span className="text-slate-600">(+) Comisiones</span>
              <span className="font-medium tabular-nums text-amber-600">{formatCurrency(totalComm)}</span>
            </div>
            )}
            <div className="border-t border-slate-200 pt-2" />
            <div className="flex justify-between text-sm">
              <span className="text-slate-600 font-semibold">Costo Total Inventario</span>
              <span className="font-bold tabular-nums text-base">{formatCurrency(total + totalComm)}</span>
            </div>
          </div>
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
            disabled={!canSubmit || updatePurchase.isPending}
            className="bg-emerald-600 hover:bg-emerald-700"
          >
            {updatePurchase.isPending ? "Guardando..." : "Guardar Cambios"}
          </Button>
        </div>
      </div>
      <ConfirmDialog
        open={invoiceOpen}
        onOpenChange={setInvoiceOpen}
        title="Factura duplicada"
        description={`El numero de factura "${invoiceNumber}" ya existe en:`}
        confirmLabel="Guardar de todas formas"
        variant="default"
        onConfirm={() => { setInvoiceOpen(false); doUpdate(); }}
      >
        <div className="mt-2 space-y-1 text-sm">
          {invoiceMatches.map((m) => (
            <div key={m.id} className="flex justify-between bg-slate-50 rounded px-3 py-2">
              <span>Compra #{m.number} — {m.third_party_name}</span>
              <span className="text-slate-500">{m.date?.split("T")[0]}</span>
            </div>
          ))}
        </div>
      </ConfirmDialog>
    </div>
  );
}
