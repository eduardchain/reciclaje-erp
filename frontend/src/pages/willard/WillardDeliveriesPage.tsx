import { useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { Plus, Truck } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { PageHeader } from "@/components/shared/PageHeader";
import { EmptyState } from "@/components/shared/EmptyState";
import { usePermissions } from "@/hooks/usePermissions";
import { useScrollRestoration, saveScroll } from "@/hooks/useScrollRestoration";
import { useWillardDeliveries } from "@/hooks/useWillardDeliveries";
import { formatDate, formatCurrency, formatWeight } from "@/utils/formatters";
import { cn } from "@/utils";
import {
  DELIVERY_STATUS_COLORS, DELIVERY_STATUS_LABELS,
  DELIVERY_TYPE_COLORS, DELIVERY_TYPE_LABELS, num,
  type WillardDelivery, type WillardDeliveryStatus, type WillardDeliveryType,
} from "@/types/willard-delivery";
import { CrucibleChargesSection } from "./CrucibleChargesSection";

export function DeliveryTypeBadge({ type }: { type: WillardDeliveryType }) {
  return (
    <Badge className={cn("font-medium", DELIVERY_TYPE_COLORS[type])} variant="secondary">
      {DELIVERY_TYPE_LABELS[type]}
    </Badge>
  );
}

export function DeliveryStatusBadge({ status }: { status: WillardDeliveryStatus }) {
  return (
    <Badge className={cn("font-medium", DELIVERY_STATUS_COLORS[status])} variant="secondary">
      {DELIVERY_STATUS_LABELS[status]}
    </Badge>
  );
}

const TABS = [
  { value: "all", label: "Todas" },
  { value: "draft", label: "Registradas" },
  { value: "liquidated", label: "Liquidadas" },
] as const;

// Segunda fila de tabs: el TIPO. El destino cambia por tipo (un cliente, Willard,
// o el crisol de la propia planta), asi que es la primera pregunta al buscar.
// "crisol" NO es un tipo de salida: es el 4º ítem que Hugo pidió (28-ago) y
// vive en su propia tabla (documentos de crisol, #107 D2). Comparte la pantalla
// porque para el usuario es "otra salida de plomo de planta".
const TYPE_TABS: { value: "all" | WillardDeliveryType | "crisol"; label: string }[] = [
  { value: "all", label: "Todos los tipos" },
  { value: "venta", label: DELIVERY_TYPE_LABELS.venta },
  { value: "abono_bateria", label: DELIVERY_TYPE_LABELS.abono_bateria },
  { value: "abono_material", label: DELIVERY_TYPE_LABELS.abono_material },
  { value: "crisol", label: "Crisol" },
];

export default function WillardDeliveriesPage() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const { hasPermission } = usePermissions();
  const [page] = useState(1);

  const tab = searchParams.get("tab") ?? "all";
  const typeTab = searchParams.get("type") ?? "all";
  const isCrisol = typeTab === "crisol";
  const { data, isLoading } = useWillardDeliveries(
    {
      status: tab === "all" ? undefined : tab,
      delivery_type: typeTab === "all" || isCrisol ? undefined : typeTab,
      page,
      page_size: 50,
    },
    !isCrisol,
  );

  // El hook de scroll va ANTES de cualquier return condicional (#93 bloqueante a)
  useScrollRestoration(!isLoading);

  const items = data?.items ?? [];
  const pendientes = items.filter((d) => d.status === "draft" || d.status === "reviewed").length;

  const open = (d: WillardDelivery) => {
    saveScroll(window.location.pathname + window.location.search);
    navigate(`/willard-deliveries/${d.id}`);
  };

  return (
    <div className="space-y-4">
      <PageHeader
        title="Salidas de Plomo"
        description="Ventas de plomo, abonos a Willard y control del crisol, desde planta"
      >
        {hasPermission("sales.create") && !isCrisol && (
          <Button onClick={() => navigate("/willard-deliveries/new")} className="w-full sm:w-auto">
            <Plus className="h-4 w-4 mr-2" /> Nueva Salida
          </Button>
        )}
        {hasPermission("sales.create") && isCrisol && (
          <Button onClick={() => navigate("/willard-deliveries/crisol/new")} className="w-full sm:w-auto">
            <Plus className="h-4 w-4 mr-2" /> Nuevo documento de crisol
          </Button>
        )}
      </PageHeader>

      {!isCrisol && (
      <div className="overflow-x-auto -mx-3 px-3 sm:mx-0 sm:px-0">
        <Tabs
          value={tab}
          onValueChange={(v) =>
            setSearchParams((prev) => {
              const next = new URLSearchParams(prev);
              if (v === "all") next.delete("tab");
              else next.set("tab", v);
              return next;
            })
          }
        >
          <TabsList className="inline-flex w-max sm:w-auto sm:flex-wrap">
            {TABS.map((t) => (
              <TabsTrigger key={t.value} value={t.value}>
                {t.label}
                {t.value === "draft" && pendientes > 0 && tab === "all" ? null : null}
              </TabsTrigger>
            ))}
          </TabsList>
        </Tabs>
      </div>
      )}
      <div className="overflow-x-auto -mx-3 px-3 sm:mx-0 sm:px-0">
        <Tabs
          value={typeTab}
          onValueChange={(v) =>
            setSearchParams((prev) => {
              const next = new URLSearchParams(prev);
              if (v === "all") next.delete("type");
              else next.set("type", v);
              return next;
            })
          }
        >
          <TabsList className="inline-flex w-max sm:w-auto sm:flex-wrap">
            {TYPE_TABS.map((t) => (
              <TabsTrigger key={t.value} value={t.value}>{t.label}</TabsTrigger>
            ))}
          </TabsList>
        </Tabs>
      </div>

      {isCrisol ? (
        <CrucibleChargesSection />
      ) : isLoading ? (
        <Card><CardContent className="p-8 text-center text-slate-500">Cargando…</CardContent></Card>
      ) : items.length === 0 ? (
        <EmptyState
          icon={<Truck className="h-10 w-10 text-slate-300" />}
          title="Sin salidas"
          description="Todavía no hay entregas de plomo registradas."
        />
      ) : (
        <>
          {/* Desktop */}
          <Card className="hidden md:block">
            <CardContent className="p-0">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>#</TableHead>
                    <TableHead>Fecha</TableHead>
                    <TableHead>Tipo</TableHead>
                    <TableHead>Bodega</TableHead>
                    <TableHead className="text-right">Kg plomo</TableHead>
                    <TableHead className="text-right">Maquila + Flete</TableHead>
                    <TableHead>Estado</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {items.map((d) => (
                    <TableRow key={d.id} className="cursor-pointer" onClick={() => open(d)}>
                      <TableCell className="font-medium whitespace-nowrap">{d.label}</TableCell>
                      <TableCell>{formatDate(d.date)}</TableCell>
                      <TableCell><DeliveryTypeBadge type={d.delivery_type} /></TableCell>
                      <TableCell>{d.warehouse_name ?? "—"}</TableCell>
                      <TableCell className="text-right tabular-nums">
                        {formatWeight(num(d.total_kg_lead), "kg")}
                      </TableCell>
                      <TableCell className="text-right tabular-nums">
                        {formatCurrency(num(d.maquila_amount) + num(d.freight_amount))}
                      </TableCell>
                      <TableCell><DeliveryStatusBadge status={d.status} /></TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>

          {/* Mobile */}
          <div className="md:hidden space-y-2">
            {items.map((d) => (
              <Card key={d.id} className="cursor-pointer" onClick={() => open(d)}>
                <CardContent className="p-3 space-y-2">
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-semibold">{d.label}</span>
                    <DeliveryStatusBadge status={d.status} />
                  </div>
                  <div className="flex items-center justify-between gap-2 text-sm">
                    <DeliveryTypeBadge type={d.delivery_type} />
                    <span className="text-slate-500">{formatDate(d.date)}</span>
                  </div>
                  <div className="flex justify-between gap-3 text-sm">
                    <span className="text-slate-500">Kg plomo</span>
                    <span className="tabular-nums">{formatWeight(num(d.total_kg_lead), "kg")}</span>
                  </div>
                  <div className="flex justify-between gap-3 text-sm">
                    <span className="text-slate-500">Maquila + Flete</span>
                    <span className="tabular-nums">
                      {formatCurrency(num(d.maquila_amount) + num(d.freight_amount))}
                    </span>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
