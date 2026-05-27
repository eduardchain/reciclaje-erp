import { useState, useMemo } from "react";
import { useDateFilter } from "@/stores/dateFilterStore";
import { useNavigate, useSearchParams, useLocation } from "react-router-dom";
import { type ColumnDef, type SortingState } from "@tanstack/react-table";
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
import { ResponsiveFilterBar } from "@/components/shared/ResponsiveFilterBar";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { KpiCard } from "@/components/shared/KpiCard";
import { ConfirmDialog } from "@/components/shared/ConfirmDialog";
import { OperationListCard } from "@/components/shared/OperationListCard";
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
      meta: { hideOnMobile: true },
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
      meta: { hideOnMobile: true },
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
        meta: { hideOnMobile: true },
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
        cell: ({ row }: { row: { original: SaleResponse } }) => (
          <span className={`font-medium tabular-nums ${row.original.total_profit >= 0 ? "text-emerald-700" : "text-red-700"}`}>
            {formatCurrency(row.original.total_profit)}
          </span>
        ),
      } as ColumnDef<SaleResponse, unknown>,
      {
        id: "commissions",
        header: "COMISIONES",
        meta: { hideOnMobile: true },
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
      meta: { hideOnMobile: true },
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

  // URL date params override Zustand (decision #50): permite drill-down con bounds
  // mes-especificos sin contaminar el filtro global de fecha. Lectura directa en
  // cada render (NO useState) para reaccionar a cambios de URL.
  const urlDateFrom = searchParams.get("date_from");
  const urlDateTo = searchParams.get("date_to");
  const effectiveDateFrom = urlDateFrom || dateFrom;
  const effectiveDateTo = urlDateTo || dateTo;
  const hasUrlDateOverride = Boolean(urlDateFrom || urlDateTo);

  const status = searchParams.get("tab") || "all";
  const page = parseInt(searchParams.get("page") || "0", 10);
  const search = searchParams.get("search") || "";
  const dpFilter = (searchParams.get("dp") as "all" | "exclude" | "only" | null) || "all";
  const dateField = (searchParams.get("date_field") as "date" | "liquidated_at" | null) || "date";
  const sortField = searchParams.get("sort") || "";
  const sortDesc = searchParams.get("dir") !== "asc";
  const sorting: SortingState = sortField ? [{ id: sortField, desc: sortDesc }] : [];

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

  const onSortingChange = (next: SortingState) => {
    setParam({
      sort: next.length > 0 ? next[0].id : null,
      dir: next.length > 0 ? (next[0].desc ? null : "asc") : null,
    });
  };

  // Al cambiar el picker manualmente o limpiar el badge, drop ambos URL params
  // para que Zustand vuelva a ser unica fuente de verdad.
  const clearDateOverride = () => {
    if (hasUrlDateOverride) setParam({ date_from: null, date_to: null });
  };
  const handleDateFromChange = (v: string) => { setDateFrom(v); clearDateOverride(); };
  const handleDateToChange = (v: string) => { setDateTo(v); clearDateOverride(); };

  const { data, isLoading } = useSales({
    skip: page * PAGE_SIZE,
    limit: PAGE_SIZE,
    status: status === "all" ? undefined : status,
    search: search || undefined,
    date_from: effectiveDateFrom || undefined,
    date_to: effectiveDateTo || undefined,
    dp_filter: dpFilter === "all" ? undefined : dpFilter,
    date_field: dateField === "date" ? undefined : dateField,
    sort_by: sortField || undefined,
    sort_dir: sortField ? (sortDesc ? "desc" : "asc") : undefined,
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
      date_from: effectiveDateFrom || undefined,
      date_to: effectiveDateTo || undefined,
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
      {(dpFilter !== "all" || dateField !== "date" || hasUrlDateOverride) && (
        <div className="flex items-center gap-2 flex-wrap">
          {hasUrlDateOverride && (
            <span className="inline-flex items-center gap-1 bg-indigo-50 text-indigo-700 text-xs px-2 py-1 rounded border border-indigo-200">
              Rango: {formatDate(effectiveDateFrom)} – {formatDate(effectiveDateTo)}
              <button onClick={clearDateOverride} className="hover:bg-indigo-100 rounded px-1" aria-label="Limpiar override de fechas">×</button>
            </span>
          )}
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
        sorting={sorting}
        onSortingChange={onSortingChange}
        emptyTitle="Sin ventas"
        emptyDescription="No se encontraron ventas para los filtros seleccionados."
        exportFilename="ecobalance_ventas"
        onExportAll={handleExportAll}
        currencyColumns={["total_amount", "total_profit"]}
        renderMobileCard={(s) => (
          <OperationListCard
            operationNumber={s.sale_number}
            date={s.date}
            invoiceNumber={s.invoice_number}
            partyLabel="Cliente"
            partyName={s.customer_name}
            total={canViewPrices ? s.total_amount : undefined}
            statusBadge={<StatusBadge status={s.status} />}
            cancelled={s.status === "cancelled"}
            actions={<ActionsCell sale={s} />}
            description={s.lines.length > 0 ? s.lines.map((l) => `${l.material_code} ${formatWeight(l.quantity)}`).join(" · ") : undefined}
            extras={
              <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs">
                {canViewProfit && (
                  <span>
                    <span className="text-slate-400">Util:</span>{" "}
                    <span className={`tabular-nums font-medium ${s.total_profit >= 0 ? "text-emerald-700" : "text-red-700"}`}>
                      {formatCurrency(s.total_profit)}
                    </span>
                  </span>
                )}
                {s.double_entry_id && <span className="bg-emerald-100 text-emerald-700 text-[10px] px-1.5 py-0.5 rounded font-medium">Pasa Mano</span>}
              </div>
            }
          />
        )}
        toolbar={
          <ResponsiveFilterBar>
            <SearchInput value={search} onChange={(v) => setParam({ search: v, page: null })} placeholder="Buscar venta..." />
            <DateRangePicker dateFrom={effectiveDateFrom} dateTo={effectiveDateTo} onDateFromChange={handleDateFromChange} onDateToChange={handleDateToChange} />
          </ResponsiveFilterBar>
        }
      />
    </div>
  );
}
