"use client";

import { useEffect } from "react";

import { useUiStore } from "@/stores/ui";

/**
 * Applies the persisted theme + density to the `<html>` element.
 *
 * Theme values: "light" | "dark" | "system". When "system" we follow
 * the OS `prefers-color-scheme` media query.
 *
 * Density values: "comfortable" | "compact". We expose this as a data
 * attribute so component CSS can opt in.
 *
 * Mounted at the root so every page sees the correct class on first paint.
 */
export function ThemeApplier() {
  const theme = useUiStore((s) => s.theme);
  const density = useUiStore((s) => s.density);

  useEffect(() => {
    const root = document.documentElement;

    const applyTheme = (resolved: "light" | "dark") => {
      root.classList.toggle("dark", resolved === "dark");
      root.style.colorScheme = resolved;
    };

    if (theme === "system") {
      const mql = window.matchMedia("(prefers-color-scheme: dark)");
      applyTheme(mql.matches ? "dark" : "light");
      const handler = (e: MediaQueryListEvent) => applyTheme(e.matches ? "dark" : "light");
      mql.addEventListener("change", handler);
      return () => mql.removeEventListener("change", handler);
    }
    applyTheme(theme);
    return undefined;
  }, [theme]);

  useEffect(() => {
    document.documentElement.dataset.density = density;
  }, [density]);

  return null;
}
