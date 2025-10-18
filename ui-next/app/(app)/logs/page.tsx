"use client";

export default function LogsPage() {
  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-semibold text-white">Logs y diagnósticos</h1>
        <p className="text-sm text-zinc-500">Todo se almacena en la carpeta de datos local para soporte sin internet.</p>
      </div>
      <div className="space-y-3 rounded-xl border border-zinc-800 bg-zinc-900/40 p-6 text-sm text-zinc-300">
        <p>
          Los registros rotativos están en <code>%APPDATA%/Transcriptor/logs</code>. Desde aquí podrás empaquetar un ZIP de
          diagnóstico junto con métricas de rendimiento para compartir con soporte cuando lo necesites.
        </p>
        <ul className="list-disc space-y-1 pl-4 text-xs text-zinc-400">
          <li>Tiempo de arranque, transcripción y resumen se guardan en local.</li>
          <li>Las exportaciones incluyen un hash para detectar corrupción.</li>
          <li>El modo servicio opcional reinicia el backend si detecta fallos.</li>
        </ul>
      </div>
    </div>
  );
}
