"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

import { useMe, useSession } from "@/lib/auth/hooks";
import { ApiClientError } from "@/lib/api/client";
import { useSignOut } from "@/lib/auth/hooks";

export function AuthGate({ children }: { children: React.ReactNode }) {
  const session = useSession();
  const router = useRouter();
  const me = useMe(Boolean(session));
  const signOut = useSignOut();

  useEffect(() => {
    // No session → redirect to sign-in
    if (session === null) {
      router.replace("/sign-in");
    }
  }, [session, router]);

  useEffect(() => {
    // 401 from /me → clear session and redirect
    if (me.error instanceof ApiClientError && me.error.status === 401) {
      void signOut.mutateAsync();
    }
  }, [me.error, signOut]);

  if (!session) {
    return (
      <div className="flex min-h-screen items-center justify-center text-sm text-muted-foreground">
        Redirecting…
      </div>
    );
  }

  if (me.isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center text-sm text-muted-foreground">
        Loading workspace…
      </div>
    );
  }

  if (me.isError) {
    return (
      <div className="flex min-h-screen items-center justify-center text-sm text-destructive">
        Couldn&apos;t load your workspace. Please try again.
      </div>
    );
  }

  return <>{children}</>;
}
