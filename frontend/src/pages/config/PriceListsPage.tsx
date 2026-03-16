import { useState, useMemo, useRef, useEffect, useCallback } from "react";
import { CheckCircle2, History, Loader2 } from "lucide-react";
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

type CellField = "purchase_price" | "sale_price";

interface EditingCell {
  materialId: string;
  field: CellField;
}

function EditableCell({
  item,
  field,
  canEdit,
  isEditing,
  onStartEdit,
  onSave,
  onCancel,
  savingCell,
  savedCell,
}: {
  item: PriceTableItem;
  field: CellField;
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
  const cellKey = `${item.material_id}-${field}`;
  const isSaving = savingCell === cellKey;
  const isSaved = savedCell === cellKey;
  const currentValue = item[field];

  useEffect(() => {
    if (isEditing) {
      setEditValue(currentValue != null ? String(currentValue) : "");
      setTimeout(() => inputRef.current?.focus(), 0);
    }
  }, [isEditing, currentValue]);

  const handleSave = useCallback(() => {
    const parsed = parseFloat(editValue) || 0;
    const final = Math.max(0, parsed);
    if (final !== (currentValue ?? 0)) {
      onSave(final);
    } else {
      onCancel();
    }
  }, [editValue, currentValue, onSave, onCancel]);

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === "Enter") {
      e.preventDefault();
      handleSave();
    } else if (e.key === "Escape") {
      e.preventDefault();
      onCancel();
    } else if (e.key === "Tab") {
      handleSave();
    }
  }, [handleSave, onCancel]);

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

  return (
    <div
      className={`flex items-center justify-end gap-1 h-8 px-2 rounded text-sm tabular-nums ${canEdit ? "cursor-pointer hover:bg-emerald-50" : ""} ${currentValue == null ? "text-slate-400 italic" : ""}`}
      onClick={canEdit ? onStartEdit : undefined}
    >
      {isSaving && <Loader2 className="w-3 h-3 animate-spin text-emerald-600" />}
      {isSaved && <CheckCircle2 className="w-3 h-3 text-emerald-500" />}
      <span>{currentValue != null ? formatCurrency(currentValue) : "$0"}</span>
    </div>
  );
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

  const handleSaveCell = (item: PriceTableItem, field: CellField, newValue: number) => {
    const cellKey = `${item.material_id}-${field}`;
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
                        <EditableCell
                          item={item}
                          field="purchase_price"
                          canEdit={canEdit}
                          isEditing={editingCell?.materialId === item.material_id && editingCell?.field === "purchase_price"}
                          onStartEdit={() => setEditingCell({ materialId: item.material_id, field: "purchase_price" })}
                          onSave={(v) => handleSaveCell(item, "purchase_price", v)}
                          onCancel={() => setEditingCell(null)}
                          savingCell={savingCell}
                          savedCell={savedCell}
                        />
                      </TableCell>
                      <TableCell className="p-1">
                        <EditableCell
                          item={item}
                          field="sale_price"
                          canEdit={canEdit}
                          isEditing={editingCell?.materialId === item.material_id && editingCell?.field === "sale_price"}
                          onStartEdit={() => setEditingCell({ materialId: item.material_id, field: "sale_price" })}
                          onSave={(v) => handleSaveCell(item, "sale_price", v)}
                          onCancel={() => setEditingCell(null)}
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
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>Historial de Precios</DialogTitle>
            <p className="text-sm text-slate-500">{historyMaterialName}</p>
          </DialogHeader>
          {historyLoading ? (
            <div className="text-center py-4 text-slate-400">Cargando...</div>
          ) : (
            <div className="max-h-80 overflow-y-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Fecha</TableHead>
                    <TableHead className="text-right">Precio Compra</TableHead>
                    <TableHead className="text-right">Precio Venta</TableHead>
                    <TableHead>Notas</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {(historyData?.items ?? []).length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={4} className="text-center text-slate-400 py-4">
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
