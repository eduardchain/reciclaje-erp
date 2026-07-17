import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowLeft, Plus, Info } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { PageHeader } from "@/components/shared/PageHeader";
import { EntitySelect } from "@/components/shared/EntitySelect";
import { MoneyInput } from "@/components/shared/MoneyInput";
import { FormLineGrid, lineLabelClass } from "@/components/shared/FormLineGrid";
import { useCreateInboundOrder } from "@/hooks/useInboundOrders";
import { useMaterials, useSuppliers, useWarehouses } from "@/hooks/useMasterData";
import { useCurrentFormulas, useDrivers, useKgProfiles, useVehicles } from "@/hooks/useSacConfig";
import { useOrgSettings } from "@/hooks/useOrgSettings";
import { formatWeight, toLocalDateInput } from "@/utils/formatters";
import { buildRoute, ROUTES } from "@/utils/constants";
import { cn } from "@/utils";
import {
  INBOUND_TYPE_LABELS,
  PURCHASE_INBOUND_TYPES,
  WILLARD_INBOUND_TYPES,
  type InboundType,
} from "@/types/inbound-order";
import type { MaterialConversionFormulaResponse, WillardWorld } from "@/types/sac-config";

interface LineFormData {
  _key: number;
  material_id: string;
  quantity: number;
  unit_price: number;
  scale_weight_kg: number;
  quality_notes: string;
}

let lineKeyCounter = 0;

function createEmptyLine(): LineFormData {
  return {
    _key: ++lineKeyCounter,
    material_id: "",
    quantity: 0,
    unit_price: 0,
    scale_weight_kg: 0,
    quality_notes: "",
  };
}

// Prettify de los codigos de centro Willard (org settings): "santa_marta" → "Santa Marta"
export function willardCenterLabel(code: string): string {
  if (code.length <= 3) return code.toUpperCase();
  return code
    .split("_")
    .map((w) => (w ? w[0].toUpperCase() + w.slice(1) : w))
    .join(" ");
}

/**
 * Preview client-side del delta kg de una linea (plan §5: "estimado" — el
 * numero REAL lo calcula el backend al confirmar con la formula vigente).
 * Una formula vigente por material (CC-001, sin subtipo).
 */
export function estimateKgLead(
  formulas: MaterialConversionFormulaResponse[],
  materialId: string,
  quantity: number
): number | null {
  const formula = formulas.find((f) => f.material_id === materialId);
  if (!formula || quantity <= 0) return null;
  if (formula.formula_type === "battery_to_lead") {
    return quantity * Number(formula.parameters.kg_lead_per_unit ?? 0);
  }
  if (formula.formula_type === "drosses_to_lead") {
    return quantity * Number(formula.parameters.lead_percentage ?? 0);
  }
  return null;
}

export default function InboundCreatePage() {
  const navigate = useNavigate();
  const createOrder = useCreateInboundOrder();
  const { getSetting } = useOrgSettings();

  const { data: suppliersData } = useSuppliers();
  const { data: materialsData } = useMaterials();
  const { data: warehousesData } = useWarehouses();
  const { data: driversData } = useDrivers();
  const { data: vehiclesData } = useVehicles();
  const { data: formulasData } = useCurrentFormulas();
  const { data: profilesData } = useKgProfiles();

  const suppliers = suppliersData?.items ?? [];
  const materials = materialsData?.items ?? [];
  const warehouses = (warehousesData?.items ?? []) as { id: string; name: string }[];
  const drivers = driversData?.items ?? [];
  const vehicles = vehiclesData?.items ?? [];
  const formulas = formulasData?.items ?? [];
  const willardCenters = (getSetting("willard_distribution_centers") as string[] | null) ?? [];

  // Clasificacion Willard por material (CC-005): filtra el selector por tipo
  const worldByMaterial = useMemo(() => {
    const compra = new Map<string, boolean>();
    const world = new Map<string, WillardWorld>();
    for (const p of profilesData?.items ?? []) {
      compra.set(p.material_id, p.compra_regular);
      world.set(p.material_id, p.willard_world);
    }
    return { compra, world };
  }, [profilesData]);

  const [inboundType, setInboundType] = useState<InboundType>("purchase");
  const [warehouseId, setWarehouseId] = useState("");
  const [thirdPartyId, setThirdPartyId] = useState("");
  const [date, setDate] = useState(toLocalDateInput());
  const [driverId, setDriverId] = useState("");
  const [vehicleId, setVehicleId] = useState("");
  const [willardCenter, setWillardCenter] = useState("none");
  const [goesDirectly, setGoesDirectly] = useState(false);
  const [lines, setLines] = useState<LineFormData[]>([createEmptyLine()]);

  const isWillard = WILLARD_INBOUND_TYPES.includes(inboundType);
  const isPurchaseType = PURCHASE_INBOUND_TYPES.includes(inboundType);
  const todayStr = toLocalDateInput();
  const isFutureDate = date ? date > todayStr : false;

  // Willard: solo materiales de mundo Willard (postconsumo/drosses). Compra:
  // materiales marcados compra_regular; los sin clasificar se muestran (normales).
  const materialsForType = useMemo(() => {
    return materials.filter((m) => {
      const world = worldByMaterial.world.get(m.id) ?? "none";
      if (isWillard) return world !== "none";
      return worldByMaterial.compra.get(m.id) ?? true;
    });
  }, [materials, worldByMaterial, isWillard]);

  const unitSuffix = (materialId: string) => {
    const u = materials.find((m) => m.id === materialId)?.default_unit;
    return u ? ` (${u})` : "";
  };

  const updateLine = (key: number, field: keyof Omit<LineFormData, "_key">, value: string | number) => {
    setLines((prev) => prev.map((l) => (l._key === key ? { ...l, [field]: value } : l)));
  };

  // Preview "estimado" (solo tipos Willard)
  const lineEstimates = useMemo(() => {
    if (!isWillard) return new Map<number, number | null>();
    return new Map(
      lines.map((l) => [l._key, estimateKgLead(formulas, l.material_id, l.quantity)])
    );
  }, [isWillard, lines, formulas]);

  const totalEstimate = useMemo(() => {
    let total = 0;
    let hasAny = false;
    lineEstimates.forEach((v) => {
      if (v != null) {
        total += v;
        hasAny = true;
      }
    });
    return hasAny ? total : null;
  }, [lineEstimates]);

  const hasUnresolvedLines =
    isWillard && lines.some((l) => l.material_id && l.quantity > 0 && lineEstimates.get(l._key) == null);

  const canSubmit =
    !!warehouseId &&
    !!thirdPartyId &&
    !!date &&
    !isFutureDate &&
    lines.length > 0 &&
    lines.every((l) => l.material_id && l.quantity > 0);

  const handleSubmit = () => {
    if (!canSubmit) return;
    createOrder.mutate(
      {
        inbound_type: inboundType,
        warehouse_id: warehouseId,
        third_party_id: thirdPartyId,
        date,
        driver_id: driverId || null,
        vehicle_id: vehicleId || null,
        willard_distribution_center: isWillard && willardCenter !== "none" ? willardCenter : null,
        goes_directly_to_jm: isWillard ? goesDirectly : false,
        lines: lines.map((l) => ({
          material_id: l.material_id,
          quantity: l.quantity,
          unit_price: isPurchaseType && l.unit_price > 0 ? l.unit_price : null,
          scale_weight_kg: l.scale_weight_kg > 0 ? l.scale_weight_kg : null,
          quality_notes: l.quality_notes.trim() || null,
        })),
      },
      {
        onSuccess: (order) => navigate(buildRoute(ROUTES.INBOUND_DETAIL, { id: order.id })),
      }
    );
  };

  return (
    <div className="space-y-6">
      <PageHeader title="Nueva Recepción" description="Captura de entrada de material en patio">
        <Button variant="outline" onClick={() => navigate(ROUTES.INBOUND)}>
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
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Tipo de Recepción *</Label>
              <Select value={inboundType} onValueChange={(v) => setInboundType(v as InboundType)}>
                <SelectTrigger className="w-full"><SelectValue /></SelectTrigger>
                <SelectContent>
                  {(Object.keys(INBOUND_TYPE_LABELS) as InboundType[]).map((t) => (
                    <SelectItem key={t} value={t}>{INBOUND_TYPE_LABELS[t]}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Sede / Bodega *</Label>
              <EntitySelect
                value={warehouseId}
                onChange={setWarehouseId}
                options={warehouses.map((w) => ({ id: w.id, label: w.name }))}
                placeholder="Bodega..."
              />
            </div>
            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Tercero *</Label>
              <EntitySelect
                value={thirdPartyId}
                onChange={setThirdPartyId}
                options={suppliers.map((s) => ({ id: s.id, label: s.name }))}
                placeholder="Proveedor / tercero..."
              />
            </div>
            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Fecha *</Label>
              <Input
                type="date"
                value={date}
                max={todayStr}
                onChange={(e) => setDate(e.target.value)}
                className={isFutureDate ? "border-red-300" : ""}
              />
              {isFutureDate && <p className="text-xs text-red-500 mt-0.5">La fecha no puede ser futura</p>}
            </div>
            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Conductor</Label>
              <EntitySelect
                value={driverId}
                onChange={setDriverId}
                options={drivers.map((d) => ({ id: d.id, label: d.name }))}
                placeholder="Sin conductor..."
              />
            </div>
            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Vehículo</Label>
              <EntitySelect
                value={vehicleId}
                onChange={setVehicleId}
                options={vehicles.map((v) => ({
                  id: v.id,
                  label: v.display_name ? `${v.plate} - ${v.display_name}` : v.plate,
                }))}
                placeholder="Sin vehículo..."
              />
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Seccion Willard */}
      {isWillard && (
        <Card className="shadow-sm">
          <CardHeader>
            <CardTitle className="text-sm font-semibold uppercase tracking-wider text-slate-500">Datos Willard</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Centro de Distribución</Label>
                <Select value={willardCenter} onValueChange={setWillardCenter}>
                  <SelectTrigger className="w-full"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="none">Sin centro</SelectItem>
                    {willardCenters.map((c) => (
                      <SelectItem key={c} value={c}>{willardCenterLabel(c)}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="md:col-span-2 flex items-center gap-2">
                <Checkbox
                  id="goes-jm"
                  checked={goesDirectly}
                  onCheckedChange={(v) => setGoesDirectly(v === true)}
                />
                <Label htmlFor="goes-jm" className="text-sm font-normal cursor-pointer">
                  Va directamente a JM (informativo)
                </Label>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Nota por tipo */}
      <div className="flex items-start gap-2 rounded-lg border border-indigo-200 bg-indigo-50 px-3 py-2.5 text-sm text-indigo-800">
        <Info className="h-4 w-4 mt-0.5 shrink-0" />
        {isWillard ? (
          <span>
            La recepción Willard entra el material al inventario (a costo promedio, sin efecto financiero)
            y mueve la cuenta kg de cada línea según su clasificación (postconsumo → baterías por sede;
            drosses → drosses) y la fórmula vigente.
          </span>
        ) : (
          <span>
            Esta recepción crea una <strong>Compra registrada</strong> (inventario en tránsito, sin tocar
            cuentas kg). Los precios definitivos se fijan al liquidar la compra.
          </span>
        )}
      </div>

      {/* Lineas */}
      <Card className="shadow-sm">
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle className="text-sm font-semibold uppercase tracking-wider text-slate-500">Líneas de Material</CardTitle>
          <Button variant="outline" size="sm" onClick={() => setLines((p) => [...p, createEmptyLine()])}>
            <Plus className="h-4 w-4 mr-1" />
            Agregar Línea
          </Button>
        </CardHeader>
        <CardContent className="space-y-0">
          {lines.map((line, idx) => {
            const estimate = lineEstimates.get(line._key);
            return (
              <FormLineGrid
                key={line._key}
                isFirst={idx === 0}
                isLast={idx === lines.length - 1}
                onDelete={() => setLines((p) => p.filter((l) => l._key !== line._key))}
                disableDelete={lines.length === 1}
              >
                <div className="md:col-span-3">
                  <Label className={cn("text-xs font-semibold uppercase tracking-wider text-slate-500", lineLabelClass(idx))}>Material *</Label>
                  <EntitySelect
                    value={line.material_id}
                    onChange={(v) => updateLine(line._key, "material_id", v)}
                    options={materialsForType.map((m) => ({ id: m.id, label: `${m.code} - ${m.name}` }))}
                    placeholder="Material..."
                  />
                </div>
                <div className="md:col-span-2">
                  <Label className={cn("text-xs font-semibold uppercase tracking-wider text-slate-500", lineLabelClass(idx))}>
                    Cantidad{unitSuffix(line.material_id)} *
                  </Label>
                  <MoneyInput
                    value={line.quantity}
                    onChange={(v) => updateLine(line._key, "quantity", v)}
                    decimals={4}
                    placeholder="0"
                  />
                </div>
                {isPurchaseType && (
                  <div className="md:col-span-2">
                    <Label className={cn("text-xs font-semibold uppercase tracking-wider text-slate-500", lineLabelClass(idx))}>Precio Unit.</Label>
                    <MoneyInput
                      value={line.unit_price}
                      onChange={(v) => updateLine(line._key, "unit_price", v)}
                      decimals={2}
                      placeholder="0"
                    />
                  </div>
                )}
                <div className="md:col-span-2">
                  <Label className={cn("text-xs font-semibold uppercase tracking-wider text-slate-500", lineLabelClass(idx))}>Peso Báscula (kg)</Label>
                  <MoneyInput
                    value={line.scale_weight_kg}
                    onChange={(v) => updateLine(line._key, "scale_weight_kg", v)}
                    decimals={2}
                    placeholder="0,00"
                  />
                </div>
                <div className={isPurchaseType ? "md:col-span-2" : "md:col-span-3"}>
                  <Label className={cn("text-xs font-semibold uppercase tracking-wider text-slate-500", lineLabelClass(idx))}>Notas Calidad</Label>
                  <Input
                    value={line.quality_notes}
                    onChange={(e) => updateLine(line._key, "quality_notes", e.target.value)}
                    maxLength={500}
                    placeholder="Observaciones..."
                  />
                </div>
                {isWillard && (
                  <div className="md:col-span-1 md:text-right flex md:block items-center justify-between">
                    <Label className={cn("text-xs font-semibold uppercase tracking-wider text-slate-500", lineLabelClass(idx))}>Kg Est.</Label>
                    <p className="md:h-10 flex items-center md:justify-end text-sm font-medium tabular-nums text-indigo-600">
                      {estimate != null ? formatWeight(estimate) : "—"}
                    </p>
                  </div>
                )}
              </FormLineGrid>
            );
          })}

          {isWillard && (
            <div className="bg-indigo-50 border border-indigo-100 rounded-lg p-3 mt-2 space-y-1">
              <div className="flex justify-between items-center">
                <span className="text-sm text-indigo-800">Estimado total (kg plomo)</span>
                <span className="text-lg font-bold tabular-nums text-indigo-800">
                  {totalEstimate != null ? `+${formatWeight(totalEstimate)}` : "—"}
                </span>
              </div>
              <p className="text-xs text-indigo-600">
                Preview según las fórmulas vigentes — el valor definitivo lo calcula el sistema al confirmar.
                {hasUnresolvedLines &&
                  " Hay líneas sin fórmula vigente resuelta — se validará al confirmar."}
              </p>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Acciones */}
      <div className="sticky bottom-0 bg-white/95 backdrop-blur-sm border-t border-slate-100 py-4 -mx-3 px-3 md:-mx-6 md:px-6 mt-6 pb-[max(1rem,env(safe-area-inset-bottom))]">
        <div className="flex flex-col sm:flex-row sm:justify-end gap-2">
          <Button variant="outline" onClick={() => navigate(ROUTES.INBOUND)} className="w-full sm:w-auto">
            Cancelar
          </Button>
          <Button
            onClick={handleSubmit}
            disabled={!canSubmit || createOrder.isPending}
            className="bg-emerald-600 hover:bg-emerald-700 w-full sm:w-auto"
          >
            {createOrder.isPending ? "Creando..." : "Crear Recepción"}
          </Button>
        </div>
      </div>
    </div>
  );
}
