import { useMemo, useState } from "react";
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
import { useMaterials, useThirdParties, useWarehouses } from "@/hooks/useMasterData";
import { useCreateWillardDelivery } from "@/hooks/useWillardDeliveries";
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
  const { data: thirdPartiesData } = useThirdParties();

  const materials = useMemo(() => materialsData?.items ?? [], [materialsData]);
  const warehouses = useMemo(() => {
    const list = Array.isArray(warehousesData) ? warehousesData : warehousesData?.items ?? [];
    return list.filter((w) => w.is_active && !w.is_transit);
  }, [warehousesData]);
  const thirdParties = useMemo(() => thirdPartiesData?.items ?? [], [thirdPartiesData]);

  const unitOf = (materialId: string) =>
    materials.find((m) => m.id === materialId)?.default_unit ?? "kg";

  const canSubmit =
    !!warehouseId &&
    !!thirdPartyId &&
    !!date &&
    lines.length > 0 &&
    lines.every((l) => l.material_id && l.quantity > 0);

  const submit = async () => {
    const created = await createMutation.mutateAsync({
      delivery_type: deliveryType,
      warehouse_id: warehouseId,
      third_party_id: thirdPartyId,
      date: `${date}T12:00:00`,
      remission_number: remission || null,
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
      <PageHeader title="Nueva Salida a Willard" description="Entrega de plomo desde planta">
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
            <EntitySelect
              value={warehouseId}
              onChange={setWarehouseId}
              options={warehouses.map((w) => ({ id: w.id, label: w.name }))}
              placeholder="Seleccionar bodega…"
            />
          </div>
          <div className="space-y-1">
            <Label>Tercero (Willard) *</Label>
            <EntitySelect
              value={thirdPartyId}
              onChange={setThirdPartyId}
              options={thirdParties.map((t) => ({ id: t.id, label: t.name }))}
              placeholder="Seleccionar tercero…"
            />
          </div>
          <div className="space-y-1">
            <Label>Fecha *</Label>
            <Input type="date" value={date} max={today} onChange={(e) => setDate(e.target.value)} />
          </div>
          <div className="space-y-1">
            <Label>Remisión</Label>
            <Input value={remission} onChange={(e) => setRemission(e.target.value)} />
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
          {lines.map((line, idx) => (
            <FormLineGrid key={idx}>
              <div className="md:col-span-5 space-y-1">
                <Label className={idx > 0 ? "md:sr-only" : undefined}>Material</Label>
                <EntitySelect
                  value={line.material_id}
                  onChange={(v) =>
                    setLines((prev) => prev.map((l, i) => (i === idx ? { ...l, material_id: v } : l)))
                  }
                  options={materials.map((m) => ({
                    id: m.id,
                    label: `${m.code} - ${m.name} (${m.default_unit ?? "kg"})`,
                  }))}
                  placeholder="Seleccionar material…"
                />
              </div>
              <div className="md:col-span-3 space-y-1">
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
                {unitOf(line.material_id) !== "kg" && line.scale_weight_kg <= 0 && (
                  <p className="text-xs text-amber-600">
                    Sin este peso no se puede revisar la salida.
                  </p>
                )}
              </div>
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
