"use client";

import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { createFormatter, type Formatter, type Language } from "../format";
import { useStoredValue } from "../storage";
import { LANGUAGE_STORAGE_KEY } from "../theme";
import { en } from "./en";
import { ptBR, type Messages } from "./pt-BR";

export const CATALOGS: Record<Language, Messages> = { "pt-BR": ptBR, en };

export function isLanguage(value: unknown): value is Language {
  return value === "pt-BR" || value === "en";
}

type LocaleState = {
  language: Language;
  timeZone: string;
  t: Messages;
  format: Formatter;
  setLanguage: (language: Language) => void;
  setTimeZone: (timeZone: string) => void;
};

const LocaleContext = createContext<LocaleState | null>(null);

type LocaleProviderProps = { defaultLanguage: Language; defaultTimeZone: string; children: ReactNode };

export function LocaleProvider({ defaultLanguage, defaultTimeZone, children }: LocaleProviderProps) {
  const [language, setLanguage] = useStoredValue(LANGUAGE_STORAGE_KEY, defaultLanguage, isLanguage);
  const [timeZone, setTimeZone] = useState(defaultTimeZone);

  useEffect(() => {
    document.documentElement.lang = language;
  }, [language]);

  const value = useMemo(
    () => ({ language, timeZone, t: CATALOGS[language], format: createFormatter(language, timeZone), setLanguage, setTimeZone }),
    [language, timeZone, setLanguage],
  );
  return <LocaleContext.Provider value={value}>{children}</LocaleContext.Provider>;
}

export function useLocale(): LocaleState {
  const context = useContext(LocaleContext);
  if (!context) throw new Error("useLocale precisa estar dentro de LocaleProvider");
  return context;
}

export function useT(): Messages {
  return useLocale().t;
}
