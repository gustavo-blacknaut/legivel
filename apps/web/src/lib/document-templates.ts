export type TemplateField = { name: string; label: string; kind: "text" | "textarea" | "date"; required: boolean; expiration: boolean };
export type DocumentTemplate = { id: string; name: string; fields: TemplateField[] };
