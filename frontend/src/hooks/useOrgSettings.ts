import { useQuery } from "@tanstack/react-query";
import { organizationService } from "@/services/organizations";
import { useAuthStore } from "@/stores/authStore";

/**
 * Defaults canonicos — ESPEJO de SETTING_DEFAULTS del backend
 * (backend/app/utils/org_settings.py). Mantener sincronizados.
 */
const SETTING_DEFAULTS: Record<string, unknown> = {
  kg_ledger_enabled: false,
  two_step_transfers_enabled: false,
  internal_maquila_enabled: false,
  transfer_tolerance_pct: 0.05,
  intersede_stale_days: 30,
  aging_buckets: [30, 60, 90],
  // SAC E2 (D12) — espejo del backend
  willard_distribution_centers: ["baq", "bog", "monteria", "santa_marta", "motocosta"],
  // SAC Ciclo B (B2) — sedes deterministas Willard (warehouse IDs como str)
  willard_sede_drosses: null,
  willard_sede_postconsumo_default: null,
  // SAC #93 (D8) — tolerancia del descuadre de entrada (fraccion, no %)
  inbound_discrepancy_tolerance_pct: 0.05,
};

/**
 * Lectura de organization.settings (SAC E1, D3) — espejo de usePermissions.
 *
 * Regla de no-regresion (plan E1 §5.1): en loading/error/settings NULL,
 * getSetting retorna el default y flagEnabled retorna false — las entradas
 * SIN orgFlag jamas dependen del estado de este query; el sidebar de las
 * orgs existentes se renderiza identico a hoy en todo estado del query.
 */
export function useOrgSettings() {
  const organizationId = useAuthStore((s) => s.organizationId);
  const isSystemMode = organizationId === "system";

  const { data, isLoading } = useQuery({
    queryKey: ["org-settings", organizationId],
    queryFn: () => organizationService.getOrganization(organizationId!),
    enabled: !!organizationId && !isSystemMode,
    staleTime: 5 * 60 * 1000,
  });

  const getSetting = (key: string): unknown => {
    if (isSystemMode) return SETTING_DEFAULTS[key];
    const value = data?.settings?.[key];
    return value ?? SETTING_DEFAULTS[key];
  };

  const flagEnabled = (key: string): boolean => getSetting(key) === true;

  return {
    getSetting,
    flagEnabled,
    isLoading: isSystemMode ? false : isLoading,
  };
}
