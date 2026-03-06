import { useState, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { type ColumnDef } from "@tanstack/react-table";
import { Package, DollarSign, Layers } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { PageHeader } from "@/components/shared/PageHeader";
import { DataTable } from "@/components/shared/DataTable";
import { SearchInput } from "@/components/shared/SearchInput";
import { KpiCard } from "@/components/shared/KpiCard";
import { useStock, useStockDetail } from "@/hooks/useInventory";
import { formatCurrency } from "@/utils/formatters";
import type { StockItem, WarehouseStockDetail } from "@/types/inventory";
import type { MetricCard } from "@/types/reports";

const columns: ColumnDef<StockItem, unknown>[] = [
  { accessorKey: "material_code", header: "Codigo", cell: ({ row }) => <span className="font-medium">{row.original.material_code}</span> },
  { accessorKey: "material_name", header: "Material" },
  { accessorKey: "default_unit", header: "Unidad" },
  { accessorKey: "current_stock_liquidated", header: "Stock Liq.", cell: ({ row }) => <span className="tabular-nums">{row.original.current_stock_liquidated.toFixed(2)}</span> },
  { accessorKey: "current_stock_transit", header: "Stock Trans.", cell: ({ row }) => row.original.current_stock_transit > 0 ? <Badge variant="outline" className="bg-yellow-50 text-yellow-700">{row.original.current_stock_transit.toFixed(2)}</Badge> : <span className="text-slate-400">0</span> },
  { accessorKey: "current_stock_total", header: "Total", enableSorting: true, cell: ({ row }) => <span className="font-medium tabular-nums">{row.original.current_stock_total.toFixed(2)}</span> },
  { accessorKey: "current_average_cost", header: "Costo Prom.", enableSorting: true, cell: ({ row }) => formatCurrency(row.original.current_average_cost) },
  { accessorKey: "total_value", header: "Valor Total", enableSorting: true, cell: ({ row }) => <span className="font-medium">{formatCurrency(row.original.total_value)}</span> },
];

function WarehouseBreakdown({ materialId, onClose }: { materialId: string; onClose: () => void }) {
  const { data, isLoading } = useStockDetail(materialId);

  if (isLoading) return <div className="p-4 text-sm text-slate-500">Cargando desglose...</div>;
  if (!data) return null;

  return (
    <Card className="mt-2 shadow-sm">
      <CardHeader className="py-3 flex flex-row items-center justify-between">
        <CardTitle className="text-sm font-semibold uppercase tracking-wider text-slate-500">{data.material_code} - {data.material_name} — Desglose por Bodega</CardTitle>
        <Button variant="ghost" size="sm" onClick={onClose}>Cerrar</Button>
      </CardHeader>
      <CardContent className="py-2">
        {data.warehouses.length === 0 ? (
          <p className="text-sm text-slate-500">Sin movimientos en bodegas</p>
        ) : (
          <div className="space-y-1">
            {data.warehouses.map((w: WarehouseStockDetail) => (
              <div key={w.warehouse_id} className="flex justify-between text-sm py-1 border-b last:border-0">
                <span>{w.warehouse_name}</span>
                <span className="font-medium tabular-nums">{w.stock.toFixed(2)} {data.default_unit}</span>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

export default function StockPage() {
  const navigate = useNavigate();
  const { data, isLoading } = useStock();
  const [expandedMaterial, setExpandedMaterial] = useState<string | null>(null);
  const [search, setSearch] = useState("");

  const filteredItems = useMemo(() => {
    if (!search || !data?.items) return data?.items ?? [];
    const s = search.toLowerCase();
    return data.items.filter(i => i.material_name.toLowerCase().includes(s) || i.material_code.toLowerCase().includes(s));
  }, [data, search]);

  const kpis = useMemo(() => {
    const items = data?.items ?? [];
    const count = items.length;
    const totalValue = data?.total_valuation ?? 0;
    const transitStock = items.reduce((sum, i) => sum + i.current_stock_transit, 0);
    return {
      count: { current_value: count, previous_value: 0, change_percentage: null } as MetricCard,
      value: { current_value: totalValue, previous_value: 0, change_percentage: null } as MetricCard,
      transit: { current_value: transitStock, previous_value: 0, change_percentage: null } as MetricCard,
    };
  }, [data]);

  return (
    <div className="space-y-4">
      <PageHeader title="Inventario" description="Vista consolidada de stock">
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => navigate("/inventory/movements")}>Movimientos</Button>
          <Button variant="outline" onClick={() => navigate("/inventory/adjustments")}>Ajustes</Button>
          <Button variant="outline" onClick={() => navigate("/inventory/transformations")}>Transformaciones</Button>
        </div>
      </PageHeader>

      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-28 rounded-lg" />
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <KpiCard label="Materiales" metric={kpis.count} icon={<Package className="h-4 w-4" />} accentColor="violet" formatValue={(n) => String(n)} />
          <KpiCard label="Valor Inventario" metric={kpis.value} icon={<DollarSign className="h-4 w-4" />} accentColor="emerald" />
          <KpiCard label="Stock en Transito" metric={kpis.transit} icon={<Layers className="h-4 w-4" />} accentColor="amber" formatValue={(n) => n.toFixed(2) + " kg"} />
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
        onRowClick={(row) => {
          setExpandedMaterial(expandedMaterial === row.material_id ? null : row.material_id);
        }}
        emptyTitle="Sin materiales"
        emptyDescription="No hay materiales con stock."
        exportFilename="ecobalance_inventario-stock"
        toolbar={<SearchInput value={search} onChange={setSearch} placeholder="Buscar material..." />}
      />

      {expandedMaterial && (
        <WarehouseBreakdown materialId={expandedMaterial} onClose={() => setExpandedMaterial(null)} />
      )}
    </div>
  );
}
