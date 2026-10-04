export type User = {
  id: number;
  username: string;
};

export type DocumentType = {
  doc_type: string;
  display_name: string;
};

export type DocumentStatus = "pending_review" | "reviewed";

export type DocumentSummary = {
  id: number;
  doc_type: string;
  type_name: string;
  full_name: string | null;
  cpf: string | null;
  status: DocumentStatus;
  confidence: number | null;
  processed_at: string;
  thumbnail_url: string | null;
};

export type ImageInfo = {
  id: number;
  side: string;
  kind: string;
  thumbnail_url: string;
  full_url: string;
  original_url: string;
};

export type FieldSection = "personal" | "document" | "extra";

export type Field = {
  name: string;
  label: string;
  kind: string;
  section: FieldSection;
  value: string;
  confidence: number | null;
  issues: string[];
};

export type DocumentDetail = DocumentSummary & {
  reviewed_manually: boolean;
  type_detected: boolean;
  notes: string[];
  fields: Field[];
  pages: ImageInfo[];
  crops: ImageInfo[];
  raw_text: string;
  person_id: number | null;
  image_count: number;
};

export type PersonStatus = DocumentStatus | null;

export type Person = {
  id: number;
  full_name: string | null;
  cpf: string | null;
  birth_date: string | null;
  status: DocumentStatus | null;
  doc_types: string[];
  documents: number;
  images: number;
  created_at: string;
  updated_at: string;
};

export type PersonDetail = Person & {
  mother_name: string | null;
  father_name: string | null;
  birthplace: string | null;
  document_list: DocumentSummary[];
  other_data: OtherData[];
};

export type PageResult<T> = {
  items: T[];
  total: number;
  page: number;
  page_size: number;
};

export type AuditEntry = {
  id: number;
  occurred_at: string;
  username: string | null;
  action: string;
  entity: string;
  entity_id: number | null;
  details: string | null;
  ip_address: string | null;
};

export type SystemInfo = {
  ocr_engine: string;
  ocr_device: string;
  encrypted_storage: boolean;
  max_upload_mb: number;
};

export type OtherData = {
  label: string;
  value: string;
  doc_type: string;
  document_id: number;
};

export type Verification = {
  changes: string[];
  problems: string[];
  person: PersonDetail;
};

export type Settings = {
  timezone: string;
};

export type SessionInfo = {
  id: number;
  user_agent: string | null;
  ip_address: string | null;
  created_at: string;
  last_used_at: string;
  expires_at: string;
  current: boolean;
};

export type LinkState = "active" | "used" | "expired" | "revoked";

export type ScanLink = {
  id: number;
  label: string | null;
  state: LinkState;
  created_at: string;
  expires_at: string;
  used_at: string | null;
  document_id: number | null;
};

export type ScanLinkCreated = ScanLink & { token: string };

export type PublicLink = {
  label: string | null;
  state: LinkState;
  expires_at: string;
};
