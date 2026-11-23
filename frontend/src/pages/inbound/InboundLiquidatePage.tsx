import { useEffect, useMemo, useRef, useState } from "react";
import type { FocusEvent } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import { ArrowLeft, Plus, Scale, Trash2, Truck, UserPlus, X } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { PageHeader } from "@/components/shared/PageHeader";
import { EntitySelect } from "@/components/shared/EntitySelect";
import { MoneyInput } from "@/components/shared/MoneyInput";
import { CreateSupplierDialog } from "@/components/inbound/CreateSupplierDialog";
import { usePermissions } from "@/hooks/usePermissions";
import { useInboundOrder, useLiquidateInboundOrder } from "@/hooks/useInboundOrders";
import {
  useMaterials,
  usePayableProviders,
  useRetentionRows,
  useScopeSupplierIds,
  useSuppliers,
} from "@/hooks/useMasterData";
import { retentionRowLabel } from "@/pages/treasury/RetentionsPage";
import {
  IVA_DEFAULT_RATE_PCT,
  buildRetentionPayload,
  defaultRetentionConfig,
  effAmount,
  isUsableConfig,
  ivaPayload,
  ivaRatePatch,
  newRetRow,
  pctOf,
  precargaIva,
  precargaRetentions,
  rateOutOfRange,
  rateWarning,
  rateWarningText,
  reviveDraftIvaRate,
  reviveDraftRetentions,
  staleNote,
  withAmount,
  withConfig,
  withRate,
} from "@/utils/taxRows";
import type { RetRow } from "@/utils/taxRows";
import { useCurrentTariffs, useKgProfiles } from "@/hooks/useSacConfig";
import { formOrderMap, sortByFormOrder } from "@/utils/formOrder";
import { useKgAccounts } from "@/hooks/useKgLedger";
import { useMoneyAccounts } from "@/hooks/useMasterData";
import { useOrgSettings } from "@/hooks/useOrgSettings";
import { useAuthStore } from "@/stores/authStore";
import { useSupplierPriceLookup } from "@/hooks/usePriceSuggestions";
import {
  formatCurrency,
  formatCurrencyDecimals,
  formatDateTime,
  formatWeight,
} from "@/utils/formatters";
import { buildRoute, ROUTES } from "@/utils/constants";
import { cn } from "@/utils";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type {
  InboundLiquidateLine,
  InboundOrderResponse,
  InboundPurchaseTaxes,
  InboundSupplierPayment,
  InboundSupplierRetentions,
} from "@/types/inbound-order";

/**
 * #93 — Liquidación de la Entrada. Reparto por COMPRA (plan-sac-reparto-por-compra §5).
 *
 * Lo PESADO es la verdad física (inventario); lo REPARTIDO es la verdad
 * comercial (las compras). La diferencia por material es el DESCUADRE,
 * valorado al precio de la fila (D6) con la tolerancia de la org como
 * semáforo (D8: avisa, jamás bloquea por monto).
 *
 * La pantalla es la hoja de Johana: filas = materiales (en el orden del
 * formato en papel, #121), columnas = COMPRAS, celda = cantidad. Una columna
 * es una compra, no un proveedor: el mismo proveedor puede estar en dos
 * («son dos recolecciones», Q-65). Cada columna lleva su `purchase_slot`, que
 * es IDENTIDAD — nunca se renumera (R6): una columna nueva toma max + 1 y al
 * quitar una del medio queda el hueco. Si se renumerara, al reliquidar el
 * slot 3 se compararía contra la compra del slot 2 y se perderían números.
 *
 * Precio (plan-sac-precio-por-compra-visible v1.1): cada celda muestra su
 * precio al lado de la cantidad, prellenado con el de la lista del proveedor
 * (#98) o, si no hay, con el PRECIO BASE de la fila (que es también la
 * referencia del descuadre). Escribirlo lo vuelve precio propio — unitario,
 * valor total (Q-15) o por kg (#101). Cambiar de modo NO convierte la cifra:
 * el campo nuevo queda vacío con el valor anterior como texto («antes: …»),
 * así ningún número digitado se transforma solo (hallazgo de #101: la
 * rotación por kg perdía $114,60 sobre $3.138.450).
 */

/* ------------------------------------------------------------------ */
/* Estado                                                              */
/* ------------------------------------------------------------------ */

/** Precio propio de una celda: si los tres son null, la celda usa el de la
 *  lista del proveedor (si difiere) o el de la fila. Solo uno lleno a la vez. */
interface CellState {
  quantity: number;
  unit_price: number | null;
  total_price: number | null;
  price_per_kg: number | null;
  /** «antes: $X total» — se muestra al cambiar de modo y se borra al cerrar */
  before: string | null;
}

interface LineState {
  _key: number;
  material_id: string;
  material_code: string;
  material_name: string;
  material_unit: string;
  /** cantidad pesada (0 = material que la báscula no vio, D16) */
  weighed: number;
  /** Q-13: peso de báscula certificado. Insumo del modo por kg (#101). */
  weightKg: number | null;
  isExtra: boolean;
  /** Precio de la fila: el de todas las celdas sin precio propio y la
   *  referencia con la que se valora el descuadre (D6). */
  rowPrice: number;
  rowTouched: boolean;
  unallocated: boolean;
  /** slot → celda */
  cells: Record<number, CellState>;
}

interface PurchaseCol {
  slot: number;
  third_party_id: string;
  invoice: string;
  /** Lista #98 del proveedor por material. Se carga SOLO al elegirlo: en la
   *  precarga de un reparto guardado pisaría el precio que se guardó. */
  listPrices: Record<string, number>;
  withIva: boolean;
  /** T8: el % del IVA (19 al marcar la casilla), editable */
  ivaRate: number;
  ivaAmount: number;
  ivaTouched: boolean;
  retentions: RetRow[];
  /** null = a crédito (el camino normal); "" = marcó contado sin cuenta */
  paymentAccount: string | null;
}

type OwnMode = "unit" | "total" | "kg";
type CellMode = "row" | "list" | OwnMode;

/** Plan v1.1 D1b (S-1 del Coordinador): el de la fila queda de respaldo. */
const BASE_PRICE_HINT = "se usa en las compras sin lista ni precio propio";

/** Q-66 sin respuesta: la casilla «Con IVA» nace apagada (Daniel: «IVA opcional»).
 *  T8: el % es libre; 19 es solo el valor inicial y la referencia del aviso. */
const IVA_RATE_PCT = IVA_DEFAULT_RATE_PCT;

/** Reglas 9e/9f del alcance (plan Ingrid v1.6/v1.7): el mismo texto que el
 * 422 del servidor (`RELIQUIDATE_FOREIGN_SUPPLIER` / `RELIQUIDATE_TAXES`). */
const RELIQ_FOREIGN =
  "Esta Entrada tiene una compra de un proveedor fuera de tu alcance: la vuelve a liquidar SAC";
const RELIQ_TAXES =
  "Esta Entrada tuvo retenciones o IVA en su liquidación anterior: la vuelve a liquidar SAC";

let keyCounter = 0;
const nextKey = () => ++keyCounter;

const emptyCell = (): CellState => ({
  quantity: 0,
  unit_price: null,
  total_price: null,
  price_per_kg: null,
  before: null,
});

const newCol = (slot: number, third_party_id = ""): PurchaseCol => ({
  slot,
  third_party_id,
  invoice: "",
  listPrices: {},
  withIva: false,
  ivaRate: IVA_RATE_PCT,
  ivaAmount: 0,
  ivaTouched: false,
  retentions: [],
  paymentAccount: null,
});

/* ------------------------------------------------------------------ */
/* Aritmética del precio                                               */
/* ------------------------------------------------------------------ */

/** Q-15/D8 (#120): el backend deriva el unitario a 8 decimales y re-multiplica,
 *  así que el valor total digitado vuelve exacto. La vista previa calcula
 *  igual. ⚠️ Puede diferir en 1 centavo del persistido en un empate exacto
 *  (Math.round half-up sobre float vs Decimal HALF_EVEN); con pesos no ocurre. */
const PRICE_SCALE = 1e8;
const roundPrice = (v: number): number => Math.round(v * PRICE_SCALE) / PRICE_SCALE;

/** C1 del redondeo (#120): todo valor calculado que va a un `MoneyInput`
 *  editable de 2 decimales pasa por acá; si no, el blur lo redondea solo y
 *  el total cambia por un cambio de foco. */
const toCents = (v: number): number => Math.round(v * 100) / 100;

/** El peso se pinta sin decimales en toda la app; acá los decimales aparecen
 *  SOLO cuando existen (D8: el centavo tiene que verse). */
/** Un % con hasta 4 decimales, en formato colombiano (2,5 · 0,966). */
const fmtRate = (v: number): string =>
  new Intl.NumberFormat("es-CO", { maximumFractionDigits: 4 }).format(v);

const fmtMoney = (v: number): string =>
  Math.abs(v - Math.round(v)) < 0.005 ? formatCurrency(v) : formatCurrencyDecimals(v);

/** Decimal llega como string en el JSON (#93 b): coerción en la frontera. */
const num = (v: unknown, fallback = 0): number => {
  const n = Number(v);
  return Number.isFinite(n) ? n : fallback;
};

/** Peso prorrateado de una celda: kg/unidad de la LÍNEA × cantidad. Depende
 *  solo de su propia cantidad (#101 D2). Espeja `_total_desde_kg` del backend. */
const cellWeight = (c: CellState, l: LineState): number =>
  l.weightKg && l.weighed > 0
    ? Math.round((l.weightKg / l.weighed) * c.quantity * 1000) / 1000
    : 0;

/** El modo por kg necesita con qué prorratear (#101 D4b). */
const canKg = (l: LineState) => Boolean(l.weightKg) && l.weighed > 0;

const ownMode = (c: CellState): OwnMode | null =>
  c.price_per_kg != null ? "kg" : c.total_price != null ? "total" : c.unit_price != null ? "unit" : null;

const listPriceOf = (col: PurchaseCol | undefined, l: LineState): number | null =>
  col?.listPrices[l.material_id] ?? null;

const cellMode = (c: CellState, col: PurchaseCol | undefined, l: LineState): CellMode => {
  const own = ownMode(c);
  if (own) return own;
  const lp = listPriceOf(col, l);
  return lp != null && lp !== l.rowPrice ? "list" : "row";
};

const cellUnit = (c: CellState, col: PurchaseCol | undefined, l: LineState): number => {
  switch (cellMode(c, col, l)) {
    case "kg":
      return c.quantity > 0 ? roundPrice((cellWeight(c, l) * (c.price_per_kg ?? 0)) / c.quantity) : 0;
    case "total":
      return c.quantity > 0 ? roundPrice((c.total_price ?? 0) / c.quantity) : 0;
    case "unit":
      return c.unit_price ?? 0;
    case "list":
      return listPriceOf(col, l) ?? 0;
    default:
      return l.rowPrice;
  }
};

/** Lo que la compra suma por esta celda, a centavos como `total_price` de la línea. */
const cellTotal = (c: CellState, col: PurchaseCol | undefined, l: LineState): number =>
  Math.round(c.quantity * cellUnit(c, col, l) * 100) / 100;

const cellPriced = (c: CellState, col: PurchaseCol | undefined, l: LineState): boolean => {
  const m = cellMode(c, col, l);
  if (m === "kg") return (c.price_per_kg ?? 0) > 0 && cellWeight(c, l) > 0;
  if (m === "total") return (c.total_price ?? 0) > 0;
  return cellUnit(c, col, l) > 0;
};

/** Texto del precio vigente, para «antes: …» al cambiar de modo. */
const describePrice = (c: CellState, col: PurchaseCol | undefined, l: LineState): string | null => {
  if (!cellPriced(c, col, l)) return null;
  switch (cellMode(c, col, l)) {
    case "total":
      return `${fmtMoney(c.total_price ?? 0)} total`;
    case "kg":
      return `${fmtMoney(c.price_per_kg ?? 0)}/kg`;
    default:
      return `${fmtMoney(cellUnit(c, col, l))} c/u`;
  }
};

const MODE_LABEL: Record<OwnMode, string> = {
  unit: "Unitario",
  total: "Valor total",
  kg: "Por kg",
};

const MODE_SHORT: Record<OwnMode, string> = {
  unit: "c/u",
  total: "total",
  kg: "kg",
};

/** Lo que muestra el campo de precio de la celda (plan v1.1 D2), a centavos:
 *  es contra esto que se compara el blur (C1). Sin cantidad ni precio propio,
 *  0 (el sugerido va como placeholder: una celda vacía no aparenta precio). */
const priceFieldValue = (
  c: CellState | undefined,
  col: PurchaseCol | undefined,
  l: LineState
): number => {
  if (!c) return 0;
  switch (ownMode(c)) {
    case "kg":
      return toCents(c.price_per_kg ?? 0);
    case "total":
      return toCents(c.total_price ?? 0);
    case "unit":
      return toCents(c.unit_price ?? 0);
    default:
      return c.quantity > 0 ? toCents(cellUnit(c, col, l)) : 0;
  }
};

/** `MoneyInput` reemplaza el texto al recibir el foco («1.300» → «1300») y eso
 *  borra la selección que deja el Tab: lo que se escribía se PEGABA al final
 *  (1250 sobre 1.300 daba 13.001.250). Con el precio prellenado ese es el flujo
 *  normal, así que en la celda se selecciona todo después de ese render.
 *  (MoneyInput es compartido: no se toca acá.) */
const selectOnFocus = (e: FocusEvent<HTMLElement>) => {
  const t = e.target;
  if (t instanceof HTMLInputElement) {
    requestAnimationFrame(() => {
      if (document.activeElement === t) t.select();
    });
  }
};

/** El precio que una celda usaría sin precio propio: lista del proveedor, o base. */
const suggestedUnit = (col: PurchaseCol | undefined, l: LineState): number =>
  listPriceOf(col, l) ?? l.rowPrice;

const MODE_COLOR: Record<CellMode, string> = {
  row: "text-slate-400",
  list: "text-sky-600",
  unit: "text-indigo-600",
  total: "text-indigo-600",
  kg: "text-indigo-600",
};

/* ------------------------------------------------------------------ */
/* Borrador (plan §9, Daniel 19-nov)                                   */
/* ------------------------------------------------------------------ */

/** El reparto solo se guarda al liquidar; con 10 compras un error de red
 *  perdería lo digitado. Se guarda un borrador en `localStorage` por org,
 *  usuario y Entrada. Cada lectura y escritura va con try/catch: en una
 *  ventana privada o sin espacio la pantalla funciona igual, sin borrador. */
interface Draft {
  v: 1;
  /** Firma de lo pesado: si la Entrada se editó, el borrador ya no aplica */
  sig: string;
  /** Instante del guardado (ms desde epoch, `Date.now()`), no un día de negocio */
  savedAt: number;
  lines: LineState[];
  cols: PurchaseCol[];
  collector: { enabled: boolean; tpId: string; amount: number; touched: boolean };
}

const readDraft = (key: string): Draft | null => {
  try {
    const raw = localStorage.getItem(key);
    if (!raw) return null;
    const d = JSON.parse(raw) as Draft;
    return d && d.v === 1 && Array.isArray(d.lines) && Array.isArray(d.cols) ? d : null;
  } catch {
    return null;
  }
};
const writeDraft = (key: string, d: Draft) => {
  try {
    localStorage.setItem(key, JSON.stringify(d));
  } catch {
    /* sin espacio o sin permiso: se sigue sin borrador */
  }
};
const removeDraft = (key: string) => {
  try {
    localStorage.removeItem(key);
  } catch {
    /* idem */
  }
};

/** QA C6: la firma cubre TODO lo que el borrador da por supuesto — lo
 *  pesado, el peso de báscula (la vista por kg), la referencia, el reparto
 *  guardado y el estado de las compras. Si alguien desliquidó y repartió
 *  distinto desde otro equipo, el borrador viejo ya no tapa lo nuevo. */
const orderSignature = (order: InboundOrderResponse): string =>
  [
    ...order.lines.map((l) =>
      [
        l.material_id,
        num(l.quantity),
        l.scale_weight_kg != null ? num(l.scale_weight_kg) : "-",
        l.reference_unit_price != null ? num(l.reference_unit_price) : "-",
        l.allocations
          .map((a) => `${a.id}/${a.purchase_slot}/${num(a.quantity)}`)
          .sort()
          .join(","),
      ].join(":")
    ),
    order.purchases.map((p) => `${p.purchase_id}/${p.status}`).sort().join(","),
  ].join("|");

const isObj = (v: unknown): v is Record<string, unknown> =>
  typeof v === "object" && v !== null && !Array.isArray(v);
const isNumOrNull = (v: unknown) => v === null || typeof v === "number";

/** QA C3: un borrador viene de `localStorage` y puede estar malformado (otra
 *  versión, a mano, cortado). Se valida la FORMA entera antes de aplicarlo;
 *  si algo no cuadra, lanza y el llamador lo borra y sigue con el servidor. */
function assertDraftShape(d: Draft): void {
  // Anotado `never` para que TS estreche el tipo después de cada `bad()`
  const bad: () => never = () => {
    throw new Error("borrador malformado");
  };
  // QA: un borrador viejo con `savedAt` string se descarta por forma
  if (typeof d.savedAt !== "number" || !Number.isFinite(d.savedAt)) bad();
  const c: unknown = d.collector;
  if (!isObj(c)) bad();
  if (typeof c.enabled !== "boolean" || typeof c.tpId !== "string" ||
      typeof c.amount !== "number" || typeof c.touched !== "boolean") bad();
  for (const l of d.lines as unknown[]) {
    if (!isObj(l) || typeof l._key !== "number" || typeof l.material_id !== "string" ||
        typeof l.weighed !== "number" || typeof l.rowPrice !== "number" ||
        typeof l.rowTouched !== "boolean" || typeof l.unallocated !== "boolean" ||
        typeof l.isExtra !== "boolean" || !isNumOrNull(l.weightKg) || !isObj(l.cells)) bad();
    for (const cell of Object.values(l.cells)) {
      if (!isObj(cell) || typeof cell.quantity !== "number" || !isNumOrNull(cell.unit_price) ||
          !isNumOrNull(cell.total_price) || !isNumOrNull(cell.price_per_kg)) bad();
    }
  }
  for (const col of d.cols as unknown[]) {
    if (!isObj(col) || typeof col.slot !== "number" || typeof col.third_party_id !== "string" ||
        typeof col.invoice !== "string" || !isObj(col.listPrices) ||
        typeof col.withIva !== "boolean" || typeof col.ivaAmount !== "number" ||
        // T8: un borrador de antes del cambio no trae `ivaRate`
        !(col.ivaRate === undefined || typeof col.ivaRate === "number") ||
        typeof col.ivaTouched !== "boolean" || !Array.isArray(col.retentions) ||
        !(col.paymentAccount === null || typeof col.paymentAccount === "string")) bad();
    for (const r of col.retentions as unknown[]) {
      if (!isObj(r) || typeof r._key !== "number" || typeof r.config_id !== "string" ||
          typeof r.amount !== "number" || typeof r.touched !== "boolean" ||
          // T2b: `rate` falta en un borrador de antes del cambio
          !(r.rate === undefined || typeof r.rate === "number") ||
          !(r.staleRate === undefined || isNumOrNull(r.staleRate)) ||
          !(r.staleLabel === undefined || typeof r.staleLabel === "string")) bad();
    }
  }
}

/* ------------------------------------------------------------------ */
/* Precarga                                                            */
/* ------------------------------------------------------------------ */

function initLines(order: InboundOrderResponse): LineState[] {
  return order.lines.map((l) => {
    const rowPrice = num(l.reference_unit_price ?? l.unit_price ?? 0);
    const cells: Record<number, CellState> = {};
    // Re-liquidación (D20): el reparto anterior se conserva, por SLOT
    for (const a of l.allocations) {
      const unit = num(a.unit_price);
      cells[a.purchase_slot] = {
        quantity: num(a.quantity),
        // El MODO es parte del reparto: se re-abre como se guardó
        total_price: a.total_price != null ? num(a.total_price) : null,
        price_per_kg: a.price_per_kg != null ? num(a.price_per_kg) : null,
        unit_price:
          a.total_price == null && a.price_per_kg == null && unit !== rowPrice ? unit : null,
        before: null,
      };
    }
    return {
      _key: nextKey(),
      material_id: l.material_id,
      material_code: l.material_code ?? "",
      material_name: l.material_name ?? "",
      material_unit: l.material_unit || "kg",
      weighed: num(l.quantity),
      weightKg: l.scale_weight_kg != null ? num(l.scale_weight_kg) : null,
      isExtra: false,
      rowPrice,
      rowTouched: l.reference_unit_price != null,
      unallocated: l.unallocated_intentional,
      cells,
    };
  });
}

export default function InboundLiquidatePage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const returnTo = searchParams.get("returnTo");
  const { hasPermission, collectorScope, unscoped } = usePermissions();
  const canViewPrices = hasPermission("purchases.view_prices");
  // Alcance de recolector (SAC, plan §8 y fila 9): sin cuentas kg, sin
  // retenciones ni IVA (S5) y con la comision fija (D-a: la calcula el
  // servidor). Sin alcance, la pantalla es la de siempre.
  const scoped = collectorScope !== null;
  // Regla 9e (plan v1.6): sus proveedores, activos o no. Solo con alcance.
  const scopeSupplierIds = useScopeSupplierIds(scoped);

  const { data: order, isLoading } = useInboundOrder(id!);
  const liquidateOrder = useLiquidateInboundOrder();
  const { getSetting } = useOrgSettings();

  const { data: suppliersData } = useSuppliers();
  const { data: collectorsData } = usePayableProviders();
  const { data: materialsData } = useMaterials();
  const { data: profilesData } = useKgProfiles();
  const { data: tariffsData } = useCurrentTariffs();
  const { data: kgAccountsData } = useKgAccounts(undefined, unscoped);
  const { data: accountsData } = useMoneyAccounts();

  // 🔴 TODOS los hooks van ARRIBA de los `return` condicionales de abajo: un
  // hook después de un early return rompe el orden y deja la pantalla en
  // blanco — el bloqueante (a) de #93, en esta misma página.
  const lookupSupplierPrice = useSupplierPriceLookup();

  const collectors = collectorsData?.items ?? [];
  const materials = materialsData?.items ?? [];
  const accounts = (accountsData?.items ?? []).filter((a) => a.is_active);

  // El titular de una cuenta kg NO es proveedor de compra (#80). El backend
  // lo defiende con 422; esto evita ofrecerlo.
  const suppliers = useMemo(() => {
    const holders = new Set(
      (kgAccountsData ?? [])
        .filter((a) => a.is_active && a.third_party_id)
        .map((a) => a.third_party_id as string)
    );
    return (suppliersData?.items ?? []).filter((s) => !holders.has(s.id));
  }, [suppliersData, kgAccountsData]);

  // Proveedores recién creados desde la ventana: se pintan antes de que
  // vuelva la lista invalidada
  const [createdNames, setCreatedNames] = useState<Record<string, string>>({});
  const supplierOptions = useMemo(() => {
    const opts = suppliers.map((s) => ({ id: s.id, label: s.name }));
    const known = new Set(opts.map((o) => o.id));
    for (const [sid, name] of Object.entries(createdNames)) {
      if (!known.has(sid)) opts.push({ id: sid, label: name });
    }
    return opts;
  }, [suppliers, createdNames]);
  const supplierName = (sid: string) =>
    supplierOptions.find((o) => o.id === sid)?.label ?? "—";

  const tolerance = Number(getSetting("inbound_discrepancy_tolerance_pct") ?? 0.05);

  const userId = useAuthStore((st) => st.user?.id);
  const orgId = useAuthStore((st) => st.organizationId);
  const draftKey = order && userId
    ? `inbound-liquidate-draft:v1:${orgId ?? ""}:${userId}:${order.id}`
    : null;
  const draftSig = useMemo(() => (order ? orderSignature(order) : ""), [order]);
  /** Estado tal como vino del servidor: si lo digitado vuelve a él, no hay borrador */
  const baselineRef = useRef<string | null>(null);
  const [recoveredAt, setRecoveredAt] = useState<number | null>(null);

  const [lines, setLines] = useState<LineState[]>([]);
  const [cols, setCols] = useState<PurchaseCol[]>([]);
  // QA C9: la consulta de la lista es asíncrona; al volver se mira la
  // columna VIGENTE, no la del momento del clic
  const colsRef = useRef<PurchaseCol[]>(cols);
  colsRef.current = cols;
  // Orden del formato en papel (#121): solo de PRESENTACIÓN — el estado se
  // actualiza por `_key`, pintar en otro orden no cambia lo que se manda
  const formOrder = useMemo(() => formOrderMap(profilesData?.items), [profilesData]);
  const orderedLines = useMemo(() => sortByFormOrder(lines, formOrder), [lines, formOrder]);
  const sortedCols = useMemo(() => [...cols].sort((a, b) => a.slot - b.slot), [cols]);

  // Escritorio: la compra nueva nace a la derecha, dentro del scroll de la
  // tabla; con 3+ compras quedaba fuera de la vista. Solo el botón de
  // escritorio pide el scroll (recuperar un borrador no mueve la tabla).
  const tableScrollRef = useRef<HTMLDivElement>(null);
  const scrollToNewColRef = useRef(false);
  useEffect(() => {
    if (!scrollToNewColRef.current) return;
    scrollToNewColRef.current = false;
    const el = tableScrollRef.current;
    if (el) el.scrollTo({ left: el.scrollWidth, behavior: "smooth" });
  }, [sortedCols.length]);
  const [initialized, setInitialized] = useState(false);
  const [createFor, setCreateFor] = useState<number | null>(null);
  // D11: UNA comisión por entrada, sobre lo pesado
  const [collectorEnabled, setCollectorEnabled] = useState(false);
  const [collectorTpId, setCollectorTpId] = useState("");
  const [collectorAmount, setCollectorAmount] = useState(0);
  const [collectorTouched, setCollectorTouched] = useState(false);
  const [extraMaterialId, setExtraMaterialId] = useState("");
  // Ítem 2 (Hugo): el caso más común es que todo el camión sea de un proveedor
  const [bulkSupplier, setBulkSupplier] = useState("");

  // Catálogo de retenciones (v2 #79) — la ruta ya está gated por el flag (FP)
  const { data: retentionRows } = useRetentionRows(unscoped);
  // T3: las funciones de taxRows reciben el catálogo SIN filtrar; las
  // tarifas que se pueden usar las decide `isUsableConfig`, en un solo lugar
  const retentionCatalog = useMemo(() => retentionRows ?? [], [retentionRows]);
  const retentionConfigs = useMemo(
    () => retentionCatalog.filter((r) => r.config_id && r.is_active),
    [retentionCatalog],
  );
  const configById = useMemo(
    () => new Map(retentionCatalog.filter(isUsableConfig).map((r) => [r.config_id as string, r])),
    [retentionCatalog],
  );
  const defaultConfig = useMemo(() => defaultRetentionConfig(retentionCatalog), [retentionCatalog]);

  useEffect(() => {
    // Espera al catálogo: la precarga mapea cada retención guardada a su tarifa
    // Con alcance no hay catalogo de retenciones que esperar (S5).
    if (!order || initialized || (!retentionRows && !scoped)) return;
    const initial = initLines(order);
    setLines(initial);
    setCollectorEnabled(!!order.collector_id);
    setCollectorTpId(order.collector_id ?? "");

    // Columnas = los slots del reparto guardado, con su proveedor y factura
    const bySlot = new Map<number, PurchaseCol>();
    for (const l of order.lines) {
      for (const a of l.allocations) {
        const col = bySlot.get(a.purchase_slot) ?? newCol(a.purchase_slot, a.third_party_id);
        if (!col.invoice && a.invoice_number) col.invoice = a.invoice_number;
        bySlot.set(a.purchase_slot, col);
      }
    }
    // Retenciones e IVA del último lote de la compra de ESE slot (la viva, o
    // la más reciente si se des-liquidó). Con dos compras del mismo proveedor
    // la precarga por proveedor se pisaba; por slot no.
    for (const col of bySlot.values()) {
      const same = order.purchases.filter((p) => p.purchase_slot === col.slot);
      const p = same.find((x) => x.status !== "cancelled") ?? same[same.length - 1];
      if (!p) continue;
      // T1'/T2: vuelve la tasa GUARDADA (la tarifa solo da el tipo); si no
      // queda ninguna tarifa usable de ese tipo, la fila sigue y avisa
      // C1: con alcance no se precarga ninguna (no hay catálogo ni pie)
      col.retentions = precargaRetentions(p.retentions ?? [], retentionCatalog, scoped, nextKey);
      const iva = (p.taxes ?? []).find((t) => t.tax_type === "iva");
      // T8: «editado» se mide contra la tasa guardada, no contra 19
      if (iva) Object.assign(col, precargaIva(iva));
    }
    const initialCols = [...bySlot.values()];
    const startCols = initialCols.length > 0 ? initialCols : [newCol(1)];
    setCols(startCols);
    baselineRef.current = JSON.stringify({
      lines: initial,
      cols: startCols,
      collector: { enabled: !!order.collector_id, tpId: order.collector_id ?? "", amount: 0, touched: false },
    });

    // Borrador de una visita anterior, si sigue correspondiendo a lo pesado
    if (draftKey) {
      const d = readDraft(draftKey);
      if (d && d.sig === draftSig) {
        try {
          assertDraftShape(d);
          // T2b: una retención cuya tarifa ya no sirve no desaparece: pasa a
          // otra usable de su tipo, o queda sin tarifa con la nota
          const draftCols = d.cols.map((c) => ({
            ...c,
            ivaRate: reviveDraftIvaRate(c.ivaRate),
            retentions: reviveDraftRetentions(c.retentions, retentionCatalog, scoped),
          }));
          keyCounter = Math.max(
            keyCounter,
            ...d.lines.map((l) => l._key),
            ...draftCols.flatMap((c) => c.retentions.map((r) => r._key)),
          );
          setLines(d.lines);
          setCols(draftCols);
          setCollectorEnabled(d.collector.enabled);
          setCollectorTpId(d.collector.tpId);
          setCollectorAmount(d.collector.amount);
          setCollectorTouched(d.collector.touched);
          setRecoveredAt(d.savedAt);
        } catch {
          // Malformado: se borra y se sigue con lo del servidor (ya puesto arriba)
          removeDraft(draftKey);
        }
      } else if (d) {
        removeDraft(draftKey);
      }
    }
    setInitialized(true);
    // `scoped` es dependencia REAL: si la Entrada carga antes que los permisos,
    // el init corta (sin retenciones y aun sin saber del alcance) y tiene que
    // volver a correr cuando se sabe que el usuario tiene alcance.
  }, [order, initialized, retentionRows, retentionCatalog, draftKey, draftSig, scoped]);

  // Guardar el borrador en cada cambio; si lo digitado vuelve a lo del
  // servidor, se borra (así no aparece «recuperado» sin haber nada)
  useEffect(() => {
    if (!initialized || !draftKey) return;
    const collector = {
      enabled: collectorEnabled,
      tpId: collectorTpId,
      amount: collectorAmount,
      touched: collectorTouched,
    };
    const snap = JSON.stringify({ lines, cols, collector });
    if (snap === baselineRef.current) {
      removeDraft(draftKey);
    } else {
      writeDraft(draftKey, { v: 1, sig: draftSig, savedAt: Date.now(), lines, cols, collector });
    }
  }, [
    initialized, draftKey, draftSig, lines, cols,
    collectorEnabled, collectorTpId, collectorAmount, collectorTouched,
  ]);

  // Materiales elegibles para reparto extra (D16): compra regular, no presentes
  const compraByMaterial = useMemo(() => {
    const map = new Map<string, boolean>();
    for (const p of profilesData?.items ?? []) map.set(p.material_id, p.compra_regular);
    return map;
  }, [profilesData]);
  const extraOptions = useMemo(() => {
    const present = new Set(lines.map((l) => l.material_id));
    return materials.filter(
      (m) => !present.has(m.id) && (compraByMaterial.get(m.id) ?? true)
    );
  }, [materials, lines, compraByMaterial]);

  // Tarifa vigente comision_green_loop (precio + regla de los kg/unidad)
  const greenLoopTariff = (tariffsData?.items ?? []).find(
    (t) => t.tariff_code === "comision_green_loop"
  );
  const tariffPrice = greenLoopTariff ? Number(greenLoopTariff.unit_price_cop) : 0;
  const tariffKgPerUnit = greenLoopTariff?.kg_per_unit != null
    ? Number(greenLoopTariff.kg_per_unit)
    : null;

  // Base de la comisión: lo PESADO (D11) — kg directos + unidades × kg/unidad
  const commissionBase = useMemo(() => {
    let base = 0;
    let unresolved = false;
    for (const l of lines) {
      if (l.weighed <= 0) continue;
      if (l.material_unit === "kg") base += l.weighed;
      else if (tariffKgPerUnit != null) base += l.weighed * tariffKgPerUnit;
      else unresolved = true;
    }
    return { base, unresolved };
  }, [lines, tariffKgPerUnit]);
  const suggestedCommission = tariffPrice > 0
    ? Math.round(commissionBase.base * tariffPrice * 100) / 100
    : 0;
  const effCollectorAmount = collectorTouched ? collectorAmount : suggestedCommission;

  if (isLoading || !initialized) {
    return <div className="p-8 text-center text-slate-500">Cargando...</div>;
  }
  if (!order) {
    return <div className="p-8 text-center text-slate-500">Entrada no encontrada</div>;
  }

  const backTo = returnTo && returnTo.startsWith("/")
    ? returnTo
    : buildRoute(ROUTES.INBOUND_DETAIL, { id: order.id });

  // Guards de estado — el backend también los valida (400)
  if (order.inbound_type !== "purchase" || (order.purchase_id && order.purchases.length === 0)) {
    return (
      <GuardMessage
        text="Esta entrada no se liquida con reparto — vuelva al detalle."
        onBack={() => navigate(backTo)}
      />
    );
  }
  if (order.status === "draft") {
    return (
      <GuardMessage
        text="La entrada está Registrada — debe pasar la revisión antes de liquidarse (alguien con permiso la marca Revisada desde el detalle)."
        onBack={() => navigate(backTo)}
      />
    );
  }
  if (order.status !== "reviewed") {
    return (
      <GuardMessage
        text={`La entrada está ${order.display_status === "liquidated" ? "Liquidada" : "en un estado que no permite liquidar"} — vuelva al detalle.`}
        onBack={() => navigate(backTo)}
      />
    );
  }

  const colBySlot = new Map(cols.map((c) => [c.slot, c]));

  // ---------- mutadores ----------

  const updateLine = (key: number, patch: Partial<LineState>) => {
    setLines((prev) => prev.map((l) => (l._key === key ? { ...l, ...patch } : l)));
  };

  const updateCol = (slot: number, patch: Partial<PurchaseCol>) => {
    setCols((prev) => prev.map((c) => (c.slot === slot ? { ...c, ...patch } : c)));
  };

  const setCell = (lineKey: number, slot: number, patch: Partial<CellState>) => {
    setLines((prev) =>
      prev.map((l) => {
        if (l._key !== lineKey) return l;
        const cell = { ...(l.cells[slot] ?? emptyCell()), ...patch };
        let rowPrice = l.rowPrice;
        // «Reutilizar el primer precio digitado» (Daniel): una fila virgen
        // toma el primer precio propio de una celda — a centavos (C1, A3)
        if (!l.rowTouched && rowPrice <= 0 && ownMode(cell) && cellPriced(cell, undefined, l)) {
          rowPrice = toCents(cellUnit(cell, undefined, l));
        }
        return {
          ...l,
          rowPrice,
          unallocated: cell.quantity > 0 ? false : l.unallocated,
          cells: { ...l.cells, [slot]: cell },
        };
      })
    );
  };

  /** El modo NO rota con la cifra (§5): a total o kg el campo arranca vacío y
   *  el precio anterior queda como texto «antes: …». A c/u (plan v1.1 D3) se
   *  quita el precio propio y el campo vuelve prellenado con lista/base. */
  const switchMode = (l: LineState, col: PurchaseCol, mode: OwnMode) => {
    const c = l.cells[col.slot] ?? emptyCell();
    const own = ownMode(c);
    if (mode === "unit") {
      // C3: en lista, base o propio unitario el campo YA es un unitario: no-op
      if (own !== "total" && own !== "kg") return;
      setCell(l._key, col.slot, {
        unit_price: null,
        total_price: null,
        price_per_kg: null,
        before: describePrice(c, col, l) ?? c.before,
      });
      return;
    }
    if (own === mode) return;
    setCell(l._key, col.slot, {
      unit_price: null,
      total_price: mode === "total" ? 0 : null,
      price_per_kg: mode === "kg" ? 0 : null,
      before: describePrice(c, col, l) ?? c.before,
    });
  };

  /** ↺: vuelve al precio de la lista del proveedor o al base. */
  const clearOwnPrice = (l: LineState, slot: number) =>
    setCell(l._key, slot, { unit_price: null, total_price: null, price_per_kg: null, before: null });

  /** Plan v1.1 D2. `MoneyInput` llama `onChange` en CADA blur (2 decimales). */
  const onPriceInput = (l: LineState, col: PurchaseCol, v: number) => {
    const c = l.cells[col.slot] ?? emptyCell();
    // 🔴 C1: un blur que no cambia la cifra no escribe nada, en ningún modo —
    // ni crea una celda vacía, ni redondea un unitario de 8 decimales, ni borra «antes»
    if (toCents(v) === priceFieldValue(l.cells[col.slot], col, l)) return;
    const own = ownMode(c);
    if (own === "kg") return setCell(l._key, col.slot, { price_per_kg: v, before: null });
    if (own === "total") return setCell(l._key, col.slot, { total_price: v, before: null });
    // Vista unitaria (vacía, base, lista o propio). El 0 vuelve al sugerido (S2).
    if (v === 0) {
      if (own === "unit") clearOwnPrice(l, col.slot);
      return;
    }
    setCell(l._key, col.slot, { unit_price: v, total_price: null, price_per_kg: null, before: null });
  };

  /** D8 (#98): la lista del proveedor, por material. Se aplica solo si el
   *  proveedor de la columna sigue siendo el mismo cuando vuelve la consulta.
   *  Una fila virgen (sin precio) arranca del precio de la lista. */
  const loadListPrices = async (slot: number, supplierId: string) => {
    const mats = [...new Set(lines.map((l) => l.material_id))];
    const found: Record<string, number> = {};
    await Promise.all(
      mats.map(async (m) => {
        const p = await lookupSupplierPrice(supplierId, m);
        if (p != null) found[m] = p;
      })
    );
    // Si mientras viajaba la consulta la columna cambió de proveedor (o se
    // quitó), no se aplica nada — ni la lista ni el precio de la fila
    if (colsRef.current.find((c) => c.slot === slot)?.third_party_id !== supplierId) return;
    setCols((prev) =>
      prev.map((c) =>
        c.slot === slot && c.third_party_id === supplierId ? { ...c, listPrices: found } : c
      )
    );
    setLines((prev) =>
      prev.map((l) =>
        !l.rowTouched && l.rowPrice <= 0 && found[l.material_id] != null
          ? { ...l, rowPrice: found[l.material_id] }
          : l
      )
    );
  };

  /** QA C9: retenciones, contado, factura e IVA son DEL proveedor de la
   *  columna. Al cambiarlo se vacían (una ICA de otro municipio o un pago de
   *  contado no pueden pasar al nuevo sin que nadie lo vea); el IVA vuelve a
   *  la casilla apagada (Q-66). Se avisa si había algo. */
  const setColSupplier = (slot: number, supplierId: string) => {
    const prev = cols.find((c) => c.slot === slot);
    if (prev && prev.third_party_id === supplierId) return;
    const had =
      prev &&
      (prev.retentions.length > 0 || prev.paymentAccount !== null || prev.invoice.trim() || prev.withIva);
    updateCol(slot, {
      third_party_id: supplierId,
      listPrices: {},
      retentions: [],
      paymentAccount: null,
      invoice: "",
      withIva: false,
      ivaRate: IVA_RATE_PCT,
      ivaAmount: 0,
      ivaTouched: false,
    });
    if (had && prev?.third_party_id) {
      toast.info(`Compra ${slot}: se quitaron la factura, el IVA, las retenciones y el contado del proveedor anterior`);
    }
    if (supplierId) void loadListPrices(slot, supplierId);
  };

  /** R6: max + 1 sobre las columnas Y los slots que ya existen en el puente
   *  (incluidas compras canceladas): un slot quitado queda como hueco. */
  const addCol = () => {
    const used = [
      ...cols.map((c) => c.slot),
      ...order.purchases.map((p) => p.purchase_slot ?? 0),
    ];
    const slot = Math.max(0, ...used) + 1;
    setCols((prev) => [...prev, newCol(slot)]);
  };

  const removeCol = (slot: number) => {
    setCols((prev) => prev.filter((c) => c.slot !== slot));
    setLines((prev) =>
      prev.map((l) => {
        if (!(slot in l.cells)) return l;
        const cells = { ...l.cells };
        delete cells[slot];
        return { ...l, cells };
      })
    );
  };

  /**
   * Ítem 2 — «Repartir todo a este proveedor»: UNA compra con todo lo pesado.
   * Reemplaza el reparto. Conserva el slot (la columna del mismo proveedor, o
   * la primera) para no renumerar (R6). Prioridad de precio como antes: lo ya
   * digitado > la lista del proveedor > el de la fila.
   */
  const applySingleSupplier = () => {
    if (!bulkSupplier) return;
    const keep =
      cols.find((c) => c.third_party_id === bulkSupplier)?.slot ??
      (cols.length > 0 ? Math.min(...cols.map((c) => c.slot)) : 1);
    setCols([newCol(keep, bulkSupplier)]);
    setLines((prev) =>
      prev.map((l) => {
        if (l.isExtra) {
          // QA C2: el material extra (D16) se agregó a mano para repartirlo a
          // mano. Como en HEAD, no se pierde: lo repartido pasa a la compra
          // que queda, con el primer precio propio que tuviera.
          const act = Object.entries(l.cells).filter(([, c]) => c.quantity > 0);
          if (act.length === 0) return l;
          const qty = Math.round(act.reduce((acc, [, c]) => acc + c.quantity, 0) * 1000) / 1000;
          const own = act.find(([, c]) => ownMode(c));
          const carried = own ? toCents(cellUnit(own[1], colBySlot.get(Number(own[0])), l)) : null;
          return { ...l, cells: { [keep]: { ...emptyCell(), quantity: qty, unit_price: carried } } };
        }
        if (l.weighed <= 0) {
          // en 0 no se asigna (sería inválida): «sin proveedor», inerte con descuadre 0
          return { ...l, cells: {}, unallocated: true };
        }
        const typed = Object.entries(l.cells).find(([, c]) => c.quantity > 0 && ownMode(c));
        const carried = typed
          ? toCents(cellUnit(typed[1], colBySlot.get(Number(typed[0])), l))
          : null;
        return {
          ...l,
          unallocated: false,
          cells: { [keep]: { ...emptyCell(), quantity: l.weighed, unit_price: carried } },
        };
      })
    );
    void loadListPrices(keep, bulkSupplier);
  };

  /** QA C2: el material extra se puede quitar (el backend rechaza uno sin
   *  asignaciones, y marcarlo «sin proveedor» no aplica: no se pesó). */
  const removeLine = (key: number) => {
    setLines((prev) => prev.filter((l) => l._key !== key));
  };

  const addExtraLine = () => {
    const mat = materials.find((m) => m.id === extraMaterialId);
    if (!mat) return;
    setLines((prev) => [
      ...prev,
      {
        _key: nextKey(),
        material_id: mat.id,
        material_code: mat.code,
        material_name: mat.name,
        material_unit: mat.default_unit || "kg",
        weighed: 0,
        weightKg: null, // material que la báscula no vio (D16)
        isExtra: true,
        rowPrice: 0,
        rowTouched: false,
        unallocated: false,
        cells: {},
      },
    ]);
    setExtraMaterialId("");
  };

  // ---------- retenciones / IVA por compra ----------

  // T4: el último que se tocó gana (funciones puras de taxRows)
  const effRetAmount = (r: RetRow, base: number) => effAmount(r, base);

  const updateRet = (slot: number, key: number, fn: (r: RetRow) => RetRow) =>
    setCols((prev) =>
      prev.map((c) =>
        c.slot === slot
          ? { ...c, retentions: c.retentions.map((r) => (r._key === key ? fn(r) : r)) }
          : c
      )
    );
  const removeRet = (slot: number, key: number) =>
    setCols((prev) =>
      prev.map((c) =>
        c.slot === slot ? { ...c, retentions: c.retentions.filter((r) => r._key !== key) } : c
      )
    );
  const addRet = (slot: number) =>
    setCols((prev) =>
      prev.map((c) =>
        c.slot === slot
          // D3: la ReteFuente general se propone solo al apretar «+ Retención»
          ? { ...c, retentions: [...c.retentions, newRetRow(defaultConfig, nextKey())] }
          : c
      )
    );

  // ---------- derivados ----------

  const activeCells = (l: LineState) =>
    Object.entries(l.cells)
      .map(([s, c]) => ({ slot: Number(s), cell: c }))
      .filter(({ slot, cell }) => cell.quantity > 0 && colBySlot.has(slot));

  /** QA C7: cuantizado a ALLOC_Q (0,001), igual que el servidor. Sin esto
   *  100,1 + 200,2 contra 300,3 da 5,7e-14 y la pantalla bloquea un
   *  descuadre que el backend ve en 0. */
  const q3 = (v: number) => Math.round(v * 1000) / 1000;
  const lineAllocated = (l: LineState) =>
    q3(activeCells(l).reduce((acc, { cell }) => acc + cell.quantity, 0));
  const lineDisc = (l: LineState) => q3(l.weighed - lineAllocated(l));

  const colStats = (col: PurchaseCol) => {
    const rows = orderedLines
      .map((l) => ({ l, c: l.cells[col.slot] }))
      .filter(({ c }) => c && c.quantity > 0) as { l: LineState; c: CellState }[];
    const subtotal = rows.reduce((acc, { l, c }) => acc + cellTotal(c, col, l), 0);
    const iva = col.withIva ? (col.ivaTouched ? col.ivaAmount : pctOf(subtotal, col.ivaRate)) : 0;
    const ret = col.retentions.reduce((acc, r) => acc + effRetAmount(r, subtotal), 0);
    const qtyByUnit: Record<string, number> = {};
    for (const { l, c } of rows) {
      qtyByUnit[l.material_unit] = q3((qtyByUnit[l.material_unit] ?? 0) + c.quantity);
    }
    return {
      rows,
      subtotal,
      iva,
      ret,
      neto: subtotal + iva - ret,
      // Cantidad POR UNIDAD (#54): kg y unidades no se suman
      qtyLabel: Object.entries(qtyByUnit).map(([u, q]) => formatWeight(q, u)).join(" + "),
    };
  };
  const statsBySlot = new Map(cols.map((c) => [c.slot, colStats(c)]));
  const activeCols = sortedCols.filter((c) => (statsBySlot.get(c.slot)?.rows.length ?? 0) > 0);
  const emptyColCount = sortedCols.length - activeCols.length;

  // ---------- validación ----------

  const lineProblem = (l: LineState): string | null => {
    for (const { slot, cell } of activeCells(l)) {
      if (!cellPriced(cell, colBySlot.get(slot), l)) {
        return `Falta el precio en la compra ${slot}`;
      }
    }
    // 9g (plan Ingrid v1.10), solo con alcance: todo lo pesado se reparte.
    // Mismo orden que el servidor: antes de «sin asignar» y del precio base.
    if (scoped && lineDisc(l) !== 0) {
      const qty = formatWeight(Math.abs(lineDisc(l)), l.material_unit);
      const what =
        activeCells(l).length === 0
          ? `sin repartir (${formatWeight(l.weighed, l.material_unit)} pesados)`
          : lineDisc(l) > 0
            ? `faltan ${qty} por repartir`
            : `se repartieron ${qty} de más`;
      return `${what} — con tu alcance hay que repartir todo lo pesado; si no se puede, esta Entrada la liquida SAC`;
    }
    if (activeCells(l).length === 0 && l.isExtra) {
      return "Reparta este material o quítelo";
    }
    if (activeCells(l).length === 0 && !l.unallocated) {
      return "Sin asignar — reparta o marque \"sin proveedor (intencional)\"";
    }
    if (lineDisc(l) !== 0 && l.rowPrice <= 0) {
      const qty = formatWeight(Math.abs(lineDisc(l)), l.material_unit);
      return l.unallocated
        ? `Falta el precio base: con él se valoran los ${qty} que entran como ganancia`
        : `Falta el precio base: con él se valora el descuadre de ${qty}`;
    }
    return null;
  };

  const problems: string[] = [];
  for (const l of orderedLines) {
    const p = lineProblem(l);
    if (p) problems.push(`${l.material_code || l.material_name}: ${p}`);
  }
  for (const col of activeCols) {
    const st = statsBySlot.get(col.slot)!;
    const who = col.third_party_id ? supplierName(col.third_party_id) : "";
    const tag = `Compra ${col.slot}${who ? ` (${who})` : ""}`;
    if (!col.third_party_id) problems.push(`${tag}: falta el proveedor`);
    // Tres causas, tres mensajes: «falta tarifa o monto» mandaba a revisar
    // el selector con la tarifa bien puesta (pruebas Daniel)
    if (col.retentions.some((r) => !r.config_id)) {
      problems.push(`${tag}: falta elegir la tarifa de una retención`);
    } else if (col.retentions.some((r) => !configById.has(r.config_id))) {
      problems.push(`${tag}: una retención usa una tarifa que ya no está activa — elíjala de nuevo`);
    } else if (col.retentions.some((r) => rateOutOfRange(r.rate))) {
      const r = col.retentions.find((x) => rateOutOfRange(x.rate))!;
      const cfg = configById.get(r.config_id);
      problems.push(`${tag}: el % de ${cfg ? retentionRowLabel(cfg) : "una retención"} debe estar entre 0 y 100`);
    } else if (col.retentions.length > 0 && st.subtotal <= 0) {
      problems.push(`${tag}: su subtotal es $0, no hay base sobre la cual retener`);
    } else if (col.retentions.some((r) => effRetAmount(r, st.subtotal) <= 0)) {
      problems.push(`${tag}: una retención quedó en $0`);
    } else if (st.ret > 0 && st.ret >= st.subtotal + st.iva) {
      problems.push(`${tag}: las retenciones deben ser menores al total (${fmtMoney(st.subtotal + st.iva)})`);
    }
    if (col.withIva && rateOutOfRange(col.ivaRate)) problems.push(`${tag}: el % de IVA debe estar entre 0 y 100`);
    else if (col.withIva && st.iva <= 0) problems.push(`${tag}: el IVA quedó en $0`);
    // Contado sin cuenta es un error silencioso: nacería a crédito sin avisar
    if (col.paymentAccount === "") problems.push(`${tag}: pago de contado sin cuenta`);
  }

  // Reglas 9e/9f (plan Ingrid v1.6/v1.7), SOLO con alcance: una Entrada que
  // SAC liquidó y des-liquidó con una compra viva de un proveedor ajeno, o
  // con retenciones o IVA en su última liquidación, la vuelve a liquidar SAC.
  // Se avisa al abrir, no al enviar; el 422 del servidor sigue siendo la red.
  // `taxes`/`retentions` ya son el lote de la ÚLTIMA liquidación (la misma
  // función del servidor, `last_liquidation_batch`).
  const livePurchases = order.purchases.filter((p) => p.status !== "cancelled");
  const reliqBlocks: string[] = !scoped
    ? []
    : [
        ...(scopeSupplierIds && livePurchases.some((p) => !scopeSupplierIds.has(p.supplier_id))
          ? [RELIQ_FOREIGN]
          : []),
        ...(livePurchases.some((p) => (p.retentions?.length ?? 0) > 0 || (p.taxes?.length ?? 0) > 0)
          ? [RELIQ_TAXES]
          : []),
      ];
  problems.push(...reliqBlocks);

  // Con alcance la comision no la arma la pantalla (fila 9): no bloquea.
  const collectorValid = scoped || !collectorEnabled || (!!collectorTpId && effCollectorAmount > 0);
  const canSubmit = problems.length === 0 && collectorValid && !liquidateOrder.isPending;

  const handleSubmit = () => {
    if (!canSubmit) return;
    const payloadLines: InboundLiquidateLine[] = lines.map((l) => {
      const act = activeCells(l);
      return {
        material_id: l.material_id,
        reference_unit_price: l.rowPrice > 0 ? l.rowPrice : null,
        unallocated_intentional: act.length === 0 && l.unallocated,
        allocations: act.map(({ slot, cell }) => {
          const col = colBySlot.get(slot)!;
          const mode = cellMode(cell, col, l);
          // Viaja UNO de los tres precios — mandar más de uno es 422
          const price =
            mode === "kg"
              ? { price_per_kg: cell.price_per_kg }
              : mode === "total"
                ? { total_price: cell.total_price }
                : { unit_price: cellUnit(cell, col, l) };
          return {
            third_party_id: col.third_party_id,
            purchase_slot: slot,
            quantity: cell.quantity,
            ...price,
            invoice_number: col.invoice.trim() || null,
          };
        }),
      };
    });
    const retentionBlocks: InboundSupplierRetentions[] = [];
    const paymentBlocks: InboundSupplierPayment[] = [];
    const taxBlocks: InboundPurchaseTaxes[] = [];
    for (const col of activeCols) {
      const st = statsBySlot.get(col.slot)!;
      const rows = col.retentions.flatMap((r) => {
        const cfg = configById.get(r.config_id);
        return cfg ? [{ r, cfg }] : [];
      });
      if (rows.length > 0) {
        retentionBlocks.push({
          purchase_slot: col.slot,
          third_party_id: col.third_party_id,
          // T4: va el % digitado, no el del catálogo; el monto es la verdad (#79 F1)
          retentions: rows.map(({ r, cfg }) => buildRetentionPayload(r, cfg, st.subtotal)),
        });
      }
      if (col.paymentAccount) {
        paymentBlocks.push({
          purchase_slot: col.slot,
          third_party_id: col.third_party_id,
          account_id: col.paymentAccount,
        });
      }
      if (col.withIva && st.iva > 0) {
        taxBlocks.push({
          purchase_slot: col.slot,
          third_party_id: col.third_party_id,
          taxes: [ivaPayload(col.ivaRate, st.iva)],
        });
      }
    }
    liquidateOrder.mutate(
      {
        id: order.id,
        data: {
          lines: payloadLines,
          // Con alcance la comision la fija el servidor (fila 9, D-a): no se manda.
          collector_commission: scoped
            ? null
            : collectorEnabled && collectorTpId && effCollectorAmount > 0
              ? { third_party_id: collectorTpId, amount: effCollectorAmount }
              : null,
          // Ausentes (no []) sin bloques — data-gate D9
          supplier_retentions: retentionBlocks.length > 0 ? retentionBlocks : undefined,
          supplier_payments: paymentBlocks.length > 0 ? paymentBlocks : undefined,
          purchase_taxes: taxBlocks.length > 0 ? taxBlocks : undefined,
        },
      },
      {
        onSuccess: () => {
          if (draftKey) removeDraft(draftKey);
          navigate(buildRoute(ROUTES.INBOUND_DETAIL, { id: order.id }));
        },
      }
    );
  };

  // ---------- piezas de render (funciones, no componentes: no remontan) ----------

  const discInfo = (l: LineState) => {
    const disc = lineDisc(l);
    const pct = l.weighed > 0 ? Math.abs(disc) / l.weighed : null;
    const state = disc === 0 ? "ok" : pct != null && pct <= tolerance ? "within" : "out";
    return { disc, pct, state };
  };

  const renderDisc = (l: LineState) => {
    const { disc, pct, state } = discInfo(l);
    return (
      <div className="text-xs tabular-nums space-y-0.5">
        <div className="text-slate-500">
          Repartido{" "}
          <span className="font-semibold text-slate-700">
            {formatWeight(lineAllocated(l), l.material_unit)}
          </span>
        </div>
        <div
          className={cn(
            "font-semibold",
            state === "ok" && "text-emerald-700",
            state === "within" && "text-amber-700",
            state === "out" && "text-rose-700"
          )}
          title={
            disc === 0
              ? "Cuadre exacto — sin ajuste de inventario"
              : disc > 0
                ? "Sobrante: entra al inventario como ganancia al precio de la fila"
                : "Faltante: sale del inventario como pérdida al precio de la fila"
          }
        >
          {disc === 0 ? "Cuadra" : `${disc > 0 ? "+" : ""}${formatWeight(disc, l.material_unit)}`}
          {pct != null && disc !== 0 && (
            <span className="font-normal"> ({(pct * 100).toFixed(1)}%{state === "out" ? ", fuera de tolerancia" : ""})</span>
          )}
        </div>
        {/* 9g: con alcance, «sin proveedor» en un material pesado solo
            termina en 422; con pesado 0 no deja descuadre y se ofrece. */}
        {activeCells(l).length === 0 && !l.isExtra && !(scoped && l.weighed !== 0) && (
          <label className="flex items-center gap-1.5 text-slate-600 cursor-pointer font-normal">
            <Checkbox
              checked={l.unallocated}
              onCheckedChange={(v) => updateLine(l._key, { unallocated: v === true })}
            />
            Sin proveedor (intencional)
          </label>
        )}
      </div>
    );
  };

  const renderMaterial = (l: LineState) => {
    const problem = lineProblem(l);
    return (
      <div className="space-y-0.5">
        <div className="font-semibold text-slate-800">{l.material_code}</div>
        <div className="text-xs text-slate-500 leading-tight">{l.material_name}</div>
        {l.isExtra && (
          <div className="text-[11px] text-amber-600">
            no pesado (entra como faltante) ·{" "}
            <button type="button" className="underline hover:text-red-600" onClick={() => removeLine(l._key)}>
              Quitar
            </button>
          </div>
        )}
        {problem && <div className="text-[11px] text-rose-600 leading-tight">{problem}</div>}
      </div>
    );
  };

  const renderWeighed = (l: LineState) => (
    <div className="text-xs tabular-nums">
      <div className="flex items-center gap-1 font-semibold text-slate-700 whitespace-nowrap">
        <Scale className="h-3.5 w-3.5 text-slate-400" />
        {formatWeight(l.weighed, l.material_unit)}
      </div>
      {/* Q-13: el peso certificado, solo cuando dice algo que la cantidad no dice */}
      {l.weightKg != null && (l.material_unit !== "kg" || l.weightKg !== l.weighed) && (
        <div className="text-indigo-700 whitespace-nowrap">Báscula {formatWeight(l.weightKg, "kg")}</div>
      )}
    </div>
  );

  const renderRowPrice = (l: LineState) => {
    const needed = lineDisc(l) !== 0 || activeCells(l).length > 0;
    return (
      // Mismo pegado de cifras que en la celda: con Tab, 710 sobre 700 daba 700710
      <div onFocus={selectOnFocus}>
        <MoneyInput
          value={l.rowPrice}
          // QA C5: MoneyInput llama onChange en CADA blur; sin el guard, pasar
          // con Tab marcaba la fila como tocada sin haber cambiado nada
          onChange={(v) => v !== l.rowPrice && updateLine(l._key, { rowPrice: v, rowTouched: true })}
          decimals={2}
          placeholder="Precio base"
          className={cn("h-8 text-sm", needed && l.rowPrice <= 0 && "border-red-300")}
        />
      </div>
    );
  };

  const renderCell = (l: LineState, col: PurchaseCol) => {
    const c = l.cells[col.slot];
    const qty = c?.quantity ?? 0;
    const mode = c ? cellMode(c, col, l) : "row";
    const own = c ? ownMode(c) : null;
    const priced = c ? cellPriced(c, col, l) : false;
    // En lista, base o propio unitario el campo es un unitario: se ve activo c/u (C3)
    const activeMode: OwnMode = own === "total" || own === "kg" ? own : "unit";
    const suggested = suggestedUnit(col, l);
    const fieldValue = priceFieldValue(c, col, l);
    const origin = own
      ? "propio"
      : mode === "list" || listPriceOf(col, l) != null
        ? "lista"
        : "base";
    return (
      <div className="space-y-1">
        {/* Plan v1.1 D1: cantidad y precio lado a lado, siempre visibles. El
            campo de precio existe también con cantidad 0, para que el Tab vaya
            cantidad → precio → celda siguiente. */}
        <div className="grid grid-cols-2 gap-1" onFocus={selectOnFocus}>
          <MoneyInput
            value={qty}
            // C5: un blur sin cambio no crea una celda en 0 (borrador fantasma)
            onChange={(v) => v !== qty && setCell(l._key, col.slot, { quantity: v })}
            // 3 decimales: la escala con la que se guarda (ALLOC_Q)
            decimals={3}
            placeholder="—"
            className="h-8 text-sm px-2"
          />
          <MoneyInput
            value={fieldValue}
            onChange={(v) => onPriceInput(l, col, v)}
            decimals={2}
            placeholder={
              activeMode !== "unit"
                ? MODE_LABEL[activeMode]
                : suggested > 0
                  ? fmtMoney(suggested).replace(/^\$\s?/, "")
                  : "Precio"
            }
            className={cn(
              "h-8 text-sm px-2",
              qty > 0 && !priced && "border-red-300",
              own && "text-indigo-700 font-medium"
            )}
          />
        </div>
        {c && qty > 0 && (
          <>
            <div className="flex items-center justify-between gap-1 text-[11px] leading-tight">
              <div className="flex gap-0.5">
                {(["unit", "total", "kg"] as OwnMode[])
                  .filter((m) => m !== "kg" || canKg(l))
                  .map((m) => (
                    <button
                      key={m}
                      type="button"
                      // C2: fuera del recorrido con Tab
                      tabIndex={-1}
                      title={MODE_LABEL[m]}
                      onClick={() => switchMode(l, col, m)}
                      className={cn(
                        "px-1.5 py-0.5 rounded border",
                        activeMode === m
                          ? "bg-indigo-600 border-indigo-600 text-white"
                          : "bg-white border-slate-200 text-slate-500 hover:border-indigo-300"
                      )}
                    >
                      {MODE_SHORT[m]}
                    </button>
                  ))}
              </div>
              {own ? (
                <button
                  type="button"
                  // C2: fuera del recorrido con Tab
                  tabIndex={-1}
                  onClick={() => clearOwnPrice(l, col.slot)}
                  className="text-indigo-600 hover:underline whitespace-nowrap"
                  title={
                    suggested > 0
                      ? `Volver al precio ${listPriceOf(col, l) != null ? "de la lista" : "base"} (${fmtMoney(suggested)})`
                      : "Quitar el precio propio"
                  }
                >
                  propio ↺
                </button>
              ) : (
                <span className={cn("whitespace-nowrap", MODE_COLOR[origin === "lista" ? "list" : "row"])}>
                  {origin}
                </span>
              )}
            </div>
            <div
              className={cn(
                "text-[11px] leading-tight tabular-nums",
                priced ? "text-slate-500" : "text-rose-600"
              )}
            >
              {!priced
                ? "falta precio"
                : mode === "kg"
                  ? `${formatWeight(cellWeight(c, l), "kg")} × ${fmtMoney(c.price_per_kg ?? 0)} = ${fmtMoney(cellTotal(c, col, l))}`
                  : mode === "total"
                    ? `→ ${fmtMoney(cellUnit(c, col, l))} c/u`
                    : `= ${fmtMoney(cellTotal(c, col, l))}`}
            </div>
            {c.before && <p className="text-[11px] text-slate-500">antes: {c.before}</p>}
            {own === "total" && priced && Math.abs(cellTotal(c, col, l) - (c.total_price ?? 0)) >= 0.005 && (
              <p className="text-[11px] text-amber-600">
                La compra suma {fmtMoney(cellTotal(c, col, l))}
              </p>
            )}
          </>
        )}
      </div>
    );
  };

  const renderColHeader = (col: PurchaseCol) => {
    const twin = cols.find(
      (o) => o.slot !== col.slot && o.third_party_id && o.third_party_id === col.third_party_id
    );
    return (
      <div className="space-y-1.5 text-left font-normal normal-case tracking-normal">
        <div className="flex items-center justify-between gap-2">
          <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">
            Compra {col.slot}
          </span>
          <button
            type="button"
            onClick={() => removeCol(col.slot)}
            className="text-slate-400 hover:text-red-500"
            title={`Quitar la compra ${col.slot}`}
          >
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
        <EntitySelect
          value={col.third_party_id}
          onChange={(v) => setColSupplier(col.slot, v)}
          options={supplierOptions}
          placeholder="Proveedor..."
        />
        <button
          type="button"
          onClick={() => setCreateFor(col.slot)}
          className="flex items-center gap-1 text-[11px] text-indigo-600 hover:underline"
        >
          <UserPlus className="h-3 w-3" />
          Crear proveedor
        </button>
        {twin && (
          <p className="text-[11px] text-slate-500">También en la compra {twin.slot} (otra recolección)</p>
        )}
        <Input
          value={col.invoice}
          onChange={(e) => updateCol(col.slot, { invoice: e.target.value })}
          maxLength={50}
          className="h-8 text-sm"
          placeholder="N° factura (opcional)"
        />
        <div className="grid grid-cols-2 gap-1 pt-0.5 text-[10px] font-semibold uppercase tracking-wider text-slate-400">
          <span>Cantidad</span>
          <span>Precio</span>
        </div>
      </div>
    );
  };

  /** T7/T9: % y monto en la misma fila, el % angosto; el monto siempre a la vista. */
  const renderRateAmount = (o: {
    rate: number;
    onRate: (v: number) => void;
    amount: number;
    onAmount: (v: number) => void;
    amountInvalid: boolean;
    rateLabel: string;
  }) => (
    <div className="grid grid-cols-[5.5rem_minmax(0,1fr)] gap-x-1 gap-y-0.5">
      <span className="text-[10px] text-slate-400">{o.rateLabel}</span>
      <span className="text-[10px] text-slate-400">Monto</span>
      <div className="relative" data-field="tax-rate">
        <MoneyInput
          value={o.rate}
          onChange={o.onRate}
          decimals={4}
          // T11: el monto se recalcula mientras se escribe el %
          liveChange
          className={cn("h-8 pr-5 text-sm", rateOutOfRange(o.rate) && "border-red-300")}
        />
        <span className="pointer-events-none absolute right-1.5 top-1/2 -translate-y-1/2 text-[11px] text-slate-400">
          %
        </span>
      </div>
      <div data-field="tax-amount">
      <MoneyInput
        value={o.amount}
        onChange={o.onAmount}
        decimals={2}
        className={cn("h-8 text-sm", o.amountInvalid && "border-red-300")}
      />
      </div>
    </div>
  );

  const renderFooter = (col: PurchaseCol) => {
    const st = statsBySlot.get(col.slot)!;
    if (st.rows.length === 0) {
      return <p className="text-xs text-slate-400">Sin materiales — no nace compra.</p>;
    }
    const suggestedIva = pctOf(st.subtotal, col.ivaRate);
    return (
      <div className="space-y-2 text-xs">
        <div className="flex items-baseline justify-between gap-2">
          <span className="text-slate-500">{st.qtyLabel}</span>
          {canViewPrices && (
            <span className="font-semibold tabular-nums text-slate-800">{fmtMoney(st.subtotal)}</span>
          )}
        </div>

        {/* IVA (§4): a la entidad [Impuestos] IVA; el proveedor queda con +IVA.
            Con alcance no hay IVA ni retenciones (S5): la liquida SAC. */}
        {!scoped && (<>
        <div className="space-y-1 border-t border-slate-100 pt-1.5">
          <label className="flex items-center gap-1.5 text-slate-600 cursor-pointer">
            <Checkbox
              checked={col.withIva}
              onCheckedChange={(v) =>
                updateCol(col.slot, { withIva: v === true, ivaRate: IVA_RATE_PCT, ivaTouched: false, ivaAmount: 0 })
              }
            />
            Con IVA
          </label>
          {col.withIva && (
            <>
              {renderRateAmount({
                rate: col.ivaRate,
                // T4: pasar por el % sin cambiarlo no cuenta como tocarlo
                onRate: (v) => {
                  const patch = ivaRatePatch(col.ivaRate, v);
                  if (patch) updateCol(col.slot, patch);
                },
                amount: st.iva,
                // C5: solo un valor DISTINTO congela el IVA; un Tab no
                onAmount: (v) => v !== st.iva && updateCol(col.slot, { ivaAmount: v, ivaTouched: true }),
                amountInvalid: st.iva <= 0,
                rateLabel: "% del subtotal",
              })}
              {rateWarning(col.ivaRate, IVA_RATE_PCT) && (
                <p className="text-[11px] text-amber-700">
                  {rateWarningText(col.ivaRate, IVA_RATE_PCT, "el IVA habitual")}
                </p>
              )}
              {col.ivaTouched && st.iva !== suggestedIva && (
                <button
                  type="button"
                  className="text-[11px] text-indigo-600 hover:underline"
                  onClick={() => updateCol(col.slot, { ivaTouched: false, ivaAmount: 0 })}
                >
                  Sugerido: {fmtMoney(suggestedIva)} ({fmtRate(col.ivaRate)}%)
                </button>
              )}
            </>
          )}
        </div>

        {/* Retenciones OPCIONALES de la compra (addendum #93) */}
        <div className="space-y-1 border-t border-slate-100 pt-1.5">
          <div className="flex items-center justify-between">
            <span className="text-slate-500">Retenciones</span>
            <button type="button" className="text-indigo-600 hover:underline" onClick={() => addRet(col.slot)}>
              + Retención
            </button>
          </div>
          {col.retentions.map((r) => {
            const cfg = configById.get(r.config_id);
            const ref = cfg?.rate_pct != null ? Number(cfg.rate_pct) : null;
            const amount = effRetAmount(r, st.subtotal);
            const suggested = pctOf(st.subtotal, r.rate);
            return (
              <div key={r._key} className="space-y-1">
                <div className="flex items-center gap-1">
                  <Select
                    value={r.config_id || undefined}
                    onValueChange={(v) => {
                      const next = configById.get(v);
                      if (next) updateRet(col.slot, r._key, (row) => withConfig(row, next));
                    }}
                  >
                    <SelectTrigger className={cn("h-8 text-xs flex-1 min-w-0", !r.config_id && "border-red-300")}>
                      <SelectValue placeholder="Tipo de retención..." />
                    </SelectTrigger>
                    <SelectContent>
                      {/* 🔴 CC-013 C2: una tarifa «sobre el IVA» no se precalcula
                          acá (% × subtotal); el servidor la rechaza. Q-68 abierta. */}
                      {retentionConfigs
                        .filter((c) => c.base_kind !== "iva" || c.config_id === r.config_id)
                        .map((c) => (
                          <SelectItem key={c.config_id} value={c.config_id as string}>
                            {retentionRowLabel(c)}
                            {c.config_id === defaultConfig?.config_id ? " · por defecto" : ""}
                          </SelectItem>
                        ))}
                    </SelectContent>
                  </Select>
                  <button
                    type="button"
                    onClick={() => removeRet(col.slot, r._key)}
                    className="text-slate-400 hover:text-red-500"
                    title="Quitar retención"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </div>
                {renderRateAmount({
                  rate: r.rate,
                  onRate: (v) => updateRet(col.slot, r._key, (row) => withRate(row, v)),
                  amount,
                  onAmount: (v) => v !== amount && updateRet(col.slot, r._key, (row) => withAmount(row, v)),
                  amountInvalid: st.subtotal > 0 && amount <= 0,
                  rateLabel: "% del subtotal",
                })}
                {!r.config_id && r.staleLabel && (
                  <p className="text-[11px] text-red-600">{staleNote(r.staleLabel)}</p>
                )}
                {ref != null && rateWarning(r.rate, ref) && (
                  <p className="text-[11px] text-amber-700">{rateWarningText(r.rate, ref, "la tarifa")}</p>
                )}
                {r.touched && amount !== suggested && (
                  <button
                    type="button"
                    className="text-[11px] text-indigo-600 hover:underline"
                    onClick={() => updateRet(col.slot, r._key, (row) => ({ ...row, touched: false, amount: 0 }))}
                  >
                    Sugerido: {formatCurrency(suggested)} ({fmtRate(r.rate)}%)
                  </button>
                )}
              </div>
            );
          })}
        </div>
        </>)}

        {/* Pago de contado OPCIONAL (#20 vía canal único). Sin marcar = crédito */}
        <div className="space-y-1 border-t border-slate-100 pt-1.5">
          <label className="flex items-center gap-1.5 text-slate-600 cursor-pointer">
            <Checkbox
              checked={col.paymentAccount !== null}
              onCheckedChange={(v) =>
                updateCol(col.slot, { paymentAccount: v === true ? accounts[0]?.id ?? "" : null })
              }
            />
            Pagar de contado
          </label>
          {col.paymentAccount !== null && (
            <Select
              value={col.paymentAccount || undefined}
              onValueChange={(v) => updateCol(col.slot, { paymentAccount: v })}
            >
              <SelectTrigger className={cn("h-8 text-xs", !col.paymentAccount && "border-red-300")}>
                <SelectValue placeholder="Cuenta..." />
              </SelectTrigger>
              <SelectContent>
                {accounts.map((acc) => (
                  <SelectItem key={acc.id} value={acc.id}>
                    {acc.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          )}
        </div>

        {canViewPrices && (st.iva > 0 || st.ret > 0) && (
          <div className="flex items-baseline justify-between gap-2 border-t border-slate-100 pt-1.5">
            <span className="text-slate-500">
              {col.paymentAccount !== null ? "Sale de la cuenta" : "A pagar"}
            </span>
            <span className="font-semibold tabular-nums text-slate-800">{fmtMoney(st.neto)}</span>
          </div>
        )}
      </div>
    );
  };

  const anyAllocated = lines.some((l) => activeCells(l).length > 0);
  const totalAll = activeCols.reduce((acc, c) => acc + (statsBySlot.get(c.slot)?.subtotal ?? 0), 0);
  const ivaAll = activeCols.reduce((acc, c) => acc + (statsBySlot.get(c.slot)?.iva ?? 0), 0);
  const retAll = activeCols.reduce((acc, c) => acc + (statsBySlot.get(c.slot)?.ret ?? 0), 0);

  return (
    <div className="space-y-6">
      <PageHeader
        title={`Liquidar Entrada #${order.order_number}`}
        description="Cada columna es una compra: elija el proveedor y ponga cuánto se le compró de cada material"
      >
        <Button variant="outline" onClick={() => navigate(backTo)}>
          <ArrowLeft className="h-4 w-4 mr-2" />
          Volver
        </Button>
      </PageHeader>

      {reliqBlocks.length > 0 && (
        <div className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800 space-y-0.5">
          {reliqBlocks.map((t) => (
            <p key={t}>{t}.</p>
          ))}
        </div>
      )}

      {recoveredAt !== null && (
        <div className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
          <span>Se recuperó el reparto sin liquidar ({formatDateTime(new Date(recoveredAt).toISOString())}).</span>
          <Button
            variant="outline"
            size="sm"
            className="bg-white w-full sm:w-auto"
            onClick={() => {
              if (draftKey) removeDraft(draftKey);
              setRecoveredAt(null);
              setInitialized(false);
            }}
          >
            Descartar borrador
          </Button>
        </div>
      )}

      {/* Ítem 2: el atajo del caso común — todo el camión de un proveedor */}
      <Card className="shadow-sm border-indigo-100 bg-indigo-50/40">
        <CardContent className="pt-4">
          <div className="flex flex-col sm:flex-row gap-2 sm:items-end">
            <div className="flex-1">
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                ¿Toda la entrada es de un solo proveedor?
              </Label>
              <EntitySelect
                value={bulkSupplier}
                onChange={setBulkSupplier}
                options={supplierOptions}
                placeholder="Proveedor..."
              />
            </div>
            <Button
              variant="outline"
              className="w-full sm:w-auto bg-white"
              onClick={applySingleSupplier}
              disabled={!bulkSupplier}
            >
              Repartir todo a este proveedor
            </Button>
          </div>
          <p className="text-xs text-slate-500 mt-1.5">
            Una sola compra con todo lo pesado; después puede ajustar celda por celda.
            {anyAllocated && <span className="text-amber-600"> Reemplaza el reparto actual.</span>}
          </p>
        </CardContent>
      </Card>

      {/* Escritorio: la hoja de Johana (Opción B: overflow + columna sticky) */}
      <Card className="shadow-sm hidden md:block">
        <CardContent className="p-0">
          {/* «Agregar compra» fuera de la tabla: como última columna quedaba
              cortado en el borde derecho apenas había dos compras. */}
          <div className="flex items-center justify-between gap-3 border-b border-slate-200 px-3 py-2">
            <span className="text-xs text-slate-500">
              {/* Plan v1.1 D4: cuenta lo mismo que el pie (activeCols); las
                  columnas vacías van aparte — no nace compra de ellas */}
              {activeCols.length === 0
                ? `${sortedCols.length === 1 ? "1 columna" : `${sortedCols.length} columnas`}, ninguna con materiales todavía`
                : `${activeCols.length === 1 ? "1 compra" : `${activeCols.length} compras`}${
                    emptyColCount > 0
                      ? ` · ${emptyColCount === 1 ? "1 columna" : `${emptyColCount} columnas`} sin materiales (no nace compra)`
                      : " — una columna por compra"
                  }`}
            </span>
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                scrollToNewColRef.current = true;
                addCol();
              }}
              className="whitespace-nowrap"
            >
              <Plus className="h-4 w-4 mr-1" />
              Agregar compra
            </Button>
          </div>
          <div ref={tableScrollRef} className="overflow-x-auto">
            <table className="min-w-full text-sm border-separate border-spacing-0">
              <thead>
                <tr className="align-top">
                  <th className="sticky left-0 z-20 bg-white border-b border-r border-slate-200 px-3 py-2 text-left text-xs font-semibold uppercase tracking-wider text-slate-500 min-w-[11rem]">
                    Material
                  </th>
                  <th className="border-b border-slate-200 px-3 py-2 text-left text-xs font-semibold uppercase tracking-wider text-slate-500 min-w-[7rem]">
                    Pesado
                  </th>
                  <th className="border-b border-slate-200 px-3 py-2 text-left text-xs font-semibold uppercase tracking-wider text-slate-500 min-w-[8rem]">
                    Precio base
                    <div className="mt-0.5 text-[10px] font-normal normal-case tracking-normal text-slate-400 leading-tight">
                      {BASE_PRICE_HINT}
                    </div>
                  </th>
                  <th className="border-b border-r border-slate-200 px-3 py-2 text-left text-xs font-semibold uppercase tracking-wider text-slate-500 min-w-[9rem]">
                    Descuadre
                  </th>
                  {sortedCols.map((col) => (
                    <th key={col.slot} className="border-b border-slate-200 bg-slate-50/60 px-3 py-2 min-w-[15rem] max-w-[17rem]">
                      {renderColHeader(col)}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {orderedLines.map((l) => (
                  <tr key={l._key} className="align-top">
                    <td className="sticky left-0 z-10 bg-white border-b border-r border-slate-100 px-3 py-2">
                      {renderMaterial(l)}
                    </td>
                    <td className="border-b border-slate-100 px-3 py-2">{renderWeighed(l)}</td>
                    <td className="border-b border-slate-100 px-3 py-2">{renderRowPrice(l)}</td>
                    <td className="border-b border-r border-slate-100 px-3 py-2">{renderDisc(l)}</td>
                    {sortedCols.map((col) => (
                      <td key={col.slot} className="border-b border-slate-100 bg-slate-50/30 px-3 py-2">
                        {renderCell(l, col)}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr className="align-top">
                  {/* QA C8: pegajosa SOLO la celda del ancho de Material, como en
                      el cuerpo; las otras tres columnas van en una celda normal */}
                  <td className="sticky left-0 z-10 bg-white border-r border-slate-100 px-3 py-3 text-xs font-semibold uppercase tracking-wider text-slate-500">
                    Cierre de cada compra
                  </td>
                  <td colSpan={3} className="border-r border-slate-100" />
                  {sortedCols.map((col) => (
                    <td key={col.slot} className="bg-slate-50/60 px-3 py-3">
                      {renderFooter(col)}
                    </td>
                  ))}
                </tr>
              </tfoot>
            </table>
          </div>
        </CardContent>
      </Card>

      {/* Celular: la matriz no cabe en 390 px — materiales y una tarjeta por compra */}
      <div className="md:hidden space-y-4">
        <Card className="shadow-sm">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-semibold uppercase tracking-wider text-slate-500">
              Materiales
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {orderedLines.map((l) => (
              <div key={l._key} className="rounded-lg border border-slate-200 p-3 space-y-2">
                <div className="flex items-start justify-between gap-2">
                  {renderMaterial(l)}
                  {renderWeighed(l)}
                </div>
                <div className="grid grid-cols-1 gap-2">
                  <div>
                    <Label className="text-[10px] font-semibold uppercase tracking-wider text-slate-400">
                      Precio base
                    </Label>
                    {renderRowPrice(l)}
                    <p className="text-[10px] text-slate-400 mt-0.5">{BASE_PRICE_HINT}</p>
                  </div>
                  {renderDisc(l)}
                </div>
              </div>
            ))}
          </CardContent>
        </Card>

        {sortedCols.map((col) => (
          <Card key={col.slot} className="shadow-sm">
            <CardHeader className="pb-2">{renderColHeader(col)}</CardHeader>
            <CardContent className="space-y-3">
              {orderedLines.map((l) => (
                <div key={l._key} className="space-y-1">
                  <div className="text-xs text-slate-600">
                    <span className="font-semibold">{l.material_code}</span>
                    <span className="text-slate-400"> · {formatWeight(l.weighed, l.material_unit)} pesado</span>
                  </div>
                  {renderCell(l, col)}
                </div>
              ))}
              <div className="border-t border-slate-200 pt-2">{renderFooter(col)}</div>
            </CardContent>
          </Card>
        ))}

        <Button variant="outline" onClick={addCol} className="w-full">
          <Plus className="h-4 w-4 mr-1" />
          Agregar compra
        </Button>
      </div>

      {/* D16: material reportado por proveedores que la báscula no vio.
          Con alcance no se ofrece: repartirlo deja descuadre (9g). */}
      {!scoped && (
      <Card className="shadow-sm border-dashed">
        <CardContent className="pt-4">
          <div className="flex flex-col sm:flex-row gap-2 sm:items-end">
            <div className="flex-1">
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                ¿Un proveedor reporta un material que la báscula no pesó?
              </Label>
              <EntitySelect
                value={extraMaterialId}
                onChange={setExtraMaterialId}
                options={extraOptions.map((m) => ({ id: m.id, label: `${m.code} - ${m.name}` }))}
                placeholder="Material a agregar al reparto..."
              />
            </div>
            <Button variant="outline" onClick={addExtraLine} disabled={!extraMaterialId}>
              <Plus className="h-4 w-4 mr-1" />
              Agregar al reparto
            </Button>
          </div>
          <p className="text-xs text-slate-400 mt-1.5">
            La fila nace con pesado 0 — todo lo repartido queda como faltante valorado al precio de la fila.
          </p>
        </CardContent>
      </Card>
      )}

      {/* D11: comisión del recolector — UNA por entrada, sobre lo pesado */}
      <Card className="shadow-sm">
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-semibold uppercase tracking-wider text-slate-500 flex items-center gap-2">
            <Truck className="h-4 w-4" />
            Comisión de Recolección
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {scoped ? (
            // Fila 9 (D-a): con alcance la comision la fija el servidor —
            // tarifa x lo pesado, a su recolector. Aca solo se informa.
            <p className="text-sm text-slate-600">
              {suggestedCommission > 0 ? (
                <>
                  Se causa a <strong>{collectorScope?.name}</strong>:{" "}
                  {canViewPrices && <strong>{formatCurrency(suggestedCommission)}</strong>}
                  {" "}— tarifa × {formatWeight(commissionBase.base)} pesados. La calcula el sistema.
                </>
              ) : (
                "Sin comisión: no hay tarifa de recolección vigente."
              )}
            </p>
          ) : (<>
          <label className="flex items-center gap-2 text-sm text-slate-600 cursor-pointer">
            <Checkbox
              checked={collectorEnabled}
              onCheckedChange={(v) => setCollectorEnabled(v === true)}
            />
            Causar comisión al recolector (gasto — jamás al costo del material)
          </label>
          {collectorEnabled && (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Recolector *</Label>
                <EntitySelect
                  value={collectorTpId}
                  onChange={setCollectorTpId}
                  options={collectors.map((c) => ({ id: c.id, label: c.name }))}
                  placeholder="Green Loop u otro..."
                />
              </div>
              <div>
                <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Monto *</Label>
                <MoneyInput
                  value={effCollectorAmount}
                  onChange={(v) => {
                    if (v === effCollectorAmount) return; // C5
                    setCollectorAmount(v);
                    setCollectorTouched(true);
                  }}
                  decimals={2}
                  placeholder="0"
                />
                {suggestedCommission > 0 && (
                  <p className="text-xs text-slate-400 mt-0.5">
                    Sugerido:{" "}
                    <button
                      type="button"
                      className="text-indigo-600 hover:underline"
                      onClick={() => {
                        setCollectorTouched(false);
                        setCollectorAmount(0);
                      }}
                    >
                      {formatCurrency(suggestedCommission)}
                    </button>{" "}
                    — tarifa × {formatWeight(commissionBase.base)} pesados
                    {tariffKgPerUnit != null ? ` (unidades a ${tariffKgPerUnit} kg c/u)` : ""}
                  </p>
                )}
                {commissionBase.unresolved && (
                  <p className="text-xs text-amber-600 mt-0.5">
                    Hay líneas por unidad y la tarifa no define kg/unidad — la base sugerida no las incluye.
                  </p>
                )}
              </div>
            </div>
          )}
          </>)}
        </CardContent>
      </Card>

      {problems.length > 0 && (
        <div className="rounded-md bg-red-50 border border-red-100 px-3 py-2 text-xs text-red-600 space-y-0.5">
          {problems.map((p) => (
            <p key={p}>{p}</p>
          ))}
        </div>
      )}
      {retAll > 0 && (
        <p className="text-xs text-slate-500">
          Cada retención acredita al proveedor por el <strong>neto</strong> y deja la deuda en su entidad
          [Retenciones]. Las tarifas se administran en Tesorería → Retenciones.
        </p>
      )}

      {/* Submit */}
      <div className="sticky bottom-0 bg-white/95 backdrop-blur-sm border-t border-slate-100 py-4 -mx-3 px-3 md:-mx-6 md:px-6 mt-6 pb-[max(1rem,env(safe-area-inset-bottom))]">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
          <div className="text-sm text-slate-500">
            {activeCols.length > 0 && (
              <>
                {activeCols.length} compra{activeCols.length === 1 ? "" : "s"}
                {canViewPrices && ` · ${fmtMoney(totalAll)}`}
                {ivaAll > 0 && canViewPrices && ` · IVA ${formatCurrency(ivaAll)}`}
                {retAll > 0 && canViewPrices && ` · retenciones ${formatCurrency(retAll)}`}
                {collectorEnabled && effCollectorAmount > 0 && canViewPrices &&
                  ` · comisión ${formatCurrency(effCollectorAmount)}`}
              </>
            )}
          </div>
          <div className="flex flex-col sm:flex-row gap-2">
            <Button variant="outline" onClick={() => navigate(backTo)} className="w-full sm:w-auto">
              Cancelar
            </Button>
            <Button
              onClick={handleSubmit}
              disabled={!canSubmit}
              className="bg-emerald-600 hover:bg-emerald-700 w-full sm:w-auto"
            >
              {liquidateOrder.isPending ? "Liquidando..." : "Liquidar Entrada"}
            </Button>
          </div>
        </div>
      </div>

      <CreateSupplierDialog
        open={createFor !== null}
        onOpenChange={(o) => !o && setCreateFor(null)}
        onCreated={(sid, name) => {
          setCreatedNames((prev) => ({ ...prev, [sid]: name }));
          if (createFor !== null) setColSupplier(createFor, sid);
        }}
      />
    </div>
  );
}

function GuardMessage({ text, onBack }: { text: string; onBack: () => void }) {
  return (
    <div className="p-8 text-center space-y-4">
      <p className="text-slate-600">{text}</p>
      <Button variant="outline" onClick={onBack}>
        <ArrowLeft className="h-4 w-4 mr-2" />
        Volver
      </Button>
    </div>
  );
}
