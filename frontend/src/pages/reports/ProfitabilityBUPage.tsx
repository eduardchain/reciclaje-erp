import { useState } from "react";
import { useDateFilter } from "@/stores/dateFilterStore";
import { Card, CardContent } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { DateRangePicker } from "@/components/shared/DateRangePicker";
import { ChevronDown, ChevronRight } from "lucide-react";
import ReportsLayout from "./ReportsLayout";
import { useProfitabilityByBU } from "@/hooks/useReports";
import { formatCurrency, formatPercentage } from "@/utils/formatters";
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
              <td className="py-1 px-3 pl-8" colSpan={3}>Margen Doble Partida</td>
              <td className="py-1 px-3 text-right tabular-nums">{formatCurrency(bu.de_profit)}</td>
              <td colSpan={6} />
            </tr>
          )}
          {bu.direct_expenses_detail.map((d) => (
            <tr key={d.category_name} className="text-xs text-slate-500 bg-slate-50/50">
              <td className="py-1 px-3 pl-8" colSpan={4}>{d.category_name}</td>
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
      <div className="flex justify-between items-center">
        <h2 className="text-lg font-semibold">Rentabilidad por Unidad de Negocio</h2>
        <DateRangePicker dateFrom={dateFrom} dateTo={dateTo} onDateFromChange={setDateFrom} onDateToChange={setDateTo} />
      </div>

      {isLoading && <div className="text-center text-slate-500 py-8">Cargando...</div>}

      {data && (
        <Card className="shadow-sm overflow-x-auto">
          <CardContent className="p-0">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b bg-slate-50 text-xs text-slate-500 uppercase tracking-wider">
                  <th className="py-2 px-3 text-left">Unidad de Negocio</th>
                  <th className="py-2 px-3 text-right">Ventas</th>
                  <th className="py-2 px-3 text-right">COGS</th>
                  <th className="py-2 px-3 text-right">Ut. Bruta</th>
                  <th className="py-2 px-3 text-right">G. Directos</th>
                  <th className="py-2 px-3 text-right">G. Compartidos</th>
                  <th className="py-2 px-3 text-right">G. Generales</th>
                  <th className="py-2 px-3 text-right">Comisiones</th>
                  <th className="py-2 px-3 text-right">Ut. Neta</th>
                  <th className="py-2 px-3 text-right">Margen</th>
                </tr>
              </thead>
              <tbody>
                {data.business_units.map((bu) => (
                  <BURow key={bu.business_unit_id ?? "unassigned"} bu={bu} />
                ))}
                <tr><td colSpan={10}><Separator /></td></tr>
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
