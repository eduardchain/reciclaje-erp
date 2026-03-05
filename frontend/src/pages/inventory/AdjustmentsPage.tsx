import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { type ColumnDef } from "@tanstack/react-table";
import { Plus, ArrowLeft } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { PageHeader } from "@/components/shared/PageHeader";
import { DataTable } from "@/components/shared/DataTable";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { DateRangePicker } from "@/components/shared/DateRangePicker";
import { useAdjustments } from "@/hooks/useInventory";
import { formatCurrency, formatDate } from "@/utils/formatters";
import { ROUTES } from "@/utils/constants";
import type { InventoryAdjustmentResponse } from "@/types/inventory";

const PAGE_SIZE = 20;

const typeLabels: Record<string, string> = {
  increase: "Aumento",
  decrease: "Disminucion",
  recount: "Conteo",
  zero_out: "Llevar a Cero",
};

const typeColors: Record<string, string> = {
  increase: "bg-green-100 text-green-800",
  decrease: "bg-red-100 text-red-800",
  recount: "bg-blue-100 text-blue-800",
  zero_out: "bg-orange-100 text-orange-800",
};

const columns: ColumnDef<InventoryAdjustmentResponse, unknown>[] = [
  { accessorKey: "adjustment_number", header: "#", cell: ({ row }) => <span className="font-medium">#{row.original.adjustment_number}</span> },
  { accessorKey: "date", header: "Fecha", cell: ({ row }) => formatDate(row.original.date) },
  { accessorKey: "adjustment_type", header: "Tipo", cell: ({ row }) => <Badge variant="outline" className={typeColors[row.original.adjustment_type] ?? ""}>{typeLabels[row.original.adjustment_type] ?? row.original.adjustment_type}</Badge> },
  { accessorKey: "material_name", header: "Material", cell: ({ row }) => `${row.original.material_code ?? ""} - ${row.original.material_name ?? ""}` },
  { accessorKey: "warehouse_name", header: "Bodega" },
  { accessorKey: "quantity", header: "Cantidad", cell: ({ row }) => <span className="tabular-nums">{row.original.quantity.toFixed(2)}</span> },
  { accessorKey: "total_value", header: "Valor", cell: ({ row }) => formatCurrency(row.original.total_value) },
  { accessorKey: "status", header: "Estado", cell: ({ row }) => <StatusBadge status={row.original.status} /> },
];

export default function AdjustmentsPage() {
  const navigate = useNavigate();
  const [page, setPage] = useState(0);
  const [statusFilter, setStatusFilter] = useState("all");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");

  const { data, isLoading } = useAdjustments({
    skip: page * PAGE_SIZE,
    limit: PAGE_SIZE,
    status: statusFilter === "all" ? undefined : statusFilter,
    date_from: dateFrom || undefined,
    date_to: dateTo || undefined,
  });

  const pageCount = data ? Math.ceil(data.total / PAGE_SIZE) : 1;

  return (
    <div className="space-y-4">
      <PageHeader title="Ajustes de Inventario" description="Ajustes manuales de stock">
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => navigate(ROUTES.INVENTORY)}>
            <ArrowLeft className="h-4 w-4 mr-2" />Stock
          </Button>
          <Button onClick={() => navigate(ROUTES.INVENTORY_ADJUSTMENTS_NEW)} className="bg-green-600 hover:bg-green-700">
            <Plus className="h-4 w-4 mr-2" />Nuevo Ajuste
          </Button>
        </div>
      </PageHeader>

      <div className="flex flex-col sm:flex-row items-start sm:items-center gap-4">
        <Tabs value={statusFilter} onValueChange={(v) => { setStatusFilter(v); setPage(0); }}>
          <TabsList>
            <TabsTrigger value="all">Todos</TabsTrigger>
            <TabsTrigger value="completed">Completados</TabsTrigger>
            <TabsTrigger value="annulled">Anulados</TabsTrigger>
          </TabsList>
        </Tabs>
        <div className="ml-auto">
          <DateRangePicker dateFrom={dateFrom} dateTo={dateTo} onDateFromChange={setDateFrom} onDateToChange={setDateTo} />
        </div>
      </div>

      <DataTable
        columns={columns}
        data={data?.items ?? []}
        loading={isLoading}
        pageCount={pageCount}
        pageIndex={page}
        pageSize={PAGE_SIZE}
        onPageChange={setPage}
        onRowClick={(row) => navigate(`/inventory/adjustments/${row.id}`)}
        emptyTitle="Sin ajustes"
        emptyDescription="No se encontraron ajustes de inventario."
      />
    </div>
  );
}
