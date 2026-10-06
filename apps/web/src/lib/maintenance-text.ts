"use client";
import { useLocale } from "./i18n";
export function useWords() {
  const { language } = useLocale();
  return (pt: string, en: string) => language === "en" ? en : pt;
}
