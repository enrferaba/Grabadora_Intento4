"use client";

import { useQuery } from "@tanstack/react-query";
import { StatCard } from "@/components/stat-card";
import { JobTable } from "@/components/job-table";
import { Activity, Timer, FileText, AlertTriangle } from "lucide-react";
import { getHealth, HealthResponse } from "@/lib/api";

export default function DashboardPage() {
  const { data } = useQuery({ queryKey: ["health"], queryFn: getHealth, refetchInterval: 10000 });

  const health: HealthResponse =
    data ?? {
      status: "error",
      time: new Date().toISOString(),
      version: "desconocida",
      license: { active: false, plan: "desconocido" },
      cuda_available: false,
      vad_available: false,
      missing_vad_assets: [],
      ffmpeg_path: null,
    };

  const gpuStatus = health.cuda_available ? "GPU lista" : "GPU no disponible";
  const vadStatus = health.vad_available ? "VAD activo" : "VAD desactivado";
  const ffmpegStatus = health.ffmpeg_path ? `FFmpeg: ${health.ffmpeg_path}` : "FFmpeg automático";
  const footer = `Licencia: ${health.license.plan} · ${gpuStatus} · ${vadStatus} · ${ffmpegStatus}`;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-white">Panel general</h1>
        <p className="text-sm text-zinc-500">Supervisa el estado del backend local y la cola de trabajos.</p>
      </div>
      {!health.vad_available && health.missing_vad_assets.length > 0 && (
        <div className="flex items-start gap-3 rounded-xl border border-yellow-600/40 bg-yellow-600/10 p-4">
          <AlertTriangle className="mt-0.5 h-5 w-5 text-yellow-400" />
          <div>
            <p className="text-sm font-semibold text-yellow-200">Faltan los modelos Silero para VAD</p>
            <p className="text-xs text-yellow-200/80">
              Se desactivó el filtrado de silencios. Añade los archivos {health.missing_vad_assets.join(", ") || "requeridos"} al
              directorio de assets o ejecuta <code>transcriptor doctor autotest</code> para intentar descargarlos automáticamente.
            </p>
          </div>
        </div>
      )}
      <div className="grid gap-4 md:grid-cols-3">
        <StatCard
          title="Estado API"
          value={health.status === "ok" ? "Operativa" : "Revisar"}
          footer={footer}
          icon={<Activity className="h-5 w-5 text-brand-500" />}
        />
        <StatCard
          title="Tiempo medio de resumen"
          value="< 30 s"
          footer="Objetivo para reuniones de 15 min"
          icon={<Timer className="h-5 w-5 text-brand-500" />}
        />
        <StatCard
          title="Exportaciones disponibles"
          value="DOCX / MD / JSON"
          footer="Siempre offline"
          icon={<FileText className="h-5 w-5 text-brand-500" />}
        />
      </div>
      <section className="space-y-3">
        <div>
          <h2 className="text-lg font-semibold text-white">Trabajos recientes</h2>
          <p className="text-sm text-zinc-500">Monitorea la cola en tiempo real. Se actualiza automáticamente.</p>
        </div>
        <JobTable />
      </section>
    </div>
  );
}
