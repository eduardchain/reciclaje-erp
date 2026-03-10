import { useState, useEffect, useRef } from "react";
import { Input } from "@/components/ui/input";

function getFormatter(decimals: number) {
  return new Intl.NumberFormat("es-CO", {
    minimumFractionDigits: 0,
    maximumFractionDigits: decimals,
  });
}

interface MoneyInputProps {
  value: number;
  onChange: (value: number) => void;
  min?: number;
  step?: string;
  placeholder?: string;
  className?: string;
  disabled?: boolean;
  /** Decimales permitidos (default: 0 para montos, usar 2 o 4 para cantidades) */
  decimals?: number;
}

/**
 * Input de monto con separador de miles (formato colombiano: 1.000.000).
 * Muestra formateado cuando no tiene foco; permite edicion libre con foco.
 */
export function MoneyInput({
  value,
  onChange,
  min = 0,
  placeholder = "0",
  className,
  disabled,
  decimals = 0,
}: MoneyInputProps) {
  const formatter = getFormatter(decimals);
  const [focused, setFocused] = useState(false);
  const [displayValue, setDisplayValue] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!focused) {
      setDisplayValue(value ? formatter.format(value) : "");
    }
  }, [value, focused]);

  const handleFocus = () => {
    setFocused(true);
    setDisplayValue(value ? String(value) : "");
  };

  const handleBlur = () => {
    setFocused(false);
    const parsed = parseFloat(displayValue.replace(/\./g, "").replace(",", ".")) || 0;
    const final = min !== undefined && parsed < min ? min : parsed;
    onChange(final);
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const raw = e.target.value;
    // Permitir digitos, punto decimal y signo negativo
    if (raw === "" || raw === "-" || /^-?\d*[.,]?\d*$/.test(raw)) {
      setDisplayValue(raw);
    }
  };

  return (
    <Input
      ref={inputRef}
      type="text"
      inputMode="numeric"
      value={displayValue}
      onChange={handleChange}
      onFocus={handleFocus}
      onBlur={handleBlur}
      placeholder={placeholder}
      className={className}
      disabled={disabled}
    />
  );
}
