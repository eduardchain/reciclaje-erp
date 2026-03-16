import { useState, useMemo } from "react";
import { TrendingUp, TrendingDown, DollarSign } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Skeleton } from "@/components/ui/skeleton";
import { PageHeader } from "@/components/shared/PageHeader";
import { MoneyInput } from "@/components/shared/MoneyInput";
import { MoneyDisplay } from "@/components/shared/MoneyDisplay";
import { ConfirmDialog } from "@/components/shared/ConfirmDialog";
import {
  useAvailableProfit,
  usePartners,
  useCreateDistribution,
  useProfitDistributions,
} from "@/hooks/useProfitDistributions";
import { formatCurrency, formatDate, toLocalDatetimeInput } from "@/utils/formatters";

export default function ProfitDistributionPage() {
  const { data: available, isLoading: loadingAvailable } = useAvailableProfit();
  const { data: partners, isLoading: loadingPartners } = usePartners();
  const { data: history, isLoading: loadingHistory } = useProfitDistributions({ limit: 50 });
  const createMutation = useCreateDistribution();

  const [date, setDate] = useState(toLocalDatetimeInput().slice(0, 10));
  const [notes, setNotes] = useState("");
  const [amounts, setAmounts] = useState<Record<string, number>>({});
  const [confirmOpen, setConfirmOpen] = useState(false);

  const totalToDistribute = useMemo(
    () => Object.values(amounts).reduce((sum, v) => sum + (v || 0), 0),
    [amounts]
  );

  const handleAmountChange = (partnerId: string, value: number) => {
    setAmounts((prev) => ({ ...prev, [partnerId]: value }));
  };

  const handleSubmit = () => {
    if (totalToDistribute <= 0) return;
    setConfirmOpen(true);
  };

  const handleConfirm = () => {
    const lines = Object.entries(amounts)
      .filter(([, amount]) => amount > 0)
      .map(([third_party_id, amount]) => ({ third_party_id, amount }));

    createMutation.mutate(
      { date, lines, notes: notes || undefined },
      {
        onSuccess: () => {
          setAmounts({});
          setNotes("");
          setConfirmOpen(false);
        },
      }
    );
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Repartición de Utilidades"
        description="Distribuir utilidades acumuladas entre los socios"
      />

      {/* KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card className="shadow-sm">
          <CardContent className="pt-6">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-emerald-100">
                <TrendingUp className="h-5 w-5 text-emerald-600" />
              </div>
              <div>
                <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                  Utilidad Acumulada
                </p>
                {loadingAvailable ? (
                  <Skeleton className="h-7 w-32 mt-1" />
                ) : (
                  <p className="text-xl font-bold text-emerald-700">
                    {formatCurrency(available?.accumulated_profit ?? 0)}
                  </p>
                )}
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="shadow-sm">
          <CardContent className="pt-6">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-red-100">
                <TrendingDown className="h-5 w-5 text-red-600" />
              </div>
              <div>
                <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                  Ya Distribuida
                </p>
                {loadingAvailable ? (
                  <Skeleton className="h-7 w-32 mt-1" />
                ) : (
                  <p className="text-xl font-bold text-red-700">
                    {formatCurrency(available?.distributed_profit ?? 0)}
                  </p>
                )}
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="shadow-sm border-2 border-blue-200 bg-blue-50">
          <CardContent className="pt-6">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-blue-100">
                <DollarSign className="h-5 w-5 text-blue-600" />
              </div>
              <div>
                <p className="text-xs font-semibold uppercase tracking-wider text-blue-600">
                  Disponible
                </p>
                {loadingAvailable ? (
                  <Skeleton className="h-7 w-32 mt-1" />
                ) : (
                  <p className="text-xl font-bold text-blue-700">
                    {formatCurrency(available?.available_profit ?? 0)}
                  </p>
                )}
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Formulario de distribución */}
      <Card className="shadow-sm">
        <CardHeader>
          <CardTitle className="text-sm font-semibold uppercase tracking-wider text-slate-700">
            Nueva Repartición
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <Label>Fecha</Label>
              <Input
                type="date"
                value={date}
                onChange={(e) => setDate(e.target.value)}
              />
            </div>
            <div>
              <Label>Notas (opcional)</Label>
              <Input
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                placeholder="Ej: Repartición primer trimestre 2026"
              />
            </div>
          </div>

          <Separator />

          {loadingPartners ? (
            <div className="space-y-2">
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-full" />
            </div>
          ) : partners && partners.length > 0 ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Socio</TableHead>
                  <TableHead className="text-right">Saldo Actual</TableHead>
                  <TableHead className="w-64">Monto a Asignar</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {partners.map((partner) => (
                  <TableRow key={partner.id}>
                    <TableCell className="font-medium">{partner.name}</TableCell>
                    <TableCell className="text-right">
                      <MoneyDisplay amount={partner.current_balance} />
                    </TableCell>
                    <TableCell>
                      <MoneyInput
                        value={amounts[partner.id] || 0}
                        onChange={(v) => handleAmountChange(partner.id, v)}
                        placeholder="0"
                      />
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : (
            <p className="text-sm text-slate-500 text-center py-4">
              No hay socios registrados (terceros con tipo inversor = socio)
            </p>
          )}

          <Separator />

          <div className="flex items-center justify-between">
            <div>
              <span className="text-sm text-slate-500">Total a Repartir:</span>
              <span className="ml-2 text-lg font-bold text-slate-900">
                {formatCurrency(totalToDistribute)}
              </span>
            </div>
            <Button
              onClick={handleSubmit}
              disabled={totalToDistribute <= 0 || createMutation.isPending}
              className="bg-emerald-600 hover:bg-emerald-700"
            >
              {createMutation.isPending ? "Registrando..." : "Registrar Repartición"}
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Historial */}
      <Card className="shadow-sm">
        <CardHeader>
          <CardTitle className="text-sm font-semibold uppercase tracking-wider text-slate-700">
            Historial de Reparticiones
          </CardTitle>
        </CardHeader>
        <CardContent>
          {loadingHistory ? (
            <div className="space-y-2">
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-full" />
            </div>
          ) : history && history.items.length > 0 ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Fecha</TableHead>
                  <TableHead className="text-right">Monto Total</TableHead>
                  <TableHead className="text-center"># Socios</TableHead>
                  <TableHead>Detalle</TableHead>
                  <TableHead>Notas</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {history.items.map((dist) => (
                  <TableRow key={dist.id}>
                    <TableCell>{formatDate(dist.date)}</TableCell>
                    <TableCell className="text-right font-medium">
                      {formatCurrency(dist.total_amount)}
                    </TableCell>
                    <TableCell className="text-center">{dist.lines.length}</TableCell>
                    <TableCell>
                      <div className="text-xs text-slate-500 space-y-0.5">
                        {dist.lines.map((line) => (
                          <div key={line.id}>
                            {line.third_party_name}: {formatCurrency(line.amount)}
                          </div>
                        ))}
                      </div>
                    </TableCell>
                    <TableCell className="text-sm text-slate-500">
                      {dist.notes || "—"}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : (
            <p className="text-sm text-slate-500 text-center py-4">
              No hay reparticiones registradas
            </p>
          )}
        </CardContent>
      </Card>

      <ConfirmDialog
        open={confirmOpen}
        onOpenChange={setConfirmOpen}
        title="Confirmar Repartición"
        description={`Se distribuirán ${formatCurrency(totalToDistribute)} entre los socios seleccionados. Esta operación no se puede reversar automáticamente.`}
        onConfirm={handleConfirm}
        confirmLabel="Confirmar"
        variant="default"
      />
    </div>
  );
}
