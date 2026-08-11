import { useMemo, useState } from "react";
import { useLocation, useNavigate, useSearchParams } from "react-router-dom";
import { type ColumnDef } from "@tanstack/react-table";
import { Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { PageHeader } from "@/components/shared/PageHeader";
import { DataTable } from "@/components/shared/DataTable";
import { DateRangePicker } from "@/components/shared/DateRangePicker";
import { EntitySelect } from "@/components/shared/EntitySelect";
import { SearchInput } from "@/components/shared/SearchInput";
import { ConfirmDialog } from "@/components/shared/ConfirmDialog";
import { OperationListCard } from "@/components/shared/OperationListCard";
import { usePermissions } from "@/hooks/usePermissions";
import { useSuppliers, useWarehouses } from "@/hooks/useMasterData";
import {
  useConfirmInboundOrder,
  useEntriesStatusCounts,
  useInboundOrders,
  useReviewInboundOrder,
} from "@/hooks/useInboundOrders";
import { saveScroll, useScrollRestoration } from "@/hooks/useScrollRestoration";
import { formatCurrency, formatDate, formatWeight } from "@/utils/formatters";
import { formatLinesTotalQuantity } from "@/utils/operationLines";
import { buildRoute, ROUTES } from "@/utils/constants";
import { cn } from "@/utils";
import {
  DISPLAY_STATUS_LABELS,
  INBOUND_TYPE_LABELS,
  WILLARD_INBOUND_TYPES,
  type InboundDisplayStatus,
  type InboundOrderResponse,
} from "@/types/inbound-order";

const PAGE_SIZE = 20;

const TABS: { value: string; label: string }[] = [
  { value: "all", label: "Todas" },
  { value: "registered", label: "Registradas" },
  { value: "reviewed", label: "Revisadas" },
  { value: "liquidated", label: "Liquidadas" },
  { value: "annulled", label: "Anuladas" },
];

// Estado UNICO visible (#93, columna-driven) — femenino para "entrada"
const DISPLAY_STATUS_STYLES: Record<InboundDisplayStatus, string> = {
  registered: "bg-yellow-100 text-yellow-800 border-yellow-200",
  reviewed: "bg-sky-100 text-sky-800 border-sky-200",
  liquidated: "bg-emerald-100 text-emerald-800 border-emerald-200",
  annulled: "bg-red-100 text-red-800 border-red-200",
};

export function EntradaStatusBadge({ status, className }: { status: InboundDisplayStatus; className?: string }) {
  return (
    <Badge variant="outline" className={cn(DISPLAY_STATUS_STYLES[status], className)}>
      {DISPLAY_STATUS_LABELS[status] ?? status}
    </Badge>
  );
}

const WORLD_LABELS: Record<string, string> = {
  drosses: "Drosses",
  postconsumo: "Postconsumo",
};

// Colores bien separados por tipo (feedback Daniel: indigo vs blue se confundian):
// compra azul · postconsumo violeta · drosses cian — sin chocar con los de estado
const WORLD_BADGE_STYLES: Record<string, string> = {
  postconsumo: "bg-violet-100 text-violet-800 border-violet-200",
  drosses: "bg-cyan-100 text-cyan-800 border-cyan-200",
};

export function EntradaTypeBadge({ order }: { order: InboundOrderResponse }) {
  const isWillard = WILLARD_INBOUND_TYPES.includes(order.inbound_type);
  if (isWillard) {
    const world = order.willard_world ? WORLD_LABELS[order.willard_world] ?? order.willard_world : null;
    const style = (order.willard_world && WORLD_BADGE_STYLES[order.willard_world]) ||
      "bg-violet-100 text-violet-800 border-violet-200";
    return (
      <Badge variant="outline" className={style}>
        {world ? `Willard · ${world}` : "Willard"}
      </Badge>
    );
  }
  return (
    <Badge variant="outline" className="bg-blue-100 text-blue-800 border-blue-200">
      {INBOUND_TYPE_LABELS[order.inbound_type] ?? order.inbound_type}
    </Badge>
  );
}

/** Dias desde la captura — semaforo de antiguedad para la bandeja (patron #68) */
function daysPending(createdAt: string): number {
  return Math.floor((Date.now() - new Date(createdAt).getTime()) / 86_400_000);
}

function AgingBadge({ createdAt }: { createdAt: string }) {
  const days = daysPending(createdAt);
  const color =
    days > 3 ? "bg-red-100 text-red-800" :
    days > 1 ? "bg-orange-100 text-orange-800" :
    "bg-amber-50 text-amber-700";
  return (
    <span className={cn("inline-flex px-2 py-0.5 rounded-full text-xs font-medium tabular-nums", color)}>
      {days === 0 ? "Hoy" : days === 1 ? "1 día" : `${days} días`}
    </span>
  );
}

/** Total $ de una entrada tipo compra: liquidada = Σ compras del reparto;
 *  pendiente = referencia capturada (puede ser 0 — #93 captura sin precios) */
function purchaseTotal(order: InboundOrderResponse): number {
  const live = order.purchases.filter((p) => p.status !== "cancelled");
  if (live.length > 0) return live.reduce((acc, p) => acc + p.total_amount, 0);
  return order.lines.reduce((acc, l) => acc + l.quantity * (l.unit_price ?? 0), 0);
}

/** #93: el tercero de una entrada tipo compra vive en el REPARTO —
 *  "Varios (N)" cuando hay más de un proveedor */
export function entradaPartyLabel(order: InboundOrderResponse): string {
  if (order.third_party_name) return order.third_party_name;
  const live = order.purchases.filter((p) => p.status !== "cancelled");
  if (live.length === 0) return order.display_status === "liquidated" ? "Sin proveedor" : "—";
  if (live.length === 1) return live[0].supplier_name ?? "—";
  return `Varios (${live.length})`;
}

export default function InboundOrdersPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const { hasPermission } = usePermissions();
  const canCreate = hasPermission("purchases.create");
  const canLiquidate = hasPermission("purchases.liquidate");
  const canReview = hasPermission("purchases.review");
  const canViewPrices = hasPermission("purchases.view_prices");

  const { data: warehousesData } = useWarehouses();
  const { data: suppliersData } = useSuppliers();
  const warehouses = warehousesData?.items ?? [];
  const suppliers = suppliersData?.items ?? [];

  const [searchParams, setSearchParams] = useSearchParams();
  const rawTab = searchParams.get("tab") ?? "all";
  const tab = TABS.some((t) => t.value === rawTab) ? rawTab : "all";
  const setTab = (v: string) => {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      if (v === "all") next.delete("tab");
      else next.set("tab", v);
      return next;
    }, { replace: true });
    setPage(0);
  };

  const [page, setPage] = useState(0);
  const [typeFilter, setTypeFilter] = useState("all");
  const [warehouseFilter, setWarehouseFilter] = useState("all");
  const [tpFilter, setTpFilter] = useState("all");
  const [search, setSearch] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");

  const isBandeja = tab === "registered" || tab === "reviewed";

  // Selector combinado tipo/mundo (feedback Daniel): "willard_postconsumo" y
  // "willard_drosses" mapean a inbound_type + willard_world
  const typeParams = useMemo(() => {
    if (typeFilter === "all") return {};
    if (typeFilter === "willard_postconsumo")
      return { inbound_type: "willard", willard_world: "postconsumo" as const };
    if (typeFilter === "willard_drosses")
      return { inbound_type: "willard", willard_world: "drosses" as const };
    return { inbound_type: typeFilter };
  }, [typeFilter]);

  const { data, isLoading } = useInboundOrders({
    skip: page * PAGE_SIZE,
    limit: PAGE_SIZE,
    ...typeParams,
    display_status: tab === "all" ? undefined : (tab as InboundDisplayStatus),
    search: search.trim() || undefined,
    warehouse_id: warehouseFilter === "all" ? undefined : warehouseFilter,
    third_party_id: tpFilter === "all" ? undefined : tpFilter,
    // Bandeja FIFO: la registrada mas vieja primero (Johana procesa en orden)
    sort: isBandeja ? "oldest" : "newest",
    date_from: dateFrom || undefined,
    date_to: dateTo || undefined,
  });

  const { registered: registeredCount, reviewed: reviewedCount } = useEntriesStatusCounts();
  const pendingCount = registeredCount + reviewedCount;

  useScrollRestoration(!isLoading);

  const pageCount = data ? Math.max(1, Math.ceil(data.total / PAGE_SIZE)) : 1;

  const goToDetail = (order: InboundOrderResponse) => {
    saveScroll(location.pathname + location.search);
    navigate(buildRoute(ROUTES.INBOUND_DETAIL, { id: order.id }));
  };

  // Liquidar desde la fila: willard = dialogo inline; compra #93 = reparto;
  // legacy 1:1 = formulario de la compra derivada (W-C1)
  const confirmOrder = useConfirmInboundOrder();
  const reviewOrder = useReviewInboundOrder();
  const [willardToLiquidate, setWillardToLiquidate] = useState<InboundOrderResponse | null>(null);

  const startLiquidate = (order: InboundOrderResponse) => {
    if (WILLARD_INBOUND_TYPES.includes(order.inbound_type)) {
      setWillardToLiquidate(order);
    } else if (order.purchase_id) {
      // Legacy 1:1 (ciclos B-D): su cara financiera es la compra derivada
      saveScroll(location.pathname + location.search);
      const returnTo = encodeURIComponent(location.pathname + location.search);
      navigate(`/purchases/${order.purchase_id}/liquidate?returnTo=${returnTo}`);
    } else {
      // #93: reparto de proveedores
      saveScroll(location.pathname + location.search);
      const returnTo = encodeURIComponent(location.pathname + location.search);
      navigate(`/inbound/${order.id}/liquidate?returnTo=${returnTo}`);
    }
  };

  const columns: ColumnDef<InboundOrderResponse, unknown>[] = useMemo(() => {
    const cols: ColumnDef<InboundOrderResponse, unknown>[] = [
      {
        accessorKey: "order_number",
        header: "#",
        cell: ({ row }) => <span className="font-medium tabular-nums">#{row.original.order_number}</span>,
      },
      {
        accessorKey: "date",
        header: "Fecha",
        cell: ({ row }) => formatDate(row.original.date),
      },
      {
        accessorKey: "inbound_type",
        header: "Tipo",
        cell: ({ row }) => <EntradaTypeBadge order={row.original} />,
      },
      {
        accessorKey: "third_party_name",
        header: "Tercero",
        cell: ({ row }) => <span className="font-medium">{entradaPartyLabel(row.original)}</span>,
      },
      { accessorKey: "warehouse_name", header: "Sede" },
      {
        // Patron Costa (feedback Daniel): codigo + cantidad por linea, apiladas
        id: "materiales",
        header: "Materiales",
        meta: { hideOnMobile: true },
        cell: ({ row }) => {
          const o = row.original;
          const showPrice = canViewPrices && !WILLARD_INBOUND_TYPES.includes(o.inbound_type);
          return (
            <div className="space-y-0.5">
              {o.lines.slice(0, 3).map((line) => (
                <div key={line.id} className="text-xs text-slate-600 whitespace-nowrap">
                  {line.material_code} - {formatWeight(line.quantity, line.material_unit)}
                  {showPrice && line.unit_price != null ? ` x ${formatCurrency(line.unit_price)}` : ""}
                </div>
              ))}
              {o.lines.length > 3 && (
                <div className="text-xs text-slate-400 whitespace-nowrap">
                  +{o.lines.length - 3} materiales más
                </div>
              )}
            </div>
          );
        },
      },
      {
        id: "cantidad",
        header: "Cant.",
        cell: ({ row }) => (
          <span className="tabular-nums">{formatLinesTotalQuantity(row.original.lines)}</span>
        ),
      },
      {
        id: "efecto",
        header: canViewPrices ? "Kg Plomo / Total $" : "Kg Plomo",
        cell: ({ row }) => {
          const o = row.original;
          if (WILLARD_INBOUND_TYPES.includes(o.inbound_type)) {
            return (
              <span className="font-medium tabular-nums text-emerald-700">
                {o.total_kg_lead != null ? `+${formatWeight(o.total_kg_lead)}` : "—"}
              </span>
            );
          }
          if (!canViewPrices) return <span className="text-slate-400 text-sm">—</span>;
          return (
            <span className="font-medium tabular-nums">{formatCurrency(purchaseTotal(o))}</span>
          );
        },
      },
      {
        accessorKey: "vehicle_plate",
        header: "Placa",
        cell: ({ row }) => (
          <span className="tabular-nums text-sm">
            {row.original.vehicle_plate ? row.original.vehicle_plate.toUpperCase() : "—"}
          </span>
        ),
      },
    ];

    if (isBandeja) {
      cols.push({
        id: "dias",
        header: "Días",
        cell: ({ row }) => <AgingBadge createdAt={row.original.created_at} />,
      });
    }

    cols.push({
      accessorKey: "display_status",
      header: "Estado",
      cell: ({ row }) => <EntradaStatusBadge status={row.original.display_status} />,
    });

    if (canLiquidate || canReview) {
      cols.push({
        id: "acciones",
        header: "",
        cell: ({ row }) => {
          const o = row.original;
          const isWillardRow = WILLARD_INBOUND_TYPES.includes(o.inbound_type);
          const isLegacyRow = !isWillardRow && !!o.purchase_id;
          // #93: compra nueva registrada -> Revisar; revisada -> Liquidar.
          // Willard/legacy conservan Liquidar directo desde registrada.
          if (o.display_status === "registered" && !isWillardRow && !isLegacyRow) {
            if (!canReview) return null;
            return (
              <Button
                size="sm"
                variant="outline"
                className="h-7 border-sky-200 text-sky-700 hover:bg-sky-50"
                disabled={reviewOrder.isPending}
                onClick={(e) => {
                  e.stopPropagation();
                  reviewOrder.mutate(o.id);
                }}
              >
                Revisar
              </Button>
            );
          }
          const liquidatable =
            (o.display_status === "registered" && (isWillardRow || isLegacyRow)) ||
            (o.display_status === "reviewed" && !isWillardRow && !isLegacyRow);
          if (!liquidatable || !canLiquidate) return null;
          return (
            <Button
              size="sm"
              variant="outline"
              className="h-7 border-emerald-200 text-emerald-700 hover:bg-emerald-50"
              onClick={(e) => {
                e.stopPropagation();
                startLiquidate(o);
              }}
            >
              Liquidar
            </Button>
          );
        },
      });
    }

    return cols;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [canLiquidate, canReview, canViewPrices, isBandeja, location.pathname, location.search, reviewOrder.isPending]);

  return (
    <div className="space-y-4">
      <PageHeader title="Entradas" description="Todas las entradas de material — compras y Willard en un solo lugar">
        {pendingCount > 0 && !isBandeja && (
          <Button
            variant="outline"
            onClick={() => setTab("registered")}
            className="border-amber-300 bg-amber-50 text-amber-800 hover:bg-amber-100 w-full sm:w-auto"
          >
            Por liquidar: {pendingCount}
          </Button>
        )}
        {canCreate && (
          <Button
            onClick={() => navigate(ROUTES.INBOUND_NEW)}
            className="bg-emerald-600 hover:bg-emerald-700 w-full sm:w-auto"
          >
            <Plus className="h-4 w-4 mr-2" />
            Nueva Entrada
          </Button>
        )}
      </PageHeader>

      <div className="overflow-x-auto -mx-3 px-3 sm:mx-0 sm:px-0">
        <Tabs value={tab} onValueChange={setTab}>
          <TabsList className="inline-flex w-max sm:w-auto">
            {TABS.map((t) => {
              const badge =
                t.value === "registered" ? registeredCount :
                t.value === "reviewed" ? reviewedCount : 0;
              const badgeColor = t.value === "registered" ? "bg-amber-500" : "bg-sky-500";
              return (
                <TabsTrigger key={t.value} value={t.value}>
                  {t.label}
                  {badge > 0 && (
                    <span className={cn(
                      "ml-1.5 min-w-[18px] h-[18px] px-1 rounded-full text-white text-[10px] font-semibold inline-flex items-center justify-center tabular-nums",
                      badgeColor,
                    )}>
                      {badge > 99 ? "99+" : badge}
                    </span>
                  )}
                </TabsTrigger>
              );
            })}
          </TabsList>
        </Tabs>
      </div>

      <DataTable
        columns={columns}
        data={data?.items ?? []}
        loading={isLoading}
        pageCount={pageCount}
        pageIndex={page}
        pageSize={PAGE_SIZE}
        onPageChange={setPage}
        totalItems={data?.total}
        onRowClick={goToDetail}
        emptyTitle={isBandeja ? "Nada por liquidar" : "Sin entradas"}
        emptyDescription={
          isBandeja
            ? "Todas las entradas están liquidadas — la bandeja está al día."
            : "No se encontraron entradas con los filtros actuales."
        }
        exportFilename="ecobalance_entradas"
        renderMobileCard={(o) => (
          <OperationListCard
            operationNumber={o.order_number}
            date={o.date}
            partyName={entradaPartyLabel(o)}
            statusBadge={<EntradaStatusBadge status={o.display_status} />}
            cancelled={o.display_status === "annulled"}
            description={`${
              o.lines.length > 0
                ? `${o.lines.map((l) => `${l.material_code} ${formatWeight(l.quantity, l.material_unit)}`).join(" · ")} — `
                : ""
            }${
              WILLARD_INBOUND_TYPES.includes(o.inbound_type)
                ? `Willard${o.willard_world ? ` · ${WORLD_LABELS[o.willard_world] ?? o.willard_world}` : ""}`
                : INBOUND_TYPE_LABELS[o.inbound_type] ?? o.inbound_type
            }${o.warehouse_name ? ` · ${o.warehouse_name}` : ""}${o.vehicle_plate ? ` · ${o.vehicle_plate.toUpperCase()}` : ""}`}
            extras={
              <span className="flex items-center gap-2">
                {WILLARD_INBOUND_TYPES.includes(o.inbound_type) ? (
                  <span className="text-[11px] font-medium tabular-nums text-emerald-700">
                    Plomo: {o.total_kg_lead != null ? `+${formatWeight(o.total_kg_lead)}` : "—"}
                  </span>
                ) : canViewPrices ? (
                  <span className="text-[11px] font-medium tabular-nums text-slate-700">
                    {formatCurrency(purchaseTotal(o))}
                  </span>
                ) : null}
                {isBandeja && <AgingBadge createdAt={o.created_at} />}
                {(() => {
                  const isWillardRow = WILLARD_INBOUND_TYPES.includes(o.inbound_type);
                  const isLegacyRow = !isWillardRow && !!o.purchase_id;
                  if (o.display_status === "registered" && !isWillardRow && !isLegacyRow) {
                    return canReview ? (
                      <Button
                        size="sm"
                        variant="outline"
                        className="h-6 px-2 text-[11px] border-sky-200 text-sky-700"
                        disabled={reviewOrder.isPending}
                        onClick={(e) => {
                          e.stopPropagation();
                          reviewOrder.mutate(o.id);
                        }}
                      >
                        Revisar
                      </Button>
                    ) : null;
                  }
                  const liquidatable =
                    (o.display_status === "registered" && (isWillardRow || isLegacyRow)) ||
                    (o.display_status === "reviewed" && !isWillardRow && !isLegacyRow);
                  return canLiquidate && liquidatable ? (
                    <Button
                      size="sm"
                      variant="outline"
                      className="h-6 px-2 text-[11px] border-emerald-200 text-emerald-700"
                      onClick={(e) => {
                        e.stopPropagation();
                        startLiquidate(o);
                      }}
                    >
                      Liquidar
                    </Button>
                  ) : null;
                })()}
              </span>
            }
          />
        )}
        toolbar={
          <div className="flex flex-col sm:flex-row sm:flex-wrap sm:items-center gap-2 sm:gap-3 w-full sm:w-auto">
            <SearchInput
              value={search}
              onChange={(v) => { setSearch(v); setPage(0); }}
              placeholder="Buscar #, placa, conductor, material..."
            />
            <Select value={typeFilter} onValueChange={(v) => { setTypeFilter(v); setPage(0); }}>
              <SelectTrigger className="w-full sm:w-48">
                <SelectValue placeholder="Todos los tipos" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Todos los tipos</SelectItem>
                <SelectItem value="purchase">Compra regular</SelectItem>
                <SelectItem value="willard">Willard (todos)</SelectItem>
                <SelectItem value="willard_postconsumo">Willard · Postconsumo</SelectItem>
                <SelectItem value="willard_drosses">Willard · Drosses</SelectItem>
              </SelectContent>
            </Select>
            <Select value={warehouseFilter} onValueChange={(v) => { setWarehouseFilter(v); setPage(0); }}>
              <SelectTrigger className="w-full sm:w-44">
                <SelectValue placeholder="Todas las sedes" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Todas las sedes</SelectItem>
                {warehouses.map((w) => (
                  <SelectItem key={w.id} value={w.id}>{w.name}</SelectItem>
                ))}
              </SelectContent>
            </Select>
            {/* Combobox con escritura (patron EntitySelect de los formularios —
                asi manejan terceros en toda la app); re-seleccionar limpia */}
            <div className="w-full sm:w-56">
              <EntitySelect
                value={tpFilter === "all" ? "" : tpFilter}
                onChange={(v) => { setTpFilter(v || "all"); setPage(0); }}
                options={suppliers.map((s) => ({ id: s.id, label: s.name }))}
                placeholder="Todos los terceros"
              />
            </div>
            <DateRangePicker
              dateFrom={dateFrom}
              dateTo={dateTo}
              onDateFromChange={(d) => { setDateFrom(d); setPage(0); }}
              onDateToChange={(d) => { setDateTo(d); setPage(0); }}
            />
          </div>
        }
      />

      {/* Liquidar willard desde la fila (verbo unico — el efecto es el confirm B.2) */}
      <ConfirmDialog
        open={!!willardToLiquidate}
        onOpenChange={(o) => { if (!o) setWillardToLiquidate(null); }}
        title={`Liquidar Entrada #${willardToLiquidate?.order_number ?? ""}`}
        description="El material entra al inventario y mueve el libro kg con la fórmula vigente (sin efecto financiero — entrada Willard)."
        confirmLabel="Liquidar"
        loading={confirmOrder.isPending}
        onConfirm={() => {
          if (!willardToLiquidate) return;
          confirmOrder.mutate(willardToLiquidate.id, {
            onSuccess: () => setWillardToLiquidate(null),
          });
        }}
      />
    </div>
  );
}
