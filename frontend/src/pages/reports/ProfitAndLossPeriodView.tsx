import { Link, useLocation } from "react-router-dom";
import { useDateFilter } from "@/stores/dateFilterStore";
import { saveScroll, useScrollRestoration } from "@/hooks/useScrollRestoration";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { DateRangePicker } from "@/components/shared/DateRangePicker";
import { ResponsiveFilterBar } from "@/components/shared/ResponsiveFilterBar";
import { FileSpreadsheet, ChevronRight } from "lucide-react";
import { useState } from "react";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useOrgSettings } from "@/hooks/useOrgSettings";
import { useWarehouses } from "@/hooks/useMasterData";
import { useProfitAndLoss } from "@/hooks/useReports";
import { formatCurrency } from "@/utils/formatters";
import { exportPnlExcel } from "@/utils/excelExport";
import { PNL_EXPENSE_DRILL_URLS } from "@/utils/pnlSections";

interface DrillRowProps {
  to: string;
  label: string;
  value: string;
  valueClass?: string;
  indent?: boolean;
}

function DrillRow({ to, label, value, valueClass = "", indent = false }: DrillRowProps) {
  const location = useLocation();
  return (
    <Link
      to={to}
      // Guardar el scroll del P&L antes de irse al drill-down, para que
      // useScrollRestoration lo restaure al volver (patron decision #57)
      onClick={() => saveScroll(location.pathname + location.search)}
      className={`group flex justify-between text-sm cursor-pointer hover:bg-slate-50 rounded px-2 -mx-2 py-0.5 transition-colors ${indent ? "pl-4 text-slate-600" : ""}`}
    >
      <span className="flex items-center gap-1">
        {label}
        <ChevronRight className="h-3.5 w-3.5 text-slate-400 opacity-0 group-hover:opacity-100 transition-opacity" />
      </span>
      <span className={`font-medium ${valueClass}`}>{value}</span>
    </Link>
  );
}

export default function ProfitAndLossPeriodView() {
  const { dateFrom, dateTo, setDateFrom, setDateTo } = useDateFilter();
  // SAC E3.1: P&L por sede — selector solo con two_step_transfers_enabled.
  // Regla de no-regresion: sin flag el selector no se monta y el query no
  // gana el param (URL identica a hoy).
  const { flagEnabled } = useOrgSettings();
  const bySedeEnabled = flagEnabled("two_step_transfers_enabled");
  const [warehouseId, setWarehouseId] = useState<string>("all");
  const { data: warehousesData } = useWarehouses();
  const sedes = (warehousesData?.items ?? []).filter((w) => w.is_active && !w.is_transit);
  const effectiveWarehouse = bySedeEnabled && warehouseId !== "all" ? warehouseId : undefined;
  const { data, isLoading } = useProfitAndLoss({
    date_from: dateFrom,
    date_to: dateTo,
    ...(effectiveWarehouse ? { warehouse_id: effectiveWarehouse } : {}),
  });
  useScrollRestoration(!isLoading);

  return (
    <>
      <ResponsiveFilterBar className="sm:justify-end">
        {bySedeEnabled && (
          <Select value={warehouseId} onValueChange={setWarehouseId}>
            <SelectTrigger className="w-full sm:w-44">
              <SelectValue placeholder="Sede" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Consolidado</SelectItem>
              {sedes.map((w) => (
                <SelectItem key={w.id} value={w.id}>{w.name}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        )}
        {data && <Button variant="outline" size="sm" onClick={() => exportPnlExcel(data)} className="w-full sm:w-auto"><FileSpreadsheet className="w-4 h-4 mr-1" /> Excel</Button>}
        <DateRangePicker dateFrom={dateFrom} dateTo={dateTo} onDateFromChange={setDateFrom} onDateToChange={setDateTo} />
      </ResponsiveFilterBar>

      {effectiveWarehouse && (
        <div className="mb-4 rounded-lg border border-indigo-200 bg-indigo-50 px-4 py-2.5 text-sm text-indigo-800">
          Vista por sede: ventas, costo, comisiones y maquila de{" "}
          <span className="font-medium">{sedes.find((w) => w.id === effectiveWarehouse)?.name}</span>.
          Los gastos operativos sin sede, cruces y ajustes solo aparecen en el consolidado.
        </div>
      )}

      {isLoading && <div className="text-center text-slate-500 py-8">Cargando...</div>}

      {data && (
        <Card className="shadow-sm">
          <CardHeader><CardTitle className="text-sm font-semibold uppercase tracking-wider text-slate-500">Estado de Resultados</CardTitle></CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <DrillRow
                to="/sales?tab=liquidated&dp=exclude&date_field=liquidated_at"
                label={`Ingresos por Ventas (${data.sales_count} ventas)`}
                value={formatCurrency(data.sales_revenue)}
              />
              <DrillRow
                to="/sales?tab=liquidated&dp=exclude&date_field=liquidated_at"
                label="Costo de Ventas (COGS)"
                value={`-${formatCurrency(data.cost_of_goods_sold)}`}
                valueClass="text-red-600"
              />
              <Separator />
              <div className="flex justify-between font-medium"><span>Utilidad Bruta Ventas</span><span className={data.gross_profit_sales >= 0 ? "text-emerald-700" : "text-red-700"}>{formatCurrency(data.gross_profit_sales)} ({data.gross_margin_sales.toFixed(1)}%)</span></div>
            </div>

            <div className="space-y-2">
              <DrillRow
                to="/treasury?tab=service_income&status=confirmed"
                label="Ingresos por Servicios"
                value={formatCurrency(data.service_income)}
                valueClass="text-emerald-700"
              />
              <DrillRow
                to="/double-entries?tab=liquidated&date_field=liquidated_at"
                label={`Utilidad Pasa Mano (${data.double_entry_count} operaciones)`}
                value={formatCurrency(data.double_entry_profit)}
                valueClass="text-emerald-700"
              />
              {data.transformation_count > 0 && (
                <DrillRow
                  to="/inventory/transformations?tab=confirmed"
                  label={`Ganancia/Perdida Transformaciones (${data.transformation_count})`}
                  value={formatCurrency(data.transformation_profit)}
                  valueClass={data.transformation_profit >= 0 ? "text-emerald-700" : "text-red-700"}
                />
              )}
              {data.waste_loss > 0 && (
                <DrillRow
                  to="/inventory/transformations?tab=confirmed"
                  label="Perdida por Merma"
                  value={`-${formatCurrency(data.waste_loss)}`}
                  valueClass="text-red-600"
                />
              )}
              {data.adjustment_net !== 0 && (
                <DrillRow
                  to="/inventory/adjustments?tab=confirmed&exclude_migration=true"
                  label="Ajustes de Inventario"
                  value={`${data.adjustment_net >= 0 ? "" : "-"}${formatCurrency(Math.abs(data.adjustment_net))}`}
                  valueClass={data.adjustment_net >= 0 ? "text-emerald-700" : "text-red-700"}
                />
              )}
              {data.oversell_cost_adjustment !== 0 && (
                <div className="flex justify-between text-sm">
                  <span className="text-muted-foreground">Ajuste Costo por Sobreventa y Reversiones</span>
                  <span className={data.oversell_cost_adjustment >= 0 ? "text-emerald-700" : "text-red-700"}>
                    {`${data.oversell_cost_adjustment >= 0 ? "" : "-"}${formatCurrency(Math.abs(data.oversell_cost_adjustment))}`}
                  </span>
                </div>
              )}
              {(data.asset_sale_gain ?? 0) !== 0 && (
                <div className="flex justify-between text-sm">
                  <span className="text-muted-foreground">Ganancia/Pérdida por Venta de Activos</span>
                  <span className={data.asset_sale_gain >= 0 ? "text-emerald-700" : "text-red-700"}>
                    {`${data.asset_sale_gain >= 0 ? "" : "-"}${formatCurrency(Math.abs(data.asset_sale_gain))}`}
                  </span>
                </div>
              )}
              {(data.internal_maquila_income ?? 0) !== 0 && (
                <div className="flex justify-between text-sm">
                  <span className="text-muted-foreground">+ Ingreso Maquila Intersede</span>
                  <span className="text-emerald-700">{formatCurrency(data.internal_maquila_income)}</span>
                </div>
              )}
              {(data.internal_maquila_expense ?? 0) !== 0 && (
                <div className="flex justify-between text-sm">
                  <span className="text-muted-foreground">- Gasto Maquila Intersede</span>
                  <span className="text-red-700">-{formatCurrency(data.internal_maquila_expense)}</span>
                </div>
              )}
              {data.tp_adjustment_gain > 0 && (
                <DrillRow
                  to="/treasury?tab=tp_adjustment&adjustment_class=gain&status=confirmed"
                  label="+ Ganancia Ajuste Terceros"
                  value={formatCurrency(data.tp_adjustment_gain)}
                  valueClass="text-emerald-700"
                />
              )}
              {data.tp_adjustment_loss > 0 && (
                <DrillRow
                  to="/treasury?tab=tp_adjustment&adjustment_class=loss&status=confirmed"
                  label="- Perdida Ajuste Terceros"
                  value={`-${formatCurrency(data.tp_adjustment_loss)}`}
                  valueClass="text-red-600"
                />
              )}
              <Separator />
              {/* GAP-1 QA: subtotal bruto SIN intereses — cada subtotal impreso
                  suma exactamente las filas visibles que lo preceden. */}
              <div className="flex justify-between font-medium"><span>Utilidad Bruta Total</span><span className={data.gross_profit_before_financial >= 0 ? "text-emerald-700" : "text-red-700"}>{formatCurrency(data.gross_profit_before_financial)}</span></div>
            </div>

            {/* Deducciones: comisiones (linea propia, D2) + una linea por rubro
                de gasto — sin desglose por fuente (causado o pagado da igual);
                el detalle por categoria vive en el Reporte de Gastos. */}
            <div className="space-y-2">
              <DrillRow
                to="/treasury?tab=commission_accrual&status=confirmed&commission_source=sale"
                label="Comisiones y Cargos (Ventas)"
                value={`-${formatCurrency(data.commissions_paid_sales)}`}
                valueClass="text-red-600"
              />
              <DrillRow
                to="/treasury?tab=commission_accrual&status=confirmed&commission_source=double_entry"
                label="Comisiones y Cargos (Pasa Mano)"
                value={`-${formatCurrency(data.commissions_paid_dp)}`}
                valueClass="text-red-600"
              />
              <DrillRow
                to={PNL_EXPENSE_DRILL_URLS.operativo}
                label="Gastos Operativos"
                value={`-${formatCurrency(data.expenses_operating)}`}
                valueClass="text-red-600"
              />
              {data.expenses_depreciation !== 0 && (
                <DrillRow
                  to={PNL_EXPENSE_DRILL_URLS.depreciacion}
                  label="Depreciación de Activos"
                  value={`-${formatCurrency(data.expenses_depreciation)}`}
                  valueClass="text-red-600"
                />
              )}
              <Separator />
              {/* UTILIDAD OPERACIONAL (D4) */}
              <div className="flex justify-between font-medium"><span>Utilidad Operacional</span><span className={data.operating_result >= 0 ? "text-emerald-700" : "text-red-700"}>{formatCurrency(data.operating_result)}</span></div>
            </div>

            {/* Ingresos Financieros (unica aparicion, GAP-1) + Gastos Financieros */}
            {((data.interest_income ?? 0) !== 0 || data.expenses_financial !== 0) && (
              <div className="space-y-2">
                {(data.interest_income ?? 0) !== 0 && (
                  <DrillRow
                    to="/treasury?tab=loan_interest_accrual&status=confirmed"
                    label="Ingresos Financieros (Intereses)"
                    value={formatCurrency(data.interest_income)}
                    valueClass="text-emerald-700"
                  />
                )}
                {data.expenses_financial !== 0 && (
                  <DrillRow
                    to={PNL_EXPENSE_DRILL_URLS.financiero}
                    label="Gastos Financieros"
                    value={`-${formatCurrency(data.expenses_financial)}`}
                    valueClass="text-red-600"
                  />
                )}
              </div>
            )}

            {/* UTILIDAD NETA (valor intacto) */}
            <div className="space-y-2">
              <Separator />
              <div className="flex justify-between text-lg font-bold"><span>Utilidad Neta</span><span className={data.net_profit >= 0 ? "text-emerald-700" : "text-red-700"}>{formatCurrency(data.net_profit)} ({data.net_margin.toFixed(1)}%)</span></div>
            </div>
          </CardContent>
        </Card>
      )}
    </>
  );
}
