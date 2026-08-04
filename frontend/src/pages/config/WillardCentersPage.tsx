import { useEffect, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Plus, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { organizationService } from "@/services/organizations";
import { useOrgSettings } from "@/hooks/useOrgSettings";
import { usePermissions } from "@/hooks/usePermissions";
import { useAuthStore } from "@/stores/authStore";
import { willardCenterLabel } from "@/pages/inbound/InboundCreatePage";
import { getApiErrorMessage } from "@/utils/formatters";

/**
 * Centros de distribucion Willard (ajustes reunion 2026-08-03, item C).
 *
 * Johana: "¿se pueden adicionar?" — hasta ahora solo podia un superusuario.
 *
 * La lectura NO tiene endpoint propio (H2 del micro-QA): `useOrgSettings` ya
 * trae la lista via GET /organizations/{id}, que es la MISMA query que
 * alimenta el selector de la Entrada. Por eso al guardar se invalida
 * ["org-settings", organizationId] y se refrescan las dos superficies.
 */
export default function WillardCentersPage() {
  const qc = useQueryClient();
  const organizationId = useAuthStore((s) => s.organizationId);
  const { getSetting, isLoading } = useOrgSettings();
  const { hasPermission } = usePermissions();
  const canEdit = hasPermission("config.manage_sac_settings");

  const stored = (getSetting("willard_distribution_centers") as string[]) ?? [];
  const [centers, setCenters] = useState<string[]>(stored);
  const [draft, setDraft] = useState("");

  // Sincroniza cuando llega el query (o cambia de org) sin pisar la edicion
  const storedKey = stored.join("|");
  useEffect(() => {
    setCenters(stored);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [storedKey, organizationId]);

  const save = useMutation({
    mutationFn: (next: string[]) =>
      organizationService.updateWillardDistributionCenters(next),
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: ["org-settings", organizationId] });
      setCenters(data.centers);
      data.warnings.forEach((w) => toast.warning(w));
      toast.success("Centros de distribucion actualizados");
    },
    onError: (e) => toast.error(getApiErrorMessage(e)),
  });

  const dirty = centers.join("|") !== storedKey;

  const addDraft = () => {
    const value = draft.trim();
    if (!value) return;
    // El backend normaliza y deduplica; aca solo se evita el duplicado obvio
    if (centers.some((c) => c.toLowerCase() === value.toLowerCase())) {
      toast.warning(`"${value}" ya esta en la lista`);
      return;
    }
    setCenters([...centers, value]);
    setDraft("");
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Centros de Distribucion Willard</CardTitle>
        <p className="text-xs text-slate-500">
          Origenes que se pueden declarar al capturar una recepcion Willard. Quitar
          uno no cambia las entradas ya registradas: solo deja de poder elegirse.
        </p>
      </CardHeader>
      <CardContent className="space-y-4">
        {isLoading ? (
          <p className="text-sm text-slate-400">Cargando...</p>
        ) : (
          <>
            <div className="flex flex-wrap gap-2">
              {centers.length === 0 && (
                <p className="text-sm text-slate-400">Sin centros configurados.</p>
              )}
              {centers.map((c) => (
                <span
                  key={c}
                  className="inline-flex items-center gap-1.5 rounded-full bg-slate-100 px-3 py-1 text-sm text-slate-700"
                >
                  {willardCenterLabel(c)}
                  {canEdit && (
                    <button
                      type="button"
                      aria-label={`Quitar ${c}`}
                      className="text-slate-400 hover:text-red-600"
                      onClick={() => setCenters(centers.filter((x) => x !== c))}
                    >
                      <X className="h-3.5 w-3.5" />
                    </button>
                  )}
                </span>
              ))}
            </div>

            {canEdit && (
              <>
                <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
                  <Input
                    value={draft}
                    onChange={(e) => setDraft(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") {
                        e.preventDefault();
                        addDraft();
                      }
                    }}
                    maxLength={24}
                    placeholder="Nuevo centro (ej. Sincelejo)"
                    className="w-full sm:w-64"
                  />
                  <Button
                    type="button"
                    variant="outline"
                    onClick={addDraft}
                    className="w-full sm:w-auto"
                  >
                    <Plus className="mr-1.5 h-4 w-4" />
                    Agregar
                  </Button>
                </div>

                <div className="flex flex-col gap-2 sm:flex-row sm:justify-end">
                  <Button
                    type="button"
                    variant="ghost"
                    onClick={() => setCenters(stored)}
                    disabled={!dirty || save.isPending}
                    className="w-full sm:w-auto"
                  >
                    Descartar
                  </Button>
                  <Button
                    type="button"
                    onClick={() => save.mutate(centers)}
                    disabled={!dirty || centers.length === 0 || save.isPending}
                    className="w-full sm:w-auto"
                  >
                    {save.isPending ? "Guardando..." : "Guardar cambios"}
                  </Button>
                </div>
              </>
            )}
          </>
        )}
      </CardContent>
    </Card>
  );
}
