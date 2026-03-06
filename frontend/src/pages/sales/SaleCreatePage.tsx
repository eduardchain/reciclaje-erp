import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
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
import { useCreateSale } from "@/hooks/useSales";
import { saleService } from "@/services/sales";
import { inventoryService } from "@/services/inventory";
import { usePriceSuggestions } from "@/hooks/usePriceSuggestions";
import { useCustomers, useSuppliers, useMaterials, useWarehouses } from "@/hooks/useMasterData";
import { formatCurrency, formatWeight, toLocalDatetimeInput } from "@/utils/formatters";
import { ROUTES } from "@/utils/constants";
import type { SaleLineCreate, SaleCommissionCreate } from "@/types/sale";

interface LineFormData extends SaleLineCreate {
  _key: number;
}

interface CommissionFormData extends SaleCommissionCreate {
  _key: number;
}

function WarehouseStockIndicator({ materialId, warehouseId, quantity }: { materialId: string; warehouseId: string; quantity: number }) {
  const { data } = useQuery({
    queryKey: ["inventory", "stock-detail", materialId],
    queryFn: () => inventoryService.getStockDetail(materialId),
    enabled: !!materialId && !!warehouseId,
    staleTime: 30_000,
  });
  if (!data || !warehouseId) return null;
  const wh = data.warehouses?.find((w) => w.warehouse_id === warehouseId);
  const stock = wh?.stock ?? 0;
  const insufficient = quantity > 0 && stock < quantity;
  return (
    <div className="text-xs mt-1">
      <span className="text-slate-500">Stock en bodega: </span>
      <span className={insufficient ? "text-amber-600 font-medium" : "text-emerald-600"}>
        {formatWeight(stock)}
      </span>
      {insufficient && (
        <span className="text-amber-600 ml-2">
          — Insuficiente (faltan {formatWeight(quantity - stock)})
        </span>
      )}
    </div>
  );
}

let lineKeyCounter = 0;
let commKeyCounter = 0;

function createEmptyLine(): LineFormData {
  return { _key: ++lineKeyCounter, material_id: "", quantity: 0, unit_price: 0 };
}

function createEmptyCommission(): CommissionFormData {
  return { _key: ++commKeyCounter, third_party_id: "", concept: "", commission_type: "percentage", commission_value: 0 };
}

export default function SaleCreatePage() {
  const navigate = useNavigate();
  const createSale = useCreateSale();

  const { data: customersData } = useCustomers();
  const { data: suppliersData } = useSuppliers();
  const { data: materialsData } = useMaterials();
  const { data: warehousesData } = useWarehouses();

  const customers = customersData?.items ?? [];
  const thirdParties = [...(customersData?.items ?? []), ...(suppliersData?.items ?? [])];
  const materials = materialsData?.items ?? [];
  const warehouses = warehousesData?.items ?? [];
  const { getSuggestedPrice } = usePriceSuggestions();

  const [customerId, setCustomerId] = useState("");
  const [warehouseId, setWarehouseId] = useState("");
  const [date, setDate] = useState(toLocalDatetimeInput());
  const [vehiclePlate, setVehiclePlate] = useState("");
  const [invoiceNumber, setInvoiceNumber] = useState("");
  const [notes, setNotes] = useState("");
  const [autoLiquidate, setAutoLiquidate] = useState(false);
  const [lines, setLines] = useState<LineFormData[]>([createEmptyLine()]);
  const [commissions, setCommissions] = useState<CommissionFormData[]>([]);

  const updateLine = (key: number, field: keyof SaleLineCreate, value: string | number) => {
    setLines((prev) => prev.map((l) => (l._key === key ? { ...l, [field]: value } : l)));
  };

  const handleMaterialChange = (key: number, materialId: string) => {
    updateLine(key, "material_id", materialId);
    const line = lines.find((l) => l._key === key);
    if (line && line.unit_price === 0) {
      const suggested = getSuggestedPrice(materialId, "sale");
      if (suggested) updateLine(key, "unit_price", suggested);
    }
  };

  const updateCommission = (key: number, field: keyof SaleCommissionCreate, value: string | number) => {
    setCommissions((prev) => prev.map((c) => (c._key === key ? { ...c, [field]: value } : c)));
  };

  const total = lines.reduce((sum, l) => sum + l.quantity * l.unit_price, 0);

  const isFutureDate = date ? new Date(date) > new Date() : false;

  const canSubmit =
    customerId &&
    date &&
    !isFutureDate &&
    lines.length > 0 &&
    lines.every((l) => l.material_id && l.quantity > 0 && l.unit_price >= 0) &&
    commissions.every((c) => c.third_party_id && c.concept && c.commission_value > 0);

  const [duplicateOpen, setDuplicateOpen] = useState(false);
  const [duplicateCount, setDuplicateCount] = useState(0);
  const [checkingDuplicate, setCheckingDuplicate] = useState(false);

  const doCreate = () => {
    createSale.mutate(
      {
        customer_id: customerId,
        warehouse_id: warehouseId || null,
        date,
        vehicle_plate: vehiclePlate || null,
        invoice_number: invoiceNumber || null,
        notes: notes || null,
        auto_liquidate: autoLiquidate,
        lines: lines.map(({ _key, ...rest }) => rest),
        commissions: commissions.map(({ _key, ...rest }) => rest),
      },
      { onSuccess: (sale) => navigate(`/sales/${sale.id}`) },
    );
  };

  const handleSubmit = async () => {
    if (!canSubmit) return;
    setCheckingDuplicate(true);
    try {
      const { count } = await saleService.checkDuplicate(customerId, date);
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
      <PageHeader title="Nueva Venta" description="Registrar una venta de material">
        <Button variant="outline" onClick={() => navigate(ROUTES.SALES)}>
          <ArrowLeft className="h-4 w-4 mr-2" />Volver
        </Button>
      </PageHeader>

      {/* Datos generales */}
      <Card className="shadow-sm">
        <CardHeader><CardTitle className="text-sm font-semibold uppercase tracking-wider text-slate-500">Datos Generales</CardTitle></CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Cliente *</Label>
              <EntitySelect value={customerId} onChange={setCustomerId} options={customers.map((c) => ({ id: c.id, label: c.name }))} placeholder="Seleccionar cliente..." />
            </div>
            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Bodega de Salida</Label>
              <EntitySelect value={warehouseId} onChange={setWarehouseId} options={warehouses.map((w) => ({ id: w.id, label: w.name }))} placeholder="Seleccionar bodega..." />
            </div>
            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Fecha *</Label>
              <Input type="datetime-local" value={date} onChange={(e) => setDate(e.target.value)} className={isFutureDate ? "border-red-300" : ""} />
              {isFutureDate && <p className="text-xs text-red-500 mt-0.5">La fecha no puede ser futura</p>}
            </div>
            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Placa Vehiculo</Label>
              <Input value={vehiclePlate} onChange={(e) => setVehiclePlate(e.target.value)} placeholder="ABC-123" />
            </div>
            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Numero Factura</Label>
              <Input value={invoiceNumber} onChange={(e) => setInvoiceNumber(e.target.value)} placeholder="FV-001" />
            </div>
            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Notas</Label>
              <Textarea value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="Observaciones..." rows={2} />
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Lineas */}
      <Card className="shadow-sm">
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle className="text-sm font-semibold uppercase tracking-wider text-slate-500">Lineas de Venta</CardTitle>
          <Button variant="outline" size="sm" onClick={() => setLines((p) => [...p, createEmptyLine()])}>
            <Plus className="h-4 w-4 mr-1" />Agregar Linea
          </Button>
        </CardHeader>
        <CardContent className="space-y-0">
          {lines.map((line, idx) => {
            const mat = materials.find((m) => m.id === line.material_id);
            const avgCost = mat?.current_average_cost ?? 0;
            const lineProfit = line.unit_price > 0 && avgCost > 0 ? (line.unit_price - avgCost) * line.quantity : 0;
            return (
            <div key={line._key} className={`grid grid-cols-12 gap-2 items-end pb-3 mb-3 ${idx < lines.length - 1 ? "border-b border-slate-100" : ""}`}>
              <div className="col-span-3">
                {idx === 0 && <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Material *</Label>}
                <EntitySelect value={line.material_id} onChange={(v) => handleMaterialChange(line._key, v)} options={materials.map((m) => ({ id: m.id, label: `${m.code} - ${m.name}` }))} placeholder="Material..." />
              </div>
              <div className="col-span-2">
                {idx === 0 && <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Cantidad (kg) *</Label>}
                <Input type="number" min={0} step="0.01" value={line.quantity || ""} onChange={(e) => updateLine(line._key, "quantity", parseFloat(e.target.value) || 0)} placeholder="0.00" />
                <WarehouseStockIndicator materialId={line.material_id} warehouseId={warehouseId} quantity={line.quantity} />
              </div>
              <div className="col-span-1">
                {idx === 0 && <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Costo</Label>}
                <p className="h-10 flex items-center text-sm tabular-nums text-slate-400">{avgCost > 0 ? formatCurrency(avgCost) : "-"}</p>
              </div>
              <div className="col-span-2">
                {idx === 0 && <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Precio *</Label>}
                <Input type="number" min={0} step="1" value={line.unit_price || ""} onChange={(e) => updateLine(line._key, "unit_price", parseFloat(e.target.value) || 0)} placeholder="0" />
                <PriceSuggestion suggestedPrice={getSuggestedPrice(line.material_id, "sale")} onApply={(p) => updateLine(line._key, "unit_price", p)} />
              </div>
              <div className="col-span-2 text-right">
                {idx === 0 && <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Total</Label>}
                <p className="h-10 flex items-center justify-end text-sm font-medium tabular-nums">{formatCurrency(line.quantity * line.unit_price)}</p>
              </div>
              <div className="col-span-1 text-right">
                {idx === 0 && <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Utilidad</Label>}
                <p className={`h-10 flex items-center justify-end text-sm font-medium tabular-nums ${lineProfit >= 0 ? "text-emerald-600" : "text-red-600"}`}>
                  {line.unit_price > 0 && avgCost > 0 ? formatCurrency(lineProfit) : "-"}
                </p>
              </div>
              <div className="col-span-1">
                {idx === 0 && <Label className="text-xs">&nbsp;</Label>}
                <Button variant="ghost" size="sm" onClick={() => setLines((p) => p.filter((l) => l._key !== line._key))} disabled={lines.length === 1} className="text-red-500 hover:text-red-700"><Trash2 className="h-4 w-4" /></Button>
              </div>
            </div>
            );
          })}
          {(() => {
            const estProfit = lines.reduce((sum, l) => {
              const mat = materials.find((m) => m.id === l.material_id);
              const avgCost = mat?.current_average_cost ?? 0;
              return sum + (l.unit_price > 0 && avgCost > 0 ? (l.unit_price - avgCost) * l.quantity : 0);
            }, 0);
            const totalComm = commissions.reduce((sum, c) => {
              return sum + (c.commission_type === "percentage" ? (total * c.commission_value) / 100 : c.commission_value);
            }, 0);
            const netProfit = estProfit - totalComm;
            const margin = total > 0 ? (estProfit / total) * 100 : 0;
            return (
              <div className="bg-slate-50 rounded-lg p-3 mt-2 space-y-1">
                <div className="flex justify-end gap-6">
                  <span className="text-lg font-bold">Total: {formatCurrency(total)}</span>
                  {estProfit !== 0 && (
                    <span className={`text-lg font-bold ${estProfit >= 0 ? "text-emerald-600" : "text-red-600"}`}>
                      Util. Bruta: {formatCurrency(estProfit)} ({margin.toFixed(1)}%)
                    </span>
                  )}
                </div>
                {totalComm > 0 && (
                  <div className="flex justify-end gap-6 text-sm">
                    <span className="text-amber-600">Comisiones: -{formatCurrency(totalComm)}</span>
                    <span className={`font-semibold ${netProfit >= 0 ? "text-emerald-600" : "text-red-600"}`}>
                      Util. Neta: {formatCurrency(netProfit)}
                    </span>
                  </div>
                )}
              </div>
            );
          })()}
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
                  <EntitySelect value={comm.third_party_id} onChange={(v) => updateCommission(comm._key, "third_party_id", v)} options={thirdParties.map((tp) => ({ id: tp.id, label: tp.name }))} placeholder="Tercero..." />
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
                    </SelectContent>
                  </Select>
                </div>
                <div className="col-span-2">
                  {idx === 0 && <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Valor *</Label>}
                  <Input type="number" min={0} step="0.01" value={comm.commission_value || ""} onChange={(e) => updateCommission(comm._key, "commission_value", parseFloat(e.target.value) || 0)} placeholder={comm.commission_type === "percentage" ? "%" : "$"} />
                </div>
                <div className="col-span-1 text-right">
                  {idx === 0 && <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Monto</Label>}
                  <p className="h-10 flex items-center justify-end text-sm font-medium tabular-nums">
                    {comm.commission_type === "percentage"
                      ? formatCurrency((total * comm.commission_value) / 100)
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

      {/* Liquidacion */}
      <Card className="shadow-sm">
        <CardContent className="pt-6">
          <div className="flex items-center justify-between">
            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Liquidar inmediatamente</Label>
              <p className="text-xs text-slate-500 mt-1">Si se activa, la venta se liquidara al crearla (confirma precios y aplica saldo al cliente)</p>
            </div>
            <Switch checked={autoLiquidate} onCheckedChange={setAutoLiquidate} />
          </div>
        </CardContent>
      </Card>

      {/* Acciones */}
      <div className="sticky bottom-0 bg-white/95 backdrop-blur-sm border-t border-slate-100 py-4 -mx-6 px-6 mt-6">
        <div className="flex justify-end gap-2">
          <Button variant="outline" onClick={() => navigate(ROUTES.SALES)}>Cancelar</Button>
          <Button onClick={handleSubmit} disabled={!canSubmit || createSale.isPending || checkingDuplicate} className="bg-emerald-600 hover:bg-emerald-700">
            {createSale.isPending || checkingDuplicate ? "Creando..." : "Crear Venta"}
          </Button>
        </div>
      </div>

      <ConfirmDialog
        open={duplicateOpen}
        onOpenChange={setDuplicateOpen}
        title="Posible venta duplicada"
        description={`Ya existen ${duplicateCount} venta(s) del mismo cliente en esta fecha. ¿Desea crear la venta de todas formas?`}
        confirmLabel="Sí, crear"
        onConfirm={() => { setDuplicateOpen(false); doCreate(); }}
      />
    </div>
  );
}
