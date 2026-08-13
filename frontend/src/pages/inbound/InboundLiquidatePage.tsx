import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import { ArrowLeft, Plus, Scale, Trash2, Truck } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { PageHeader } from "@/components/shared/PageHeader";
import { EntitySelect } from "@/components/shared/EntitySelect";
import { MoneyInput } from "@/components/shared/MoneyInput";
import { usePermissions } from "@/hooks/usePermissions";
import { useInboundOrder, useLiquidateInboundOrder } from "@/hooks/useInboundOrders";
import {
  useMaterials,
  usePayableProviders,
  useRetentionRows,
  useSuppliers,
} from "@/hooks/useMasterData";
import { retentionRowLabel } from "@/pages/treasury/RetentionsPage";
import { useCurrentTariffs, useKgProfiles } from "@/hooks/useSacConfig";
import { useKgAccounts } from "@/hooks/useKgLedger";
import { useMoneyAccounts } from "@/hooks/useMasterData";
import { useOrgSettings } from "@/hooks/useOrgSettings";
import { formatCurrency, formatWeight } from "@/utils/formatters";
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
  InboundSupplierRetentions,
} from "@/types/inbound-order";

/**
 * #93 — Reparto de proveedores (liquidación de la Entrada).
 *
 * Lo PESADO es la verdad física (inventario); lo REPARTIDO es la verdad
 * comercial (compras por proveedor). La diferencia por material es el
 * DESCUADRE, valorado al precio de referencia (D6) — visible en vivo, con
 * la tolerancia de la org como semáforo (D8: avisa, jamás bloquea por monto).
 */

let allocKeyCounter = 0;

interface AllocRow {
  _key: number;
  third_party_id: string;
  quantity: number;
  unit_price: number;
  /** Q-15: si NO es null, Johana digitó el valor total y el unitario es una
   *  fórmula (total / cantidad). null = digitó el unitario, como siempre. */
  total_price: number | null;
}

interface LineState {
  _key: number;
  material_id: string;
  material_code: string;
  material_name: string;
  material_unit: string;
  /** cantidad pesada (0 = material de reparto que la báscula no vio, D16) */
  weighed: number;
  /** Q-13: peso de báscula certificado en la revisión. Es literalmente la
   *  pregunta de Hugo en vivo — "¿dónde sale aquí el peso de lo que acabamos
   *  de traer?" —: se capturaba y esta pantalla nunca lo mostraba. NO entra a
   *  ningún cálculo: Johana lo mira para decidir el precio. */
  weightKg: number | null;
  isExtra: boolean;
  refPrice: number;
  refTouched: boolean;
  unallocated: boolean;
  allocations: AllocRow[];
}

function newAlloc(price = 0): AllocRow {
  return {
    _key: ++allocKeyCounter,
    third_party_id: "",
    quantity: 0,
    unit_price: price,
    total_price: null,
  };
}

/** Q-15/D8: el efecto REAL del valor total digitado. El backend deriva el
 *  unitario a 2 decimales y después re-multiplica, así que $200.000 entre 3
 *  vuelven como $200.000,01. Se calcula igual acá para que el centavo nunca
 *  sea una sorpresa contra la factura: se acepta, pero se muestra.
 *
 *  ⚠️ La vista previa puede diferir en 1 centavo del valor persistido en un
 *  empate exacto: acá es `Math.round` sobre float (half up) y allá
 *  `Decimal.quantize` (HALF_EVEN). Igualar el modo de redondeo NO lo cierra —
 *  float y Decimal difieren en la representación, no solo en el redondeo — y
 *  pintar el número del servidor exigiría un round-trip que antes de guardar
 *  no existe. Con montos en pesos el empate al medio centavo no ocurre. */
const effUnitPrice = (a: AllocRow): number =>
  a.total_price != null && a.quantity > 0
    ? Math.round((a.total_price / a.quantity) * 100) / 100
    : a.unit_price;

const effAllocTotal = (a: AllocRow): number => a.quantity * effUnitPrice(a);

/** Una asignación está completa si tiene proveedor, cantidad y ALGUNO de los
 *  dos precios — no siempre el unitario (Q-15). */
const allocPriced = (a: AllocRow): boolean =>
  a.total_price != null ? a.total_price > 0 : a.unit_price > 0;

/** Fila de retención por proveedor (patrón RetentionFormData de
 *  PurchaseLiquidatePage: monto vigente solo cuando touched) */
interface RetRow {
  _key: number;
  config_id: string;
  amount: number;
  touched: boolean;
}

let retRowCounter = 0;

function newRetRow(): RetRow {
  return { _key: ++retRowCounter, config_id: "", amount: 0, touched: false };
}

/** El backend serializa Decimal como STRING en JSON ("530.0000") aunque el
 *  tipo TS diga number — sin coerción, `acc + a.quantity` concatena texto y el
 *  repartido/descuadre sale NaN al precargar un reparto (bug encontrado en
 *  pruebas: solo aparece tras des-liquidar, porque en la primera captura los
 *  valores los digita el usuario y sí son números). */
const num = (v: unknown, fallback = 0): number => {
  const n = Number(v);
  return Number.isFinite(n) ? n : fallback;
};

function initLines(order: InboundOrderResponse): LineState[] {
  return order.lines.map((l, idx) => ({
    _key: idx + 1,
    material_id: l.material_id,
    material_code: l.material_code ?? "",
    material_name: l.material_name ?? "",
    material_unit: l.material_unit || "kg",
    weighed: num(l.quantity),
    weightKg: l.scale_weight_kg != null ? num(l.scale_weight_kg) : null,
    isExtra: false,
    refPrice: num(l.reference_unit_price ?? l.unit_price ?? 0),
    refTouched: l.reference_unit_price != null,
    unallocated: l.unallocated_intentional,
    // Re-liquidación (D20): el reparto anterior se conserva — precargar
    allocations: l.allocations.map((a) => ({
      _key: ++allocKeyCounter,
      third_party_id: a.third_party_id,
      quantity: num(a.quantity),
      unit_price: num(a.unit_price),
      // El MODO es parte del reparto: si se guardó por total, se re-abre por
      // total. Sin esto Johana vería un unitario derivado en vez de lo suyo.
      total_price: a.total_price != null ? num(a.total_price) : null,
    })),
  }));
}

export default function InboundLiquidatePage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const returnTo = searchParams.get("returnTo");
  const { hasPermission } = usePermissions();
  const canViewPrices = hasPermission("purchases.view_prices");

  const { data: order, isLoading } = useInboundOrder(id!);
  const liquidateOrder = useLiquidateInboundOrder();
  const { getSetting } = useOrgSettings();

  const { data: suppliersData } = useSuppliers();
  const { data: collectorsData } = usePayableProviders();
  const { data: materialsData } = useMaterials();
  const { data: profilesData } = useKgProfiles();
  const { data: tariffsData } = useCurrentTariffs();
  const { data: kgAccountsData } = useKgAccounts();
  const { data: accountsData } = useMoneyAccounts();

  const collectors = collectorsData?.items ?? [];
  const materials = materialsData?.items ?? [];
  const accounts = (accountsData?.items ?? []).filter((a) => a.is_active);

  // El titular de una cuenta kg NO es proveedor de compra (#80: "lo Willard
  // nunca es compra"). El backend lo defiende con 422; esto evita ofrecerlo.
  const suppliers = useMemo(() => {
    const holders = new Set(
      (kgAccountsData ?? [])
        .filter((a) => a.is_active && a.third_party_id)
        .map((a) => a.third_party_id as string)
    );
    return (suppliersData?.items ?? []).filter((s) => !holders.has(s.id));
  }, [suppliersData, kgAccountsData]);

  // D8: tolerancia de descuadre de la org (fracción, ej. 0.05 = 5%)
  const tolerance = Number(getSetting("inbound_discrepancy_tolerance_pct") ?? 0.05);

  const [lines, setLines] = useState<LineState[]>([]);
  const [initialized, setInitialized] = useState(false);
  // D11: UNA comisión por entrada, sobre lo pesado
  const [collectorEnabled, setCollectorEnabled] = useState(false);
  const [collectorTpId, setCollectorTpId] = useState("");
  const [collectorAmount, setCollectorAmount] = useState(0);
  const [collectorTouched, setCollectorTouched] = useState(false);
  // D5/D12: factura POR PROVEEDOR (se estampa en sus asignaciones)
  const [invoiceBySupplier, setInvoiceBySupplier] = useState<Record<string, string>>({});
  // Addendum retenciones #93: bloques OPCIONALES por proveedor ("sí les
  // descuenta, pero no a todas"). touched=false → sugerido % × subtotal vivo
  const [retentionsBySupplier, setRetentionsBySupplier] = useState<
    Record<string, RetRow[]>
  >({});
  // Pago de contado por proveedor (opcional, como las retenciones): tpId ->
  // cuenta. Ausente = se le queda debiendo, que es el camino normal.
  const [paymentBySupplier, setPaymentBySupplier] = useState<Record<string, string>>({});
  const [extraMaterialId, setExtraMaterialId] = useState("");
  // Ítem 2 (Hugo): el caso más común es que todo el camión sea de un proveedor
  const [bulkSupplier, setBulkSupplier] = useState("");

  // Catálogo de retenciones (v2 #79) — la ruta ya está gated por el flag (FP),
  // enabled=true no fuga requests a orgs sin SAC
  const { data: retentionRows } = useRetentionRows(true);
  const retentionConfigs = useMemo(
    () => (retentionRows ?? []).filter((r) => r.config_id && r.is_active),
    [retentionRows],
  );
  const configById = useMemo(
    () => new Map(retentionConfigs.map((r) => [r.config_id as string, r])),
    [retentionConfigs],
  );

  useEffect(() => {
    // Espera al catálogo: la precarga necesita mapear cada retención guardada
    // a su tarifa (por tipo + municipio), y sin catálogo no hay a qué mapear
    if (order && !initialized && retentionRows) {
      setLines(initLines(order));
      setCollectorEnabled(!!order.collector_id);
      setCollectorTpId(order.collector_id ?? "");
      // Precarga del último lote de retenciones por proveedor (pruebas
      // Daniel: si el reparto se conserva al des-liquidar, la retención
      // también — es lo que más se corrige). El monto va como `touched` para
      // que NO se recalcule al vuelo: si Johana lo había editado a mano,
      // reaparece tal cual lo dejó.
      const preload: Record<string, RetRow[]> = {};
      for (const p of order.purchases) {
        const rows = (p.retentions ?? [])
          .map((r) => {
            const cfg = retentionConfigs.find(
              (c) =>
                c.retention_type === r.retention_type &&
                (c.municipality ?? null) === (r.municipality ?? null),
            );
            if (!cfg?.config_id) return null;   // tarifa borrada: se re-elige
            return {
              _key: ++retRowCounter,
              config_id: cfg.config_id,
              amount: num(r.amount),
              touched: true,
            } as RetRow;
          })
          .filter(Boolean) as RetRow[];
        if (rows.length) preload[p.supplier_id] = rows;
      }
      if (Object.keys(preload).length) setRetentionsBySupplier(preload);
      setInitialized(true);
    }
  }, [order, initialized, retentionRows, retentionConfigs]);

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

  // Tarifa vigente comision_green_loop (precio + regla de los 14 kg/unidad)
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

  // Resumen por proveedor (las N compras que van a nacer). Regla de Hooks:
  // TODOS los hooks van antes de los `return` condicionales de abajo — si un
  // useMemo queda después de un guard, el conteo de hooks difiere entre el
  // render "Cargando..." (guard activo) y el render con datos (guard pasado)
  // y React revienta con "Rendered more hooks than during the previous
  // render" (bug real encontrado en pruebas manuales — pantalla en blanco en
  // TODA liquidación, no solo con retenciones; tsc/build no lo detectan).
  const supplierSummary = useMemo(() => {
    // Cantidad POR UNIDAD (#54): un proveedor puede traer 530 kg de scrap y 60
    // baterías por unidad — sumarlos en un solo número y llamarlo "kg" es un
    // dato falso (bug encontrado en pruebas: "590 kg repartidos")
    const map = new Map<
      string,
      {
        name: string;
        total: number;
        qtyByUnit: Record<string, number>;
        // Detalle por material (pruebas de usuario): la card decía solo el
        // total, y Johana no podía verificar QUÉ le está comprando a cada uno
        materials: { code: string; qty: number; unit: string; price: number }[];
      }
    >();
    for (const l of lines) {
      for (const a of l.allocations) {
        if (!a.third_party_id || a.quantity <= 0) continue;
        const name = suppliers.find((s) => s.id === a.third_party_id)?.name ?? "—";
        const entry =
          map.get(a.third_party_id) ??
          { name, total: 0, qtyByUnit: {}, materials: [] };
        // Q-15/D8: el resumen muestra el efecto REAL (unitario derivado y
        // re-multiplicado), no el total digitado — es donde el centavo se ve
        entry.total += effAllocTotal(a);
        entry.qtyByUnit[l.material_unit] =
          (entry.qtyByUnit[l.material_unit] ?? 0) + a.quantity;
        entry.materials.push({
          code: l.material_code || l.material_name || "—",
          qty: a.quantity,
          unit: l.material_unit,
          price: effUnitPrice(a),
        });
        map.set(a.third_party_id, entry);
      }
    }
    return [...map.entries()].map(([tpId, v]) => ({
      tpId,
      name: v.name,
      total: v.total,
      materials: v.materials,
      // "530 kg + 60 unidad" cuando hay mezcla; "530 kg" cuando no
      qtyLabel: Object.entries(v.qtyByUnit)
        .map(([unit, qty]) => formatWeight(qty, unit))
        .join(" + "),
    }));
  }, [lines, suppliers]);

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

  // ---------- mutadores ----------

  const updateLine = (key: number, patch: Partial<LineState>) => {
    setLines((prev) => prev.map((l) => (l._key === key ? { ...l, ...patch } : l)));
  };

  const updateAlloc = (
    lineKey: number,
    allocKey: number,
    patch: Partial<Omit<AllocRow, "_key">>
  ) => {
    setLines((prev) =>
      prev.map((l) => {
        if (l._key !== lineKey) return l;
        const allocations = l.allocations.map((a) =>
          a._key === allocKey ? { ...a, ...patch } : a
        );
        // "Reutilizar el primer precio digitado" (respuesta Daniel): si la
        // referencia sigue virgen, el primer precio del reparto la llena.
        // Q-15: si se digitó el TOTAL, la llena el unitario derivado — es el
        // mismo precio expresado distinto, así que se lee del efectivo y no
        // del campo, que puede venir vacío en modo total.
        let refPrice = l.refPrice;
        if (!l.refTouched && refPrice <= 0) {
          const touched = allocations.find((a) => a._key === allocKey);
          const eff = touched ? effUnitPrice(touched) : 0;
          if (eff > 0) refPrice = eff;
        }
        return { ...l, allocations, refPrice };
      })
    );
  };

  /** Q-15: cambiar entre unitario y total NO pierde el número — se convierte
   *  con la cantidad vigente. Sin cantidad no hay conversión posible y el
   *  campo arranca en 0 (la validación lo marca incompleto, que es honesto). */
  const toggleAllocMode = (lineKey: number, allocKey: number) => {
    setLines((prev) =>
      prev.map((l) => {
        if (l._key !== lineKey) return l;
        return {
          ...l,
          allocations: l.allocations.map((a) => {
            if (a._key !== allocKey) return a;
            if (a.total_price != null) {
              return { ...a, unit_price: effUnitPrice(a), total_price: null };
            }
            return {
              ...a,
              total_price:
                a.quantity > 0 ? Math.round(a.unit_price * a.quantity * 100) / 100 : 0,
            };
          }),
        };
      })
    );
  };

  const addAlloc = (lineKey: number) => {
    setLines((prev) =>
      prev.map((l) =>
        l._key === lineKey
          ? { ...l, unallocated: false, allocations: [...l.allocations, newAlloc(l.refPrice)] }
          : l
      )
    );
  };

  const removeAlloc = (lineKey: number, allocKey: number) => {
    setLines((prev) =>
      prev.map((l) =>
        l._key === lineKey
          ? { ...l, allocations: l.allocations.filter((a) => a._key !== allocKey) }
          : l
      )
    );
  };

  /**
   * Ítem 2 — Hugo: *"no le carga las cantidades al llamar el proveedor de lo
   * que tenga pendiente"*. Pide más de lo que suena: no es fijar el tercero,
   * es pre-llenar el reparto con lo pesado.
   *
   * Las líneas con pesado 0 NO reciben asignación (una asignación en 0 es
   * inválida y quedarían bloqueando la pantalla): las capturadas en 0 se
   * marcan "sin proveedor" —con descuadre 0 eso es inerte, ni ajuste ni P&L—
   * y los extras del D16 se dejan quietos, que se agregaron a mano para
   * asignarlos a mano.
   */
  const applySingleSupplier = () => {
    if (!bulkSupplier) return;
    setLines((prev) =>
      prev.map((l) => {
        if (l.weighed <= 0) {
          return l.isExtra ? l : { ...l, unallocated: true };
        }
        // Conserva el precio ya digitado en la línea, venga del modo que venga
        const priced = l.allocations.find((a) => allocPriced(a));
        return {
          ...l,
          unallocated: false,
          allocations: [
            {
              _key: ++allocKeyCounter,
              third_party_id: bulkSupplier,
              quantity: l.weighed,
              unit_price: priced ? effUnitPrice(priced) : l.refPrice,
              total_price: null,
            },
          ],
        };
      })
    );
  };

  const addExtraLine = () => {
    const mat = materials.find((m) => m.id === extraMaterialId);
    if (!mat) return;
    setLines((prev) => [
      ...prev,
      {
        _key: prev.length + 1000,
        material_id: mat.id,
        material_code: mat.code,
        material_name: mat.name,
        material_unit: mat.default_unit || "kg",
        weighed: 0,
        weightKg: null, // material que la báscula no vio (D16)
        isExtra: true,
        refPrice: 0,
        refTouched: false,
        unallocated: false,
        allocations: [newAlloc()],
      },
    ]);
    setExtraMaterialId("");
  };

  // ---------- derivados ----------

  const lineAllocated = (l: LineState) =>
    l.allocations.reduce((acc, a) => acc + (a.quantity > 0 ? a.quantity : 0), 0);

  const lineDisc = (l: LineState) => l.weighed - lineAllocated(l);

  const activeAllocs = (l: LineState) =>
    l.allocations.filter((a) => a.third_party_id && a.quantity > 0);

  // ---------- retenciones por proveedor (addendum #93) ----------

  const suggestedRet = (configId: string, supplierTotal: number) => {
    const cfg = configById.get(configId);
    if (!cfg || cfg.rate_pct == null) return 0;
    return Math.round(supplierTotal * cfg.rate_pct) / 100; // % × subtotal a 2 dec
  };
  const effRetAmount = (r: RetRow, supplierTotal: number) =>
    r.touched ? r.amount : suggestedRet(r.config_id, supplierTotal);
  const supplierRetTotal = (tpId: string, supplierTotal: number) =>
    (retentionsBySupplier[tpId] ?? []).reduce(
      (acc, r) => acc + effRetAmount(r, supplierTotal), 0);

  const updateRet = (tpId: string, key: number, patch: Partial<RetRow>) =>
    setRetentionsBySupplier((prev) => ({
      ...prev,
      [tpId]: (prev[tpId] ?? []).map((r) => (r._key === key ? { ...r, ...patch } : r)),
    }));
  const removeRet = (tpId: string, key: number) =>
    setRetentionsBySupplier((prev) => ({
      ...prev,
      [tpId]: (prev[tpId] ?? []).filter((r) => r._key !== key),
    }));

  // Solo cuentan proveedores QUE SIGUEN en el reparto — editar asignaciones
  // puede sacar a uno y sus filas quedan huérfanas (no viajan ni validan)
  const retentionProblems: string[] = [];
  for (const s of supplierSummary) {
    const rows = retentionsBySupplier[s.tpId] ?? [];
    if (rows.length === 0) continue;
    // Tres causas distintas, tres mensajes distintos. "Falta tarifa o monto"
    // mandaba a revisar el selector incluso con la tarifa bien puesta: el monto
    // sale $0 porque el % se calcula sobre un subtotal de $0, y el usuario no
    // tenía cómo saberlo (pruebas Daniel).
    if (rows.some((r) => !r.config_id)) {
      retentionProblems.push(`Retenciones de ${s.name}: falta elegir la tarifa`);
    } else if (s.total <= 0) {
      retentionProblems.push(
        `Retenciones de ${s.name}: su subtotal es $0, no hay base sobre la cual ` +
        `retener — ponga los precios del reparto o quite la retención`
      );
    } else if (rows.some((r) => effRetAmount(r, s.total) <= 0)) {
      retentionProblems.push(`Retenciones de ${s.name}: el monto quedó en $0`);
    } else if (supplierRetTotal(s.tpId, s.total) >= s.total) {
      retentionProblems.push(
        `Retenciones de ${s.name} deben ser menores a su total (${formatCurrency(s.total)})`
      );
    }
  }
  const totalRetAll = supplierSummary.reduce(
    (acc, s) => acc + supplierRetTotal(s.tpId, s.total), 0);

  // Marcar "pagar de contado" sin cuenta es un error silencioso: el bloque no
  // viajaría y la compra nacería a crédito sin avisar
  for (const s of supplierSummary) {
    if (paymentBySupplier[s.tpId] !== undefined && !paymentBySupplier[s.tpId]) {
      retentionProblems.push(`Pago de contado de ${s.name}: falta la cuenta`);
    }
  }

  // ---------- validación ----------

  const lineProblems = (l: LineState): string | null => {
    const active = activeAllocs(l);
    // Q-15: "precio" es el unitario O el total, según el modo de la fila
    const halfFilled = l.allocations.some(
      (a) => (a.third_party_id || a.quantity > 0) && !(a.third_party_id && a.quantity > 0 && allocPriced(a))
    );
    if (halfFilled) return "Hay asignaciones incompletas (proveedor, cantidad y precio)";
    const ids = active.map((a) => a.third_party_id);
    if (new Set(ids).size !== ids.length) return "El mismo proveedor aparece dos veces";
    if (active.length === 0 && !l.unallocated) {
      return "Sin asignaciones — reparta o marque \"sin proveedor (intencional)\"";
    }
    if (lineDisc(l) !== 0 && l.refPrice <= 0) {
      // El mensaje explica POR QUÉ hace falta (pruebas de usuario: marcar
      // "sin proveedor" y seguir bloqueado sin saber la razón desconcierta)
      const disc = lineDisc(l);
      const qty = `${formatWeight(Math.abs(disc), l.material_unit)}`;
      return l.unallocated
        ? `Falta el precio de referencia: con él se valoran los ${qty} que entran como ganancia`
        : `Falta el precio de referencia: con él se valora el descuadre de ${qty}`;
    }
    return null;
  };

  const problems = lines.map((l) => lineProblems(l)).filter(Boolean) as string[];
  const collectorValid = !collectorEnabled || (!!collectorTpId && effCollectorAmount > 0);
  const canSubmit =
    problems.length === 0 && retentionProblems.length === 0 &&
    collectorValid && !liquidateOrder.isPending;

  const handleSubmit = () => {
    if (!canSubmit) return;
    const payloadLines: InboundLiquidateLine[] = lines.map((l) => ({
      material_id: l.material_id,
      reference_unit_price: l.refPrice > 0 ? l.refPrice : null,
      unallocated_intentional: activeAllocs(l).length === 0 && l.unallocated,
      allocations: activeAllocs(l).map((a) => ({
        third_party_id: a.third_party_id,
        quantity: a.quantity,
        // Q-15: viaja UNO de los dos — mandar ambos es 422 del backend
        ...(a.total_price != null
          ? { total_price: a.total_price }
          : { unit_price: a.unit_price }),
        invoice_number: invoiceBySupplier[a.third_party_id]?.trim() || null,
      })),
    }));
    // Bloques por proveedor — solo los que siguen en el reparto y tienen filas
    const supplierRetentionBlocks = supplierSummary
      .map((s) => {
        const rows = (retentionsBySupplier[s.tpId] ?? []).filter((r) => r.config_id);
        if (rows.length === 0) return null;
        return {
          third_party_id: s.tpId,
          retentions: rows.map((r) => {
            const cfg = configById.get(r.config_id)!;
            return {
              retention_type: cfg.retention_type,
              ...(cfg.retention_type === "ica" && cfg.municipality
                ? { municipality: cfg.municipality }
                : {}),
              amount: effRetAmount(r, s.total),
              // Auditoría del precálculo ofrecido (F1: el backend los persiste)
              ...(cfg.rate_pct != null ? { rate: cfg.rate_pct, base: s.total } : {}),
            };
          }),
        };
      })
      .filter(Boolean) as InboundSupplierRetentions[];
    // Pago de contado: igual que arriba, solo proveedores vigentes con cuenta
    const supplierPaymentBlocks = supplierSummary
      .filter((s) => paymentBySupplier[s.tpId])
      .map((s) => ({ third_party_id: s.tpId, account_id: paymentBySupplier[s.tpId] }));
    liquidateOrder.mutate(
      {
        id: order.id,
        data: {
          lines: payloadLines,
          collector_commission:
            collectorEnabled && collectorTpId && effCollectorAmount > 0
              ? { third_party_id: collectorTpId, amount: effCollectorAmount }
              : null,
          // Ausente (no []) sin bloques — data-gate D9
          ...(supplierRetentionBlocks.length > 0
            ? { supplier_retentions: supplierRetentionBlocks }
            : {}),
          ...(supplierPaymentBlocks.length > 0
            ? { supplier_payments: supplierPaymentBlocks }
            : {}),
        },
      },
      {
        onSuccess: () => navigate(buildRoute(ROUTES.INBOUND_DETAIL, { id: order.id })),
      }
    );
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title={`Liquidar Entrada #${order.order_number}`}
        description="Reparta cada material entre sus proveedores — lo pesado es la verdad física, el reparto es la comercial"
      >
        <Button variant="outline" onClick={() => navigate(backTo)}>
          <ArrowLeft className="h-4 w-4 mr-2" />
          Volver
        </Button>
      </PageHeader>

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
                options={suppliers.map((s) => ({ id: s.id, label: s.name }))}
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
            Carga cada material con lo pesado; después puede ajustar línea por línea.
            {lines.some((l) => activeAllocs(l).length > 0) && (
              <span className="text-amber-600"> Reemplaza el reparto actual.</span>
            )}
          </p>
        </CardContent>
      </Card>

      {/* Lineas con reparto */}
      {lines.map((l) => {
        const allocated = lineAllocated(l);
        const disc = lineDisc(l);
        const pct = l.weighed > 0 ? Math.abs(disc) / l.weighed : null;
        const discState =
          disc === 0 ? "ok" : pct != null && pct <= tolerance ? "within" : "out";
        const problem = lineProblems(l);
        return (
          <Card key={l._key} className="shadow-sm">
            <CardHeader className="pb-2">
              <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
                <CardTitle className="text-base">
                  <span className="font-semibold">{l.material_code}</span>
                  <span className="text-slate-500 font-normal"> — {l.material_name}</span>
                  {l.isExtra && (
                    <span className="ml-2 text-xs font-normal text-amber-600">
                      no pesado en la entrada (entra con faltante completo)
                    </span>
                  )}
                </CardTitle>
                <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm">
                  <div className="flex items-center gap-2">
                    <Scale className="h-4 w-4 text-slate-400" />
                    <span className="text-slate-500">Pesado:</span>
                    <span className="font-semibold tabular-nums">
                      {formatWeight(l.weighed, l.material_unit)}
                    </span>
                  </div>
                  {/* Q-13: el peso de báscula que certificó el revisor. Se
                      capturaba desde E2 y esta pantalla nunca lo mostró — es
                      exactamente lo que Hugo preguntó en la reunión. Solo
                      aparece cuando dice algo que la cantidad no dice ya. */}
                  {l.weightKg != null &&
                    (l.material_unit !== "kg" || l.weightKg !== l.weighed) && (
                      <div className="flex items-center gap-2 sm:border-l sm:pl-3">
                        <span className="text-slate-500">Báscula:</span>
                        <span className="font-semibold tabular-nums text-indigo-700">
                          {formatWeight(l.weightKg, "kg")}
                        </span>
                      </div>
                    )}
                </div>
              </div>
            </CardHeader>
            <CardContent className="space-y-3">
              {/* Asignaciones */}
              {l.allocations.map((a) => (
                <div key={a._key} className="grid grid-cols-1 md:grid-cols-12 gap-2 items-end">
                  <div className="md:col-span-4">
                    <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Proveedor</Label>
                    <EntitySelect
                      value={a.third_party_id}
                      onChange={(v) => updateAlloc(l._key, a._key, { third_party_id: v })}
                      options={suppliers.map((s) => ({ id: s.id, label: s.name }))}
                      placeholder="Proveedor..."
                    />
                  </div>
                  <div className="md:col-span-3">
                    <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                      Cantidad ({l.material_unit})
                    </Label>
                    <MoneyInput
                      value={a.quantity}
                      onChange={(v) => updateAlloc(l._key, a._key, { quantity: v })}
                      /* 3 decimales: es la escala real con la que se guarda
                         (ALLOC_Q) y con la que entra al inventario — un 4º
                         decimal se perdía en silencio */
                      decimals={3}
                      placeholder="0"
                    />
                  </div>
                  {/* Q-15: Johana digita el VALOR TOTAL; el unitario es una
                      fórmula (total / cantidad). El modo es por asignación
                      porque cada proveedor negocia su precio. */}
                  <div className="md:col-span-4">
                    <div className="flex items-baseline justify-between gap-2">
                      <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                        {a.total_price != null ? "Valor total" : "Precio unit."}
                      </Label>
                      <button
                        type="button"
                        className="text-[11px] text-indigo-600 hover:underline"
                        onClick={() => toggleAllocMode(l._key, a._key)}
                      >
                        {a.total_price != null ? "usar precio unit." : "usar valor total"}
                      </button>
                    </div>
                    <MoneyInput
                      value={a.total_price != null ? a.total_price : a.unit_price}
                      onChange={(v) =>
                        updateAlloc(
                          l._key,
                          a._key,
                          a.total_price != null ? { total_price: v } : { unit_price: v }
                        )
                      }
                      decimals={2}
                      placeholder="0"
                    />
                    {a.quantity > 0 && allocPriced(a) && (
                      <p
                        className={cn(
                          "text-xs mt-0.5 tabular-nums",
                          a.total_price != null &&
                            Math.abs(effAllocTotal(a) - a.total_price) >= 0.005
                            ? "text-amber-600"
                            : "text-slate-400"
                        )}
                      >
                        {a.total_price != null
                          ? // D8: el total que realmente queda. $200.000 entre 3
                            // vuelven como $200.000,01 — se acepta, pero se ve
                            `${formatCurrency(effUnitPrice(a))} c/u → ${formatCurrency(effAllocTotal(a))}`
                          : `Total ${formatCurrency(effAllocTotal(a))}`}
                      </p>
                    )}
                  </div>
                  <div className="md:col-span-1 flex justify-end">
                    <Button
                      variant="ghost"
                      size="icon"
                      className="text-slate-400 hover:text-red-500"
                      onClick={() => removeAlloc(l._key, a._key)}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              ))}

              <div className="flex flex-col sm:flex-row sm:items-center gap-2">
                <Button variant="outline" size="sm" onClick={() => addAlloc(l._key)}>
                  <Plus className="h-4 w-4 mr-1" />
                  Agregar proveedor
                </Button>
                {activeAllocs(l).length === 0 && (
                  <label className="flex items-center gap-2 text-sm text-slate-600 cursor-pointer">
                    <Checkbox
                      checked={l.unallocated}
                      onCheckedChange={(v) => updateLine(l._key, { unallocated: v === true })}
                    />
                    Sin proveedor (intencional) — entra completo como {disc >= 0 ? "ganancia" : "pérdida"}
                  </label>
                )}
              </div>

              {/* Descuadre en vivo + precio de referencia */}
              <div
                className={cn(
                  "rounded-lg border p-3 flex flex-col sm:flex-row sm:items-center gap-3",
                  discState === "ok" && "border-emerald-200 bg-emerald-50",
                  discState === "within" && "border-amber-200 bg-amber-50",
                  discState === "out" && "border-rose-200 bg-rose-50"
                )}
              >
                <div className="flex-1 text-sm">
                  <div className="flex flex-wrap gap-x-4 gap-y-1">
                    <span>
                      Repartido:{" "}
                      <span className="font-semibold tabular-nums">
                        {formatWeight(allocated, l.material_unit)}
                      </span>
                    </span>
                    <span>
                      Descuadre:{" "}
                      <span
                        className={cn(
                          "font-semibold tabular-nums",
                          disc === 0 ? "text-emerald-700" : disc > 0 ? "text-emerald-700" : "text-rose-700"
                        )}
                      >
                        {disc > 0 ? "+" : ""}
                        {formatWeight(disc, l.material_unit)}
                        {pct != null && disc !== 0 && (
                          <span className="font-normal"> ({(pct * 100).toFixed(1)}%)</span>
                        )}
                      </span>
                    </span>
                  </div>
                  <p className="text-xs mt-0.5 text-slate-500">
                    {disc === 0
                      ? "Cuadre exacto — sin ajuste de inventario."
                      : disc > 0
                        ? `Sobrante: entra al inventario como ganancia a $referencia${discState === "out" ? " — FUERA de tolerancia" : " (dentro de tolerancia)"}.`
                        : `Faltante: sale del inventario como pérdida a $referencia${discState === "out" ? " — FUERA de tolerancia" : " (dentro de tolerancia)"}.`}
                  </p>
                </div>
                {(disc !== 0 || l.refPrice > 0) && (
                  <div className="w-full sm:w-44">
                    <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                      Precio de referencia {disc !== 0 ? "*" : ""}
                    </Label>
                    <MoneyInput
                      value={l.refPrice}
                      onChange={(v) => updateLine(l._key, { refPrice: v, refTouched: true })}
                      decimals={2}
                      placeholder="0"
                    />
                  </div>
                )}
              </div>

              {problem && <p className="text-xs text-rose-600">{problem}</p>}
            </CardContent>
          </Card>
        );
      })}

      {/* D16: material reportado por proveedores que la bascula no vio */}
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
            La línea nace con pesado 0 — todo lo repartido queda como faltante valorado al precio de referencia.
          </p>
        </CardContent>
      </Card>

      {/* D11: comisión del recolector — UNA por entrada, sobre lo pesado */}
      <Card className="shadow-sm">
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-semibold uppercase tracking-wider text-slate-500 flex items-center gap-2">
            <Truck className="h-4 w-4" />
            Comisión de Recolección
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
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
        </CardContent>
      </Card>

      {/* Resumen por proveedor */}
      {supplierSummary.length > 0 && (
        <Card className="shadow-sm">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-semibold uppercase tracking-wider text-slate-500">
              Compras que van a nacer ({supplierSummary.length})
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
              {supplierSummary.map((s) => (
                <div key={s.tpId} className="rounded-lg border border-slate-200 p-3 space-y-1.5">
                  <div className="flex items-center justify-between gap-2 text-sm">
                    <span className="font-medium truncate">{s.name}</span>
                    {canViewPrices && (
                      <span className="font-semibold tabular-nums">{formatCurrency(s.total)}</span>
                    )}
                  </div>
                  <div className="text-xs text-slate-500 tabular-nums">{s.qtyLabel} repartidos</div>

                  {/* Detalle por material — verificar QUÉ se le compra a cada
                      uno sin volver a leer el reparto arriba */}
                  <ul className="space-y-0.5 border-t border-slate-100 pt-1.5">
                    {s.materials.map((m, i) => (
                      <li
                        key={`${m.code}-${i}`}
                        className="flex items-baseline justify-between gap-2 text-xs"
                      >
                        <span className="truncate text-slate-600">{m.code}</span>
                        <span className="tabular-nums text-slate-500 shrink-0">
                          {formatWeight(m.qty, m.unit)}
                          {canViewPrices && ` × ${formatCurrency(m.price)}`}
                        </span>
                      </li>
                    ))}
                  </ul>

                  <div>
                    <Label className="text-[10px] font-semibold uppercase tracking-wider text-slate-400">
                      N° Factura proveedor
                    </Label>
                    <Input
                      value={invoiceBySupplier[s.tpId] ?? ""}
                      onChange={(e) =>
                        setInvoiceBySupplier((prev) => ({ ...prev, [s.tpId]: e.target.value }))
                      }
                      maxLength={50}
                      className="h-8 text-sm"
                      placeholder="Opcional"
                    />
                  </div>

                  {/* Retenciones OPCIONALES del proveedor (addendum #93) */}
                  <div className="space-y-1.5 pt-1 border-t border-slate-100">
                    <div className="flex items-center justify-between">
                      <Label className="text-[10px] font-semibold uppercase tracking-wider text-slate-400">
                        Retenciones
                      </Label>
                      <button
                        type="button"
                        className="text-xs text-indigo-600 hover:underline"
                        onClick={() =>
                          setRetentionsBySupplier((prev) => ({
                            ...prev,
                            [s.tpId]: [...(prev[s.tpId] ?? []), newRetRow()],
                          }))
                        }
                      >
                        + Retención
                      </button>
                    </div>
                    {(retentionsBySupplier[s.tpId] ?? []).map((r) => (
                      <div key={r._key} className="space-y-1">
                        <div className="flex items-center gap-1.5">
                          <Select
                            value={r.config_id || undefined}
                            onValueChange={(v) =>
                              updateRet(s.tpId, r._key, { config_id: v, touched: false })
                            }
                          >
                            <SelectTrigger
                              className={cn("h-8 text-xs flex-1", !r.config_id && "border-red-300")}
                            >
                              <SelectValue placeholder="Tarifa..." />
                            </SelectTrigger>
                            <SelectContent>
                              {retentionConfigs.map((cfg) => (
                                <SelectItem key={cfg.config_id} value={cfg.config_id as string}>
                                  {retentionRowLabel(cfg)} ({cfg.rate_pct}%)
                                </SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                          <button
                            type="button"
                            onClick={() => removeRet(s.tpId, r._key)}
                            className="text-slate-400 hover:text-red-500"
                            title="Quitar retención"
                          >
                            <Trash2 className="h-3.5 w-3.5" />
                          </button>
                        </div>
                        <MoneyInput
                          value={effRetAmount(r, s.total)}
                          onChange={(v) => updateRet(s.tpId, r._key, { amount: v, touched: true })}
                          decimals={2}
                          placeholder="0"
                          // Con subtotal $0 el monto SIEMPRE sale 0: marcar el
                          // input en rojo culpa al campo de algo que no es suyo
                          className={cn(
                            "h-8 text-sm",
                            s.total > 0 && effRetAmount(r, s.total) <= 0 && "border-red-300"
                          )}
                        />
                        {r.config_id && r.touched &&
                          effRetAmount(r, s.total) !== suggestedRet(r.config_id, s.total) && (
                          <button
                            type="button"
                            className="text-[11px] text-indigo-600 hover:underline"
                            onClick={() => updateRet(s.tpId, r._key, { touched: false, amount: 0 })}
                          >
                            Sugerido: {formatCurrency(suggestedRet(r.config_id, s.total))} (
                            {configById.get(r.config_id)?.rate_pct}%)
                          </button>
                        )}
                      </div>
                    ))}
                    {supplierRetTotal(s.tpId, s.total) > 0 && canViewPrices && (
                      <p className="text-xs text-slate-500">
                        Neto al proveedor:{" "}
                        <span className="font-semibold text-slate-700">
                          {formatCurrency(s.total - supplierRetTotal(s.tpId, s.total))}
                        </span>
                      </p>
                    )}
                  </div>

                  {/* Pago de contado OPCIONAL por proveedor (#20 via canal
                      unico). Sin marcar = se le queda debiendo, el camino normal */}
                  <div className="space-y-1.5 pt-1 border-t border-slate-100">
                    <label className="flex items-center gap-2 text-xs text-slate-600 cursor-pointer">
                      <Checkbox
                        checked={paymentBySupplier[s.tpId] !== undefined}
                        onCheckedChange={(v) =>
                          setPaymentBySupplier((prev) => {
                            const next = { ...prev };
                            if (v === true) next[s.tpId] = accounts[0]?.id ?? "";
                            else delete next[s.tpId];
                            return next;
                          })
                        }
                      />
                      Pagar de contado
                    </label>
                    {paymentBySupplier[s.tpId] !== undefined && (
                      <>
                        <Select
                          value={paymentBySupplier[s.tpId] || undefined}
                          onValueChange={(v) =>
                            setPaymentBySupplier((prev) => ({ ...prev, [s.tpId]: v }))
                          }
                        >
                          <SelectTrigger
                            className={cn(
                              "h-8 text-xs",
                              !paymentBySupplier[s.tpId] && "border-red-300",
                            )}
                          >
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
                        {canViewPrices && (
                          <p className="text-[11px] text-slate-500">
                            Sale de la cuenta:{" "}
                            <span className="font-semibold text-slate-700">
                              {formatCurrency(s.total - supplierRetTotal(s.tpId, s.total))}
                            </span>{" "}
                            (el neto)
                          </p>
                        )}
                      </>
                    )}
                  </div>
                </div>
              ))}
            </div>
            {retentionProblems.length > 0 && (
              <div className="mt-3 rounded-md bg-red-50 border border-red-100 px-3 py-2 text-xs text-red-600 space-y-0.5">
                {retentionProblems.map((p) => (
                  <p key={p}>{p}</p>
                ))}
              </div>
            )}
            {totalRetAll > 0 && (
              <p className="mt-3 text-xs text-slate-500">
                Cada retención acredita al proveedor por el <strong>neto</strong> y deja la
                deuda en su entidad [Retenciones] para el pago mensual de impuestos. Las
                tarifas se administran en Tesorería → Retenciones.
              </p>
            )}
          </CardContent>
        </Card>
      )}

      {/* Submit */}
      <div className="sticky bottom-0 bg-white/95 backdrop-blur-sm border-t border-slate-100 py-4 -mx-3 px-3 md:-mx-6 md:px-6 mt-6 pb-[max(1rem,env(safe-area-inset-bottom))]">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
          <div className="text-sm text-slate-500">
            {supplierSummary.length > 0 && (
              <>
                {supplierSummary.length} compra{supplierSummary.length === 1 ? "" : "s"}
                {canViewPrices &&
                  ` · ${formatCurrency(supplierSummary.reduce((acc, s) => acc + s.total, 0))}`}
                {totalRetAll > 0 && canViewPrices &&
                  ` · retenciones ${formatCurrency(totalRetAll)}`}
                {collectorEnabled && effCollectorAmount > 0 &&
                  canViewPrices && ` · comisión ${formatCurrency(effCollectorAmount)}`}
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
