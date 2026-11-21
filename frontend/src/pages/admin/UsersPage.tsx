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
  useUpdateCollectorScope,
  useCreateUser,
  useResetPassword,
  useDeleteMember,
} from "@/hooks/useRoles";
import { useMoneyAccounts, usePayableProviders } from "@/hooks/useMasterData";
import { useOrgSettings } from "@/hooks/useOrgSettings";
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
  const updateCollectorScope = useUpdateCollectorScope();
  // Alcance de recolector (SAC, plan §8): solo con el flag; sin flag, cero requests.
  const { flagEnabled } = useOrgSettings();
  const scopeEnabled = flagEnabled("kg_ledger_enabled");
  const { data: providersData } = usePayableProviders(undefined, scopeEnabled);
  const collectors = scopeEnabled ? (providersData?.items ?? []) : [];
  const collectorName = (id: string | null | undefined) =>
    id ? (collectors.find((c) => c.id === id)?.name ?? "Recolector") : null;
  const createUser = useCreateUser();
  const resetPassword = useResetPassword();
  const deleteMember = useDeleteMember();
  const currentUserId = useAuthStore((s) => s.user?.id);

  const accounts = accountsData?.items ?? [];

  // Estado: Dialog Configurar Usuario
  const [editMember, setEditMember] = useState<OrgMemberResponse | null>(null);
  const [selectedRoleId, setSelectedRoleId] = useState("");
  const [selectedAccountIds, setSelectedAccountIds] = useState<string[]>([]);
  const [selectedCollectorId, setSelectedCollectorId] = useState("");

  // Estado: Dialog Nuevo Usuario
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const [newEmail, setNewEmail] = useState("");
  const [newFullName, setNewFullName] = useState("");
  const [newRoleId, setNewRoleId] = useState("");
  // D2 (plan quitar-clave-constante): la clave la elige el admin, mínimo 8 (UserCreate).
  const [newPassword, setNewPassword] = useState("");
  const [newPasswordConfirm, setNewPasswordConfirm] = useState("");
  const newPasswordTooShort = newPassword.length > 0 && newPassword.length < 8;
  const newPasswordMismatch = newPasswordConfirm.length > 0 && newPassword !== newPasswordConfirm;
  const canCreate =
    !!newEmail && !!newFullName && !!newRoleId &&
    newPassword.length >= 8 && newPassword === newPasswordConfirm && !createUser.isPending;

  // Estado: Resetear Contraseña (D1, patrón #85: mínimo 6, la clave no vuelve)
  const [resetTarget, setResetTarget] = useState<OrgMemberResponse | null>(null);
  const [resetPwd, setResetPwd] = useState("");
  const [resetPwdConfirm, setResetPwdConfirm] = useState("");
  const resetPwdTooShort = resetPwd.length > 0 && resetPwd.length < 6;
  const resetPwdMismatch = resetPwdConfirm.length > 0 && resetPwd !== resetPwdConfirm;
  const canReset = resetPwd.length >= 6 && resetPwd === resetPwdConfirm && !resetPassword.isPending;
  const openReset = (member: OrgMemberResponse) => {
    setResetTarget(member);
    setResetPwd("");
    setResetPwdConfirm("");
  };
  const closeReset = () => {
    setResetTarget(null);
    setResetPwd("");
    setResetPwdConfirm("");
  };

  // Estado: Confirmar Eliminar
  const [deleteTarget, setDeleteTarget] = useState<OrgMemberResponse | null>(null);

  const openEdit = (member: OrgMemberResponse) => {
    setEditMember(member);
    setSelectedRoleId(member.role_id);
    setSelectedAccountIds(member.account_ids ?? []);
    setSelectedCollectorId(member.collector_scope_id ?? "");
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

    const collectorChanged =
      scopeEnabled && selectedCollectorId !== (editMember.collector_scope_id ?? "");

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
    if (collectorChanged) {
      pending++;
      updateCollectorScope.mutate(
        { userId: editMember.user_id, collectorId: selectedCollectorId || null },
        { onSuccess: done },
      );
    }
    if (!roleChanged && !accountsChanged && !collectorChanged) {
      setEditMember(null);
    }
  };

  const closeCreate = () => {
    setShowCreateDialog(false);
    setNewEmail("");
    setNewFullName("");
    setNewRoleId("");
    setNewPassword("");
    setNewPasswordConfirm("");
  };

  const handleCreateUser = () => {
    if (!canCreate) return;
    createUser.mutate(
      { email: newEmail, full_name: newFullName, role_id: newRoleId, password: newPassword },
      { onSuccess: closeCreate },
    );
  };

  const handleResetPassword = () => {
    if (!resetTarget || !canReset) return;
    resetPassword.mutate(
      { userId: resetTarget.user_id, newPassword: resetPwd },
      { onSuccess: closeReset },
    );
  };

  // D5: si el miembro también está en otra org ACTIVA, el reseteo lo hace soporte.
  // El backend lo respalda con 403; la pantalla lo dice antes.
  const resetItem = (member: OrgMemberResponse) =>
    member.in_other_active_org ? (
      <DropdownMenuItem disabled className="flex-col items-start gap-0.5" data-testid="reset-disabled">
        <span className="flex items-center">
          <KeyRound className="h-4 w-4 mr-2" />
          Resetear Contraseña
        </span>
        <span className="text-[11px] text-slate-500 pl-6 max-w-[14rem] whitespace-normal">
          También pertenece a otra organización: el reseteo lo hace soporte
        </span>
      </DropdownMenuItem>
    ) : (
      <DropdownMenuItem onClick={() => openReset(member)}>
        <KeyRound className="h-4 w-4 mr-2" />
        Resetear Contraseña
      </DropdownMenuItem>
    );

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
        <>
          {/* Desktop: tabla */}
          <div className="hidden md:block rounded-lg border border-slate-200/80 overflow-hidden">
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
                      {scopeEnabled && member.collector_scope_id && (
                        <Badge variant="secondary" className="ml-1.5 bg-teal-100 text-teal-700">
                          Alcance: {collectorName(member.collector_scope_id)}
                        </Badge>
                      )}
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
                          {resetItem(member)}
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

          {/* Mobile: cards */}
          <div className="md:hidden space-y-2">
            {members?.map((member) => (
              <div key={member.id} className="rounded-md border bg-white p-3 shadow-sm">
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0 flex-1">
                    <div className="font-medium truncate">{member.user_full_name ?? "-"}</div>
                    <div className="text-xs text-slate-500 truncate">{member.user_email ?? "-"}</div>
                  </div>
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button variant="ghost" size="sm" className="h-8 w-8 p-0 shrink-0">
                        <MoreHorizontal className="h-4 w-4" />
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      <DropdownMenuItem onClick={() => openEdit(member)}>
                        <UserCog className="h-4 w-4 mr-2" />
                        Configurar Usuario
                      </DropdownMenuItem>
                      {resetItem(member)}
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
                </div>
                <div
                  className={
                    // flex-wrap solo con el flag (el badge de alcance puede no
                    // caber a 390): sin flag, la tarjeta queda byte a byte.
                    scopeEnabled
                      ? "mt-2 flex flex-wrap items-center justify-between gap-2 text-xs"
                      : "mt-2 flex items-center justify-between gap-2 text-xs"
                  }
                >
                  <Badge
                    variant="secondary"
                    className={roleBadgeColors[member.role_name ?? ""] ?? "bg-slate-100 text-slate-600"}
                  >
                    {member.role_display_name ?? member.role_name ?? "-"}
                  </Badge>
                  {scopeEnabled && member.collector_scope_id && (
                    <Badge variant="secondary" className="bg-teal-100 text-teal-700">
                      Alcance: {collectorName(member.collector_scope_id)}
                    </Badge>
                  )}
                  <span className="text-slate-500">Desde {formatDate(member.joined_at)}</span>
                </div>
              </div>
            ))}
          </div>
        </>
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
            {scopeEnabled && (
              <div>
                <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Alcance: recolector</Label>
                <p className="text-xs text-slate-400 mt-0.5 mb-2">
                  Con alcance, el usuario solo ve las Entradas, proveedores, compras y cuentas de ese recolector
                </p>
                <Select
                  value={selectedCollectorId || "__none__"}
                  onValueChange={(v) => setSelectedCollectorId(v === "__none__" ? "" : v)}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Sin alcance" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="__none__">Sin alcance (ve toda la organizacion)</SelectItem>
                    {collectors.map((c) => (
                      <SelectItem key={c.id} value={c.id}>{c.name}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            )}
            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Cuentas Visibles</Label>
              <p className="text-xs text-slate-400 mt-0.5 mb-2">
                {scopeEnabled && selectedCollectorId
                  ? "Con alcance, vacio = ninguna cuenta: marca la caja del recolector"
                  : "Dejar vacio para ver todas las cuentas"}
              </p>
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
              disabled={updateMemberRole.isPending || updateAccountAssignments.isPending || updateCollectorScope.isPending}
              className="bg-emerald-600 hover:bg-emerald-700"
            >
              {(updateMemberRole.isPending || updateAccountAssignments.isPending || updateCollectorScope.isPending) ? "Guardando..." : "Guardar"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Dialog: Nuevo Usuario */}
      <Dialog open={showCreateDialog} onOpenChange={(open) => (open ? setShowCreateDialog(true) : closeCreate())}>
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
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <Label htmlFor="new-user-password" className="text-xs font-semibold uppercase tracking-wider text-slate-500">Contraseña</Label>
                <Input
                  id="new-user-password"
                  type="password"
                  autoComplete="new-password"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  placeholder="Mínimo 8 caracteres"
                  className="mt-1"
                />
                {newPasswordTooShort && <p className="text-xs text-red-600 mt-1">Debe tener al menos 8 caracteres.</p>}
              </div>
              <div>
                <Label htmlFor="new-user-password-confirm" className="text-xs font-semibold uppercase tracking-wider text-slate-500">Confirmar</Label>
                <Input
                  id="new-user-password-confirm"
                  type="password"
                  autoComplete="new-password"
                  value={newPasswordConfirm}
                  onChange={(e) => setNewPasswordConfirm(e.target.value)}
                  className="mt-1"
                />
                {newPasswordMismatch && <p className="text-xs text-red-600 mt-1">Las contraseñas no coinciden.</p>}
              </div>
            </div>
            <p className="text-xs text-slate-500">
              Entrégale esta contraseña en persona o por un canal privado. El sistema no la vuelve a mostrar.
            </p>
          </div>
          <DialogFooter className="flex-col sm:flex-row gap-2">
            <Button variant="outline" onClick={closeCreate} className="w-full sm:w-auto">Cancelar</Button>
            <Button
              onClick={handleCreateUser}
              disabled={!canCreate}
              className="w-full sm:w-auto bg-emerald-600 hover:bg-emerald-700"
            >
              {createUser.isPending ? "Creando..." : "Crear Usuario"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Dialog: Resetear Contraseña (D1, patrón #85) */}
      <Dialog open={!!resetTarget} onOpenChange={(open) => !open && closeReset()}>
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle>Resetear Contraseña</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div className="rounded-md bg-slate-50 border p-3 text-sm">
              <div className="font-medium">{resetTarget?.user_full_name ?? "-"}</div>
              <div className="text-slate-500 text-xs mt-0.5">{resetTarget?.user_email}</div>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="member-new-password">Nueva contraseña</Label>
              <Input
                id="member-new-password"
                type="password"
                autoComplete="new-password"
                value={resetPwd}
                onChange={(e) => setResetPwd(e.target.value)}
                placeholder="Mínimo 6 caracteres"
              />
              {resetPwdTooShort && <p className="text-xs text-red-600">Debe tener al menos 6 caracteres.</p>}
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="member-confirm-password">Confirmar contraseña</Label>
              <Input
                id="member-confirm-password"
                type="password"
                autoComplete="new-password"
                value={resetPwdConfirm}
                onChange={(e) => setResetPwdConfirm(e.target.value)}
              />
              {resetPwdMismatch && <p className="text-xs text-red-600">Las contraseñas no coinciden.</p>}
            </div>
            <p className="text-xs text-amber-800 rounded-md border border-amber-200 bg-amber-50 p-3">
              Las sesiones que esa persona tenga abiertas siguen válidas hasta 7 días.
              Entrégale la contraseña por un canal privado: el sistema no se la envía.
            </p>
          </div>
          <DialogFooter className="flex-col sm:flex-row gap-2">
            <Button variant="outline" onClick={closeReset} className="w-full sm:w-auto">Cancelar</Button>
            <Button
              onClick={handleResetPassword}
              disabled={!canReset}
              className="w-full sm:w-auto bg-emerald-600 hover:bg-emerald-700"
            >
              {resetPassword.isPending ? "Guardando..." : "Resetear Contraseña"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

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
