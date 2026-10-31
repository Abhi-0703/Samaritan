"use client";

import { useCallback, useEffect, useSyncExternalStore } from "react";

export type Theme = "light" | "dark" | "system";

export const THEME_KEY = "samaritan.theme";

/**
 * Runs in the document head before first paint (see layout.tsx) so the right theme is applied without a flash.
 * It is rendered by a Server Component; next-themes renders its script from a Client Component, which React 19 reports as an error.
 */
export const THEME_INIT_SCRIPT = `(function(){try{var t=localStorage.getItem(${JSON.stringify(THEME_KEY)});var d=t==="dark"||(t!=="light"&&window.matchMedia("(prefers-color-scheme: dark)").matches);var r=document.documentElement;if(d)r.classList.add("dark");r.style.colorScheme=d?"dark":"light"}catch(e){}})()`;

const listeners = new Set<() => void>();
const emit = () => listeners.forEach((l) => l());

function readTheme(): Theme {
  try {
    const v = window.localStorage.getItem(THEME_KEY);
    return v === "light" || v === "dark" ? v : "system";
  } catch {
    return "system";
  }
}

const media = () => window.matchMedia("(prefers-color-scheme: dark)");

function subscribe(cb: () => void) {
  listeners.add(cb);
  window.addEventListener("storage", cb);
  media().addEventListener("change", cb);
  return () => {
    listeners.delete(cb);
    window.removeEventListener("storage", cb);
    media().removeEventListener("change", cb);
  };
}

export function useTheme() {
  const theme = useSyncExternalStore(subscribe, readTheme, () => "system" as Theme);
  const systemDark = useSyncExternalStore(subscribe, () => media().matches, () => false);
  const resolvedTheme: "light" | "dark" = theme === "system" ? (systemDark ? "dark" : "light") : theme;
  const setTheme = useCallback((next: Theme) => {
    try {
      if (next === "system") window.localStorage.removeItem(THEME_KEY);
      else window.localStorage.setItem(THEME_KEY, next);
    } catch {
      // Storage can be unavailable; the choice then lasts only until the page reloads.
    }
    document.documentElement.classList.toggle("dark", next === "dark" || (next === "system" && media().matches));
    emit();
  }, []);
  return { theme, resolvedTheme, setTheme };
}

/** Keeps the <html> class in step with the stored choice and the operating-system setting. */
export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const { resolvedTheme } = useTheme();
  useEffect(() => {
    const root = document.documentElement;
    root.classList.toggle("dark", resolvedTheme === "dark");
    root.style.colorScheme = resolvedTheme;
  }, [resolvedTheme]);
  return <>{children}</>;
}
