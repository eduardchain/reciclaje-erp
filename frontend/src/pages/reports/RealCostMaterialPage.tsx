import { useState } from "react";
import { useDateFilter } from "@/stores/dateFilterStore";
import { DateRangePicker } from "@/components/shared/DateRangePicker";
import { ChevronDown, ChevronRight } from "lucide-react";
import ReportsLayout from "./ReportsLayout";
import { useRealCostByMaterial } from "@/hooks/useReports";
import { formatCurrency } from "@/utils/formatters";
import type { BusinessUnitOverhead } from "@/types/reports";

function BUSection({ bu }: { bu: BusinessUnitOverhead }) {
  const [expanded, setExpanded] = useState(true);

  return (
    <div className="border rounded-lg overflow-hidden">
      <button
        type="button"
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between px-4 py-3 bg-slate-50 hover:bg-slate-100 transition-colors"
      >
        <div className="flex items-center gap-2">
          {expanded ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
          <span className="font-semibold text-sm">{bu.business_unit_name}</span>
        </div>
        <div className="flex gap-6 text-xs text-slate-500">
          <span>Gastos: <span className="font-medium text-slate-700">{formatCurrency(bu.total_expenses)}</span></span>
          <span>Kg: <span className="font-medium text-slate-700">{bu.kg_purchased.toLocaleString("es-CO", { maximumFractionDigits: 2 })}</span></span>
          <span>Overhead: <span className="font-medium text-emerald-700">{formatCurrency(bu.overhead_rate)}/kg</span></span>
        </div>
      </button>

      {expanded && (
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b text-xs text-slate-500 uppercase tracking-wider">
              <th className="py-2 px-4 text-left">Codigo</th>
              <th className="py-2 px-4 text-left">Material</th>
              <th className="py-2 px-4 text-right">Costo Promedio</th>
              <th className="py-2 px-4 text-right">Overhead</th>
              <th className="py-2 px-4 text-right">Costo Real</th>
            </tr>
          </thead>
          <tbody>
            {bu.materials.map((m) => (
              <tr key={m.material_id} className="border-b last:border-b-0 hover:bg-slate-50">
                <td className="py-2 px-4 font-mono text-xs">{m.material_code}</td>
                <td className="py-2 px-4">{m.material_name}</td>
                <td className="py-2 px-4 text-right tabular-nums">{formatCurrency(m.average_cost)}</td>
                <td className="py-2 px-4 text-right tabular-nums text-amber-600">{formatCurrency(m.overhead_rate)}</td>
                <td className="py-2 px-4 text-right tabular-nums font-medium">{formatCurrency(m.real_cost)}</td>
              </tr>
            ))}
            {bu.materials.length === 0 && (
              <tr><td colSpan={5} className="py-4 text-center text-slate-400 text-xs">Sin materiales en esta unidad</td></tr>
            )}
          </tbody>
        </table>
      )}
    </div>
  );
}

export default function RealCostMaterialPage() {
  const { dateFrom, dateTo, setDateFrom, setDateTo } = useDateFilter();
  const { data, isLoading } = useRealCostByMaterial({ date_from: dateFrom, date_to: dateTo });

  return (
    <ReportsLayout>
      <div className="flex justify-between items-center">
        <h2 className="text-lg font-semibold">Costo Real por Material</h2>
        <DateRangePicker dateFrom={dateFrom} dateTo={dateTo} onDateFromChange={setDateFrom} onDateToChange={setDateTo} />
      </div>

      {isLoading && <div className="text-center text-slate-500 py-8">Cargando...</div>}

      {data && (
        <div className="space-y-4">
          {data.business_units.map((bu) => (
            <BUSection key={bu.business_unit_id ?? "unassigned"} bu={bu} />
          ))}
        </div>
      )}

      {data && data.business_units.length === 0 && (
        <div className="text-center text-slate-400 py-8">No hay datos para el periodo seleccionado</div>
      )}
    </ReportsLayout>
  );
}
