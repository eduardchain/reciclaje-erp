import { useEffect, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useThirdPartyCategoriesFlat } from "@/hooks/useMasterData";
import { usePermissions } from "@/hooks/usePermissions";
import { thirdPartyService } from "@/services/thirdParties";
import { getApiErrorMessage } from "@/utils/formatters";
import type { SimilarThirdParty } from "@/types/third-party";

/**
 * Reparto por compra §5 — crear un proveedor sin salir de la liquidación.
 *
 * Johana (19-nov): en una sola Entrada llegan proveedores nuevos y crearlos en
 * Terceros obligaba a salir de la pantalla. La tabla de terceros NO tiene
 * unicidad, así que antes de crear se pregunta `/third-parties/similar`: es el
 * único freno a un duplicado.
 *
 * - Ya es proveedor → «Usar este».
 * - Existe pero no es proveedor (un cliente, por ejemplo) → se le AGREGA la
 *   categoría de proveedor: el PATCH reemplaza la lista entera, así que se
 *   manda la suya más la nueva, nunca solo la nueva.
 * - No existe → se crea con la categoría de proveedor de material.
 *
 * Dos clases de resultado (plan similar-por-contenido v1.1, D3):
 * - `exact` (nombre igual sin tildes ni mayúsculas, o identificación limpia
 *   igual): es el mismo tercero → BLOQUEA, sin «crear igual». Si no lo es,
 *   basta con distinguir el nombre.
 * - `similar` (se parece por contenido): solo AVISA (O1 de Daniel, 20-nov) y
 *   el botón pasa a «Crear igual», que crea sin volver a preguntar. En SAC la
 *   mayoría de los parecidos medidos son cuentas aparte a propósito
 *   («… - Préstamo»), así que bloquear trabaría un uso legítimo.
 * Un resultado sin `match` (backend anterior) cuenta como exact: la dirección
 * conservadora.
 *
 * `onCreated(id, name)`: el nombre viaja para que el selector lo pinte antes
 * de que vuelva la lista de proveedores invalidada.
 */
export function CreateSupplierDialog({
  open,
  onOpenChange,
  onCreated,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onCreated: (id: string, name: string) => void;
}) {
  const qc = useQueryClient();
  // Alcance de recolector (plan §5.5): editar un tercero existente esta fuera
  // de su lista blanca, asi que no se le ofrece agregar la categoria.
  const { collectorScope } = usePermissions();
  const scoped = collectorScope !== null;
  const [name, setName] = useState("");
  const [identification, setIdentification] = useState("");
  const [phone, setPhone] = useState("");
  const [categoryId, setCategoryId] = useState("");
  const [matches, setMatches] = useState<SimilarThirdParty[] | null>(null);
  const [busy, setBusy] = useState(false);
  const hasExact = (matches ?? []).some((m) => m.match !== "similar");
  const onlySimilar = (matches?.length ?? 0) > 0 && !hasExact;

  const { data: catData } = useThirdPartyCategoriesFlat("material_supplier");
  const categories = (catData?.items ?? []).filter((c) => c.is_active);

  useEffect(() => {
    if (open) {
      setName("");
      setIdentification("");
      setPhone("");
      setMatches(null);
    }
  }, [open]);

  // Una sola categoría de proveedor (SAC dev: «Proveedor Material») → se usa
  // sin preguntar; con varias, la ventana las ofrece.
  useEffect(() => {
    if (!categoryId && categories.length === 1) setCategoryId(categories[0].id);
  }, [categories, categoryId]);

  // Editar los datos invalida la búsqueda anterior: hay que volver a preguntar
  const edit = (setter: (v: string) => void) => (v: string) => {
    setter(v);
    setMatches(null);
  };

  const finish = async (id: string, label: string) => {
    await qc.invalidateQueries({ queryKey: ["third-parties"] });
    onCreated(id, label);
    onOpenChange(false);
  };

  // `skipSearch`: «Crear igual» — el usuario ya vio los parecidos (D3)
  const handleContinue = async (skipSearch = false) => {
    if (!name.trim() || busy) return;
    setBusy(true);
    try {
      if (!skipSearch) {
        const found = await thirdPartyService.findSimilar(name, identification);
        if (found.length > 0) {
          setMatches(found);
          return;
        }
      }
      if (!categoryId) {
        toast.error("No hay una categoría de proveedor de material. Créela en Configuración → Terceros.");
        return;
      }
      const created = await thirdPartyService.create({
        name: name.trim(),
        identification_number: identification.trim() || null,
        phone: phone.trim() || null,
        category_ids: [categoryId],
      });
      toast.success(`Proveedor ${created.name} creado`);
      await finish(created.id, created.name);
    } catch (e) {
      toast.error(getApiErrorMessage(e, "No se pudo crear el proveedor"));
    } finally {
      setBusy(false);
    }
  };

  const pickExisting = async (m: SimilarThirdParty) => {
    if (busy) return;
    if (m.is_material_supplier) {
      await finish(m.id, m.name);
      return;
    }
    if (!categoryId) {
      toast.error("No hay una categoría de proveedor de material. Créela en Configuración → Terceros.");
      return;
    }
    setBusy(true);
    try {
      await thirdPartyService.update(m.id, {
        category_ids: [...new Set([...m.category_ids, categoryId])],
      });
      toast.success(`${m.name} ahora también es proveedor`);
      await finish(m.id, m.name);
    } catch (e) {
      toast.error(getApiErrorMessage(e, "No se pudo agregar la categoría"));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Nuevo proveedor</DialogTitle>
          <DialogDescription>
            Antes de crearlo se busca si ya existe, por nombre o por identificación.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-3">
          <div>
            <Label htmlFor="ns-name">Nombre *</Label>
            <Input
              id="ns-name"
              value={name}
              onChange={(e) => edit(setName)(e.target.value)}
              maxLength={200}
              autoFocus
            />
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <Label htmlFor="ns-id">Identificación</Label>
              <Input
                id="ns-id"
                value={identification}
                onChange={(e) => edit(setIdentification)(e.target.value)}
                maxLength={50}
                placeholder="Opcional"
              />
            </div>
            <div>
              <Label htmlFor="ns-phone">Teléfono</Label>
              <Input
                id="ns-phone"
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                maxLength={50}
                placeholder="Opcional"
              />
            </div>
          </div>
          {categories.length > 1 && (
            <div>
              <Label>Categoría</Label>
              <Select value={categoryId || undefined} onValueChange={setCategoryId}>
                <SelectTrigger>
                  <SelectValue placeholder="Categoría de proveedor..." />
                </SelectTrigger>
                <SelectContent>
                  {categories.map((c) => (
                    <SelectItem key={c.id} value={c.id}>
                      {c.display_name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          )}

          {matches && matches.length > 0 && (
            <div
              data-testid="similar-panel"
              data-kind={hasExact ? "exact" : "similar"}
              className="rounded-md border border-amber-200 bg-amber-50 p-3 space-y-2"
            >
              <p className="text-sm text-amber-800">
                {hasExact ? (matches.length === 1 ? "Ya existe:" : "Ya existen:") : "Se parece a:"}
              </p>
              {matches.map((m) => (
                <div
                  key={m.id}
                  className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 text-sm"
                >
                  <div className="min-w-0">
                    <p className="font-medium truncate">{m.name}</p>
                    <p className="text-xs text-slate-500">
                      {m.identification_number || "sin identificación"}
                      {!m.is_material_supplier && " · no es proveedor de material"}
                      {hasExact && m.match === "similar" && " · se parece"}
                    </p>
                  </div>
                  {scoped && !m.is_material_supplier ? (
                    <p className="text-xs text-slate-500 sm:text-right">
                      Para usarlo como proveedor, SAC tiene que agregarle la categoría
                    </p>
                  ) : (
                  <Button
                    size="sm"
                    variant="outline"
                    className="bg-white w-full sm:w-auto"
                    disabled={busy}
                    onClick={() => pickExisting(m)}
                  >
                    {m.is_material_supplier ? "Usar este" : "Agregar categoría y usar"}
                  </Button>
                  )}
                </div>
              ))}
              <p className="text-xs text-amber-700">
                {hasExact
                  ? "Si es otro tercero, cambie el nombre o la identificación para distinguirlo."
                  : "Si es otro tercero, puede crearlo igual."}
              </p>
            </div>
          )}
        </div>

        <DialogFooter className="flex-col sm:flex-row gap-2">
          <Button
            variant="outline"
            onClick={() => onOpenChange(false)}
            className="w-full sm:w-auto"
          >
            Cancelar
          </Button>
          <Button
            data-testid="create-supplier-submit"
            onClick={() => handleContinue(onlySimilar)}
            disabled={!name.trim() || busy || hasExact}
            className="w-full sm:w-auto"
          >
            {busy ? "Buscando..." : onlySimilar ? "Crear igual" : "Crear proveedor"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
