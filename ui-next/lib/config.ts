const DEFAULT_API_ORIGIN = "http://127.0.0.1:4814";

function normaliseOrigin(origin: string): string {
  try {
    const url = new URL(origin);
    url.pathname = "";
    url.search = "";
    url.hash = "";
    return url.toString().replace(/\/$/, "");
  } catch (_error) {
    return DEFAULT_API_ORIGIN;
  }
}

export const API_ORIGIN = normaliseOrigin(
  process.env.NEXT_PUBLIC_API_URL ?? DEFAULT_API_ORIGIN,
);

if (process.env.NODE_ENV !== "production") {
  try {
    const url = new URL(API_ORIGIN);
    if (url.hostname !== "127.0.0.1") {
      console.warn(
        `[solo-local] NEXT_PUBLIC_API_URL apunta a ${API_ORIGIN}. Cambia el host a 127.0.0.1 para mantener el modo solo local.`,
      );
    }
  } catch (error) {
    console.warn("[solo-local] NEXT_PUBLIC_API_URL inválida:", error);
  }
}

export const API_JSON_HEADERS = {
  "Content-Type": "application/json",
};
