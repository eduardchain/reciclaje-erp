import { useState, useMemo } from "react";
import { useDateFilter } from "@/stores/dateFilterStore";
import { useNavigate } from "react-router-dom";
import { type ColumnDef } from "@tanstack/react-table";
import { Plus, Wallet, Hash, Paperclip } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { PageHeader } from "@/components/shared/PageHeader";
import { DataTable } from "@/components/shared/DataTable";
import { DateRangePicker } from "@/components/shared/DateRangePicker";
import { SearchInput } from "@/components/shared/SearchInput";
import { KpiCard } from "@/components/shared/KpiCard";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { useMoneyMovements } from "@/hooks/useMoneyMovements";
import { formatCurrency, formatDate } from "@/utils/formatters";
import { ROUTES } from "@/utils/constants";
import type { MoneyMovementResponse, MoneyMovementType } from "@/types/money-movement";
import type { MetricCard } from "@/types/reports";
import { usePermissions } from "@/hooks/usePermissions";

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
  provision_deposit: "Deposito Provision",
  provision_expense: "Gasto Provision",
  advance_payment: "Anticipo Proveedor",
  advance_collection: "Anticipo Cliente",
  asset_payment: "Pago Activo Fijo",
  asset_purchase: "Compra Activo (Crédito)",
  expense_accrual: "Gasto Causado (Pasivo)",
  deferred_funding: "Pago Gasto Diferido",
  deferred_expense: "Cuota Gasto Diferido",
  commission_accrual: "Comisión Causada",
  depreciation_expense: "Depreciación Activo",
};

const typeColors: Record<string, string> = {
  payment_to_supplier: "bg-red-100 text-red-800",
  collection_from_client: "bg-emerald-100 text-emerald-800",
  expense: "bg-orange-100 text-orange-800",
  service_income: "bg-blue-100 text-blue-800",
  transfer_out: "bg-purple-100 text-purple-800",
  transfer_in: "bg-purple-100 text-purple-800",
  capital_injection: "bg-teal-100 text-teal-800",
  capital_return: "bg-yellow-100 text-yellow-800",
  commission_payment: "bg-pink-100 text-pink-800",
  provision_deposit: "bg-violet-100 text-violet-800",
  provision_expense: "bg-amber-100 text-amber-800",
  asset_payment: "bg-slate-100 text-slate-800",
  asset_purchase: "bg-slate-100 text-slate-800",
  expense_accrual: "bg-rose-100 text-rose-800",
  deferred_funding: "bg-indigo-100 text-indigo-800",
  deferred_expense: "bg-cyan-100 text-cyan-800",
  commission_accrual: "bg-pink-100 text-pink-800",
  depreciation_expense: "bg-amber-100 text-amber-800",
};

const columns: ColumnDef<MoneyMovementResponse, unknown>[] = [
  { accessorKey: "movement_number", header: "#", cell: ({ row }) => <span className="font-medium">#{row.original.movement_number}</span> },
  { accessorKey: "date", header: "Fecha", enableSorting: true, cell: ({ row }) => formatDate(row.original.date) },
  { accessorKey: "movement_type", header: "Tipo", cell: ({ row }) => <Badge variant="outline" className={typeColors[row.original.movement_type] ?? ""}>{typeLabels[row.original.movement_type] ?? row.original.movement_type}</Badge> },
  { accessorKey: "description", header: "Descripcion", cell: ({ row }) => (
    <span className="flex items-center gap-1.5">
      {row.original.description}
      {row.original.evidence_url && <Paperclip className="h-3.5 w-3.5 text-slate-400 shrink-0" />}
    </span>
  ) },
  { accessorKey: "amount", header: "Monto", enableSorting: true, cell: ({ row }) => <span className="font-medium tabular-nums">{formatCurrency(row.original.amount)}</span> },
  { accessorKey: "account_name", header: "Cuenta" },
  { accessorKey: "third_party_name", header: "Tercero", cell: ({ row }) => row.original.third_party_name ?? "-" },
  { accessorKey: "status", header: "Estado", cell: ({ row }) => <StatusBadge status={row.original.status} /> },
];

export default function TreasuryPage() {
  const navigate = useNavigate();
  const { hasPermission } = usePermissions();
  const [page, setPage] = useState(0);
  const [typeFilter, setTypeFilter] = useState<string>("all");
  const [search, setSearch] = useState("");
  const { dateFrom, dateTo, setDateFrom, setDateTo } = useDateFilter();

  const { data, isLoading } = useMoneyMovements({
    skip: page * PAGE_SIZE,
    limit: PAGE_SIZE,
    movement_type: typeFilter === "all" ? undefined : typeFilter,
    date_from: dateFrom || undefined,
    date_to: dateTo || undefined,
  });

  const pageCount = data ? Math.ceil(data.total / PAGE_SIZE) : 1;

  const kpis = useMemo(() => {
    const items = data?.items ?? [];
    const totalAmount = items.reduce((sum, m) => sum + Number(m.amount), 0);
    const count = data?.total ?? 0;
    return {
      total: { current_value: totalAmount, previous_value: 0, change_percentage: null } as MetricCard,
      count: { current_value: count, previous_value: 0, change_percentage: null } as MetricCard,
    };
  }, [data]);

  return (
    <div className="space-y-4">
      <PageHeader title="Tesoreria" description="Movimientos de dinero">
        {hasPermission("treasury.create_movements") && (
          <Button onClick={() => navigate(ROUTES.TREASURY_NEW)} className="bg-emerald-600 hover:bg-emerald-700">
            <Plus className="h-4 w-4 mr-2" />Nuevo Movimiento
          </Button>
        )}
      </PageHeader>

      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {Array.from({ length: 2 }).map((_, i) => (
            <Skeleton key={i} className="h-[120px] rounded-lg" />
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <KpiCard
            label="Total Movimientos"
            metric={kpis.total}
            icon={<Wallet className="h-4 w-4" />}
            accentColor="sky"
          />
          <KpiCard
            label="Operaciones"
            metric={kpis.count}
            icon={<Hash className="h-4 w-4" />}
            accentColor="violet"
            formatValue={(n) => String(n)}
          />
        </div>
      )}

      <Tabs value={typeFilter} onValueChange={(v) => { setTypeFilter(v); setPage(0); }}>
        <TabsList className="flex-wrap h-auto">
          <TabsTrigger value="all">Todos</TabsTrigger>
          <TabsTrigger value="payment_to_supplier">Pagos</TabsTrigger>
          <TabsTrigger value="collection_from_client">Cobros</TabsTrigger>
          <TabsTrigger value="expense">Gastos</TabsTrigger>
          <TabsTrigger value="transfer_out">Transf.</TabsTrigger>
          <TabsTrigger value="provision_deposit">Provisiones</TabsTrigger>
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
        onRowClick={(row) => navigate(`/treasury/${row.id}`)}
        emptyTitle="Sin movimientos"
        emptyDescription="No se encontraron movimientos de tesoreria."
        exportFilename="ecobalance_movimientos-tesoreria"
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
