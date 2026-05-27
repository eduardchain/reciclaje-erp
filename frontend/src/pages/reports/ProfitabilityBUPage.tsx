import { useState } from "react";
import { useDateFilter } from "@/stores/dateFilterStore";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { DateRangePicker } from "@/components/shared/DateRangePicker";
import { ResponsiveFilterBar } from "@/components/shared/ResponsiveFilterBar";
import { ChevronDown, ChevronRight, FileSpreadsheet } from "lucide-react";
import ReportsLayout from "./ReportsLayout";
import { useProfitabilityByBU } from "@/hooks/useReports";
import { formatCurrency, formatPercentage } from "@/utils/formatters";
import { exportProfitabilityBUExcel } from "@/utils/excelExport";
import type { BusinessUnitProfitability } from "@/types/reports";

function BURow({ bu, isTotal = false }: { bu: BusinessUnitProfitability; isTotal?: boolean }) {
  const [expanded, setExpanded] = useState(false);
  const cls = isTotal ? "font-bold bg-slate-50" : "";
  const nameEl = isTotal ? (
    <span className="font-bold">{bu.business_unit_name}</span>
  ) : (
    <button type="button" className="flex items-center gap-1 hover:text-emerald-700" onClick={() => setExpanded(!expanded)}>
      {expanded ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
      <span className="font-medium">{bu.business_unit_name}</span>
    </button>
  );

  return (
    <>
      <tr className={`text-sm border-b ${cls}`}>
        <td className="py-2 px-3">{nameEl}</td>
        <td className="py-2 px-3 text-right tabular-nums">{formatCurrency(bu.purchases_total)}</td>
        <td className="py-2 px-3 text-right tabular-nums text-slate-500">{formatPercentage(bu.purchases_weight_pct)}</td>
        <td className="py-2 px-3 text-right tabular-nums">{formatCurrency(bu.sales_revenue)}</td>
        <td className="py-2 px-3 text-right tabular-nums">{formatCurrency(bu.sales_cogs)}</td>
        <td className="py-2 px-3 text-right tabular-nums">{formatCurrency(bu.total_gross_profit)}</td>
        <td className="py-2 px-3 text-right tabular-nums">{formatCurrency(bu.direct_expenses)}</td>
        <td className="py-2 px-3 text-right tabular-nums">{formatCurrency(bu.shared_expenses)}</td>
        <td className="py-2 px-3 text-right tabular-nums">{formatCurrency(bu.general_expenses)}</td>
        <td className="py-2 px-3 text-right tabular-nums">{formatCurrency(bu.sale_commissions)}</td>
        <td className={`py-2 px-3 text-right tabular-nums font-medium ${bu.net_profit >= 0 ? "text-emerald-700" : "text-red-700"}`}>
          {formatCurrency(bu.net_profit)}
        </td>
        <td className="py-2 px-3 text-right tabular-nums">{formatPercentage(bu.net_margin)}</td>
      </tr>
      {expanded && !isTotal && (
        <>
          {bu.de_profit !== 0 && (
            <tr className="text-xs text-slate-500 bg-slate-50/50">
              <td className="py-1 px-3 pl-8" colSpan={5}>Margen Doble Partida</td>
              <td className="py-1 px-3 text-right tabular-nums">{formatCurrency(bu.de_profit)}</td>
              <td colSpan={6} />
            </tr>
          )}
          {bu.direct_expenses_detail.map((d) => (
            <tr key={d.category_name} className="text-xs text-slate-500 bg-slate-50/50">
              <td className="py-1 px-3 pl-8" colSpan={6}>{d.category_name}</td>
              <td className="py-1 px-3 text-right tabular-nums">{formatCurrency(d.amount)}</td>
              <td colSpan={5} />
            </tr>
          ))}
        </>
      )}
    </>
  );
}

export default function ProfitabilityBUPage() {
  const { dateFrom, dateTo, setDateFrom, setDateTo } = useDateFilter();
  const { data, isLoading } = useProfitabilityByBU({ date_from: dateFrom, date_to: dateTo });

  return (
    <ReportsLayout>
      <div className="flex flex-col sm:flex-row sm:justify-between sm:items-center gap-3">
        <h2 className="text-lg font-semibold">Rentabilidad por Unidad de Negocio</h2>
        <ResponsiveFilterBar>
          {data && (
            <Button variant="outline" size="sm" onClick={() => exportProfitabilityBUExcel(data)} className="w-full sm:w-auto">
              <FileSpreadsheet className="w-4 h-4 mr-1" /> Excel
            </Button>
          )}
          <DateRangePicker dateFrom={dateFrom} dateTo={dateTo} onDateFromChange={setDateFrom} onDateToChange={setDateTo} />
        </ResponsiveFilterBar>
      </div>

      {isLoading && <div className="text-center text-slate-500 py-8">Cargando...</div>}

      {data && (
        <Card className="shadow-sm overflow-x-auto">
          <CardContent className="p-0">
            <table className="w-full text-sm min-w-[900px]">
              <thead>
                <tr className="border-b bg-slate-50 text-xs text-slate-500 uppercase tracking-wider">
                  <th className="py-2 px-3 text-left whitespace-nowrap">Unidad de Negocio</th>
                  <th className="py-2 px-3 text-right whitespace-nowrap">Compras</th>
                  <th className="py-2 px-3 text-right whitespace-nowrap">Peso %</th>
                  <th className="py-2 px-3 text-right whitespace-nowrap">Ventas</th>
                  <th className="py-2 px-3 text-right whitespace-nowrap">COGS</th>
                  <th className="py-2 px-3 text-right whitespace-nowrap">Ut. Bruta</th>
                  <th className="py-2 px-3 text-right whitespace-nowrap">G. Directos</th>
                  <th className="py-2 px-3 text-right whitespace-nowrap">G. Compartidos</th>
                  <th className="py-2 px-3 text-right whitespace-nowrap">G. Generales</th>
                  <th className="py-2 px-3 text-right whitespace-nowrap">Comisiones</th>
                  <th className="py-2 px-3 text-right whitespace-nowrap">Ut. Neta</th>
                  <th className="py-2 px-3 text-right whitespace-nowrap">Margen</th>
                </tr>
              </thead>
              <tbody>
                {data.business_units.map((bu) => (
                  <BURow key={bu.business_unit_id ?? "unassigned"} bu={bu} />
                ))}
                <tr><td colSpan={12}><Separator /></td></tr>
                <BURow bu={data.totals} isTotal />
              </tbody>
            </table>
          </CardContent>
        </Card>
      )}

      {data && data.business_units.length === 0 && (
        <div className="text-center text-slate-400 py-8">No hay datos para el periodo seleccionado</div>
      )}
    </ReportsLayout>
  );
}
