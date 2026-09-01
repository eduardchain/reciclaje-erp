import { useState, useMemo } from "react";
import { History } from "lucide-react";
import { usePermissions } from "@/hooks/usePermissions";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { EntitySelect } from "@/components/shared/EntitySelect";
import { SearchInput } from "@/components/shared/SearchInput";
import { usePriceTable, usePriceHistory, useCreatePriceList } from "@/hooks/useCrudData";
import { useMaterialCategories } from "@/hooks/useCrudData";
import { formatCurrency, formatDate } from "@/utils/formatters";
import ConfigLayout from "./ConfigLayout";
import type { PriceTableItem } from "@/types/config";
import { EditablePriceCell, priceCellKey, type PriceCellField } from "@/components/shared/EditablePriceCell";

type CellField = PriceCellField;

interface EditingCell {
  materialId: string;
  field: CellField;
}

export default function PriceListsPage() {
  const { hasPermission } = usePermissions();
  const canEdit = hasPermission("materials.edit_prices");
  const [categoryFilter, setCategoryFilter] = useState<string>("");
  const [searchQuery, setSearchQuery] = useState("");
  const [editingCell, setEditingCell] = useState<EditingCell | null>(null);
  const [savingCell, setSavingCell] = useState<string | null>(null);
  const [savedCell, setSavedCell] = useState<string | null>(null);
  const [historyMaterialId, setHistoryMaterialId] = useState<string | null>(null);

  const { data: tableData, isLoading } = usePriceTable(categoryFilter || undefined);
  const { data: categoriesData } = useMaterialCategories();
  const { data: historyData, isLoading: historyLoading } = usePriceHistory(historyMaterialId);
  const createPrice = useCreatePriceList();

  const categories = categoriesData?.items ?? [];

  const historyMaterialName = useMemo(() => {
    if (!historyMaterialId || !tableData) return "";
    const item = tableData.items.find((i) => i.material_id === historyMaterialId);
    return item ? `${item.material_code} - ${item.material_name}` : "";
  }, [historyMaterialId, tableData]);

  const filteredItems = useMemo(() => {
    if (!tableData) return [];
    if (!searchQuery) return tableData.items;
    const q = searchQuery.toLowerCase();
    return tableData.items.filter(
      (i) =>
        i.material_code.toLowerCase().includes(q) ||
        i.material_name.toLowerCase().includes(q)
    );
  }, [tableData, searchQuery]);

  // Orden de tabulacion tipo hoja de calculo: Compra -> Venta de la misma fila
  // -> Compra de la fila siguiente. Se deriva de las filas VISIBLES, asi que
  // respeta el filtro de categoria y la busqueda.
  const cellSequence = useMemo(
    () =>
      filteredItems.flatMap((i) => [
        { materialId: i.material_id, field: "purchase_price" as CellField },
        { materialId: i.material_id, field: "sale_price" as CellField },
      ]),
    [filteredItems],
  );

  const moveEdit = (from: EditingCell, direction: 1 | -1) => {
    const idx = cellSequence.findIndex(
      (c) => c.materialId === from.materialId && c.field === from.field,
    );
    if (idx === -1) return;
    const next = cellSequence[idx + direction];
    // En los extremos de la hoja no se envuelve: se sale de edicion (ya guardado).
    if (next) setEditingCell(next);
  };

  const handleSaveCell = (item: PriceTableItem, field: CellField, newValue: number) => {
    const cellKey = priceCellKey(item.material_id, field);
    setSavingCell(cellKey);
    setEditingCell(null);

    const otherField: CellField = field === "purchase_price" ? "sale_price" : "purchase_price";
    const otherValue = item[otherField] ?? 0;

    createPrice.mutate(
      {
        material_id: item.material_id,
        [field]: newValue,
        [otherField]: otherValue,
      },
      {
        onSuccess: () => {
          setSavingCell(null);
          setSavedCell(cellKey);
          setTimeout(() => setSavedCell(null), 1500);
        },
        onSettled: () => {
          setSavingCell(null);
        },
      }
    );
  };

  return (
    <ConfigLayout>
      <div className="space-y-4">
        {/* Filtros */}
        <div className="flex flex-wrap items-center gap-3">
          <EntitySelect
            value={categoryFilter}
            onChange={setCategoryFilter}
            options={categories.map((c) => ({ id: c.id, label: c.name }))}
            placeholder="Todas las categorias"
          />
          <SearchInput
            value={searchQuery}
            onChange={setSearchQuery}
            placeholder="Buscar codigo o nombre..."
          />
          <div className="ml-auto text-xs text-slate-400">
            {filteredItems.length} materiales
          </div>
        </div>

        {/* Tabla */}
        {isLoading ? (
          <div className="text-center text-slate-500 py-8">Cargando...</div>
        ) : (
          <div className="border rounded-md">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-24">Codigo</TableHead>
                  <TableHead>Material</TableHead>
                  <TableHead className="w-32">Categoria</TableHead>
                  <TableHead className="w-36 text-right">Precio Compra</TableHead>
                  <TableHead className="w-36 text-right">Precio Venta</TableHead>
                  <TableHead className="w-36">Actualizado</TableHead>
                  <TableHead className="w-10"></TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredItems.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={7} className="text-center text-slate-400 py-8">
                      Sin materiales
                    </TableCell>
                  </TableRow>
                ) : (
                  filteredItems.map((item) => (
                    <TableRow key={item.material_id} className="group">
                      <TableCell className="font-mono text-xs">{item.material_code}</TableCell>
                      <TableCell className="font-medium">{item.material_name}</TableCell>
                      <TableCell className="text-xs text-slate-500">{item.category_name ?? "-"}</TableCell>
                      <TableCell className="p-1">
                        <EditablePriceCell
                          item={item}
                          field="purchase_price"
                          canEdit={canEdit}
                          isEditing={editingCell?.materialId === item.material_id && editingCell?.field === "purchase_price"}
                          onStartEdit={() => setEditingCell({ materialId: item.material_id, field: "purchase_price" })}
                          onSave={(v) => handleSaveCell(item, "purchase_price", v)}
                          onCancel={() => setEditingCell(null)}
                          onNavigate={(dir) => moveEdit({ materialId: item.material_id, field: "purchase_price" }, dir)}
                          savingCell={savingCell}
                          savedCell={savedCell}
                        />
                      </TableCell>
                      <TableCell className="p-1">
                        <EditablePriceCell
                          item={item}
                          field="sale_price"
                          canEdit={canEdit}
                          isEditing={editingCell?.materialId === item.material_id && editingCell?.field === "sale_price"}
                          onStartEdit={() => setEditingCell({ materialId: item.material_id, field: "sale_price" })}
                          onSave={(v) => handleSaveCell(item, "sale_price", v)}
                          onCancel={() => setEditingCell(null)}
                          onNavigate={(dir) => moveEdit({ materialId: item.material_id, field: "sale_price" }, dir)}
                          savingCell={savingCell}
                          savedCell={savedCell}
                        />
                      </TableCell>
                      <TableCell className="text-xs text-slate-400">
                        {item.last_updated ? (
                          <div>
                            <div>{formatDate(item.last_updated)}</div>
                            {item.updated_by_name && <div className="text-slate-300">{item.updated_by_name}</div>}
                          </div>
                        ) : (
                          "-"
                        )}
                      </TableCell>
                      <TableCell className="p-1">
                        <Button
                          variant="ghost"
                          size="sm"
                          className="h-7 w-7 p-0 opacity-0 group-hover:opacity-100"
                          onClick={() => setHistoryMaterialId(item.material_id)}
                          title="Historial de precios"
                        >
                          <History className="w-4 h-4 text-slate-400" />
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </div>
        )}
      </div>

      {/* Modal Historial */}
      <Dialog open={!!historyMaterialId} onOpenChange={(open) => !open && setHistoryMaterialId(null)}>
        <DialogContent className="max-w-[calc(100vw-2rem)] sm:max-w-2xl">
          <DialogHeader>
            <DialogTitle>Historial de Precios</DialogTitle>
            <p className="text-sm text-slate-500">{historyMaterialName}</p>
          </DialogHeader>
          {historyLoading ? (
            <div className="text-center py-4 text-slate-400">Cargando...</div>
          ) : (
            <div className="max-h-80 overflow-y-auto overflow-x-auto">
              <Table className="min-w-[560px]">
                <TableHeader>
                  <TableRow>
                    <TableHead>Fecha</TableHead>
                    <TableHead className="text-right">Precio Compra</TableHead>
                    <TableHead className="text-right">Precio Venta</TableHead>
                    <TableHead>Notas</TableHead>
                    <TableHead>Usuario</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {(historyData?.items ?? []).length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={5} className="text-center text-slate-400 py-4">
                        Sin registros
                      </TableCell>
                    </TableRow>
                  ) : (
                    (historyData?.items ?? []).map((h, idx) => (
                      <TableRow key={idx}>
                        <TableCell className="text-xs">{formatDate(h.created_at)}</TableCell>
                        <TableCell className="text-right tabular-nums">{formatCurrency(h.purchase_price)}</TableCell>
                        <TableCell className="text-right tabular-nums">{formatCurrency(h.sale_price)}</TableCell>
                        <TableCell className="text-xs text-slate-500 max-w-[200px] truncate">{h.notes ?? "-"}</TableCell>
                        <TableCell className="text-xs text-slate-400">{((h as unknown as Record<string, unknown>).updated_by_name as string) ?? "-"}</TableCell>
                      </TableRow>
                    ))
                  )}
                </TableBody>
              </Table>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </ConfigLayout>
  );
}
