import {
  ShoppingCart,
  DollarSign,
  TrendingUp,
  Wallet,
  AlertTriangle,
  CreditCard,
  Receipt,
  Info,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { PageHeader } from "@/components/shared/PageHeader";
import { DateRangePicker } from "@/components/shared/DateRangePicker";
import { KpiCard } from "@/components/shared/KpiCard";
import { useDashboard } from "@/hooks/useReports";
import { useDateFilter } from "@/stores/dateFilterStore";
import { formatCurrency, formatWeight, formatPercentage } from "@/utils/formatters";
import { ROUTES } from "@/utils/constants";

export default function Dashboard() {
  const { dateFrom, dateTo, setDateFrom, setDateTo } = useDateFilter();
  const { data, isLoading } = useDashboard({ date_from: dateFrom, date_to: dateTo });

  return (
    <div className="space-y-6">
      <PageHeader title="Dashboard" description="Resumen del periodo seleccionado">
        <DateRangePicker
          dateFrom={dateFrom}
          dateTo={dateTo}
          onDateFromChange={setDateFrom}
          onDateToChange={setDateTo}
        />
      </PageHeader>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {isLoading ? (
          Array.from({ length: 6 }).map((_, i) => (
            <Card key={i} className="border-t-[3px] border-t-slate-200">
              <CardContent className="p-5">
                <Skeleton className="h-3 w-20 mb-4" />
                <Skeleton className="h-8 w-32 mb-2" />
                <Skeleton className="h-3 w-24" />
              </CardContent>
            </Card>
          ))
        ) : data?.metrics ? (
          <>
            <KpiCard
              label="Total Ventas"
              metric={data.metrics.total_sales}
              icon={<DollarSign className="h-4 w-4" />}
              accentColor="emerald"
              href={ROUTES.SALES}
            />
            <KpiCard
              label="Total Compras"
              metric={data.metrics.total_purchases}
              icon={<ShoppingCart className="h-4 w-4" />}
              accentColor="sky"
              href={ROUTES.PURCHASES}
            />
            <KpiCard
              label="Utilidad Bruta"
              metric={data.metrics.gross_profit}
              icon={<TrendingUp className="h-4 w-4" />}
              accentColor="violet"
            />
            <KpiCard
              label="Saldo en Caja"
              metric={data.metrics.cash_balance}
              icon={<Wallet className="h-4 w-4" />}
              accentColor="amber"
              href={ROUTES.TREASURY}
            />
            <KpiCard
              label="Cuentas por Cobrar"
              metric={data.metrics.pending_receivables}
              icon={<Receipt className="h-4 w-4" />}
              accentColor="teal"
            />
            <KpiCard
              label="Cuentas por Pagar"
              metric={data.metrics.pending_payables}
              icon={<CreditCard className="h-4 w-4" />}
              accentColor="rose"
            />
          </>
        ) : null}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        {/* Top Materiales por Utilidad */}
        <Card className="shadow-sm">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-semibold text-slate-500 uppercase tracking-wider">
              Top Materiales por Utilidad
            </CardTitle>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <LoadingRows />
            ) : data?.top_materials_by_profit?.length ? (
              <div className="space-y-2.5">
                {data.top_materials_by_profit.map((m, i) => (
                  <div
                    key={m.material_id}
                    className="flex items-center justify-between py-2 px-3 rounded-lg hover:bg-slate-50 transition-colors"
                  >
                    <div className="flex items-center gap-3">
                      <span className="text-xs font-bold text-slate-300 w-5 tabular-nums">{i + 1}</span>
                      <span className="text-sm font-medium text-slate-700">{m.material_name}</span>
                    </div>
                    <div className="flex items-center gap-4">
                      <span className="text-xs text-slate-400 tabular-nums">{formatPercentage(m.margin_percentage)}</span>
                      <span className="text-sm font-semibold text-emerald-700 tabular-nums">
                        {formatCurrency(m.total_profit)}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <EmptyMessage />
            )}
          </CardContent>
        </Card>

        {/* Top Proveedores por Volumen */}
        <Card className="shadow-sm">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-semibold text-slate-500 uppercase tracking-wider">
              Top Proveedores por Volumen
            </CardTitle>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <LoadingRows />
            ) : data?.top_suppliers_by_volume?.length ? (
              <div className="space-y-2.5">
                {data.top_suppliers_by_volume.map((s, i) => (
                  <div
                    key={s.supplier_id}
                    className="flex items-center justify-between py-2 px-3 rounded-lg hover:bg-slate-50 transition-colors"
                  >
                    <div className="flex items-center gap-3">
                      <span className="text-xs font-bold text-slate-300 w-5 tabular-nums">{i + 1}</span>
                      <span className="text-sm font-medium text-slate-700">{s.supplier_name}</span>
                    </div>
                    <div className="flex items-center gap-4">
                      <span className="text-xs text-slate-400 tabular-nums">{formatWeight(s.total_quantity)}</span>
                      <span className="text-sm font-semibold text-slate-700 tabular-nums">
                        {formatCurrency(s.total_amount)}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <EmptyMessage />
            )}
          </CardContent>
        </Card>

        {/* Top Clientes por Ingreso */}
        <Card className="shadow-sm">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-semibold text-slate-500 uppercase tracking-wider">
              Top Clientes por Ingreso
            </CardTitle>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <LoadingRows />
            ) : data?.top_customers_by_revenue?.length ? (
              <div className="space-y-2.5">
                {data.top_customers_by_revenue.map((c, i) => (
                  <div
                    key={c.customer_id}
                    className="flex items-center justify-between py-2 px-3 rounded-lg hover:bg-slate-50 transition-colors"
                  >
                    <div className="flex items-center gap-3">
                      <span className="text-xs font-bold text-slate-300 w-5 tabular-nums">{i + 1}</span>
                      <span className="text-sm font-medium text-slate-700">{c.customer_name}</span>
                    </div>
                    <div className="flex items-center gap-4">
                      <span className="text-sm font-semibold text-slate-700 tabular-nums">{formatCurrency(c.total_amount)}</span>
                      <span className="text-xs font-medium text-emerald-600 tabular-nums">
                        {formatCurrency(c.total_profit)}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <EmptyMessage />
            )}
          </CardContent>
        </Card>

        {/* Alertas */}
        <Card className="shadow-sm">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-semibold text-slate-500 uppercase tracking-wider">
              Alertas
            </CardTitle>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <LoadingRows count={3} />
            ) : data?.alerts?.length ? (
              <div className="space-y-2">
                {data.alerts.map((alert, i) => (
                  <div
                    key={i}
                    className={`flex items-start gap-3 p-3 rounded-lg text-sm ${
                      alert.severity === "warning"
                        ? "bg-amber-50 border border-amber-200/60"
                        : "bg-sky-50 border border-sky-200/60"
                    }`}
                  >
                    {alert.severity === "warning" ? (
                      <AlertTriangle className="h-4 w-4 mt-0.5 shrink-0 text-amber-500" />
                    ) : (
                      <Info className="h-4 w-4 mt-0.5 shrink-0 text-sky-500" />
                    )}
                    <div>
                      <p className={`font-semibold ${
                        alert.severity === "warning" ? "text-amber-800" : "text-sky-800"
                      }`}>
                        {alert.alert_type}
                        {alert.count != null && ` (${alert.count})`}
                      </p>
                      <p className={`mt-0.5 ${
                        alert.severity === "warning" ? "text-amber-700" : "text-sky-700"
                      }`}>
                        {alert.message}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-center py-6">
                <p className="text-sm text-slate-400">Sin alertas activas</p>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function LoadingRows({ count = 5 }: { count?: number }) {
  return (
    <div className="space-y-3">
      {Array.from({ length: count }).map((_, i) => (
        <Skeleton key={i} className="h-6 w-full" />
      ))}
    </div>
  );
}

function EmptyMessage() {
  return (
    <div className="text-center py-6">
      <p className="text-sm text-slate-400">Sin datos para el periodo</p>
    </div>
  );
}
