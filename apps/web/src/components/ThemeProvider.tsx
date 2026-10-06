"use client";

import { createContext, useContext, useEffect, type ReactNode } from "react";
import { useStoredValue } from "@/lib/storage";
import { THEME_STORAGE_KEY, applyTheme, isThemePreference, watchSystemTheme, type ThemePreference } from "@/lib/theme";
import { useInstanceTheme } from "./useInstanceTheme";

type ThemeState = { preference: ThemePreference; setPreference: (preference: ThemePreference) => void };
const ThemeContext = createContext<ThemeState | null>(null);

export function ThemeProvider({ children }: { children: ReactNode }) {
  const fallback = useInstanceTheme();
  const [preference, setPreference] = useStoredValue(THEME_STORAGE_KEY, fallback, isThemePreference);

  useEffect(() => {
    applyTheme(preference);
    return watchSystemTheme(() => applyTheme(preference));
  }, [preference]);

  return <ThemeContext.Provider value={{ preference, setPreference }}>{children}</ThemeContext.Provider>;
}

export function useTheme(): ThemeState {
  const context = useContext(ThemeContext);
  if (!context) throw new Error("useTheme precisa estar dentro de ThemeProvider");
  return context;
}
