import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowLeft } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { PageHeader } from "@/components/shared/PageHeader";
import { EntitySelect } from "@/components/shared/EntitySelect";
import { useCreateDeferredExpense } from "@/hooks/useDeferredExpenses";
import { useMoneyAccounts, useExpenseCategories, useProvisions } from "@/hooks/useMasterData";
import { MoneyInput } from "@/components/shared/MoneyInput";
import { formatCurrency, toLocalDateInput } from "@/utils/formatters";
import { ROUTES } from "@/utils/constants";
import type { DeferredExpenseType } from "@/types/deferred-expense";

export default function DeferredExpenseCreatePage() {
  const navigate = useNavigate();
  const create = useCreateDeferredExpense();

  const { data: accountsData } = useMoneyAccounts();
  const { data: categoriesData } = useExpenseCategories();
  const { data: provisionsData } = useProvisions();

  const accounts = accountsData?.items ?? [];
  const categories = categoriesData?.items ?? [];
  const provisions = provisionsData?.items ?? [];

  const [name, setName] = useState("");
  const [totalAmount, setTotalAmount] = useState(0);
  const [totalMonths, setTotalMonths] = useState(12);
  const [expenseType, setExpenseType] = useState<DeferredExpenseType>("expense");
  const [categoryId, setCategoryId] = useState("");
  const [accountId, setAccountId] = useState("");
  const [provisionId, setProvisionId] = useState("");
  const [description, setDescription] = useState("");
  const [startDate, setStartDate] = useState(toLocalDateInput());

  const monthlyAmount = totalAmount > 0 && totalMonths >= 2
    ? Math.floor((totalAmount / totalMonths) * 100) / 100
    : 0;
  const lastMonthAmount = totalAmount > 0 && totalMonths >= 2
    ? totalAmount - monthlyAmount * (totalMonths - 1)
    : 0;

  const canSubmit =
    name.trim() !== "" &&
    totalAmount > 0 &&
    totalMonths >= 2 &&
    categoryId !== "" &&
    (expenseType === "expense" ? accountId !== "" : provisionId !== "") &&
    !create.isPending;

  const handleSubmit = () => {
    create.mutate(
      {
        name,
        total_amount: totalAmount,
        total_months: totalMonths,
        expense_category_id: categoryId,
        expense_type: expenseType,
        account_id: expenseType === "expense" ? accountId : null,
        provision_id: expenseType === "provision_expense" ? provisionId : null,
        description: description || null,
        start_date: startDate,
      },
      {
        onSuccess: () => navigate(ROUTES.TREASURY_DEFERRED),
      },
    );
  };

  return (
    <div className="space-y-6">
      <PageHeader title="Nuevo Gasto Programado" description="Distribuir un gasto grande en cuotas mensuales">
        <Button variant="outline" onClick={() => navigate(ROUTES.TREASURY_DEFERRED)}>
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
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Tipo de Gasto *</Label>
              <Select value={expenseType} onValueChange={(v) => setExpenseType(v as DeferredExpenseType)}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="expense">Desde Cuenta de Dinero</SelectItem>
                  <SelectItem value="provision_expense">Desde Provision</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Categoria de Gasto *</Label>
              <EntitySelect
                value={categoryId}
                onChange={setCategoryId}
                options={categories.map((c) => ({ id: c.id, label: c.name }))}
                placeholder="Seleccionar categoria..."
              />
            </div>

            {expenseType === "expense" && (
              <div>
                <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Cuenta *</Label>
                <EntitySelect
                  value={accountId}
                  onChange={setAccountId}
                  options={accounts.map((a) => ({ id: a.id, label: `${a.name} (${formatCurrency(a.current_balance)})` }))}
                  placeholder="Seleccionar cuenta..."
                />
              </div>
            )}

            {expenseType === "provision_expense" && (
              <div>
                <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Provision *</Label>
                <EntitySelect
                  value={provisionId}
                  onChange={setProvisionId}
                  options={provisions.map((p) => ({
                    id: p.id,
                    label: `${p.name} (Fondos: ${formatCurrency(p.current_balance < 0 ? Math.abs(p.current_balance) : 0)})`,
                  }))}
                  placeholder="Seleccionar provision..."
                />
              </div>
            )}

            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Fecha Inicio *</Label>
              <Input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} />
            </div>

            <div className="md:col-span-2">
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Descripcion</Label>
              <Input value={description} onChange={(e) => setDescription(e.target.value)} placeholder="Descripcion adicional (opcional)" />
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Preview de cuotas */}
      {totalAmount > 0 && totalMonths >= 2 && (
        <Card className="shadow-sm border-t-[3px] border-t-emerald-500">
          <CardContent className="p-5">
            <p className="text-xs font-semibold uppercase tracking-wider text-slate-500 mb-3">Vista Previa</p>
            <div className="grid grid-cols-3 gap-4">
              <div>
                <p className="text-xs text-slate-400">Cuota mensual</p>
                <p className="text-lg font-bold text-slate-900 tabular-nums">{formatCurrency(monthlyAmount)}</p>
              </div>
              <div>
                <p className="text-xs text-slate-400">Ultima cuota (ajuste)</p>
                <p className="text-lg font-bold text-slate-900 tabular-nums">{formatCurrency(lastMonthAmount)}</p>
              </div>
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
          <Button variant="outline" onClick={() => navigate(ROUTES.TREASURY_DEFERRED)}>Cancelar</Button>
          <Button
            onClick={handleSubmit}
            disabled={!canSubmit}
            className="bg-emerald-600 hover:bg-emerald-700"
          >
            {create.isPending ? "Creando..." : "Crear Gasto Programado"}
          </Button>
        </div>
      </div>
    </div>
  );
}
