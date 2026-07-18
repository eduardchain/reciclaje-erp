import { useMemo, useState } from "react";
import { type ColumnDef } from "@tanstack/react-table";
import { Plus } from "lucide-react";
import { usePermissions } from "@/hooks/usePermissions";
import { useOrgSettings } from "@/hooks/useOrgSettings";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { DataTable } from "@/components/shared/DataTable";
import { useWarehouses } from "@/hooks/useMasterData";
import { useCreateWarehouse, useUpdateWarehouse } from "@/hooks/useCrudData";
import ConfigLayout from "./ConfigLayout";
import type { WarehouseResponse } from "@/types/warehouse";

// Q-12: la columna "Recibe" solo aparece con kg_ledger (SAC) — prod identica
function getColumns(showReceiving: boolean): ColumnDef<WarehouseResponse, unknown>[] {
  return [
    { accessorKey: "name", header: "Nombre", cell: ({ row }) => <span className="font-medium">{row.original.name}</span> },
    { accessorKey: "description", header: "Descripcion", cell: ({ row }) => row.original.description ?? "-" },
    { accessorKey: "address", header: "Direccion", cell: ({ row }) => row.original.address ?? "-" },
    ...(showReceiving
      ? [{
          id: "is_receiving",
          header: "Recibe",
          cell: ({ row }: { row: { original: WarehouseResponse } }) =>
            row.original.is_receiving !== false ? (
              <span className="bg-emerald-100 text-emerald-700 text-xs px-1.5 py-0.5 rounded font-medium">Recibe</span>
            ) : (
              <span className="bg-slate-100 text-slate-500 text-xs px-1.5 py-0.5 rounded font-medium">Interna</span>
            ),
        } as ColumnDef<WarehouseResponse, unknown>]
      : []),
  ];
}

export default function WarehousesPage() {
  const { hasPermission } = usePermissions();
  const { flagEnabled } = useOrgSettings();
  const showReceiving = flagEnabled("kg_ledger_enabled");
  const { data, isLoading } = useWarehouses();
  const create = useCreateWarehouse();
  const update = useUpdateWarehouse();
  const columns = useMemo(() => getColumns(showReceiving), [showReceiving]);

  const [dialogOpen, setDialogOpen] = useState(false);
  const [editItem, setEditItem] = useState<WarehouseResponse | null>(null);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [address, setAddress] = useState("");
  const [isReceiving, setIsReceiving] = useState(true);

  const openDialog = (item: WarehouseResponse | null) => {
    setEditItem(item);
    setName(item?.name ?? ""); setDescription(item?.description ?? ""); setAddress(item?.address ?? "");
    setIsReceiving(item?.is_receiving ?? true);
    setDialogOpen(true);
  };

  const handleSubmit = () => {
    const payload = {
      name,
      description: description || null,
      address: address || null,
      // Q-12: solo se envia con flag — el payload de orgs prod queda identico
      ...(showReceiving ? { is_receiving: isReceiving } : {}),
    };
    const opts = { onSuccess: () => setDialogOpen(false) };
    if (editItem) { update.mutate({ id: editItem.id, data: payload }, opts); }
    else { create.mutate(payload, opts); }
  };

  return (
    <ConfigLayout>
      <div className="flex justify-end">
        {hasPermission("warehouses.create") && (
          <Button onClick={() => openDialog(null)} className="bg-emerald-600 hover:bg-emerald-700"><Plus className="h-4 w-4 mr-2" />Nueva Bodega</Button>
        )}
      </div>

      <DataTable columns={columns} data={data?.items ?? []} loading={isLoading} pageCount={1} pageIndex={0} pageSize={100} onPageChange={() => {}}
        onRowClick={hasPermission("warehouses.edit") ? (row) => openDialog(row) : undefined} emptyTitle="Sin bodegas" emptyDescription="No hay bodegas." exportFilename="ecobalance_bodegas" />

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="max-w-sm">
          <DialogHeader><DialogTitle>{editItem ? "Editar Bodega" : "Nueva Bodega"}</DialogTitle></DialogHeader>
          <div className="space-y-4">
            <div><Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Nombre *</Label><Input value={name} onChange={(e) => setName(e.target.value)} /></div>
            <div><Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Descripcion</Label><Input value={description} onChange={(e) => setDescription(e.target.value)} /></div>
            <div><Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Direccion</Label><Input value={address} onChange={(e) => setAddress(e.target.value)} /></div>
            {showReceiving && (
              <div className="flex items-start gap-2">
                <Checkbox
                  id="wh-receiving"
                  checked={isReceiving}
                  onCheckedChange={(v) => setIsReceiving(v === true)}
                  className="mt-0.5"
                />
                <div>
                  <Label htmlFor="wh-receiving" className="text-sm font-normal cursor-pointer">
                    Recibe material de terceros
                  </Label>
                  <p className="text-xs text-slate-400">
                    Desmarcar en bodegas internas (molino, tránsito) — no aparecen en Recepción.
                  </p>
                </div>
              </div>
            )}
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
