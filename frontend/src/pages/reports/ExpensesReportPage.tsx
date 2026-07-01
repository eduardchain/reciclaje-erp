import { useEffect, useMemo, useState } from "react";
import { useNavigate, useLocation, useSearchParams } from "react-router-dom";
import { useDateFilter } from "@/stores/dateFilterStore";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription } from "@/components/ui/sheet";
import { ChevronDown, ChevronRight, FileSpreadsheet, ListFilter, ExternalLink, Expand, Shrink } from "lucide-react";
import { DateRangePicker } from "@/components/shared/DateRangePicker";
import { ResponsiveFilterBar } from "@/components/shared/ResponsiveFilterBar";
import ReportsLayout from "./ReportsLayout";
import { useExpensesReport, useExpensesDetail } from "@/hooks/useReports";
import { useBusinessUnits } from "@/hooks/useCrudData";
import { useExpenseCategoriesFlat } from "@/hooks/useMasterData";
import { exportExpensesReportExcel, exportExpensesFlatExcel } from "@/utils/excelExport";
import { formatCurrency, formatDate } from "@/utils/formatters";
import type {
  ExpenseGroupNode,
  ExpensesGroupBy,
  ExpenseAllocationType,
  ExpensesReportResponse,
} from "@/types/reports";

const GROUP_BY_OPTIONS: { value: ExpensesGroupBy; label: string }[] = [
  { value: "bu_then_category", label: "UN → Categoria" },
  { value: "category_then_bu", label: "Categoria → UN" },
  { value: "bu", label: "Solo UN" },
  { value: "category", label: "Solo Categoria" },
  { value: "none", label: "Sin agrupar (detalle)" },
];

const ALLOC_LABELS: Record<ExpenseAllocationType, string> = {
  direct: "Directo",
  shared: "Compartido",
  general: "General",
};

const ALLOC_COLORS: Record<ExpenseAllocationType, string> = {
  direct: "bg-emerald-50 text-emerald-700",
  shared: "bg-blue-50 text-blue-700",
  general: "bg-amber-50 text-amber-700",
};

interface DetailContext {
  bu_id: string | null;
  bu_label: string;
  cat_id: string | null;
  cat_label: string;
}

function SummaryHeader({ data }: { data: ExpensesReportResponse }) {
  const { total, total_direct, total_shared, total_general, movement_count } = data;
  const pct = (v: number) => (total > 0 ? (v / total) * 100 : 0);
  const segments: { type: ExpenseAllocationType; value: number; pctVal: number }[] = [
    { type: "direct", value: total_direct, pctVal: pct(total_direct) },
    { type: "shared", value: total_shared, pctVal: pct(total_shared) },
    { type: "general", value: total_general, pctVal: pct(total_general) },
  ];
  const visibleSegments = segments.filter((s) => s.value > 0);
  const segColors: Record<ExpenseAllocationType, string> = {
    direct: "bg-emerald-500",
    shared: "bg-blue-500",
    general: "bg-amber-500",
  };
  const dotColors: Record<ExpenseAllocationType, string> = {
    direct: "bg-emerald-500",
    shared: "bg-blue-500",
    general: "bg-amber-500",
  };

  return (
    <Card className="shadow-sm">
      <CardContent className="p-4">
        <div className="flex items-start justify-between mb-2">
          <div>
            <div className="text-xs text-slate-500 uppercase tracking-wider">Total del Periodo</div>
            <div className="text-2xl font-bold tabular-nums">{formatCurrency(total)}</div>
          </div>
          <div className="text-sm text-slate-500 tabular-nums">
            {movement_count} movimiento{movement_count === 1 ? "" : "s"}
          </div>
        </div>

        {visibleSegments.length > 0 && (
          <>
            <div className="flex h-2 rounded-full overflow-hidden bg-slate-100 mt-3">
              {visibleSegments.map((s) => (
                <div
                  key={s.type}
                  className={segColors[s.type]}
                  style={{ width: `${s.pctVal}%` }}
                  title={`${ALLOC_LABELS[s.type]}: ${formatCurrency(s.value)} (${s.pctVal.toFixed(1)}%)`}
                />
              ))}
            </div>
            <div className="flex flex-wrap gap-x-5 gap-y-1 mt-2 text-xs text-slate-600">
              {visibleSegments.map((s) => (
                <div key={s.type} className="flex items-center gap-1.5">
                  <span className={`inline-block w-2 h-2 rounded-full ${dotColors[s.type]}`} />
                  <span className="font-medium">{ALLOC_LABELS[s.type]}</span>
                  <span className="tabular-nums">{formatCurrency(s.value)}</span>
                  <span className="text-slate-400">({s.pctVal.toFixed(1)}%)</span>
                </div>
              ))}
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}

function NodeRow({
  node,
  depth,
  expanded,
  onToggle,
  onClickRow,
}: {
  node: ExpenseGroupNode;
  depth: number;
  expanded: Set<string>;
  onToggle: (key: string) => void;
  onClickRow: (node: ExpenseGroupNode) => void;
}) {
  const hasChildren = node.children && node.children.length > 0;
  const isOpen = expanded.has(node.key);

  return (
    <>
      <tr
        className="text-sm border-b cursor-pointer transition-colors hover:bg-emerald-50/40 group"
        onClick={() => onClickRow(node)}
      >
        <td className="py-2 px-3" style={{ paddingLeft: `${12 + depth * 20}px` }}>
          <div className="flex items-center gap-2">
            {hasChildren ? (
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  onToggle(node.key);
                }}
                className="text-slate-500 hover:text-slate-700 -ml-1 px-1 py-0.5 rounded"
                aria-label={isOpen ? "Colapsar" : "Expandir"}
              >
                {isOpen ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
              </button>
            ) : (
              <span className="inline-block w-4" />
            )}
            <span className={depth === 0 ? "font-semibold" : ""}>{node.label}</span>
          </div>
        </td>
        <td className="py-2 px-3 text-right tabular-nums font-medium">{formatCurrency(node.total)}</td>
        <td className="py-2 px-2 w-8 text-slate-400">
          <ChevronRight className="h-4 w-4 opacity-0 group-hover:opacity-100 transition-opacity" />
        </td>
      </tr>
      {hasChildren && isOpen &&
        node.children.map((child) => (
          <NodeRow
            key={child.key}
            node={child}
            depth={depth + 1}
            expanded={expanded}
            onToggle={onToggle}
            onClickRow={onClickRow}
          />
        ))}
    </>
  );
}

function MultiSelectDropdown({
  label,
  options,
  selected,
  onToggle,
  onClear,
  placeholder,
}: {
  label: string;
  options: { id: string; label: string }[];
  selected: Set<string>;
  onToggle: (id: string) => void;
  onClear: () => void;
  placeholder: string;
}) {
  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button variant="outline" size="sm" className="h-9">
          <ListFilter className="h-3.5 w-3.5 mr-1" />
          {selected.size > 0 ? `${label}: ${selected.size}` : placeholder}
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-72 max-h-80 overflow-y-auto" align="start">
        <div className="flex justify-between items-center mb-2">
          <span className="text-xs text-slate-500">{label}</span>
          {selected.size > 0 && (
            <Button variant="ghost" size="sm" onClick={onClear} className="h-6 text-xs">Limpiar</Button>
          )}
        </div>
        <div className="space-y-1">
          {options.map((opt) => (
            <label key={opt.id} className="flex items-center gap-2 text-sm py-1 px-2 hover:bg-slate-50 rounded cursor-pointer">
              <Checkbox checked={selected.has(opt.id)} onCheckedChange={() => onToggle(opt.id)} />
              <span>{opt.label}</span>
            </label>
          ))}
        </div>
      </PopoverContent>
    </Popover>
  );
}

function ExpenseDetailSheet({
  open,
  onOpenChange,
  context,
  dateFrom,
  dateTo,
  returnTo,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  context: DetailContext | null;
  dateFrom: string;
  dateTo: string;
  returnTo: string;
}) {
  const navigate = useNavigate();

  const params = useMemo(() => {
    if (!context) return null;
    return {
      date_from: dateFrom,
      date_to: dateTo,
      business_unit_id: context.bu_id ?? undefined,
      business_unit_unassigned: context.bu_id === null && context.bu_label === "Sin Asignar" ? true : undefined,
      category_id: context.cat_id ?? undefined,
      category_uncategorized: context.cat_id === null && context.cat_label === "Sin Categoría" ? true : undefined,
      include_child_categories: true,
    };
  }, [context, dateFrom, dateTo]);

  const { data, isLoading } = useExpensesDetail(params ?? { date_from: "", date_to: "" }, !!params && open);

  const handleOpenMovement = (movId: string) => {
    onOpenChange(false);
    navigate(`/treasury/${movId}?returnTo=${encodeURIComponent(returnTo)}`);
  };

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent
        side="right"
        className="w-full sm:max-w-[70vw] sm:w-[70vw] overflow-y-auto"
      >
        <SheetHeader className="mb-4">
          <SheetTitle>Detalle de gastos</SheetTitle>
          {context && (
            <SheetDescription className="space-y-0.5">
              <div><span className="font-medium">UN:</span> {context.bu_label || "Todas"}</div>
              <div><span className="font-medium">Categoría:</span> {context.cat_label || "Todas"}</div>
            </SheetDescription>
          )}
        </SheetHeader>

        {isLoading && <div className="py-6 text-center text-slate-500">Cargando...</div>}

        {data && (
          <>
            <div className="mb-3 flex items-start justify-between gap-3">
              <div className="text-sm text-slate-600 flex items-center gap-3 flex-wrap">
                <span>{data.total_count} movimiento{data.total_count === 1 ? "" : "s"}</span>
                <span className="text-slate-300">·</span>
                <span>Total asignado: <span className="font-semibold tabular-nums">{formatCurrency(data.total_allocated)}</span></span>
              </div>
              <Button
                variant="outline"
                size="sm"
                onClick={() => exportExpensesFlatExcel(data, dateFrom, dateTo, {
                  buLabel: context?.bu_label || "Todas",
                  catLabel: context?.cat_label || "Todas",
                })}
                disabled={data.total_count === 0}
                className="shrink-0"
              >
                <FileSpreadsheet className="w-4 h-4 mr-1" /> Excel
              </Button>
            </div>
            <div className="border rounded overflow-x-auto">
              <table className="w-full text-sm min-w-[640px]">
                <thead className="bg-slate-50 text-xs text-slate-500 uppercase sticky top-0">
                  <tr>
                    <th className="py-2 px-2 text-left whitespace-nowrap">Fecha</th>
                    <th className="py-2 px-2 text-left whitespace-nowrap">#</th>
                    <th className="py-2 px-2 text-left whitespace-nowrap">Tipo</th>
                    <th className="py-2 px-2 text-left whitespace-nowrap">Tercero</th>
                    <th className="py-2 px-2 text-left whitespace-nowrap">Categoría</th>
                    <th className="py-2 px-2 text-left whitespace-nowrap">Descripción</th>
                    <th className="py-2 px-2 text-right whitespace-nowrap">Monto Original</th>
                    <th className="py-2 px-2 text-right whitespace-nowrap">Asignado</th>
                    <th className="py-2 px-2 text-center whitespace-nowrap">Asig.</th>
                    <th className="py-2 px-2 text-center" />
                  </tr>
                </thead>
                <tbody>
                  {data.items.map((item) => (
                    <tr key={item.movement_id} className="border-b hover:bg-slate-50/50">
                      <td className="py-2 px-2 whitespace-nowrap">{formatDate(item.date)}</td>
                      <td className="py-2 px-2">{item.movement_number}</td>
                      <td className="py-2 px-2 text-xs text-slate-500">{item.movement_type}</td>
                      <td className="py-2 px-2">{item.third_party_name ?? "—"}</td>
                      <td className="py-2 px-2">{item.expense_category_name ?? "Sin Categoría"}</td>
                      <td className="py-2 px-2 max-w-[240px] truncate" title={item.description ?? ""}>
                        {item.description ?? ""}
                      </td>
                      <td className="py-2 px-2 text-right tabular-nums">{formatCurrency(item.amount)}</td>
                      <td className="py-2 px-2 text-right tabular-nums font-medium">{formatCurrency(item.allocated_amount)}</td>
                      <td className="py-2 px-2 text-center">
                        <Badge variant="outline" className={`${ALLOC_COLORS[item.allocation_type]} text-xs`}>
                          {ALLOC_LABELS[item.allocation_type]}
                        </Badge>
                      </td>
                      <td className="py-2 px-2 text-center">
                        <button
                          type="button"
                          onClick={() => handleOpenMovement(item.movement_id)}
                          className="text-emerald-600 hover:text-emerald-700"
                          title="Abrir movimiento"
                        >
                          <ExternalLink className="h-4 w-4" />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </SheetContent>
    </Sheet>
  );
}

export default function ExpensesReportPage() {
  const { dateFrom, dateTo, setDateFrom, setDateTo } = useDateFilter();
  const location = useLocation();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();

  const groupBy = (searchParams.get("group_by") as ExpensesGroupBy | null) ?? "bu_then_category";
  const buFilter = useMemo(
    () => new Set((searchParams.get("bu") ?? "").split(",").filter(Boolean)),
    [searchParams],
  );
  const catFilter = useMemo(
    () => new Set((searchParams.get("cat") ?? "").split(",").filter(Boolean)),
    [searchParams],
  );

  const setParam = (updates: Record<string, string | null>) => {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      Object.entries(updates).forEach(([k, v]) => {
        if (v === null || v === "" || v === "bu_then_category") next.delete(k);
        else next.set(k, v);
      });
      return next;
    }, { replace: true });
  };

  const setSelectionParam = (key: string, set: Set<string>) => {
    const v = Array.from(set).join(",");
    setParam({ [key]: v.length > 0 ? v : null });
  };

  const { data: bus } = useBusinessUnits();
  const { data: cats } = useExpenseCategoriesFlat();

  const { data, isLoading } = useExpensesReport({
    date_from: dateFrom,
    date_to: dateTo,
    group_by: groupBy,
    business_unit_id: buFilter.size > 0 ? Array.from(buFilter) : undefined,
    expense_category_id: catFilter.size > 0 ? Array.from(catFilter) : undefined,
  });

  // Flat detail (modo "Sin agrupar"): respeta los mismos filtros del reporte
  const flatEnabled = groupBy === "none";
  const { data: flatData, isLoading: flatLoading } = useExpensesDetail(
    {
      date_from: dateFrom,
      date_to: dateTo,
      business_unit_ids: buFilter.size > 0 ? Array.from(buFilter) : undefined,
      category_ids: catFilter.size > 0 ? Array.from(catFilter) : undefined,
    },
    flatEnabled,
  );

  // Estado de expansion de nodos del arbol (lifted desde NodeRow)
  const allExpandableKeys = useMemo(() => {
    if (!data) return [];
    const keys: string[] = [];
    const walk = (nodes: ExpenseGroupNode[]) => {
      for (const n of nodes) {
        if (n.children && n.children.length > 0) {
          keys.push(n.key);
          walk(n.children);
        }
      }
    };
    walk(data.groups);
    return keys;
  }, [data]);

  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  // Al recargar el reporte, expandir top-level por default
  useEffect(() => {
    if (data && data.groups.length > 0) {
      const top = data.groups
        .filter((n) => n.children && n.children.length > 0)
        .map((n) => n.key);
      setExpanded(new Set(top));
    }
  }, [data]);

  const toggleExpand = (key: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };
  const expandAll = () => setExpanded(new Set(allExpandableKeys));
  const collapseAll = () => setExpanded(new Set());
  const hasExpandableNodes = allExpandableKeys.length > 0;

  const [detailContext, setDetailContext] = useState<DetailContext | null>(null);
  const detailOpen = !!detailContext;

  const handleClickNode = (node: ExpenseGroupNode) => {
    const buLabel = node.business_unit_id === null && node.label === "Sin Asignar"
      ? "Sin Asignar"
      : (node.business_unit_id ? (bus?.items.find((b) => b.id === node.business_unit_id)?.name ?? node.label) : "");
    const catLabel = node.category_id === null && node.label === "Sin Categoría"
      ? "Sin Categoría"
      : (node.category_id ? (cats?.items.find((c) => c.id === node.category_id)?.display_name ?? node.label) : "");

    setDetailContext({
      bu_id: node.business_unit_id,
      bu_label: buLabel,
      cat_id: node.category_id,
      cat_label: catLabel,
    });
  };

  const buOptions = useMemo(
    () => (bus?.items ?? []).map((b) => ({ id: b.id, label: b.name })),
    [bus],
  );
  const catOptions = useMemo(
    () => (cats?.items ?? []).map((c) => ({ id: c.id, label: c.display_name })),
    [cats],
  );

  const toggleBu = (id: string) => {
    const next = new Set(buFilter);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    setSelectionParam("bu", next);
  };
  const toggleCat = (id: string) => {
    const next = new Set(catFilter);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    setSelectionParam("cat", next);
  };

  return (
    <ReportsLayout>
      {/* Toolbar única: filtros + fecha + Excel en una sola fila */}
        <Card className="shadow-sm">
          <CardContent className="p-3">
            <div className="flex flex-wrap items-end justify-between gap-3">
              <div className="flex flex-wrap items-end gap-3">
                <div className="flex flex-col gap-1">
                  <Label className="text-xs text-slate-500">Agrupar por</Label>
                  <Select value={groupBy} onValueChange={(v) => setParam({ group_by: v })}>
                    <SelectTrigger className="w-full sm:w-48 h-9">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {GROUP_BY_OPTIONS.map((opt) => (
                        <SelectItem key={opt.value} value={opt.value}>{opt.label}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <div className="flex flex-col gap-1">
                  <Label className="text-xs text-slate-500">Unidades de Negocio</Label>
                  <MultiSelectDropdown
                    label="UN"
                    placeholder="Todas las UN"
                    options={buOptions}
                    selected={buFilter}
                    onToggle={toggleBu}
                    onClear={() => setSelectionParam("bu", new Set())}
                  />
                </div>

                <div className="flex flex-col gap-1">
                  <Label className="text-xs text-slate-500">Categorías</Label>
                  <MultiSelectDropdown
                    label="Cat"
                    placeholder="Todas las categorías"
                    options={catOptions}
                    selected={catFilter}
                    onToggle={toggleCat}
                    onClear={() => setSelectionParam("cat", new Set())}
                  />
                </div>
              </div>

              <ResponsiveFilterBar>
                <DateRangePicker
                  dateFrom={dateFrom}
                  dateTo={dateTo}
                  onDateFromChange={setDateFrom}
                  onDateToChange={setDateTo}
                />
                {groupBy !== "none" && hasExpandableNodes && (
                  <>
                    <Button variant="outline" size="sm" onClick={expandAll} className="w-full sm:w-auto">
                      <Expand className="w-4 h-4 mr-1" /> Expandir
                    </Button>
                    <Button variant="outline" size="sm" onClick={collapseAll} className="w-full sm:w-auto">
                      <Shrink className="w-4 h-4 mr-1" /> Colapsar
                    </Button>
                  </>
                )}
                {data && groupBy !== "none" && (
                  <Button variant="outline" size="sm" onClick={() => exportExpensesReportExcel(data)} className="w-full sm:w-auto">
                    <FileSpreadsheet className="w-4 h-4 mr-1" /> Excel
                  </Button>
                )}
                {flatEnabled && flatData && flatData.items.length > 0 && (
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => exportExpensesFlatExcel(flatData, dateFrom, dateTo)}
                    className="w-full sm:w-auto"
                  >
                    <FileSpreadsheet className="w-4 h-4 mr-1" /> Excel
                  </Button>
                )}
              </ResponsiveFilterBar>
            </div>
          </CardContent>
        </Card>

        {data && <SummaryHeader data={data} />}

        {(isLoading || (flatEnabled && flatLoading)) && (
          <div className="text-center text-slate-500 py-8">Cargando...</div>
        )}

        {/* Modo agrupado */}
        {!flatEnabled && data && data.groups.length === 0 && (
          <div className="text-center text-slate-400 py-8">No hay gastos para el periodo y filtros seleccionados</div>
        )}

        {!flatEnabled && data && data.groups.length > 0 && (
          <Card className="shadow-sm">
            <CardContent className="p-0 overflow-x-auto">
              <table className="w-full text-sm min-w-[400px]">
                <thead>
                  <tr className="border-b bg-slate-50 text-xs text-slate-500 uppercase tracking-wider">
                    <th className="py-2 px-3 text-left">Grupo</th>
                    <th className="py-2 px-3 text-right whitespace-nowrap">Total</th>
                    <th className="py-2 px-2 w-8" />
                  </tr>
                </thead>
                <tbody>
                  {data.groups.map((node) => (
                    <NodeRow
                      key={node.key}
                      node={node}
                      depth={0}
                      expanded={expanded}
                      onToggle={toggleExpand}
                      onClickRow={handleClickNode}
                    />
                  ))}
                </tbody>
              </table>
            </CardContent>
          </Card>
        )}

        {/* Modo "Sin agrupar": tabla plana de movimientos */}
        {flatEnabled && flatData && flatData.items.length === 0 && (
          <div className="text-center text-slate-400 py-8">No hay gastos para el periodo y filtros seleccionados</div>
        )}

        {flatEnabled && flatData && flatData.items.length > 0 && (
          <Card className="shadow-sm">
            <CardContent className="p-0">
              <div className="px-3 py-2 border-b bg-slate-50 text-xs text-slate-500 flex items-center gap-3">
                <span>{flatData.total_count} movimiento{flatData.total_count === 1 ? "" : "s"}</span>
                <span className="text-slate-300">·</span>
                <span>Total: <span className="font-semibold tabular-nums text-slate-700">{formatCurrency(flatData.total_allocated)}</span></span>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-sm min-w-[720px]">
                  <thead className="bg-slate-50 text-xs text-slate-500 uppercase tracking-wider">
                    <tr className="border-b">
                      <th className="py-2 px-2 text-left whitespace-nowrap">Fecha</th>
                      <th className="py-2 px-2 text-left whitespace-nowrap">#</th>
                      <th className="py-2 px-2 text-left whitespace-nowrap">Tipo</th>
                      <th className="py-2 px-2 text-left whitespace-nowrap">Tercero</th>
                      <th className="py-2 px-2 text-left whitespace-nowrap">UN</th>
                      <th className="py-2 px-2 text-left whitespace-nowrap">Categoría</th>
                      <th className="py-2 px-2 text-left whitespace-nowrap">Descripción</th>
                      <th className="py-2 px-2 text-right whitespace-nowrap">Monto</th>
                      <th className="py-2 px-2 text-center whitespace-nowrap">Asig.</th>
                      <th className="py-2 px-2 text-center w-10" />
                    </tr>
                  </thead>
                  <tbody>
                    {flatData.items.map((item) => (
                      <tr
                        key={item.movement_id}
                        className="border-b cursor-pointer hover:bg-emerald-50/40 transition-colors group"
                        onClick={() => navigate(`/treasury/${item.movement_id}?returnTo=${encodeURIComponent(location.pathname + location.search)}`)}
                      >
                        <td className="py-2 px-2 whitespace-nowrap">{formatDate(item.date)}</td>
                        <td className="py-2 px-2">{item.movement_number}</td>
                        <td className="py-2 px-2 text-xs text-slate-500">{item.movement_type}</td>
                        <td className="py-2 px-2">{item.third_party_name ?? "—"}</td>
                        <td className="py-2 px-2">{item.business_unit_name ?? "Sin Asignar"}</td>
                        <td className="py-2 px-2">{item.expense_category_name ?? "Sin Categoría"}</td>
                        <td className="py-2 px-2 max-w-[260px] truncate" title={item.description ?? ""}>
                          {item.description ?? ""}
                        </td>
                        <td className="py-2 px-2 text-right tabular-nums font-medium">{formatCurrency(item.amount)}</td>
                        <td className="py-2 px-2 text-center">
                          <Badge variant="outline" className={`${ALLOC_COLORS[item.allocation_type]} text-xs`}>
                            {ALLOC_LABELS[item.allocation_type]}
                          </Badge>
                        </td>
                        <td className="py-2 px-2 text-center text-slate-400">
                          <ExternalLink className="h-4 w-4 opacity-0 group-hover:opacity-100 transition-opacity inline" />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>
        )}

        <ExpenseDetailSheet
          open={detailOpen}
          onOpenChange={(v) => { if (!v) setDetailContext(null); }}
          context={detailContext}
          dateFrom={dateFrom}
          dateTo={dateTo}
          returnTo={location.pathname + location.search}
        />
    </ReportsLayout>
  );
}
