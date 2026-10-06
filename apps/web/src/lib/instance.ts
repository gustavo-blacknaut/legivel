import "server-only";
import { readServerEnv } from "@/env";
import type { Instance } from "./api/endpoints";

export const FALLBACK_INSTANCE: Instance = {
  name: "Legível",
  default_theme: "system",
  default_language: "pt-BR",
  timezone: "America/Sao_Paulo",
  logo_url: null,
  setup_required: false,
  smtp_configured: false,
  upload_max_mb: 15,
  upload_formats: ["jpeg", "png", "webp", "heic"],
  password_min_length: 10,
  password_require_mixed: true,
  refresh_days: 30,
};

export async function loadInstance(): Promise<Instance> {
  try {
    const response = await fetch(`${readServerEnv().LEGIVEL_API_URL}/api/public/instance`, {
      cache: "no-store",
      signal: AbortSignal.timeout(3000),
    });
    if (!response.ok) return FALLBACK_INSTANCE;
    return (await response.json()) as Instance;
  } catch {
    return FALLBACK_INSTANCE;
  }
}
