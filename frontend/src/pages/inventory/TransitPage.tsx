import { useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { type ColumnDef } from "@tanstack/react-table";
import { ArrowLeft, Truck, ShoppingCart, DollarSign, AlertTriangle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { PageHeader } from "@/components/shared/PageHeader";
import { DataTable } from "@/components/shared/DataTable";
import { KpiCard } from "@/components/shared/KpiCard";
import { useTransitStock } from "@/hooks/useInventory";
import { formatDate } from "@/utils/formatters";
import { ROUTES } from "@/utils/constants";
import type { TransitPurchaseItem, TransitSaleItem } from "@/types/inventory";
import type { MetricCard } from "@/types/reports";

const purchaseColumns: ColumnDef<TransitPurchaseItem, unknown>[] = [
  { accessorKey: "purchase_number", header: "#", cell: ({ row }) => <span className="font-medium">{row.original.purchase_number}</span> },
  { accessorKey: "date", header: "Fecha", cell: ({ row }) => formatDate(row.original.date) },
  { accessorKey: "supplier_name", header: "Proveedor" },
  { accessorKey: "material_code", header: "Codigo", cell: ({ row }) => <span className="font-medium">{row.original.material_code}</span> },
  { accessorKey: "material_name", header: "Material" },
  { accessorKey: "quantity", header: "Cantidad", cell: ({ row }) => <span className="tabular-nums font-medium">{row.original.quantity.toFixed(2)}</span> },
];

const saleColumns: ColumnDef<TransitSaleItem, unknown>[] = [
  { accessorKey: "sale_number", header: "#", cell: ({ row }) => <span className="font-medium">{row.original.sale_number}</span> },
  { accessorKey: "date", header: "Fecha", cell: ({ row }) => formatDate(row.original.date) },
  { accessorKey: "customer_name", header: "Cliente" },
  { accessorKey: "material_code", header: "Codigo", cell: ({ row }) => <span className="font-medium">{row.original.material_code}</span> },
  { accessorKey: "material_name", header: "Material" },
  { accessorKey: "quantity", header: "Cantidad", cell: ({ row }) => <span className="tabular-nums font-medium">{row.original.quantity.toFixed(2)}</span> },
];

export default function TransitPage() {
  const navigate = useNavigate();
  const { data, isLoading } = useTransitStock();

  const kpis = useMemo(() => ({
    transit: { current_value: data?.total_transit_kg ?? 0, previous_value: 0, change_percentage: null } as MetricCard,
    purchases: { current_value: data?.total_pending_purchases ?? 0, previous_value: 0, change_percentage: null } as MetricCard,
    sales: { current_value: data?.total_pending_sales ?? 0, previous_value: 0, change_percentage: null } as MetricCard,
  }), [data]);

  return (
    <div className="space-y-4">
      <PageHeader title="Inventario en Transito" description="Compras y ventas pendientes de liquidar">
        <Button variant="outline" onClick={() => navigate(ROUTES.INVENTORY)}>
          <ArrowLeft className="h-4 w-4 mr-2" />Volver a Stock
        </Button>
      </PageHeader>

      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-28 rounded-lg" />
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <KpiCard label="Stock en Transito" metric={kpis.transit} icon={<Truck className="h-4 w-4" />} accentColor="amber" formatValue={(n) => n.toFixed(2) + " kg"} />
          <KpiCard label="Compras Pendientes" metric={kpis.purchases} icon={<ShoppingCart className="h-4 w-4" />} accentColor="blue" formatValue={(n) => String(n)} />
          <KpiCard label="Ventas Pendientes" metric={kpis.sales} icon={<DollarSign className="h-4 w-4" />} accentColor="emerald" formatValue={(n) => String(n)} />
        </div>
      )}

      {/* Alertas de cuello de botella */}
      {data?.bottleneck_alerts && data.bottleneck_alerts.length > 0 && (
        <Card className="border-amber-200 bg-amber-50">
          <CardHeader className="py-3">
            <CardTitle className="text-sm font-semibold text-amber-800 flex items-center gap-2">
              <AlertTriangle className="h-4 w-4" />
              Alertas de Cuello de Botella
            </CardTitle>
          </CardHeader>
          <CardContent className="py-2">
            <div className="space-y-1">
              {data.bottleneck_alerts.map((alert) => (
                <div key={alert.material_code} className="flex justify-between text-sm py-1 border-b border-amber-200 last:border-0">
                  <span className="font-medium text-amber-900">{alert.material_code} - {alert.material_name}</span>
                  <span className="text-amber-700">
                    {alert.stock_transit.toFixed(0)} kg en transito ({(alert.ratio * 100).toFixed(0)}% del liquidado)
                  </span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Compras pendientes */}
      <Card>
        <CardHeader className="py-3">
          <CardTitle className="text-sm font-semibold uppercase tracking-wider text-slate-500">
            Compras Pendientes
          </CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          <DataTable
            columns={purchaseColumns}
            data={data?.pending_purchases ?? []}
            loading={isLoading}
            pageCount={1}
            pageIndex={0}
            pageSize={200}
            onPageChange={() => {}}
            onRowClick={(row) => navigate(`/purchases/${row.purchase_id}`)}
            emptyTitle="Sin compras pendientes"
            emptyDescription="No hay compras en estado registrado."
          />
        </CardContent>
      </Card>

      {/* Ventas pendientes */}
      <Card>
        <CardHeader className="py-3">
          <CardTitle className="text-sm font-semibold uppercase tracking-wider text-slate-500">
            Ventas Pendientes
          </CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          <DataTable
            columns={saleColumns}
            data={data?.pending_sales ?? []}
            loading={isLoading}
            pageCount={1}
            pageIndex={0}
            pageSize={200}
            onPageChange={() => {}}
            onRowClick={(row) => navigate(`/sales/${row.sale_id}`)}
            emptyTitle="Sin ventas pendientes"
            emptyDescription="No hay ventas en estado registrado."
          />
        </CardContent>
      </Card>
    </div>
  );
}
