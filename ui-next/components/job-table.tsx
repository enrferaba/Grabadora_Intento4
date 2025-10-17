"use client";

import { useQuery } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import { fetchJobs } from "@/lib/jobs";

export function JobTable() {
  const { data, isLoading } = useQuery({ queryKey: ["jobs"], queryFn: fetchJobs, refetchInterval: 5000 });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-10 text-zinc-400">
        <Loader2 className="mr-2 h-5 w-5 animate-spin" /> Cargando trabajos…
      </div>
    );
  }

  const jobs = data?.jobs ?? [];
  if (!jobs.length) {
    return <div className="rounded-lg border border-dashed border-zinc-800 p-6 text-center text-zinc-500">Aún no hay trabajos en la cola.</div>;
  }

  return (
    <div className="overflow-hidden rounded-xl border border-zinc-800">
      <table className="min-w-full divide-y divide-zinc-800">
        <thead className="bg-zinc-900/80 text-xs uppercase tracking-wide text-zinc-500">
          <tr>
            <th className="px-4 py-3 text-left">Archivo</th>
            <th className="px-4 py-3 text-left">Estado</th>
            <th className="px-4 py-3 text-left">Progreso</th>
            <th className="px-4 py-3 text-left">Duración</th>
            <th className="px-4 py-3 text-left">Actualizado</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-zinc-800 text-sm text-zinc-300">
          {jobs.map((job) => (
            <tr key={job.id} className="hover:bg-zinc-900/60">
              <td className="px-4 py-3 font-medium text-white">{job.filename}</td>
              <td className="px-4 py-3 capitalize text-zinc-400">{job.status}</td>
              <td className="px-4 py-3">
                <div className="flex items-center gap-3">
                  <div className="h-2 flex-1 overflow-hidden rounded-full bg-zinc-800">
                    <div className="h-2 rounded-full bg-brand-500" style={{ width: `${Math.min(job.progress, 100)}%` }} />
                  </div>
                  <span className="w-12 text-right text-xs text-zinc-400">{Math.round(job.progress)}%</span>
                </div>
              </td>
              <td className="px-4 py-3 text-xs text-zinc-400">{job.duration_seconds ? `${Math.round(job.duration_seconds)} s` : "—"}</td>
              <td className="px-4 py-3 text-xs text-zinc-500">{new Date(job.updated_at).toLocaleTimeString("es-ES")}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
