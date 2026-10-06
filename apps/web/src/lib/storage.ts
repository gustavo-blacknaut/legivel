"use client";

import { useCallback, useSyncExternalStore } from "react";

const CHANGE_EVENT = "legivel:storage";

function read(key: string): string | null {
  try {
    return window.localStorage.getItem(key);
  } catch {
    return null;
  }
}

function subscribe(callback: () => void): () => void {
  window.addEventListener("storage", callback);
  window.addEventListener(CHANGE_EVENT, callback);
  return () => {
    window.removeEventListener("storage", callback);
    window.removeEventListener(CHANGE_EVENT, callback);
  };
}

export function writeStored(key: string, value: string): void {
  try {
    window.localStorage.setItem(key, value);
  } catch {
    return;
  }
  window.dispatchEvent(new Event(CHANGE_EVENT));
}

export function useStoredValue<T extends string>(key: string, fallback: T, accept: (value: unknown) => value is T): [T, (value: T) => void] {
  const raw = useSyncExternalStore(
    subscribe,
    () => read(key),
    () => null,
  );
  const value = accept(raw) ? raw : fallback;
  const update = useCallback((next: T) => writeStored(key, next), [key]);
  return [value, update];
}

const noop = () => () => undefined;

export function useBrowserValue<T>(getValue: () => T, serverValue: T): T {
  return useSyncExternalStore(noop, getValue, () => serverValue);
}
