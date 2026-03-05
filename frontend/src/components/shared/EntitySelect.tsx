import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

interface EntityOption {
  id: string;
  label: string;
}

interface EntitySelectProps {
  value: string;
  onChange: (value: string) => void;
  options: EntityOption[];
  placeholder?: string;
  disabled?: boolean;
  loading?: boolean;
}

export function EntitySelect({
  value,
  onChange,
  options,
  placeholder = "Seleccionar...",
  disabled = false,
  loading = false,
}: EntitySelectProps) {
  return (
    <Select value={value} onValueChange={onChange} disabled={disabled || loading}>
      <SelectTrigger>
        <SelectValue placeholder={loading ? "Cargando..." : placeholder} />
      </SelectTrigger>
      <SelectContent>
        {options.map((opt) => (
          <SelectItem key={opt.id} value={opt.id}>
            {opt.label}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
