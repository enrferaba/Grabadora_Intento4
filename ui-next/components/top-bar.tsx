"use client";

import { Bell, Cpu } from "lucide-react";
import { useEffect, useState } from "react";

export function TopBar() {
  const [now, setNow] = useState<Date | null>(null);

  useEffect(() => {
    const update = () => setNow(new Date());

    update();
    const id = setInterval(update, 30_000);
    return () => clearInterval(id);
  }, []);

  return (
    <header className="flex items-center justify-between border-b border-zinc-800 bg-zinc-950/80 px-6 py-3">
      <div className="text-sm text-zinc-400">
        {now ? now.toLocaleString("es-ES") : "—"}
      </div>
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-2 rounded-lg border border-zinc-700 px-3 py-1 text-xs text-zinc-300">
          <Cpu className="h-4 w-4" /> Solo local activo
        </div>
        <button className="relative rounded-full border border-zinc-700 p-2 text-zinc-300 hover:text-white">
          <Bell className="h-4 w-4" />
          <span className="absolute -right-1 -top-1 h-2 w-2 rounded-full bg-brand-500" />
        </button>
      </div>
    </header>
  );
}
