import { useMemo } from "react";
import { useDateFilter } from "@/stores/dateFilterStore";
import { Link, useNavigate, useSearchParams, useLocation } from "react-router-dom";
import { type ColumnDef, type SortingState } from "@tanstack/react-table";
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
import { ResponsiveFilterBar } from "@/components/shared/ResponsiveFilterBar";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { KpiCard } from "@/components/shared/KpiCard";
import { ConfirmDialog } from "@/components/shared/ConfirmDialog";
import { LinkedPaymentChoice, type AnnulChoice } from "@/components/shared/LinkedPaymentChoice";
import { OperationListCard } from "@/components/shared/OperationListCard";
import { usePurchases, usePurchase, useCancelPurchase } from "@/hooks/usePurchases";
import { purchaseService } from "@/services/purchases";
import { formatCurrency, formatDate, formatWeight } from "@/utils/formatters";
import { formatLinesTotalQuantity } from "@/utils/operationLines";
import { fetchAllPages } from "@/utils/fetchAllPages";
import { ROUTES } from "@/utils/constants";
import type { PurchaseResponse } from "@/types/purchase";
import type { MetricCard } from "@/types/reports";
import { useAuthStore } from "@/stores/authStore";
import { exportPurchasePDF } from "@/utils/pdfExport";
import { exportPurchasesDetailExcel } from "@/utils/excelExport";
import { usePermissions } from "@/hooks/usePermissions";
import { useOrgSettings } from "@/hooks/useOrgSettings";
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
  const [annulChoice, setAnnulChoice] = useState<AnnulChoice>(null);
  const { hasPermission } = usePermissions();

  // Al abrir el dialogo de cancelacion de una liquidada, consultamos el pago enlazado
  // para ofrecer la misma eleccion que el detalle (decision #63). Sin fetch por fila.
  const isLiquidated = purchase.status === "liquidated";
  const linkedQuery = usePurchase(purchase.id, { enabled: cancelOpen && isLiquidated });
  const linkedPaymentTotal = linkedQuery.data?.linked_payment_total ?? 0;
  const linkedLoading = cancelOpen && isLiquidated && linkedQuery.isLoading;

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
        onOpenChange={(open) => {
          setCancelOpen(open);
          if (!open) setAnnulChoice(null);
        }}
        title="Cancelar Compra"
        description={`Esta accion cancelara la compra #${purchase.purchase_number} y revertira inventario y saldos del proveedor. No se puede deshacer.`}
        confirmLabel="Cancelar Compra"
        variant="destructive"
        onConfirm={() => {
          cancelMutation.mutate(
            { id: purchase.id, annulLinkedPayments: annulChoice === "annul" },
            {
              onSuccess: () => {
                setCancelOpen(false);
                setAnnulChoice(null);
              },
            },
          );
        }}
        loading={cancelMutation.isPending}
        disabled={linkedLoading || (linkedPaymentTotal > 0 && annulChoice === null)}
      >
        <LinkedPaymentChoice
          kind="purchase"
          amount={linkedPaymentTotal}
          value={annulChoice}
          onChange={setAnnulChoice}
        />
      </ConfirmDialog>
    </>
  );
}

function getColumns(canViewPrices: boolean): ColumnDef<PurchaseResponse, unknown>[] {
  return [
    {
      accessorKey: "purchase_number",
      header: "#",
      cell: ({ row }) => (
        <div>
          <span className="font-medium">#{row.original.purchase_number}</span>
          {row.original.inbound_order_number != null && row.original.inbound_order_id && (
            <Link
              to={`/inbound/${row.original.inbound_order_id}`}
              onClick={(e) => e.stopPropagation()}
              className="block text-[10px] text-indigo-600 hover:text-indigo-800 hover:underline whitespace-nowrap"
              title="Ver la entrada de origen"
            >
              Entrada #{row.original.inbound_order_number}
            </Link>
          )}
        </div>
      ),
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
      accessorKey: "supplier_name",
      header: "PROVEEDOR",
      cell: ({ row }) => <ThirdPartyLink id={row.original.supplier_id}>{row.original.supplier_name}</ThirdPartyLink>,
    },
    {
      id: "vehicle_plate",
      header: "PLACA",
      meta: { hideOnMobile: true },
      cell: ({ row }) =>
        row.original.vehicle_plate ? (
          <span className="text-xs uppercase whitespace-nowrap">{row.original.vehicle_plate}</span>
        ) : (
          <span className="text-slate-300">—</span>
        ),
    },
    {
      id: "items",
      header: "DETALLE",
      meta: { hideOnMobile: true },
      cell: ({ row }) => (
        <div className="space-y-0.5">
          {row.original.lines.slice(0, 3).map((line) => (
            <div key={line.id} className="text-xs text-slate-600 whitespace-nowrap">
              {line.material_code} - {formatWeight(line.quantity, line.material_unit)}{canViewPrices ? ` x ${formatCurrency(line.unit_price)}` : ""}
            </div>
          ))}
          {row.original.lines.length > 3 && (
            <div className="text-xs text-slate-400 whitespace-nowrap">
              +{row.original.lines.length - 3} materiales más
            </div>
          )}
        </div>
      ),
    },
    {
      id: "total_quantity",
      header: "CANT. TOTAL",
      meta: { hideOnMobile: true },
      cell: ({ row }) => (
        <span className="text-xs font-medium tabular-nums whitespace-nowrap text-slate-700">
          {formatLinesTotalQuantity(row.original.lines)}
        </span>
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
      cell: ({ row }) => <ActionsCell purchase={row.original} />,
    },
  ];
}

export default function PurchasesPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const { hasPermission } = usePermissions();
  const { flagEnabled } = useOrgSettings();
  const inboundOnly = flagEnabled("kg_ledger_enabled");
  const canViewPrices = hasPermission("purchases.view_prices");
  const [searchParams, setSearchParams] = useSearchParams();
  const columns = useMemo(() => getColumns(canViewPrices), [canViewPrices]);
  const { dateFrom, dateTo, setDateFrom, setDateTo } = useDateFilter();

  const status = searchParams.get("tab") || "all";
  const page = parseInt(searchParams.get("page") || "0", 10);
  const search = searchParams.get("search") || "";
  const sortField = searchParams.get("sort") || "";
  const sortDesc = searchParams.get("dir") !== "asc";
  const sorting: SortingState = sortField ? [{ id: sortField, desc: sortDesc }] : [];

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

  const { data, isLoading } = usePurchases({
    skip: page * PAGE_SIZE,
    limit: PAGE_SIZE,
    status: status === "all" ? undefined : status,
    search: search || undefined,
    date_from: dateFrom || undefined,
    date_to: dateTo || undefined,
    sort_by: sortField || undefined,
    sort_dir: sortField ? (sortDesc ? "desc" : "asc") : undefined,
  });

  useScrollRestoration(!isLoading);

  const pageCount = data ? Math.ceil(data.total / PAGE_SIZE) : 1;

  const kpis = useMemo(() => {
    // Sumas y count excluyen canceladas (paridad con P&L y "Total Compras" real).
    // `total` (con canceladas) sigue siendo el de paginacion del listado.
    const totalAmount = data?.total_amount_sum ?? 0;
    const count = data?.active_total ?? 0;
    const avg = count > 0 ? totalAmount / count : 0;
    return {
      total: { current_value: totalAmount, previous_value: 0, change_percentage: null } as MetricCard,
      count: { current_value: count, previous_value: 0, change_percentage: null } as MetricCard,
      avg: { current_value: avg, previous_value: 0, change_percentage: null } as MetricCard,
    };
  }, [data]);

  const currentUrl = location.pathname + location.search;

  // Export completo: pagina en lotes de 1000 (cap del backend por request)
  // hasta cubrir el total filtrado — sin el tope efectivo de 1000 filas.
  const handleExportAll = () =>
    fetchAllPages((skip, limit) =>
      purchaseService.getAll({
        skip,
        limit,
        status: status === "all" ? undefined : status,
        search: search || undefined,
        date_from: dateFrom || undefined,
        date_to: dateTo || undefined,
      }),
    );

  return (
    <div className="space-y-4">
      <PageHeader title="Compras" description="Gestion de compras de material">
        {/* Ciclo B (B1): canal unico — con kg_ledger la unica puerta de creacion
            es Recepcion; Compras queda como gestion/liquidacion */}
        {hasPermission("purchases.create") && !inboundOnly && (
          <Button onClick={() => navigate(ROUTES.PURCHASES_NEW)} className="bg-emerald-600 hover:bg-emerald-700">
            <Plus className="h-4 w-4 mr-2" />
            Nueva Compra
          </Button>
        )}
        {hasPermission("purchases.create") && inboundOnly && (
          <Button onClick={() => navigate(ROUTES.INBOUND_NEW)} className="bg-emerald-600 hover:bg-emerald-700">
            <Plus className="h-4 w-4 mr-2" />
            Nueva Entrada
          </Button>
        )}
      </PageHeader>

      {/* KPI Cards */}
      {isLoading ? (
        <div className={`grid ${canViewPrices ? "grid-cols-2 md:grid-cols-3" : "grid-cols-1"} gap-4`}>
          {Array.from({ length: canViewPrices ? 3 : 1 }).map((_, i) => (
            <Skeleton key={i} className="h-28 rounded-lg" />
          ))}
        </div>
      ) : (
        <div className={`grid ${canViewPrices ? "grid-cols-2 md:grid-cols-3" : "grid-cols-1"} gap-4`}>
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
        sorting={sorting}
        onSortingChange={onSortingChange}
        emptyTitle="Sin compras"
        emptyDescription="No se encontraron compras para los filtros seleccionados."
        exportFilename="ecobalance_compras"
        onExportAll={handleExportAll}
        currencyColumns={["total_amount"]}
        exportOverride={(rows) => exportPurchasesDetailExcel(rows, { canViewPrices })}
        renderMobileCard={(p) => (
          <OperationListCard
            operationNumber={p.purchase_number}
            date={p.date}
            invoiceNumber={p.invoice_number}
            partyLabel="Proveedor"
            partyName={p.supplier_name}
            total={canViewPrices ? p.total_amount : undefined}
            statusBadge={<StatusBadge status={p.status} />}
            cancelled={p.status === "cancelled"}
            actions={<ActionsCell purchase={p} />}
            plate={p.vehicle_plate}
            totalQuantity={p.lines.length > 0 ? formatLinesTotalQuantity(p.lines) : undefined}
            description={p.lines.length > 0 ? p.lines.map((l) => `${l.material_code} ${formatWeight(l.quantity, l.material_unit)}`).join(" · ") : undefined}
            extras={
              p.double_entry_id ? (
                <span className="bg-emerald-100 text-emerald-700 text-[10px] px-1.5 py-0.5 rounded font-medium">Pasa Mano</span>
              ) : p.inbound_order_number != null ? (
                <span className="bg-indigo-100 text-indigo-700 text-[10px] px-1.5 py-0.5 rounded font-medium">
                  Entrada #{p.inbound_order_number}
                </span>
              ) : undefined
            }
          />
        )}
        toolbar={
          <ResponsiveFilterBar>
            <SearchInput value={search} onChange={(v) => setParam({ search: v, page: null })} placeholder="Buscar por #, proveedor, placa o factura..." />
            <DateRangePicker
              dateFrom={dateFrom}
              dateTo={dateTo}
              onDateFromChange={setDateFrom}
              onDateToChange={setDateTo}
            />
          </ResponsiveFilterBar>
        }
      />
    </div>
  );
}
