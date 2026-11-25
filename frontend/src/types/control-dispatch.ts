// Salida de control y Talonario de remisiones (SAC, documentos de control).
// Espejo de backend/app/schemas/control_dispatch.py.
//
// Lo que sale solo por el consecutivo (estibas, tubulares, electrolito a $0):
// el documento deja numero y remision, y CERO efectos.
//
// ⚠️ Los Decimal llegan como STRING (FastAPI): el servicio los coerciona con
// `num()` al entrar (regla de #107), asi que aca ya son `number`.

export type ControlDispatchStatus = "registered" | "annulled";

export const CONTROL_DISPATCH_STATUS_LABELS: Record<ControlDispatchStatus, string> = {
  registered: "Registrada",
  annulled: "Anulada",
};

export interface ControlDispatchLineCreate {
  material_id: string;
  quantity: string;
  scale_weight_kg?: string;
}

export interface ControlDispatchCreate {
  date: string;
  warehouse_id: string;
  third_party_id?: string;
  remission_number: string;
  notes?: string;
  lines: ControlDispatchLineCreate[];
}

/** Parcial. La remision se cambia pero no se borra (422). `third_party_id:
 *  null` quita el tercero. */
export interface ControlDispatchUpdate {
  date?: string;
  warehouse_id?: string;
  third_party_id?: string | null;
  remission_number?: string;
  notes?: string | null;
  lines?: ControlDispatchLineCreate[];
}

export interface ControlDispatchLine {
  id: string;
  material_id: string;
  material_code: string | null;
  material_name: string | null;
  material_unit: string;
  quantity: number;
  scale_weight_kg: number | null;
}

export interface ControlDispatch {
  id: string;
  dispatch_number: number;
  /** Fecha de NEGOCIO → formatDate (sin hora, #87) */
  date: string;
  warehouse_id: string;
  warehouse_name: string | null;
  third_party_id: string | null;
  third_party_name: string | null;
  remission_number: string;
  notes: string | null;
  status: ControlDispatchStatus;
  annulled_reason: string | null;
  /** Instante real → formatDateTime */
  annulled_at: string | null;
  annulled_by_name: string | null;
  created_at: string;
  created_by_name: string | null;
  lines: ControlDispatchLine[];
  /** Remision repetida: se AVISA, no se rechaza (D8) */
  warnings: string[];
}

export interface ControlDispatchListResponse {
  items: ControlDispatch[];
  total: number;
}

/** Una fila del talonario: un documento o un tramo de numeros sin documento. */
export interface RemissionBookItem {
  kind: "doc" | "gap";
  doc_type: "inbound" | "control_dispatch" | null;
  doc_id: string | null;
  doc_number: number | null;
  remission: string | null;
  date: string | null;
  status: string | null;
  inbound_type: string | null;
  duplicated: boolean;
  materials: string | null;
  /** Texto y no number: una remisión de 20 dígitos pasa 2^53 y un number
   *  la redondearía. El backend la entrega exacta. */
  gap_from: string | null;
  gap_to: string | null;
  count: string | null;
}

export interface RemissionBookResponse {
  items: RemissionBookItem[];
  /** Filas (documentos + tramos) del filtro entero, para paginar */
  total: number;
  documents: number;
  inbound_without_remission: number;
}
