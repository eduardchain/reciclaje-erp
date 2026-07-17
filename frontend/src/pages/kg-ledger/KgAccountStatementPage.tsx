import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, ArrowDownUp } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { PageHeader } from "@/components/shared/PageHeader";
import { DateRangePicker } from "@/components/shared/DateRangePicker";
import { ConfirmDialog } from "@/components/shared/ConfirmDialog";
import { EntityLink } from "@/components/shared/EntityLink";
import { KgManualMovementDialog } from "./KgManualMovementDialog";
import { usePermissions } from "@/hooks/usePermissions";
import { useAnnulKgMovement, useKgStatement } from "@/hooks/useKgLedger";
import { formatDate, formatWeight } from "@/utils/formatters";
import { buildRoute, ROUTES } from "@/utils/constants";
import { cn } from "@/utils";
import {
  KG_ACCOUNT_TYPE_LABELS,
  KG_SOURCE_TYPE_LABELS,
  type KgLedgerStatementRow,
} from "@/types/kg-ledger";

type StatusFilter = "confirmed" | "annulled" | "all";

// source_types emitidos por Recepcion — el link navega a la orden origen
const INBOUND_SOURCE_TYPES = new Set(["postconsumo_receipt", "drosses_receipt"]);

const deltaClass = (v: number) =>
  cn("font-semibold tabular-nums", v < 0 ? "text-red-600" : "text-emerald-700");

export default function KgAccountStatementPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { hasPermission } = usePermissions();
  const canAdjust = hasPermission("kg_ledger.manage_adjustments");

  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("confirmed");

  const { data, isLoading } = useKgStatement(id!, {
    date_from: dateFrom || undefined,
    date_to: dateTo || undefined,
    status_filter: statusFilter,
  });

  const annulMovement = useAnnulKgMovement();
  const [annulTarget, setAnnulTarget] = useState<KgLedgerStatementRow | null>(null);
  const [annulReason, setAnnulReason] = useState("");
  const [manualOpen, setManualOpen] = useState(false);

  const account = data?.account;
  const movements = data?.movements ?? [];

  const confirmAnnul = () => {
    if (!annulTarget || !annulReason.trim()) return;
    annulMovement.mutate(
      { id: annulTarget.id, reason: annulReason.trim() },
      {
        onSuccess: () => {
          setAnnulTarget(null);
          setAnnulReason("");
        },
      }
    );
  };

  if (isLoading) return <div className="p-8 text-center text-slate-500">Cargando...</div>;
  if (!account) return <div className="p-8 text-center text-slate-500">Cuenta no encontrada</div>;

  return (
    <div className="space-y-4">
      <PageHeader
        title={account.display_name}
        description={`${account.code} · ${KG_ACCOUNT_TYPE_LABELS[account.account_type] ?? account.account_type}${account.warehouse_name ? ` · ${account.warehouse_name}` : ""}${account.third_party_name ? ` · ${account.third_party_name}` : ""}`}
      >
        <Button variant="outline" onClick={() => navigate(ROUTES.KG_LEDGER)}>
          <ArrowLeft className="h-4 w-4 mr-2" />
          Volver
        </Button>
        {canAdjust && account.is_active && (
          <Button variant="outline" onClick={() => setManualOpen(true)}>
            <ArrowDownUp className="h-4 w-4 mr-2" />
            Movimiento Manual
          </Button>
        )}
      </PageHeader>

      {/* Resumen */}
      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4">
        <Card className="shadow-sm border-t-[3px] border-t-emerald-500">
          <CardContent className="p-3 sm:p-4">
            <p className="text-[10px] sm:text-xs font-semibold uppercase tracking-wider text-slate-500">Saldo Actual</p>
            <p className={cn("text-lg sm:text-2xl font-bold tabular-nums", account.current_balance_kg < 0 ? "text-red-600" : "text-slate-900")}>
              {formatWeight(account.current_balance_kg)}
            </p>
          </CardContent>
        </Card>
        <Card className="shadow-sm border-t-[3px] border-t-sky-500">
          <CardContent className="p-3 sm:p-4">
            <p className="text-[10px] sm:text-xs font-semibold uppercase tracking-wider text-slate-500">Movimientos (ventana)</p>
            <p className="text-lg sm:text-2xl font-bold tabular-nums text-slate-900">{movements.length}</p>
          </CardContent>
        </Card>
        <Card className="shadow-sm border-t-[3px] border-t-amber-500">
          <CardContent className="p-3 sm:p-4">
            <p className="text-[10px] sm:text-xs font-semibold uppercase tracking-wider text-slate-500">Tolerancia Cuadre</p>
            <p className="text-lg sm:text-2xl font-bold tabular-nums text-slate-900">
              {account.tolerance_kg != null ? `± ${formatWeight(account.tolerance_kg)}` : "—"}
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Filtros */}
      <div className="flex flex-col sm:flex-row sm:flex-wrap gap-2 sm:items-center">
        <DateRangePicker
          dateFrom={dateFrom}
          dateTo={dateTo}
          onDateFromChange={setDateFrom}
          onDateToChange={setDateTo}
        />
        <Select value={statusFilter} onValueChange={(v) => setStatusFilter(v as StatusFilter)}>
          <SelectTrigger className="w-full sm:w-44">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="confirmed">Confirmados</SelectItem>
            <SelectItem value="annulled">Anulados</SelectItem>
            <SelectItem value="all">Todos</SelectItem>
          </SelectContent>
        </Select>
        {!dateFrom && (
          <span className="text-xs text-slate-400">Últimos 90 días por defecto</span>
        )}
      </div>

      {/* Statement — la fila sintetica "Saldo Inicial" se muestra siempre
          (apertura real de la ventana, patron #55) */}
      <div className="overflow-x-auto -mx-3 sm:mx-0 rounded-lg border bg-white">
          <Table className="min-w-[720px]">
            <TableHeader>
              <TableRow>
                <TableHead>Fecha</TableHead>
                <TableHead>Origen</TableHead>
                <TableHead>Descripción</TableHead>
                <TableHead className="text-right">Δ kg</TableHead>
                <TableHead className="text-right">Saldo (kg)</TableHead>
                <TableHead className="w-24" />
              </TableRow>
            </TableHeader>
            <TableBody>
              {/* Fila sintetica: saldo de apertura real de la ventana (#55) */}
              <TableRow className="bg-slate-50/80">
                <TableCell className="text-slate-500 text-sm" colSpan={3}>
                  Saldo Inicial
                </TableCell>
                <TableCell />
                <TableCell className="text-right">
                  <span className="font-semibold tabular-nums text-slate-700">
                    {formatWeight(data?.opening_balance_kg ?? 0)}
                  </span>
                </TableCell>
                <TableCell />
              </TableRow>
              {movements.length === 0 && (
                <TableRow>
                  <TableCell colSpan={6} className="text-center text-sm text-slate-400 py-6">
                    Sin movimientos en la ventana seleccionada
                  </TableCell>
                </TableRow>
              )}
              {movements.map((m) => {
                const isAnnulled = m.status === "annulled";
                return (
                  <TableRow key={m.id} className={cn(isAnnulled && "opacity-60")}>
                    <TableCell className="whitespace-nowrap">{formatDate(m.transaction_date)}</TableCell>
                    <TableCell>
                      <div className="flex items-center gap-1.5 flex-wrap">
                        <Badge variant="outline" className="bg-slate-100 text-slate-700">
                          {KG_SOURCE_TYPE_LABELS[m.source_type] ?? m.source_type}
                        </Badge>
                        {isAnnulled && (
                          <Badge variant="outline" className="bg-red-100 text-red-800">Anulado</Badge>
                        )}
                        {INBOUND_SOURCE_TYPES.has(m.source_type) && m.source_id && (
                          <EntityLink to={buildRoute(ROUTES.INBOUND_DETAIL, { id: m.source_id })}>
                            Ver recepción
                          </EntityLink>
                        )}
                      </div>
                    </TableCell>
                    <TableCell className={cn("text-sm text-slate-600 max-w-[280px]", isAnnulled && "line-through")}>
                      <span className="truncate block">{m.description ?? "—"}</span>
                      {isAnnulled && m.annulled_reason && (
                        <span className="text-xs text-red-500 block truncate">Motivo: {m.annulled_reason}</span>
                      )}
                    </TableCell>
                    <TableCell className="text-right whitespace-nowrap">
                      <span className={cn(deltaClass(m.delta_kg), isAnnulled && "line-through")}>
                        {m.delta_kg > 0 ? "+" : ""}
                        {formatWeight(m.delta_kg)}
                      </span>
                    </TableCell>
                    <TableCell className="text-right whitespace-nowrap">
                      <span className={cn("tabular-nums font-medium", m.balance_after_kg < 0 ? "text-red-600" : "")}>
                        {formatWeight(m.balance_after_kg)}
                      </span>
                    </TableCell>
                    <TableCell>
                      {canAdjust && m.source_type === "manual_adjustment" && m.status === "confirmed" && (
                        <Button
                          variant="ghost"
                          size="sm"
                          className="text-red-600 hover:text-red-700"
                          onClick={() => { setAnnulTarget(m); setAnnulReason(""); }}
                        >
                          Anular
                        </Button>
                      )}
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </div>

      {/* Anular movimiento manual */}
      <ConfirmDialog
        open={!!annulTarget}
        onOpenChange={(o) => { if (!o) { setAnnulTarget(null); setAnnulReason(""); } }}
        title="Anular movimiento manual"
        description={`Se anulará el movimiento de ${annulTarget ? formatWeight(annulTarget.delta_kg) : ""} del ${annulTarget ? formatDate(annulTarget.transaction_date) : ""}. Esta acción queda auditada.`}
        confirmLabel="Anular"
        variant="destructive"
        loading={annulMovement.isPending}
        disabled={!annulReason.trim()}
        onConfirm={confirmAnnul}
      >
        <div>
          <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Razón *</Label>
          <Input
            value={annulReason}
            onChange={(e) => setAnnulReason(e.target.value)}
            maxLength={500}
            placeholder="Motivo de la anulación..."
          />
        </div>
      </ConfirmDialog>

      <KgManualMovementDialog
        open={manualOpen}
        onOpenChange={setManualOpen}
        accounts={account ? [account] : []}
        defaultAccountId={account.id}
      />
    </div>
  );
}
