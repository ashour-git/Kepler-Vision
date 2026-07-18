"use client";

import { LogOut } from "lucide-react";

import { useMe, useSignOut } from "@/lib/auth/hooks";
import { Button } from "@/components/ui/button";
import { AppearanceMenu } from "./appearance-menu";

export function TopBar() {
  const me = useMe(true);
  const signOut = useSignOut();

  return (
    <header className="sticky top-0 z-10 flex h-12 items-center gap-3 border-b border-border bg-background/80 px-6 backdrop-blur">
      <div className="flex flex-1 items-center gap-3">
        <div className="font-mono text-xs text-muted-foreground">
          {me.data?.default_tenant ? me.data.default_tenant.name : "—"}
        </div>
      </div>
      <div className="flex items-center gap-2 text-sm">
        {me.data?.user ? (
          <span className="text-muted-foreground">{me.data.user.email}</span>
        ) : null}
        <AppearanceMenu />
        <Button
          variant="ghost"
          size="sm"
          onClick={() => {
            void signOut.mutateAsync();
          }}
          aria-label="Sign out"
        >
          <LogOut className="h-4 w-4" />
          <span className="hidden sm:inline">Sign out</span>
        </Button>
      </div>
    </header>
  );
}
