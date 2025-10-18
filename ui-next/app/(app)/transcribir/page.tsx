"use client";

import { TranscribeForm } from "@/components/transcribe-form";

export default function TranscribirPage() {
  return (
    <div className="grid gap-6 md:grid-cols-[2fr_1fr]">
      <div className="space-y-4">
        <div>
          <h1 className="text-2xl font-semibold text-white">Transcribir archivos</h1>
          <p className="text-sm text-zinc-500">Sube audios o videos. Se procesan en segundo plano y podrás seguir trabajando.</p>
        </div>
        <TranscribeForm />
      </div>
      <aside className="space-y-4 rounded-xl border border-zinc-800 bg-zinc-900/40 p-6 text-sm text-zinc-400">
        <h2 className="text-lg font-semibold text-white">Consejos rápidos</h2>
        <ul className="space-y-2 list-disc pl-4">
          <li>Arrastra varios archivos al mismo tiempo; cada uno será un job independiente.</li>
          <li>El modo AUTO usa GPU si está disponible y cae a CPU en caso contrario.</li>
          <li>La detección VAD elimina silencios y mejora la estimación de tiempo restante.</li>
          <li>Mientras se transcribe puedes preparar resúmenes o exportaciones previas.</li>
        </ul>
      </aside>
    </div>
  );
}
