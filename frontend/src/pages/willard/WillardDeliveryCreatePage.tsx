import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowLeft, Plus, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { PageHeader } from "@/components/shared/PageHeader";
import { EntitySelect } from "@/components/shared/EntitySelect";
import { MoneyInput } from "@/components/shared/MoneyInput";
import { FormLineGrid } from "@/components/shared/FormLineGrid";
import { useCustomers, useMaterials, useWarehouses } from "@/hooks/useMasterData";
import { useCreateWillardDelivery } from "@/hooks/useWillardDeliveries";
import { useKgAccounts } from "@/hooks/useKgLedger";
import { useKgProfiles } from "@/hooks/useSacConfig";
import { useOrgSettings } from "@/hooks/useOrgSettings";
import { toLocalDateInput } from "@/utils/formatters";
import { DELIVERY_TYPE_LABELS, type WillardDeliveryType } from "@/types/willard-delivery";

interface DraftLine {
  material_id: string;
  quantity: number;
  scale_weight_kg: number;
}

const TYPES: WillardDeliveryType[] = ["venta", "abono_bateria", "abono_material"];

export default function WillardDeliveryCreatePage() {
  const navigate = useNavigate();
  const createMutation = useCreateWillardDelivery();

  const today = toLocalDateInput(new Date());
  const [deliveryType, setDeliveryType] = useState<WillardDeliveryType>("venta");
  const [warehouseId, setWarehouseId] = useState("");
  const [thirdPartyId, setThirdPartyId] = useState("");
  const [date, setDate] = useState(today);
  const [remission, setRemission] = useState("");
  const [invoice, setInvoice] = useState("");
  const [notes] = useState("");
  const [lines, setLines] = useState<DraftLine[]>([
    { material_id: "", quantity: 0, scale_weight_kg: 0 },
  ]);

  const { data: materialsData } = useMaterials();
  const { data: warehousesData } = useWarehouses();
  // Solo CLIENTES: la venta derivada exige behavior `customer` (#32) y el
  // 400 del backend saltaria al LIQUIDAR, dias despues de capturar. En los
  // abonos el tercero va fijo al titular de la cuenta kg, no pasa por aca.
  const { data: thirdPartiesData } = useCustomers();
  const { data: kgAccounts } = useKgAccounts();
  const { data: profilesData } = useKgProfiles();
  const { getSetting } = useOrgSettings();

  const materials = useMemo(() => materialsData?.items ?? [], [materialsData]);
  const warehouses = useMemo(() => {
    const list = Array.isArray(warehousesData) ? warehousesData : warehousesData?.items ?? [];
    return list.filter((w) => w.is_active && !w.is_transit);
  }, [warehousesData]);
  const thirdParties = useMemo(() => thirdPartiesData?.items ?? [], [thirdPartiesData]);

  // Solo el plomo ENTREGABLE (#103 D1). El backend rechaza el resto con un 400
  // que nombra el material, pero ofrecer los 39 obliga a descubrirlo despues de
  // llenar el formulario. Mismo patron que la Entrada, que filtra por mundo.
  // El puro NO se excluye: en abono es valido y solo avisa (D2).
  const leadMaterials = useMemo(() => {
    const lead = new Map<string, string>();
    for (const prof of profilesData?.items ?? []) lead.set(prof.material_id, prof.lead_product);
    // `is_active` explicito: GET /materials devuelve tambien los desactivados si
    // nadie lo pide (#93, "Sin clasificar fantasma"), y un material dado de baja
    // conserva su perfil kg — PLO-CRU siguio apareciendo como "crudo" un dia
    // entero despues de retirarlo. El backend lo rechaza ("no esta activo"),
    // pero ofrecerlo es la misma trampa de siempre.
    // Por tipo (Johana 9-sep): los ABONOS se hacen con lingote = crudo — "abono
    // a bateria plomo lingote; abono a material: PLOMO LINGOTE". El puro se
    // vende (Hugo 28-ago). El backend conserva el aviso de #103 D2 si alguien
    // llega a abonar puro por API; la pantalla simplemente no lo ofrece.
    const allowed = deliveryType === "venta" ? new Set(["crudo", "puro"]) : new Set(["crudo"]);
    return materials
      .filter((m) => m.is_active !== false && allowed.has(lead.get(m.id) ?? "none"))
      .map((m) => ({
        id: m.id,
        label: `${m.code} - ${m.name} (${m.default_unit ?? "kg"})`,
        lead: lead.get(m.id) as "crudo" | "puro",
      }));
  }, [materials, profilesData, deliveryType]);

  // D8 — la bodega de origen SIEMPRE es la planta. El backend ya lo defiende con
  // un 400, pero ofrecer seis opciones donde cinco llevan a error es pedirle al
  // usuario que descubra por ensayo y error un valor que el sistema ya conoce.
  const plantWarehouseId = (getSetting("willard_sede_drosses") as string | null) ?? "";
  const plantWarehouse = warehouses.find((w) => w.id === plantWarehouseId);

  // D7 — el tercero de un ABONO es el titular de la cuenta kg que se descarga.
  // La venta NO: descarga `intersede`, que no puede tener titular, y venderle
  // plomo a otro cliente es legitimo.
  const holderId = useMemo(() => {
    if (deliveryType === "venta") return null;
    const type = deliveryType === "abono_bateria" ? "willard_baterias" : "willard_drosses";
    return (kgAccounts ?? []).find(
      (a) => a.account_type === type && a.is_active
    )?.third_party_id ?? null;
  }, [deliveryType, kgAccounts]);
  const holderName = useMemo(() => {
    return (kgAccounts ?? []).find(
      (a) => a.third_party_id === holderId
    )?.third_party_name ?? null;
  }, [holderId, kgAccounts]);

  useEffect(() => {
    if (plantWarehouseId && warehouseId !== plantWarehouseId) setWarehouseId(plantWarehouseId);
  }, [plantWarehouseId, warehouseId]);
  useEffect(() => {
    if (holderId) setThirdPartyId(holderId);
  }, [holderId]);

  const unitOf = (materialId: string) =>
    materials.find((m) => m.id === materialId)?.default_unit ?? "kg";

  const canSubmit =
    !!warehouseId &&
    !!thirdPartyId &&
    !!date &&
    !!remission.trim() &&
    lines.length > 0 &&
    lines.every((l) => l.material_id && l.quantity > 0);

  const submit = async () => {
    const created = await createMutation.mutateAsync({
      delivery_type: deliveryType,
      warehouse_id: warehouseId,
      third_party_id: thirdPartyId,
      date: `${date}T12:00:00`,
      remission_number: remission.trim(),
      invoice_number: invoice || null,
      notes: notes || null,
      lines: lines.map((l) => ({
        material_id: l.material_id,
        quantity: String(l.quantity),
        scale_weight_kg: l.scale_weight_kg > 0 ? String(l.scale_weight_kg) : null,
      })),
    });
    navigate(`/willard-deliveries/${created.id}`);
  };

  return (
    <div className="space-y-4">
      <PageHeader
        title="Nueva Salida de Plomo"
        description={
          deliveryType === "venta"
            ? "Venta de plomo a un cliente, desde planta"
            : "Abono de plomo a Willard, desde planta"
        }
      >
        <Button variant="outline" onClick={() => navigate("/willard-deliveries")} className="w-full sm:w-auto">
          <ArrowLeft className="h-4 w-4 mr-2" /> Volver
        </Button>
      </PageHeader>

      <Card>
        <CardHeader><CardTitle className="text-base">Documento</CardTitle></CardHeader>
        <CardContent className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
          <div className="space-y-1">
            <Label>Tipo de entrega *</Label>
            <EntitySelect
              value={deliveryType}
              onChange={(v) => setDeliveryType(v as WillardDeliveryType)}
              options={TYPES.map((t) => ({ id: t, label: DELIVERY_TYPE_LABELS[t] }))}
            />
            <p className="text-xs text-slate-500">
              {deliveryType === "venta" && "Baja lo que planta le debe a Circunvalar."}
              {deliveryType === "abono_bateria" && "Baja la deuda de postconsumo y lo que planta debe, por la misma cantidad."}
              {deliveryType === "abono_material" && "Baja la deuda de drosses. No toca lo que planta debe."}
            </p>
          </div>
          <div className="space-y-1">
            <Label>Bodega de origen *</Label>
            {plantWarehouse ? (
              <>
                <Input value={plantWarehouse.name} disabled />
                <p className="text-xs text-slate-400">El plomo sale siempre de la planta.</p>
              </>
            ) : (
              <EntitySelect
                value={warehouseId}
                onChange={setWarehouseId}
                options={warehouses.map((w) => ({ id: w.id, label: w.name }))}
                placeholder="Seleccionar bodega…"
              />
            )}
          </div>
          <div className="space-y-1">
            <Label>{deliveryType === "venta" ? "Cliente *" : "Tercero (Willard) *"}</Label>
            {holderId && holderName ? (
              <>
                <Input value={holderName} disabled />
                <p className="text-xs text-slate-400">
                  El abono salda la deuda en kg de {holderName}, así que va a ese mismo tercero.
                </p>
              </>
            ) : (
              <EntitySelect
                value={thirdPartyId}
                onChange={setThirdPartyId}
                options={thirdParties.map((t) => ({ id: t.id, label: t.name }))}
                placeholder="Seleccionar tercero…"
              />
            )}
          </div>
          <div className="space-y-1">
            <Label>Fecha *</Label>
            <Input type="date" value={date} max={today} onChange={(e) => setDate(e.target.value)} />
          </div>
          <div className="space-y-1">
            <Label>Remisión *</Label>
            <Input
              value={remission}
              onChange={(e) => setRemission(e.target.value)}
              className={!remission.trim() ? "ring-1 ring-red-300" : undefined}
            />
            <p className="text-xs text-slate-400">
              {deliveryType === "venta"
                ? "Consecutivo de ventas de SAC."
                : "Consecutivo de abonos: es el número con el que se concilia con Willard."}
            </p>
          </div>
          <div className="space-y-1">
            <Label>Factura</Label>
            <Input value={invoice} onChange={(e) => setInvoice(e.target.value)} />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle className="text-base">Materiales</CardTitle></CardHeader>
        <CardContent className="space-y-3">
          {leadMaterials.length === 0 && (
            <p className="text-xs text-amber-600">
              Ningún material está marcado como plomo entregable, así que no hay nada que elegir.
              Márquelos en <span className="font-medium">Config → Materiales (kg)</span> como plomo
              crudo o puro.
            </p>
          )}
          {lines.map((line, idx) => (
            <FormLineGrid key={idx}>
              <div className="md:col-span-5 space-y-1">
                <Label className={idx > 0 ? "md:sr-only" : undefined}>Material</Label>
                <EntitySelect
                  value={line.material_id}
                  onChange={(v) =>
                    setLines((prev) => prev.map((l, i) => (i === idx ? { ...l, material_id: v } : l)))
                  }
                  options={leadMaterials.map((m) => ({
                    id: m.id,
                    label: `${m.label} · ${m.lead === "crudo" ? "crudo" : "puro"}`,
                  }))}
                  placeholder="Seleccionar plomo…"
                />
              </div>
              <div className={unitOf(line.material_id) === "kg" ? "md:col-span-6 space-y-1" : "md:col-span-3 space-y-1"}>
                <Label className={idx > 0 ? "md:sr-only" : undefined}>
                  Cantidad ({unitOf(line.material_id)})
                </Label>
                <MoneyInput
                  value={line.quantity}
                  onChange={(v) =>
                    setLines((prev) => prev.map((l, i) => (i === idx ? { ...l, quantity: v } : l)))
                  }
                  decimals={3}
                />
              </div>
              {/* Báscula solo si el material NO se mide en kg (#105 item 2): en kg
                  el servidor iguala el peso a la cantidad (`_auto_weight`) y la
                  casilla era un campo repetido (Daniel, pruebas 9-sep). */}
              {unitOf(line.material_id) !== "kg" && (
                <div className="md:col-span-3 space-y-1">
                  <Label className={idx > 0 ? "md:sr-only" : undefined}>Báscula (kg)</Label>
                  <MoneyInput
                    value={line.scale_weight_kg}
                    onChange={(v) =>
                      setLines((prev) =>
                        prev.map((l, i) => (i === idx ? { ...l, scale_weight_kg: v } : l)),
                      )
                    }
                    decimals={3}
                  />
                  {line.scale_weight_kg <= 0 && (
                    <p className="text-xs text-amber-600">
                      Sin este peso no se puede liquidar la salida.
                    </p>
                  )}
                </div>
              )}
              <div className="md:col-span-1 flex md:items-end">
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  disabled={lines.length === 1}
                  onClick={() => setLines((prev) => prev.filter((_, i) => i !== idx))}
                >
                  <Trash2 className="h-4 w-4 text-red-500" />
                </Button>
              </div>
            </FormLineGrid>
          ))}
          <Button
            type="button"
            variant="outline"
            onClick={() =>
              setLines((prev) => [...prev, { material_id: "", quantity: 0, scale_weight_kg: 0 }])
            }
          >
            <Plus className="h-4 w-4 mr-2" /> Agregar material
          </Button>
        </CardContent>
      </Card>

      <div className="sticky bottom-0 bg-white border-t -mx-3 px-3 md:-mx-6 md:px-6 py-3 pb-[max(1rem,env(safe-area-inset-bottom))] flex flex-col sm:flex-row sm:justify-end gap-2">
        <Button variant="outline" onClick={() => navigate("/willard-deliveries")} className="w-full sm:w-auto">
          Cancelar
        </Button>
        <Button onClick={submit} disabled={!canSubmit || createMutation.isPending} className="w-full sm:w-auto">
          Registrar Salida
        </Button>
      </div>
    </div>
  );
}
