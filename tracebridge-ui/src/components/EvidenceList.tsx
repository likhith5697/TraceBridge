import { CheckCircle2, XCircle } from "lucide-react";
import type { EvidenceItem } from "../types";

export function EvidenceList({ items }: { items: EvidenceItem[] }) {
  if (items.length === 0) return null;

  return (
    <section className="rounded-2xl border border-zinc-800 bg-zinc-900/40 p-6">
      <h3 className="text-sm font-medium text-zinc-300">Evidence</h3>
      <ul className="mt-4 flex flex-col gap-3">
        {items.map((item) => (
          <li
            key={item.id}
            className="flex items-start gap-3 rounded-lg border border-zinc-800/80 bg-zinc-950/50 px-4 py-3"
          >
            <span className="mt-0.5 rounded-md bg-zinc-900 px-1.5 py-0.5 font-mono text-[11px] text-zinc-500">
              {item.id}
            </span>
            {item.success ? (
              <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-500" />
            ) : (
              <XCircle className="mt-0.5 h-4 w-4 shrink-0 text-rose-500" />
            )}
            <div className="min-w-0">
              <p className="text-[11px] uppercase tracking-wide text-zinc-600">
                {item.source} &middot; <span className="font-mono normal-case">{item.tool}</span>
              </p>
              <p className="mt-0.5 truncate text-sm text-zinc-300" title={item.summary}>
                {item.summary}
              </p>
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}
