import { useState, useMemo } from "react";
import { useDateFilter } from "@/stores/dateFilterStore";
import { useNavigate } from "react-router-dom";
import { type ColumnDef } from "@tanstack/react-table";
import { Plus, ArrowLeft, Calculator, Hash, Puzzle, MoreHorizontal, Eye, XCircle } from "lucide-react";
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
import { DateRangePicker } from "@/components/shared/DateRangePicker";
import { SearchInput } from "@/components/shared/SearchInput";
import { KpiCard } from "@/components/shared/KpiCard";
import { ConfirmDialog } from "@/components/shared/ConfirmDialog";
import { useTransformations, useAnnulTransformation } from "@/hooks/useInventory";
import { formatCurrency, formatDate } from "@/utils/formatters";
import { ROUTES } from "@/utils/constants";
import type { MaterialTransformationResponse } from "@/types/inventory";
import type { MetricCard } from "@/types/reports";

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
  const [page, setPage] = useState(0);
  const [statusFilter, setStatusFilter] = useState("all");
  const [search, setSearch] = useState("");
  const { dateFrom, dateTo, setDateFrom, setDateTo } = useDateFilter();
  const [annulTarget, setAnnulTarget] = useState<MaterialTransformationResponse | null>(null);
  const [annulReason, setAnnulReason] = useState("");
  const annulMutation = useAnnulTransformation();

  const { data, isLoading } = useTransformations({
    skip: page * PAGE_SIZE,
    limit: PAGE_SIZE,
    status: statusFilter === "all" ? undefined : statusFilter,
    date_from: dateFrom || undefined,
    date_to: dateTo || undefined,
  });

  const pageCount = data ? Math.ceil(data.total / PAGE_SIZE) : 1;

  const kpis = useMemo(() => {
    const items = data?.items ?? [];
    const totalValue = items.reduce((sum, t) => sum + t.source_total_value, 0);
    const count = data?.total ?? 0;
    const totalWaste = items.reduce((sum, t) => sum + t.waste_quantity, 0);
    return {
      total: { current_value: totalValue, previous_value: 0, change_percentage: null } as MetricCard,
      count: { current_value: count, previous_value: 0, change_percentage: null } as MetricCard,
      waste: { current_value: totalWaste, previous_value: 0, change_percentage: null } as MetricCard,
    };
  }, [data]);

  const columns: ColumnDef<MaterialTransformationResponse, unknown>[] = [
    { accessorKey: "transformation_number", header: "#", cell: ({ row }) => <span className="font-medium">#{row.original.transformation_number}</span> },
    { accessorKey: "date", header: "Fecha", enableSorting: true, cell: ({ row }) => formatDate(row.original.date) },
    { accessorKey: "source_material_name", header: "Material Origen", cell: ({ row }) => `${row.original.source_material_code ?? ""} - ${row.original.source_material_name ?? ""}` },
    { accessorKey: "source_quantity", header: "Cantidad", enableSorting: true, cell: ({ row }) => <span className="tabular-nums">{row.original.source_quantity.toFixed(2)}</span> },
    { accessorKey: "waste_quantity", header: "Merma", cell: ({ row }) => <span className="tabular-nums text-orange-600">{row.original.waste_quantity.toFixed(2)}</span> },
    { accessorKey: "source_total_value", header: "Valor", enableSorting: true, cell: ({ row }) => formatCurrency(row.original.source_total_value) },
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
          <Button onClick={() => navigate(ROUTES.INVENTORY_TRANSFORMATIONS_NEW)} className="bg-emerald-600 hover:bg-emerald-700">
            <Plus className="h-4 w-4 mr-2" />Nueva Transformacion
          </Button>
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
        </div>
      )}

      <Tabs value={statusFilter} onValueChange={(v) => { setStatusFilter(v); setPage(0); }}>
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
        onRowClick={(row) => navigate(`/inventory/transformations/${row.id}`)}
        emptyTitle="Sin transformaciones"
        emptyDescription="No se encontraron transformaciones."
        exportFilename="ecobalance_transformaciones"
        totalItems={data?.total}
        toolbar={
          <div className="flex items-center gap-3">
            <SearchInput value={search} onChange={(v) => { setSearch(v); setPage(0); }} placeholder="Buscar transformacion..." />
            <DateRangePicker dateFrom={dateFrom} dateTo={dateTo} onDateFromChange={setDateFrom} onDateToChange={setDateTo} />
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
