export const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/$/, "");
export const WS_URL = (process.env.NEXT_PUBLIC_WS_URL ?? API_URL.replace(/^http/, "ws")).replace(/\/$/, "");
export const DEMO_MODE = (process.env.NEXT_PUBLIC_DEMO_MODE ?? "true") === "true";
