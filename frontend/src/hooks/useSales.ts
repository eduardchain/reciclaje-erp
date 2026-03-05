import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { saleService } from "@/services/sales";
import type { SaleCreate, SaleLiquidateRequest } from "@/types/sale";

interface SaleFilters {
  skip?: number;
  limit?: number;
  status?: string;
  customer_id?: string;
  date_from?: string;
  date_to?: string;
  search?: string;
}

export function useSales(filters: SaleFilters = {}) {
  return useQuery({
    queryKey: ["sales", "list", filters],
    queryFn: () => saleService.getAll(filters),
  });
}

export function useSale(id: string) {
  return useQuery({
    queryKey: ["sales", "detail", id],
    queryFn: () => saleService.getById(id),
    enabled: !!id,
  });
}

export function useCreateSale() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: SaleCreate) => saleService.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["sales"] });
      toast.success("Venta creada exitosamente");
    },
    onError: (error: unknown) => {
      const message =
        (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
        "Error al crear la venta";
      toast.error(message);
    },
  });
}

export function useLiquidateSale() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: SaleLiquidateRequest }) =>
      saleService.liquidate(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["sales"] });
      toast.success("Venta cobrada exitosamente");
    },
    onError: (error: unknown) => {
      const message =
        (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
        "Error al cobrar la venta";
      toast.error(message);
    },
  });
}

export function useCancelSale() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => saleService.cancel(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["sales"] });
      toast.success("Venta cancelada exitosamente");
    },
    onError: (error: unknown) => {
      const message =
        (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
        "Error al cancelar la venta";
      toast.error(message);
    },
  });
}
