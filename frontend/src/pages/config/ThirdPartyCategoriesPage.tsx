import { useState, useMemo } from "react";
import { type ColumnDef } from "@tanstack/react-table";
import { Plus } from "lucide-react";
import { usePermissions } from "@/hooks/usePermissions";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { DataTable } from "@/components/shared/DataTable";
import { EntitySelect } from "@/components/shared/EntitySelect";
import { useThirdPartyCategoriesList, useCreateThirdPartyCategory, useUpdateThirdPartyCategory } from "@/hooks/useCrudData";
import ConfigLayout from "./ConfigLayout";
import type { ThirdPartyCategoryResponse } from "@/types/third-party-category";

const BEHAVIOR_TYPES = [
  { value: "material_supplier", label: "Proveedor Material" },
  { value: "service_provider", label: "Proveedor Servicios" },
  { value: "customer", label: "Cliente" },
  { value: "investor", label: "Inversionista" },
  { value: "generic", label: "Genérico" },
  { value: "provision", label: "Provisión" },
  { value: "liability", label: "Pasivo" },
];

const BEHAVIOR_COLORS: Record<string, string> = {
  material_supplier: "bg-blue-50 text-blue-700",
  service_provider: "bg-rose-50 text-rose-700",
  customer: "bg-emerald-50 text-emerald-700",
  investor: "bg-purple-50 text-purple-700",
  generic: "bg-slate-50 text-slate-700",
  provision: "bg-orange-50 text-orange-700",
  liability: "bg-amber-50 text-amber-700",
};

const columns: ColumnDef<ThirdPartyCategoryResponse, unknown>[] = [
  { accessorKey: "name", header: "Nombre", cell: ({ row }) => <span className="font-medium">{row.original.name}</span> },
  { accessorKey: "parent_name", header: "Categoria Padre", cell: ({ row }) => row.original.parent_name ?? "-" },
  {
    accessorKey: "behavior_type",
    header: "Tipo",
    cell: ({ row }) => {
      const bt = row.original.behavior_type;
      const label = BEHAVIOR_TYPES.find((t) => t.value === bt)?.label ?? bt;
      return <Badge variant="outline" className={BEHAVIOR_COLORS[bt] ?? ""}>{label}</Badge>;
    },
  },
  { accessorKey: "description", header: "Descripcion", cell: ({ row }) => row.original.description ?? "-" },
  {
    accessorKey: "is_active",
    header: "Estado",
    cell: ({ row }) => row.original.is_active
      ? <Badge variant="outline" className="bg-green-50 text-green-700">Activa</Badge>
      : <Badge variant="outline" className="bg-red-50 text-red-700">Inactiva</Badge>,
  },
];

export default function ThirdPartyCategoriesPage() {
  const { hasPermission } = usePermissions();
  const { data, isLoading } = useThirdPartyCategoriesList();
  const create = useCreateThirdPartyCategory();
  const update = useUpdateThirdPartyCategory();

  const [dialogOpen, setDialogOpen] = useState(false);
  const [editItem, setEditItem] = useState<ThirdPartyCategoryResponse | null>(null);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [behaviorType, setBehaviorType] = useState("");
  const [parentId, setParentId] = useState("");
  const [isActive, setIsActive] = useState(true);

  const items = data?.items ?? [];

  const parentOptions = useMemo(() => {
    return items
      .filter((c) => !c.parent_id && c.id !== editItem?.id)
      .map((c) => ({ id: c.id, label: `${c.name} (${BEHAVIOR_TYPES.find((t) => t.value === c.behavior_type)?.label ?? c.behavior_type})` }));
  }, [items, editItem]);

  const openDialog = (item: ThirdPartyCategoryResponse | null) => {
    setEditItem(item);
    setName(item?.name ?? "");
    setDescription(item?.description ?? "");
    setBehaviorType(item?.behavior_type ?? "");
    setParentId(item?.parent_id ?? "");
    setIsActive(item?.is_active ?? true);
    setDialogOpen(true);
  };

  const handleSubmit = () => {
    const payload: Record<string, unknown> = {
      name,
      description: description || null,
      parent_id: parentId || null,
    };
    if (!parentId) {
      payload.behavior_type = behaviorType;
    }
    if (editItem) {
      payload.is_active = isActive;
    }
    const opts = { onSuccess: () => setDialogOpen(false) };
    if (editItem) { update.mutate({ id: editItem.id, data: payload }, opts); }
    else { create.mutate(payload as never, opts); }
  };

  return (
    <ConfigLayout>
      <div className="flex justify-end">
        {hasPermission("third_parties.create") && (
          <Button onClick={() => openDialog(null)} className="bg-emerald-600 hover:bg-emerald-700"><Plus className="h-4 w-4 mr-2" />Nueva Categoria</Button>
        )}
      </div>

      <DataTable columns={columns} data={items} loading={isLoading} pageCount={1} pageIndex={0} pageSize={100} onPageChange={() => {}}
        onRowClick={hasPermission("third_parties.create") ? (row) => openDialog(row) : undefined} emptyTitle="Sin categorias" emptyDescription="No hay categorias de terceros." exportFilename="ecobalance_categorias-terceros" />

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="max-w-sm">
          <DialogHeader><DialogTitle>{editItem ? "Editar Categoria" : "Nueva Categoria de Tercero"}</DialogTitle></DialogHeader>
          <div className="space-y-4">
            <div><Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Nombre *</Label><Input value={name} onChange={(e) => setName(e.target.value)} /></div>
            <div><Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Descripcion</Label><Input value={description} onChange={(e) => setDescription(e.target.value)} /></div>
            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Categoria Padre (opcional)</Label>
              <EntitySelect
                value={parentId}
                onChange={setParentId}
                options={parentOptions}
                placeholder="Sin padre (categoria principal)"
              />
            </div>
            {!parentId && (
              <div>
                <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Tipo de Comportamiento *</Label>
                <Select value={behaviorType} onValueChange={setBehaviorType}>
                  <SelectTrigger><SelectValue placeholder="Seleccionar tipo..." /></SelectTrigger>
                  <SelectContent>
                    {BEHAVIOR_TYPES.filter((t) => !["liability", "provision"].includes(t.value)).map((t) => (
                      <SelectItem key={t.value} value={t.value}>{t.label}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            )}
            {parentId && (
              <p className="text-xs text-slate-400">El tipo de comportamiento se hereda de la categoria padre.</p>
            )}
            {editItem && (
              <div className="flex items-center justify-between">
                <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Activa</Label>
                <Switch checked={isActive} onCheckedChange={setIsActive} />
              </div>
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogOpen(false)}>Cancelar</Button>
            <Button onClick={handleSubmit} disabled={!name || (!parentId && !behaviorType) || create.isPending || update.isPending} className="bg-emerald-600 hover:bg-emerald-700">
              {create.isPending || update.isPending ? "Guardando..." : editItem ? "Actualizar" : "Crear"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </ConfigLayout>
  );
}
