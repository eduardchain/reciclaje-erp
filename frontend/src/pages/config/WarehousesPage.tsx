import { useState } from "react";
import { type ColumnDef } from "@tanstack/react-table";
import { Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { DataTable } from "@/components/shared/DataTable";
import { useWarehouses } from "@/hooks/useMasterData";
import { useCreateWarehouse, useUpdateWarehouse } from "@/hooks/useCrudData";
import ConfigLayout from "./ConfigLayout";
import type { WarehouseResponse } from "@/types/warehouse";

const columns: ColumnDef<WarehouseResponse, unknown>[] = [
  { accessorKey: "name", header: "Nombre", cell: ({ row }) => <span className="font-medium">{row.original.name}</span> },
  { accessorKey: "description", header: "Descripcion", cell: ({ row }) => row.original.description ?? "-" },
  { accessorKey: "address", header: "Direccion", cell: ({ row }) => row.original.address ?? "-" },
];

export default function WarehousesPage() {
  const { data, isLoading } = useWarehouses();
  const create = useCreateWarehouse();
  const update = useUpdateWarehouse();

  const [dialogOpen, setDialogOpen] = useState(false);
  const [editItem, setEditItem] = useState<WarehouseResponse | null>(null);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [address, setAddress] = useState("");

  const openDialog = (item: WarehouseResponse | null) => {
    setEditItem(item);
    setName(item?.name ?? ""); setDescription(item?.description ?? ""); setAddress(item?.address ?? "");
    setDialogOpen(true);
  };

  const handleSubmit = () => {
    const payload = { name, description: description || null, address: address || null };
    const opts = { onSuccess: () => setDialogOpen(false) };
    if (editItem) { update.mutate({ id: editItem.id, data: payload }, opts); }
    else { create.mutate(payload, opts); }
  };

  return (
    <ConfigLayout>
      <div className="flex justify-end">
        <Button onClick={() => openDialog(null)} className="bg-emerald-600 hover:bg-emerald-700"><Plus className="h-4 w-4 mr-2" />Nueva Bodega</Button>
      </div>

      <DataTable columns={columns} data={data?.items ?? []} loading={isLoading} pageCount={1} pageIndex={0} pageSize={100} onPageChange={() => {}}
        onRowClick={(row) => openDialog(row)} emptyTitle="Sin bodegas" emptyDescription="No hay bodegas." exportFilename="ecobalance_bodegas" />

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="max-w-sm">
          <DialogHeader><DialogTitle>{editItem ? "Editar Bodega" : "Nueva Bodega"}</DialogTitle></DialogHeader>
          <div className="space-y-4">
            <div><Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Nombre *</Label><Input value={name} onChange={(e) => setName(e.target.value)} /></div>
            <div><Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Descripcion</Label><Input value={description} onChange={(e) => setDescription(e.target.value)} /></div>
            <div><Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Direccion</Label><Input value={address} onChange={(e) => setAddress(e.target.value)} /></div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogOpen(false)}>Cancelar</Button>
            <Button onClick={handleSubmit} disabled={!name || create.isPending || update.isPending} className="bg-emerald-600 hover:bg-emerald-700">
              {create.isPending || update.isPending ? "Guardando..." : editItem ? "Actualizar" : "Crear"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </ConfigLayout>
  );
}
