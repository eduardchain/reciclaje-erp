import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { getApiErrorMessage } from "@/utils/formatters";
import { crucibleChargeService, type CrucibleChargeFilters } from "@/services/crucibleCharges";
import type { CrucibleChargeCreate } from "@/types/crucible-charge";
import { invalidateAfterCrucibleCharge } from "@/utils/queryInvalidation";

export function useCrucibleCharges(filters: CrucibleChargeFilters = {}, enabled = true) {
  return useQuery({
    queryKey: ["crucible-charges", "list", filters],
    queryFn: () => crucibleChargeService.getAll(filters),
    enabled,
  });
}

export function useCrucibleCharge(id: string | undefined) {
  return useQuery({
    queryKey: ["crucible-charges", "detail", id],
    queryFn: () => crucibleChargeService.getById(id!),
    enabled: !!id,
  });
}

export function useCreateCrucibleCharge() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: CrucibleChargeCreate) => crucibleChargeService.create(data),
    onSuccess: (d) => {
      toast.success(`${d.label} registrado`);
      // Los warnings viajan en la respuesta HTTP (#100 D4d): si la pantalla
      // los descarta, es como si el backend no los calculara.
      (d.warnings ?? []).forEach((w) => toast.warning(w, { duration: 10000 }));
      invalidateAfterCrucibleCharge(qc);
    },
    onError: (e: unknown) =>
      toast.error(getApiErrorMessage(e, "Error al registrar el documento de crisol")),
  });
}

export function useAnnulCrucibleCharge() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, reason }: { id: string; reason: string }) =>
      crucibleChargeService.annul(id, reason),
    onSuccess: () => {
      toast.success("Documento de crisol anulado");
      invalidateAfterCrucibleCharge(qc);
    },
    onError: (e: unknown) => toast.error(getApiErrorMessage(e, "Error al anular")),
  });
}
