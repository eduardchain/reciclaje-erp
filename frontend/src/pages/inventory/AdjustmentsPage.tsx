import { useState, useMemo } from "react";
import { useDateFilter } from "@/stores/dateFilterStore";
import { useNavigate, useSearchParams } from "react-router-dom";
import { type ColumnDef } from "@tanstack/react-table";
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

  const { data, isLoading } = useAdjustments({
    skip: page * PAGE_SIZE,
    limit: PAGE_SIZE,
    status: statusFilter === "all" ? undefined : statusFilter,
    date_from: dateFrom || undefined,
    date_to: dateTo || undefined,
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

      <Tabs value={statusFilter} onValueChange={(v) => { setStatusFilter(v); setPage(0); setSearchParams(v === "all" ? {} : { tab: v }, { replace: true }); }}>
        <TabsList>
          <TabsTrigger value="all">Todos</TabsTrigger>
          <TabsTrigger value="confirmed">Confirmados</TabsTrigger>
          <TabsTrigger value="annulled">Anulados</TabsTrigger>
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
        onRowClick={(row) => navigate(`/inventory/adjustments/${row.id}`)}
        emptyTitle="Sin ajustes"
        emptyDescription="No se encontraron ajustes de inventario."
        exportFilename="ecobalance_ajustes-inventario"
        totalItems={data?.total}
        toolbar={
          <div className="flex items-center gap-3">
            <SearchInput value={search} onChange={(v) => { setSearch(v); setPage(0); }} placeholder="Buscar ajuste..." />
            <DateRangePicker dateFrom={dateFrom} dateTo={dateTo} onDateFromChange={setDateFrom} onDateToChange={setDateTo} />
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
