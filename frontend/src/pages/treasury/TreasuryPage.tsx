import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { type ColumnDef } from "@tanstack/react-table";
import { Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { PageHeader } from "@/components/shared/PageHeader";
import { DataTable } from "@/components/shared/DataTable";
import { DateRangePicker } from "@/components/shared/DateRangePicker";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { useMoneyMovements } from "@/hooks/useMoneyMovements";
import { formatCurrency, formatDate } from "@/utils/formatters";
import { ROUTES } from "@/utils/constants";
import type { MoneyMovementResponse, MoneyMovementType } from "@/types/money-movement";

const PAGE_SIZE = 20;

const typeLabels: Record<MoneyMovementType, string> = {
  payment_to_supplier: "Pago Proveedor",
  collection_from_client: "Cobro Cliente",
  expense: "Gasto",
  service_income: "Ingreso Servicio",
  transfer_out: "Transferencia Salida",
  transfer_in: "Transferencia Entrada",
  capital_injection: "Aporte Capital",
  capital_return: "Devolucion Capital",
  commission_payment: "Pago Comision",
};

const typeColors: Record<string, string> = {
  payment_to_supplier: "bg-red-100 text-red-800",
  collection_from_client: "bg-green-100 text-green-800",
  expense: "bg-orange-100 text-orange-800",
  service_income: "bg-blue-100 text-blue-800",
  transfer_out: "bg-purple-100 text-purple-800",
  transfer_in: "bg-purple-100 text-purple-800",
  capital_injection: "bg-teal-100 text-teal-800",
  capital_return: "bg-yellow-100 text-yellow-800",
  commission_payment: "bg-pink-100 text-pink-800",
};

const columns: ColumnDef<MoneyMovementResponse, unknown>[] = [
  { accessorKey: "movement_number", header: "#", cell: ({ row }) => <span className="font-medium">#{row.original.movement_number}</span> },
  { accessorKey: "date", header: "Fecha", cell: ({ row }) => formatDate(row.original.date) },
  { accessorKey: "movement_type", header: "Tipo", cell: ({ row }) => <Badge variant="outline" className={typeColors[row.original.movement_type] ?? ""}>{typeLabels[row.original.movement_type] ?? row.original.movement_type}</Badge> },
  { accessorKey: "description", header: "Descripcion" },
  { accessorKey: "amount", header: "Monto", cell: ({ row }) => <span className="font-medium tabular-nums">{formatCurrency(row.original.amount)}</span> },
  { accessorKey: "account_name", header: "Cuenta" },
  { accessorKey: "third_party_name", header: "Tercero", cell: ({ row }) => row.original.third_party_name ?? "-" },
  { accessorKey: "status", header: "Estado", cell: ({ row }) => <StatusBadge status={row.original.status} /> },
];

export default function TreasuryPage() {
  const navigate = useNavigate();
  const [page, setPage] = useState(0);
  const [typeFilter, setTypeFilter] = useState<string>("all");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");

  const { data, isLoading } = useMoneyMovements({
    skip: page * PAGE_SIZE,
    limit: PAGE_SIZE,
    movement_type: typeFilter === "all" ? undefined : typeFilter,
    date_from: dateFrom || undefined,
    date_to: dateTo || undefined,
  });

  const pageCount = data ? Math.ceil(data.total / PAGE_SIZE) : 1;

  return (
    <div className="space-y-4">
      <PageHeader title="Tesoreria" description="Movimientos de dinero">
        <Button onClick={() => navigate(ROUTES.TREASURY_NEW)} className="bg-green-600 hover:bg-green-700">
          <Plus className="h-4 w-4 mr-2" />Nuevo Movimiento
        </Button>
      </PageHeader>

      <div className="flex flex-col sm:flex-row items-start sm:items-center gap-4">
        <Tabs value={typeFilter} onValueChange={(v) => { setTypeFilter(v); setPage(0); }}>
          <TabsList className="flex-wrap h-auto">
            <TabsTrigger value="all">Todos</TabsTrigger>
            <TabsTrigger value="payment_to_supplier">Pagos</TabsTrigger>
            <TabsTrigger value="collection_from_client">Cobros</TabsTrigger>
            <TabsTrigger value="expense">Gastos</TabsTrigger>
            <TabsTrigger value="transfer_out">Transf.</TabsTrigger>
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
        onRowClick={(row) => navigate(`/treasury/${row.id}`)}
        emptyTitle="Sin movimientos"
        emptyDescription="No se encontraron movimientos de tesoreria."
      />
    </div>
  );
}
