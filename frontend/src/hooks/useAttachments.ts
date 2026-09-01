import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { attachmentService } from "@/services/attachments";
import { getApiErrorMessage } from "@/utils/formatters";
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
