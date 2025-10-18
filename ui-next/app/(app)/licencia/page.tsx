"use client";

import { LicensePanel } from "@/components/license-panel";

export default function LicenciaPage() {
  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-semibold text-white">Licencia</h1>
        <p className="text-sm text-zinc-500">Gestiona el token firmado, libera dispositivos y revisa las features activas.</p>
      </div>
      <LicensePanel />
      <div className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-6 text-xs text-zinc-400">
        <h2 className="text-sm font-semibold text-white">¿Cómo activar?</h2>
        <ol className="mt-2 list-decimal space-y-1 pl-4">
          <li>Coloca el archivo <code>licencia.json</code> junto al ejecutable o en la carpeta de datos.</li>
          <li>Introduce la contraseña de activación la primera vez que abras la app.</li>
          <li>El backend validará la firma RS256 offline y habilitará las funciones Pro autorizadas.</li>
        </ol>
      </div>
    </div>
  );
}
