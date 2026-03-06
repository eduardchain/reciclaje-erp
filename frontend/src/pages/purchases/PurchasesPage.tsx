import { useState, useMemo } from "react";
import { useDateFilter } from "@/stores/dateFilterStore";
import { useNavigate } from "react-router-dom";
import { type ColumnDef } from "@tanstack/react-table";
import { Plus, ShoppingCart, Hash, Calculator, MoreHorizontal, Eye, Pencil, DollarSign, XCircle, FileText } from "lucide-react";
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
import { EntitySelect } from "@/components/shared/EntitySelect";
import { usePurchases, useLiquidatePurchase, useCancelPurchase } from "@/hooks/usePurchases";
import { useMoneyAccounts } from "@/hooks/useMasterData";
import { formatCurrency, formatDate, formatWeight } from "@/utils/formatters";
import { ROUTES } from "@/utils/constants";
import type { PurchaseResponse } from "@/types/purchase";
import type { MetricCard } from "@/types/reports";
import { exportPurchasePDF } from "@/utils/pdfExport";

const PAGE_SIZE = 20;

function ActionsCell({ purchase }: { purchase: PurchaseResponse }) {
  const navigate = useNavigate();
  const [liquidateOpen, setLiquidateOpen] = useState(false);
  const [cancelOpen, setCancelOpen] = useState(false);
  const [paymentAccountId, setPaymentAccountId] = useState("");

  const { data: accountsData } = useMoneyAccounts();
  const liquidateMutation = useLiquidatePurchase();
  const cancelMutation = useCancelPurchase();

  const canEdit = purchase.status === "registered" && !purchase.double_entry_id;
  const accounts = accountsData?.items ?? [];

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
          <DropdownMenuItem onClick={() => navigate(`/purchases/${purchase.id}`)}>
            <Eye className="h-4 w-4 mr-2" />
            Ver detalle
          </DropdownMenuItem>
          {canEdit && (
            <DropdownMenuItem onClick={() => navigate(`/purchases/${purchase.id}/edit`)}>
              <Pencil className="h-4 w-4 mr-2" />
              Editar
            </DropdownMenuItem>
          )}
          {canEdit && (
            <DropdownMenuItem onClick={() => setLiquidateOpen(true)}>
              <DollarSign className="h-4 w-4 mr-2" />
              Liquidar
            </DropdownMenuItem>
          )}
          {canEdit && (
            <DropdownMenuItem onClick={() => setCancelOpen(true)} className="text-red-600">
              <XCircle className="h-4 w-4 mr-2" />
              Cancelar
            </DropdownMenuItem>
          )}
          <DropdownMenuSeparator />
          <DropdownMenuItem onClick={() => exportPurchasePDF(purchase)}>
            <FileText className="h-4 w-4 mr-2" />
            Exportar PDF
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>

      {/* Dialog Liquidar */}
      <ConfirmDialog
        open={liquidateOpen}
        onOpenChange={setLiquidateOpen}
        title="Liquidar Compra"
        description={`Liquidar compra #${purchase.purchase_number} por ${formatCurrency(purchase.total_amount)}`}
        confirmLabel="Liquidar"
        onConfirm={() => {
          liquidateMutation.mutate(
            { id: purchase.id, data: { payment_account_id: paymentAccountId } },
            {
              onSuccess: () => {
                setLiquidateOpen(false);
                setPaymentAccountId("");
              },
            }
          );
        }}
        loading={liquidateMutation.isPending}
        disabled={!paymentAccountId}
      >
        <div className="py-2">
          <label className="text-sm font-medium mb-1.5 block">Cuenta de pago</label>
          <EntitySelect
            value={paymentAccountId}
            onChange={setPaymentAccountId}
            options={accounts.map((a) => ({ id: a.id, label: a.name }))}
            placeholder="Seleccionar cuenta..."
          />
        </div>
      </ConfirmDialog>

      {/* Dialog Cancelar */}
      <ConfirmDialog
        open={cancelOpen}
        onOpenChange={setCancelOpen}
        title="Cancelar Compra"
        description={`Esta accion cancelara la compra #${purchase.purchase_number} y revertira los movimientos de inventario. Esta accion no se puede deshacer.`}
        confirmLabel="Cancelar Compra"
        variant="destructive"
        onConfirm={() => {
          cancelMutation.mutate(purchase.id, {
            onSuccess: () => setCancelOpen(false),
          });
        }}
        loading={cancelMutation.isPending}
      />
    </>
  );
}

const columns: ColumnDef<PurchaseResponse, unknown>[] = [
  {
    accessorKey: "purchase_number",
    header: "#",
    cell: ({ row }) => <span className="font-medium">#{row.original.purchase_number}</span>,
  },
  {
    accessorKey: "date",
    header: "Fecha",
    enableSorting: true,
    cell: ({ row }) => formatDate(row.original.date),
  },
  {
    accessorKey: "supplier_name",
    header: "Proveedor",
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
    cell: ({ row }) => <ActionsCell purchase={row.original} />,
  },
];

export default function PurchasesPage() {
  const navigate = useNavigate();
  const [page, setPage] = useState(0);
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState<string>("all");
  const { dateFrom, dateTo, setDateFrom, setDateTo } = useDateFilter();

  const { data, isLoading } = usePurchases({
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
    const totalAmount = items.reduce((sum, p) => sum + p.total_amount, 0);
    const count = data?.total ?? 0;
    const avg = count > 0 ? totalAmount / items.length : 0;
    return {
      total: { current_value: totalAmount, previous_value: 0, change_percentage: null } as MetricCard,
      count: { current_value: count, previous_value: 0, change_percentage: null } as MetricCard,
      avg: { current_value: avg, previous_value: 0, change_percentage: null } as MetricCard,
    };
  }, [data]);

  return (
    <div className="space-y-4">
      <PageHeader title="Compras" description="Gestion de compras de material">
        <Button onClick={() => navigate(ROUTES.PURCHASES_NEW)} className="bg-emerald-600 hover:bg-emerald-700">
          <Plus className="h-4 w-4 mr-2" />
          Nueva Compra
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
            label="Total Compras"
            metric={kpis.total}
            icon={<ShoppingCart className="h-4 w-4" />}
            accentColor="sky"
          />
          <KpiCard
            label="Operaciones"
            metric={kpis.count}
            icon={<Hash className="h-4 w-4" />}
            accentColor="violet"
            formatValue={(n) => String(n)}
          />
          <KpiCard
            label="Promedio"
            metric={kpis.avg}
            icon={<Calculator className="h-4 w-4" />}
            accentColor="amber"
          />
        </div>
      )}

      <Tabs value={status} onValueChange={(v) => { setStatus(v); setPage(0); }}>
        <TabsList>
          <TabsTrigger value="all">Todas</TabsTrigger>
          <TabsTrigger value="registered">Registradas</TabsTrigger>
          <TabsTrigger value="paid">Pagadas</TabsTrigger>
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
        onRowClick={(row) => navigate(`/purchases/${row.id}`)}
        emptyTitle="Sin compras"
        emptyDescription="No se encontraron compras para los filtros seleccionados."
        exportFilename="ecobalance_compras"
        toolbar={
          <div className="flex items-center gap-3">
            <SearchInput value={search} onChange={(v) => { setSearch(v); setPage(0); }} placeholder="Buscar compra..." />
            <DateRangePicker
              dateFrom={dateFrom}
              dateTo={dateTo}
              onDateFromChange={setDateFrom}
              onDateToChange={setDateTo}
            />
          </div>
        }
      />
    </div>
  );
}
