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
import { useCurrentFormulas, useCurrentTariffs, useKgProfiles } from "@/hooks/useSacConfig";
import { useOrgSettings } from "@/hooks/useOrgSettings";
import { useCreateCrucibleCharge } from "@/hooks/useCrucibleCharges";
import { formatCurrency, formatWeightPrecise as formatWeight, toLocalDateInput } from "@/utils/formatters";
import { cn } from "@/utils";
import { CRUCIBLE_EVENT_LABELS, num, type CrucibleEventType } from "@/types/crucible-charge";

const EVENTS: { value: CrucibleEventType; hint: string }[] = [
  {
    value: "charge",
    hint: "Plomo crudo que pasa del horno grande al crisol. Baja la etapa horno y sube la etapa crisol; la deuda total no cambia. En inventario sale crudo y entra puro, kilo por kilo.",
  },
  {
    value: "dross_return",
    hint: "Dross del crisol que vuelve al horno grande. Se digitan los kg de DROSS: el crisol baja esos kg y el horno sube solo el plomo que contienen. La maquila del horno se causa otra vez, sobre ese plomo.",
  },
];

// El inventario guarda tres decimales: se redondea igual que el servidor
// (`CRUCIBLE_Q`), o la vista previa mostraría un número que no se va a guardar.
const round3 = (n: number) => Math.round(n * 1000) / 1000;

/**
 * Documento de crisol (#107 D2, corregido en #109 con el cierre del cliente).
 * Un solo paso: no hay revisor en salidas. Desde #109 el documento lleva DOS
 * cantidades (kg físicos y kg de plomo) y mueve inventario él mismo — las
 * conversiones crudo ↔ puro ya NO se registran aparte en Transformaciones.
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
  const { data: formulasData } = useCurrentFormulas();
  const { data: tariffsData } = useCurrentTariffs();
  const { data: summary } = useKgSummary();
  const { getSetting, flagEnabled } = useOrgSettings();
  const [puroId, setPuroId] = useState("");
  const [crudoId, setCrudoId] = useState("");

  const materials = useMemo(() => materialsData?.items ?? [], [materialsData]);
  const warehouses = useMemo(() => {
    const list = Array.isArray(warehousesData) ? warehousesData : warehousesData?.items ?? [];
    return list.filter((w) => w.is_active && !w.is_transit);
  }, [warehousesData]);

  // Al crisol solo entra plomo CRUDO (spec §4.1) — el backend lo defiende con
  // 422, pero ofrecer el catálogo entero es pedirle al usuario que descubra
  // la regla después de llenar el formulario (#103, misma lección que la
  // Entrada). El retorno de dross es el dross, que no lleva marca.
  const leadOf = useMemo(() => {
    const lead = new Map<string, string>();
    for (const prof of profilesData?.items ?? []) lead.set(prof.material_id, prof.lead_product);
    return lead;
  }, [profilesData]);

  // Mundo Willard por material. Los materiales que MANDA Willard (guarru,
  // cenizas, scrap…) también tienen fórmula de dross — 15 de 16 en SAC — y no
  // son dross del crisol: son insumos que llegan con deuda. Lo que sale del
  // crisol es de proceso propio, o sea sin mundo Willard.
  const worldOf = useMemo(() => {
    const world = new Map<string, string>();
    for (const prof of profilesData?.items ?? []) world.set(prof.material_id, prof.willard_world);
    return world;
  }, [profilesData]);

  // % de plomo por material, de la fórmula VIGENTE tipo dross. Sin fórmula el
  // servidor rechaza el retorno (422): no se cae a 1:1, porque subir el horno
  // por los kg de dross es justo el defecto que se corrigió. Por eso el selector
  // del retorno solo ofrece materiales que la tienen.
  const drossPct = useMemo(() => {
    const pct = new Map<string, number>();
    for (const f of formulasData?.items ?? []) {
      if (f.formula_type === "drosses_to_lead") pct.set(f.material_id, num(f.parameters.lead_percentage as number | string));
    }
    return pct;
  }, [formulasData]);

  const materialOptions = useMemo(() => {
    return materials
      .filter((m) => m.is_active !== false)
      .filter((m) =>
        eventType === "charge"
          ? leadOf.get(m.id) === "crudo"
          : drossPct.has(m.id) && (worldOf.get(m.id) ?? "none") === "none",
      )
      .map((m) => ({ id: m.id, label: `${m.code} - ${m.name} (${m.default_unit ?? "kg"})` }));
  }, [materials, leadOf, worldOf, drossPct, eventType]);

  // El material que entra/sale del inventario lo decide la marca (#103), no un
  // nombre. Con uno solo se usa ese; con más de uno hay que decir cuál.
  const byLead = (lead: string) =>
    materials.filter((m) => m.is_active !== false && leadOf.get(m.id) === lead);
  const puros = byLead("puro");
  const crudos = byLead("crudo");
  const puro = puros.length === 1 ? puros[0] : puros.find((m) => m.id === puroId);
  const crudoDest = crudos.length === 1 ? crudos[0] : crudos.find((m) => m.id === crudoId);

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

  const horno = num(summary?.intersede_horno_kg);
  const crisol = num(summary?.intersede_crisol_kg);
  const [downLabel, downBefore, upLabel, upBefore] =
    eventType === "charge"
      ? ["En horno (crudo)", horno, "En crisol", crisol]
      : ["En crisol", crisol, "En horno (crudo)", horno];

  // Dos cantidades: lo físico baja una etapa, el PLOMO sube la otra.
  const isDross = eventType === "dross_return";
  const pct = isDross ? drossPct.get(materialId) : 1;
  const leadKg = pct === undefined ? 0 : round3(quantity * pct);
  const lossKg = round3(quantity - leadKg);
  const downAfter = downBefore - quantity;
  const totalBefore = horno + crisol;

  const maquilaOn = flagEnabled("internal_maquila_enabled");
  const maquilaTariff = (tariffsData?.items ?? []).find(
    (t) => t.tariff_code === "maquila_intersede_cv_jm",
  );
  const maquilaAmount = maquilaTariff ? Math.round(leadKg * num(maquilaTariff.unit_price_cop)) : 0;

  const source = materials.find((m) => m.id === materialId);
  const invOut = isDross ? puro : source;
  const invIn = isDross ? crudoDest : puro;
  const needsPuro = puros.length !== 1;
  const needsCrudo = isDross && crudos.length !== 1;
  const destReady = isDross ? !!puro && !!crudoDest : !!puro;

  const isFuture = date > today;
  const canSubmit =
    !!warehouseId && !!materialId && quantity > 0 && leadKg > 0 && destReady && !!date && !isFuture;

  const submit = async () => {
    const created = await createMutation.mutateAsync({
      event_type: eventType,
      warehouse_id: warehouseId,
      material_id: materialId,
      quantity_kg: String(quantity),
      date: `${date}T12:00:00`,
      notes: notes.trim() || null,
      // Solo viajan si hubo que elegir: con un único marcado decide el servidor.
      puro_material_id: puros.length > 1 ? puro?.id ?? null : null,
      crudo_material_id: isDross && crudos.length > 1 ? crudoDest?.id ?? null : null,
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
                placeholder={eventType === "charge" ? "Solo materiales marcados como crudo..." : "Solo dross de proceso propio con % de plomo..."}
              />
              {isDross && materialOptions.length === 0 && (
                <p className="text-xs text-amber-600 mt-0.5">
                  Ningún material de proceso propio tiene fórmula de dross (% de plomo). Créela en Config → Materiales (kg).
                </p>
              )}
              {eventType === "charge" && materialOptions.length === 0 && (
                <p className="text-xs text-amber-600 mt-0.5">
                  Ningún material está marcado como plomo crudo. Márquelo en Config → Materiales (kg).
                </p>
              )}
            </div>
            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                {isDross ? "Kg de dross *" : "Kg de plomo crudo *"}
              </Label>
              <MoneyInput value={quantity} onChange={setQuantity} decimals={3} placeholder="0,000" />
              {isDross && pct !== undefined && quantity > 0 && (
                <p className="text-xs text-slate-500 mt-0.5">
                  Al {formatWeight(pct * 100, "%")} de plomo: {formatWeight(leadKg)} de plomo vuelven al horno.
                </p>
              )}
            </div>
          </div>

          {(needsPuro || needsCrudo) && (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {needsPuro && (
                <div>
                  <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                    {isDross ? "Plomo puro que sale del inventario *" : "Plomo puro que entra al inventario *"}
                  </Label>
                  {puros.length === 0 ? (
                    <p className="text-xs text-amber-600 mt-1">
                      Ningún material está marcado como plomo puro. Márquelo en Config → Materiales (kg).
                    </p>
                  ) : (
                    <EntitySelect
                      value={puroId}
                      onChange={setPuroId}
                      options={puros.map((m) => ({ id: m.id, label: `${m.code} - ${m.name}` }))}
                      placeholder="Hay más de un plomo puro: elija cuál..."
                    />
                  )}
                </div>
              )}
              {needsCrudo && (
                <div>
                  <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                    Plomo crudo que entra al inventario *
                  </Label>
                  {crudos.length === 0 ? (
                    <p className="text-xs text-amber-600 mt-1">
                      Ningún material está marcado como plomo crudo. Márquelo en Config → Materiales (kg).
                    </p>
                  ) : (
                    <EntitySelect
                      value={crudoId}
                      onChange={setCrudoId}
                      options={crudos.map((m) => ({ id: m.id, label: `${m.code} - ${m.name}` }))}
                      placeholder="Hay más de un plomo crudo: elija cuál..."
                    />
                  )}
                </div>
              )}
            </div>
          )}

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
            <span className="tabular-nums">{formatWeight(upBefore)} → {formatWeight(upBefore + leadKg)}</span>
          </div>
          <div className="flex justify-between gap-3 border-t pt-1 mt-1">
            <span className="text-slate-500">Deuda total</span>
            <span className="tabular-nums">
              {lossKg > 0
                ? `${formatWeight(totalBefore)} → ${formatWeight(totalBefore - lossKg)}`
                : `${formatWeight(totalBefore)} (no cambia)`}
            </span>
          </div>
          {lossKg > 0 && (
            <p className="text-xs text-slate-500 pt-1">
              La deuda total baja {formatWeight(lossKg)}: es lo que el dross tiene que no es plomo. Es lo esperado en un retorno.
            </p>
          )}
          {downAfter < 0 && quantity > 0 && (
            <p className="text-xs text-amber-700 pt-1">
              La etapa {downLabel.toLowerCase()} queda en negativo. Se registra igual, con aviso.
            </p>
          )}
          {isDross && (
            <p className="text-xs text-slate-500 pt-1">
              {!maquilaOn
                ? "La maquila interna está apagada: no se causa maquila por este retorno."
                : maquilaTariff
                  ? `Maquila del reproceso: ${formatWeight(leadKg)} de plomo × ${formatCurrency(num(maquilaTariff.unit_price_cop))} = ${formatCurrency(maquilaAmount)}, de la sede que factura a planta.`
                  : "No hay tarifa vigente de maquila intersede: el retorno se registra sin maquila, con aviso."}
            </p>
          )}
        </CardContent>
      </Card>

      <Card className="bg-slate-50/60">
        <CardContent className="p-4 text-sm space-y-1">
          <div className="font-medium">Efecto sobre el inventario</div>
          <div className="flex justify-between gap-3">
            <span className="text-slate-500">Sale {invOut ? `${invOut.code} - ${invOut.name}` : "—"}</span>
            <span className="tabular-nums">−{formatWeight(quantity)}</span>
          </div>
          <div className="flex justify-between gap-3">
            <span className="text-slate-500">Entra {invIn ? `${invIn.code} - ${invIn.name}` : "—"}</span>
            <span className="tabular-nums">+{formatWeight(leadKg)}</span>
          </div>
          {lossKg > 0 && (
            <div className="flex justify-between gap-3">
              <span className="text-slate-500">Merma</span>
              <span className="tabular-nums">{formatWeight(lossKg)}</span>
            </div>
          )}
          <p className="text-xs text-slate-500 pt-1">
            El documento mueve el inventario él mismo. No registre además una transformación entre plomo crudo y plomo puro.
          </p>
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
