import { useCallback } from "react";
import {
  type ColumnDef,
  type SortingState,
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  useReactTable,
} from "@tanstack/react-table";
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
} from "lucide-react";
import * as XLSX from "xlsx";
import { EmptyState } from "./EmptyState";
import { useState } from "react";

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
  toolbar?: React.ReactNode;
}

function exportToExcel<TData>(columns: ColumnDef<TData, unknown>[], data: TData[], filename: string) {
  const headers = columns
    .filter((col) => col.id !== "actions" && col.id !== "select")
    .map((col) => {
      if (typeof col.header === "string") return col.header;
      return col.id || "";
    });

  const rows = data.map((row) =>
    columns
      .filter((col) => col.id !== "actions" && col.id !== "select")
      .map((col) => {
        const key = (col as { accessorKey?: string }).accessorKey || col.id || "";
        const value = (row as Record<string, unknown>)[key];
        if (value == null) return "";
        return value;
      })
  );

  const ws = XLSX.utils.aoa_to_sheet([headers, ...rows]);
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
  toolbar,
}: DataTableProps<TData, TValue>) {
  const [sorting, setSorting] = useState<SortingState>([]);

  const table = useReactTable({
    data,
    columns,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    onSortingChange: setSorting,
    manualPagination: true,
    pageCount,
    state: {
      pagination: { pageIndex, pageSize },
      sorting,
    },
  });

  const handleExport = useCallback(() => {
    if (exportFilename) {
      exportToExcel(columns as ColumnDef<TData, unknown>[], data, exportFilename);
    }
  }, [columns, data, exportFilename]);

  if (loading) {
    return (
      <div className="rounded-lg border border-slate-200/80 bg-white shadow-sm overflow-hidden">
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
        <div className="flex items-center justify-between gap-3">
          <div className="flex-1">{toolbar}</div>
          {exportFilename && (
            <Button
              variant="outline"
              size="sm"
              onClick={handleExport}
              className="text-slate-600 shrink-0"
            >
              <FileSpreadsheet className="h-4 w-4 mr-1.5" />
              Excel
            </Button>
          )}
        </div>
      )}

      {/* Table */}
      <div className="rounded-lg border border-slate-200/80 bg-white shadow-sm overflow-hidden">
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
        <div className="flex items-center justify-between text-sm">
          <p className="text-slate-500 tabular-nums">
            Mostrando {showFrom}-{showTo} de {total} registros
          </p>
          <div className="flex items-center gap-1">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => onPageChange(0)}
              disabled={pageIndex === 0}
              className="h-8 w-8 p-0 text-slate-500"
            >
              <ChevronsLeft className="h-4 w-4" />
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => onPageChange(pageIndex - 1)}
              disabled={pageIndex === 0}
              className="h-8 w-8 p-0 text-slate-500"
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
              className="h-8 w-8 p-0 text-slate-500"
            >
              <ChevronRight className="h-4 w-4" />
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => onPageChange(pageCount - 1)}
              disabled={pageIndex >= pageCount - 1}
              className="h-8 w-8 p-0 text-slate-500"
            >
              <ChevronsRight className="h-4 w-4" />
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
