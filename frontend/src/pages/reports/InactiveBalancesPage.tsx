import { useMemo } from "react";
import { Link, useSearchParams, useLocation } from "react-router-dom";
import { Clock, Phone, ArrowRight, FileSpreadsheet, AlertTriangle, ChevronUp, ChevronDown, ArrowUpDown } from "lucide-react";
import ReportsLayout from "./ReportsLayout";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/shared/EmptyState";
import { MoneyDisplay } from "@/components/shared/MoneyDisplay";
import { MoneyInput } from "@/components/shared/MoneyInput";
import { useInactiveBalances } from "@/hooks/useReports";
import { exportInactiveBalancesExcel } from "@/utils/excelExport";
import { saveScroll, useScrollRestoration } from "@/hooks/useScrollRestoration";
import { ROUTES } from "@/utils/constants";
import { formatCurrency, formatDate } from "@/utils/formatters";

const TYPE_LABEL: Record<string, string> = {
  customer: "Cliente",
  material_supplier: "Proveedor",
  service_provider: "Servicio",
  provision: "Provisión",
  investor: "Inversionista",
  liability: "Pasivo",
  generic: "Genérico",
};

// Semáforo de severidad por antigüedad (absoluto, estable, separado del accent)
function sevClasses(days: number): { badge: string; stripe: string } {
  if (days > 35) return { badge: "bg-red-50 text-red-700 border-red-200", stripe: "border-l-red-500" };
  if (days > 15) return { badge: "bg-orange-50 text-orange-700 border-orange-200", stripe: "border-l-orange-400" };
  return { badge: "bg-amber-50 text-amber-700 border-amber-200", stripe: "border-l-amber-300" };
}

const TYPE_BADGE: Record<string, string> = {
  customer: "bg-blue-50 text-blue-700",
  material_supplier: "bg-emerald-50 text-emerald-700",
  service_provider: "bg-indigo-50 text-indigo-700",
  provision: "bg-violet-50 text-violet-700",
  investor: "bg-sky-50 text-sky-700",
  liability: "bg-rose-50 text-rose-700",
  generic: "bg-slate-100 text-slate-600",
};

function expectLabel(type: string): string {
  if (type === "customer") return "esperando pago";
  if (type === "material_supplier") return "esperando entrega de material";
  if (type === "provision") return "fondos apartados sin ejecutar";
  return "saldo a favor sin cruzar";
}

export default function InactiveBalancesPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const location = useLocation();

  const minDays = Number(searchParams.get("min_days") ?? 10);
  const minAmount = Number(searchParams.get("min_amount") ?? 0);
  const activeTab = searchParams.get("tab") ?? "all";

  const setParam = (key: string, value: string | null) => {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      if (value === null || value === "") next.delete(key);
      else next.set(key, value);
      return next;
    }, { replace: true });
  };

  const { data, isLoading } = useInactiveBalances({ min_days: minDays, min_amount: minAmount });
  const allItems = data?.items ?? [];

  // Restaura el scroll al volver del estado de cuenta (par de saveScroll en los links, #57)
  useScrollRestoration(!isLoading);

  // Conteo por tipo para las tabs (sobre el resultado completo del backend)
  const typeCounts = useMemo(() => {
    const c: Record<string, number> = {};
    allItems.forEach((i) => { c[i.third_party_type] = (c[i.third_party_type] ?? 0) + 1; });
    return c;
  }, [allItems]);

  const tabs = useMemo(() => {
    const present = Object.keys(typeCounts).sort((a, b) => (typeCounts[b] ?? 0) - (typeCounts[a] ?? 0));
    return ["all", ...present];
  }, [typeCounts]);

  const items = useMemo(
    () => (activeTab === "all" ? allItems : allItems.filter((i) => i.third_party_type === activeTab)),
    [allItems, activeTab],
  );

  const tabTotal = useMemo(() => items.reduce((s, i) => s + i.amount_inactive, 0), [items]);
  const oldest = allItems[0]; // KPI "el más viejo": backend siempre ordena por días desc

  // Orden de la tabla (persistido en URL para sobrevivir al ida/vuelta del estado de cuenta)
  const [sortField, sortDir] = (searchParams.get("sort") ?? "days_desc").split("_") as
    ["days" | "amount", "asc" | "desc"];
  const toggleSort = (field: "days" | "amount") => {
    const nextDir = sortField === field && sortDir === "desc" ? "asc" : "desc";
    const value = `${field}_${nextDir}`;
    setParam("sort", value === "days_desc" ? null : value); // default limpio de URL
  };
  const sortIcon = (field: "days" | "amount") =>
    sortField !== field ? <ArrowUpDown className="h-3.5 w-3.5 opacity-40" />
      : sortDir === "desc" ? <ChevronDown className="h-3.5 w-3.5" />
      : <ChevronUp className="h-3.5 w-3.5" />;
  const sortedItems = useMemo(() => {
    const mul = sortDir === "asc" ? 1 : -1;
    return [...items].sort((a, b) => {
      const av = sortField === "amount" ? a.amount_inactive : a.days_inactive;
      const bv = sortField === "amount" ? b.amount_inactive : b.days_inactive;
      return (av - bv) * mul;
    });
  }, [items, sortField, sortDir]);

  const stmtHref = (id: string) =>
    `${ROUTES.TREASURY_ACCOUNT_STATEMENT}?third_party_id=${id}&returnTo=${encodeURIComponent(
      location.pathname + location.search,
    )}`;

  const telHref = (phone: string) => `tel:${phone.replace(/\s/g, "")}`;

  return (
    <ReportsLayout>
      <div className="space-y-4">
        {/* Encabezado del panel + Excel */}
        <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold flex items-center gap-2">
              <Clock className="h-5 w-5 text-slate-400" /> Dinero Inactivo
            </h2>
            <p className="text-sm text-slate-500 max-w-prose">
              Saldos a favor que llevan días sin moverse. Lo más viejo, arriba — para llamar y recuperar.
            </p>
          </div>
          <Button
            variant="outline"
            size="sm"
            className="w-full sm:w-auto"
            disabled={!items.length}
            onClick={() => data && exportInactiveBalancesExcel({ ...data, items: sortedItems }, TYPE_LABEL[activeTab])}
          >
            <FileSpreadsheet className="w-4 h-4 mr-1" /> Excel
          </Button>
        </div>

        {/* Filtros */}
        <Card className="shadow-sm">
          <CardContent className="pt-4 flex flex-col sm:flex-row sm:flex-wrap gap-4 sm:items-end">
            <div className="flex flex-col gap-1.5 w-full sm:w-56">
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                Avisarme desde (días sin mover)
              </Label>
              <Input
                type="number"
                min={0}
                inputMode="numeric"
                value={minDays}
                onChange={(e) => setParam("min_days", e.target.value === "" ? null : e.target.value)}
              />
            </div>
            <div className="flex flex-col gap-1.5 w-full sm:w-56">
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                Ocultar saldos menores a
              </Label>
              <MoneyInput
                value={minAmount}
                onChange={(n) => setParam("min_amount", n > 0 ? String(n) : null)}
                placeholder="0"
              />
            </div>
          </CardContent>
        </Card>

        {/* KPIs */}
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
          <Card className="shadow-sm">
            <CardContent className="pt-4">
              <div className="text-xs font-semibold uppercase tracking-wider text-slate-400">Total parado</div>
              <div className="text-2xl font-bold text-red-700 tabular-nums">
                {isLoading ? <Skeleton className="h-7 w-32" /> : formatCurrency(data?.total_inactive_balance ?? 0)}
              </div>
              <div className="text-xs text-slate-500 mt-0.5">
                en {data?.item_count ?? 0} {(data?.item_count ?? 0) === 1 ? "tercero" : "terceros"}
              </div>
            </CardContent>
          </Card>
          <Card className="shadow-sm">
            <CardContent className="pt-4">
              <div className="text-xs font-semibold uppercase tracking-wider text-slate-400">El más viejo</div>
              <div className="text-2xl font-bold tabular-nums">
                {isLoading ? <Skeleton className="h-7 w-20" /> : `${oldest?.days_inactive ?? 0} días`}
              </div>
              <div className="text-xs text-slate-500 mt-0.5 truncate">{oldest?.third_party_name ?? "—"}</div>
            </CardContent>
          </Card>
          <Card className="shadow-sm">
            <CardContent className="pt-4">
              <div className="text-xs font-semibold uppercase tracking-wider text-slate-400">Umbral aplicado</div>
              <div className="text-2xl font-bold tabular-nums">{minDays} días</div>
              <div className="text-xs text-slate-500 mt-0.5">
                {minAmount > 0 ? `desde ${formatCurrency(minAmount)}` : "sin mínimo de monto"}
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Tabs por tipo */}
        {tabs.length > 1 && (
          <Tabs value={activeTab} onValueChange={(v) => setParam("tab", v === "all" ? null : v)}>
            <div className="overflow-x-auto -mx-3 px-3 sm:mx-0 sm:px-0">
              <TabsList className="inline-flex w-max sm:w-auto sm:flex-wrap sm:h-auto">
                {tabs.map((t) => (
                  <TabsTrigger key={t} value={t}>
                    {t === "all" ? "Todos" : TYPE_LABEL[t] ?? t}
                    <span className="ml-1.5 text-xs opacity-70 tabular-nums">
                      {t === "all" ? allItems.length : typeCounts[t]}
                    </span>
                  </TabsTrigger>
                ))}
              </TabsList>
            </div>
          </Tabs>
        )}

        {/* Contenido */}
        {isLoading ? (
          <div className="space-y-2">
            {[...Array(4)].map((_, i) => <Skeleton key={i} className="h-16 w-full" />)}
          </div>
        ) : !items.length ? (
          <EmptyState
            icon={<Clock className="h-10 w-10" />}
            title="Nada inactivo en este filtro"
            description="Bajá el umbral de días o revisá otro tipo de tercero."
          />
        ) : (
          <>
            {/* Desktop */}
            <div className="hidden md:block rounded-lg border overflow-hidden">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-24">
                      <button onClick={() => toggleSort("days")} className="inline-flex items-center gap-1 hover:text-slate-900 select-none">
                        Días {sortIcon("days")}
                      </button>
                    </TableHead>
                    <TableHead>Tercero</TableHead>
                    <TableHead>Última actividad</TableHead>
                    <TableHead className="text-right">
                      <button onClick={() => toggleSort("amount")} className="inline-flex items-center gap-1 hover:text-slate-900 select-none ml-auto">
                        Monto {sortIcon("amount")}
                      </button>
                    </TableHead>
                    <TableHead className="text-right">Acciones</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {sortedItems.map((it) => {
                    const sev = sevClasses(it.days_inactive);
                    return (
                      <TableRow key={it.third_party_id} className={`border-l-4 ${sev.stripe}`}>
                        <TableCell>
                          <span className={`inline-flex items-baseline gap-1 px-2 py-0.5 rounded-md border text-sm font-bold tabular-nums ${sev.badge}`}>
                            {it.days_inactive}<span className="text-[10px] font-semibold opacity-70">d</span>
                          </span>
                        </TableCell>
                        <TableCell>
                          <div className="font-medium">{it.third_party_name}</div>
                          <div className="flex items-center gap-2 mt-0.5">
                            <Badge variant="outline" className={`text-[11px] ${TYPE_BADGE[it.third_party_type] ?? ""}`}>
                              {TYPE_LABEL[it.third_party_type] ?? it.third_party_type}
                            </Badge>
                            <span className="text-xs text-slate-500">{expectLabel(it.third_party_type)}</span>
                          </div>
                        </TableCell>
                        <TableCell className="text-sm text-slate-600">
                          {it.has_movements ? (
                            formatDate(it.last_activity_date)
                          ) : (
                            <span className="inline-flex items-center gap-1 text-amber-700">
                              <AlertTriangle className="h-3.5 w-3.5" /> Sin movimientos desde la carga
                            </span>
                          )}
                        </TableCell>
                        <TableCell className="text-right">
                          <MoneyDisplay amount={it.amount_inactive} />
                        </TableCell>
                        <TableCell className="text-right">
                          <div className="flex items-center justify-end gap-2">
                            {it.phone && (
                              <Button asChild variant="outline" size="sm">
                                <a href={telHref(it.phone)}><Phone /> {it.phone}</a>
                              </Button>
                            )}
                            <Button asChild variant="outline" size="sm">
                              <Link
                                to={stmtHref(it.third_party_id)}
                                onClick={() => saveScroll(location.pathname + location.search)}
                              >
                                Estado de cuenta <ArrowRight />
                              </Link>
                            </Button>
                          </div>
                        </TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            </div>

            {/* Mobile */}
            <div className="md:hidden space-y-2">
              <div className="flex items-center gap-1.5 text-sm pb-1">
                <span className="text-slate-500 mr-0.5">Ordenar:</span>
                {(["days", "amount"] as const).map((f) => (
                  <button
                    key={f}
                    onClick={() => toggleSort(f)}
                    className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-md border text-xs font-medium ${
                      sortField === f
                        ? "border-emerald-500 bg-emerald-50 text-emerald-700"
                        : "border-slate-200 text-slate-600"
                    }`}
                  >
                    {f === "days" ? "Días" : "Monto"} {sortField === f && sortIcon(f)}
                  </button>
                ))}
              </div>
              {sortedItems.map((it) => {
                const sev = sevClasses(it.days_inactive);
                return (
                  <Card key={it.third_party_id} className={`border-l-4 shadow-sm ${sev.stripe}`}>
                    <CardContent className="pt-4 space-y-2">
                      <div className="flex items-start justify-between gap-2">
                        <div className="min-w-0">
                          <div className="font-medium truncate">{it.third_party_name}</div>
                          <Badge variant="outline" className={`text-[11px] mt-1 ${TYPE_BADGE[it.third_party_type] ?? ""}`}>
                            {TYPE_LABEL[it.third_party_type] ?? it.third_party_type}
                          </Badge>
                        </div>
                        <span className={`inline-flex items-baseline gap-1 px-2 py-0.5 rounded-md border text-sm font-bold tabular-nums ${sev.badge}`}>
                          {it.days_inactive}<span className="text-[10px] font-semibold opacity-70">d</span>
                        </span>
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="text-xs text-slate-500">
                          {it.has_movements ? `Última: ${formatDate(it.last_activity_date)}` : "Sin movimientos"}
                        </span>
                        <MoneyDisplay amount={it.amount_inactive} />
                      </div>
                      <div className="flex items-center justify-between gap-2 border-t pt-2">
                        {it.phone ? (
                          <Button asChild variant="outline" size="sm">
                            <a href={telHref(it.phone)}><Phone /> {it.phone}</a>
                          </Button>
                        ) : <span className="text-xs text-slate-400">Sin teléfono</span>}
                        <Button asChild variant="outline" size="sm">
                          <Link
                            to={stmtHref(it.third_party_id)}
                            onClick={() => saveScroll(location.pathname + location.search)}
                          >
                            Estado de cuenta <ArrowRight />
                          </Link>
                        </Button>
                      </div>
                    </CardContent>
                  </Card>
                );
              })}
            </div>

            <div className="text-sm text-slate-500 flex items-center justify-between px-1">
              <span>{items.length} {items.length === 1 ? "tercero" : "terceros"}</span>
              <span className="font-medium">Subtotal: {formatCurrency(tabTotal)}</span>
            </div>
          </>
        )}

        <p className="text-xs text-slate-400 flex items-start gap-1.5 pt-1">
          <Clock className="h-3.5 w-3.5 mt-0.5 flex-none" />
          El reloj se reinicia con cualquier movimiento real del saldo (compra, venta, pago, cobro). Las
          operaciones anuladas no cuentan. Los terceros cargados en la migración sin movimientos cuentan
          desde su fecha de carga.
        </p>
      </div>
    </ReportsLayout>
  );
}
