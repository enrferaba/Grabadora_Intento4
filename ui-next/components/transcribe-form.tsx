"use client";

import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { clsx } from "clsx";
import { buildApiUrl } from "@/lib/config";
import { getHealth, HealthResponse } from "@/lib/api";

export function TranscribeForm() {
  const formRef = useRef<HTMLFormElement | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const [device, setDevice] = useState<"auto" | "cpu" | "cuda">("auto");
  const [vad, setVad] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);

  const { data: health } = useQuery<HealthResponse>({
    queryKey: ["health"],
    queryFn: getHealth,
    refetchInterval: 15000,
  });
  const cudaAvailable = health?.cuda_available ?? false;
  const vadAvailable = health?.vad_available ?? true;
  const missingVadAssets = health?.missing_vad_assets ?? [];

  useEffect(() => {
    if (!cudaAvailable && device === "cuda") {
      setDevice("cpu");
    }
  }, [cudaAvailable, device]);

  useEffect(() => {
    if (!vadAvailable && vad) {
      setVad(false);
    }
  }, [vadAvailable, vad]);

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();

    const file = selectedFile;
    if (!file) {
      setMessage("Selecciona un audio para comenzar");
      return;
    }

    const effectiveDevice = device === "cuda" && !cudaAvailable ? "cpu" : device;
    const effectiveVad = vad && vadAvailable;

    const formData = new FormData();
    formData.append("file", file);
    formData.append("device", effectiveDevice);
    formData.append("vad", String(effectiveVad));

    try {
      setUploading(true);
      setMessage(null);

      const res = await fetch(buildApiUrl("/transcribe"), {
        method: "POST",
        body: formData,
      });
      if (!res.ok) throw new Error("Error al subir el audio");

      setMessage("Trabajo enviado a la cola. Revisa la pestaña Jobs.");
    } catch (err) {
      setMessage((err as Error).message);
    } finally {
      setUploading(false);

      formRef.current?.reset();
      if (fileInputRef.current) fileInputRef.current.value = "";
      setSelectedFile(null);
      setDevice("auto");
      setVad(vadAvailable);
    }
  }

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.currentTarget.files?.[0] ?? null;
    setSelectedFile(file);
  }

  return (
    <form
      ref={formRef}
      onSubmit={handleSubmit}
      className="space-y-4 rounded-xl border border-zinc-800 bg-zinc-900/60 p-6"
    >
      <div>
        <label className="text-sm font-medium text-white">Archivo de audio o video</label>
        <input
          ref={fileInputRef}
          type="file"
          name="file"
          accept="audio/*,video/*"
          onChange={handleFileChange}
          className="mt-2 w-full rounded border border-dashed border-zinc-700 bg-zinc-950 px-4 py-6 text-sm text-zinc-400 file:hidden"
        />
        <p className="mt-2 text-xs text-zinc-500">
          Arrastra y suelta o haz clic para seleccionar. Se procesa 100% en local.
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <div className="space-y-2">
          <span className="text-xs uppercase text-zinc-500">Dispositivo</span>
          <div className="flex gap-2">
            {["auto", "cpu", "cuda"].map((option) => {
              const isCuda = option === "cuda";
              const disabled = isCuda && !cudaAvailable;
              return (
                <button
                  type="button"
                  key={option}
                  onClick={() => (!disabled ? setDevice(option as typeof device) : null)}
                  disabled={disabled}
                  className={clsx(
                    "flex-1 rounded-lg border px-3 py-2 text-sm",
                    device === option
                      ? "border-brand-600 bg-brand-600/20 text-white"
                      : "border-zinc-700 text-zinc-400",
                    disabled ? "cursor-not-allowed opacity-50" : null,
                  )}
                >
                  {option.toUpperCase()}
                </button>
              );
            })}
          </div>
          {!cudaAvailable && (
            <p className="text-xs text-zinc-500">GPU no detectada; las transcripciones usarán CPU automáticamente.</p>
          )}
        </div>

        <div className="space-y-2">
          <span className="text-xs uppercase text-zinc-500">Detección de voz</span>
          <button
            type="button"
            onClick={() => (vadAvailable ? setVad((v) => !v) : null)}
            disabled={!vadAvailable}
            className={clsx(
              "w-full rounded-lg border px-3 py-2 text-sm",
              vad
                ? "border-brand-600 bg-brand-600/20 text-white"
                : "border-zinc-700 text-zinc-400",
              !vadAvailable ? "cursor-not-allowed opacity-50" : null,
            )}
          >
            {vad ? "Activada (filtra silencios)" : "Desactivada"}
          </button>
          {!vadAvailable && (
            <p className="text-xs text-zinc-500">
              Faltan los modelos Silero ({missingVadAssets.join(", ") || "no detectados"}). Ejecuta "transcriptor doctor autotest"
              para intentar descargarlos automáticamente.
            </p>
          )}
        </div>
      </div>

      <button
        type="submit"
        disabled={uploading}
        className="w-full rounded-lg bg-brand-600 px-4 py-2 text-sm font-semibold text-white shadow-lg shadow-brand-600/40 transition hover:bg-brand-500 disabled:cursor-not-allowed disabled:opacity-60"
      >
        {uploading ? "Subiendo…" : "Enviar a transcribir"}
      </button>

      {message && (
        <div className="rounded border border-zinc-700 bg-zinc-900/70 px-4 py-2 text-sm text-zinc-300">
          {message}
        </div>
      )}
    </form>
  );
}
