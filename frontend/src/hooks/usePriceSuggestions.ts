import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useMemo } from "react";
import { priceListService } from "@/services/masterData";

/**
 * Precios sugeridos.
 *
 * `supplierId` opcional: con el, el servidor resuelve la lista de ESE proveedor
 * (listas de precios por proveedor, SAC). Sin el, devuelve la lista general —
 * exactamente lo de siempre, que es lo que llaman las 6 pantallas de ventas y
 * cruces y las 3 empresas cliente.
 *
 * ⚠️ La resolucion vive en el SERVIDOR a proposito: la misma regla aplica en
 * las pantallas de compras y en la liquidacion de la Entrada, que es otro flujo
 * con otro estado. Escrita en JS quedaria duplicada — y esta regla ya cambio
 * una vez en 24 horas.
 */
export function usePriceSuggestions(supplierId?: string | null) {
  const { data } = useQuery({
    // El proveedor entra en la llave: cambiar de proveedor trae SUS precios en
    // vez de servir los del anterior desde cache.
    queryKey: ["price-lists", "current-all", supplierId ?? null],
    queryFn: () => priceListService.getCurrentPrices(supplierId ?? undefined),
    staleTime: 5 * 60 * 1000,
  });

  const priceMap = useMemo(() => {
    const map: Record<string, { purchase_price: number; sale_price: number }> = {};
    if (data?.items) {
      for (const item of data.items) {
        map[item.material_id] = {
          // El backend serializa Decimal como string: coercionar en la frontera
          // y no confiar en el tipo (bloqueante (b) de #93).
          purchase_price: Number(item.purchase_price) || 0,
          sale_price: Number(item.sale_price) || 0,
        };
      }
    }
    return map;
  }, [data]);

  const getSuggestedPrice = (materialId: string, type: "purchase" | "sale"): number | null => {
    const entry = priceMap[materialId];
    if (!entry) return null;
    const price = type === "purchase" ? entry.purchase_price : entry.sale_price;
    // Cero = sin sugerencia. Cuando hay lista por proveedor, ese cero es una
    // decision deliberada del usuario y NO se rellena con la lista general.
    return price > 0 ? price : null;
  };

  return { priceMap, getSuggestedPrice };
}

/**
 * Lookup imperativo de precio por proveedor, para pantallas donde conviven
 * VARIOS proveedores a la vez — el reparto de la liquidacion de la Entrada.
 *
 * `usePriceSuggestions` resuelve un proveedor por render y ahi no alcanza: cada
 * asignacion puede tener el suyo. Usa `fetchQuery` con LA MISMA llave y el
 * mismo `staleTime`, asi que comparte cache con el hook — pedir el precio de un
 * proveedor ya consultado no genera request.
 *
 * Devuelve `null` cuando el proveedor no tiene lista o el material esta en cero
 * (D3: el sistema no adivina). Quien llama decide que hacer con esa ausencia.
 */
export function useSupplierPriceLookup() {
  const qc = useQueryClient();

  return useCallback(
    async (supplierId: string, materialId: string): Promise<number | null> => {
      if (!supplierId || !materialId) return null;
      try {
        const data = await qc.fetchQuery({
          queryKey: ["price-lists", "current-all", supplierId],
          queryFn: () => priceListService.getCurrentPrices(supplierId),
          staleTime: 5 * 60 * 1000,
        });
        const hit = data.items.find((i) => i.material_id === materialId);
        const price = Number(hit?.purchase_price) || 0;
        return price > 0 ? price : null;
      } catch {
        // Un fallo de red no puede tumbar la captura: se sigue sin sugerencia.
        return null;
      }
    },
    [qc]
  );
}
