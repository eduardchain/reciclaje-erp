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
import { useRetentionRows, useCreateRetentionConfig, useUpdateRetentionConfig } from "@/hooks/useMasterData";
import { ROUTES } from "@/utils/constants";
import { RETENTION_TYPE_LABELS } from "@/types/purchase";
import type { RetentionRow, RetentionConfigType } from "@/types/third-party";

export function retentionRowLabel(r: RetentionRow): string {
  let label: string = RETENTION_TYPE_LABELS[r.retention_type];
  if (r.municipality) label += ` — ${r.municipality}`;
  if (r.concept) label += ` · ${r.concept}`;
  return label;
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
  const openAdd = (prefill?: RetentionRow) => {
    setNewType(prefill?.retention_type ?? "retefuente");
    setNewMunicipality(prefill?.municipality ?? "");
    setNewConcept("");
    setNewRate("");
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
      },
      {
        onSuccess: (created) => {
          toast.success(`Retención configurada: ${retentionRowLabel(created)} (${created.rate_pct}%)`);
          setShowAdd(false);
        },
      },
    );
  };

  // Dialog editar %
  const [editTarget, setEditTarget] = useState<RetentionRow | null>(null);
  const [editRate, setEditRate] = useState("");
  const editRateNum = parseFloat(editRate);
  const editValid = !Number.isNaN(editRateNum) && editRateNum > 0 && editRateNum <= 100;
  const handleEdit = () => {
    if (!editTarget?.config_id) return;
    updateConfig.mutate(
      { configId: editTarget.config_id, data: { rate_pct: editRateNum } },
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

  const rowActions = (r: RetentionRow, mobile = false) => (
    <>
      {canPay && r.entity_id && (
        <Button variant="outline" size="sm" className={mobile ? "w-full" : ""} onClick={() => navigate(`${ROUTES.TREASURY_NEW}?type=liability_payment&third_party_id=${r.entity_id}`)}>
          Pagar
        </Button>
      )}
      {r.entity_id && (
        <Button variant="outline" size="sm" className={mobile ? "w-full" : ""} onClick={() => navigate(`${ROUTES.TREASURY_ACCOUNT_STATEMENT}?third_party_id=${r.entity_id}&returnTo=/treasury/retentions`)}>
          {mobile ? "Estado" : "Estado de Cuenta"}
        </Button>
      )}
      {canManage && r.config_id && (
        <Button variant="outline" size="sm" className={mobile ? "w-full" : ""} onClick={() => { setEditTarget(r); setEditRate(String(r.rate_pct ?? "")); }}>
          <Pencil className="h-3 w-3 mr-1" />% Tarifa
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
        title="Retenciones"
        description="Tarifas configuradas y deuda acumulada por retenciones aplicadas al liquidar compras — para el pago de impuestos"
      >
        {canManage && (
          <Button onClick={() => openAdd()} className="bg-emerald-600 hover:bg-emerald-700 w-full sm:w-auto">
            <Plus className="h-4 w-4 mr-2" />Agregar Retención
          </Button>
        )}
      </PageHeader>

      <div className="flex flex-col sm:flex-row sm:gap-3 sm:items-center gap-2">
        <SearchInput value={search} onChange={setSearch} placeholder="Buscar retención..." />
        <div className="flex items-center gap-2">
          <Checkbox id="show-inactive-ret" checked={showInactive} onCheckedChange={(c) => setShowInactive(c === true)} />
          <label htmlFor="show-inactive-ret" className="text-sm text-slate-600 cursor-pointer whitespace-nowrap">
            Mostrar inactivas
          </label>
        </div>
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
                      </TableCell>
                      <TableCell className="text-right">
                        {r.entity_id ? <MoneyDisplay amount={r.current_balance} /> : <span className="text-slate-400">—</span>}
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
              <p className="text-xs text-slate-500 mt-1">Al liquidar, el monto se pre-calcula con este % sobre el subtotal — siempre editable.</p>
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
