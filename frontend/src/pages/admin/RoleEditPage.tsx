import { useState, useEffect, useMemo } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { ArrowLeft, Save, AlertTriangle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { PageHeader } from "@/components/shared/PageHeader";
import { useRole, usePermissionsByModule, useUpdateRole } from "@/hooks/useRoles";
import { ROUTES } from "@/utils/constants";

export default function RoleEditPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { data: role, isLoading: roleLoading } = useRole(id!);
  const { data: modules, isLoading: permsLoading } = usePermissionsByModule();
  const updateRole = useUpdateRole();

  const [displayName, setDisplayName] = useState("");
  const [description, setDescription] = useState("");
  const [selectedPerms, setSelectedPerms] = useState<Set<string>>(new Set());

  // Inicializar estado cuando cargan datos
  useEffect(() => {
    if (role) {
      setDisplayName(role.display_name);
      setDescription(role.description ?? "");
      setSelectedPerms(new Set(role.permissions.map((p) => p.code)));
    }
  }, [role]);

  const isAdminRole = role?.name === "admin";
  const adminPermsRemoved = useMemo(() => {
    if (!isAdminRole || !role) return false;
    const originalAdminPerms = role.permissions.filter((p) => p.module === "admin").map((p) => p.code);
    return originalAdminPerms.some((code) => !selectedPerms.has(code));
  }, [isAdminRole, role, selectedPerms]);

  const togglePerm = (code: string) => {
    setSelectedPerms((prev) => {
      const next = new Set(prev);
      if (next.has(code)) next.delete(code);
      else next.add(code);
      return next;
    });
  };

  const toggleModule = (moduleName: string) => {
    if (!modules) return;
    const mod = modules.find((m) => m.module === moduleName);
    if (!mod) return;
    const allSelected = mod.permissions.every((p) => selectedPerms.has(p.code));
    setSelectedPerms((prev) => {
      const next = new Set(prev);
      mod.permissions.forEach((p) => {
        if (allSelected) next.delete(p.code);
        else next.add(p.code);
      });
      return next;
    });
  };

  const handleSave = () => {
    if (!id) return;
    updateRole.mutate(
      {
        id,
        data: {
          display_name: displayName,
          description: description || undefined,
          permission_codes: Array.from(selectedPerms),
        },
      },
      { onSuccess: () => navigate(ROUTES.ADMIN_ROLES) },
    );
  };

  if (roleLoading || permsLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  if (!role) {
    return <div className="text-center py-12 text-slate-500">Rol no encontrado</div>;
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title={`Editar Rol: ${role.display_name}`}
        description={role.is_system_role ? "Rol del sistema" : "Rol personalizado"}
      >
        <div className="flex items-center gap-2">
          <Button onClick={handleSave} disabled={!displayName.trim() || updateRole.isPending} className="bg-emerald-600 hover:bg-emerald-700">
            <Save className="h-4 w-4 mr-2" />
            {updateRole.isPending ? "Guardando..." : "Guardar Cambios"}
          </Button>
          <Button variant="outline" onClick={() => navigate(ROUTES.ADMIN_ROLES)}>
            <ArrowLeft className="h-4 w-4 mr-2" />
            Volver
          </Button>
        </div>
      </PageHeader>

      {/* Info del rol */}
      <Card className="shadow-sm">
        <CardHeader>
          <CardTitle className="text-sm font-semibold uppercase tracking-wider text-slate-500">Informacion del Rol</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Nombre visible</Label>
              <Input value={displayName} onChange={(e) => setDisplayName(e.target.value)} />
            </div>
            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Identificador</Label>
              <div className="flex items-center gap-2 mt-1">
                <code className="text-sm text-slate-600 bg-slate-100 px-2 py-1.5 rounded">{role.name}</code>
                {role.is_system_role && <Badge variant="secondary" className="bg-blue-100 text-blue-700">Sistema</Badge>}
              </div>
            </div>
            <div className="md:col-span-2">
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Descripcion</Label>
              <Input value={description} onChange={(e) => setDescription(e.target.value)} placeholder="Descripcion opcional" />
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Advertencia admin */}
      {adminPermsRemoved && (
        <div className="flex items-start gap-3 p-4 bg-amber-50 border border-amber-200 rounded-lg">
          <AlertTriangle className="h-5 w-5 text-amber-600 shrink-0 mt-0.5" />
          <div>
            <p className="text-sm font-medium text-amber-800">Atencion: modificando permisos del Administrador</p>
            <p className="text-sm text-amber-700 mt-1">
              Si quitas permisos de administracion, podrias perder acceso a esta pantalla. Asegurate de saber lo que haces.
            </p>
          </div>
        </div>
      )}

      {/* Permisos por modulo */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {modules?.map((mod) => {
          const allSelected = mod.permissions.every((p) => selectedPerms.has(p.code));
          const someSelected = mod.permissions.some((p) => selectedPerms.has(p.code));
          const selectedCount = mod.permissions.filter((p) => selectedPerms.has(p.code)).length;

          return (
            <Card key={mod.module} className="shadow-sm">
              <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                  <CardTitle className="text-sm font-semibold">{mod.module_display}</CardTitle>
                  <span className="text-xs text-slate-400 tabular-nums">{selectedCount}/{mod.permissions.length}</span>
                </div>
                <div className="flex items-center gap-2 pt-1">
                  <Checkbox
                    id={`mod-${mod.module}`}
                    checked={allSelected}
                    data-indeterminate={someSelected && !allSelected}
                    onCheckedChange={() => toggleModule(mod.module)}
                  />
                  <label htmlFor={`mod-${mod.module}`} className="text-xs text-slate-500 cursor-pointer">
                    Seleccionar todo
                  </label>
                </div>
              </CardHeader>
              <CardContent className="pt-0">
                <div className="space-y-2">
                  {mod.permissions.map((perm) => (
                    <div key={perm.code} className="flex items-start gap-2">
                      <Checkbox
                        id={`perm-${perm.code}`}
                        checked={selectedPerms.has(perm.code)}
                        onCheckedChange={() => togglePerm(perm.code)}
                        className="mt-0.5"
                      />
                      <label htmlFor={`perm-${perm.code}`} className="cursor-pointer">
                        <span className="text-sm">{perm.display_name}</span>
                        {perm.description && (
                          <span className="block text-[11px] text-slate-400 leading-tight">{perm.description}</span>
                        )}
                      </label>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          );
        })}
      </div>
    </div>
  );
}
