export type SummaryRequest = {
  job_id: string;
  template: "atencion" | "comercial" | "soporte";
  mode: "redactado" | "extractivo" | "literal";
  language: "es" | "en";
  client_name?: string;
  meeting_date?: string;
};

export type SummaryResponse = {
  job_id: string;
  template: string;
  mode: string;
  fallback_used: boolean;
  generated_at: string;
  title: string;
  client: string | null;
  date: string | null;
  attendees: string[];
  summary: string;
  key_points: string[];
  actions: { owner: string; task: string; due?: string | null }[];
  risks: string[];
  next_steps: string[];
};

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:4814";

export async function createSummary(body: SummaryRequest): Promise<SummaryResponse> {
  const response = await fetch(`${BASE}/summarize`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body)
  });
  if (!response.ok) {
    throw new Error("No se pudo generar el resumen");
  }
  return response.json();
}

export async function exportSummary(body: SummaryRequest & { format: "markdown" | "docx" | "json" }): Promise<Blob> {
  const response = await fetch(`${BASE}/export`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body)
  });
  if (!response.ok) {
    throw new Error("No se pudo exportar el resumen");
  }
  return response.blob();
}
