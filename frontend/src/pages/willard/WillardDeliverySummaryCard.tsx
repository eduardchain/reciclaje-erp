import { useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { useWillardDeliverySummary } from "@/hooks/useWillardDeliveries";
import { formatCurrency, formatWeight, toLocalDateInput } from "@/utils/formatters";
import { DELIVERY_TYPE_LABELS } from "@/types/willard-delivery";

/**
 * Resumen por tipo de salida (#109 D6). Johana (18-sep) eligió la opción B:
 * "Materiales Willard" es un nombre interno para separar ese negocio dentro de
 * la contabilidad. Que baste con que el reporte separe el ingreso es decisión
 * NUESTRA, no pedido de ella. ⚠️ Q-37 se REABRIÓ el 19-sep (🟠 en el
 * inventario): el 16-sep ella dijo que lo facturado por materiales no es
 * ingreso de Circunvalar sino cuenta por pagar. Solo salidas LIQUIDADAS, por
 * fecha de liquidación.
 *
 * ⚠️ La última columna NO se llama "neto" ni "utilidad" a propósito (F4 de QA):
 * es lo facturado menos lo repartido a planta. No incluye la maquila interna
 * que planta ya cobró al trasladar (sin decirlo, en baterías la columna se lee
 * como lo que le queda a Circunvalar) ni descuenta el costo del plomo
 * entregado. La nota fija de abajo dice las dos cosas en pantalla; la primera
 * faltaba hasta el 19-sep aunque F4 la exigía.
 */
export function WillardDeliverySummaryCard() {
  const today = toLocalDateInput(new Date());
  const [open, setOpen] = useState(false);
  const [from, setFrom] = useState(`${today.slice(0, 8)}01`);
  const [to, setTo] = useState(today);
  const { data, isLoading } = useWillardDeliverySummary(from, to, open);

  const rows = data?.rows ?? [];
  const showCrucible = rows.some((r) => r.crucible_amount > 0);

  return (
    <Card>
      <CardContent className="p-3 sm:p-4 space-y-3">
        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          className="flex items-center gap-2 text-sm font-medium text-slate-700 w-full text-left"
        >
          {open ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
          Resumen por tipo de salida
        </button>

        {open && (
          <>
            <div className="flex flex-col sm:flex-row sm:flex-wrap gap-2 sm:items-center">
              <Input type="date" value={from} max={to} onChange={(e) => setFrom(e.target.value)} className="w-full sm:w-40" />
              <span className="hidden sm:inline text-slate-400">a</span>
              <Input type="date" value={to} min={from} max={today} onChange={(e) => setTo(e.target.value)} className="w-full sm:w-40" />
              <span className="text-xs text-slate-500">Salidas liquidadas, por fecha de liquidación</span>
            </div>

            {isLoading ? (
              <p className="text-sm text-slate-500">Cargando…</p>
            ) : rows.length === 0 ? (
              <p className="text-sm text-slate-500">No hay salidas liquidadas en ese rango.</p>
            ) : (
              <>
                {/* Desktop */}
                <div className="hidden md:block overflow-x-auto">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Tipo</TableHead>
                        <TableHead className="text-right">Salidas</TableHead>
                        <TableHead className="text-right">Kg plomo</TableHead>
                        <TableHead className="text-right">Maquila facturada</TableHead>
                        <TableHead className="text-right">Flete facturado</TableHead>
                        <TableHead className="text-right">Reparto a planta</TableHead>
                        {showCrucible && <TableHead className="text-right">Diferencial crisol a planta</TableHead>}
                        <TableHead className="text-right">Queda en Circunvalar de lo facturado</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {rows.map((r) => (
                        <TableRow key={r.delivery_type}>
                          <TableCell className="font-medium">{DELIVERY_TYPE_LABELS[r.delivery_type]}</TableCell>
                          <TableCell className="text-right tabular-nums">{r.documents}</TableCell>
                          <TableCell className="text-right tabular-nums">{formatWeight(r.lead_kg)}</TableCell>
                          <TableCell className="text-right tabular-nums">{formatCurrency(r.maquila_amount)}</TableCell>
                          <TableCell className="text-right tabular-nums">{formatCurrency(r.freight_amount)}</TableCell>
                          <TableCell className="text-right tabular-nums">{formatCurrency(r.plant_credit_amount)}</TableCell>
                          {showCrucible && (
                            <TableCell className="text-right tabular-nums">{formatCurrency(r.crucible_amount)}</TableCell>
                          )}
                          <TableCell className="text-right tabular-nums font-medium">{formatCurrency(r.kept_by_billing_sede)}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>

                {/* Mobile */}
                <div className="md:hidden space-y-2">
                  {rows.map((r) => (
                    <div key={r.delivery_type} className="rounded-md border p-3 text-sm space-y-1">
                      <div className="flex justify-between gap-3 font-medium">
                        <span>{DELIVERY_TYPE_LABELS[r.delivery_type]}</span>
                        <span className="text-slate-500 font-normal">{r.documents} salidas · {formatWeight(r.lead_kg)}</span>
                      </div>
                      <div className="flex justify-between gap-3"><span className="text-slate-500">Maquila facturada</span><span className="tabular-nums">{formatCurrency(r.maquila_amount)}</span></div>
                      <div className="flex justify-between gap-3"><span className="text-slate-500">Flete facturado</span><span className="tabular-nums">{formatCurrency(r.freight_amount)}</span></div>
                      <div className="flex justify-between gap-3"><span className="text-slate-500">Reparto a planta</span><span className="tabular-nums">{formatCurrency(r.plant_credit_amount)}</span></div>
                      {r.crucible_amount > 0 && (
                        <div className="flex justify-between gap-3"><span className="text-slate-500">Diferencial crisol a planta</span><span className="tabular-nums">{formatCurrency(r.crucible_amount)}</span></div>
                      )}
                      <div className="flex justify-between gap-3 border-t pt-1 font-medium"><span>Queda en Circunvalar de lo facturado</span><span className="tabular-nums">{formatCurrency(r.kept_by_billing_sede)}</span></div>
                    </div>
                  ))}
                </div>

                <p className="text-xs text-slate-500">
                  "Queda en Circunvalar" es maquila más flete facturados menos lo repartido a planta. No incluye la maquila interna que planta ya le cobró a Circunvalar al trasladar el material, así que en baterías no es lo que le queda a Circunvalar. Tampoco es una utilidad: no descuenta el costo del plomo entregado{showCrucible ? " ni el diferencial de crisol" : ""}.
                </p>
              </>
            )}
          </>
        )}
      </CardContent>
    </Card>
  );
}
