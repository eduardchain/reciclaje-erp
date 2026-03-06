import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { type ColumnDef } from "@tanstack/react-table";
import { Plus, ArrowLeft } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { PageHeader } from "@/components/shared/PageHeader";
import { DataTable } from "@/components/shared/DataTable";
import { useMaterialCategories, useCreateMaterialCategory, useUpdateMaterialCategory } from "@/hooks/useCrudData";
import { ROUTES } from "@/utils/constants";
import type { MaterialCategoryResponse } from "@/types/material";

const columns: ColumnDef<MaterialCategoryResponse, unknown>[] = [
  { accessorKey: "name", header: "Nombre", cell: ({ row }) => <span className="font-medium">{row.original.name}</span> },
  { accessorKey: "description", header: "Descripcion", cell: ({ row }) => row.original.description ?? "-" },
];

export default function CategoriesPage() {
  const navigate = useNavigate();
  const { data, isLoading } = useMaterialCategories();
  const create = useCreateMaterialCategory();
  const update = useUpdateMaterialCategory();

  const [dialogOpen, setDialogOpen] = useState(false);
  const [editItem, setEditItem] = useState<MaterialCategoryResponse | null>(null);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");

  const openDialog = (item: MaterialCategoryResponse | null) => {
    setEditItem(item);
    setName(item?.name ?? "");
    setDescription(item?.description ?? "");
    setDialogOpen(true);
  };

  const handleSubmit = () => {
    const payload = { name, description: description || null };
    const opts = { onSuccess: () => setDialogOpen(false) };
    if (editItem) {
      update.mutate({ id: editItem.id, data: payload }, opts);
    } else {
      create.mutate(payload, opts);
    }
  };

  return (
    <div className="space-y-4">
      <PageHeader title="Categorias de Material" description="Clasificacion de materiales">
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => navigate(ROUTES.MATERIALS)}><ArrowLeft className="h-4 w-4 mr-2" />Materiales</Button>
          <Button onClick={() => openDialog(null)} className="bg-emerald-600 hover:bg-emerald-700"><Plus className="h-4 w-4 mr-2" />Nueva Categoria</Button>
        </div>
      </PageHeader>

      <DataTable
        columns={columns}
        data={data?.items ?? []}
        loading={isLoading}
        pageCount={1} pageIndex={0} pageSize={100} onPageChange={() => {}}
        onRowClick={(row) => openDialog(row)}
        emptyTitle="Sin categorias" emptyDescription="No hay categorias de material."
        exportFilename="ecobalance_categorias-material"
      />

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="max-w-sm">
          <DialogHeader><DialogTitle>{editItem ? "Editar Categoria" : "Nueva Categoria"}</DialogTitle></DialogHeader>
          <div className="space-y-4">
            <div><Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Nombre *</Label><Input value={name} onChange={(e) => setName(e.target.value)} /></div>
            <div><Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Descripcion</Label><Input value={description} onChange={(e) => setDescription(e.target.value)} /></div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogOpen(false)}>Cancelar</Button>
            <Button onClick={handleSubmit} disabled={!name || create.isPending || update.isPending} className="bg-emerald-600 hover:bg-emerald-700">
              {create.isPending || update.isPending ? "Guardando..." : editItem ? "Actualizar" : "Crear"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
