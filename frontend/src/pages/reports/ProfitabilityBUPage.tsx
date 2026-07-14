import { useState } from "react";
import { Link } from "react-router-dom";
import { useDateFilter } from "@/stores/dateFilterStore";
import { usePermissions } from "@/hooks/usePermissions";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { DateRangePicker } from "@/components/shared/DateRangePicker";
import { ResponsiveFilterBar } from "@/components/shared/ResponsiveFilterBar";
import { ChevronDown, ChevronRight, FileSpreadsheet, Settings } from "lucide-react";
import ReportsLayout from "./ReportsLayout";
import { useProfitabilityByBU } from "@/hooks/useReports";
import { formatCurrency, formatPercentage } from "@/utils/formatters";
import { exportProfitabilityBUExcel } from "@/utils/excelExport";
import type { BusinessUnitProfitability, DoubleEntryProfitability, PnlReconciliation } from "@/types/reports";

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

function PasaManoCard({
  de,
  grandTotalNet,
  reconciliation,
}: {
  de: DoubleEntryProfitability;
  grandTotalNet: number;
  reconciliation: PnlReconciliation;
}) {
  const [expanded, setExpanded] = useState(false);
  const [generalExpanded, setGeneralExpanded] = useState(false);
  const [reconExpanded, setReconExpanded] = useState(false);
  const { hasPermission } = usePermissions();
  const hasActivity =
    de.sales_total !== 0 || de.gross_profit !== 0 || de.commissions !== 0 ||
    de.direct_expenses !== 0 || de.general_expenses !== 0;

  const Line = ({ label, value, negative = false, bold = false }: { label: string; value: number; negative?: boolean; bold?: boolean }) => (
    <div className={`flex justify-between gap-3 py-1.5 ${bold ? "font-semibold" : ""}`}>
      <span className={bold ? "" : "text-slate-600"}>{label}</span>
      <span className={`tabular-nums ${negative && value !== 0 ? "text-red-700" : ""}`}>
        {negative && value !== 0 ? `(${formatCurrency(value)})` : formatCurrency(value)}
      </span>
    </div>
  );

  // Linea de gasto expandible (Directos / Generales comparten patron)
  const ExpenseLine = ({
    label, total, hasDetail, isOpen, onToggle,
  }: {
    label: string; total: number; hasDetail: boolean; isOpen: boolean; onToggle: () => void;
  }) => (
    <div className="flex justify-between gap-3 py-1.5">
      <button
        type="button"
        className="flex items-center gap-1 text-slate-600 hover:text-emerald-700"
        onClick={onToggle}
        disabled={!hasDetail}
      >
        {hasDetail && (isOpen ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />)}
        {label}
      </button>
      <span className={`tabular-nums ${total !== 0 ? "text-red-700" : ""}`}>
        {total !== 0 ? `(${formatCurrency(total)})` : formatCurrency(0)}
      </span>
    </div>
  );

  return (
    <Card className="shadow-sm">
      <CardContent className="p-4 md:p-6">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-1 mb-3">
          <h3 className="font-semibold text-indigo-900 flex items-center gap-2">
            {de.label} (Doble Partida)
            {hasPermission("treasury.manage_expenses") && (
              <Link
                to="/config/expense-categories"
                title="Configurar % Pasa Mano por categoria de gasto"
                className="text-slate-400 hover:text-indigo-700"
              >
                <Settings className="h-4 w-4" />
              </Link>
            )}
          </h3>
          <span className="text-xs text-slate-500">
            Comisiones y gastos directos asignados + % de gastos generales por categoría
          </span>
        </div>

        {!hasActivity ? (
          <p className="text-sm text-slate-400">Sin actividad de doble partida en el periodo</p>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-x-10 text-sm">
            <div>
              <Line label="Ventas Pasa Mano" value={de.sales_total} />
              <Line label="Compras Pasa Mano" value={de.purchases_total} />
              <Separator className="my-1" />
              <Line label="Margen Bruto" value={de.gross_profit} bold />
            </div>
            <div>
              <Line label="Comisiones" value={de.commissions} negative />
              <ExpenseLine
                label="Gastos Directos"
                total={de.direct_expenses}
                hasDetail={de.direct_expenses_detail.length > 0}
                isOpen={expanded}
                onToggle={() => setExpanded(!expanded)}
              />
              {expanded &&
                de.direct_expenses_detail.map((d) => (
                  <div key={d.category_name} className="flex justify-between gap-3 py-0.5 pl-5 text-xs text-slate-500">
                    <span>{d.category_name}</span>
                    <span className="tabular-nums">{formatCurrency(d.amount)}</span>
                  </div>
                ))}
              <ExpenseLine
                label="Gastos Generales asignados"
                total={de.general_expenses}
                hasDetail={de.general_expenses_detail.length > 0}
                isOpen={generalExpanded}
                onToggle={() => setGeneralExpanded(!generalExpanded)}
              />
              {generalExpanded &&
                de.general_expenses_detail.map((d) => (
                  <div key={d.category_name} className="flex justify-between gap-3 py-0.5 pl-5 text-xs text-slate-500">
                    <span>{d.category_name} ({formatPercentage(d.pct)})</span>
                    <span className="tabular-nums">{formatCurrency(d.amount)}</span>
                  </div>
                ))}
              <Separator className="my-1" />
              <div className="flex justify-between gap-3 py-1.5 font-semibold">
                <span>Utilidad Neta Pasa Mano</span>
                <span className={`tabular-nums ${de.net_profit >= 0 ? "text-emerald-700" : "text-red-700"}`}>
                  {formatCurrency(de.net_profit)}
                  <span className="ml-2 text-xs font-normal text-slate-500">({formatPercentage(de.net_margin)})</span>
                </span>
              </div>
            </div>
          </div>
        )}

        <Separator className="my-3" />
        <div className="flex justify-between gap-3 text-sm font-bold">
          <span>TOTAL GENERAL (Bodega + Pasa Mano)</span>
          <span className={`tabular-nums ${grandTotalNet >= 0 ? "text-emerald-700" : "text-red-700"}`}>
            {formatCurrency(grandTotalNet)}
          </span>
        </div>

        {/* Conciliacion con P&L: lineas no atribuibles a UN (plan A.2 §3.7) */}
        <div className="mt-2 text-sm">
          <button
            type="button"
            className="flex items-center gap-1 text-xs text-slate-500 hover:text-indigo-700"
            onClick={() => setReconExpanded(!reconExpanded)}
          >
            {reconExpanded ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
            Conciliación con Estado de Resultados
          </button>
          {reconExpanded && (
            <div className="mt-1 pl-4 border-l-2 border-slate-100">
              <Line label="Ingresos por Servicios" value={reconciliation.service_income} />
              <Line label="Ingresos Financieros (Intereses)" value={reconciliation.interest_income ?? 0} />
              <Line label="Transformaciones (neto)" value={reconciliation.transformation_net} />
              <Line label="Ajustes de Inventario (neto)" value={reconciliation.inventory_adjustment_net} />
              <Line label="Ajustes de Terceros (neto)" value={reconciliation.tp_adjustment_net} />
              <Line label="Ajuste Costo por Sobreventa y Reversiones" value={reconciliation.oversell_cost_adjustment} />
              <Separator className="my-1" />
              <div className="flex justify-between gap-3 py-1.5 font-bold">
                <span>= Utilidad Neta P&L</span>
                <span className={`tabular-nums ${reconciliation.pnl_net_profit >= 0 ? "text-emerald-700" : "text-red-700"}`}>
                  {formatCurrency(reconciliation.pnl_net_profit)}
                </span>
              </div>
              <p className="text-xs text-slate-400 pb-1">
                Servicios, transformaciones y ajustes no pertenecen a ninguna unidad de negocio —
                por eso el TOTAL GENERAL difiere de la utilidad del P&L.
              </p>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
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
            <div className="px-3 pt-3 text-xs text-slate-500">
              Solo operación de bodega — el Pasa Mano (doble partida) se analiza en la sección de abajo
            </div>
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
        <div className="text-center text-slate-400 py-8">No hay datos de bodega para el periodo seleccionado</div>
      )}

      {data && (
        <PasaManoCard
          de={data.double_entry}
          grandTotalNet={data.grand_total_net}
          reconciliation={data.pnl_reconciliation}
        />
      )}
    </ReportsLayout>
  );
}
