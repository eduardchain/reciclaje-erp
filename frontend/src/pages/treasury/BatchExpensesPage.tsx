import { useState, useCallback, useRef } from "react";
import { toast } from "sonner";
import { PageHeader } from "@/components/shared/PageHeader";
import { MoneyInput } from "@/components/shared/MoneyInput";
import { EntitySelect } from "@/components/shared/EntitySelect";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Plus, Trash2, Copy } from "lucide-react";
import { useExpenseCategoriesFlat, useMoneyAccounts } from "@/hooks/useMasterData";
import { useBusinessUnits } from "@/hooks/useCrudData";
import { useCreateBatchExpenses } from "@/hooks/useMoneyMovements";
import { toLocalDateInput, formatCurrency } from "@/utils/formatters";
import { AxiosError } from "axios";

interface ExpenseRow {
  _key: number;
  amount: number;
  date: string;
  expense_category_id: string;
  business_unit_id: string;
  account_id: string;
  description: string;
  reference_number: string;
  error?: Record<string, string>;
}

const MAX_ROWS = 50;

let keyCounter = 0;
function nextKey() {
  return ++keyCounter;
}

function makeEmptyRow(defaults: {
  date: string;
  account_id: string;
  expense_category_id: string;
  business_unit_id: string;
}): ExpenseRow {
  return {
    _key: nextKey(),
    amount: 0,
    date: defaults.date,
    expense_category_id: defaults.expense_category_id,
    business_unit_id: defaults.business_unit_id,
    account_id: defaults.account_id,
    description: "",
    reference_number: "",
  };
}

export default function BatchExpensesPage() {
  const today = toLocalDateInput();

  // Global defaults
  const [defaultAccountId, setDefaultAccountId] = useState("");
  const [defaultCategoryId, setDefaultCategoryId] = useState("");
  const [defaultDate, setDefaultDate] = useState(today);
  const [defaultBusinessUnitId, setDefaultBusinessUnitId] = useState("");

  const defaults = useRef({ date: today, account_id: "", expense_category_id: "", business_unit_id: "" });
  defaults.current = { date: defaultDate, account_id: defaultAccountId, expense_category_id: defaultCategoryId, business_unit_id: defaultBusinessUnitId };

  const [rows, setRows] = useState<ExpenseRow[]>(() =>
    Array.from({ length: 5 }, () => makeEmptyRow(defaults.current))
  );

  // Data hooks
  const { data: categoriesData, isLoading: catsLoading } = useExpenseCategoriesFlat();
  const { data: accountsData, isLoading: accsLoading } = useMoneyAccounts();
  const { data: busData, isLoading: busLoading } = useBusinessUnits();
  const batchMutation = useCreateBatchExpenses();

  const categories = categoriesData?.items ?? [];
  const accounts = accountsData?.items ?? [];
  const businessUnits = busData?.items ?? [];

  const categoryOptions = categories.map((c: { id: string; display_name?: string; name?: string }) => ({
    id: c.id,
    label: c.display_name ?? c.name ?? "",
  }));
  const accountOptions = accounts.map((a: { id: string; name: string }) => ({
    id: a.id,
    label: a.name,
  }));
  const buOptions = businessUnits.map((b: { id: string; name: string }) => ({
    id: b.id,
    label: b.name,
  }));

  // Update a single row field
  const updateRow = useCallback((key: number, field: keyof ExpenseRow, value: unknown) => {
    setRows((prev) =>
      prev.map((r) => {
        if (r._key !== key) return r;
        const updated = { ...r, [field]: value };
        if (r.error) {
          const newError = { ...r.error };
          delete newError[field];
          updated.error = Object.keys(newError).length > 0 ? newError : undefined;
        }
        return updated;
      })
    );
  }, []);

  // Add row
  const addRow = useCallback(() => {
    setRows((prev) => {
      if (prev.length >= MAX_ROWS) {
        toast.error(`Maximo ${MAX_ROWS} filas`);
        return prev;
      }
      return [...prev, makeEmptyRow(defaults.current)];
    });
  }, []);

  // Remove row
  const removeRow = useCallback((key: number) => {
    setRows((prev) => {
      if (prev.length <= 1) return prev;
      return prev.filter((r) => r._key !== key);
    });
  }, []);

  // Apply defaults
  const applyToAll = useCallback((field: keyof ExpenseRow, value: string) => {
    setRows((prev) => prev.map((r) => ({ ...r, [field]: value })));
  }, []);

  // Filter non-empty rows
  const filledRows = rows.filter((r) => r.amount > 0 || r.description.trim() !== "");

  // Total
  const total = rows.reduce((sum, r) => sum + (r.amount || 0), 0);

  // Validation
  const validate = (): boolean => {
    let valid = true;
    setRows((prev) =>
      prev.map((r) => {
        if (r.amount === 0 && r.description.trim() === "") return { ...r, error: undefined };
        const error: Record<string, string> = {};
        if (!r.amount || r.amount <= 0) error.amount = "Monto requerido";
        if (!r.expense_category_id) error.expense_category_id = "Seleccione categoria";
        if (!r.account_id) error.account_id = "Seleccione cuenta";
        if (!r.date) error.date = "Fecha requerida";
        if (!r.description.trim()) error.description = "Descripcion requerida";
        if (Object.keys(error).length > 0) {
          valid = false;
          return { ...r, error };
        }
        return { ...r, error: undefined };
      })
    );
    return valid;
  };

  // Submit
  const handleSubmit = () => {
    if (filledRows.length === 0) {
      toast.error("No hay filas con datos para guardar");
      return;
    }
    if (!validate()) {
      toast.error("Corrige los errores antes de guardar");
      return;
    }

    const items = filledRows.map((r) => ({
      amount: r.amount,
      expense_category_id: r.expense_category_id,
      account_id: r.account_id,
      date: r.date,
      description: r.description.trim(),
      ...(r.reference_number.trim() ? { reference_number: r.reference_number.trim() } : {}),
      ...(r.business_unit_id ? { business_unit_id: r.business_unit_id } : {}),
    }));

    batchMutation.mutate(items, {
      onSuccess: () => {
        setRows(Array.from({ length: 5 }, () => makeEmptyRow(defaults.current)));
      },
      onError: (error: unknown) => {
        const axiosErr = error as AxiosError<{ detail?: unknown }>;
        const detail = axiosErr?.response?.data?.detail;

        // Format 1: Our service errors {errors: [{row, field, message}]}
        if (detail && typeof detail === "object" && "errors" in (detail as Record<string, unknown>) && Array.isArray((detail as Record<string, unknown>).errors)) {
          const errors = (detail as { errors: Array<{ row: number; field: string; message: string }> }).errors;
          setRows((prev) => {
            const filled = prev.filter((r) => r.amount > 0 || r.description.trim() !== "");
            const filledKeys = filled.map((r) => r._key);
            const updated = [...prev];
            for (const err of errors) {
              const targetKey = filledKeys[err.row];
              if (targetKey == null) continue;
              const idx = updated.findIndex((r) => r._key === targetKey);
              if (idx === -1) continue;
              updated[idx] = {
                ...updated[idx],
                error: { ...(updated[idx].error || {}), [err.field]: err.message },
              };
            }
            return updated;
          });
          toast.error("Error en algunos registros — revisa los campos marcados");
        }
        // Format 2: Pydantic validation [{type, loc: [body, items, N, field], msg}]
        else if (Array.isArray(detail)) {
          setRows((prev) => {
            const filled = prev.filter((r) => r.amount > 0 || r.description.trim() !== "");
            const filledKeys = filled.map((r) => r._key);
            const updated = [...prev];
            for (const err of detail as Array<{ loc?: string[]; msg?: string }>) {
              if (!err.loc || err.loc.length < 4) continue;
              const rowIdx = Number(err.loc[2]);
              const field = err.loc[3];
              const targetKey = filledKeys[rowIdx];
              if (targetKey == null) continue;
              const idx = updated.findIndex((r) => r._key === targetKey);
              if (idx === -1) continue;
              // Traducir mensajes de Pydantic a español
              const fieldLabels: Record<string, string> = {
                expense_category_id: "Categoria",
                account_id: "Cuenta",
                amount: "Monto",
                date: "Fecha",
                description: "Descripcion",
              };
              let msg = err.msg || "Campo requerido";
              if (msg.includes("invalid") || msg.includes("UUID")) msg = `${fieldLabels[field] || field} invalido`;
              else if (msg.includes("required") || msg.includes("missing")) msg = `${fieldLabels[field] || field} requerido`;
              else if (msg.includes("at least 1 character")) msg = `${fieldLabels[field] || field} no puede estar vacio`;
              updated[idx] = {
                ...updated[idx],
                error: { ...(updated[idx].error || {}), [field]: msg },
              };
            }
            return updated;
          });
          toast.error("Campos requeridos faltantes — revisa los marcados en rojo");
        } else {
          const msg = detail && typeof detail === "string" ? detail : "Error al crear los gastos";
          toast.error(msg);
        }
      },
    });
  };

  // Handle Enter on last row
  const handleKeyDown = (e: React.KeyboardEvent, rowKey: number) => {
    if (e.key === "Enter") {
      const lastRow = rows[rows.length - 1];
      if (lastRow && lastRow._key === rowKey) {
        e.preventDefault();
        addRow();
      }
    }
  };

  const inputCls = (row: ExpenseRow, field: string) =>
    row.error?.[field] ? "border-red-500 focus:ring-red-500" : "";

  const errorMsg = (row: ExpenseRow, field: string) =>
    row.error?.[field] ? <p className="text-[10px] text-red-500 mt-0.5">{row.error[field]}</p> : null;

  return (
    <div>
      <PageHeader title="Gastos Masivos" description="Registra multiples gastos de forma rapida">
        <Button onClick={handleSubmit} disabled={batchMutation.isPending || filledRows.length === 0}>
          {batchMutation.isPending ? "Guardando..." : `Guardar Todo (${filledRows.length})`}
        </Button>
      </PageHeader>

      {/* Global defaults */}
      <div className="bg-white border rounded-lg p-4 mb-4">
        <h3 className="text-sm font-medium text-slate-700 mb-3">Valores por defecto</h3>
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
          {/* Date */}
          <div>
            <label className="text-xs text-slate-500 mb-1 block">Fecha</label>
            <div className="flex gap-1">
              <Input
                type="date"
                value={defaultDate}
                onChange={(e) => setDefaultDate(e.target.value)}
                className="flex-1"
              />
              <Button
                variant="ghost"
                size="icon"
                className="shrink-0 h-9 w-9"
                title="Aplicar a todas"
                onClick={() => applyToAll("date", defaultDate)}
                disabled={!defaultDate}
              >
                <Copy className="w-3.5 h-3.5" />
              </Button>
            </div>
          </div>

          {/* Category */}
          <div>
            <label className="text-xs text-slate-500 mb-1 block">Categoria</label>
            <div className="flex gap-1">
              <div className="flex-1">
                <EntitySelect
                  value={defaultCategoryId}
                  onChange={setDefaultCategoryId}
                  options={categoryOptions}
                  placeholder="Categoria..."
                  loading={catsLoading}
                />
              </div>
              <Button
                variant="ghost"
                size="icon"
                className="shrink-0 h-9 w-9"
                title="Aplicar a todas"
                onClick={() => applyToAll("expense_category_id", defaultCategoryId)}
                disabled={!defaultCategoryId}
              >
                <Copy className="w-3.5 h-3.5" />
              </Button>
            </div>
          </div>

          {/* Business Unit */}
          <div>
            <label className="text-xs text-slate-500 mb-1 block">Unidad de Negocio</label>
            <div className="flex gap-1">
              <div className="flex-1">
                <EntitySelect
                  value={defaultBusinessUnitId}
                  onChange={setDefaultBusinessUnitId}
                  options={buOptions}
                  placeholder="UN..."
                  loading={busLoading}
                />
              </div>
              <Button
                variant="ghost"
                size="icon"
                className="shrink-0 h-9 w-9"
                title="Aplicar a todas"
                onClick={() => applyToAll("business_unit_id", defaultBusinessUnitId)}
                disabled={!defaultBusinessUnitId}
              >
                <Copy className="w-3.5 h-3.5" />
              </Button>
            </div>
          </div>

          {/* Account */}
          <div>
            <label className="text-xs text-slate-500 mb-1 block">Cuenta</label>
            <div className="flex gap-1">
              <div className="flex-1">
                <EntitySelect
                  value={defaultAccountId}
                  onChange={setDefaultAccountId}
                  options={accountOptions}
                  placeholder="Cuenta..."
                  loading={accsLoading}
                />
              </div>
              <Button
                variant="ghost"
                size="icon"
                className="shrink-0 h-9 w-9"
                title="Aplicar a todas"
                onClick={() => applyToAll("account_id", defaultAccountId)}
                disabled={!defaultAccountId}
              >
                <Copy className="w-3.5 h-3.5" />
              </Button>
            </div>
          </div>
        </div>
      </div>

      {/* Table */}
      <div className="bg-white border rounded-lg overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b bg-slate-50 text-slate-600">
              <th className="px-2 py-2 text-center w-8">#</th>
              <th className="px-2 py-2 text-left w-32">Monto</th>
              <th className="px-2 py-2 text-left w-36">Fecha</th>
              <th className="px-2 py-2 text-left min-w-[180px]">Categoria</th>
              <th className="px-2 py-2 text-left min-w-[140px]">UN</th>
              <th className="px-2 py-2 text-left min-w-[160px]">Cuenta</th>
              <th className="px-2 py-2 text-left min-w-[180px]">Descripcion</th>
              <th className="px-2 py-2 text-left w-28">Ref</th>
              <th className="px-2 py-2 text-center w-10"></th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row, idx) => (
              <tr
                key={row._key}
                className="border-b last:border-b-0 hover:bg-slate-50/50"
                onKeyDown={(e) => handleKeyDown(e, row._key)}
              >
                <td className="px-2 py-1.5 text-center text-slate-400 text-xs">{idx + 1}</td>
                <td className="px-2 py-1.5">
                  <MoneyInput
                    value={row.amount}
                    onChange={(v) => updateRow(row._key, "amount", v)}
                    placeholder="0"
                    className={`h-8 ${inputCls(row, "amount")}`}
                  />
                  {errorMsg(row, "amount")}
                </td>
                <td className="px-2 py-1.5">
                  <Input
                    type="date"
                    value={row.date}
                    onChange={(e) => updateRow(row._key, "date", e.target.value)}
                    className={`h-8 ${inputCls(row, "date")}`}
                  />
                  {errorMsg(row, "date")}
                </td>
                <td className="px-2 py-1.5">
                  <div className={row.error?.expense_category_id ? "ring-1 ring-red-500 rounded-md" : ""}>
                    <EntitySelect
                      value={row.expense_category_id}
                      onChange={(v) => updateRow(row._key, "expense_category_id", v)}
                      options={categoryOptions}
                      placeholder="Categoria..."
                      loading={catsLoading}
                    />
                  </div>
                  {errorMsg(row, "expense_category_id")}
                </td>
                <td className="px-2 py-1.5">
                  <EntitySelect
                    value={row.business_unit_id}
                    onChange={(v) => updateRow(row._key, "business_unit_id", v)}
                    options={buOptions}
                    placeholder="UN..."
                    loading={busLoading}
                  />
                </td>
                <td className="px-2 py-1.5">
                  <div className={row.error?.account_id ? "ring-1 ring-red-500 rounded-md" : ""}>
                    <EntitySelect
                      value={row.account_id}
                      onChange={(v) => updateRow(row._key, "account_id", v)}
                      options={accountOptions}
                      placeholder="Cuenta..."
                      loading={accsLoading}
                    />
                  </div>
                  {errorMsg(row, "account_id")}
                </td>
                <td className="px-2 py-1.5">
                  <Input
                    value={row.description}
                    onChange={(e) => updateRow(row._key, "description", e.target.value)}
                    placeholder="Descripcion del gasto"
                    className={`h-8 ${inputCls(row, "description")}`}
                  />
                  {errorMsg(row, "description")}
                </td>
                <td className="px-2 py-1.5">
                  <Input
                    value={row.reference_number}
                    onChange={(e) => updateRow(row._key, "reference_number", e.target.value)}
                    placeholder="Ref"
                    className="h-8"
                  />
                </td>
                <td className="px-2 py-1.5 text-center">
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-7 w-7 text-slate-400 hover:text-red-500"
                    onClick={() => removeRow(row._key)}
                    disabled={rows.length <= 1}
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </Button>
                </td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr className="border-t bg-slate-50">
              <td colSpan={2} className="px-2 py-2">
                <Button
                  variant="ghost"
                  size="sm"
                  className="text-xs"
                  onClick={addRow}
                  disabled={rows.length >= MAX_ROWS}
                >
                  <Plus className="w-3.5 h-3.5 mr-1" />
                  Agregar fila
                </Button>
              </td>
              <td colSpan={5} className="px-2 py-2 text-right font-semibold text-slate-700">
                Total: {formatCurrency(total)}
              </td>
              <td colSpan={2}></td>
            </tr>
          </tfoot>
        </table>
      </div>
    </div>
  );
}
