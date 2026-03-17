import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Plus, Receipt } from "lucide-react";
import { usePermissions } from "@/hooks/usePermissions";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { PageHeader } from "@/components/shared/PageHeader";
import { SearchInput } from "@/components/shared/SearchInput";
import { EntitySelect } from "@/components/shared/EntitySelect";
import { MoneyInput } from "@/components/shared/MoneyInput";
import { MoneyDisplay } from "@/components/shared/MoneyDisplay";
import { EmptyState } from "@/components/shared/EmptyState";
import { useLiabilities, useExpenseCategoriesFlat, useThirdPartyCategoriesFlat } from "@/hooks/useMasterData";
import { useCreateMovement } from "@/hooks/useMoneyMovements";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { thirdPartyService } from "@/services/thirdParties";
import { getApiErrorMessage, toLocalDateInput } from "@/utils/formatters";
import { ROUTES } from "@/utils/constants";
import type { ThirdPartyCreate } from "@/types/third-party";

export default function LiabilitiesPage() {
  const navigate = useNavigate();
  const { hasPermission } = usePermissions();
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const { data: liabilitiesData, isLoading } = useLiabilities(search || undefined);
  const items = liabilitiesData?.items ?? [];
  const { data: serviceCatsData } = useThirdPartyCategoriesFlat("service_provider");
  const serviceCategories = serviceCatsData?.items ?? [];
  const serviceCategoryId = serviceCategories.length > 0 ? serviceCategories[0].id : null;

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
  const [accrueDescription, setAccrueDescription] = useState("");
  const [accrueDate, setAccrueDate] = useState(toLocalDateInput());
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
            <Button onClick={() => setShowCreate(true)} className="bg-emerald-600 hover:bg-emerald-700" disabled={!serviceCategoryId} title={!serviceCategoryId ? "Configure categorias de Proveedor Servicios primero" : undefined}>
              <Plus className="h-4 w-4 mr-2" />Nuevo Pasivo
            </Button>
          )}
        </div>
      </PageHeader>

      <div className="flex gap-3 items-center">
        <SearchInput value={search} onChange={setSearch} placeholder="Buscar pasivo..." />
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
                    <TableCell className="font-medium">{tp.name}</TableCell>
                    <TableCell className="text-right">
                      <MoneyDisplay amount={tp.current_balance} />
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex justify-end gap-2">
                        {hasPermission("treasury.create_movements") && (
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => openAccrue(tp.id, tp.name)}
                          >
                            <Receipt className="h-3.5 w-3.5 mr-1" />Causar
                          </Button>
                        )}
                        {hasPermission("treasury.create_movements") && (
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
                          onClick={() => navigate(`${ROUTES.TREASURY_ACCOUNT_STATEMENT}?third_party_id=${tp.id}`)}
                        >
                          Estado de Cuenta
                        </Button>
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
                category_ids: serviceCategoryId ? [serviceCategoryId] : [],
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
                onChange={setAccrueCategoryId}
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
    </div>
  );
}
