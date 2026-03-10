import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { PiggyBank, Plus, Receipt, FileText } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { PageHeader } from "@/components/shared/PageHeader";
import { MoneyDisplay } from "@/components/shared/MoneyDisplay";
import { EmptyState } from "@/components/shared/EmptyState";
import { useProvisions } from "@/hooks/useMasterData";
import { formatCurrency } from "@/utils/formatters";
import { ROUTES } from "@/utils/constants";

export default function ProvisionsPage() {
  const navigate = useNavigate();
  const { data, isLoading } = useProvisions();
  const provisions = data?.items ?? [];

  const totalAvailable = provisions.reduce((sum, p) => {
    return sum + (p.current_balance < 0 ? Math.abs(p.current_balance) : 0);
  }, 0);

  return (
    <div className="space-y-6">
      <PageHeader title="Provisiones" description="Gestion de fondos provisionados">
        <Button variant="outline" onClick={() => navigate(ROUTES.TREASURY)}>
          Volver a Tesoreria
        </Button>
      </PageHeader>

      <Card className="border-t-[3px] border-t-violet-500 shadow-sm">
        <CardContent className="p-5">
          <div className="flex items-center gap-2 mb-1">
            <PiggyBank className="h-5 w-5 text-violet-600" />
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">Total Fondos Disponibles</span>
          </div>
          <p className="text-2xl font-bold text-slate-900 tabular-nums">{formatCurrency(totalAvailable)}</p>
          <p className="text-xs text-slate-400 mt-1">{provisions.length} provision(es) registrada(s)</p>
        </CardContent>
      </Card>

      <Card className="shadow-sm">
        <CardHeader>
          <CardTitle className="text-sm font-semibold uppercase tracking-wider text-slate-500">Provisiones</CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <p className="text-sm text-slate-400 py-8 text-center">Cargando...</p>
          ) : provisions.length === 0 ? (
            <EmptyState
              title="Sin provisiones"
              description="No hay terceros con rol de provision. Crea uno desde Terceros."
            />
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Nombre</TableHead>
                  <TableHead className="text-right">Fondos Disponibles</TableHead>
                  <TableHead className="text-right">Saldo Contable</TableHead>
                  <TableHead className="text-right">Acciones</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {provisions.map((p) => {
                  const funds = p.current_balance < 0 ? Math.abs(p.current_balance) : 0;
                  return (
                    <TableRow key={p.id}>
                      <TableCell className="font-medium">{p.name}</TableCell>
                      <TableCell className="text-right">
                        <MoneyDisplay amount={funds} />
                      </TableCell>
                      <TableCell className="text-right">
                        <MoneyDisplay amount={p.current_balance} />
                      </TableCell>
                      <TableCell className="text-right">
                        <div className="flex justify-end gap-1">
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => navigate(`${ROUTES.TREASURY_NEW}?type=provision_deposit&provision_id=${p.id}`)}
                          >
                            <Plus className="h-3 w-3 mr-1" />Depositar
                          </Button>
                          <Button
                            size="sm"
                            variant="outline"
                            disabled={p.current_balance >= 0}
                            onClick={() => {
                              if (p.current_balance >= 0) {
                                toast.error(`La provision "${p.name}" esta en sobregiro. Deposite fondos antes de registrar un gasto.`);
                                return;
                              }
                              navigate(`${ROUTES.TREASURY_NEW}?type=provision_expense&provision_id=${p.id}`);
                            }}
                          >
                            <Receipt className="h-3 w-3 mr-1" />Gasto
                          </Button>
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => navigate(`${ROUTES.TREASURY_ACCOUNT_STATEMENT}?third_party_id=${p.id}`)}
                          >
                            <FileText className="h-3 w-3 mr-1" />Estado Cuenta
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
