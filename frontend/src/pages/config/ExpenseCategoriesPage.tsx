import { useState, useMemo } from "react";
import { type ColumnDef } from "@tanstack/react-table";
import { Plus } from "lucide-react";
import { usePermissions } from "@/hooks/usePermissions";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { DataTable } from "@/components/shared/DataTable";
import { EntitySelect } from "@/components/shared/EntitySelect";
import { useExpenseCategoriesList, useCreateExpenseCategory, useUpdateExpenseCategory } from "@/hooks/useCrudData";
import ConfigLayout from "./ConfigLayout";
import type { ExpenseCategoryResponse } from "@/types/config";

const columns: ColumnDef<ExpenseCategoryResponse, unknown>[] = [
  { accessorKey: "name", header: "Nombre", cell: ({ row }) => <span className="font-medium">{row.original.name}</span> },
  { accessorKey: "parent_name", header: "Categoria Padre", cell: ({ row }) => row.original.parent_name ?? "-" },
  { accessorKey: "description", header: "Descripcion", cell: ({ row }) => row.original.description ?? "-" },
  { accessorKey: "is_direct_expense", header: "Tipo", cell: ({ row }) => row.original.is_direct_expense ? <Badge variant="outline" className="bg-blue-50 text-blue-700">Directo</Badge> : <Badge variant="outline" className="bg-slate-50 text-slate-700">Indirecto</Badge> },
];

export default function ExpenseCategoriesPage() {
  const { hasPermission } = usePermissions();
  const { data, isLoading } = useExpenseCategoriesList();
  const create = useCreateExpenseCategory();
  const update = useUpdateExpenseCategory();

  const [dialogOpen, setDialogOpen] = useState(false);
  const [editItem, setEditItem] = useState<ExpenseCategoryResponse | null>(null);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [isDirect, setIsDirect] = useState(false);
  const [parentId, setParentId] = useState("");

  const items = data?.items ?? [];

  // Opciones de padre: solo categorias nivel 1 (sin parent), excluyendo item actual si edita
  const parentOptions = useMemo(() => {
    return items
      .filter((c) => !c.parent_id && c.id !== editItem?.id)
      .map((c) => ({ id: c.id, label: c.name }));
  }, [items, editItem]);

  const openDialog = (item: ExpenseCategoryResponse | null) => {
    setEditItem(item);
    setName(item?.name ?? "");
    setDescription(item?.description ?? "");
    setIsDirect(item?.is_direct_expense ?? false);
    setParentId(item?.parent_id ?? "");
    setDialogOpen(true);
  };

  const handleSubmit = () => {
    const payload: Record<string, unknown> = {
      name,
      description: description || null,
      parent_id: parentId || null,
    };
    // Solo enviar is_direct_expense si NO tiene padre (el backend lo hereda)
    if (!parentId) {
      payload.is_direct_expense = isDirect;
    }
    const opts = { onSuccess: () => setDialogOpen(false) };
    if (editItem) { update.mutate({ id: editItem.id, data: payload }, opts); }
    else { create.mutate(payload as never, opts); }
  };

  return (
    <ConfigLayout>
      <div className="flex justify-end">
        {hasPermission("treasury.manage_expenses") && (
          <Button onClick={() => openDialog(null)} className="bg-emerald-600 hover:bg-emerald-700"><Plus className="h-4 w-4 mr-2" />Nueva Categoria</Button>
        )}
      </div>

      <DataTable columns={columns} data={items} loading={isLoading} pageCount={1} pageIndex={0} pageSize={100} onPageChange={() => {}}
        onRowClick={hasPermission("treasury.manage_expenses") ? (row) => openDialog(row) : undefined} emptyTitle="Sin categorias" emptyDescription="No hay categorias de gasto." exportFilename="ecobalance_categorias-gasto" />

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="max-w-sm">
          <DialogHeader><DialogTitle>{editItem ? "Editar Categoria" : "Nueva Categoria de Gasto"}</DialogTitle></DialogHeader>
          <div className="space-y-4">
            <div><Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Nombre *</Label><Input value={name} onChange={(e) => setName(e.target.value)} /></div>
            <div><Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Descripcion</Label><Input value={description} onChange={(e) => setDescription(e.target.value)} /></div>
            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Categoria Padre (opcional)</Label>
              <EntitySelect
                value={parentId}
                onChange={setParentId}
                options={parentOptions}
                placeholder="Sin padre (categoria principal)"
              />
            </div>
            {!parentId && (
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">Gasto Directo (afecta costo material)</span>
                <Switch checked={isDirect} onCheckedChange={setIsDirect} />
              </div>
            )}
            {parentId && (
              <p className="text-xs text-slate-400">El tipo (directo/indirecto) se hereda de la categoria padre.</p>
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogOpen(false)}>Cancelar</Button>
            <Button onClick={handleSubmit} disabled={!name || create.isPending || update.isPending} className="bg-emerald-600 hover:bg-emerald-700">
              {create.isPending || update.isPending ? "Guardando..." : editItem ? "Actualizar" : "Crear"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </ConfigLayout>
  );
}
