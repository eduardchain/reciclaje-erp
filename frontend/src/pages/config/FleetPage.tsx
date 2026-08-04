import { useState } from "react";
import { Plus } from "lucide-react";
import { usePermissions } from "@/hooks/usePermissions";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { EmptyState } from "@/components/shared/EmptyState";
import {
  useCreateDriver,
  useCreateVehicle,
  useDrivers,
  useUpdateDriver,
  useUpdateVehicle,
  useVehicles,
} from "@/hooks/useSacConfig";
import ConfigLayout from "./ConfigLayout";
import {
  VEHICLE_TYPE_LABELS,
  type DriverResponse,
  type VehicleResponse,
  type VehicleType,
} from "@/types/sac-config";

export default function FleetPage() {
  const { hasPermission } = usePermissions();
  const canManage = hasPermission("config.manage_fleet");
  const [tab, setTab] = useState<"drivers" | "vehicles">("drivers");
  const [showInactive, setShowInactive] = useState(false);

  const drivers = useDrivers(showInactive);
  const vehicles = useVehicles(showInactive);
  const createDriver = useCreateDriver();
  const updateDriver = useUpdateDriver();
  const createVehicle = useCreateVehicle();
  const updateVehicle = useUpdateVehicle();

  // --- Dialog conductor ---
  const [driverDialog, setDriverDialog] = useState(false);
  const [editDriver, setEditDriver] = useState<DriverResponse | null>(null);
  const [dName, setDName] = useState("");
  const [dDocument, setDDocument] = useState("");
  const [dPhone, setDPhone] = useState("");

  const openDriverDialog = (item: DriverResponse | null) => {
    setEditDriver(item);
    setDName(item?.name ?? "");
    setDDocument(item?.document_id ?? "");
    setDPhone(item?.phone ?? "");
    setDriverDialog(true);
  };

  const submitDriver = () => {
    const payload = { name: dName, document_id: dDocument || null, phone: dPhone || null };
    const opts = { onSuccess: () => setDriverDialog(false) };
    if (editDriver) updateDriver.mutate({ id: editDriver.id, data: payload }, opts);
    else createDriver.mutate(payload, opts);
  };

  // --- Dialog vehiculo ---
  const [vehicleDialog, setVehicleDialog] = useState(false);
  const [editVehicle, setEditVehicle] = useState<VehicleResponse | null>(null);
  const [vPlate, setVPlate] = useState("");
  const [vDisplay, setVDisplay] = useState("");
  const [vType, setVType] = useState<string>("none");

  const openVehicleDialog = (item: VehicleResponse | null) => {
    setEditVehicle(item);
    setVPlate(item?.plate ?? "");
    setVDisplay(item?.display_name ?? "");
    setVType(item?.vehicle_type ?? "none");
    setVehicleDialog(true);
  };

  const submitVehicle = () => {
    const payload = {
      plate: vPlate,
      display_name: vDisplay || null,
      vehicle_type: vType === "none" ? null : (vType as VehicleType),
    };
    const opts = { onSuccess: () => setVehicleDialog(false) };
    if (editVehicle) updateVehicle.mutate({ id: editVehicle.id, data: payload }, opts);
    else createVehicle.mutate(payload, opts);
  };

  const driverItems = drivers.data?.items ?? [];
  const vehicleItems = vehicles.data?.items ?? [];

  return (
    <ConfigLayout>
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
        <Tabs value={tab} onValueChange={(v) => setTab(v as "drivers" | "vehicles")}>
          <TabsList>
            <TabsTrigger value="drivers">Conductores</TabsTrigger>
            <TabsTrigger value="vehicles">Vehiculos</TabsTrigger>
          </TabsList>
        </Tabs>
        <div className="flex flex-col sm:flex-row gap-2 sm:items-center">
          <label className="flex items-center gap-2 text-sm text-slate-500">
            <Switch checked={showInactive} onCheckedChange={setShowInactive} />
            Mostrar inactivos
          </label>
          {canManage && (
            <Button
              onClick={() => (tab === "drivers" ? openDriverDialog(null) : openVehicleDialog(null))}
              className="bg-emerald-600 hover:bg-emerald-700 w-full sm:w-auto"
            >
              <Plus className="h-4 w-4 mr-2" />
              {tab === "drivers" ? "Nuevo Conductor" : "Nuevo Vehiculo"}
            </Button>
          )}
        </div>
      </div>

      {tab === "drivers" &&
        (!drivers.isLoading && driverItems.length === 0 ? (
          <EmptyState title="Sin conductores" description="Crea el primer conductor." />
        ) : (
          <div className="overflow-x-auto -mx-3 sm:mx-0 rounded-lg border bg-white">
            <Table className="min-w-[560px]">
              <TableHeader>
                <TableRow>
                  <TableHead>Nombre</TableHead>
                  <TableHead>Documento</TableHead>
                  <TableHead>Telefono</TableHead>
                  <TableHead>Activo</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {driverItems.map((d) => (
                  <TableRow
                    key={d.id}
                    className={canManage ? "cursor-pointer hover:bg-slate-50" : undefined}
                    onClick={canManage ? () => openDriverDialog(d) : undefined}
                  >
                    <TableCell className="font-medium">{d.name}</TableCell>
                    <TableCell className="text-slate-500">{d.document_id ?? "—"}</TableCell>
                    <TableCell className="text-slate-500">{d.phone ?? "—"}</TableCell>
                    <TableCell onClick={(e) => e.stopPropagation()}>
                      <Switch
                        checked={d.is_active}
                        disabled={!canManage || updateDriver.isPending}
                        onCheckedChange={(checked) =>
                          updateDriver.mutate({ id: d.id, data: { is_active: checked } })
                        }
                      />
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        ))}

      {tab === "vehicles" &&
        (!vehicles.isLoading && vehicleItems.length === 0 ? (
          <EmptyState title="Sin vehiculos" description="Crea el primer vehiculo." />
        ) : (
          <div className="overflow-x-auto -mx-3 sm:mx-0 rounded-lg border bg-white">
            <Table className="min-w-[560px]">
              <TableHeader>
                <TableRow>
                  <TableHead>Placa</TableHead>
                  <TableHead>Nombre</TableHead>
                  <TableHead>Tipo</TableHead>
                  <TableHead>Activo</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {vehicleItems.map((v) => (
                  <TableRow
                    key={v.id}
                    className={canManage ? "cursor-pointer hover:bg-slate-50" : undefined}
                    onClick={canManage ? () => openVehicleDialog(v) : undefined}
                  >
                    <TableCell className="font-medium uppercase">{v.plate}</TableCell>
                    <TableCell className="text-slate-500">{v.display_name ?? "—"}</TableCell>
                    <TableCell className="text-slate-500">
                      {v.vehicle_type ? VEHICLE_TYPE_LABELS[v.vehicle_type] : "—"}
                    </TableCell>
                    <TableCell onClick={(e) => e.stopPropagation()}>
                      <Switch
                        checked={v.is_active}
                        disabled={!canManage || updateVehicle.isPending}
                        onCheckedChange={(checked) =>
                          updateVehicle.mutate({ id: v.id, data: { is_active: checked } })
                        }
                      />
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        ))}

      {/* Dialog conductor */}
      <Dialog open={driverDialog} onOpenChange={setDriverDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{editDriver ? "Editar Conductor" : "Nuevo Conductor"}</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Nombre *</Label>
              <Input value={dName} onChange={(e) => setDName(e.target.value)} maxLength={150} />
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Documento</Label>
                <Input value={dDocument} onChange={(e) => setDDocument(e.target.value)} maxLength={30} />
              </div>
              <div>
                <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Telefono</Label>
                <Input value={dPhone} onChange={(e) => setDPhone(e.target.value)} maxLength={30} inputMode="tel" />
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDriverDialog(false)} className="w-full sm:w-auto">Cancelar</Button>
            <Button
              onClick={submitDriver}
              disabled={!dName.trim() || createDriver.isPending || updateDriver.isPending}
              className="bg-emerald-600 hover:bg-emerald-700 w-full sm:w-auto"
            >
              {createDriver.isPending || updateDriver.isPending
                ? "Guardando..."
                : editDriver ? "Actualizar" : "Crear"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Dialog vehiculo */}
      <Dialog open={vehicleDialog} onOpenChange={setVehicleDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{editVehicle ? "Editar Vehiculo" : "Nuevo Vehiculo"}</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Placa *</Label>
                <Input
                  value={vPlate}
                  onChange={(e) => setVPlate(e.target.value.toUpperCase())}
                  maxLength={15}
                  placeholder="ABC123"
                />
              </div>
              <div>
                <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Tipo</Label>
                <Select value={vType} onValueChange={setVType}>
                  <SelectTrigger className="w-full"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="none">Sin tipo</SelectItem>
                    {(Object.keys(VEHICLE_TYPE_LABELS) as VehicleType[]).map((t) => (
                      <SelectItem key={t} value={t}>{VEHICLE_TYPE_LABELS[t]}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Nombre visible</Label>
              <Input
                value={vDisplay}
                onChange={(e) => setVDisplay(e.target.value)}
                maxLength={120}
                placeholder="Ej: Camion grande"
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setVehicleDialog(false)} className="w-full sm:w-auto">Cancelar</Button>
            <Button
              onClick={submitVehicle}
              disabled={!vPlate.trim() || createVehicle.isPending || updateVehicle.isPending}
              className="bg-emerald-600 hover:bg-emerald-700 w-full sm:w-auto"
            >
              {createVehicle.isPending || updateVehicle.isPending
                ? "Guardando..."
                : editVehicle ? "Actualizar" : "Crear"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </ConfigLayout>
  );
}
