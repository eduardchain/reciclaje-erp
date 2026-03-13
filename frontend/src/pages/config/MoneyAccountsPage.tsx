import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { type ColumnDef } from "@tanstack/react-table";
import { Plus, FileText } from "lucide-react";
import { usePermissions } from "@/hooks/usePermissions";
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
import { MoneyInput } from "@/components/shared/MoneyInput";
import ConfigLayout from "./ConfigLayout";
import { ROUTES } from "@/utils/constants";
import type { MoneyAccountResponse, MoneyAccountType } from "@/types/money-account";

const typeLabels: Record<MoneyAccountType, string> = { cash: "Efectivo", bank: "Banco", digital: "Digital" };
const typeColors: Record<MoneyAccountType, string> = { cash: "bg-emerald-100 text-emerald-800", bank: "bg-blue-100 text-blue-800", digital: "bg-purple-100 text-purple-800" };

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const getColumns = (onViewMovements: (id: string) => void): ColumnDef<MoneyAccountResponse, unknown>[] => [
  { accessorKey: "name", header: "Nombre", cell: ({ row }) => <span className="font-medium">{row.original.name}</span> },
  { accessorKey: "account_type", header: "Tipo", cell: ({ row }) => <Badge variant="outline" className={typeColors[row.original.account_type]}>{typeLabels[row.original.account_type]}</Badge> },
  { accessorKey: "bank_name", header: "Banco", cell: ({ row }) => row.original.bank_name ?? "-" },
  { accessorKey: "account_number", header: "Numero", cell: ({ row }) => row.original.account_number ?? "-" },
  { accessorKey: "current_balance", header: "Saldo", enableSorting: true, cell: ({ row }) => <span className="font-medium">{formatCurrency(row.original.current_balance)}</span> },
  { id: "actions", header: "", cell: ({ row }) => (
    <Button size="sm" variant="outline" onClick={(e) => { e.stopPropagation(); onViewMovements(row.original.id); }}>
      <FileText className="h-3 w-3 mr-1" />Movimientos
    </Button>
  )},
];

export default function MoneyAccountsPage() {
  const navigate = useNavigate();
  const { hasPermission } = usePermissions();
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
        {hasPermission("treasury.manage_accounts") && (
          <Button onClick={() => openDialog(null)} className="bg-emerald-600 hover:bg-emerald-700"><Plus className="h-4 w-4 mr-2" />Nueva Cuenta</Button>
        )}
      </div>

      <DataTable columns={getColumns((id) => navigate(`${ROUTES.TREASURY_ACCOUNT_MOVEMENTS}?account_id=${id}`))} data={filteredItems} loading={isLoading} pageCount={1} pageIndex={0} pageSize={100} onPageChange={() => {}}
        onRowClick={hasPermission("treasury.manage_accounts") ? (row) => openDialog(row) : undefined} emptyTitle="Sin cuentas" emptyDescription="No hay cuentas de dinero." exportFilename="ecobalance_cuentas-dinero" />

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="max-w-sm">
          <DialogHeader><DialogTitle>{editItem ? "Editar Cuenta" : "Nueva Cuenta"}</DialogTitle></DialogHeader>
          <div className="space-y-4">
            <div><Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Nombre *</Label><Input value={name} onChange={(e) => setName(e.target.value)} /></div>
            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Tipo *</Label>
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
                <div><Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Banco</Label><Input value={bankName} onChange={(e) => setBankName(e.target.value)} /></div>
                <div><Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Numero de Cuenta</Label><Input value={accountNumber} onChange={(e) => setAccountNumber(e.target.value)} /></div>
              </>
            )}
            {!editItem && <div><Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Saldo Inicial</Label><MoneyInput value={initialBalance} onChange={setInitialBalance} /></div>}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogOpen(false)}>Cancelar</Button>
            <Button onClick={handleSubmit} disabled={!name || create.isPending || update.isPending} className="bg-emerald-600 hover:bg-emerald-700">
              {create.isPending || update.isPending ? "Guardando..." : editItem ? "Actualizar" : "Crear"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </ConfigLayout>
  );
}
