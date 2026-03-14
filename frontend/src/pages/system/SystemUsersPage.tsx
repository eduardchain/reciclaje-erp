import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { UserPlus, Shield, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Label } from "@/components/ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { PageHeader } from "@/components/shared/PageHeader";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useSystemOrganizations, useSystemUsers, useAddUserToOrg, useOrgRoles } from "@/hooks/useSystem";
import { formatDate } from "@/utils/formatters";
import type { SystemUserResponse } from "@/types/organization";

export default function SystemUsersPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const filterOrgId = searchParams.get("org") ?? "";
  const filterOrgName = searchParams.get("org_name") ?? "";

  const { data: users, isLoading } = useSystemUsers();
  const { data: orgs } = useSystemOrganizations();
  const addUserToOrg = useAddUserToOrg();

  // Agregar a org
  const [addTarget, setAddTarget] = useState<SystemUserResponse | null>(null);
  const [selectedOrgId, setSelectedOrgId] = useState("");
  const [selectedRoleId, setSelectedRoleId] = useState("");

  // Roles de la org seleccionada (se cargan cuando cambia selectedOrgId)
  const { data: orgRoles } = useOrgRoles(selectedOrgId);

  const handleAddToOrg = () => {
    if (!addTarget || !selectedOrgId || !selectedRoleId) return;
    addUserToOrg.mutate(
      {
        userId: addTarget.id,
        data: { organization_id: selectedOrgId, role_id: selectedRoleId },
      },
      {
        onSuccess: () => {
          setAddTarget(null);
          setSelectedOrgId("");
          setSelectedRoleId("");
        },
      },
    );
  };

  const openAddDialog = (user: SystemUserResponse) => {
    setAddTarget(user);
    setSelectedOrgId("");
    setSelectedRoleId("");
  };

  const handleOrgChange = (orgId: string) => {
    setSelectedOrgId(orgId);
    setSelectedRoleId(""); // Reset rol al cambiar org
  };

  const clearFilter = () => {
    setSearchParams({});
  };

  // Orgs en las que NO esta el usuario (para no agregar duplicados)
  const availableOrgs = addTarget
    ? (orgs ?? []).filter(
        (org) => org.is_active && !addTarget.memberships.some((m) => m.organization_id === org.id),
      )
    : [];

  // Filtrar usuarios por org si hay filtro activo
  const filteredUsers = filterOrgId
    ? users?.filter((u) => u.memberships.some((m) => m.organization_id === filterOrgId))
    : users;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Usuarios del Sistema"
        description={filterOrgId ? `Usuarios de "${filterOrgName}"` : "Todos los usuarios registrados y sus organizaciones"}
      />

      {filterOrgId && (
        <div className="flex items-center gap-2">
          <Badge variant="secondary" className="text-xs px-3 py-1">
            Org: {filterOrgName}
            <button onClick={clearFilter} className="ml-2 hover:text-red-600">
              <X className="h-3 w-3" />
            </button>
          </Badge>
        </div>
      )}

      {isLoading ? (
        <div className="space-y-2">
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} className="h-12 w-full rounded-lg" />
          ))}
        </div>
      ) : (
        <div className="rounded-lg border border-slate-200/80 overflow-hidden">
          <Table>
            <TableHeader>
              <TableRow className="bg-slate-50/80 border-b border-slate-200/80">
                <TableHead className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 h-10">Nombre</TableHead>
                <TableHead className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 h-10">Email</TableHead>
                <TableHead className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 h-10 text-center">Estado</TableHead>
                <TableHead className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 h-10 text-center">Super Admin</TableHead>
                <TableHead className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 h-10">Organizaciones</TableHead>
                <TableHead className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 h-10">Creado</TableHead>
                <TableHead className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 h-10 text-right">Acciones</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filteredUsers?.map((user) => (
                <TableRow key={user.id} className={!user.is_active ? "opacity-50" : ""}>
                  <TableCell className="font-medium">{user.full_name ?? "-"}</TableCell>
                  <TableCell className="text-slate-600">{user.email}</TableCell>
                  <TableCell className="text-center">
                    <Badge variant="secondary" className={user.is_active ? "bg-emerald-100 text-emerald-700" : "bg-red-100 text-red-700"}>
                      {user.is_active ? "Activo" : "Inactivo"}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-center">
                    {user.is_superuser && (
                      <Badge variant="secondary" className="bg-amber-100 text-amber-700">
                        <Shield className="h-3 w-3 mr-1" />
                        Super
                      </Badge>
                    )}
                  </TableCell>
                  <TableCell>
                    <div className="flex flex-wrap gap-1">
                      {user.memberships.length === 0 && (
                        <span className="text-xs text-slate-400">Sin organizacion</span>
                      )}
                      {user.memberships.map((m) => (
                        <Badge key={m.organization_id} variant="outline" className="text-[10px]">
                          {m.organization_name}
                          <span className="text-slate-400 ml-1">({m.role_display_name})</span>
                        </Badge>
                      ))}
                    </div>
                  </TableCell>
                  <TableCell className="text-sm text-slate-500">{formatDate(user.created_at)}</TableCell>
                  <TableCell className="text-right">
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-8 px-2 text-xs"
                      onClick={() => openAddDialog(user)}
                    >
                      <UserPlus className="h-3.5 w-3.5 mr-1" />
                      Agregar a Org
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
              {filteredUsers?.length === 0 && (
                <TableRow>
                  <TableCell colSpan={7} className="text-center text-slate-400 py-8">
                    No hay usuarios
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </div>
      )}

      {/* Dialog: Agregar a Organizacion */}
      <Dialog open={!!addTarget} onOpenChange={(open) => !open && setAddTarget(null)}>
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle>Agregar a Organizacion</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Usuario</Label>
              <p className="text-sm font-medium mt-1">{addTarget?.full_name ?? addTarget?.email}</p>
              <p className="text-xs text-slate-500">{addTarget?.email}</p>
            </div>
            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Organizacion</Label>
              <Select value={selectedOrgId} onValueChange={handleOrgChange}>
                <SelectTrigger className="mt-1">
                  <SelectValue placeholder="Seleccionar organizacion..." />
                </SelectTrigger>
                <SelectContent>
                  {availableOrgs.map((org) => (
                    <SelectItem key={org.id} value={org.id}>
                      {org.name}
                    </SelectItem>
                  ))}
                  {availableOrgs.length === 0 && (
                    <SelectItem value="_none" disabled>
                      Ya es miembro de todas las organizaciones
                    </SelectItem>
                  )}
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Rol</Label>
              <Select
                value={selectedRoleId}
                onValueChange={setSelectedRoleId}
                disabled={!selectedOrgId}
              >
                <SelectTrigger className="mt-1">
                  <SelectValue placeholder={selectedOrgId ? "Seleccionar rol..." : "Primero seleccione una organizacion"} />
                </SelectTrigger>
                <SelectContent>
                  {orgRoles?.map((role) => (
                    <SelectItem key={role.id} value={role.id}>
                      {role.display_name}
                      {role.is_system_role ? " (Sistema)" : ""}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setAddTarget(null)}>Cancelar</Button>
            <Button
              onClick={handleAddToOrg}
              disabled={!selectedOrgId || !selectedRoleId || addUserToOrg.isPending}
              className="bg-emerald-600 hover:bg-emerald-700"
            >
              {addUserToOrg.isPending ? "Agregando..." : "Agregar"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
