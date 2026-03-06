import { useState, useMemo } from "react";
import { useDateFilter } from "@/stores/dateFilterStore";
import { useNavigate } from "react-router-dom";
import { type ColumnDef } from "@tanstack/react-table";
import { Plus, DollarSign, TrendingUp, Hash, MoreHorizontal, Eye, Pencil, XCircle, FileText } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Skeleton } from "@/components/ui/skeleton";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { PageHeader } from "@/components/shared/PageHeader";
import { DataTable } from "@/components/shared/DataTable";
import { SearchInput } from "@/components/shared/SearchInput";
import { DateRangePicker } from "@/components/shared/DateRangePicker";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { KpiCard } from "@/components/shared/KpiCard";
import { ConfirmDialog } from "@/components/shared/ConfirmDialog";
import { useSales, useCancelSale } from "@/hooks/useSales";
import { formatCurrency, formatDate, formatWeight, formatPercentage } from "@/utils/formatters";
import { ROUTES } from "@/utils/constants";
import type { SaleResponse } from "@/types/sale";
import type { MetricCard } from "@/types/reports";
import { useAuthStore } from "@/stores/authStore";
import { exportSalePDF } from "@/utils/pdfExport";

const PAGE_SIZE = 20;

function ActionsCell({ sale }: { sale: SaleResponse }) {
  const navigate = useNavigate();
  const { organizationId, organizations } = useAuthStore();
  const orgName = organizations.find((o) => o.id === organizationId)?.name ?? "";
  const [cancelOpen, setCancelOpen] = useState(false);

  const cancelMutation = useCancelSale();

  const canEdit = sale.status === "registered" && !sale.double_entry_id;

  return (
    <>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button
            variant="ghost"
            size="sm"
            className="h-8 w-8 p-0"
            onClick={(e) => e.stopPropagation()}
          >
            <MoreHorizontal className="h-4 w-4" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" onClick={(e) => e.stopPropagation()}>
          <DropdownMenuItem onClick={() => navigate(`/sales/${sale.id}`)}>
            <Eye className="h-4 w-4 mr-2" />
            Ver detalle
          </DropdownMenuItem>
          {canEdit && (
            <DropdownMenuItem onClick={() => navigate(`/sales/${sale.id}/edit`)}>
              <Pencil className="h-4 w-4 mr-2" />
              Editar
            </DropdownMenuItem>
          )}
          {canEdit && (
            <DropdownMenuItem onClick={() => navigate(`/sales/${sale.id}/liquidate`)}>
              <DollarSign className="h-4 w-4 mr-2" />
              Cobrar
            </DropdownMenuItem>
          )}
          {canEdit && (
            <DropdownMenuItem onClick={() => setCancelOpen(true)} className="text-red-600">
              <XCircle className="h-4 w-4 mr-2" />
              Cancelar
            </DropdownMenuItem>
          )}
          <DropdownMenuSeparator />
          <DropdownMenuItem onClick={() => exportSalePDF(sale, orgName)}>
            <FileText className="h-4 w-4 mr-2" />
            Exportar PDF
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>

      {/* Dialog Cancelar */}
      <ConfirmDialog
        open={cancelOpen}
        onOpenChange={setCancelOpen}
        title="Cancelar Venta"
        description={`Esta accion cancelara la venta #${sale.sale_number} y revertira los movimientos de inventario. Esta accion no se puede deshacer.`}
        confirmLabel="Cancelar Venta"
        variant="destructive"
        onConfirm={() => {
          cancelMutation.mutate(sale.id, {
            onSuccess: () => setCancelOpen(false),
          });
        }}
        loading={cancelMutation.isPending}
      />
    </>
  );
}

const columns: ColumnDef<SaleResponse, unknown>[] = [
  {
    accessorKey: "sale_number",
    header: "#",
    cell: ({ row }) => <span className="font-medium">#{row.original.sale_number}</span>,
  },
  {
    accessorKey: "date",
    header: "Fecha",
    enableSorting: true,
    cell: ({ row }) => formatDate(row.original.date),
  },
  {
    accessorKey: "customer_name",
    header: "Cliente",
  },
  {
    id: "items",
    header: "Items",
    cell: ({ row }) => (
      <div className="space-y-0.5">
        {row.original.lines.map((line) => (
          <div key={line.id} className="text-xs text-slate-600">
            {line.material_code} - {formatWeight(line.quantity)} x {formatCurrency(line.unit_price)}
          </div>
        ))}
      </div>
    ),
  },
  {
    accessorKey: "total_amount",
    header: "Total",
    enableSorting: true,
    cell: ({ row }) => (
      <span className="font-medium tabular-nums">{formatCurrency(row.original.total_amount)}</span>
    ),
  },
  {
    accessorKey: "total_profit",
    header: "Utilidad",
    enableSorting: true,
    cell: ({ row }) => (
      <span className={`font-medium tabular-nums ${row.original.total_profit >= 0 ? "text-emerald-700" : "text-red-700"}`}>
        {formatCurrency(row.original.total_profit)}
      </span>
    ),
  },
  {
    id: "commissions",
    header: "Comisiones",
    cell: ({ row }) => {
      const total = row.original.commissions.reduce((sum, c) => sum + c.commission_amount, 0);
      return total > 0 ? (
        <span className="text-xs tabular-nums">{formatCurrency(total)}</span>
      ) : (
        <span className="text-slate-300">-</span>
      );
    },
  },
  {
    id: "double_entry",
    header: "D.P.",
    cell: ({ row }) =>
      row.original.double_entry_id ? (
        <span className="bg-emerald-100 text-emerald-700 text-xs px-1.5 py-0.5 rounded font-medium">
          DP
        </span>
      ) : (
        <span className="text-slate-300">-</span>
      ),
  },
  {
    accessorKey: "status",
    header: "Estado",
    cell: ({ row }) => <StatusBadge status={row.original.status} />,
  },
  {
    id: "actions",
    header: "",
    cell: ({ row }) => <ActionsCell sale={row.original} />,
  },
];

export default function SalesPage() {
  const navigate = useNavigate();
  const [page, setPage] = useState(0);
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState<string>("all");
  const { dateFrom, dateTo, setDateFrom, setDateTo } = useDateFilter();

  const { data, isLoading } = useSales({
    skip: page * PAGE_SIZE,
    limit: PAGE_SIZE,
    status: status === "all" ? undefined : status,
    search: search || undefined,
    date_from: dateFrom || undefined,
    date_to: dateTo || undefined,
  });

  const pageCount = data ? Math.ceil(data.total / PAGE_SIZE) : 1;

  const kpis = useMemo(() => {
    const items = data?.items ?? [];
    const totalAmount = items.reduce((sum, s) => sum + s.total_amount, 0);
    const totalProfit = items.reduce((sum, s) => sum + s.total_profit, 0);
    const count = data?.total ?? 0;
    const margin = totalAmount > 0 ? (totalProfit / totalAmount) * 100 : 0;
    return {
      total: { current_value: totalAmount, previous_value: 0, change_percentage: null } as MetricCard,
      profit: { current_value: totalProfit, previous_value: 0, change_percentage: null } as MetricCard,
      count: { current_value: count, previous_value: 0, change_percentage: null } as MetricCard,
      margin,
    };
  }, [data]);

  return (
    <div className="space-y-4">
      <PageHeader title="Ventas" description="Gestion de ventas de material">
        <Button onClick={() => navigate(ROUTES.SALES_NEW)} className="bg-emerald-600 hover:bg-emerald-700">
          <Plus className="h-4 w-4 mr-2" />
          Nueva Venta
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
            label="Total Ventas"
            metric={kpis.total}
            icon={<DollarSign className="h-4 w-4" />}
            accentColor="emerald"
          />
          <KpiCard
            label="Utilidad Total"
            metric={kpis.profit}
            icon={<TrendingUp className="h-4 w-4" />}
            accentColor="violet"
            secondaryLabel="Margen"
            secondaryValue={formatPercentage(kpis.margin)}
          />
          <KpiCard
            label="Operaciones"
            metric={kpis.count}
            icon={<Hash className="h-4 w-4" />}
            accentColor="sky"
            formatValue={(n) => String(n)}
          />
        </div>
      )}

      <Tabs value={status} onValueChange={(v) => { setStatus(v); setPage(0); }}>
        <TabsList>
          <TabsTrigger value="all">Todas</TabsTrigger>
          <TabsTrigger value="registered">Registradas</TabsTrigger>
          <TabsTrigger value="paid">Cobradas</TabsTrigger>
          <TabsTrigger value="cancelled">Canceladas</TabsTrigger>
        </TabsList>
      </Tabs>

      <DataTable
        columns={columns}
        data={data?.items ?? []}
        loading={isLoading}
        pageCount={pageCount}
        pageIndex={page}
        pageSize={PAGE_SIZE}
        totalItems={data?.total}
        onPageChange={setPage}
        onRowClick={(row) => navigate(`/sales/${row.id}`)}
        emptyTitle="Sin ventas"
        emptyDescription="No se encontraron ventas para los filtros seleccionados."
        exportFilename="ecobalance_ventas"
        toolbar={
          <div className="flex items-center gap-3">
            <SearchInput value={search} onChange={(v) => { setSearch(v); setPage(0); }} placeholder="Buscar venta..." />
            <DateRangePicker dateFrom={dateFrom} dateTo={dateTo} onDateFromChange={setDateFrom} onDateToChange={setDateTo} />
          </div>
        }
      />
    </div>
  );
}
