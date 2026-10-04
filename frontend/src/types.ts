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
  languages: string[];
  default_language: string;
  store_card_numbers: boolean;
  card_key_configured: boolean;
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

export type ModuleInfo = {
  key: string;
  name: string;
  description: string;
  icon: string;
  multi_page: boolean;
  max_pages: number;
  page_labels: string[];
  exports: string[];
  kinds: Record<string, string>;
};

export type LanguageInfo = {
  code: string;
  name: string;
  pack: string;
};

export type RecordSummary = {
  id: number;
  module: string;
  kind: string | null;
  title: string | null;
  status: DocumentStatus;
  language: string | null;
  confidence: number | null;
  page_count: number;
  created_at: string;
  thumbnail_url: string | null;
};

export type RecordField = {
  name: string;
  label: string;
  kind: string;
  value: string;
  confidence: number | null;
  issues: string[];
};

export type RecordPageInfo = {
  id: number;
  number: number;
  thumbnail_url: string | null;
  full_url: string | null;
  text: string;
  columns: number | null;
};

export type CardInfo = {
  brand: string | null;
  last4: string | null;
  holder_name: string | null;
  expiry: string | null;
  luhn_valid: boolean;
  number_stored: boolean;
};

export type RecordDetail = RecordSummary & {
  module_name: string;
  kind_label: string | null;
  fields: RecordField[];
  issues: { field: string; code: string; message: string }[];
  pages: RecordPageInfo[];
  exports: string[];
  card: CardInfo | null;
};

export type SearchHit = {
  module: string;
  id: number;
  title: string;
  subtitle: string;
  status: DocumentStatus;
  created_at: string;
  url: string;
};
