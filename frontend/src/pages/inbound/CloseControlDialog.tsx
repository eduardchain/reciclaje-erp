import { ConfirmDialog } from "@/components/shared/ConfirmDialog";
import { useCloseInboundOrder } from "@/hooks/useInboundOrders";
import type { InboundOrderResponse } from "@/types/inbound-order";

/** Documentos de control: cierre sin valor de una Entrada cuyas lineas son
 *  TODAS de control (estibas, tubulares, electrolito a $0). Un solo dialogo
 *  para el detalle y la fila de la lista (O1 de QA 2). */
export function CloseControlDialog({
  order,
  onClose,
}: {
  order: InboundOrderResponse | null;
  onClose: () => void;
}) {
  const closeOrder = useCloseInboundOrder();
  return (
    <ConfirmDialog
      open={!!order}
      onOpenChange={(o) => {
        if (!o) onClose();
      }}
      title={`Cerrar sin valor la Entrada #${order?.order_number ?? ""}`}
      description={
        "Todos sus materiales son de control. La entrada queda registrada con su número" +
        (order?.remission_number ? ` y su remisión ${order.remission_number}` : "") +
        ", pero no crea compras, no mueve inventario ni plata y sale de la bandeja. " +
        "Si fue un error, se puede reabrir."
      }
      confirmLabel="Cerrar sin valor"
      loading={closeOrder.isPending}
      onConfirm={() => {
        if (!order) return;
        closeOrder.mutate(order.id, { onSuccess: onClose });
      }}
    />
  );
}
