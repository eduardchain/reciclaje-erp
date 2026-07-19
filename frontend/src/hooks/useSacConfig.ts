import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { sacConfigService } from "@/services/sacConfig";
import { getApiErrorMessage } from "@/utils/formatters";
import type {
  DriverCreate,
  DriverUpdate,
  MaterialConversionFormulaCreate,
  MaterialKgProfileUpsert,
  ServiceTariffCreate,
  VehicleCreate,
  VehicleUpdate,
} from "@/types/sac-config";

// Config pura sin side-effects cross-module: invalidacion inline por key
// propia — NO se toca queryInvalidation.ts (conforme decision #27).

// --- Tarifas ---

export function useCurrentTariffs(enabled = true) {
  return useQuery({
    queryKey: ["service-tariffs", "current"],
    queryFn: sacConfigService.getCurrentTariffs,
    // F2: paginas compartidas gatean por flag — cero requests en orgs prod
    enabled,
  });
}

export function useTariffHistory(tariffCode?: string, enabled = true) {
  return useQuery({
    queryKey: ["service-tariffs", "list", tariffCode ?? "all"],
    queryFn: () => sacConfigService.getTariffs(tariffCode),
    enabled,
  });
}

export function useCreateTariff() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: ServiceTariffCreate) => sacConfigService.createTariff(data),
    onSuccess: () => {
      toast.success("Tarifa registrada — es la nueva vigente");
      qc.invalidateQueries({ queryKey: ["service-tariffs"] });
    },
    onError: (e: unknown) => toast.error(getApiErrorMessage(e, "Error al registrar tarifa")),
  });
}

// --- Formulas de conversion ---

export function useCurrentFormulas(materialId?: string, enabled = true) {
  return useQuery({
    queryKey: ["conversion-formulas", "current", materialId ?? "all"],
    queryFn: () => sacConfigService.getCurrentFormulas(materialId),
    // F2: paginas compartidas (StockPage) gatean por flag — cero requests en prod
    enabled,
  });
}

export function useFormulaHistory(materialId?: string, enabled = true) {
  return useQuery({
    queryKey: ["conversion-formulas", "list", materialId ?? "all"],
    queryFn: () => sacConfigService.getFormulas(materialId ? { material_id: materialId } : undefined),
    enabled,
  });
}

export function useCreateFormula() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: MaterialConversionFormulaCreate) => sacConfigService.createFormula(data),
    onSuccess: () => {
      toast.success("Formula registrada — es la nueva vigente");
      qc.invalidateQueries({ queryKey: ["conversion-formulas"] });
    },
    onError: (e: unknown) => toast.error(getApiErrorMessage(e, "Error al registrar formula")),
  });
}

// --- Clasificacion Willard del material (material_kg_profile, CC-005) ---

export function useKgProfiles(filters?: { compra_regular?: boolean; willard_world?: string }) {
  return useQuery({
    queryKey: ["kg-profiles", "list", filters ?? {}],
    queryFn: () => sacConfigService.getKgProfiles(filters),
  });
}

export function useUpsertKgProfile() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ materialId, data }: { materialId: string; data: MaterialKgProfileUpsert }) =>
      sacConfigService.upsertKgProfile(materialId, data),
    onSuccess: () => {
      toast.success("Clasificacion guardada");
      qc.invalidateQueries({ queryKey: ["kg-profiles"] });
    },
    onError: (e: unknown) => toast.error(getApiErrorMessage(e, "Error al guardar clasificacion")),
  });
}

// --- Flota ---

export function useDrivers(includeInactive = false) {
  return useQuery({
    queryKey: ["fleet", "drivers", includeInactive],
    queryFn: () => sacConfigService.getDrivers(includeInactive),
  });
}

export function useCreateDriver() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: DriverCreate) => sacConfigService.createDriver(data),
    onSuccess: () => {
      toast.success("Conductor creado");
      qc.invalidateQueries({ queryKey: ["fleet", "drivers"] });
    },
    onError: (e: unknown) => toast.error(getApiErrorMessage(e, "Error al crear conductor")),
  });
}

export function useUpdateDriver() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: DriverUpdate }) =>
      sacConfigService.updateDriver(id, data),
    onSuccess: () => {
      toast.success("Conductor actualizado");
      qc.invalidateQueries({ queryKey: ["fleet", "drivers"] });
    },
    onError: (e: unknown) => toast.error(getApiErrorMessage(e, "Error al actualizar conductor")),
  });
}

export function useVehicles(includeInactive = false) {
  return useQuery({
    queryKey: ["fleet", "vehicles", includeInactive],
    queryFn: () => sacConfigService.getVehicles(includeInactive),
  });
}

export function useCreateVehicle() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: VehicleCreate) => sacConfigService.createVehicle(data),
    onSuccess: () => {
      toast.success("Vehiculo creado");
      qc.invalidateQueries({ queryKey: ["fleet", "vehicles"] });
    },
    onError: (e: unknown) => toast.error(getApiErrorMessage(e, "Error al crear vehiculo")),
  });
}

export function useUpdateVehicle() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: VehicleUpdate }) =>
      sacConfigService.updateVehicle(id, data),
    onSuccess: () => {
      toast.success("Vehiculo actualizado");
      qc.invalidateQueries({ queryKey: ["fleet", "vehicles"] });
    },
    onError: (e: unknown) => toast.error(getApiErrorMessage(e, "Error al actualizar vehiculo")),
  });
}
