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
