import { useQuery } from "@tanstack/react-query";
import { useMemo } from "react";
import { priceListService } from "@/services/masterData";

export function usePriceSuggestions() {
  const { data } = useQuery({
    queryKey: ["price-lists", "current-all"],
    queryFn: () => priceListService.getCurrentPrices(),
    staleTime: 5 * 60 * 1000,
  });

  const priceMap = useMemo(() => {
    const map: Record<string, { purchase_price: number; sale_price: number }> = {};
    if (data?.items) {
      for (const item of data.items) {
        map[item.material_id] = {
          purchase_price: item.purchase_price,
          sale_price: item.sale_price,
        };
      }
    }
    return map;
  }, [data]);

  const getSuggestedPrice = (materialId: string, type: "purchase" | "sale"): number | null => {
    const entry = priceMap[materialId];
    if (!entry) return null;
    const price = type === "purchase" ? entry.purchase_price : entry.sale_price;
    return price > 0 ? price : null;
  };

  return { priceMap, getSuggestedPrice };
}
