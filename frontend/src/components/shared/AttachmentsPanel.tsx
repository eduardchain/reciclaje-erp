import { useEffect, useRef, useState } from "react";
import { FileText, Loader2, Paperclip, Trash2, Upload, X } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/shared/ConfirmDialog";
import {
  useAttachments,
  useDeleteAttachment,
  useUpdateAttachmentDescription,
  useUploadAttachment,
} from "@/hooks/useAttachments";
import { attachmentService } from "@/services/attachments";
import { compressImage } from "@/utils/imageCompression";
import {
  ATTACHMENT_ACCEPT,
  MAX_ATTACHMENTS_PER_OWNER,
  MAX_ATTACHMENT_SIZE,
} from "@/types/attachment";
import type { Attachment, AttachmentOwnerType } from "@/types/attachment";

interface Props {
  ownerType: AttachmentOwnerType;
  ownerId: string;
  canUpload: boolean;
  canDelete: boolean;
}

/** Formatos que el navegador pinta seguro. HEIC crudo NO (N2 del plan). */
const isRenderable = (contentType: string, filename: string) =>
  contentType.startsWith("image/") && !/\.(hei[cf])$/i.test(filename);

const prettySize = (bytes: number) =>
  bytes >= 1024 * 1024
    ? `${(bytes / (1024 * 1024)).toFixed(1)} MB`
    : `${Math.max(1, Math.round(bytes / 1024))} KB`;

/**
 * Miniatura de un adjunto.
 *
 * D8 — el contenido se pide por blob (el endpoint exige headers que un
 * <img src> no manda) y la object URL se revoca al desmontar: sin eso, abrir
 * veinte detalles con fotos deja los blobs vivos en memoria de la pestana.
 */
function Thumb({ att, onOpen }: { att: Attachment; onOpen: (url: string) => void }) {
  const [url, setUrl] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);
  const renderable = isRenderable(att.content_type, att.original_filename);

  useEffect(() => {
    if (!renderable) return;
    let objectUrl: string | null = null;
    let cancelled = false;
    attachmentService
      .fetchBlob(att.id)
      .then((blob) => {
        if (cancelled) return;
        objectUrl = URL.createObjectURL(blob);
        setUrl(objectUrl);
      })
      .catch(() => !cancelled && setFailed(true));
    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [att.id, renderable]);

  // N2 — fallback para lo que el navegador no pinta: PDFs, HEIC crudo de un
  // iPhone que no paso por la compresion, o una descarga que fallo.
  if (!renderable || failed) {
    return (
      <div className="flex h-24 w-full items-center justify-center rounded bg-slate-100 text-slate-400">
        <FileText className="h-8 w-8" />
      </div>
    );
  }
  if (!url) {
    return (
      <div className="flex h-24 w-full items-center justify-center rounded bg-slate-50">
        <Loader2 className="h-4 w-4 animate-spin text-slate-300" />
      </div>
    );
  }
  return (
    <button
      type="button"
      onClick={() => onOpen(url)}
      className="block h-24 w-full overflow-hidden rounded focus:outline-none focus:ring-2 focus:ring-emerald-400"
    >
      <img
        src={url}
        alt={att.original_filename}
        className="h-full w-full object-cover transition hover:opacity-90"
      />
    </button>
  );
}

export function AttachmentsPanel({ ownerType, ownerId, canUpload, canDelete }: Props) {
  const { data, isLoading } = useAttachments(ownerType, ownerId);
  const upload = useUploadAttachment(ownerType, ownerId);
  const remove = useDeleteAttachment(ownerType, ownerId);
  const rename = useUpdateAttachmentDescription(ownerType, ownerId);
  const [editing, setEditing] = useState<string | null>(null);
  const [noteDraft, setNoteDraft] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const [toDelete, setToDelete] = useState<Attachment | null>(null);
  const [preview, setPreview] = useState<string | null>(null);

  const items = data?.items ?? [];
  const full = items.length >= MAX_ATTACHMENTS_PER_OWNER;

  const handleFiles = async (files: FileList | null) => {
    if (!files?.length) return;
    const room = MAX_ATTACHMENTS_PER_OWNER - items.length;
    const picked = Array.from(files).slice(0, Math.max(0, room));
    if (picked.length < files.length) {
      toast.warning(
        `Solo caben ${room} archivo(s) mas: el maximo es ${MAX_ATTACHMENTS_PER_OWNER} por operacion.`,
      );
    }

    setBusy(true);
    try {
      for (const raw of picked) {
        const file = await compressImage(raw);
        if (file.size > MAX_ATTACHMENT_SIZE) {
          toast.error(
            `"${raw.name}" pesa ${prettySize(file.size)} y el maximo es 5 MB.`,
          );
          continue;
        }
        try {
          await upload.mutateAsync({ file });
        } catch {
          // Un archivo que falla no puede llevarse el resto del lote: quien
          // sube 5 fotos del patio espera que entren las 4 que si podian.
          // El hook ya mostro el toast con el motivo.
        }
      }
    } finally {
      setBusy(false);
      if (inputRef.current) inputRef.current.value = "";
    }
  };

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between gap-2">
        <h3 className="flex items-center gap-2 text-sm font-semibold text-slate-700">
          <Paperclip className="h-4 w-4" />
          Archivos adjuntos
          {items.length > 0 && (
            <span className="text-xs font-normal text-slate-400">
              {items.length}/{MAX_ATTACHMENTS_PER_OWNER}
            </span>
          )}
        </h3>
        {canUpload && (
          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={busy || full}
            onClick={() => inputRef.current?.click()}
            className="w-full sm:w-auto"
          >
            {busy ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <Upload className="mr-2 h-4 w-4" />
            )}
            {full ? "Limite alcanzado" : "Adjuntar"}
          </Button>
        )}
      </div>

      {/*
        N3 — `multiple` si, `capture` NO: `capture="environment"` fuerza la
        camara y SUPRIME la galeria, o sea que no se podria adjuntar la foto
        que se tomo hace un rato. El picker del celular ya ofrece la camara
        como primera opcion sin el atributo.
      */}
      <input
        ref={inputRef}
        type="file"
        multiple
        accept={ATTACHMENT_ACCEPT}
        className="hidden"
        onChange={(e) => handleFiles(e.target.files)}
      />

      {isLoading ? (
        <p className="text-sm text-slate-400">Cargando adjuntos...</p>
      ) : items.length === 0 ? (
        <p className="text-sm text-slate-400">
          Sin archivos adjuntos.
          {canUpload && " Evidencias de calidad, remisiones, fotos del material."}
        </p>
      ) : (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4">
          {items.map((att) => (
            <div
              key={att.id}
              className="group relative rounded border border-slate-200 p-2"
            >
              <Thumb att={att} onOpen={setPreview} />
              <div className="mt-1.5">
                <p
                  className="truncate text-xs font-medium text-slate-700"
                  title={att.original_filename}
                >
                  {att.original_filename}
                </p>
                <p className="text-[11px] text-slate-400">
                  {prettySize(att.size_bytes)}
                  {att.uploaded_by_name ? ` · ${att.uploaded_by_name}` : ""}
                </p>
                {editing === att.id ? (
                  <input
                    autoFocus
                    value={noteDraft}
                    onChange={(e) => setNoteDraft(e.target.value)}
                    maxLength={200}
                    placeholder="Nota: remision, calidad..."
                    className="mt-0.5 w-full rounded border border-emerald-400 px-1 py-0.5 text-[11px] focus:outline-none"
                    onBlur={() => {
                      if (noteDraft !== (att.description ?? "")) {
                        rename.mutate({ id: att.id, description: noteDraft });
                      }
                      setEditing(null);
                    }}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") e.currentTarget.blur();
                      if (e.key === "Escape") setEditing(null);
                    }}
                  />
                ) : (
                  canUpload ? (
                    <button
                      type="button"
                      className="block max-w-full truncate text-left text-[11px] text-slate-500 hover:text-emerald-700"
                      title={att.description || "Agregar una nota"}
                      onClick={() => {
                        setNoteDraft(att.description ?? "");
                        setEditing(att.id);
                      }}
                    >
                      {att.description || "+ nota"}
                    </button>
                  ) : (
                    att.description && (
                      <p className="truncate text-[11px] text-slate-500" title={att.description}>
                        {att.description}
                      </p>
                    )
                  )
                )}
              </div>
              <div className="mt-1.5 flex items-center gap-2">
                <button
                  type="button"
                  className="text-[11px] text-emerald-700 hover:underline"
                  onClick={() =>
                    attachmentService.download(att.id, att.original_filename)
                  }
                >
                  Descargar
                </button>
                {canDelete && (
                  <button
                    type="button"
                    className="ml-auto text-slate-300 hover:text-red-600"
                    onClick={() => setToDelete(att)}
                    aria-label={`Eliminar ${att.original_filename}`}
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {preview && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-4"
          onClick={() => setPreview(null)}
        >
          <button
            type="button"
            className="absolute right-4 top-4 text-white/80 hover:text-white"
            onClick={() => setPreview(null)}
            aria-label="Cerrar"
          >
            <X className="h-6 w-6" />
          </button>
          <img
            src={preview}
            alt="Vista previa"
            className="max-h-full max-w-full object-contain"
          />
        </div>
      )}

      <ConfirmDialog
        open={!!toDelete}
        onOpenChange={(open) => !open && setToDelete(null)}
        title="Eliminar archivo"
        description={`Se eliminara "${toDelete?.original_filename}" de forma permanente.`}
        confirmLabel="Eliminar"
        variant="destructive"
        onConfirm={() => {
          if (toDelete) remove.mutate(toDelete.id);
          setToDelete(null);
        }}
      />
    </div>
  );
}
