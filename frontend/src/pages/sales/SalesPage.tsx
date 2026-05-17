import { useState, useMemo } from "react";
import { useDateFilter } from "@/stores/dateFilterStore";
import { useNavigate, useSearchParams, useLocation } from "react-router-dom";
import { type ColumnDef } from "@tanstack/react-table";
import { Plus, DollarSign, TrendingUp, TrendingDown, Hash, MoreHorizontal, Eye, Pencil, XCircle, FileText, Scale } from "lucide-react";
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
import { saleService } from "@/services/sales";
import { toast } from "sonner";
import { formatCurrency, formatDate, formatWeight, formatPercentage } from "@/utils/formatters";
import { ROUTES } from "@/utils/constants";
import type { SaleResponse } from "@/types/sale";
import type { MetricCard } from "@/types/reports";
import { useAuthStore } from "@/stores/authStore";
import { exportSalePDF } from "@/utils/pdfExport";
import { usePermissions } from "@/hooks/usePermissions";
import { ThirdPartyLink } from "@/components/shared/EntityLink";
import { saveScroll, useScrollRestoration } from "@/hooks/useScrollRestoration";

const PAGE_SIZE = 20;

function ActionsCell({ sale }: { sale: SaleResponse }) {
  const navigate = useNavigate();
  const location = useLocation();
  const { organizationId, organizations } = useAuthStore();
  const orgName = organizations.find((o) => o.id === organizationId)?.name ?? "";
  const [cancelOpen, setCancelOpen] = useState(false);
  const { hasPermission } = usePermissions();

  const cancelMutation = useCancelSale();

  const canEdit = sale.status === "registered" && !sale.double_entry_id && hasPermission("sales.edit");
  const canLiquidate = sale.status === "registered" && !sale.double_entry_id && hasPermission("sales.liquidate");
  const canCancel = (sale.status === "registered" || sale.status === "liquidated") && !sale.double_entry_id && hasPermission("sales.cancel");

  const currentUrl = location.pathname + location.search;

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
          <DropdownMenuItem onClick={() => { saveScroll(currentUrl); navigate(`/sales/${sale.id}`); }}>
            <Eye className="h-4 w-4 mr-2" />
            Ver detalle
          </DropdownMenuItem>
          {canEdit && (
            <DropdownMenuItem onClick={() => { saveScroll(currentUrl); navigate(`/sales/${sale.id}/edit`); }}>
              <Pencil className="h-4 w-4 mr-2" />
              Editar
            </DropdownMenuItem>
          )}
          {canLiquidate && (
            <DropdownMenuItem onClick={() => { saveScroll(currentUrl); navigate(`/sales/${sale.id}/liquidate`); }}>
              <DollarSign className="h-4 w-4 mr-2" />
              Liquidar
            </DropdownMenuItem>
          )}
          {canCancel && (
            <DropdownMenuItem onClick={() => setCancelOpen(true)} className="text-red-600">
              <XCircle className="h-4 w-4 mr-2" />
              Cancelar
            </DropdownMenuItem>
          )}
          <DropdownMenuSeparator />
          <DropdownMenuItem onClick={() => exportSalePDF(sale, orgName, { showPrices: hasPermission("sales.view_prices"), showProfit: hasPermission("sales.view_profit") })}>
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

function getColumns(canViewPrices: boolean, canViewProfit: boolean, showCogs: boolean): ColumnDef<SaleResponse, unknown>[] {
  return [
    {
      accessorKey: "sale_number",
      header: "#",
      cell: ({ row }) => <span className="font-medium">#{row.original.sale_number}</span>,
    },
    {
      accessorKey: "invoice_number",
      header: "FACTURA",
      cell: ({ row }) => row.original.invoice_number || "—",
    },
    {
      accessorKey: "date",
      header: "FECHA",
      enableSorting: true,
      cell: ({ row }) => formatDate(row.original.date),
    },
    {
      accessorKey: "customer_name",
      header: "CLIENTE",
      cell: ({ row }) => <ThirdPartyLink id={row.original.customer_id}>{row.original.customer_name}</ThirdPartyLink>,
    },
    {
      id: "items",
      header: "DETALLE",
      cell: ({ row }) => (
        <div className="space-y-0.5">
          {row.original.lines.map((line) => (
            <div key={line.id} className="text-xs text-slate-600">
              {line.material_code} - {formatWeight(line.quantity)}{canViewPrices ? ` x ${formatCurrency(line.unit_price)}` : ""}
            </div>
          ))}
        </div>
      ),
    },
    ...(canViewPrices ? [
      {
        accessorKey: "total_amount",
        header: "TOTAL",
        enableSorting: true,
        cell: ({ row }: { row: { original: SaleResponse } }) => (
          <span className="font-medium tabular-nums">
            {formatCurrency(row.original.total_amount)}
            {row.original.total_amount_difference != null && Math.abs(row.original.total_amount_difference) > 0.01 && (
              <Scale className={`inline-block ml-1 h-3.5 w-3.5 ${row.original.total_amount_difference > 0 ? "text-emerald-500" : "text-red-500"}`} />
            )}
          </span>
        ),
      } as ColumnDef<SaleResponse, unknown>,
    ] : []),
    ...(showCogs && canViewProfit ? [
      {
        id: "cogs",
        header: "COSTO (COGS)",
        cell: ({ row }: { row: { original: SaleResponse } }) => (
          <span className="font-medium tabular-nums text-slate-700">
            {formatCurrency(row.original.total_amount - row.original.total_profit)}
          </span>
        ),
      } as ColumnDef<SaleResponse, unknown>,
    ] : []),
    ...(canViewProfit ? [
      {
        accessorKey: "total_profit",
        header: "UTILIDAD BRUTA",
        enableSorting: true,
        cell: ({ row }: { row: { original: SaleResponse } }) => (
          <span className={`font-medium tabular-nums ${row.original.total_profit >= 0 ? "text-emerald-700" : "text-red-700"}`}>
            {formatCurrency(row.original.total_profit)}
          </span>
        ),
      } as ColumnDef<SaleResponse, unknown>,
      {
        id: "commissions",
        header: "COMISIONES",
        cell: ({ row }: { row: { original: SaleResponse } }) => {
          const total = row.original.commissions.reduce((sum, c) => sum + c.commission_amount, 0);
          return total > 0 ? (
            <span className="text-xs tabular-nums">{formatCurrency(total)}</span>
          ) : (
            <span className="text-slate-300">-</span>
          );
        },
      } as ColumnDef<SaleResponse, unknown>,
    ] : []),
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
      header: "ESTADO",
      cell: ({ row }) => <StatusBadge status={row.original.status} />,
    },
    {
      id: "actions",
      header: "",
      cell: ({ row }) => <ActionsCell sale={row.original} />,
    },
  ];
}

export default function SalesPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const { hasPermission } = usePermissions();
  const canViewPrices = hasPermission("sales.view_prices");
  const canViewProfit = hasPermission("sales.view_profit");
  const [searchParams, setSearchParams] = useSearchParams();
  const { dateFrom, dateTo, setDateFrom, setDateTo } = useDateFilter();

  const status = searchParams.get("tab") || "all";
  const page = parseInt(searchParams.get("page") || "0", 10);
  const search = searchParams.get("search") || "";
  const dpFilter = (searchParams.get("dp") as "all" | "exclude" | "only" | null) || "all";
  const dateField = (searchParams.get("date_field") as "date" | "liquidated_at" | null) || "date";

  const showCogs = dpFilter === "exclude" && dateField === "liquidated_at";
  const columns = useMemo(() => getColumns(canViewPrices, canViewProfit, showCogs), [canViewPrices, canViewProfit, showCogs]);

  const setParam = (updates: Record<string, string | null>) => {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      Object.entries(updates).forEach(([k, v]) => {
        if (v === null || v === "" || v === "0" || v === "all") next.delete(k);
        else next.set(k, v);
      });
      return next;
    }, { replace: true });
  };

  const { data, isLoading } = useSales({
    skip: page * PAGE_SIZE,
    limit: PAGE_SIZE,
    status: status === "all" ? undefined : status,
    search: search || undefined,
    date_from: dateFrom || undefined,
    date_to: dateTo || undefined,
    dp_filter: dpFilter === "all" ? undefined : dpFilter,
    date_field: dateField === "date" ? undefined : dateField,
  });

  useScrollRestoration(!isLoading);

  const pageCount = data ? Math.ceil(data.total / PAGE_SIZE) : 1;

  const kpis = useMemo(() => {
    // Totales sobre TODO el set filtrado (no solo la pagina actual) — necesario
    // para que coincidan con el P&L cuando hay paginacion.
    const totalAmount = data?.total_amount_sum ?? 0;
    const totalProfit = data?.total_profit_sum ?? 0;
    const totalCommissions = data?.total_commissions_sum ?? 0;
    const cogs = totalAmount - totalProfit;
    const netProfit = totalProfit - totalCommissions;
    const count = data?.total ?? 0;
    const margin = totalAmount > 0 ? (totalProfit / totalAmount) * 100 : 0;
    const netMargin = totalAmount > 0 ? (netProfit / totalAmount) * 100 : 0;
    const cogsRatio = totalAmount > 0 ? (cogs / totalAmount) * 100 : 0;
    return {
      total: { current_value: totalAmount, previous_value: 0, change_percentage: null } as MetricCard,
      cogs: { current_value: cogs, previous_value: 0, change_percentage: null } as MetricCard,
      profit: { current_value: totalProfit, previous_value: 0, change_percentage: null } as MetricCard,
      netProfit: { current_value: netProfit, previous_value: 0, change_percentage: null } as MetricCard,
      count: { current_value: count, previous_value: 0, change_percentage: null } as MetricCard,
      margin,
      netMargin,
      cogsRatio,
    };
  }, [data]);

  const currentUrl = location.pathname + location.search;

  const handleExportAll = async () => {
    const all = await saleService.getAll({
      skip: 0,
      limit: 1000,
      status: status === "all" ? undefined : status,
      search: search || undefined,
      date_from: dateFrom || undefined,
      date_to: dateTo || undefined,
      dp_filter: dpFilter === "all" ? undefined : dpFilter,
      date_field: dateField === "date" ? undefined : dateField,
    });
    if (all.total > all.items.length) {
      toast.warning(`Excel limitado a ${all.items.length} filas. Hay ${all.total} en total — refina filtros para descargar todo.`);
    }
    return all.items;
  };

  return (
    <div className="space-y-4">
      <PageHeader title="Ventas" description="Gestion de ventas de material">
        {hasPermission("sales.create") && (
          <Button onClick={() => navigate(ROUTES.SALES_NEW)} className="bg-emerald-600 hover:bg-emerald-700">
            <Plus className="h-4 w-4 mr-2" />
            Nueva Venta
          </Button>
        )}
      </PageHeader>

      {/* KPI Cards */}
      {(() => {
        // Total Ventas + COGS + Utilidad Bruta + Utilidad Neta + Operaciones = 5 cuando precios+profit visibles
        const cardCount = canViewPrices ? (canViewProfit ? 5 : 2) : 1;
        const gridClass =
          cardCount === 5
            ? "grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4"
            : cardCount === 2
              ? "grid grid-cols-1 md:grid-cols-2 gap-4"
              : "grid grid-cols-1 gap-4";
        return isLoading ? (
          <div className={gridClass}>
            {Array.from({ length: cardCount }).map((_, i) => (
              <Skeleton key={i} className="h-28 rounded-lg" />
            ))}
          </div>
        ) : (
          <div className={gridClass}>
            {canViewPrices && (
              <KpiCard
                label="Total Ventas"
                metric={kpis.total}
                icon={<DollarSign className="h-4 w-4" />}
                accentColor="emerald"
              />
            )}
            {canViewProfit && (
              <KpiCard
                label="Costo de Ventas (COGS)"
                metric={kpis.cogs}
                icon={<TrendingDown className="h-4 w-4" />}
                accentColor="rose"
                secondaryLabel="% sobre ventas"
                secondaryValue={formatPercentage(kpis.cogsRatio)}
              />
            )}
            {canViewProfit && (
              <KpiCard
                label="Utilidad Bruta"
                metric={kpis.profit}
                icon={<TrendingUp className="h-4 w-4" />}
                accentColor="violet"
                secondaryLabel="Margen"
                secondaryValue={formatPercentage(kpis.margin)}
              />
            )}
            {canViewProfit && (
              <KpiCard
                label="Utilidad Neta"
                metric={kpis.netProfit}
                icon={<TrendingUp className="h-4 w-4" />}
                accentColor="amber"
                secondaryLabel="Margen Neto"
                secondaryValue={formatPercentage(kpis.netMargin)}
              />
            )}
            <KpiCard
              label="Operaciones"
              metric={kpis.count}
              icon={<Hash className="h-4 w-4" />}
              accentColor="sky"
              formatValue={(n) => String(n)}
            />
          </div>
        );
      })()}

      <Tabs value={status} onValueChange={(v) => setParam({ tab: v, page: null, search: null })}>
        <TabsList>
          <TabsTrigger value="all">Todas</TabsTrigger>
          <TabsTrigger value="registered">Registradas</TabsTrigger>
          <TabsTrigger value="liquidated">Liquidadas</TabsTrigger>
          <TabsTrigger value="cancelled">Canceladas</TabsTrigger>
        </TabsList>
      </Tabs>

      {/* Filtros activos del drill-down de P&L */}
      {(dpFilter !== "all" || dateField !== "date") && (
        <div className="flex items-center gap-2 flex-wrap">
          {dpFilter === "exclude" && (
            <span className="inline-flex items-center gap-1 bg-amber-50 text-amber-700 text-xs px-2 py-1 rounded border border-amber-200">
              Sin Pasa Mano
              <button onClick={() => setParam({ dp: null })} className="hover:bg-amber-100 rounded px-1">×</button>
            </span>
          )}
          {dpFilter === "only" && (
            <span className="inline-flex items-center gap-1 bg-emerald-50 text-emerald-700 text-xs px-2 py-1 rounded border border-emerald-200">
              Solo Pasa Mano
              <button onClick={() => setParam({ dp: null })} className="hover:bg-emerald-100 rounded px-1">×</button>
            </span>
          )}
          {dateField === "liquidated_at" && (
            <span className="inline-flex items-center gap-1 bg-sky-50 text-sky-700 text-xs px-2 py-1 rounded border border-sky-200">
              Por fecha de liquidación
              <button onClick={() => setParam({ date_field: null })} className="hover:bg-sky-100 rounded px-1">×</button>
            </span>
          )}
        </div>
      )}

      <DataTable
        columns={columns}
        data={data?.items ?? []}
        loading={isLoading}
        pageCount={pageCount}
        pageIndex={page}
        pageSize={PAGE_SIZE}
        totalItems={data?.total}
        onPageChange={(p) => setParam({ page: p === 0 ? null : String(p) })}
        onRowClick={(row) => { saveScroll(currentUrl); navigate(`/sales/${row.id}`); }}
        emptyTitle="Sin ventas"
        emptyDescription="No se encontraron ventas para los filtros seleccionados."
        exportFilename="ecobalance_ventas"
        onExportAll={handleExportAll}
        currencyColumns={["total_amount", "total_profit"]}
        toolbar={
          <div className="flex items-center gap-3">
            <SearchInput value={search} onChange={(v) => setParam({ search: v, page: null })} placeholder="Buscar venta..." />
            <DateRangePicker dateFrom={dateFrom} dateTo={dateTo} onDateFromChange={setDateFrom} onDateToChange={setDateTo} />
          </div>
        }
      />
    </div>
  );
}
