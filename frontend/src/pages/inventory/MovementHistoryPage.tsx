import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { type ColumnDef } from "@tanstack/react-table";
import { ArrowLeft } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { PageHeader } from "@/components/shared/PageHeader";
import { DataTable } from "@/components/shared/DataTable";
import { DateRangePicker } from "@/components/shared/DateRangePicker";
import { useInventoryMovements } from "@/hooks/useInventory";
import { formatCurrency, formatDate } from "@/utils/formatters";
import { ROUTES } from "@/utils/constants";
import type { MovementItem } from "@/types/inventory";

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
  sale: "bg-green-100 text-green-800",
  adjustment: "bg-yellow-100 text-yellow-800",
  transfer: "bg-purple-100 text-purple-800",
  purchase_reversal: "bg-red-100 text-red-800",
  sale_reversal: "bg-red-100 text-red-800",
  transformation: "bg-orange-100 text-orange-800",
};

const columns: ColumnDef<MovementItem, unknown>[] = [
  { accessorKey: "date", header: "Fecha", cell: ({ row }) => formatDate(row.original.date) },
  { accessorKey: "movement_type", header: "Tipo", cell: ({ row }) => <Badge variant="outline" className={typeColors[row.original.movement_type] ?? ""}>{typeLabels[row.original.movement_type] ?? row.original.movement_type}</Badge> },
  { accessorKey: "material_code", header: "Codigo", cell: ({ row }) => <span className="font-medium">{row.original.material_code}</span> },
  { accessorKey: "material_name", header: "Material" },
  { accessorKey: "warehouse_name", header: "Bodega" },
  { accessorKey: "quantity", header: "Cantidad", cell: ({ row }) => <span className={`font-medium tabular-nums ${row.original.quantity >= 0 ? "text-green-700" : "text-red-700"}`}>{row.original.quantity >= 0 ? "+" : ""}{row.original.quantity.toFixed(2)}</span> },
  { accessorKey: "unit_cost", header: "Costo Unit.", cell: ({ row }) => formatCurrency(row.original.unit_cost) },
  { accessorKey: "notes", header: "Notas", cell: ({ row }) => <span className="text-sm text-gray-500 truncate max-w-[200px] block">{row.original.notes ?? "-"}</span> },
];

export default function MovementHistoryPage() {
  const navigate = useNavigate();
  const [page, setPage] = useState(0);
  const [typeFilter, setTypeFilter] = useState("all");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");

  const { data, isLoading } = useInventoryMovements({
    skip: page * PAGE_SIZE,
    limit: PAGE_SIZE,
    movement_type: typeFilter === "all" ? undefined : typeFilter,
    date_from: dateFrom || undefined,
    date_to: dateTo || undefined,
  });

  const pageCount = data ? Math.ceil(data.total / PAGE_SIZE) : 1;

  return (
    <div className="space-y-4">
      <PageHeader title="Movimientos de Inventario" description="Historial completo de entradas y salidas">
        <Button variant="outline" onClick={() => navigate(ROUTES.INVENTORY)}>
          <ArrowLeft className="h-4 w-4 mr-2" />Volver a Stock
        </Button>
      </PageHeader>

      <div className="flex flex-col sm:flex-row items-start sm:items-center gap-4">
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
        emptyTitle="Sin movimientos"
        emptyDescription="No se encontraron movimientos de inventario."
      />
    </div>
  );
}
