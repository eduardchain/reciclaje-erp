import { useState, useMemo, useRef, useEffect, useCallback } from "react";
import { CheckCircle2, Loader2, Plus, Users, Tag, AlertTriangle } from "lucide-react";
import { usePermissions } from "@/hooks/usePermissions";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
import { SearchInput } from "@/components/shared/SearchInput";
import { useCreatePriceList } from "@/hooks/useCrudData";
import {
  usePriceListGroups,
  usePriceListGroupTable,
  usePriceListGroupSuppliers,
  useCreatePriceListGroup,
  useUpdatePriceListGroup,
  useSetPriceListGroupMembers,
} from "@/hooks/usePriceListGroups";
import { formatCurrency, formatDate } from "@/utils/formatters";
import ConfigLayout from "./ConfigLayout";
import type { PriceTableItem } from "@/types/config";
import type { SupplierMembershipItem } from "@/types/price-list-group";

/**
 * Listas de precios por proveedor (SAC).
 *
 * Dos zonas dentro de una lista: la hoja de calculo de precios y la asignacion
 * de proveedores. La asignacion se hace DESDE la lista — "para esta lista son
 * estos, estos y estos proveedores" (Hugo, corrigiendo en vivo el sentido).
 */

// ---------------------------------------------------------------- celda editable

function EditableCell({
  item,
  canEdit,
  isEditing,
  onStartEdit,
  onSave,
  onCancel,
  savingCell,
  savedCell,
}: {
  item: PriceTableItem;
  canEdit: boolean;
  isEditing: boolean;
  onStartEdit: () => void;
  onSave: (value: number) => void;
  onCancel: () => void;
  savingCell: string | null;
  savedCell: string | null;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [editValue, setEditValue] = useState("");
  const cellKey = item.material_id;
  const isSaving = savingCell === cellKey;
  const isSaved = savedCell === cellKey;
  const currentValue = item.purchase_price;

  useEffect(() => {
    if (isEditing) {
      setEditValue(currentValue != null ? String(currentValue) : "");
      setTimeout(() => inputRef.current?.focus(), 0);
    }
  }, [isEditing, currentValue]);

  const handleSave = useCallback(() => {
    const parsed = parseFloat(editValue) || 0;
    const final = Math.max(0, parsed);
    if (final !== (currentValue ?? 0)) onSave(final);
    else onCancel();
  }, [editValue, currentValue, onSave, onCancel]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "Enter") {
        e.preventDefault();
        handleSave();
      } else if (e.key === "Escape") {
        e.preventDefault();
        onCancel();
      } else if (e.key === "Tab") {
        handleSave();
      }
    },
    [handleSave, onCancel]
  );

  if (isEditing) {
    return (
      <input
        ref={inputRef}
        type="text"
        inputMode="numeric"
        value={editValue}
        onChange={(e) => {
          if (e.target.value === "" || /^\d*\.?\d*$/.test(e.target.value)) {
            setEditValue(e.target.value);
          }
        }}
        onBlur={handleSave}
        onKeyDown={handleKeyDown}
        className="w-full h-8 px-2 text-right text-sm border border-emerald-400 rounded bg-white focus:outline-none focus:ring-2 focus:ring-emerald-300"
      />
    );
  }

  const sinPrecio = currentValue == null || currentValue === 0;
  return (
    <div
      className={`flex items-center justify-end gap-1 h-8 px-2 rounded text-sm tabular-nums ${
        canEdit ? "cursor-pointer hover:bg-emerald-50" : ""
      } ${sinPrecio ? "text-slate-400 italic" : ""}`}
      onClick={canEdit ? onStartEdit : undefined}
      title={sinPrecio ? "Sin precio: a este proveedor no se le sugiere nada para este material" : undefined}
    >
      {isSaving && <Loader2 className="w-3 h-3 animate-spin text-emerald-600" />}
      {isSaved && <CheckCircle2 className="w-3 h-3 text-emerald-500" />}
      <span>{sinPrecio ? "Sin precio" : formatCurrency(currentValue)}</span>
    </div>
  );
}

// ------------------------------------------------------------- crear lista

function CreateGroupDialog({
  open,
  onOpenChange,
  esPrimera,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  esPrimera: boolean;
}) {
  const [name, setName] = useState("");
  // El sembrado viene marcado cuando es la PRIMERA lista: es justo el momento
  // en que hace falta (sin el, todos los proveedores quedan sin sugerencia).
  const [seed, setSeed] = useState(esPrimera);
  const [assign, setAssign] = useState(esPrimera);
  const createGroup = useCreatePriceListGroup();

  useEffect(() => {
    if (open) {
      setName("");
      setSeed(esPrimera);
      setAssign(esPrimera);
    }
  }, [open, esPrimera]);

  const submit = () => {
    if (!name.trim()) return;
    createGroup.mutate(
      { name: name.trim(), seed_from_general: seed, assign_all_suppliers: assign },
      { onSuccess: () => onOpenChange(false) }
    );
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Nueva lista de precios</DialogTitle>
        </DialogHeader>
        <div className="space-y-4">
          <div className="space-y-1.5">
            <Label htmlFor="group-name">Nombre</Label>
            <Input
              id="group-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Ej. Lista A"
              onKeyDown={(e) => e.key === "Enter" && submit()}
            />
          </div>

          {esPrimera && (
            <div className="flex gap-2 rounded-md border border-amber-200 bg-amber-50 p-3 text-xs text-amber-900">
              <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
              <div>
                <strong>Es la primera lista.</strong> Desde que exista una, a un proveedor sin lista
                asignada <strong>no se le sugiere ningun precio</strong>. Las dos opciones de abajo
                dejan el sistema comportandose igual que hoy mientras reparte los proveedores con calma.
              </div>
            </div>
          )}

          <label className="flex items-start gap-2 text-sm cursor-pointer">
            <Checkbox checked={seed} onCheckedChange={(v) => setSeed(v === true)} className="mt-0.5" />
            <span>
              Copiar los precios de la lista general
              <span className="block text-xs text-slate-500">
                Punto de partida editable. Solo copia los materiales que hoy tienen precio.
              </span>
            </span>
          </label>

          <label className="flex items-start gap-2 text-sm cursor-pointer">
            <Checkbox checked={assign} onCheckedChange={(v) => setAssign(v === true)} className="mt-0.5" />
            <span>
              Asignar los proveedores que no tienen lista
              <span className="block text-xs text-slate-500">
                No mueve los que ya pertenecen a otra lista.
              </span>
            </span>
          </label>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} className="w-full sm:w-auto">
            Cancelar
          </Button>
          <Button onClick={submit} disabled={!name.trim() || createGroup.isPending} className="w-full sm:w-auto">
            {createGroup.isPending ? "Creando..." : "Crear lista"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// ------------------------------------------------------------------ pagina

export default function SupplierPriceListsPage() {
  const { hasPermission } = usePermissions();
  const canEdit = hasPermission("materials.edit_prices");

  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [search, setSearch] = useState("");
  const [supplierSearch, setSupplierSearch] = useState("");
  const [editingMaterialId, setEditingMaterialId] = useState<string | null>(null);
  const [savingCell, setSavingCell] = useState<string | null>(null);
  const [savedCell, setSavedCell] = useState<string | null>(null);
  const [pendingMembers, setPendingMembers] = useState<Set<string> | null>(null);

  const { data: groupsData, isLoading } = usePriceListGroups(true);
  const groups = useMemo(() => groupsData?.items ?? [], [groupsData]);
  const selected = groups.find((g) => g.id === selectedId) ?? null;

  const { data: tableData, isLoading: tableLoading } = usePriceListGroupTable(selectedId);
  const { data: suppliersData } = usePriceListGroupSuppliers(!!selectedId);
  const createPrice = useCreatePriceList();
  const updateGroup = useUpdatePriceListGroup();
  const setMembers = useSetPriceListGroupMembers();

  // Selección inicial: la primera lista, cuando llegan.
  useEffect(() => {
    if (!selectedId && groups.length > 0) setSelectedId(groups[0].id);
  }, [groups, selectedId]);

  // Los checkboxes arrancan desde el servidor y se editan en local hasta guardar.
  const serverMembers = useMemo(() => {
    const s = new Set<string>();
    for (const item of suppliersData?.items ?? []) {
      if (item.current_group_id === selectedId) s.add(item.third_party_id);
    }
    return s;
  }, [suppliersData, selectedId]);

  useEffect(() => {
    setPendingMembers(null);
  }, [selectedId]);

  const members = pendingMembers ?? serverMembers;
  const dirty = pendingMembers !== null;

  const filteredMaterials = useMemo(() => {
    const items = tableData?.items ?? [];
    if (!search) return items;
    const q = search.toLowerCase();
    return items.filter(
      (i: PriceTableItem) => i.material_code.toLowerCase().includes(q) || i.material_name.toLowerCase().includes(q)
    );
  }, [tableData, search]);

  const filteredSuppliers = useMemo(() => {
    const items = suppliersData?.items ?? [];
    if (!supplierSearch) return items;
    const q = supplierSearch.toLowerCase();
    return items.filter((i: SupplierMembershipItem) => i.third_party_name.toLowerCase().includes(q));
  }, [suppliersData, supplierSearch]);

  const handleSaveCell = (item: PriceTableItem, newValue: number) => {
    if (!selectedId) return;
    setSavingCell(item.material_id);
    setEditingMaterialId(null);
    createPrice.mutate(
      {
        material_id: item.material_id,
        purchase_price: newValue,
        sale_price: 0,
        price_list_group_id: selectedId,
      },
      {
        onSuccess: () => {
          setSavedCell(item.material_id);
          setTimeout(() => setSavedCell(null), 1500);
        },
        onSettled: () => setSavingCell(null),
      }
    );
  };

  const toggleMember = (tpId: string) => {
    const next = new Set(members);
    if (next.has(tpId)) next.delete(tpId);
    else next.add(tpId);
    setPendingMembers(next);
  };

  const saveMembers = () => {
    if (!selectedId || !pendingMembers) return;
    setMembers.mutate(
      { id: selectedId, thirdPartyIds: [...pendingMembers] },
      { onSuccess: () => setPendingMembers(null) }
    );
  };

  const conPrecio = filteredMaterials.filter((i: PriceTableItem) => (i.purchase_price ?? 0) > 0).length;

  return (
    <ConfigLayout>
      <div className="space-y-4">
        {/* Selector de listas */}
        <div className="flex flex-col sm:flex-row sm:flex-wrap gap-2 sm:items-center">
          {isLoading ? (
            <span className="text-sm text-slate-400">Cargando listas...</span>
          ) : groups.length === 0 ? (
            <span className="text-sm text-slate-500">
              Todavia no hay listas. Mientras no exista ninguna, todos los proveedores usan la lista general.
            </span>
          ) : (
            groups.map((g) => (
              <button
                key={g.id}
                onClick={() => setSelectedId(g.id)}
                className={`flex items-center gap-2 rounded-md border px-3 py-1.5 text-sm transition ${
                  g.id === selectedId
                    ? "border-emerald-400 bg-emerald-50 text-emerald-900"
                    : "border-slate-200 hover:bg-slate-50"
                } ${g.is_active ? "" : "opacity-60"}`}
              >
                <span className="font-medium">{g.name}</span>
                <span className="text-xs text-slate-500">
                  {g.member_count} prov · {g.priced_material_count} con precio
                </span>
                {!g.is_active && <Badge variant="outline" className="text-xs">Inactiva</Badge>}
              </button>
            ))
          )}
          {canEdit && (
            <Button
              variant="outline"
              size="sm"
              onClick={() => setCreateOpen(true)}
              className="w-full sm:w-auto sm:ml-auto"
            >
              <Plus className="w-4 h-4 mr-1" /> Nueva lista
            </Button>
          )}
        </div>

        {selected && (
          <Tabs defaultValue="precios" className="space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center gap-2">
              <TabsList>
                <TabsTrigger value="precios">
                  <Tag className="w-4 h-4 mr-1" /> Precios
                </TabsTrigger>
                <TabsTrigger value="proveedores">
                  <Users className="w-4 h-4 mr-1" /> Proveedores ({members.size})
                </TabsTrigger>
              </TabsList>
              {canEdit && (
                <Button
                  variant="ghost"
                  size="sm"
                  className="sm:ml-auto text-xs text-slate-500"
                  onClick={() =>
                    updateGroup.mutate({
                      id: selected.id,
                      data: { is_active: !selected.is_active },
                    })
                  }
                >
                  {selected.is_active ? "Desactivar lista" : "Reactivar lista"}
                </Button>
              )}
            </div>

            {/* --- Precios --- */}
            <TabsContent value="precios" className="space-y-3">
              <div className="flex flex-col sm:flex-row sm:flex-wrap gap-2 sm:items-center">
                <SearchInput
                  value={search}
                  onChange={setSearch}
                  placeholder="Buscar codigo o nombre..."
                />
                <div className="text-xs text-slate-400 sm:ml-auto">
                  {conPrecio} con precio de {filteredMaterials.length} materiales
                </div>
              </div>

              <div className="rounded-md border border-slate-200 bg-slate-50 p-3 text-xs text-slate-600">
                La lista trae <strong>todos</strong> los materiales. Los que se dejan{" "}
                <em>sin precio</em> no se le sugieren a estos proveedores — y{" "}
                <strong>tampoco se rellenan con la lista general</strong>: dejarlo vacio es una
                decision, no un olvido.
              </div>

              {tableLoading ? (
                <div className="text-center text-slate-500 py-8">Cargando...</div>
              ) : (
                <div className="border rounded-md overflow-x-auto">
                  <Table className="min-w-[560px]">
                    <TableHeader>
                      <TableRow>
                        <TableHead className="w-24">Codigo</TableHead>
                        <TableHead>Material</TableHead>
                        <TableHead className="w-32">Categoria</TableHead>
                        <TableHead className="w-40 text-right">Precio Compra</TableHead>
                        <TableHead className="w-32">Actualizado</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {filteredMaterials.length === 0 ? (
                        <TableRow>
                          <TableCell colSpan={5} className="text-center text-slate-400 py-8">
                            Sin materiales
                          </TableCell>
                        </TableRow>
                      ) : (
                        filteredMaterials.map((item) => (
                          <TableRow key={item.material_id}>
                            <TableCell className="font-mono text-xs">{item.material_code}</TableCell>
                            <TableCell className="font-medium">{item.material_name}</TableCell>
                            <TableCell className="text-xs text-slate-500">
                              {item.category_name ?? "-"}
                            </TableCell>
                            <TableCell className="p-1">
                              <EditableCell
                                item={item}
                                canEdit={canEdit}
                                isEditing={editingMaterialId === item.material_id}
                                onStartEdit={() => setEditingMaterialId(item.material_id)}
                                onSave={(v) => handleSaveCell(item, v)}
                                onCancel={() => setEditingMaterialId(null)}
                                savingCell={savingCell}
                                savedCell={savedCell}
                              />
                            </TableCell>
                            <TableCell className="text-xs text-slate-400">
                              {item.last_updated ? formatDate(item.last_updated) : "-"}
                            </TableCell>
                          </TableRow>
                        ))
                      )}
                    </TableBody>
                  </Table>
                </div>
              )}
            </TabsContent>

            {/* --- Proveedores --- */}
            <TabsContent value="proveedores" className="space-y-3">
              <SearchInput
                value={supplierSearch}
                onChange={setSupplierSearch}
                placeholder="Buscar proveedor..."
              />

              <div className="border rounded-md divide-y">
                {filteredSuppliers.length === 0 ? (
                  <div className="text-center text-slate-400 py-8 text-sm">Sin proveedores</div>
                ) : (
                  filteredSuppliers.map((s) => {
                    const checked = members.has(s.third_party_id);
                    const enOtra =
                      !checked &&
                      s.current_group_id != null &&
                      s.current_group_id !== selected.id;
                    return (
                      <label
                        key={s.third_party_id}
                        className="flex items-center gap-3 px-3 py-2 text-sm cursor-pointer hover:bg-slate-50"
                      >
                        <Checkbox
                          checked={checked}
                          disabled={!canEdit}
                          onCheckedChange={() => toggleMember(s.third_party_id)}
                        />
                        <span className="flex-1">{s.third_party_name}</span>
                        {enOtra && (
                          <Badge variant="outline" className="text-xs text-amber-700 border-amber-300">
                            en {s.current_group_name}
                          </Badge>
                        )}
                        {!checked && s.current_group_id == null && (
                          <span className="text-xs text-slate-400">sin lista</span>
                        )}
                      </label>
                    );
                  })
                )}
              </div>

              {dirty && (
                <div className="sticky bottom-0 flex flex-col sm:flex-row sm:items-center gap-2 border-t bg-white -mx-3 px-3 py-3 md:-mx-6 md:px-6 pb-[max(1rem,env(safe-area-inset-bottom))]">
                  <span className="text-xs text-amber-700">
                    Marcar un proveedor que ya esta en otra lista lo <strong>mueve</strong> a esta:
                    cada proveedor pertenece a una sola.
                  </span>
                  <div className="flex gap-2 sm:ml-auto">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setPendingMembers(null)}
                      className="w-full sm:w-auto"
                    >
                      Descartar
                    </Button>
                    <Button
                      size="sm"
                      onClick={saveMembers}
                      disabled={setMembers.isPending}
                      className="w-full sm:w-auto"
                    >
                      {setMembers.isPending ? "Guardando..." : "Guardar proveedores"}
                    </Button>
                  </div>
                </div>
              )}
            </TabsContent>
          </Tabs>
        )}
      </div>

      <CreateGroupDialog
        open={createOpen}
        onOpenChange={setCreateOpen}
        esPrimera={groups.length === 0}
      />
    </ConfigLayout>
  );
}
