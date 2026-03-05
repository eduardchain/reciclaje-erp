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
      {isLoading && <div className="text-center text-gray-500 py-8">Cargando...</div>}

      {data && (
        <div className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <Card>
              <CardContent className="pt-6">
                <p className="text-sm text-gray-500">Cuentas por Pagar</p>
                <p className="text-2xl font-bold text-red-700">{formatCurrency(data.total_payable)}</p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <p className="text-sm text-gray-500">Cuentas por Cobrar</p>
                <p className="text-2xl font-bold text-green-700">{formatCurrency(data.total_receivable)}</p>
              </CardContent>
            </Card>
            <Card className="border-2 border-blue-200 bg-blue-50">
              <CardContent className="pt-6">
                <p className="text-sm text-gray-500">Posicion Neta</p>
                <p className={`text-2xl font-bold ${data.net_position >= 0 ? "text-green-700" : "text-red-700"}`}>{formatCurrency(data.net_position)}</p>
              </CardContent>
            </Card>
          </div>

          <Tabs defaultValue="suppliers">
            <TabsList>
              <TabsTrigger value="suppliers">Proveedores ({data.suppliers.length})</TabsTrigger>
              <TabsTrigger value="customers">Clientes ({data.customers.length})</TabsTrigger>
            </TabsList>

            <TabsContent value="suppliers">
              <Card>
                <CardHeader><CardTitle className="text-base">Saldos con Proveedores</CardTitle></CardHeader>
                <CardContent>
                  {data.suppliers.length === 0 ? (
                    <p className="text-sm text-gray-500">Sin saldos pendientes</p>
                  ) : (
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Proveedor</TableHead>
                          <TableHead className="text-right">Saldo</TableHead>
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
                  )}
                </CardContent>
              </Card>
            </TabsContent>

            <TabsContent value="customers">
              <Card>
                <CardHeader><CardTitle className="text-base">Saldos con Clientes</CardTitle></CardHeader>
                <CardContent>
                  {data.customers.length === 0 ? (
                    <p className="text-sm text-gray-500">Sin saldos pendientes</p>
                  ) : (
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Cliente</TableHead>
                          <TableHead className="text-right">Saldo</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {data.customers.map((c) => (
                          <TableRow key={c.id}>
                            <TableCell>{c.name}</TableCell>
                            <TableCell className="text-right font-medium text-green-700">{formatCurrency(c.balance)}</TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
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
