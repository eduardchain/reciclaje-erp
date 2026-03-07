import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { inventoryService } from "@/services/inventory";
import { getApiErrorMessage } from "@/utils/formatters";
import { invalidateAfterInventoryChange } from "@/utils/queryInvalidation";
import type {
  IncreaseCreate,
  DecreaseCreate,
  RecountCreate,
  ZeroOutCreate,
  WarehouseTransferCreate,
  MaterialTransformationCreate,
  AnnulAdjustmentRequest,
  AnnulTransformationRequest,
} from "@/types/inventory";


// --- Views ---

export function useStock(params?: { category_id?: string; warehouse_id?: string; active_only?: boolean }) {
  return useQuery({
    queryKey: ["inventory", "stock", params],
    queryFn: () => inventoryService.getStock(params),
  });
}

export function useStockDetail(materialId: string) {
  return useQuery({
    queryKey: ["inventory", "stock", materialId],
    queryFn: () => inventoryService.getStockDetail(materialId),
    enabled: !!materialId,
  });
}

export function useTransitStock() {
  return useQuery({
    queryKey: ["inventory", "transit"],
    queryFn: () => inventoryService.getTransit(),
  });
}

export function useInventoryMovements(filters: {
  skip?: number;
  limit?: number;
  material_id?: string;
  warehouse_id?: string;
  movement_type?: string;
  date_from?: string;
  date_to?: string;
}) {
  return useQuery({
    queryKey: ["inventory", "movements", filters],
    queryFn: () => inventoryService.getMovements(filters),
  });
}

export function useValuation(params?: { category_id?: string }) {
  return useQuery({
    queryKey: ["inventory", "valuation", params],
    queryFn: () => inventoryService.getValuation(params),
  });
}

// --- Adjustments ---

export function useAdjustments(filters: {
  skip?: number;
  limit?: number;
  material_id?: string;
  adjustment_type?: string;
  status?: string;
  date_from?: string;
  date_to?: string;
}) {
  return useQuery({
    queryKey: ["inventory", "adjustments", "list", filters],
    queryFn: () => inventoryService.getAdjustments(filters),
  });
}

export function useAdjustment(id: string) {
  return useQuery({
    queryKey: ["inventory", "adjustments", "detail", id],
    queryFn: () => inventoryService.getAdjustment(id),
    enabled: !!id,
  });
}

export function useCreateAdjustment(type: string) {
  const qc = useQueryClient();
  const fnMap: Record<string, (data: never) => Promise<unknown>> = {
    increase: inventoryService.createIncrease as (data: never) => Promise<unknown>,
    decrease: inventoryService.createDecrease as (data: never) => Promise<unknown>,
    recount: inventoryService.createRecount as (data: never) => Promise<unknown>,
    zero_out: inventoryService.createZeroOut as (data: never) => Promise<unknown>,
  };

  return useMutation({
    mutationFn: (data: IncreaseCreate | DecreaseCreate | RecountCreate | ZeroOutCreate) =>
      fnMap[type](data as never),
    onSuccess: () => {
      toast.success("Ajuste creado exitosamente");
      invalidateAfterInventoryChange(qc);
    },
    onError: (error: unknown) => {
      toast.error(getApiErrorMessage(error, "Error al crear ajuste"));
    },
  });
}

export function useAnnulAdjustment() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: AnnulAdjustmentRequest }) =>
      inventoryService.annulAdjustment(id, data),
    onSuccess: () => {
      toast.success("Ajuste anulado");
      invalidateAfterInventoryChange(qc);
    },
    onError: (error: unknown) => {
      toast.error(getApiErrorMessage(error, "Error al anular ajuste"));
    },
  });
}

export function useCreateTransfer() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: WarehouseTransferCreate) => inventoryService.createTransfer(data),
    onSuccess: () => {
      toast.success("Traslado realizado");
      invalidateAfterInventoryChange(qc);
    },
    onError: (error: unknown) => {
      toast.error(getApiErrorMessage(error, "Error al crear traslado"));
    },
  });
}

// --- Transformations ---

export function useTransformations(filters: {
  skip?: number;
  limit?: number;
  source_material_id?: string;
  status?: string;
  date_from?: string;
  date_to?: string;
}) {
  return useQuery({
    queryKey: ["inventory", "transformations", "list", filters],
    queryFn: () => inventoryService.getTransformations(filters),
  });
}

export function useTransformation(id: string) {
  return useQuery({
    queryKey: ["inventory", "transformations", "detail", id],
    queryFn: () => inventoryService.getTransformation(id),
    enabled: !!id,
  });
}

export function useCreateTransformation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: MaterialTransformationCreate) => inventoryService.createTransformation(data),
    onSuccess: () => {
      toast.success("Transformacion creada exitosamente");
      invalidateAfterInventoryChange(qc);
    },
    onError: (error: unknown) => {
      toast.error(getApiErrorMessage(error, "Error al crear transformacion"));
    },
  });
}

export function useAnnulTransformation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: AnnulTransformationRequest }) =>
      inventoryService.annulTransformation(id, data),
    onSuccess: () => {
      toast.success("Transformacion anulada");
      invalidateAfterInventoryChange(qc);
    },
    onError: (error: unknown) => {
      toast.error(getApiErrorMessage(error, "Error al anular transformacion"));
    },
  });
}
