/**
 * Config → Materiales (kg) → «Formato de captura» (plan-sac-orden-formato-
 * materiales.md D3/F3). El orden del formato en papel «Materiales recolectados»
 * que usa la captura de la Entrada: flechas subir/bajar, vaciar o eliminar un
 * renglon, agregar material o renglon vacio, y Guardar manda la lista COMPLETA
 * (REPLACE).
 *
 * C3 (decision de producto nuestra, la ve Daniel en localhost; no es pedido
 * del cliente): «Vaciar renglon» deja el numero como hueco, para que los
 * renglones de abajo sigan coincidiendo con el papel; «Eliminar renglon» solo
 * existe sobre un renglon vacio y ese si corre los de abajo. Si se prefiere
 * renumerar, se revierte en `remove`. Vaciar el ULTIMO renglon equivale a
 * eliminarlo: el guardado recorta los vacios del final.
 *
 * Sin arrastrar y soltar a proposito: es fragil en el celular y para 25
 * renglones no hace falta.
 */
import { useMemo, useState } from "react";
import { ArrowDown, ArrowUp, Eraser, Pencil, Plus, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { EntitySelect } from "@/components/shared/EntitySelect";
import { useSetFormOrder } from "@/hooks/useSacConfig";
import { cn } from "@/utils";
import type { MaterialKgProfileResponse } from "@/types/sac-config";

interface Props {
  profiles: MaterialKgProfileResponse[];
  canEdit: boolean;
}

/** La lista del servidor como renglones, con los huecos (null) en su numero. */
function currentList(profiles: MaterialKgProfileResponse[]): (string | null)[] {
  const ordered = profiles.filter((p) => p.form_order != null);
  const max = ordered.reduce((m, p) => Math.max(m, p.form_order as number), 0);
  const list: (string | null)[] = Array.from({ length: max }, () => null);
  for (const p of ordered) list[(p.form_order as number) - 1] = p.material_id;
  return list;
}

export function FormatoCapturaSection({ profiles, canEdit }: Props) {
  const setFormOrder = useSetFormOrder();
  const byId = useMemo(() => new Map(profiles.map((p) => [p.material_id, p])), [profiles]);
  const saved = useMemo(() => currentList(profiles), [profiles]);
  const [draft, setDraft] = useState<(string | null)[] | null>(null);
  const [adding, setAdding] = useState("");

  const editing = draft !== null;
  const list = draft ?? saved;
  // F3: un material desactivado conserva su renglon; mientras siga en la
  // lista no se guarda (el servidor la rechazaria con 422)
  const inactiveInList = list.some((id) => id && byId.get(id)?.material_is_active === false);

  const addOptions = useMemo(() => {
    const inList = new Set(list.filter(Boolean));
    return profiles
      .filter((p) => p.material_is_active !== false && !inList.has(p.material_id))
      .sort((a, b) => (a.material_code ?? "").localeCompare(b.material_code ?? "", "es", { numeric: true }))
      .map((p) => ({ id: p.material_id, label: `${p.material_code} - ${p.material_name}` }));
  }, [profiles, list]);

  const move = (i: number, d: -1 | 1) =>
    setDraft((prev) => {
      const next = [...(prev ?? [])];
      [next[i], next[i + d]] = [next[i + d], next[i]];
      return next;
    });
  // C3: un material se vacia (su numero queda como hueco); un hueco se elimina
  const remove = (i: number) =>
    setDraft((prev) => {
      const cur = prev ?? [];
      return cur[i] === null ? cur.filter((_, j) => j !== i) : cur.map((id, j) => (j === i ? null : id));
    });

  const save = () => {
    if (!draft) return;
    // un renglon vacio al final no significa nada en el papel
    const trimmed = [...draft];
    while (trimmed.length && trimmed[trimmed.length - 1] === null) trimmed.pop();
    setFormOrder.mutate(trimmed, { onSuccess: () => setDraft(null) });
  };

  return (
    <div className="rounded-lg border bg-white">
      <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-2 p-4 border-b">
        <div>
          <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-500">Formato de captura</h2>
          <p className="text-xs text-slate-500 mt-0.5 max-w-prose">
            El orden del formato en papel «Materiales recolectados». La Entrada tipo compra muestra un
            renglón por material, en este orden, y el mismo orden se usa al liquidar, en el detalle y en el PDF.
          </p>
        </div>
        {canEdit && !editing && (
          <Button variant="outline" size="sm" onClick={() => setDraft(saved)} className="w-full sm:w-auto shrink-0">
            <Pencil className="h-4 w-4 mr-1" />
            Editar formato
          </Button>
        )}
      </div>

      {list.length === 0 && !editing ? (
        <p className="p-4 text-sm text-slate-400">
          Sin formato: la captura muestra las líneas libres de siempre.
        </p>
      ) : (
        <ol className="divide-y divide-slate-100">
          {list.map((id, i) => {
            const p = id ? byId.get(id) : undefined;
            const inactive = p?.material_is_active === false;
            return (
              <li key={`${id ?? "vacio"}-${i}`} className="flex items-center gap-3 px-4 py-2">
                <span className="w-6 shrink-0 text-right text-xs tabular-nums text-slate-400">{i + 1}</span>
                <div className="min-w-0 flex-1">
                  {id ? (
                    <p className={cn("text-sm text-slate-800 break-words", inactive && "text-slate-400")}>
                      {p?.material_name ?? "Material"}{" "}
                      <span className="text-xs text-slate-400">{p?.material_code}</span>
                    </p>
                  ) : (
                    <p className="text-sm italic text-slate-400">Renglón vacío</p>
                  )}
                  {inactive && <p className="text-xs text-amber-700">Inactivo — vacíe su renglón</p>}
                </div>
                {editing && (
                  <div className="flex items-center gap-0.5 shrink-0">
                    <Button variant="ghost" size="sm" aria-label="Subir" disabled={i === 0} onClick={() => move(i, -1)}>
                      <ArrowUp className="h-4 w-4" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      aria-label="Bajar"
                      disabled={i === list.length - 1}
                      onClick={() => move(i, 1)}
                    >
                      <ArrowDown className="h-4 w-4" />
                    </Button>
                    {id ? (
                      <Button variant="ghost" size="sm" aria-label="Vaciar renglón" title="Vaciar renglón" onClick={() => remove(i)}>
                        <Eraser className="h-4 w-4 text-amber-600" />
                        <span className="hidden sm:inline ml-1">Vaciar renglón</span>
                      </Button>
                    ) : (
                      <Button variant="ghost" size="sm" aria-label="Eliminar renglón" title="Eliminar renglón" onClick={() => remove(i)}>
                        <Trash2 className="h-4 w-4 text-red-500" />
                        <span className="hidden sm:inline ml-1">Eliminar renglón</span>
                      </Button>
                    )}
                  </div>
                )}
              </li>
            );
          })}
        </ol>
      )}

      {editing && (
        <div className="space-y-3 p-4 border-t">
          <div className="flex flex-col sm:flex-row gap-2 sm:items-center">
            <div className="w-full sm:w-80">
              <EntitySelect
                value={adding}
                onChange={setAdding}
                options={addOptions}
                placeholder="Material a agregar..."
              />
            </div>
            <Button
              variant="outline"
              size="sm"
              disabled={!adding}
              onClick={() => {
                setDraft((prev) => [...(prev ?? []), adding]);
                setAdding("");
              }}
              className="w-full sm:w-auto"
            >
              <Plus className="h-4 w-4 mr-1" />
              Agregar material
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setDraft((prev) => [...(prev ?? []), null])}
              className="w-full sm:w-auto"
            >
              Agregar renglón vacío
            </Button>
          </div>
          <p className="text-xs text-slate-400">
            Solo aparecen los materiales clasificados. Si falta uno, clasifíquelo arriba con el lápiz.
          </p>
          {inactiveInList && (
            <p className="text-xs text-amber-700">
              Vacíe los renglones de materiales inactivos para poder guardar.
            </p>
          )}
          <div className="flex flex-col sm:flex-row sm:justify-end gap-2">
            <Button variant="outline" onClick={() => setDraft(null)} className="w-full sm:w-auto">
              Cancelar
            </Button>
            <Button
              onClick={save}
              disabled={inactiveInList || setFormOrder.isPending}
              className="bg-emerald-600 hover:bg-emerald-700 w-full sm:w-auto"
            >
              {setFormOrder.isPending ? "Guardando..." : "Guardar formato"}
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
