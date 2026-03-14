import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { systemService } from "@/services/system";
import type { SystemOrgCreate, SystemOrgUpdate, AddUserToOrgRequest } from "@/types/organization";

// --- Queries ---

export function useSystemOrganizations(includeInactive = false) {
  return useQuery({
    queryKey: ["system", "organizations", { includeInactive }],
    queryFn: () => systemService.getOrganizations(includeInactive),
  });
}

export function useSystemUsers() {
  return useQuery({
    queryKey: ["system", "users"],
    queryFn: () => systemService.getUsers(),
  });
}

export function useOrgRoles(orgId: string) {
  return useQuery({
    queryKey: ["system", "org-roles", orgId],
    queryFn: () => systemService.getOrgRoles(orgId),
    enabled: !!orgId,
  });
}

// --- Mutations ---

export function useCreateOrganization() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: SystemOrgCreate) => systemService.createOrganization(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["system", "organizations"] });
      toast.success("Organizacion creada exitosamente");
    },
    onError: () => {
      toast.error("Error al crear organizacion");
    },
  });
}

export function useUpdateOrganization() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: SystemOrgUpdate }) =>
      systemService.updateOrganization(id, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["system", "organizations"] });
      toast.success("Organizacion actualizada");
    },
    onError: () => {
      toast.error("Error al actualizar organizacion");
    },
  });
}

export function useDeleteOrganization() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => systemService.deleteOrganization(id),
    onSuccess: (result) => {
      qc.invalidateQueries({ queryKey: ["system", "organizations"] });
      qc.invalidateQueries({ queryKey: ["system", "users"] });
      toast.success(result.message);
    },
    onError: () => {
      toast.error("Error al desactivar organizacion");
    },
  });
}

export function useAddUserToOrg() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ userId, data }: { userId: string; data: AddUserToOrgRequest }) =>
      systemService.addUserToOrg(userId, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["system", "users"] });
      qc.invalidateQueries({ queryKey: ["system", "organizations"] });
      toast.success("Usuario agregado a la organizacion");
    },
    onError: () => {
      toast.error("Error al agregar usuario a la organizacion");
    },
  });
}
