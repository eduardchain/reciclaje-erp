import { useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
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
import { PageHeader } from "@/components/shared/PageHeader";
import { DataTable } from "@/components/shared/DataTable";
import { DateRangePicker } from "@/components/shared/DateRangePicker";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { OperationListCard } from "@/components/shared/OperationListCard";
import { PurchaseLink } from "@/components/shared/EntityLink";
import { usePermissions } from "@/hooks/usePermissions";
import { useInboundOrders } from "@/hooks/useInboundOrders";
import { saveScroll, useScrollRestoration } from "@/hooks/useScrollRestoration";
import { formatDate, formatWeight } from "@/utils/formatters";
import { buildRoute, ROUTES } from "@/utils/constants";
import {
  INBOUND_TYPE_LABELS,
  WILLARD_INBOUND_TYPES,
  type InboundOrderResponse,
  type InboundType,
} from "@/types/inbound-order";

const PAGE_SIZE = 20;

const typeBadgeColors: Record<InboundType, string> = {
  purchase: "bg-blue-100 text-blue-800",
  willard: "bg-indigo-100 text-indigo-800",
};

function TypeBadge({ type }: { type: InboundType }) {
  return (
    <Badge variant="outline" className={typeBadgeColors[type] ?? ""}>
      {INBOUND_TYPE_LABELS[type] ?? type}
    </Badge>
  );
}

export default function InboundOrdersPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const { hasPermission } = usePermissions();
  const canCreate = hasPermission("purchases.create");

  const [page, setPage] = useState(0);
  const [typeFilter, setTypeFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState("all");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");

  const { data, isLoading } = useInboundOrders({
    skip: page * PAGE_SIZE,
    limit: PAGE_SIZE,
    inbound_type: typeFilter === "all" ? undefined : typeFilter,
    status: statusFilter === "all" ? undefined : (statusFilter as "confirmed" | "annulled"),
    date_from: dateFrom || undefined,
    date_to: dateTo || undefined,
  });

  useScrollRestoration(!isLoading);

  const pageCount = data ? Math.max(1, Math.ceil(data.total / PAGE_SIZE)) : 1;

  const goToDetail = (order: InboundOrderResponse) => {
    saveScroll(location.pathname + location.search);
    navigate(buildRoute(ROUTES.INBOUND_DETAIL, { id: order.id }));
  };

  const columns: ColumnDef<InboundOrderResponse, unknown>[] = [
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
      cell: ({ row }) => <TypeBadge type={row.original.inbound_type} />,
    },
    {
      accessorKey: "third_party_name",
      header: "Tercero",
      cell: ({ row }) => <span className="font-medium">{row.original.third_party_name ?? "—"}</span>,
    },
    { accessorKey: "warehouse_name", header: "Sede" },
    {
      id: "efecto",
      header: "Kg Plomo / Compra",
      cell: ({ row }) => {
        const o = row.original;
        if (WILLARD_INBOUND_TYPES.includes(o.inbound_type)) {
          return (
            <span className="font-medium tabular-nums text-emerald-700">
              {o.total_kg_lead != null ? `+${formatWeight(o.total_kg_lead)}` : "—"}
            </span>
          );
        }
        if (o.purchase_id) {
          return (
            <PurchaseLink id={o.purchase_id}>Compra #{o.purchase_number}</PurchaseLink>
          );
        }
        return <span className="text-slate-400 text-sm">—</span>;
      },
    },
    {
      accessorKey: "status",
      header: "Estado",
      cell: ({ row }) => <StatusBadge status={row.original.status} />,
    },
  ];

  return (
    <div className="space-y-4">
      <PageHeader title="Recepción" description="Órdenes de entrada de material — captura en patio">
        {canCreate && (
          <Button
            onClick={() => navigate(ROUTES.INBOUND_NEW)}
            className="bg-emerald-600 hover:bg-emerald-700 w-full sm:w-auto"
          >
            <Plus className="h-4 w-4 mr-2" />
            Nueva Recepción
          </Button>
        )}
      </PageHeader>

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
        emptyTitle="Sin recepciones"
        emptyDescription="No se encontraron órdenes de recepción con los filtros actuales."
        exportFilename="ecobalance_recepciones"
        renderMobileCard={(o) => (
          <OperationListCard
            operationNumber={o.order_number}
            date={o.date}
            partyName={o.third_party_name ?? "—"}
            statusBadge={<StatusBadge status={o.status} />}
            cancelled={o.status === "annulled"}
            description={`${INBOUND_TYPE_LABELS[o.inbound_type] ?? o.inbound_type}${o.warehouse_name ? ` · ${o.warehouse_name}` : ""}`}
            extras={
              WILLARD_INBOUND_TYPES.includes(o.inbound_type) ? (
                <span className="text-[11px] font-medium tabular-nums text-emerald-700">
                  Plomo: {o.total_kg_lead != null ? `+${formatWeight(o.total_kg_lead)}` : "—"}
                </span>
              ) : o.purchase_number != null ? (
                <span className="text-[11px] text-slate-600">Compra #{o.purchase_number}</span>
              ) : undefined
            }
          />
        )}
        toolbar={
          <div className="flex flex-col sm:flex-row sm:flex-wrap sm:items-center gap-2 sm:gap-3 w-full sm:w-auto">
            <Select value={typeFilter} onValueChange={(v) => { setTypeFilter(v); setPage(0); }}>
              <SelectTrigger className="w-full sm:w-52">
                <SelectValue placeholder="Todos los tipos" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Todos los tipos</SelectItem>
                {(Object.keys(INBOUND_TYPE_LABELS) as InboundType[]).map((t) => (
                  <SelectItem key={t} value={t}>{INBOUND_TYPE_LABELS[t]}</SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select value={statusFilter} onValueChange={(v) => { setStatusFilter(v); setPage(0); }}>
              <SelectTrigger className="w-full sm:w-40">
                <SelectValue placeholder="Todos" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Todos</SelectItem>
                <SelectItem value="confirmed">Confirmadas</SelectItem>
                <SelectItem value="annulled">Anuladas</SelectItem>
              </SelectContent>
            </Select>
            <DateRangePicker
              dateFrom={dateFrom}
              dateTo={dateTo}
              onDateFromChange={(d) => { setDateFrom(d); setPage(0); }}
              onDateToChange={(d) => { setDateTo(d); setPage(0); }}
            />
          </div>
        }
      />
    </div>
  );
}
