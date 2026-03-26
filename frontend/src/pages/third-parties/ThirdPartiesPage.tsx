import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { type ColumnDef } from "@tanstack/react-table";
import { Plus, FileText, Power, PowerOff } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Checkbox } from "@/components/ui/checkbox";
import { PageHeader } from "@/components/shared/PageHeader";
import { DataTable } from "@/components/shared/DataTable";
import { SearchInput } from "@/components/shared/SearchInput";
import { MoneyDisplay } from "@/components/shared/MoneyDisplay";
import { ConfirmDialog } from "@/components/shared/ConfirmDialog";
import { useThirdParties } from "@/hooks/useMasterData";
import { useDeactivateThirdParty, useReactivateThirdParty } from "@/hooks/useCrudData";
import ThirdPartyFormDialog from "./ThirdPartyFormDialog";
import type { ThirdPartyResponse } from "@/types/third-party";
import { ROUTES } from "@/utils/constants";
import { usePermissions } from "@/hooks/usePermissions";

const PAGE_SIZE = 20;

const BEHAVIOR_COLORS: Record<string, string> = {
  material_supplier: "bg-blue-50 text-blue-700",
  service_provider: "bg-rose-50 text-rose-700",
  customer: "bg-emerald-50 text-emerald-700",
  investor: "bg-purple-50 text-purple-700",
  generic: "bg-slate-50 text-slate-700",
  provision: "bg-orange-50 text-orange-700",
  liability: "bg-amber-50 text-amber-700",
};

function CategoryBadges({ tp }: { tp: ThirdPartyResponse }) {
  return (
    <div className="flex gap-1 flex-wrap">
      {(tp.categories ?? []).map((cat) => (
        <Badge key={cat.id} variant="outline" className={`${BEHAVIOR_COLORS[cat.behavior_type] ?? ""} text-xs`}>
          {cat.display_name}
        </Badge>
      ))}
    </div>
  );
}

function getColumns(
  navigate: ReturnType<typeof useNavigate>,
  canViewBalance: boolean,
  canDelete: boolean,
  onDeactivate: (tp: ThirdPartyResponse) => void,
  onReactivate: (tp: ThirdPartyResponse) => void,
): ColumnDef<ThirdPartyResponse, unknown>[] {
  const cols: ColumnDef<ThirdPartyResponse, unknown>[] = [
    {
      accessorKey: "name",
      header: "Nombre",
      enableSorting: true,
      cell: ({ row }) => (
        <div className="flex items-center gap-2">
          <span className={`font-medium ${!row.original.is_active ? "opacity-50" : ""}`}>{row.original.name}</span>
          {!row.original.is_active && <Badge variant="secondary" className="text-xs">Inactivo</Badge>}
        </div>
      ),
    },
    { accessorKey: "identification_number", header: "Identificacion", cell: ({ row }) => <span className={!row.original.is_active ? "opacity-50" : ""}>{row.original.identification_number ?? "-"}</span> },
    { accessorKey: "categories", header: "Categorias", cell: ({ row }) => <div className={!row.original.is_active ? "opacity-50" : ""}><CategoryBadges tp={row.original} /></div> },
    { accessorKey: "phone", header: "Telefono", cell: ({ row }) => <span className={!row.original.is_active ? "opacity-50" : ""}>{row.original.phone ?? "-"}</span> },
  ];
  if (canViewBalance) {
    cols.push(
      { accessorKey: "current_balance", header: "Saldo", enableSorting: true, cell: ({ row }) => <span className={!row.original.is_active ? "opacity-50" : ""}><MoneyDisplay amount={row.original.current_balance} /></span> },
    );
  }
  cols.push({
    id: "actions",
    header: "",
    cell: ({ row }) => {
      const tp = row.original;
      return (
        <div className="flex justify-end gap-1">
          {canViewBalance && (
            <Button
              size="sm"
              variant="outline"
              onClick={(e) => { e.stopPropagation(); navigate(`${ROUTES.TREASURY_ACCOUNT_STATEMENT}?third_party_id=${tp.id}`); }}
            >
              <FileText className="h-3 w-3 mr-1" />Estado de Cuenta
            </Button>
          )}
          {canDelete && tp.is_active && (
            <Button
              size="sm"
              variant="outline"
              className="text-red-600 hover:text-red-700 hover:bg-red-50"
              onClick={(e) => { e.stopPropagation(); onDeactivate(tp); }}
            >
              <PowerOff className="h-3 w-3 mr-1" />Desactivar
            </Button>
          )}
          {canDelete && !tp.is_active && (
            <Button
              size="sm"
              variant="outline"
              className="text-emerald-600 hover:text-emerald-700 hover:bg-emerald-50"
              onClick={(e) => { e.stopPropagation(); onReactivate(tp); }}
            >
              <Power className="h-3 w-3 mr-1" />Reactivar
            </Button>
          )}
        </div>
      );
    },
  });
  return cols;
}

export default function ThirdPartiesPage() {
  const navigate = useNavigate();
  const { hasPermission } = usePermissions();
  const [page, setPage] = useState(0);
  const [roleFilter, setRoleFilter] = useState("all");
  const [search, setSearch] = useState("");
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editItem, setEditItem] = useState<ThirdPartyResponse | null>(null);
  const [showInactive, setShowInactive] = useState(false);
  const [deactivateTarget, setDeactivateTarget] = useState<ThirdPartyResponse | null>(null);
  const [reactivateTarget, setReactivateTarget] = useState<ThirdPartyResponse | null>(null);
  const canViewBalance = hasPermission("third_parties.view_balance");
  const canDelete = hasPermission("third_parties.delete");
  const deactivateMutation = useDeactivateThirdParty();
  const reactivateMutation = useReactivateThirdParty();

  const columns = getColumns(navigate, canViewBalance, canDelete, setDeactivateTarget, setReactivateTarget);

  const { data, isLoading } = useThirdParties({
    search: search || undefined,
    role: roleFilter === "all" ? undefined : roleFilter,
    is_active: showInactive ? undefined : true,
  });

  const pageCount = data ? Math.ceil(data.total / PAGE_SIZE) : 1;

  return (
    <div className="space-y-4">
      <PageHeader title="Terceros" description="Proveedores, clientes, inversionistas y mas">
        {hasPermission("third_parties.create") && (
          <Button onClick={() => { setEditItem(null); setDialogOpen(true); }} className="bg-emerald-600 hover:bg-emerald-700">
            <Plus className="h-4 w-4 mr-2" />Nuevo Tercero
          </Button>
        )}
      </PageHeader>

      <Tabs value={roleFilter} onValueChange={(v) => { setRoleFilter(v); setPage(0); }}>
        <TabsList>
          <TabsTrigger value="all">Todos</TabsTrigger>
          <TabsTrigger value="supplier">Proveedores</TabsTrigger>
          <TabsTrigger value="service_provider">Servicios</TabsTrigger>
          <TabsTrigger value="customer">Clientes</TabsTrigger>
          <TabsTrigger value="investor">Inversionistas</TabsTrigger>
          <TabsTrigger value="liability">Pasivos</TabsTrigger>
          <TabsTrigger value="provision">Provisiones</TabsTrigger>
          <TabsTrigger value="generic">Genericos</TabsTrigger>
        </TabsList>
      </Tabs>

      <DataTable
        columns={columns}
        data={data?.items ?? []}
        loading={isLoading}
        pageCount={pageCount}
        pageIndex={page}
        pageSize={PAGE_SIZE}
        totalItems={data?.total}
        onPageChange={setPage}
        onRowClick={(row) => { setEditItem(row); setDialogOpen(true); }}
        emptyTitle="Sin terceros"
        emptyDescription="No se encontraron terceros."
        exportFilename="ecobalance_terceros"
        toolbar={
          <div className="flex items-center gap-4">
            <SearchInput value={search} onChange={setSearch} placeholder="Buscar tercero..." />
            <div className="flex items-center gap-2">
              <Checkbox
                id="show-inactive"
                checked={showInactive}
                onCheckedChange={(checked) => setShowInactive(checked === true)}
              />
              <label htmlFor="show-inactive" className="text-sm text-slate-600 cursor-pointer whitespace-nowrap">
                Mostrar inactivos
              </label>
            </div>
          </div>
        }
      />

      <ThirdPartyFormDialog open={dialogOpen} onOpenChange={setDialogOpen} editItem={editItem} />

      <ConfirmDialog
        open={!!deactivateTarget}
        onOpenChange={(open) => { if (!open) setDeactivateTarget(null); }}
        title="Desactivar tercero"
        description={`¿Desactivar "${deactivateTarget?.name}"? No aparecerá en selectores.`}
        confirmLabel="Desactivar"
        variant="destructive"
        loading={deactivateMutation.isPending}
        onConfirm={() => {
          if (deactivateTarget) {
            deactivateMutation.mutate(deactivateTarget.id, {
              onSuccess: () => setDeactivateTarget(null),
            });
          }
        }}
      />

      <ConfirmDialog
        open={!!reactivateTarget}
        onOpenChange={(open) => { if (!open) setReactivateTarget(null); }}
        title="Reactivar tercero"
        description={`¿Reactivar "${reactivateTarget?.name}"?`}
        confirmLabel="Reactivar"
        variant="default"
        loading={reactivateMutation.isPending}
        onConfirm={() => {
          if (reactivateTarget) {
            reactivateMutation.mutate(reactivateTarget.id, {
              onSuccess: () => setReactivateTarget(null),
            });
          }
        }}
      />
    </div>
  );
}
