import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { type ColumnDef } from "@tanstack/react-table";
import { Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { PageHeader } from "@/components/shared/PageHeader";
import { DataTable } from "@/components/shared/DataTable";
import { SearchInput } from "@/components/shared/SearchInput";
import { DateRangePicker } from "@/components/shared/DateRangePicker";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { useSales } from "@/hooks/useSales";
import { formatCurrency, formatDate } from "@/utils/formatters";
import { ROUTES } from "@/utils/constants";
import type { SaleResponse } from "@/types/sale";

const PAGE_SIZE = 20;

const columns: ColumnDef<SaleResponse, unknown>[] = [
  {
    accessorKey: "sale_number",
    header: "#",
    cell: ({ row }) => <span className="font-medium">#{row.original.sale_number}</span>,
  },
  {
    accessorKey: "date",
    header: "Fecha",
    cell: ({ row }) => formatDate(row.original.date),
  },
  {
    accessorKey: "customer_name",
    header: "Cliente",
  },
  {
    accessorKey: "total_amount",
    header: "Total",
    cell: ({ row }) => (
      <span className="font-medium tabular-nums">{formatCurrency(row.original.total_amount)}</span>
    ),
  },
  {
    accessorKey: "total_profit",
    header: "Utilidad",
    cell: ({ row }) => (
      <span className={`font-medium tabular-nums ${row.original.total_profit >= 0 ? "text-green-700" : "text-red-700"}`}>
        {formatCurrency(row.original.total_profit)}
      </span>
    ),
  },
  {
    accessorKey: "status",
    header: "Estado",
    cell: ({ row }) => <StatusBadge status={row.original.status} />,
  },
];

export default function SalesPage() {
  const navigate = useNavigate();
  const [page, setPage] = useState(0);
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState<string>("all");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");

  const { data, isLoading } = useSales({
    skip: page * PAGE_SIZE,
    limit: PAGE_SIZE,
    status: status === "all" ? undefined : status,
    search: search || undefined,
    date_from: dateFrom || undefined,
    date_to: dateTo || undefined,
  });

  const pageCount = data ? Math.ceil(data.total / PAGE_SIZE) : 1;

  return (
    <div className="space-y-4">
      <PageHeader title="Ventas" description="Gestion de ventas de material">
        <Button onClick={() => navigate(ROUTES.SALES_NEW)} className="bg-green-600 hover:bg-green-700">
          <Plus className="h-4 w-4 mr-2" />
          Nueva Venta
        </Button>
      </PageHeader>

      <div className="flex flex-col sm:flex-row items-start sm:items-center gap-4">
        <Tabs value={status} onValueChange={(v) => { setStatus(v); setPage(0); }}>
          <TabsList>
            <TabsTrigger value="all">Todas</TabsTrigger>
            <TabsTrigger value="registered">Registradas</TabsTrigger>
            <TabsTrigger value="paid">Cobradas</TabsTrigger>
            <TabsTrigger value="cancelled">Canceladas</TabsTrigger>
          </TabsList>
        </Tabs>

        <div className="flex items-center gap-2 ml-auto">
          <SearchInput value={search} onChange={(v) => { setSearch(v); setPage(0); }} placeholder="Buscar venta..." />
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
        onRowClick={(row) => navigate(`/sales/${row.id}`)}
        emptyTitle="Sin ventas"
        emptyDescription="No se encontraron ventas para los filtros seleccionados."
      />
    </div>
  );
}
