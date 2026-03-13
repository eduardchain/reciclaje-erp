import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Plus, ShieldCheck, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { PageHeader } from "@/components/shared/PageHeader";
import { ConfirmDialog } from "@/components/shared/ConfirmDialog";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Skeleton } from "@/components/ui/skeleton";
import { useRoles, useCreateRole, useDeleteRole } from "@/hooks/useRoles";

export default function RolesPage() {
  const navigate = useNavigate();
  const { data: roles, isLoading } = useRoles();
  const createRole = useCreateRole();
  const deleteRole = useDeleteRole();

  const [showCreate, setShowCreate] = useState(false);
  const [name, setName] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [description, setDescription] = useState("");

  const [deleteTarget, setDeleteTarget] = useState<{ id: string; name: string } | null>(null);

  const handleCreate = () => {
    createRole.mutate(
      { name, display_name: displayName, description: description || undefined, permission_codes: [] },
      {
        onSuccess: (role) => {
          setShowCreate(false);
          setName("");
          setDisplayName("");
          setDescription("");
          navigate(`/admin/roles/${role.id}`);
        },
      },
    );
  };

  const handleDelete = () => {
    if (!deleteTarget) return;
    deleteRole.mutate(deleteTarget.id, {
      onSuccess: () => setDeleteTarget(null),
    });
  };

  return (
    <div className="space-y-6">
      <PageHeader title="Roles" description="Gestionar roles y permisos de la organizacion">
        <Button onClick={() => setShowCreate(true)} className="bg-emerald-600 hover:bg-emerald-700">
          <Plus className="h-4 w-4 mr-2" />
          Nuevo Rol
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
                <TableHead className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 h-10">Rol</TableHead>
                <TableHead className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 h-10">Identificador</TableHead>
                <TableHead className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 h-10 text-center">Permisos</TableHead>
                <TableHead className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 h-10 text-center">Usuarios</TableHead>
                <TableHead className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 h-10 text-right">Acciones</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {roles?.map((role) => (
                <TableRow
                  key={role.id}
                  className="cursor-pointer hover:bg-slate-50"
                  onClick={() => navigate(`/admin/roles/${role.id}`)}
                >
                  <TableCell>
                    <div className="flex items-center gap-2">
                      <ShieldCheck className="h-4 w-4 text-slate-400" />
                      <span className="font-medium">{role.display_name}</span>
                      {role.is_system_role && (
                        <Badge variant="secondary" className="bg-blue-100 text-blue-700 text-[10px]">Sistema</Badge>
                      )}
                    </div>
                  </TableCell>
                  <TableCell>
                    <code className="text-xs text-slate-500 bg-slate-100 px-1.5 py-0.5 rounded">{role.name}</code>
                  </TableCell>
                  <TableCell className="text-center tabular-nums">{role.permission_count}</TableCell>
                  <TableCell className="text-center tabular-nums">{role.member_count}</TableCell>
                  <TableCell className="text-right">
                    {!role.is_system_role && role.member_count === 0 && (
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-8 w-8 p-0 text-red-500 hover:text-red-700 hover:bg-red-50"
                        onClick={(e) => {
                          e.stopPropagation();
                          setDeleteTarget({ id: role.id, name: role.display_name });
                        }}
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      {/* Dialog: Crear Rol */}
      <Dialog open={showCreate} onOpenChange={setShowCreate}>
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle>Nuevo Rol</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Nombre visible *</Label>
              <Input
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                placeholder="Ej: Supervisor de Operaciones"
              />
            </div>
            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Identificador *</Label>
              <Input
                value={name}
                onChange={(e) => setName(e.target.value.toLowerCase().replace(/[^a-z0-9_-]/g, ""))}
                placeholder="Ej: supervisor"
              />
              <p className="text-[11px] text-slate-400 mt-1">Solo minusculas, numeros, guiones. Unico por organizacion.</p>
            </div>
            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Descripcion</Label>
              <Input
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Descripcion opcional del rol"
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowCreate(false)}>Cancelar</Button>
            <Button
              onClick={handleCreate}
              disabled={!name.trim() || !displayName.trim() || createRole.isPending}
              className="bg-emerald-600 hover:bg-emerald-700"
            >
              {createRole.isPending ? "Creando..." : "Crear y Asignar Permisos"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Dialog: Confirmar Eliminar */}
      <ConfirmDialog
        open={!!deleteTarget}
        onOpenChange={(open) => !open && setDeleteTarget(null)}
        title="Eliminar Rol"
        description={`Esta accion eliminara el rol "${deleteTarget?.name}". No se puede deshacer.`}
        confirmLabel="Eliminar"
        variant="destructive"
        onConfirm={handleDelete}
        loading={deleteRole.isPending}
      />
    </div>
  );
}
