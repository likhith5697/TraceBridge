import { Clock, History } from "lucide-react";
import type { HistorySummary, Outcome } from "../types";

const OUTCOME_DOT: Record<Outcome, string> = {
  SUCCESS: "bg-emerald-400",
  FAILURE: "bg-rose-500",
  INCOMPLETE: "bg-amber-400",
};

function formatTime(unixSeconds: number): string {
  return new Date(unixSeconds * 1000).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

interface Props {
  history: HistorySummary[];
  activeInvestigationId?: string;
  onSelect: (investigationId: string) => void;
}

export function HistorySidebar({ history, activeInvestigationId, onSelect }: Props) {
  return (
    <aside className="h-fit rounded-2xl border border-zinc-800 bg-zinc-900/40 p-5 lg:sticky lg:top-24">
      <div className="flex items-center gap-2 text-sm font-medium text-zinc-300">
        <History className="h-4 w-4 text-zinc-500" />
        Recent investigations
      </div>

      {history.length === 0 ? (
        <p className="mt-4 text-xs text-zinc-600">Nothing investigated yet this session.</p>
      ) : (
        <ul className="mt-4 flex flex-col gap-1">
          {history.map((item) => (
            <li key={item.investigationId}>
              <button
                onClick={() => onSelect(item.investigationId)}
                className={`w-full rounded-lg px-3 py-2.5 text-left transition hover:bg-zinc-800/60 ${
                  activeInvestigationId === item.investigationId ? "bg-zinc-800/80" : ""
                }`}
              >
                <div className="flex items-center gap-2">
                  <span className={`h-1.5 w-1.5 shrink-0 rounded-full ${OUTCOME_DOT[item.outcome]}`} />
                  <span className="truncate font-mono text-xs text-zinc-300">{item.correlationId}</span>
                </div>
                <div className="mt-1 flex items-center gap-2 pl-3.5 text-[11px] text-zinc-600">
                  <span>{item.outcome}</span>
                  <span>&middot;</span>
                  <Clock className="h-3 w-3" />
                  <span>{formatTime(item.timestamp)}</span>
                  <span>&middot;</span>
                  <span>{item.durationSeconds.toFixed(1)}s</span>
                </div>
              </button>
            </li>
          ))}
        </ul>
      )}
    </aside>
  );
}
