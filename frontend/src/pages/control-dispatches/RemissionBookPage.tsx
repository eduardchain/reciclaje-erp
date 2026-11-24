import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ArrowLeft } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { PageHeader } from "@/components/shared/PageHeader";
import { SearchInput } from "@/components/shared/SearchInput";
import { useRemissionBook } from "@/hooks/useControlDispatches";
import { buildRoute, ROUTES } from "@/utils/constants";
import { formatDate } from "@/utils/formatters";
import type { RemissionBookItem } from "@/types/control-dispatch";
import type { RemissionBookFilters } from "@/services/controlDispatches";

const PAGE_SIZE = 100;

// Estado de cada documento con el nombre que usa su propio módulo. Una Willard
// confirmada se ve «Liquidada» en Entradas (display_status, #82): acá igual (O8).
const STATUS_LABELS: Record<string, string> = {
  draft: "Registrada",
  reviewed: "Revisada",
  liquidated: "Liquidada",
  confirmed: "Liquidada",
  closed: "Cerrada sin valor",
  registered: "Registrada",
  annulled: "Anulada",
};

/** Texto del tramo sin documento (desviación (b), aprobada por el Coordinador):
 *  un número sin documento no es por fuerza una remisión perdida. */
export function gapText(item: RemissionBookItem): string {
  if (item.gap_from === item.gap_to) return `Sin documento: ${item.gap_from} (1 número)`;
  // El conteo llega como texto exacto; se agrupa por miles sin pasar por number.
  const n = (item.count ?? "0").replace(/\B(?=(\d{3})+(?!\d))/g, ".");
  return `Sin documento: ${item.gap_from} a ${item.gap_to} (${n} números)`;
}

const GAP_NOTE =
  "Un número sin documento puede ser una remisión que no se registró o un error al digitar otra. " +
  "Una remisión fuera de serie o repetida suele ser la otra mitad del mismo error.";

function docLabel(item: RemissionBookItem): string {
  return item.doc_type === "control_dispatch"
    ? `Salida de control #${item.doc_number}`
    : `Entrada #${item.doc_number}`;
}

function docLink(item: RemissionBookItem): string {
  return item.doc_type === "control_dispatch"
    ? buildRoute(ROUTES.CONTROL_DISPATCH_DETAIL, { id: item.doc_id! })
    : buildRoute(ROUTES.INBOUND_DETAIL, { id: item.doc_id! });
}

function Direction({ item }: { item: RemissionBookItem }) {
  const out = item.doc_type === "control_dispatch";
  return (
    <Badge variant="secondary" className={out ? "bg-sky-50 text-sky-700" : "bg-emerald-50 text-emerald-700"}>
      {out ? "Sale" : item.inbound_type === "willard" ? "Entra · Willard" : "Entra"}
    </Badge>
  );
}

function StatusText({ status }: { status: string | null }) {
  const label = status ? (STATUS_LABELS[status] ?? status) : "—";
  return <span className={status === "annulled" ? "text-red-600" : "text-slate-600"}>{label}</span>;
}

function Repeated() {
  return (
    <Badge variant="secondary" className="bg-amber-100 text-amber-800">Repetida</Badge>
  );
}

/** Solo dígitos; viaja como texto para no redondear una remisión de 20 dígitos. */
const toDigits = (v: string): string | undefined => {
  const t = v.trim();
  return /^[0-9]+$/.test(t) ? t : undefined;
};

/** Talonario de remisiones (Q-75): Entradas y Salidas de control en una sola
 *  lista por remisión, con los números sin documento intercalados. */
export default function RemissionBookPage() {
  const navigate = useNavigate();
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [search, setSearch] = useState("");
  const [order, setOrder] = useState<"asc" | "desc">("desc");
  const [page, setPage] = useState(0);

  const filters: RemissionBookFilters = {
    remission_from: toDigits(from),
    remission_to: toDigits(to),
    date_from: dateFrom || undefined,
    // La fecha sola: el servidor la combina con el final del día (O5 de QA 2).
    date_to: dateTo || undefined,
    search: search || undefined,
    order,
    skip: page * PAGE_SIZE,
    limit: PAGE_SIZE,
  };
  const { data, isLoading } = useRemissionBook(filters);
  const items = data?.items ?? [];
  const total = data?.total ?? 0;
  const reset = <T,>(set: (v: T) => void) => (v: T) => {
    set(v);
    setPage(0);
  };

  return (
    <div className="space-y-4">
      <PageHeader
        title="Talonario de remisiones"
        description="Entradas y Salidas de control por número de remisión"
      >
        <Button variant="outline" onClick={() => navigate(-1)} className="w-full sm:w-auto">
          <ArrowLeft className="h-4 w-4 mr-2" /> Volver
        </Button>
      </PageHeader>

      <Card>
        <CardContent className="pt-4 grid grid-cols-1 sm:grid-cols-2 md:grid-cols-6 gap-3">
          <div className="space-y-1">
            <Label className="text-xs">Remisión desde</Label>
            <Input inputMode="numeric" value={from} onChange={(e) => reset(setFrom)(e.target.value)} />
          </div>
          <div className="space-y-1">
            <Label className="text-xs">Remisión hasta</Label>
            <Input inputMode="numeric" value={to} onChange={(e) => reset(setTo)(e.target.value)} />
          </div>
          <div className="space-y-1">
            <Label className="text-xs">Fecha desde</Label>
            <Input type="date" value={dateFrom} onChange={(e) => reset(setDateFrom)(e.target.value)} />
          </div>
          <div className="space-y-1">
            <Label className="text-xs">Fecha hasta</Label>
            <Input type="date" value={dateTo} onChange={(e) => reset(setDateTo)(e.target.value)} />
          </div>
          {/* SearchInput fija sm:w-64 y en la grilla de 6 columnas tapaba «Orden»
              a 1440: el selector hijo (clase + elemento) le gana al ancho fijo. */}
          <div className="space-y-1 min-w-0 [&>div]:w-full">
            <Label className="text-xs">Buscar remisión</Label>
            <SearchInput value={search} onChange={reset(setSearch)} placeholder="Remisión…" />
          </div>
          <div className="space-y-1">
            <Label className="text-xs">Orden</Label>
            <Select value={order} onValueChange={(v) => reset(setOrder)(v as "asc" | "desc")}>
              <SelectTrigger className="w-full"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="desc">Mayor a menor</SelectItem>
                <SelectItem value="asc">Menor a mayor</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </CardContent>
      </Card>

      <div className="text-sm text-slate-600 space-y-1">
        {data && (
          <p>
            {data.documents} {data.documents === 1 ? "documento" : "documentos"}
            {data.inbound_without_remission > 0 && (
              <span className="text-amber-700">
                {" "}· {data.inbound_without_remission}{" "}
                {data.inbound_without_remission === 1 ? "Entrada sin remisión" : "Entradas sin remisión"} (no
                aparecen en el talonario)
              </span>
            )}
          </p>
        )}
        {search && <p className="text-xs text-slate-500">Con búsqueda no se muestran los números sin documento.</p>}
      </div>

      <div className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
        {GAP_NOTE}
      </div>

      {isLoading ? (
        <Card><CardContent className="p-8 text-center text-slate-500">Cargando…</CardContent></Card>
      ) : items.length === 0 ? (
        <Card><CardContent className="p-8 text-center text-slate-500">Ninguna remisión en este filtro.</CardContent></Card>
      ) : (
        <>
          {/* Escritorio */}
          <Card className="hidden md:block">
            <CardContent className="p-0">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Remisión</TableHead>
                    <TableHead>Documento</TableHead>
                    <TableHead>Dirección</TableHead>
                    <TableHead>Fecha</TableHead>
                    <TableHead>Estado</TableHead>
                    <TableHead>Materiales</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {items.map((item, i) =>
                    item.kind === "gap" ? (
                      <TableRow key={`gap-${item.gap_from}-${i}`} className="bg-amber-50 hover:bg-amber-50">
                        <TableCell colSpan={6} className="text-amber-800 font-medium">
                          {gapText(item)}
                        </TableCell>
                      </TableRow>
                    ) : (
                      <TableRow key={`${item.doc_type}-${item.doc_id}`}>
                        <TableCell className="whitespace-nowrap font-medium">
                          <span className="inline-flex items-center gap-2">
                            {item.remission}
                            {item.duplicated && <Repeated />}
                          </span>
                        </TableCell>
                        <TableCell className="whitespace-nowrap">
                          <Link to={docLink(item)} className="text-indigo-600 hover:underline">
                            {docLabel(item)}
                          </Link>
                        </TableCell>
                        <TableCell><Direction item={item} /></TableCell>
                        <TableCell className="whitespace-nowrap">{formatDate(item.date)}</TableCell>
                        <TableCell className="whitespace-nowrap"><StatusText status={item.status} /></TableCell>
                        <TableCell className="text-slate-600">{item.materials ?? "—"}</TableCell>
                      </TableRow>
                    ),
                  )}
                </TableBody>
              </Table>
            </CardContent>
          </Card>

          {/* 390 */}
          <div className="md:hidden space-y-2">
            {items.map((item, i) =>
              item.kind === "gap" ? (
                <div
                  key={`gap-${item.gap_from}-${i}`}
                  className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm font-medium text-amber-800"
                >
                  {gapText(item)}
                </div>
              ) : (
                <Card key={`${item.doc_type}-${item.doc_id}`}>
                  <CardContent className="p-3 space-y-1.5 text-sm">
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-semibold inline-flex items-center gap-2">
                        {item.remission}
                        {item.duplicated && <Repeated />}
                      </span>
                      <Direction item={item} />
                    </div>
                    <div className="flex justify-between gap-3">
                      <Link to={docLink(item)} className="text-indigo-600 hover:underline">
                        {docLabel(item)}
                      </Link>
                      <StatusText status={item.status} />
                    </div>
                    <div className="flex justify-between gap-3">
                      <span className="text-slate-500">Fecha</span>
                      <span>{formatDate(item.date)}</span>
                    </div>
                    {item.materials && <p className="text-slate-600">{item.materials}</p>}
                  </CardContent>
                </Card>
              ),
            )}
          </div>

          {total > PAGE_SIZE && (
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
              <span className="text-xs text-slate-500">
                Filas {page * PAGE_SIZE + 1}–{Math.min((page + 1) * PAGE_SIZE, total)} de {total}
              </span>
              <div className="flex gap-2">
                <Button variant="outline" size="sm" disabled={page === 0} onClick={() => setPage((p) => p - 1)}>
                  Anterior
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={(page + 1) * PAGE_SIZE >= total}
                  onClick={() => setPage((p) => p + 1)}
                >
                  Siguiente
                </Button>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
