import { useNavigate, useSearchParams } from "react-router-dom";
import { BookOpen, PackageMinus, Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { PageHeader } from "@/components/shared/PageHeader";
import { EmptyState } from "@/components/shared/EmptyState";
import { SearchInput } from "@/components/shared/SearchInput";
import { usePermissions } from "@/hooks/usePermissions";
import { useScrollRestoration, saveScroll } from "@/hooks/useScrollRestoration";
import { useControlDispatches } from "@/hooks/useControlDispatches";
import { buildRoute, ROUTES } from "@/utils/constants";
import { formatDate, formatWeight } from "@/utils/formatters";
import { cn } from "@/utils";
import {
  CONTROL_DISPATCH_STATUS_LABELS,
  type ControlDispatch,
  type ControlDispatchStatus,
} from "@/types/control-dispatch";

export function ControlDispatchStatusBadge({ status }: { status: ControlDispatchStatus }) {
  return (
    <Badge
      variant="secondary"
      className={cn(
        "font-medium",
        status === "annulled" ? "bg-red-50 text-red-700" : "bg-slate-100 text-slate-700",
      )}
    >
      {CONTROL_DISPATCH_STATUS_LABELS[status]}
    </Badge>
  );
}

/** Los materiales del documento en una línea: «ESTIBAS 40 unidad · TUBULAR 3 unidad». */
export function linesSummary(d: ControlDispatch): string {
  return d.lines
    .map((l) => `${l.material_code ?? l.material_name ?? "?"} ${formatWeight(l.quantity, l.material_unit)}`)
    .join(" · ");
}

const TABS = [
  { value: "all", label: "Todas" },
  { value: "registered", label: "Registradas" },
  { value: "annulled", label: "Anuladas" },
] as const;

export default function ControlDispatchesPage() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const { hasPermission } = usePermissions();

  const tab = searchParams.get("tab") ?? "all";
  const search = searchParams.get("q") ?? "";
  const { data, isLoading } = useControlDispatches({
    status: tab === "registered" || tab === "annulled" ? tab : undefined,
    search: search || undefined,
    limit: 200,
  });

  // El hook de scroll va ANTES de cualquier return condicional (#93 bloqueante a)
  useScrollRestoration(!isLoading);

  const items = data?.items ?? [];
  const setParam = (key: string, value: string) =>
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      if (!value || value === "all") next.delete(key);
      else next.set(key, value);
      return next;
    });

  const open = (d: ControlDispatch) => {
    saveScroll(window.location.pathname + window.location.search);
    navigate(buildRoute(ROUTES.CONTROL_DISPATCH_DETAIL, { id: d.id }));
  };

  return (
    <div className="space-y-4">
      <PageHeader
        title="Salidas de control"
        description="Estibas, tubulares, electrolito: salen con su remisión, sin precio, sin inventario ni plata"
      >
        <div className="flex flex-col sm:flex-row flex-wrap gap-2 w-full sm:w-auto">
          {hasPermission("purchases.view") && hasPermission("sales.view") && (
            <Button
              variant="outline"
              onClick={() => navigate(ROUTES.REMISSION_BOOK)}
              className="w-full sm:w-auto"
            >
              <BookOpen className="h-4 w-4 mr-2" /> Talonario de remisiones
            </Button>
          )}
          {hasPermission("sales.create") && (
            <Button onClick={() => navigate(ROUTES.CONTROL_DISPATCH_NEW)} className="w-full sm:w-auto">
              <Plus className="h-4 w-4 mr-2" /> Nueva salida de control
            </Button>
          )}
        </div>
      </PageHeader>

      <div className="flex flex-col sm:flex-row sm:flex-wrap gap-2 sm:items-center">
        <div className="overflow-x-auto -mx-3 px-3 sm:mx-0 sm:px-0">
          <Tabs value={tab} onValueChange={(v) => setParam("tab", v)}>
            <TabsList className="inline-flex w-max sm:w-auto sm:flex-wrap">
              {TABS.map((t) => (
                <TabsTrigger key={t.value} value={t.value}>{t.label}</TabsTrigger>
              ))}
            </TabsList>
          </Tabs>
        </div>
        <div className="w-full sm:w-72">
          <SearchInput
            value={search}
            onChange={(v) => setParam("q", v.trim())}
            placeholder="Número, remisión o tercero…"
          />
        </div>
      </div>

      {isLoading ? (
        <Card><CardContent className="p-8 text-center text-slate-500">Cargando…</CardContent></Card>
      ) : items.length === 0 ? (
        <EmptyState
          icon={<PackageMinus className="h-10 w-10 text-slate-300" />}
          title="Sin salidas de control"
          description={search ? "Nada coincide con la búsqueda." : "Todavía no hay salidas de control registradas."}
        />
      ) : (
        <>
          {/* Escritorio */}
          <Card className="hidden md:block">
            <CardContent className="p-0">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>#</TableHead>
                    <TableHead>Remisión</TableHead>
                    <TableHead>Fecha</TableHead>
                    <TableHead>Bodega</TableHead>
                    <TableHead>Tercero</TableHead>
                    <TableHead>Materiales</TableHead>
                    <TableHead>Estado</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {items.map((d) => (
                    <TableRow key={d.id} className="cursor-pointer" onClick={() => open(d)}>
                      <TableCell className="font-medium whitespace-nowrap">#{d.dispatch_number}</TableCell>
                      <TableCell className="whitespace-nowrap">{d.remission_number}</TableCell>
                      <TableCell className="whitespace-nowrap">{formatDate(d.date)}</TableCell>
                      <TableCell>{d.warehouse_name ?? "—"}</TableCell>
                      <TableCell>{d.third_party_name ?? "—"}</TableCell>
                      <TableCell className="text-slate-600">{linesSummary(d)}</TableCell>
                      <TableCell><ControlDispatchStatusBadge status={d.status} /></TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>

          {/* 390 */}
          <div className="md:hidden space-y-2">
            {items.map((d) => (
              <Card key={d.id} className="cursor-pointer" onClick={() => open(d)}>
                <CardContent className="p-3 space-y-1.5">
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-semibold">Salida de control #{d.dispatch_number}</span>
                    <ControlDispatchStatusBadge status={d.status} />
                  </div>
                  <div className="flex justify-between gap-3 text-sm">
                    <span className="text-slate-500">Remisión</span>
                    <span>{d.remission_number}</span>
                  </div>
                  <div className="flex justify-between gap-3 text-sm">
                    <span className="text-slate-500">Fecha</span>
                    <span>{formatDate(d.date)}</span>
                  </div>
                  {d.third_party_name && (
                    <div className="flex flex-col gap-0.5 text-sm">
                      <span className="text-slate-500">Tercero</span>
                      <span>{d.third_party_name}</span>
                    </div>
                  )}
                  <p className="text-sm text-slate-600">{linesSummary(d)}</p>
                </CardContent>
              </Card>
            ))}
          </div>
          {data && data.total > items.length && (
            <p className="text-xs text-slate-500">
              Se muestran {items.length} de {data.total}. Use la búsqueda para encontrar las demás.
            </p>
          )}
        </>
      )}
    </div>
  );
}
