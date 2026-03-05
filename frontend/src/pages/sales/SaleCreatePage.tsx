import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowLeft, Plus, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Switch } from "@/components/ui/switch";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { PageHeader } from "@/components/shared/PageHeader";
import { EntitySelect } from "@/components/shared/EntitySelect";
import { useCreateSale } from "@/hooks/useSales";
import { useCustomers, useSuppliers, useMaterials, useWarehouses, useMoneyAccounts } from "@/hooks/useMasterData";
import { formatCurrency } from "@/utils/formatters";
import { ROUTES } from "@/utils/constants";
import type { SaleLineCreate, SaleCommissionCreate } from "@/types/sale";

interface LineFormData extends SaleLineCreate {
  _key: number;
}

interface CommissionFormData extends SaleCommissionCreate {
  _key: number;
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
  const { data: accountsData } = useMoneyAccounts();

  const customers = customersData?.items ?? [];
  const thirdParties = [...(customersData?.items ?? []), ...(suppliersData?.items ?? [])];
  const materials = materialsData?.items ?? [];
  const warehouses = warehousesData?.items ?? [];
  const accounts = accountsData?.items ?? [];

  const [customerId, setCustomerId] = useState("");
  const [warehouseId, setWarehouseId] = useState("");
  const [date, setDate] = useState(new Date().toISOString().slice(0, 16));
  const [vehiclePlate, setVehiclePlate] = useState("");
  const [invoiceNumber, setInvoiceNumber] = useState("");
  const [notes, setNotes] = useState("");
  const [autoLiquidate, setAutoLiquidate] = useState(false);
  const [paymentAccountId, setPaymentAccountId] = useState("");
  const [lines, setLines] = useState<LineFormData[]>([createEmptyLine()]);
  const [commissions, setCommissions] = useState<CommissionFormData[]>([]);

  const updateLine = (key: number, field: keyof SaleLineCreate, value: string | number) => {
    setLines((prev) => prev.map((l) => (l._key === key ? { ...l, [field]: value } : l)));
  };

  const updateCommission = (key: number, field: keyof SaleCommissionCreate, value: string | number) => {
    setCommissions((prev) => prev.map((c) => (c._key === key ? { ...c, [field]: value } : c)));
  };

  const total = lines.reduce((sum, l) => sum + l.quantity * l.unit_price, 0);

  const canSubmit =
    customerId &&
    date &&
    lines.length > 0 &&
    lines.every((l) => l.material_id && l.quantity > 0 && l.unit_price >= 0) &&
    commissions.every((c) => c.third_party_id && c.concept && c.commission_value > 0) &&
    (!autoLiquidate || paymentAccountId);

  const handleSubmit = () => {
    if (!canSubmit) return;
    createSale.mutate(
      {
        customer_id: customerId,
        warehouse_id: warehouseId || null,
        date,
        vehicle_plate: vehiclePlate || null,
        invoice_number: invoiceNumber || null,
        notes: notes || null,
        auto_liquidate: autoLiquidate,
        payment_account_id: autoLiquidate ? paymentAccountId : null,
        lines: lines.map(({ _key, ...rest }) => rest),
        commissions: commissions.map(({ _key, ...rest }) => rest),
      },
      { onSuccess: (sale) => navigate(`/sales/${sale.id}`) },
    );
  };

  return (
    <div className="space-y-6">
      <PageHeader title="Nueva Venta" description="Registrar una venta de material">
        <Button variant="outline" onClick={() => navigate(ROUTES.SALES)}>
          <ArrowLeft className="h-4 w-4 mr-2" />Volver
        </Button>
      </PageHeader>

      {/* Datos generales */}
      <Card>
        <CardHeader><CardTitle className="text-base">Datos Generales</CardTitle></CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <Label>Cliente *</Label>
              <EntitySelect value={customerId} onChange={setCustomerId} options={customers.map((c) => ({ id: c.id, label: c.name }))} placeholder="Seleccionar cliente..." />
            </div>
            <div>
              <Label>Bodega de Salida</Label>
              <EntitySelect value={warehouseId} onChange={setWarehouseId} options={warehouses.map((w) => ({ id: w.id, label: w.name }))} placeholder="Seleccionar bodega..." />
            </div>
            <div>
              <Label>Fecha *</Label>
              <Input type="datetime-local" value={date} onChange={(e) => setDate(e.target.value)} />
            </div>
            <div>
              <Label>Placa Vehiculo</Label>
              <Input value={vehiclePlate} onChange={(e) => setVehiclePlate(e.target.value)} placeholder="ABC-123" />
            </div>
            <div>
              <Label>Numero Factura</Label>
              <Input value={invoiceNumber} onChange={(e) => setInvoiceNumber(e.target.value)} placeholder="FV-001" />
            </div>
            <div>
              <Label>Notas</Label>
              <Textarea value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="Observaciones..." rows={2} />
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Lineas */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle className="text-base">Lineas de Venta</CardTitle>
          <Button variant="outline" size="sm" onClick={() => setLines((p) => [...p, createEmptyLine()])}>
            <Plus className="h-4 w-4 mr-1" />Agregar Linea
          </Button>
        </CardHeader>
        <CardContent className="space-y-4">
          {lines.map((line, idx) => (
            <div key={line._key} className="grid grid-cols-12 gap-2 items-end">
              <div className="col-span-4">
                {idx === 0 && <Label className="text-xs">Material *</Label>}
                <EntitySelect value={line.material_id} onChange={(v) => updateLine(line._key, "material_id", v)} options={materials.map((m) => ({ id: m.id, label: `${m.code} - ${m.name}` }))} placeholder="Material..." />
              </div>
              <div className="col-span-3">
                {idx === 0 && <Label className="text-xs">Cantidad (kg) *</Label>}
                <Input type="number" min={0} step="0.01" value={line.quantity || ""} onChange={(e) => updateLine(line._key, "quantity", parseFloat(e.target.value) || 0)} placeholder="0.00" />
              </div>
              <div className="col-span-2">
                {idx === 0 && <Label className="text-xs">Precio Unit. *</Label>}
                <Input type="number" min={0} step="1" value={line.unit_price || ""} onChange={(e) => updateLine(line._key, "unit_price", parseFloat(e.target.value) || 0)} placeholder="0" />
              </div>
              <div className="col-span-2 text-right">
                {idx === 0 && <Label className="text-xs">Total</Label>}
                <p className="h-10 flex items-center justify-end text-sm font-medium tabular-nums">{formatCurrency(line.quantity * line.unit_price)}</p>
              </div>
              <div className="col-span-1">
                {idx === 0 && <Label className="text-xs">&nbsp;</Label>}
                <Button variant="ghost" size="sm" onClick={() => setLines((p) => p.filter((l) => l._key !== line._key))} disabled={lines.length === 1} className="text-red-500 hover:text-red-700"><Trash2 className="h-4 w-4" /></Button>
              </div>
            </div>
          ))}
          <Separator />
          <div className="flex justify-end"><span className="text-lg font-bold">Total: {formatCurrency(total)}</span></div>
        </CardContent>
      </Card>

      {/* Comisiones */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle className="text-base">Comisiones (Opcional)</CardTitle>
          <Button variant="outline" size="sm" onClick={() => setCommissions((p) => [...p, createEmptyCommission()])}>
            <Plus className="h-4 w-4 mr-1" />Agregar Comision
          </Button>
        </CardHeader>
        {commissions.length > 0 && (
          <CardContent className="space-y-4">
            {commissions.map((comm, idx) => (
              <div key={comm._key} className="grid grid-cols-12 gap-2 items-end">
                <div className="col-span-3">
                  {idx === 0 && <Label className="text-xs">Comisionista *</Label>}
                  <EntitySelect value={comm.third_party_id} onChange={(v) => updateCommission(comm._key, "third_party_id", v)} options={thirdParties.map((tp) => ({ id: tp.id, label: tp.name }))} placeholder="Tercero..." />
                </div>
                <div className="col-span-3">
                  {idx === 0 && <Label className="text-xs">Concepto *</Label>}
                  <Input value={comm.concept} onChange={(e) => updateCommission(comm._key, "concept", e.target.value)} placeholder="Concepto..." />
                </div>
                <div className="col-span-2">
                  {idx === 0 && <Label className="text-xs">Tipo</Label>}
                  <Select value={comm.commission_type} onValueChange={(v) => updateCommission(comm._key, "commission_type", v)}>
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="percentage">Porcentaje</SelectItem>
                      <SelectItem value="fixed">Fijo</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="col-span-2">
                  {idx === 0 && <Label className="text-xs">Valor *</Label>}
                  <Input type="number" min={0} step="0.01" value={comm.commission_value || ""} onChange={(e) => updateCommission(comm._key, "commission_value", parseFloat(e.target.value) || 0)} placeholder={comm.commission_type === "percentage" ? "%" : "$"} />
                </div>
                <div className="col-span-1 text-right">
                  {idx === 0 && <Label className="text-xs">Monto</Label>}
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
      <Card>
        <CardContent className="pt-6">
          <div className="flex items-center justify-between">
            <div>
              <Label>Cobrar inmediatamente</Label>
              <p className="text-xs text-gray-500">Si se activa, la venta se cobrara al crearla</p>
            </div>
            <Switch checked={autoLiquidate} onCheckedChange={setAutoLiquidate} />
          </div>
          {autoLiquidate && (
            <div className="mt-4">
              <Label>Cuenta de Cobro *</Label>
              <EntitySelect value={paymentAccountId} onChange={setPaymentAccountId} options={accounts.map((a) => ({ id: a.id, label: `${a.name} (${formatCurrency(a.current_balance)})` }))} placeholder="Seleccionar cuenta..." />
            </div>
          )}
        </CardContent>
      </Card>

      {/* Acciones */}
      <div className="flex justify-end gap-2">
        <Button variant="outline" onClick={() => navigate(ROUTES.SALES)}>Cancelar</Button>
        <Button onClick={handleSubmit} disabled={!canSubmit || createSale.isPending} className="bg-green-600 hover:bg-green-700">
          {createSale.isPending ? "Creando..." : "Crear Venta"}
        </Button>
      </div>
    </div>
  );
}
