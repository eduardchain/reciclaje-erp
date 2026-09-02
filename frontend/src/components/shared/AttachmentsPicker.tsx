import { useEffect, useState } from "react";
import { FileText, Paperclip, X } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import {
  ATTACHMENT_ACCEPT,
  MAX_ATTACHMENTS_PER_OWNER,
  MAX_ATTACHMENT_SIZE,
} from "@/types/attachment";

interface Props {
  files: File[];
  onChange: (files: File[]) => void;
  disabled?: boolean;
}

const EXTS = ATTACHMENT_ACCEPT.split(",").map((e) => e.replace(".", "").toLowerCase());

const prettySize = (bytes: number) =>
  bytes >= 1024 * 1024
    ? `${(bytes / (1024 * 1024)).toFixed(1)} MB`
    : `${Math.max(1, Math.round(bytes / 1024))} KB`;

/** Miniatura desde el File local (todavia no hay nada en el servidor). */
function LocalThumb({ file }: { file: File }) {
  const [url, setUrl] = useState<string | null>(null);
  const renderable = file.type.startsWith("image/") && !/\.(hei[cf])$/i.test(file.name);

  useEffect(() => {
    if (!renderable) return;
    const objectUrl = URL.createObjectURL(file);
    setUrl(objectUrl);
    return () => URL.revokeObjectURL(objectUrl);
  }, [file, renderable]);

  if (!renderable || !url) {
    return (
      <div className="flex h-16 w-full items-center justify-center rounded bg-slate-100 text-slate-400">
        <FileText className="h-6 w-6" />
      </div>
    );
  }
  return (
    <img src={url} alt={file.name} className="h-16 w-full rounded object-cover" />
  );
}

/**
 * Elegir archivos DENTRO de un formulario de creacion.
 *
 * Un adjunto necesita un dueno y la operacion todavia no existe, asi que aca
 * los archivos solo se acumulan en memoria; el formulario los sube apenas la
 * operacion nace (`uploadPendingAttachments`). El panel del detalle
 * (`AttachmentsPanel`) sigue sirviendo para lo que llega despues — la remision
 * que aparece dos dias mas tarde.
 *
 * La validacion de extension y tamano se hace aca, al elegir: enterarse de que
 * el archivo no servia DESPUES de guardar la compra seria el peor momento.
 */
export function AttachmentsPicker({ files, onChange, disabled }: Props) {
  const [inputKey, setInputKey] = useState(0);

  const handleSelect = (selected: FileList | null) => {
    if (!selected?.length) return;
    const room = MAX_ATTACHMENTS_PER_OWNER - files.length;
    const accepted: File[] = [];

    for (const file of Array.from(selected)) {
      if (accepted.length >= room) {
        toast.warning(
          `Maximo ${MAX_ATTACHMENTS_PER_OWNER} archivos por operacion.`,
        );
        break;
      }
      const ext = file.name.split(".").pop()?.toLowerCase() ?? "";
      if (!EXTS.includes(ext)) {
        toast.error(`"${file.name}": tipo de archivo no permitido.`);
        continue;
      }
      // El tope se revisa contra el archivo ORIGINAL y solo para NO-imagenes:
      // a una imagen la dejamos pasar porque la compresion (que corre al subir)
      // casi siempre la achica. Queda un borde conocido: un HEIC de mas de 5MB
      // en un navegador que no sabe decodificarlo (Chrome de escritorio) no se
      // comprime, pasa por aca y lo rechaza el servidor — el usuario lo ve en
      // el toast de "N no se pudieron adjuntar" y lo reintenta desde el
      // detalle, donde el mensaje si nombra el tamano. Es el precio de no
      // rechazar aca fotos que habrian entrado perfectamente comprimidas.
      if (file.size > MAX_ATTACHMENT_SIZE && !file.type.startsWith("image/")) {
        toast.error(`"${file.name}" pesa ${prettySize(file.size)}; el maximo es 5 MB.`);
        continue;
      }
      accepted.push(file);
    }

    if (accepted.length) onChange([...files, ...accepted]);
    setInputKey((k) => k + 1); // permite volver a elegir el mismo archivo
  };

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between gap-2">
        <p className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-slate-500">
          <Paperclip className="h-3.5 w-3.5" />
          Archivos adjuntos
          {files.length > 0 && (
            <span className="normal-case tracking-normal text-slate-400">
              {files.length}/{MAX_ATTACHMENTS_PER_OWNER}
            </span>
          )}
        </p>
        <label className="shrink-0">
          <input
            key={inputKey}
            type="file"
            multiple
            accept={ATTACHMENT_ACCEPT}
            className="hidden"
            disabled={disabled || files.length >= MAX_ATTACHMENTS_PER_OWNER}
            onChange={(e) => handleSelect(e.target.files)}
          />
          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={disabled || files.length >= MAX_ATTACHMENTS_PER_OWNER}
            asChild
          >
            <span className="cursor-pointer">Elegir archivos</span>
          </Button>
        </label>
      </div>

      {files.length === 0 ? (
        <p className="text-xs text-slate-400">
          Evidencias de calidad, remisiones. Se suben al guardar; tambien se
          pueden agregar despues desde el detalle.
        </p>
      ) : (
        <div className="grid grid-cols-3 gap-2 sm:grid-cols-4 md:grid-cols-6">
          {files.map((file, i) => (
            <div
              key={`${file.name}-${i}`}
              className="relative rounded border border-slate-200 p-1.5"
            >
              <LocalThumb file={file} />
              <p className="mt-1 truncate text-[11px] text-slate-600" title={file.name}>
                {file.name}
              </p>
              <p className="text-[10px] text-slate-400">{prettySize(file.size)}</p>
              <button
                type="button"
                className="absolute -right-1.5 -top-1.5 rounded-full bg-white p-0.5 text-slate-400 shadow hover:text-red-600"
                onClick={() => onChange(files.filter((_, idx) => idx !== i))}
                aria-label={`Quitar ${file.name}`}
              >
                <X className="h-3.5 w-3.5" />
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
