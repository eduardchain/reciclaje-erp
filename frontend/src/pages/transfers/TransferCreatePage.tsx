import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowLeft, Plus, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
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
import { useDispatchTransfer } from "@/hooks/useTransfers";
import { useMaterials, useWarehouses } from "@/hooks/useMasterData";
import { toLocalDateInput } from "@/utils/formatters";
import { ROUTES } from "@/utils/constants";

// SAC E3.1 — despacho (paso 1). CERO kg, CERO pesos: solo físico a tránsito.

interface LineDraft {
  material_id: string;
  quantity: number;
}

export default function TransferCreatePage() {
  const navigate = useNavigate();
  const dispatch = useDispatchTransfer();

  const { data: warehousesData } = useWarehouses();
  const { data: materialsData } = useMaterials();
  // Origen/destino: solo sedes reales (las de tránsito las resuelve el backend)
  const warehouses = (warehousesData?.items ?? []).filter(
    (w) => w.is_active && !w.is_transit
  );
  const materials = materialsData?.items ?? [];

  const [fromId, setFromId] = useState("");
  const [toId, setToId] = useState("");
  const [date, setDate] = useState(toLocalDateInput(new Date()));
  const [notes, setNotes] = useState("");
  const [lines, setLines] = useState<LineDraft[]>([{ material_id: "", quantity: 0 }]);

  const materialOptions = useMemo(
    () =>
      materials.map((m) => ({
        id: m.id,
        label: `${m.code} - ${m.name} (${m.default_unit ?? "kg"})`,
      })),
    [materials]
  );

  const updateLine = (i: number, patch: Partial<LineDraft>) =>
    setLines((prev) => prev.map((ln, idx) => (idx === i ? { ...ln, ...patch } : ln)));

  const canSubmit =
    !!fromId &&
    !!toId &&
    fromId !== toId &&
    !!date &&
    lines.length > 0 &&
    lines.every((ln) => ln.material_id && ln.quantity > 0) &&
    !dispatch.isPending;

  // Aviso, nunca bloqueo: la sede decide si el traslado genera deuda de plomo
  // intersede y maquila. Sin decirlo, el operador solo lo descubre despues.
  const sedeOf = (id: string) => {
    const w = warehouses.find((x) => x.id === id);
    return w ? w.sede_warehouse_id || w.id : null;
  };
  const bothPicked = !!fromId && !!toId && fromId !== toId;
  const sameSede = bothPicked && sedeOf(fromId) === sedeOf(toId);

  const submit = () => {
    dispatch.mutate(
      {
        from_warehouse_id: fromId,
        to_warehouse_id: toId,
        dispatch_date: `${date}T12:00:00`,
        notes: notes.trim() || undefined,
        lines: lines.map((ln) => ({
          material_id: ln.material_id,
          quantity_dispatched: ln.quantity,
        })),
      },
      { onSuccess: (t) => navigate(ROUTES.TRANSFER_DETAIL.replace(":id", t.id)) }
    );
  };

  return (
    <div>
      <PageHeader title="Nuevo Traslado" description="Entre sedes va en dos pasos; dentro de una misma sede se completa al registrarlo">
        <Button variant="outline" onClick={() => navigate(ROUTES.TRANSFERS)} className="w-full sm:w-auto">
          <ArrowLeft className="w-4 h-4 mr-2" /> Volver
        </Button>
      </PageHeader>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Datos del despacho</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4">
            <div className="space-y-1.5">
              <Label>Bodega origen *</Label>
              <Select value={fromId} onValueChange={setFromId}>
                <SelectTrigger>
                  <SelectValue placeholder="Seleccionar…" />
                </SelectTrigger>
                <SelectContent>
                  {warehouses.map((w) => (
                    <SelectItem key={w.id} value={w.id} disabled={w.id === toId}>
                      {w.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label>Bodega destino *</Label>
              <Select value={toId} onValueChange={setToId}>
                <SelectTrigger>
                  <SelectValue placeholder="Seleccionar…" />
                </SelectTrigger>
                <SelectContent>
                  {warehouses.map((w) => (
                    <SelectItem key={w.id} value={w.id} disabled={w.id === fromId}>
                      {w.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label>Fecha de despacho *</Label>
              <Input
                type="date"
                value={date}
                max={toLocalDateInput(new Date())}
                onChange={(e) => setDate(e.target.value)}
              />
            </div>
          </div>

          {bothPicked && (
            <div
              className={`rounded-md border px-3 py-2 text-xs ${
                sameSede
                  ? "border-slate-200 bg-slate-50 text-slate-600"
                  : "border-indigo-200 bg-indigo-50 text-indigo-700"
              }`}
            >
              {sameSede ? (
                <>
                  <span className="font-semibold">
                    Traslado dentro de la misma sede: se completa de inmediato.
                  </span>{" "}
                  No pasa por tránsito ni requiere confirmar recepción, y no genera
                  plomo intersede ni cargo de maquila.
                </>
              ) : (
                <>
                  <span className="font-semibold">Traslado entre sedes: en dos pasos.</span>{" "}
                  El material queda en tránsito hasta confirmar la recepción, y los
                  materiales con fórmula generan plomo intersede y cargo de maquila.
                </>
              )}
            </div>
          )}

          <div className="space-y-2">
            <Label>Materiales *</Label>
            {lines.map((ln, i) => (
              <div key={i} className="grid grid-cols-1 md:grid-cols-12 gap-2 items-end">
                <div className="md:col-span-7">
                  <EntitySelect
                    value={ln.material_id}
                    onChange={(v) => updateLine(i, { material_id: v })}
                    options={materialOptions}
                    placeholder="Material…"
                  />
                </div>
                <div className="md:col-span-3">
                  <MoneyInput
                    value={ln.quantity}
                    onChange={(v) => updateLine(i, { quantity: v })}
                    decimals={4}
                    placeholder="Cantidad"
                  />
                </div>
                <div className="md:col-span-2 flex">
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    disabled={lines.length === 1}
                    onClick={() => setLines((prev) => prev.filter((_, idx) => idx !== i))}
                  >
                    <Trash2 className="w-4 h-4 text-slate-400" />
                  </Button>
                </div>
              </div>
            ))}
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => setLines((prev) => [...prev, { material_id: "", quantity: 0 }])}
            >
              <Plus className="w-4 h-4 mr-1" /> Agregar material
            </Button>
          </div>

          <div className="space-y-1.5">
            <Label>Notas</Label>
            <Textarea value={notes} onChange={(e) => setNotes(e.target.value)} rows={2} />
          </div>
        </CardContent>
      </Card>

      <div className="sticky bottom-0 bg-white border-t -mx-3 px-3 md:-mx-6 md:px-6 py-3 mt-6 pb-[max(1rem,env(safe-area-inset-bottom))] flex flex-col sm:flex-row gap-2 sm:justify-end">
        <Button variant="outline" className="w-full sm:w-auto" onClick={() => navigate(ROUTES.TRANSFERS)}>
          Cancelar
        </Button>
        <Button className="w-full sm:w-auto" disabled={!canSubmit} onClick={submit}>
          {dispatch.isPending
            ? "Guardando…"
            : sameSede
              ? "Registrar Traslado"
              : "Despachar"}
        </Button>
      </div>
    </div>
  );
}
