const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:4814";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {})
    },
    cache: "no-store"
  });
  if (!response.ok) {
    throw new Error(`Error ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export function getHealth() {
  return request<{ status: string; license: { active: boolean; plan: string } }>("/health");
}
