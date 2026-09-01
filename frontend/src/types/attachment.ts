export type AttachmentOwnerType = "purchase" | "sale" | "transformation";

export interface Attachment {
  id: string;
  owner_type: AttachmentOwnerType;
  owner_id: string;
  original_filename: string;
  content_type: string;
  size_bytes: number;
  description: string | null;
  uploaded_by: string | null;
  uploaded_by_name: string | null;
  created_at: string;
}

export interface AttachmentListResponse {
  items: Attachment[];
  total: number;
}

/** Espejo de ALLOWED_ATTACHMENT_EXTENSIONS del backend. */
export const ATTACHMENT_ACCEPT = ".jpg,.jpeg,.png,.gif,.webp,.heic,.heif,.pdf";
export const MAX_ATTACHMENTS_PER_OWNER = 10;
export const MAX_ATTACHMENT_SIZE = 5 * 1024 * 1024;
