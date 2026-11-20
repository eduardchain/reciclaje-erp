import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Plus, Landmark, Pencil } from "lucide-react";
import { toast } from "sonner";
import { usePermissions } from "@/hooks/usePermissions";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { PageHeader } from "@/components/shared/PageHeader";
import { SearchInput } from "@/components/shared/SearchInput";
import { MoneyDisplay } from "@/components/shared/MoneyDisplay";
import { useRetentionRows, useTaxEntityRows, useCreateRetentionConfig, useUpdateRetentionConfig } from "@/hooks/useMasterData";
import { taxBalanceNature } from "@/utils/taxBalanceNature";
import { ROUTES } from "@/utils/constants";
import { RETENTION_TYPE_LABELS } from "@/types/purchase";
import type { RetentionRow, RetentionConfigType, RetentionBaseKind, TaxEntityRow } from "@/types/third-party";

export function retentionRowLabel(r: RetentionRow): string {
  let label: string = RETENTION_TYPE_LABELS[r.retention_type];
  if (r.municipality) label += ` — ${r.municipality}`;
  if (r.concept) label += ` · ${r.concept}`;
  return label;
}

/** Etiqueta «Por pagar» / «A favor» — el criterio vive en `taxBalanceNature`. */
function NatureBadge({ balance, small = false }: { balance: number; small?: boolean }) {
  const n = taxBalanceNature(balance);
  return (
    <Badge variant="outline" data-nature={n.kind} className={`${small ? "text-[10px]" : "text-xs"} ${n.className}`}>
      {n.label}
    </Badge>
  );
}

export default function RetentionsPage() {
  const navigate = useNavigate();
  const { hasPermission } = usePermissions();
  const [search, setSearch] = useState("");
  const [showInactive, setShowInactive] = useState(false);

  // La ruta ya está gated por FP (flag + permiso) — acá el fetch va directo.
  const { data, isLoading } = useRetentionRows(true);
  const rows = (data ?? []).filter(
    (r) =>
      (showInactive || r.is_active) &&
      (!search || retentionRowLabel(r).toLowerCase().includes(search.toLowerCase())),
  );

  // Sección 1 (plan v1.2 D2): entidades «[Impuestos] X». SIN filtro de
  // inactivas — una inactiva con saldo se muestra (C3); solo la búsqueda filtra.
  const { data: taxData, isLoading: taxLoading } = useTaxEntityRows(true);
  const taxRows = (taxData ?? []).filter(
    (t) => !search || `${t.label} ${t.name}`.toLowerCase().includes(search.toLowerCase()),
  );

  const canManage = hasPermission("third_parties.create");
  const canPay = hasPermission("treasury.create_movements");
  const createConfig = useCreateRetentionConfig();
  const updateConfig = useUpdateRetentionConfig();

  // Dialog crear/configurar tarifa
  const [showAdd, setShowAdd] = useState(false);
  const [newType, setNewType] = useState<RetentionConfigType>("retefuente");
  const [newMunicipality, setNewMunicipality] = useState("");
  const [newConcept, setNewConcept] = useState("");
  const [newRate, setNewRate] = useState("");
  // CC-013 D5: sobre QUE se aplica la tarifa. `subtotal` es lo que hacen hoy
  // las dos pantallas de compras, asi que ese default deja compras byte a byte.
  const [newBaseKind, setNewBaseKind] = useState<RetentionBaseKind>("subtotal");
  const openAdd = (prefill?: RetentionRow) => {
    setNewType(prefill?.retention_type ?? "retefuente");
    setNewMunicipality(prefill?.municipality ?? "");
    setNewConcept("");
    setNewRate("");
    setNewBaseKind("subtotal");
    setShowAdd(true);
  };
  const newRateNum = parseFloat(newRate);
  const addValid =
    !Number.isNaN(newRateNum) && newRateNum > 0 && newRateNum <= 100 &&
    (newType !== "ica" || !!newMunicipality.trim());
  const handleAdd = () => {
    createConfig.mutate(
      {
        retention_type: newType,
        ...(newType === "ica" ? { municipality: newMunicipality.trim() } : {}),
        ...(newConcept.trim() ? { concept: newConcept.trim() } : {}),
        rate_pct: newRateNum,
        base_kind: newBaseKind,
      },
      {
        onSuccess: (created) => {
          toast.success(`Retención configurada: ${retentionRowLabel(created)} (${created.rate_pct}%)`);
          setShowAdd(false);
        },
      },
    );
  };

  // Dialog editar % y base
  const [editTarget, setEditTarget] = useState<RetentionRow | null>(null);
  const [editRate, setEditRate] = useState("");
  // La base se edita igual que el %: sin esto, una tarifa sembrada con el
  // default `subtotal` no se podia corregir desde ninguna pantalla, que es
  // justo lo que el runbook manda hacer con las tres tarifas de sistema.
  const [editBaseKind, setEditBaseKind] = useState<RetentionBaseKind>("subtotal");
  const editRateNum = parseFloat(editRate);
  const editValid = !Number.isNaN(editRateNum) && editRateNum > 0 && editRateNum <= 100;
  const handleEdit = () => {
    if (!editTarget?.config_id) return;
    updateConfig.mutate(
      { configId: editTarget.config_id, data: { rate_pct: editRateNum, base_kind: editBaseKind } },
      {
        onSuccess: () => {
          toast.success("Tarifa actualizada");
          setEditTarget(null);
        },
      },
    );
  };

  const toggleActive = (r: RetentionRow) => {
    if (!r.config_id) return;
    updateConfig.mutate(
      { configId: r.config_id, data: { is_active: !r.is_active } },
      { onSuccess: () => toast.success(r.is_active ? "Tarifa desactivada" : "Tarifa reactivada") },
    );
  };

  const statementUrl = (entityId: string) =>
    `${ROUTES.TREASURY_ACCOUNT_STATEMENT}?third_party_id=${entityId}&returnTo=/treasury/retentions`;

  // Pagar en la sección 1: SOLO si el saldo es «Por pagar». Un saldo a favor se
  // cruza en la declaración, no se paga.
  const taxActions = (t: TaxEntityRow, mobile = false) => (
    <>
      {canPay && taxBalanceNature(t.current_balance).payable && (
        <Button variant="outline" size="sm" className={mobile ? "w-full" : ""} onClick={() => navigate(`${ROUTES.TREASURY_NEW}?type=liability_payment&third_party_id=${t.entity_id}`)}>
          Pagar
        </Button>
      )}
      <Button variant="outline" size="sm" className={mobile ? "w-full" : ""} onClick={() => navigate(statementUrl(t.entity_id))}>
        {mobile ? "Estado" : "Estado de Cuenta"}
      </Button>
    </>
  );

  const rowActions = (r: RetentionRow, mobile = false) => (
    <>
      {canPay && r.entity_id && (
        <Button variant="outline" size="sm" className={mobile ? "w-full" : ""} onClick={() => navigate(`${ROUTES.TREASURY_NEW}?type=liability_payment&third_party_id=${r.entity_id}`)}>
          Pagar
        </Button>
      )}
      {r.entity_id && (
        <Button variant="outline" size="sm" className={mobile ? "w-full" : ""} onClick={() => navigate(statementUrl(r.entity_id!))}>
          {mobile ? "Estado" : "Estado de Cuenta"}
        </Button>
      )}
      {canManage && r.config_id && (
        <Button variant="outline" size="sm" className={mobile ? "w-full" : ""} onClick={() => { setEditTarget(r); setEditRate(String(r.rate_pct ?? "")); setEditBaseKind(r.base_kind === "iva" ? "iva" : "subtotal"); }}>
          <Pencil className="h-3 w-3 mr-1" />Editar
        </Button>
      )}
      {canManage && !r.config_id && (
        <Button variant="outline" size="sm" className={mobile ? "w-full" : "text-indigo-600"} onClick={() => openAdd(r)}>
          Configurar %
        </Button>
      )}
    </>
  );

  return (
    <div className="space-y-6">
      <PageHeader
        title="Impuestos y retenciones"
        description="El IVA y las retenciones que nos practican, y las retenciones que practicamos al liquidar compras. Cada saldo se muestra solo: no se suman entre sí."
      >
        {canManage && (
          <Button onClick={() => openAdd()} className="bg-emerald-600 hover:bg-emerald-700 w-full sm:w-auto">
            <Plus className="h-4 w-4 mr-2" />Agregar Retención
          </Button>
        )}
      </PageHeader>

      <div className="flex flex-col sm:flex-row sm:gap-3 sm:items-center gap-2">
        <SearchInput value={search} onChange={setSearch} placeholder="Buscar impuesto o retención..." />
        <div className="flex items-center gap-2">
          <Checkbox id="show-inactive-ret" checked={showInactive} onCheckedChange={(c) => setShowInactive(c === true)} />
          <label htmlFor="show-inactive-ret" className="text-sm text-slate-600 cursor-pointer whitespace-nowrap">
            Mostrar tarifas inactivas
          </label>
        </div>
      </div>

      {/* Sección 1 — Impuestos (IVA y retenciones que nos practican) */}
      <section className="space-y-2" data-testid="tax-section">
        <div>
          <h2 className="text-base font-semibold text-slate-800">Impuestos (IVA y retenciones que nos practican)</h2>
          <p className="text-xs text-slate-500">
            Saldo negativo: se le debe a la DIAN. Saldo positivo: queda a favor y se cruza en la declaración.
          </p>
        </div>
        <Card className="shadow-sm">
          <CardContent className="p-0">
            {taxLoading ? (
              <p className="text-sm text-slate-400 py-8 text-center">Cargando...</p>
            ) : taxRows.length === 0 ? (
              <p className="p-6 text-sm text-slate-500">
                {search
                  ? "Ningún impuesto coincide con la búsqueda."
                  : "Aún no hay impuestos registrados. Aparecen al liquidar una venta, una Salida de Plomo o una compra con IVA."}
              </p>
            ) : (
              <>
                <Table className="hidden md:table">
                  <TableHeader>
                    <TableRow>
                      <TableHead>Impuesto</TableHead>
                      <TableHead className="text-right">Saldo Contable</TableHead>
                      <TableHead>Naturaleza</TableHead>
                      <TableHead className="text-right">Acciones</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {taxRows.map((t) => (
                      <TableRow key={t.entity_id} data-testid="tax-row" className={!t.is_active ? "opacity-60" : ""}>
                        <TableCell>
                          <div className="flex items-center gap-2 flex-wrap font-medium">
                            {t.label}
                            {!t.is_active && <Badge variant="secondary" className="text-xs">Inactiva</Badge>}
                          </div>
                          <div className="text-xs text-slate-400">{t.name}</div>
                        </TableCell>
                        <TableCell className="text-right">
                          <MoneyDisplay amount={t.current_balance} />
                        </TableCell>
                        <TableCell><NatureBadge balance={t.current_balance} /></TableCell>
                        <TableCell className="text-right">
                          <div className="flex justify-end gap-2">{taxActions(t)}</div>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>

                {/* Mobile: cards */}
                <div className="md:hidden space-y-2 p-3">
                  {taxRows.map((t) => (
                    <div key={t.entity_id} data-testid="tax-card" className={`rounded-md border bg-white p-3 shadow-sm ${!t.is_active ? "opacity-60" : ""}`}>
                      <div className="flex items-start justify-between gap-2">
                        <div className="min-w-0 flex-1">
                          <div className="font-medium truncate">{t.label}</div>
                          <div className="text-xs text-slate-400 truncate">{t.name}</div>
                          <div className="flex gap-1 mt-1 flex-wrap">
                            <NatureBadge balance={t.current_balance} small />
                            {!t.is_active && <Badge variant="secondary" className="text-[10px]">Inactiva</Badge>}
                          </div>
                        </div>
                        <MoneyDisplay amount={t.current_balance} className="text-sm shrink-0" />
                      </div>
                      <div className="mt-3 grid grid-cols-2 gap-1.5">{taxActions(t, true)}</div>
                    </div>
                  ))}
                </div>
              </>
            )}
          </CardContent>
        </Card>
      </section>

      {/* Sección 2 — Retenciones que practicamos (la tabla de siempre) */}
      <div>
        <h2 className="text-base font-semibold text-slate-800">Retenciones que practicamos</h2>
        <p className="text-xs text-slate-500">Las que aplicamos al liquidar compras: se le deben a la DIAN.</p>
      </div>
      <Card className="shadow-sm">
        <CardContent className="p-0">
          {isLoading ? (
            <p className="text-sm text-slate-400 py-8 text-center">Cargando...</p>
          ) : rows.length === 0 ? (
            <div className="p-6 text-sm text-slate-500 space-y-1">
              <p className="font-medium flex items-center gap-2"><Landmark className="h-4 w-4 text-indigo-600" />Sin retenciones configuradas.</p>
              <p>Agrega las tarifas (ReteFuente, ReteIVA, ICA por municipio) y quedarán disponibles en el selector al liquidar compras, con el monto pre-calculado y editable.</p>
            </div>
          ) : (
            <>
              <Table className="hidden md:table">
                <TableHeader>
                  <TableRow>
                    <TableHead>Retención</TableHead>
                    <TableHead className="text-right">% Tarifa</TableHead>
                    <TableHead className="text-right">Saldo Contable</TableHead>
                    <TableHead className="text-right">Acciones</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {rows.map((r) => (
                    <TableRow key={r.config_id ?? r.entity_id} className={!r.is_active ? "opacity-60" : ""}>
                      <TableCell className="font-medium">
                        <div className="flex items-center gap-2 flex-wrap">
                          {retentionRowLabel(r)}
                          <Badge variant="outline" className="text-xs text-indigo-600 border-indigo-200">Sistema</Badge>
                          {!r.is_active && <Badge variant="secondary" className="text-xs">Inactiva</Badge>}
                          {!r.entity_id && <Badge variant="secondary" className="text-xs">Sin uso aún</Badge>}
                          {!r.config_id && <Badge variant="secondary" className="text-xs text-amber-700">Sin tarifa</Badge>}
                        </div>
                      </TableCell>
                      <TableCell className="text-right tabular-nums">
                        {r.rate_pct != null ? `${r.rate_pct}%` : "—"}
                        {r.base_kind === "iva" && (
                          <span className="text-xs text-slate-400 ml-1">sobre IVA</span>
                        )}
                      </TableCell>
                      <TableCell className="text-right">
                        {r.entity_id ? (
                          <div className="flex items-center justify-end gap-2">
                            <MoneyDisplay amount={r.current_balance} />
                            <NatureBadge balance={r.current_balance} />
                          </div>
                        ) : <span className="text-slate-400">—</span>}
                      </TableCell>
                      <TableCell className="text-right">
                        <div className="flex justify-end gap-2">{rowActions(r)}</div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>

              {/* Mobile: cards */}
              <div className="md:hidden space-y-2 p-3">
                {rows.map((r) => (
                  <div key={r.config_id ?? r.entity_id} className={`rounded-md border bg-white p-3 shadow-sm ${!r.is_active ? "opacity-60" : ""}`}>
                    <div className="flex items-center justify-between gap-2">
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2">
                          <span className="font-medium truncate">{retentionRowLabel(r)}</span>
                          {r.rate_pct != null && <span className="text-sm text-slate-500 shrink-0">{r.rate_pct}%</span>}
                        </div>
                        <div className="flex gap-1 mt-1 flex-wrap">
                          <Badge variant="outline" className="text-[10px] text-indigo-600 border-indigo-200">Sistema</Badge>
                          {!r.is_active && <Badge variant="secondary" className="text-[10px]">Inactiva</Badge>}
                          {!r.entity_id && <Badge variant="secondary" className="text-[10px]">Sin uso aún</Badge>}
                          {r.entity_id && <NatureBadge balance={r.current_balance} small />}
                        </div>
                      </div>
                      {r.entity_id && <MoneyDisplay amount={r.current_balance} className="text-sm shrink-0" />}
                    </div>
                    <div className="mt-3 grid grid-cols-2 gap-1.5">{rowActions(r, true)}</div>
                  </div>
                ))}
              </div>
            </>
          )}
        </CardContent>
      </Card>

      {/* Dialog: agregar tarifa */}
      <Dialog open={showAdd} onOpenChange={setShowAdd}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Agregar Retención</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Impuesto *</Label>
              <Select value={newType} onValueChange={(v) => { setNewType(v as RetentionConfigType); if (v !== "ica") setNewMunicipality(""); }}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  {(Object.keys(RETENTION_TYPE_LABELS) as RetentionConfigType[]).map((t) => (
                    <SelectItem key={t} value={t}>{RETENTION_TYPE_LABELS[t]}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            {newType === "ica" && (
              <div>
                <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Municipio *</Label>
                <Input value={newMunicipality} onChange={(e) => setNewMunicipality(e.target.value)} maxLength={60} placeholder="Ej: Barranquilla" />
              </div>
            )}
            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Concepto (opcional)</Label>
              <Input value={newConcept} onChange={(e) => setNewConcept(e.target.value)} maxLength={60} placeholder="Ej: Compras, Servicios..." />
              <p className="text-xs text-slate-500 mt-1">Si el mismo impuesto tiene tarifas distintas por concepto, crea una retención por concepto.</p>
            </div>
            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">% Tarifa *</Label>
              <Input type="number" min={0.01} max={100} step="0.01" value={newRate} onChange={(e) => setNewRate(e.target.value)} placeholder="Ej: 2.5" />
              <p className="text-xs text-slate-500 mt-1">Al liquidar, el monto se pre-calcula con este % — siempre editable.</p>
            </div>
            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Se aplica sobre *</Label>
              <Select value={newBaseKind} onValueChange={(v) => setNewBaseKind(v as RetentionBaseKind)}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="subtotal">El subtotal del documento</SelectItem>
                  <SelectItem value="iva">El IVA de la factura</SelectItem>
                </SelectContent>
              </Select>
              <p className="text-xs text-slate-500 mt-1">
                La reteIVA se aplica sobre el IVA; la retefuente y el ICA sobre el subtotal.
                Guardar una reteIVA como un % del subtotal da el número correcto solo
                mientras el IVA no cambie.
              </p>
              {newBaseKind === "iva" && (
                <p className="text-xs text-amber-700 mt-1">
                  Una tarifa sobre el IVA deja de ofrecerse al liquidar Entradas y compras:
                  una compra no lleva IVA.
                </p>
              )}
            </div>
          </div>
          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={() => setShowAdd(false)}>Cancelar</Button>
            <Button onClick={handleAdd} disabled={!addValid || createConfig.isPending} className="bg-emerald-600 hover:bg-emerald-700">
              {createConfig.isPending ? "Agregando..." : "Agregar"}
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Dialog: editar % */}
      <Dialog open={!!editTarget} onOpenChange={(open) => { if (!open) setEditTarget(null); }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Editar Tarifa — {editTarget ? retentionRowLabel(editTarget) : ""}</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">% Tarifa *</Label>
              <Input type="number" min={0.01} max={100} step="0.01" value={editRate} onChange={(e) => setEditRate(e.target.value)} autoFocus />
              <p className="text-xs text-slate-500 mt-1">Aplica a liquidaciones futuras; las pasadas conservan el % con que se liquidaron.</p>
            </div>
            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Se aplica sobre *</Label>
              <Select value={editBaseKind} onValueChange={(v) => setEditBaseKind(v as RetentionBaseKind)}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="subtotal">El subtotal del documento</SelectItem>
                  <SelectItem value="iva">El IVA de la factura</SelectItem>
                </SelectContent>
              </Select>
              <p className="text-xs text-slate-500 mt-1">
                La reteIVA se aplica sobre el IVA; la retefuente y el ICA sobre el subtotal.
                Guardar una reteIVA como un % del subtotal da el número correcto solo
                mientras el IVA no cambie.
              </p>
              {editBaseKind === "iva" && (
                <p className="text-xs text-amber-700 mt-1">
                  Una tarifa sobre el IVA deja de ofrecerse al liquidar Entradas y compras:
                  una compra no lleva IVA.
                </p>
              )}
            </div>
            {editTarget?.config_id && (
              <Button variant="outline" size="sm" className="text-red-600 hover:text-red-700 hover:bg-red-50" onClick={() => { if (editTarget) toggleActive(editTarget); setEditTarget(null); }}>
                {editTarget.is_active ? "Desactivar esta tarifa" : "Reactivar esta tarifa"}
              </Button>
            )}
          </div>
          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={() => setEditTarget(null)}>Cancelar</Button>
            <Button onClick={handleEdit} disabled={!editValid || updateConfig.isPending} className="bg-emerald-600 hover:bg-emerald-700">
              {updateConfig.isPending ? "Guardando..." : "Guardar"}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
