import { useState, useEffect } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { ArrowLeft } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { PageHeader } from "@/components/shared/PageHeader";
import { EntitySelect } from "@/components/shared/EntitySelect";
import { useCreateAdjustment } from "@/hooks/useInventory";
import { useMaterials, useWarehouses } from "@/hooks/useMasterData";
import { MoneyInput } from "@/components/shared/MoneyInput";
import { toLocalDateInput } from "@/utils/formatters";
import { ROUTES } from "@/utils/constants";

type AdjType = "increase" | "decrease" | "recount" | "zero_out";

const typeLabels: Record<AdjType, string> = {
  increase: "Aumento de Stock",
  decrease: "Disminucion de Stock",
  recount: "Conteo Fisico",
  zero_out: "Llevar a Cero",
};

export default function AdjustmentCreatePage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [adjType, setAdjType] = useState<AdjType>("increase");
  const create = useCreateAdjustment(adjType);

  const { data: materialsData } = useMaterials();
  const { data: warehousesData } = useWarehouses();
  const materials = materialsData?.items ?? [];
  const warehouses = warehousesData?.items ?? [];

  const [materialId, setMaterialId] = useState("");

  // Pre-seleccionar material desde URL params (navegacion desde StockPage)
  useEffect(() => {
    const urlMaterialId = searchParams.get("material_id");
    if (urlMaterialId && !materialId) setMaterialId(urlMaterialId);
  }, [searchParams, materialId]);
  const [warehouseId, setWarehouseId] = useState("");
  const [quantity, setQuantity] = useState(0);
  const [unitCost, setUnitCost] = useState(0);
  const [countedQuantity, setCountedQuantity] = useState(0);
  const [date, setDate] = useState(toLocalDateInput());
  const [reason, setReason] = useState("");
  const [notes, setNotes] = useState("");

  const handleTypeChange = (v: string) => {
    setAdjType(v as AdjType);
    setQuantity(0);
    setUnitCost(0);
    setCountedQuantity(0);
  };

  const buildPayload = () => {
    const base = { material_id: materialId, warehouse_id: warehouseId, date, reason, notes: notes || undefined };
    switch (adjType) {
      case "increase": return { ...base, quantity, unit_cost: unitCost };
      case "decrease": return { ...base, quantity };
      case "recount": return { ...base, counted_quantity: countedQuantity };
      case "zero_out": return base;
    }
  };

  const canSubmit = materialId && warehouseId && reason.length >= 3 && date && (
    (adjType === "increase" && quantity > 0 && unitCost > 0) ||
    (adjType === "decrease" && quantity > 0) ||
    (adjType === "recount" && countedQuantity >= 0) ||
    adjType === "zero_out"
  );

  const handleSubmit = () => {
    if (!canSubmit) return;
    create.mutate(buildPayload() as never, {
      onSuccess: () => navigate(ROUTES.INVENTORY_ADJUSTMENTS),
    });
  };

  return (
    <div className="space-y-6">
      <PageHeader title="Nuevo Ajuste" description="Ajuste manual de inventario">
        <Button variant="outline" onClick={() => navigate(ROUTES.INVENTORY_ADJUSTMENTS)}>
          <ArrowLeft className="h-4 w-4 mr-2" />Volver
        </Button>
      </PageHeader>

      <Card className="shadow-sm">
        <CardHeader><CardTitle className="text-sm font-semibold uppercase tracking-wider text-slate-500">Tipo de Ajuste</CardTitle></CardHeader>
        <CardContent>
          <Select value={adjType} onValueChange={handleTypeChange}>
            <SelectTrigger className="w-full max-w-md">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {Object.entries(typeLabels).map(([key, label]) => (
                <SelectItem key={key} value={key}>{label}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </CardContent>
      </Card>

      <Card className="shadow-sm">
        <CardHeader><CardTitle className="text-sm font-semibold uppercase tracking-wider text-slate-500">{typeLabels[adjType]}</CardTitle></CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Material *</Label>
              <EntitySelect value={materialId} onChange={setMaterialId} options={materials.map((m) => ({ id: m.id, label: `${m.code} - ${m.name}` }))} placeholder="Seleccionar material..." />
            </div>
            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Bodega *</Label>
              <EntitySelect value={warehouseId} onChange={setWarehouseId} options={warehouses.map((w) => ({ id: w.id, label: w.name }))} placeholder="Seleccionar bodega..." />
            </div>
            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Fecha *</Label>
              <Input type="date" value={date} onChange={(e) => setDate(e.target.value)} />
            </div>

            {(adjType === "increase" || adjType === "decrease") && (
              <div>
                <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Cantidad *</Label>
                <MoneyInput value={quantity} onChange={setQuantity} decimals={2} placeholder="0" />
              </div>
            )}

            {adjType === "increase" && (
              <div>
                <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Costo Unitario *</Label>
                <MoneyInput value={unitCost} onChange={setUnitCost} placeholder="0" />
              </div>
            )}

            {adjType === "recount" && (
              <div>
                <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Cantidad Contada *</Label>
                <MoneyInput value={countedQuantity} onChange={setCountedQuantity} decimals={2} placeholder="0" />
              </div>
            )}

            <div className="md:col-span-2">
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Razon *</Label>
              <Input value={reason} onChange={(e) => setReason(e.target.value)} placeholder="Razon del ajuste (minimo 3 caracteres)" />
            </div>
            <div className="md:col-span-2">
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Notas</Label>
              <Textarea value={notes} onChange={(e) => setNotes(e.target.value)} rows={2} placeholder="Notas adicionales..." />
            </div>
          </div>
        </CardContent>
      </Card>

      <div className="sticky bottom-0 bg-white/95 backdrop-blur-sm border-t border-slate-100 py-4 -mx-6 px-6 mt-6">
        <div className="flex justify-end gap-2">
          <Button variant="outline" onClick={() => navigate(ROUTES.INVENTORY_ADJUSTMENTS)}>Cancelar</Button>
          <Button onClick={handleSubmit} disabled={!canSubmit || create.isPending} className="bg-emerald-600 hover:bg-emerald-700">
            {create.isPending ? "Creando..." : "Crear Ajuste"}
          </Button>
        </div>
      </div>
    </div>
  );
}
