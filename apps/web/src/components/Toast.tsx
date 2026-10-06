"use client";

import { CircleAlert, CircleCheck } from "lucide-react";
import { createContext, useCallback, useContext, useState, type ReactNode } from "react";
import styles from "./Toast.module.css";

type Tone = "ok" | "error";
type Item = { id: number; message: string; tone: Tone };
type Show = (message: string, tone?: Tone) => void;

const ToastContext = createContext<Show>(() => undefined);
const DURATION_MS = 3500;

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<Item[]>([]);
  const show = useCallback<Show>((message, tone = "ok") => {
    const id = Date.now() + Math.random();
    setItems((current) => [...current, { id, message, tone }]);
    window.setTimeout(() => setItems((current) => current.filter((item) => item.id !== id)), DURATION_MS);
  }, []);
  return (
    <ToastContext.Provider value={show}>
      {children}
      <div className={styles.toasts} role="status" aria-live="polite">
        {items.map((item) => (
          <div key={item.id} className={`${styles.toast} ${item.tone === "error" ? styles.error : ""}`}>
            {item.tone === "ok" ? <CircleCheck size={16} /> : <CircleAlert size={16} />}
            {item.message}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast(): Show {
  return useContext(ToastContext);
}
