import { Fragment, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, Archive, CheckCircle2, ClipboardCheck, Clock, Pencil, RotateCcw, Undo2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { PageHeader } from "@/components/shared/PageHeader";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { ConfirmDialog } from "@/components/shared/ConfirmDialog";
import { WillardLiquidateDialog } from "@/components/inbound/WillardLiquidateDialog";
import { AdjustmentLink, PurchaseLink, ThirdPartyLink } from "@/components/shared/EntityLink";
import { cn } from "@/utils";
import { useReturnToBack } from "@/hooks/useReturnToBack";
import { usePermissions } from "@/hooks/usePermissions";
import {
  useAnnulInboundOrder,
  useInboundOrder,
  useReopenInboundOrder,
  useReviewInboundOrder,
  useUnliquidateInboundOrder,
} from "@/hooks/useInboundOrders";
import { useCurrentFormulas, useKgProfiles } from "@/hooks/useSacConfig";
import { useScopeSupplierIds } from "@/hooks/useMasterData";
import { formOrderMap, sortByFormOrder } from "@/utils/formOrder";
import {
  countsAsLiquidated,
  liquidatedTotals,
  purchaseMaterials,
  purchaseMoney,
  type PurchaseTotals,
} from "@/utils/inboundPurchases";
import {
  formatCurrency,
  formatCurrencyDecimals,
  formatDate,
  formatTime,
  formatWeight,
} from "@/utils/formatters";
import { buildRoute, ROUTES } from "@/utils/constants";
import { estimateKgLead, willardCenterLabel } from "./InboundCreatePage";
import { EntradaStatusBadge, EntradaTypeBadge } from "./InboundOrdersPage";
import { CloseControlDialog } from "./CloseControlDialog";
import {
  INBOUND_TYPE_LABELS,
  PURCHASE_INBOUND_TYPES,
  WILLARD_INBOUND_TYPES,
  type InboundOrderLineResponse,
  type InboundPurchaseSummary,
} from "@/types/inbound-order";
import { pctText } from "@/utils/willardFactors";

/** El backend serializa Decimal como STRING ("0.0000") aunque el tipo TS diga
 *  number. Para PINTAR da igual (Intl lo coacciona), pero toda COMPARACION
 *  falla en silencio: `"0.0000" === 0` es false. Lección de #93. */
const num = (v: unknown, fallback = 0): number => {
  const n = Number(v);
  return Number.isFinite(n) ? n : fallback;
};

/** Los pesos van sin decimales en toda la app, pero al liquidar por VALOR
 *  TOTAL el centavo del redondeo ES el dato (D8): una compra de $200.000,01
 *  no puede mostrarse como $200.000. Decimales solo cuando existen. */
const fmtMoney = (v: number | null | undefined): string => {
  const n = num(v);
  return Math.abs(n - Math.round(n)) < 0.005
    ? formatCurrency(n)
    : formatCurrencyDecimals(n);
};

// #93: el borde sigue el estado UNICO visible (columna-driven)
const statusBorderMap: Record<string, string> = {
  registered: "border-t-[3px] border-t-amber-400",
  reviewed: "border-t-[3px] border-t-sky-400",
  liquidated: "border-t-[3px] border-t-emerald-400",
  annulled: "border-t-[3px] border-t-rose-400",
  closed: "border-t-[3px] border-t-slate-400",
};

function InfoRow({ label, value, long = false }: { label: string; value: React.ReactNode; long?: boolean }) {
  return (
    <div className={long ? "flex flex-col sm:flex-row sm:justify-between gap-0.5 sm:gap-3" : "flex justify-between gap-3"}>
      <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">{label}</span>
      <span className="text-sm text-slate-800 sm:text-right">{value}</span>
    </div>
  );
}

/**
 * Valor de una fila de auditoría («Registrada/Revisada/Liquidada/Anulada por»):
 * «nombre · fecha, hora», con el mismo formato en todas las filas. El bloque
 * «fecha, hora» no se parte (whitespace-nowrap): a 1440 la hora se cortaba
 * antes de «p. m.». El «·» va pegado al nombre (espacio de no separación), así
 * que si el renglón no alcanza, la fecha baja entera y ningún renglón empieza
 * con el separador. La fecha y la hora llegan ya formateadas porque en
 * «Liquidada por» salen de dos campos: la fecha es de NEGOCIO (liquidated_at →
 * formatDate, #87) y la hora es del instante real (liquidated_ts → formatTime).
 * Sin nombre (la fila «Anulada» de la tarjeta de efectos) pinta solo
 * «fecha, hora», con el mismo bloque; sin nombre ni fecha, «—».
 */
function AuditValue({ name, date, time }: { name?: string; date: string | null; time: string | null }) {
  const when = [date, time].filter(Boolean).join(", ");
  if (!when) return <>{name ?? "—"}</>;
  if (!name) return <span className="whitespace-nowrap">{when}</span>;
  return (
    <>
      {`${name}\u00A0·`} <span className="whitespace-nowrap">{when}</span>
    </>
  );
}

const MAX_MATERIALS = 3;

/** Materiales de la compra (D3): hasta 3 renglones + «+N más» (patrón #82). */
function PurchaseMaterialsCell({
  purchase,
  lines,
}: {
  purchase: InboundPurchaseSummary;
  lines: InboundOrderLineResponse[];
}) {
  const mats = purchaseMaterials(purchase, lines);
  if (mats.length === 0) return <span className="text-slate-400">—</span>;
  return (
    <div className="space-y-0.5 text-xs">
      {mats.slice(0, MAX_MATERIALS).map((m, i) => (
        <div key={i} className="whitespace-nowrap">
          <span className="font-medium">{m.code}</span>{" "}
          <span className="tabular-nums text-slate-500">{formatWeight(m.quantity, m.unit)}</span>
        </div>
      ))}
      {mats.length > MAX_MATERIALS && (
        <div className="text-slate-400">+{mats.length - MAX_MATERIALS} más</div>
      )}
    </div>
  );
}

function totalsLabel(totals: PurchaseTotals): string {
  const s = totals.count === 1 ? "" : "s";
  return `Total (${totals.count} compra${s} liquidada${s})`;
}

/** Compras de la Entrada en tabla, desde md (plan compras en tabla v1.2, D1).
 *  Suman solo las liquidadas (O1); una registrada (Entrada desliquidada) y una
 *  cancelada se ven, pero con «no suma». */
function PurchasesTable({
  purchases,
  lines,
  totals,
  canViewPrices,
  outOfScope,
  collectorName,
}: {
  purchases: InboundPurchaseSummary[];
  lines: InboundOrderLineResponse[];
  totals: PurchaseTotals;
  canViewPrices: boolean;
  /** Alcance de recolector (#129, plan D6): la MISMA regla de las tarjetas —
   *  proveedor fuera del alcance → Compra y Proveedor sin link (darían 404) y
   *  la nota ámbar debajo del proveedor. Sin alcance siempre da false. */
  outOfScope: (supplierId: string | null | undefined) => boolean;
  collectorName: string | null | undefined;
}) {
  const money = "text-right tabular-nums whitespace-nowrap";
  return (
    <div className="hidden md:block overflow-x-auto" data-testid="purchases-table">
      <Table className={canViewPrices ? "min-w-[960px]" : "min-w-[640px]"}>
        <TableHeader>
          <TableRow>
            <TableHead>Compra</TableHead>
            <TableHead>Proveedor</TableHead>
            <TableHead>Factura</TableHead>
            <TableHead>Materiales</TableHead>
            {canViewPrices && (
              <>
                <TableHead className="text-right">Subtotal</TableHead>
                <TableHead className="text-right">IVA</TableHead>
                <TableHead className="text-right">Retenciones</TableHead>
                <TableHead className="text-right">Total al proveedor</TableHead>
              </>
            )}
            <TableHead>Estado</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {purchases.map((p) => {
            const m = purchaseMoney(p);
            const cancelled = p.status === "cancelled";
            const counts = countsAsLiquidated(p);
            const moneyCls = cn(money, cancelled && "line-through");
            const out = outOfScope(p.supplier_id);
            return (
              <TableRow
                key={p.purchase_id}
                data-testid="purchase-row"
                data-purchase-number={p.purchase_number}
                data-counts={counts ? "1" : "0"}
                className={cn(
                  cancelled && "bg-slate-50/70 text-slate-400",
                  !cancelled && !counts && "text-slate-500"
                )}
              >
                <TableCell className="whitespace-nowrap" data-col="compra">
                  {out ? (
                    <span>Compra #{p.purchase_number}</span>
                  ) : (
                    <PurchaseLink id={p.purchase_id}>Compra #{p.purchase_number}</PurchaseLink>
                  )}
                  {p.purchase_slot != null && (
                    <div className="text-[11px] uppercase tracking-wider text-slate-400">
                      Compra {p.purchase_slot}
                    </div>
                  )}
                </TableCell>
                <TableCell className="max-w-[220px]" data-col="proveedor">
                  {out ? (
                    p.supplier_name ?? "—"
                  ) : (
                    <ThirdPartyLink id={p.supplier_id}>{p.supplier_name ?? "—"}</ThirdPartyLink>
                  )}
                  {out && (
                    <div data-testid="out-of-scope-note" className="text-xs text-amber-700 mt-0.5 whitespace-normal">
                      Proveedor sin la marca de {collectorName ?? "tu recolector"}: pídele a SAC
                      que lo marque en Terceros.
                    </div>
                  )}
                </TableCell>
                <TableCell className="whitespace-nowrap">{p.invoice_number || "—"}</TableCell>
                <TableCell>
                  <PurchaseMaterialsCell purchase={p} lines={lines} />
                </TableCell>
                {canViewPrices && (
                  <>
                    <TableCell className={moneyCls} data-col="subtotal">{fmtMoney(m.subtotal)}</TableCell>
                    <TableCell className={moneyCls} data-col="iva">{fmtMoney(m.iva)}</TableCell>
                    <TableCell className={moneyCls} data-col="ret">{fmtMoney(m.ret)}</TableCell>
                    <TableCell className={cn(moneyCls, "font-medium")} data-col="total">
                      {fmtMoney(m.total)}
                    </TableCell>
                  </>
                )}
                <TableCell className="whitespace-nowrap">
                  <StatusBadge status={p.status} />
                  {!counts && (
                    <div className="text-[11px] text-slate-400 mt-0.5">
                      {cancelled ? "no suma" : "no suma: sin liquidar"}
                    </div>
                  )}
                </TableCell>
              </TableRow>
            );
          })}
          {canViewPrices && (
            <TableRow data-testid="purchase-totals" className="bg-slate-50 font-semibold">
              {totals.count > 0 ? (
                <>
                  <TableCell colSpan={4}>{totalsLabel(totals)}</TableCell>
                  <TableCell className={money} data-col="subtotal">{fmtMoney(totals.subtotal)}</TableCell>
                  <TableCell className={money} data-col="iva">{fmtMoney(totals.iva)}</TableCell>
                  <TableCell className={money} data-col="ret">{fmtMoney(totals.ret)}</TableCell>
                  <TableCell className={money} data-col="total">{fmtMoney(totals.total)}</TableCell>
                  <TableCell />
                </>
              ) : (
                <TableCell colSpan={9} className="text-slate-500 font-medium">
                  Sin compras liquidadas
                </TableCell>
              )}
            </TableRow>
          )}
        </TableBody>
      </Table>
    </div>
  );
}

/** Los mismos totales de la tabla, para el celular (D5). */
function PurchasesTotalsCard({ totals }: { totals: PurchaseTotals }) {
  return (
    <div
      data-testid="purchase-totals-card"
      className="md:hidden mt-3 rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm space-y-1"
    >
      {totals.count === 0 ? (
        <div className="text-slate-500 font-medium">Sin compras liquidadas</div>
      ) : (
        <>
          <div className="font-semibold">{totalsLabel(totals)}</div>
          <div className="flex justify-between gap-3">
            <span className="text-slate-500">Subtotal</span>
            <span className="tabular-nums" data-col="subtotal">{fmtMoney(totals.subtotal)}</span>
          </div>
          <div className="flex justify-between gap-3">
            <span className="text-slate-500">IVA</span>
            <span className="tabular-nums" data-col="iva">{fmtMoney(totals.iva)}</span>
          </div>
          <div className="flex justify-between gap-3">
            <span className="text-slate-500">Retenciones</span>
            <span className="tabular-nums" data-col="ret">{fmtMoney(totals.ret)}</span>
          </div>
          <div className="flex justify-between gap-3 font-semibold">
            <span>Total al proveedor</span>
            <span className="tabular-nums" data-col="total">{fmtMoney(totals.total)}</span>
          </div>
        </>
      )}
    </div>
  );
}

export default function InboundDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const handleBack = useReturnToBack(ROUTES.INBOUND);
  const { hasPermission, unscoped, collectorScope } = usePermissions();
  // v1.6 §5.6/§8: con alcance, una compra de un proveedor fuera de su alcance
  // se pinta SIN link (le daría 404) y con una nota que dice qué pedir.
  // Mientras carga la lista se pinta como hoy (el 404 del servidor es la red).
  const scopeSupplierIds = useScopeSupplierIds(collectorScope !== null);
  const outOfScope = (supplierId: string | null | undefined) =>
    !!supplierId && !!scopeSupplierIds && !scopeSupplierIds.has(supplierId);
  const canEdit = hasPermission("purchases.edit");
  const canCancel = hasPermission("purchases.cancel");
  const canConfirm = hasPermission("purchases.liquidate");
  const canReview = hasPermission("purchases.review");
  const canViewPrices = hasPermission("purchases.view_prices");

  const { data: order, isLoading } = useInboundOrder(id!);
  const annulOrder = useAnnulInboundOrder();
  const reviewOrder = useReviewInboundOrder();
  const unliquidateOrder = useUnliquidateInboundOrder();
  const reopenOrder = useReopenInboundOrder();
  const [closeOpen, setCloseOpen] = useState(false);
  const [reopenOpen, setReopenOpen] = useState(false);
  const [annulOpen, setAnnulOpen] = useState(false);
  const [annulReason, setAnnulReason] = useState("");
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [reviewOpen, setReviewOpen] = useState(false);
  const [unliquidateOpen, setUnliquidateOpen] = useState(false);

  // B.2: kg estimados client-side para drafts (los definitivos nacen al confirmar)
  // Alcance de recolector (plan §8): las formulas (kg estimados de Willard)
  // estan fuera de su lista blanca. Sin alcance, como hoy.
  const { data: formulasData } = useCurrentFormulas(undefined, unscoped);
  const formulas = formulasData?.items ?? [];
  const { data: profilesData } = useKgProfiles();

  if (isLoading) return <div className="p-8 text-center text-slate-500">Cargando...</div>;
  if (!order) return <div className="p-8 text-center text-slate-500">Entrada no encontrada</div>;

  const isWillard = WILLARD_INBOUND_TYPES.includes(order.inbound_type);
  const isPurchaseType = PURCHASE_INBOUND_TYPES.includes(order.inbound_type);
  const isDraft = order.status === "draft";
  const isReviewed = order.display_status === "reviewed";
  const isLiquidated = order.display_status === "liquidated";
  const isRegistered = order.display_status === "registered";
  const isClosed = order.display_status === "closed";
  // #93: legacy 1:1 (ciclos B-D) — la fila vieja tiene purchase_id y su cara
  // financiera se maneja en la compra derivada, no con el reparto nuevo
  const isLegacy = isPurchaseType && !!order.purchase_id;
  // Documentos de control: TODAS sus lineas son de control -> se cierra sin
  // valor en vez de liquidarse (la marca se lee al momento, R2).
  const isControlOnly = isPurchaseType && !isLegacy && order.is_control_only;
  const controlLineCount = order.lines.filter((l) => l.is_control).length;
  // Los kg de plomo NACEN al liquidar: hasta entonces se muestra el estimado
  // con la fórmula vigente. Antes se condicionaba a `isDraft`, pero al meter
  // la revisión de Willard apareció un estado intermedio donde ya no era draft
  // y los kg todavía no existían — el estimado se borraba justo en Revisada,
  // que es cuando el revisor lo está mirando para certificar.
  const showsEstimatedKg = isWillard && (isRegistered || isReviewed);
  // plan-sac-factor-willard D7: el factor que usó cada línea liquidada. Solo
  // si escogió una alternativa o si su material tiene factores de Willard; el
  // % sale de la respuesta (snapshot del kg), no de la fórmula de hoy.
  // D7 (O1 de QA 1): nombre y % salen los DOS del snapshot del kg confirmado,
  // nunca de la formula de hoy. Sin factores alternativos al liquidar no hay
  // nombre y no se pinta nada (no hubo nada que escoger).
  const factorUsed = (line: InboundOrderLineResponse): string | null => {
    const name = line.lead_factor_label_applied;
    if (!name || line.lead_percentage_applied == null) return null;
    return `${name} · ${pctText(num(line.lead_percentage_applied))}`;
  };
  const estimatedTotalKg = showsEstimatedKg
    ? order.lines.reduce((acc, l) => acc + (estimateKgLead(formulas, l.material_id, l.quantity) ?? 0), 0)
    : null;
  // Orden del formato en papel «Materiales recolectados» en TODOS los
  // estados (plan-sac-orden-formato-materiales §3): con la captura como el
  // papel, el orden que ve el pesador ya es ese. Lo que no esta en el formato
  // va al final, alfabetico (la regla de 0862891 queda como desempate).
  // `sortByFormOrder` devuelve una copia: `order.lines` es del cache.
  const displayLines = sortByFormOrder(order.lines, formOrderMap(profilesData?.items));
  const purchaseTotal = isPurchaseType
    ? order.lines.reduce((acc, l) => acc + l.quantity * (l.unit_price ?? 0), 0)
    : 0;
  // O1 de Daniel: solo suman las compras LIQUIDADAS (`countsAsLiquidated`);
  // una Entrada desliquidada no muestra «Total Liquidado» hasta reliquidar.
  // La misma suma alimenta la fila de totales de la tabla y la tarjeta móvil.
  const totals = liquidatedTotals(order.purchases);
  // Vigentes por slot (como antes); las canceladas al final
  const sortedPurchases = [...order.purchases].sort(
    (a, b) =>
      Number(a.status === "cancelled") - Number(b.status === "cancelled") ||
      (a.purchase_slot ?? 0) - (b.purchase_slot ?? 0) ||
      a.purchase_number - b.purchase_number
  );
  // Descuadre neto que llegó a resultados (solo ajustes vigentes: los
  // anulados ya no cuentan, igual que en el P&L)
  const discrepancyAdjustments = (order.discrepancy_adjustments ?? []).filter(
    (a) => a.status === "confirmed"
  );
  const discrepancyNet = discrepancyAdjustments.reduce(
    (acc, a) => acc + Number(a.total_value), 0
  );

  const goLiquidateEntrada = () => {
    navigate(buildRoute(ROUTES.INBOUND_LIQUIDATE, { id: order.id }));
  };

  const goLiquidateLegacyPurchase = () => {
    if (!order.purchase_id) return;
    navigate(
      `/purchases/${order.purchase_id}/liquidate?returnTo=${encodeURIComponent(`/inbound/${order.id}`)}`
    );
  };

  const confirmAnnul = () => {
    if (!annulReason.trim()) return;
    annulOrder.mutate(
      { id: order.id, reason: annulReason.trim() },
      { onSuccess: () => { setAnnulOpen(false); setAnnulReason(""); } }
    );
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title={`Entrada #${order.order_number}`}
        description={
          // C1 de QA 2: el subtitulo dice lo mismo que el badge de Tipo
          isControlOnly ? "Control" : (INBOUND_TYPE_LABELS[order.inbound_type] ?? order.inbound_type)
        }
      >
        <Button variant="outline" onClick={handleBack}>
          <ArrowLeft className="h-4 w-4 mr-2" />
          Volver
        </Button>
        {/* Cerrada sin valor: terminal (lineas y fecha piden reabrirla) */}
        {canEdit && order.status !== "annulled" && !isLiquidated && !isClosed && (
          <Button
            variant="outline"
            onClick={() => navigate(buildRoute(ROUTES.INBOUND_EDIT, { id: order.id }))}
          >
            <Pencil className="h-4 w-4 mr-2" />
            Editar
          </Button>
        )}
        {/* #93 D10: registrada -> revisada (permiso propio). Ítem 4: Willard
            también pasa por revisión — el revisor certifica el peso de
            báscula, que es la carta con la que Hugo renegocia el kg/unidad
            con Willard. La compra legacy 1:1 conserva su flujo viejo. */}
        {/* Documentos de control v1.3 (§11.4): una solo de control pasa de
            Registrada a Cerrada sin valor, sin revisión */}
        {isRegistered && !isLegacy && canReview && !isControlOnly && (
          <Button
            onClick={() => setReviewOpen(true)}
            className="bg-sky-600 hover:bg-sky-700"
          >
            <ClipboardCheck className="h-4 w-4 mr-2" />
            Marcar Revisada
          </Button>
        )}
        {/* Liquidar: willard REVISADA -> confirm; compra revisada -> reparto;
            legacy 1:1 -> liquidacion de la compra derivada */}
        {/* Documentos de control: «Cerrar sin valor» reemplaza a Liquidar */}
        {/* Cerrar y reabrir no están en la lista del alcance de recolector (#129) */}
        {canConfirm && unscoped && isControlOnly && (isRegistered || isReviewed) && (
          <Button onClick={() => setCloseOpen(true)} className="bg-slate-700 hover:bg-slate-800">
            <Archive className="h-4 w-4 mr-2" />
            Cerrar sin valor
          </Button>
        )}
        {isClosed && canCancel && unscoped && (
          <Button variant="outline" onClick={() => setReopenOpen(true)}>
            <RotateCcw className="h-4 w-4 mr-2" />
            Reabrir
          </Button>
        )}
        {canConfirm && !isControlOnly && (
          (isWillard && isReviewed) ? (
            <Button onClick={() => setConfirmOpen(true)} className="bg-emerald-600 hover:bg-emerald-700">
              <CheckCircle2 className="h-4 w-4 mr-2" />
              Liquidar
            </Button>
          ) : isLegacy && isRegistered ? (
            <Button onClick={goLiquidateLegacyPurchase} className="bg-emerald-600 hover:bg-emerald-700">
              <CheckCircle2 className="h-4 w-4 mr-2" />
              Liquidar
            </Button>
          ) : isPurchaseType && !isLegacy && isReviewed ? (
            <Button onClick={goLiquidateEntrada} className="bg-emerald-600 hover:bg-emerald-700">
              <CheckCircle2 className="h-4 w-4 mr-2" />
              Liquidar
            </Button>
          ) : null
        )}
        {/* #93 D20: revertir la liquidacion (vuelve a Revisada, conserva reparto) */}
        {isLiquidated && isPurchaseType && !isLegacy && canCancel && (
          <Button variant="outline" onClick={() => setUnliquidateOpen(true)}>
            <Undo2 className="h-4 w-4 mr-2" />
            Revertir Liquidación
          </Button>
        )}
        {canCancel && order.status !== "annulled" && order.display_status !== "annulled" && (
          <Button variant="destructive" onClick={() => setAnnulOpen(true)}>
            Anular
          </Button>
        )}
      </PageHeader>

      {isRegistered && (
        <div className="flex items-start gap-2.5 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
          <Clock className="h-4 w-4 mt-0.5 shrink-0" />
          <div>
            <span className="font-semibold">Registrada — pendiente.</span>{" "}
            {isWillard
              ? "El siguiente paso es la revisión: alguien con permiso certifica el peso de báscula y la marca Revisada. Al liquidar, el material entra al inventario y mueve el libro kg — los kg mostrados son estimados con la fórmula vigente."
              : isLegacy
                ? "Al liquidar se confirman los precios y la compra tiene efecto financiero (saldo del proveedor, costo promedio, retenciones)."
                : isControlOnly
                  ? "Todos sus materiales son de control: no se liquida, se cierra sin valor. Queda registrada con su número y su remisión."
                  : "El siguiente paso es la revisión: alguien con permiso valida lo pesado y la marca Revisada. Después se liquida con el reparto de proveedores."}
          </div>
        </div>
      )}

      {isReviewed && (
        <div className="flex items-start gap-2.5 rounded-lg border border-sky-200 bg-sky-50 px-4 py-3 text-sm text-sky-800">
          <ClipboardCheck className="h-4 w-4 mt-0.5 shrink-0" />
          <div>
            <span className="font-semibold">
              {isControlOnly ? "Revisada — lista para cerrar sin valor." : "Revisada — lista para liquidar."}
            </span>{" "}
            {isControlOnly
              ? "Todos sus materiales son de control: al cerrarla no nacen compras ni se mueve inventario."
              : isWillard
              ? "Al liquidar, el material entra al inventario al costo promedio vigente y se emite la deuda en kg de plomo con Willard."
              : "Al liquidar se reparte cada material entre sus proveedores: nacen las compras, se valora el descuadre contra lo pesado y se causa la comisión del recolector."}
          </div>
        </div>
      )}

      {isClosed && (
        <div className="flex items-start gap-2.5 rounded-lg border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-700">
          <Archive className="h-4 w-4 mt-0.5 shrink-0" />
          <div>
            <span className="font-semibold">Cerrada sin valor.</span>{" "}
            Sus materiales son de control: la entrada conserva su número y su
            remisión, pero no creó compras ni movió inventario ni plata.
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Informacion general */}
        <Card className={`shadow-sm ${statusBorderMap[order.display_status] ?? ""}`}>
          <CardHeader>
            <CardTitle className="text-sm font-semibold uppercase tracking-wider text-slate-500">Información General</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            <InfoRow label="Estado" value={<EntradaStatusBadge status={order.display_status} />} />
            <InfoRow label="Fecha" value={formatDate(order.date)} />
            <InfoRow label="Tipo" value={<EntradaTypeBadge order={order} />} />
            {/* #93: en tipo compra el proveedor vive en el reparto (tarjetas
                de la cara financiera) — la cabecera no tiene tercero */}
            {(isWillard || isLegacy || order.third_party_name) && (
              <InfoRow label="Tercero" value={order.third_party_name ?? "—"} long />
            )}
            <InfoRow label="Sede" value={order.warehouse_name ?? "—"} long />
            {order.remission_number && (
              <InfoRow label="N° Remisión" value={order.remission_number} long />
            )}
            {order.invoice_number && (
              <InfoRow label="N° Factura" value={order.invoice_number} long />
            )}
            {/* Ciclo C (C-5): quien hizo que — capa de confianza del flujo a 2 personas */}
            {order.created_by_name && (
              <InfoRow
                label="Registrada por"
                value={
                  <AuditValue
                    name={order.created_by_name}
                    date={formatDate(order.created_at)}
                    time={formatTime(order.created_at)}
                  />
                }
                long
              />
            )}
            {/* #93 D10: auditoria de la revision */}
            {order.reviewed_by_name && order.display_status !== "annulled" && (
              <InfoRow
                label="Revisada por"
                value={
                  <AuditValue
                    name={order.reviewed_by_name}
                    date={order.reviewed_at ? formatDate(order.reviewed_at) : null}
                    time={order.reviewed_at ? formatTime(order.reviewed_at) : null}
                  />
                }
                long
              />
            )}
            {order.liquidated_by_name && order.display_status !== "annulled" && (
              <InfoRow
                label="Liquidada por"
                // liquidated_at es fecha de NEGOCIO → formatDate (#87); la hora
                // real del clic vive aparte en liquidated_ts (null en entradas
                // liquidadas antes de que existiera la columna: sale solo la fecha)
                value={
                  <AuditValue
                    name={order.liquidated_by_name}
                    date={order.liquidated_at ? formatDate(order.liquidated_at) : null}
                    time={order.liquidated_ts ? formatTime(order.liquidated_ts) : null}
                  />
                }
                long
              />
            )}
            {isClosed && (order.closed_by_name || order.closed_at) && (
              <InfoRow
                label="Cerrada sin valor por"
                value={
                  <AuditValue
                    name={order.closed_by_name ?? "—"}
                    date={order.closed_at ? formatDate(order.closed_at) : null}
                    time={order.closed_at ? formatTime(order.closed_at) : null}
                  />
                }
                long
              />
            )}
            {order.display_status === "annulled" && (order.annulled_by_name || order.annulled_at) && (
              <InfoRow
                label="Anulada por"
                value={
                  <AuditValue
                    name={order.annulled_by_name ?? "—"}
                    date={order.annulled_at ? formatDate(order.annulled_at) : null}
                    time={order.annulled_at ? formatTime(order.annulled_at) : null}
                  />
                }
                long
              />
            )}
          </CardContent>
        </Card>

        {/* Transporte + Willard */}
        <Card className="shadow-sm">
          <CardHeader>
            <CardTitle className="text-sm font-semibold uppercase tracking-wider text-slate-500">Transporte y Detalle</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            <InfoRow label="Conductor" value={order.driver_name ?? "—"} long />
            <InfoRow label="Vehículo" value={order.vehicle_plate ? order.vehicle_plate.toUpperCase() : "—"} />
            {order.collector_name && (
              <InfoRow
                label="Recolector"
                value={
                  order.collector_id ? (
                    <ThirdPartyLink id={order.collector_id}>{order.collector_name}</ThirdPartyLink>
                  ) : (
                    order.collector_name
                  )
                }
                long
              />
            )}
            {isWillard && (
              <InfoRow
                label="Centro Willard"
                value={order.willard_distribution_center ? willardCenterLabel(order.willard_distribution_center) : "—"}
              />
            )}
            {order.notes && <InfoRow label="Notas" value={order.notes} long />}
          </CardContent>
        </Card>

        {/* Efectos */}
        <Card className="shadow-sm">
          <CardHeader>
            <CardTitle className="text-sm font-semibold uppercase tracking-wider text-slate-500">Efectos</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            {isWillard && (
              <InfoRow
                label={showsEstimatedKg ? "Kg Plomo (estimado)" : "Total Kg Plomo"}
                value={
                  showsEstimatedKg ? (
                    <span className="font-semibold tabular-nums text-amber-700">
                      {estimatedTotalKg != null && estimatedTotalKg > 0
                        ? `~${formatWeight(estimatedTotalKg)}`
                        : "—"}
                    </span>
                  ) : (
                    <span className="font-semibold tabular-nums text-emerald-700">
                      {order.total_kg_lead != null ? `+${formatWeight(order.total_kg_lead)}` : "—"}
                    </span>
                  )
                }
              />
            )}
            {isPurchaseType && (
              <>
                {canViewPrices && purchaseTotal > 0 && (
                  <InfoRow
                    label="Total Capturado (ref.)"
                    value={
                      <span className="font-semibold tabular-nums">{formatCurrency(purchaseTotal)}</span>
                    }
                  />
                )}
                {canViewPrices && totals.count > 0 && (
                  <InfoRow
                    label="Total Liquidado"
                    value={
                      <span className="font-semibold tabular-nums">{fmtMoney(totals.subtotal)}</span>
                    }
                  />
                )}
                {/* O3: solo si hay IVA — si no, repetiría el mismo número */}
                {canViewPrices && totals.count > 0 && totals.iva > 0 && (
                  <InfoRow
                    label="Total con IVA"
                    value={
                      <span className="font-semibold tabular-nums">
                        {fmtMoney(totals.subtotal + totals.iva)}
                      </span>
                    }
                  />
                )}
                {/* Entrada #142: «Total Liquidado» es el subtotal y no dice que
                    hubo retención. Con retenciones, el neto que queda al
                    proveedor va debajo; sin ellas, la tarjeta no cambia. */}
                {canViewPrices && totals.count > 0 && totals.ret > 0 && (
                  <>
                    <InfoRow
                      label="Retenciones"
                      value={
                        <span className="font-semibold tabular-nums">{fmtMoney(-totals.ret)}</span>
                      }
                    />
                    <InfoRow
                      label="Total al proveedor"
                      value={
                        <span className="font-semibold tabular-nums">{fmtMoney(totals.total)}</span>
                      }
                    />
                  </>
                )}
                {/* Legacy 1:1 (ciclos B-D): la cara financiera es la derivada */}
                {isLegacy && (
                  <>
                    <InfoRow
                      label="Cara Financiera"
                      value={
                        order.purchase_id && outOfScope(order.third_party_id) ? (
                          `Compra #${order.purchase_number}`
                        ) : order.purchase_id ? (
                          <PurchaseLink id={order.purchase_id}>Ver compra #{order.purchase_number}</PurchaseLink>
                        ) : (
                          "—"
                        )
                      }
                    />
                    {order.purchase_status && (
                      <InfoRow label="Estado Compra" value={<StatusBadge status={order.purchase_status} />} />
                    )}
                  </>
                )}
                {order.collector_commission_total != null && canViewPrices && (
                  <InfoRow
                    label="Comisión Recolección"
                    value={
                      <span className="font-semibold tabular-nums">
                        {formatCurrency(order.collector_commission_total)}
                        <span className="ml-1.5 font-normal text-xs text-slate-500">(gasto)</span>
                      </span>
                    }
                  />
                )}
                {/* La plata del descuadre: sin esto solo se veía yendo a
                    Reportes o a Inventario (hallazgo de pruebas de usuario) */}
                {canViewPrices && discrepancyNet !== 0 && (
                  <InfoRow
                    label="Descuadre a Resultados"
                    value={
                      <span
                        className={cn(
                          "font-semibold tabular-nums",
                          discrepancyNet > 0 ? "text-emerald-700" : "text-rose-700"
                        )}
                      >
                        {discrepancyNet > 0 ? "+" : ""}
                        {formatCurrency(discrepancyNet)}
                        <span className="ml-1.5 font-normal text-xs text-slate-500">
                          ({discrepancyNet > 0 ? "ganancia" : "pérdida"})
                        </span>
                      </span>
                    }
                  />
                )}
              </>
            )}
            {order.status === "annulled" && (
              <>
                <InfoRow
                  label="Anulada"
                  // annulled_at es un instante real (#87): lleva hora
                  value={
                    <AuditValue
                      date={order.annulled_at ? formatDate(order.annulled_at) : null}
                      time={order.annulled_at ? formatTime(order.annulled_at) : null}
                    />
                  }
                />
                <InfoRow label="Motivo" value={order.annulled_reason ?? "—"} long />
              </>
            )}
          </CardContent>
        </Card>
      </div>

      {/* #93: cara financiera — una tarjeta por COMPRA del reparto (reparto
          por compra: un proveedor puede tener dos, Q-65). Orden por slot. */}
      {isPurchaseType && order.purchases.length > 0 && (
        <Card className="shadow-sm">
          <CardHeader>
            <CardTitle className="text-sm font-semibold uppercase tracking-wider text-slate-500">
              Compras ({order.purchases.length})
            </CardTitle>
          </CardHeader>
          <CardContent>
            {/* Desde md: tabla (con 10 compras las tarjetas no se leen) */}
            <PurchasesTable
              purchases={sortedPurchases}
              lines={order.lines}
              totals={totals}
              canViewPrices={canViewPrices}
              outOfScope={outOfScope}
              collectorName={order.collector_name}
            />
            {/* Bajo md: las tarjetas de siempre + una de totales */}
            <div className="md:hidden grid grid-cols-1 sm:grid-cols-2 gap-3">
              {sortedPurchases
                .map((p) => {
                // IVA vivo de la compra (§4): el proveedor queda con +IVA
                const { iva, ret, total } = purchaseMoney(p);
                return (
                <div
                  data-testid="purchase-card"
                  data-purchase-number={p.purchase_number}
                  key={p.purchase_id}
                  className={`rounded-lg border p-3 space-y-1 ${
                    p.status === "cancelled" ? "border-rose-200 bg-rose-50/50 opacity-70" : "border-slate-200"
                  }`}
                >
                  {p.purchase_slot != null && (
                    <div className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">
                      Compra {p.purchase_slot}
                    </div>
                  )}
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-medium text-sm truncate">
                      {outOfScope(p.supplier_id) ? (
                        p.supplier_name ?? "—"
                      ) : (
                        <ThirdPartyLink id={p.supplier_id}>{p.supplier_name ?? "—"}</ThirdPartyLink>
                      )}
                    </span>
                    <StatusBadge status={p.status} />
                  </div>
                  <div className="flex items-center justify-between gap-2 text-sm">
                    {outOfScope(p.supplier_id) ? (
                      <span>Compra #{p.purchase_number}</span>
                    ) : (
                      <PurchaseLink id={p.purchase_id}>Compra #{p.purchase_number}</PurchaseLink>
                    )}
                    {canViewPrices && (
                      <span className="font-semibold tabular-nums">{fmtMoney(p.total_amount)}</span>
                    )}
                  </div>
                  {p.invoice_number && (
                    <div className="text-xs text-slate-500">Factura: {p.invoice_number}</div>
                  )}
                  {(ret > 0 || iva > 0) && canViewPrices && (
                    <div className="text-xs text-slate-500">
                      {iva > 0 && <>IVA: {fmtMoney(iva)} · </>}
                      {ret > 0 && <>Retenciones: {fmtMoney(ret)} · </>}
                      Total al proveedor:{" "}
                      <span data-testid="card-total" className="font-medium text-slate-700">
                        {fmtMoney(total)}
                      </span>
                    </div>
                  )}
                  {outOfScope(p.supplier_id) && (
                    <div className="text-xs text-amber-700">
                      Proveedor sin la marca de {order.collector_name ?? "tu recolector"}: pídele a SAC
                      que lo marque en Terceros.
                    </div>
                  )}
                </div>
                );
              })}
            </div>
            {canViewPrices && <PurchasesTotalsCard totals={totals} />}
          </CardContent>
        </Card>
      )}

      {/* #93 D7: los ajustes del descuadre — la plata que la Entrada mandó a
          resultados, con link a cada ajuste (antes solo se veía en Reportes) */}
      {discrepancyAdjustments.length > 0 && canViewPrices && (
        <Card className="shadow-sm">
          <CardHeader>
            <CardTitle className="text-sm font-semibold uppercase tracking-wider text-slate-500">
              Descuadre a Resultados ({discrepancyAdjustments.length})
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {discrepancyAdjustments.map((a) => (
                <div
                  key={a.adjustment_id}
                  className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-1 sm:gap-3 text-sm border-b border-slate-100 last:border-0 pb-2 last:pb-0"
                >
                  <div className="flex items-center gap-2 min-w-0">
                    <AdjustmentLink id={a.adjustment_id}>
                      {a.material_code ?? "—"}
                    </AdjustmentLink>
                    <span className="text-slate-500 text-xs">
                      {a.adjustment_type === "increase" ? "sobrante" : "faltante"}{" "}
                      {formatWeight(a.quantity, a.material_unit)}
                      {a.unit_cost != null && ` × ${formatCurrency(a.unit_cost)}`}
                    </span>
                  </div>
                  <span
                    className={cn(
                      "font-semibold tabular-nums shrink-0",
                      a.total_value > 0 ? "text-emerald-700" : "text-rose-700"
                    )}
                  >
                    {a.total_value > 0 ? "+" : ""}
                    {formatCurrency(a.total_value)}
                  </span>
                </div>
              ))}
              <div className="flex justify-between pt-1 text-sm font-semibold">
                <span className="text-slate-500">Neto</span>
                <span
                  className={cn(
                    "tabular-nums",
                    discrepancyNet > 0 ? "text-emerald-700" : "text-rose-700"
                  )}
                >
                  {discrepancyNet > 0 ? "+" : ""}
                  {formatCurrency(discrepancyNet)}
                </span>
              </div>
            </div>
            <p className="mt-3 text-xs text-slate-500">
              Diferencia entre lo pesado y lo repartido, valorada al precio de
              referencia. Entra al inventario y al Estado de Resultados como
              ganancia o pérdida. Para deshacerlo, use «Revertir Liquidación».
            </p>
          </CardContent>
        </Card>
      )}

      {/* Lineas */}
      <Card className="shadow-sm">
        <CardHeader>
          <CardTitle className="text-sm font-semibold uppercase tracking-wider text-slate-500">Líneas</CardTitle>
          {/* v1.3.1: habla en futuro — en una liquidada antes de marcar el
              material sería falsa, así que solo en Registrada y Revisada */}
          {isPurchaseType && !isControlOnly && controlLineCount > 0 && (isRegistered || isReviewed) && (
            <p className="text-xs text-slate-500">
              {controlLineCount === 1
                ? "1 línea de control no se liquida"
                : `${controlLineCount} líneas de control no se liquidan`}{" "}
              (se registra solo por el consecutivo).
            </p>
          )}
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto -mx-3 sm:mx-0">
            <Table className="min-w-[640px]">
              <TableHeader>
                <TableRow>
                  <TableHead>Material</TableHead>
                  <TableHead className="text-right">Cantidad</TableHead>
                  {isPurchaseType && <TableHead className="text-right">Precio (ref.)</TableHead>}
                  {isPurchaseType && !isLegacy && (
                    <>
                      <TableHead className="text-right">Repartido</TableHead>
                      <TableHead className="text-right">Descuadre</TableHead>
                    </>
                  )}
                  <TableHead className="text-right">Peso Báscula</TableHead>
                  {isWillard && <TableHead className="text-right">Kg Plomo</TableHead>}
                  <TableHead>Notas</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {displayLines.map((line) => {
                  const hasAllocs = line.allocations.length > 0;
                  // 🔴 El backend serializa Decimal como STRING ("0.0000")
                  // aunque el tipo TS diga number: `disc === 0` daba false y el
                  // cuadre exacto —el resultado BUENO— se pintaba de rojo como
                  // si fuera un faltante. Misma trampa de #93, encontrada
                  // abriendo la pantalla.
                  const disc = line.discrepancy != null ? num(line.discrepancy) : null;
                  return (
                    <Fragment key={line.id}>
                      <TableRow>
                        <TableCell>
                          <span className="font-medium">{line.material_code}</span>
                          <span className="text-slate-500"> — {line.material_name}</span>
                          {line.is_control && (
                            <span className="ml-2 text-xs text-slate-500">(control)</span>
                          )}
                          {line.unallocated_intentional && (
                            <span className="ml-2 text-xs text-slate-400">(sin proveedor, intencional)</span>
                          )}
                        </TableCell>
                        <TableCell className="text-right tabular-nums">
                          {formatWeight(line.quantity, line.material_unit || "kg")}
                        </TableCell>
                        {isPurchaseType && (
                          <TableCell className="text-right tabular-nums">
                            {line.reference_unit_price != null
                              ? formatCurrency(line.reference_unit_price)
                              : line.unit_price != null
                                ? formatCurrency(line.unit_price)
                                : "—"}
                          </TableCell>
                        )}
                        {isPurchaseType && !isLegacy && (
                          <>
                            <TableCell className="text-right tabular-nums">
                              {line.allocated_quantity != null
                                ? formatWeight(line.allocated_quantity, line.material_unit || "kg")
                                : "—"}
                            </TableCell>
                            <TableCell className="text-right">
                              {disc == null || (!hasAllocs && disc === 0) ? (
                                <span className="text-slate-400">—</span>
                              ) : disc === 0 ? (
                                <span className="text-emerald-600 tabular-nums font-medium">
                                  0 {line.material_unit || "kg"}
                                </span>
                              ) : (
                                <span
                                  className={`tabular-nums font-medium ${disc > 0 ? "text-emerald-700" : "text-rose-700"}`}
                                  title={disc > 0 ? "Sobrante (entra como ganancia)" : "Faltante (sale como pérdida)"}
                                >
                                  {disc > 0 ? "+" : ""}
                                  {formatWeight(disc, line.material_unit || "kg")}
                                </span>
                              )}
                            </TableCell>
                          </>
                        )}
                        <TableCell className="text-right tabular-nums">
                          {line.scale_weight_kg != null ? formatWeight(line.scale_weight_kg) : "—"}
                        </TableCell>
                        {isWillard && (
                          <TableCell className="text-right">
                            {showsEstimatedKg ? (
                              <span className="font-medium tabular-nums text-amber-700">
                                {(() => {
                                  const est = estimateKgLead(formulas, line.material_id, line.quantity);
                                  return est != null ? `~${formatWeight(est)}` : "—";
                                })()}
                              </span>
                            ) : (
                              <>
                                <span className="font-medium tabular-nums text-emerald-700">
                                  {line.kg_lead != null ? `+${formatWeight(line.kg_lead)}` : "—"}
                                </span>
                                {factorUsed(line) && (
                                  <span className="block text-xs text-slate-500" data-testid="factor-usado">
                                    {factorUsed(line)}
                                  </span>
                                )}
                              </>
                            )}
                          </TableCell>
                        )}
                        <TableCell className="text-sm text-slate-500 max-w-[220px]">
                          <span className="truncate block">{line.quality_notes ?? "—"}</span>
                        </TableCell>
                      </TableRow>
                      {/* #93: el reparto de la linea — proveedor x cantidad x precio */}
                      {hasAllocs && (
                        <TableRow className="bg-slate-50/60 hover:bg-slate-50/60">
                          <TableCell colSpan={isWillard ? 5 : isLegacy ? 5 : 7} className="py-2">
                            <div className="pl-4 space-y-0.5">
                              {[...line.allocations]
                                .sort((x, y) => x.purchase_slot - y.purchase_slot)
                                .map((a) => (
                                <div key={a.id} className="text-xs text-slate-600 flex flex-wrap gap-x-2">
                                  <span className="font-medium">
                                    <span className="text-slate-400 font-normal">Compra {a.purchase_slot} · </span>
                                    {a.third_party_name ?? "—"}
                                  </span>
                                  <span className="tabular-nums">
                                    {formatWeight(a.quantity, line.material_unit || "kg")}
                                    {canViewPrices ? ` × ${fmtMoney(a.unit_price)}` : ""}
                                  </span>
                                  {/* La trazabilidad que pidió Hugo: si se
                                      liquidó por peso, el documento dice
                                      cuántos kg y a qué $/kg — no solo el
                                      unitario derivado. Se LEE lo persistido,
                                      no se re-deriva de la línea (que pudo
                                      editarse después). */}
                                  {canViewPrices && a.price_per_kg != null && a.weight_kg_used != null && (
                                    <span className="text-slate-400 tabular-nums">
                                      ({formatWeight(num(a.weight_kg_used), "kg")} × {fmtMoney(num(a.price_per_kg))})
                                    </span>
                                  )}
                                  {a.invoice_number && (
                                    <span className="text-slate-400">Fact. {a.invoice_number}</span>
                                  )}
                                </div>
                              ))}
                            </div>
                          </TableCell>
                        </TableRow>
                      )}
                    </Fragment>
                  );
                })}
              </TableBody>
            </Table>
          </div>
          {isWillard && order.total_kg_lead != null && (
            <div className="bg-slate-50 rounded-lg p-3 mt-3 flex justify-end">
              <span className="text-base font-bold tabular-nums text-emerald-700">
                Total: +{formatWeight(order.total_kg_lead)}
              </span>
            </div>
          )}
          {showsEstimatedKg && estimatedTotalKg != null && estimatedTotalKg > 0 && (
            <div className="bg-amber-50 rounded-lg p-3 mt-3 flex justify-end">
              <span className="text-base font-bold tabular-nums text-amber-700">
                Estimado: ~{formatWeight(estimatedTotalKg)}
              </span>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Liquidar willard (verbo unico Ciclo C — el efecto es el confirm B.2) */}
      <WillardLiquidateDialog
        order={order}
        open={confirmOpen}
        onOpenChange={setConfirmOpen}
        description="El material entra al inventario y mueve el libro kg con la fórmula vigente (sin efecto financiero — entrada Willard). Esta acción registra los efectos definitivos."
      />

      {/* #93 D10: marcar revisada */}
      <ConfirmDialog
        open={reviewOpen}
        onOpenChange={setReviewOpen}
        title={`Marcar Revisada — Entrada #${order.order_number}`}
        description={
          isWillard
            ? "Certifica el peso de báscula de cada línea. Si a alguna le falta, la revisión se rechaza indicando el material. Después la entrada queda lista para liquidar."
            : "Confirma que lo pesado en patio fue validado — sin peso de báscula la revisión se rechaza. La entrada pasa a Revisada y queda lista para liquidar con el reparto de proveedores."
        }
        confirmLabel="Marcar Revisada"
        loading={reviewOrder.isPending}
        onConfirm={() =>
          reviewOrder.mutate(order.id, { onSuccess: () => setReviewOpen(false) })
        }
      />

      {/* #93 D20: revertir la liquidacion */}
      <ConfirmDialog
        open={unliquidateOpen}
        onOpenChange={setUnliquidateOpen}
        title={`Revertir Liquidación — Entrada #${order.order_number}`}
        description={`Se revierten las ${order.purchases.filter((p) => p.status === "liquidated").length} compras (vuelven a registradas, con sus mismos números), los ajustes de descuadre y la comisión del recolector. La entrada vuelve a Revisada CONSERVANDO el reparto — corrija lo necesario y liquide de nuevo. Un pago ya registrado queda como anticipo del proveedor (se avisa).`}
        confirmLabel="Revertir Liquidación"
        loading={unliquidateOrder.isPending}
        onConfirm={() =>
          unliquidateOrder.mutate(order.id, { onSuccess: () => setUnliquidateOpen(false) })
        }
      />

      <CloseControlDialog order={closeOpen ? order : null} onClose={() => setCloseOpen(false)} />
      <ConfirmDialog
        open={reopenOpen}
        onOpenChange={setReopenOpen}
        title={`Reabrir Entrada #${order.order_number}`}
        description={`Vuelve a ${order.reviewed_at ? "Revisada" : "Registrada"} y otra vez a la bandeja. No anula nada: el número y la remisión se conservan.`}
        confirmLabel="Reabrir"
        loading={reopenOrder.isPending}
        onConfirm={() => reopenOrder.mutate(order.id, { onSuccess: () => setReopenOpen(false) })}
      />

      {/* Anular */}
      <ConfirmDialog
        open={annulOpen}
        onOpenChange={(o) => { setAnnulOpen(o); if (!o) setAnnulReason(""); }}
        title={`Anular Entrada #${order.order_number}`}
        description={
          isWillard
            ? isDraft
              ? "La entrada está Registrada y no ha movido inventario ni libro kg — solo se marcará como anulada."
              : "Se revertirán los movimientos de inventario y de la cuenta kg. Si el stock queda negativo, se avisará sin bloquear."
            : isLiquidated
              ? `Se revierte TODO el evento: las ${order.purchases.filter((p) => p.status !== "cancelled").length} compras del reparto se cancelan, los ajustes de descuadre y la comisión se anulan, y la entrada queda Anulada. Pagos ya registrados quedan como anticipos (se avisa).`
              : "La entrada no ha tenido efectos (el reparto llega al liquidar) — solo se marcará como anulada."
        }
        confirmLabel="Anular"
        variant="destructive"
        loading={annulOrder.isPending}
        disabled={!annulReason.trim()}
        onConfirm={confirmAnnul}
      >
        <div>
          <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Razón *</Label>
          <Input
            value={annulReason}
            onChange={(e) => setAnnulReason(e.target.value)}
            maxLength={500}
            placeholder="Motivo de la anulación..."
          />
        </div>
      </ConfirmDialog>
    </div>
  );
}
