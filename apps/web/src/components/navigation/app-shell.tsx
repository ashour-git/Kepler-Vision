"use client";

import Link from "next/link";
import type { ReactNode } from "react";

import { LeftRail } from "./left-rail";
import { TopBar } from "./top-bar";
import { useUiStore } from "@/stores/ui";

export function AppShell({ children }: { children: ReactNode }) {
  const collapsed = useUiStore((s) => s.leftRailCollapsed);
  return (
    <div className="flex min-h-screen w-full">
      <LeftRail collapsed={collapsed} />
      <div className="flex min-w-0 flex-1 flex-col">
        <TopBar />
        <main
          id="main"
          tabIndex={-1}
          className="min-w-0 flex-1 overflow-x-hidden focus:outline-none"
        >
          <div className="mx-auto w-full max-w-7xl px-6 py-6">{children}</div>
        </main>
        <footer className="border-t border-border px-6 py-3 text-xs text-muted-foreground">
          <Link href="https://kepler.vision" className="hover:underline">
            Kepler Vision
          </Link>{" "}
          · v0.1.0
        </footer>
      </div>
    </div>
  );
}
