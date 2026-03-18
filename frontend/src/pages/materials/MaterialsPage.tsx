import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { type ColumnDef } from "@tanstack/react-table";
import { Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { PageHeader } from "@/components/shared/PageHeader";
import { DataTable } from "@/components/shared/DataTable";
import { SearchInput } from "@/components/shared/SearchInput";
import { useMaterials } from "@/hooks/useMasterData";
import { ROUTES } from "@/utils/constants";
import MaterialFormDialog from "./MaterialFormDialog";
import type { MaterialResponse } from "@/types/material";
import { usePermissions } from "@/hooks/usePermissions";

const columns: ColumnDef<MaterialResponse, unknown>[] = [
  { accessorKey: "code", header: "Codigo", cell: ({ row }) => <span className="font-medium">{row.original.code}</span> },
  { accessorKey: "name", header: "Nombre" },
  { accessorKey: "default_unit", header: "Unidad" },
  { accessorKey: "category_name", header: "Categoria", cell: ({ row }) => row.original.category_name ?? "-" },
  { accessorKey: "business_unit_name", header: "Unidad de Negocio", cell: ({ row }) => row.original.business_unit_name ?? "-" },
  { accessorKey: "description", header: "Descripcion", cell: ({ row }) => <span className="text-slate-500">{row.original.description ?? "-"}</span> },
];

export default function MaterialsPage() {
  const navigate = useNavigate();
  const { hasPermission } = usePermissions();
  const [search, setSearch] = useState("");
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editItem, setEditItem] = useState<MaterialResponse | null>(null);

  const { data, isLoading } = useMaterials(search || undefined);

  return (
    <div className="space-y-4">
      <PageHeader title="Materiales" description="Catalogo de materiales">
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => navigate(ROUTES.MATERIALS_CATEGORIES)}>Categorias</Button>
          {hasPermission("materials.create") && (
            <Button onClick={() => { setEditItem(null); setDialogOpen(true); }} className="bg-emerald-600 hover:bg-emerald-700">
              <Plus className="h-4 w-4 mr-2" />Nuevo Material
            </Button>
          )}
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
