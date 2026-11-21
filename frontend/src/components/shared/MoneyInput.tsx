import { useState, useEffect, useLayoutEffect, useRef } from "react";
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
 *
 * Al entrar con teclado (Tab, Shift+Tab, `.focus()`) selecciona todo, para que
 * escribir REEMPLACE el valor. El foco cambia «1.300» por «1300», y ese cambio de
 * `value` en un input controlado borra la seleccion del Tab: escribir 1250 daba
 * «13.001.250». Con mouse o dedo no se selecciona: el clic deja el cursor donde
 * se hizo, para corregir un digito (plan-moneyinput-seleccion.md).
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
  // D1: el foco llego por puntero (mouse, dedo, lapiz) -> no seleccionar
  const pointerDownRef = useRef(false);
  // D2: seleccionar todo cuando el texto crudo ya este pintado
  const selectPendingRef = useRef(false);

  useEffect(() => {
    if (!focused) {
      setDisplayValue(value ? formatter.format(value) : "");
    }
  }, [value, focused]);

  // D2: corre en el mismo commit que pinta el texto crudo, antes de la tecla siguiente
  useLayoutEffect(() => {
    const el = inputRef.current;
    if (!selectPendingRef.current || !el) return;
    selectPendingRef.current = false;
    if (document.activeElement === el) el.select();
  }, [displayValue, focused]);

  const handleFocus = () => {
    selectPendingRef.current = !pointerDownRef.current;
    pointerDownRef.current = false;
    setFocused(true);
    setDisplayValue(value ? String(value) : "");
  };

  const handleBlur = () => {
    pointerDownRef.current = false; // D3
    setFocused(false);
    // Aceptar tanto "1.5" (US) como "1,5" (CO) como decimal cuando decimals > 0.
    // El regex de handleChange ya garantiza un solo separador, asi que basta con
    // normalizar coma a punto. Para decimals=0 (montos), el separador se ignora.
    const normalized = decimals > 0
      ? displayValue.replace(",", ".")
      : displayValue.replace(/[.,]/g, "");
    const parsed = parseFloat(normalized) || 0;
    const factor = Math.pow(10, decimals);
    const rounded = Math.round(parsed * factor) / factor;
    const final = min !== undefined && rounded < min ? min : rounded;
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
      inputMode={decimals > 0 ? "decimal" : "numeric"}
      value={displayValue}
      onChange={handleChange}
      onFocus={handleFocus}
      onBlur={handleBlur}
      onPointerDown={() => { pointerDownRef.current = true; }}
      placeholder={placeholder}
      className={className}
      disabled={disabled}
    />
  );
}
