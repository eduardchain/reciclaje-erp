import { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { Plus, Scale, Warehouse, Flame, FlaskConical, ArrowDownUp, Pencil } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Skeleton } from "@/components/ui/skeleton";
import { PageHeader } from "@/components/shared/PageHeader";
import { EntitySelect } from "@/components/shared/EntitySelect";
import { EmptyState } from "@/components/shared/EmptyState";
import { KpiCard } from "@/components/shared/KpiCard";
import { MoneyInput } from "@/components/shared/MoneyInput";
import { KgManualMovementDialog } from "./KgManualMovementDialog";
import { usePermissions } from "@/hooks/usePermissions";
import { useKgAccounts, useKgSummary, useCreateKgAccount, useUpdateKgAccount } from "@/hooks/useKgLedger";
import { useThirdParties, useWarehouses } from "@/hooks/useMasterData";
import { saveScroll, useScrollRestoration } from "@/hooks/useScrollRestoration";
import { formatWeight } from "@/utils/formatters";
import { buildRoute, ROUTES } from "@/utils/constants";
import { cn } from "@/utils";
import {
  KG_ACCOUNT_TYPE_LABELS,
  KG_WAREHOUSE_REQUIRED_TYPES,
  KG_WILLARD_TYPES,
  type KgAccountType,
  type KgLedgerAccountResponse,
} from "@/types/kg-ledger";
import type { MetricCard } from "@/types/reports";

const asMetric = (value: number): MetricCard => ({
  current_value: value,
  previous_value: 0,
  change_percentage: null,
});

const typeBadgeColors: Record<KgAccountType, string> = {
  willard_baterias: "bg-sky-100 text-sky-800",
  willard_drosses: "bg-teal-100 text-teal-800",
  intersede: "bg-violet-100 text-violet-800",
  intra_horno: "bg-amber-100 text-amber-800",
  crisol: "bg-orange-100 text-orange-800",
};

const balanceClass = (v: number) =>
  cn("font-semibold tabular-nums", v < 0 ? "text-red-600" : "text-emerald-700");

export default function KgLedgerPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const { hasPermission } = usePermissions();
  const canManage = hasPermission("kg_ledger.manage");
  const canAdjust = hasPermission("kg_ledger.manage_adjustments");

  const [showInactive, setShowInactive] = useState(false);
  const { data: summary, isLoading: summaryLoading } = useKgSummary();
  const { data: accounts, isLoading } = useKgAccounts({ include_inactive: showInactive });
  const { data: warehousesData } = useWarehouses();
  const { data: thirdPartiesData } = useThirdParties({ is_active: true });
  const createAccount = useCreateKgAccount();
  const updateAccount = useUpdateKgAccount();

  useScrollRestoration(!isLoading);

  const warehouses = (warehousesData?.items ?? []) as { id: string; name: string }[];
  const thirdParties = thirdPartiesData?.items ?? [];
  const accountItems = accounts ?? [];

  // --- Dialog crear cuenta ---
  const [createOpen, setCreateOpen] = useState(false);
  const [cCode, setCCode] = useState("");
  const [cName, setCName] = useState("");
  const [cType, setCType] = useState<KgAccountType>("willard_baterias");
  const [cWarehouseId, setCWarehouseId] = useState("");
  const [cThirdPartyId, setCThirdPartyId] = useState("");
  const [cTolerance, setCTolerance] = useState(0);

  const isWillardType = KG_WILLARD_TYPES.includes(cType);
  const warehouseRequired = KG_WAREHOUSE_REQUIRED_TYPES.includes(cType);

  // Cuentas internas (intersede/horno/crisol) no llevan tercero (422 backend)
  useEffect(() => {
    if (!isWillardType) setCThirdPartyId("");
  }, [isWillardType]);

  const openCreate = () => {
    setCCode("");
    setCName("");
    setCType("willard_baterias");
    setCWarehouseId("");
    setCThirdPartyId("");
    setCTolerance(0);
    setCreateOpen(true);
  };

  const canSubmitCreate =
    !!cCode.trim() &&
    !!cName.trim() &&
    (!warehouseRequired || !!cWarehouseId) &&
    (!isWillardType || !!cThirdPartyId);

  const submitCreate = () => {
    createAccount.mutate(
      {
        code: cCode.trim(),
        display_name: cName.trim(),
        account_type: cType,
        warehouse_id: cWarehouseId || null,
        third_party_id: isWillardType ? cThirdPartyId || null : null,
        tolerance_kg: cTolerance > 0 ? cTolerance : null,
      },
      { onSuccess: () => setCreateOpen(false) }
    );
  };

  // --- Dialog editar cuenta ---
  const [editAccount, setEditAccount] = useState<KgLedgerAccountResponse | null>(null);
  const [eName, setEName] = useState("");
  const [eTolerance, setETolerance] = useState(0);
  const [eActive, setEActive] = useState(true);

  const openEdit = (acc: KgLedgerAccountResponse) => {
    setEditAccount(acc);
    setEName(acc.display_name);
    setETolerance(acc.tolerance_kg ?? 0);
    setEActive(acc.is_active);
  };

  const submitEdit = () => {
    if (!editAccount) return;
    const payload: { display_name?: string; tolerance_kg?: number; is_active?: boolean } = {};
    if (eName.trim() && eName.trim() !== editAccount.display_name) payload.display_name = eName.trim();
    if (eTolerance > 0 && eTolerance !== (editAccount.tolerance_kg ?? 0)) payload.tolerance_kg = eTolerance;
    if (eActive !== editAccount.is_active) payload.is_active = eActive;
    updateAccount.mutate(
      { id: editAccount.id, data: payload },
      { onSuccess: () => setEditAccount(null) }
    );
  };

  // --- Dialog movimiento manual ---
  const [manualOpen, setManualOpen] = useState(false);

  const goToStatement = (accountId: string) => {
    saveScroll(location.pathname + location.search);
    navigate(buildRoute(ROUTES.KG_LEDGER_ACCOUNT, { id: accountId }));
  };

  return (
    <div className="space-y-4">
      <PageHeader title="Plomo (kg)" description="Cuentas en kilogramos de plomo — saldos y movimientos">
        {canAdjust && (
          <Button variant="outline" onClick={() => setManualOpen(true)} className="w-full sm:w-auto">
            <ArrowDownUp className="h-4 w-4 mr-2" />
            Movimiento Manual
          </Button>
        )}
        {canManage && (
          <Button onClick={openCreate} className="bg-emerald-600 hover:bg-emerald-700 w-full sm:w-auto">
            <Plus className="h-4 w-4 mr-2" />
            Nueva Cuenta
          </Button>
        )}
      </PageHeader>

      {/* KPIs por tipo */}
      {summaryLoading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-[100px] rounded-lg" />
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4">
          <KpiCard label="Willard" metric={asMetric(summary?.total_willard_kg ?? 0)} icon={<Scale className="h-4 w-4" />} accentColor="sky" formatValue={(n) => formatWeight(n)} />
          <KpiCard label="Intersede" metric={asMetric(summary?.total_intersede_kg ?? 0)} icon={<Warehouse className="h-4 w-4" />} accentColor="violet" formatValue={(n) => formatWeight(n)} />
          <KpiCard label="Horno" metric={asMetric(summary?.total_intra_horno_kg ?? 0)} icon={<Flame className="h-4 w-4" />} accentColor="amber" formatValue={(n) => formatWeight(n)} />
          <KpiCard label="Crisol" metric={asMetric(summary?.total_crisol_kg ?? 0)} icon={<FlaskConical className="h-4 w-4" />} accentColor="teal" formatValue={(n) => formatWeight(n)} />
        </div>
      )}

      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
        <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-500">Cuentas</h2>
        <label className="flex items-center gap-2 text-sm text-slate-500">
          <Switch checked={showInactive} onCheckedChange={setShowInactive} />
          Mostrar inactivas
        </label>
      </div>

      {!isLoading && accountItems.length === 0 ? (
        <EmptyState
          title="Sin cuentas kg"
          description="Crea la primera cuenta (tipo + sede definen su estructura)."
        />
      ) : (
        <>
          {/* Desktop: tabla */}
          <div className="hidden md:block rounded-lg border bg-white overflow-x-auto">
            <Table className="min-w-[760px]">
              <TableHeader>
                <TableRow>
                  <TableHead>Código</TableHead>
                  <TableHead>Nombre</TableHead>
                  <TableHead>Tipo</TableHead>
                  <TableHead>Sede</TableHead>
                  <TableHead>Tercero</TableHead>
                  <TableHead className="text-right">Saldo (kg)</TableHead>
                  <TableHead className="text-right">Tolerancia</TableHead>
                  {canManage && <TableHead className="w-12" />}
                </TableRow>
              </TableHeader>
              <TableBody>
                {accountItems.map((acc) => (
                  <TableRow
                    key={acc.id}
                    className={cn("cursor-pointer hover:bg-slate-50", !acc.is_active && "opacity-60")}
                    onClick={() => goToStatement(acc.id)}
                  >
                    <TableCell className="font-medium">{acc.code}</TableCell>
                    <TableCell>
                      {acc.display_name}
                      {!acc.is_active && (
                        <Badge variant="outline" className="ml-2 bg-slate-100 text-slate-600">Inactiva</Badge>
                      )}
                    </TableCell>
                    <TableCell>
                      <Badge variant="outline" className={typeBadgeColors[acc.account_type] ?? ""}>
                        {KG_ACCOUNT_TYPE_LABELS[acc.account_type] ?? acc.account_type}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-slate-500">{acc.warehouse_name ?? "—"}</TableCell>
                    <TableCell className="text-slate-500">{acc.third_party_name ?? "—"}</TableCell>
                    <TableCell className="text-right">
                      <span className={balanceClass(acc.current_balance_kg)}>
                        {formatWeight(acc.current_balance_kg)}
                      </span>
                    </TableCell>
                    <TableCell className="text-right text-slate-500 tabular-nums">
                      {acc.tolerance_kg != null ? `± ${formatWeight(acc.tolerance_kg)}` : "—"}
                    </TableCell>
                    {canManage && (
                      <TableCell onClick={(e) => e.stopPropagation()}>
                        <Button variant="ghost" size="sm" onClick={() => openEdit(acc)} aria-label="Editar cuenta">
                          <Pencil className="h-4 w-4 text-slate-500" />
                        </Button>
                      </TableCell>
                    )}
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>

          {/* Mobile: cards */}
          <div className="md:hidden space-y-2">
            {accountItems.map((acc) => (
              <div
                key={acc.id}
                className={cn(
                  "rounded-md border bg-white px-3 py-2 shadow-sm",
                  !acc.is_active && "opacity-60"
                )}
                onClick={() => goToStatement(acc.id)}
              >
                <div className="flex items-center gap-2">
                  <span className="text-xs font-semibold text-slate-700 shrink-0">{acc.code}</span>
                  <span className="text-sm font-medium text-slate-800 truncate flex-1 min-w-0">
                    {acc.display_name}
                  </span>
                  <span className={cn("text-sm shrink-0", balanceClass(acc.current_balance_kg))}>
                    {formatWeight(acc.current_balance_kg)}
                  </span>
                  {canManage && (
                    <Button
                      variant="ghost"
                      size="sm"
                      className="shrink-0 h-7 w-7 p-0"
                      onClick={(e) => { e.stopPropagation(); openEdit(acc); }}
                      aria-label="Editar cuenta"
                    >
                      <Pencil className="h-3.5 w-3.5 text-slate-500" />
                    </Button>
                  )}
                </div>
                <div className="mt-0.5 flex flex-wrap items-center gap-x-1.5 gap-y-0.5 text-[11px] text-slate-500">
                  <Badge variant="outline" className={cn("text-[10px] py-0", typeBadgeColors[acc.account_type] ?? "")}>
                    {KG_ACCOUNT_TYPE_LABELS[acc.account_type] ?? acc.account_type}
                  </Badge>
                  {acc.warehouse_name && <span>· {acc.warehouse_name}</span>}
                  {acc.tolerance_kg != null && <span>· Tol: ± {formatWeight(acc.tolerance_kg)}</span>}
                  {!acc.is_active && <span className="text-slate-400">· Inactiva</span>}
                </div>
              </div>
            ))}
          </div>
        </>
      )}

      {/* Dialog crear cuenta */}
      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent onClick={(e) => e.stopPropagation()}>
          <DialogHeader>
            <DialogTitle>Nueva Cuenta (kg)</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Código *</Label>
                <Input
                  value={cCode}
                  onChange={(e) => setCCode(e.target.value.toUpperCase())}
                  maxLength={32}
                  placeholder="Ej: WILLARD-BAT-CV"
                />
              </div>
              <div>
                <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Tipo *</Label>
                <Select value={cType} onValueChange={(v) => setCType(v as KgAccountType)}>
                  <SelectTrigger className="w-full"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {(Object.keys(KG_ACCOUNT_TYPE_LABELS) as KgAccountType[]).map((t) => (
                      <SelectItem key={t} value={t}>{KG_ACCOUNT_TYPE_LABELS[t]}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Nombre *</Label>
              <Input value={cName} onChange={(e) => setCName(e.target.value)} maxLength={120} placeholder="Ej: Willard Baterías CV" />
            </div>
            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                Sede {warehouseRequired ? "*" : "(opcional)"}
              </Label>
              <EntitySelect
                value={cWarehouseId}
                onChange={setCWarehouseId}
                options={warehouses.map((w) => ({ id: w.id, label: w.name }))}
                placeholder="Bodega / sede..."
              />
              {warehouseRequired && !cWarehouseId && (
                <p className="text-xs text-slate-500 mt-0.5">Este tipo de cuenta requiere sede.</p>
              )}
            </div>
            {isWillardType && (
              <div>
                <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Tercero (Willard) *</Label>
                <EntitySelect
                  value={cThirdPartyId}
                  onChange={setCThirdPartyId}
                  options={thirdParties.map((tp) => ({ id: tp.id, label: tp.name }))}
                  placeholder="Tercero..."
                />
              </div>
            )}
            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Tolerancia (± kg, opcional)</Label>
              <MoneyInput value={cTolerance} onChange={setCTolerance} decimals={2} placeholder="0,00" />
              <p className="text-xs text-slate-400 mt-0.5">Para alertas del cuadre — vacío = sin alerta.</p>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setCreateOpen(false)} className="w-full sm:w-auto">Cancelar</Button>
            <Button
              onClick={submitCreate}
              disabled={!canSubmitCreate || createAccount.isPending}
              className="bg-emerald-600 hover:bg-emerald-700 w-full sm:w-auto"
            >
              {createAccount.isPending ? "Creando..." : "Crear Cuenta"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Dialog editar cuenta */}
      <Dialog open={!!editAccount} onOpenChange={(o) => !o && setEditAccount(null)}>
        <DialogContent onClick={(e) => e.stopPropagation()}>
          <DialogHeader>
            <DialogTitle>Editar Cuenta {editAccount?.code}</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <p className="text-xs text-slate-500">
              Tipo, sede y tercero son inmutables — para cambiarlos, desactive esta cuenta y cree otra.
            </p>
            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Nombre *</Label>
              <Input value={eName} onChange={(e) => setEName(e.target.value)} maxLength={120} />
            </div>
            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Tolerancia (± kg)</Label>
              <MoneyInput value={eTolerance} onChange={setETolerance} decimals={2} placeholder="0,00" />
            </div>
            <div className="flex items-center justify-between">
              <div>
                <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Activa</Label>
                <p className="text-xs text-slate-400">Desactivar requiere saldo en 0.</p>
              </div>
              <Switch checked={eActive} onCheckedChange={setEActive} />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setEditAccount(null)} className="w-full sm:w-auto">Cancelar</Button>
            <Button
              onClick={submitEdit}
              disabled={!eName.trim() || updateAccount.isPending}
              className="bg-emerald-600 hover:bg-emerald-700 w-full sm:w-auto"
            >
              {updateAccount.isPending ? "Guardando..." : "Actualizar"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <KgManualMovementDialog
        open={manualOpen}
        onOpenChange={setManualOpen}
        accounts={accountItems.filter((a) => a.is_active)}
      />
    </div>
  );
}
