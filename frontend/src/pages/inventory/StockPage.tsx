import { useState, useMemo, Fragment } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { Package, DollarSign, Layers, Weight, ChevronRight, ArrowRightLeft, Loader2, ChevronsUpDown, FileSpreadsheet } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Checkbox } from "@/components/ui/checkbox";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { PageHeader } from "@/components/shared/PageHeader";
import { KpiCard } from "@/components/shared/KpiCard";
import { useStock, useStockDetail, useCreateTransfer } from "@/hooks/useInventory";
import { useWarehouses } from "@/hooks/useMasterData";
import { formatCurrency } from "@/utils/formatters";
import { exportStockExcel } from "@/utils/excelExport";
import { cn } from "@/utils";
import type { StockItem } from "@/types/inventory";
import type { MetricCard } from "@/types/reports";
import { usePermissions } from "@/hooks/usePermissions";

// --- Multi-select filter ---

interface MultiSelectOption {
  value: string;
  label: string;
}

function MultiSelectFilter({
  options,
  selected,
  onChange,
  placeholder,
}: {
  options: MultiSelectOption[];
  selected: Set<string>;
  onChange: (next: Set<string>) => void;
  placeholder: string;
}) {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState("");

  const toggle = (value: string) => {
    const next = new Set(selected);
    if (next.has(value)) next.delete(value);
    else next.add(value);
    onChange(next);
  };

  const visibleOptions = search
    ? options.filter((o) => o.label.toLowerCase().includes(search.toLowerCase()))
    : options;

  const allVisibleSelected = visibleOptions.length > 0 && visibleOptions.every((o) => selected.has(o.value));

  const toggleVisible = () => {
    const next = new Set(selected);
    if (allVisibleSelected) visibleOptions.forEach((o) => next.delete(o.value));
    else visibleOptions.forEach((o) => next.add(o.value));
    onChange(next);
  };

  const label =
    selected.size === 0
      ? placeholder
      : selected.size === options.length
      ? "Todos"
      : `${selected.size} seleccionado${selected.size > 1 ? "s" : ""}`;

  return (
    <Popover open={open} onOpenChange={(v) => { setOpen(v); if (!v) setSearch(""); }}>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          role="combobox"
          className={cn("w-48 justify-between font-normal", selected.size > 0 && "border-blue-400 bg-blue-50 text-blue-700")}
        >
          <span className="truncate">{label}</span>
          <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-56 p-2" align="start">
        <input
          className="w-full mb-2 px-2 py-1 text-sm border rounded outline-none focus:ring-1 focus:ring-blue-400"
          placeholder="Buscar..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          onClick={(e) => e.stopPropagation()}
        />
        <div className="space-y-1 max-h-56 overflow-y-auto">
          <button
            className="flex items-center gap-2 w-full px-2 py-1.5 text-sm rounded hover:bg-slate-100"
            onClick={toggleVisible}
          >
            <Checkbox checked={allVisibleSelected} />
            <span className="font-medium">{search ? "Seleccionar visibles" : "Todos"}</span>
          </button>
          <div className="border-t my-1" />
          {visibleOptions.length === 0 && (
            <p className="text-xs text-slate-400 px-2 py-1">Sin resultados</p>
          )}
          {visibleOptions.map((opt) => (
            <button
              key={opt.value}
              className="flex items-center gap-2 w-full px-2 py-1.5 text-sm rounded hover:bg-slate-100"
              onClick={() => toggle(opt.value)}
            >
              <Checkbox checked={selected.has(opt.value)} />
              <span className="truncate">{opt.label}</span>
            </button>
          ))}
        </div>
      </PopoverContent>
    </Popover>
  );
}

// --- Modal de traslado entre bodegas ---

interface TransferModalState {
  materialId: string;
  materialName: string;
  sourceWarehouseId: string;
  sourceWarehouseName: string;
}

function WarehouseTransferModal({
  state,
  onClose,
  allWarehouses,
}: {
  state: TransferModalState;
  onClose: () => void;
  allWarehouses: { id: string; name: string }[];
}) {
  const transfer = useCreateTransfer();
  const [destinationWarehouseId, setDestinationWarehouseId] = useState("");
  const [quantity, setQuantity] = useState("");
  const [reason, setReason] = useState("");
  const [date, setDate] = useState(new Date().toISOString().split("T")[0]);

  const availableWarehouses = allWarehouses.filter(w => w.id !== state.sourceWarehouseId);

  const handleSubmit = () => {
    if (!destinationWarehouseId || !quantity || !reason) {
      toast.error("Complete todos los campos");
      return;
    }
    transfer.mutate({
      material_id: state.materialId,
      source_warehouse_id: state.sourceWarehouseId,
      destination_warehouse_id: destinationWarehouseId,
      quantity: parseFloat(quantity),
      date,
      reason,
    }, {
      onSuccess: () => onClose(),
    });
  };

  return (
    <Dialog open onOpenChange={onClose}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Trasladar entre Bodegas</DialogTitle>
          <DialogDescription>
            Trasladar {state.materialName} desde {state.sourceWarehouseName}
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-4 py-4">
          <div>
            <Label>Material</Label>
            <Input value={state.materialName} disabled />
          </div>
          <div>
            <Label>Bodega Origen</Label>
            <Input value={state.sourceWarehouseName} disabled />
          </div>
          <div>
            <Label>Bodega Destino</Label>
            <Select value={destinationWarehouseId} onValueChange={setDestinationWarehouseId}>
              <SelectTrigger>
                <SelectValue placeholder="Seleccionar bodega destino" />
              </SelectTrigger>
              <SelectContent>
                {availableWarehouses.map(w => (
                  <SelectItem key={w.id} value={w.id}>{w.name}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div>
            <Label>Cantidad</Label>
            <Input type="number" step="0.01" min="0.01" value={quantity} onChange={(e) => setQuantity(e.target.value)} placeholder="0.00" />
          </div>
          <div>
            <Label>Fecha</Label>
            <Input type="date" value={date} onChange={(e) => setDate(e.target.value)} />
          </div>
          <div>
            <Label>Razon del traslado</Label>
            <Input value={reason} onChange={(e) => setReason(e.target.value)} placeholder="Ej: Redistribucion de inventario" />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>Cancelar</Button>
          <Button onClick={handleSubmit} disabled={transfer.isPending}>
            {transfer.isPending ? "Trasladando..." : "Confirmar Traslado"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function WarehouseBreakdownRow({
  materialId,
  materialName,
  defaultUnit,
  onTransfer,
}: {
  materialId: string;
  materialName: string;
  defaultUnit: string;
  onTransfer: (materialId: string, warehouseId: string, warehouseName: string) => void;
}) {
  const navigate = useNavigate();
  const { data, isLoading } = useStockDetail(materialId);
  const { hasPermission } = usePermissions();

  if (isLoading) {
    return (
      <TableRow className="bg-slate-50/50">
        <TableCell colSpan={9} className="py-4">
          <div className="flex items-center gap-2 text-sm text-slate-500">
            <Loader2 className="h-4 w-4 animate-spin" />
            Cargando desglose...
          </div>
        </TableCell>
      </TableRow>
    );
  }

  if (!data || data.warehouses.length === 0) {
    return (
      <TableRow className="bg-slate-50/50">
        <TableCell colSpan={9} className="py-4 text-sm text-slate-500">
          Sin movimientos en bodegas
        </TableCell>
      </TableRow>
    );
  }

  return (
    <TableRow className="bg-slate-50/50 hover:bg-slate-50/50">
      <TableCell colSpan={9} className="py-3 px-6">
        <div className="text-xs font-medium text-slate-500 uppercase mb-2">
          Desglose por Bodega — {materialName}
        </div>
        <div className="bg-white rounded border">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b bg-slate-50">
                <th className="text-left py-2 px-3 font-medium">Bodega</th>
                <th className="text-right py-2 px-3 font-medium">Stock</th>
                <th className="text-right py-2 px-3 font-medium">Acciones</th>
              </tr>
            </thead>
            <tbody>
              {data.warehouses.map((w) => (
                <tr key={w.warehouse_id} className="border-b last:border-0">
                  <td className="py-2 px-3">{w.warehouse_name}</td>
                  <td className="py-2 px-3 text-right tabular-nums">
                    {w.stock.toFixed(2)} {defaultUnit}
                  </td>
                  <td className="py-2 px-3 text-right">
                    {hasPermission("inventory.transfer") && (
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={(e) => {
                          e.stopPropagation();
                          onTransfer(materialId, w.warehouse_id, w.warehouse_name);
                        }}
                        disabled={w.stock <= 0}
                      >
                        <ArrowRightLeft className="h-3 w-3 mr-1" />
                        Trasladar
                      </Button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="flex gap-2 mt-3">
          <Button
            variant="outline"
            size="sm"
            onClick={() => navigate(`/inventory/movements?material_id=${materialId}`)}
          >
            Ver Movimientos
          </Button>
          {hasPermission("inventory.adjust") && (
            <Button
              variant="outline"
              size="sm"
              onClick={() => navigate(`/inventory/adjustments/new?material_id=${materialId}`)}
            >
              Ajustar Stock
            </Button>
          )}
        </div>
      </TableCell>
    </TableRow>
  );
}

export default function StockPage() {
  const navigate = useNavigate();
  const { hasPermission } = usePermissions();
  const canViewValues = hasPermission("inventory.view_values");
  const [expandedMaterial, setExpandedMaterial] = useState<string | null>(null);
  const [categoryFilters, setCategoryFilters] = useState<Set<string>>(new Set());
  const [warehouseFilters, setWarehouseFilters] = useState<Set<string>>(new Set());
  const [materialFilters, setMaterialFilters] = useState<Set<string>>(new Set());
  const [transferModal, setTransferModal] = useState<TransferModalState | null>(null);

  const { data: warehousesData } = useWarehouses();
  const warehouses = warehousesData?.items ?? [];

  const { data, isLoading } = useStock();

  // Derive filter options from loaded data
  const categoryOptions = useMemo<MultiSelectOption[]>(() => {
    if (!data?.items) return [];
    const seen = new Map<string, string>();
    for (const item of data.items) {
      if (item.category_name) seen.set(item.category_name, item.category_name);
    }
    return Array.from(seen.entries())
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([v]) => ({ value: v, label: v }));
  }, [data]);

  const warehouseOptions = useMemo<MultiSelectOption[]>(
    () => (warehouses as { id: string; name: string }[]).map((w) => ({ value: w.id, label: w.name })),
    [warehouses],
  );

  const materialOptions = useMemo<MultiSelectOption[]>(() => {
    if (!data?.items) return [];
    return data.items.map((i) => ({ value: i.material_id, label: `${i.material_code} - ${i.material_name}` }));
  }, [data]);

  const filteredItems = useMemo(() => {
    if (!data?.items) return [];
    return data.items.filter((item) => {
      if (materialFilters.size > 0 && !materialFilters.has(item.material_id)) return false;
      if (categoryFilters.size > 0) {
        if (!item.category_name || !categoryFilters.has(item.category_name)) return false;
      }
      if (warehouseFilters.size > 0) {
        if (!item.warehouse_ids.some((wid) => warehouseFilters.has(wid))) return false;
      }
      return true;
    });
  }, [data, materialFilters, categoryFilters, warehouseFilters]);

  const kpis = useMemo(() => {
    const count = filteredItems.length;
    const totalValue = filteredItems.reduce((s, i) => s + i.total_value, 0);
    const transitStock = filteredItems.reduce((s, i) => s + i.current_stock_transit, 0);
    const totalStock = filteredItems.reduce((s, i) => s + i.current_stock_total, 0);
    return {
      count: { current_value: count, previous_value: 0, change_percentage: null } as MetricCard,
      value: { current_value: totalValue, previous_value: 0, change_percentage: null } as MetricCard,
      transit: { current_value: transitStock, previous_value: 0, change_percentage: null } as MetricCard,
      totalStock: { current_value: totalStock, previous_value: 0, change_percentage: null } as MetricCard,
    };
  }, [data, filteredItems]);

  const toggleExpand = (materialId: string) => {
    setExpandedMaterial(expandedMaterial === materialId ? null : materialId);
  };

  const handleOpenTransfer = (materialId: string, warehouseId: string, warehouseName: string) => {
    const material = data?.items.find(i => i.material_id === materialId);
    setTransferModal({
      materialId,
      materialName: material?.material_name ?? "",
      sourceWarehouseId: warehouseId,
      sourceWarehouseName: warehouseName,
    });
  };

  const colSpan = canViewValues ? 9 : 7;

  return (
    <div className="space-y-4">
      <PageHeader title="Inventario" description="Vista consolidada de stock">
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={() => exportStockExcel(filteredItems, canViewValues)}>
            <FileSpreadsheet className="h-4 w-4 mr-2" />Excel
          </Button>
          <Button variant="outline" onClick={() => navigate("/inventory/movements")}>Movimientos</Button>
          <Button variant="outline" onClick={() => navigate("/inventory/adjustments")}>Ajustes</Button>
          <Button variant="outline" onClick={() => navigate("/inventory/transformations")}>Transformaciones</Button>
        </div>
      </PageHeader>

      {isLoading ? (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-28 rounded-lg" />
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <KpiCard label="Materiales" metric={kpis.count} icon={<Package className="h-4 w-4" />} accentColor="violet" formatValue={(n) => String(n)} />
          <KpiCard label="Stock Total" metric={kpis.totalStock} icon={<Weight className="h-4 w-4" />} accentColor="sky" formatValue={(n) => n.toFixed(2) + " kg"} />
          {canViewValues && <KpiCard label="Valor Inventario" metric={kpis.value} icon={<DollarSign className="h-4 w-4" />} accentColor="emerald" />}
          <KpiCard label="Stock en Transito" metric={kpis.transit} icon={<Layers className="h-4 w-4" />} accentColor="amber" formatValue={(n) => n.toFixed(2) + " kg"} />
        </div>
      )}

      <div className="flex items-center gap-3 flex-wrap">
        <MultiSelectFilter
          options={materialOptions}
          selected={materialFilters}
          onChange={setMaterialFilters}
          placeholder="Material"
        />
        <MultiSelectFilter
          options={categoryOptions}
          selected={categoryFilters}
          onChange={setCategoryFilters}
          placeholder="Categoria"
        />
        <MultiSelectFilter
          options={warehouseOptions}
          selected={warehouseFilters}
          onChange={setWarehouseFilters}
          placeholder="Bodega"
        />
        {(materialFilters.size > 0 || categoryFilters.size > 0 || warehouseFilters.size > 0) && (
          <Button
            variant="ghost"
            size="sm"
            className="text-xs text-slate-500"
            onClick={() => { setMaterialFilters(new Set()); setCategoryFilters(new Set()); setWarehouseFilters(new Set()); }}
          >
            Limpiar filtros
          </Button>
        )}
      </div>

      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-8" />
              <TableHead>Codigo</TableHead>
              <TableHead>Material</TableHead>
              <TableHead>Unidad</TableHead>
              <TableHead className="text-right">Stock Liq.</TableHead>
              <TableHead className="text-right">Stock Trans.</TableHead>
              <TableHead className="text-right">Total</TableHead>
              {canViewValues && <TableHead className="text-right">Costo Prom.</TableHead>}
              {canViewValues && <TableHead className="text-right">Valor Total</TableHead>}
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading ? (
              <TableRow>
                <TableCell colSpan={colSpan} className="h-24 text-center text-slate-500">
                  Cargando...
                </TableCell>
              </TableRow>
            ) : filteredItems.length === 0 ? (
              <TableRow>
                <TableCell colSpan={colSpan} className="h-24 text-center text-slate-500">
                  Sin materiales con stock.
                </TableCell>
              </TableRow>
            ) : (
              filteredItems.map((item: StockItem) => (
                <Fragment key={item.material_id}>
                  <TableRow
                    onClick={() => toggleExpand(item.material_id)}
                    className="cursor-pointer hover:bg-slate-50"
                  >
                    <TableCell className="w-8 px-2">
                      <ChevronRight className={cn(
                        "h-4 w-4 transition-transform text-slate-400",
                        expandedMaterial === item.material_id && "rotate-90"
                      )} />
                    </TableCell>
                    <TableCell className="font-medium">{item.material_code}</TableCell>
                    <TableCell>
                      <div>{item.material_name}</div>
                      {item.category_name && (
                        <div className="text-xs text-slate-400">{item.category_name}</div>
                      )}
                    </TableCell>
                    <TableCell>{item.default_unit}</TableCell>
                    <TableCell className="text-right tabular-nums">{item.current_stock_liquidated.toFixed(2)}</TableCell>
                    <TableCell className="text-right">
                      {item.current_stock_transit !== 0 ? (
                        <Badge variant="outline" className={item.current_stock_transit > 0 ? "bg-yellow-50 text-yellow-700" : "bg-red-50 text-red-700"}>{item.current_stock_transit.toFixed(2)}</Badge>
                      ) : (
                        <span className="text-slate-400">0</span>
                      )}
                    </TableCell>
                    <TableCell className="text-right font-medium tabular-nums">{item.current_stock_total.toFixed(2)}</TableCell>
                    {canViewValues && <TableCell className="text-right">{formatCurrency(item.current_average_cost)}</TableCell>}
                    {canViewValues && <TableCell className="text-right font-medium">{formatCurrency(item.total_value)}</TableCell>}
                  </TableRow>

                  {expandedMaterial === item.material_id && (
                    <WarehouseBreakdownRow
                      materialId={item.material_id}
                      materialName={item.material_name}
                      defaultUnit={item.default_unit}
                      onTransfer={handleOpenTransfer}
                    />
                  )}
                </Fragment>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      {transferModal && (
        <WarehouseTransferModal
          state={transferModal}
          onClose={() => setTransferModal(null)}
          allWarehouses={warehouses as { id: string; name: string }[]}
        />
      )}
    </div>
  );
}
