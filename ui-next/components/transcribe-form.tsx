"use client";

import { useState } from "react";
import { clsx } from "clsx";
import { API_ORIGIN } from "@/lib/config";

export function TranscribeForm() {
  const [device, setDevice] = useState<"auto" | "cpu" | "cuda">("auto");
  const [vad, setVad] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formData = new FormData(event.currentTarget);
    const file = formData.get("file") as File | null;
    if (!file) {
      setMessage("Selecciona un audio para comenzar");
      return;
    }
    setUploading(true);
    setMessage(null);
    formData.set("device", device);
    formData.set("vad", String(vad));
    try {
      const response = await fetch(`${API_ORIGIN}/transcribe`, {
        method: "POST",
        body: formData,
      });
      if (!response.ok) {
        throw new Error("Error al subir el audio");
      }
      setMessage("Trabajo enviado a la cola. Revisa la pestaña Jobs.");
      event.currentTarget.reset();
    } catch (error) {
      setMessage((error as Error).message);
    } finally {
      setUploading(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4 rounded-xl border border-zinc-800 bg-zinc-900/60 p-6">
      <div>
        <label className="text-sm font-medium text-white">Archivo de audio o video</label>
        <input
          type="file"
          name="file"
          accept="audio/*,video/*"
          className="mt-2 w-full rounded border border-dashed border-zinc-700 bg-zinc-950 px-4 py-6 text-sm text-zinc-400 file:hidden"
        />
        <p className="mt-2 text-xs text-zinc-500">Arrastra y suelta o haz clic para seleccionar. Se procesa 100% en local.</p>
      </div>
      <div className="grid gap-4 md:grid-cols-2">
        <div className="space-y-2">
          <span className="text-xs uppercase text-zinc-500">Dispositivo</span>
          <div className="flex gap-2">
            {["auto", "cpu", "cuda"].map((option) => (
              <button
                type="button"
                key={option}
                onClick={() => setDevice(option as typeof device)}
                className={clsx(
                  "flex-1 rounded-lg border px-3 py-2 text-sm",
                  device === option ? "border-brand-600 bg-brand-600/20 text-white" : "border-zinc-700 text-zinc-400"
                )}
              >
                {option.toUpperCase()}
              </button>
            ))}
          </div>
        </div>
        <div className="space-y-2">
          <span className="text-xs uppercase text-zinc-500">Detección de voz</span>
          <button
            type="button"
            onClick={() => setVad((value) => !value)}
            className={clsx(
              "w-full rounded-lg border px-3 py-2 text-sm",
              vad ? "border-brand-600 bg-brand-600/20 text-white" : "border-zinc-700 text-zinc-400"
            )}
          >
            {vad ? "Activada (filtra silencios)" : "Desactivada"}
          </button>
        </div>
      </div>
      <button
        type="submit"
        disabled={uploading}
        className="w-full rounded-lg bg-brand-600 px-4 py-2 text-sm font-semibold text-white shadow-lg shadow-brand-600/40 transition hover:bg-brand-500 disabled:cursor-not-allowed disabled:opacity-60"
      >
        {uploading ? "Subiendo…" : "Enviar a transcribir"}
      </button>
      {message ? <div className="rounded border border-zinc-700 bg-zinc-900/70 px-4 py-2 text-sm text-zinc-300">{message}</div> : null}
    </form>
  );
}
