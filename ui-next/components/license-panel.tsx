"use client";

import { useQuery } from "@tanstack/react-query";
import { fetchLicenseStatus } from "@/lib/license";
import { ShieldCheck, ShieldAlert } from "lucide-react";

export function LicensePanel() {
  const { data, isLoading, refetch } = useQuery({ queryKey: ["license"], queryFn: fetchLicenseStatus });

  if (isLoading) {
    return <div className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-6 text-sm text-zinc-400">Comprobando licencia…</div>;
  }

  if (!data) {
    return <div className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-6 text-sm text-zinc-400">No se pudo cargar el estado de la licencia.</div>;
  }

  const Icon = data.active ? ShieldCheck : ShieldAlert;

  return (
    <div className="space-y-4 rounded-xl border border-zinc-800 bg-zinc-900/60 p-6">
      <div className="flex items-center gap-3">
        <Icon className={`h-6 w-6 ${data.active ? "text-emerald-400" : "text-red-400"}`} />
        <div>
          <div className="text-sm font-semibold text-white">Plan {data.plan}</div>
          <div className="text-xs text-zinc-500">
            {data.active ? "Funciones Pro activas" : data.reason ?? "Licencia inactiva"}
          </div>
        </div>
      </div>
      <div className="grid gap-2 text-xs text-zinc-400">
        <div>Caducidad: {data.expires_at ?? "Sin fecha"}</div>
        <div>En gracia: {data.in_grace ? "sí" : "no"}</div>
      </div>
      <div>
        <div className="text-xs uppercase text-zinc-500">Features habilitadas</div>
        <ul className="mt-2 space-y-1 text-sm text-zinc-300">
          {data.features.map((feature) => (
            <li key={feature}>• {feature}</li>
          ))}
        </ul>
      </div>
      <button
        type="button"
        onClick={() => refetch()}
        className="rounded-lg border border-zinc-700 px-4 py-2 text-xs text-zinc-300 hover:border-brand-500 hover:text-white"
      >
        Volver a comprobar
      </button>
    </div>
  );
}
