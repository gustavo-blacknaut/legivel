"use client";

import { isThemePreference, type ThemePreference } from "@/lib/theme";
import { useInstance } from "./Providers";

export function useInstanceTheme(): ThemePreference {
  const theme = useInstance().default_theme;
  return isThemePreference(theme) ? theme : "system";
}
