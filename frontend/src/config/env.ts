/**
 * Resolved API base URL.
 * Empty string -> same-origin requests, which in dev are forwarded to the
 * FastAPI backend by the Vite proxy (see vite.config.ts).
 */
export const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/$/, "");
