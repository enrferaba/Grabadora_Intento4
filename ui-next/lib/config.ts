function normaliseOrigin(origin: string): string | null {
  try {
    const url = new URL(origin);
    url.pathname = "";
    url.search = "";
    url.hash = "";
    return url.toString().replace(/\/$/, "");
  } catch (_error) {
    return null;
  }
}

const ENV_ORIGIN = process.env.NEXT_PUBLIC_API_URL?.trim();
export const API_ORIGIN = ENV_ORIGIN ? normaliseOrigin(ENV_ORIGIN) ?? "" : "";

if (ENV_ORIGIN && !API_ORIGIN) {
  console.warn(`[solo-local] NEXT_PUBLIC_API_URL inválida: ${ENV_ORIGIN}`);
}

if (API_ORIGIN && process.env.NODE_ENV !== "production") {
  try {
    const url = new URL(API_ORIGIN);
    if (url.hostname !== "127.0.0.1") {
      console.warn(
        `[solo-local] NEXT_PUBLIC_API_URL apunta a ${API_ORIGIN}. Cambia el host a 127.0.0.1 para mantener el modo solo local.`,
      );
    }
  } catch (error) {
    console.warn("[solo-local] URL inválida para NEXT_PUBLIC_API_URL:", error);
  }
}

export function resolveApiOrigin(): string {
  if (API_ORIGIN) {
    return API_ORIGIN;
  }
  if (typeof window !== "undefined" && window.location) {
    return window.location.origin.replace(/\/$/, "");
  }
  return "";
}

export function buildApiUrl(path: string): string {
  const base = resolveApiOrigin();
  const normalisedPath = path.startsWith("/") ? path : `/${path}`;
  return base ? `${base}${normalisedPath}` : normalisedPath;
}

export const API_JSON_HEADERS = {
  "Content-Type": "application/json",
};
