import { useState } from "react";
import { type ColumnDef } from "@tanstack/react-table";
import { Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { DataTable } from "@/components/shared/DataTable";
import { useMoneyAccounts } from "@/hooks/useMasterData";
import { useCreateMoneyAccount, useUpdateMoneyAccount } from "@/hooks/useCrudData";
import { formatCurrency } from "@/utils/formatters";
import ConfigLayout from "./ConfigLayout";
import type { MoneyAccountResponse, MoneyAccountType } from "@/types/money-account";

const typeLabels: Record<MoneyAccountType, string> = { cash: "Efectivo", bank: "Banco", digital: "Digital" };
const typeColors: Record<MoneyAccountType, string> = { cash: "bg-green-100 text-green-800", bank: "bg-blue-100 text-blue-800", digital: "bg-purple-100 text-purple-800" };

const columns: ColumnDef<MoneyAccountResponse, unknown>[] = [
  { accessorKey: "name", header: "Nombre", cell: ({ row }) => <span className="font-medium">{row.original.name}</span> },
  { accessorKey: "account_type", header: "Tipo", cell: ({ row }) => <Badge variant="outline" className={typeColors[row.original.account_type]}>{typeLabels[row.original.account_type]}</Badge> },
  { accessorKey: "bank_name", header: "Banco", cell: ({ row }) => row.original.bank_name ?? "-" },
  { accessorKey: "account_number", header: "Numero", cell: ({ row }) => row.original.account_number ?? "-" },
  { accessorKey: "current_balance", header: "Saldo", cell: ({ row }) => <span className="font-medium">{formatCurrency(row.original.current_balance)}</span> },
];

export default function MoneyAccountsPage() {
  const { data, isLoading } = useMoneyAccounts();
  const create = useCreateMoneyAccount();
  const update = useUpdateMoneyAccount();

  const [typeFilter, setTypeFilter] = useState("all");
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editItem, setEditItem] = useState<MoneyAccountResponse | null>(null);
  const [name, setName] = useState("");
  const [accountType, setAccountType] = useState<MoneyAccountType>("cash");
  const [bankName, setBankName] = useState("");
  const [accountNumber, setAccountNumber] = useState("");
  const [initialBalance, setInitialBalance] = useState(0);

  const filteredItems = (data?.items ?? []).filter((a) => typeFilter === "all" || a.account_type === typeFilter);

  const openDialog = (item: MoneyAccountResponse | null) => {
    setEditItem(item);
    setName(item?.name ?? ""); setAccountType(item?.account_type ?? "cash");
    setBankName(item?.bank_name ?? ""); setAccountNumber(item?.account_number ?? "");
    setInitialBalance(0);
    setDialogOpen(true);
  };

  const handleSubmit = () => {
    const opts = { onSuccess: () => setDialogOpen(false) };
    if (editItem) {
      update.mutate({ id: editItem.id, data: { name, account_type: accountType, bank_name: bankName || null, account_number: accountNumber || null } }, opts);
    } else {
      create.mutate({ name, account_type: accountType, bank_name: bankName || null, account_number: accountNumber || null, initial_balance: initialBalance }, opts);
    }
  };

  return (
    <ConfigLayout>
      <div className="flex justify-between items-center">
        <Tabs value={typeFilter} onValueChange={setTypeFilter}>
          <TabsList>
            <TabsTrigger value="all">Todas</TabsTrigger>
            <TabsTrigger value="cash">Efectivo</TabsTrigger>
            <TabsTrigger value="bank">Banco</TabsTrigger>
            <TabsTrigger value="digital">Digital</TabsTrigger>
          </TabsList>
        </Tabs>
        <Button onClick={() => openDialog(null)} className="bg-green-600 hover:bg-green-700"><Plus className="h-4 w-4 mr-2" />Nueva Cuenta</Button>
      </div>

      <DataTable columns={columns} data={filteredItems} loading={isLoading} pageCount={1} pageIndex={0} pageSize={100} onPageChange={() => {}}
        onRowClick={(row) => openDialog(row)} emptyTitle="Sin cuentas" emptyDescription="No hay cuentas de dinero." />

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="max-w-sm">
          <DialogHeader><DialogTitle>{editItem ? "Editar Cuenta" : "Nueva Cuenta"}</DialogTitle></DialogHeader>
          <div className="space-y-4">
            <div><Label>Nombre *</Label><Input value={name} onChange={(e) => setName(e.target.value)} /></div>
            <div>
              <Label>Tipo *</Label>
              <Select value={accountType} onValueChange={(v) => setAccountType(v as MoneyAccountType)}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="cash">Efectivo</SelectItem>
                  <SelectItem value="bank">Banco</SelectItem>
                  <SelectItem value="digital">Digital</SelectItem>
                </SelectContent>
              </Select>
            </div>
            {accountType !== "cash" && (
              <>
                <div><Label>Banco</Label><Input value={bankName} onChange={(e) => setBankName(e.target.value)} /></div>
                <div><Label>Numero de Cuenta</Label><Input value={accountNumber} onChange={(e) => setAccountNumber(e.target.value)} /></div>
              </>
            )}
            {!editItem && <div><Label>Saldo Inicial</Label><Input type="number" value={initialBalance || ""} onChange={(e) => setInitialBalance(parseFloat(e.target.value) || 0)} /></div>}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogOpen(false)}>Cancelar</Button>
            <Button onClick={handleSubmit} disabled={!name || create.isPending || update.isPending} className="bg-green-600 hover:bg-green-700">
              {create.isPending || update.isPending ? "Guardando..." : editItem ? "Actualizar" : "Crear"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </ConfigLayout>
  );
}
