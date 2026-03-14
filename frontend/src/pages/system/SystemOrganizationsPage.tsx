import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Building2, Plus, MoreHorizontal, Power, Pencil, Users } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { PageHeader } from "@/components/shared/PageHeader";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  useSystemOrganizations,
  useCreateOrganization,
  useUpdateOrganization,
  useDeleteOrganization,
} from "@/hooks/useSystem";
import { formatDate } from "@/utils/formatters";
import type { SystemOrgResponse } from "@/types/organization";

const planBadgeColors: Record<string, string> = {
  basic: "bg-slate-100 text-slate-600",
  professional: "bg-blue-100 text-blue-700",
  enterprise: "bg-purple-100 text-purple-700",
};

export default function SystemOrganizationsPage() {
  const navigate = useNavigate();
  const { data: orgs, isLoading } = useSystemOrganizations(true);
  const createOrg = useCreateOrganization();
  const updateOrg = useUpdateOrganization();
  const deleteOrg = useDeleteOrganization();

  // Crear org
  const [showCreate, setShowCreate] = useState(false);
  const [newName, setNewName] = useState("");
  const [newAdminEmail, setNewAdminEmail] = useState("");
  const [newAdminName, setNewAdminName] = useState("");

  // Editar org
  const [editOrg, setEditOrg] = useState<SystemOrgResponse | null>(null);
  const [editName, setEditName] = useState("");
  const [editMaxUsers, setEditMaxUsers] = useState("");
  const [editPlan, setEditPlan] = useState("");

  // Desactivar org
  const [deactivateTarget, setDeactivateTarget] = useState<SystemOrgResponse | null>(null);
  const [confirmName, setConfirmName] = useState("");

  const handleCreate = () => {
    if (!newName || !newAdminEmail) return;
    createOrg.mutate(
      {
        name: newName,
        admin_email: newAdminEmail,
        admin_full_name: newAdminName || undefined,
      },
      {
        onSuccess: () => {
          setShowCreate(false);
          setNewName("");
          setNewAdminEmail("");
          setNewAdminName("");
        },
      },
    );
  };

  const openEdit = (org: SystemOrgResponse) => {
    setEditOrg(org);
    setEditName(org.name);
    setEditMaxUsers(String(org.max_users));
    setEditPlan(org.subscription_plan);
  };

  const handleEdit = () => {
    if (!editOrg) return;
    updateOrg.mutate(
      {
        id: editOrg.id,
        data: {
          name: editName !== editOrg.name ? editName : undefined,
          max_users: Number(editMaxUsers) !== editOrg.max_users ? Number(editMaxUsers) : undefined,
          subscription_plan: editPlan !== editOrg.subscription_plan ? editPlan : undefined,
        },
      },
      { onSuccess: () => setEditOrg(null) },
    );
  };

  const handleDeactivate = () => {
    if (!deactivateTarget) return;
    deleteOrg.mutate(deactivateTarget.id, {
      onSuccess: () => {
        setDeactivateTarget(null);
        setConfirmName("");
      },
    });
  };

  return (
    <div className="space-y-6">
      <PageHeader title="Organizaciones" description="Gestionar todas las organizaciones del sistema">
        <Button onClick={() => setShowCreate(true)} className="bg-emerald-600 hover:bg-emerald-700">
          <Plus className="h-4 w-4 mr-1.5" />
          Nueva Organizacion
        </Button>
      </PageHeader>

      {isLoading ? (
        <div className="space-y-2">
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} className="h-12 w-full rounded-lg" />
          ))}
        </div>
      ) : (
        <div className="rounded-lg border border-slate-200/80 overflow-hidden">
          <Table>
            <TableHeader>
              <TableRow className="bg-slate-50/80 border-b border-slate-200/80">
                <TableHead className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 h-10">Organizacion</TableHead>
                <TableHead className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 h-10">Slug</TableHead>
                <TableHead className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 h-10">Plan</TableHead>
                <TableHead className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 h-10 text-center">Miembros</TableHead>
                <TableHead className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 h-10 text-center">Max</TableHead>
                <TableHead className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 h-10 text-center">Estado</TableHead>
                <TableHead className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 h-10">Creada</TableHead>
                <TableHead className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 h-10 text-right">Acciones</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {orgs?.map((org) => (
                <TableRow key={org.id} className={!org.is_active ? "opacity-50" : ""}>
                  <TableCell>
                    <div className="flex items-center gap-2">
                      <Building2 className="h-4 w-4 text-slate-400" />
                      <span className="font-medium">{org.name}</span>
                    </div>
                  </TableCell>
                  <TableCell>
                    <code className="text-xs text-slate-500 bg-slate-100 px-1.5 py-0.5 rounded">{org.slug}</code>
                  </TableCell>
                  <TableCell>
                    <Badge variant="secondary" className={planBadgeColors[org.subscription_plan] ?? "bg-slate-100 text-slate-600"}>
                      {org.subscription_plan}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-center tabular-nums">
                    <button
                      onClick={() => navigate(`/system/users?org=${org.id}&org_name=${encodeURIComponent(org.name)}`)}
                      className="inline-flex items-center gap-1 hover:text-emerald-600 hover:underline cursor-pointer"
                      title="Ver usuarios de esta organizacion"
                    >
                      {org.member_count}
                      <Users className="h-3 w-3" />
                    </button>
                  </TableCell>
                  <TableCell className="text-center tabular-nums">{org.max_users}</TableCell>
                  <TableCell className="text-center">
                    <Badge variant="secondary" className={org.is_active ? "bg-emerald-100 text-emerald-700" : "bg-red-100 text-red-700"}>
                      {org.is_active ? "Activa" : "Inactiva"}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-sm text-slate-500">{formatDate(org.created_at)}</TableCell>
                  <TableCell className="text-right">
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button variant="ghost" size="sm" className="h-8 w-8 p-0">
                          <MoreHorizontal className="h-4 w-4" />
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end">
                        <DropdownMenuItem onClick={() => openEdit(org)}>
                          <Pencil className="h-4 w-4 mr-2" />
                          Editar
                        </DropdownMenuItem>
                        {org.is_active && (
                          <DropdownMenuItem
                            onClick={() => setDeactivateTarget(org)}
                            className="text-red-600 focus:text-red-600"
                          >
                            <Power className="h-4 w-4 mr-2" />
                            Desactivar
                          </DropdownMenuItem>
                        )}
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </TableCell>
                </TableRow>
              ))}
              {orgs?.length === 0 && (
                <TableRow>
                  <TableCell colSpan={8} className="text-center text-slate-400 py-8">
                    No hay organizaciones
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </div>
      )}

      {/* Dialog: Crear Organizacion */}
      <Dialog open={showCreate} onOpenChange={setShowCreate}>
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle>Nueva Organizacion</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Nombre *</Label>
              <Input
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                placeholder="Ej: Reciclajes del Norte"
                className="mt-1"
              />
            </div>
            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Email del Administrador *</Label>
              <Input
                type="email"
                value={newAdminEmail}
                onChange={(e) => setNewAdminEmail(e.target.value)}
                placeholder="admin@empresa.com"
                className="mt-1"
              />
              <p className="text-[11px] text-slate-400 mt-1">Si el email no existe, se creara un nuevo usuario.</p>
            </div>
            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Nombre del Admin (solo si es nuevo)</Label>
              <Input
                value={newAdminName}
                onChange={(e) => setNewAdminName(e.target.value)}
                placeholder="Nombre completo"
                className="mt-1"
              />
            </div>
            <p className="text-xs text-slate-400">Si se crea un usuario nuevo, la contraseña sera: <strong>123456</strong></p>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowCreate(false)}>Cancelar</Button>
            <Button
              onClick={handleCreate}
              disabled={!newName.trim() || !newAdminEmail.trim() || createOrg.isPending}
              className="bg-emerald-600 hover:bg-emerald-700"
            >
              {createOrg.isPending ? "Creando..." : "Crear Organizacion"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Dialog: Editar Organizacion */}
      <Dialog open={!!editOrg} onOpenChange={(open) => !open && setEditOrg(null)}>
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle>Editar Organizacion</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Nombre</Label>
              <Input
                value={editName}
                onChange={(e) => setEditName(e.target.value)}
                className="mt-1"
              />
            </div>
            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Max Usuarios</Label>
              <Input
                type="number"
                value={editMaxUsers}
                onChange={(e) => setEditMaxUsers(e.target.value)}
                className="mt-1"
                min={1}
              />
            </div>
            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Plan</Label>
              <Select value={editPlan} onValueChange={setEditPlan}>
                <SelectTrigger className="mt-1">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="basic">Basic</SelectItem>
                  <SelectItem value="professional">Professional</SelectItem>
                  <SelectItem value="enterprise">Enterprise</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setEditOrg(null)}>Cancelar</Button>
            <Button
              onClick={handleEdit}
              disabled={updateOrg.isPending}
              className="bg-emerald-600 hover:bg-emerald-700"
            >
              {updateOrg.isPending ? "Guardando..." : "Guardar"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Dialog: Desactivar Organizacion (requiere escribir nombre) */}
      <Dialog open={!!deactivateTarget} onOpenChange={(open) => { if (!open) { setDeactivateTarget(null); setConfirmName(""); } }}>
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle>Desactivar Organizacion</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <p className="text-sm text-slate-600">
              Esta accion desactivara <strong>"{deactivateTarget?.name}"</strong> y todos sus datos dejaran de ser accesibles.
              Los usuarios que solo pertenezcan a esta organizacion seran desactivados.
            </p>
            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                Escriba "{deactivateTarget?.name}" para confirmar
              </Label>
              <Input
                value={confirmName}
                onChange={(e) => setConfirmName(e.target.value)}
                placeholder="Nombre de la organizacion"
                className="mt-1"
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => { setDeactivateTarget(null); setConfirmName(""); }}>Cancelar</Button>
            <Button
              variant="destructive"
              onClick={handleDeactivate}
              disabled={confirmName !== deactivateTarget?.name || deleteOrg.isPending}
            >
              {deleteOrg.isPending ? "Desactivando..." : "Desactivar"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
