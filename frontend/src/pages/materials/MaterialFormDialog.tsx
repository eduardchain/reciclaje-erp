import { useState, useEffect } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { EntitySelect } from "@/components/shared/EntitySelect";
import { useCreateMaterial, useUpdateMaterial, useMaterialCategories, useBusinessUnits } from "@/hooks/useCrudData";
import type { MaterialResponse } from "@/types/material";

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  editItem: MaterialResponse | null;
}

export default function MaterialFormDialog({ open, onOpenChange, editItem }: Props) {
  const create = useCreateMaterial();
  const update = useUpdateMaterial();
  const { data: categoriesData } = useMaterialCategories();
  const { data: businessUnitsData } = useBusinessUnits();

  const categories = categoriesData?.items ?? [];
  const businessUnits = businessUnitsData?.items ?? [];

  const [code, setCode] = useState("");
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [categoryId, setCategoryId] = useState("");
  const [businessUnitId, setBusinessUnitId] = useState("");
  const [defaultUnit, setDefaultUnit] = useState("kg");

  useEffect(() => {
    if (editItem) {
      setCode(editItem.code); setName(editItem.name); setDescription(editItem.description ?? "");
      setCategoryId(editItem.category_id); setBusinessUnitId(editItem.business_unit_id); setDefaultUnit(editItem.default_unit);
    } else {
      setCode(""); setName(""); setDescription(""); setCategoryId(""); setBusinessUnitId(""); setDefaultUnit("kg");
    }
  }, [editItem, open]);

  const handleSubmit = () => {
    const data = {
      code, name,
      description: description || null,
      category_id: categoryId,
      business_unit_id: businessUnitId,
      default_unit: defaultUnit,
    };
    const opts = { onSuccess: () => onOpenChange(false) };

    if (editItem) {
      update.mutate({ id: editItem.id, data }, opts);
    } else {
      create.mutate(data, opts);
    }
  };

  const canSubmit = code && name && categoryId && businessUnitId && defaultUnit;
  const isPending = create.isPending || update.isPending;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>{editItem ? "Editar Material" : "Nuevo Material"}</DialogTitle>
        </DialogHeader>
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div><Label>Codigo *</Label><Input value={code} onChange={(e) => setCode(e.target.value)} /></div>
            <div><Label>Unidad *</Label><Input value={defaultUnit} onChange={(e) => setDefaultUnit(e.target.value)} /></div>
          </div>
          <div><Label>Nombre *</Label><Input value={name} onChange={(e) => setName(e.target.value)} /></div>
          <div><Label>Descripcion</Label><Input value={description} onChange={(e) => setDescription(e.target.value)} /></div>
          <div><Label>Categoria *</Label><EntitySelect value={categoryId} onChange={setCategoryId} options={categories.map((c) => ({ id: c.id, label: c.name }))} placeholder="Seleccionar..." /></div>
          <div><Label>Unidad de Negocio *</Label><EntitySelect value={businessUnitId} onChange={setBusinessUnitId} options={businessUnits.map((b) => ({ id: b.id, label: b.name }))} placeholder="Seleccionar..." /></div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>Cancelar</Button>
          <Button onClick={handleSubmit} disabled={!canSubmit || isPending} className="bg-green-600 hover:bg-green-700">
            {isPending ? "Guardando..." : editItem ? "Actualizar" : "Crear"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
