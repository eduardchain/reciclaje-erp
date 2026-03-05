import { useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { ArrowLeft, XCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Skeleton } from "@/components/ui/skeleton";
import { PageHeader } from "@/components/shared/PageHeader";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { ConfirmDialog } from "@/components/shared/ConfirmDialog";
import { useDoubleEntry, useCancelDoubleEntry } from "@/hooks/useDoubleEntries";
import { formatCurrency, formatDate, formatWeight, formatPercentage } from "@/utils/formatters";
import { ROUTES } from "@/utils/constants";

export default function DoubleEntryDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { data: de, isLoading } = useDoubleEntry(id!);
  const cancel = useCancelDoubleEntry();
  const [showCancel, setShowCancel] = useState(false);

  if (isLoading) return <div className="space-y-4"><Skeleton className="h-8 w-64" /><Skeleton className="h-64 w-full" /></div>;
  if (!de) return <div className="text-center py-12 text-gray-500">Doble partida no encontrada</div>;

  return (
    <div className="space-y-6">
      <PageHeader title={`Doble Partida #${de.double_entry_number}`} description={`${de.material_name} - ${formatWeight(de.quantity)}`}>
        <div className="flex items-center gap-2">
          {de.status === "completed" && (
            <Button variant="outline" onClick={() => setShowCancel(true)} className="text-red-600 border-red-200 hover:bg-red-50"><XCircle className="h-4 w-4 mr-2" />Cancelar</Button>
          )}
          <Button variant="outline" onClick={() => navigate(ROUTES.DOUBLE_ENTRIES)}><ArrowLeft className="h-4 w-4 mr-2" />Volver</Button>
        </div>
      </PageHeader>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card>
          <CardContent className="pt-6">
            <dl className="space-y-2 text-sm">
              <div className="flex justify-between"><dt className="text-gray-500">Estado</dt><dd><StatusBadge status={de.status} /></dd></div>
              <div className="flex justify-between"><dt className="text-gray-500">Fecha</dt><dd>{formatDate(de.date)}</dd></div>
              <div className="flex justify-between"><dt className="text-gray-500">Material</dt><dd>{de.material_name} ({de.material_code})</dd></div>
              <div className="flex justify-between"><dt className="text-gray-500">Cantidad</dt><dd>{formatWeight(de.quantity)}</dd></div>
            </dl>
          </CardContent>
        </Card>

        <Card className="border-blue-200">
          <CardHeader className="pb-2"><CardTitle className="text-sm text-blue-700">Compra</CardTitle></CardHeader>
          <CardContent>
            <dl className="space-y-2 text-sm">
              <div className="flex justify-between"><dt className="text-gray-500">Proveedor</dt><dd>{de.supplier_name}</dd></div>
              <div className="flex justify-between"><dt className="text-gray-500">Precio Unit.</dt><dd>{formatCurrency(de.purchase_unit_price)}</dd></div>
              <div className="flex justify-between"><dt className="text-gray-500">Total</dt><dd className="font-bold">{formatCurrency(de.total_purchase_cost)}</dd></div>
            </dl>
          </CardContent>
        </Card>

        <Card className="border-green-200">
          <CardHeader className="pb-2"><CardTitle className="text-sm text-green-700">Venta</CardTitle></CardHeader>
          <CardContent>
            <dl className="space-y-2 text-sm">
              <div className="flex justify-between"><dt className="text-gray-500">Cliente</dt><dd>{de.customer_name}</dd></div>
              <div className="flex justify-between"><dt className="text-gray-500">Precio Unit.</dt><dd>{formatCurrency(de.sale_unit_price)}</dd></div>
              <div className="flex justify-between"><dt className="text-gray-500">Total</dt><dd className="font-bold">{formatCurrency(de.total_sale_amount)}</dd></div>
            </dl>
          </CardContent>
        </Card>
      </div>

      {/* Resumen Utilidad */}
      <Card className="border-2 border-green-200 bg-green-50">
        <CardContent className="pt-6 flex justify-between items-center">
          <div className="text-sm space-y-1">
            <div>Compra: {formatCurrency(de.total_purchase_cost)}</div>
            <div>Venta: {formatCurrency(de.total_sale_amount)}</div>
            <div>Margen: {formatPercentage(de.profit_margin)}</div>
          </div>
          <div className="text-right">
            <p className="text-sm text-gray-500">Utilidad</p>
            <p className={`text-3xl font-bold ${de.profit >= 0 ? "text-green-700" : "text-red-700"}`}>{formatCurrency(de.profit)}</p>
          </div>
        </CardContent>
      </Card>

      {/* Comisiones */}
      {de.commissions.length > 0 && (
        <Card>
          <CardHeader><CardTitle className="text-base">Comisiones</CardTitle></CardHeader>
          <CardContent>
            <Table>
              <TableHeader><TableRow><TableHead>Comisionista</TableHead><TableHead>Concepto</TableHead><TableHead className="text-right">Monto</TableHead></TableRow></TableHeader>
              <TableBody>
                {de.commissions.map((c) => (
                  <TableRow key={c.id}><TableCell>{c.third_party_name}</TableCell><TableCell>{c.concept}</TableCell><TableCell className="text-right font-medium">{formatCurrency(c.commission_amount)}</TableCell></TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}

      {de.notes && (
        <Card><CardContent className="pt-6"><Label className="text-gray-500">Notas</Label><p className="mt-1 text-sm">{de.notes}</p></CardContent></Card>
      )}

      <ConfirmDialog
        open={showCancel}
        onOpenChange={setShowCancel}
        title="Cancelar Doble Partida"
        description="Esto revertira la compra y venta asociadas. Esta seguro?"
        confirmLabel="Si, cancelar"
        variant="destructive"
        onConfirm={() => cancel.mutate(id!, { onSuccess: () => setShowCancel(false) })}
        loading={cancel.isPending}
      />
    </div>
  );
}
