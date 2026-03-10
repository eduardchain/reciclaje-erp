const currencyFormatter = new Intl.NumberFormat("es-CO", {
  style: "currency",
  currency: "COP",
  minimumFractionDigits: 0,
  maximumFractionDigits: 0,
});

const currencyFormatterDecimals = new Intl.NumberFormat("es-CO", {
  style: "currency",
  currency: "COP",
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

const numberFormatter = new Intl.NumberFormat("es-CO", {
  minimumFractionDigits: 0,
  maximumFractionDigits: 2,
});

export function formatCurrency(value: number | null | undefined): string {
  if (value == null) return "$ 0";
  return currencyFormatter.format(value);
}

export function formatCurrencyDecimals(value: number | null | undefined): string {
  if (value == null) return "$ 0,00";
  return currencyFormatterDecimals.format(value);
}

export function formatNumber(value: number | null | undefined): string {
  if (value == null) return "0";
  return numberFormatter.format(value);
}

export function formatWeight(value: number | null | undefined, unit = "kg"): string {
  if (value == null) return `0 ${unit}`;
  return `${numberFormatter.format(value)} ${unit}`;
}

export function formatPercentage(value: number | null | undefined): string {
  if (value == null) return "0%";
  return `${value.toFixed(1)}%`;
}

export function formatDate(dateStr: string | null | undefined): string {
  if (!dateStr) return "-";
  const date = new Date(dateStr);
  return date.toLocaleDateString("es-CO", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  });
}

export function formatDateTime(dateStr: string | null | undefined): string {
  if (!dateStr) return "-";
  const date = new Date(dateStr);
  return date.toLocaleString("es-CO", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function toISODate(date: Date): string {
  return date.toISOString().split("T")[0];
}

export function toISODateTime(date: Date): string {
  return date.toISOString();
}

/**
 * Convierte un Date a formato "YYYY-MM-DD" en fecha LOCAL del cliente.
 * Para usar como valor inicial de inputs type="date".
 */
export function toLocalDateInput(date: Date = new Date()): string {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, "0");
  const d = String(date.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

/**
 * Convierte un Date a formato "YYYY-MM-DDTHH:MM" en hora LOCAL del cliente.
 * Para usar como valor inicial de inputs type="datetime-local".
 */
export function toLocalDatetimeInput(date: Date = new Date()): string {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, "0");
  const d = String(date.getDate()).padStart(2, "0");
  const h = String(date.getHours()).padStart(2, "0");
  const min = String(date.getMinutes()).padStart(2, "0");
  return `${y}-${m}-${d}T${h}:${min}`;
}

/**
 * Convierte un ISO string UTC del backend a formato "YYYY-MM-DDTHH:MM" en hora LOCAL.
 * Para pre-popular inputs datetime-local en formularios de edicion.
 */
export function utcToLocalDatetimeInput(isoStr: string): string {
  return toLocalDatetimeInput(new Date(isoStr));
}

/**
 * Convierte un ISO string UTC del backend a formato "YYYY-MM-DD" en fecha LOCAL.
 * Para pre-popular inputs type="date" en formularios de edicion.
 */
export function utcToLocalDateInput(isoStr: string): string {
  return toLocalDateInput(new Date(isoStr));
}

type PydanticError = { msg: string; loc?: string[] };
type ApiErrorResponse = { detail?: string | PydanticError[] };

/** Extrae un mensaje legible de cualquier error de API (string o array Pydantic). */
export function getApiErrorMessage(error: unknown, fallback = "Error inesperado"): string {
  const detail = (error as { response?: { data?: ApiErrorResponse } })?.response?.data?.detail;
  if (!detail) return fallback;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail) && detail.length > 0) {
    return detail.map((e) => e.msg).join(", ");
  }
  return fallback;
}
