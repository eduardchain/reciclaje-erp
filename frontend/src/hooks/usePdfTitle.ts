import { useAuthStore } from "@/stores/authStore";
import { useOrgSettings } from "@/hooks/useOrgSettings";
import { pdfTitle } from "@/utils/pdfExport";

/**
 * Encabezado de los PDF para la org actual (pedido de Johana 2026-11-19):
 * SAC (`kg_ledger_enabled`) ve solo su nombre; el resto, lo de siempre.
 * Se llama arriba del componente, nunca dentro del onClick (rules-of-hooks).
 *
 * Fail-open declarado: mientras el query de settings no cargo, flagEnabled
 * da false y SAC veria la marca. En SAC el sidebar ya carga ese query al
 * entrar (entradas con orgFlag), asi que al exportar esta en cache.
 */
export function usePdfTitle(): string {
  const { organizationId, organizations } = useAuthStore();
  const { flagEnabled } = useOrgSettings();
  const orgName = organizations.find((o) => o.id === organizationId)?.name ?? "";
  return pdfTitle(orgName, flagEnabled("kg_ledger_enabled"));
}
