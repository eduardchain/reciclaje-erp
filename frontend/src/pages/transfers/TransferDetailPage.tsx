import { useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, AlertTriangle, Ban } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
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
import { ConfirmDialog } from "@/components/shared/ConfirmDialog";
import { MoneyInput } from "@/components/shared/MoneyInput";
import { usePermissions } from "@/hooks/usePermissions";
import {
  useAnnulTransfer,
  useReceiveTransfer,
  useResolveTransfer,
  useTransfer,
} from "@/hooks/useTransfers";
import {
  formatCurrency,
  formatDate,
  formatWeight,
  toLocalDateInput,
} from "@/utils/formatters";
import { ROUTES } from "@/utils/constants";
import {
  TRANSFER_STATUS_LABELS,
  type TransferLineResponse,
  type TransferResponse,
} from "@/types/transfer";

// SAC E3.1 — detalle: recepción (paso 2), resolución de discrepancias y anulación.

const STATUS_STYLES: Record<string, string> = {
  dispatched: "bg-amber-100 text-amber-800 border-amber-200",
  held_discrepancy: "bg-red-100 text-red-800 border-red-200",
  received: "bg-emerald-100 text-emerald-800 border-emerald-200",
  annulled: "bg-slate-100 text-slate-500 border-slate-200",
};

function LineRow({ line }: { line: TransferLineResponse }) {
  const effective = line.resolved_quantity ?? line.quantity_received;
  return (
    <TableRow>
      <TableCell className="font-medium">
        {line.material_code}
        <span className="hidden lg:inline text-slate-500"> — {line.material_name}</span>
      </TableCell>
      <TableCell className="text-right">
        {formatWeight(line.quantity_dispatched, line.material_unit)}
      </TableCell>
      <TableCell className="text-right">
        {effective != null ? formatWeight(effective, line.material_unit) : "—"}
        {line.variance_pct != null && Number(line.variance_pct) > 0 && (
          <span className="ml-1 text-xs text-slate-500">
            ({(Number(line.variance_pct) * 100).toFixed(2)}%)
          </span>
        )}
      </TableCell>
      <TableCell className="text-right">
        {line.kg_lead_equivalent != null
          ? formatWeight(line.kg_lead_equivalent, "kg")
          : line.is_contributor
            ? "—"
            : "N/A"}
      </TableCell>
      <TableCell className="text-right">
        {line.maquila_amount != null ? formatCurrency(line.maquila_amount) : "—"}
      </TableCell>
    </TableRow>
  );
}

export default function TransferDetailPage() {
  const { id = "" } = useParams();
  const navigate = useNavigate();
  const { hasPermission, isAdmin } = usePermissions();
  const { data: transfer, isLoading } = useTransfer(id);

  const receive = useReceiveTransfer();
  const resolve = useResolveTransfer();
  const annul = useAnnulTransfer();

  const [recvQty, setRecvQty] = useState<Record<string, number>>({});
  const [receiptDate, setReceiptDate] = useState(toLocalDateInput(new Date()));
  const [resolutions, setResolutions] = useState<
    Record<string, { resolution: "justify" | "correct"; final?: number }>
  >({});
  const [resolveNotes, setResolveNotes] = useState("");
  const [annulOpen, setAnnulOpen] = useState(false);
  const [annulReason, setAnnulReason] = useState("");

  const canReceive = isAdmin || hasPermission("inventory.transfer_receive");
  const canManage = isAdmin || hasPermission("inventory.transfer");

  const heldLines = useMemo(
    () =>
      (transfer?.lines ?? []).filter(
        (ln) => ln.discrepancy_task_id && !ln.effects_emitted
      ),
    [transfer]
  );

  if (isLoading || !transfer) {
    return <p className="text-sm text-slate-500 py-8 text-center">Cargando…</p>;
  }

  const t: TransferResponse = transfer;

  const submitReceive = () => {
    receive.mutate({
      id: t.id,
      data: {
        lines: t.lines.map((ln) => ({
          transfer_line_id: ln.id,
          quantity_received: recvQty[ln.id] ?? 0,
        })),
        receipt_date: `${receiptDate}T12:00:00`,
      },
    });
  };

  const receiveReady = t.lines.every((ln) => recvQty[ln.id] != null);

  const submitResolve = () => {
    resolve.mutate({
      id: t.id,
      data: {
        lines: heldLines.map((ln) => {
          const r = resolutions[ln.id] ?? { resolution: "justify" as const };
          return {
            transfer_line_id: ln.id,
            resolution: r.resolution,
            final_quantity: r.resolution === "correct" ? r.final : undefined,
          };
        }),
        notes: resolveNotes,
      },
    });
  };

  const resolveReady =
    heldLines.length > 0 &&
    resolveNotes.trim().length >= 3 &&
    heldLines.every((ln) => {
      const r = resolutions[ln.id];
      if (!r) return false;
      return r.resolution === "justify" || (r.final != null && r.final >= 0);
    });

  return (
    <div>
      <PageHeader title={`Traslado #${t.transfer_number}`}>
        <div className="flex flex-wrap items-center gap-2">
          <span
            className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-sm font-medium ${STATUS_STYLES[t.status]}`}
          >
            {TRANSFER_STATUS_LABELS[t.status]}
          </span>
          {canManage && t.status !== "annulled" && (
            <Button
              variant="outline"
              className="text-red-600 border-red-200 hover:bg-red-50 w-full sm:w-auto"
              onClick={() => setAnnulOpen(true)}
            >
              <Ban className="w-4 h-4 mr-2" /> Anular
            </Button>
          )}
          <Button variant="outline" className="w-full sm:w-auto" onClick={() => navigate(ROUTES.TRANSFERS)}>
            <ArrowLeft className="w-4 h-4 mr-2" /> Volver
          </Button>
        </div>
      </PageHeader>

      {t.status === "annulled" && (
        <div className="mb-4 rounded-lg border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600">
          Anulado{t.annulled_at ? ` el ${formatDate(t.annulled_at)}` : ""}
          {t.annulled_reason ? ` — ${t.annulled_reason}` : ""}
        </div>
      )}

      <Card className="mb-4">
        <CardContent className="pt-6">
          <dl className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-x-6 gap-y-2 text-sm">
            <div className="flex justify-between gap-3 sm:block">
              <dt className="text-slate-500">Origen</dt>
              <dd className="font-medium">{t.from_warehouse_name}</dd>
            </div>
            <div className="flex justify-between gap-3 sm:block">
              <dt className="text-slate-500">Destino</dt>
              <dd className="font-medium">{t.to_warehouse_name}</dd>
            </div>
            <div className="flex justify-between gap-3 sm:block">
              <dt className="text-slate-500">Despacho</dt>
              <dd className="font-medium">
                {formatDate(t.dispatch_date)}
                {t.created_by_name ? ` · ${t.created_by_name}` : ""}
              </dd>
            </div>
            <div className="flex justify-between gap-3 sm:block">
              <dt className="text-slate-500">Recepción</dt>
              <dd className="font-medium">
                {t.received_date
                  ? `${formatDate(t.received_date)}${t.received_by_name ? ` · ${t.received_by_name}` : ""}`
                  : "Pendiente"}
              </dd>
            </div>
          </dl>
          {t.notes && <p className="mt-3 text-sm text-slate-500">{t.notes}</p>}
        </CardContent>
      </Card>

      <Card className="mb-4">
        <CardHeader>
          <CardTitle className="text-base">Líneas</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto -mx-3 sm:mx-0">
            <Table className="min-w-[560px]">
              <TableHeader>
                <TableRow>
                  <TableHead>Material</TableHead>
                  <TableHead className="text-right">Despachado</TableHead>
                  <TableHead className="text-right">Recibido</TableHead>
                  <TableHead className="text-right">Kg plomo</TableHead>
                  <TableHead className="text-right">Maquila</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {t.lines.map((ln) => (
                  <LineRow key={ln.id} line={ln} />
                ))}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>

      {/* Paso 2 — Recepción */}
      {t.status === "dispatched" && canReceive && (
        <Card className="mb-4 border-amber-200">
          <CardHeader>
            <CardTitle className="text-base">Confirmar recepción</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <Label>Fecha de recepción *</Label>
                <Input
                  type="date"
                  value={receiptDate}
                  max={toLocalDateInput(new Date())}
                  onChange={(e) => setReceiptDate(e.target.value)}
                />
              </div>
            </div>
            <div className="space-y-2">
              {t.lines.map((ln) => (
                <div key={ln.id} className="grid grid-cols-1 sm:grid-cols-2 gap-2 items-center">
                  <span className="text-sm">
                    {ln.material_code} — despachado{" "}
                    {formatWeight(ln.quantity_dispatched, ln.material_unit)}
                  </span>
                  <MoneyInput
                    value={recvQty[ln.id] ?? 0}
                    onChange={(v) => setRecvQty((prev) => ({ ...prev, [ln.id]: v }))}
                    decimals={4}
                    placeholder="Cantidad recibida (báscula)"
                  />
                </div>
              ))}
            </div>
            <p className="text-xs text-slate-500">
              Lo recibido es la fuente de verdad: el kg de plomo y la maquila se calculan
              sobre la báscula del destino. Diferencias fuera de tolerancia quedan en
              discrepancia para revisión.
            </p>
            <Button
              className="w-full sm:w-auto"
              disabled={!receiveReady || receive.isPending}
              onClick={submitReceive}
            >
              {receive.isPending ? "Confirmando…" : "Confirmar Recepción"}
            </Button>
          </CardContent>
        </Card>
      )}

      {/* Resolución de discrepancias */}
      {t.status === "held_discrepancy" && canReceive && heldLines.length > 0 && (
        <Card className="mb-4 border-red-200">
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 text-red-500" /> Resolver discrepancias
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {heldLines.map((ln) => {
              const r = resolutions[ln.id];
              return (
                <div key={ln.id} className="rounded-lg border p-3 space-y-2">
                  <p className="text-sm font-medium">
                    {ln.material_code} — despachado{" "}
                    {formatWeight(ln.quantity_dispatched, ln.material_unit)}, báscula{" "}
                    {formatWeight(ln.quantity_received ?? 0, ln.material_unit)}
                  </p>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                    <Select
                      value={r?.resolution ?? ""}
                      onValueChange={(v) =>
                        setResolutions((prev) => ({
                          ...prev,
                          [ln.id]: { ...prev[ln.id], resolution: v as "justify" | "correct" },
                        }))
                      }
                    >
                      <SelectTrigger>
                        <SelectValue placeholder="Resolución…" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="justify">Justificar (aceptar báscula)</SelectItem>
                        <SelectItem value="correct">Corregir (arqueo)</SelectItem>
                      </SelectContent>
                    </Select>
                    {r?.resolution === "correct" && (
                      <MoneyInput
                        value={r?.final ?? 0}
                        onChange={(v) =>
                          setResolutions((prev) => ({
                            ...prev,
                            [ln.id]: { ...prev[ln.id], resolution: "correct", final: v },
                          }))
                        }
                        decimals={4}
                        placeholder="Cantidad final (arqueo)"
                      />
                    )}
                  </div>
                </div>
              );
            })}
            <div className="space-y-1.5">
              <Label>Notas de resolución *</Label>
              <Textarea
                value={resolveNotes}
                onChange={(e) => setResolveNotes(e.target.value)}
                rows={2}
                placeholder="Qué se revisó y por qué se acepta/corrige"
              />
            </div>
            <Button
              className="w-full sm:w-auto"
              disabled={!resolveReady || resolve.isPending}
              onClick={submitResolve}
            >
              {resolve.isPending ? "Resolviendo…" : "Resolver"}
            </Button>
          </CardContent>
        </Card>
      )}

      <ConfirmDialog
        open={annulOpen}
        onOpenChange={setAnnulOpen}
        title={`Anular traslado #${t.transfer_number}`}
        description="Se revierte el inventario, los kg intersede y la maquila. El stock que ya se haya vendido o procesado en destino quedará negativo (con aviso)."
        confirmLabel="Anular"
        variant="destructive"
        loading={annul.isPending}
        disabled={annulReason.trim().length < 3}
        onConfirm={() =>
          annul.mutate(
            { id: t.id, reason: annulReason.trim() },
            { onSuccess: () => setAnnulOpen(false) }
          )
        }
      >
        <div className="space-y-1.5">
          <Label>Motivo *</Label>
          <Textarea
            value={annulReason}
            onChange={(e) => setAnnulReason(e.target.value)}
            rows={2}
          />
        </div>
      </ConfirmDialog>
    </div>
  );
}
