import { API_JSON_HEADERS, buildApiUrl } from "@/lib/config";

export interface HealthResponse {
  status: "ok" | "degraded" | "error";
  time: string;
  version: string;
  license: { active: boolean; plan: string; [key: string]: unknown };
  cuda_available: boolean;
  vad_available: boolean;
  missing_vad_assets: string[];
  ffmpeg_path: string | null;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(buildApiUrl(path), {
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
  return request<HealthResponse>("/health");
}
