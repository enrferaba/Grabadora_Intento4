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
  const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:4814"}/jobs`, { cache: "no-store" });
  if (!response.ok) {
    throw new Error("No se pudieron cargar los trabajos");
  }
  return response.json();
}
