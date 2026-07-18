"use client";

import { Monitor, Moon, Sun, Maximize2, Minimize2 } from "lucide-react";
import * as React from "react";

import { useUiStore } from "@/stores/ui";
import { Button } from "@/components/ui/button";

/**
 * A small dropdown with theme and density toggles. Mounted in the top bar.
 *
 * Theme is stored in the UI store; we mirror it to the DOM via
 * `<ThemeApplier />`. Density is also persisted in the UI store.
 */
export function AppearanceMenu() {
  const theme = useUiStore((s) => s.theme);
  const setTheme = useUiStore((s) => s.setTheme);
  const density = useUiStore((s) => s.density);
  const setDensity = useUiStore((s) => s.setDensity);
  const [open, setOpen] = React.useState(false);
  const ref = React.useRef<HTMLDivElement>(null);

  React.useEffect(() => {
    if (!open) return;
    const onClick = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, [open]);

  return (
    <div ref={ref} className="relative">
      <Button
        size="sm"
        variant="ghost"
        onClick={() => setOpen((v) => !v)}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label="Appearance settings"
      >
        {density === "compact" ? <Minimize2 className="h-4 w-4" /> : <Maximize2 className="h-4 w-4" />}
      </Button>
      {open ? (
        <div
          role="menu"
          aria-label="Appearance"
          className="absolute right-0 top-full z-50 mt-1 w-56 rounded-md border border-border bg-popover p-1 text-popover-foreground shadow-md animate-fade-in"
        >
          <div className="px-2 py-1.5 text-2xs font-medium uppercase tracking-wide text-muted-foreground">
            Theme
          </div>
          <ThemeItem
            current={theme}
            value="light"
            label="Light"
            icon={<Sun className="h-4 w-4" />}
            onSelect={setTheme}
            onAfterSelect={() => setOpen(false)}
          />
          <ThemeItem
            current={theme}
            value="dark"
            label="Dark"
            icon={<Moon className="h-4 w-4" />}
            onSelect={setTheme}
            onAfterSelect={() => setOpen(false)}
          />
          <ThemeItem
            current={theme}
            value="system"
            label="System"
            icon={<Monitor className="h-4 w-4" />}
            onSelect={setTheme}
            onAfterSelect={() => setOpen(false)}
          />
          <div className="my-1 h-px bg-border" />
          <div className="px-2 py-1.5 text-2xs font-medium uppercase tracking-wide text-muted-foreground">
            Density
          </div>
          <button
            type="button"
            role="menuitemradio"
            aria-checked={density === "comfortable"}
            onClick={() => {
              setDensity("comfortable");
              setOpen(false);
            }}
            className="flex w-full items-center justify-between rounded-xs px-2 py-1.5 text-sm hover:bg-accent"
          >
            Comfortable
            {density === "comfortable" ? <span aria-hidden>✓</span> : null}
          </button>
          <button
            type="button"
            role="menuitemradio"
            aria-checked={density === "compact"}
            onClick={() => {
              setDensity("compact");
              setOpen(false);
            }}
            className="flex w-full items-center justify-between rounded-xs px-2 py-1.5 text-sm hover:bg-accent"
          >
            Compact
            {density === "compact" ? <span aria-hidden>✓</span> : null}
          </button>
        </div>
      ) : null}
    </div>
  );
}

function ThemeItem({
  current,
  value,
  label,
  icon,
  onSelect,
  onAfterSelect,
}: {
  current: "light" | "dark" | "system";
  value: "light" | "dark" | "system";
  label: string;
  icon: React.ReactNode;
  onSelect: (v: "light" | "dark" | "system") => void;
  onAfterSelect: () => void;
}) {
  const selected = current === value;
  return (
    <button
      type="button"
      role="menuitemradio"
      aria-checked={selected}
      onClick={() => {
        onSelect(value);
        onAfterSelect();
      }}
      className="flex w-full items-center justify-between gap-2 rounded-xs px-2 py-1.5 text-sm hover:bg-accent"
    >
      <span className="flex items-center gap-2">
        {icon}
        {label}
      </span>
      {selected ? <span aria-hidden>✓</span> : null}
    </button>
  );
}
