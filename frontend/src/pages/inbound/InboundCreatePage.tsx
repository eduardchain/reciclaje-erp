import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowLeft, Plus, Info } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
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
import { useKgAccounts } from "@/hooks/useKgLedger";
import { useMaterials, usePayableProviders, useWarehouses } from "@/hooks/useMasterData";
import {
  useCreateDriver,
  useCreateVehicle,
  useCurrentFormulas,
  useDrivers,
  useKgProfiles,
  useVehicles,
} from "@/hooks/useSacConfig";
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

  // Ciclo D: recolectores por comision (service_provider) — ambos tipos
  const { data: collectorsData } = usePayableProviders();
  const { data: materialsData } = useMaterials();
  const { data: warehousesData } = useWarehouses();
  const { data: driversData } = useDrivers();
  const { data: vehiclesData } = useVehicles();
  const { data: formulasData } = useCurrentFormulas();
  const { data: profilesData } = useKgProfiles();

  const collectors = collectorsData?.items ?? [];
  const materials = materialsData?.items ?? [];
  const warehouses = (warehousesData?.items ?? []) as { id: string; name: string; is_receiving?: boolean }[];
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
  const [willardWorld, setWillardWorld] = useState<"" | "drosses" | "postconsumo">("");
  const [warehouseId, setWarehouseId] = useState("");
  const [thirdPartyId, setThirdPartyId] = useState("");
  const [date, setDate] = useState(toLocalDateInput());
  const [driverId, setDriverId] = useState("");
  const [vehicleId, setVehicleId] = useState("");
  const [collectorId, setCollectorId] = useState("");
  const [willardCenter, setWillardCenter] = useState("none");
  const [notes, setNotes] = useState("");
  const [invoiceNumber, setInvoiceNumber] = useState("");
  // #93 D12: remision del camion — el documento de patio de la captura
  const [remissionNumber, setRemissionNumber] = useState("");
  const [lines, setLines] = useState<LineFormData[]>([createEmptyLine()]);

  // Quick-create de conductor/vehiculo (feedback Daniel: "deben ser creados
  // antes" era la friccion — ahora se crean en linea desde la captura)
  const createDriver = useCreateDriver();
  const createVehicle = useCreateVehicle();
  const [driverDialogOpen, setDriverDialogOpen] = useState(false);
  const [newDriverName, setNewDriverName] = useState("");
  const [vehicleDialogOpen, setVehicleDialogOpen] = useState(false);
  const [newVehiclePlate, setNewVehiclePlate] = useState("");

  const handleQuickCreateDriver = () => {
    const name = newDriverName.trim();
    if (!name) return;
    createDriver.mutate(
      { name },
      {
        onSuccess: (d) => {
          setDriverId(d.id);
          setDriverDialogOpen(false);
          setNewDriverName("");
        },
      }
    );
  };

  const handleQuickCreateVehicle = () => {
    const plate = newVehiclePlate.trim().toUpperCase();
    if (!plate) return;
    createVehicle.mutate(
      { plate },
      {
        onSuccess: (v) => {
          setVehicleId(v.id);
          setVehicleDialogOpen(false);
          setNewVehiclePlate("");
        },
      }
    );
  };

  const isWillard = WILLARD_INBOUND_TYPES.includes(inboundType);
  const isPurchaseType = PURCHASE_INBOUND_TYPES.includes(inboundType);
  const todayStr = toLocalDateInput();
  const isFutureDate = date ? date > todayStr : false;

  // Ciclo B (B2): sedes deterministas Willard desde org settings
  const sedeDrosses = (getSetting("willard_sede_drosses") as string | null) ?? null;
  const sedePostconsumoDefault =
    (getSetting("willard_sede_postconsumo_default") as string | null) ?? null;

  // Mejora Daniel (B2): en postconsumo el selector SOLO lista bodegas con
  // cuenta willard_baterias activa — la sede invalida es inalcanzable en UI
  const { data: batAccounts } = useKgAccounts({ account_type: "willard_baterias" });
  const { data: drossAccounts } = useKgAccounts({ account_type: "willard_drosses" });
  const batWarehouseIds = useMemo(() => {
    const set = new Set<string>();
    for (const a of batAccounts ?? []) {
      if (a.is_active && a.warehouse_id) set.add(a.warehouse_id);
    }
    return set;
  }, [batAccounts]);

  // Feedback Daniel: el tercero de una recepcion Willard ES el titular de la
  // cuenta kg — fijo e inamovible (como la sede en drosses). Se deriva de la
  // cuenta del mundo elegido (postconsumo: la de la sede; drosses: org-wide).
  const willardTitular = useMemo(() => {
    if (!isWillard || !willardWorld) return null;
    const pool = willardWorld === "drosses" ? drossAccounts : batAccounts;
    const account = (pool ?? []).find(
      (a) =>
        a.is_active &&
        (willardWorld === "drosses" ? !a.warehouse_id : a.warehouse_id === warehouseId)
    );
    if (!account?.third_party_id) return null;
    return { id: account.third_party_id, name: account.third_party_name ?? "Willard" };
  }, [isWillard, willardWorld, warehouseId, batAccounts, drossAccounts]);

  // #93: en compra regular ya no hay selector de tercero en la captura —
  // el filtro anti-Willard de proveedores vive ahora en la pagina de reparto

  // Willard: el sub-selector de mundo filtra el picker (una recepcion = UN
  // mundo, Q-10; sin mundo elegido no hay materiales). Compra: como siempre.
  const materialsForType = useMemo(() => {
    return materials.filter((m) => {
      const world = worldByMaterial.world.get(m.id) ?? "none";
      if (isWillard) return willardWorld !== "" && world === willardWorld;
      return worldByMaterial.compra.get(m.id) ?? true;
    });
  }, [materials, worldByMaterial, isWillard, willardWorld]);

  // Q-12 (feedback Daniel): la Recepcion solo lista bodegas RECEPTORAS — las
  // internas (molino/transito) se alimentan por Traslados, no por aca
  const receivingWarehouses = useMemo(
    () => warehouses.filter((w) => w.is_receiving !== false),
    [warehouses]
  );

  // Bodega gobernada por el mundo: drosses -> planta bloqueada; postconsumo ->
  // solo sedes receptoras con cuenta de baterias; compra -> receptoras
  const drossesLocked = isWillard && willardWorld === "drosses" && !!sedeDrosses;
  const warehouseOptions = useMemo(() => {
    if (isWillard && willardWorld === "postconsumo") {
      return receivingWarehouses.filter((w) => batWarehouseIds.has(w.id));
    }
    return receivingWarehouses;
  }, [receivingWarehouses, isWillard, willardWorld, batWarehouseIds]);
  const postconsumoSinSedes =
    isWillard && willardWorld === "postconsumo" && !!batAccounts && batWarehouseIds.size === 0;

  useEffect(() => {
    if (!isWillard || !willardWorld) return;
    if (willardWorld === "drosses") {
      if (sedeDrosses) setWarehouseId(sedeDrosses);
      return;
    }
    // postconsumo: conservar si es valida; default CV (setting) o primera valida
    setWarehouseId((prev) => {
      if (prev && batWarehouseIds.has(prev)) return prev;
      if (sedePostconsumoDefault && batWarehouseIds.has(sedePostconsumoDefault)) {
        return sedePostconsumoDefault;
      }
      return warehouseOptions[0]?.id ?? "";
    });
  }, [isWillard, willardWorld, sedeDrosses, sedePostconsumoDefault, batWarehouseIds, warehouseOptions]);

  // Tercero fijo al titular (feedback Daniel) — se re-deriva si cambia el
  // mundo o la sede; sin titular resoluble queda vacio (submit bloqueado)
  useEffect(() => {
    if (!isWillard) return;
    setThirdPartyId(willardTitular?.id ?? "");
  }, [isWillard, willardTitular]);

  // Cambiar de tipo resetea la captura (tercero/mundo/lineas son de canales
  // distintos — evita arrastrar valores invalidos entre tipos)
  const selectInboundType = (v: InboundType) => {
    setInboundType(v);
    setWillardWorld("");
    setThirdPartyId("");
    setLines([createEmptyLine()]);
  };

  // Cambiar de mundo limpia las lineas que ya no aplican (homogeneidad en UI)
  const selectWorld = (w: "drosses" | "postconsumo") => {
    setWillardWorld(w);
    setLines((prev) => {
      const kept = prev.filter(
        (l) => !l.material_id || worldByMaterial.world.get(l.material_id) === w
      );
      return kept.length ? kept : [createEmptyLine()];
    });
  };

  const unitOf = (materialId: string) =>
    materials.find((m) => m.id === materialId)?.default_unit || "";

  const unitSuffix = (materialId: string) => {
    const u = unitOf(materialId);
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
    // #93 D1: el tercero es SOLO de willard (titular cuenta kg) — la captura
    // tipo compra no registra proveedor (llega con el reparto al liquidar)
    (!isWillard || !!thirdPartyId) &&
    !!date &&
    !isFutureDate &&
    (!isWillard || !!willardWorld) &&
    !postconsumoSinSedes &&
    lines.length > 0 &&
    lines.every((l) => l.material_id && l.quantity > 0);

  const handleSubmit = () => {
    if (!canSubmit) return;
    createOrder.mutate(
      {
        inbound_type: inboundType,
        warehouse_id: warehouseId,
        third_party_id: isWillard ? thirdPartyId : null,
        date,
        driver_id: driverId || null,
        vehicle_id: vehicleId || null,
        collector_id: collectorId || null,
        willard_distribution_center: isWillard && willardCenter !== "none" ? willardCenter : null,
        notes: notes.trim() || null,
        // #93 D12: factura SOLO willard — en compra llega por proveedor al liquidar
        invoice_number: isWillard ? invoiceNumber.trim() || null : null,
        remission_number: remissionNumber.trim() || null,
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
      <PageHeader title="Nueva Entrada" description="Captura de entrada de material en patio">
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
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Tipo de Entrada *</Label>
              <Select value={inboundType} onValueChange={(v) => selectInboundType(v as InboundType)}>
                <SelectTrigger className="w-full"><SelectValue /></SelectTrigger>
                <SelectContent>
                  {(Object.keys(INBOUND_TYPE_LABELS) as InboundType[]).map((t) => (
                    <SelectItem key={t} value={t}>{INBOUND_TYPE_LABELS[t]}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            {isWillard && (
              <div>
                <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Tipo Willard *</Label>
                <Select
                  value={willardWorld || undefined}
                  onValueChange={(v) => selectWorld(v as "drosses" | "postconsumo")}
                >
                  <SelectTrigger className={cn("w-full", !willardWorld && "border-amber-300")}>
                    <SelectValue placeholder="Drosses o Postconsumo..." />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="postconsumo">Baterías Postconsumo</SelectItem>
                    <SelectItem value="drosses">Drosses</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            )}
            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Sede / Bodega *</Label>
              <EntitySelect
                value={warehouseId}
                onChange={setWarehouseId}
                options={warehouseOptions.map((w) => ({ id: w.id, label: w.name }))}
                placeholder={
                  isWillard && !willardWorld ? "Elija primero el mundo..." : "Bodega..."
                }
                disabled={drossesLocked || (isWillard && !willardWorld)}
              />
              {drossesLocked && (
                <p className="text-xs text-slate-400 mt-0.5">
                  Los drosses se reciben en la planta — bodega fija.
                </p>
              )}
              {postconsumoSinSedes && (
                <p className="text-xs text-red-500 mt-0.5">
                  No hay bodegas con cuenta de baterías postconsumo. Créala en Plomo (kg).
                </p>
              )}
            </div>
            {isWillard && (
              <div>
                <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Tercero *</Label>
                {/* Feedback Daniel: en Willard el tercero es el titular de la
                    cuenta kg — fijo e inamovible (como la sede en drosses).
                    #93: en tipo compra NO hay tercero en la captura — el
                    proveedor se asigna al liquidar, con el reparto. */}
                <Input
                  value={
                    willardTitular?.name ??
                    (willardWorld ? "Sin cuenta kg para este tipo" : "Se fija al elegir el tipo")
                  }
                  disabled
                />
              </div>
            )}
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
              <div className="flex gap-1.5">
                <div className="flex-1 min-w-0">
                  <EntitySelect
                    value={driverId}
                    onChange={setDriverId}
                    options={drivers.map((d) => ({ id: d.id, label: d.name }))}
                    placeholder="Sin conductor..."
                  />
                </div>
                <Button
                  type="button"
                  variant="outline"
                  size="icon"
                  className="shrink-0"
                  title="Crear conductor"
                  onClick={() => setDriverDialogOpen(true)}
                >
                  <Plus className="h-4 w-4" />
                </Button>
              </div>
            </div>
            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Vehículo</Label>
              <div className="flex gap-1.5">
                <div className="flex-1 min-w-0">
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
                <Button
                  type="button"
                  variant="outline"
                  size="icon"
                  className="shrink-0"
                  title="Crear vehículo"
                  onClick={() => setVehicleDialogOpen(true)}
                >
                  <Plus className="h-4 w-4" />
                </Button>
              </div>
            </div>
            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                Recolector{isWillard ? "" : " (comisión)"}
              </Label>
              <EntitySelect
                value={collectorId}
                onChange={setCollectorId}
                options={collectors.map((c) => ({ id: c.id, label: c.name }))}
                placeholder="Sin recolector..."
              />
              <p className="text-[11px] text-slate-400 mt-0.5">
                {isWillard
                  ? "Solo registro — la recolección Willard no genera comisión"
                  : "Green Loop u otro recolector — la comisión se define al liquidar (va a gastos, no al costo)"}
              </p>
            </div>
            {isWillard && (
              <div>
                <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                  N° Factura
                </Label>
                <Input
                  value={invoiceNumber}
                  onChange={(e) => setInvoiceNumber(e.target.value)}
                  maxLength={50}
                  className="w-full"
                  placeholder="Opcional"
                />
              </div>
            )}
            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                N° Remisión
              </Label>
              <Input
                value={remissionNumber}
                onChange={(e) => setRemissionNumber(e.target.value)}
                maxLength={50}
                className="w-full"
                placeholder="Remisión del camión (opcional)"
              />
              {isPurchaseType && (
                <p className="text-[11px] text-slate-400 mt-0.5">
                  La factura llega al liquidar, por proveedor
                </p>
              )}
            </div>
            <div className="md:col-span-2">
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Notas</Label>
              <Textarea
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                maxLength={1000}
                rows={2}
                placeholder="Observaciones de la captura (opcional)..."
              />
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Quick-create conductor / vehiculo (feedback Daniel) */}
      <Dialog open={driverDialogOpen} onOpenChange={setDriverDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Nuevo Conductor</DialogTitle>
          </DialogHeader>
          <div>
            <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Nombre *</Label>
            <Input
              value={newDriverName}
              onChange={(e) => setNewDriverName(e.target.value)}
              placeholder="Nombre del conductor..."
              autoFocus
              onKeyDown={(e) => e.key === "Enter" && handleQuickCreateDriver()}
            />
            <p className="text-xs text-slate-400 mt-1">
              Documento y teléfono se pueden completar después en Configuración → Flota.
            </p>
          </div>
          <DialogFooter className="gap-2">
            <Button variant="outline" onClick={() => setDriverDialogOpen(false)} className="w-full sm:w-auto">
              Cancelar
            </Button>
            <Button
              onClick={handleQuickCreateDriver}
              disabled={!newDriverName.trim() || createDriver.isPending}
              className="bg-emerald-600 hover:bg-emerald-700 w-full sm:w-auto"
            >
              {createDriver.isPending ? "Creando..." : "Crear y usar"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={vehicleDialogOpen} onOpenChange={setVehicleDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Nuevo Vehículo</DialogTitle>
          </DialogHeader>
          <div>
            <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Placa *</Label>
            <Input
              value={newVehiclePlate}
              onChange={(e) => setNewVehiclePlate(e.target.value.toUpperCase())}
              placeholder="ABC123"
              maxLength={10}
              autoFocus
              onKeyDown={(e) => e.key === "Enter" && handleQuickCreateVehicle()}
            />
            <p className="text-xs text-slate-400 mt-1">
              Tipo y descripción se pueden completar después en Configuración → Flota.
            </p>
          </div>
          <DialogFooter className="gap-2">
            <Button variant="outline" onClick={() => setVehicleDialogOpen(false)} className="w-full sm:w-auto">
              Cancelar
            </Button>
            <Button
              onClick={handleQuickCreateVehicle}
              disabled={!newVehiclePlate.trim() || createVehicle.isPending}
              className="bg-emerald-600 hover:bg-emerald-700 w-full sm:w-auto"
            >
              {createVehicle.isPending ? "Creando..." : "Crear y usar"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

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
            </div>
          </CardContent>
        </Card>
      )}

      {/* Nota por tipo */}
      <div className="flex items-start gap-2 rounded-lg border border-indigo-200 bg-indigo-50 px-3 py-2.5 text-sm text-indigo-800">
        <Info className="h-4 w-4 mt-0.5 shrink-0" />
        {isWillard ? (
          <span>
            La entrada Willard mete el material al inventario (a costo promedio, sin efecto financiero)
            y mueve la cuenta kg de cada línea según su clasificación (postconsumo → baterías por sede;
            drosses → drosses) y la fórmula vigente.
          </span>
        ) : (
          <span>
            La entrada registra <strong>lo que pesó la báscula</strong> — sin proveedor ni efectos.
            El proveedor (uno o varios) se asigna al <strong>liquidar</strong>, con el reparto;
            el precio de acá es referencia para ese momento.
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
                  {/* La unidad va DENTRO del input: en desktop el label se oculta
                      de la 2a fila en adelante (lineLabelClass) y kg vs unidad
                      dejaba de verse — pruebas de usuario */}
                  <div className="relative">
                    <MoneyInput
                      value={line.quantity}
                      onChange={(v) => updateLine(line._key, "quantity", v)}
                      decimals={4}
                      placeholder="0"
                      className={unitOf(line.material_id) ? "pr-16" : undefined}
                    />
                    {unitOf(line.material_id) && (
                      <span className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-xs font-medium text-slate-400">
                        {unitOf(line.material_id)}
                      </span>
                    )}
                  </div>
                </div>
                {isPurchaseType && (
                  <div className="md:col-span-2">
                    <Label className={cn("text-xs font-semibold uppercase tracking-wider text-slate-500", lineLabelClass(idx))}>Precio (ref.)</Label>
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
                  {/* D1/D2: opcional al capturar, obligatorio al REVISAR. Si el
                      material se mide en kg el revisor lo autocompleta con la
                      cantidad; si se mide por unidad (baterías) no hay de dónde
                      sacarlo y la revisión se rechaza. Sin este aviso el
                      pesador se entera cuando ya no está frente a la báscula. */}
                  {unitOf(line.material_id) &&
                    unitOf(line.material_id) !== "kg" &&
                    line.scale_weight_kg <= 0 && (
                      <p className="text-xs text-amber-600 mt-0.5">
                        Sin este peso no se puede revisar
                      </p>
                    )}
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
            {createOrder.isPending ? "Creando..." : "Registrar Entrada"}
          </Button>
        </div>
      </div>
    </div>
  );
}
