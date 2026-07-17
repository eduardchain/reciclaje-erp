import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Download, History, Pencil, Plus, Tag } from "lucide-react";
import { usePermissions } from "@/hooks/usePermissions";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { EmptyState } from "@/components/shared/EmptyState";
import { EntitySelect } from "@/components/shared/EntitySelect";
import { useMaterials } from "@/hooks/useMasterData";
import { useMaterialCategories, useBusinessUnits } from "@/hooks/useCrudData";
import { useCurrentFormulas, useFormulaHistory, useKgProfiles } from "@/hooks/useSacConfig";
import { materialService } from "@/services/materials";
import { sacConfigService } from "@/services/sacConfig";
import { exportMaterialsKgExcel } from "@/utils/excelExport";
import { formatDate, getApiErrorMessage } from "@/utils/formatters";
import { ROUTES } from "@/utils/constants";
import ConfigLayout from "./ConfigLayout";
import {
  formulaTypeForUnit,
  type MaterialConversionFormulaResponse,
  type MaterialKgProfileResponse,
  type WillardWorld,
} from "@/types/sac-config";
import type { MaterialResponse } from "@/types/material";

const BATTERY_REFS = ["07", "08", "1", "2", "3", "4", "5"];

// C3: el concepto se presenta como "Clasificación" (genérico, sin marca de cliente)
type Classification = "compra" | "postconsumo" | "drosses";

const CLASSIFICATION_LABELS: Record<Classification, string> = {
  compra: "Compra regular",
  postconsumo: "Postconsumo (baterías)",
  drosses: "Drosses",
};

/** Fila material-céntrica (C5): material + perfil + fórmula vigente. */
interface MaterialKgRow {
  material: MaterialResponse;
  profile?: MaterialKgProfileResponse;
  formula?: MaterialConversionFormulaResponse;
}

/** Estado visible de clasificación — sin perfil (o none sin compra) = sin clasificar. */
function classificationOf(row: MaterialKgRow): Classification | "unclassified" {
  const p = row.profile;
  if (!p) return "unclassified";
  if (p.willard_world === "postconsumo" || p.willard_world === "drosses") return p.willard_world;
  return p.compra_regular ? "compra" : "unclassified";
}

/** Parametros legibles: "53% plomo", "2.5 kg/unidad". */
function readableParams(f: MaterialConversionFormulaResponse): string {
  const p = f.parameters as Record<string, number | string | undefined>;
  if (f.formula_type === "battery_to_lead") {
    const ref = p.material_reference ? ` (ref ${p.material_reference})` : "";
    return `${p.kg_lead_per_unit} kg/unidad${ref}`;
  }
  if (f.formula_type === "drosses_to_lead") {
    return `${(Number(p.lead_percentage) * 100).toFixed(1).replace(/\.0$/, "")}% plomo`;
  }
  return JSON.stringify(p);
}

function ClassificationBadge({ row }: { row: MaterialKgRow }) {
  const cls = classificationOf(row);
  if (cls === "unclassified") {
    return (
      <span className="inline-flex px-2 py-0.5 rounded-full bg-slate-100 text-slate-500 text-xs font-medium">
        Sin clasificar
      </span>
    );
  }
  // W4 (estandarización, feedback Daniel): cada clasificación tiene UNA sola
  // forma de badge — idéntica aparezca sola o acompañada. Un material Willard
  // que también entra por compra muestra AMBOS tags: el suyo + el MISMO
  // "Compra regular" estándar (nada de variantes outline/"+"). Paleta:
  // verde=compra, azul=postconsumo, ámbar=drosses, gris=sin clasificar.
  return (
    <span className="inline-flex items-center gap-1 flex-wrap">
      <ClassPill cls={cls} />
      {cls !== "compra" && row.profile?.compra_regular && <ClassPill cls="compra" />}
    </span>
  );
}

/** El badge canónico de una clasificación — única definición, cero variantes. */
function ClassPill({ cls }: { cls: Classification }) {
  const colors: Record<Classification, string> = {
    compra: "bg-emerald-50 text-emerald-700",
    postconsumo: "bg-sky-50 text-sky-700",
    drosses: "bg-amber-50 text-amber-700",
  };
  return (
    <span className={`inline-flex px-2 py-0.5 rounded-full text-xs font-medium ${colors[cls]}`}>
      {CLASSIFICATION_LABELS[cls]}
    </span>
  );
}

export default function FormulasPage() {
  const { hasPermission } = usePermissions();
  const navigate = useNavigate();
  const qc = useQueryClient();

  const { data: materialsData, isLoading } = useMaterials();
  const { data: profilesData } = useKgProfiles();
  const { data: formulasData } = useCurrentFormulas();
  const { data: categoriesData } = useMaterialCategories();
  const { data: businessUnitsData } = useBusinessUnits();

  const categories = categoriesData?.items ?? [];
  // Excluir UN de sistema (Pasa Mano): no puede tener materiales (decisión #58)
  const businessUnits = (businessUnitsData?.items ?? []).filter((b) => !b.system_code);

  // F2 QA: el submit encadena materials.create/edit + formulas.manage — gatear en el permiso base
  const canCreate = hasPermission("materials.create");
  const canEdit = hasPermission("materials.edit");

  // Join material-céntrico (C5): TODOS los materiales, con o sin perfil/fórmula
  const rows = useMemo((): MaterialKgRow[] => {
    const profByMat = new Map<string, MaterialKgProfileResponse>();
    for (const p of profilesData?.items ?? []) profByMat.set(p.material_id, p);
    const formByMat = new Map<string, MaterialConversionFormulaResponse>();
    for (const f of formulasData?.items ?? []) formByMat.set(f.material_id, f);
    return (materialsData?.items ?? []).map((m) => ({
      material: m,
      profile: profByMat.get(m.id),
      formula: formByMat.get(m.id),
    }));
  }, [materialsData, profilesData, formulasData]);

  // Filtros client-side
  const [search, setSearch] = useState("");
  const [classFilter, setClassFilter] = useState<string>("all");
  const filteredRows = useMemo(() => {
    const q = search.trim().toLowerCase();
    return rows.filter((r) => {
      if (q && !`${r.material.code} ${r.material.name}`.toLowerCase().includes(q)) return false;
      if (classFilter !== "all") {
        const cls = classificationOf(r);
        // W4: el filtro matchea por TAG visible — "Compra regular" incluye
        // también los Willard que además entran por compra (llevan ese tag)
        const matches =
          cls === classFilter ||
          (classFilter === "compra" && cls !== "unclassified" && (r.profile?.compra_regular ?? false));
        if (!matches) return false;
      }
      return true;
    });
  }, [rows, search, classFilter]);

  // ---------------- Formulario unificado (C1): crear + editar ----------------
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editRow, setEditRow] = useState<MaterialKgRow | null>(null);
  const [saving, setSaving] = useState(false);

  const [code, setCode] = useState("");
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [unit, setUnit] = useState<"kg" | "unidad">("kg");
  const [categoryId, setCategoryId] = useState("");
  const [businessUnitId, setBusinessUnitId] = useState("");
  const [classification, setClassification] = useState<Classification>("compra");
  const [alsoCompra, setAlsoCompra] = useState(false);
  const [kgPerUnit, setKgPerUnit] = useState("");
  const [batteryRef, setBatteryRef] = useState<string>("none");
  const [leadPct, setLeadPct] = useState("");
  const [notes, setNotes] = useState("");

  const isWillard = classification !== "compra";
  const derivedType = formulaTypeForUnit(unit);
  // Guard F3 (frontend-only): con fórmula vigente la unidad no se cambia
  const unitLocked = !!editRow?.formula;

  const openCreate = () => {
    setEditRow(null);
    setCode("");
    setName("");
    setDescription("");
    setUnit("kg");
    setCategoryId("");
    setBusinessUnitId("");
    setClassification("compra");
    setAlsoCompra(false);
    setKgPerUnit("");
    setBatteryRef("none");
    setLeadPct("");
    setNotes("");
    setDialogOpen(true);
  };

  const openEdit = (row: MaterialKgRow) => {
    setEditRow(row);
    setCode(row.material.code);
    setName(row.material.name);
    setDescription(row.material.description ?? "");
    setUnit((row.material.default_unit ?? "kg").trim().toLowerCase() === "unidad" ? "unidad" : "kg");
    setCategoryId(row.material.category_id);
    setBusinessUnitId(row.material.business_unit_id);
    const cls = classificationOf(row);
    setClassification(cls === "unclassified" ? "compra" : cls);
    setAlsoCompra(cls !== "compra" && cls !== "unclassified" ? (row.profile?.compra_regular ?? false) : false);
    const f = row.formula;
    if (f?.formula_type === "battery_to_lead") {
      const p = f.parameters as Record<string, unknown>;
      setKgPerUnit(String(p.kg_lead_per_unit ?? ""));
      setBatteryRef((p.material_reference as string) ?? "none");
      setLeadPct("");
    } else if (f?.formula_type === "drosses_to_lead") {
      const p = f.parameters as Record<string, unknown>;
      setLeadPct(String(Number(p.lead_percentage ?? 0) * 100));
      setKgPerUnit("");
      setBatteryRef("none");
    } else {
      setKgPerUnit("");
      setBatteryRef("none");
      setLeadPct("");
    }
    setNotes("");
    setDialogOpen(true);
  };

  // Parámetros del factor (solo Willard); null = inválidos/incompletos
  const parameters = useMemo((): Record<string, unknown> | null => {
    if (!isWillard) return null;
    if (derivedType === "battery_to_lead") {
      const kg = parseFloat(kgPerUnit);
      if (!kg || kg <= 0) return null;
      const base: Record<string, unknown> = { kg_lead_per_unit: kg };
      if (batteryRef !== "none") base.material_reference = batteryRef;
      return base;
    }
    const pct = parseFloat(leadPct);
    if (!pct || pct <= 0 || pct > 100) return null;
    return { lead_percentage: pct / 100 };
  }, [isWillard, derivedType, kgPerUnit, batteryRef, leadPct]);

  const factorValid = !isWillard || parameters !== null;
  const canSubmit =
    !!code.trim() && !!name.trim() && !!categoryId && !!businessUnitId && factorValid && !saving;

  const invalidateAll = () => {
    qc.invalidateQueries({ queryKey: ["materials"] });
    qc.invalidateQueries({ queryKey: ["kg-profiles"] });
    qc.invalidateQueries({ queryKey: ["conversion-formulas"] });
  };

  /** ¿La fórmula del form difiere de la vigente? (sin cambio → no se postea: append-only) */
  const factorChanged = (): boolean => {
    if (!isWillard || !parameters) return false;
    const f = editRow?.formula;
    if (!f) return true; // no había — se crea
    if (f.formula_type !== derivedType) return true;
    const p = f.parameters as Record<string, unknown>;
    if (derivedType === "battery_to_lead") {
      return (
        Number(p.kg_lead_per_unit) !== Number(parameters.kg_lead_per_unit) ||
        (p.material_reference ?? null) !== (parameters.material_reference ?? null)
      );
    }
    return Number(p.lead_percentage) !== Number(parameters.lead_percentage);
  };

  // Submit encadenado (QA-a: toast específico del paso que falla; el material
  // queda "Sin clasificar" y se recupera desde Editar — sin rollback distribuido)
  const handleSubmit = async () => {
    if (!canSubmit) return;
    setSaving(true);
    const willardWorld: WillardWorld = classification === "compra" ? "none" : classification;
    const compraRegular = classification === "compra" ? true : alsoCompra;

    try {
      let materialId: string;
      if (editRow) {
        materialId = editRow.material.id;
        const m = editRow.material;
        const matDiff: Record<string, unknown> = {};
        if (name.trim() !== m.name) matDiff.name = name.trim();
        if ((description.trim() || null) !== (m.description ?? null)) matDiff.description = description.trim() || null;
        if (categoryId !== m.category_id) matDiff.category_id = categoryId;
        if (businessUnitId !== m.business_unit_id) matDiff.business_unit_id = businessUnitId;
        if (!unitLocked && unit !== (m.default_unit ?? "kg")) matDiff.default_unit = unit;
        if (Object.keys(matDiff).length > 0) {
          try {
            await materialService.update(materialId, matDiff);
          } catch (e) {
            toast.error(getApiErrorMessage(e, "Error al actualizar el material"));
            return;
          }
        }
      } else {
        try {
          const created = await materialService.create({
            code: code.trim(),
            name: name.trim(),
            description: description.trim() || null,
            category_id: categoryId,
            business_unit_id: businessUnitId,
            default_unit: unit,
          });
          materialId = created.id;
        } catch (e) {
          toast.error(getApiErrorMessage(e, "Error al crear el material"));
          return;
        }
      }

      const prevProfile = editRow?.profile;
      const profileChanged =
        !prevProfile ||
        prevProfile.willard_world !== willardWorld ||
        prevProfile.compra_regular !== compraRegular;
      if (profileChanged) {
        try {
          await sacConfigService.upsertKgProfile(materialId, {
            compra_regular: compraRegular,
            willard_world: willardWorld,
          });
        } catch (e) {
          toast.error(
            getApiErrorMessage(e, "Fallo la clasificación") +
              " — el material quedó guardado; complete la clasificación desde Editar"
          );
          return;
        }
      }

      if (factorChanged() && parameters) {
        try {
          await sacConfigService.createFormula({
            material_id: materialId,
            formula_type: derivedType,
            parameters,
            notes: notes.trim() || null,
          });
        } catch (e) {
          toast.error(
            getApiErrorMessage(e, "Fallo el factor de conversión") +
              " — material y clasificación guardados; complete el factor desde Editar"
          );
          return;
        }
      }

      toast.success(editRow ? "Material actualizado" : "Material configurado");
      setDialogOpen(false);
    } finally {
      invalidateAll();
      setSaving(false);
    }
  };

  // ---------------- Historial de fórmulas ----------------
  const [historyMaterial, setHistoryMaterial] = useState<{ id: string; label: string } | null>(null);
  const history = useFormulaHistory(historyMaterial?.id, historyMaterial !== null);

  // W2: export respeta los filtros activos (misma promesa que los demás exports)
  const handleExport = () => {
    const cl = (row: MaterialKgRow) => {
      const c = classificationOf(row);
      return c === "unclassified" ? "Sin clasificar" : CLASSIFICATION_LABELS[c];
    };
    exportMaterialsKgExcel(
      filteredRows.map((row) => ({
        code: row.material.code,
        name: row.material.name,
        unit: row.material.default_unit ?? "kg",
        category: row.material.category_name ?? "",
        businessUnit: row.material.business_unit_name ?? "",
        classification: cl(row),
        alsoCompra: classificationOf(row) !== "compra" && (row.profile?.compra_regular ?? false),
        factor: row.formula ? readableParams(row.formula) : "",
        since: row.formula ? formatDate(row.formula.created_at) : "",
        by: row.formula?.created_by_name ?? "",
        description: row.material.description ?? "",
      }))
    );
  };

  return (
    <ConfigLayout>
      <div className="flex flex-col sm:flex-row sm:flex-wrap gap-2 sm:items-center sm:justify-between">
        <div className="flex flex-col sm:flex-row gap-2 sm:items-center">
          <Input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Buscar código o nombre..."
            className="w-full sm:w-56"
          />
          <Select value={classFilter} onValueChange={setClassFilter}>
            <SelectTrigger className="w-full sm:w-52">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Todas las clasificaciones</SelectItem>
              <SelectItem value="unclassified">Sin clasificar</SelectItem>
              <SelectItem value="compra">Compra regular</SelectItem>
              <SelectItem value="postconsumo">Postconsumo (baterías)</SelectItem>
              <SelectItem value="drosses">Drosses</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div className="flex flex-col sm:flex-row gap-2">
          <Button variant="outline" onClick={handleExport} disabled={filteredRows.length === 0} className="w-full sm:w-auto">
            <Download className="h-4 w-4 mr-2" />
            Excel
          </Button>
          <Button variant="outline" onClick={() => navigate(ROUTES.MATERIALS_CATEGORIES)} className="w-full sm:w-auto">
            <Tag className="h-4 w-4 mr-2" />
            Categorías
          </Button>
          {canCreate && (
            <Button onClick={openCreate} className="bg-emerald-600 hover:bg-emerald-700 w-full sm:w-auto">
              <Plus className="h-4 w-4 mr-2" />
              Nuevo Material
            </Button>
          )}
        </div>
      </div>

      {!isLoading && rows.length === 0 ? (
        <EmptyState
          title="Sin materiales"
          description="Crea el primer material con su clasificación y factor — todo en un solo formulario."
        />
      ) : (
        <div className="overflow-x-auto -mx-3 sm:mx-0 rounded-lg border bg-white">
          <Table className="min-w-[1120px]">
            <TableHeader>
              <TableRow>
                <TableHead>Material</TableHead>
                <TableHead>Unidad</TableHead>
                <TableHead>Categoría</TableHead>
                <TableHead>Unidad de Negocio</TableHead>
                <TableHead>Clasificación</TableHead>
                <TableHead>Factor vigente</TableHead>
                <TableHead>Desde</TableHead>
                <TableHead>Por</TableHead>
                <TableHead className="w-20" />
              </TableRow>
            </TableHeader>
            <TableBody>
              {filteredRows.map((row) => (
                <TableRow key={row.material.id}>
                  <TableCell className="font-medium">
                    {row.material.code} - {row.material.name}
                  </TableCell>
                  <TableCell className="text-slate-600">{row.material.default_unit ?? "kg"}</TableCell>
                  <TableCell className="text-slate-600">{row.material.category_name ?? "—"}</TableCell>
                  <TableCell className="text-slate-600">{row.material.business_unit_name ?? "—"}</TableCell>
                  <TableCell>
                    <ClassificationBadge row={row} />
                  </TableCell>
                  <TableCell className="font-medium">
                    {row.formula ? readableParams(row.formula) : <span className="text-slate-400">—</span>}
                  </TableCell>
                  <TableCell>{row.formula ? formatDate(row.formula.created_at) : "—"}</TableCell>
                  <TableCell className="text-slate-500">{row.formula?.created_by_name ?? "—"}</TableCell>
                  <TableCell>
                    <div className="flex items-center gap-1">
                      {canEdit && (
                        <Button
                          variant="ghost"
                          size="sm"
                          title="Editar material, clasificación y factor"
                          onClick={() => openEdit(row)}
                        >
                          <Pencil className="h-4 w-4" />
                        </Button>
                      )}
                      {row.formula && (
                        <Button
                          variant="ghost"
                          size="sm"
                          title="Ver historial del factor"
                          onClick={() =>
                            setHistoryMaterial({
                              id: row.material.id,
                              label: `${row.material.code} - ${row.material.name}`,
                            })
                          }
                        >
                          <History className="h-4 w-4" />
                        </Button>
                      )}
                    </div>
                  </TableCell>
                </TableRow>
              ))}
              {filteredRows.length === 0 && (
                <TableRow>
                  <TableCell colSpan={9} className="text-center text-sm text-slate-400 py-6">
                    Sin materiales para el filtro seleccionado
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </div>
      )}

      {/* Formulario unificado: crear/editar material + clasificación + factor (C1) */}
      <Dialog open={dialogOpen} onOpenChange={(o) => !saving && setDialogOpen(o)}>
        <DialogContent className="max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>{editRow ? `Editar ${editRow.material.code}` : "Nuevo Material"}</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Código *</Label>
                <Input
                  value={code}
                  onChange={(e) => setCode(e.target.value.toUpperCase())}
                  disabled={!!editRow}
                  placeholder="Ej: BAT-07"
                />
              </div>
              <div>
                <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Unidad *</Label>
                <Select
                  value={unit}
                  onValueChange={(v) => setUnit(v as "kg" | "unidad")}
                  disabled={unitLocked}
                >
                  <SelectTrigger className="w-full"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="kg">kg</SelectItem>
                    <SelectItem value="unidad">unidad</SelectItem>
                  </SelectContent>
                </Select>
                {unitLocked && (
                  <p className="text-xs text-slate-400 mt-0.5">
                    Con fórmula vigente la unidad no se cambia.
                  </p>
                )}
              </div>
            </div>
            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Nombre *</Label>
              <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="Ej: Batería ref 07" />
            </div>
            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Descripción</Label>
              <Input value={description} onChange={(e) => setDescription(e.target.value)} placeholder="Opcional" />
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Categoría *</Label>
                <EntitySelect
                  value={categoryId}
                  onChange={setCategoryId}
                  options={categories.map((c) => ({ id: c.id, label: c.name }))}
                  placeholder="Seleccionar..."
                />
              </div>
              <div>
                <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Unidad de Negocio *</Label>
                <EntitySelect
                  value={businessUnitId}
                  onChange={setBusinessUnitId}
                  options={businessUnits.map((b) => ({ id: b.id, label: b.name }))}
                  placeholder="Seleccionar..."
                />
              </div>
            </div>

            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Clasificación *</Label>
              <Select value={classification} onValueChange={(v) => setClassification(v as Classification)}>
                <SelectTrigger className="w-full"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="compra">Compra regular</SelectItem>
                  <SelectItem value="postconsumo">Postconsumo (baterías)</SelectItem>
                  <SelectItem value="drosses">Drosses</SelectItem>
                </SelectContent>
              </Select>
              <p className="text-xs text-slate-400 mt-1">
                {isWillard
                  ? "Los kg de una recepción Willard van a la cuenta kg según esta clasificación."
                  : "Se recibe como Compra regular (deriva una compra registrada)."}
              </p>
            </div>

            {isWillard && (
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={alsoCompra}
                  onChange={(e) => setAlsoCompra(e.target.checked)}
                  className="h-4 w-4"
                />
                También entra por compra regular
              </label>
            )}

            {isWillard && (
              <div className="rounded-lg border border-slate-200 bg-slate-50/60 p-3 space-y-3">
                <p className="text-xs text-slate-500">
                  Factor de conversión — unidad '{unit}' →{" "}
                  {derivedType === "battery_to_lead" ? "kg de plomo por unidad" : "% de plomo"}
                </p>
                {derivedType === "battery_to_lead" ? (
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
                ) : (
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
                )}
                <div>
                  <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Notas del factor</Label>
                  <Input
                    value={notes}
                    onChange={(e) => setNotes(e.target.value)}
                    placeholder="Ej: vigente contrato 2026"
                    maxLength={500}
                  />
                </div>
                {editRow?.formula && (
                  <p className="text-xs text-slate-400">
                    Cambiar el factor crea una nueva versión vigente (el historial se conserva).
                  </p>
                )}
              </div>
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogOpen(false)} disabled={saving} className="w-full sm:w-auto">
              Cancelar
            </Button>
            <Button
              onClick={handleSubmit}
              disabled={!canSubmit}
              className="bg-emerald-600 hover:bg-emerald-700 w-full sm:w-auto"
            >
              {saving ? "Guardando..." : editRow ? "Guardar cambios" : "Crear Material"}
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
                  <TableHead>Factor</TableHead>
                  <TableHead>Por</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {(history.data?.items ?? []).map((h) => (
                  <TableRow key={h.id}>
                    <TableCell>{formatDate(h.created_at)}</TableCell>
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
