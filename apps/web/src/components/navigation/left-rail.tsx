"use client";

import { usePathname } from "next/navigation";
import Link from "next/link";
import { BarChart3, Compass, FolderKanban, LayoutGrid, Settings, Users } from "lucide-react";
import { type ComponentType } from "react";

import { useUiStore } from "@/stores/ui";
import { cn } from "@/lib/cn";

interface NavItem {
  href: string;
  label: string;
  icon: ComponentType<{ className?: string }>;
  hotkey?: string;
}

const NAV: NavItem[] = [
  { href: "/home", label: "Home", icon: LayoutGrid, hotkey: "G H" },
  { href: "/map", label: "Map", icon: Compass, hotkey: "G M" },
  { href: "/projects", label: "Projects", icon: FolderKanban, hotkey: "G P" },
  { href: "/datasets", label: "Datasets", icon: BarChart3, hotkey: "G D" },
  { href: "/members", label: "Members", icon: Users, hotkey: "G U" },
  { href: "/settings", label: "Settings", icon: Settings, hotkey: "G S" },
];

export function LeftRail({ collapsed }: { collapsed: boolean }) {
  const pathname = usePathname();
  const toggle = useUiStore((s) => s.toggleLeftRail);

  return (
    <aside
      className={cn(
        "sticky top-0 flex h-screen flex-col border-r border-border bg-card",
        collapsed ? "w-14" : "w-60",
      )}
      aria-label="Primary navigation"
    >
      <div className="flex h-12 items-center gap-2 border-b border-border px-3">
        <button
          type="button"
          onClick={toggle}
          aria-label={collapsed ? "Expand navigation" : "Collapse navigation"}
          className="focus-ring inline-flex h-8 w-8 items-center justify-center rounded-xs hover:bg-accent"
        >
          <span aria-hidden className="font-mono text-sm font-semibold">K</span>
        </button>
        {!collapsed ? <span className="text-sm font-semibold">Kepler Vision</span> : null}
      </div>
      <nav className="flex-1 overflow-y-auto p-2">
        <ul className="flex flex-col gap-0.5">
          {NAV.map((item) => {
            const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
            return (
              <li key={item.href}>
                <Link
                  href={item.href as never}
                  aria-current={active ? "page" : undefined}
                  className={cn(
                    "flex h-8 items-center gap-2 rounded-xs px-2 text-sm transition-colors focus-ring",
                    active
                      ? "bg-accent text-accent-foreground font-medium"
                      : "text-muted-foreground hover:bg-accent hover:text-foreground",
                  )}
                >
                  <item.icon className="h-4 w-4" />
                  {!collapsed ? <span className="flex-1 truncate">{item.label}</span> : null}
                  {!collapsed && item.hotkey ? (
                    <kbd className="font-mono text-2xs text-muted-foreground">{item.hotkey}</kbd>
                  ) : null}
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>
      {!collapsed ? (
        <div className="border-t border-border p-3 text-xs text-muted-foreground">
          <p>Press <kbd className="font-mono">?</kbd> for shortcuts</p>
        </div>
      ) : null}
    </aside>
  );
}
