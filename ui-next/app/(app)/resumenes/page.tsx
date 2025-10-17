import { SummaryGenerator } from "@/components/summary-generator";

export default function ResumenesPage() {
  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-semibold text-white">Generar resúmenes</h1>
        <p className="text-sm text-zinc-500">Convierte cualquier transcripción en un informe profesional listo para compartir.</p>
      </div>
      <SummaryGenerator />
    </div>
  );
}
