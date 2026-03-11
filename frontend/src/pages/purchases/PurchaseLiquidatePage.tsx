import { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { ArrowLeft, CheckCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { PageHeader } from "@/components/shared/PageHeader";
import { PriceSuggestion } from "@/components/shared/PriceSuggestion";
import { usePurchase, useLiquidatePurchase } from "@/hooks/usePurchases";
import { usePriceSuggestions } from "@/hooks/usePriceSuggestions";
import { MoneyInput } from "@/components/shared/MoneyInput";
import { formatCurrency, formatDate, formatWeight } from "@/utils/formatters";

interface LiquidationLine {
  line_id: string;
  material_id: string;
  material_name: string;
  material_code: string;
  warehouse_name: string | null;
  quantity: number;
  unit_price: number;
}

export default function PurchaseLiquidatePage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { data: purchase, isLoading } = usePurchase(id!);
  const { getSuggestedPrice } = usePriceSuggestions();
  const liquidate = useLiquidatePurchase();

  const [lines, setLines] = useState<LiquidationLine[]>([]);

  // Inicializar lineas desde la compra cargada
  useEffect(() => {
    if (purchase && lines.length === 0) {
      setLines(
        purchase.lines.map((line) => {
          // Si el precio es 0, intentar pre-llenar desde lista de precios
          let price = line.unit_price;
          if (price === 0) {
            const suggested = getSuggestedPrice(line.material_id, "purchase");
            if (suggested) price = suggested;
          }
          return {
            line_id: line.id,
            material_id: line.material_id,
            material_name: line.material_name,
            material_code: line.material_code,
            warehouse_name: line.warehouse_name,
            quantity: line.quantity,
            unit_price: price,
          };
        }),
      );
    }
  }, [purchase, getSuggestedPrice, lines.length]);

  // Redirigir si la compra no es liquidable
  useEffect(() => {
    if (purchase && (purchase.status !== "registered" || purchase.double_entry_id)) {
      navigate(`/purchases/${id}`, { replace: true });
    }
  }, [purchase, id, navigate]);

  const updatePrice = (lineId: string, price: number) => {
    setLines((prev) =>
      prev.map((l) => (l.line_id === lineId ? { ...l, unit_price: price } : l)),
    );
  };

  const total = lines.reduce((sum, l) => sum + l.quantity * l.unit_price, 0);
  const allPricesValid = lines.every((l) => l.unit_price > 0);
  const canSubmit = allPricesValid && lines.length > 0;

  const handleSubmit = () => {
    if (!canSubmit || !id) return;
    liquidate.mutate(
      {
        id,
        data: {
          lines: lines.map((l) => ({
            line_id: l.line_id,
            unit_price: l.unit_price,
          })),
        },
      },
      {
        onSuccess: () => {
          navigate(`/purchases/${id}`);
        },
      },
    );
  };

  if (isLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  if (!purchase) {
    return <div className="text-center py-12 text-slate-500">Compra no encontrada</div>;
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title={`Liquidar Compra #${purchase.purchase_number}`}
        description={`Proveedor: ${purchase.supplier_name} | Fecha: ${formatDate(purchase.date)}`}
      >
        <Button variant="outline" onClick={() => navigate(`/purchases/${id}`)}>
          <ArrowLeft className="h-4 w-4 mr-2" />
          Volver
        </Button>
      </PageHeader>

      {/* Info resumida */}
      <Card className="shadow-sm border-t-[3px] border-t-amber-400">
        <CardContent className="pt-6">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
            <div>
              <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">Proveedor</span>
              <p className="font-medium">{purchase.supplier_name}</p>
            </div>
            <div>
              <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">Fecha</span>
              <p>{formatDate(purchase.date)}</p>
            </div>
            {purchase.vehicle_plate && (
              <div>
                <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">Placa</span>
                <p>{purchase.vehicle_plate}</p>
              </div>
            )}
            {purchase.invoice_number && (
              <div>
                <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">Factura</span>
                <p>{purchase.invoice_number}</p>
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Lineas con precios editables */}
      <Card className="shadow-sm">
        <CardHeader>
          <CardTitle className="text-sm font-semibold uppercase tracking-wider text-slate-500">
            Confirmar Precios
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-0">
          {lines.map((line, idx) => (
            <div
              key={line.line_id}
              className={`grid grid-cols-12 gap-2 items-end pb-8 mb-3 relative ${idx < lines.length - 1 ? "border-b border-slate-100" : ""}`}
            >
              <div className="col-span-3">
                {idx === 0 && <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Material</Label>}
                <p className="h-10 flex items-center text-sm">
                  <span className="font-medium">{line.material_name}</span>
                  <span className="text-slate-400 ml-2 text-xs">{line.material_code}</span>
                </p>
              </div>
              <div className="col-span-2">
                {idx === 0 && <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Bodega</Label>}
                <p className="h-10 flex items-center text-sm text-slate-600">
                  {line.warehouse_name ?? "-"}
                </p>
              </div>
              <div className="col-span-2">
                {idx === 0 && <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Cantidad (kg)</Label>}
                <p className="h-10 flex items-center text-sm tabular-nums">
                  {formatWeight(line.quantity)}
                </p>
              </div>
              <div className="col-span-3 relative">
                {idx === 0 && <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Precio Unit. *</Label>}
                <MoneyInput
                  value={line.unit_price}
                  onChange={(v) => updatePrice(line.line_id, v)}
                  placeholder="0"
                  className={line.unit_price <= 0 ? "border-red-300" : ""}
                />
                <div className="absolute left-0 w-max" style={{ top: "100%" }}>
                  <PriceSuggestion
                    suggestedPrice={getSuggestedPrice(line.material_id, "purchase")}
                    onApply={(p) => updatePrice(line.line_id, p)}
                  />
                  {line.unit_price <= 0 && (
                    <p className="text-xs text-red-500 mt-0.5">El precio debe ser mayor a 0</p>
                  )}
                </div>
              </div>
              <div className="col-span-2 text-right">
                {idx === 0 && <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Total</Label>}
                <p className="h-10 flex items-center justify-end text-sm font-medium tabular-nums">
                  {formatCurrency(line.quantity * line.unit_price)}
                </p>
              </div>
            </div>
          ))}

          <div className="bg-slate-50 rounded-lg p-3 mt-2">
            <div className="flex justify-end">
              <span className="text-lg font-bold">Total: {formatCurrency(total)}</span>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Acciones */}
      <div className="sticky bottom-0 bg-white/95 backdrop-blur-sm border-t border-slate-100 py-4 -mx-6 px-6 mt-6">
        <div className="flex justify-end gap-2">
          <Button variant="outline" onClick={() => navigate(`/purchases/${id}`)}>
            Cancelar
          </Button>
          <Button
            onClick={handleSubmit}
            disabled={!canSubmit || liquidate.isPending}
            className="bg-emerald-600 hover:bg-emerald-700"
          >
            <CheckCircle className="h-4 w-4 mr-2" />
            {liquidate.isPending ? "Liquidando..." : "Confirmar Liquidacion"}
          </Button>
        </div>
      </div>
    </div>
  );
}
