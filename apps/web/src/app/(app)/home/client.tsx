"use client";

import { useMe } from "@/lib/auth/hooks";

export function DashboardClient() {
  const me = useMe(true);

  if (me.isLoading) {
    return <p className="text-sm text-muted-foreground">Loading…</p>;
  }
  if (me.isError || !me.data) {
    return <p className="text-sm text-destructive">Couldn&apos;t load your profile.</p>;
  }

  return (
    <dl className="grid grid-cols-1 gap-4 sm:grid-cols-2">
      <div>
        <dt className="text-xs font-medium text-muted-foreground">Email</dt>
        <dd className="font-mono text-sm">{me.data.user.email}</dd>
      </div>
      <div>
        <dt className="text-xs font-medium text-muted-foreground">Default workspace</dt>
        <dd className="text-sm">{me.data.default_tenant?.name ?? "—"}</dd>
      </div>
      <div>
        <dt className="text-xs font-medium text-muted-foreground">Default role</dt>
        <dd>
          <span className="inline-flex items-center rounded-xs border border-border bg-secondary px-2 py-0.5 font-mono text-2xs uppercase">
            {me.data.default_role ?? "—"}
          </span>
        </dd>
      </div>
      <div>
        <dt className="text-xs font-medium text-muted-foreground">Scopes</dt>
        <dd className="flex flex-wrap gap-1 pt-1">
          {me.data.scopes.slice(0, 6).map((s: string) => (
            <span
              key={s}
              className="inline-flex items-center rounded-xs border border-border bg-secondary px-2 py-0.5 font-mono text-2xs"
            >
              {s}
            </span>
          ))}
          {me.data.scopes.length > 6 ? (
            <span className="text-2xs text-muted-foreground">
              +{me.data.scopes.length - 6} more
            </span>
          ) : null}
        </dd>
      </div>
    </dl>
  );
}
