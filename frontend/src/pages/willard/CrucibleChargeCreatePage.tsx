import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowLeft } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { PageHeader } from "@/components/shared/PageHeader";
import { EntitySelect } from "@/components/shared/EntitySelect";
import { MoneyInput } from "@/components/shared/MoneyInput";
import { useMaterials, useWarehouses } from "@/hooks/useMasterData";
import { useKgSummary } from "@/hooks/useKgLedger";
import { useKgProfiles } from "@/hooks/useSacConfig";
import { useOrgSettings } from "@/hooks/useOrgSettings";
import { useCreateCrucibleCharge } from "@/hooks/useCrucibleCharges";
import { formatWeight, toLocalDateInput } from "@/utils/formatters";
import { cn } from "@/utils";
import { CRUCIBLE_EVENT_LABELS, type CrucibleEventType } from "@/types/crucible-charge";

const EVENTS: { value: CrucibleEventType; hint: string }[] = [
  {
    value: "charge",
    hint: "Plomo crudo que pasa del horno grande al crisol. Baja la etapa horno y sube la etapa crisol; la deuda total no cambia.",
  },
  {
    value: "dross_return",
    hint: "Dross del crisol que vuelve al horno grande. Baja la etapa crisol y sube la etapa horno; se causa otra vez la maquila del horno.",
  },
];

/**
 * Documento de crisol (#107 D2). Un solo paso: no hay revisor en salidas y
 * aquí ni siquiera hay pesos que certificar. Las conversiones físicas
 * (crudo → puro + dross, dross → crudo) siguen siendo transformaciones.
 */
export default function CrucibleChargeCreatePage() {
  const navigate = useNavigate();
  const createMutation = useCreateCrucibleCharge();

  const today = toLocalDateInput(new Date());
  const [eventType, setEventType] = useState<CrucibleEventType>("charge");
  const [warehouseId, setWarehouseId] = useState("");
  const [materialId, setMaterialId] = useState("");
  const [quantity, setQuantity] = useState(0);
  const [date, setDate] = useState(today);
  const [notes, setNotes] = useState("");

  const { data: materialsData } = useMaterials();
  const { data: warehousesData } = useWarehouses();
  const { data: profilesData } = useKgProfiles();
  const { data: summary } = useKgSummary();
  const { getSetting } = useOrgSettings();

  const materials = useMemo(() => materialsData?.items ?? [], [materialsData]);
  const warehouses = useMemo(() => {
    const list = Array.isArray(warehousesData) ? warehousesData : warehousesData?.items ?? [];
    return list.filter((w) => w.is_active && !w.is_transit);
  }, [warehousesData]);

  // Al crisol solo entra plomo CRUDO (spec §4.1) — el backend lo defiende con
  // 422, pero ofrecer el catálogo entero es pedirle al usuario que descubra
  // la regla después de llenar el formulario (#103, misma lección que la
  // Entrada). El retorno de dross es el dross, que no lleva marca.
  const materialOptions = useMemo(() => {
    const lead = new Map<string, string>();
    for (const prof of profilesData?.items ?? []) lead.set(prof.material_id, prof.lead_product);
    return materials
      .filter((m) => m.is_active !== false)
      .filter((m) => (eventType === "charge" ? lead.get(m.id) === "crudo" : true))
      .map((m) => ({ id: m.id, label: `${m.code} - ${m.name} (${m.default_unit ?? "kg"})` }));
  }, [materials, profilesData, eventType]);

  // D8 (#100): el crisol vive en planta. El backend lo defiende; la pantalla
  // fija el valor que el sistema ya conoce.
  const plantWarehouseId = (getSetting("willard_sede_drosses") as string | null) ?? "";
  const plantWarehouse = warehouses.find((w) => w.id === plantWarehouseId);
  useEffect(() => {
    if (plantWarehouseId && warehouseId !== plantWarehouseId) setWarehouseId(plantWarehouseId);
  }, [plantWarehouseId, warehouseId]);

  // Si el material elegido deja de ser válido al cambiar el tipo, se limpia.
  useEffect(() => {
    if (materialId && !materialOptions.some((o) => o.id === materialId)) setMaterialId("");
  }, [materialId, materialOptions]);

  const horno = summary?.intersede_horno_kg ?? 0;
  const crisol = summary?.intersede_crisol_kg ?? 0;
  const [downLabel, downBefore, upLabel, upBefore] =
    eventType === "charge"
      ? ["En horno (crudo)", horno, "En crisol", crisol]
      : ["En crisol", crisol, "En horno (crudo)", horno];
  const downAfter = downBefore - quantity;

  const isFuture = date > today;
  const canSubmit = !!warehouseId && !!materialId && quantity > 0 && !!date && !isFuture;

  const submit = async () => {
    const created = await createMutation.mutateAsync({
      event_type: eventType,
      warehouse_id: warehouseId,
      material_id: materialId,
      quantity_kg: String(quantity),
      date: `${date}T12:00:00`,
      notes: notes.trim() || null,
    });
    navigate(`/willard-deliveries/crisol/${created.id}`, { replace: true });
  };

  return (
    <div className="space-y-4">
      <PageHeader title="Nuevo documento de crisol" description="Traslado a crisoles o retorno de dross al horno, en planta">
        <Button variant="outline" onClick={() => navigate("/willard-deliveries?type=crisol")} className="w-full sm:w-auto">
          <ArrowLeft className="h-4 w-4 mr-2" /> Volver
        </Button>
      </PageHeader>

      <Card>
        <CardHeader><CardTitle className="text-base">Documento</CardTitle></CardHeader>
        <CardContent className="space-y-4">
          <div>
            <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Tipo *</Label>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 mt-1">
              {EVENTS.map((e) => (
                <button
                  type="button"
                  key={e.value}
                  onClick={() => setEventType(e.value)}
                  className={cn(
                    "text-left rounded-md border p-3 transition-colors",
                    eventType === e.value
                      ? "border-indigo-500 bg-indigo-50 ring-1 ring-indigo-500"
                      : "border-slate-200 hover:bg-slate-50",
                  )}
                >
                  <div className="font-medium text-sm">{CRUCIBLE_EVENT_LABELS[e.value]}</div>
                  <div className="text-xs text-slate-500 mt-1">{e.hint}</div>
                </button>
              ))}
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Planta *</Label>
              {plantWarehouseId ? (
                <Input value={plantWarehouse?.name ?? "Planta"} disabled />
              ) : (
                <EntitySelect
                  value={warehouseId}
                  onChange={setWarehouseId}
                  options={warehouses.map((w) => ({ id: w.id, label: w.name }))}
                  placeholder="Bodega de planta..."
                />
              )}
            </div>
            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Fecha *</Label>
              <Input
                type="date"
                value={date}
                max={today}
                onChange={(e) => setDate(e.target.value)}
                className={isFuture ? "border-red-300" : ""}
              />
              {isFuture && <p className="text-xs text-red-500 mt-0.5">La fecha no puede ser futura</p>}
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                {eventType === "charge" ? "Plomo crudo *" : "Material (dross) *"}
              </Label>
              <EntitySelect
                value={materialId}
                onChange={setMaterialId}
                options={materialOptions}
                placeholder={eventType === "charge" ? "Solo materiales marcados como crudo..." : "Material..."}
              />
              {eventType === "charge" && materialOptions.length === 0 && (
                <p className="text-xs text-amber-600 mt-0.5">
                  Ningún material está marcado como plomo crudo. Márquelo en Config → Materiales (kg).
                </p>
              )}
            </div>
            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Kg de plomo *</Label>
              <MoneyInput value={quantity} onChange={setQuantity} decimals={2} placeholder="0,00" />
            </div>
          </div>

          <div>
            <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Notas</Label>
            <Textarea value={notes} onChange={(e) => setNotes(e.target.value)} rows={2} maxLength={1000} />
          </div>
        </CardContent>
      </Card>

      {/* Vista previa: lo que hace el documento sobre las dos etapas. Avisa,
          no bloquea (#17/#76) — el backend devuelve el mismo aviso en la respuesta. */}
      <Card className={cn(downAfter < 0 && quantity > 0 ? "border-amber-300 bg-amber-50/60" : "bg-slate-50/60")}>
        <CardContent className="p-4 text-sm space-y-1">
          <div className="font-medium">Efecto sobre la deuda intersede (planta → Circunvalar)</div>
          <div className="flex justify-between gap-3">
            <span className="text-slate-500">{downLabel}</span>
            <span className="tabular-nums">
              {formatWeight(downBefore)} → <span className={cn(downAfter < 0 && "text-amber-700 font-semibold")}>{formatWeight(downAfter)}</span>
            </span>
          </div>
          <div className="flex justify-between gap-3">
            <span className="text-slate-500">{upLabel}</span>
            <span className="tabular-nums">{formatWeight(upBefore)} → {formatWeight(upBefore + quantity)}</span>
          </div>
          <div className="flex justify-between gap-3 border-t pt-1 mt-1">
            <span className="text-slate-500">Deuda total</span>
            <span className="tabular-nums">{formatWeight(horno + crisol)} (no cambia)</span>
          </div>
          {downAfter < 0 && quantity > 0 && (
            <p className="text-xs text-amber-700 pt-1">
              La etapa {downLabel.toLowerCase()} queda en negativo. Se registra igual, con aviso.
            </p>
          )}
          {eventType === "dross_return" && (
            <p className="text-xs text-slate-500 pt-1">
              Se causa la maquila del reproceso (tarifa vigente de maquila intersede × kg) de planta a la sede que factura, si la maquila interna está activa.
            </p>
          )}
        </CardContent>
      </Card>

      <div className="sticky bottom-0 bg-white border-t -mx-3 px-3 md:-mx-6 md:px-6 pb-[max(1rem,env(safe-area-inset-bottom))] pt-3 flex flex-col sm:flex-row sm:justify-end gap-2">
        <Button variant="outline" onClick={() => navigate("/willard-deliveries?type=crisol")} className="w-full sm:w-auto">
          Cancelar
        </Button>
        <Button onClick={submit} disabled={!canSubmit || createMutation.isPending} className="w-full sm:w-auto">
          {createMutation.isPending ? "Registrando..." : "Registrar"}
        </Button>
      </div>
    </div>
  );
}
