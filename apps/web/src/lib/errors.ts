import type { ApiError } from "./api/types";

/** Extract a user-facing error message from any thrown value. */
export function getErrorMessage(err: unknown): string {
  if (err == null) return "Unknown error";
  if (typeof err === "string") return err;
  if (typeof err === "object") {
    const apiErr = err as Partial<ApiError>;
    if (apiErr.error?.message) return apiErr.error.message;
    if ("message" in err && typeof err.message === "string") return err.message;
  }
  return "Unknown error";
}
