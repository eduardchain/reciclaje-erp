import { useMemo, useState } from "react";
import { ChevronDown, ChevronRight, History, Plus } from "lucide-react";
import { usePermissions } from "@/hooks/usePermissions";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { EmptyState } from "@/components/shared/EmptyState";
import { useMaterials } from "@/hooks/useMasterData";
import { useCreateFormula, useCurrentFormulas, useFormulaHistory } from "@/hooks/useSacConfig";
import { formatDate } from "@/utils/formatters";
import ConfigLayout from "./ConfigLayout";
import {
  FORMULA_TYPE_LABELS,
  type FormulaType,
  type MaterialConversionFormulaResponse,
  type WillardSubtype,
} from "@/types/sac-config";

const BATTERY_REFS = ["07", "08", "1", "2", "3", "4", "5"];

/** Parametros legibles: "53% plomo", "2.5 kg/unidad", "56% scrap + borne 50 kg". */
function readableParams(f: MaterialConversionFormulaResponse): string {
  const p = f.parameters as Record<string, number | string | undefined>;
  if (f.formula_type === "battery_to_lead") {
    const ref = p.material_reference ? ` (ref ${p.material_reference})` : "";
    return `${p.kg_lead_per_unit} kg/unidad${ref}`;
  }
  if (f.formula_type === "drosses_to_lead") {
    return `${(Number(p.lead_percentage) * 100).toFixed(1).replace(/\.0$/, "")}% plomo`;
  }
  if (f.formula_type === "scrap_with_terminal_to_lead") {
    return `${(Number(p.scrap_factor) * 100).toFixed(1).replace(/\.0$/, "")}% scrap + borne ${p.terminal_weight_kg} kg`;
  }
  return JSON.stringify(p);
}

export default function FormulasPage() {
  const { hasPermission } = usePermissions();
  const [filterMaterial, setFilterMaterial] = useState<string>("all");
  const { data, isLoading } = useCurrentFormulas(
    filterMaterial === "all" ? undefined : filterMaterial
  );
  const { data: materialsData } = useMaterials();
  const create = useCreateFormula();

  const [dialogOpen, setDialogOpen] = useState(false);
  const [materialId, setMaterialId] = useState("");
  const [formulaType, setFormulaType] = useState<FormulaType | "">("");
  const [kgPerUnit, setKgPerUnit] = useState("");
  const [batteryRef, setBatteryRef] = useState<string>("none");
  const [leadPct, setLeadPct] = useState("");
  const [scrapPct, setScrapPct] = useState("");
  const [terminalKg, setTerminalKg] = useState("");
  const [subtype, setSubtype] = useState<string>("none");
  const [notes, setNotes] = useState("");
  const [showJson, setShowJson] = useState(false);
  const [historyMaterial, setHistoryMaterial] = useState<{ id: string; label: string } | null>(null);
  const history = useFormulaHistory(historyMaterial?.id, historyMaterial !== null);

  const items = data?.items ?? [];
  const materials = materialsData?.items ?? [];
  const canManage = hasPermission("formulas.manage");
  const selectedMaterial = materials.find((m) => m.id === materialId);

  const parameters = useMemo((): Record<string, unknown> | null => {
    if (formulaType === "battery_to_lead") {
      const kg = parseFloat(kgPerUnit);
      if (!kg || kg <= 0) return null;
      const base: Record<string, unknown> = { kg_lead_per_unit: kg };
      if (batteryRef !== "none") base.material_reference = batteryRef;
      return base;
    }
    if (formulaType === "drosses_to_lead") {
      const pct = parseFloat(leadPct);
      if (!pct || pct <= 0 || pct > 100) return null;
      return { lead_percentage: pct / 100 };
    }
    if (formulaType === "scrap_with_terminal_to_lead") {
      const pct = parseFloat(scrapPct);
      const term = parseFloat(terminalKg);
      if (!pct || pct <= 0 || pct > 100 || isNaN(term) || term < 0) return null;
      return { scrap_factor: pct / 100, terminal_weight_kg: term };
    }
    return null;
  }, [formulaType, kgPerUnit, batteryRef, leadPct, scrapPct, terminalKg]);

  const openCreate = () => {
    setMaterialId("");
    setFormulaType("");
    setKgPerUnit("");
    setBatteryRef("none");
    setLeadPct("");
    setScrapPct("");
    setTerminalKg("");
    setSubtype("none");
    setNotes("");
    setShowJson(false);
    setDialogOpen(true);
  };

  const handleSubmit = () => {
    if (!materialId || !formulaType || !parameters) return;
    create.mutate(
      {
        material_id: materialId,
        formula_type: formulaType,
        parameters,
        willard_account_subtype: subtype === "none" ? null : (subtype as WillardSubtype),
        notes: notes || null,
      },
      { onSuccess: () => setDialogOpen(false) }
    );
  };

  return (
    <ConfigLayout>
      <div className="flex flex-col sm:flex-row sm:flex-wrap gap-2 sm:items-center sm:justify-between">
        <div className="flex flex-col sm:flex-row gap-2 sm:items-center">
          <Select value={filterMaterial} onValueChange={setFilterMaterial}>
            <SelectTrigger className="w-full sm:w-64">
              <SelectValue placeholder="Todos los materiales" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Todos los materiales</SelectItem>
              {materials.map((m) => (
                <SelectItem key={m.id} value={m.id}>
                  {m.code} - {m.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        {canManage && (
          <Button onClick={openCreate} className="bg-emerald-600 hover:bg-emerald-700 w-full sm:w-auto">
            <Plus className="h-4 w-4 mr-2" />
            Nueva Formula
          </Button>
        )}
      </div>

      {!isLoading && items.length === 0 ? (
        <EmptyState
          title="Sin formulas"
          description="Crea la primera formula de conversion — los factores reales los valida el cliente."
        />
      ) : (
        <div className="overflow-x-auto -mx-3 sm:mx-0 rounded-lg border bg-white">
          <Table className="min-w-[760px]">
            <TableHeader>
              <TableRow>
                <TableHead>Material</TableHead>
                <TableHead>Tipo</TableHead>
                <TableHead>Sub-cuenta</TableHead>
                <TableHead>Factor vigente</TableHead>
                <TableHead>Desde</TableHead>
                <TableHead>Por</TableHead>
                <TableHead className="w-10" />
              </TableRow>
            </TableHeader>
            <TableBody>
              {items.map((f) => (
                <TableRow key={f.id}>
                  <TableCell className="font-medium">
                    {f.material_code} - {f.material_name}
                    <span className="text-xs text-slate-400 ml-1">({f.material_unit})</span>
                  </TableCell>
                  <TableCell className="text-slate-500">
                    {FORMULA_TYPE_LABELS[f.formula_type] ?? f.formula_type}
                  </TableCell>
                  <TableCell>
                    {f.willard_account_subtype ? (
                      <span className="inline-flex px-2 py-0.5 rounded-full bg-indigo-50 text-indigo-700 text-xs font-medium capitalize">
                        {f.willard_account_subtype}
                      </span>
                    ) : (
                      <span className="text-slate-400">—</span>
                    )}
                  </TableCell>
                  <TableCell className="font-medium">{readableParams(f)}</TableCell>
                  <TableCell>{formatDate(f.created_at)}</TableCell>
                  <TableCell className="text-slate-500">{f.created_by_name ?? "—"}</TableCell>
                  <TableCell>
                    <Button
                      variant="ghost"
                      size="sm"
                      title="Ver historial del material"
                      onClick={() =>
                        setHistoryMaterial({
                          id: f.material_id,
                          label: `${f.material_code} - ${f.material_name}`,
                        })
                      }
                    >
                      <History className="h-4 w-4" />
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      {/* Dialog nueva formula */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Nueva Formula de Conversion</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Material *</Label>
                <Select value={materialId} onValueChange={setMaterialId}>
                  <SelectTrigger className="w-full">
                    <SelectValue placeholder="Selecciona material" />
                  </SelectTrigger>
                  <SelectContent>
                    {materials.map((m) => (
                      <SelectItem key={m.id} value={m.id}>
                        {m.code} - {m.name} ({m.default_unit ?? "kg"})
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div>
                <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Tipo de formula *</Label>
                <Select value={formulaType} onValueChange={(v) => setFormulaType(v as FormulaType)}>
                  <SelectTrigger className="w-full">
                    <SelectValue placeholder="Selecciona tipo" />
                  </SelectTrigger>
                  <SelectContent>
                    {(Object.keys(FORMULA_TYPE_LABELS) as FormulaType[]).map((t) => (
                      <SelectItem key={t} value={t}>{FORMULA_TYPE_LABELS[t]}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>

            {selectedMaterial && formulaType && (
              <p className="text-xs text-slate-500">
                {formulaType === "battery_to_lead"
                  ? "Aplica a materiales en 'unidad'"
                  : "Aplica a materiales en 'kg'"}
                {" — "}
                {selectedMaterial.code} esta en '{selectedMaterial.default_unit ?? "kg"}'
              </p>
            )}

            {/* Campos dinamicos por tipo */}
            {formulaType === "battery_to_lead" && (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Kg de plomo por unidad *</Label>
                  <Input
                    type="number"
                    inputMode="decimal"
                    step="0.01"
                    min="0"
                    value={kgPerUnit}
                    onChange={(e) => setKgPerUnit(e.target.value)}
                    placeholder="Ej: 2.5"
                  />
                </div>
                <div>
                  <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Referencia (opcional)</Label>
                  <Select value={batteryRef} onValueChange={setBatteryRef}>
                    <SelectTrigger className="w-full"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="none">Sin referencia</SelectItem>
                      {BATTERY_REFS.map((r) => (
                        <SelectItem key={r} value={r}>Ref {r}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>
            )}

            {formulaType === "drosses_to_lead" && (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">% de plomo *</Label>
                  <div className="relative">
                    <Input
                      type="number"
                      inputMode="decimal"
                      step="0.1"
                      min="0"
                      max="100"
                      value={leadPct}
                      onChange={(e) => setLeadPct(e.target.value)}
                      placeholder="Ej: 53"
                      className="pr-8"
                    />
                    <span className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 text-sm">%</span>
                  </div>
                </div>
                <div>
                  <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Sub-cuenta Willard</Label>
                  <Select value={subtype} onValueChange={setSubtype}>
                    <SelectTrigger className="w-full"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="none">Sin sub-cuenta</SelectItem>
                      <SelectItem value="escurrido">Escurrido</SelectItem>
                      <SelectItem value="pinza">Pinza</SelectItem>
                    </SelectContent>
                  </Select>
                  <p className="text-xs text-slate-400 mt-1">Caso SEC: dos formulas sobre el mismo material</p>
                </div>
              </div>
            )}

            {formulaType === "scrap_with_terminal_to_lead" && (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Factor scrap *</Label>
                  <div className="relative">
                    <Input
                      type="number"
                      inputMode="decimal"
                      step="0.1"
                      min="0"
                      max="100"
                      value={scrapPct}
                      onChange={(e) => setScrapPct(e.target.value)}
                      placeholder="Ej: 56"
                      className="pr-8"
                    />
                    <span className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 text-sm">%</span>
                  </div>
                </div>
                <div>
                  <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Peso borne (kg) *</Label>
                  <Input
                    type="number"
                    inputMode="decimal"
                    step="0.1"
                    min="0"
                    value={terminalKg}
                    onChange={(e) => setTerminalKg(e.target.value)}
                    placeholder="Ej: 50"
                  />
                </div>
              </div>
            )}

            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Notas</Label>
              <Input
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                placeholder="Ej: vigente contrato Willard 2026"
                maxLength={500}
              />
            </div>

            {parameters && (
              <div>
                <button
                  type="button"
                  onClick={() => setShowJson(!showJson)}
                  className="flex items-center gap-1 text-xs text-slate-500 hover:text-slate-700"
                >
                  {showJson ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
                  Ver JSON tecnico
                </button>
                {showJson && (
                  <pre className="mt-1 text-xs bg-slate-50 rounded p-2 overflow-x-auto">
                    {JSON.stringify(parameters, null, 2)}
                  </pre>
                )}
              </div>
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogOpen(false)} className="w-full sm:w-auto">Cancelar</Button>
            <Button
              onClick={handleSubmit}
              disabled={!materialId || !formulaType || !parameters || create.isPending}
              className="bg-emerald-600 hover:bg-emerald-700 w-full sm:w-auto"
            >
              {create.isPending ? "Guardando..." : "Registrar Formula"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Modal historial por material */}
      <Dialog open={historyMaterial !== null} onOpenChange={(open) => !open && setHistoryMaterial(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Historial — {historyMaterial?.label}</DialogTitle>
          </DialogHeader>
          <div className="overflow-x-auto max-h-[50vh] overflow-y-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Desde</TableHead>
                  <TableHead>Sub-cuenta</TableHead>
                  <TableHead>Factor</TableHead>
                  <TableHead>Por</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {(history.data?.items ?? []).map((h) => (
                  <TableRow key={h.id}>
                    <TableCell>{formatDate(h.created_at)}</TableCell>
                    <TableCell className="capitalize">{h.willard_account_subtype ?? "—"}</TableCell>
                    <TableCell>{readableParams(h)}</TableCell>
                    <TableCell className="text-slate-500">{h.created_by_name ?? "—"}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </DialogContent>
      </Dialog>
    </ConfigLayout>
  );
}
