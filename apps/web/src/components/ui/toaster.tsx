"use client";

import { Toaster as SonnerToaster } from "sonner";

export function Toaster() {
  return (
    <SonnerToaster
      position="bottom-right"
      theme="system"
      richColors
      closeButton
      duration={4000}
      toastOptions={{
        classNames: {
          toast: "rounded-md border border-border text-sm",
        },
      }}
    />
  );
}
