import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { saleService } from "@/services/sales";
import { getApiErrorMessage } from "@/utils/formatters";
import { invalidateAfterSale, invalidateAfterSaleLiquidateOrCancel } from "@/utils/queryInvalidation";
import type { SaleCreate, SaleFullUpdate, SaleLiquidateRequest } from "@/types/sale";

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
    onSuccess: (sale) => {
      // auto_liquidate con cobro inmediato afecta mas queries (movimientos, cuentas, etc.)
      if (sale.status === "liquidated") {
        invalidateAfterSaleLiquidateOrCancel(queryClient);
      } else {
        invalidateAfterSale(queryClient);
      }
      toast.success("Venta creada exitosamente");
      if (sale.warnings && sale.warnings.length > 0) {
        sale.warnings.forEach((w: string) => toast.warning(w));
      }
    },
    onError: (error: unknown) => {
      toast.error(getApiErrorMessage(error, "Error al crear la venta"));
    },
  });
}

export function useUpdateSale() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: SaleFullUpdate }) =>
      saleService.update(id, data),
    onSuccess: (sale) => {
      invalidateAfterSale(queryClient);
      toast.success("Venta actualizada exitosamente");
      if (sale.warnings && sale.warnings.length > 0) {
        sale.warnings.forEach((w: string) => toast.warning(w));
      }
    },
    onError: (error: unknown) => {
      toast.error(getApiErrorMessage(error, "Error al actualizar la venta"));
    },
  });
}

export function useLiquidateSale() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: SaleLiquidateRequest }) =>
      saleService.liquidate(id, data),
    onSuccess: () => {
      invalidateAfterSaleLiquidateOrCancel(queryClient);
      toast.success("Venta liquidada exitosamente");
    },
    onError: (error: unknown) => {
      toast.error(getApiErrorMessage(error, "Error al liquidar la venta"));
    },
  });
}

export function useCancelSale() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => saleService.cancel(id),
    onSuccess: () => {
      invalidateAfterSaleLiquidateOrCancel(queryClient);
      toast.success("Venta cancelada exitosamente");
    },
    onError: (error: unknown) => {
      toast.error(getApiErrorMessage(error, "Error al cancelar la venta"));
    },
  });
}
