import { useState, useEffect, useMemo } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";

import { useCreateThirdParty, useUpdateThirdParty } from "@/hooks/useCrudData";
import { useThirdPartyCategoriesFlat } from "@/hooks/useMasterData";
import type { ThirdPartyResponse } from "@/types/third-party";

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  editItem: ThirdPartyResponse | null;
}

const BEHAVIOR_COLORS: Record<string, string> = {
  material_supplier: "bg-blue-50 text-blue-700",
  service_provider: "bg-rose-50 text-rose-700",
  customer: "bg-emerald-50 text-emerald-700",
  investor: "bg-purple-50 text-purple-700",
  generic: "bg-slate-50 text-slate-700",
  provision: "bg-orange-50 text-orange-700",
  liability: "bg-amber-50 text-amber-700",
};

const BEHAVIOR_ORDER = [
  { value: "material_supplier", label: "PROVEEDOR MATERIAL" },
  { value: "service_provider", label: "PROVEEDOR SERVICIOS" },
  { value: "customer", label: "CLIENTE" },
  { value: "investor", label: "INVERSIONISTA" },
  { value: "generic", label: "GENÉRICO" },
  { value: "provision", label: "PROVISIÓN" },
  { value: "liability", label: "PASIVO" },
];

export default function ThirdPartyFormDialog({ open, onOpenChange, editItem }: Props) {
  const create = useCreateThirdParty();
  const update = useUpdateThirdParty();
  const { data: categoriesData } = useThirdPartyCategoriesFlat();
  const categories = categoriesData?.items ?? [];

  const [name, setName] = useState("");
  const [identification, setIdentification] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [address, setAddress] = useState("");
  const [categoryIds, setCategoryIds] = useState<string[]>([]);

  useEffect(() => {
    if (editItem) {
      setName(editItem.name);
      setIdentification(editItem.identification_number ?? "");
      setEmail(editItem.email ?? "");
      setPhone(editItem.phone ?? "");
      setAddress(editItem.address ?? "");
      setCategoryIds((editItem.categories ?? []).map((c) => c.id));
    } else {
      setName(""); setIdentification(""); setEmail(""); setPhone(""); setAddress("");
      setCategoryIds([]);
    }
  }, [editItem, open]);

  const toggleCategory = (id: string) => {
    setCategoryIds((prev) => prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]);
  };

  const handleSubmit = () => {
    const base = {
      name,
      identification_number: identification || null,
      email: email || null,
      phone: phone || null,
      address: address || null,
      category_ids: categoryIds,
    };
    const opts = { onSuccess: () => onOpenChange(false) };

    if (editItem) {
      update.mutate({ id: editItem.id, data: base }, opts);
    } else {
      create.mutate({ ...base, initial_balance: 0 }, opts);
    }
  };

  const isPending = create.isPending || update.isPending;
  const activeCategories = useMemo(() => categories.filter((c) => c.is_active !== false), [categories]);
  const selectedCategories = activeCategories.filter((c) => categoryIds.includes(c.id));
  const HIDDEN_BEHAVIORS = ["liability", "provision"];
  const isRestrictedType = editItem && (editItem.categories ?? []).some((c) => HIDDEN_BEHAVIORS.includes(c.behavior_type));
  const groupedCategories = useMemo(() => {
    return BEHAVIOR_ORDER
      .filter((bt) => !HIDDEN_BEHAVIORS.includes(bt.value))
      .map((bt) => ({ ...bt, items: activeCategories.filter((c) => c.behavior_type === bt.value) }))
      .filter((g) => g.items.length > 0);
  }, [activeCategories]);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>{editItem ? "Editar Tercero" : "Nuevo Tercero"}</DialogTitle>
        </DialogHeader>
        <div className="space-y-4">
          <div><Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Nombre *</Label><Input value={name} onChange={(e) => setName(e.target.value)} /></div>
          <div><Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Identificacion</Label><Input value={identification} onChange={(e) => setIdentification(e.target.value)} /></div>
          <div className="grid grid-cols-2 gap-4">
            <div><Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Email</Label><Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} /></div>
            <div><Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Telefono</Label><Input value={phone} onChange={(e) => setPhone(e.target.value)} /></div>
          </div>
          <div><Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Direccion</Label><Input value={address} onChange={(e) => setAddress(e.target.value)} /></div>
          {isRestrictedType ? (
            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Tipo</Label>
              <div className="flex gap-1 flex-wrap mt-1">
                {(editItem?.categories ?? []).filter((c) => HIDDEN_BEHAVIORS.includes(c.behavior_type)).map((c) => (
                  <Badge key={c.id} variant="outline" className={`${BEHAVIOR_COLORS[c.behavior_type] ?? ""} text-xs`}>
                    {c.display_name}
                  </Badge>
                ))}
              </div>
              <p className="text-xs text-slate-400 mt-1">Este tercero se administra desde su módulo correspondiente.</p>
            </div>
          ) : (
          <div className="space-y-2">
            <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Categorias</Label>
            {selectedCategories.length > 0 && (
              <div className="flex gap-1 flex-wrap">
                {selectedCategories.map((c) => (
                  <Badge key={c.id} variant="outline" className={`${BEHAVIOR_COLORS[c.behavior_type] ?? ""} text-xs cursor-pointer`} onClick={() => toggleCategory(c.id)}>
                    {c.display_name} ✕
                  </Badge>
                ))}
              </div>
            )}
            <div className="max-h-48 overflow-y-auto border rounded-md p-2 space-y-2">
              {groupedCategories.map((group) => (
                <div key={group.value}>
                  <p className="text-[10px] font-bold uppercase tracking-wider text-slate-400 px-1 mb-0.5">{group.label}</p>
                  {group.items.map((cat) => (
                    <label key={cat.id} className="flex items-center gap-2 text-sm cursor-pointer hover:bg-slate-50 rounded px-1 py-0.5">
                      <input type="checkbox" checked={categoryIds.includes(cat.id)} onChange={() => toggleCategory(cat.id)} className="rounded border-slate-300" />
                      <span>{cat.display_name}</span>
                    </label>
                  ))}
                </div>
              ))}
              {activeCategories.length === 0 && <p className="text-xs text-slate-400">No hay categorias configuradas.</p>}
            </div>
          </div>
          )}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>Cancelar</Button>
          <Button onClick={handleSubmit} disabled={!name || isPending} className="bg-emerald-600 hover:bg-emerald-700">
            {isPending ? "Guardando..." : editItem ? "Actualizar" : "Crear"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
