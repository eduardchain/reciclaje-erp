import { useState } from "react";
import { Link } from "react-router-dom";
import {
  ShoppingCart,
  DollarSign,
  TrendingUp,
  TrendingDown,
  Wallet,
  AlertTriangle,
  CreditCard,
  Receipt,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { PageHeader } from "@/components/shared/PageHeader";
import { DateRangePicker } from "@/components/shared/DateRangePicker";
import { useDashboard } from "@/hooks/useReports";
import { formatCurrency, formatWeight, formatPercentage, toISODate } from "@/utils/formatters";
import { ROUTES } from "@/utils/constants";
import type { MetricCard } from "@/types/reports";

function getDefaultDates() {
  const now = new Date();
  const firstDay = new Date(now.getFullYear(), now.getMonth(), 1);
  return {
    date_from: toISODate(firstDay),
    date_to: toISODate(now),
  };
}

export default function Dashboard() {
  const [dates, setDates] = useState(getDefaultDates);
  const { data, isLoading } = useDashboard(dates);

  return (
    <div className="space-y-6">
      <PageHeader title="Dashboard" description="Resumen del periodo seleccionado">
        <DateRangePicker
          dateFrom={dates.date_from}
          dateTo={dates.date_to}
          onDateFromChange={(d) => setDates((prev) => ({ ...prev, date_from: d }))}
          onDateToChange={(d) => setDates((prev) => ({ ...prev, date_to: d }))}
        />
      </PageHeader>

      {/* Metric Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {isLoading ? (
          Array.from({ length: 6 }).map((_, i) => (
            <Card key={i}>
              <CardContent className="p-6">
                <Skeleton className="h-4 w-24 mb-2" />
                <Skeleton className="h-8 w-32" />
              </CardContent>
            </Card>
          ))
        ) : data?.metrics ? (
          <>
            <MetricCardDisplay
              label="Total Ventas"
              metric={data.metrics.total_sales}
              icon={<DollarSign className="h-5 w-5 text-green-600" />}
              bgColor="bg-green-100"
              href={ROUTES.SALES}
            />
            <MetricCardDisplay
              label="Total Compras"
              metric={data.metrics.total_purchases}
              icon={<ShoppingCart className="h-5 w-5 text-blue-600" />}
              bgColor="bg-blue-100"
              href={ROUTES.PURCHASES}
            />
            <MetricCardDisplay
              label="Utilidad Bruta"
              metric={data.metrics.gross_profit}
              icon={<TrendingUp className="h-5 w-5 text-purple-600" />}
              bgColor="bg-purple-100"
            />
            <MetricCardDisplay
              label="Saldo en Caja"
              metric={data.metrics.cash_balance}
              icon={<Wallet className="h-5 w-5 text-yellow-600" />}
              bgColor="bg-yellow-100"
              href={ROUTES.TREASURY}
            />
            <MetricCardDisplay
              label="Cuentas por Cobrar"
              metric={data.metrics.pending_receivables}
              icon={<Receipt className="h-5 w-5 text-teal-600" />}
              bgColor="bg-teal-100"
            />
            <MetricCardDisplay
              label="Cuentas por Pagar"
              metric={data.metrics.pending_payables}
              icon={<CreditCard className="h-5 w-5 text-red-600" />}
              bgColor="bg-red-100"
            />
          </>
        ) : null}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Top Materiales por Utilidad */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Top Materiales por Utilidad</CardTitle>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <LoadingRows />
            ) : data?.top_materials_by_profit?.length ? (
              <div className="space-y-3">
                {data.top_materials_by_profit.map((m) => (
                  <div key={m.material_id} className="flex items-center justify-between text-sm">
                    <span className="text-gray-700">{m.material_name}</span>
                    <div className="flex items-center gap-4">
                      <span className="text-gray-500">{formatPercentage(m.margin_percentage)}</span>
                      <span className="font-medium text-green-700">{formatCurrency(m.total_profit)}</span>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-gray-500">Sin datos para el periodo</p>
            )}
          </CardContent>
        </Card>

        {/* Top Proveedores por Volumen */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Top Proveedores por Volumen</CardTitle>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <LoadingRows />
            ) : data?.top_suppliers_by_volume?.length ? (
              <div className="space-y-3">
                {data.top_suppliers_by_volume.map((s) => (
                  <div key={s.supplier_id} className="flex items-center justify-between text-sm">
                    <span className="text-gray-700">{s.supplier_name}</span>
                    <div className="flex items-center gap-4">
                      <span className="text-gray-500">{formatWeight(s.total_quantity)}</span>
                      <span className="font-medium">{formatCurrency(s.total_amount)}</span>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-gray-500">Sin datos para el periodo</p>
            )}
          </CardContent>
        </Card>

        {/* Top Clientes por Ingreso */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Top Clientes por Ingreso</CardTitle>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <LoadingRows />
            ) : data?.top_customers_by_revenue?.length ? (
              <div className="space-y-3">
                {data.top_customers_by_revenue.map((c) => (
                  <div key={c.customer_id} className="flex items-center justify-between text-sm">
                    <span className="text-gray-700">{c.customer_name}</span>
                    <div className="flex items-center gap-4">
                      <span className="font-medium">{formatCurrency(c.total_amount)}</span>
                      <span className="text-green-700 text-xs">{formatCurrency(c.total_profit)} util.</span>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-gray-500">Sin datos para el periodo</p>
            )}
          </CardContent>
        </Card>

        {/* Alertas */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Alertas</CardTitle>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <LoadingRows count={3} />
            ) : data?.alerts?.length ? (
              <div className="space-y-2">
                {data.alerts.map((alert, i) => (
                  <div
                    key={i}
                    className={`flex items-start gap-2 p-2 rounded text-sm ${
                      alert.severity === "warning" ? "bg-yellow-50" : "bg-blue-50"
                    }`}
                  >
                    <AlertTriangle
                      className={`h-4 w-4 mt-0.5 shrink-0 ${
                        alert.severity === "warning" ? "text-yellow-600" : "text-blue-600"
                      }`}
                    />
                    <div>
                      <p className={`font-medium ${
                        alert.severity === "warning" ? "text-yellow-800" : "text-blue-800"
                      }`}>
                        {alert.alert_type}
                        {alert.count != null && ` (${alert.count})`}
                      </p>
                      <p className={alert.severity === "warning" ? "text-yellow-700" : "text-blue-700"}>
                        {alert.message}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-gray-500">Sin alertas</p>
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

function MetricCardDisplay({
  label,
  metric,
  icon,
  bgColor,
  href,
}: {
  label: string;
  metric: MetricCard;
  icon: React.ReactNode;
  bgColor: string;
  href?: string;
}) {
  const content = (
    <Card className={href ? "hover:shadow-md transition-shadow" : undefined}>
      <CardContent className="p-6">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm text-gray-600">{label}</p>
            <p className="text-2xl font-bold text-gray-900 mt-1">
              {formatCurrency(metric.current_value)}
            </p>
            {metric.change_percentage != null && (
              <div className="flex items-center gap-1 mt-1">
                {metric.change_percentage >= 0 ? (
                  <TrendingUp className="h-3 w-3 text-green-600" />
                ) : (
                  <TrendingDown className="h-3 w-3 text-red-600" />
                )}
                <span
                  className={`text-xs font-medium ${
                    metric.change_percentage >= 0 ? "text-green-600" : "text-red-600"
                  }`}
                >
                  {formatPercentage(Math.abs(metric.change_percentage))} vs anterior
                </span>
              </div>
            )}
          </div>
          <div className={`w-12 h-12 ${bgColor} rounded-lg flex items-center justify-center`}>
            {icon}
          </div>
        </div>
      </CardContent>
    </Card>
  );

  if (href) {
    return <Link to={href}>{content}</Link>;
  }
  return content;
}
