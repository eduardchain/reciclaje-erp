import { useMemo } from "react";
import { useOrgSettings } from "@/hooks/useOrgSettings";
import { useKgProfiles } from "@/hooks/useSacConfig";
import { formOrderMap, orderPurchaseLinesForPdf } from "@/utils/formOrder";

/**
 * Ordena las lineas de una compra nacida de una Entrada segun el formato en
 * papel antes de exportar el PDF (F4). Se llama arriba del componente, nunca
 * en el onClick (rules-of-hooks). Sin `kg_ledger_enabled` no hay request (F2)
 * y la funcion devuelve la compra tal cual.
 */
export function usePurchasePdfOrder() {
  const { flagEnabled } = useOrgSettings();
  const sac = flagEnabled("kg_ledger_enabled");
  const { data } = useKgProfiles(undefined, sac);
  const order = useMemo(() => formOrderMap(data?.items), [data]);
  return <P extends Parameters<typeof orderPurchaseLinesForPdf>[0]>(purchase: P): P =>
    orderPurchaseLinesForPdf(purchase, order, sac);
}
