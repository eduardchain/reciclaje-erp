import { useState } from "react";
import { type ColumnDef } from "@tanstack/react-table";
import { Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { DataTable } from "@/components/shared/DataTable";
import { useBusinessUnits, useCreateBusinessUnit, useUpdateBusinessUnit } from "@/hooks/useCrudData";
import ConfigLayout from "./ConfigLayout";
import type { BusinessUnitResponse } from "@/types/config";

const columns: ColumnDef<BusinessUnitResponse, unknown>[] = [
  { accessorKey: "name", header: "Nombre", cell: ({ row }) => <span className="font-medium">{row.original.name}</span> },
  { accessorKey: "description", header: "Descripcion", cell: ({ row }) => row.original.description ?? "-" },
];

export default function BusinessUnitsPage() {
  const { data, isLoading } = useBusinessUnits();
  const create = useCreateBusinessUnit();
  const update = useUpdateBusinessUnit();

  const [dialogOpen, setDialogOpen] = useState(false);
  const [editItem, setEditItem] = useState<BusinessUnitResponse | null>(null);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");

  const openDialog = (item: BusinessUnitResponse | null) => {
    setEditItem(item); setName(item?.name ?? ""); setDescription(item?.description ?? "");
    setDialogOpen(true);
  };

  const handleSubmit = () => {
    const payload = { name, description: description || null };
    const opts = { onSuccess: () => setDialogOpen(false) };
    if (editItem) { update.mutate({ id: editItem.id, data: payload }, opts); }
    else { create.mutate(payload, opts); }
  };

  return (
    <ConfigLayout>
      <div className="flex justify-end">
        <Button onClick={() => openDialog(null)} className="bg-green-600 hover:bg-green-700"><Plus className="h-4 w-4 mr-2" />Nueva Unidad</Button>
      </div>

      <DataTable columns={columns} data={data?.items ?? []} loading={isLoading} pageCount={1} pageIndex={0} pageSize={100} onPageChange={() => {}}
        onRowClick={(row) => openDialog(row)} emptyTitle="Sin unidades" emptyDescription="No hay unidades de negocio." />

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="max-w-sm">
          <DialogHeader><DialogTitle>{editItem ? "Editar Unidad" : "Nueva Unidad de Negocio"}</DialogTitle></DialogHeader>
          <div className="space-y-4">
            <div><Label>Nombre *</Label><Input value={name} onChange={(e) => setName(e.target.value)} /></div>
            <div><Label>Descripcion</Label><Input value={description} onChange={(e) => setDescription(e.target.value)} /></div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogOpen(false)}>Cancelar</Button>
            <Button onClick={handleSubmit} disabled={!name || create.isPending || update.isPending} className="bg-green-600 hover:bg-green-700">
              {create.isPending || update.isPending ? "Guardando..." : editItem ? "Actualizar" : "Crear"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </ConfigLayout>
  );
}
