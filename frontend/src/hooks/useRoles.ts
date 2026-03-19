import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { rolesService } from "@/services/roles";
import { useAuthStore } from "@/stores/authStore";
import { getApiErrorMessage } from "@/utils/formatters";
import type { RoleCreate, RoleUpdate, CreateUserWithMembership } from "@/types/role";

export function useRoles() {
  return useQuery({
    queryKey: ["roles", "list"],
    queryFn: rolesService.getAll,
  });
}

export function useRole(id: string) {
  return useQuery({
    queryKey: ["roles", "detail", id],
    queryFn: () => rolesService.getById(id),
    enabled: !!id,
  });
}

export function usePermissionsByModule() {
  return useQuery({
    queryKey: ["roles", "permissions"],
    queryFn: rolesService.getPermissionsByModule,
  });
}

export function useOrgMembers() {
  const organizationId = useAuthStore((s) => s.organizationId);
  return useQuery({
    queryKey: ["org-members", organizationId],
    queryFn: () => rolesService.getMembers(organizationId!),
    enabled: !!organizationId,
  });
}

export function useCreateRole() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: RoleCreate) => rolesService.create(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["roles"] });
      toast.success("Rol creado exitosamente");
    },
    onError: (e: unknown) => toast.error(getApiErrorMessage(e, "Error al crear el rol")),
  });
}

export function useUpdateRole() {
  const qc = useQueryClient();
  const organizationId = useAuthStore((s) => s.organizationId);
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: RoleUpdate }) => rolesService.update(id, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["roles"] });
      qc.invalidateQueries({ queryKey: ["permissions", organizationId] });
      toast.success("Rol actualizado exitosamente");
    },
    onError: (e: unknown) => toast.error(getApiErrorMessage(e, "Error al actualizar el rol")),
  });
}

export function useDeleteRole() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, reassignTo }: { id: string; reassignTo?: string }) =>
      rolesService.delete(id, reassignTo),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["roles"] });
      qc.invalidateQueries({ queryKey: ["org-members"] });
      toast.success("Rol eliminado exitosamente");
    },
    onError: (e: unknown) => toast.error(getApiErrorMessage(e, "Error al eliminar el rol")),
  });
}

export function useUpdateMemberRole() {
  const qc = useQueryClient();
  const organizationId = useAuthStore((s) => s.organizationId);
  return useMutation({
    mutationFn: ({ userId, roleId }: { userId: string; roleId: string }) =>
      rolesService.updateMemberRole(organizationId!, userId, roleId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["org-members"] });
      qc.invalidateQueries({ queryKey: ["roles"] });
      qc.invalidateQueries({ queryKey: ["permissions", organizationId] });
      toast.success("Rol del usuario actualizado");
    },
    onError: (e: unknown) => toast.error(getApiErrorMessage(e, "Error al cambiar el rol")),
  });
}

export function useUpdateAccountAssignments() {
  const qc = useQueryClient();
  const organizationId = useAuthStore((s) => s.organizationId);
  return useMutation({
    mutationFn: ({ userId, accountIds }: { userId: string; accountIds: string[] }) =>
      rolesService.updateAccountAssignments(organizationId!, userId, accountIds),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["org-members"] });
      qc.invalidateQueries({ queryKey: ["money-accounts"] });
      toast.success("Cuentas asignadas actualizadas");
    },
    onError: (e: unknown) => toast.error(getApiErrorMessage(e, "Error al asignar cuentas")),
  });
}

export function useCreateUser() {
  const qc = useQueryClient();
  const organizationId = useAuthStore((s) => s.organizationId);
  return useMutation({
    mutationFn: (data: CreateUserWithMembership) =>
      rolesService.createUserWithMembership(organizationId!, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["org-members"] });
      toast.success("Usuario creado exitosamente (contraseña: 123456)");
    },
    onError: (e: unknown) => toast.error(getApiErrorMessage(e, "Error al crear usuario")),
  });
}

export function useResetPassword() {
  const organizationId = useAuthStore((s) => s.organizationId);
  return useMutation({
    mutationFn: (userId: string) =>
      rolesService.resetPassword(organizationId!, userId),
    onSuccess: () => {
      toast.success("Contraseña reseteada a 123456");
    },
    onError: (e: unknown) => toast.error(getApiErrorMessage(e, "Error al resetear contraseña")),
  });
}

export function useDeleteMember() {
  const qc = useQueryClient();
  const organizationId = useAuthStore((s) => s.organizationId);
  return useMutation({
    mutationFn: (userId: string) =>
      rolesService.deleteMember(organizationId!, userId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["org-members"] });
      toast.success("Usuario eliminado exitosamente");
    },
    onError: (e: unknown) => toast.error(getApiErrorMessage(e, "Error al eliminar usuario")),
  });
}
