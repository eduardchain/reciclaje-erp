import { useState } from "react";
import { type ColumnDef } from "@tanstack/react-table";
import { Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { PageHeader } from "@/components/shared/PageHeader";
import { DataTable } from "@/components/shared/DataTable";
import { SearchInput } from "@/components/shared/SearchInput";
import { MoneyDisplay } from "@/components/shared/MoneyDisplay";
import { useThirdParties } from "@/hooks/useMasterData";
import ThirdPartyFormDialog from "./ThirdPartyFormDialog";
import type { ThirdPartyResponse } from "@/types/third-party";

const PAGE_SIZE = 20;

function RoleBadges({ tp }: { tp: ThirdPartyResponse }) {
  return (
    <div className="flex gap-1 flex-wrap">
      {tp.is_supplier && <Badge variant="outline" className="bg-blue-50 text-blue-700 text-xs">Proveedor</Badge>}
      {tp.is_customer && <Badge variant="outline" className="bg-green-50 text-green-700 text-xs">Cliente</Badge>}
      {tp.is_investor && <Badge variant="outline" className="bg-purple-50 text-purple-700 text-xs">Inversionista</Badge>}
      {tp.is_provision && <Badge variant="outline" className="bg-orange-50 text-orange-700 text-xs">Provision</Badge>}
    </div>
  );
}

const columns: ColumnDef<ThirdPartyResponse, unknown>[] = [
  { accessorKey: "name", header: "Nombre", cell: ({ row }) => <span className="font-medium">{row.original.name}</span> },
  { accessorKey: "identification_number", header: "Identificacion", cell: ({ row }) => row.original.identification_number ?? "-" },
  { accessorKey: "roles", header: "Roles", cell: ({ row }) => <RoleBadges tp={row.original} /> },
  { accessorKey: "phone", header: "Telefono", cell: ({ row }) => row.original.phone ?? "-" },
  { accessorKey: "current_balance", header: "Saldo", cell: ({ row }) => <MoneyDisplay amount={row.original.current_balance} /> },
];

export default function ThirdPartiesPage() {
  const [page, setPage] = useState(0);
  const [roleFilter, setRoleFilter] = useState("all");
  const [search, setSearch] = useState("");
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editItem, setEditItem] = useState<ThirdPartyResponse | null>(null);

  const { data, isLoading } = useThirdParties({
    search: search || undefined,
    role: roleFilter === "all" ? undefined : roleFilter,
  });

  const pageCount = data ? Math.ceil(data.total / PAGE_SIZE) : 1;

  return (
    <div className="space-y-4">
      <PageHeader title="Terceros" description="Proveedores, clientes e inversionistas">
        <Button onClick={() => { setEditItem(null); setDialogOpen(true); }} className="bg-green-600 hover:bg-green-700">
          <Plus className="h-4 w-4 mr-2" />Nuevo Tercero
        </Button>
      </PageHeader>

      <div className="flex flex-col sm:flex-row items-start sm:items-center gap-4">
        <Tabs value={roleFilter} onValueChange={(v) => { setRoleFilter(v); setPage(0); }}>
          <TabsList>
            <TabsTrigger value="all">Todos</TabsTrigger>
            <TabsTrigger value="supplier">Proveedores</TabsTrigger>
            <TabsTrigger value="customer">Clientes</TabsTrigger>
            <TabsTrigger value="investor">Inversionistas</TabsTrigger>
          </TabsList>
        </Tabs>
        <div className="ml-auto w-64">
          <SearchInput value={search} onChange={setSearch} placeholder="Buscar tercero..." />
        </div>
      </div>

      <DataTable
        columns={columns}
        data={data?.items ?? []}
        loading={isLoading}
        pageCount={pageCount}
        pageIndex={page}
        pageSize={PAGE_SIZE}
        onPageChange={setPage}
        onRowClick={(row) => { setEditItem(row); setDialogOpen(true); }}
        emptyTitle="Sin terceros"
        emptyDescription="No se encontraron terceros."
      />

      <ThirdPartyFormDialog open={dialogOpen} onOpenChange={setDialogOpen} editItem={editItem} />
    </div>
  );
}
