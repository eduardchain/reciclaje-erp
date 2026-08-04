import { useMemo } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { Plus, TruckIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { PageHeader } from "@/components/shared/PageHeader";
import { EmptyState } from "@/components/shared/EmptyState";
import { PermissionGate } from "@/components/auth/PermissionGate";
import { useTransfers } from "@/hooks/useTransfers";
import { formatDate, formatWeight } from "@/utils/formatters";
import { ROUTES } from "@/utils/constants";
import {
  TRANSFER_STATUS_LABELS,
  type TransferResponse,
  type TransferStatus,
} from "@/types/transfer";

// SAC E3.1 — bandeja de traslados dos pasos (patron Entradas #82)

const STATUS_STYLES: Record<TransferStatus, string> = {
  dispatched: "bg-amber-100 text-amber-800 border-amber-200",
  held_discrepancy: "bg-red-100 text-red-800 border-red-200",
  received: "bg-emerald-100 text-emerald-800 border-emerald-200",
  annulled: "bg-slate-100 text-slate-500 border-slate-200",
};

function TransferStatusBadge({ status }: { status: TransferStatus }) {
  return (
    <span
      className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium ${STATUS_STYLES[status]}`}
    >
      {TRANSFER_STATUS_LABELS[status]}
    </span>
  );
}

function linesSummary(t: TransferResponse): string {
  const parts = t.lines
    .slice(0, 2)
    .map((ln) => `${ln.material_code} × ${formatWeight(ln.quantity_dispatched, ln.material_unit)}`);
  if (t.lines.length > 2) parts.push(`+${t.lines.length - 2} más`);
  return parts.join(" · ");
}

const TABS: { value: string; label: string }[] = [
  { value: "all", label: "Todos" },
  { value: "dispatched", label: "Por recibir" },
  { value: "held_discrepancy", label: "En discrepancia" },
  { value: "received", label: "Recibidos" },
  { value: "annulled", label: "Anulados" },
];

export default function TransfersPage() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const tab = searchParams.get("tab") ?? "all";

  const filters = useMemo(
    () => ({
      status: tab === "all" ? undefined : tab,
      sort: tab === "dispatched" ? ("oldest" as const) : ("newest" as const),
      limit: 200,
    }),
    [tab]
  );
  const { data, isLoading } = useTransfers(filters);
  const items = data?.items ?? [];
  const pendingCount = data?.pending_receipt_count ?? 0;

  const setTab = (value: string) => {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      if (value === "all") next.delete("tab");
      else next.set("tab", value);
      return next;
    });
  };

  const goDetail = (t: TransferResponse) =>
    navigate(ROUTES.TRANSFER_DETAIL.replace(":id", t.id));

  return (
    <div>
      <PageHeader
        title="Traslados"
        description="Traslados intersede en dos pasos: despacho → recepción confirmada"
      >
        <div className="flex flex-wrap items-center gap-2">
          {pendingCount > 0 && (
            <Button
              variant="outline"
              className="border-amber-300 bg-amber-50 text-amber-800 hover:bg-amber-100 w-full sm:w-auto"
              onClick={() => setTab("dispatched")}
            >
              Por recibir: {pendingCount}
            </Button>
          )}
          <PermissionGate permission="inventory.transfer">
            <Button className="w-full sm:w-auto" onClick={() => navigate(ROUTES.TRANSFER_NEW)}>
              <Plus className="w-4 h-4 mr-2" /> Nuevo Traslado
            </Button>
          </PermissionGate>
        </div>
      </PageHeader>

      <div className="overflow-x-auto -mx-3 px-3 sm:mx-0 sm:px-0 mb-4">
        <Tabs value={tab} onValueChange={setTab}>
          <TabsList className="inline-flex w-max sm:w-auto sm:flex-wrap">
            {TABS.map((t) => (
              <TabsTrigger key={t.value} value={t.value}>
                {t.label}
              </TabsTrigger>
            ))}
          </TabsList>
        </Tabs>
      </div>

      {isLoading ? (
        <p className="text-sm text-slate-500 py-8 text-center">Cargando…</p>
      ) : items.length === 0 ? (
        <EmptyState
          icon={<TruckIcon className="w-10 h-10 text-slate-300" />}
          title="Sin traslados"
          description={
            tab === "dispatched"
              ? "No hay traslados pendientes de recepción."
              : "Registra un despacho para iniciar un traslado intersede."
          }
        />
      ) : (
        <>
          {/* Desktop */}
          <div className="hidden md:block bg-white border rounded-lg">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>#</TableHead>
                  <TableHead>Despacho</TableHead>
                  <TableHead>Origen → Destino</TableHead>
                  <TableHead>Materiales</TableHead>
                  <TableHead>Recepción</TableHead>
                  <TableHead>Estado</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {items.map((t) => (
                  <TableRow
                    key={t.id}
                    className="cursor-pointer hover:bg-slate-50"
                    onClick={() => goDetail(t)}
                  >
                    <TableCell className="font-medium">#{t.transfer_number}</TableCell>
                    <TableCell>{formatDate(t.dispatch_date)}</TableCell>
                    <TableCell>
                      {t.from_warehouse_name} → {t.to_warehouse_name}
                    </TableCell>
                    <TableCell className="text-slate-600 text-sm">{linesSummary(t)}</TableCell>
                    <TableCell>{t.received_date ? formatDate(t.received_date) : "—"}</TableCell>
                    <TableCell>
                      <TransferStatusBadge status={t.status} />
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>

          {/* Mobile cards */}
          <div className="md:hidden space-y-2">
            {items.map((t) => (
              <button
                key={t.id}
                className="w-full text-left bg-white border rounded-lg p-3 active:bg-slate-50"
                onClick={() => goDetail(t)}
              >
                <div className="flex items-center justify-between gap-3">
                  <span className="font-medium">#{t.transfer_number}</span>
                  <TransferStatusBadge status={t.status} />
                </div>
                <p className="mt-1 text-sm text-slate-600">
                  {t.from_warehouse_name} → {t.to_warehouse_name}
                </p>
                <p className="mt-0.5 text-xs text-slate-500">{linesSummary(t)}</p>
                <p className="mt-0.5 text-xs text-slate-400">
                  Despacho: {formatDate(t.dispatch_date)}
                  {t.received_date ? ` · Recibido: ${formatDate(t.received_date)}` : ""}
                </p>
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
