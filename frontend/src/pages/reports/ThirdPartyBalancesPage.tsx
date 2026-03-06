import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import ReportsLayout from "./ReportsLayout";
import { useThirdPartyBalances } from "@/hooks/useReports";
import { formatCurrency } from "@/utils/formatters";

export default function ThirdPartyBalancesPage() {
  const { data, isLoading } = useThirdPartyBalances();

  return (
    <ReportsLayout>
      {isLoading && <div className="text-center text-slate-500 py-8">Cargando...</div>}

      {data && (
        <div className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <Card className="shadow-sm">
              <CardContent className="pt-6">
                <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">Cuentas por Pagar</p>
                <p className="text-2xl font-bold text-red-700">{formatCurrency(data.total_payable)}</p>
              </CardContent>
            </Card>
            <Card className="shadow-sm">
              <CardContent className="pt-6">
                <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">Cuentas por Cobrar</p>
                <p className="text-2xl font-bold text-emerald-700">{formatCurrency(data.total_receivable)}</p>
              </CardContent>
            </Card>
            <Card className="border-2 border-blue-200 bg-blue-50 shadow-sm">
              <CardContent className="pt-6">
                <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">Posicion Neta</p>
                <p className={`text-2xl font-bold ${data.net_position >= 0 ? "text-emerald-700" : "text-red-700"}`}>{formatCurrency(data.net_position)}</p>
              </CardContent>
            </Card>
          </div>

          <Tabs defaultValue="suppliers">
            <TabsList>
              <TabsTrigger value="suppliers">Proveedores ({data.suppliers.length})</TabsTrigger>
              <TabsTrigger value="customers">Clientes ({data.customers.length})</TabsTrigger>
            </TabsList>

            <TabsContent value="suppliers">
              <Card className="shadow-sm">
                <CardHeader><CardTitle className="text-sm font-semibold uppercase tracking-wider text-slate-500">Saldos con Proveedores</CardTitle></CardHeader>
                <CardContent>
                  {data.suppliers.length === 0 ? (
                    <p className="text-sm text-slate-500">Sin saldos pendientes</p>
                  ) : (
                    <div className="rounded-lg border border-slate-200/80 overflow-hidden">
                    <Table>
                      <TableHeader>
                        <TableRow className="bg-slate-50/80 border-b border-slate-200/80">
                          <TableHead className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 h-10">Proveedor</TableHead>
                          <TableHead className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 h-10 text-right">Saldo</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {data.suppliers.map((s) => (
                          <TableRow key={s.id}>
                            <TableCell>{s.name}</TableCell>
                            <TableCell className="text-right font-medium text-red-700">{formatCurrency(s.balance)}</TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                    </div>
                  )}
                </CardContent>
              </Card>
            </TabsContent>

            <TabsContent value="customers">
              <Card className="shadow-sm">
                <CardHeader><CardTitle className="text-sm font-semibold uppercase tracking-wider text-slate-500">Saldos con Clientes</CardTitle></CardHeader>
                <CardContent>
                  {data.customers.length === 0 ? (
                    <p className="text-sm text-slate-500">Sin saldos pendientes</p>
                  ) : (
                    <div className="rounded-lg border border-slate-200/80 overflow-hidden">
                    <Table>
                      <TableHeader>
                        <TableRow className="bg-slate-50/80 border-b border-slate-200/80">
                          <TableHead className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 h-10">Cliente</TableHead>
                          <TableHead className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 h-10 text-right">Saldo</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {data.customers.map((c) => (
                          <TableRow key={c.id}>
                            <TableCell>{c.name}</TableCell>
                            <TableCell className="text-right font-medium text-emerald-700">{formatCurrency(c.balance)}</TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                    </div>
                  )}
                </CardContent>
              </Card>
            </TabsContent>
          </Tabs>
        </div>
      )}
    </ReportsLayout>
  );
}
