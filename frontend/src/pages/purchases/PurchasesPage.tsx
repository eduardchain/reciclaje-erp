import { useMemo } from "react";
import { useDateFilter } from "@/stores/dateFilterStore";
import { useNavigate, useSearchParams, useLocation } from "react-router-dom";
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
import { usePurchases, useCancelPurchase } from "@/hooks/usePurchases";
import { formatCurrency, formatDate, formatWeight } from "@/utils/formatters";
import { ROUTES } from "@/utils/constants";
import type { PurchaseResponse } from "@/types/purchase";
import type { MetricCard } from "@/types/reports";
import { useAuthStore } from "@/stores/authStore";
import { exportPurchasePDF } from "@/utils/pdfExport";
import { usePermissions } from "@/hooks/usePermissions";
import { ThirdPartyLink } from "@/components/shared/EntityLink";
import { saveScroll, useScrollRestoration } from "@/hooks/useScrollRestoration";
import { useState } from "react";

const PAGE_SIZE = 20;

function ActionsCell({ purchase }: { purchase: PurchaseResponse }) {
  const navigate = useNavigate();
  const location = useLocation();
  const [cancelOpen, setCancelOpen] = useState(false);
  const { organizationId, organizations } = useAuthStore();
  const orgName = organizations.find((o) => o.id === organizationId)?.name ?? "";
  const cancelMutation = useCancelPurchase();
  const { hasPermission } = usePermissions();

  const canEdit = purchase.status === "registered" && !purchase.double_entry_id && hasPermission("purchases.edit");
  const canLiquidate = purchase.status === "registered" && !purchase.double_entry_id && hasPermission("purchases.liquidate");
  const canCancel = (purchase.status === "registered" || purchase.status === "liquidated") && !purchase.double_entry_id && hasPermission("purchases.cancel");

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
          <DropdownMenuItem onClick={() => { saveScroll(currentUrl); navigate(`/purchases/${purchase.id}`); }}>
            <Eye className="h-4 w-4 mr-2" />
            Ver detalle
          </DropdownMenuItem>
          {canEdit && (
            <DropdownMenuItem onClick={() => { saveScroll(currentUrl); navigate(`/purchases/${purchase.id}/edit`); }}>
              <Pencil className="h-4 w-4 mr-2" />
              Editar
            </DropdownMenuItem>
          )}
          {canLiquidate && (
            <DropdownMenuItem onClick={() => { saveScroll(currentUrl); navigate(`/purchases/${purchase.id}/liquidate`); }}>
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
          <DropdownMenuItem onClick={() => exportPurchasePDF(purchase, orgName)}>
            <FileText className="h-4 w-4 mr-2" />
            Exportar PDF
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>

      {/* Dialog Cancelar */}
      <ConfirmDialog
        open={cancelOpen}
        onOpenChange={setCancelOpen}
        title="Cancelar Compra"
        description={
          purchase.status === "liquidated"
            ? `Esta accion cancelara la compra #${purchase.purchase_number}, revertira inventario y saldos del proveedor. No se puede deshacer.`
            : `Esta accion cancelara la compra #${purchase.purchase_number} y revertira los movimientos de inventario. No se puede deshacer.`
        }
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

function getColumns(canViewPrices: boolean): ColumnDef<PurchaseResponse, unknown>[] {
  return [
    {
      accessorKey: "purchase_number",
      header: "#",
      cell: ({ row }) => <span className="font-medium">#{row.original.purchase_number}</span>,
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
      accessorKey: "supplier_name",
      header: "PROVEEDOR",
      cell: ({ row }) => <ThirdPartyLink id={row.original.supplier_id}>{row.original.supplier_name}</ThirdPartyLink>,
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
    ...(canViewPrices ? [{
      accessorKey: "total_amount",
      header: "TOTAL",
      enableSorting: true,
      cell: ({ row }: { row: { original: PurchaseResponse } }) => (
        <span className="font-medium tabular-nums">{formatCurrency(row.original.total_amount)}</span>
      ),
    } as ColumnDef<PurchaseResponse, unknown>] : []),
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
      cell: ({ row }) => <ActionsCell purchase={row.original} />,
    },
  ];
}

export default function PurchasesPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const { hasPermission } = usePermissions();
  const canViewPrices = hasPermission("purchases.view_prices");
  const [searchParams, setSearchParams] = useSearchParams();
  const columns = useMemo(() => getColumns(canViewPrices), [canViewPrices]);
  const { dateFrom, dateTo, setDateFrom, setDateTo } = useDateFilter();

  const status = searchParams.get("tab") || "all";
  const page = parseInt(searchParams.get("page") || "0", 10);
  const search = searchParams.get("search") || "";

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

  const { data, isLoading } = usePurchases({
    skip: page * PAGE_SIZE,
    limit: PAGE_SIZE,
    status: status === "all" ? undefined : status,
    search: search || undefined,
    date_from: dateFrom || undefined,
    date_to: dateTo || undefined,
  });

  useScrollRestoration(!isLoading);

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

  const currentUrl = location.pathname + location.search;

  return (
    <div className="space-y-4">
      <PageHeader title="Compras" description="Gestion de compras de material">
        {hasPermission("purchases.create") && (
          <Button onClick={() => navigate(ROUTES.PURCHASES_NEW)} className="bg-emerald-600 hover:bg-emerald-700">
            <Plus className="h-4 w-4 mr-2" />
            Nueva Compra
          </Button>
        )}
      </PageHeader>

      {/* KPI Cards */}
      {isLoading ? (
        <div className={`grid grid-cols-1 ${canViewPrices ? "md:grid-cols-3" : "md:grid-cols-1"} gap-4`}>
          {Array.from({ length: canViewPrices ? 3 : 1 }).map((_, i) => (
            <Skeleton key={i} className="h-28 rounded-lg" />
          ))}
        </div>
      ) : (
        <div className={`grid grid-cols-1 ${canViewPrices ? "md:grid-cols-3" : "md:grid-cols-1"} gap-4`}>
          {canViewPrices && (
            <KpiCard
              label="Total Compras"
              metric={kpis.total}
              icon={<ShoppingCart className="h-4 w-4" />}
              accentColor="sky"
            />
          )}
          <KpiCard
            label="Operaciones"
            metric={kpis.count}
            icon={<Hash className="h-4 w-4" />}
            accentColor="violet"
            formatValue={(n) => String(n)}
          />
          {canViewPrices && (
            <KpiCard
              label="Promedio"
              metric={kpis.avg}
              icon={<Calculator className="h-4 w-4" />}
              accentColor="amber"
            />
          )}
        </div>
      )}

      <Tabs value={status} onValueChange={(v) => setParam({ tab: v, page: null, search: null })}>
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
        onPageChange={(p) => setParam({ page: p === 0 ? null : String(p) })}
        onRowClick={(row) => { saveScroll(currentUrl); navigate(`/purchases/${row.id}`); }}
        emptyTitle="Sin compras"
        emptyDescription="No se encontraron compras para los filtros seleccionados."
        exportFilename="ecobalance_compras"
        toolbar={
          <div className="flex items-center gap-3">
            <SearchInput value={search} onChange={(v) => setParam({ search: v, page: null })} placeholder="Buscar compra..." />
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
