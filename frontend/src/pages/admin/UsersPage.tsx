import { useState } from "react";
import { UserCog, UserPlus, MoreHorizontal, KeyRound, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { PageHeader } from "@/components/shared/PageHeader";
import { ConfirmDialog } from "@/components/shared/ConfirmDialog";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  useOrgMembers,
  useRoles,
  useUpdateMemberRole,
  useUpdateAccountAssignments,
  useCreateUser,
  useResetPassword,
  useDeleteMember,
} from "@/hooks/useRoles";
import { useMoneyAccounts } from "@/hooks/useMasterData";
import { useAuthStore } from "@/stores/authStore";
import { formatDate } from "@/utils/formatters";
import type { OrgMemberResponse } from "@/types/role";

const roleBadgeColors: Record<string, string> = {
  admin: "bg-purple-100 text-purple-700",
  liquidador: "bg-emerald-100 text-emerald-700",
  bascula: "bg-sky-100 text-sky-700",
  planillador: "bg-amber-100 text-amber-700",
  viewer: "bg-slate-100 text-slate-600",
};

export default function UsersPage() {
  const { data: members, isLoading } = useOrgMembers();
  const { data: roles } = useRoles();
  const { data: accountsData } = useMoneyAccounts();
  const updateMemberRole = useUpdateMemberRole();
  const updateAccountAssignments = useUpdateAccountAssignments();
  const createUser = useCreateUser();
  const resetPassword = useResetPassword();
  const deleteMember = useDeleteMember();
  const currentUserId = useAuthStore((s) => s.user?.id);

  const accounts = accountsData?.items ?? [];

  // Estado: Dialog Configurar Usuario
  const [editMember, setEditMember] = useState<OrgMemberResponse | null>(null);
  const [selectedRoleId, setSelectedRoleId] = useState("");
  const [selectedAccountIds, setSelectedAccountIds] = useState<string[]>([]);

  // Estado: Dialog Nuevo Usuario
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const [newEmail, setNewEmail] = useState("");
  const [newFullName, setNewFullName] = useState("");
  const [newRoleId, setNewRoleId] = useState("");

  // Estado: Confirmar Resetear Contraseña
  const [resetTarget, setResetTarget] = useState<OrgMemberResponse | null>(null);

  // Estado: Confirmar Eliminar
  const [deleteTarget, setDeleteTarget] = useState<OrgMemberResponse | null>(null);

  const openEdit = (member: OrgMemberResponse) => {
    setEditMember(member);
    setSelectedRoleId(member.role_id);
    setSelectedAccountIds(member.account_ids ?? []);
  };

  const toggleAccount = (accountId: string) => {
    setSelectedAccountIds((prev) =>
      prev.includes(accountId) ? prev.filter((id) => id !== accountId) : [...prev, accountId],
    );
  };

  const handleSave = () => {
    if (!editMember) return;

    const roleChanged = selectedRoleId !== editMember.role_id;
    const originalAccIds = editMember.account_ids ?? [];
    const accountsChanged =
      selectedAccountIds.length !== originalAccIds.length ||
      selectedAccountIds.some((id) => !originalAccIds.includes(id));

    let pending = 0;
    const done = () => { pending--; if (pending <= 0) setEditMember(null); };

    if (roleChanged) {
      pending++;
      updateMemberRole.mutate(
        { userId: editMember.user_id, roleId: selectedRoleId },
        { onSuccess: done },
      );
    }
    if (accountsChanged) {
      pending++;
      updateAccountAssignments.mutate(
        { userId: editMember.user_id, accountIds: selectedAccountIds },
        { onSuccess: done },
      );
    }
    if (!roleChanged && !accountsChanged) {
      setEditMember(null);
    }
  };

  const handleCreateUser = () => {
    if (!newEmail || !newFullName || !newRoleId) return;
    createUser.mutate(
      { email: newEmail, full_name: newFullName, role_id: newRoleId },
      {
        onSuccess: () => {
          setShowCreateDialog(false);
          setNewEmail("");
          setNewFullName("");
          setNewRoleId("");
        },
      },
    );
  };

  const handleResetPassword = () => {
    if (!resetTarget) return;
    resetPassword.mutate(resetTarget.user_id, {
      onSuccess: () => setResetTarget(null),
    });
  };

  const handleDelete = () => {
    if (!deleteTarget) return;
    deleteMember.mutate(deleteTarget.user_id, {
      onSuccess: () => setDeleteTarget(null),
    });
  };

  return (
    <div className="space-y-6">
      <PageHeader title="Usuarios" description="Miembros de la organizacion y sus roles">
        <Button onClick={() => setShowCreateDialog(true)} className="bg-emerald-600 hover:bg-emerald-700">
          <UserPlus className="h-4 w-4 mr-1.5" />
          Nuevo Usuario
        </Button>
      </PageHeader>

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
                <TableHead className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 h-10">Rol</TableHead>
                <TableHead className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 h-10">Desde</TableHead>
                <TableHead className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 h-10 text-right">Acciones</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {members?.map((member) => (
                <TableRow key={member.id}>
                  <TableCell className="font-medium">{member.user_full_name ?? "-"}</TableCell>
                  <TableCell className="text-slate-600">{member.user_email ?? "-"}</TableCell>
                  <TableCell>
                    <Badge
                      variant="secondary"
                      className={roleBadgeColors[member.role_name ?? ""] ?? "bg-slate-100 text-slate-600"}
                    >
                      {member.role_display_name ?? member.role_name ?? "-"}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-sm text-slate-500">{formatDate(member.joined_at)}</TableCell>
                  <TableCell className="text-right">
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button variant="ghost" size="sm" className="h-8 w-8 p-0">
                          <MoreHorizontal className="h-4 w-4" />
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end">
                        <DropdownMenuItem onClick={() => openEdit(member)}>
                          <UserCog className="h-4 w-4 mr-2" />
                          Configurar Usuario
                        </DropdownMenuItem>
                        <DropdownMenuItem onClick={() => setResetTarget(member)}>
                          <KeyRound className="h-4 w-4 mr-2" />
                          Resetear Contraseña
                        </DropdownMenuItem>
                        {member.user_id !== currentUserId && (
                          <DropdownMenuItem
                            onClick={() => setDeleteTarget(member)}
                            className="text-red-600 focus:text-red-600"
                          >
                            <Trash2 className="h-4 w-4 mr-2" />
                            Eliminar
                          </DropdownMenuItem>
                        )}
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      {/* Dialog: Configurar Usuario (Rol + Cuentas) */}
      <Dialog open={!!editMember} onOpenChange={(open) => !open && setEditMember(null)}>
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle>Configurar Usuario</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Usuario</Label>
              <p className="text-sm font-medium mt-1">{editMember?.user_full_name}</p>
              <p className="text-xs text-slate-500">{editMember?.user_email}</p>
            </div>
            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Rol</Label>
              <Select value={selectedRoleId} onValueChange={setSelectedRoleId}>
                <SelectTrigger>
                  <SelectValue placeholder="Seleccionar rol..." />
                </SelectTrigger>
                <SelectContent>
                  {roles?.map((role) => (
                    <SelectItem key={role.id} value={role.id}>
                      {role.display_name}
                      {role.is_system_role ? " (Sistema)" : ""}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Cuentas Visibles</Label>
              <p className="text-xs text-slate-400 mt-0.5 mb-2">Dejar vacio para ver todas las cuentas</p>
              <div className="space-y-1.5 max-h-40 overflow-y-auto border rounded-md p-2">
                {accounts.map((acc) => (
                  <label key={acc.id} className="flex items-center gap-2 cursor-pointer hover:bg-slate-50 rounded px-1 py-0.5">
                    <Checkbox
                      checked={selectedAccountIds.includes(acc.id)}
                      onCheckedChange={() => toggleAccount(acc.id)}
                    />
                    <span className="text-sm">{acc.name}</span>
                  </label>
                ))}
                {accounts.length === 0 && (
                  <p className="text-xs text-slate-400 text-center py-2">No hay cuentas</p>
                )}
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setEditMember(null)}>Cancelar</Button>
            <Button
              onClick={handleSave}
              disabled={updateMemberRole.isPending || updateAccountAssignments.isPending}
              className="bg-emerald-600 hover:bg-emerald-700"
            >
              {(updateMemberRole.isPending || updateAccountAssignments.isPending) ? "Guardando..." : "Guardar"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Dialog: Nuevo Usuario */}
      <Dialog open={showCreateDialog} onOpenChange={setShowCreateDialog}>
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle>Nuevo Usuario</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Email</Label>
              <Input
                type="email"
                value={newEmail}
                onChange={(e) => setNewEmail(e.target.value)}
                placeholder="usuario@ejemplo.com"
                className="mt-1"
              />
            </div>
            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Nombre Completo</Label>
              <Input
                value={newFullName}
                onChange={(e) => setNewFullName(e.target.value)}
                placeholder="Nombre del usuario"
                className="mt-1"
              />
            </div>
            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Rol</Label>
              <Select value={newRoleId} onValueChange={setNewRoleId}>
                <SelectTrigger className="mt-1">
                  <SelectValue placeholder="Seleccionar rol..." />
                </SelectTrigger>
                <SelectContent>
                  {roles?.map((role) => (
                    <SelectItem key={role.id} value={role.id}>
                      {role.display_name}
                      {role.is_system_role ? " (Sistema)" : ""}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <p className="text-xs text-slate-400">La contraseña por defecto sera: <strong>123456</strong></p>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowCreateDialog(false)}>Cancelar</Button>
            <Button
              onClick={handleCreateUser}
              disabled={createUser.isPending || !newEmail || !newFullName || !newRoleId}
              className="bg-emerald-600 hover:bg-emerald-700"
            >
              {createUser.isPending ? "Creando..." : "Crear Usuario"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Confirm: Resetear Contraseña */}
      <ConfirmDialog
        open={!!resetTarget}
        onOpenChange={(open) => !open && setResetTarget(null)}
        onConfirm={handleResetPassword}
        title="Resetear Contraseña"
        description={`La contraseña de ${resetTarget?.user_full_name ?? resetTarget?.user_email} sera reseteada a "123456".`}
        confirmLabel="Resetear"
        loading={resetPassword.isPending}
      />

      {/* Confirm: Eliminar Usuario */}
      <ConfirmDialog
        open={!!deleteTarget}
        onOpenChange={(open) => !open && setDeleteTarget(null)}
        onConfirm={handleDelete}
        title="Eliminar Usuario"
        description={
          deleteTarget?.org_count === 1
            ? `"${deleteTarget?.user_full_name ?? deleteTarget?.user_email}" sera eliminado permanentemente del sistema.`
            : `"${deleteTarget?.user_full_name ?? deleteTarget?.user_email}" sera removido de esta organizacion.`
        }
        confirmLabel="Eliminar"
        variant="destructive"
        loading={deleteMember.isPending}
      />
    </div>
  );
}
