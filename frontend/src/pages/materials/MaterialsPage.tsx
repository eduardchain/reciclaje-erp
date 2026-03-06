import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { type ColumnDef } from "@tanstack/react-table";
import { Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { PageHeader } from "@/components/shared/PageHeader";
import { DataTable } from "@/components/shared/DataTable";
import { SearchInput } from "@/components/shared/SearchInput";
import { useMaterials } from "@/hooks/useMasterData";
import { formatCurrency } from "@/utils/formatters";
import { ROUTES } from "@/utils/constants";
import MaterialFormDialog from "./MaterialFormDialog";
import type { MaterialResponse } from "@/types/material";

const columns: ColumnDef<MaterialResponse, unknown>[] = [
  { accessorKey: "code", header: "Codigo", cell: ({ row }) => <span className="font-medium">{row.original.code}</span> },
  { accessorKey: "name", header: "Nombre" },
  { accessorKey: "default_unit", header: "Unidad" },
  { accessorKey: "current_stock_liquidated", header: "Stock Liq.", enableSorting: true, cell: ({ row }) => <span className="tabular-nums">{(row.original.current_stock_liquidated ?? 0).toFixed(2)}</span> },
  { accessorKey: "current_stock_transit", header: "Stock Trans.", cell: ({ row }) => <span className="tabular-nums">{(row.original.current_stock_transit ?? 0).toFixed(2)}</span> },
  { accessorKey: "current_average_cost", header: "Costo Prom.", enableSorting: true, cell: ({ row }) => formatCurrency(row.original.current_average_cost ?? 0) },
  { accessorKey: "total_value", header: "Valor", cell: ({ row }) => formatCurrency((row.original.current_stock_liquidated ?? 0) * (row.original.current_average_cost ?? 0)) },
];

export default function MaterialsPage() {
  const navigate = useNavigate();
  const [search, setSearch] = useState("");
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editItem, setEditItem] = useState<MaterialResponse | null>(null);

  const { data, isLoading } = useMaterials(search || undefined);

  return (
    <div className="space-y-4">
      <PageHeader title="Materiales" description="Catalogo de materiales">
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => navigate(ROUTES.MATERIALS_CATEGORIES)}>Categorias</Button>
          <Button onClick={() => { setEditItem(null); setDialogOpen(true); }} className="bg-emerald-600 hover:bg-emerald-700">
            <Plus className="h-4 w-4 mr-2" />Nuevo Material
          </Button>
        </div>
      </PageHeader>

      <DataTable
        columns={columns}
        data={data?.items ?? []}
        loading={isLoading}
        pageCount={1}
        pageIndex={0}
        pageSize={200}
        onPageChange={() => {}}
        onRowClick={(row) => { setEditItem(row); setDialogOpen(true); }}
        emptyTitle="Sin materiales"
        emptyDescription="No se encontraron materiales."
        exportFilename="ecobalance_materiales"
        toolbar={<SearchInput value={search} onChange={setSearch} placeholder="Buscar material..." />}
      />

      <MaterialFormDialog open={dialogOpen} onOpenChange={setDialogOpen} editItem={editItem} />
    </div>
  );
}
