import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Plus, Receipt, Power, PowerOff } from "lucide-react";
import { usePermissions } from "@/hooks/usePermissions";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { PageHeader } from "@/components/shared/PageHeader";
import { SearchInput } from "@/components/shared/SearchInput";
import { EntitySelect } from "@/components/shared/EntitySelect";
import { MoneyInput } from "@/components/shared/MoneyInput";
import { MoneyDisplay } from "@/components/shared/MoneyDisplay";
import { BusinessUnitAllocationSelector } from "@/components/shared/BusinessUnitAllocationSelector";
import { EmptyState } from "@/components/shared/EmptyState";
import { ConfirmDialog } from "@/components/shared/ConfirmDialog";
import { useLiabilities, useExpenseCategoriesFlat, useThirdPartyCategoriesFlat } from "@/hooks/useMasterData";
import { useDeactivateThirdParty, useReactivateThirdParty } from "@/hooks/useCrudData";
import { useCreateMovement } from "@/hooks/useMoneyMovements";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { thirdPartyService } from "@/services/thirdParties";
import { getApiErrorMessage, toLocalDateInput } from "@/utils/formatters";
import { ROUTES } from "@/utils/constants";
import type { ThirdPartyCreate } from "@/types/third-party";
import type { ThirdPartyResponse } from "@/types/third-party";

export default function LiabilitiesPage() {
  const navigate = useNavigate();
  const { hasPermission } = usePermissions();
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const [showInactive, setShowInactive] = useState(false);
  const { data: liabilitiesData, isLoading } = useLiabilities(search || undefined, showInactive ? undefined : true);
  const items = liabilitiesData?.items ?? [];
  const { data: liabilityCatsData } = useThirdPartyCategoriesFlat("liability");
  const liabilityCategories = liabilityCatsData?.items ?? [];
  const liabilityCategoryId = liabilityCategories.length > 0 ? liabilityCategories[0].id : null;

  const canDelete = hasPermission("third_parties.delete");
  const deactivateMutation = useDeactivateThirdParty();
  const reactivateMutation = useReactivateThirdParty();
  const [deactivateTarget, setDeactivateTarget] = useState<ThirdPartyResponse | null>(null);
  const [reactivateTarget, setReactivateTarget] = useState<ThirdPartyResponse | null>(null);

  // Modal crear pasivo
  const [showCreate, setShowCreate] = useState(false);
  const [newName, setNewName] = useState("");
  const [newIdNumber, setNewIdNumber] = useState("");
  const [newPhone, setNewPhone] = useState("");
  const createTP = useMutation({
    mutationFn: (data: ThirdPartyCreate) => thirdPartyService.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["third-parties"] });
      toast.success("Pasivo creado exitosamente");
      setShowCreate(false);
      setNewName("");
      setNewIdNumber("");
      setNewPhone("");
    },
    onError: (error: unknown) => {
      toast.error(getApiErrorMessage(error, "Error al crear el pasivo"));
    },
  });

  // Modal causar gasto
  const [showAccrue, setShowAccrue] = useState(false);
  const [accrueTPId, setAccrueTPId] = useState("");
  const [accrueTPName, setAccrueTPName] = useState("");
  const [accrueAmount, setAccrueAmount] = useState(0);
  const [accrueCategoryId, setAccrueCategoryId] = useState("");
  const handleAccrueCategoryChange = (catId: string) => {
    setAccrueCategoryId(catId);
    const cat = categories.find((c) => c.id === catId);
    if (cat) {
      if (cat.default_business_unit_id) {
        setAccrueBuType("direct");
        setAccrueBuDirectId(cat.default_business_unit_id);
        setAccrueBuSharedIds([]);
      } else if (cat.default_applicable_business_unit_ids?.length) {
        setAccrueBuType("shared");
        setAccrueBuDirectId("");
        setAccrueBuSharedIds(cat.default_applicable_business_unit_ids);
      } else {
        setAccrueBuType("general");
        setAccrueBuDirectId("");
        setAccrueBuSharedIds([]);
      }
    }
  };
  const [accrueDescription, setAccrueDescription] = useState("");
  const [accrueDate, setAccrueDate] = useState(toLocalDateInput());
  const [accrueBuType, setAccrueBuType] = useState<"direct" | "shared" | "general">("general");
  const [accrueBuDirectId, setAccrueBuDirectId] = useState("");
  const [accrueBuSharedIds, setAccrueBuSharedIds] = useState<string[]>([]);
  const { data: categoriesData } = useExpenseCategoriesFlat();
  const categories = categoriesData?.items ?? [];
  const createAccrual = useCreateMovement("expense_accrual");

  const openAccrue = (tpId: string, tpName: string) => {
    setAccrueTPId(tpId);
    setAccrueTPName(tpName);
    setAccrueAmount(0);
    setAccrueCategoryId("");
    setAccrueDescription("");
    setAccrueDate(toLocalDateInput());
    setAccrueBuType("general");
    setAccrueBuDirectId("");
    setAccrueBuSharedIds([]);
    setShowAccrue(true);
  };

  const handleAccrue = () => {
    createAccrual.mutate(
      {
        third_party_id: accrueTPId,
        amount: accrueAmount,
        expense_category_id: accrueCategoryId,
        date: accrueDate,
        description: accrueDescription,
        ...(accrueBuType === "direct" && accrueBuDirectId ? { business_unit_id: accrueBuDirectId } : {}),
        ...(accrueBuType === "shared" && accrueBuSharedIds.length > 0 ? { applicable_business_unit_ids: accrueBuSharedIds } : {}),
      },
      { onSuccess: () => setShowAccrue(false) },
    );
  };

  return (
    <div className="space-y-6">
      <PageHeader title="Pasivos" description="Obligaciones laborales, prestaciones y otros pasivos">
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => navigate(ROUTES.TREASURY)}>
            Volver a Tesoreria
          </Button>
          {hasPermission("treasury.create_movements") && (
            <Button onClick={() => setShowCreate(true)} className="bg-emerald-600 hover:bg-emerald-700" disabled={!liabilityCategoryId} title={!liabilityCategoryId ? "Configure categoria Pasivo primero" : undefined}>
              <Plus className="h-4 w-4 mr-2" />Nuevo Pasivo
            </Button>
          )}
        </div>
      </PageHeader>

      <div className="flex gap-3 items-center">
        <SearchInput value={search} onChange={setSearch} placeholder="Buscar pasivo..." />
        <div className="flex items-center gap-2">
          <Checkbox
            id="show-inactive-liabilities"
            checked={showInactive}
            onCheckedChange={(checked) => setShowInactive(checked === true)}
          />
          <label htmlFor="show-inactive-liabilities" className="text-sm text-slate-600 cursor-pointer whitespace-nowrap">
            Mostrar inactivos
          </label>
        </div>
      </div>

      <Card className="shadow-sm">
        <CardContent className="p-0">
          {isLoading ? (
            <p className="text-sm text-slate-400 py-8 text-center">Cargando...</p>
          ) : items.length === 0 ? (
            <div className="p-6">
              <EmptyState
                title="Sin pasivos registrados"
                description="Crea un pasivo para registrar obligaciones laborales u otras deudas."
              />
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Nombre</TableHead>
                  <TableHead className="text-right">Saldo Contable</TableHead>
                  <TableHead className="text-right">Acciones</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {items.map((tp) => (
                  <TableRow key={tp.id}>
                    <TableCell className={`font-medium ${!tp.is_active ? "opacity-50" : ""}`}>
                      <div className="flex items-center gap-2">
                        {tp.name}
                        {!tp.is_active && <Badge variant="secondary" className="text-xs">Inactivo</Badge>}
                      </div>
                    </TableCell>
                    <TableCell className={`text-right ${!tp.is_active ? "opacity-50" : ""}`}>
                      <MoneyDisplay amount={tp.current_balance} />
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex justify-end gap-2">
                        {hasPermission("treasury.create_movements") && tp.is_active && (
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => openAccrue(tp.id, tp.name)}
                          >
                            <Receipt className="h-3.5 w-3.5 mr-1" />Causar
                          </Button>
                        )}
                        {hasPermission("treasury.create_movements") && tp.is_active && (
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => navigate(`${ROUTES.TREASURY_NEW}?type=liability_payment&third_party_id=${tp.id}`)}
                          >
                            Pagar
                          </Button>
                        )}
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => navigate(`${ROUTES.TREASURY_ACCOUNT_STATEMENT}?third_party_id=${tp.id}&returnTo=/treasury/liabilities`)}
                        >
                          Estado de Cuenta
                        </Button>
                        {canDelete && tp.is_active && (
                          <Button
                            variant="outline"
                            size="sm"
                            className="text-red-600 hover:text-red-700 hover:bg-red-50"
                            onClick={() => setDeactivateTarget(tp)}
                          >
                            <PowerOff className="h-3 w-3 mr-1" />Desactivar
                          </Button>
                        )}
                        {canDelete && !tp.is_active && (
                          <Button
                            variant="outline"
                            size="sm"
                            className="text-emerald-600 hover:text-emerald-700 hover:bg-emerald-50"
                            onClick={() => setReactivateTarget(tp)}
                          >
                            <Power className="h-3 w-3 mr-1" />Reactivar
                          </Button>
                        )}
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {/* Modal: Crear pasivo */}
      <Dialog open={showCreate} onOpenChange={setShowCreate}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Nuevo Pasivo</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Nombre *</Label>
              <Input value={newName} onChange={(e) => setNewName(e.target.value)} placeholder="Ej: Prestaciones Juan Perez" />
            </div>
            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Identificacion</Label>
              <Input value={newIdNumber} onChange={(e) => setNewIdNumber(e.target.value)} placeholder="Cedula o NIT (opcional)" />
            </div>
            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Telefono</Label>
              <Input value={newPhone} onChange={(e) => setNewPhone(e.target.value)} placeholder="Telefono (opcional)" />
            </div>
          </div>
          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={() => setShowCreate(false)}>Cancelar</Button>
            <Button
              onClick={() => createTP.mutate({
                name: newName,
                category_ids: liabilityCategoryId ? [liabilityCategoryId] : [],
                identification_number: newIdNumber || undefined,
                phone: newPhone || undefined,
              })}
              disabled={!newName.trim() || createTP.isPending}
              className="bg-emerald-600 hover:bg-emerald-700"
            >
              {createTP.isPending ? "Creando..." : "Crear Pasivo"}
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Modal: Causar gasto */}
      <Dialog open={showAccrue} onOpenChange={setShowAccrue}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Causar Gasto — {accrueTPName}</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Monto *</Label>
              <MoneyInput value={accrueAmount} onChange={setAccrueAmount} placeholder="0" />
            </div>
            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Categoria de Gasto *</Label>
              <EntitySelect
                value={accrueCategoryId}
                onChange={handleAccrueCategoryChange}
                options={categories.map((c) => ({ id: c.id, label: c.display_name }))}
                placeholder="Seleccionar categoria..."
              />
            </div>
            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Fecha *</Label>
              <Input type="date" value={accrueDate} onChange={(e) => setAccrueDate(e.target.value)} />
            </div>
            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Descripcion *</Label>
              <Input value={accrueDescription} onChange={(e) => setAccrueDescription(e.target.value)} placeholder="Descripcion del gasto causado" />
            </div>
            <BusinessUnitAllocationSelector
              businessUnitId={accrueBuDirectId}
              setBusinessUnitId={setAccrueBuDirectId}
              applicableBusinessUnitIds={accrueBuSharedIds}
              setApplicableBusinessUnitIds={setAccrueBuSharedIds}
              allocationType={accrueBuType}
              setAllocationType={setAccrueBuType}
            />
          </div>
          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={() => setShowAccrue(false)}>Cancelar</Button>
            <Button
              onClick={handleAccrue}
              disabled={accrueAmount <= 0 || !accrueCategoryId || !accrueDescription.trim() || createAccrual.isPending}
              className="bg-emerald-600 hover:bg-emerald-700"
            >
              {createAccrual.isPending ? "Causando..." : "Causar Gasto"}
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
