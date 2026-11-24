/**
 * Liquidar una Entrada de Willard (el confirm B.2), desde el detalle y desde
 * la fila del listado — UN solo componente (plan-sac-factor-willard D7).
 *
 * Si alguna línea es de un material con factores de Willard alternativos
 * (ej. SCR-SG: Seco pinza 59 % / Seco escurrido 56 %), muestra por línea un
 * selector con el defecto preseleccionado y los kg estimados en vivo. Sin
 * alternativas, el diálogo queda como antes y el confirm va sin cuerpo.
 */
import { useEffect, useMemo, useState } from "react";
import { ConfirmDialog } from "@/components/shared/ConfirmDialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useConfirmInboundOrder } from "@/hooks/useInboundOrders";
import { useCurrentFormulas } from "@/hooks/useSacConfig";
import type { InboundOrderResponse } from "@/types/inbound-order";
import { num } from "@/types/willard-delivery";
import { formatWeight } from "@/utils/formatters";
import { DEFAULT_FACTOR, factorOptions, pctText, type FactorOption } from "@/utils/willardFactors";

interface Props {
  order: InboundOrderResponse | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  description: string;
  onDone?: () => void;
}

interface LineChoice {
  materialId: string;
  label: string;
  quantity: number;
  options: FactorOption[];
}

export function WillardLiquidateDialog({ order, open, onOpenChange, description, onDone }: Props) {
  const confirmOrder = useConfirmInboundOrder();
  // F2: solo se piden las fórmulas con el diálogo abierto
  const {
    data: formulasData,
    isLoading: formulasLoading,
    isError: formulasError,
  } = useCurrentFormulas(undefined, open);
  const [chosen, setChosen] = useState<Record<string, string>>({});

  useEffect(() => {
    if (open) setChosen({});
  }, [open, order?.id]);

  const lines = useMemo((): LineChoice[] => {
    if (!order) return [];
    const formulas = formulasData?.items ?? [];
    return order.lines
      .map((l) => ({
        materialId: l.material_id,
        label: [l.material_code, l.material_name].filter(Boolean).join(" - "),
        quantity: num(l.quantity),
        options: factorOptions(formulas.find((f) => f.material_id === l.material_id)),
      }))
      .filter((l) => l.options.length > 0);
  }, [order, formulasData]);

  const optionOf = (line: LineChoice): FactorOption => {
    const v = chosen[line.materialId] ?? DEFAULT_FACTOR;
    return line.options.find((o) => (o.value ?? DEFAULT_FACTOR) === v) ?? line.options[0];
  };

  const submit = () => {
    if (!order) return;
    const conversionOptions = lines.map((l) => ({ material_id: l.materialId, option: optionOf(l).value }));
    confirmOrder.mutate(
      { id: order.id, conversionOptions },
      {
        onSuccess: () => {
          onOpenChange(false);
          onDone?.();
        },
      }
    );
  };

  return (
    <ConfirmDialog
      open={open}
      onOpenChange={onOpenChange}
      title={`Liquidar Entrada #${order?.order_number ?? ""}`}
      description={description}
      confirmLabel="Liquidar"
      loading={confirmOrder.isPending}
      disabled={formulasLoading}
      onConfirm={submit}
    >
      {/* C2 de QA 1: sin las fórmulas (un rol sin formulas.view, o la red) no
          hay selectores. No bloquea, pero lo dice: corregir un factor mal
          escogido después es anular y registrar de nuevo (D6). */}
      {formulasError && (
        <div
          className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800"
          data-testid="factores-no-leidos"
        >
          No se pudieron leer los factores de Willard. Si liquida ahora, cada material
          usa su factor por defecto. Para escoger otro, cierre y vuelva a intentar o
          pida a un administrador que liquide.
        </div>
      )}
      {lines.length > 0 && (
        <div className="space-y-3" data-testid="willard-factors">
          <p className="text-sm font-medium text-slate-700">Factor de Willard por línea</p>
          {lines.map((line) => {
            const opt = optionOf(line);
            return (
              <div
                key={line.materialId}
                className="flex flex-col sm:flex-row sm:items-center gap-1.5 sm:gap-3"
                data-testid={`factor-line-${line.materialId}`}
              >
                <div className="text-sm text-slate-600 sm:flex-1 min-w-0">
                  <span className="font-medium text-slate-800">{line.label}</span>
                  <span className="block text-xs text-slate-500">
                    {formatWeight(line.quantity)} → ~{formatWeight(line.quantity * opt.pct)} de plomo
                  </span>
                </div>
                <Select
                  value={opt.value ?? DEFAULT_FACTOR}
                  onValueChange={(v) => setChosen((c) => ({ ...c, [line.materialId]: v }))}
                >
                  <SelectTrigger className="w-full sm:w-56" aria-label={`Factor de ${line.label}`}>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {line.options.map((o) => (
                      <SelectItem key={o.value ?? DEFAULT_FACTOR} value={o.value ?? DEFAULT_FACTOR}>
                        {o.label} · {pctText(o.pct)}
                        {o.value === null ? " (por defecto)" : ""}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            );
          })}
        </div>
      )}
    </ConfirmDialog>
  );
}
