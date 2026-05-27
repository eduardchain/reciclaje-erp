import { useState, useMemo } from "react";
import { useDateFilter } from "@/stores/dateFilterStore";
import { useNavigate, useSearchParams } from "react-router-dom";
import { type ColumnDef, type SortingState } from "@tanstack/react-table";
import { Plus, ArrowLeft, Calculator, Hash, Puzzle, MoreHorizontal, Eye, XCircle, TrendingUp } from "lucide-react";
import { Button } from "@/components/ui/button";
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
import { OperationListCard } from "@/components/shared/OperationListCard";
import { DateRangePicker } from "@/components/shared/DateRangePicker";
import { SearchInput } from "@/components/shared/SearchInput";
import { KpiCard } from "@/components/shared/KpiCard";
import { ConfirmDialog } from "@/components/shared/ConfirmDialog";
import { useTransformations, useAnnulTransformation } from "@/hooks/useInventory";
import { inventoryService } from "@/services/inventory";
import { toast } from "sonner";
import { formatCurrency, formatDate } from "@/utils/formatters";
import { ROUTES } from "@/utils/constants";
import type { MaterialTransformationResponse } from "@/types/inventory";
import type { MetricCard } from "@/types/reports";
import { usePermissions } from "@/hooks/usePermissions";

const PAGE_SIZE = 20;

function ActionsCell({ transformation, onAnnul }: { transformation: MaterialTransformationResponse; onAnnul: (t: MaterialTransformationResponse) => void }) {
  const navigate = useNavigate();
  const canAnnul = transformation.status === "confirmed";

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="sm" className="h-8 w-8 p-0" onClick={(e) => e.stopPropagation()}>
          <MoreHorizontal className="h-4 w-4" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" onClick={(e) => e.stopPropagation()}>
        <DropdownMenuItem onClick={() => navigate(`/inventory/transformations/${transformation.id}`)}>
          <Eye className="h-4 w-4 mr-2" />
          Ver Detalle
        </DropdownMenuItem>
        {canAnnul && (
          <DropdownMenuItem onClick={() => onAnnul(transformation)} className="text-red-600">
            <XCircle className="h-4 w-4 mr-2" />
            Anular
          </DropdownMenuItem>
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

export default function TransformationsPage() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const { hasPermission } = usePermissions();
  const [page, setPage] = useState(0);
  const [statusFilter, setStatusFilter] = useState(searchParams.get("tab") || "all");
  const [search, setSearch] = useState("");
  const { dateFrom, dateTo, setDateFrom, setDateTo } = useDateFilter();
  const [annulTarget, setAnnulTarget] = useState<MaterialTransformationResponse | null>(null);
  const [annulReason, setAnnulReason] = useState("");
  const annulMutation = useAnnulTransformation();

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

  const sortField = searchParams.get("sort") || "";
  const sortDesc = searchParams.get("dir") !== "asc";
  const sorting: SortingState = sortField ? [{ id: sortField, desc: sortDesc }] : [];

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

  const { data, isLoading } = useTransformations({
    skip: page * PAGE_SIZE,
    limit: PAGE_SIZE,
    status: statusFilter === "all" ? undefined : statusFilter,
    date_from: effectiveDateFrom || undefined,
    date_to: effectiveDateTo || undefined,
    sort_by: sortField || undefined,
    sort_dir: sortField ? (sortDesc ? "desc" : "asc") : undefined,
  });

  // Fetch separado para KPI "Utilidad/Perdida": SIEMPRE confirmed (mismo filtro
  // que el P&L), independiente del tab activo. Limit alto para sumar todo el rango.
  const { data: confirmedData } = useTransformations({
    skip: 0,
    limit: 1000,
    status: "confirmed",
    date_from: effectiveDateFrom || undefined,
    date_to: effectiveDateTo || undefined,
  });

  const pageCount = data ? Math.ceil(data.total / PAGE_SIZE) : 1;

  const kpis = useMemo(() => {
    const items = data?.items ?? [];
    const totalValue = items.reduce((sum, t) => sum + t.source_total_value, 0);
    const count = data?.total ?? 0;
    const totalWaste = items.reduce((sum, t) => sum + t.waste_quantity, 0);
    const confirmed = confirmedData?.items ?? [];
    const profitLoss = confirmed.reduce((sum, t) => sum + (t.value_difference ?? 0), 0);
    const wasteValue = confirmed.reduce((sum, t) => sum + (t.waste_value ?? 0), 0);
    return {
      total: { current_value: totalValue, previous_value: 0, change_percentage: null } as MetricCard,
      count: { current_value: count, previous_value: 0, change_percentage: null } as MetricCard,
      waste: { current_value: totalWaste, previous_value: 0, change_percentage: null } as MetricCard,
      profitLoss: { current_value: profitLoss, previous_value: 0, change_percentage: null } as MetricCard,
      wasteValue: { current_value: wasteValue, previous_value: 0, change_percentage: null } as MetricCard,
    };
  }, [data, confirmedData]);

  const handleExportAll = async () => {
    const all = await inventoryService.getTransformations({
      skip: 0,
      limit: 1000,
      status: statusFilter === "all" ? undefined : statusFilter,
      date_from: effectiveDateFrom || undefined,
      date_to: effectiveDateTo || undefined,
    });
    if (all.total > all.items.length) {
      toast.warning(`Excel limitado a ${all.items.length} filas. Hay ${all.total} en total — refina filtros para descargar todo.`);
    }
    return all.items;
  };

  const columns: ColumnDef<MaterialTransformationResponse, unknown>[] = [
    { accessorKey: "transformation_number", header: "#", cell: ({ row }) => <span className="font-medium">#{row.original.transformation_number}</span> },
    { accessorKey: "date", header: "Fecha", enableSorting: true, cell: ({ row }) => formatDate(row.original.date) },
    { accessorKey: "source_material_name", header: "Material Origen", cell: ({ row }) => `${row.original.source_material_code ?? ""} - ${row.original.source_material_name ?? ""}` },
    { accessorKey: "source_quantity", header: "Cantidad", enableSorting: true, cell: ({ row }) => <span className="tabular-nums">{row.original.source_quantity.toFixed(2)}</span> },
    { accessorKey: "waste_quantity", header: "Merma", cell: ({ row }) => <span className="tabular-nums text-orange-600">{row.original.waste_quantity.toFixed(2)}</span> },
    { accessorKey: "waste_value", header: "Pérdida Merma", enableSorting: true, cell: ({ row }) => row.original.waste_value > 0 ? <span className="tabular-nums text-red-600">{formatCurrency(row.original.waste_value)}</span> : <span className="text-slate-300">-</span> },
    { accessorKey: "source_total_value", header: "Valor", enableSorting: true, cell: ({ row }) => formatCurrency(row.original.source_total_value) },
    { accessorKey: "value_difference", header: "Ganancia/Pérdida", enableSorting: true, cell: ({ row }) => {
        const vd = row.original.value_difference;
        if (vd == null || Math.abs(vd) < 0.01) return <span className="text-slate-300">-</span>;
        return <span className={`tabular-nums font-medium ${vd > 0 ? "text-emerald-700" : "text-red-700"}`}>{formatCurrency(vd)}</span>;
      },
    },
    { accessorKey: "lines", header: "Destinos", cell: ({ row }) => <span>{row.original.lines.length} material(es)</span> },
    { accessorKey: "status", header: "Estado", cell: ({ row }) => <StatusBadge status={row.original.status} /> },
    {
      id: "actions",
      header: "",
      cell: ({ row }) => <ActionsCell transformation={row.original} onAnnul={(t) => { setAnnulTarget(t); setAnnulReason(""); }} />,
    },
  ];

  return (
    <div className="space-y-4">
      <PageHeader title="Transformaciones" description="Desintegracion de materiales compuestos">
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => navigate(ROUTES.INVENTORY)}>
            <ArrowLeft className="h-4 w-4 mr-2" />Stock
          </Button>
          {hasPermission("transformations.create") && (
            <Button onClick={() => navigate(ROUTES.INVENTORY_TRANSFORMATIONS_NEW)} className="bg-emerald-600 hover:bg-emerald-700">
              <Plus className="h-4 w-4 mr-2" />Nueva Transformacion
            </Button>
          )}
        </div>
      </PageHeader>

      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4">
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} className="h-[120px] rounded-lg" />
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4">
          <KpiCard
            label="Valor Transformado"
            metric={kpis.total}
            icon={<Calculator className="h-4 w-4" />}
            accentColor="sky"
          />
          <KpiCard
            label="Transformaciones"
            metric={kpis.count}
            icon={<Hash className="h-4 w-4" />}
            accentColor="violet"
            formatValue={(n) => String(n)}
          />
          <KpiCard
            label="Merma Total"
            metric={kpis.waste}
            icon={<Puzzle className="h-4 w-4" />}
            accentColor="amber"
            formatValue={(n) => n.toFixed(2) + " kg"}
          />
          <KpiCard
            label="Perdida por Merma (Confirmadas)"
            metric={kpis.wasteValue}
            icon={<Puzzle className="h-4 w-4" />}
            accentColor="rose"
          />
          <KpiCard
            label="Utilidad/Perdida (Confirmadas)"
            metric={kpis.profitLoss}
            icon={<TrendingUp className="h-4 w-4" />}
            accentColor={kpis.profitLoss.current_value >= 0 ? "emerald" : "rose"}
          />
        </div>
      )}

      <Tabs value={statusFilter} onValueChange={(v) => {
        setStatusFilter(v);
        setPage(0);
        // Preservar URL params existentes (date_from/date_to/etc).
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

      {hasUrlDateOverride && (
        <div className="flex items-center gap-2 flex-wrap">
          <span className="inline-flex items-center gap-1 bg-indigo-50 text-indigo-700 text-xs px-2 py-1 rounded border border-indigo-200">
            Rango: {formatDate(effectiveDateFrom)} – {formatDate(effectiveDateTo)}
            <button onClick={clearDateOverride} className="hover:bg-indigo-100 rounded px-1" aria-label="Limpiar override de fechas">×</button>
          </span>
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
        onRowClick={(row) => navigate(`/inventory/transformations/${row.id}`)}
        sorting={sorting}
        onSortingChange={onSortingChange}
        emptyTitle="Sin transformaciones"
        emptyDescription="No se encontraron transformaciones."
        exportFilename="ecobalance_transformaciones"
        onExportAll={handleExportAll}
        currencyColumns={["source_total_value", "waste_value", "value_difference"]}
        totalItems={data?.total}
        renderMobileCard={(t) => {
          const vd = t.value_difference;
          return (
            <OperationListCard
              operationNumber={t.transformation_number}
              date={t.date}
              partyLabel="Origen"
              partyName={`${t.source_material_code ?? ""} - ${t.source_material_name ?? ""}`}
              total={t.source_total_value}
              statusBadge={<StatusBadge status={t.status} />}
              cancelled={t.status === "annulled"}
              actions={<ActionsCell transformation={t} onAnnul={(tr) => { setAnnulTarget(tr); setAnnulReason(""); }} />}
              description={`${t.source_quantity.toFixed(2)} → ${t.lines.length} destino(s)`}
              extras={
                <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs">
                  {t.waste_quantity > 0 && (
                    <span><span className="text-slate-400">Merma:</span> <span className="tabular-nums text-orange-600">{t.waste_quantity.toFixed(2)}</span></span>
                  )}
                  {t.waste_value > 0 && (
                    <span><span className="text-slate-400">Perdida:</span> <span className="tabular-nums text-red-600">{formatCurrency(t.waste_value)}</span></span>
                  )}
                  {vd != null && Math.abs(vd) >= 0.01 && (
                    <span>
                      <span className="text-slate-400">Util:</span>{" "}
                      <span className={`tabular-nums font-medium ${vd > 0 ? "text-emerald-700" : "text-red-700"}`}>
                        {formatCurrency(vd)}
                      </span>
                    </span>
                  )}
                </div>
              }
            />
          );
        }}
        toolbar={
          <div className="flex flex-col sm:flex-row sm:items-center gap-2 sm:gap-3 w-full sm:w-auto">
            <SearchInput value={search} onChange={(v) => { setSearch(v); setPage(0); }} placeholder="Buscar transformacion..." />
            <DateRangePicker dateFrom={effectiveDateFrom} dateTo={effectiveDateTo} onDateFromChange={handleDateFromChange} onDateToChange={handleDateToChange} />
          </div>
        }
      />

      <ConfirmDialog
        open={!!annulTarget}
        onOpenChange={(open) => { if (!open) setAnnulTarget(null); }}
        title="Anular Transformacion"
        description={`Esta accion revertira los movimientos de inventario de la transformacion #${annulTarget?.transformation_number ?? ""}. No se puede deshacer.`}
        confirmLabel="Anular Transformacion"
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
