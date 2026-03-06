import { Tag } from "lucide-react";
import { formatCurrency } from "@/utils/formatters";

interface PriceSuggestionProps {
  suggestedPrice: number | null;
  onApply: (price: number) => void;
}

export function PriceSuggestion({ suggestedPrice, onApply }: PriceSuggestionProps) {
  if (!suggestedPrice) return null;

  return (
    <button
      type="button"
      onClick={() => onApply(suggestedPrice)}
      className="flex items-center gap-1 mt-0.5 text-xs text-blue-600 hover:text-blue-800 hover:underline cursor-pointer"
    >
      <Tag className="h-3 w-3" />
      Lista: {formatCurrency(suggestedPrice)}
    </button>
  );
}
