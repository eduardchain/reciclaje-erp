import { useState } from "react";
import { Plus } from "lucide-react";
import { usePermissions } from "@/hooks/usePermissions";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { MoneyInput } from "@/components/shared/MoneyInput";
import { EmptyState } from "@/components/shared/EmptyState";
import { useCreateLeadPrice, useLeadPriceHistory } from "@/hooks/useSacConfig";
import { formatCurrencyDecimals, formatDate, formatDateTime, toLocalDateInput } from "@/utils/formatters";
import ConfigLayout from "./ConfigLayout";

/**
 * Precio de mercado del plomo (CC-014, Q-B). Johana lo lleva hoy a mano fuera
 * del sistema para valorar en el balance la deuda en plomo con Willard.
 *
 * Append-only como las tarifas, con UNA diferencia: la vigencia se decide por
 * la fecha que ella elige, no por cuando carga el dato. El balance de fin de
 * mes siempre se calcula despues.
 *
 * ⚠️ `effective_date` es fecha de negocio: se pinta con formatDate. Solo
 * `created_at`, que si es un instante real, lleva hora (#87).
 */
export default function LeadPricePage() {
  const { hasPermission } = usePermissions();
  const { data, isLoading } = useLeadPriceHistory();
  const create = useCreateLeadPrice();

  const [dialogOpen, setDialogOpen] = useState(false);
  const [price, setPrice] = useState(0);
  const [effectiveDate, setEffectiveDate] = useState("");
  const [notes, setNotes] = useState("");

  const items = data?.items ?? [];
  const vigente = items[0];
  const canManage = hasPermission("tariffs.manage");
  const hoy = toLocalDateInput(new Date());

  const openCreate = () => {
    setPrice(0);
    // Sin default de fecha, igual que la liquidacion de dos pasos (#62): que
    // la elija a conciencia, porque una fecha vieja reescribe cortes ya
    // impresos y eso es justo lo que se aprobo a sabiendas.
    setEffectiveDate("");
    setNotes("");
    setDialogOpen(true);
  };

  const handleSubmit = () => {
    if (price <= 0 || !effectiveDate) return;
    create.mutate(
      { price_per_kg: price, effective_date: effectiveDate, notes: notes || null },
      { onSuccess: () => setDialogOpen(false) }
    );
  };

  return (
    <ConfigLayout>
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
        <p className="text-sm text-slate-500">
          Precio de mercado del plomo por kilo. Con el, la deuda en plomo con Willard
          aparece en el Balance General y en el Detallado como un valor negativo que
          resta del inventario. Cargar un precio crea una version nueva — el historial
          queda intacto.
        </p>
        {canManage && (
          <Button onClick={openCreate} className="bg-emerald-600 hover:bg-emerald-700 w-full sm:w-auto">
            <Plus className="h-4 w-4 mr-2" />
            Nuevo Precio
          </Button>
        )}
      </div>

      {vigente && (
        <div className="rounded-lg border bg-white p-4">
          <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">Precio vigente</p>
          <p className="text-2xl font-semibold text-slate-900 mt-1">
            {formatCurrencyDecimals(Number(vigente.price_per_kg))}
            <span className="text-base font-normal text-slate-500"> por kg</span>
          </p>
          <p className="text-sm text-slate-500 mt-1">
            Rige desde el {formatDate(vigente.effective_date)}
          </p>
        </div>
      )}

      {!isLoading && items.length === 0 ? (
        <EmptyState
          title="Sin precio de mercado"
          description="Mientras no haya precio, el balance muestra los kilos de la deuda con Willard pero no su valor en pesos."
        />
      ) : (
        <div className="overflow-x-auto -mx-3 sm:mx-0 rounded-lg border bg-white">
          <Table className="min-w-[640px]">
            <TableHeader>
              <TableRow>
                <TableHead className="text-right">Precio por kg</TableHead>
                <TableHead>Rige desde</TableHead>
                <TableHead>Notas</TableHead>
                <TableHead>Cargado</TableHead>
                <TableHead>Por</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {items.map((p, i) => (
                <TableRow key={p.id} className={i === 0 ? "bg-emerald-50/60" : undefined}>
                  <TableCell className="text-right font-medium">
                    {formatCurrencyDecimals(Number(p.price_per_kg))}
                    {i === 0 && (
                      <span className="ml-2 text-xs font-normal text-emerald-700">vigente</span>
                    )}
                  </TableCell>
                  <TableCell>{formatDate(p.effective_date)}</TableCell>
                  <TableCell className="text-slate-500">{p.notes ?? "—"}</TableCell>
                  <TableCell className="text-slate-500">{formatDateTime(p.created_at)}</TableCell>
                  <TableCell className="text-slate-500">{p.created_by_name ?? "—"}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Nuevo Precio de Mercado</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                Precio por kg (COP) *
              </Label>
              <MoneyInput value={price} onChange={setPrice} decimals={2} placeholder="0" />
            </div>
            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                Rige desde *
              </Label>
              <Input
                type="date"
                value={effectiveDate}
                max={hoy}
                onChange={(e) => setEffectiveDate(e.target.value)}
                className="w-full"
              />
              <p className="text-xs text-slate-500 mt-1">
                Es la fecha del precio, no la de hoy. Si eliges una fecha anterior, los
                balances ya consultados de esos dias pasan a mostrar este valor.
              </p>
            </div>
            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Notas</Label>
              <Input
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                placeholder="Ej: cotizacion LME del 31 de agosto"
                maxLength={500}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogOpen(false)} className="w-full sm:w-auto">
              Cancelar
            </Button>
            <Button
              onClick={handleSubmit}
              disabled={price <= 0 || !effectiveDate || create.isPending}
              className="bg-emerald-600 hover:bg-emerald-700 w-full sm:w-auto"
            >
              {create.isPending ? "Guardando..." : "Registrar Precio"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </ConfigLayout>
  );
}
