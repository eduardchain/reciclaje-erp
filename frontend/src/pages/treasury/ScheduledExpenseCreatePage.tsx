import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowLeft } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { PageHeader } from "@/components/shared/PageHeader";
import { EntitySelect } from "@/components/shared/EntitySelect";
import { MoneyInput } from "@/components/shared/MoneyInput";
import { useCreateScheduledExpense } from "@/hooks/useScheduledExpenses";
import { useMoneyAccounts, useExpenseCategoriesFlat } from "@/hooks/useMasterData";
import { formatCurrency, toLocalDateInput } from "@/utils/formatters";
import { ROUTES } from "@/utils/constants";

export default function ScheduledExpenseCreatePage() {
  const navigate = useNavigate();
  const create = useCreateScheduledExpense();

  const { data: accountsData } = useMoneyAccounts();
  const { data: categoriesData } = useExpenseCategoriesFlat();

  const accounts = accountsData?.items ?? [];
  const categories = categoriesData?.items ?? [];

  const [name, setName] = useState("");
  const [totalAmount, setTotalAmount] = useState(0);
  const [totalMonths, setTotalMonths] = useState(12);
  const [accountId, setAccountId] = useState("");
  const [categoryId, setCategoryId] = useState("");
  const [startDate, setStartDate] = useState(toLocalDateInput());
  const [applyDay, setApplyDay] = useState(1);
  const [description, setDescription] = useState("");

  const monthlyAmount = totalAmount > 0 && totalMonths >= 2
    ? Math.floor((totalAmount / totalMonths) * 100) / 100
    : 0;
  const lastMonthAmount = totalAmount > 0 && totalMonths >= 2
    ? +(totalAmount - monthlyAmount * (totalMonths - 1)).toFixed(2)
    : 0;

  const selectedAccount = accounts.find((a) => a.id === accountId);

  const canSubmit =
    name.trim() !== "" &&
    totalAmount > 0 &&
    totalMonths >= 2 &&
    accountId !== "" &&
    categoryId !== "" &&
    !create.isPending;

  const handleSubmit = () => {
    create.mutate(
      {
        name,
        total_amount: totalAmount,
        total_months: totalMonths,
        source_account_id: accountId,
        expense_category_id: categoryId,
        start_date: startDate,
        apply_day: applyDay,
        description: description || null,
      },
      {
        onSuccess: () => navigate(ROUTES.TREASURY_SCHEDULED),
      },
    );
  };

  return (
    <div className="space-y-6">
      <PageHeader title="Nuevo Gasto Diferido" description="Pago upfront con distribucion mensual en P&L">
        <Button variant="outline" onClick={() => navigate(ROUTES.TREASURY_SCHEDULED)}>
          <ArrowLeft className="h-4 w-4 mr-2" />Volver
        </Button>
      </PageHeader>

      <Card className="shadow-sm">
        <CardHeader>
          <CardTitle className="text-sm font-semibold uppercase tracking-wider text-slate-500">Datos del Gasto</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="md:col-span-2">
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Nombre *</Label>
              <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="Ej: Seguro anual 2026" />
            </div>

            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Monto Total *</Label>
              <MoneyInput value={totalAmount} onChange={setTotalAmount} placeholder="0" />
            </div>
            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Meses (cuotas) *</Label>
              <Input
                type="number"
                min={2}
                max={60}
                value={totalMonths}
                onChange={(e) => setTotalMonths(parseInt(e.target.value) || 2)}
              />
            </div>

            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Cuenta Origen *</Label>
              <EntitySelect
                value={accountId}
                onChange={setAccountId}
                options={accounts.map((a) => ({ id: a.id, label: `${a.name} (${formatCurrency(a.current_balance)})` }))}
                placeholder="Seleccionar cuenta..."
              />
              {selectedAccount && (
                <p className="text-xs mt-1 text-slate-500">
                  Saldo disponible: <span className="font-medium">{formatCurrency(selectedAccount.current_balance)}</span>
                </p>
              )}
            </div>

            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Categoria de Gasto *</Label>
              <EntitySelect
                value={categoryId}
                onChange={setCategoryId}
                options={categories.map((c) => ({ id: c.id, label: c.display_name }))}
                placeholder="Seleccionar categoria..."
              />
            </div>

            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Fecha Inicio *</Label>
              <Input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} />
            </div>

            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Dia del Mes para Cuotas</Label>
              <Input
                type="number"
                min={1}
                max={28}
                value={applyDay}
                onChange={(e) => setApplyDay(parseInt(e.target.value) || 1)}
              />
              <p className="text-xs mt-1 text-slate-400">Dia del mes en que se aplica cada cuota (1-28)</p>
            </div>

            <div className="md:col-span-2">
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Descripcion</Label>
              <Input value={description} onChange={(e) => setDescription(e.target.value)} placeholder="Descripcion adicional (opcional)" />
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Preview */}
      {totalAmount > 0 && totalMonths >= 2 && (
        <Card className="shadow-sm border-t-[3px] border-t-emerald-500">
          <CardContent className="p-5">
            <p className="text-xs font-semibold uppercase tracking-wider text-slate-500 mb-3">Vista Previa</p>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div>
                <p className="text-xs text-slate-400">Pago upfront (sale de cuenta)</p>
                <p className="text-lg font-bold text-rose-600 tabular-nums">{formatCurrency(totalAmount)}</p>
              </div>
              <div>
                <p className="text-xs text-slate-400">Cuota mensual en P&L</p>
                <p className="text-lg font-bold text-slate-900 tabular-nums">{formatCurrency(monthlyAmount)}</p>
              </div>
              {lastMonthAmount !== monthlyAmount && (
                <div>
                  <p className="text-xs text-slate-400">Ultima cuota (ajuste)</p>
                  <p className="text-lg font-bold text-slate-900 tabular-nums">{formatCurrency(lastMonthAmount)}</p>
                </div>
              )}
              <div>
                <p className="text-xs text-slate-400">Total verificado</p>
                <p className="text-lg font-bold text-slate-900 tabular-nums">
                  {formatCurrency(monthlyAmount * (totalMonths - 1) + lastMonthAmount)}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      <div className="sticky bottom-0 bg-white/95 backdrop-blur-sm border-t border-slate-100 py-4 -mx-6 px-6 mt-6">
        <div className="flex justify-end gap-2">
          <Button variant="outline" onClick={() => navigate(ROUTES.TREASURY_SCHEDULED)}>Cancelar</Button>
          <Button
            onClick={handleSubmit}
            disabled={!canSubmit}
            className="bg-emerald-600 hover:bg-emerald-700"
          >
            {create.isPending ? "Creando..." : "Crear Gasto Diferido"}
          </Button>
        </div>
      </div>
    </div>
  );
}
