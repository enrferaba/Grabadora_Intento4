import { API_JSON_HEADERS, API_ORIGIN } from "@/lib/config";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_ORIGIN}${path}`, {
    ...init,
    headers: {
      ...API_JSON_HEADERS,
      ...(init?.headers ?? {}),
    },
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(`Error ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export function getHealth() {
  return request<{ status: string; license: { active: boolean; plan: string } }>("/health");
}
