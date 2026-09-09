import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, Plus, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { PageHeader } from "@/components/shared/PageHeader";
import { EntitySelect } from "@/components/shared/EntitySelect";
import { MoneyInput } from "@/components/shared/MoneyInput";
import { FormLineGrid } from "@/components/shared/FormLineGrid";
import { useMaterials } from "@/hooks/useMasterData";
import { useKgProfiles } from "@/hooks/useSacConfig";
import {
  useUpdateWillardDelivery,
  useWillardDelivery,
} from "@/hooks/useWillardDeliveries";
import { toLocalDateInput } from "@/utils/formatters";
import { DELIVERY_TYPE_LABELS } from "@/types/willard-delivery";

interface DraftLine {
  material_id: string;
  quantity: number;
  scale_weight_kg: number;
}

/**
 * Editar una salida antes de liquidarla (#103 D9).
 *
 * El backend ya lo permitia mientras el estado no fuera `liquidated` ni
 * `annulled`; lo que faltaba era la pantalla. Sin ella, quien registraba una
 * salida sin peso de bascula quedaba en un callejon sin salida: `Revisar` la
 * rechazaba y la unica accion disponible era anular y volver a capturar.
 *
 * Tipo, bodega y tercero NO se editan aca: su valor lo determina la
 * configuracion (D7/D8) y cambiarlos cambiaria que deuda se salda. Para eso se
 * anula y se vuelve a capturar, que es una decision consciente.
 */
export default function WillardDeliveryEditPage() {
  const { id = "" } = useParams();
  const navigate = useNavigate();
  const { data: delivery, isLoading } = useWillardDelivery(id);
  const updateMutation = useUpdateWillardDelivery();

  const today = toLocalDateInput(new Date());
  const [date, setDate] = useState("");
  const [remission, setRemission] = useState("");
  const [invoice, setInvoice] = useState("");
  const [notes, setNotes] = useState("");
  const [lines, setLines] = useState<DraftLine[]>([]);
  const [loaded, setLoaded] = useState(false);

  const { data: materialsData } = useMaterials();
  const materials = useMemo(() => materialsData?.items ?? [], [materialsData]);
  const { data: profilesData } = useKgProfiles();

  // Mismo filtro que la captura (#103 D1): la pantalla no ofrece lo que el
  // servidor rechaza.
  const leadMaterials = useMemo(() => {
    const lead = new Map<string, string>();
    for (const prof of profilesData?.items ?? []) lead.set(prof.material_id, prof.lead_product);
    return materials
      .filter((m) => (lead.get(m.id) ?? "none") !== "none")
      .map((m) => ({
        id: m.id,
        label: `${m.code} - ${m.name} (${m.default_unit ?? "kg"}) · ${lead.get(m.id)}`,
      }));
  }, [materials, profilesData]);

  useEffect(() => {
    if (!delivery || loaded) return;
    setDate(toLocalDateInput(new Date(delivery.date)));
    setRemission(delivery.remission_number ?? "");
    setInvoice(delivery.invoice_number ?? "");
    setNotes(delivery.notes ?? "");
    setLines(
      (delivery.lines ?? []).map((l) => ({
        material_id: l.material_id,
        quantity: Number(l.quantity),
        scale_weight_kg: Number(l.scale_weight_kg ?? 0),
      })),
    );
    setLoaded(true);
  }, [delivery, loaded]);

  const unitOf = (materialId: string) =>
    materials.find((m) => m.id === materialId)?.default_unit ?? "kg";

  const canSubmit =
    !!date &&
    !!remission.trim() &&
    lines.length > 0 &&
    lines.every((l) => l.material_id && l.quantity > 0);

  const submit = async () => {
    await updateMutation.mutateAsync({
      id,
      data: {
        date: `${date}T12:00:00`,
        remission_number: remission.trim(),
        invoice_number: invoice || null,
        notes: notes || null,
        lines: lines.map((l) => ({
          material_id: l.material_id,
          quantity: String(l.quantity),
          scale_weight_kg: l.scale_weight_kg > 0 ? String(l.scale_weight_kg) : null,
        })),
      },
    });
    navigate(`/willard-deliveries/${id}`);
  };

  if (isLoading || !delivery) {
    return <div className="p-6 text-sm text-slate-500">Cargando…</div>;
  }

  if (delivery.status === "liquidated" || delivery.status === "annulled") {
    return (
      <div className="p-6 space-y-3">
        <p className="text-sm text-slate-600">
          Esta salida ya no se puede editar.
        </p>
        <Button variant="outline" onClick={() => navigate(`/willard-deliveries/${id}`)}>
          <ArrowLeft className="h-4 w-4 mr-2" /> Volver
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <PageHeader title={`Editar salida #${delivery.delivery_number}`}>
        <Button
          variant="outline"
          onClick={() => navigate(`/willard-deliveries/${id}`)}
          className="w-full sm:w-auto"
        >
          <ArrowLeft className="h-4 w-4 mr-2" /> Volver
        </Button>
      </PageHeader>

      <Card>
        <CardHeader><CardTitle className="text-base">Documento</CardTitle></CardHeader>
        <CardContent className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div className="space-y-1">
            <Label>Tipo</Label>
            <Input value={DELIVERY_TYPE_LABELS[delivery.delivery_type]} disabled />
            <p className="text-xs text-slate-400">
              Para cambiar el tipo, la bodega o el tercero hay que anular y volver a capturar:
              determinan qué deuda se salda.
            </p>
          </div>
          <div className="space-y-1">
            <Label>Fecha *</Label>
            <Input
              type="date"
              value={date}
              max={today}
              onChange={(e) => setDate(e.target.value)}
            />
          </div>
          <div className="space-y-1">
            <Label>Remisión *</Label>
            <Input
              value={remission}
              onChange={(e) => setRemission(e.target.value)}
              className={!remission.trim() ? "ring-1 ring-red-300" : undefined}
            />
          </div>
          <div className="space-y-1">
            <Label>Factura</Label>
            <Input value={invoice} onChange={(e) => setInvoice(e.target.value)} />
          </div>
          <div className="space-y-1 sm:col-span-2">
            <Label>Notas</Label>
            <Input value={notes} onChange={(e) => setNotes(e.target.value)} />
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
          {delivery.status === "reviewed" && (
            <p className="text-xs text-amber-600">
              Esta salida ya está revisada. Si cambia las líneas vuelve a quedar registrada y
              habrá que certificar los pesos otra vez.
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
                  options={leadMaterials}
                  placeholder="Seleccionar plomo…"
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
                  <Trash2 className="h-4 w-4" />
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
            className="w-full sm:w-auto"
          >
            <Plus className="h-4 w-4 mr-2" /> Agregar material
          </Button>
        </CardContent>
      </Card>

      <div className="sticky bottom-0 bg-white border-t -mx-3 px-3 md:-mx-6 md:px-6 py-3 pb-[max(1rem,env(safe-area-inset-bottom))] flex flex-col sm:flex-row gap-2 sm:justify-end">
        <Button
          variant="outline"
          onClick={() => navigate(`/willard-deliveries/${id}`)}
          className="w-full sm:w-auto"
        >
          Cancelar
        </Button>
        <Button
          onClick={submit}
          disabled={!canSubmit || updateMutation.isPending}
          className="w-full sm:w-auto"
        >
          Guardar cambios
        </Button>
      </div>
    </div>
  );
}
