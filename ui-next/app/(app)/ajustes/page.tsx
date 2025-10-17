export default function AjustesPage() {
  const preferences = [
    { title: "Carpeta de salida", description: "Define dónde se guardan transcripciones y resúmenes exportados." },
    { title: "Modo solo local", description: "Activa o desactiva conexiones salientes según tu política de privacidad." },
    { title: "Retención automática", description: "Programa la limpieza de trabajos antiguos para ahorrar espacio." },
    { title: "Atajos globales", description: "Configura teclas rápidas para grabar, pausar o abrir la bandeja." }
  ];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-white">Ajustes</h1>
        <p className="text-sm text-zinc-500">Preferencias que se guardan en el perfil local del usuario.</p>
      </div>
      <div className="space-y-4">
        {preferences.map((item) => (
          <div key={item.title} className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-4">
            <div className="text-sm font-medium text-white">{item.title}</div>
            <div className="text-xs text-zinc-500">{item.description}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
