import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { attachmentService } from "@/services/attachments";
import { getApiErrorMessage } from "@/utils/formatters";
import { compressImage } from "@/utils/imageCompression";
import type { AttachmentOwnerType } from "@/types/attachment";

const key = (ownerType: AttachmentOwnerType, ownerId: string) => [
  "attachments",
  ownerType,
  ownerId,
];

export function useAttachments(
  ownerType: AttachmentOwnerType,
  ownerId: string | undefined,
) {
  return useQuery({
    queryKey: key(ownerType, ownerId ?? ""),
    queryFn: () => attachmentService.list(ownerType, ownerId!),
    enabled: !!ownerId,
  });
}

export function useUploadAttachment(
  ownerType: AttachmentOwnerType,
  ownerId: string,
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ file, description }: { file: File; description?: string }) =>
      attachmentService.upload(ownerType, ownerId, file, description),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: key(ownerType, ownerId) });
    },
    onError: (error: unknown) => {
      toast.error(getApiErrorMessage(error, "Error al subir el archivo"));
    },
  });
}

export function useUpdateAttachmentDescription(
  ownerType: AttachmentOwnerType,
  ownerId: string,
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, description }: { id: string; description: string }) =>
      attachmentService.updateDescription(id, description),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: key(ownerType, ownerId) });
    },
    onError: (error: unknown) => {
      toast.error(getApiErrorMessage(error, "Error al guardar la nota"));
    },
  });
}

export function useDeleteAttachment(
  ownerType: AttachmentOwnerType,
  ownerId: string,
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => attachmentService.remove(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: key(ownerType, ownerId) });
      toast.success("Archivo eliminado");
    },
    onError: (error: unknown) => {
      toast.error(getApiErrorMessage(error, "Error al eliminar el archivo"));
    },
  });
}

/**
 * Sube los archivos que se eligieron en un formulario de creacion, ya con el
 * dueno recien nacido.
 *
 * 🔴 NUNCA hace fallar la operacion: para cuando esto corre, la compra (o la
 * venta, o la transformacion) YA existe y ya movio inventario y saldos. Un
 * archivo que no sube es una molestia — se reintenta desde el detalle —, no un
 * motivo para dejar al usuario creyendo que no guardo nada.
 */
export async function uploadPendingAttachments(
  ownerType: AttachmentOwnerType,
  ownerId: string,
  files: File[],
): Promise<void> {
  if (!files.length) return;

  let fallaron = 0;
  for (const raw of files) {
    try {
      const file = await compressImage(raw);
      await attachmentService.upload(ownerType, ownerId, file);
    } catch {
      fallaron += 1;
    }
  }

  if (fallaron > 0) {
    toast.warning(
      fallaron === files.length
        ? "La operacion se guardo, pero los archivos no se pudieron adjuntar. Podes hacerlo desde el detalle."
        : `La operacion se guardo. ${fallaron} de ${files.length} archivos no se pudieron adjuntar; podes reintentarlo desde el detalle.`,
    );
  }
}
