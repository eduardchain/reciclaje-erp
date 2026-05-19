import { useState, useMemo } from "react";
import { useDateFilter } from "@/stores/dateFilterStore";
import { useNavigate, useSearchParams, useLocation } from "react-router-dom";
import { type ColumnDef, type SortingState } from "@tanstack/react-table";
import { Plus, TrendingUp, TrendingDown, DollarSign, Hash, Percent, MoreHorizontal, Eye, XCircle, FileText, Pencil, CheckCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
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
import { ConfirmDialog } from "@/components/shared/ConfirmDialog";
import { KpiCard } from "@/components/shared/KpiCard";
import { useDoubleEntries, useCancelDoubleEntry } from "@/hooks/useDoubleEntries";
import { doubleEntryService } from "@/services/doubleEntries";
import { toast } from "sonner";
import { useAuthStore } from "@/stores/authStore";
import { formatCurrency, formatDate, formatPercentage } from "@/utils/formatters";
import { exportDoubleEntryPDF } from "@/utils/pdfExport";
import { ROUTES } from "@/utils/constants";
import type { DoubleEntryResponse } from "@/types/double-entry";
import type { MetricCard } from "@/types/reports";
import { usePermissions } from "@/hooks/usePermissions";
import { saveScroll, useScrollRestoration } from "@/hooks/useScrollRestoration";

const PAGE_SIZE = 20;

function ActionsCell({ de }: { de: DoubleEntryResponse }) {
  const navigate = useNavigate();
  const location = useLocation();
  const [cancelOpen, setCancelOpen] = useState(false);
  const cancel = useCancelDoubleEntry();
  const { organizationId, organizations } = useAuthStore();
  const orgName = organizations.find((o) => o.id === organizationId)?.name ?? "";
  const { hasPermission } = usePermissions();

  const canEdit = de.status === "registered" && hasPermission("double_entries.edit");
  const canLiquidate = de.status === "registered" && hasPermission("double_entries.liquidate");
  const canCancel = (de.status === "registered" || de.status === "liquidated") && hasPermission("double_entries.cancel");

  const currentUrl = location.pathname + location.search;

  return (
    <>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button
            variant="ghost"
            size="icon"
            className="h-8 w-8"
            onClick={(e) => e.stopPropagation()}
          >
            <MoreHorizontal className="h-4 w-4" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" onClick={(e) => e.stopPropagation()}>
          <DropdownMenuItem onClick={() => { saveScroll(currentUrl); navigate(`/double-entries/${de.id}`); }}>
            <Eye className="h-4 w-4 mr-2" />
            Ver detalle
          </DropdownMenuItem>
          {canEdit && (
            <DropdownMenuItem onClick={() => { saveScroll(currentUrl); navigate(`/double-entries/${de.id}/edit`); }}>
              <Pencil className="h-4 w-4 mr-2" />
              Editar
            </DropdownMenuItem>
          )}
          {canLiquidate && (
            <DropdownMenuItem onClick={() => { saveScroll(currentUrl); navigate(`/double-entries/${de.id}/liquidate`); }}>
              <CheckCircle className="h-4 w-4 mr-2" />
              Liquidar
            </DropdownMenuItem>
          )}
          {canCancel && (
            <>
              <DropdownMenuSeparator />
              <DropdownMenuItem onClick={() => setCancelOpen(true)} className="text-red-600">
                <XCircle className="h-4 w-4 mr-2" />
                Cancelar
              </DropdownMenuItem>
            </>
          )}
          {de.status === "liquidated" && (
            <>
              <DropdownMenuSeparator />
              <DropdownMenuItem onClick={() => exportDoubleEntryPDF(de, orgName, { showProfit: hasPermission("double_entries.view_profit") })}>
                <FileText className="h-4 w-4 mr-2" />
                Exportar PDF
              </DropdownMenuItem>
            </>
          )}
        </DropdownMenuContent>
      </DropdownMenu>

      <ConfirmDialog
        open={cancelOpen}
        onOpenChange={setCancelOpen}
        title="Cancelar Doble Partida"
        description={`Esto ${de.status === "liquidated" ? "revertira los saldos y " : ""}cancelara la Doble Partida #${de.double_entry_number}. Esta seguro?`}
        confirmLabel="Si, cancelar"
        variant="destructive"
        onConfirm={() => cancel.mutate(de.id, { onSuccess: () => setCancelOpen(false) })}
        loading={cancel.isPending}
      />
    </>
  );
}

function getColumns(canViewProfit: boolean): ColumnDef<DoubleEntryResponse, unknown>[] {
  return [
    { accessorKey: "double_entry_number", header: "#", cell: ({ row }) => <span className="font-medium">#{row.original.double_entry_number}</span> },
    { accessorKey: "invoice_number", header: "FACTURA", cell: ({ row }) => row.original.invoice_number || "—" },
    { accessorKey: "date", header: "FECHA", enableSorting: true, cell: ({ row }) => formatDate(row.original.date) },
    { accessorKey: "customer_name", header: "CLIENTE" },
    { accessorKey: "materials_summary", header: "DETALLE", cell: ({ row }) => <span className="text-xs text-slate-600">{row.original.materials_summary}</span> },
    { accessorKey: "total_sale_amount", header: "TOTAL", cell: ({ row }) => <span className="font-medium tabular-nums">{formatCurrency(row.original.total_sale_amount)}</span> },
    ...(canViewProfit ? [
      { accessorKey: "profit", header: "UTILIDAD BRUTA", cell: ({ row }: { row: { original: DoubleEntryResponse } }) => <span className={`font-medium tabular-nums ${row.original.profit >= 0 ? "text-emerald-700" : "text-red-700"}`}>{formatCurrency(row.original.profit)}</span> } as ColumnDef<DoubleEntryResponse, unknown>,
      { id: "commissions", header: "COMISIONES", cell: ({ row }: { row: { original: DoubleEntryResponse } }) => {
          const total = row.original.commissions.reduce((sum, c) => sum + c.commission_amount, 0);
          return total > 0 ? <span className="text-xs tabular-nums">{formatCurrency(total)}</span> : <span className="text-slate-300">-</span>;
        },
      } as ColumnDef<DoubleEntryResponse, unknown>,
    ] : []),
    { accessorKey: "status", header: "ESTADO", cell: ({ row }) => <StatusBadge status={row.original.status} /> },
    {
      id: "actions",
      header: "",
      cell: ({ row }) => <ActionsCell de={row.original} />,
    },
  ];
}

export default function DoubleEntriesPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const { hasPermission } = usePermissions();
  const canViewValues = hasPermission("double_entries.view_values");
  const canViewProfit = hasPermission("double_entries.view_profit");
  const [searchParams, setSearchParams] = useSearchParams();
  const columns = useMemo(() => getColumns(canViewProfit), [canViewProfit]);
  const { dateFrom, dateTo, setDateFrom, setDateTo } = useDateFilter();

  const status = searchParams.get("tab") || "all";
  const page = parseInt(searchParams.get("page") || "0", 10);
  const search = searchParams.get("search") || "";
  const dateField = (searchParams.get("date_field") as "date" | "liquidated_at" | null) || "date";
  const sortField = searchParams.get("sort") || "";
  const sortDesc = searchParams.get("dir") !== "asc";
  const sorting: SortingState = sortField ? [{ id: sortField, desc: sortDesc }] : [];

  // URL date params override Zustand (decision #50). Lectura directa por render.
  const urlDateFrom = searchParams.get("date_from");
  const urlDateTo = searchParams.get("date_to");
  const effectiveDateFrom = urlDateFrom || dateFrom;
  const effectiveDateTo = urlDateTo || dateTo;
  const hasUrlDateOverride = Boolean(urlDateFrom || urlDateTo);

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

  const clearDateOverride = () => {
    if (hasUrlDateOverride) setParam({ date_from: null, date_to: null });
  };
  const handleDateFromChange = (v: string) => { setDateFrom(v); clearDateOverride(); };
  const handleDateToChange = (v: string) => { setDateTo(v); clearDateOverride(); };

  const { data, isLoading } = useDoubleEntries({
    skip: page * PAGE_SIZE,
    limit: PAGE_SIZE,
    status: status === "all" ? undefined : status,
    search: search || undefined,
    date_from: effectiveDateFrom || undefined,
    date_to: effectiveDateTo || undefined,
    date_field: dateField === "date" ? undefined : dateField,
    sort_by: sortField || undefined,
    sort_dir: sortField ? (sortDesc ? "desc" : "asc") : undefined,
  });

  useScrollRestoration(!isLoading);

  const pageCount = data ? Math.ceil(data.total / PAGE_SIZE) : 1;

  const kpis = useMemo(() => {
    // Totales sobre TODO el set filtrado (no solo la pagina actual) — paridad con P&L.
    const totalPurchase = data?.total_purchase_cost_sum ?? 0;
    const totalSale = data?.total_sale_amount_sum ?? 0;
    const totalProfit = data?.total_profit_sum ?? 0;
    const count = data?.total ?? 0;
    // Margen ponderado = profit / sale * 100 (mas preciso que promedio simple de margenes).
    const margin = totalSale > 0 ? (totalProfit / totalSale) * 100 : 0;
    return {
      purchase: { current_value: totalPurchase, previous_value: 0, change_percentage: null } as MetricCard,
      sale: { current_value: totalSale, previous_value: 0, change_percentage: null } as MetricCard,
      profit: { current_value: totalProfit, previous_value: 0, change_percentage: null } as MetricCard,
      count: { current_value: count, previous_value: 0, change_percentage: null } as MetricCard,
      margin: { current_value: margin, previous_value: 0, change_percentage: null } as MetricCard,
    };
  }, [data]);

  const currentUrl = location.pathname + location.search;

  const handleExportAll = async () => {
    const all = await doubleEntryService.getAll({
      skip: 0,
      limit: 1000,
      status: status === "all" ? undefined : status,
      search: search || undefined,
      date_from: effectiveDateFrom || undefined,
      date_to: effectiveDateTo || undefined,
      date_field: dateField === "date" ? undefined : dateField,
    });
    if (all.total > all.items.length) {
      toast.warning(`Excel limitado a ${all.items.length} filas. Hay ${all.total} en total — refina filtros para descargar todo.`);
    }
    return all.items;
  };

  return (
    <div className="space-y-4">
      <PageHeader title="Doble Partida" description="Operaciones Pasa Mano (compra+venta simultanea)">
        {hasPermission("double_entries.create") && (
          <Button onClick={() => navigate(ROUTES.DOUBLE_ENTRIES_NEW)} className="bg-emerald-600 hover:bg-emerald-700">
            <Plus className="h-4 w-4 mr-2" />Nueva Doble Partida
          </Button>
        )}
      </PageHeader>

      {/* KPI Cards */}
      {(() => {
        // Total Ventas + Costo Compras + Utilidad + Margen + Operaciones
        const cards: number = (canViewValues ? 2 : 0) + (canViewProfit ? 2 : 0) + 1;
        const gridClass =
          cards >= 5
            ? "grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4"
            : cards >= 3
              ? "grid grid-cols-1 md:grid-cols-3 gap-4"
              : cards === 2
                ? "grid grid-cols-1 md:grid-cols-2 gap-4"
                : "grid grid-cols-1 gap-4";
        return isLoading ? (
          <div className={gridClass}>
            {Array.from({ length: cards }).map((_, i) => (
              <Skeleton key={i} className="h-28 rounded-lg" />
            ))}
          </div>
        ) : (
          <div className={gridClass}>
            {canViewValues && (
              <KpiCard
                label="Total Ventas"
                metric={kpis.sale}
                icon={<DollarSign className="h-4 w-4" />}
                accentColor="emerald"
              />
            )}
            {canViewValues && (
              <KpiCard
                label="Costo Compras"
                metric={kpis.purchase}
                icon={<TrendingDown className="h-4 w-4" />}
                accentColor="rose"
              />
            )}
            {canViewProfit && (
              <KpiCard
                label="Utilidad Pasa Mano"
                metric={kpis.profit}
                icon={<TrendingUp className="h-4 w-4" />}
                accentColor="violet"
              />
            )}
            {canViewProfit && (
              <KpiCard
                label="Margen"
                metric={kpis.margin}
                icon={<Percent className="h-4 w-4" />}
                accentColor="amber"
                formatValue={formatPercentage}
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

      {(dateField === "liquidated_at" || hasUrlDateOverride) && (
        <div className="flex items-center gap-2 flex-wrap">
          {hasUrlDateOverride && (
            <span className="inline-flex items-center gap-1 bg-indigo-50 text-indigo-700 text-xs px-2 py-1 rounded border border-indigo-200">
              Rango: {formatDate(effectiveDateFrom)} – {formatDate(effectiveDateTo)}
              <button onClick={clearDateOverride} className="hover:bg-indigo-100 rounded px-1" aria-label="Limpiar override de fechas">×</button>
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
        onRowClick={(row) => { saveScroll(currentUrl); navigate(`/double-entries/${row.id}`); }}
        sorting={sorting}
        onSortingChange={onSortingChange}
        emptyTitle="Sin doble partidas"
        emptyDescription="No se encontraron operaciones pasa mano."
        exportFilename="ecobalance_doble-partidas"
        onExportAll={handleExportAll}
        currencyColumns={["total_sale_amount", "profit"]}
        toolbar={
          <div className="flex items-center gap-3">
            <SearchInput value={search} onChange={(v) => setParam({ search: v, page: null })} placeholder="Buscar..." />
            <DateRangePicker dateFrom={effectiveDateFrom} dateTo={effectiveDateTo} onDateFromChange={handleDateFromChange} onDateToChange={handleDateToChange} />
          </div>
        }
      />
    </div>
  );
}
