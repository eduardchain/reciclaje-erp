import { useMemo } from "react";
import { toast } from "sonner";
import { useDateFilter } from "@/stores/dateFilterStore";
import { useNavigate, useSearchParams, useLocation } from "react-router-dom";
import { type ColumnDef, type SortingState } from "@tanstack/react-table";
import { Plus, Wallet, Hash, Paperclip } from "lucide-react";
import { moneyMovementService } from "@/services/moneyMovements";
import { Button } from "@/components/ui/button";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { PageHeader } from "@/components/shared/PageHeader";
import { DataTable } from "@/components/shared/DataTable";
import { DateRangePicker } from "@/components/shared/DateRangePicker";
import { ResponsiveFilterBar } from "@/components/shared/ResponsiveFilterBar";
import { SearchInput } from "@/components/shared/SearchInput";
import { KpiCard } from "@/components/shared/KpiCard";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { useMoneyMovements } from "@/hooks/useMoneyMovements";
import { formatCurrency, formatDate } from "@/utils/formatters";
import { ROUTES } from "@/utils/constants";
import type { MoneyMovementResponse, MoneyMovementType } from "@/types/money-movement";
import type { MetricCard } from "@/types/reports";
import { usePermissions } from "@/hooks/usePermissions";
import { ThirdPartyLink, AccountLink } from "@/components/shared/EntityLink";
import { MovementListCard } from "@/components/shared/MovementListCard";
import { saveScroll, useScrollRestoration } from "@/hooks/useScrollRestoration";

// Tipos que representan entrada de dinero/credito (verde). El resto se considera salida (rojo).
const INFLOW_TYPES = new Set<MoneyMovementType>([
  "collection_from_client",
  "service_income",
  "capital_injection",
  "advance_collection",
  "transfer_in",
  "collection_from_generic",
  "tp_transfer_in",
  "tp_adjustment_credit",
  "obligation_disbursement",
  "loan_interest_accrual",
  "loan_interest_collection",
  "loan_capital_collection",
]);

const PAGE_SIZE = 20;

const typeLabels: Record<MoneyMovementType, string> = {
  payment_to_supplier: "Pago Proveedor",
  collection_from_client: "Cobro Cliente",
  expense: "Gasto",
  service_income: "Ingreso Servicio",
  transfer_out: "Transferencia Salida",
  transfer_in: "Transferencia Entrada",
  capital_injection: "Aporte Capital",
  capital_return: "Devolucion Capital",
  commission_payment: "Pago Comision",
  provision_deposit: "Deposito Provision",
  provision_expense: "Gasto Provision",
  advance_payment: "Anticipo Proveedor",
  advance_collection: "Anticipo Cliente",
  asset_payment: "Pago Activo Fijo",
  asset_purchase: "Compra Activo (Crédito)",
  asset_revaluation_payment: "Revalorización Activo (Pago)",
  asset_revaluation_credit: "Revalorización Activo (Crédito)",
  asset_devaluation_collection: "Devaluación Activo (Reembolso)",
  asset_devaluation_receivable: "Devaluación Activo (Por Cobrar)",
  obligation_disbursement: "Desembolso Obligación",
  obligation_interest_accrual: "Interés Causado (Obligación)",
  obligation_interest_payment: "Pago Intereses Obligación",
  obligation_capital_payment: "Abono Capital Obligación",
  loan_disbursement: "Desembolso Préstamo",
  loan_interest_accrual: "Interés Causado (Préstamo)",
  loan_interest_collection: "Recaudo Intereses Préstamo",
  loan_capital_collection: "Recaudo Capital Préstamo",
  expense_accrual: "Gasto Causado (Pasivo)",
  deferred_funding: "Pago Gasto Diferido",
  deferred_expense: "Cuota Gasto Diferido",
  commission_accrual: "Comisión Causada",
  depreciation_expense: "Depreciación Activo",
  profit_distribution: "Repartición Utilidades",
  payment_to_generic: "Pago Genérico",
  collection_from_generic: "Cobro Genérico",
  tp_transfer_out: "Cruce Terceros (Origen)",
  tp_transfer_in: "Cruce Terceros (Destino)",
  tp_adjustment_credit: "Ajuste Saldo (Credito)",
  tp_adjustment_debit: "Ajuste Saldo (Debito)",
};

const typeColors: Record<string, string> = {
  payment_to_supplier: "bg-red-100 text-red-800",
  collection_from_client: "bg-emerald-100 text-emerald-800",
  expense: "bg-orange-100 text-orange-800",
  service_income: "bg-blue-100 text-blue-800",
  transfer_out: "bg-purple-100 text-purple-800",
  transfer_in: "bg-purple-100 text-purple-800",
  capital_injection: "bg-teal-100 text-teal-800",
  capital_return: "bg-yellow-100 text-yellow-800",
  commission_payment: "bg-pink-100 text-pink-800",
  provision_deposit: "bg-violet-100 text-violet-800",
  provision_expense: "bg-amber-100 text-amber-800",
  asset_payment: "bg-slate-100 text-slate-800",
  asset_purchase: "bg-slate-100 text-slate-800",
  asset_revaluation_payment: "bg-indigo-100 text-indigo-800",
  asset_revaluation_credit: "bg-indigo-100 text-indigo-800",
  asset_devaluation_collection: "bg-indigo-100 text-indigo-800",
  asset_devaluation_receivable: "bg-indigo-100 text-indigo-800",
  obligation_disbursement: "bg-sky-100 text-sky-800",
  obligation_interest_accrual: "bg-sky-100 text-sky-800",
  obligation_interest_payment: "bg-sky-100 text-sky-800",
  obligation_capital_payment: "bg-sky-100 text-sky-800",
  loan_disbursement: "bg-sky-100 text-sky-800",
  loan_interest_accrual: "bg-sky-100 text-sky-800",
  loan_interest_collection: "bg-sky-100 text-sky-800",
  loan_capital_collection: "bg-sky-100 text-sky-800",
  expense_accrual: "bg-rose-100 text-rose-800",
  deferred_funding: "bg-indigo-100 text-indigo-800",
  deferred_expense: "bg-cyan-100 text-cyan-800",
  commission_accrual: "bg-pink-100 text-pink-800",
  depreciation_expense: "bg-amber-100 text-amber-800",
  profit_distribution: "bg-emerald-100 text-emerald-800",
  payment_to_generic: "bg-orange-100 text-orange-800",
  collection_from_generic: "bg-teal-100 text-teal-800",
  tp_transfer_out: "bg-purple-100 text-purple-800",
  tp_transfer_in: "bg-purple-100 text-purple-800",
  tp_adjustment_credit: "bg-orange-100 text-orange-800",
  tp_adjustment_debit: "bg-orange-100 text-orange-800",
};

const columns: ColumnDef<MoneyMovementResponse, unknown>[] = [
  { accessorKey: "movement_number", header: "#", cell: ({ row }) => <span className="font-medium">#{row.original.movement_number}</span> },
  { accessorKey: "date", header: "Fecha", enableSorting: true, cell: ({ row }) => formatDate(row.original.date) },
  { accessorKey: "movement_type", header: "Tipo", cell: ({ row }) => <Badge variant="outline" className={typeColors[row.original.movement_type] ?? ""}>{typeLabels[row.original.movement_type] ?? row.original.movement_type}</Badge> },
  { accessorKey: "description", header: "Descripcion", meta: { hideOnMobile: true }, cell: ({ row }) => (
    <span className="flex items-center gap-1.5">
      {row.original.description}
      {row.original.evidence_url && <Paperclip className="h-3.5 w-3.5 text-slate-400 shrink-0" />}
    </span>
  ) },
  { accessorKey: "amount", header: "Monto", enableSorting: true, cell: ({ row }) => <span className="font-medium tabular-nums">{formatCurrency(row.original.amount)}</span> },
  { accessorKey: "account_name", header: "Cuenta", meta: { hideOnMobile: true }, cell: ({ row }) => <AccountLink id={row.original.account_id}>{row.original.account_name ?? "-"}</AccountLink> },
  { accessorKey: "third_party_name", header: "Tercero", meta: { hideOnMobile: true }, cell: ({ row }) => <ThirdPartyLink id={row.original.third_party_id}>{row.original.third_party_name ?? "-"}</ThirdPartyLink> },
  { accessorKey: "status", header: "Estado", meta: { hideOnMobile: true }, cell: ({ row }) => <StatusBadge status={row.original.status} /> },
];

export default function TreasuryPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const [searchParams, setSearchParams] = useSearchParams();
  const { hasPermission } = usePermissions();
  const { dateFrom, dateTo, setDateFrom, setDateTo } = useDateFilter();

  const typeFilter = searchParams.get("tab") || "all";
  const page = parseInt(searchParams.get("page") || "0", 10);
  const search = searchParams.get("search") || "";
  const statusFromUrl = searchParams.get("status") || undefined;
  const adjustmentClassFromUrl = searchParams.get("adjustment_class") as "gain" | "loss" | null;
  const commissionSourceFromUrl = searchParams.get("commission_source") as "sale" | "double_entry" | null;
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

  const clearDateOverride = () => {
    if (hasUrlDateOverride) setParam({ date_from: null, date_to: null });
  };
  const handleDateFromChange = (v: string) => { setDateFrom(v); clearDateOverride(); };
  const handleDateToChange = (v: string) => { setDateTo(v); clearDateOverride(); };

  const onSortingChange = (next: SortingState) => {
    setParam({
      sort: next.length > 0 ? next[0].id : null,
      dir: next.length > 0 ? (next[0].desc ? null : "asc") : null,
    });
  };

  // Tab compuesto `tp_adjustment` mapea a CSV de tipos
  const movementTypeQuery = typeFilter === "all"
    ? undefined
    : typeFilter === "tp_adjustment"
      ? "tp_adjustment_credit,tp_adjustment_debit"
      : typeFilter;

  const { data, isLoading } = useMoneyMovements({
    skip: page * PAGE_SIZE,
    limit: PAGE_SIZE,
    movement_type: movementTypeQuery,
    date_from: effectiveDateFrom || undefined,
    date_to: effectiveDateTo || undefined,
    search: search || undefined,
    status: statusFromUrl,
    adjustment_class: adjustmentClassFromUrl || undefined,
    commission_source: commissionSourceFromUrl || undefined,
    sort_by: sortField || undefined,
    sort_dir: sortField ? (sortDesc ? "desc" : "asc") : undefined,
  });

  useScrollRestoration(!isLoading);

  const pageCount = data ? Math.ceil(data.total / PAGE_SIZE) : 1;

  const kpis = useMemo(() => {
    // Suma sobre TODO el set filtrado (no solo la pagina actual) — paridad con P&L.
    const totalAmount = data?.total_amount_sum ?? 0;
    const count = data?.total ?? 0;
    return {
      total: { current_value: totalAmount, previous_value: 0, change_percentage: null } as MetricCard,
      count: { current_value: count, previous_value: 0, change_percentage: null } as MetricCard,
    };
  }, [data]);

  const currentUrl = location.pathname + location.search;

  const handleExportAll = async () => {
    const all = await moneyMovementService.getAll({
      skip: 0,
      limit: 10000,
      movement_type: movementTypeQuery,
      date_from: effectiveDateFrom || undefined,
      date_to: effectiveDateTo || undefined,
      search: search || undefined,
      status: statusFromUrl,
      adjustment_class: adjustmentClassFromUrl || undefined,
      commission_source: commissionSourceFromUrl || undefined,
    });
    if (all.total > all.items.length) {
      toast.warning(`Excel limitado a ${all.items.length} filas. Hay ${all.total} en total — refina filtros para descargar todo.`);
    }
    return all.items;
  };

  return (
    <div className="space-y-4">
      <PageHeader title="Tesoreria" description="Movimientos de dinero">
        {hasPermission("treasury.create_movements") && (
          <Button onClick={() => navigate(ROUTES.TREASURY_NEW)} className="bg-emerald-600 hover:bg-emerald-700">
            <Plus className="h-4 w-4 mr-2" />Nuevo Movimiento
          </Button>
        )}
      </PageHeader>

      {isLoading ? (
        <div className="grid grid-cols-2 gap-4">
          {Array.from({ length: 2 }).map((_, i) => (
            <Skeleton key={i} className="h-[120px] rounded-lg" />
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-2 gap-4">
          <KpiCard
            label="Total Movimientos"
            metric={kpis.total}
            icon={<Wallet className="h-4 w-4" />}
            accentColor="sky"
          />
          <KpiCard
            label="Operaciones"
            metric={kpis.count}
            icon={<Hash className="h-4 w-4" />}
            accentColor="violet"
            formatValue={(n) => String(n)}
          />
        </div>
      )}

      <Tabs value={typeFilter} onValueChange={(v) => setParam({ tab: v, page: null, search: null, status: null, adjustment_class: null, commission_source: null })}>
        <div className="overflow-x-auto -mx-3 px-3 sm:mx-0 sm:px-0">
          <TabsList className="inline-flex w-max sm:flex sm:w-auto sm:flex-wrap sm:h-auto">
            <TabsTrigger value="all">Todos</TabsTrigger>
            <TabsTrigger value="payment_to_supplier">Pagos</TabsTrigger>
            <TabsTrigger value="collection_from_client">Cobros</TabsTrigger>
            <TabsTrigger value="expense">Gastos</TabsTrigger>
            <TabsTrigger value="transfer_out">Transf.</TabsTrigger>
            <TabsTrigger value="provision_deposit">Dep. Provisiones</TabsTrigger>
            <TabsTrigger value="service_income">Ing. Servicios</TabsTrigger>
            <TabsTrigger value="provision_expense">Gasto Provisión</TabsTrigger>
            <TabsTrigger value="expense_accrual">Causaciones</TabsTrigger>
            <TabsTrigger value="deferred_expense">Diferidos</TabsTrigger>
            <TabsTrigger value="depreciation_expense">Depreciación</TabsTrigger>
            <TabsTrigger value="commission_accrual">Comisiones</TabsTrigger>
            <TabsTrigger value="obligation_interest_accrual">Int. Obligaciones</TabsTrigger>
            <TabsTrigger value="loan_interest_accrual">Int. Préstamos</TabsTrigger>
            <TabsTrigger value="tp_adjustment">Aj. Terceros</TabsTrigger>
          </TabsList>
        </div>
      </Tabs>

      {/* Filtros activos del drill-down de P&L */}
      {(statusFromUrl || adjustmentClassFromUrl || commissionSourceFromUrl || hasUrlDateOverride) && (
        <div className="flex items-center gap-2 flex-wrap">
          {hasUrlDateOverride && (
            <span className="inline-flex items-center gap-1 bg-indigo-50 text-indigo-700 text-xs px-2 py-1 rounded border border-indigo-200">
              Rango: {formatDate(effectiveDateFrom)} – {formatDate(effectiveDateTo)}
              <button onClick={clearDateOverride} className="hover:bg-indigo-100 rounded px-1" aria-label="Limpiar override de fechas">×</button>
            </span>
          )}
          {statusFromUrl && (
            <span className="inline-flex items-center gap-1 bg-emerald-50 text-emerald-700 text-xs px-2 py-1 rounded border border-emerald-200">
              Estado: {statusFromUrl === "confirmed" ? "Confirmados" : statusFromUrl}
              <button onClick={() => setParam({ status: null })} className="hover:bg-emerald-100 rounded px-1">×</button>
            </span>
          )}
          {adjustmentClassFromUrl === "gain" && (
            <span className="inline-flex items-center gap-1 bg-emerald-50 text-emerald-700 text-xs px-2 py-1 rounded border border-emerald-200">
              Ganancia
              <button onClick={() => setParam({ adjustment_class: null })} className="hover:bg-emerald-100 rounded px-1">×</button>
            </span>
          )}
          {adjustmentClassFromUrl === "loss" && (
            <span className="inline-flex items-center gap-1 bg-red-50 text-red-700 text-xs px-2 py-1 rounded border border-red-200">
              Pérdida
              <button onClick={() => setParam({ adjustment_class: null })} className="hover:bg-red-100 rounded px-1">×</button>
            </span>
          )}
          {commissionSourceFromUrl === "sale" && (
            <span className="inline-flex items-center gap-1 bg-violet-50 text-violet-700 text-xs px-2 py-1 rounded border border-violet-200">
              Origen: Ventas
              <button onClick={() => setParam({ commission_source: null })} className="hover:bg-violet-100 rounded px-1">×</button>
            </span>
          )}
          {commissionSourceFromUrl === "double_entry" && (
            <span className="inline-flex items-center gap-1 bg-violet-50 text-violet-700 text-xs px-2 py-1 rounded border border-violet-200">
              Origen: Pasa Mano
              <button onClick={() => setParam({ commission_source: null })} className="hover:bg-violet-100 rounded px-1">×</button>
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
        onPageChange={(p) => setParam({ page: p === 0 ? null : String(p) })}
        onRowClick={(row) => { saveScroll(currentUrl); navigate(`/treasury/${row.id}`); }}
        sorting={sorting}
        onSortingChange={onSortingChange}
        emptyTitle="Sin movimientos"
        emptyDescription="No se encontraron movimientos de tesoreria."
        exportFilename="ecobalance_movimientos-tesoreria"
        onExportAll={handleExportAll}
        currencyColumns={["amount"]}
        totalItems={data?.total}
        renderMobileCard={(m) => (
          <MovementListCard
            date={m.date}
            typeLabel={typeLabels[m.movement_type] ?? m.movement_type}
            movementNumber={m.movement_number}
            amount={m.amount}
            isInflow={INFLOW_TYPES.has(m.movement_type)}
            description={m.description}
            thirdPartyName={m.third_party_name ?? (m.account_name ?? undefined)}
            annulled={m.status === "annulled"}
          />
        )}
        toolbar={
          <ResponsiveFilterBar>
            <SearchInput value={search} onChange={(v) => setParam({ search: v, page: null })} placeholder="Buscar movimiento..." />
            <DateRangePicker dateFrom={effectiveDateFrom} dateTo={effectiveDateTo} onDateFromChange={handleDateFromChange} onDateToChange={handleDateToChange} />
          </ResponsiveFilterBar>
        }
      />
    </div>
  );
}
