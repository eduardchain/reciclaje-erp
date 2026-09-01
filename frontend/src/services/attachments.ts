import apiClient from "./api";
import type {
  Attachment,
  AttachmentListResponse,
  AttachmentOwnerType,
} from "@/types/attachment";

const BASE = "/api/v1/attachments";

/** El dueno viaja como un query param u otro segun el modulo. */
export const ownerParam = (type: AttachmentOwnerType) =>
  type === "purchase" ? "purchase_id" : type === "sale" ? "sale_id" : "transformation_id";

export const attachmentService = {
  list: async (
    ownerType: AttachmentOwnerType,
    ownerId: string,
  ): Promise<AttachmentListResponse> => {
    const response = await apiClient.get<AttachmentListResponse>(BASE, {
      params: { [ownerParam(ownerType)]: ownerId },
    });
    return response.data;
  },

  upload: async (
    ownerType: AttachmentOwnerType,
    ownerId: string,
    file: File,
    description?: string,
  ): Promise<Attachment> => {
    const form = new FormData();
    form.append("file", file);
    form.append(ownerParam(ownerType), ownerId);
    if (description) form.append("description", description);
    const response = await apiClient.post<Attachment>(BASE, form, {
      headers: { "Content-Type": "multipart/form-data" },
    });
    return response.data;
  },

  updateDescription: async (id: string, description: string): Promise<Attachment> => {
    const response = await apiClient.patch<Attachment>(`${BASE}/${id}`, {
      description: description || null,
    });
    return response.data;
  },

  remove: async (id: string): Promise<void> => {
    await apiClient.delete(`${BASE}/${id}`);
  },

  /**
   * D8 — el contenido se trae por blob, NUNCA con <img src={url}>: el
   * endpoint exige Authorization y X-Organization-ID, headers que el navegador
   * no manda en un <img> ni en un <a href>. Quien llame a esto es dueno de
   * revocar la URL que crea (revokeObjectURL).
   */
  fetchBlob: async (id: string): Promise<Blob> => {
    const response = await apiClient.get(`${BASE}/${id}/download`, {
      responseType: "blob",
    });
    return response.data as Blob;
  },

  /**
   * Dispara la descarga con el nombre original.
   *
   * La revocacion va diferida a proposito: revocar la object URL en la misma
   * vuelta del event loop que el click cancela la descarga en Safari — el
   * navegador todavia no leyo el blob. Es un fallo que ningun gate ve porque
   * solo existe dentro del navegador.
   */
  download: async (id: string, filename: string): Promise<void> => {
    const blob = await attachmentService.fetchBlob(id);
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 10_000);
  },
};
