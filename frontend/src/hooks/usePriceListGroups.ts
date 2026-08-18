import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { priceListGroupService } from "@/services/priceListGroups";
import { getApiErrorMessage } from "@/utils/formatters";
import type {
  PriceListGroupCreate,
  PriceListGroupUpdate,
} from "@/types/price-list-group";

/**
 * ⚠️ Todo hook de aca invalida TAMBIEN `["price-lists"]`: un precio de lista
 * vive en la misma tabla que la general y alimenta el resolutor
 * (`/price-lists/current?third_party_id=`), asi que tocar una lista cambia lo
 * que sugieren las pantallas de compras. Sin esto, el usuario edita un precio y
 * la liquidacion le sigue proponiendo el viejo desde cache.
 */
function invalidatePrices(qc: ReturnType<typeof useQueryClient>) {
  qc.invalidateQueries({ queryKey: ["price-list-groups"] });
  qc.invalidateQueries({ queryKey: ["price-lists"] });
}

export function usePriceListGroups(includeInactive = false, enabled = true) {
  return useQuery({
    queryKey: ["price-list-groups", "list", includeInactive],
    queryFn: () => priceListGroupService.getAll(includeInactive),
    enabled,
  });
}

export function usePriceListGroupTable(groupId: string | null) {
  return useQuery({
    queryKey: ["price-list-groups", "table", groupId],
    queryFn: () => priceListGroupService.getTable(groupId!),
    enabled: !!groupId,
  });
}

export function usePriceListGroupSuppliers(enabled = true) {
  return useQuery({
    queryKey: ["price-list-groups", "suppliers"],
    queryFn: () => priceListGroupService.getSuppliers(),
    enabled,
  });
}

export function useCreatePriceListGroup() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: PriceListGroupCreate) => priceListGroupService.create(data),
    onSuccess: (res) => {
      invalidatePrices(qc);
      const partes = [`Lista "${res.group.name}" creada`];
      if (res.seeded_prices) partes.push(`${res.seeded_prices} precios copiados`);
      if (res.assigned_suppliers) partes.push(`${res.assigned_suppliers} proveedores asignados`);
      if (res.skipped_suppliers) {
        partes.push(`${res.skipped_suppliers} ya estaban en otra lista (sin tocar)`);
      }
      toast.success(partes.join(" · "));
    },
    onError: (e: unknown) => toast.error(getApiErrorMessage(e, "Error al crear la lista")),
  });
}

export function useUpdatePriceListGroup() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: PriceListGroupUpdate }) =>
      priceListGroupService.update(id, data),
    onSuccess: () => {
      invalidatePrices(qc);
      toast.success("Lista actualizada");
    },
    onError: (e: unknown) => toast.error(getApiErrorMessage(e, "Error al actualizar")),
  });
}

export function useSetPriceListGroupMembers() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, thirdPartyIds }: { id: string; thirdPartyIds: string[] }) =>
      priceListGroupService.setMembers(id, thirdPartyIds),
    onSuccess: () => {
      invalidatePrices(qc);
      toast.success("Proveedores actualizados");
    },
    onError: (e: unknown) => toast.error(getApiErrorMessage(e, "Error al asignar proveedores")),
  });
}
