import { client, sendForm, unwrap, type Schemas } from "./client";

export type User = Schemas["UserOut"];
export type LoginResult = Schemas["LoginOut"];
export type Instance = Schemas["InstanceOut"];
export type Person = Schemas["PersonOut"];
export type PersonDetail = Schemas["PersonDetail"];
export type DocumentSummary = Schemas["DocumentSummary"];
export type DocumentDetail = Schemas["DocumentDetail"];
export type Field = Schemas["FieldOut"];
export type ImageInfo = Schemas["ImageOut"];
export type AuditEntry = Schemas["AuditOut"];
export type SessionInfo = Schemas["SessionOut"];
export type SystemInfo = Schemas["SystemOut"];
export type SettingsInfo = Schemas["SettingsOut"];
export type ScanLink = Schemas["ScanLinkOut"];
export type ScanLinkCreated = Schemas["ScanLinkCreated"];
export type PublicLink = Schemas["PublicLinkOut"];
export type Account = Schemas["AccountOut"];
export type Invitation = Schemas["InvitationOut"];
export type InvitationCreated = Schemas["InvitationCreated"];
export type InvitationPreview = Schemas["InvitationPreview"];
export type Delivery = Schemas["DeliveryOut"];
export type TwoFactorSetup = Schemas["TwoFactorSetupOut"];
export type Verification = Schemas["VerificationOut"];
export type Role = User["role"];
export type Page<T> = { items: T[]; total: number; page: number; page_size: number };

export type ListQuery = {
  q?: string;
  doc_type?: string;
  status?: string;
  from?: string;
  to?: string;
  sort?: string;
  order?: string;
  page?: number;
  page_size?: number;
  action?: string;
  entity?: string;
};

export const api = {
  instance: () => unwrap(client.GET("/api/public/instance")),
  setupStatus: () => unwrap(client.GET("/api/setup")),
  setup: (body: Schemas["SetupIn"]) => unwrap(client.POST("/api/setup", { body })),
  me: () => unwrap(client.GET("/api/auth/me")),
  login: (body: Schemas["LoginIn"]) => unwrap(client.POST("/api/auth/login", { body })),
  loginTwoFactor: (code: string) => unwrap(client.POST("/api/auth/login/two-factor", { body: { code } })),
  logout: () => unwrap(client.POST("/api/auth/logout")),
  forgotPassword: (email: string) => unwrap(client.POST("/api/auth/password/forgot", { body: { email } })),
  resetPassword: (token: string, password: string) =>
    unwrap(client.POST("/api/auth/password/reset", { body: { token, password } })),
  invitation: (token: string) => unwrap(client.GET("/api/auth/invitations/{token}", { params: { path: { token } } })),
  acceptInvitation: (token: string, body: Schemas["AcceptInviteIn"]) =>
    unwrap(client.POST("/api/auth/invitations/{token}/accept", { params: { path: { token } }, body })),
  verifyEmail: (token: string) => unwrap(client.POST("/api/auth/email/verify", { body: { token } })),
  resendVerification: () => unwrap(client.POST("/api/auth/email/resend")),
  updateProfile: (name: string) => unwrap(client.PUT("/api/auth/profile", { body: { name } })),
  changePassword: (body: Schemas["PasswordChangeIn"]) => unwrap(client.POST("/api/auth/password", { body })),
  changeEmail: (body: Schemas["EmailChangeIn"]) => unwrap(client.POST("/api/auth/email", { body })),
  sessions: () => unwrap(client.GET("/api/auth/sessions")),
  endSession: (id: number) => unwrap(client.DELETE("/api/auth/sessions/{session_id}", { params: { path: { session_id: id } } })),
  revokeOtherSessions: () => unwrap(client.POST("/api/auth/sessions/revoke-others")),
  startTwoFactor: () => unwrap(client.POST("/api/auth/two-factor/setup")),
  confirmTwoFactor: (code: string) => unwrap(client.POST("/api/auth/two-factor/confirm", { body: { code } })),
  disableTwoFactor: (password: string) => unwrap(client.POST("/api/auth/two-factor/disable", { body: { password } })),
  accounts: () => unwrap(client.GET("/api/users")),
  updateAccount: (id: number, body: Partial<Schemas["AccountUpdateIn"]>) =>
    unwrap(client.PATCH("/api/users/{user_id}", { params: { path: { user_id: id } }, body: { unlock: false, ...body } })),
  accountResetLink: (id: number) => unwrap(client.POST("/api/users/{user_id}/reset-link", { params: { path: { user_id: id } } })),
  accountRevokeSessions: (id: number) =>
    unwrap(client.POST("/api/users/{user_id}/revoke-sessions", { params: { path: { user_id: id } } })),
  accountDisableTwoFactor: (id: number) =>
    unwrap(client.DELETE("/api/users/{user_id}/two-factor", { params: { path: { user_id: id } } })),
  invitations: () => unwrap(client.GET("/api/users/invitations")),
  invite: (body: Schemas["InvitationIn"]) => unwrap(client.POST("/api/users/invitations", { body })),
  cancelInvitation: (id: number) =>
    unwrap(client.DELETE("/api/users/invitations/{invitation_id}", { params: { path: { invitation_id: id } } })),
  people: (query: ListQuery) => unwrap(client.GET("/api/people", { params: { query } })) as Promise<Page<Person>>,
  person: (id: number, reveal = false) =>
    unwrap(client.GET("/api/people/{person_id}", { params: { path: { person_id: id }, query: { reveal } } })),
  updatePerson: (id: number, values: Record<string, string | null>, reveal = false) =>
    unwrap(client.PUT("/api/people/{person_id}", { params: { path: { person_id: id }, query: { reveal } }, body: { values } })),
  verifyPerson: (id: number, reveal = false) =>
    unwrap(client.POST("/api/people/{person_id}/verify", { params: { path: { person_id: id }, query: { reveal } } })),
  exportPerson: (id: number) =>
    unwrap(client.GET("/api/people/{person_id}/export", { params: { path: { person_id: id } }, parseAs: "blob" })),
  deletePerson: (id: number) => unwrap(client.DELETE("/api/people/{person_id}", { params: { path: { person_id: id } } })),
  documents: (query: ListQuery) =>
    unwrap(client.GET("/api/documents", { params: { query } })) as Promise<Page<DocumentSummary>>,
  document: (id: number, reveal = false) =>
    unwrap(client.GET("/api/documents/{document_id}", { params: { path: { document_id: id }, query: { reveal } } })),
  saveDocument: (id: number, values: Record<string, string>, reveal = false) =>
    unwrap(
      client.PUT("/api/documents/{document_id}", { params: { path: { document_id: id }, query: { reveal } }, body: { values } }),
    ),
  reprocess: (id: number, reveal = false) =>
    unwrap(client.POST("/api/documents/{document_id}/reprocess", { params: { path: { document_id: id }, query: { reveal } } })),
  deleteDocument: (id: number) => unwrap(client.DELETE("/api/documents/{document_id}", { params: { path: { document_id: id } } })),
  upload: (form: FormData) => sendForm<DocumentDetail>("/api/documents", form),
  audit: (query: ListQuery) => unwrap(client.GET("/api/audit", { params: { query } })) as Promise<Page<AuditEntry>>,
  system: () => unwrap(client.GET("/api/system")),
  settings: () => unwrap(client.GET("/api/settings")),
  saveSettings: (values: Record<string, unknown>) => unwrap(client.PUT("/api/settings", { body: { values } })),
  saveRolePermissions: (rolePermissions: Record<string, string[]>) =>
    unwrap(client.PUT("/api/settings/roles", { body: { role_permissions: rolePermissions } })),
  uploadLogo: (file: File) => {
    const form = new FormData();
    form.append("logo", file);
    return sendForm<void>("/api/settings/logo", form, "PUT");
  },
  removeLogo: () => unwrap(client.DELETE("/api/settings/logo")),
  timezones: () => unwrap(client.GET("/api/settings/timezones")),
  scanLinks: () => unwrap(client.GET("/api/scan-links")),
  createScanLink: (label: string, hours: number) => unwrap(client.POST("/api/scan-links", { body: { label, hours } })),
  revokeScanLink: (id: number) => unwrap(client.DELETE("/api/scan-links/{link_id}", { params: { path: { link_id: id } } })),
  publicLink: (token: string) => unwrap(client.GET("/api/public/scan/{token}", { params: { path: { token } } })),
  publicUpload: (token: string, form: FormData) =>
    sendForm<{ status: string }>(`/api/public/scan/${encodeURIComponent(token)}`, form),
};
