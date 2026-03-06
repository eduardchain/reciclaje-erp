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
import { formatCurrency, toLocalDateInput } from "@/utils/formatters";
import { ROUTES } from "@/utils/constants";
import type { SaleCommissionCreate } from "@/types/sale";

interface CommissionFormData extends SaleCommissionCreate { _key: number; }
let commKeyCounter = 0;
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

  const [materialId, setMaterialId] = useState("");
  const [quantity, setQuantity] = useState(0);
  const [supplierId, setSupplierId] = useState("");
  const [purchaseUnitPrice, setPurchaseUnitPrice] = useState(0);
  const [customerId, setCustomerId] = useState("");
  const [saleUnitPrice, setSaleUnitPrice] = useState(0);
  const [date, setDate] = useState(toLocalDateInput());
  const [invoiceNumber, setInvoiceNumber] = useState("");
  const [vehiclePlate, setVehiclePlate] = useState("");
  const [notes, setNotes] = useState("");
  const [commissions, setCommissions] = useState<CommissionFormData[]>([]);

  const handleMaterialChange = (id: string) => {
    setMaterialId(id);
    if (purchaseUnitPrice === 0) {
      const sp = getSuggestedPrice(id, "purchase");
      if (sp) setPurchaseUnitPrice(sp);
    }
    if (saleUnitPrice === 0) {
      const sp = getSuggestedPrice(id, "sale");
      if (sp) setSaleUnitPrice(sp);
    }
  };

  const totalPurchase = quantity * purchaseUnitPrice;
  const totalSale = quantity * saleUnitPrice;
  const totalCommissions = useMemo(
    () => commissions.reduce((sum, c) => sum + (c.commission_type === "percentage" ? (totalSale * c.commission_value) / 100 : c.commission_value), 0),
    [commissions, totalSale],
  );
  const profit = totalSale - totalPurchase - totalCommissions;

  const canSubmit = materialId && quantity > 0 && supplierId && purchaseUnitPrice >= 0 && customerId && saleUnitPrice >= 0 && date && commissions.every((c) => c.third_party_id && c.concept && c.commission_value > 0);

  const handleSubmit = () => {
    if (!canSubmit) return;
    create.mutate(
      {
        material_id: materialId,
        quantity,
        supplier_id: supplierId,
        purchase_unit_price: purchaseUnitPrice,
        customer_id: customerId,
        sale_unit_price: saleUnitPrice,
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

      {/* Material y Cantidad */}
      <Card className="shadow-sm">
        <CardHeader><CardTitle className="text-sm font-semibold uppercase tracking-wider text-slate-500">Material</CardTitle></CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Material *</Label>
              <EntitySelect value={materialId} onChange={handleMaterialChange} options={materials.map((m) => ({ id: m.id, label: `${m.code} - ${m.name}` }))} placeholder="Seleccionar material..." />
            </div>
            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Cantidad (kg) *</Label>
              <Input type="number" min={0} step="0.01" value={quantity || ""} onChange={(e) => setQuantity(parseFloat(e.target.value) || 0)} />
            </div>
            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Fecha *</Label>
              <Input type="date" value={date} onChange={(e) => setDate(e.target.value)} />
            </div>
          </div>
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Compra */}
        <Card className="border-l-[3px] border-l-blue-500 shadow-sm">
          <CardHeader><CardTitle className="text-sm font-semibold uppercase tracking-wider text-blue-700">Lado Compra</CardTitle></CardHeader>
          <CardContent className="space-y-4">
            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Proveedor *</Label>
              <EntitySelect value={supplierId} onChange={setSupplierId} options={suppliers.map((s) => ({ id: s.id, label: s.name }))} placeholder="Seleccionar proveedor..." />
            </div>
            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Precio Compra Unit. *</Label>
              <Input type="number" min={0} step="1" value={purchaseUnitPrice || ""} onChange={(e) => setPurchaseUnitPrice(parseFloat(e.target.value) || 0)} />
              <PriceSuggestion suggestedPrice={getSuggestedPrice(materialId, "purchase")} onApply={setPurchaseUnitPrice} />
            </div>
            <div className="bg-slate-50 rounded-lg p-3">
              <div className="flex justify-between"><span className="text-slate-500">Total Compra</span><span className="font-bold text-lg">{formatCurrency(totalPurchase)}</span></div>
            </div>
          </CardContent>
        </Card>

        {/* Venta */}
        <Card className="border-l-[3px] border-l-emerald-500 shadow-sm">
          <CardHeader><CardTitle className="text-sm font-semibold uppercase tracking-wider text-emerald-700">Lado Venta</CardTitle></CardHeader>
          <CardContent className="space-y-4">
            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Cliente *</Label>
              <EntitySelect value={customerId} onChange={setCustomerId} options={customers.map((c) => ({ id: c.id, label: c.name }))} placeholder="Seleccionar cliente..." />
            </div>
            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Precio Venta Unit. *</Label>
              <Input type="number" min={0} step="1" value={saleUnitPrice || ""} onChange={(e) => setSaleUnitPrice(parseFloat(e.target.value) || 0)} />
              <PriceSuggestion suggestedPrice={getSuggestedPrice(materialId, "sale")} onApply={setSaleUnitPrice} />
            </div>
            <div className="bg-slate-50 rounded-lg p-3">
              <div className="flex justify-between"><span className="text-slate-500">Total Venta</span><span className="font-bold text-lg">{formatCurrency(totalSale)}</span></div>
            </div>
          </CardContent>
        </Card>
      </div>

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

      {/* Info adicional */}
      <Card className="shadow-sm">
        <CardContent className="pt-6">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div><Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Placa</Label><Input value={vehiclePlate} onChange={(e) => setVehiclePlate(e.target.value)} /></div>
            <div><Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Factura</Label><Input value={invoiceNumber} onChange={(e) => setInvoiceNumber(e.target.value)} /></div>
            <div><Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Notas</Label><Textarea value={notes} onChange={(e) => setNotes(e.target.value)} rows={1} /></div>
          </div>
        </CardContent>
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
