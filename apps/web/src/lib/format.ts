/** Date and number formatting helpers. */

export function formatDate(value: string | Date, opts?: Intl.DateTimeFormatOptions): string {
  const date = typeof value === "string" ? new Date(value) : value;
  if (Number.isNaN(date.getTime())) return "—";
  return new Intl.DateTimeFormat("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
    ...opts,
  }).format(date);
}

export function formatNumber(value: number, opts?: Intl.NumberFormatOptions): string {
  return new Intl.NumberFormat("en-US", opts).format(value);
}

export function formatRelativeTime(value: string | Date): string {
  const date = typeof value === "string" ? new Date(value) : value;
  if (Number.isNaN(date.getTime())) return "—";
  const diff = (Date.now() - date.getTime()) / 1000;
  const abs = Math.abs(diff);
  const formatter = new Intl.RelativeTimeFormat("en-US", { numeric: "auto" });
  if (abs < 60) return formatter.format(-Math.round(diff), "second");
  if (abs < 3600) return formatter.format(-Math.round(diff / 60), "minute");
  if (abs < 86400) return formatter.format(-Math.round(diff / 3600), "hour");
  if (abs < 86400 * 30) return formatter.format(-Math.round(diff / 86400), "day");
  if (abs < 86400 * 365) return formatter.format(-Math.round(diff / (86400 * 30)), "month");
  return formatter.format(-Math.round(diff / (86400 * 365)), "year");
}
