import { useState, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowLeft, Plus, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { PageHeader } from "@/components/shared/PageHeader";
import { EntitySelect } from "@/components/shared/EntitySelect";
import { PriceSuggestion } from "@/components/shared/PriceSuggestion";
import { useCreateDoubleEntry } from "@/hooks/useDoubleEntries";
import { usePriceSuggestions } from "@/hooks/usePriceSuggestions";
import { useSuppliers, useCustomers, useMaterials } from "@/hooks/useMasterData";
import { MoneyInput } from "@/components/shared/MoneyInput";
import { formatCurrency, toLocalDateInput } from "@/utils/formatters";
import { ROUTES } from "@/utils/constants";
import type { DoubleEntryLineCreate } from "@/types/double-entry";
import type { SaleCommissionCreate } from "@/types/sale";

interface LineFormData extends DoubleEntryLineCreate { _key: number; }
interface CommissionFormData extends SaleCommissionCreate { _key: number; }

let lineKeyCounter = 0;
let commKeyCounter = 0;

function createEmptyLine(): LineFormData {
  return { _key: ++lineKeyCounter, material_id: "", quantity: 0, purchase_unit_price: 0, sale_unit_price: 0 };
}
function createEmptyCommission(): CommissionFormData {
  return { _key: ++commKeyCounter, third_party_id: "", concept: "", commission_type: "percentage", commission_value: 0 };
}

export default function DoubleEntryCreatePage() {
  const navigate = useNavigate();
  const create = useCreateDoubleEntry();

  const { data: suppliersData } = useSuppliers();
  const { data: customersData } = useCustomers();
  const { data: materialsData } = useMaterials();

  const suppliers = suppliersData?.items ?? [];
  const customers = customersData?.items ?? [];
  const materials = materialsData?.items ?? [];
  const allThirdParties = [...suppliers, ...customers];
  const { getSuggestedPrice } = usePriceSuggestions();

  const [lines, setLines] = useState<LineFormData[]>([createEmptyLine()]);
  const [supplierId, setSupplierId] = useState("");
  const [customerId, setCustomerId] = useState("");
  const [date, setDate] = useState(toLocalDateInput());
  const [invoiceNumber, setInvoiceNumber] = useState("");
  const [vehiclePlate, setVehiclePlate] = useState("");
  const [notes, setNotes] = useState("");
  const [commissions, setCommissions] = useState<CommissionFormData[]>([]);

  const updateLine = (key: number, field: keyof DoubleEntryLineCreate, value: string | number) => {
    setLines((prev) => prev.map((l) => l._key === key ? { ...l, [field]: value } : l));
  };

  const handleLineMaterialChange = (key: number, materialId: string) => {
    const line = lines.find((l) => l._key === key);
    updateLine(key, "material_id", materialId);
    if (!line || line.purchase_unit_price === 0) {
      const sp = getSuggestedPrice(materialId, "purchase");
      if (sp) updateLine(key, "purchase_unit_price", sp);
    }
    if (!line || line.sale_unit_price === 0) {
      const sp = getSuggestedPrice(materialId, "sale");
      if (sp) updateLine(key, "sale_unit_price", sp);
    }
  };

  const removeLine = (key: number) => {
    if (lines.length <= 1) return;
    setLines((prev) => prev.filter((l) => l._key !== key));
  };

  // Materiales ya usados en otras lineas
  const usedMaterialIds = (excludeKey: number) =>
    lines.filter((l) => l._key !== excludeKey && l.material_id).map((l) => l.material_id);

  const totalPurchase = useMemo(() => lines.reduce((sum, l) => sum + l.quantity * l.purchase_unit_price, 0), [lines]);
  const totalSale = useMemo(() => lines.reduce((sum, l) => sum + l.quantity * l.sale_unit_price, 0), [lines]);
  const totalCommissions = useMemo(
    () => commissions.reduce((sum, c) => sum + (c.commission_type === "percentage" ? (totalSale * c.commission_value) / 100 : c.commission_value), 0),
    [commissions, totalSale],
  );
  const profit = totalSale - totalPurchase - totalCommissions;

  const canSubmit =
    lines.length > 0 &&
    lines.every((l) => l.material_id && l.quantity > 0 && l.purchase_unit_price > 0 && l.sale_unit_price > 0) &&
    supplierId &&
    customerId &&
    supplierId !== customerId &&
    date &&
    commissions.every((c) => c.third_party_id && c.concept && c.commission_value > 0);

  const handleSubmit = () => {
    if (!canSubmit) return;
    create.mutate(
      {
        lines: lines.map(({ _key, ...rest }) => rest),
        supplier_id: supplierId,
        customer_id: customerId,
        date,
        invoice_number: invoiceNumber || null,
        vehicle_plate: vehiclePlate || null,
        notes: notes || null,
        commissions: commissions.map(({ _key, ...rest }) => rest),
      },
      { onSuccess: (de) => navigate(`/double-entries/${de.id}`) },
    );
  };

  return (
    <div className="space-y-6">
      <PageHeader title="Nueva Doble Partida" description="Operacion Pasa Mano (compra + venta simultanea)">
        <Button variant="outline" onClick={() => navigate(ROUTES.DOUBLE_ENTRIES)}><ArrowLeft className="h-4 w-4 mr-2" />Volver</Button>
      </PageHeader>

      {/* Datos Generales */}
      <Card className="shadow-sm">
        <CardHeader><CardTitle className="text-sm font-semibold uppercase tracking-wider text-slate-500">Datos Generales</CardTitle></CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Proveedor *</Label>
              <EntitySelect value={supplierId} onChange={setSupplierId} options={suppliers.map((s) => ({ id: s.id, label: s.name }))} placeholder="Seleccionar proveedor..." />
            </div>
            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Cliente *</Label>
              <EntitySelect value={customerId} onChange={setCustomerId} options={customers.map((c) => ({ id: c.id, label: c.name }))} placeholder="Seleccionar cliente..." />
            </div>
            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Fecha *</Label>
              <Input type="date" value={date} onChange={(e) => setDate(e.target.value)} />
            </div>
            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Placa</Label>
              <Input value={vehiclePlate} onChange={(e) => setVehiclePlate(e.target.value)} />
            </div>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-4">
            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Factura</Label>
              <Input value={invoiceNumber} onChange={(e) => setInvoiceNumber(e.target.value)} />
            </div>
            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Notas</Label>
              <Textarea value={notes} onChange={(e) => setNotes(e.target.value)} rows={1} />
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Materiales (lineas) */}
      <Card className="shadow-sm">
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle className="text-sm font-semibold uppercase tracking-wider text-slate-500">Materiales</CardTitle>
          <Button variant="outline" size="sm" onClick={() => setLines((p) => [...p, createEmptyLine()])}><Plus className="h-4 w-4 mr-1" />Agregar Linea</Button>
        </CardHeader>
        <CardContent className="space-y-0">
          {/* Header */}
          <div className="grid grid-cols-12 gap-2 pb-2 border-b border-slate-200 mb-2">
            <div className="col-span-3 text-[11px] font-semibold uppercase tracking-wider text-slate-500">Material</div>
            <div className="col-span-2 text-[11px] font-semibold uppercase tracking-wider text-slate-500">Cantidad (kg)</div>
            <div className="col-span-2 text-[11px] font-semibold uppercase tracking-wider text-slate-500">P. Compra</div>
            <div className="col-span-2 text-[11px] font-semibold uppercase tracking-wider text-slate-500">P. Venta</div>
            <div className="col-span-2 text-[11px] font-semibold uppercase tracking-wider text-slate-500 text-right">Ganancia</div>
            <div className="col-span-1" />
          </div>

          {lines.map((line) => {
            const lineProfit = (line.sale_unit_price - line.purchase_unit_price) * line.quantity;
            const used = usedMaterialIds(line._key);
            const availableMaterials = materials.filter((m) => !used.includes(m.id));

            return (
              <div key={line._key} className="grid grid-cols-12 gap-2 items-start py-2 pb-8 relative border-b border-slate-100 last:border-0">
                <div className="col-span-3">
                  <EntitySelect
                    value={line.material_id}
                    onChange={(v) => handleLineMaterialChange(line._key, v)}
                    options={availableMaterials.map((m) => ({ id: m.id, label: `${m.code} - ${m.name}` }))}
                    placeholder="Material..."
                  />
                </div>
                <div className="col-span-2">
                  <MoneyInput value={line.quantity} onChange={(v) => updateLine(line._key, "quantity", v)} decimals={2} />
                </div>
                <div className="col-span-2 relative">
                  <MoneyInput value={line.purchase_unit_price} onChange={(v) => updateLine(line._key, "purchase_unit_price", v)} />
                  <div className="absolute left-0 w-max" style={{ top: "100%" }}>
                    <PriceSuggestion suggestedPrice={getSuggestedPrice(line.material_id, "purchase")} onApply={(p) => updateLine(line._key, "purchase_unit_price", p)} />
                  </div>
                </div>
                <div className="col-span-2 relative">
                  <MoneyInput value={line.sale_unit_price} onChange={(v) => updateLine(line._key, "sale_unit_price", v)} />
                  <div className="absolute left-0 w-max" style={{ top: "100%" }}>
                    <PriceSuggestion suggestedPrice={getSuggestedPrice(line.material_id, "sale")} onApply={(p) => updateLine(line._key, "sale_unit_price", p)} />
                  </div>
                </div>
                <div className="col-span-2 text-right pt-2">
                  <span className={`font-medium tabular-nums ${lineProfit >= 0 ? "text-emerald-700" : "text-red-700"}`}>
                    {formatCurrency(lineProfit)}
                  </span>
                </div>
                <div className="col-span-1 text-center pt-1">
                  {lines.length > 1 && (
                    <Button variant="ghost" size="sm" onClick={() => removeLine(line._key)} className="text-red-500 h-8 w-8 p-0">
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  )}
                </div>
              </div>
            );
          })}

          {/* Totales */}
          <div className="grid grid-cols-12 gap-2 pt-3 mt-2 border-t border-slate-300">
            <div className="col-span-5 text-right text-sm font-semibold text-slate-600">Totales:</div>
            <div className="col-span-2 text-sm font-bold">{formatCurrency(totalPurchase)}</div>
            <div className="col-span-2 text-sm font-bold">{formatCurrency(totalSale)}</div>
            <div className="col-span-2 text-right">
              <span className={`text-sm font-bold ${totalSale - totalPurchase >= 0 ? "text-emerald-700" : "text-red-700"}`}>
                {formatCurrency(totalSale - totalPurchase)}
              </span>
            </div>
            <div className="col-span-1" />
          </div>
        </CardContent>
      </Card>

      {/* Comisiones */}
      <Card className="shadow-sm">
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle className="text-sm font-semibold uppercase tracking-wider text-slate-500">Comisiones (Opcional)</CardTitle>
          <Button variant="outline" size="sm" onClick={() => setCommissions((p) => [...p, createEmptyCommission()])}><Plus className="h-4 w-4 mr-1" />Agregar</Button>
        </CardHeader>
        {commissions.length > 0 && (
          <CardContent className="space-y-0">
            {commissions.map((comm, idx) => (
              <div key={comm._key} className={`grid grid-cols-12 gap-2 items-end pb-3 mb-3 ${idx < commissions.length - 1 ? "border-b border-slate-100" : ""}`}>
                <div className="col-span-3">
                  {idx === 0 && <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Comisionista</Label>}
                  <EntitySelect value={comm.third_party_id} onChange={(v) => setCommissions((p) => p.map((c) => c._key === comm._key ? { ...c, third_party_id: v } : c))} options={allThirdParties.map((t) => ({ id: t.id, label: t.name }))} placeholder="Tercero..." />
                </div>
                <div className="col-span-3">
                  {idx === 0 && <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Concepto</Label>}
                  <Input value={comm.concept} onChange={(e) => setCommissions((p) => p.map((c) => c._key === comm._key ? { ...c, concept: e.target.value } : c))} />
                </div>
                <div className="col-span-2">
                  {idx === 0 && <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Tipo</Label>}
                  <Select value={comm.commission_type} onValueChange={(v) => setCommissions((p) => p.map((c) => c._key === comm._key ? { ...c, commission_type: v as "percentage" | "fixed" } : c))}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent><SelectItem value="percentage">%</SelectItem><SelectItem value="fixed">$</SelectItem></SelectContent></Select>
                </div>
                <div className="col-span-2">
                  {idx === 0 && <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Valor</Label>}
                  <Input type="number" min={0} value={comm.commission_value || ""} onChange={(e) => setCommissions((p) => p.map((c) => c._key === comm._key ? { ...c, commission_value: parseFloat(e.target.value) || 0 } : c))} />
                </div>
                <div className="col-span-1">
                  {idx === 0 && <Label className="text-xs">&nbsp;</Label>}
                  <Button variant="ghost" size="sm" onClick={() => setCommissions((p) => p.filter((c) => c._key !== comm._key))} className="text-red-500"><Trash2 className="h-4 w-4" /></Button>
                </div>
              </div>
            ))}
          </CardContent>
        )}
      </Card>

      {/* Resumen */}
      <Card className="border-2 border-emerald-200 bg-emerald-50 shadow-sm">
        <CardContent className="pt-6">
          <div className="flex justify-between items-center">
            <div className="space-y-1 text-sm">
              <div>Compra: <span className="font-medium">{formatCurrency(totalPurchase)}</span></div>
              <div>Venta: <span className="font-medium">{formatCurrency(totalSale)}</span></div>
              {totalCommissions > 0 && <div>Comisiones: <span className="font-medium text-red-600">-{formatCurrency(totalCommissions)}</span></div>}
            </div>
            <div className="text-right">
              <p className="text-sm text-slate-500">Utilidad estimada</p>
              <p className={`text-3xl font-bold ${profit >= 0 ? "text-emerald-700" : "text-red-700"}`}>{formatCurrency(profit)}</p>
            </div>
          </div>
        </CardContent>
      </Card>

      <div className="sticky bottom-0 bg-white/95 backdrop-blur-sm border-t border-slate-100 py-4 -mx-6 px-6 mt-6">
        <div className="flex justify-end gap-2">
          <Button variant="outline" onClick={() => navigate(ROUTES.DOUBLE_ENTRIES)}>Cancelar</Button>
          <Button onClick={handleSubmit} disabled={!canSubmit || create.isPending} className="bg-emerald-600 hover:bg-emerald-700">{create.isPending ? "Creando..." : "Crear Doble Partida"}</Button>
        </div>
      </div>
    </div>
  );
}
