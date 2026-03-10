import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ShieldCheck, AlertTriangle, RefreshCw } from "lucide-react";
import ReportsLayout from "./ReportsLayout";
import { useAuditBalances } from "@/hooks/useReports";
import { formatCurrency } from "@/utils/formatters";

const ACCOUNT_TYPE_LABELS: Record<string, string> = {
  cash: "Efectivo",
  bank: "Banco",
  digital: "Digital",
};

const ROLE_LABELS: Record<string, string> = {
  supplier: "Proveedor",
  customer: "Cliente",
  investor: "Inversionista",
  provision: "Provisión",
};

export default function AuditBalancesPage() {
  const [enabled, setEnabled] = useState(false);
  const { data, isLoading, refetch } = useAuditBalances(enabled);

  const handleRun = () => {
    if (enabled) {
      refetch();
    } else {
      setEnabled(true);
    }
  };

  const allOk = data && data.summary.accounts_mismatch === 0 && data.summary.third_parties_mismatch === 0;

  return (
    <ReportsLayout>
      <div className="space-y-4">
        <Card className="shadow-sm">
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="font-semibold text-lg">Auditoría de Saldos</h3>
                <p className="text-sm text-slate-500 mt-1">
                  Recalcula todos los saldos desde cero y compara con los valores almacenados. Detecta discrepancias por errores de sincronización.
                </p>
              </div>
              <Button onClick={handleRun} disabled={isLoading} className="bg-emerald-600 hover:bg-emerald-700">
                <RefreshCw className={`h-4 w-4 mr-2 ${isLoading ? "animate-spin" : ""}`} />
                {isLoading ? "Auditando..." : "Ejecutar Auditoría"}
              </Button>
            </div>
          </CardContent>
        </Card>

        {isLoading && <div className="text-center text-slate-500 py-8">Recalculando saldos...</div>}

        {data && (
          <>
            {/* Resumen */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <Card className={`shadow-sm ${allOk ? "border-emerald-200 bg-emerald-50" : "border-red-200 bg-red-50"}`}>
                <CardContent className="pt-6 flex items-center gap-3">
                  {allOk ? (
                    <ShieldCheck className="h-8 w-8 text-emerald-600" />
                  ) : (
                    <AlertTriangle className="h-8 w-8 text-red-600" />
                  )}
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">Estado General</p>
                    <p className={`text-xl font-bold ${allOk ? "text-emerald-700" : "text-red-700"}`}>
                      {allOk ? "Todo correcto" : "Discrepancias detectadas"}
                    </p>
                  </div>
                </CardContent>
              </Card>
              <Card className="shadow-sm">
                <CardContent className="pt-6">
                  <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">Cuentas de Dinero</p>
                  <p className="text-2xl font-bold">
                    <span className="text-emerald-700">{data.summary.accounts_ok}</span>
                    <span className="text-slate-400 text-lg"> / {data.summary.total_accounts}</span>
                  </p>
                  {data.summary.accounts_mismatch > 0 && (
                    <p className="text-xs text-red-600 mt-1">{data.summary.accounts_mismatch} con discrepancia</p>
                  )}
                </CardContent>
              </Card>
              <Card className="shadow-sm">
                <CardContent className="pt-6">
                  <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">Terceros</p>
                  <p className="text-2xl font-bold">
                    <span className="text-emerald-700">{data.summary.third_parties_ok}</span>
                    <span className="text-slate-400 text-lg"> / {data.summary.total_third_parties}</span>
                  </p>
                  {data.summary.third_parties_mismatch > 0 && (
                    <p className="text-xs text-red-600 mt-1">{data.summary.third_parties_mismatch} con discrepancia</p>
                  )}
                </CardContent>
              </Card>
            </div>

            {/* Detalle */}
            <Tabs defaultValue="accounts">
              <TabsList>
                <TabsTrigger value="accounts">
                  Cuentas ({data.accounts.length})
                  {data.summary.accounts_mismatch > 0 && (
                    <Badge variant="destructive" className="ml-2 text-[10px] py-0">{data.summary.accounts_mismatch}</Badge>
                  )}
                </TabsTrigger>
                <TabsTrigger value="third-parties">
                  Terceros ({data.third_parties.length})
                  {data.summary.third_parties_mismatch > 0 && (
                    <Badge variant="destructive" className="ml-2 text-[10px] py-0">{data.summary.third_parties_mismatch}</Badge>
                  )}
                </TabsTrigger>
              </TabsList>

              <TabsContent value="accounts">
                <Card className="shadow-sm">
                  <CardHeader>
                    <CardTitle className="text-sm font-semibold uppercase tracking-wider text-slate-500">
                      Auditoría de Cuentas de Dinero
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    {data.accounts.length === 0 ? (
                      <p className="text-sm text-slate-500">Sin cuentas registradas</p>
                    ) : (
                      <div className="rounded-lg border border-slate-200/80 overflow-hidden">
                        <Table>
                          <TableHeader>
                            <TableRow className="bg-slate-50/80 border-b border-slate-200/80">
                              <TableHead className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 h-10">Cuenta</TableHead>
                              <TableHead className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 h-10">Tipo</TableHead>
                              <TableHead className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 h-10 text-right">Saldo Almacenado</TableHead>
                              <TableHead className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 h-10 text-right">Saldo Calculado</TableHead>
                              <TableHead className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 h-10 text-right">Diferencia</TableHead>
                              <TableHead className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 h-10 text-center">Estado</TableHead>
                            </TableRow>
                          </TableHeader>
                          <TableBody>
                            {data.accounts.map((a) => (
                              <TableRow key={a.id} className={a.status === "mismatch" ? "bg-red-50" : ""}>
                                <TableCell className="font-medium">{a.name}</TableCell>
                                <TableCell>{ACCOUNT_TYPE_LABELS[a.account_type] || a.account_type}</TableCell>
                                <TableCell className="text-right">{formatCurrency(a.stored_balance)}</TableCell>
                                <TableCell className="text-right">{formatCurrency(a.calculated_balance)}</TableCell>
                                <TableCell className={`text-right font-medium ${a.difference !== 0 ? "text-red-700" : ""}`}>
                                  {formatCurrency(a.difference)}
                                </TableCell>
                                <TableCell className="text-center">
                                  {a.status === "ok" ? (
                                    <Badge variant="outline" className="bg-emerald-50 text-emerald-700 text-[10px] py-0">OK</Badge>
                                  ) : (
                                    <Badge variant="destructive" className="text-[10px] py-0">Error</Badge>
                                  )}
                                </TableCell>
                              </TableRow>
                            ))}
                          </TableBody>
                        </Table>
                      </div>
                    )}
                  </CardContent>
                </Card>
              </TabsContent>

              <TabsContent value="third-parties">
                <Card className="shadow-sm">
                  <CardHeader>
                    <CardTitle className="text-sm font-semibold uppercase tracking-wider text-slate-500">
                      Auditoría de Saldos de Terceros
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    {data.third_parties.length === 0 ? (
                      <p className="text-sm text-slate-500">Sin terceros registrados</p>
                    ) : (
                      <div className="rounded-lg border border-slate-200/80 overflow-hidden">
                        <Table>
                          <TableHeader>
                            <TableRow className="bg-slate-50/80 border-b border-slate-200/80">
                              <TableHead className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 h-10">Tercero</TableHead>
                              <TableHead className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 h-10">Roles</TableHead>
                              <TableHead className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 h-10 text-right">Saldo Almacenado</TableHead>
                              <TableHead className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 h-10 text-right">Saldo Calculado</TableHead>
                              <TableHead className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 h-10 text-right">Diferencia</TableHead>
                              <TableHead className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 h-10 text-center">Estado</TableHead>
                            </TableRow>
                          </TableHeader>
                          <TableBody>
                            {data.third_parties.map((tp) => (
                              <TableRow key={tp.id} className={tp.status === "mismatch" ? "bg-red-50" : ""}>
                                <TableCell className="font-medium">{tp.name}</TableCell>
                                <TableCell>
                                  <div className="flex gap-1 flex-wrap">
                                    {tp.roles.map((r) => (
                                      <Badge key={r} variant="outline" className="text-[10px] py-0">
                                        {ROLE_LABELS[r] || r}
                                      </Badge>
                                    ))}
                                  </div>
                                </TableCell>
                                <TableCell className="text-right">{formatCurrency(tp.stored_balance)}</TableCell>
                                <TableCell className="text-right">{formatCurrency(tp.calculated_balance)}</TableCell>
                                <TableCell className={`text-right font-medium ${tp.difference !== 0 ? "text-red-700" : ""}`}>
                                  {formatCurrency(tp.difference)}
                                </TableCell>
                                <TableCell className="text-center">
                                  {tp.status === "ok" ? (
                                    <Badge variant="outline" className="bg-emerald-50 text-emerald-700 text-[10px] py-0">OK</Badge>
                                  ) : (
                                    <Badge variant="destructive" className="text-[10px] py-0">Error</Badge>
                                  )}
                                </TableCell>
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
          </>
        )}
      </div>
    </ReportsLayout>
  );
}
