/**
 * Compresion de imagenes en el navegador antes de subir (D9 del plan).
 *
 * Una foto de celular sin comprimir pesa 2-5 MB. Redimensionada a 1920px y
 * re-encodeada a JPEG 0.8 queda en ~300 KB — 10x menos — sin perder
 * legibilidad para una evidencia de calidad. Con 20 operaciones al dia y 3
 * fotos cada una, eso es la diferencia entre 5.4 GB/mes y 0.54 GB/mes.
 *
 * Ademas la subida es mucho mas rapida en el patio, que es donde peor esta la
 * senal.
 */

const MAX_DIMENSION = 1920;
const JPEG_QUALITY = 0.8;

/** Los PDF no se tocan; el resto se intenta comprimir. */
const isCompressible = (file: File) =>
  file.type.startsWith("image/") || /\.(hei[cf])$/i.test(file.name);

function loadImage(url: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = () => reject(new Error("no se pudo decodificar"));
    img.src = url;
  });
}

/**
 * Devuelve una version comprimida, o el archivo ORIGINAL si no se puede.
 *
 * Nunca falla hacia arriba: si el navegador no sabe decodificar el formato
 * (Chrome de escritorio con un HEIC, por ejemplo) el archivo crudo se sube
 * igual — el backend lo acepta y el panel muestra el fallback de icono.
 */
export async function compressImage(file: File): Promise<File> {
  if (!isCompressible(file)) return file;

  const url = URL.createObjectURL(file);
  try {
    const img = await loadImage(url);
    const scale = Math.min(1, MAX_DIMENSION / Math.max(img.width, img.height));
    const w = Math.round(img.width * scale);
    const h = Math.round(img.height * scale);

    const canvas = document.createElement("canvas");
    canvas.width = w;
    canvas.height = h;
    const ctx = canvas.getContext("2d");
    if (!ctx) return file;
    ctx.drawImage(img, 0, 0, w, h);

    const blob = await new Promise<Blob | null>((resolve) =>
      canvas.toBlob(resolve, "image/jpeg", JPEG_QUALITY),
    );
    if (!blob) return file;

    // Si comprimir no ayudo (imagen ya pequena o muy optimizada), gana el
    // original: no tiene sentido re-encodear un PNG nitido a JPEG mas pesado.
    if (blob.size >= file.size) return file;

    const newName = file.name.replace(/\.[^.]+$/, "") + ".jpg";
    return new File([blob], newName, { type: "image/jpeg" });
  } catch {
    return file;
  } finally {
    URL.revokeObjectURL(url);
  }
}
