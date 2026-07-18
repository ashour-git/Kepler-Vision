import { AuthGate } from "@/components/auth/auth-gate";
import { AppShell } from "@/components/navigation/app-shell";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <AuthGate>
      <AppShell>{children}</AppShell>
    </AuthGate>
  );
}
