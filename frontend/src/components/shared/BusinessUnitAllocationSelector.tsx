import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import { EntitySelect } from "@/components/shared/EntitySelect";
import { useBusinessUnits } from "@/hooks/useCrudData";

type AllocationType = "direct" | "shared" | "general";

interface Props {
  businessUnitId: string;
  setBusinessUnitId: (v: string) => void;
  applicableBusinessUnitIds: string[];
  setApplicableBusinessUnitIds: (v: string[]) => void;
  allocationType: AllocationType;
  setAllocationType: (v: AllocationType) => void;
}

const OPTIONS: { value: AllocationType; label: string }[] = [
  { value: "direct", label: "Directo a UNA unidad" },
  { value: "shared", label: "Compartido entre ALGUNAS" },
  { value: "general", label: "General (TODAS)" },
];

export function BusinessUnitAllocationSelector({
  businessUnitId,
  setBusinessUnitId,
  applicableBusinessUnitIds,
  setApplicableBusinessUnitIds,
  allocationType,
  setAllocationType,
}: Props) {
  const { data: busData } = useBusinessUnits();
  const businessUnits = (busData?.items ?? []).filter((bu) => bu.is_active);

  const handleTypeChange = (v: AllocationType) => {
    setAllocationType(v);
    if (v !== "direct") setBusinessUnitId("");
    if (v !== "shared") setApplicableBusinessUnitIds([]);
  };

  const toggleBU = (id: string) => {
    setApplicableBusinessUnitIds(
      applicableBusinessUnitIds.includes(id)
        ? applicableBusinessUnitIds.filter((x) => x !== id)
        : [...applicableBusinessUnitIds, id]
    );
  };

  return (
    <div className="md:col-span-2 space-y-3">
      <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">
        Unidad de Negocio
      </Label>
      <div className="flex flex-wrap gap-2">
        {OPTIONS.map((opt) => (
          <button
            key={opt.value}
            type="button"
            onClick={() => handleTypeChange(opt.value)}
            className={`px-3 py-1.5 text-xs rounded-full border transition-colors ${
              allocationType === opt.value
                ? "bg-emerald-600 text-white border-emerald-600"
                : "bg-white text-slate-600 border-slate-300 hover:border-slate-400"
            }`}
          >
            {opt.label}
          </button>
        ))}
      </div>

      {allocationType === "direct" && (
        <EntitySelect
          value={businessUnitId}
          onChange={setBusinessUnitId}
          options={businessUnits.map((bu) => ({ id: bu.id, label: bu.name }))}
          placeholder="Seleccionar unidad de negocio..."
        />
      )}

      {allocationType === "shared" && (
        <div className="grid grid-cols-2 md:grid-cols-3 gap-2 p-3 border rounded-md bg-slate-50">
          {businessUnits.map((bu) => (
            <div key={bu.id} className="flex items-center space-x-2">
              <Checkbox
                id={`bu-${bu.id}`}
                checked={applicableBusinessUnitIds.includes(bu.id)}
                onCheckedChange={() => toggleBU(bu.id)}
              />
              <label htmlFor={`bu-${bu.id}`} className="text-sm cursor-pointer">{bu.name}</label>
            </div>
          ))}
          {businessUnits.length === 0 && (
            <p className="text-xs text-slate-400 col-span-full">No hay unidades de negocio activas</p>
          )}
        </div>
      )}
    </div>
  );
}
