import { useState, useMemo, useEffect } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Separator } from "@/components/ui/separator";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { ChevronRight, ChevronDown, Expand, Shrink, FileSpreadsheet, FileText, CheckCircle2 } from "lucide-react";
import { ResponsiveFilterBar } from "@/components/shared/ResponsiveFilterBar";
import ReportsLayout from "./ReportsLayout";
import { useBalanceDetailed } from "@/hooks/useReports";
import { formatCurrency, formatDate } from "@/utils/formatters";
import { exportBalanceDetailedExcel } from "@/utils/excelExport";
import { exportBalanceDetailedPDF } from "@/utils/pdfExport";
import { useAuthStore } from "@/stores/authStore";
import { useDateFilter } from "@/stores/dateFilterStore";
import { useScrollRestoration, saveScroll } from "@/hooks/useScrollRestoration";
import {
  transformBalanceData,
  filtersAreDefault,
  filtersLabel,
  sectionExtraHidden,
  DEFAULT_BALANCE_FILTERS,
  type BalanceFilters,
  type BalanceSortBy,
} from "@/utils/balanceTransform";
import type { BalanceDetailedSection, BalanceDetailedItem, BalanceDetailedGroup } from "@/types/reports";

const BALANCE_FILTERS_STORAGE_KEY = "balance_detailed_filters_v1";

const ASSET_SECTION_ORDER = [
  "cash_and_bank", "inventory_liquidated",
  "customers_receivable", "supplier_advances", "service_provider_advances",
  "liability_advances", "investor_receivable",
  "provision_funds", "prepaid_expenses", "generic_receivable", "fixed_assets",
];

const LIABILITY_SECTION_ORDER = [
  "suppliers_payable", "service_provider_payable", "liability_debt",
  "investors_partners", "investors_obligations",
  "investors_legacy", "customer_advances", "provision_obligations",
  "generic_payable",
];

function fmtBalance(value: number) {
  if (value < 0) return `(${formatCurrency(Math.abs(value))})`;
  return formatCurrency(value);
}

function getItemLink(sectionKey: string, item: BalanceDetailedItem): string | null {
  if (sectionKey === "cash_and_bank") return `/treasury/account-movements?account_id=${item.id}&returnTo=/reports/balance-detailed`;
  if (sectionKey === "inventory_liquidated") return `/inventory/movements?material_id=${item.id}`;
  if (sectionKey === "fixed_assets") return `/treasury/fixed-assets`;
  // Terceros → estado de cuenta
  return `/treasury/account-statement?third_party_id=${item.id}&returnTo=/reports/balance-detailed`;
}

function ItemDetail({ item, sectionKey }: { item: BalanceDetailedItem; sectionKey: string }) {
  if (sectionKey === "cash_and_bank" && item.account_type) {
    const typeLabel: Record<string, string> = { cash: "Efectivo", bank: "Banco", digital: "Digital" };
    return <span className="text-xs text-slate-400">{typeLabel[item.account_type] ?? item.account_type}</span>;
  }
  if (sectionKey === "inventory_liquidated" && item.stock != null && item.avg_cost != null) {
    return <span className="text-xs text-slate-400">{item.code} | {item.stock.toLocaleString("es-CO")} kg x {formatCurrency(item.avg_cost)}</span>;
  }
  if (sectionKey === "fixed_assets" && item.purchase_value != null && item.accumulated_depreciation != null) {
    return <span className="text-xs text-slate-400">Costo: {formatCurrency(item.purchase_value)} | Dep. Acum.: {formatCurrency(item.accumulated_depreciation)}</span>;
  }
  if (item.investor_type) {
    const typeLabel: Record<string, string> = { socio: "Socio", obligacion_financiera: "Obl. Financiera" };
    return <span className="text-xs text-slate-400">{typeLabel[item.investor_type] ?? item.investor_type}</span>;
  }
  return null;
}

export default function BalanceDetailedPage() {
  const _now = new Date();
  const today = `${_now.getFullYear()}-${String(_now.getMonth() + 1).padStart(2, "0")}-${String(_now.getDate()).padStart(2, "0")}`;
  const { balanceAsOfDate: asOfDate, setBalanceAsOfDate: setAsOfDate } = useDateFilter();
  const { data, isLoading } = useBalanceDetailed(asOfDate || undefined);
  const navigate = useNavigate();
  const location = useLocation();
  const { organizationId, organizations } = useAuthStore();
  const orgName = organizations.find((o) => o.id === organizationId)?.name ?? "";

  useScrollRestoration(!isLoading);

  const expandedStorageKey = `expanded:${location.pathname}`;
  const [expanded, setExpanded] = useState<Set<string>>(() => {
    try {
      const saved = sessionStorage.getItem(expandedStorageKey);
      return saved ? new Set(JSON.parse(saved)) : new Set();
    } catch {
      return new Set();
    }
  });

  useEffect(() => {
    sessionStorage.setItem(expandedStorageKey, JSON.stringify([...expanded]));
  }, [expanded]);

  // Filtros del usuario (threshold + sort), persistidos en localStorage
  const [filters, setFilters] = useState<BalanceFilters>(() => {
    try {
      const saved = localStorage.getItem(BALANCE_FILTERS_STORAGE_KEY);
      if (saved) {
        const parsed = JSON.parse(saved);
        // Validar shape minimo
        return {
          hideBelow: typeof parsed.hideBelow === "number" ? parsed.hideBelow : DEFAULT_BALANCE_FILTERS.hideBelow,
          sortBy: parsed.sortBy === "alphabetical" || parsed.sortBy === "amount_desc"
            ? parsed.sortBy
            : DEFAULT_BALANCE_FILTERS.sortBy,
        };
      }
    } catch {
      /* ignore */
    }
    return DEFAULT_BALANCE_FILTERS;
  });
  useEffect(() => {
    localStorage.setItem(BALANCE_FILTERS_STORAGE_KEY, JSON.stringify(filters));
  }, [filters]);

  // Data transformada (ordenada + filtrada) — fuente unica para web/PDF/Excel
  const displayData = useMemo(
    () => (data ? transformBalanceData(data, filters) : null),
    [data, filters],
  );
  const filtersActiveLabel = filtersLabel(filters, formatCurrency);
  const hasActiveFilters = !filtersAreDefault(filters);

  const allExpandableKeys = useMemo(() => {
    if (!displayData) return [];
    const keys: string[] = [];
    const addSections = (sections: Record<string, BalanceDetailedSection>) => {
      for (const [key, section] of Object.entries(sections)) {
        keys.push(key);
        if (section.groups) {
          for (const g of section.groups) keys.push(`${key}:${g.label}`);
        }
      }
    };
    addSections(displayData.assets);
    addSections(displayData.liabilities);
    return keys;
  }, [displayData]);

  const toggleSection = (key: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };

  const expandAll = () => setExpanded(new Set(allExpandableKeys));
  const collapseAll = () => setExpanded(new Set());

  const currentUrl = location.pathname + location.search;
  const renderItems = (items: BalanceDetailedItem[], sectionKey: string) =>
    items.map((item) => {
      const link = getItemLink(sectionKey, item);
      return (
        <div
          key={item.id}
          className={`flex items-center justify-between py-1 px-2 rounded text-sm ${link ? "hover:bg-slate-100 cursor-pointer" : ""}`}
          onClick={() => {
            if (!link) return;
            saveScroll(currentUrl);
            navigate(link);
          }}
        >
          <div className="flex flex-col">
            <span>
              {item.name}
              {item.is_inactive && (
                <span className="ml-2 inline-block rounded bg-slate-100 px-1.5 py-0.5 text-[10px] font-medium text-slate-500 align-middle">
                  Inactivo
                </span>
              )}
            </span>
            <ItemDetail item={item} sectionKey={sectionKey} />
          </div>
          <span className="tabular-nums font-medium">{fmtBalance(item.balance)}</span>
        </div>
      );
    });

  const renderHiddenNote = (count: number | undefined, total: number | undefined) => {
    if (!count || count <= 0) return null;
    const totalStr = total != null && total !== 0 ? ` (suma: ${fmtBalance(total)})` : "";
    return (
      <p className="text-xs text-slate-400 italic px-2 py-1">
        {count} {count === 1 ? "item por debajo del umbral no mostrado" : "items por debajo del umbral no mostrados"}{totalStr}
      </p>
    );
  };

  const renderGroup = (group: BalanceDetailedGroup, sectionKey: string, colorClass: string) => {
    const groupKey = `${sectionKey}:${group.label}`;
    const isGroupOpen = expanded.has(groupKey);
    return (
      <div key={groupKey} className="border-t border-slate-50">
        <button
          className="w-full flex items-center justify-between px-2 py-1.5 text-sm hover:bg-slate-50 transition-colors"
          onClick={() => toggleSection(groupKey)}
        >
          <div className="flex items-center gap-2">
            {isGroupOpen ? <ChevronDown className="w-3.5 h-3.5 text-slate-400" /> : <ChevronRight className="w-3.5 h-3.5 text-slate-400" />}
            <span className="font-medium text-slate-600">{group.label}</span>
            <span className="text-xs text-slate-400">({group.items.length})</span>
          </div>
          <span className={`font-medium tabular-nums text-xs ${colorClass}`}>{fmtBalance(group.total)}</span>
        </button>
        {isGroupOpen && (
          <div className="pl-6 pr-2 pb-1 space-y-0.5">
            {renderItems(group.items, sectionKey)}
            {renderHiddenNote(group.hidden_count, group.hidden_total)}
          </div>
        )}
      </div>
    );
  };

  const renderSection = (key: string, section: BalanceDetailedSection, colorClass: string) => {
    const isOpen = expanded.has(key);
    const hasItems = section.items.length > 0;
    const hasGroups = section.groups && section.groups.length > 0;

    return (
      <div key={key} className="border-b border-slate-100 last:border-b-0">
        <button
          className={`w-full flex items-center justify-between px-3 py-2 text-sm hover:bg-slate-50 transition-colors ${!hasItems ? "opacity-50" : ""}`}
          onClick={() => hasItems && toggleSection(key)}
          disabled={!hasItems}
        >
          <div className="flex items-center gap-2">
            {hasItems ? (
              isOpen ? <ChevronDown className="w-4 h-4 text-slate-400" /> : <ChevronRight className="w-4 h-4 text-slate-400" />
            ) : (
              <ChevronRight className="w-4 h-4 text-slate-300" />
            )}
            <span className="font-medium">{section.label}</span>
            {hasItems && <span className="text-xs text-slate-400">({section.items.length})</span>}
          </div>
          <span className={`font-semibold tabular-nums ${colorClass}`}>{fmtBalance(section.total)}</span>
        </button>
        {isOpen && hasItems && (
          <div className="pl-9 pr-3 pb-2 space-y-1">
            {hasGroups ? (
              <>
                {section.groups!.map((g) => renderGroup(g, key, colorClass))}
                {/* Items ocultos por grupos enteramente saltados (delta no cubierto por notas por-grupo) */}
                {(() => {
                  const extra = sectionExtraHidden(section);
                  return renderHiddenNote(extra.count, extra.total);
                })()}
              </>
            ) : (
              <>
                {renderItems(section.items, key)}
                {renderHiddenNote(section.hidden_count, section.hidden_total)}
              </>
            )}
          </div>
        )}
      </div>
    );
  };

  const orderedSections = (
    sections: Record<string, BalanceDetailedSection>,
    order: string[],
    colorClass: string,
  ) => {
    return order
      .filter((key) => key in sections)
      .map((key) => renderSection(key, sections[key], colorClass));
  };

  return (
    <ReportsLayout>
      {isLoading && <div className="text-center text-slate-500 py-8">Cargando...</div>}

      {data && displayData && (
        <div className="space-y-4">
          {/* Header */}
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
            <div className="flex flex-col gap-1">
              <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                Corte al: {formatDate(data.as_of_date)}
              </p>
              {hasActiveFilters && (
                <span className="text-xs text-amber-700 bg-amber-50 border border-amber-200 px-2 py-0.5 rounded inline-block w-fit">
                  {filtersActiveLabel}
                </span>
              )}
            </div>
            <ResponsiveFilterBar className="sm:items-center">
              <Input type="date" value={asOfDate} max={today} onChange={(e) => setAsOfDate(e.target.value)} className="w-full sm:w-40 h-8 text-xs" />
              {asOfDate && <Button variant="ghost" size="sm" className="text-xs h-8 w-full sm:w-auto" onClick={() => setAsOfDate("")}>Hoy</Button>}
              <Input
                type="number"
                min={0}
                step={1000}
                value={filters.hideBelow || ""}
                placeholder="Ocultar < $"
                onChange={(e) => setFilters((f) => ({ ...f, hideBelow: Math.max(0, Number(e.target.value) || 0) }))}
                className="w-full sm:w-36 h-8 text-xs"
                title="Ocultar items con |saldo| menor a este valor"
              />
              <Select value={filters.sortBy} onValueChange={(v) => setFilters((f) => ({ ...f, sortBy: v as BalanceSortBy }))}>
                <SelectTrigger className="w-full sm:w-32 h-8 text-xs">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="amount_desc">Monto desc</SelectItem>
                  <SelectItem value="alphabetical">Alfabético</SelectItem>
                </SelectContent>
              </Select>
              {hasActiveFilters && (
                <Button variant="ghost" size="sm" className="text-xs h-8 w-full sm:w-auto" onClick={() => setFilters(DEFAULT_BALANCE_FILTERS)}>
                  Reset
                </Button>
              )}
              <Button variant="outline" size="sm" onClick={expandAll} className="w-full sm:w-auto">
                <Expand className="w-4 h-4 mr-1" /> Expandir
              </Button>
              <Button variant="outline" size="sm" onClick={collapseAll} className="w-full sm:w-auto">
                <Shrink className="w-4 h-4 mr-1" /> Colapsar
              </Button>
              <Button variant="outline" size="sm" onClick={() => exportBalanceDetailedPDF(displayData, orgName, filtersActiveLabel)} className="w-full sm:w-auto">
                <FileText className="w-4 h-4 mr-1" /> PDF
              </Button>
              <Button variant="outline" size="sm" onClick={() => exportBalanceDetailedExcel(displayData, filtersActiveLabel)} className="w-full sm:w-auto">
                <FileSpreadsheet className="w-4 h-4 mr-1" /> Excel
              </Button>
            </ResponsiveFilterBar>
          </div>

          {/* Activos */}
          <Card className="shadow-sm">
            <div className="px-4 py-3 border-b bg-blue-50">
              <div className="flex items-center justify-between">
                <h3 className="text-sm font-semibold uppercase tracking-wider text-blue-700">Activos</h3>
                <span className="text-lg font-bold text-blue-700">{fmtBalance(displayData.total_assets)}</span>
              </div>
            </div>
            <CardContent className="p-0">
              {orderedSections(displayData.assets, ASSET_SECTION_ORDER, "text-blue-700")}
            </CardContent>
          </Card>

          {/* Pasivos */}
          <Card className="shadow-sm">
            <div className="px-4 py-3 border-b bg-red-50">
              <div className="flex items-center justify-between">
                <h3 className="text-sm font-semibold uppercase tracking-wider text-red-700">Pasivos</h3>
                <span className="text-lg font-bold text-red-700">{fmtBalance(displayData.total_liabilities)}</span>
              </div>
            </div>
            <CardContent className="p-0">
              {orderedSections(displayData.liabilities, LIABILITY_SECTION_ORDER, "text-red-700")}
            </CardContent>
          </Card>

          {/* Patrimonio */}
          <Card className="border-2 border-emerald-200 bg-emerald-50 shadow-sm">
            <CardContent className="py-4 space-y-2">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-sm font-semibold uppercase tracking-wider text-emerald-700">Patrimonio</h3>
                  <p className="text-xs text-emerald-600 mt-1">{displayData.equity_label}</p>
                </div>
                <span className="text-2xl font-bold text-emerald-700">{fmtBalance(displayData.equity)}</span>
              </div>
              {(displayData.accumulated_profit !== 0 || displayData.distributed_profit !== 0) && (
                <div className="pt-2 border-t border-emerald-200 space-y-1 text-sm">
                  <div className="flex justify-between"><span className="text-emerald-700">Utilidad Acumulada</span><span className="tabular-nums font-medium">{fmtBalance(displayData.accumulated_profit)}</span></div>
                  <div className="flex justify-between"><span className="text-red-600">(-) Utilidades Distribuidas</span><span className="tabular-nums font-medium text-red-600">{fmtBalance(displayData.distributed_profit)}</span></div>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Verificacion */}
          <Separator />
          <div className={`flex items-center justify-center gap-2 py-3 rounded-md text-sm font-medium ${displayData.verification.is_balanced ? "bg-emerald-50 text-emerald-700" : "bg-red-50 text-red-700"}`}>
            <CheckCircle2 className="w-4 h-4" />
            <span>{displayData.verification.formula} = {fmtBalance(displayData.verification.result)}</span>
            {displayData.verification.is_balanced && <span>Cuadrado</span>}
          </div>
        </div>
      )}
    </ReportsLayout>
  );
}
