import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { FlaskConical } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { EmptyState } from "@/components/shared/EmptyState";
import { saveScroll } from "@/hooks/useScrollRestoration";
import { useCrucibleCharges } from "@/hooks/useCrucibleCharges";
import { formatCurrency, formatDate, formatWeight } from "@/utils/formatters";
import { cn } from "@/utils";
import {
  CRUCIBLE_EVENT_COLORS, CRUCIBLE_EVENT_LABELS, CRUCIBLE_STATUS_LABELS, num,
  type CrucibleCharge, type CrucibleChargeStatus, type CrucibleEventType,
} from "@/types/crucible-charge";

export function CrucibleEventBadge({ type }: { type: CrucibleEventType }) {
  return (
    <Badge className={cn("font-medium", CRUCIBLE_EVENT_COLORS[type])} variant="secondary">
      {CRUCIBLE_EVENT_LABELS[type]}
    </Badge>
  );
}

export function CrucibleStatusBadge({ status }: { status: CrucibleChargeStatus }) {
  return (
    <Badge
      className={cn(
        "font-medium",
        status === "annulled" ? "bg-slate-200 text-slate-600" : "bg-green-100 text-green-800",
      )}
      variant="secondary"
    >
      {CRUCIBLE_STATUS_LABELS[status]}
    </Badge>
  );
}

/**
 * Tab "Crisol" de Salidas de Plomo (#107 D2): los documentos que mueven el
 * plomo entre las dos etapas de la deuda de planta con Circunvalar. No mueven
 * inventario ni deuda — solo dicen DÓNDE está el plomo.
 */
export function CrucibleChargesSection() {
  const navigate = useNavigate();
  const [eventType, setEventType] = useState<"all" | CrucibleEventType>("all");
  const [status, setStatus] = useState<"all" | CrucibleChargeStatus>("confirmed");

  const { data, isLoading } = useCrucibleCharges({
    event_type: eventType === "all" ? undefined : eventType,
    status: status === "all" ? undefined : status,
    page: 1,
    page_size: 50,
  });
  const items = data?.items ?? [];

  const open = (c: CrucibleCharge) => {
    saveScroll(window.location.pathname + window.location.search);
    navigate(`/willard-deliveries/crisol/${c.id}`);
  };

  return (
    <div className="space-y-3">
      <p className="text-sm text-slate-500">
        El traslado a crisoles y el retorno de dross no mueven inventario ni deuda: cambian la
        etapa del plomo dentro de la deuda de planta con Circunvalar (horno ↔ crisol). El
        retorno de dross causa otra vez la maquila del horno.
      </p>

      <div className="flex flex-col sm:flex-row sm:flex-wrap gap-2 sm:items-center">
        <Select value={eventType} onValueChange={(v) => setEventType(v as "all" | CrucibleEventType)}>
          <SelectTrigger className="w-full sm:w-56"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Todos los documentos</SelectItem>
            <SelectItem value="charge">{CRUCIBLE_EVENT_LABELS.charge}</SelectItem>
            <SelectItem value="dross_return">{CRUCIBLE_EVENT_LABELS.dross_return}</SelectItem>
          </SelectContent>
        </Select>
        <Select value={status} onValueChange={(v) => setStatus(v as "all" | CrucibleChargeStatus)}>
          <SelectTrigger className="w-full sm:w-44"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="confirmed">Registrados</SelectItem>
            <SelectItem value="annulled">Anulados</SelectItem>
            <SelectItem value="all">Todos</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {isLoading ? (
        <Card><CardContent className="p-8 text-center text-slate-500">Cargando…</CardContent></Card>
      ) : items.length === 0 ? (
        <EmptyState
          icon={<FlaskConical className="h-10 w-10 text-slate-300" />}
          title="Sin documentos de crisol"
          description="Todavía no se ha registrado ningún traslado a crisoles ni retorno de dross."
        />
      ) : (
        <>
          <Card className="hidden md:block">
            <CardContent className="p-0">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>#</TableHead>
                    <TableHead>Fecha</TableHead>
                    <TableHead>Documento</TableHead>
                    <TableHead>Material</TableHead>
                    <TableHead className="text-right">Kg plomo</TableHead>
                    <TableHead className="text-right">Maquila reproceso</TableHead>
                    <TableHead>Estado</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {items.map((c) => (
                    <TableRow key={c.id} className="cursor-pointer" onClick={() => open(c)}>
                      <TableCell className="font-medium whitespace-nowrap">{c.label}</TableCell>
                      <TableCell>{formatDate(c.date)}</TableCell>
                      <TableCell><CrucibleEventBadge type={c.event_type} /></TableCell>
                      <TableCell>{c.material_code ?? "—"}{c.material_name ? ` - ${c.material_name}` : ""}</TableCell>
                      <TableCell className="text-right tabular-nums">{formatWeight(num(c.quantity_kg), "kg")}</TableCell>
                      <TableCell className="text-right tabular-nums">
                        {num(c.maquila_amount) > 0 ? formatCurrency(num(c.maquila_amount)) : "—"}
                      </TableCell>
                      <TableCell><CrucibleStatusBadge status={c.status} /></TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>

          <div className="md:hidden space-y-2">
            {items.map((c) => (
              <Card key={c.id} className="cursor-pointer" onClick={() => open(c)}>
                <CardContent className="p-3 space-y-2">
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-semibold">{c.label}</span>
                    <CrucibleStatusBadge status={c.status} />
                  </div>
                  <div className="flex items-center justify-between gap-2 text-sm">
                    <CrucibleEventBadge type={c.event_type} />
                    <span className="text-slate-500">{formatDate(c.date)}</span>
                  </div>
                  <div className="text-sm text-slate-600">{c.material_code ?? "—"} {c.material_name ?? ""}</div>
                  <div className="flex justify-between gap-3 text-sm">
                    <span className="text-slate-500">Kg plomo</span>
                    <span className="tabular-nums">{formatWeight(num(c.quantity_kg), "kg")}</span>
                  </div>
                  {num(c.maquila_amount) > 0 && (
                    <div className="flex justify-between gap-3 text-sm">
                      <span className="text-slate-500">Maquila reproceso</span>
                      <span className="tabular-nums">{formatCurrency(num(c.maquila_amount))}</span>
                    </div>
                  )}
                </CardContent>
              </Card>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
