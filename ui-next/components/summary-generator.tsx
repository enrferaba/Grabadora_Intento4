"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { fetchJobs } from "@/lib/jobs";
import { createSummary, exportSummary, SummaryRequest, SummaryResponse } from "@/lib/summaries";
import { Loader2, Download } from "lucide-react";

const templates = [
  { value: "comercial", label: "Reunión comercial" },
  { value: "atencion", label: "Atención al cliente" },
  { value: "soporte", label: "Soporte técnico" }
] as const;

const modes = [
  { value: "redactado", label: "Redactado (Pro)" },
  { value: "extractivo", label: "Extractivo" },
  { value: "literal", label: "Literal" }
] as const;

export function SummaryGenerator() {
  const jobsQuery = useQuery({ queryKey: ["jobs"], queryFn: fetchJobs, refetchInterval: 7000 });
  const [selectedJob, setSelectedJob] = useState<string>("");
  const [template, setTemplate] = useState<SummaryRequest["template"]>("comercial");
  const [mode, setMode] = useState<SummaryRequest["mode"]>("redactado");
  const [language, setLanguage] = useState<SummaryRequest["language"]>("es");
  const [summary, setSummary] = useState<SummaryResponse | null>(null);
  const mutation = useMutation({
    mutationFn: (body: SummaryRequest) => createSummary(body),
    onSuccess: (data) => setSummary(data)
  });

  const isLoading = jobsQuery.isLoading || mutation.isPending;
  const jobs = jobsQuery.data?.jobs ?? [];

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedJob) {
      return;
    }
    mutation.mutate({ job_id: selectedJob, template, mode, language });
  }

  async function handleExport(format: "markdown" | "docx" | "json") {
    if (!summary) return;
    const blob = await exportSummary({ job_id: summary.job_id, template, mode, language, format });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `${summary.job_id}-${format}.${format === "markdown" ? "md" : format}`;
    anchor.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="space-y-4">
      <form onSubmit={handleSubmit} className="space-y-4 rounded-xl border border-zinc-800 bg-zinc-900/60 p-6">
        <div>
          <label className="text-sm font-medium text-white">Selecciona un job completado</label>
          <select
            value={selectedJob}
            onChange={(event) => setSelectedJob(event.target.value)}
            className="mt-2 w-full rounded-lg border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm text-zinc-200"
          >
            <option value="">Escoge una transcripción disponible…</option>
            {jobs
              .filter((job) => job.status === "completed")
              .map((job) => (
                <option key={job.id} value={job.id}>
                  {job.filename}
                </option>
              ))}
          </select>
        </div>
        <div className="grid gap-4 md:grid-cols-3">
          <div className="space-y-2">
            <span className="text-xs uppercase text-zinc-500">Plantilla</span>
            <div className="flex gap-2">
              {templates.map((item) => (
                <button
                  key={item.value}
                  type="button"
                  onClick={() => setTemplate(item.value)}
                  className={`flex-1 rounded-lg border px-3 py-2 text-sm ${template === item.value ? "border-brand-600 bg-brand-600/20 text-white" : "border-zinc-700 text-zinc-400"}`}
                >
                  {item.label}
                </button>
              ))}
            </div>
          </div>
          <div className="space-y-2">
            <span className="text-xs uppercase text-zinc-500">Modo</span>
            <div className="flex gap-2">
              {modes.map((item) => (
                <button
                  key={item.value}
                  type="button"
                  onClick={() => setMode(item.value)}
                  className={`flex-1 rounded-lg border px-3 py-2 text-sm ${mode === item.value ? "border-brand-600 bg-brand-600/20 text-white" : "border-zinc-700 text-zinc-400"}`}
                >
                  {item.label}
                </button>
              ))}
            </div>
          </div>
          <div className="space-y-2">
            <span className="text-xs uppercase text-zinc-500">Idioma</span>
            <div className="flex gap-2">
              {["es", "en"].map((option) => (
                <button
                  key={option}
                  type="button"
                  onClick={() => setLanguage(option as SummaryRequest["language"])}
                  className={`flex-1 rounded-lg border px-3 py-2 text-sm ${language === option ? "border-brand-600 bg-brand-600/20 text-white" : "border-zinc-700 text-zinc-400"}`}
                >
                  {option.toUpperCase()}
                </button>
              ))}
            </div>
          </div>
        </div>
        <button
          type="submit"
          disabled={isLoading || !selectedJob}
          className="w-full rounded-lg bg-brand-600 px-4 py-2 text-sm font-semibold text-white shadow-lg shadow-brand-600/40 transition hover:bg-brand-500 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {mutation.isPending ? <Loader2 className="mx-auto h-4 w-4 animate-spin" /> : "Generar resumen"}
        </button>
      </form>

      {summary ? (
        <div className="space-y-4 rounded-xl border border-zinc-800 bg-zinc-900/40 p-6">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-lg font-semibold text-white">{summary.title}</h3>
              <p className="text-xs text-zinc-500">
                {summary.client ?? "Sin cliente"} • {summary.date ?? "Fecha no indicada"}
              </p>
            </div>
            <div className="flex gap-2">
              {["markdown", "docx", "json"].map((format) => (
                <button
                  key={format}
                  onClick={() => handleExport(format as "markdown" | "docx" | "json")}
                  className="flex items-center gap-2 rounded-lg border border-zinc-700 px-3 py-1 text-xs text-zinc-300 hover:border-brand-500 hover:text-white"
                >
                  <Download className="h-3 w-3" /> {format.toUpperCase()}
                </button>
              ))}
            </div>
          </div>
          <p className="text-sm text-zinc-200">{summary.summary}</p>
          <div className="grid gap-4 md:grid-cols-3">
            <div>
              <h4 className="text-xs uppercase text-zinc-500">Puntos clave</h4>
              <ul className="mt-2 space-y-1 text-sm text-zinc-300">
                {summary.key_points.map((point, index) => (
                  <li key={index}>• {point}</li>
                ))}
              </ul>
            </div>
            <div>
              <h4 className="text-xs uppercase text-zinc-500">Acciones</h4>
              <ul className="mt-2 space-y-1 text-sm text-zinc-300">
                {summary.actions.map((action, index) => (
                  <li key={index}>
                    • {action.owner}: {action.task}
                  </li>
                ))}
              </ul>
            </div>
            <div>
              <h4 className="text-xs uppercase text-zinc-500">Próximos pasos</h4>
              <ul className="mt-2 space-y-1 text-sm text-zinc-300">
                {summary.next_steps.map((step, index) => (
                  <li key={index}>• {step}</li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
