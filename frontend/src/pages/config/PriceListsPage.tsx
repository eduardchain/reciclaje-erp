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
import { MoneyInput } from "@/components/shared/MoneyInput";
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

  // Mapa de precio vigente por material (primer registro = mas reciente)
  const currentPriceMap = new Map<string, { purchase_price: number; sale_price: number }>();
  for (const item of data?.items ?? []) {
    if (!currentPriceMap.has(item.material_id)) {
      currentPriceMap.set(item.material_id, { purchase_price: Number(item.purchase_price), sale_price: Number(item.sale_price) });
    }
  }

  const prefillFromMaterial = (matId: string) => {
    const current = currentPriceMap.get(matId);
    if (current) {
      setPurchasePrice(current.purchase_price);
      setSalePrice(current.sale_price);
    } else {
      setPurchasePrice(0);
      setSalePrice(0);
    }
  };

  const handleMaterialChange = (matId: string) => {
    setMaterialId(matId);
    if (matId) prefillFromMaterial(matId);
  };

  const openDialogForRow = (row: PriceListResponse) => {
    setMaterialId(row.material_id);
    prefillFromMaterial(row.material_id);
    setNotes("");
    setDialogOpen(true);
  };

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
        <Button onClick={() => { setMaterialId(""); setPurchasePrice(0); setSalePrice(0); setNotes(""); setDialogOpen(true); }} className="bg-emerald-600 hover:bg-emerald-700"><Plus className="h-4 w-4 mr-2" />Nuevo Precio</Button>
      </div>

      <DataTable columns={priceColumns} data={data?.items ?? []} loading={isLoading} pageCount={1} pageIndex={0} pageSize={200} onPageChange={() => {}}
        onRowClick={openDialogForRow}
        emptyTitle="Sin precios" emptyDescription="No hay precios registrados." exportFilename="ecobalance_lista-precios" />

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="max-w-sm">
          <DialogHeader><DialogTitle>Registrar Precio</DialogTitle></DialogHeader>
          <div className="space-y-4">
            <div><Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Material *</Label><EntitySelect value={materialId} onChange={handleMaterialChange} options={materials.map((m) => ({ id: m.id, label: `${m.code} - ${m.name}` }))} placeholder="Seleccionar..." /></div>
            <div><Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Precio Compra</Label><MoneyInput value={purchasePrice} onChange={setPurchasePrice} /></div>
            <div><Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Precio Venta</Label><MoneyInput value={salePrice} onChange={setSalePrice} /></div>
            <div><Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Notas</Label><Input value={notes} onChange={(e) => setNotes(e.target.value)} /></div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogOpen(false)}>Cancelar</Button>
            <Button onClick={handleSubmit} disabled={!materialId || create.isPending} className="bg-emerald-600 hover:bg-emerald-700">
              {create.isPending ? "Guardando..." : "Registrar"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </ConfigLayout>
  );
}
