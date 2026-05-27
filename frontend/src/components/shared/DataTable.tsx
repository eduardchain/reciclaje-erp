import { useCallback, useEffect, useMemo } from "react";
import {
  type ColumnDef,
  type SortingState,
  type VisibilityState,
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  useReactTable,
} from "@tanstack/react-table";
import { useIsMobile } from "@/hooks/useMediaQuery";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
  ChevronLeft,
  ChevronRight,
  ChevronsLeft,
  ChevronsRight,
  ArrowUpDown,
  ArrowUp,
  ArrowDown,
  FileSpreadsheet,
  Loader2,
} from "lucide-react";
import * as XLSX from "xlsx";
import { toast } from "sonner";
import { EmptyState } from "./EmptyState";
import { useState } from "react";
import { applyCurrencyFormat } from "@/utils/excelHelpers";

interface DataTableProps<TData, TValue> {
  columns: ColumnDef<TData, TValue>[];
  data: TData[];
  loading?: boolean;
  pageCount?: number;
  pageIndex?: number;
  pageSize?: number;
  totalItems?: number;
  onPageChange?: (page: number) => void;
  onRowClick?: (row: TData) => void;
  emptyTitle?: string;
  emptyDescription?: string;
  exportFilename?: string;
  onExportAll?: () => Promise<TData[]>;
  currencyColumns?: string[];
  toolbar?: React.ReactNode;
  /** Controlled sorting state. Si se pasa junto con `onSortingChange`, el orden
   * lo controla el padre (util para persistir en URL/store). Si no, se maneja
   * internamente con useState. */
  sorting?: SortingState;
  onSortingChange?: (sorting: SortingState) => void;
}

function exportToExcel<TData>(
  columns: ColumnDef<TData, unknown>[],
  data: TData[],
  filename: string,
  currencyColumns?: string[],
) {
  const exportableCols = columns.filter((col) => col.id !== "actions" && col.id !== "select");
  const headers = exportableCols.map((col) => {
    if (typeof col.header === "string") return col.header;
    return col.id || "";
  });

  const colKeys = exportableCols.map(
    (col) => (col as { accessorKey?: string }).accessorKey || col.id || "",
  );

  const rows = data.map((row) =>
    colKeys.map((key) => {
      const value = (row as Record<string, unknown>)[key];
      if (value == null) return "";
      // Backend serializa Decimal como string ("100000.00"). Convertir a número
      // si parsea limpio, para que Excel los reconozca como numéricos.
      if (typeof value === "string" && /^-?\d+(\.\d+)?$/.test(value)) {
        return Number(value);
      }
      return value;
    }),
  );

  const ws = XLSX.utils.aoa_to_sheet([headers, ...rows]);

  if (currencyColumns && currencyColumns.length > 0) {
    const currencyColIdx = currencyColumns
      .map((key) => colKeys.indexOf(key))
      .filter((idx) => idx >= 0);
    if (currencyColIdx.length > 0) {
      applyCurrencyFormat(ws, currencyColIdx);
    }
  }

  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, ws, "Datos");
  XLSX.writeFile(wb, `${filename}.xlsx`);
}

export function DataTable<TData, TValue>({
  columns,
  data,
  loading = false,
  pageCount = 1,
  pageIndex = 0,
  pageSize = 20,
  totalItems,
  onPageChange,
  onRowClick,
  emptyTitle,
  emptyDescription,
  exportFilename,
  onExportAll,
  currencyColumns,
  toolbar,
  sorting: externalSorting,
  onSortingChange: externalOnSortingChange,
}: DataTableProps<TData, TValue>) {
  const [internalSorting, setInternalSorting] = useState<SortingState>([]);
  const sorting = externalSorting ?? internalSorting;
  const [exporting, setExporting] = useState(false);

  // Visibilidad de columnas: en mobile esconde columnas marcadas con
  // meta.hideOnMobile. NUNCA marcar la columna `id: "actions"` con este flag.
  const isMobile = useIsMobile();
  const derivedVisibility = useMemo<VisibilityState>(() => {
    const v: VisibilityState = {};
    columns.forEach((col) => {
      const meta = col.meta;
      const id = (col as { id?: string; accessorKey?: string }).id
        ?? (col as { accessorKey?: string }).accessorKey;
      if (meta?.hideOnMobile && id) v[id] = !isMobile;
    });
    return v;
  }, [columns, isMobile]);
  const [columnVisibility, setColumnVisibility] = useState<VisibilityState>(derivedVisibility);
  useEffect(() => {
    setColumnVisibility(derivedVisibility);
  }, [derivedVisibility]);

  // Server-side sort cuando el padre pasa onSortingChange controlado. Sin esto,
  // DataTable ordena solo la pagina visible (client-side, comportamiento previo).
  const useManualSorting = externalOnSortingChange != null;
  const table = useReactTable({
    data,
    columns,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: useManualSorting ? undefined : getSortedRowModel(),
    manualSorting: useManualSorting,
    onSortingChange: (updater) => {
      const next = typeof updater === "function" ? updater(sorting) : updater;
      if (externalOnSortingChange) externalOnSortingChange(next);
      else setInternalSorting(next);
    },
    onColumnVisibilityChange: setColumnVisibility,
    manualPagination: true,
    pageCount,
    state: {
      pagination: { pageIndex, pageSize },
      sorting,
      columnVisibility,
    },
  });

  const handleExport = useCallback(async () => {
    if (!exportFilename) return;
    if (onExportAll) {
      setExporting(true);
      try {
        const all = await onExportAll();
        exportToExcel(columns as ColumnDef<TData, unknown>[], all, exportFilename, currencyColumns);
      } catch {
        toast.error("Error al exportar");
      } finally {
        setExporting(false);
      }
    } else {
      exportToExcel(columns as ColumnDef<TData, unknown>[], data, exportFilename, currencyColumns);
    }
  }, [columns, data, exportFilename, onExportAll, currencyColumns]);

  if (loading) {
    return (
      <div className="rounded-lg border border-slate-200/80 bg-white shadow-sm overflow-x-auto">
        <Table>
          <TableHeader>
            <TableRow className="bg-slate-50/80 hover:bg-slate-50/80">
              {columns.map((_, i) => (
                <TableHead key={i}>
                  <Skeleton className="h-3 w-20" />
                </TableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {Array.from({ length: 5 }).map((_, i) => (
              <TableRow key={i}>
                {columns.map((_, j) => (
                  <TableCell key={j}>
                    <Skeleton className="h-4 w-full" />
                  </TableCell>
                ))}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    );
  }

  const showFrom = pageIndex * pageSize + 1;
  const showTo = Math.min((pageIndex + 1) * pageSize, totalItems || data.length);
  const total = totalItems || data.length;

  return (
    <div className="space-y-3">
      {/* Toolbar */}
      {(toolbar || exportFilename) && (
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
          <div className="flex-1 min-w-0">{toolbar}</div>
          {exportFilename && (
            <Button
              variant="outline"
              size="sm"
              onClick={handleExport}
              disabled={exporting}
              className="text-slate-600 shrink-0 w-full sm:w-auto"
            >
              {exporting ? (
                <Loader2 className="h-4 w-4 mr-1.5 animate-spin" />
              ) : (
                <FileSpreadsheet className="h-4 w-4 mr-1.5" />
              )}
              Excel
            </Button>
          )}
        </div>
      )}

      {/* Table */}
      <div className="rounded-lg border border-slate-200/80 bg-white shadow-sm overflow-x-auto">
        <Table>
          <TableHeader>
            {table.getHeaderGroups().map((headerGroup) => (
              <TableRow key={headerGroup.id} className="bg-slate-50/80 hover:bg-slate-50/80 border-b border-slate-200/80">
                {headerGroup.headers.map((header) => {
                  const canSort = header.column.getCanSort();
                  const sorted = header.column.getIsSorted();
                  return (
                    <TableHead
                      key={header.id}
                      className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 h-10"
                    >
                      {header.isPlaceholder ? null : canSort ? (
                        <button
                          className="flex items-center gap-1.5 hover:text-slate-900 transition-colors"
                          onClick={header.column.getToggleSortingHandler()}
                        >
                          {flexRender(header.column.columnDef.header, header.getContext())}
                          {sorted === "asc" ? (
                            <ArrowUp className="h-3.5 w-3.5 text-emerald-600" />
                          ) : sorted === "desc" ? (
                            <ArrowDown className="h-3.5 w-3.5 text-emerald-600" />
                          ) : (
                            <ArrowUpDown className="h-3.5 w-3.5 opacity-30" />
                          )}
                        </button>
                      ) : (
                        flexRender(header.column.columnDef.header, header.getContext())
                      )}
                    </TableHead>
                  );
                })}
              </TableRow>
            ))}
          </TableHeader>
          <TableBody>
            {table.getRowModel().rows?.length ? (
              table.getRowModel().rows.map((row, i) => (
                <TableRow
                  key={row.id}
                  className={`
                    ${onRowClick ? "cursor-pointer" : ""}
                    ${i % 2 === 1 ? "bg-slate-50/40" : ""}
                    hover:bg-slate-100/60 transition-colors
                  `}
                  onClick={() => onRowClick?.(row.original)}
                >
                  {row.getVisibleCells().map((cell) => (
                    <TableCell key={cell.id} className="py-3">
                      {flexRender(cell.column.columnDef.cell, cell.getContext())}
                    </TableCell>
                  ))}
                </TableRow>
              ))
            ) : (
              <TableRow>
                <TableCell colSpan={columns.length} className="h-32 text-center">
                  <EmptyState title={emptyTitle} description={emptyDescription} />
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>

      {/* Pagination */}
      {onPageChange && pageCount > 1 && (
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 text-sm">
          <p className="text-slate-500 tabular-nums text-center sm:text-left">
            Mostrando {showFrom}-{showTo} de {total} registros
          </p>
          <div className="flex items-center justify-center sm:justify-end gap-1">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => onPageChange(0)}
              disabled={pageIndex === 0}
              className="h-9 w-9 sm:h-8 sm:w-8 p-0 text-slate-500"
            >
              <ChevronsLeft className="h-4 w-4" />
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => onPageChange(pageIndex - 1)}
              disabled={pageIndex === 0}
              className="h-9 w-9 sm:h-8 sm:w-8 p-0 text-slate-500"
            >
              <ChevronLeft className="h-4 w-4" />
            </Button>
            <span className="px-3 py-1 text-sm font-medium text-slate-700 tabular-nums">
              {pageIndex + 1} / {pageCount}
            </span>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => onPageChange(pageIndex + 1)}
              disabled={pageIndex >= pageCount - 1}
              className="h-9 w-9 sm:h-8 sm:w-8 p-0 text-slate-500"
            >
              <ChevronRight className="h-4 w-4" />
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => onPageChange(pageCount - 1)}
              disabled={pageIndex >= pageCount - 1}
              className="h-9 w-9 sm:h-8 sm:w-8 p-0 text-slate-500"
            >
              <ChevronsRight className="h-4 w-4" />
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
