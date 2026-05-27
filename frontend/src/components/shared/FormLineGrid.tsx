import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { cn } from "@/utils";
import { Trash2 } from "lucide-react";

interface FormLineGridProps {
  children: React.ReactNode;
  isLast?: boolean;
  isFirst?: boolean;
  onDelete?: () => void;
  disableDelete?: boolean;
  className?: string;
}

/**
 * Wrapper responsive para lineas de formulario (compras, ventas, movimientos).
 * Mobile (<md): stack vertical, delete button absoluto top-right.
 * Desktop (md+): grid de 12 columnas, delete button inline col-span-1.
 *
 * Los hijos deben usar `md:col-span-N` (sin clase en mobile = full width).
 * Las <Label> de los inputs deben usar el helper `lineLabelClass(idx)` para
 * mostrarse siempre en mobile pero solo en la primera linea en desktop.
 */
export function FormLineGrid({
  children,
  isLast = false,
  isFirst = false,
  onDelete,
  disableDelete,
  className,
}: FormLineGridProps) {
  return (
    <div
      className={cn(
        "relative grid grid-cols-1 gap-3 pb-4 mb-3",
        "md:grid-cols-12 md:gap-2 md:items-end md:pb-8",
        !isLast && "border-b border-slate-100",
        className,
      )}
    >
      {children}
      {onDelete && (
        <>
          {/* Mobile: delete absoluto top-right */}
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={onDelete}
            disabled={disableDelete}
            className="md:hidden absolute top-2 right-0 text-red-500 hover:text-red-700 disabled:opacity-30"
            aria-label="Eliminar linea"
          >
            <Trash2 className="h-4 w-4" />
          </Button>
          {/* Desktop: delete inline col-span-1 */}
          <div className="hidden md:block md:col-span-1">
            {isFirst && <Label className="text-xs">&nbsp;</Label>}
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={onDelete}
              disabled={disableDelete}
              className="text-red-500 hover:text-red-700"
              aria-label="Eliminar linea"
            >
              <Trash2 className="h-4 w-4" />
            </Button>
          </div>
        </>
      )}
    </div>
  );
}

/**
 * Helper para clases CSS de Label dentro de lineas de FormLineGrid.
 * En desktop, solo la primera linea (idx === 0) muestra labels (estilo tabla).
 * En mobile, TODAS las lineas muestran labels (estilo card vertical).
 */
export function lineLabelClass(idx: number): string {
  return idx > 0 ? "md:hidden" : "";
}
