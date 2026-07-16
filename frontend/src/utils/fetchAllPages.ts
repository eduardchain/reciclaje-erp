import { toast } from "sonner";

/** El backend capea `limit` a 1000 por request (le=1000) — el export pagina en lotes de este tamano. */
const PAGE_LIMIT = 1000;
/** Tope de seguridad: 20 paginas = 20.000 filas. Evita loop infinito si el backend reporta un `total` inconsistente. */
const MAX_PAGES = 20;

/**
 * Trae TODAS las paginas de un endpoint paginado (skip/limit) en loop hasta
 * cubrir `total`. Para exports Excel: reemplaza la unica llamada con
 * `limit: 1000` que dejaba el archivo truncado en 1000 filas.
 *
 * - Corta cuando `items` acumulados >= `total`, o si una pagina llega vacia
 *   (backend devolvio menos de lo que su `total` prometia — no ciclar).
 * - Si se alcanza el tope de seguridad con datos pendientes, avisa con toast.
 */
export async function fetchAllPages<T>(
  fetchPage: (skip: number, limit: number) => Promise<{ items: T[]; total: number }>,
): Promise<T[]> {
  const all: T[] = [];
  let page = 0;
  for (;;) {
    const res = await fetchPage(page * PAGE_LIMIT, PAGE_LIMIT);
    all.push(...res.items);
    page++;
    if (all.length >= res.total) break; // set completo
    if (res.items.length === 0) break; // pagina vacia antes de `total` — corta sin ciclar
    if (page >= MAX_PAGES) {
      toast.warning(
        `Excel limitado a ${all.length} filas (tope de seguridad). Hay ${res.total} en total — refina filtros para descargar el resto.`,
      );
      break;
    }
  }
  return all;
}
