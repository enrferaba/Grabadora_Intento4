"use client";

import { JobTable } from "@/components/job-table";

export default function JobsPage() {
  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-semibold text-white">Cola de trabajos</h1>
        <p className="text-sm text-zinc-500">Estado en vivo de todas las transcripciones y resúmenes.</p>
      </div>
      <JobTable />
    </div>
  );
}
