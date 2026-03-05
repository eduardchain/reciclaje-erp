import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { type ColumnDef } from "@tanstack/react-table";
import { Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { PageHeader } from "@/components/shared/PageHeader";
import { DataTable } from "@/components/shared/DataTable";
import { SearchInput } from "@/components/shared/SearchInput";
import { DateRangePicker } from "@/components/shared/DateRangePicker";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { useDoubleEntries } from "@/hooks/useDoubleEntries";
import { formatCurrency, formatDate, formatWeight, formatPercentage } from "@/utils/formatters";
import { ROUTES } from "@/utils/constants";
import type { DoubleEntryResponse } from "@/types/double-entry";

const PAGE_SIZE = 20;

const columns: ColumnDef<DoubleEntryResponse, unknown>[] = [
  { accessorKey: "double_entry_number", header: "#", cell: ({ row }) => <span className="font-medium">#{row.original.double_entry_number}</span> },
  { accessorKey: "date", header: "Fecha", cell: ({ row }) => formatDate(row.original.date) },
  { accessorKey: "material_name", header: "Material", cell: ({ row }) => <><span className="font-medium">{row.original.material_name}</span><span className="text-gray-400 ml-2 text-xs">{formatWeight(row.original.quantity)}</span></> },
  { accessorKey: "supplier_name", header: "Proveedor" },
  { accessorKey: "customer_name", header: "Cliente" },
  { accessorKey: "profit", header: "Utilidad", cell: ({ row }) => <span className={`font-medium tabular-nums ${row.original.profit >= 0 ? "text-green-700" : "text-red-700"}`}>{formatCurrency(row.original.profit)}</span> },
  { accessorKey: "profit_margin", header: "Margen", cell: ({ row }) => formatPercentage(row.original.profit_margin) },
  { accessorKey: "status", header: "Estado", cell: ({ row }) => <StatusBadge status={row.original.status} /> },
];

export default function DoubleEntriesPage() {
  const navigate = useNavigate();
  const [page, setPage] = useState(0);
  const [search, setSearch] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");

  const { data, isLoading } = useDoubleEntries({
    skip: page * PAGE_SIZE,
    limit: PAGE_SIZE,
    search: search || undefined,
    date_from: dateFrom || undefined,
    date_to: dateTo || undefined,
  });

  const pageCount = data ? Math.ceil(data.total / PAGE_SIZE) : 1;

  return (
    <div className="space-y-4">
      <PageHeader title="Doble Partida" description="Operaciones Pasa Mano (compra+venta simultanea)">
        <Button onClick={() => navigate(ROUTES.DOUBLE_ENTRIES_NEW)} className="bg-green-600 hover:bg-green-700">
          <Plus className="h-4 w-4 mr-2" />Nueva Doble Partida
        </Button>
      </PageHeader>

      <div className="flex items-center gap-4">
        <SearchInput value={search} onChange={(v) => { setSearch(v); setPage(0); }} placeholder="Buscar..." />
        <DateRangePicker dateFrom={dateFrom} dateTo={dateTo} onDateFromChange={setDateFrom} onDateToChange={setDateTo} />
      </div>

      <DataTable
        columns={columns}
        data={data?.items ?? []}
        loading={isLoading}
        pageCount={pageCount}
        pageIndex={page}
        pageSize={PAGE_SIZE}
        onPageChange={setPage}
        onRowClick={(row) => navigate(`/double-entries/${row.id}`)}
        emptyTitle="Sin doble partidas"
        emptyDescription="No se encontraron operaciones pasa mano."
      />
    </div>
  );
}
