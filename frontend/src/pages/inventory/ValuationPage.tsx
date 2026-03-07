import { useState, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { type ColumnDef } from "@tanstack/react-table";
import { ArrowLeft, DollarSign, Package } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { PageHeader } from "@/components/shared/PageHeader";
import { DataTable } from "@/components/shared/DataTable";
import { SearchInput } from "@/components/shared/SearchInput";
import { KpiCard } from "@/components/shared/KpiCard";
import { useValuation } from "@/hooks/useInventory";
import { formatCurrency } from "@/utils/formatters";
import { ROUTES } from "@/utils/constants";
import type { ValuationItem } from "@/types/inventory";
import type { MetricCard } from "@/types/reports";

const columns: ColumnDef<ValuationItem, unknown>[] = [
  { accessorKey: "material_code", header: "Codigo", cell: ({ row }) => <span className="font-medium">{row.original.material_code}</span> },
  { accessorKey: "material_name", header: "Material" },
  { accessorKey: "default_unit", header: "Unidad" },
  { accessorKey: "current_stock_liquidated", header: "Stock Liquidado", cell: ({ row }) => <span className="tabular-nums">{row.original.current_stock_liquidated.toFixed(2)}</span> },
  { accessorKey: "current_average_cost", header: "Costo Promedio", cell: ({ row }) => formatCurrency(row.original.current_average_cost) },
  { accessorKey: "total_value", header: "Valor Total", enableSorting: true, cell: ({ row }) => <span className="font-medium">{formatCurrency(row.original.total_value)}</span> },
];

export default function ValuationPage() {
  const navigate = useNavigate();
  const { data, isLoading } = useValuation();
  const [search, setSearch] = useState("");

  const filteredItems = useMemo(() => {
    if (!search || !data?.items) return data?.items ?? [];
    const s = search.toLowerCase();
    return data.items.filter(i => i.material_name.toLowerCase().includes(s) || i.material_code.toLowerCase().includes(s));
  }, [data, search]);

  const kpis = useMemo(() => ({
    value: { current_value: data?.total_valuation ?? 0, previous_value: 0, change_percentage: null } as MetricCard,
    count: { current_value: data?.total_materials ?? 0, previous_value: 0, change_percentage: null } as MetricCard,
  }), [data]);

  return (
    <div className="space-y-4">
      <PageHeader title="Valorizacion del Inventario" description="Stock liquidado x costo promedio por material">
        <Button variant="outline" onClick={() => navigate(ROUTES.INVENTORY)}>
          <ArrowLeft className="h-4 w-4 mr-2" />Volver a Stock
        </Button>
      </PageHeader>

      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Skeleton className="h-28 rounded-lg" />
          <Skeleton className="h-28 rounded-lg" />
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <KpiCard label="Valor Total" metric={kpis.value} icon={<DollarSign className="h-4 w-4" />} accentColor="emerald" />
          <KpiCard label="Materiales" metric={kpis.count} icon={<Package className="h-4 w-4" />} accentColor="violet" formatValue={(n) => String(n)} />
        </div>
      )}

      <DataTable
        columns={columns}
        data={filteredItems}
        loading={isLoading}
        pageCount={1}
        pageIndex={0}
        pageSize={200}
        onPageChange={() => {}}
        emptyTitle="Sin materiales"
        emptyDescription="No hay materiales con stock para valorizar."
        exportFilename="ecobalance_valorizacion-inventario"
        toolbar={<SearchInput value={search} onChange={setSearch} placeholder="Buscar material..." />}
      />
    </div>
  );
}
