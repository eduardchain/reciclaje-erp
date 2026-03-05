import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowLeft } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { PageHeader } from "@/components/shared/PageHeader";
import { EntitySelect } from "@/components/shared/EntitySelect";
import { useCreateMovement } from "@/hooks/useMoneyMovements";
import { useSuppliers, useCustomers, useInvestors, useMoneyAccounts, useExpenseCategories, useThirdParties } from "@/hooks/useMasterData";
import { formatCurrency } from "@/utils/formatters";
import { ROUTES } from "@/utils/constants";

type MovementType = "payment_to_supplier" | "collection_from_client" | "expense" | "service_income" | "transfer" | "capital_injection" | "capital_return" | "commission_payment";

const typeLabels: Record<MovementType, string> = {
  payment_to_supplier: "Pago a Proveedor",
  collection_from_client: "Cobro a Cliente",
  expense: "Gasto",
  service_income: "Ingreso por Servicio",
  transfer: "Transferencia entre Cuentas",
  capital_injection: "Aporte de Capital",
  capital_return: "Devolucion de Capital",
  commission_payment: "Pago de Comision",
};

export default function MovementCreatePage() {
  const navigate = useNavigate();
  const [type, setType] = useState<MovementType>("payment_to_supplier");
  const create = useCreateMovement(type);

  const { data: suppliersData } = useSuppliers();
  const { data: customersData } = useCustomers();
  const { data: investorsData } = useInvestors();
  const { data: thirdPartiesData } = useThirdParties();
  const { data: accountsData } = useMoneyAccounts();
  const { data: expCategoriesData } = useExpenseCategories();

  const suppliers = suppliersData?.items ?? [];
  const customers = customersData?.items ?? [];
  const investors = investorsData?.items ?? [];
  const thirdParties = thirdPartiesData?.items ?? [];
  const accounts = accountsData?.items ?? [];
  const expenseCategories = expCategoriesData?.items ?? [];

  const [amount, setAmount] = useState(0);
  const [accountId, setAccountId] = useState("");
  const [thirdPartyId, setThirdPartyId] = useState("");
  const [expCategoryId, setExpCategoryId] = useState("");
  const [destAccountId, setDestAccountId] = useState("");
  const [description, setDescription] = useState("");
  const [date, setDate] = useState(new Date().toISOString().slice(0, 16));
  const [referenceNumber, setReferenceNumber] = useState("");
  const [notes, setNotes] = useState("");

  const resetFields = () => {
    setAmount(0);
    setAccountId("");
    setThirdPartyId("");
    setExpCategoryId("");
    setDestAccountId("");
    setDescription("");
    setReferenceNumber("");
    setNotes("");
  };

  const handleTypeChange = (v: string) => {
    setType(v as MovementType);
    resetFields();
  };

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
    }
  };

  const handleSubmit = () => {
    const payload = buildPayload();
    create.mutate(payload, {
      onSuccess: () => navigate(ROUTES.TREASURY),
    });
  };

  const getThirdPartyOptions = () => {
    switch (type) {
      case "payment_to_supplier": return suppliers.map((s) => ({ id: s.id, label: s.name }));
      case "collection_from_client": return customers.map((c) => ({ id: c.id, label: c.name }));
      case "capital_injection":
      case "capital_return": return investors.map((i) => ({ id: i.id, label: i.name }));
      case "commission_payment": return thirdParties.map((t) => ({ id: t.id, label: t.name }));
      default: return thirdParties.map((t) => ({ id: t.id, label: t.name }));
    }
  };

  const getThirdPartyLabel = () => {
    switch (type) {
      case "payment_to_supplier": return "Proveedor *";
      case "collection_from_client": return "Cliente *";
      case "capital_injection":
      case "capital_return": return "Inversionista *";
      case "commission_payment": return "Comisionista *";
      default: return "Tercero";
    }
  };

  const needsThirdParty = ["payment_to_supplier", "collection_from_client", "capital_injection", "capital_return", "commission_payment"].includes(type);
  const needsExpenseCategory = type === "expense";
  const needsDestAccount = type === "transfer";
  const needsDescription = ["expense", "service_income", "transfer"].includes(type);

  return (
    <div className="space-y-6">
      <PageHeader title="Nuevo Movimiento" description="Registrar un movimiento de tesoreria">
        <Button variant="outline" onClick={() => navigate(ROUTES.TREASURY)}>
          <ArrowLeft className="h-4 w-4 mr-2" />Volver
        </Button>
      </PageHeader>

      {/* Tipo de movimiento */}
      <Card>
        <CardHeader><CardTitle className="text-base">Tipo de Movimiento</CardTitle></CardHeader>
        <CardContent>
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
        </CardContent>
      </Card>

      {/* Formulario dinamico */}
      <Card>
        <CardHeader><CardTitle className="text-base">{typeLabels[type]}</CardTitle></CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <Label>Monto *</Label>
              <Input type="number" min={0} step="1" value={amount || ""} onChange={(e) => setAmount(parseFloat(e.target.value) || 0)} placeholder="0" />
            </div>
            <div>
              <Label>Fecha *</Label>
              <Input type="datetime-local" value={date} onChange={(e) => setDate(e.target.value)} />
            </div>

            {needsThirdParty && (
              <div>
                <Label>{getThirdPartyLabel()}</Label>
                <EntitySelect value={thirdPartyId} onChange={setThirdPartyId} options={getThirdPartyOptions()} placeholder="Seleccionar..." />
              </div>
            )}

            {needsExpenseCategory && (
              <div>
                <Label>Categoria de Gasto *</Label>
                <EntitySelect value={expCategoryId} onChange={setExpCategoryId} options={expenseCategories.map((c) => ({ id: c.id, label: c.name }))} placeholder="Seleccionar categoria..." />
              </div>
            )}

            {!needsDestAccount && (
              <div>
                <Label>Cuenta *</Label>
                <EntitySelect value={accountId} onChange={setAccountId} options={accounts.map((a) => ({ id: a.id, label: `${a.name} (${formatCurrency(a.current_balance)})` }))} placeholder="Seleccionar cuenta..." />
              </div>
            )}

            {needsDestAccount && (
              <>
                <div>
                  <Label>Cuenta Origen *</Label>
                  <EntitySelect value={accountId} onChange={setAccountId} options={accounts.map((a) => ({ id: a.id, label: `${a.name} (${formatCurrency(a.current_balance)})` }))} placeholder="Cuenta origen..." />
                </div>
                <div>
                  <Label>Cuenta Destino *</Label>
                  <EntitySelect value={destAccountId} onChange={setDestAccountId} options={accounts.filter((a) => a.id !== accountId).map((a) => ({ id: a.id, label: `${a.name} (${formatCurrency(a.current_balance)})` }))} placeholder="Cuenta destino..." />
                </div>
              </>
            )}

            {needsDescription && (
              <div className="md:col-span-2">
                <Label>Descripcion *</Label>
                <Input value={description} onChange={(e) => setDescription(e.target.value)} placeholder="Descripcion del movimiento" />
              </div>
            )}

            {!needsDescription && type !== "expense" && (
              <div className="md:col-span-2">
                <Label>Descripcion</Label>
                <Input value={description} onChange={(e) => setDescription(e.target.value)} placeholder="Descripcion (opcional)" />
              </div>
            )}

            <div>
              <Label>Referencia</Label>
              <Input value={referenceNumber} onChange={(e) => setReferenceNumber(e.target.value)} placeholder="Numero de referencia" />
            </div>
            <div>
              <Label>Notas</Label>
              <Textarea value={notes} onChange={(e) => setNotes(e.target.value)} rows={2} placeholder="Notas adicionales..." />
            </div>
          </div>
        </CardContent>
      </Card>

      <div className="flex justify-end gap-2">
        <Button variant="outline" onClick={() => navigate(ROUTES.TREASURY)}>Cancelar</Button>
        <Button onClick={handleSubmit} disabled={create.isPending || amount <= 0} className="bg-green-600 hover:bg-green-700">
          {create.isPending ? "Creando..." : "Crear Movimiento"}
        </Button>
      </div>
    </div>
  );
}
