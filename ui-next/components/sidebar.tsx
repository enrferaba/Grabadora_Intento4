"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { clsx } from "clsx";
import { Gauge, FileAudio2, ListTodo, FileText, Settings, BadgeCheck, Bug } from "lucide-react";

const items = [
  { href: "/dashboard", label: "Dashboard", icon: Gauge },
  { href: "/transcribir", label: "Transcribir", icon: FileAudio2 },
  { href: "/jobs", label: "Jobs", icon: ListTodo },
  { href: "/resumenes", label: "Resúmenes", icon: FileText },
  { href: "/ajustes", label: "Ajustes", icon: Settings },
  { href: "/licencia", label: "Licencia", icon: BadgeCheck },
  { href: "/logs", label: "Logs", icon: Bug }
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="flex w-64 flex-col border-r border-zinc-800 bg-zinc-950/80 backdrop-blur">
      <div className="px-6 py-6">
        <div className="text-xs uppercase tracking-wide text-zinc-500">Transcriptor de FERIA</div>
        <div className="text-xl font-semibold text-white">Panel local</div>
      </div>
      <nav className="flex-1 space-y-1 px-3">
        {items.map((item) => {
          const Icon = item.icon;
          const active = pathname === item.href || pathname?.startsWith(`${item.href}/`);
          return (
            <Link
              key={item.href}
              href={item.href}
              className={clsx(
                "flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition",
                active ? "bg-brand-600/20 text-brand-200" : "text-zinc-400 hover:bg-zinc-800 hover:text-white"
              )}
            >
              <Icon className="h-4 w-4" />
              {item.label}
            </Link>
          );
        })}
      </nav>
      <div className="px-4 py-4 text-xs text-zinc-500">
        Solo local • v0.1
      </div>
    </aside>
  );
}
