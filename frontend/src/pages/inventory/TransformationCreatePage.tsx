import { useState, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowLeft, Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { AttachmentsPicker } from "@/components/shared/AttachmentsPicker";
import { uploadPendingAttachments } from "@/hooks/useAttachments";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { PageHeader } from "@/components/shared/PageHeader";
import { EntitySelect } from "@/components/shared/EntitySelect";
import { MoneyInput } from "@/components/shared/MoneyInput";
import { FormLineGrid, lineLabelClass } from "@/components/shared/FormLineGrid";
import { useCreateTransformation } from "@/hooks/useInventory";
import { useMaterials, useWarehouses } from "@/hooks/useMasterData";
import { toLocalDateInput } from "@/utils/formatters";
import { ROUTES } from "@/utils/constants";
import { cn } from "@/utils";

interface LineForm {
  _key: number;
  destination_material_id: string;
  destination_warehouse_id: string;
  quantity: number;
  unit_cost: number | null;
}

let lineKeyCounter = 0;
function createEmptyLine(): LineForm {
  return { _key: ++lineKeyCounter, destination_material_id: "", destination_warehouse_id: "", quantity: 0, unit_cost: null };
}

export default function TransformationCreatePage() {
  const navigate = useNavigate();
  const create = useCreateTransformation();

  const { data: materialsData } = useMaterials();
  const { data: warehousesData } = useWarehouses();
  const materials = materialsData?.items ?? [];
  const warehouses = warehousesData?.items ?? [];

  const [sourceMaterialId, setSourceMaterialId] = useState("");
  const [sourceWarehouseId, setSourceWarehouseId] = useState("");
  const [sourceQuantity, setSourceQuantity] = useState(0);
  const [wasteQuantity, setWasteQuantity] = useState(0);
  const [costDistribution, setCostDistribution] = useState<"average_cost" | "proportional_weight" | "manual">("average_cost");
  const [lines, setLines] = useState<LineForm[]>([createEmptyLine()]);
  const [date, setDate] = useState(toLocalDateInput());
  const [reason, setReason] = useState("");
  const [notes, setNotes] = useState("");
  const [pendingFiles, setPendingFiles] = useState<File[]>([]);

  const materialById = useMemo(() => new Map(materials.map((m) => [m.id, m])), [materials]);
  const sourceUnit = materialById.get(sourceMaterialId)?.default_unit ?? "";

  // Cambio de unidad: el origen y al menos un destino tienen unidades distintas
  // (ej: desarmar Aire Acondicionado [unidad] en metales [kg]). En ese caso la
  // conservacion de masa no aplica — no se exige balance ni se usa merma.
  const isCrossUnit = useMemo(() => {
    if (!sourceUnit) return false;
    return lines.some((l) => {
      if (!l.destination_material_id) return false;
      const u = materialById.get(l.destination_material_id)?.default_unit;
      return u != null && u !== sourceUnit;
    });
  }, [lines, sourceUnit, materialById]);

  const totalDestQty = useMemo(() => lines.reduce((sum, l) => sum + l.quantity, 0), [lines]);
  const balance = sourceQuantity - totalDestQty - wasteQuantity;
  const isBalanced = Math.abs(balance) < 0.001;
  // En cambio de unidad no se exige balance de masa.
  const balanceOk = isCrossUnit || isBalanced;

  const canSubmit = sourceMaterialId && sourceWarehouseId && sourceQuantity > 0 && reason.length >= 3 && date && lines.length > 0 && lines.every((l) => l.destination_material_id && l.destination_warehouse_id && l.quantity > 0) && balanceOk && (costDistribution !== "manual" || lines.every((l) => l.unit_cost !== null && l.unit_cost > 0));

  const handleSubmit = () => {
    if (!canSubmit) return;
    create.mutate(
      {
        source_material_id: sourceMaterialId,
        source_warehouse_id: sourceWarehouseId,
        source_quantity: sourceQuantity,
        waste_quantity: isCrossUnit ? 0 : wasteQuantity,
        cost_distribution: costDistribution,
        lines: lines.map(({ destination_material_id, destination_warehouse_id, quantity, unit_cost }) => ({
          destination_material_id,
          destination_warehouse_id,
          quantity,
          unit_cost: costDistribution === "manual" ? unit_cost : undefined,
        })),
        date,
        reason,
        notes: notes || undefined,
      },
      {
        onSuccess: async (t) => {
          await uploadPendingAttachments("transformation", t.id, pendingFiles);
          navigate(ROUTES.INVENTORY_TRANSFORMATIONS);
        },
      },
    );
  };

  const materialOptions = materials.map((m) => ({ id: m.id, label: `${m.code} - ${m.name} (${m.default_unit})` }));
  const warehouseOptions = warehouses.map((w) => ({ id: w.id, label: w.name }));

  return (
    <div className="space-y-6">
      <PageHeader title="Nueva Transformacion" description="Desintegrar material compuesto en componentes">
        <Button variant="outline" onClick={() => navigate(ROUTES.INVENTORY_TRANSFORMATIONS)}>
          <ArrowLeft className="h-4 w-4 mr-2" />Volver
        </Button>
      </PageHeader>

      {/* Origen */}
      <Card className="shadow-sm">
        <CardHeader><CardTitle className="text-sm font-semibold uppercase tracking-wider text-blue-700">Material Origen</CardTitle></CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Material *</Label>
              <EntitySelect value={sourceMaterialId} onChange={setSourceMaterialId} options={materialOptions} placeholder="Seleccionar..." />
            </div>
            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Bodega *</Label>
              <EntitySelect value={sourceWarehouseId} onChange={setSourceWarehouseId} options={warehouseOptions} placeholder="Seleccionar..." />
            </div>
            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Cantidad *{sourceUnit ? ` (${sourceUnit})` : ""}</Label>
              <MoneyInput value={sourceQuantity} onChange={setSourceQuantity} decimals={2} />
            </div>
            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Fecha *</Label>
              <Input type="date" value={date} onChange={(e) => setDate(e.target.value)} />
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Destinos */}
      <Card className="shadow-sm">
        <CardHeader className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
          <CardTitle className="text-sm font-semibold uppercase tracking-wider text-emerald-700">Materiales Destino</CardTitle>
          <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-2 sm:gap-4">
            <Select value={costDistribution} onValueChange={(v) => setCostDistribution(v as "average_cost" | "proportional_weight" | "manual")}>
              <SelectTrigger className="w-full sm:w-[220px]"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="average_cost">Costo Promedio Movil</SelectItem>
                <SelectItem value="proportional_weight">Proporcional (peso)</SelectItem>
                <SelectItem value="manual">Manual</SelectItem>
              </SelectContent>
            </Select>
            <Button variant="outline" size="sm" onClick={() => setLines((p) => [...p, createEmptyLine()])} className="w-full sm:w-auto">
              <Plus className="h-4 w-4 mr-1" />Agregar
            </Button>
          </div>
        </CardHeader>
        <CardContent className="space-y-0">
          {lines.map((line, idx) => (
            <FormLineGrid
              key={line._key}
              isLast={idx === lines.length - 1}
              isFirst={idx === 0}
              onDelete={() => setLines((p) => p.filter((l) => l._key !== line._key))}
              disableDelete={lines.length <= 1}
            >
              <div className="md:col-span-3">
                <Label className={cn("text-xs font-semibold uppercase tracking-wider text-slate-500", lineLabelClass(idx))}>Material</Label>
                <EntitySelect value={line.destination_material_id} onChange={(v) => setLines((p) => p.map((l) => l._key === line._key ? { ...l, destination_material_id: v } : l))} options={materialOptions} placeholder="Material..." />
              </div>
              <div className="md:col-span-3">
                <Label className={cn("text-xs font-semibold uppercase tracking-wider text-slate-500", lineLabelClass(idx))}>Bodega</Label>
                <EntitySelect value={line.destination_warehouse_id} onChange={(v) => setLines((p) => p.map((l) => l._key === line._key ? { ...l, destination_warehouse_id: v } : l))} options={warehouseOptions} placeholder="Bodega..." />
              </div>
              <div className={costDistribution === "manual" ? "md:col-span-2" : "md:col-span-5"}>
                <Label className={cn("text-xs font-semibold uppercase tracking-wider text-slate-500", lineLabelClass(idx))}>
                  Cantidad{line.destination_material_id && materialById.get(line.destination_material_id)?.default_unit ? ` (${materialById.get(line.destination_material_id)!.default_unit})` : ""}
                </Label>
                <MoneyInput value={line.quantity} onChange={(v) => setLines((p) => p.map((l) => l._key === line._key ? { ...l, quantity: v } : l))} decimals={2} />
              </div>
              {costDistribution === "manual" && (
                <div className="md:col-span-3">
                  <Label className={cn("text-xs font-semibold uppercase tracking-wider text-slate-500", lineLabelClass(idx))}>Costo Unit.</Label>
                  <MoneyInput value={line.unit_cost ?? 0} onChange={(v) => setLines((p) => p.map((l) => l._key === line._key ? { ...l, unit_cost: v } : l))} />
                </div>
              )}
            </FormLineGrid>
          ))}
        </CardContent>
      </Card>

      {/* Merma y Balance */}
      {isCrossUnit ? (
        /* Cambio de unidad: no aplica conservacion de masa. Sin merma (se modela
           como un material destino en kg). Panel informativo, no bloquea. */
        <Card className="shadow-sm border-2 border-indigo-200 bg-indigo-50">
          <CardContent className="pt-6">
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
              <div className="text-sm">
                <p className="text-slate-700">
                  Se consumen <span className="font-semibold">{sourceQuantity.toFixed(2)} {sourceUnit}</span> de origen
                  {" → "}se producen <span className="font-semibold">{totalDestQty.toFixed(2)}</span> en destinos.
                </p>
                <p className="text-indigo-700 mt-1">
                  Transformacion con cambio de unidad — no aplica balance de masa. La merma de peso se registra como un material destino (ej: "Basura").
                </p>
              </div>
              <span className="shrink-0 self-start sm:self-center bg-indigo-100 text-indigo-700 text-xs font-medium px-2.5 py-1 rounded-full">
                {sourceUnit || "?"} → kg
              </span>
            </div>
          </CardContent>
        </Card>
      ) : (
        <Card className={`shadow-sm border-2 ${isBalanced ? "border-emerald-200 bg-emerald-50" : "border-red-200 bg-red-50"}`}>
          <CardContent className="pt-6">
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4 items-end">
              <div>
                <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Merma/Desperdicio{sourceUnit ? ` (${sourceUnit})` : ""}</Label>
                <MoneyInput value={wasteQuantity} onChange={setWasteQuantity} decimals={2} />
              </div>
              <div className="text-sm">
                <p className="text-slate-500">Origen: <span className="font-medium">{sourceQuantity.toFixed(2)}</span></p>
                <p className="text-slate-500">Destinos: <span className="font-medium">{totalDestQty.toFixed(2)}</span></p>
                <p className="text-slate-500">Merma: <span className="font-medium">{wasteQuantity.toFixed(2)}</span></p>
              </div>
              <div className="md:col-span-2 text-right">
                <p className="text-sm text-slate-500">Balance</p>
                <p className={`text-2xl font-bold ${isBalanced ? "text-emerald-700" : "text-red-700"}`}>
                  {isBalanced ? "Cuadra" : `Diferencia: ${balance.toFixed(2)}`}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Razon y notas */}
      <Card className="shadow-sm">
        <CardContent className="pt-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Razon *</Label>
              <Input value={reason} onChange={(e) => setReason(e.target.value)} placeholder="Razon de la transformacion..." />
            </div>
            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Notas</Label>
              <Textarea value={notes} onChange={(e) => setNotes(e.target.value)} rows={1} />
            </div>
            <div className="md:col-span-2">
              <AttachmentsPicker files={pendingFiles} onChange={setPendingFiles} />
            </div>
          </div>
        </CardContent>
      </Card>

      <div className="sticky bottom-0 bg-white/95 backdrop-blur-sm border-t border-slate-100 py-4 -mx-3 px-3 md:-mx-6 md:px-6 mt-6 pb-[max(1rem,env(safe-area-inset-bottom))]">
        <div className="flex flex-col sm:flex-row sm:justify-end gap-2">
          <Button variant="outline" onClick={() => navigate(ROUTES.INVENTORY_TRANSFORMATIONS)} className="w-full sm:w-auto">Cancelar</Button>
          <Button onClick={handleSubmit} disabled={!canSubmit || create.isPending} className="bg-emerald-600 hover:bg-emerald-700 w-full sm:w-auto">
            {create.isPending ? "Creando..." : "Crear Transformacion"}
          </Button>
        </div>
      </div>
    </div>
  );
}
