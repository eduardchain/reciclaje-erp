import { useMemo, useState } from "react";
import { useNavigate, useSearchParams, useLocation } from "react-router-dom";

import { type ColumnDef, type SortingState } from "@tanstack/react-table";
import { Plus, FileText, Power, PowerOff } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Checkbox } from "@/components/ui/checkbox";
import { PageHeader } from "@/components/shared/PageHeader";
import { DataTable } from "@/components/shared/DataTable";
import { SearchInput } from "@/components/shared/SearchInput";
import { ResponsiveFilterBar } from "@/components/shared/ResponsiveFilterBar";
import { MoneyDisplay } from "@/components/shared/MoneyDisplay";
import { ConfirmDialog } from "@/components/shared/ConfirmDialog";
import { useThirdParties } from "@/hooks/useMasterData";
import { useDeactivateThirdParty, useReactivateThirdParty } from "@/hooks/useCrudData";
import { thirdPartyService } from "@/services/thirdParties";
import { toast } from "sonner";
import ThirdPartyFormDialog from "./ThirdPartyFormDialog";
import type { ThirdPartyResponse } from "@/types/third-party";
import { ROUTES } from "@/utils/constants";
import { usePermissions } from "@/hooks/usePermissions";
import { useScrollRestoration, saveScroll } from "@/hooks/useScrollRestoration";

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
  currentUrl: string,
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
    { accessorKey: "identification_number", header: "Identificacion", meta: { hideOnMobile: true }, cell: ({ row }) => <span className={!row.original.is_active ? "opacity-50" : ""}>{row.original.identification_number ?? "-"}</span> },
    { accessorKey: "categories", header: "Categorias", meta: { hideOnMobile: true }, cell: ({ row }) => <div className={!row.original.is_active ? "opacity-50" : ""}><CategoryBadges tp={row.original} /></div> },
    { accessorKey: "phone", header: "Telefono", meta: { hideOnMobile: true }, cell: ({ row }) => <span className={!row.original.is_active ? "opacity-50" : ""}>{row.original.phone ?? "-"}</span> },
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
              onClick={(e) => { e.stopPropagation(); saveScroll(currentUrl); navigate(`${ROUTES.TREASURY_ACCOUNT_STATEMENT}?third_party_id=${tp.id}&returnTo=${encodeURIComponent(currentUrl)}`); }}
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
  const location = useLocation();
  const [searchParams, setSearchParams] = useSearchParams();
  const { hasPermission } = usePermissions();

  const roleFilter = searchParams.get("tab") || "all";
  const page = parseInt(searchParams.get("page") || "0", 10);
  const search = searchParams.get("search") || "";
  const showInactive = searchParams.get("inactive") === "1";
  const sortField = searchParams.get("sort") || "";
  const sortDesc = searchParams.get("dir") !== "asc";
  const sorting: SortingState = sortField ? [{ id: sortField, desc: sortDesc }] : [];

  const setParam = (updates: Record<string, string | null>) => {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      Object.entries(updates).forEach(([k, v]) => {
        if (v === null || v === "" || v === "0" || v === "all") next.delete(k);
        else next.set(k, v);
      });
      return next;
    }, { replace: true });
  };

  const onSortingChange = (next: SortingState) => {
    setParam({
      sort: next.length > 0 ? next[0].id : null,
      dir: next.length > 0 ? (next[0].desc ? null : "asc") : null,
    });
  };

  const [dialogOpen, setDialogOpen] = useState(false);
  const [editItem, setEditItem] = useState<ThirdPartyResponse | null>(null);
  const [deactivateTarget, setDeactivateTarget] = useState<ThirdPartyResponse | null>(null);
  const [reactivateTarget, setReactivateTarget] = useState<ThirdPartyResponse | null>(null);
  const canViewBalance = hasPermission("third_parties.view_balance");
  const canDelete = hasPermission("third_parties.delete");
  const deactivateMutation = useDeactivateThirdParty();
  const reactivateMutation = useReactivateThirdParty();

  const currentUrl = location.pathname + location.search;
  const columns = useMemo(
    () => getColumns(navigate, canViewBalance, canDelete, setDeactivateTarget, setReactivateTarget, currentUrl),
    [navigate, canViewBalance, canDelete, currentUrl],
  );

  const { data, isLoading } = useThirdParties({
    skip: page * PAGE_SIZE,
    limit: PAGE_SIZE,
    search: search || undefined,
    role: roleFilter === "all" ? undefined : roleFilter,
    is_active: showInactive ? undefined : true,
    sort_by: sortField || undefined,
    sort_dir: sortField ? (sortDesc ? "desc" : "asc") : undefined,
  });
  useScrollRestoration(!isLoading);

  const pageCount = data ? Math.ceil(data.total / PAGE_SIZE) : 1;

  const handleExportAll = async () => {
    const all = await thirdPartyService.getAll({
      skip: 0,
      limit: 5000,
      search: search || undefined,
      role: roleFilter === "all" ? undefined : roleFilter,
      is_active: showInactive ? undefined : true,
    });
    if (all.total > all.items.length) {
      toast.warning(`Excel limitado a ${all.items.length} filas. Hay ${all.total} en total — refina filtros para descargar todo.`);
    }
    return all.items;
  };

  return (
    <div className="space-y-4">
      <PageHeader title="Terceros" description="Proveedores, clientes, inversionistas y mas">
        {hasPermission("third_parties.create") && (
          <Button onClick={() => { setEditItem(null); setDialogOpen(true); }} className="bg-emerald-600 hover:bg-emerald-700">
            <Plus className="h-4 w-4 mr-2" />Nuevo Tercero
          </Button>
        )}
      </PageHeader>

      <Tabs value={roleFilter} onValueChange={(v) => setParam({ tab: v, page: null, search: null })}>
        <div className="overflow-x-auto -mx-3 px-3 sm:mx-0 sm:px-0">
          <TabsList className="inline-flex w-max sm:w-auto">
            <TabsTrigger value="all">Todos</TabsTrigger>
            <TabsTrigger value="supplier">Proveedores</TabsTrigger>
            <TabsTrigger value="service_provider">Servicios</TabsTrigger>
            <TabsTrigger value="customer">Clientes</TabsTrigger>
            <TabsTrigger value="investor">Inversionistas</TabsTrigger>
            <TabsTrigger value="liability">Pasivos</TabsTrigger>
            <TabsTrigger value="provision">Provisiones</TabsTrigger>
            <TabsTrigger value="generic">Genericos</TabsTrigger>
          </TabsList>
        </div>
      </Tabs>

      <DataTable
        columns={columns}
        data={data?.items ?? []}
        loading={isLoading}
        pageCount={pageCount}
        pageIndex={page}
        pageSize={PAGE_SIZE}
        totalItems={data?.total}
        onPageChange={(p) => setParam({ page: p === 0 ? null : String(p) })}
        onRowClick={(row) => { setEditItem(row); setDialogOpen(true); }}
        sorting={sorting}
        onSortingChange={onSortingChange}
        emptyTitle="Sin terceros"
        emptyDescription="No se encontraron terceros."
        exportFilename="ecobalance_terceros"
        onExportAll={handleExportAll}
        currencyColumns={["current_balance"]}
        toolbar={
          <ResponsiveFilterBar>
            <SearchInput value={search} onChange={(v) => setParam({ search: v, page: null })} placeholder="Buscar tercero..." />
            <div className="flex items-center gap-2">
              <Checkbox
                id="show-inactive"
                checked={showInactive}
                onCheckedChange={(checked) => setParam({ inactive: checked === true ? "1" : null, page: null })}
              />
              <label htmlFor="show-inactive" className="text-sm text-slate-600 cursor-pointer whitespace-nowrap">
                Mostrar inactivos
              </label>
            </div>
          </ResponsiveFilterBar>
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
