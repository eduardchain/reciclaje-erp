import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { PageHeader } from "@/components/shared/PageHeader";
import { EntitySelect } from "@/components/shared/EntitySelect";
import { MoneyInput } from "@/components/shared/MoneyInput";
import { FormLineGrid } from "@/components/shared/FormLineGrid";
import { useMaterials, useThirdParties, useWarehouses } from "@/hooks/useMasterData";
import { useKgProfiles } from "@/hooks/useSacConfig";
import {
  useControlDispatch,
  useCreateControlDispatch,
  useUpdateControlDispatch,
} from "@/hooks/useControlDispatches";
import { buildRoute, ROUTES } from "@/utils/constants";
import { toLocalDateInput } from "@/utils/formatters";

interface DraftLine {
  _key: number;
  material_id: string;
  quantity: number;
  scale_weight_kg: number;
}

let keySeq = 0;
const newLine = (): DraftLine => ({ _key: ++keySeq, material_id: "", quantity: 0, scale_weight_kg: 0 });

/** Nueva y editar Salida de control (plan documentos de control §4.3). Un solo
 *  formulario: los dos caminos validan lo mismo en el servidor. */
export default function ControlDispatchFormPage() {
  const navigate = useNavigate();
  const { id } = useParams<{ id: string }>();
  const isEdit = !!id;
  const { data: existing, isLoading: loadingExisting } = useControlDispatch(id);
  const createMutation = useCreateControlDispatch();
  const updateMutation = useUpdateControlDispatch();

  const today = toLocalDateInput(new Date());
  const [date, setDate] = useState(today);
  const [warehouseId, setWarehouseId] = useState("");
  const [thirdPartyId, setThirdPartyId] = useState("");
  const [remission, setRemission] = useState("");
  const [notes, setNotes] = useState("");
  const [lines, setLines] = useState<DraftLine[]>([newLine()]);
  const [loaded, setLoaded] = useState(!isEdit);

  const { data: materialsData } = useMaterials();
  const { data: warehousesData } = useWarehouses();
  const { data: thirdPartiesData } = useThirdParties();
  const { data: profilesData } = useKgProfiles();

  useEffect(() => {
    if (!isEdit || loaded || !existing) return;
    setDate(existing.date.slice(0, 10));
    setWarehouseId(existing.warehouse_id);
    setThirdPartyId(existing.third_party_id ?? "");
    setRemission(existing.remission_number);
    setNotes(existing.notes ?? "");
    setLines(
      existing.lines.map((l) => ({
        _key: ++keySeq,
        material_id: l.material_id,
        quantity: l.quantity,
        scale_weight_kg: l.scale_weight_kg ?? 0,
      })),
    );
    setLoaded(true);
  }, [isEdit, loaded, existing]);

  const materials = useMemo(() => materialsData?.items ?? [], [materialsData]);
  const warehouses = useMemo(() => {
    const list = Array.isArray(warehousesData) ? warehousesData : warehousesData?.items ?? [];
    return list.filter((w) => w.is_active && !w.is_transit);
  }, [warehousesData]);
  // O2 de QA 2: ninguna entidad de sistema recibe estibas (el servidor da 422)
  const thirdParties = useMemo(
    () => (thirdPartiesData?.items ?? []).filter((t) => t.is_active && !t.is_system_entity),
    [thirdPartiesData],
  );

  // El clasificador es la marca (#103 D1): solo se ofrecen materiales de
  // control. Al editar, el material de una línea existente se conserva aunque
  // le hayan quitado la marca (un Select sin su opción se rompe); el servidor
  // lo rechaza con el nombre si se guarda así.
  const controlIds = useMemo(
    () => new Set((profilesData?.items ?? []).filter((p) => p.control_only).map((p) => p.material_id)),
    [profilesData],
  );
  const materialOptions = (keepId: string) =>
    materials
      .filter((m) => (m.is_active !== false && controlIds.has(m.id)) || m.id === keepId)
      .map((m) => ({ id: m.id, label: `${m.code} - ${m.name} (${m.default_unit ?? "kg"})` }));
  const unitOf = (materialId: string) =>
    materials.find((m) => m.id === materialId)?.default_unit ?? "kg";

  const chosen = lines.map((l) => l.material_id).filter(Boolean);
  const duplicated = chosen.length !== new Set(chosen).size;
  const canSubmit =
    !!warehouseId && !!date && !!remission.trim() && lines.length > 0 && !duplicated &&
    lines.every((l) => l.material_id && l.quantity > 0);
  const pending = createMutation.isPending || updateMutation.isPending;

  const payloadLines = () =>
    lines.map((l) => ({
      material_id: l.material_id,
      quantity: String(l.quantity),
      ...(unitOf(l.material_id) !== "kg" && l.scale_weight_kg > 0
        ? { scale_weight_kg: String(l.scale_weight_kg) }
        : {}),
    }));

  const submit = async () => {
    if (isEdit && id) {
      const d = await updateMutation.mutateAsync({
        id,
        data: {
          date: `${date}T12:00:00`,
          warehouse_id: warehouseId,
          third_party_id: thirdPartyId || null,
          remission_number: remission.trim(),
          notes: notes.trim() || null,
          lines: payloadLines(),
        },
      });
      navigate(buildRoute(ROUTES.CONTROL_DISPATCH_DETAIL, { id: d.id }));
      return;
    }
    const d = await createMutation.mutateAsync({
      date: `${date}T12:00:00`,
      warehouse_id: warehouseId,
      third_party_id: thirdPartyId || undefined,
      remission_number: remission.trim(),
      notes: notes.trim() || undefined,
      lines: payloadLines(),
    });
    navigate(buildRoute(ROUTES.CONTROL_DISPATCH_DETAIL, { id: d.id }));
  };

  const backTo = isEdit && id ? buildRoute(ROUTES.CONTROL_DISPATCH_DETAIL, { id }) : ROUTES.CONTROL_DISPATCHES;

  if (isEdit && (loadingExisting || !loaded)) {
    return <div className="p-8 text-center text-slate-500">Cargando…</div>;
  }
  if (isEdit && existing && existing.status !== "registered") {
    return (
      <div className="p-8 text-center text-slate-500 space-y-3">
        <p>La salida de control está anulada: no se edita.</p>
        <Button variant="outline" onClick={() => navigate(backTo)}>Volver</Button>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <PageHeader
        title={isEdit && existing ? `Editar Salida de control #${existing.dispatch_number}` : "Nueva salida de control"}
        description="Sale con su remisión del talonario, sin precio, sin inventario ni plata"
      >
        <Button variant="outline" onClick={() => navigate(backTo)} className="w-full sm:w-auto">
          <ArrowLeft className="h-4 w-4 mr-2" /> Volver
        </Button>
      </PageHeader>

      <Card>
        <CardHeader><CardTitle className="text-base">Documento</CardTitle></CardHeader>
        <CardContent className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
          <div className="space-y-1">
            <Label>Remisión *</Label>
            <Input
              value={remission}
              onChange={(e) => setRemission(e.target.value)}
              className={!remission.trim() ? "ring-1 ring-red-300" : undefined}
            />
            <p className="text-xs text-slate-400">
              El número del talonario de remisiones, el mismo de las Entradas.
            </p>
          </div>
          <div className="space-y-1">
            <Label>Fecha *</Label>
            <Input type="date" value={date} max={today} onChange={(e) => setDate(e.target.value)} />
          </div>
          <div className="space-y-1">
            <Label>Bodega de donde sale *</Label>
            <EntitySelect
              value={warehouseId}
              onChange={setWarehouseId}
              options={warehouses.map((w) => ({ id: w.id, label: w.name }))}
              placeholder="Seleccionar bodega…"
            />
          </div>
          <div className="space-y-1">
            <Label>Tercero</Label>
            <EntitySelect
              value={thirdPartyId}
              onChange={setThirdPartyId}
              options={thirdParties.map((t) => ({ id: t.id, label: t.name }))}
              placeholder="A quién se entrega (opcional)…"
            />
          </div>
          <div className="space-y-1 sm:col-span-2">
            <Label>Notas</Label>
            <Input value={notes} onChange={(e) => setNotes(e.target.value)} maxLength={1000} />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle className="text-base">Materiales</CardTitle></CardHeader>
        <CardContent className="space-y-3">
          {controlIds.size === 0 && (
            <p className="text-xs text-amber-600">
              Ningún material está marcado como de control, así que no hay nada que elegir.
              Márquelos en <span className="font-medium">Config → Materiales (kg)</span> con
              «Solo control (sin valor)».
            </p>
          )}
          {lines.map((line, idx) => (
            <FormLineGrid
              key={line._key}
              isFirst={idx === 0}
              isLast={idx === lines.length - 1}
              onDelete={() => setLines((prev) => prev.filter((l) => l._key !== line._key))}
              disableDelete={lines.length === 1}
            >
              <div className="md:col-span-6 space-y-1">
                <Label className={idx > 0 ? "md:sr-only" : undefined}>Material</Label>
                <EntitySelect
                  value={line.material_id}
                  onChange={(v) =>
                    setLines((prev) => prev.map((l) => (l._key === line._key ? { ...l, material_id: v } : l)))
                  }
                  options={materialOptions(line.material_id)}
                  placeholder="Seleccionar material de control…"
                />
              </div>
              <div className={unitOf(line.material_id) === "kg" ? "md:col-span-5 space-y-1" : "md:col-span-3 space-y-1"}>
                <Label className={idx > 0 ? "md:sr-only" : undefined}>
                  Cantidad ({unitOf(line.material_id)})
                </Label>
                <MoneyInput
                  value={line.quantity}
                  onChange={(v) =>
                    setLines((prev) => prev.map((l) => (l._key === line._key ? { ...l, quantity: v } : l)))
                  }
                  decimals={3}
                />
              </div>
              {unitOf(line.material_id) !== "kg" && (
                <div className="md:col-span-2 space-y-1">
                  <Label className={idx > 0 ? "md:sr-only" : undefined}>Báscula (kg)</Label>
                  <MoneyInput
                    value={line.scale_weight_kg}
                    onChange={(v) =>
                      setLines((prev) =>
                        prev.map((l) => (l._key === line._key ? { ...l, scale_weight_kg: v } : l)),
                      )
                    }
                    decimals={3}
                  />
                </div>
              )}
            </FormLineGrid>
          ))}
          {duplicated && (
            <p className="text-xs text-red-600">Un material aparece en más de una línea: una fila por material.</p>
          )}
          <Button type="button" variant="outline" onClick={() => setLines((prev) => [...prev, newLine()])}>
            <Plus className="h-4 w-4 mr-2" /> Agregar material
          </Button>
        </CardContent>
      </Card>

      <div className="sticky bottom-0 bg-white border-t -mx-3 px-3 md:-mx-6 md:px-6 py-3 pb-[max(1rem,env(safe-area-inset-bottom))] flex flex-col sm:flex-row sm:justify-end gap-2">
        <Button variant="outline" onClick={() => navigate(backTo)} className="w-full sm:w-auto">
          Cancelar
        </Button>
        <Button onClick={submit} disabled={!canSubmit || pending} className="w-full sm:w-auto">
          {isEdit ? "Guardar cambios" : "Registrar salida"}
        </Button>
      </div>
    </div>
  );
}
