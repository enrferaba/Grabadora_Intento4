import { buildApiUrl } from "@/lib/config";

export type Job = {
  id: string;
  filename: string;
  status: string;
  progress: number;
  duration_seconds: number | null;
  updated_at: string;
};

export type JobsResponse = {
  jobs: Job[];
};

export async function fetchJobs(): Promise<JobsResponse> {
  const response = await fetch(buildApiUrl("/jobs"), { cache: "no-store" });
  if (!response.ok) {
    throw new Error("No se pudieron cargar los trabajos");
  }
  return response.json();
}
