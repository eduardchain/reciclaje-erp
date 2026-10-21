import type { QueryClient } from "@tanstack/react-query";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { usePermissions } from "@/hooks/usePermissions";
import { useWarehouses } from "@/hooks/useMasterData";
import type { PaginatedResponse } from "@/types/common";
import type { WarehouseResponse } from "@/types/warehouse";

interface WarehouseFilterSelectProps {
  /** id de la bodega filtrada, o "" para "Todas" */
  value: string;
  onChange: (warehouseId: string | null) => void;
}

/**
 * Filtro "Bodega" de los listados de Compras y Ventas.
 *
 * 🔴 Gateado por `warehouses.view` — y el gate tiene que ser este componente,
 * no el padre. `GET /warehouses` exige ese permiso, y el liquidador no lo tiene
 * fuera de Costa: si la lista se pidiera igual, fallaria en silencio (api.ts
 * solo maneja los 401) y el selector ofreceria un filtro que no puede dar.
 * Sin el permiso, `useWarehouses` NO se monta y no sale ninguna peticion; si
 * igual llega un link con `?warehouse=<id>`, se muestra "Bodega filtrada ×"
 * para poder quitarlo. Por la misma razon, el nombre de la bodega para el Excel
 * sale de la cache (`cachedWarehouseName`), nunca de un fetch del padre.
 */
export function WarehouseFilterSelect({ value, onChange }: WarehouseFilterSelectProps) {
  const { hasPermission } = usePermissions();
  if (hasPermission("warehouses.view")) {
    return <WarehouseOptions value={value} onChange={onChange} />;
  }
  if (!value) return null;
  return (
    <span className="inline-flex items-center gap-1 self-start sm:self-auto bg-indigo-50 text-indigo-700 text-xs px-2 py-1 rounded border border-indigo-200">
      Bodega filtrada
      <button onClick={() => onChange(null)} className="hover:bg-indigo-100 rounded px-1" aria-label="Quitar filtro de bodega">×</button>
    </span>
  );
}

function WarehouseOptions({ value, onChange }: WarehouseFilterSelectProps) {
  const { data, isLoading } = useWarehouses();
  // Sin bodegas de transito: ninguna compra ni venta puede tenerlas (guard E12).
  // Las inactivas SI, marcadas: sirven para auditar una bodega cerrada.
  const options = (data?.items ?? []).filter((w) => !w.is_transit);
  const unknown = !!value && !isLoading && !options.some((w) => w.id === value);

  return (
    <Select value={value || "all"} onValueChange={(v) => onChange(v === "all" ? null : v)}>
      <SelectTrigger className="w-full sm:w-48" aria-label="Filtrar por bodega">
        <SelectValue placeholder="Todas las bodegas" />
      </SelectTrigger>
      <SelectContent>
        <SelectItem value="all">Todas las bodegas</SelectItem>
        {options.map((w) => (
          <SelectItem key={w.id} value={w.id}>
            {w.name}
            {!w.is_active && " (inactiva)"}
          </SelectItem>
        ))}
        {unknown && <SelectItem value={value}>Bodega filtrada</SelectItem>}
      </SelectContent>
    </Select>
  );
}

/**
 * Nombre de una bodega leido de la CACHE de React Query, sin pedir nada.
 * null si no esta: sin `warehouses.view` la lista nunca se pidio, y eso es a
 * proposito (ver arriba).
 */
export function cachedWarehouseName(queryClient: QueryClient, warehouseId: string): string | null {
  const data = queryClient.getQueryData<PaginatedResponse<WarehouseResponse>>(["warehouses", "list"]);
  return data?.items.find((w) => w.id === warehouseId)?.name ?? null;
}
