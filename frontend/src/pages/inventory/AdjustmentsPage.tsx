import { useState, useMemo } from "react";
import { useDateFilter } from "@/stores/dateFilterStore";
import { useNavigate, useSearchParams } from "react-router-dom";
import { type ColumnDef, type SortingState } from "@tanstack/react-table";
import { Plus, ArrowLeft, Calculator, Hash, ClipboardCheck, MoreHorizontal, Eye, XCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Skeleton } from "@/components/ui/skeleton";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { PageHeader } from "@/components/shared/PageHeader";
import { DataTable } from "@/components/shared/DataTable";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { DateRangePicker } from "@/components/shared/DateRangePicker";
import { SearchInput } from "@/components/shared/SearchInput";
import { KpiCard } from "@/components/shared/KpiCard";
import { ConfirmDialog } from "@/components/shared/ConfirmDialog";
import { useAdjustments, useAnnulAdjustment } from "@/hooks/useInventory";
import { inventoryService } from "@/services/inventory";
import { toast } from "sonner";
import { formatCurrency, formatDate } from "@/utils/formatters";
import { ROUTES } from "@/utils/constants";
import type { InventoryAdjustmentResponse } from "@/types/inventory";
import type { MetricCard } from "@/types/reports";
import { usePermissions } from "@/hooks/usePermissions";

const PAGE_SIZE = 20;

const typeLabels: Record<string, string> = {
  increase: "Aumento",
  decrease: "Disminucion",
  recount: "Conteo",
  zero_out: "Llevar a Cero",
};

const typeColors: Record<string, string> = {
  increase: "bg-emerald-100 text-emerald-800",
  decrease: "bg-red-100 text-red-800",
  recount: "bg-blue-100 text-blue-800",
  zero_out: "bg-orange-100 text-orange-800",
};

function ActionsCell({ adjustment, onAnnul }: { adjustment: InventoryAdjustmentResponse; onAnnul: (adj: InventoryAdjustmentResponse) => void }) {
  const navigate = useNavigate();
  const canAnnul = adjustment.status === "confirmed";

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="sm" className="h-8 w-8 p-0" onClick={(e) => e.stopPropagation()}>
          <MoreHorizontal className="h-4 w-4" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" onClick={(e) => e.stopPropagation()}>
        <DropdownMenuItem onClick={() => navigate(`/inventory/adjustments/${adjustment.id}`)}>
          <Eye className="h-4 w-4 mr-2" />
          Ver Detalle
        </DropdownMenuItem>
        {canAnnul && (
          <DropdownMenuItem onClick={() => onAnnul(adjustment)} className="text-red-600">
            <XCircle className="h-4 w-4 mr-2" />
            Anular
          </DropdownMenuItem>
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

export default function AdjustmentsPage() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const { hasPermission } = usePermissions();
  const [page, setPage] = useState(0);
  const [statusFilter, setStatusFilter] = useState(searchParams.get("tab") || "all");
  const [search, setSearch] = useState("");
  const { dateFrom, dateTo, setDateFrom, setDateTo } = useDateFilter();
  const [annulTarget, setAnnulTarget] = useState<InventoryAdjustmentResponse | null>(null);
  const [annulReason, setAnnulReason] = useState("");
  const annulMutation = useAnnulAdjustment();

  const excludeMigration = searchParams.get("exclude_migration") === "true";
  const sortField = searchParams.get("sort") || "";
  const sortDesc = searchParams.get("dir") !== "asc";
  const sorting: SortingState = sortField ? [{ id: sortField, desc: sortDesc }] : [];

  // URL date params override Zustand (decision #50). Lectura directa por render —
  // NO useState (que solo inicializa una vez al montar y no reacciona a la URL).
  const urlDateFrom = searchParams.get("date_from");
  const urlDateTo = searchParams.get("date_to");
  const effectiveDateFrom = urlDateFrom || dateFrom;
  const effectiveDateTo = urlDateTo || dateTo;
  const hasUrlDateOverride = Boolean(urlDateFrom || urlDateTo);

  const clearDateOverride = () => {
    if (!hasUrlDateOverride) return;
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      next.delete("date_from");
      next.delete("date_to");
      return next;
    }, { replace: true });
  };
  const handleDateFromChange = (v: string) => { setDateFrom(v); clearDateOverride(); };
  const handleDateToChange = (v: string) => { setDateTo(v); clearDateOverride(); };

  const onSortingChange = (next: SortingState) => {
    setSearchParams((prev) => {
      const params = new URLSearchParams(prev);
      if (next.length === 0) {
        params.delete("sort");
        params.delete("dir");
      } else {
        params.set("sort", next[0].id);
        if (next[0].desc) params.delete("dir");
        else params.set("dir", "asc");
      }
      return params;
    }, { replace: true });
  };

  const { data, isLoading } = useAdjustments({
    skip: page * PAGE_SIZE,
    limit: PAGE_SIZE,
    status: statusFilter === "all" ? undefined : statusFilter,
    date_from: effectiveDateFrom || undefined,
    date_to: effectiveDateTo || undefined,
    exclude_migration_seeds: excludeMigration || undefined,
    sort_by: sortField || undefined,
    sort_dir: sortField ? (sortDesc ? "desc" : "asc") : undefined,
  });

  const pageCount = data ? Math.ceil(data.total / PAGE_SIZE) : 1;

  const kpis = useMemo(() => {
    const items = data?.items ?? [];
    const totalValue = items.reduce((sum, a) => sum + a.total_value, 0);
    const count = data?.total ?? 0;
    const completed = items.filter(a => a.status === "confirmed").length;
    return {
      total: { current_value: totalValue, previous_value: 0, change_percentage: null } as MetricCard,
      count: { current_value: count, previous_value: 0, change_percentage: null } as MetricCard,
      completed: { current_value: completed, previous_value: 0, change_percentage: null } as MetricCard,
    };
  }, [data]);

  const handleExportAll = async () => {
    const all = await inventoryService.getAdjustments({
      skip: 0,
      limit: 1000,
      status: statusFilter === "all" ? undefined : statusFilter,
      date_from: effectiveDateFrom || undefined,
      date_to: effectiveDateTo || undefined,
      exclude_migration_seeds: excludeMigration || undefined,
    });
    if (all.total > all.items.length) {
      toast.warning(`Excel limitado a ${all.items.length} filas. Hay ${all.total} en total — refina filtros para descargar todo.`);
    }
    return all.items;
  };

  const columns: ColumnDef<InventoryAdjustmentResponse, unknown>[] = [
    { accessorKey: "adjustment_number", header: "#", cell: ({ row }) => <span className="font-medium">#{row.original.adjustment_number}</span> },
    { accessorKey: "date", header: "Fecha", enableSorting: true, cell: ({ row }) => formatDate(row.original.date) },
    { accessorKey: "adjustment_type", header: "Tipo", cell: ({ row }) => <Badge variant="outline" className={typeColors[row.original.adjustment_type] ?? ""}>{typeLabels[row.original.adjustment_type] ?? row.original.adjustment_type}</Badge> },
    { accessorKey: "material_name", header: "Material", cell: ({ row }) => `${row.original.material_code ?? ""} - ${row.original.material_name ?? ""}` },
    { accessorKey: "warehouse_name", header: "Bodega" },
    { accessorKey: "quantity", header: "Cantidad", enableSorting: true, cell: ({ row }) => <span className="tabular-nums">{row.original.quantity.toFixed(2)}</span> },
    { accessorKey: "total_value", header: "Valor", enableSorting: true, cell: ({ row }) => formatCurrency(row.original.total_value) },
    { accessorKey: "status", header: "Estado", cell: ({ row }) => <StatusBadge status={row.original.status} /> },
    {
      id: "actions",
      header: "",
      cell: ({ row }) => <ActionsCell adjustment={row.original} onAnnul={(adj) => { setAnnulTarget(adj); setAnnulReason(""); }} />,
    },
  ];

  return (
    <div className="space-y-4">
      <PageHeader title="Ajustes de Inventario" description="Ajustes manuales de stock">
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => navigate(ROUTES.INVENTORY)}>
            <ArrowLeft className="h-4 w-4 mr-2" />Stock
          </Button>
          {hasPermission("inventory.adjust") && (
            <Button onClick={() => navigate(ROUTES.INVENTORY_ADJUSTMENTS_NEW)} className="bg-emerald-600 hover:bg-emerald-700">
              <Plus className="h-4 w-4 mr-2" />Nuevo Ajuste
            </Button>
          )}
        </div>
      </PageHeader>

      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-[120px] rounded-lg" />
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <KpiCard
            label="Valor Ajustes"
            metric={kpis.total}
            icon={<Calculator className="h-4 w-4" />}
            accentColor="sky"
          />
          <KpiCard
            label="Ajustes"
            metric={kpis.count}
            icon={<Hash className="h-4 w-4" />}
            accentColor="violet"
            formatValue={(n) => String(n)}
          />
          <KpiCard
            label="Confirmados"
            metric={kpis.completed}
            icon={<ClipboardCheck className="h-4 w-4" />}
            accentColor="emerald"
            formatValue={(n) => String(n)}
          />
        </div>
      )}

      <Tabs value={statusFilter} onValueChange={(v) => {
        setStatusFilter(v);
        setPage(0);
        // Preservar URL params existentes (date_from/date_to/exclude_migration/etc).
        setSearchParams((prev) => {
          const next = new URLSearchParams(prev);
          if (v === "all") next.delete("tab");
          else next.set("tab", v);
          return next;
        }, { replace: true });
      }}>
        <TabsList>
          <TabsTrigger value="all">Todos</TabsTrigger>
          <TabsTrigger value="confirmed">Confirmados</TabsTrigger>
          <TabsTrigger value="annulled">Anulados</TabsTrigger>
        </TabsList>
      </Tabs>

      {(excludeMigration || hasUrlDateOverride) && (
        <div className="flex items-center gap-2 flex-wrap">
          {hasUrlDateOverride && (
            <span className="inline-flex items-center gap-1 bg-indigo-50 text-indigo-700 text-xs px-2 py-1 rounded border border-indigo-200">
              Rango: {formatDate(effectiveDateFrom)} – {formatDate(effectiveDateTo)}
              <button onClick={clearDateOverride} className="hover:bg-indigo-100 rounded px-1" aria-label="Limpiar override de fechas">×</button>
            </span>
          )}
          {excludeMigration && (
            <span className="inline-flex items-center gap-1 bg-amber-50 text-amber-700 text-xs px-2 py-1 rounded border border-amber-200">
              Sin seeds de migración
              <button
                onClick={() => {
                  setSearchParams((prev) => {
                    const next = new URLSearchParams(prev);
                    next.delete("exclude_migration");
                    return next;
                  }, { replace: true });
                }}
                className="hover:bg-amber-100 rounded px-1"
              >×</button>
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
        onPageChange={setPage}
        onRowClick={(row) => navigate(`/inventory/adjustments/${row.id}`)}
        sorting={sorting}
        onSortingChange={onSortingChange}
        emptyTitle="Sin ajustes"
        emptyDescription="No se encontraron ajustes de inventario."
        exportFilename="ecobalance_ajustes-inventario"
        onExportAll={handleExportAll}
        currencyColumns={["total_value"]}
        totalItems={data?.total}
        toolbar={
          <div className="flex items-center gap-3">
            <SearchInput value={search} onChange={(v) => { setSearch(v); setPage(0); }} placeholder="Buscar ajuste..." />
            <DateRangePicker dateFrom={effectiveDateFrom} dateTo={effectiveDateTo} onDateFromChange={handleDateFromChange} onDateToChange={handleDateToChange} />
          </div>
        }
      />

      <ConfirmDialog
        open={!!annulTarget}
        onOpenChange={(open) => { if (!open) setAnnulTarget(null); }}
        title="Anular Ajuste"
        description={`Esta accion revertira los cambios de stock del ajuste #${annulTarget?.adjustment_number ?? ""}. No se puede deshacer.`}
        confirmLabel="Anular Ajuste"
        variant="destructive"
        disabled={annulReason.length < 1}
        onConfirm={() => {
          if (!annulTarget) return;
          annulMutation.mutate({ id: annulTarget.id, data: { reason: annulReason } }, {
            onSuccess: () => setAnnulTarget(null),
          });
        }}
        loading={annulMutation.isPending}
      >
        <div className="space-y-2 mt-2">
          <Label>Razon de anulacion *</Label>
          <Input value={annulReason} onChange={(e) => setAnnulReason(e.target.value)} placeholder="Razon..." />
        </div>
      </ConfirmDialog>
    </div>
  );
}
