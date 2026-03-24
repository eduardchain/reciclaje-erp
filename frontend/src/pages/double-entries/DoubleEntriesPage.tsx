import { useState, useMemo } from "react";
import { useDateFilter } from "@/stores/dateFilterStore";
import { useNavigate } from "react-router-dom";
import { type ColumnDef } from "@tanstack/react-table";
import { Plus, TrendingUp, Hash, Percent, MoreHorizontal, Eye, XCircle, FileText, Pencil, CheckCircle } from "lucide-react";
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
import { useAuthStore } from "@/stores/authStore";
import { formatCurrency, formatDate, formatPercentage } from "@/utils/formatters";
import { exportDoubleEntryPDF } from "@/utils/pdfExport";
import { ROUTES } from "@/utils/constants";
import type { DoubleEntryResponse } from "@/types/double-entry";
import type { MetricCard } from "@/types/reports";
import { usePermissions } from "@/hooks/usePermissions";

const PAGE_SIZE = 20;

function ActionsCell({ de }: { de: DoubleEntryResponse }) {
  const navigate = useNavigate();
  const [cancelOpen, setCancelOpen] = useState(false);
  const cancel = useCancelDoubleEntry();
  const { organizationId, organizations } = useAuthStore();
  const orgName = organizations.find((o) => o.id === organizationId)?.name ?? "";
  const { hasPermission } = usePermissions();

  const canEdit = de.status === "registered" && hasPermission("double_entries.edit");
  const canLiquidate = de.status === "registered" && hasPermission("double_entries.liquidate");
  const canCancel = (de.status === "registered" || de.status === "liquidated") && hasPermission("double_entries.cancel");

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
          <DropdownMenuItem onClick={() => navigate(`/double-entries/${de.id}`)}>
            <Eye className="h-4 w-4 mr-2" />
            Ver detalle
          </DropdownMenuItem>
          {canEdit && (
            <DropdownMenuItem onClick={() => navigate(`/double-entries/${de.id}/edit`)}>
              <Pencil className="h-4 w-4 mr-2" />
              Editar
            </DropdownMenuItem>
          )}
          {canLiquidate && (
            <DropdownMenuItem onClick={() => navigate(`/double-entries/${de.id}/liquidate`)}>
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

function getColumns(canViewValues: boolean): ColumnDef<DoubleEntryResponse, unknown>[] {
  return [
    { accessorKey: "double_entry_number", header: "#", cell: ({ row }) => <span className="font-medium">#{row.original.double_entry_number}</span> },
    { accessorKey: "invoice_number", header: "Factura" },
    { accessorKey: "date", header: "Fecha", enableSorting: true, cell: ({ row }) => formatDate(row.original.date) },
    { accessorKey: "supplier_name", header: "Proveedor" },
    { accessorKey: "customer_name", header: "Cliente" },
    { accessorKey: "materials_summary", header: "Materiales", cell: ({ row }) => <span className="font-medium">{row.original.materials_summary}</span> },
    ...(canViewValues ? [
      { accessorKey: "profit", header: "Utilidad", enableSorting: true, cell: ({ row }: { row: { original: DoubleEntryResponse } }) => <span className={`font-medium tabular-nums ${row.original.profit >= 0 ? "text-emerald-700" : "text-red-700"}`}>{formatCurrency(row.original.profit)}</span> },
      { accessorKey: "profit_margin", header: "Margen", enableSorting: true, cell: ({ row }: { row: { original: DoubleEntryResponse } }) => formatPercentage(row.original.profit_margin) },
    ] : []),
    { accessorKey: "status", header: "Estado", cell: ({ row }) => <StatusBadge status={row.original.status} /> },
    {
      id: "actions",
      header: "",
      cell: ({ row }) => <ActionsCell de={row.original} />,
    },
  ];
}

export default function DoubleEntriesPage() {
  const navigate = useNavigate();
  const { hasPermission } = usePermissions();
  const canViewValues = hasPermission("double_entries.view_values");
  const canViewProfit = hasPermission("double_entries.view_profit");
  const columns = useMemo(() => getColumns(canViewProfit), [canViewProfit]);
  const [page, setPage] = useState(0);
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState<string>("all");
  const { dateFrom, dateTo, setDateFrom, setDateTo } = useDateFilter();

  const { data, isLoading } = useDoubleEntries({
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
    const totalProfit = items.reduce((sum, d) => sum + d.profit, 0);
    const count = data?.total ?? 0;
    const avgMargin = items.length > 0
      ? items.reduce((sum, d) => sum + d.profit_margin, 0) / items.length
      : 0;
    return {
      profit: { current_value: totalProfit, previous_value: 0, change_percentage: null } as MetricCard,
      count: { current_value: count, previous_value: 0, change_percentage: null } as MetricCard,
      margin: { current_value: avgMargin, previous_value: 0, change_percentage: null } as MetricCard,
    };
  }, [data]);

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
      {isLoading ? (
        <div className={`grid grid-cols-1 ${canViewProfit ? "md:grid-cols-3" : "md:grid-cols-1"} gap-4`}>
          {Array.from({ length: canViewProfit ? 3 : 1 }).map((_, i) => (
            <Skeleton key={i} className="h-28 rounded-lg" />
          ))}
        </div>
      ) : (
        <div className={`grid grid-cols-1 ${canViewValues ? "md:grid-cols-3" : "md:grid-cols-1"} gap-4`}>
          {canViewProfit && (
            <KpiCard
              label="Utilidad Total"
              metric={kpis.profit}
              icon={<TrendingUp className="h-4 w-4" />}
              accentColor="emerald"
            />
          )}
          <KpiCard
            label="Operaciones"
            metric={kpis.count}
            icon={<Hash className="h-4 w-4" />}
            accentColor="sky"
            formatValue={(n) => String(n)}
          />
          {canViewProfit && (
            <KpiCard
              label="Margen Promedio"
              metric={kpis.margin}
              icon={<Percent className="h-4 w-4" />}
              accentColor="violet"
              formatValue={formatPercentage}
            />
          )}
        </div>
      )}

      <Tabs value={status} onValueChange={(v) => { setStatus(v); setPage(0); }}>
        <TabsList>
          <TabsTrigger value="all">Todas</TabsTrigger>
          <TabsTrigger value="registered">Registradas</TabsTrigger>
          <TabsTrigger value="liquidated">Liquidadas</TabsTrigger>
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
        onRowClick={(row) => navigate(`/double-entries/${row.id}`)}
        emptyTitle="Sin doble partidas"
        emptyDescription="No se encontraron operaciones pasa mano."
        exportFilename="ecobalance_doble-partidas"
        toolbar={
          <div className="flex items-center gap-3">
            <SearchInput value={search} onChange={(v) => { setSearch(v); setPage(0); }} placeholder="Buscar..." />
            <DateRangePicker dateFrom={dateFrom} dateTo={dateTo} onDateFromChange={setDateFrom} onDateToChange={setDateTo} />
          </div>
        }
      />
    </div>
  );
}
