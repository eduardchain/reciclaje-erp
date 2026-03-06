import { useState, useMemo } from "react";
import { useDateFilter } from "@/stores/dateFilterStore";
import { useNavigate } from "react-router-dom";
import { type ColumnDef } from "@tanstack/react-table";
import { ArrowLeft, ArrowDownUp, TrendingUp, TrendingDown } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Skeleton } from "@/components/ui/skeleton";
import { PageHeader } from "@/components/shared/PageHeader";
import { DataTable } from "@/components/shared/DataTable";
import { DateRangePicker } from "@/components/shared/DateRangePicker";
import { SearchInput } from "@/components/shared/SearchInput";
import { KpiCard } from "@/components/shared/KpiCard";
import { useInventoryMovements } from "@/hooks/useInventory";
import { formatCurrency, formatDate } from "@/utils/formatters";
import { ROUTES } from "@/utils/constants";
import type { MovementItem } from "@/types/inventory";
import type { MetricCard } from "@/types/reports";

const PAGE_SIZE = 20;

const typeLabels: Record<string, string> = {
  purchase: "Compra",
  sale: "Venta",
  adjustment: "Ajuste",
  transfer: "Traslado",
  purchase_reversal: "Rev. Compra",
  sale_reversal: "Rev. Venta",
  transformation: "Transformacion",
};

const typeColors: Record<string, string> = {
  purchase: "bg-blue-100 text-blue-800",
  sale: "bg-emerald-100 text-emerald-800",
  adjustment: "bg-yellow-100 text-yellow-800",
  transfer: "bg-purple-100 text-purple-800",
  purchase_reversal: "bg-red-100 text-red-800",
  sale_reversal: "bg-red-100 text-red-800",
  transformation: "bg-orange-100 text-orange-800",
};

const columns: ColumnDef<MovementItem, unknown>[] = [
  { accessorKey: "date", header: "Fecha", enableSorting: true, cell: ({ row }) => formatDate(row.original.date) },
  { accessorKey: "movement_type", header: "Tipo", cell: ({ row }) => <Badge variant="outline" className={typeColors[row.original.movement_type] ?? ""}>{typeLabels[row.original.movement_type] ?? row.original.movement_type}</Badge> },
  { accessorKey: "material_code", header: "Codigo", cell: ({ row }) => <span className="font-medium">{row.original.material_code}</span> },
  { accessorKey: "material_name", header: "Material" },
  { accessorKey: "warehouse_name", header: "Bodega" },
  { accessorKey: "quantity", header: "Cantidad", enableSorting: true, cell: ({ row }) => <span className={`font-medium tabular-nums ${row.original.quantity >= 0 ? "text-emerald-700" : "text-red-700"}`}>{row.original.quantity >= 0 ? "+" : ""}{row.original.quantity.toFixed(2)}</span> },
  { accessorKey: "unit_cost", header: "Costo Unit.", enableSorting: true, cell: ({ row }) => formatCurrency(row.original.unit_cost) },
  { accessorKey: "notes", header: "Notas", cell: ({ row }) => <span className="text-sm text-slate-500 truncate max-w-[200px] block">{row.original.notes ?? "-"}</span> },
];

export default function MovementHistoryPage() {
  const navigate = useNavigate();
  const [page, setPage] = useState(0);
  const [typeFilter, setTypeFilter] = useState("all");
  const [search, setSearch] = useState("");
  const { dateFrom, dateTo, setDateFrom, setDateTo } = useDateFilter();

  const { data, isLoading } = useInventoryMovements({
    skip: page * PAGE_SIZE,
    limit: PAGE_SIZE,
    movement_type: typeFilter === "all" ? undefined : typeFilter,
    date_from: dateFrom || undefined,
    date_to: dateTo || undefined,
  });

  const pageCount = data ? Math.ceil(data.total / PAGE_SIZE) : 1;

  const kpis = useMemo(() => {
    const items = data?.items ?? [];
    const count = data?.total ?? 0;
    const entries = items.filter(m => m.quantity > 0).length;
    const exits = items.filter(m => m.quantity < 0).length;
    return {
      total: { current_value: count, previous_value: 0, change_percentage: null } as MetricCard,
      entries: { current_value: entries, previous_value: 0, change_percentage: null } as MetricCard,
      exits: { current_value: exits, previous_value: 0, change_percentage: null } as MetricCard,
    };
  }, [data]);

  return (
    <div className="space-y-4">
      <PageHeader title="Movimientos de Inventario" description="Historial completo de entradas y salidas">
        <Button variant="outline" onClick={() => navigate(ROUTES.INVENTORY)}>
          <ArrowLeft className="h-4 w-4 mr-2" />Volver a Stock
        </Button>
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
            label="Movimientos"
            metric={kpis.total}
            icon={<ArrowDownUp className="h-4 w-4" />}
            accentColor="sky"
            formatValue={(n) => String(n)}
          />
          <KpiCard
            label="Entradas"
            metric={kpis.entries}
            icon={<TrendingUp className="h-4 w-4" />}
            accentColor="emerald"
            formatValue={(n) => String(n)}
          />
          <KpiCard
            label="Salidas"
            metric={kpis.exits}
            icon={<TrendingDown className="h-4 w-4" />}
            accentColor="rose"
            formatValue={(n) => String(n)}
          />
        </div>
      )}

      <Tabs value={typeFilter} onValueChange={(v) => { setTypeFilter(v); setPage(0); }}>
        <TabsList className="flex-wrap h-auto">
          <TabsTrigger value="all">Todos</TabsTrigger>
          <TabsTrigger value="purchase">Compras</TabsTrigger>
          <TabsTrigger value="sale">Ventas</TabsTrigger>
          <TabsTrigger value="adjustment">Ajustes</TabsTrigger>
          <TabsTrigger value="transfer">Traslados</TabsTrigger>
          <TabsTrigger value="transformation">Transf.</TabsTrigger>
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
        emptyTitle="Sin movimientos"
        emptyDescription="No se encontraron movimientos de inventario."
        exportFilename="ecobalance_movimientos-inventario"
        totalItems={data?.total}
        toolbar={
          <div className="flex items-center gap-3">
            <SearchInput value={search} onChange={(v) => { setSearch(v); setPage(0); }} placeholder="Buscar movimiento..." />
            <DateRangePicker dateFrom={dateFrom} dateTo={dateTo} onDateFromChange={setDateFrom} onDateToChange={setDateTo} />
          </div>
        }
      />
    </div>
  );
}
