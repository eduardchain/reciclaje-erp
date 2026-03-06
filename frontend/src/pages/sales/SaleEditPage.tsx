import { useState, useEffect } from "react";
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
import { useSale, useUpdateSale } from "@/hooks/useSales";
import { useCustomers, useSuppliers, useMaterials, useWarehouses } from "@/hooks/useMasterData";
import { formatCurrency } from "@/utils/formatters";
import type { SaleLineCreate, SaleCommissionCreate } from "@/types/sale";

interface LineFormData extends SaleLineCreate {
  _key: number;
}

interface CommissionFormData extends SaleCommissionCreate {
  _key: number;
}

let lineKeyCounter = 2000;
let commKeyCounter = 3000;

function createEmptyLine(): LineFormData {
  return { _key: ++lineKeyCounter, material_id: "", quantity: 0, unit_price: 0 };
}

function createEmptyCommission(): CommissionFormData {
  return { _key: ++commKeyCounter, third_party_id: "", concept: "", commission_type: "percentage", commission_value: 0 };
}

export default function SaleEditPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const updateSale = useUpdateSale();

  const { data: sale, isLoading: loadingSale } = useSale(id!);
  const { data: customersData } = useCustomers();
  const { data: suppliersData } = useSuppliers();
  const { data: materialsData } = useMaterials();
  const { data: warehousesData } = useWarehouses();

  const customers = customersData?.items ?? [];
  const thirdParties = [...(customersData?.items ?? []), ...(suppliersData?.items ?? [])];
  const materials = materialsData?.items ?? [];
  const warehouses = warehousesData?.items ?? [];

  const [customerId, setCustomerId] = useState("");
  const [warehouseId, setWarehouseId] = useState("");
  const [date, setDate] = useState("");
  const [vehiclePlate, setVehiclePlate] = useState("");
  const [invoiceNumber, setInvoiceNumber] = useState("");
  const [notes, setNotes] = useState("");
  const [lines, setLines] = useState<LineFormData[]>([]);
  const [commissions, setCommissions] = useState<CommissionFormData[]>([]);
  const [initialized, setInitialized] = useState(false);

  // Pre-populate form
  useEffect(() => {
    if (sale && !initialized) {
      setCustomerId(sale.customer_id);
      setWarehouseId(sale.warehouse_id ?? "");
      setDate(sale.date.slice(0, 16));
      setVehiclePlate(sale.vehicle_plate ?? "");
      setInvoiceNumber(sale.invoice_number ?? "");
      setNotes(sale.notes ?? "");
      setLines(
        sale.lines.map((line) => ({
          _key: ++lineKeyCounter,
          material_id: line.material_id,
          quantity: line.quantity,
          unit_price: line.unit_price,
        }))
      );
      setCommissions(
        sale.commissions.map((comm) => ({
          _key: ++commKeyCounter,
          third_party_id: comm.third_party_id,
          concept: comm.concept,
          commission_type: comm.commission_type,
          commission_value: comm.commission_value,
        }))
      );
      setInitialized(true);
    }
  }, [sale, initialized]);

  // Redirect si no se puede editar
  useEffect(() => {
    if (sale && (sale.status !== "registered" || sale.double_entry_id)) {
      navigate(`/sales/${id}`, { replace: true });
    }
  }, [sale, id, navigate]);

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
    commissions.every((c) => c.third_party_id && c.concept && c.commission_value > 0);

  const handleSubmit = () => {
    if (!canSubmit || !id) return;
    updateSale.mutate(
      {
        id,
        data: {
          customer_id: customerId,
          warehouse_id: warehouseId || null,
          date,
          vehicle_plate: vehiclePlate || null,
          invoice_number: invoiceNumber || null,
          notes: notes || null,
          lines: lines.map(({ _key, ...rest }) => rest),
          commissions: commissions.map(({ _key, ...rest }) => rest),
        },
      },
      {
        onSuccess: () => {
          navigate(`/sales/${id}`);
        },
      }
    );
  };

  if (loadingSale) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-10 w-64" />
        <Skeleton className="h-64 rounded-lg" />
        <Skeleton className="h-48 rounded-lg" />
      </div>
    );
  }

  if (!sale) return null;

  return (
    <div className="space-y-6">
      <PageHeader
        title={`Editar Venta #${sale.sale_number}`}
        description="Modificar datos, lineas y comisiones de la venta"
      >
        <Button variant="outline" onClick={() => navigate(`/sales/${id}`)}>
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
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Cliente *</Label>
              <EntitySelect
                value={customerId}
                onChange={setCustomerId}
                options={customers.map((c) => ({ id: c.id, label: c.name }))}
                placeholder="Seleccionar cliente..."
              />
            </div>
            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Bodega de Salida</Label>
              <EntitySelect
                value={warehouseId}
                onChange={setWarehouseId}
                options={warehouses.map((w) => ({ id: w.id, label: w.name }))}
                placeholder="Seleccionar bodega..."
              />
            </div>
            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Fecha *</Label>
              <Input type="datetime-local" value={date} onChange={(e) => setDate(e.target.value)} />
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
            <Plus className="h-4 w-4 mr-1" />
            Agregar Linea
          </Button>
        </CardHeader>
        <CardContent className="space-y-0">
          {lines.map((line, idx) => (
            <div
              key={line._key}
              className={`grid grid-cols-12 gap-2 items-end pb-3 mb-3 ${idx < lines.length - 1 ? "border-b border-slate-100" : ""}`}
            >
              <div className="col-span-4">
                {idx === 0 && <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Material *</Label>}
                <EntitySelect
                  value={line.material_id}
                  onChange={(v) => updateLine(line._key, "material_id", v)}
                  options={materials.map((m) => ({ id: m.id, label: `${m.code} - ${m.name}` }))}
                  placeholder="Material..."
                />
              </div>
              <div className="col-span-3">
                {idx === 0 && <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Cantidad (kg) *</Label>}
                <Input
                  type="number"
                  min={0}
                  step="0.01"
                  value={line.quantity || ""}
                  onChange={(e) => updateLine(line._key, "quantity", parseFloat(e.target.value) || 0)}
                  placeholder="0.00"
                />
              </div>
              <div className="col-span-2">
                {idx === 0 && <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Precio Unit. *</Label>}
                <Input
                  type="number"
                  min={0}
                  step="1"
                  value={line.unit_price || ""}
                  onChange={(e) => updateLine(line._key, "unit_price", parseFloat(e.target.value) || 0)}
                  placeholder="0"
                />
              </div>
              <div className="col-span-2 text-right">
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
                  onClick={() => setLines((p) => p.filter((l) => l._key !== line._key))}
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

      {/* Comisiones */}
      <Card className="shadow-sm">
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle className="text-sm font-semibold uppercase tracking-wider text-slate-500">Comisiones</CardTitle>
          <Button variant="outline" size="sm" onClick={() => setCommissions((p) => [...p, createEmptyCommission()])}>
            <Plus className="h-4 w-4 mr-1" />
            Agregar Comision
          </Button>
        </CardHeader>
        {commissions.length > 0 && (
          <CardContent className="space-y-0">
            {commissions.map((comm, idx) => (
              <div key={comm._key} className={`grid grid-cols-12 gap-2 items-end pb-3 mb-3 ${idx < commissions.length - 1 ? "border-b border-slate-100" : ""}`}>
                <div className="col-span-3">
                  {idx === 0 && <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Comisionista *</Label>}
                  <EntitySelect
                    value={comm.third_party_id}
                    onChange={(v) => updateCommission(comm._key, "third_party_id", v)}
                    options={thirdParties.map((tp) => ({ id: tp.id, label: tp.name }))}
                    placeholder="Tercero..."
                  />
                </div>
                <div className="col-span-3">
                  {idx === 0 && <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Concepto *</Label>}
                  <Input
                    value={comm.concept}
                    onChange={(e) => updateCommission(comm._key, "concept", e.target.value)}
                    placeholder="Concepto..."
                  />
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
                  <Input
                    type="number"
                    min={0}
                    step="0.01"
                    value={comm.commission_value || ""}
                    onChange={(e) => updateCommission(comm._key, "commission_value", parseFloat(e.target.value) || 0)}
                    placeholder={comm.commission_type === "percentage" ? "%" : "$"}
                  />
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
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setCommissions((p) => p.filter((c) => c._key !== comm._key))}
                    className="text-red-500 hover:text-red-700"
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            ))}
          </CardContent>
        )}
      </Card>

      {/* Acciones */}
      <div className="sticky bottom-0 bg-white/95 backdrop-blur-sm border-t border-slate-100 py-4 -mx-6 px-6 mt-6">
        <div className="flex justify-end gap-2">
          <Button variant="outline" onClick={() => navigate(`/sales/${id}`)}>
            Cancelar
          </Button>
          <Button
            onClick={handleSubmit}
            disabled={!canSubmit || updateSale.isPending}
            className="bg-emerald-600 hover:bg-emerald-700"
          >
            {updateSale.isPending ? "Guardando..." : "Guardar Cambios"}
          </Button>
        </div>
      </div>
    </div>
  );
}
