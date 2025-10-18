"use client";

import { useQuery } from "@tanstack/react-query";
import { StatCard } from "@/components/stat-card";
import { JobTable } from "@/components/job-table";
import { Activity, Timer, FileText } from "lucide-react";
import { getHealth } from "@/lib/api";

export default function DashboardPage() {
  const { data } = useQuery({ queryKey: ["health"], queryFn: getHealth, refetchInterval: 10000 });

  const health = data ?? { status: "error", license: { plan: "desconocido" } };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-white">Panel general</h1>
        <p className="text-sm text-zinc-500">Supervisa el estado del backend local y la cola de trabajos.</p>
      </div>
      <div className="grid gap-4 md:grid-cols-3">
        <StatCard title="Estado API" value={health.status === "ok" ? "Operativa" : "Revisar"} footer={`Licencia: ${health.license?.plan ?? "N/A"}`} icon={<Activity className="h-5 w-5 text-brand-500" />} />
        <StatCard title="Tiempo medio de resumen" value="< 30 s" footer="Objetivo para reuniones de 15 min" icon={<Timer className="h-5 w-5 text-brand-500" />} />
        <StatCard title="Exportaciones disponibles" value="DOCX / MD / JSON" footer="Siempre offline" icon={<FileText className="h-5 w-5 text-brand-500" />} />
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
