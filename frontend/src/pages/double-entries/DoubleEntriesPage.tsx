import { useState, useMemo } from "react";
import { useDateFilter } from "@/stores/dateFilterStore";
import { useNavigate } from "react-router-dom";
import { type ColumnDef } from "@tanstack/react-table";
import { Plus, TrendingUp, Hash, Percent } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { PageHeader } from "@/components/shared/PageHeader";
import { DataTable } from "@/components/shared/DataTable";
import { SearchInput } from "@/components/shared/SearchInput";
import { DateRangePicker } from "@/components/shared/DateRangePicker";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { KpiCard } from "@/components/shared/KpiCard";
import { useDoubleEntries } from "@/hooks/useDoubleEntries";
import { formatCurrency, formatDate, formatWeight, formatPercentage } from "@/utils/formatters";
import { ROUTES } from "@/utils/constants";
import type { DoubleEntryResponse } from "@/types/double-entry";
import type { MetricCard } from "@/types/reports";

const PAGE_SIZE = 20;

const columns: ColumnDef<DoubleEntryResponse, unknown>[] = [
  { accessorKey: "double_entry_number", header: "#", cell: ({ row }) => <span className="font-medium">#{row.original.double_entry_number}</span> },
  { accessorKey: "date", header: "Fecha", enableSorting: true, cell: ({ row }) => formatDate(row.original.date) },
  { accessorKey: "material_name", header: "Material", cell: ({ row }) => <><span className="font-medium">{row.original.material_name}</span><span className="text-slate-400 ml-2 text-xs">{formatWeight(row.original.quantity)}</span></> },
  { accessorKey: "supplier_name", header: "Proveedor" },
  { accessorKey: "customer_name", header: "Cliente" },
  { accessorKey: "profit", header: "Utilidad", enableSorting: true, cell: ({ row }) => <span className={`font-medium tabular-nums ${row.original.profit >= 0 ? "text-emerald-700" : "text-red-700"}`}>{formatCurrency(row.original.profit)}</span> },
  { accessorKey: "profit_margin", header: "Margen", enableSorting: true, cell: ({ row }) => formatPercentage(row.original.profit_margin) },
  { accessorKey: "status", header: "Estado", cell: ({ row }) => <StatusBadge status={row.original.status} /> },
];

export default function DoubleEntriesPage() {
  const navigate = useNavigate();
  const [page, setPage] = useState(0);
  const [search, setSearch] = useState("");
  const { dateFrom, dateTo, setDateFrom, setDateTo } = useDateFilter();

  const { data, isLoading } = useDoubleEntries({
    skip: page * PAGE_SIZE,
    limit: PAGE_SIZE,
    search: search || undefined,
    date_from: dateFrom || undefined,
    date_to: dateTo || undefined,
  });

  const pageCount = data ? Math.ceil(data.total / PAGE_SIZE) : 1;

  const kpis = useMemo(() => {
    const items = data?.items ?? [];
    const totalProfit = items.reduce((sum, d) => sum + d.profit, 0);
    const count = data?.total ?? 0;
    const avgMargin = items.length > 0
      ? items.reduce((sum, d) => sum + d.profit_margin, 0) / items.length
      : 0;
    return {
      profit: { current_value: totalProfit, previous_value: 0, change_percentage: null } as MetricCard,
      count: { current_value: count, previous_value: 0, change_percentage: null } as MetricCard,
      margin: { current_value: avgMargin, previous_value: 0, change_percentage: null } as MetricCard,
    };
  }, [data]);

  return (
    <div className="space-y-4">
      <PageHeader title="Doble Partida" description="Operaciones Pasa Mano (compra+venta simultanea)">
        <Button onClick={() => navigate(ROUTES.DOUBLE_ENTRIES_NEW)} className="bg-emerald-600 hover:bg-emerald-700">
          <Plus className="h-4 w-4 mr-2" />Nueva Doble Partida
        </Button>
      </PageHeader>

      {/* KPI Cards */}
      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-28 rounded-lg" />
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <KpiCard
            label="Utilidad Total"
            metric={kpis.profit}
            icon={<TrendingUp className="h-4 w-4" />}
            accentColor="emerald"
          />
          <KpiCard
            label="Operaciones"
            metric={kpis.count}
            icon={<Hash className="h-4 w-4" />}
            accentColor="sky"
            formatValue={(n) => String(n)}
          />
          <KpiCard
            label="Margen Promedio"
            metric={kpis.margin}
            icon={<Percent className="h-4 w-4" />}
            accentColor="violet"
            formatValue={formatPercentage}
          />
        </div>
      )}

      <DataTable
        columns={columns}
        data={data?.items ?? []}
        loading={isLoading}
        pageCount={pageCount}
        pageIndex={page}
        pageSize={PAGE_SIZE}
        totalItems={data?.total}
        onPageChange={setPage}
        onRowClick={(row) => navigate(`/double-entries/${row.id}`)}
        emptyTitle="Sin doble partidas"
        emptyDescription="No se encontraron operaciones pasa mano."
        exportFilename="ecobalance_doble-partidas"
        toolbar={
          <div className="flex items-center gap-3">
            <SearchInput value={search} onChange={(v) => { setSearch(v); setPage(0); }} placeholder="Buscar..." />
            <DateRangePicker dateFrom={dateFrom} dateTo={dateTo} onDateFromChange={setDateFrom} onDateToChange={setDateTo} />
          </div>
        }
      />
    </div>
  );
}
