import { apiErrorSchema } from "@fogroom/shared";
import { API_URL } from "./config";
import { useAuthStore } from "./auth-store";
import type { TokenPair } from "./types";

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public details?: unknown,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

type RequestOptions = {
  method?: string;
  body?: unknown;
  auth?: boolean;
  signal?: AbortSignal;
  query?: Record<string, string | number | boolean | undefined | null | string[]>;
};

let refreshInFlight: Promise<boolean> | null = null;

/** Single-flight refresh-token rotation. */
async function refreshTokens(): Promise<boolean> {
  const { refreshToken, setSession, clear } = useAuthStore.getState();
  if (!refreshToken) return false;
  if (!refreshInFlight) {
    refreshInFlight = (async () => {
      try {
        const res = await fetch(`${API_URL}/api/v1/auth/refresh`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ refresh_token: refreshToken }),
        });
        if (!res.ok) {
          clear();
          return false;
        }
        setSession((await res.json()) as TokenPair);
        return true;
      } catch {
        return false;
      } finally {
        setTimeout(() => {
          refreshInFlight = null;
        }, 0);
      }
    })();
  }
  return refreshInFlight;
}

async function toApiError(res: Response): Promise<ApiError> {
  try {
    const body = await res.json();
    const parsed = apiErrorSchema.safeParse(body);
    if (parsed.success) {
      return new ApiError(res.status, parsed.data.error.code, parsed.data.error.message, parsed.data.error.details);
    }
  } catch {
    /* non-JSON error body */
  }
  return new ApiError(res.status, `HTTP_${res.status}`, res.statusText || "Request failed");
}

function buildUrl(path: string, query?: RequestOptions["query"]): string {
  const url = new URL(`${API_URL}/api/v1${path}`);
  if (query) {
    for (const [k, v] of Object.entries(query)) {
      if (v === undefined || v === null || v === "") continue;
      if (Array.isArray(v)) v.forEach((item) => url.searchParams.append(k, item));
      else url.searchParams.set(k, String(v));
    }
  }
  return url.toString();
}

async function send(path: string, opts: RequestOptions): Promise<Response> {
  const doFetch = () => {
    const headers: Record<string, string> = {};
    if (opts.body !== undefined) headers["Content-Type"] = "application/json";
    const token = useAuthStore.getState().accessToken;
    if (opts.auth !== false && token) headers.Authorization = `Bearer ${token}`;
    return fetch(buildUrl(path, opts.query), {
      method: opts.method ?? (opts.body !== undefined ? "POST" : "GET"),
      headers,
      body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined,
      signal: opts.signal,
    });
  };
  let res: Response;
  try {
    res = await doFetch();
    if (res.status === 401 && opts.auth !== false && (await refreshTokens())) {
      res = await doFetch();
    }
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") throw err;
    throw new ApiError(0, "NETWORK_ERROR", "Cannot reach the FOGROOM API. Is the server running?");
  }
  if (res.status === 401 && opts.auth !== false) {
    const error = await toApiError(res);
    if (useAuthStore.getState().user) useAuthStore.getState().clear();
    throw error;
  }
  if (!res.ok) throw await toApiError(res);
  return res;
}

export async function api<T>(path: string, opts: RequestOptions = {}): Promise<T> {
  const res = await send(path, opts);
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export async function apiBlob(path: string): Promise<Blob> {
  const res = await send(path, {});
  return res.blob();
}

export async function logout(): Promise<void> {
  const { refreshToken, clear } = useAuthStore.getState();
  if (refreshToken) {
    try {
      await api("/auth/logout", { body: { refresh_token: refreshToken }, auth: false });
    } catch {
      /* revocation best-effort; local session is cleared regardless */
    }
  }
  clear();
}
