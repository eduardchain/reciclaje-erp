import { useState, useMemo } from "react";
import { TrendingUp, TrendingDown, DollarSign, XCircle } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
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
  useAnnulDistribution,
} from "@/hooks/useProfitDistributions";
import { formatCurrency, formatDate, toLocalDatetimeInput } from "@/utils/formatters";

export default function ProfitDistributionPage() {
  const { data: available, isLoading: loadingAvailable } = useAvailableProfit();
  const { data: partners, isLoading: loadingPartners } = usePartners();
  const { data: history, isLoading: loadingHistory } = useProfitDistributions({ limit: 50 });
  const createMutation = useCreateDistribution();
  const annulMutation = useAnnulDistribution();

  const [date, setDate] = useState(toLocalDatetimeInput().slice(0, 10));
  const [notes, setNotes] = useState("");
  const [amounts, setAmounts] = useState<Record<string, number>>({});
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [annulTargetId, setAnnulTargetId] = useState<string | null>(null);
  const [annulReason, setAnnulReason] = useState("");

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

  const handleAnnulConfirm = () => {
    if (!annulTargetId || !annulReason.trim()) return;
    annulMutation.mutate(
      { id: annulTargetId, reason: annulReason.trim() },
      {
        onSuccess: () => {
          setAnnulTargetId(null);
          setAnnulReason("");
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
            <Table className="min-w-[560px]">
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
            <Table className="min-w-[640px]">
              <TableHeader>
                <TableRow>
                  <TableHead>Fecha</TableHead>
                  <TableHead className="text-right">Monto Total</TableHead>
                  <TableHead className="text-center"># Socios</TableHead>
                  <TableHead>Detalle</TableHead>
                  <TableHead>Notas</TableHead>
                  <TableHead className="text-center">Estado</TableHead>
                  <TableHead className="text-right">Acciones</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {history.items.map((dist) => {
                  const annulled = dist.status === "annulled";
                  return (
                    <TableRow key={dist.id} className={annulled ? "opacity-60" : ""}>
                      <TableCell>{formatDate(dist.date)}</TableCell>
                      <TableCell className={`text-right font-medium ${annulled ? "line-through text-slate-400" : ""}`}>
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
                      <TableCell className="text-center">
                        {annulled ? (
                          <Badge variant="secondary" className="bg-rose-100 text-rose-700" title={dist.annulled_reason ?? undefined}>
                            Anulada
                          </Badge>
                        ) : (
                          <Badge variant="secondary" className="bg-emerald-100 text-emerald-700">
                            Confirmada
                          </Badge>
                        )}
                      </TableCell>
                      <TableCell className="text-right">
                        {!annulled && (
                          <Button
                            variant="ghost"
                            size="sm"
                            className="h-8 px-2 text-xs text-rose-600 hover:text-rose-700 hover:bg-rose-50"
                            onClick={() => {
                              setAnnulTargetId(dist.id);
                              setAnnulReason("");
                            }}
                          >
                            <XCircle className="h-3.5 w-3.5 mr-1" />
                            Anular
                          </Button>
                        )}
                      </TableCell>
                    </TableRow>
                  );
                })}
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
        description={`Se distribuirán ${formatCurrency(totalToDistribute)} entre los socios seleccionados.`}
        onConfirm={handleConfirm}
        confirmLabel="Confirmar"
        variant="default"
      />

      <ConfirmDialog
        open={!!annulTargetId}
        onOpenChange={(open) => {
          if (!open) {
            setAnnulTargetId(null);
            setAnnulReason("");
          }
        }}
        title="Anular Repartición"
        description="Se revertirán los saldos de los socios afectados y se anularán los movimientos asociados. Esta acción no se puede deshacer."
        confirmLabel="Anular"
        variant="destructive"
        onConfirm={handleAnnulConfirm}
        loading={annulMutation.isPending}
        disabled={!annulReason.trim()}
      >
        <div className="py-2">
          <Label>Razón de anulación *</Label>
          <Input
            value={annulReason}
            onChange={(e) => setAnnulReason(e.target.value)}
            placeholder="Ej: Error en monto, distribución duplicada..."
          />
        </div>
      </ConfirmDialog>
    </div>
  );
}
