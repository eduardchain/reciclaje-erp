import apiClient from "./api";
import { toast } from "sonner";
import type {
  ThirdPartyResponse,
  ThirdPartyCreate,
  ThirdPartyUpdate,
  RetentionRow,
  RetentionConfigCreate,
  RetentionConfigUpdate,
} from "@/types/third-party";
import type { PaginatedResponse } from "@/types/common";

/**
 * Tope de filas de una carga COMPLETA de terceros (la que alimenta los
 * selectores). Es el maximo que aceptan las 9 rutas de terceros (`le=5000`) y
 * el mismo que ya usaba `golden_capture.py`.
 *
 * 🔴 Por que NO puede volver a 500: los selectores filtran CLIENT-SIDE lo que
 * el usuario escribe, sobre las filas ya cargadas. Un tercero que quede fuera
 * del tope no da error — el desplegable dice "Sin resultados" y para el usuario
 * ese tercero no existe, aunque lo vea en Maestros (que si busca server-side).
 * Costa paso de 500 terceros en sep-2026 y quedaron 18 invisibles (puestos
 * 501-518, todos los que empiezan de "U" en adelante, incluido el de mayor
 * saldo de la org) en las 5 pantallas que cargan la lista completa. El sintoma
 * no apunta a la causa: parece un tercero mal creado.
 *
 * 🔴 Y esta ACOPLADO al `le` de esas 9 rutas, sin ningun tipo que lo sostenga:
 * si una ruta topa por debajo, pedirle este limite da 422 y su desplegable
 * queda VACIO — no incompleto, vacio. Paso asi: subi el tope verificando el
 * `le` de UNA ruta y las otras 8 topaban en 500, lo que dejo Compras y Ventas
 * sin un solo proveedor ni cliente, con tsc, eslint y 1785 tests en verde. Hoy
 * lo sostiene `test_el_tope_del_endpoint_coincide_con_el_del_frontend`, que lee
 * ESTA linea y la compara contra las 9 rutas.
 *
 * Es un TOPE, no un tamano: se traen las filas que hay (518 en la org mas
 * grande), no 5000. El arreglo de fondo — que el selector busque en el servidor
 * mientras se escribe — es ciclo propio.
 */
export const SELECT_LIMIT = 5000;

// Endpoints ya avisados: el toast sale UNA vez por sesion y por endpoint. Sin
// esto, cada re-fetch de React Query lo repetiria.
const truncacionAvisada = new Set<string>();

/**
 * Avisa si una carga COMPLETA volvio cortada por el tope.
 *
 * ⚠️ Solo mira las cargas de selector (`limit === SELECT_LIMIT`). El listado
 * de Terceros usa el MISMO `getAll` con su propia paginacion (PAGE_SIZE filas de 518),
 * y ahi `total > items` es lo normal — sin este filtro el aviso saldria en cada
 * visita al listado y no significaria nada.
 *
 * Con 5000 de tope esto no deberia dispararse nunca. Existe para que el dia que
 * se dispare alguien lo SEPA, en vez de que un tercero desaparezca en silencio.
 *
 * Solape conocido y aceptado: `ThirdPartiesPage.handleExportAll` ya tiene su
 * propio aviso de `total > items`, asi que un export truncado mostraria DOS
 * toasts. Requiere >5000 terceros en una org; no justifica tocar el export.
 */
function assertNotTruncated<T>(
  data: PaginatedResponse<T>,
  endpoint: string,
  limitPedido: unknown
): PaginatedResponse<T> {
  if (limitPedido !== SELECT_LIMIT) return data; // paginacion deliberada
  const traidos = data?.items?.length ?? 0;
  const total = data?.total ?? 0;
  if (total > traidos) {
    console.error(
      `[terceros] ${endpoint} devolvio ${traidos} de ${total}: la lista esta ` +
        `truncada y los selectores no veran los terceros faltantes. ` +
        `Subir SELECT_LIMIT en hooks/useMasterData.ts o pasar a busqueda server-side.`
    );
    if (!truncacionAvisada.has(endpoint)) {
      truncacionAvisada.add(endpoint);
      toast.warning(
        `La lista de terceros esta incompleta (${traidos} de ${total}). ` +
          `Algunos terceros no apareceran en los selectores — avisa a soporte.`,
        { duration: 10000 }
      );
    }
  }
  return data;
}

interface ThirdPartyFilters {
  skip?: number;
  limit?: number;
  search?: string;
  role?: string;
  is_active?: boolean;
  sort_by?: string;
  sort_dir?: "asc" | "desc";
}

export const thirdPartyService = {
  getAll: async (filters: ThirdPartyFilters = {}): Promise<PaginatedResponse<ThirdPartyResponse>> => {
    // Omitir sort_by/sort_dir si son undefined para no contaminar el queryKey
    // ni mandar params vacios. Axios serializa undefined como omision, pero ser
    // explicitos evita que se serialice "sort_by=" cuando alguien pasa "".
    const params: Record<string, unknown> = { ...filters };
    if (!params.sort_by) delete params.sort_by;
    if (!params.sort_dir) delete params.sort_dir;
    const response = await apiClient.get<PaginatedResponse<ThirdPartyResponse>>("/api/v1/third-parties", { params });
    return assertNotTruncated(response.data, "/", params.limit);
  },

  getById: async (id: string): Promise<ThirdPartyResponse> => {
    const response = await apiClient.get<ThirdPartyResponse>(`/api/v1/third-parties/${id}`);
    return response.data;
  },

  create: async (data: ThirdPartyCreate): Promise<ThirdPartyResponse> => {
    const response = await apiClient.post<ThirdPartyResponse>("/api/v1/third-parties", data);
    return response.data;
  },

  update: async (id: string, data: ThirdPartyUpdate): Promise<ThirdPartyResponse> => {
    const response = await apiClient.patch<ThirdPartyResponse>(`/api/v1/third-parties/${id}`, data);
    return response.data;
  },

  deactivate: async (id: string): Promise<ThirdPartyResponse> => {
    const response = await apiClient.delete<ThirdPartyResponse>(`/api/v1/third-parties/${id}`);
    return response.data;
  },

  reactivate: async (id: string): Promise<ThirdPartyResponse> => {
    const response = await apiClient.patch<ThirdPartyResponse>(`/api/v1/third-parties/${id}/reactivate`);
    return response.data;
  },

  getSuppliers: async (filters: Omit<ThirdPartyFilters, "role"> = {}): Promise<PaginatedResponse<ThirdPartyResponse>> => {
    const response = await apiClient.get<PaginatedResponse<ThirdPartyResponse>>("/api/v1/third-parties/suppliers", { params: filters });
    return assertNotTruncated(response.data, "/suppliers", filters.limit);
  },

  getCustomers: async (filters: Omit<ThirdPartyFilters, "role"> = {}): Promise<PaginatedResponse<ThirdPartyResponse>> => {
    const response = await apiClient.get<PaginatedResponse<ThirdPartyResponse>>("/api/v1/third-parties/customers", { params: filters });
    return assertNotTruncated(response.data, "/customers", filters.limit);
  },

  getProvisions: async (filters: Omit<ThirdPartyFilters, "role"> = {}): Promise<PaginatedResponse<ThirdPartyResponse>> => {
    const response = await apiClient.get<PaginatedResponse<ThirdPartyResponse>>("/api/v1/third-parties/provisions", { params: filters });
    return assertNotTruncated(response.data, "/provisions", filters.limit);
  },

  getLiabilities: async (
    filters: (Omit<ThirdPartyFilters, "role"> & { include_system?: boolean }) = {}
  ): Promise<PaginatedResponse<ThirdPartyResponse>> => {
    // include_system=true (SAC E2 D9): incluye entidades sistema "[Retenciones] X"
    // — necesario en el selector de Pago de Pasivo para poder pagarlas.
    const response = await apiClient.get<PaginatedResponse<ThirdPartyResponse>>("/api/v1/third-parties/liabilities", { params: filters });
    return assertNotTruncated(response.data, "/liabilities", filters.limit);
  },

  // Retenciones v2 (CC-006): GET unificado configs+entidades + CRUD de tarifas.
  // Endpoints flag-gated (kg_ledger_enabled): NO llamar sin gate (F2 QA).
  getRetentionRows: async (): Promise<RetentionRow[]> => {
    const response = await apiClient.get<RetentionRow[]>("/api/v1/third-parties/retention-entities");
    return response.data;
  },

  createRetentionConfig: async (data: RetentionConfigCreate): Promise<RetentionRow> => {
    const response = await apiClient.post<RetentionRow>("/api/v1/third-parties/retention-configs", data);
    return response.data;
  },

  updateRetentionConfig: async (configId: string, data: RetentionConfigUpdate): Promise<RetentionRow> => {
    const response = await apiClient.patch<RetentionRow>(`/api/v1/third-parties/retention-configs/${configId}`, data);
    return response.data;
  },

  getPayableProviders: async (filters: Omit<ThirdPartyFilters, "role"> = {}): Promise<PaginatedResponse<ThirdPartyResponse>> => {
    const response = await apiClient.get<PaginatedResponse<ThirdPartyResponse>>("/api/v1/third-parties/payable-providers", { params: filters });
    return assertNotTruncated(response.data, "/payable-providers", filters.limit);
  },

  getPayableSuppliers: async (filters: Omit<ThirdPartyFilters, "role"> = {}): Promise<PaginatedResponse<ThirdPartyResponse>> => {
    const response = await apiClient.get<PaginatedResponse<ThirdPartyResponse>>("/api/v1/third-parties/payable-suppliers", { params: filters });
    return assertNotTruncated(response.data, "/payable-suppliers", filters.limit);
  },

  getInvestors: async (filters: Omit<ThirdPartyFilters, "role"> = {}): Promise<PaginatedResponse<ThirdPartyResponse>> => {
    const response = await apiClient.get<PaginatedResponse<ThirdPartyResponse>>("/api/v1/third-parties/investors", { params: filters });
    return assertNotTruncated(response.data, "/investors", filters.limit);
  },

  getGeneric: async (filters: Omit<ThirdPartyFilters, "role"> = {}): Promise<PaginatedResponse<ThirdPartyResponse>> => {
    const response = await apiClient.get<PaginatedResponse<ThirdPartyResponse>>("/api/v1/third-parties/generic", { params: filters });
    return assertNotTruncated(response.data, "/generic", filters.limit);
  },
};
