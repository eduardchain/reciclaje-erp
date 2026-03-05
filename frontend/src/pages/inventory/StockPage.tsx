import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { type ColumnDef } from "@tanstack/react-table";
import { Package } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { PageHeader } from "@/components/shared/PageHeader";
import { DataTable } from "@/components/shared/DataTable";
import { useStock, useStockDetail } from "@/hooks/useInventory";
import { formatCurrency } from "@/utils/formatters";
import type { StockItem, WarehouseStockDetail } from "@/types/inventory";

const columns: ColumnDef<StockItem, unknown>[] = [
  { accessorKey: "material_code", header: "Codigo", cell: ({ row }) => <span className="font-medium">{row.original.material_code}</span> },
  { accessorKey: "material_name", header: "Material" },
  { accessorKey: "default_unit", header: "Unidad" },
  { accessorKey: "current_stock_liquidated", header: "Stock Liq.", cell: ({ row }) => <span className="tabular-nums">{row.original.current_stock_liquidated.toFixed(2)}</span> },
  { accessorKey: "current_stock_transit", header: "Stock Trans.", cell: ({ row }) => row.original.current_stock_transit > 0 ? <Badge variant="outline" className="bg-yellow-50 text-yellow-700">{row.original.current_stock_transit.toFixed(2)}</Badge> : <span className="text-gray-400">0</span> },
  { accessorKey: "current_stock_total", header: "Total", cell: ({ row }) => <span className="font-medium tabular-nums">{row.original.current_stock_total.toFixed(2)}</span> },
  { accessorKey: "current_average_cost", header: "Costo Prom.", cell: ({ row }) => formatCurrency(row.original.current_average_cost) },
  { accessorKey: "total_value", header: "Valor Total", cell: ({ row }) => <span className="font-medium">{formatCurrency(row.original.total_value)}</span> },
];

function WarehouseBreakdown({ materialId, onClose }: { materialId: string; onClose: () => void }) {
  const { data, isLoading } = useStockDetail(materialId);

  if (isLoading) return <div className="p-4 text-sm text-gray-500">Cargando desglose...</div>;
  if (!data) return null;

  return (
    <Card className="mt-2">
      <CardHeader className="py-3 flex flex-row items-center justify-between">
        <CardTitle className="text-sm">{data.material_code} - {data.material_name} — Desglose por Bodega</CardTitle>
        <Button variant="ghost" size="sm" onClick={onClose}>Cerrar</Button>
      </CardHeader>
      <CardContent className="py-2">
        {data.warehouses.length === 0 ? (
          <p className="text-sm text-gray-500">Sin movimientos en bodegas</p>
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

  return (
    <div className="space-y-4">
      <PageHeader title="Inventario" description="Vista consolidada de stock">
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => navigate("/inventory/movements")}>Movimientos</Button>
          <Button variant="outline" onClick={() => navigate("/inventory/adjustments")}>Ajustes</Button>
          <Button variant="outline" onClick={() => navigate("/inventory/transformations")}>Transformaciones</Button>
        </div>
      </PageHeader>

      {data && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <Card>
            <CardContent className="pt-6">
              <div className="flex items-center gap-2">
                <Package className="h-5 w-5 text-blue-600" />
                <div>
                  <p className="text-sm text-gray-500">Materiales</p>
                  <p className="text-2xl font-bold">{data.total}</p>
                </div>
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <p className="text-sm text-gray-500">Valor Total Inventario</p>
              <p className="text-2xl font-bold text-green-700">{formatCurrency(data.total_valuation)}</p>
            </CardContent>
          </Card>
        </div>
      )}

      <DataTable
        columns={columns}
        data={data?.items ?? []}
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
      />

      {expandedMaterial && (
        <WarehouseBreakdown materialId={expandedMaterial} onClose={() => setExpandedMaterial(null)} />
      )}
    </div>
  );
}
