import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
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
import { PurchaseLink } from "@/components/shared/EntityLink";
import { FormLineGrid, lineLabelClass } from "@/components/shared/FormLineGrid";
import { useInboundOrder, useUpdateInboundOrder } from "@/hooks/useInboundOrders";
import { useMaterials } from "@/hooks/useMasterData";
import { useDrivers, useVehicles } from "@/hooks/useSacConfig";
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
  scale_weight_kg: number;
  quality_notes: string;
}

let lineKeyCounter = 0;

const toApiLines = (lines: LineFormData[]): InboundOrderLineCreate[] =>
  lines.map((l) => ({
    material_id: l.material_id,
    quantity: l.quantity,
    unit_price: null,
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
  const { data: vehiclesData } = useVehicles();

  const materials = materialsData?.items ?? [];
  const drivers = driversData?.items ?? [];
  const vehicles = vehiclesData?.items ?? [];
  const willardCenters = (getSetting("willard_distribution_centers") as string[] | null) ?? [];

  const [initialized, setInitialized] = useState(false);
  const [date, setDate] = useState("");
  const [driverId, setDriverId] = useState("");
  const [vehicleId, setVehicleId] = useState("");
  const [willardCenter, setWillardCenter] = useState("none");
  const [goesDirectly, setGoesDirectly] = useState(false);
  const [lines, setLines] = useState<LineFormData[]>([]);
  const [linesDirty, setLinesDirty] = useState(false);

  useEffect(() => {
    if (order && !initialized) {
      setDate(utcToLocalDateInput(order.date));
      setDriverId(order.driver_id ?? "");
      setVehicleId(order.vehicle_id ?? "");
      setWillardCenter(order.willard_distribution_center ?? "none");
      setGoesDirectly(order.goes_directly_to_jm);
      setLines(
        order.lines.map((l) => ({
          _key: ++lineKeyCounter,
          material_id: l.material_id,
          quantity: Number(l.quantity),
          scale_weight_kg: l.scale_weight_kg != null ? Number(l.scale_weight_kg) : 0,
          quality_notes: l.quality_notes ?? "",
        }))
      );
      setInitialized(true);
    }
  }, [order, initialized]);

  if (isLoading || !initialized) return <div className="p-8 text-center text-slate-500">Cargando...</div>;
  if (!order) return <div className="p-8 text-center text-slate-500">Recepción no encontrada</div>;
  if (order.status === "annulled") {
    return (
      <div className="p-8 text-center text-slate-500">
        Las recepciones anuladas no se pueden editar.
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
  const todayStr = toLocalDateInput();
  const isFutureDate = date ? date > todayStr : false;

  const unitSuffix = (materialId: string) => {
    const u = materials.find((m) => m.id === materialId)?.default_unit;
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
    if (isWillard) {
      if (date && date !== originalDate) payload.date = date;
      if (linesDirty) payload.lines = toApiLines(lines);
      if (willardCenter !== "none" && willardCenter !== (order.willard_distribution_center ?? "none")) {
        payload.willard_distribution_center = willardCenter;
      }
      if (goesDirectly !== order.goes_directly_to_jm) {
        payload.goes_directly_to_jm = goesDirectly;
      }
    }
    if (driverId && driverId !== (order.driver_id ?? "")) payload.driver_id = driverId;
    if (vehicleId && vehicleId !== (order.vehicle_id ?? "")) payload.vehicle_id = vehicleId;
    return payload;
  };

  const payload = buildPayload();
  const hasChanges = Object.keys(payload).length > 0;

  const linesValid = !isWillard || (lines.length > 0 && lines.every((l) => l.material_id && l.quantity > 0));
  const canSubmit = hasChanges && linesValid && !isFutureDate && (!isWillard || !!date);

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
        title={`Editar Recepción #${order.order_number}`}
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
              <span>{order.third_party_name ?? "—"}</span>
            </div>
          </div>
          <p className="text-xs text-slate-400 mt-2">
            Tipo, sede y tercero son inmutables — para cambiarlos, anule la orden y cree otra.
          </p>
        </CardContent>
      </Card>

      {/* Nota para tipos compra */}
      {!isWillard && (
        <div className="flex items-start gap-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2.5 text-sm text-amber-800">
          <Info className="h-4 w-4 mt-0.5 shrink-0" />
          <span>
            En recepciones tipo compra solo se editan conductor y vehículo — las líneas y la fecha se editan
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

      {/* Cabecera editable */}
      <Card className="shadow-sm">
        <CardHeader>
          <CardTitle className="text-sm font-semibold uppercase tracking-wider text-slate-500">Cabecera</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {isWillard && (
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
            {isWillard && (
              <>
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
                    id="goes-jm-edit"
                    checked={goesDirectly}
                    onCheckedChange={(v) => setGoesDirectly(v === true)}
                  />
                  <Label htmlFor="goes-jm-edit" className="text-sm font-normal cursor-pointer">
                    Va directamente a JM (informativo)
                  </Label>
                </div>
              </>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Lineas (solo Willard) */}
      {isWillard && (
        <Card className="shadow-sm">
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle className="text-sm font-semibold uppercase tracking-wider text-slate-500">Líneas de Material</CardTitle>
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                setLines((p) => [
                  ...p,
                  { _key: ++lineKeyCounter, material_id: "", quantity: 0, scale_weight_kg: 0, quality_notes: "" },
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
                <div className="md:col-span-4">
                  <Label className={cn("text-xs font-semibold uppercase tracking-wider text-slate-500", lineLabelClass(idx))}>Material *</Label>
                  <EntitySelect
                    value={line.material_id}
                    onChange={(v) => updateLine(line._key, "material_id", v)}
                    options={materials.map((m) => ({ id: m.id, label: `${m.code} - ${m.name}` }))}
                    placeholder="Material..."
                  />
                </div>
                <div className="md:col-span-3">
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
              Editar líneas o fecha re-emite los movimientos de inventario y kg (revert-and-reapply) —
              los saldos quedan exactos con los valores nuevos.
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
    </div>
  );
}
