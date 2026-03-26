import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { PiggyBank, Plus, Receipt, FileText, Power, PowerOff } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { PageHeader } from "@/components/shared/PageHeader";
import { SearchInput } from "@/components/shared/SearchInput";
import { MoneyDisplay } from "@/components/shared/MoneyDisplay";
import { EmptyState } from "@/components/shared/EmptyState";
import { ConfirmDialog } from "@/components/shared/ConfirmDialog";
import { usePermissions } from "@/hooks/usePermissions";
import { useProvisions, useThirdPartyCategoriesFlat } from "@/hooks/useMasterData";
import { useDeactivateThirdParty, useReactivateThirdParty } from "@/hooks/useCrudData";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { thirdPartyService } from "@/services/thirdParties";
import { getApiErrorMessage } from "@/utils/formatters";
import { formatCurrency } from "@/utils/formatters";
import { ROUTES } from "@/utils/constants";
import type { ThirdPartyCreate, ThirdPartyResponse } from "@/types/third-party";

export default function ProvisionsPage() {
  const navigate = useNavigate();
  const { hasPermission } = usePermissions();
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const [showInactive, setShowInactive] = useState(false);
  const { data, isLoading } = useProvisions(search || undefined, showInactive ? undefined : true);
  const provisions = data?.items ?? [];
  const { data: provCatsData } = useThirdPartyCategoriesFlat("provision");
  const provisionCategories = provCatsData?.items ?? [];
  const provisionCategoryId = provisionCategories.length > 0 ? provisionCategories[0].id : null;

  const canDelete = hasPermission("third_parties.delete");
  const deactivateMutation = useDeactivateThirdParty();
  const reactivateMutation = useReactivateThirdParty();
  const [deactivateTarget, setDeactivateTarget] = useState<ThirdPartyResponse | null>(null);
  const [reactivateTarget, setReactivateTarget] = useState<ThirdPartyResponse | null>(null);

  const totalAvailable = provisions.reduce((sum, p) => {
    return sum + (p.current_balance < 0 ? Math.abs(p.current_balance) : 0);
  }, 0);

  // Modal crear provision
  const [showCreate, setShowCreate] = useState(false);
  const [newName, setNewName] = useState("");
  const createTP = useMutation({
    mutationFn: (data: ThirdPartyCreate) => thirdPartyService.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["third-parties"] });
      toast.success("Provision creada exitosamente");
      setShowCreate(false);
      setNewName("");
    },
    onError: (error: unknown) => {
      toast.error(getApiErrorMessage(error, "Error al crear la provision"));
    },
  });

  return (
    <div className="space-y-6">
      <PageHeader title="Provisiones" description="Gestion de fondos provisionados">
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => navigate(ROUTES.TREASURY)}>
            Volver a Tesoreria
          </Button>
          <Button onClick={() => setShowCreate(true)} className="bg-emerald-600 hover:bg-emerald-700" disabled={!provisionCategoryId} title={!provisionCategoryId ? "Configure categorias de Provision primero" : undefined}>
            <Plus className="h-4 w-4 mr-2" />Nueva Provision
          </Button>
        </div>
      </PageHeader>

      <Card className="border-t-[3px] border-t-violet-500 shadow-sm">
        <CardContent className="p-5">
          <div className="flex items-center gap-2 mb-1">
            <PiggyBank className="h-5 w-5 text-violet-600" />
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">Total Fondos Disponibles</span>
          </div>
          <p className="text-2xl font-bold text-slate-900 tabular-nums">{formatCurrency(totalAvailable)}</p>
          <p className="text-xs text-slate-400 mt-1">{provisions.length} provision(es) registrada(s)</p>
        </CardContent>
      </Card>

      <div className="flex gap-3 items-center">
        <SearchInput value={search} onChange={setSearch} placeholder="Buscar provision..." />
        <div className="flex items-center gap-2">
          <Checkbox
            id="show-inactive-provisions"
            checked={showInactive}
            onCheckedChange={(checked) => setShowInactive(checked === true)}
          />
          <label htmlFor="show-inactive-provisions" className="text-sm text-slate-600 cursor-pointer whitespace-nowrap">
            Mostrar inactivos
          </label>
        </div>
      </div>

      <Card className="shadow-sm">
        <CardHeader>
          <CardTitle className="text-sm font-semibold uppercase tracking-wider text-slate-500">Provisiones</CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <p className="text-sm text-slate-400 py-8 text-center">Cargando...</p>
          ) : provisions.length === 0 ? (
            <EmptyState
              title="Sin provisiones"
              description="Crea una provision para apartar fondos."
            />
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Nombre</TableHead>
                  <TableHead className="text-right">Fondos Disponibles</TableHead>
                  <TableHead className="text-right">Saldo Contable</TableHead>
                  <TableHead className="text-right">Acciones</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {provisions.map((p) => {
                  const funds = p.current_balance < 0 ? Math.abs(p.current_balance) : 0;
                  return (
                    <TableRow key={p.id}>
                      <TableCell className={`font-medium ${!p.is_active ? "opacity-50" : ""}`}>
                        <div className="flex items-center gap-2">
                          {p.name}
                          {!p.is_active && <Badge variant="secondary" className="text-xs">Inactivo</Badge>}
                        </div>
                      </TableCell>
                      <TableCell className={`text-right ${!p.is_active ? "opacity-50" : ""}`}>
                        <MoneyDisplay amount={funds} />
                      </TableCell>
                      <TableCell className={`text-right ${!p.is_active ? "opacity-50" : ""}`}>
                        <MoneyDisplay amount={p.current_balance} />
                      </TableCell>
                      <TableCell className="text-right">
                        <div className="flex justify-end gap-1">
                          {p.is_active && (
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => navigate(`${ROUTES.TREASURY_NEW}?type=provision_deposit&provision_id=${p.id}`)}
                            >
                              <Plus className="h-3 w-3 mr-1" />Depositar
                            </Button>
                          )}
                          {p.is_active && (
                            <Button
                              size="sm"
                              variant="outline"
                              disabled={p.current_balance >= 0}
                              onClick={() => {
                                if (p.current_balance >= 0) {
                                  toast.error(`La provision "${p.name}" esta en sobregiro. Deposite fondos antes de registrar un gasto.`);
                                  return;
                                }
                                navigate(`${ROUTES.TREASURY_NEW}?type=provision_expense&provision_id=${p.id}`);
                              }}
                            >
                              <Receipt className="h-3 w-3 mr-1" />Gasto
                            </Button>
                          )}
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => navigate(`${ROUTES.TREASURY_ACCOUNT_STATEMENT}?third_party_id=${p.id}`)}
                          >
                            <FileText className="h-3 w-3 mr-1" />Estado Cuenta
                          </Button>
                          {canDelete && p.is_active && (
                            <Button
                              size="sm"
                              variant="outline"
                              className="text-red-600 hover:text-red-700 hover:bg-red-50"
                              onClick={() => setDeactivateTarget(p)}
                            >
                              <PowerOff className="h-3 w-3 mr-1" />Desactivar
                            </Button>
                          )}
                          {canDelete && !p.is_active && (
                            <Button
                              size="sm"
                              variant="outline"
                              className="text-emerald-600 hover:text-emerald-700 hover:bg-emerald-50"
                              onClick={() => setReactivateTarget(p)}
                            >
                              <Power className="h-3 w-3 mr-1" />Reactivar
                            </Button>
                          )}
                        </div>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {/* Modal: Crear provision */}
      <Dialog open={showCreate} onOpenChange={setShowCreate}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Nueva Provision</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Nombre *</Label>
              <Input value={newName} onChange={(e) => setNewName(e.target.value)} placeholder="Ej: Provision Vacaciones" />
            </div>
          </div>
          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={() => setShowCreate(false)}>Cancelar</Button>
            <Button
              onClick={() => createTP.mutate({ name: newName, category_ids: provisionCategoryId ? [provisionCategoryId] : [] })}
              disabled={!newName.trim() || createTP.isPending}
              className="bg-emerald-600 hover:bg-emerald-700"
            >
              {createTP.isPending ? "Creando..." : "Crear Provision"}
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      <ConfirmDialog
        open={!!deactivateTarget}
        onOpenChange={(open) => { if (!open) setDeactivateTarget(null); }}
        title="Desactivar tercero"
        description={`¿Desactivar "${deactivateTarget?.name}"? No aparecerá en selectores.`}
        confirmLabel="Desactivar"
        variant="destructive"
        loading={deactivateMutation.isPending}
        onConfirm={() => {
          if (deactivateTarget) {
            deactivateMutation.mutate(deactivateTarget.id, {
              onSuccess: () => setDeactivateTarget(null),
            });
          }
        }}
      />

      <ConfirmDialog
        open={!!reactivateTarget}
        onOpenChange={(open) => { if (!open) setReactivateTarget(null); }}
        title="Reactivar tercero"
        description={`¿Reactivar "${reactivateTarget?.name}"?`}
        confirmLabel="Reactivar"
        variant="default"
        loading={reactivateMutation.isPending}
        onConfirm={() => {
          if (reactivateTarget) {
            reactivateMutation.mutate(reactivateTarget.id, {
              onSuccess: () => setReactivateTarget(null),
            });
          }
        }}
      />
    </div>
  );
}
