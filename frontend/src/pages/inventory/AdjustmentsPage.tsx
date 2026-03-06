import { useState, useMemo } from "react";
import { useDateFilter } from "@/stores/dateFilterStore";
import { useNavigate } from "react-router-dom";
import { type ColumnDef } from "@tanstack/react-table";
import { Plus, ArrowLeft, Calculator, Hash, ClipboardCheck } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Skeleton } from "@/components/ui/skeleton";
import { PageHeader } from "@/components/shared/PageHeader";
import { DataTable } from "@/components/shared/DataTable";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { DateRangePicker } from "@/components/shared/DateRangePicker";
import { SearchInput } from "@/components/shared/SearchInput";
import { KpiCard } from "@/components/shared/KpiCard";
import { useAdjustments } from "@/hooks/useInventory";
import { formatCurrency, formatDate } from "@/utils/formatters";
import { ROUTES } from "@/utils/constants";
import type { InventoryAdjustmentResponse } from "@/types/inventory";
import type { MetricCard } from "@/types/reports";

const PAGE_SIZE = 20;

const typeLabels: Record<string, string> = {
  increase: "Aumento",
  decrease: "Disminucion",
  recount: "Conteo",
  zero_out: "Llevar a Cero",
};

const typeColors: Record<string, string> = {
  increase: "bg-emerald-100 text-emerald-800",
  decrease: "bg-red-100 text-red-800",
  recount: "bg-blue-100 text-blue-800",
  zero_out: "bg-orange-100 text-orange-800",
};

const columns: ColumnDef<InventoryAdjustmentResponse, unknown>[] = [
  { accessorKey: "adjustment_number", header: "#", cell: ({ row }) => <span className="font-medium">#{row.original.adjustment_number}</span> },
  { accessorKey: "date", header: "Fecha", enableSorting: true, cell: ({ row }) => formatDate(row.original.date) },
  { accessorKey: "adjustment_type", header: "Tipo", cell: ({ row }) => <Badge variant="outline" className={typeColors[row.original.adjustment_type] ?? ""}>{typeLabels[row.original.adjustment_type] ?? row.original.adjustment_type}</Badge> },
  { accessorKey: "material_name", header: "Material", cell: ({ row }) => `${row.original.material_code ?? ""} - ${row.original.material_name ?? ""}` },
  { accessorKey: "warehouse_name", header: "Bodega" },
  { accessorKey: "quantity", header: "Cantidad", enableSorting: true, cell: ({ row }) => <span className="tabular-nums">{row.original.quantity.toFixed(2)}</span> },
  { accessorKey: "total_value", header: "Valor", enableSorting: true, cell: ({ row }) => formatCurrency(row.original.total_value) },
  { accessorKey: "status", header: "Estado", cell: ({ row }) => <StatusBadge status={row.original.status} /> },
];

export default function AdjustmentsPage() {
  const navigate = useNavigate();
  const [page, setPage] = useState(0);
  const [statusFilter, setStatusFilter] = useState("all");
  const [search, setSearch] = useState("");
  const { dateFrom, dateTo, setDateFrom, setDateTo } = useDateFilter();

  const { data, isLoading } = useAdjustments({
    skip: page * PAGE_SIZE,
    limit: PAGE_SIZE,
    status: statusFilter === "all" ? undefined : statusFilter,
    date_from: dateFrom || undefined,
    date_to: dateTo || undefined,
  });

  const pageCount = data ? Math.ceil(data.total / PAGE_SIZE) : 1;

  const kpis = useMemo(() => {
    const items = data?.items ?? [];
    const totalValue = items.reduce((sum, a) => sum + a.total_value, 0);
    const count = data?.total ?? 0;
    const completed = items.filter(a => a.status === "completed").length;
    return {
      total: { current_value: totalValue, previous_value: 0, change_percentage: null } as MetricCard,
      count: { current_value: count, previous_value: 0, change_percentage: null } as MetricCard,
      completed: { current_value: completed, previous_value: 0, change_percentage: null } as MetricCard,
    };
  }, [data]);

  return (
    <div className="space-y-4">
      <PageHeader title="Ajustes de Inventario" description="Ajustes manuales de stock">
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => navigate(ROUTES.INVENTORY)}>
            <ArrowLeft className="h-4 w-4 mr-2" />Stock
          </Button>
          <Button onClick={() => navigate(ROUTES.INVENTORY_ADJUSTMENTS_NEW)} className="bg-emerald-600 hover:bg-emerald-700">
            <Plus className="h-4 w-4 mr-2" />Nuevo Ajuste
          </Button>
        </div>
      </PageHeader>

      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-[120px] rounded-lg" />
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <KpiCard
            label="Valor Ajustes"
            metric={kpis.total}
            icon={<Calculator className="h-4 w-4" />}
            accentColor="sky"
          />
          <KpiCard
            label="Ajustes"
            metric={kpis.count}
            icon={<Hash className="h-4 w-4" />}
            accentColor="violet"
            formatValue={(n) => String(n)}
          />
          <KpiCard
            label="Completados"
            metric={kpis.completed}
            icon={<ClipboardCheck className="h-4 w-4" />}
            accentColor="emerald"
            formatValue={(n) => String(n)}
          />
        </div>
      )}

      <Tabs value={statusFilter} onValueChange={(v) => { setStatusFilter(v); setPage(0); }}>
        <TabsList>
          <TabsTrigger value="all">Todos</TabsTrigger>
          <TabsTrigger value="completed">Completados</TabsTrigger>
          <TabsTrigger value="annulled">Anulados</TabsTrigger>
        </TabsList>
      </Tabs>

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
        exportFilename="ecobalance_ajustes-inventario"
        totalItems={data?.total}
        toolbar={
          <div className="flex items-center gap-3">
            <SearchInput value={search} onChange={(v) => { setSearch(v); setPage(0); }} placeholder="Buscar ajuste..." />
            <DateRangePicker dateFrom={dateFrom} dateTo={dateTo} onDateFromChange={setDateFrom} onDateToChange={setDateTo} />
          </div>
        }
      />
    </div>
  );
}
