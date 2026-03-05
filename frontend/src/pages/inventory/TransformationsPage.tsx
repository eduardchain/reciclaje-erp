import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { type ColumnDef } from "@tanstack/react-table";
import { Plus, ArrowLeft } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { PageHeader } from "@/components/shared/PageHeader";
import { DataTable } from "@/components/shared/DataTable";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { DateRangePicker } from "@/components/shared/DateRangePicker";
import { useTransformations } from "@/hooks/useInventory";
import { formatCurrency, formatDate } from "@/utils/formatters";
import { ROUTES } from "@/utils/constants";
import type { MaterialTransformationResponse } from "@/types/inventory";

const PAGE_SIZE = 20;

const columns: ColumnDef<MaterialTransformationResponse, unknown>[] = [
  { accessorKey: "transformation_number", header: "#", cell: ({ row }) => <span className="font-medium">#{row.original.transformation_number}</span> },
  { accessorKey: "date", header: "Fecha", cell: ({ row }) => formatDate(row.original.date) },
  { accessorKey: "source_material_name", header: "Material Origen", cell: ({ row }) => `${row.original.source_material_code ?? ""} - ${row.original.source_material_name ?? ""}` },
  { accessorKey: "source_quantity", header: "Cantidad", cell: ({ row }) => <span className="tabular-nums">{row.original.source_quantity.toFixed(2)}</span> },
  { accessorKey: "waste_quantity", header: "Merma", cell: ({ row }) => <span className="tabular-nums text-orange-600">{row.original.waste_quantity.toFixed(2)}</span> },
  { accessorKey: "source_total_value", header: "Valor", cell: ({ row }) => formatCurrency(row.original.source_total_value) },
  { accessorKey: "lines", header: "Destinos", cell: ({ row }) => <span>{row.original.lines.length} material(es)</span> },
  { accessorKey: "status", header: "Estado", cell: ({ row }) => <StatusBadge status={row.original.status} /> },
];

export default function TransformationsPage() {
  const navigate = useNavigate();
  const [page, setPage] = useState(0);
  const [statusFilter, setStatusFilter] = useState("all");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");

  const { data, isLoading } = useTransformations({
    skip: page * PAGE_SIZE,
    limit: PAGE_SIZE,
    status: statusFilter === "all" ? undefined : statusFilter,
    date_from: dateFrom || undefined,
    date_to: dateTo || undefined,
  });

  const pageCount = data ? Math.ceil(data.total / PAGE_SIZE) : 1;

  return (
    <div className="space-y-4">
      <PageHeader title="Transformaciones" description="Desintegracion de materiales compuestos">
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => navigate(ROUTES.INVENTORY)}>
            <ArrowLeft className="h-4 w-4 mr-2" />Stock
          </Button>
          <Button onClick={() => navigate(ROUTES.INVENTORY_TRANSFORMATIONS_NEW)} className="bg-green-600 hover:bg-green-700">
            <Plus className="h-4 w-4 mr-2" />Nueva Transformacion
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
        onRowClick={(row) => navigate(`/inventory/transformations/${row.id}`)}
        emptyTitle="Sin transformaciones"
        emptyDescription="No se encontraron transformaciones."
      />
    </div>
  );
}
