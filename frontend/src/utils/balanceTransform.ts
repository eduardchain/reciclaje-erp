import type {
  BalanceDetailedResponse,
  BalanceDetailedSection,
  BalanceDetailedGroup,
  BalanceDetailedItem,
} from "@/types/reports";

export type BalanceSortBy = "amount_desc" | "alphabetical";

export interface BalanceFilters {
  /** Items con |balance| < hideBelow se ocultan. 0 = mostrar todos. */
  hideBelow: number;
  /** Orden de items y grupos: signed desc (positivos arriba, negativos al final) o alfabetico. */
  sortBy: BalanceSortBy;
}

export const DEFAULT_BALANCE_FILTERS: BalanceFilters = {
  hideBelow: 0,
  sortBy: "amount_desc",
};

export function filtersAreDefault(filters: BalanceFilters): boolean {
  return filters.hideBelow === DEFAULT_BALANCE_FILTERS.hideBelow
    && filters.sortBy === DEFAULT_BALANCE_FILTERS.sortBy;
}

function sortItems(items: BalanceDetailedItem[], sortBy: BalanceSortBy): BalanceDetailedItem[] {
  if (sortBy === "alphabetical") {
    return [...items].sort((a, b) => a.name.localeCompare(b.name, "es"));
  }
  // signed desc: positivos primero (mayor a menor), negativos al final
  return [...items].sort((a, b) => b.balance - a.balance);
}

function filterAndSortItems(
  items: BalanceDetailedItem[],
  filters: BalanceFilters,
): { items: BalanceDetailedItem[]; hidden_count: number; hidden_total: number } {
  let hidden_count = 0;
  let hidden_total = 0;
  const kept: BalanceDetailedItem[] = [];
  for (const item of items) {
    if (filters.hideBelow > 0 && Math.abs(item.balance) < filters.hideBelow) {
      hidden_count++;
      hidden_total += item.balance;
    } else {
      kept.push(item);
    }
  }
  return { items: sortItems(kept, filters.sortBy), hidden_count, hidden_total };
}

function transformSection(
  section: BalanceDetailedSection,
  filters: BalanceFilters,
): BalanceDetailedSection {
  if (section.groups && section.groups.length > 0) {
    // Ordenar grupos por |total| signed desc o alfabetico
    const sortedGroups = filters.sortBy === "alphabetical"
      ? [...section.groups].sort((a, b) => a.label.localeCompare(b.label, "es"))
      : [...section.groups].sort((a, b) => b.total - a.total);

    let section_hidden_count = 0;
    let section_hidden_total = 0;
    const transformedGroups: BalanceDetailedGroup[] = [];

    for (const group of sortedGroups) {
      const { items, hidden_count, hidden_total } = filterAndSortItems(group.items, filters);
      section_hidden_count += hidden_count;
      section_hidden_total += hidden_total;
      // Saltar grupo si quedo vacio (todos sus items filtrados)
      if (items.length === 0 && group.items.length > 0) continue;
      transformedGroups.push({ ...group, items, hidden_count, hidden_total });
    }

    return {
      ...section,
      groups: transformedGroups,
      items: section.items, // grupos toman precedencia, pero preservamos por shape
      hidden_count: section_hidden_count,
      hidden_total: section_hidden_total,
    };
  }

  const { items, hidden_count, hidden_total } = filterAndSortItems(section.items, filters);
  return { ...section, items, hidden_count, hidden_total };
}

/**
 * Transforma un Balance Detallado aplicando filtros del usuario.
 * Los totales de seccion/grupo NO cambian — siguen siendo la verdad contable.
 * Solo los items listados se filtran/reordenan. Metadata `hidden_count` y
 * `hidden_total` queda en cada section/group para que la UI pueda mostrar
 * "N items por debajo del umbral no mostrados".
 */
export function transformBalanceData(
  data: BalanceDetailedResponse,
  filters: BalanceFilters,
): BalanceDetailedResponse {
  const transformSections = (sections: Record<string, BalanceDetailedSection>) => {
    const out: Record<string, BalanceDetailedSection> = {};
    for (const [key, section] of Object.entries(sections)) {
      const transformed = transformSection(section, filters);
      const hadItems = section.items.length > 0
        || (section.groups?.some((g) => g.items.length > 0) ?? false);
      const hasItems = transformed.items.length > 0
        || (transformed.groups?.some((g) => g.items.length > 0) ?? false);
      // Esconder rubros que quedaron vacios DESPUES del filtro (originalmente tenian items)
      if (hadItems && !hasItems) continue;
      out[key] = transformed;
    }
    return out;
  };

  return {
    ...data,
    assets: transformSections(data.assets),
    liabilities: transformSections(data.liabilities),
  };
}

/** Etiqueta corta describiendo filtros activos para mostrar en UI/PDF. */
export function filtersLabel(filters: BalanceFilters, formatCurrency: (n: number) => string): string {
  const parts: string[] = [];
  if (filters.hideBelow > 0) parts.push(`< ${formatCurrency(filters.hideBelow)} oculto`);
  if (filters.sortBy === "alphabetical") parts.push("alfabético");
  return parts.length > 0 ? `Filtros: ${parts.join(" · ")}` : "";
}

/**
 * Items ocultos que NO estan reflejados en notas por-grupo — solo aplica cuando
 * un grupo entero cayo bajo el umbral y se omitio del listado. Devuelve el
 * delta: (section.hidden_count - sum de hidden_count de grupos visibles).
 * Cuando es > 0, el render debe mostrar una nota a nivel seccion para que el
 * total cuadre con lo visible.
 */
export function sectionExtraHidden(section: BalanceDetailedSection): { count: number; total: number } {
  if (!section.groups || section.groups.length === 0) return { count: 0, total: 0 };
  const groupsCount = section.groups.reduce((sum, g) => sum + (g.hidden_count ?? 0), 0);
  const groupsTotal = section.groups.reduce((sum, g) => sum + (g.hidden_total ?? 0), 0);
  return {
    count: (section.hidden_count ?? 0) - groupsCount,
    total: (section.hidden_total ?? 0) - groupsTotal,
  };
}
