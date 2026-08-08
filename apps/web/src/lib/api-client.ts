import axios, { AxiosError, InternalAxiosRequestConfig } from "axios";

const defaultBackendDomain = "http://localhost:8000";
const apiPath = "/api/v1";
const wsPath = "/api/v1/ws";

function envValue(value: string | undefined): string | undefined {
  return value?.trim() || undefined;
}

const backendDomain = envValue(process.env.NEXT_PUBLIC_BACKEND_DOMAIN) ?? defaultBackendDomain;

function withPath(rawDomain: string, path: string): string {
  const domainWithProtocol = rawDomain.includes("://") ? rawDomain : `https://${rawDomain}`;
  const url = new URL(domainWithProtocol);
  url.pathname = `${url.pathname.replace(/\/$/, "")}${path}`;
  url.search = "";
  url.hash = "";
  return url.toString().replace(/\/$/, "");
}

const apiBaseUrl = envValue(process.env.NEXT_PUBLIC_API_BASE_URL) ?? withPath(backendDomain, apiPath);
const wsBaseUrl =
  envValue(process.env.NEXT_PUBLIC_WS_URL) ??
  withPath(backendDomain, wsPath).replace(/^http:\/\//, "ws://").replace(/^https:\/\//, "wss://");

function runtimeApiBaseUrl(): string {
  if (typeof window !== "undefined" && ["localhost", "127.0.0.1", "0.0.0.0"].includes(window.location.hostname)) {
    return `http://${window.location.hostname}:8000/api/v1`;
  }
  return apiBaseUrl;
}

function alignLoopbackHost(rawUrl: string): string {
  if (typeof window === "undefined") return rawUrl;
  const url = new URL(rawUrl);
  const loopbackHosts = new Set(["localhost", "127.0.0.1", "0.0.0.0"]);
  if (loopbackHosts.has(url.hostname) && loopbackHosts.has(window.location.hostname)) {
    url.hostname = window.location.hostname;
  }
  return url.toString().replace(/\/$/, "");
}

function apiRequestHeaders(rawUrl: string): Record<string, string> {
  const hostname = new URL(rawUrl).hostname.toLowerCase();
  if (hostname.endsWith(".ngrok-free.app") || hostname.endsWith(".ngrok-free.dev")) {
    // Free ngrok domains return a browser interstitial before the API response
    // unless programmatic clients explicitly opt out of it.
    return { "ngrok-skip-browser-warning": "true" };
  }
  return {};
}

const resolvedApiBaseUrl = alignLoopbackHost(runtimeApiBaseUrl());

export function getStoredAccessToken(): string | null {
  if (typeof window === "undefined") return null;
  const params = new URLSearchParams(window.location.search);
  const tokenFromUrl = params.get("access_token");
  const refreshTokenFromUrl = params.get("refresh_token");
  if (tokenFromUrl) {
    localStorage.setItem("relay_access_token", tokenFromUrl);
    if (refreshTokenFromUrl) {
      localStorage.setItem("relay_refresh_token", refreshTokenFromUrl);
    }
    const url = new URL(window.location.href);
    url.searchParams.delete("access_token");
    url.searchParams.delete("refresh_token");
    const cleanUrl = `${url.pathname}${url.search}${url.hash}`;
    window.history.replaceState({}, "", cleanUrl);
    return tokenFromUrl;
  }
  return localStorage.getItem("relay_access_token");
}

export function setStoredTokens(accessToken?: string, refreshToken?: string) {
  if (typeof window === "undefined") return;
  if (accessToken) localStorage.setItem("relay_access_token", accessToken);
  if (refreshToken) localStorage.setItem("relay_refresh_token", refreshToken);
}

export function clearLegacyTokenStorage() {
  if (typeof window === "undefined") return;
  localStorage.removeItem("relay_access_token");
  localStorage.removeItem("relay_refresh_token");
}

export const apiClient = axios.create({
  baseURL: resolvedApiBaseUrl,
  withCredentials: true,
  headers: apiRequestHeaders(resolvedApiBaseUrl),
});

apiClient.interceptors.request.use((config) => {
  const token = getStoredAccessToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export function getApiBaseUrl(): string {
  return alignLoopbackHost(runtimeApiBaseUrl());
}

export async function beginGoogleLogin(): Promise<void> {
  const response = await apiClient.get<{ authorization_url: string }>("/auth/google/authorization");
  window.location.assign(response.data.authorization_url);
}

export function getWebSocketUrl(): string {
  let url = alignLoopbackHost(wsBaseUrl);
  if (typeof window !== "undefined" && window.location.protocol === "https:") {
    url = url.replace(/^ws:\/\//, "wss://");
  }
  return url;
}

type ApiErrorBody = {
  error?: { message?: string; code?: string };
  detail?: string | Array<{ msg?: string }>;
};

type RetryRequest = InternalAxiosRequestConfig & { _retry?: boolean };
let refreshInFlight: Promise<void> | null = null;

export async function refreshSession(): Promise<void> {
  if (refreshInFlight) return refreshInFlight;
  refreshInFlight = (async () => {
    const storedRefresh = typeof window !== "undefined" ? localStorage.getItem("relay_refresh_token") : null;
    const response = await axios.post<{ access_token?: string; refresh_token?: string }>(
      `${resolvedApiBaseUrl}/auth/refresh`,
      storedRefresh ? { refresh_token: storedRefresh } : {},
      { withCredentials: true, headers: apiRequestHeaders(resolvedApiBaseUrl) },
    );
    if (response.data?.access_token) {
      setStoredTokens(response.data.access_token, response.data.refresh_token);
    }
  })();
  try {
    return await refreshInFlight;
  } finally {
    refreshInFlight = null;
  }
}

function isAuthenticationRoute(url?: string): boolean {
  return !!url && ["/auth/login", "/auth/register", "/auth/refresh"].some((route) => url.includes(route));
}

apiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError<ApiErrorBody>) => {
    const request = error.config as RetryRequest | undefined;
    if (error.response?.status !== 401 || !request || request._retry || isAuthenticationRoute(request.url)) {
      return Promise.reject(error);
    }
    request._retry = true;
    try {
      await refreshSession();
      return apiClient(request);
    } catch (refreshError) {
      if (typeof window !== "undefined" && window.location.pathname !== "/login") {
        window.location.assign("/login?reason=session-expired");
      }
      return Promise.reject(refreshError);
    }
  },
);

export function getApiErrorMessage(error: unknown, fallback: string): string {
  const response = (error as { response?: { data?: ApiErrorBody } }).response;
  if (!response) return "Could not reach the server. Check that the API is running and try again.";
  const body = response.data;
  if (body?.error?.message) return body.error.message;
  if (typeof body?.detail === "string") return body.detail;
  if (Array.isArray(body?.detail)) {
    const messages = body.detail.map((item) => item.msg).filter(Boolean);
    if (messages.length) return messages.join(" ");
  }
  return fallback;
}

export function getApiErrorCode(error: unknown): string | undefined {
  return (error as { response?: { data?: ApiErrorBody } }).response?.data?.error?.code;
}
