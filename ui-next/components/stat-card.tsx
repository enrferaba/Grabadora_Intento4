import { ReactNode } from "react";

export function StatCard({ title, value, footer, icon }: { title: string; value: string; footer?: string; icon?: ReactNode }) {
  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-4 shadow-lg shadow-black/40">
      <div className="flex items-center justify-between text-sm text-zinc-400">
        <span>{title}</span>
        {icon}
      </div>
      <div className="mt-3 text-2xl font-semibold text-white">{value}</div>
      {footer ? <div className="mt-2 text-xs text-zinc-500">{footer}</div> : null}
    </div>
  );
}
