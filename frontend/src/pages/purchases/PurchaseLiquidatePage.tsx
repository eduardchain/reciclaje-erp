import { useState, useEffect, useMemo } from "react";
import { useParams, useNavigate, useSearchParams } from "react-router-dom";
import { ArrowLeft, CheckCircle, Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import { PageHeader } from "@/components/shared/PageHeader";
import { PriceSuggestion } from "@/components/shared/PriceSuggestion";
import { EntitySelect } from "@/components/shared/EntitySelect";
import { FormLineGrid, lineLabelClass } from "@/components/shared/FormLineGrid";
import { cn } from "@/utils";
import { usePurchase, useLiquidatePurchase } from "@/hooks/usePurchases";
import { usePriceSuggestions } from "@/hooks/usePriceSuggestions";
import { usePayableProviders, useMoneyAccounts, useRetentionRows, useCreateRetentionConfig } from "@/hooks/useMasterData";
import { useCurrentTariffs } from "@/hooks/useSacConfig";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { useOrgSettings } from "@/hooks/useOrgSettings";
import { MoneyInput } from "@/components/shared/MoneyInput";
import { formatCurrency, formatDate, formatWeight } from "@/utils/formatters";
import { RETENTION_TYPE_LABELS, type PurchaseCommissionCreate } from "@/types/purchase";
import type { RetentionConfigType } from "@/types/third-party";
import { retentionRowLabel } from "@/pages/treasury/RetentionsPage";

interface LiquidationLine {
  line_id: string;
  material_id: string;
  material_name: string;
  material_code: string;
  material_unit: string;
  warehouse_name: string | null;
  quantity: number;
  unit_price: number;
}

interface CommissionFormData extends PurchaseCommissionCreate {
  _key: number;
}

let commKeyCounter = 0;

function createEmptyCommission(): CommissionFormData {
  return { _key: ++commKeyCounter, third_party_id: "", concept: "", commission_type: "percentage", commission_value: 0, charge_type: "commission" };
}

// SAC — retenciones por catálogo (v2 CC-006, solo con flag kg_ledger_enabled):
// la fila referencia una config (tipo+municipio+concepto+%); el monto se
// pre-calcula con el % y solo se guarda aparte si el usuario lo editó (touched).
interface RetentionFormData {
  _key: number;
  config_id: string;
  amount: number; // vigente solo cuando touched
  touched: boolean;
}

let retKeyCounter = 0;

function createEmptyRetention(): RetentionFormData {
  return { _key: ++retKeyCounter, config_id: "", amount: 0, touched: false };
}

export default function PurchaseLiquidatePage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  // Ciclo C (W-C1): si se llega desde una Entrada, volver alla al terminar.
  // Sin el param (las 3 orgs prod y el flujo Compras) el destino es EXACTO al
  // de siempre: el detalle de la compra. Solo rutas internas (anti open-redirect).
  const [searchParams] = useSearchParams();
  const rawReturnTo = searchParams.get("returnTo");
  const returnTo = rawReturnTo && rawReturnTo.startsWith("/") ? rawReturnTo : null;
  const exitTo = returnTo ?? `/purchases/${id}`;
  const { data: purchase, isLoading } = usePurchase(id!);
  const { getSuggestedPrice } = usePriceSuggestions();
  const liquidate = useLiquidatePurchase();
  const { data: payableData } = usePayableProviders();
  const payableProviders = payableData?.items ?? [];

  const { getSetting } = useOrgSettings();
  // Gating D9: sin flag no se muestra la sección y el payload no lleva retentions
  const retentionsEnabled = getSetting("kg_ledger_enabled") === true;

  // Catálogo de retenciones (v2 CC-006; F2: enabled=flag → cero requests para
  // orgs sin SAC). El selector cerrado + precálculo matan typo y digitación.
  const { data: retentionRows } = useRetentionRows(retentionsEnabled);
  // Ciclo D: tarifa vigente comision_green_loop para pre-sugerir (F2: gated)
  const { data: tariffsData } = useCurrentTariffs(retentionsEnabled);
  const retentionConfigs = useMemo(
    () => (retentionRows ?? []).filter((r) => r.config_id && r.is_active),
    [retentionRows],
  );
  const configById = useMemo(
    () => new Map(retentionConfigs.map((r) => [r.config_id as string, r])),
    [retentionConfigs],
  );
  const createRetentionConfig = useCreateRetentionConfig();
  const [addRetForKey, setAddRetForKey] = useState<number | null>(null);
  const [newRetType, setNewRetType] = useState<RetentionConfigType>("retefuente");
  const [newMunicipality, setNewMunicipality] = useState("");
  const [newConcept, setNewConcept] = useState("");
  const [newRate, setNewRate] = useState("");
  const newRateNum = parseFloat(newRate);
  const addRetValid =
    !Number.isNaN(newRateNum) && newRateNum > 0 && newRateNum <= 100 &&
    (newRetType !== "ica" || !!newMunicipality.trim());
  const handleAddRetention = () => {
    createRetentionConfig.mutate(
      {
        retention_type: newRetType,
        ...(newRetType === "ica" ? { municipality: newMunicipality.trim() } : {}),
        ...(newConcept.trim() ? { concept: newConcept.trim() } : {}),
        rate_pct: newRateNum,
      },
      {
        onSuccess: (created) => {
          if (addRetForKey !== null && created.config_id) {
            selectRetentionConfig(addRetForKey, created.config_id);
          }
          setAddRetForKey(null);
        },
      },
    );
  };

  const [lines, setLines] = useState<LiquidationLine[]>([]);
  const [commissions, setCommissions] = useState<CommissionFormData[]>([]);
  const [retentions, setRetentions] = useState<RetentionFormData[]>([]);
  // Ciclo D: comision de recoleccion — GASTO causado, no prorratea al costo (#30)
  const [collectorRow, setCollectorRow] = useState(false);
  const [collectorTpId, setCollectorTpId] = useState("");
  const [collectorAmount, setCollectorAmount] = useState(0);
  const [collectorTouched, setCollectorTouched] = useState(false);
  const [collectorDismissed, setCollectorDismissed] = useState(false);
  const [immediatePayment, setImmediatePayment] = useState(false);
  const [paymentAccountId, setPaymentAccountId] = useState("");
  const [liquidationDate, setLiquidationDate] = useState("");
  const { data: accountsData } = useMoneyAccounts();
  const accounts = accountsData?.items ?? (Array.isArray(accountsData) ? accountsData : []);
  const _todayNow = new Date();
  const todayStr = `${_todayNow.getFullYear()}-${String(_todayNow.getMonth() + 1).padStart(2, "0")}-${String(_todayNow.getDate()).padStart(2, "0")}`;
  const docDateStr = purchase ? (() => { const d = new Date(purchase.date); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`; })() : "";

  // Fecha de liquidacion SIN default: el liquidador debe elegirla conscientemente
  // (evita back-dating silencioso a la fecha del documento). Ver retro-fechado.

  // Inicializar lineas y comisiones desde la compra cargada
  useEffect(() => {
    if (purchase && lines.length === 0) {
      setLines(
        purchase.lines.map((line) => {
          // Si el precio es 0, intentar pre-llenar desde lista de precios
          let price = line.unit_price;
          if (price === 0) {
            const suggested = getSuggestedPrice(line.material_id, "purchase");
            if (suggested) price = suggested;
          }
          return {
            line_id: line.id,
            material_id: line.material_id,
            material_name: line.material_name,
            material_code: line.material_code,
            material_unit: line.material_unit,
            warehouse_name: line.warehouse_name,
            quantity: line.quantity,
            unit_price: price,
          };
        }),
      );
      if (purchase.commissions?.length > 0) {
        setCommissions(
          purchase.commissions.map((c) => ({
            _key: ++commKeyCounter,
            third_party_id: c.third_party_id,
            concept: c.concept,
            commission_type: c.commission_type,
            commission_value: c.commission_value,
            charge_type: c.charge_type,
          }))
        );
      }
    }
  }, [purchase, getSuggestedPrice, lines.length]);

  // Ciclo D: pre-carga del recolector de la entrada — efecto propio que
  // reacciona cuando collector_id LLEGA (robusto ante cache con shape viejo);
  // "Quitar" marca dismissed para que el refetch no re-abra la fila
  useEffect(() => {
    if (purchase?.collector_id && !collectorRow && !collectorDismissed && !collectorTpId) {
      setCollectorRow(true);
      setCollectorTpId(purchase.collector_id);
    }
  }, [purchase?.collector_id, collectorRow, collectorDismissed, collectorTpId]);

  // Redirigir si la compra no es liquidable (honra returnTo — W-C1)
  useEffect(() => {
    if (purchase && (purchase.status !== "registered" || purchase.double_entry_id)) {
      navigate(exitTo, { replace: true });
    }
  }, [purchase, id, navigate, exitTo]);

  const updatePrice = (lineId: string, price: number) => {
    setLines((prev) =>
      prev.map((l) => (l.line_id === lineId ? { ...l, unit_price: price } : l)),
    );
  };

  const updateCommission = (key: number, field: keyof PurchaseCommissionCreate, value: string | number) => {
    setCommissions((prev) => prev.map((c) => (c._key === key ? { ...c, [field]: value } : c)));
  };

  const selectRetentionConfig = (key: number, configId: string) => {
    // Elegir config resetea el monto al precálculo (touched=false)
    setRetentions((prev) =>
      prev.map((r) => (r._key === key ? { ...r, config_id: configId, touched: false, amount: 0 } : r)),
    );
  };

  const setRetentionAmount = (key: number, value: number) => {
    setRetentions((prev) =>
      prev.map((r) => (r._key === key ? { ...r, amount: value, touched: true } : r)),
    );
  };

  const total = lines.reduce((sum, l) => sum + l.quantity * l.unit_price, 0);
  const totalQuantity = lines.reduce((sum, l) => sum + (l.quantity || 0), 0);
  const totalComm = useMemo(() => commissions.reduce((sum, c) => {
    return sum + (c.commission_type === "percentage" ? (total * c.commission_value) / 100 : c.commission_type === "per_kg" ? totalQuantity * c.commission_value : c.commission_value);
  }, 0), [commissions, total, totalQuantity]);
  const linesCostData = useMemo(() => {
    if (totalComm === 0 || total === 0) return null;
    return lines.map(line => {
      const lineValue = line.quantity * line.unit_price;
      const weight = lineValue / total;
      const lineCommission = totalComm * weight;
      const unitCost = line.quantity > 0
        ? (lineValue + lineCommission) / line.quantity
        : line.unit_price;
      return { materialId: line.material_id, unitCost };
    });
  }, [lines, commissions, total, totalComm]);
  const allPricesValid = lines.every((l) => l.unit_price > 0);
  const selectedAccount = accounts.find((a) => a.id === paymentAccountId);
  // D9: el proveedor queda acreditado (y el pago inmediato paga) por el NETO
  // Precálculo: % de la config sobre el subtotal; editable (touched conserva
  // el valor del usuario). El sugerido sigue vivo si cambian los precios.
  const suggestedRetention = (configId: string) => {
    const cfg = configById.get(configId);
    if (!cfg || cfg.rate_pct == null) return 0;
    return Math.round(total * cfg.rate_pct) / 100; // = total × pct/100 a 2 decimales
  };
  const effRetentionAmount = (r: RetentionFormData) =>
    r.touched ? r.amount : suggestedRetention(r.config_id);
  const totalRet = retentions.reduce((sum, r) => sum + effRetentionAmount(r), 0);
  const netTotal = total - totalRet;
  const retentionsValid =
    retentions.every((r) => !!r.config_id && effRetentionAmount(r) > 0) &&
    (totalRet === 0 || totalRet < total);
  // Ciclo D: sugerido = tarifa vigente comision_green_loop x kg de la compra
  // (cantidad ORIGINAL, asimetria #70). El monto editado es la verdad (F1 #79).
  const greenLoopTariff = (tariffsData?.items ?? []).find(
    (t) => t.tariff_code === "comision_green_loop",
  );
  const suggestedCollector = greenLoopTariff
    ? Math.round(totalQuantity * Number(greenLoopTariff.unit_price_cop) * 100) / 100
    : 0;
  const effCollectorAmount = collectorTouched ? collectorAmount : suggestedCollector;
  const collectorValid = !collectorRow || (!!collectorTpId && effCollectorAmount > 0);
  const canSubmit = allPricesValid && lines.length > 0
    && (!immediatePayment || (paymentAccountId && (!selectedAccount || selectedAccount.current_balance >= netTotal)))
    && commissions.every((c) => c.third_party_id && c.concept && c.commission_value > 0)
    && retentionsValid
    && collectorValid
    && !!liquidationDate;

  const handleSubmit = () => {
    if (!canSubmit || !id) return;
    liquidate.mutate(
      {
        id,
        data: {
          lines: lines.map((l) => ({
            line_id: l.line_id,
            unit_price: l.unit_price,
          })),
          commissions: commissions
            .filter((c) => c.third_party_id && c.commission_value > 0)
            .map(({ _key, ...rest }) => rest),
          // D9: AUSENTE (no []) sin filas — payload byte-idéntico para orgs sin flag
          ...(retentionsEnabled && retentions.length > 0
            ? {
                retentions: retentions.map((r) => {
                  const cfg = configById.get(r.config_id)!;
                  return {
                    retention_type: cfg.retention_type,
                    ...(cfg.retention_type === "ica" && cfg.municipality
                      ? { municipality: cfg.municipality }
                      : {}),
                    amount: effRetentionAmount(r),
                    // Auditoría del precálculo ofrecido (F1: backend ya los persiste)
                    ...(cfg.rate_pct != null ? { rate: cfg.rate_pct, base: total } : {}),
                  };
                }),
              }
            : {}),
          // Ciclo D: AUSENTE sin fila — mismo data-gate D9 (orgs sin flag
          // jamas lo envian: la seccion no se renderiza)
          ...(retentionsEnabled && collectorRow && collectorTpId && effCollectorAmount > 0
            ? {
                collector_commission: {
                  third_party_id: collectorTpId,
                  amount: effCollectorAmount,
                },
              }
            : {}),
          ...(immediatePayment && paymentAccountId
            ? { immediate_payment: true, payment_account_id: paymentAccountId }
            : {}),
          ...(liquidationDate ? { liquidation_date: liquidationDate } : {}),
        },
      },
      {
        onSuccess: () => {
          navigate(exitTo);
        },
      },
    );
  };

  if (isLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  if (!purchase) {
    return <div className="text-center py-12 text-slate-500">Compra no encontrada</div>;
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title={`Liquidar Compra #${purchase.purchase_number}`}
        description={`Proveedor: ${purchase.supplier_name} | Fecha: ${formatDate(purchase.date)}`}
      >
        <Button variant="outline" onClick={() => navigate(exitTo)}>
          <ArrowLeft className="h-4 w-4 mr-2" />
          Volver
        </Button>
      </PageHeader>

      {/* Info resumida */}
      <Card className="shadow-sm border-t-[3px] border-t-amber-400">
        <CardContent className="pt-6">
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4 text-sm">
            <div>
              <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">Proveedor</span>
              <p className="font-medium">{purchase.supplier_name}</p>
            </div>
            <div>
              <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">Fecha</span>
              <p>{formatDate(purchase.date)}</p>
            </div>
            {purchase.vehicle_plate && (
              <div>
                <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">Placa</span>
                <p>{purchase.vehicle_plate}</p>
              </div>
            )}
            {purchase.invoice_number && (
              <div>
                <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">Factura</span>
                <p>{purchase.invoice_number}</p>
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Lineas con precios editables */}
      <Card className="shadow-sm">
        <CardHeader>
          <CardTitle className="text-sm font-semibold uppercase tracking-wider text-slate-500">
            Confirmar Precios
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-0">
          {lines.map((line, idx) => (
            <FormLineGrid
              key={line.line_id}
              isFirst={idx === 0}
              isLast={idx === lines.length - 1}
            >
              <div className="md:col-span-3">
                <Label className={cn("text-xs font-semibold uppercase tracking-wider text-slate-500", lineLabelClass(idx))}>Material</Label>
                <p className="md:h-10 flex items-center text-sm">
                  <span className="font-medium">{line.material_name}</span>
                  <span className="text-slate-400 ml-2 text-xs">{line.material_code}</span>
                </p>
              </div>
              <div className="md:col-span-2 flex md:block items-center justify-between">
                <Label className={cn("text-xs font-semibold uppercase tracking-wider text-slate-500", lineLabelClass(idx))}>Bodega</Label>
                <p className="md:h-10 flex items-center text-sm text-slate-600">
                  {line.warehouse_name ?? "-"}
                </p>
              </div>
              <div className="md:col-span-2 flex md:block items-center justify-between">
                <Label className={cn("text-xs font-semibold uppercase tracking-wider text-slate-500", lineLabelClass(idx))}>Cantidad{line.material_unit ? ` (${line.material_unit})` : ""}</Label>
                <p className="md:h-10 flex items-center text-sm tabular-nums">
                  {formatWeight(line.quantity, line.material_unit || "kg")}
                </p>
              </div>
              <div className={cn("relative", linesCostData ? "md:col-span-2" : "md:col-span-3")}>
                <Label className={cn("text-xs font-semibold uppercase tracking-wider text-slate-500", lineLabelClass(idx))}>Precio Unit. *</Label>
                <MoneyInput
                  value={line.unit_price}
                  onChange={(v) => updatePrice(line.line_id, v)}
                  decimals={2}
                  placeholder="0"
                  className={line.unit_price <= 0 ? "border-red-300" : ""}
                />
                <div className="absolute left-0 w-max" style={{ top: "100%" }}>
                  <PriceSuggestion
                    suggestedPrice={getSuggestedPrice(line.material_id, "purchase")}
                    onApply={(p) => updatePrice(line.line_id, p)}
                  />
                  {line.unit_price <= 0 && (
                    <p className="text-xs text-red-500 mt-0.5">El precio debe ser mayor a 0</p>
                  )}
                </div>
              </div>
              {linesCostData && (
              <div className="md:col-span-1 md:text-right flex md:block items-center justify-between">
                <Label className={cn("text-xs font-semibold uppercase tracking-wider text-slate-500", lineLabelClass(idx))}>Costo Unit*</Label>
                <p className="md:h-10 flex items-center md:justify-end text-sm font-medium tabular-nums text-emerald-600">
                  {formatCurrency(linesCostData.find(c => c.materialId === line.material_id)?.unitCost ?? line.unit_price)}
                </p>
              </div>
              )}
              <div className="md:col-span-2 md:text-right flex md:block items-center justify-between">
                <Label className={cn("text-xs font-semibold uppercase tracking-wider text-slate-500", lineLabelClass(idx))}>Total</Label>
                <p className="md:h-10 flex items-center md:justify-end text-sm font-medium tabular-nums">
                  {formatCurrency(line.quantity * line.unit_price)}
                </p>
              </div>
            </FormLineGrid>
          ))}

          {linesCostData && (
            <p className="text-xs text-slate-500 mt-2">* Costo incluye comision prorrateada</p>
          )}
          <div className="bg-slate-50 rounded-lg p-3 mt-2">
            <div className="flex justify-end">
              <span className="text-lg font-bold">Total: {formatCurrency(total)}</span>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Comisiones */}
      <Card className="shadow-sm">
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle className="text-sm font-semibold uppercase tracking-wider text-slate-500">Comisiones y Cargos (Opcional)</CardTitle>
          <Button variant="outline" size="sm" onClick={() => setCommissions((p) => [...p, createEmptyCommission()])}>
            <Plus className="h-4 w-4 mr-1" />Agregar Cargo
          </Button>
        </CardHeader>
        {commissions.length > 0 && (
          <CardContent className="space-y-0">
            {commissions.map((comm, idx) => (
              <FormLineGrid
                key={comm._key}
                isFirst={idx === 0}
                isLast={idx === commissions.length - 1}
                onDelete={() => setCommissions((p) => p.filter((c) => c._key !== comm._key))}
              >
                <div className="md:col-span-3">
                  <Label className={cn("text-xs font-semibold uppercase tracking-wider text-slate-500", lineLabelClass(idx))}>Receptor *</Label>
                  <EntitySelect value={comm.third_party_id} onChange={(v) => updateCommission(comm._key, "third_party_id", v)} options={payableProviders.map((tp) => ({ id: tp.id, label: tp.name }))} placeholder="Receptor..." />
                </div>
                <div className="md:col-span-2">
                  <Label className={cn("text-xs font-semibold uppercase tracking-wider text-slate-500", lineLabelClass(idx))}>Cargo</Label>
                  <Select value={comm.charge_type ?? "commission"} onValueChange={(v) => updateCommission(comm._key, "charge_type", v)}>
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="commission">Comisión</SelectItem>
                      <SelectItem value="freight">Flete</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="md:col-span-2">
                  <Label className={cn("text-xs font-semibold uppercase tracking-wider text-slate-500", lineLabelClass(idx))}>Concepto *</Label>
                  <Input value={comm.concept} onChange={(e) => updateCommission(comm._key, "concept", e.target.value)} placeholder="Concepto..." />
                </div>
                <div className="md:col-span-2">
                  <Label className={cn("text-xs font-semibold uppercase tracking-wider text-slate-500", lineLabelClass(idx))}>Cálculo</Label>
                  <Select value={comm.commission_type} onValueChange={(v) => updateCommission(comm._key, "commission_type", v)}>
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="percentage">Porcentaje</SelectItem>
                      <SelectItem value="fixed">Fijo</SelectItem>
                      <SelectItem value="per_kg">Por Kilo</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="md:col-span-2">
                  <Label className={cn("text-xs font-semibold uppercase tracking-wider text-slate-500", lineLabelClass(idx))}>Valor *</Label>
                  <Input type="number" min={0} step="0.01" value={comm.commission_value || ""} onChange={(e) => updateCommission(comm._key, "commission_value", parseFloat(e.target.value) || 0)} placeholder={comm.commission_type === "percentage" ? "%" : comm.commission_type === "per_kg" ? "$/kg" : "$"} />
                </div>
                <div className="md:col-span-1 md:text-right flex md:block items-center justify-between">
                  <Label className={cn("text-xs font-semibold uppercase tracking-wider text-slate-500", lineLabelClass(idx))}>Monto</Label>
                  <p className="md:h-10 flex items-center md:justify-end text-sm font-medium tabular-nums">
                    {comm.commission_type === "percentage"
                      ? formatCurrency((total * comm.commission_value) / 100)
                      : comm.commission_type === "per_kg"
                      ? formatCurrency(totalQuantity * comm.commission_value)
                      : formatCurrency(comm.commission_value)}
                  </p>
                </div>
              </FormLineGrid>
            ))}
          </CardContent>
        )}
      </Card>

      {/* Comision de recoleccion (SAC Ciclo D — gasto, no prorratea al costo) */}
      {retentionsEnabled && (
        <Card className="shadow-sm">
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle className="text-sm font-semibold uppercase tracking-wider text-slate-500">
              Comisión de Recolección {collectorRow ? "" : "(Opcional)"}
            </CardTitle>
            {collectorRow ? (
              <Button
                variant="ghost"
                size="sm"
                className="text-red-500 hover:text-red-600"
                onClick={() => {
                  setCollectorRow(false);
                  setCollectorTpId("");
                  setCollectorAmount(0);
                  setCollectorTouched(false);
                  setCollectorDismissed(true);
                }}
              >
                Quitar
              </Button>
            ) : (
              <Button variant="outline" size="sm" onClick={() => setCollectorRow(true)}>
                <Plus className="h-4 w-4 mr-1" />Agregar
              </Button>
            )}
          </CardHeader>
          {collectorRow && (
            <CardContent className="space-y-3">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Recolector *</Label>
                  <EntitySelect
                    value={collectorTpId}
                    onChange={setCollectorTpId}
                    options={payableProviders.map((tp) => ({ id: tp.id, label: tp.name }))}
                    placeholder="Seleccionar recolector..."
                  />
                  {purchase.collector_name && collectorTpId === purchase.collector_id && (
                    <p className="text-[11px] text-slate-400 mt-0.5">Capturado en la entrada</p>
                  )}
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
                    className={effCollectorAmount <= 0 ? "border-red-300" : ""}
                  />
                  {greenLoopTariff && collectorTouched && effCollectorAmount !== suggestedCollector ? (
                    <button
                      type="button"
                      className="text-[11px] text-indigo-600 hover:underline mt-0.5"
                      onClick={() => {
                        setCollectorTouched(false);
                        setCollectorAmount(0);
                      }}
                    >
                      Sugerido: {formatCurrency(suggestedCollector)} — restaurar
                    </button>
                  ) : greenLoopTariff ? (
                    <p className="text-[11px] text-slate-400 mt-0.5">
                      Tarifa vigente: {formatCurrency(Number(greenLoopTariff.unit_price_cop))}/kg × {totalQuantity.toLocaleString()} kg
                    </p>
                  ) : (
                    <p className="text-[11px] text-amber-600 mt-0.5">
                      Sin tarifa comisión Green Loop vigente — ingrese el monto manualmente
                    </p>
                  )}
                </div>
              </div>
              <div className="rounded-md bg-indigo-50 border border-indigo-100 px-3 py-2 text-xs text-indigo-900">
                Se causa como <strong>gasto</strong> (categoría "Comisiones de recolección") al liquidar —
                no suma al costo del material ni al total a pagar al proveedor. El pago al recolector
                se hace después desde Tesorería.
              </div>
            </CardContent>
          )}
        </Card>
      )}

      {/* Retenciones (SAC D9 — solo con flag) */}
      {retentionsEnabled && (
        <Card className="shadow-sm">
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle className="text-sm font-semibold uppercase tracking-wider text-slate-500">Retenciones (Opcional)</CardTitle>
            <Button variant="outline" size="sm" onClick={() => setRetentions((p) => [...p, createEmptyRetention()])}>
              <Plus className="h-4 w-4 mr-1" />Agregar Retención
            </Button>
          </CardHeader>
          {retentions.length > 0 && (
            <CardContent className="space-y-0">
              {retentions.map((ret, idx) => (
                <FormLineGrid
                  key={ret._key}
                  isFirst={idx === 0}
                  isLast={idx === retentions.length - 1}
                  onDelete={() => setRetentions((p) => p.filter((r) => r._key !== ret._key))}
                >
                  <div className="md:col-span-6">
                    <Label className={cn("text-xs font-semibold uppercase tracking-wider text-slate-500", lineLabelClass(idx))}>Retención *</Label>
                    <Select
                      value={ret.config_id || undefined}
                      onValueChange={(v) => {
                        if (v === "__add__") {
                          setNewRetType("retefuente");
                          setNewMunicipality("");
                          setNewConcept("");
                          setNewRate("");
                          setAddRetForKey(ret._key);
                        } else {
                          selectRetentionConfig(ret._key, v);
                        }
                      }}
                    >
                      <SelectTrigger className={!ret.config_id ? "border-red-300" : ""}>
                        <SelectValue placeholder="Seleccionar retención..." />
                      </SelectTrigger>
                      <SelectContent>
                        {retentionConfigs.map((cfg) => (
                          <SelectItem key={cfg.config_id} value={cfg.config_id as string}>
                            {retentionRowLabel(cfg)} ({cfg.rate_pct}%)
                          </SelectItem>
                        ))}
                        <SelectItem value="__add__" className="text-indigo-600 font-medium">
                          + Agregar retención…
                        </SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="md:col-span-4">
                    <Label className={cn("text-xs font-semibold uppercase tracking-wider text-slate-500", lineLabelClass(idx))}>Monto *</Label>
                    <MoneyInput
                      value={effRetentionAmount(ret)}
                      onChange={(v) => setRetentionAmount(ret._key, v)}
                      decimals={2}
                      placeholder="0"
                      className={effRetentionAmount(ret) <= 0 ? "border-red-300" : ""}
                    />
                    {ret.config_id && ret.touched && effRetentionAmount(ret) !== suggestedRetention(ret.config_id) && (
                      <button
                        type="button"
                        className="text-xs text-indigo-600 hover:underline mt-0.5"
                        onClick={() => selectRetentionConfig(ret._key, ret.config_id)}
                      >
                        Sugerido: {formatCurrency(suggestedRetention(ret.config_id))} ({configById.get(ret.config_id)?.rate_pct}%)
                      </button>
                    )}
                    {ret.config_id && !ret.touched && (
                      <p className="text-xs text-slate-400 mt-0.5">
                        {configById.get(ret.config_id)?.rate_pct}% de {formatCurrency(total)} — editable
                      </p>
                    )}
                  </div>
                </FormLineGrid>
              ))}
              <div className="bg-slate-50 rounded-lg p-3 mt-2 text-xs text-slate-500 space-y-1">
                <p>El proveedor queda acreditado por el <strong>neto</strong> (total − retenciones); cada retención crea deuda con su entidad [Retenciones] para el pago mensual de impuestos.</p>
                {totalRet > 0 && totalRet >= total && (
                  <p className="text-red-500 font-medium">La suma de retenciones ({formatCurrency(totalRet)}) debe ser menor al total ({formatCurrency(total)}).</p>
                )}
              </div>
            </CardContent>
          )}
        </Card>
      )}

      {/* Resumen Financiero */}
      <Card className="shadow-sm bg-slate-50/50">
        <CardHeader>
          <CardTitle className="text-sm font-semibold uppercase tracking-wider text-slate-500">Resumen Financiero</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="max-w-sm ml-auto space-y-2">
            <div className="flex justify-between text-sm">
              <span className="text-slate-600">Subtotal Materiales</span>
              <span className="font-medium tabular-nums">{formatCurrency(total)}</span>
            </div>
            {totalComm > 0 && (
            <>
            <div className="flex justify-between text-sm">
              <span className="text-slate-600">(+) Comisiones</span>
              <span className="font-medium tabular-nums text-amber-600">{formatCurrency(totalComm)}</span>
            </div>
            <div className="border-t border-slate-200 pt-2" />
            </>
            )}
            <div className="flex justify-between text-sm">
              <span className="text-slate-600 font-semibold">Costo Total Inventario</span>
              <span className="font-bold tabular-nums text-base">{formatCurrency(total + totalComm)}</span>
            </div>
            {totalRet > 0 && (
            <>
            <div className="border-t border-slate-200 pt-2" />
            <div className="flex justify-between text-sm">
              <span className="text-slate-600">(−) Retenciones</span>
              <span className="font-medium tabular-nums text-rose-600">−{formatCurrency(totalRet)}</span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-slate-600 font-semibold">Neto al Proveedor</span>
              <span className="font-bold tabular-nums">{formatCurrency(netTotal)}</span>
            </div>
            </>
            )}
            {(totalComm > 0 || totalRet > 0) && (
            <>
            <div className="border-t border-dashed border-slate-200 pt-2" />
            <div className="flex justify-between text-xs text-slate-500">
              <span>CxP Proveedor</span>
              <span className="tabular-nums">{formatCurrency(netTotal)}</span>
            </div>
            {totalComm > 0 && (
            <div className="flex justify-between text-xs text-slate-500">
              <span>CxP Comisionistas</span>
              <span className="tabular-nums">{formatCurrency(totalComm)}</span>
            </div>
            )}
            {totalRet > 0 && (
            <div className="flex justify-between text-xs text-slate-500">
              <span>CxP Entidades de Retención</span>
              <span className="tabular-nums">{formatCurrency(totalRet)}</span>
            </div>
            )}
            </>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Pago inmediato */}
      <Card className="shadow-sm">
        <CardContent className="pt-6 space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center gap-3 sm:gap-4">
            <div className="flex-1">
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Fecha de Liquidación <span className="text-red-500">*</span></Label>
              <p className={`text-xs mt-0.5 ${liquidationDate ? "text-slate-500" : "text-red-600"}`}>
                {liquidationDate ? "Fecha en que la operación tiene efecto financiero." : "Obligatorio: elige conscientemente la fecha en que se liquida."}
              </p>
            </div>
            <Input
              type="date"
              value={liquidationDate}
              min={docDateStr}
              max={todayStr}
              onChange={(e) => setLiquidationDate(e.target.value)}
              className={`w-full sm:w-40 h-9 sm:h-8 text-xs ${liquidationDate ? "" : "border-red-300 focus-visible:ring-red-400"}`}
            />
          </div>
          <div className="border-t border-slate-100" />
          <div className="flex items-center justify-between gap-3">
            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Registrar pago inmediato</Label>
              <p className="text-xs text-slate-500 mt-1">
                Crea el pago al proveedor automaticamente al liquidar.
                {totalRet > 0 && <> Se paga el <strong>neto</strong>: {formatCurrency(netTotal)}.</>}
              </p>
            </div>
            <Switch checked={immediatePayment} onCheckedChange={setImmediatePayment} />
          </div>
          {immediatePayment && (
            <div className="space-y-2">
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Cuenta de Pago *</Label>
              <EntitySelect
                value={paymentAccountId}
                onChange={setPaymentAccountId}
                options={accounts.map((a) => ({ id: a.id, label: `${a.name} (${formatCurrency(a.current_balance)})` }))}
                placeholder="Seleccionar cuenta..."
              />
              {selectedAccount && selectedAccount.current_balance < netTotal && (
                <p className="text-xs text-red-500">Fondos insuficientes. Disponible: {formatCurrency(selectedAccount.current_balance)}, Requerido: {formatCurrency(netTotal)}</p>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Acciones */}
      <div className="sticky bottom-0 bg-white/95 backdrop-blur-sm border-t border-slate-100 py-4 -mx-3 px-3 md:-mx-6 md:px-6 mt-6 pb-[max(1rem,env(safe-area-inset-bottom))]">
        <div className="flex flex-col sm:flex-row sm:justify-end gap-2">
          <Button variant="outline" onClick={() => navigate(exitTo)} className="w-full sm:w-auto">
            Cancelar
          </Button>
          <Button
            onClick={handleSubmit}
            disabled={!canSubmit || liquidate.isPending}
            className="bg-emerald-600 hover:bg-emerald-700 w-full sm:w-auto"
          >
            <CheckCircle className="h-4 w-4 mr-2" />
            {liquidate.isPending ? "Liquidando..." : "Confirmar Liquidacion"}
          </Button>
        </div>
      </div>

      {/* Modal: Agregar retención al catálogo (desde el selector) */}
      <Dialog open={addRetForKey !== null} onOpenChange={(open) => { if (!open) setAddRetForKey(null); }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Agregar Retención</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Impuesto *</Label>
              <Select value={newRetType} onValueChange={(v) => { setNewRetType(v as RetentionConfigType); if (v !== "ica") setNewMunicipality(""); }}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  {(Object.keys(RETENTION_TYPE_LABELS) as RetentionConfigType[]).map((t) => (
                    <SelectItem key={t} value={t}>{RETENTION_TYPE_LABELS[t]}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            {newRetType === "ica" && (
              <div>
                <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Municipio *</Label>
                <Input value={newMunicipality} onChange={(e) => setNewMunicipality(e.target.value)} maxLength={60} placeholder="Ej: Barranquilla" />
              </div>
            )}
            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Concepto (opcional)</Label>
              <Input value={newConcept} onChange={(e) => setNewConcept(e.target.value)} maxLength={60} placeholder="Ej: Compras, Servicios..." />
            </div>
            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">% Tarifa *</Label>
              <Input type="number" min={0.01} max={100} step="0.01" value={newRate} onChange={(e) => setNewRate(e.target.value)} placeholder="Ej: 2.5" />
              <p className="text-xs text-slate-500 mt-1.5">
                Queda en el catálogo (Tesorería → Retenciones) y se selecciona en esta fila con el monto pre-calculado — editable.
              </p>
            </div>
          </div>
          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={() => setAddRetForKey(null)}>Cancelar</Button>
            <Button
              onClick={handleAddRetention}
              disabled={!addRetValid || createRetentionConfig.isPending}
              className="bg-emerald-600 hover:bg-emerald-700"
            >
              {createRetentionConfig.isPending ? "Agregando..." : "Agregar"}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
