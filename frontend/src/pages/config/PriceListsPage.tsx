import { useState } from "react";
import { type ColumnDef } from "@tanstack/react-table";
import { Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { DataTable } from "@/components/shared/DataTable";
import { EntitySelect } from "@/components/shared/EntitySelect";
import { usePriceLists, useCreatePriceList } from "@/hooks/useCrudData";
import { useMaterials } from "@/hooks/useMasterData";
import { formatCurrency, formatDate } from "@/utils/formatters";
import ConfigLayout from "./ConfigLayout";
import type { PriceListResponse } from "@/types/config";

export default function PriceListsPage() {
  const { data, isLoading } = usePriceLists();
  const { data: materialsData } = useMaterials();
  const materials = materialsData?.items ?? [];
  const create = useCreatePriceList();

  const [dialogOpen, setDialogOpen] = useState(false);
  const [materialId, setMaterialId] = useState("");
  const [purchasePrice, setPurchasePrice] = useState(0);
  const [salePrice, setSalePrice] = useState(0);
  const [notes, setNotes] = useState("");

  const materialMap = new Map(materials.map((m) => [m.id, `${m.code} - ${m.name}`]));

  const priceColumns: ColumnDef<PriceListResponse, unknown>[] = [
    { accessorKey: "created_at", header: "Fecha", cell: ({ row }) => formatDate(row.original.created_at) },
    { accessorKey: "material_id", header: "Material", cell: ({ row }) => materialMap.get(row.original.material_id) ?? row.original.material_id },
    { accessorKey: "purchase_price", header: "Precio Compra", cell: ({ row }) => formatCurrency(row.original.purchase_price) },
    { accessorKey: "sale_price", header: "Precio Venta", cell: ({ row }) => formatCurrency(row.original.sale_price) },
    { accessorKey: "notes", header: "Notas", cell: ({ row }) => row.original.notes ?? "-" },
  ];

  const handleSubmit = () => {
    create.mutate(
      { material_id: materialId, purchase_price: purchasePrice, sale_price: salePrice, notes: notes || null },
      { onSuccess: () => { setDialogOpen(false); setMaterialId(""); setPurchasePrice(0); setSalePrice(0); setNotes(""); } },
    );
  };

  return (
    <ConfigLayout>
      <div className="flex justify-end">
        <Button onClick={() => setDialogOpen(true)} className="bg-green-600 hover:bg-green-700"><Plus className="h-4 w-4 mr-2" />Nuevo Precio</Button>
      </div>

      <DataTable columns={priceColumns} data={data?.items ?? []} loading={isLoading} pageCount={1} pageIndex={0} pageSize={200} onPageChange={() => {}}
        emptyTitle="Sin precios" emptyDescription="No hay precios registrados." />

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="max-w-sm">
          <DialogHeader><DialogTitle>Registrar Precio</DialogTitle></DialogHeader>
          <div className="space-y-4">
            <div><Label>Material *</Label><EntitySelect value={materialId} onChange={setMaterialId} options={materials.map((m) => ({ id: m.id, label: `${m.code} - ${m.name}` }))} placeholder="Seleccionar..." /></div>
            <div><Label>Precio Compra</Label><Input type="number" min={0} step="1" value={purchasePrice || ""} onChange={(e) => setPurchasePrice(parseFloat(e.target.value) || 0)} /></div>
            <div><Label>Precio Venta</Label><Input type="number" min={0} step="1" value={salePrice || ""} onChange={(e) => setSalePrice(parseFloat(e.target.value) || 0)} /></div>
            <div><Label>Notas</Label><Input value={notes} onChange={(e) => setNotes(e.target.value)} /></div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogOpen(false)}>Cancelar</Button>
            <Button onClick={handleSubmit} disabled={!materialId || create.isPending} className="bg-green-600 hover:bg-green-700">
              {create.isPending ? "Guardando..." : "Registrar"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </ConfigLayout>
  );
}
