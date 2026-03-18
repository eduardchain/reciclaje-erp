import { useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { ArrowLeft, AlertCircle, Paperclip, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { PageHeader } from "@/components/shared/PageHeader";
import { EntitySelect } from "@/components/shared/EntitySelect";
import { MoneyInput } from "@/components/shared/MoneyInput";
import { useCreateMovement, useUploadEvidence } from "@/hooks/useMoneyMovements";
import { useSuppliers, useCustomers, useInvestors, useMoneyAccounts, useExpenseCategoriesFlat, useThirdParties, useProvisions, useLiabilities, useGenericThirdParties } from "@/hooks/useMasterData";
import { formatCurrency, toLocalDateInput } from "@/utils/formatters";
import { ROUTES } from "@/utils/constants";

type MovementType = "payment_to_supplier" | "collection_from_client" | "expense" | "service_income" | "transfer" | "capital_injection" | "capital_return" | "commission_payment" | "provision_deposit" | "provision_expense" | "advance_payment" | "advance_collection" | "asset_payment" | "expense_accrual" | "liability_payment" | "payment_to_generic" | "collection_from_generic";

const typeLabels: Record<MovementType, string> = {
  payment_to_supplier: "Pago a Proveedor",
  collection_from_client: "Cobro a Cliente",
  expense: "Gasto",
  service_income: "Ingreso por Servicio",
  transfer: "Transferencia entre Cuentas",
  capital_injection: "Aporte de Capital",
  capital_return: "Devolucion de Capital",
  commission_payment: "Pago de Comision",
  provision_deposit: "Deposito a Provision",
  provision_expense: "Gasto desde Provision",
  advance_payment: "Anticipo a Proveedor",
  advance_collection: "Anticipo de Cliente",
  asset_payment: "Pago Activo Fijo",
  expense_accrual: "Causar Gasto (Pasivo)",
  liability_payment: "Pago de Pasivo",
  payment_to_generic: "Pago a Tercero Generico",
  collection_from_generic: "Cobro a Tercero Generico",
};

// Tipos frontend-only que mapean a un tipo backend diferente
const backendTypeMap: Partial<Record<MovementType, string>> = {
  liability_payment: "payment_to_supplier",
};

export default function MovementCreatePage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const initialType = (searchParams.get("type") as MovementType) || "payment_to_supplier";
  const initialProvisionId = searchParams.get("provision_id") || "";
  const initialThirdPartyId = searchParams.get("third_party_id") || "";
  const [type, setType] = useState<MovementType>(initialType);
  const isTypeLocked = !!searchParams.get("type");
  const backendType = backendTypeMap[type] ?? type;
  const create = useCreateMovement(backendType);
  const uploadEvidence = useUploadEvidence();

  const { data: suppliersData } = useSuppliers();
  const { data: customersData } = useCustomers();
  const { data: investorsData } = useInvestors();
  const { data: thirdPartiesData } = useThirdParties();
  const { data: accountsData } = useMoneyAccounts();
  const { data: expCategoriesData } = useExpenseCategoriesFlat();
  const { data: provisionsData } = useProvisions();
  const { data: liabilitiesData } = useLiabilities();
  const { data: genericData } = useGenericThirdParties();

  const suppliers = suppliersData?.items ?? [];
  const customers = customersData?.items ?? [];
  const investors = investorsData?.items ?? [];
  const thirdParties = thirdPartiesData?.items ?? [];
  const accounts = accountsData?.items ?? [];
  const expenseCategories = expCategoriesData?.items ?? [];
  const provisions = provisionsData?.items ?? [];
  const liabilities = liabilitiesData?.items ?? [];
  const generics = genericData?.items ?? [];

  const [amount, setAmount] = useState(0);
  const [accountId, setAccountId] = useState("");
  const [thirdPartyId, setThirdPartyId] = useState(initialThirdPartyId);
  const [provisionId, setProvisionId] = useState(initialProvisionId);
  const [expCategoryId, setExpCategoryId] = useState("");
  const [destAccountId, setDestAccountId] = useState("");
  const [description, setDescription] = useState("");
  const [date, setDate] = useState(toLocalDateInput());
  const [referenceNumber, setReferenceNumber] = useState("");
  const [notes, setNotes] = useState("");
  const [evidenceFile, setEvidenceFile] = useState<File | null>(null);

  const resetFields = () => {
    setAmount(0);
    setAccountId("");
    setThirdPartyId("");
    setProvisionId("");
    setExpCategoryId("");
    setDestAccountId("");
    setDescription("");
    setReferenceNumber("");
    setNotes("");
    setEvidenceFile(null);
  };

  const handleTypeChange = (v: string) => {
    setType(v as MovementType);
    resetFields();
  };

  // Fondos disponibles de la provision seleccionada
  const selectedProvision = provisions.find((p) => p.id === provisionId);
  const availableFunds = selectedProvision ? (selectedProvision.current_balance < 0 ? Math.abs(selectedProvision.current_balance) : 0) : 0;
  const isProvisionExpenseBlocked = type === "provision_expense" && provisionId && amount > availableFunds;

  const buildPayload = () => {
    const base = {
      amount,
      date,
      description: description || undefined,
      reference_number: referenceNumber || undefined,
      notes: notes || undefined,
    };

    switch (type) {
      case "payment_to_supplier":
      case "liability_payment":
        return { ...base, supplier_id: thirdPartyId, account_id: accountId };
      case "collection_from_client":
        return { ...base, customer_id: thirdPartyId, account_id: accountId };
      case "expense":
        return { ...base, expense_category_id: expCategoryId, account_id: accountId, description, third_party_id: thirdPartyId || undefined };
      case "service_income":
        return { ...base, account_id: accountId, description, third_party_id: thirdPartyId || undefined };
      case "transfer":
        return { ...base, source_account_id: accountId, destination_account_id: destAccountId, description };
      case "capital_injection":
        return { ...base, investor_id: thirdPartyId, account_id: accountId };
      case "capital_return":
        return { ...base, investor_id: thirdPartyId, account_id: accountId };
      case "commission_payment":
        return { ...base, third_party_id: thirdPartyId, account_id: accountId };
      case "provision_deposit":
        return { ...base, provision_id: provisionId, account_id: accountId };
      case "provision_expense":
        return { ...base, provision_id: provisionId, expense_category_id: expCategoryId, description };
      case "advance_payment":
        return { ...base, supplier_id: thirdPartyId, account_id: accountId };
      case "advance_collection":
        return { ...base, customer_id: thirdPartyId, account_id: accountId };
      case "asset_payment":
        return { ...base, account_id: accountId, description, third_party_id: thirdPartyId || undefined };
      case "expense_accrual":
        return { ...base, third_party_id: thirdPartyId, expense_category_id: expCategoryId, description };
      case "payment_to_generic":
      case "collection_from_generic":
        return { ...base, third_party_id: thirdPartyId, account_id: accountId };
    }
  };

  const handleSubmit = () => {
    const payload = buildPayload();
    create.mutate(payload, {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      onSuccess: (response: any) => {
        if (evidenceFile && response?.id) {
          uploadEvidence.mutate(
            { id: response.id, file: evidenceFile },
            { onSettled: () => navigate(ROUTES.TREASURY) },
          );
        } else {
          navigate(ROUTES.TREASURY);
        }
      },
    });
  };

  const getThirdPartyOptions = () => {
    switch (type) {
      case "payment_to_supplier":
      case "advance_payment": return suppliers.map((s) => ({ id: s.id, label: s.name }));
      case "liability_payment": return liabilities.map((l) => ({ id: l.id, label: l.name }));
      case "collection_from_client":
      case "advance_collection": return customers.map((c) => ({ id: c.id, label: c.name }));
      case "capital_injection":
      case "capital_return": return investors.map((i) => ({ id: i.id, label: i.name }));
      case "commission_payment": return thirdParties.map((t) => ({ id: t.id, label: t.name }));
      case "expense_accrual": return liabilities.map((l) => ({ id: l.id, label: l.name }));
      case "payment_to_generic":
      case "collection_from_generic": return generics.map((g) => ({ id: g.id, label: g.name }));
      default: return thirdParties.map((t) => ({ id: t.id, label: t.name }));
    }
  };

  const getThirdPartyLabel = () => {
    switch (type) {
      case "payment_to_supplier":
      case "advance_payment": return "Proveedor *";
      case "liability_payment": return "Pasivo *";
      case "collection_from_client":
      case "advance_collection": return "Cliente *";
      case "capital_injection":
      case "capital_return": return "Inversionista *";
      case "commission_payment": return "Comisionista *";
      case "expense_accrual": return "Tercero (Pasivo) *";
      case "payment_to_generic":
      case "collection_from_generic": return "Tercero *";
      default: return "Tercero";
    }
  };

  const needsThirdParty = ["payment_to_supplier", "collection_from_client", "capital_injection", "capital_return", "commission_payment", "advance_payment", "advance_collection", "expense_accrual", "liability_payment", "payment_to_generic", "collection_from_generic"].includes(type);
  const optionalThirdParty = type === "asset_payment";
  const needsProvision = type === "provision_deposit" || type === "provision_expense";
  const needsExpenseCategory = type === "expense" || type === "provision_expense" || type === "expense_accrual";
  const needsDestAccount = type === "transfer";
  const needsAccount = type !== "transfer" && type !== "provision_expense" && type !== "expense_accrual";
  const needsDescription = ["expense", "service_income", "transfer", "provision_expense", "asset_payment", "expense_accrual"].includes(type);

  return (
    <div className="space-y-6">
      <PageHeader title="Nuevo Movimiento" description="Registrar un movimiento de tesoreria">
        <Button variant="outline" onClick={() => navigate(ROUTES.TREASURY)}>
          <ArrowLeft className="h-4 w-4 mr-2" />Volver
        </Button>
      </PageHeader>

      {/* Tipo de movimiento */}
      <Card className="shadow-sm">
        <CardHeader><CardTitle className="text-sm font-semibold uppercase tracking-wider text-slate-500">Tipo de Movimiento</CardTitle></CardHeader>
        <CardContent>
          {isTypeLocked ? (
            <p className="text-sm font-medium text-slate-900 py-2">{typeLabels[type]}</p>
          ) : (
            <Select value={type} onValueChange={handleTypeChange}>
              <SelectTrigger className="w-full max-w-md">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {Object.entries(typeLabels).map(([key, label]) => (
                  <SelectItem key={key} value={key}>{label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          )}
        </CardContent>
      </Card>

      {/* Formulario dinamico */}
      <Card className="shadow-sm">
        <CardHeader><CardTitle className="text-sm font-semibold uppercase tracking-wider text-slate-500">{typeLabels[type]}</CardTitle></CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Monto *</Label>
              <MoneyInput value={amount} onChange={setAmount} placeholder="0" />
            </div>
            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Fecha *</Label>
              <Input type="date" value={date} onChange={(e) => setDate(e.target.value)} />
            </div>

            {needsThirdParty && (
              <div>
                <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">{getThirdPartyLabel()}</Label>
                <EntitySelect value={thirdPartyId} onChange={setThirdPartyId} options={getThirdPartyOptions()} placeholder="Seleccionar..." />
              </div>
            )}

            {optionalThirdParty && (
              <div>
                <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Tercero (opcional)</Label>
                <EntitySelect value={thirdPartyId} onChange={setThirdPartyId} options={getThirdPartyOptions()} placeholder="Seleccionar tercero..." />
              </div>
            )}

            {needsProvision && (
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
                {selectedProvision && type === "provision_expense" && (
                  <p className="text-xs mt-1 text-slate-500">
                    Fondos disponibles: <span className={availableFunds > 0 ? "text-emerald-600 font-medium" : "text-red-600 font-medium"}>{formatCurrency(availableFunds)}</span>
                  </p>
                )}
              </div>
            )}

            {needsExpenseCategory && (
              <div>
                <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Categoria de Gasto *</Label>
                <EntitySelect value={expCategoryId} onChange={setExpCategoryId} options={expenseCategories.map((c) => ({ id: c.id, label: c.display_name }))} placeholder="Seleccionar categoria..." />
              </div>
            )}

            {needsAccount && !needsDestAccount && (
              <div>
                <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Cuenta *</Label>
                <EntitySelect value={accountId} onChange={setAccountId} options={accounts.map((a) => ({ id: a.id, label: `${a.name} (${formatCurrency(a.current_balance)})` }))} placeholder="Seleccionar cuenta..." />
              </div>
            )}

            {needsDestAccount && (
              <>
                <div>
                  <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Cuenta Origen *</Label>
                  <EntitySelect value={accountId} onChange={setAccountId} options={accounts.map((a) => ({ id: a.id, label: `${a.name} (${formatCurrency(a.current_balance)})` }))} placeholder="Cuenta origen..." />
                </div>
                <div>
                  <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Cuenta Destino *</Label>
                  <EntitySelect value={destAccountId} onChange={setDestAccountId} options={accounts.filter((a) => a.id !== accountId).map((a) => ({ id: a.id, label: `${a.name} (${formatCurrency(a.current_balance)})` }))} placeholder="Cuenta destino..." />
                </div>
              </>
            )}

            {needsDescription && (
              <div className="md:col-span-2">
                <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Descripcion *</Label>
                <Input value={description} onChange={(e) => setDescription(e.target.value)} placeholder="Descripcion del movimiento" />
              </div>
            )}

            {!needsDescription && type !== "expense" && (
              <div className="md:col-span-2">
                <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Descripcion</Label>
                <Input value={description} onChange={(e) => setDescription(e.target.value)} placeholder="Descripcion (opcional)" />
              </div>
            )}

            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Referencia</Label>
              <Input value={referenceNumber} onChange={(e) => setReferenceNumber(e.target.value)} placeholder="Numero de referencia" />
            </div>
            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Notas</Label>
              <Textarea value={notes} onChange={(e) => setNotes(e.target.value)} rows={2} placeholder="Notas adicionales..." />
            </div>
            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Comprobante</Label>
              {!evidenceFile ? (
                <Input
                  type="file"
                  accept="image/*,.pdf"
                  onChange={(e) => setEvidenceFile(e.target.files?.[0] || null)}
                  className="cursor-pointer"
                />
              ) : (
                <div className="flex items-center gap-2 mt-1 p-2 bg-slate-50 rounded-md border">
                  <Paperclip className="h-4 w-4 text-slate-400 shrink-0" />
                  <span className="text-sm text-slate-700 truncate">{evidenceFile.name}</span>
                  <button type="button" onClick={() => setEvidenceFile(null)} className="ml-auto text-slate-400 hover:text-red-500">
                    <X className="h-4 w-4" />
                  </button>
                </div>
              )}
            </div>
          </div>

          {isProvisionExpenseBlocked && (
            <div className="flex items-center gap-2 mt-4 p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
              <AlertCircle className="h-4 w-4 shrink-0" />
              <span>El monto ({formatCurrency(amount)}) excede los fondos disponibles ({formatCurrency(availableFunds)})</span>
            </div>
          )}
        </CardContent>
      </Card>

      <div className="sticky bottom-0 bg-white/95 backdrop-blur-sm border-t border-slate-100 py-4 -mx-6 px-6 mt-6">
        <div className="flex justify-end gap-2">
          <Button variant="outline" onClick={() => navigate(ROUTES.TREASURY)}>Cancelar</Button>
          <Button
            onClick={handleSubmit}
            disabled={create.isPending || amount <= 0 || !!isProvisionExpenseBlocked}
            className="bg-emerald-600 hover:bg-emerald-700"
          >
            {create.isPending ? "Creando..." : "Crear Movimiento"}
          </Button>
        </div>
      </div>
    </div>
  );
}
