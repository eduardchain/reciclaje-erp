import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
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
import { PurchaseLink } from "@/components/shared/EntityLink";
import { FormLineGrid, lineLabelClass } from "@/components/shared/FormLineGrid";
import { useInboundOrder, useUpdateInboundOrder } from "@/hooks/useInboundOrders";
import { useMaterials, usePayableProviders } from "@/hooks/useMasterData";
import {
  useCreateDriver,
  useCreateVehicle,
  useDrivers,
  useKgProfiles,
  useVehicles,
} from "@/hooks/useSacConfig";
import { useOrgSettings } from "@/hooks/useOrgSettings";
import { toLocalDateInput, utcToLocalDateInput } from "@/utils/formatters";
import { buildRoute, ROUTES } from "@/utils/constants";
import { cn } from "@/utils";
import { willardCenterLabel } from "./InboundCreatePage";
import {
  INBOUND_TYPE_LABELS,
  WILLARD_INBOUND_TYPES,
  type InboundOrderLineCreate,
  type InboundOrderUpdate,
} from "@/types/inbound-order";

interface LineFormData {
  _key: number;
  material_id: string;
  quantity: number;
  /** #93: precio de referencia (solo tipo compra, informativo hasta liquidar) */
  unit_price: number;
  scale_weight_kg: number;
  quality_notes: string;
}

let lineKeyCounter = 0;

const toApiLines = (lines: LineFormData[], withPrice: boolean): InboundOrderLineCreate[] =>
  lines.map((l) => ({
    material_id: l.material_id,
    quantity: l.quantity,
    unit_price: withPrice && l.unit_price > 0 ? l.unit_price : null,
    scale_weight_kg: l.scale_weight_kg > 0 ? l.scale_weight_kg : null,
    quality_notes: l.quality_notes.trim() || null,
  }));

export default function InboundEditPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { data: order, isLoading } = useInboundOrder(id!);
  const updateOrder = useUpdateInboundOrder();
  const { getSetting } = useOrgSettings();

  const { data: materialsData } = useMaterials();
  const { data: driversData } = useDrivers();
  const { data: collectorsData } = usePayableProviders();
  const { data: vehiclesData } = useVehicles();
  const { data: profilesData } = useKgProfiles();

  const materials = materialsData?.items ?? [];
  const drivers = driversData?.items ?? [];
  const vehicles = vehiclesData?.items ?? [];
  const willardCenters = (getSetting("willard_distribution_centers") as string[] | null) ?? [];

  const [initialized, setInitialized] = useState(false);
  const [date, setDate] = useState("");
  const [driverId, setDriverId] = useState("");
  const [vehicleId, setVehicleId] = useState("");
  // Quick-create de flota: el Ciclo B lo agrego SOLO en la pagina de crear;
  // en edicion el operador quedaba atrapado con "Sin resultados" (reportado
  // por Daniel en pruebas 2026-08-04). Mismo dialogo, mismos hooks.
  const [driverDialogOpen, setDriverDialogOpen] = useState(false);
  const [vehicleDialogOpen, setVehicleDialogOpen] = useState(false);
  const [newDriverName, setNewDriverName] = useState("");
  const [newVehiclePlate, setNewVehiclePlate] = useState("");
  const createDriver = useCreateDriver();
  const createVehicle = useCreateVehicle();

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
  const [collectorId, setCollectorId] = useState("");
  const [willardCenter, setWillardCenter] = useState("none");
  const [notes, setNotes] = useState("");
  const [invoiceNumber, setInvoiceNumber] = useState("");
  const [remissionNumber, setRemissionNumber] = useState("");
  const [lines, setLines] = useState<LineFormData[]>([]);
  const [linesDirty, setLinesDirty] = useState(false);

  // Ciclo B (B2): el mundo de la orden se deriva de sus lineas (homogeneas) —
  // el picker de edicion queda filtrado a ese mundo
  const worldById = useMemo(() => {
    const map = new Map<string, string>();
    for (const p of profilesData?.items ?? []) map.set(p.material_id, p.willard_world);
    return map;
  }, [profilesData]);
  const orderWorld = useMemo(() => {
    for (const l of order?.lines ?? []) {
      const w = worldById.get(l.material_id);
      if (w && w !== "none") return w;
    }
    return null;
  }, [order, worldById]);

  useEffect(() => {
    if (order && !initialized) {
      setDate(utcToLocalDateInput(order.date));
      setDriverId(order.driver_id ?? "");
      setVehicleId(order.vehicle_id ?? "");
      setCollectorId(order.collector_id ?? "");
      setWillardCenter(order.willard_distribution_center ?? "none");
      setNotes(order.notes ?? "");
      setInvoiceNumber(order.invoice_number ?? "");
      setRemissionNumber(order.remission_number ?? "");
      setLines(
        order.lines.map((l) => ({
          _key: ++lineKeyCounter,
          material_id: l.material_id,
          quantity: Number(l.quantity),
          unit_price: l.unit_price != null ? Number(l.unit_price) : 0,
          scale_weight_kg: l.scale_weight_kg != null ? Number(l.scale_weight_kg) : 0,
          quality_notes: l.quality_notes ?? "",
        }))
      );
      setInitialized(true);
    }
  }, [order, initialized]);

  if (isLoading || !initialized) return <div className="p-8 text-center text-slate-500">Cargando...</div>;
  if (!order) return <div className="p-8 text-center text-slate-500">Entrada no encontrada</div>;
  if (order.status === "annulled") {
    return (
      <div className="p-8 text-center text-slate-500">
        Las entradas anuladas no se pueden editar.
        <div className="mt-4">
          <Button variant="outline" onClick={() => navigate(buildRoute(ROUTES.INBOUND_DETAIL, { id: order.id }))}>
            <ArrowLeft className="h-4 w-4 mr-2" />
            Volver al detalle
          </Button>
        </div>
      </div>
    );
  }

  const isWillard = WILLARD_INBOUND_TYPES.includes(order.inbound_type);
  const collectors = collectorsData?.items ?? [];
  // #93: legacy 1:1 (ciclos B-D) — su cara financiera es la compra derivada
  const isLegacy = !isWillard && !!order.purchase_id;
  // #93: lineas/fecha editables mientras la entrada no este liquidada (la
  // captura es la fuente de verdad, cero efectos que revertir — respuesta 4)
  const linesEditable = isWillard || (!isLegacy && order.status !== "liquidated");
  // Ciclo D/#93: el recolector se congela al liquidar — la comision ya se causo
  const collectorLocked = !isWillard && (
    isLegacy
      ? order.purchase_status != null && order.purchase_status !== "registered"
      : order.status === "liquidated"
  );
  const todayStr = toLocalDateInput();
  const isFutureDate = date ? date > todayStr : false;

  const unitOf = (materialId: string) =>
    materials.find((m) => m.id === materialId)?.default_unit || "";

  const unitSuffix = (materialId: string) => {
    const u = unitOf(materialId);
    return u ? ` (${u})` : "";
  };

  const markLinesDirty = () => setLinesDirty(true);

  const updateLine = (key: number, field: keyof Omit<LineFormData, "_key">, value: string | number) => {
    setLines((prev) => prev.map((l) => (l._key === key ? { ...l, [field]: value } : l)));
    markLinesDirty();
  };

  // Payload minimo: solo campos que cambiaron — en Willard, mandar lines/date
  // sin cambio dispararia un revert-and-reapply innecesario (D18)
  const originalDate = utcToLocalDateInput(order.date);

  const buildPayload = (): InboundOrderUpdate => {
    const payload: InboundOrderUpdate = {};
    if (linesEditable) {
      if (date && date !== originalDate) payload.date = date;
      if (linesDirty) payload.lines = toApiLines(lines, !isWillard);
    }
    if (isWillard) {
      if (willardCenter !== "none" && willardCenter !== (order.willard_distribution_center ?? "none")) {
        payload.willard_distribution_center = willardCenter;
      }
    }
    // El `&&` de antes hacia que vaciar el selector NO mandara nada: el
    // conductor/vehiculo no se podian QUITAR (misma asimetria que el backend
    // tenia con `is not None`, alineada en este ciclo). `|| null` manda el
    // borrado explicito que el servicio ya distingue via fields_set.
    if (driverId !== (order.driver_id ?? "")) payload.driver_id = driverId || null;
    if (vehicleId !== (order.vehicle_id ?? "")) payload.vehicle_id = vehicleId || null;
    // Ciclo D: null explicito quita el recolector. Willard: siempre editable
    // (informativo); tipo compra: congelado cuando la derivada no esta registered
    if (!collectorLocked && collectorId !== (order.collector_id ?? "")) {
      payload.collector_id = collectorId || null;
    }
    // Nota de cabecera: editable en AMBOS tipos (informativa, sin efectos)
    if (notes.trim() !== (order.notes ?? "")) payload.notes = notes.trim() || null;
    // #93 D12: factura editable en willard y legacy (en compra nueva vive en
    // el reparto → el campo ni se muestra); remision editable siempre
    if ((isWillard || isLegacy) && invoiceNumber.trim() !== (order.invoice_number ?? ""))
      payload.invoice_number = invoiceNumber.trim() || null;
    if (remissionNumber.trim() !== (order.remission_number ?? ""))
      payload.remission_number = remissionNumber.trim() || null;
    return payload;
  };

  const payload = buildPayload();
  const hasChanges = Object.keys(payload).length > 0;

  const linesValid = !linesEditable || (lines.length > 0 && lines.every((l) => l.material_id && l.quantity > 0));
  const canSubmit = hasChanges && linesValid && !isFutureDate && (!linesEditable || !!date);

  const handleSubmit = () => {
    if (!canSubmit) return;
    updateOrder.mutate(
      { id: order.id, data: payload },
      { onSuccess: () => navigate(buildRoute(ROUTES.INBOUND_DETAIL, { id: order.id })) }
    );
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title={`Editar Entrada #${order.order_number}`}
        description={INBOUND_TYPE_LABELS[order.inbound_type] ?? order.inbound_type}
      >
        <Button variant="outline" onClick={() => navigate(buildRoute(ROUTES.INBOUND_DETAIL, { id: order.id }))}>
          <ArrowLeft className="h-4 w-4 mr-2" />
          Volver
        </Button>
      </PageHeader>

      {/* Header inmutable */}
      <Card className="shadow-sm bg-slate-50/50">
        <CardContent className="pt-4 pb-4">
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 text-sm">
            <div>
              <span className="text-xs font-semibold uppercase tracking-wider text-slate-500 block">Tipo</span>
              <span>{INBOUND_TYPE_LABELS[order.inbound_type] ?? order.inbound_type}</span>
            </div>
            <div>
              <span className="text-xs font-semibold uppercase tracking-wider text-slate-500 block">Sede</span>
              <span>{order.warehouse_name ?? "—"}</span>
            </div>
            <div>
              <span className="text-xs font-semibold uppercase tracking-wider text-slate-500 block">Tercero</span>
              <span>{order.third_party_name ?? (isWillard ? "—" : "Se asigna al liquidar")}</span>
            </div>
          </div>
          <p className="text-xs text-slate-400 mt-2">
            Tipo y sede son inmutables — para cambiarlos, anule la orden y cree otra.
          </p>
        </CardContent>
      </Card>

      {/* Nota para tipos compra */}
      {!isWillard && isLegacy && (
        <div className="flex items-start gap-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2.5 text-sm text-amber-800">
          <Info className="h-4 w-4 mt-0.5 shrink-0" />
          <span>
            Esta entrada es del modelo anterior: las líneas y la fecha se editan
            en la compra derivada{" "}
            {order.purchase_id ? (
              <PurchaseLink id={order.purchase_id}>#{order.purchase_number}</PurchaseLink>
            ) : (
              `#${order.purchase_number ?? ""}`
            )}
            .
          </span>
        </div>
      )}
      {!isWillard && !isLegacy && order.status === "liquidated" && (
        <div className="flex items-start gap-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2.5 text-sm text-amber-800">
          <Info className="h-4 w-4 mt-0.5 shrink-0" />
          <span>
            La entrada está liquidada — solo se edita la cabecera informativa. Para tocar
            líneas o fecha, revierta la liquidación desde el detalle.
          </span>
        </div>
      )}

      {/* Cabecera editable */}
      <Card className="shadow-sm">
        <CardHeader>
          <CardTitle className="text-sm font-semibold uppercase tracking-wider text-slate-500">Cabecera</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {linesEditable && (
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
            )}
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
                disabled={collectorLocked}
              />
              <p className="text-[11px] text-slate-400 mt-0.5">
                {isWillard
                  ? "Solo registro — la recolección Willard no genera comisión"
                  : collectorLocked
                  ? "La compra ya se liquidó — la comisión ya se definió; el recolector no se puede cambiar"
                  : "La comisión se define al liquidar (va a gastos, no al costo)"}
              </p>
            </div>
            {isWillard && (
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
            )}
            {(isWillard || isLegacy) && (
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

      {/* Lineas — willard y tipo compra #93 (draft/reviewed) */}
      {linesEditable && (
        <Card className="shadow-sm">
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle className="text-sm font-semibold uppercase tracking-wider text-slate-500">Líneas de Material</CardTitle>
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                setLines((p) => [
                  ...p,
                  { _key: ++lineKeyCounter, material_id: "", quantity: 0, unit_price: 0, scale_weight_kg: 0, quality_notes: "" },
                ]);
                markLinesDirty();
              }}
            >
              <Plus className="h-4 w-4 mr-1" />
              Agregar Línea
            </Button>
          </CardHeader>
          <CardContent className="space-y-0">
            {lines.map((line, idx) => (
              <FormLineGrid
                key={line._key}
                isFirst={idx === 0}
                isLast={idx === lines.length - 1}
                onDelete={() => {
                  setLines((p) => p.filter((l) => l._key !== line._key));
                  markLinesDirty();
                }}
                disableDelete={lines.length === 1}
              >
                <div className={isWillard ? "md:col-span-4" : "md:col-span-3"}>
                  <Label className={cn("text-xs font-semibold uppercase tracking-wider text-slate-500", lineLabelClass(idx))}>Material *</Label>
                  <EntitySelect
                    value={line.material_id}
                    onChange={(v) => updateLine(line._key, "material_id", v)}
                    options={materials
                      .filter((m) =>
                        isWillard
                          ? !orderWorld || worldById.get(m.id) === orderWorld
                          : true
                      )
                      .map((m) => ({ id: m.id, label: `${m.code} - ${m.name}` }))}
                    placeholder="Material..."
                  />
                </div>
                <div className={isWillard ? "md:col-span-3" : "md:col-span-2"}>
                  <Label className={cn("text-xs font-semibold uppercase tracking-wider text-slate-500", lineLabelClass(idx))}>
                    Cantidad{unitSuffix(line.material_id)} *
                  </Label>
                  {/* Unidad DENTRO del input: el label se oculta de la 2a fila
                      en adelante en desktop (lineLabelClass) */}
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
                {!isWillard && (
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
                </div>
                <div className="md:col-span-2">
                  <Label className={cn("text-xs font-semibold uppercase tracking-wider text-slate-500", lineLabelClass(idx))}>Notas Calidad</Label>
                  <Input
                    value={line.quality_notes}
                    onChange={(e) => updateLine(line._key, "quality_notes", e.target.value)}
                    maxLength={500}
                    placeholder="Observaciones..."
                  />
                </div>
              </FormLineGrid>
            ))}
            <p className="text-xs text-amber-600 mt-2">
              {!isWillard
                ? "La captura es la fuente de verdad de lo pesado — corregir acá el error de báscula evita descuadres falsos al liquidar (respuesta 4). Cero efectos hasta liquidar."
                : order.status === "draft"
                  ? "La entrada está Registrada — editar solo actualiza el documento; los efectos nacen al liquidar."
                  : "Editar líneas o fecha re-emite los movimientos de inventario y kg (revert-and-reapply) — los saldos quedan exactos con los valores nuevos."}
            </p>
          </CardContent>
        </Card>
      )}

      {/* Acciones */}
      <div className="sticky bottom-0 bg-white/95 backdrop-blur-sm border-t border-slate-100 py-4 -mx-3 px-3 md:-mx-6 md:px-6 mt-6 pb-[max(1rem,env(safe-area-inset-bottom))]">
        <div className="flex flex-col sm:flex-row sm:justify-end gap-2">
          <Button
            variant="outline"
            onClick={() => navigate(buildRoute(ROUTES.INBOUND_DETAIL, { id: order.id }))}
            className="w-full sm:w-auto"
          >
            Cancelar
          </Button>
          <Button
            onClick={handleSubmit}
            disabled={!canSubmit || updateOrder.isPending}
            className="bg-emerald-600 hover:bg-emerald-700 w-full sm:w-auto"
          >
            {updateOrder.isPending ? "Guardando..." : "Guardar Cambios"}
          </Button>
        </div>
      </div>

      {/* Quick-create de flota (calco de InboundCreatePage) */}
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
    </div>
  );
}
