import { useState } from "react";
import { Plus, History } from "lucide-react";
import { usePermissions } from "@/hooks/usePermissions";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { MoneyInput } from "@/components/shared/MoneyInput";
import { EmptyState } from "@/components/shared/EmptyState";
import { useCreateTariff, useCurrentTariffs, useTariffHistory } from "@/hooks/useSacConfig";
import { formatCurrencyDecimals, formatDate } from "@/utils/formatters";
import ConfigLayout from "./ConfigLayout";
import {
  CANONICAL_UNIT_BY_CODE,
  TARIFF_CODE_LABELS,
  TARIFF_UNIT_LABELS,
  type TariffCode,
} from "@/types/sac-config";

const CODES = Object.keys(TARIFF_CODE_LABELS) as TariffCode[];

export default function TariffsPage() {
  const { hasPermission } = usePermissions();
  const { data, isLoading } = useCurrentTariffs();
  const create = useCreateTariff();

  const [dialogOpen, setDialogOpen] = useState(false);
  const [code, setCode] = useState<TariffCode | "">("");
  const [price, setPrice] = useState(0);
  const [notes, setNotes] = useState("");
  const [historyCode, setHistoryCode] = useState<TariffCode | null>(null);
  const history = useTariffHistory(historyCode ?? undefined, historyCode !== null);

  const items = data?.items ?? [];
  const canManage = hasPermission("tariffs.manage");

  const openCreate = (preselect?: TariffCode) => {
    setCode(preselect ?? "");
    setPrice(0);
    setNotes("");
    setDialogOpen(true);
  };

  const handleSubmit = () => {
    if (!code || price <= 0) return;
    create.mutate(
      // La unidad es canonica por codigo (D11a) — la UI no la deja cambiar
      { tariff_code: code, unit_price_cop: price, unit: CANONICAL_UNIT_BY_CODE[code], notes: notes || null },
      { onSuccess: () => setDialogOpen(false) }
    );
  };

  return (
    <ConfigLayout>
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
        <p className="text-sm text-slate-500">
          Tarifas vigentes de maquila y fletes. Corregir una tarifa crea una nueva
          version — el historial queda intacto.
        </p>
        {canManage && (
          <Button onClick={() => openCreate()} className="bg-emerald-600 hover:bg-emerald-700 w-full sm:w-auto">
            <Plus className="h-4 w-4 mr-2" />
            Nueva Tarifa
          </Button>
        )}
      </div>

      {!isLoading && items.length === 0 ? (
        <EmptyState
          title="Sin tarifas"
          description="Crea la primera tarifa — el sistema no siembra valores: los carga el cliente."
        />
      ) : (
        <div className="overflow-x-auto -mx-3 sm:mx-0 rounded-lg border bg-white">
          <Table className="min-w-[640px]">
            <TableHeader>
              <TableRow>
                <TableHead>Tarifa</TableHead>
                <TableHead className="text-right">Precio</TableHead>
                <TableHead>Unidad</TableHead>
                <TableHead>Vigente desde</TableHead>
                <TableHead>Registrada por</TableHead>
                <TableHead className="w-10" />
              </TableRow>
            </TableHeader>
            <TableBody>
              {items.map((t) => (
                <TableRow key={t.id}>
                  <TableCell className="font-medium">
                    {TARIFF_CODE_LABELS[t.tariff_code] ?? t.tariff_code}
                  </TableCell>
                  <TableCell className="text-right font-medium">
                    {formatCurrencyDecimals(Number(t.unit_price_cop))}
                  </TableCell>
                  <TableCell className="text-slate-500">
                    {TARIFF_UNIT_LABELS[t.unit] ?? t.unit}
                  </TableCell>
                  <TableCell>{formatDate(t.created_at)}</TableCell>
                  <TableCell className="text-slate-500">{t.created_by_name ?? "—"}</TableCell>
                  <TableCell>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => setHistoryCode(t.tariff_code)}
                      title="Ver historial"
                    >
                      <History className="h-4 w-4" />
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      {/* Dialog nueva tarifa */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Nueva Tarifa</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Servicio *</Label>
              <Select value={code} onValueChange={(v) => setCode(v as TariffCode)}>
                <SelectTrigger className="w-full">
                  <SelectValue placeholder="Selecciona el servicio" />
                </SelectTrigger>
                <SelectContent>
                  {CODES.map((c) => (
                    <SelectItem key={c} value={c}>{TARIFF_CODE_LABELS[c]}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {code && (
                <p className="text-xs text-slate-500 mt-1">
                  Se cobra <span className="font-medium">{TARIFF_UNIT_LABELS[CANONICAL_UNIT_BY_CODE[code]]}</span> (fijo por servicio)
                </p>
              )}
            </div>
            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Precio (COP) *</Label>
              <MoneyInput value={price} onChange={setPrice} decimals={2} placeholder="0" />
            </div>
            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Notas</Label>
              <Input
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                placeholder="Ej: renegociacion IPC 2026"
                maxLength={500}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogOpen(false)} className="w-full sm:w-auto">Cancelar</Button>
            <Button
              onClick={handleSubmit}
              disabled={!code || price <= 0 || create.isPending}
              className="bg-emerald-600 hover:bg-emerald-700 w-full sm:w-auto"
            >
              {create.isPending ? "Guardando..." : "Registrar Tarifa"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Modal historial por codigo */}
      <Dialog open={historyCode !== null} onOpenChange={(open) => !open && setHistoryCode(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              Historial — {historyCode ? TARIFF_CODE_LABELS[historyCode] : ""}
            </DialogTitle>
          </DialogHeader>
          <div className="overflow-x-auto max-h-[50vh] overflow-y-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Desde</TableHead>
                  <TableHead className="text-right">Precio</TableHead>
                  <TableHead>Por</TableHead>
                  <TableHead>Notas</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {(history.data?.items ?? []).map((h, idx) => (
                  <TableRow key={h.id}>
                    <TableCell>
                      {formatDate(h.created_at)}
                      {idx === 0 && (
                        <span className="ml-2 text-xs text-emerald-600 font-medium">vigente</span>
                      )}
                    </TableCell>
                    <TableCell className="text-right">{formatCurrencyDecimals(Number(h.unit_price_cop))}</TableCell>
                    <TableCell className="text-slate-500">{h.created_by_name ?? "—"}</TableCell>
                    <TableCell className="text-slate-500 max-w-[200px] truncate">{h.notes ?? "—"}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </DialogContent>
      </Dialog>
    </ConfigLayout>
  );
}
