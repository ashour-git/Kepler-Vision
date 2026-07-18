"use client";

import { useEffect } from "react";

import { Button } from "@/components/ui/button";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // Production code would forward to Sentry / OTel here.
    // eslint-disable-next-line no-console
    console.error("app_error", { message: error.message, digest: error.digest });
  }, [error]);

  return (
    <main
      id="main"
      className="flex min-h-screen flex-col items-center justify-center px-6 text-center"
    >
      <p className="font-mono text-xs text-muted-foreground">500</p>
      <h1 className="mt-3 text-2xl font-semibold tracking-tight">Something went wrong</h1>
      <p className="mt-2 max-w-md text-sm text-muted-foreground">
        {error.message || "An unexpected error occurred."}
      </p>
      {error.digest ? (
        <p className="mt-2 font-mono text-2xs text-muted-foreground">
          Error ID: {error.digest}
        </p>
      ) : null}
      <div className="mt-6 flex gap-2">
        <Button onClick={reset}>Try again</Button>
        <Button asChild variant="outline">
          <a href="/home">Go to Home</a>
        </Button>
      </div>
    </main>
  );
}
