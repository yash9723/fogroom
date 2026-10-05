// "same-origin": the API serves this frontend (single Render service), so use the page's own origin.
const rawApi = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const origin = typeof window === "undefined" ? "http://localhost" : window.location.origin;
export const API_URL = (rawApi === "same-origin" ? origin : rawApi).replace(/\/$/, "");
export const WS_URL = (process.env.NEXT_PUBLIC_WS_URL ?? API_URL.replace(/^http/, "ws")).replace(/\/$/, "");
export const DEMO_MODE = (process.env.NEXT_PUBLIC_DEMO_MODE ?? "true") === "true";
