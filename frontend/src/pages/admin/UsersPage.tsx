import { useState } from "react";
import { UserCog } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
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
import { useOrgMembers, useRoles, useUpdateMemberRole, useUpdateAccountAssignments } from "@/hooks/useRoles";
import { useMoneyAccounts } from "@/hooks/useMasterData";
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

  const accounts = accountsData?.items ?? [];

  const [editMember, setEditMember] = useState<OrgMemberResponse | null>(null);
  const [selectedRoleId, setSelectedRoleId] = useState("");
  const [selectedAccountIds, setSelectedAccountIds] = useState<string[]>([]);

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

  return (
    <div className="space-y-6">
      <PageHeader title="Usuarios" description="Miembros de la organizacion y sus roles" />

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
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => openEdit(member)}
                    >
                      <UserCog className="h-3.5 w-3.5 mr-1" />
                      Cambiar Rol
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      {/* Dialog: Cambiar Rol */}
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
    </div>
  );
}
