import { AlertTriangle, CheckCircle2, HelpCircle } from "lucide-react";
import type { Confidence, FinalResult, Outcome } from "../types";

const OUTCOME_STYLES: Record<Outcome, { text: string; bg: string; border: string }> = {
  SUCCESS: { text: "text-emerald-400", bg: "bg-emerald-950/40", border: "border-emerald-800/60" },
  FAILURE: { text: "text-rose-400", bg: "bg-rose-950/40", border: "border-rose-800/60" },
  INCOMPLETE: { text: "text-amber-400", bg: "bg-amber-950/40", border: "border-amber-800/60" },
};

const OUTCOME_ICON: Record<Outcome, typeof CheckCircle2> = {
  SUCCESS: CheckCircle2,
  FAILURE: AlertTriangle,
  INCOMPLETE: HelpCircle,
};

const CONFIDENCE_STYLES: Record<Confidence, string> = {
  HIGH: "text-emerald-400 border-emerald-800/60 bg-emerald-950/30",
  MEDIUM: "text-amber-400 border-amber-800/60 bg-amber-950/30",
  LOW: "text-rose-400 border-rose-800/60 bg-rose-950/30",
};

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <p className="text-[11px] uppercase tracking-wide text-zinc-600">{label}</p>
      <div className="mt-1 text-sm text-zinc-200">{children}</div>
    </div>
  );
}

export function ResultPanel({ result }: { result: FinalResult }) {
  const style = OUTCOME_STYLES[result.outcome];
  const Icon = OUTCOME_ICON[result.outcome];

  return (
    <section className={`rounded-2xl border ${style.border} ${style.bg} p-6`}>
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="flex items-center gap-3">
          <Icon className={`h-6 w-6 ${style.text}`} strokeWidth={1.75} />
          <div>
            <p className="text-[11px] uppercase tracking-wide text-zinc-500">Outcome</p>
            <p className={`text-xl font-semibold ${style.text}`}>{result.outcome}</p>
          </div>
        </div>
        <span
          className={`rounded-full border px-3 py-1 text-xs font-medium ${CONFIDENCE_STYLES[result.confidence]}`}
        >
          {result.confidence} confidence
        </span>
      </div>

      <div className="mt-6 grid grid-cols-1 gap-5 sm:grid-cols-2">
        {result.failureBoundary && (
          <Field label="Failure Boundary">
            <span className="font-mono">{result.failureBoundary}</span>
          </Field>
        )}
        {result.observedError && (
          <Field label="Observed Error">
            <span className="font-mono text-rose-300">{result.observedError}</span>
          </Field>
        )}
        {result.recommendedInvestigationArea && (
          <Field label="Recommended Investigation">{result.recommendedInvestigationArea}</Field>
        )}
      </div>

      <div className="mt-6 border-t border-zinc-800/80 pt-5">
        <Field label="Interpretation">
          <p className="leading-relaxed text-zinc-300">{result.interpretation}</p>
        </Field>
      </div>

      {result.limitations && (
        <div className="mt-5 rounded-lg border border-zinc-800 bg-zinc-950/60 p-4">
          <p className="text-[11px] uppercase tracking-wide text-zinc-600">Limitations</p>
          <p className="mt-1 text-sm leading-relaxed text-zinc-400">{result.limitations}</p>
        </div>
      )}

      <p className="mt-5 text-[11px] text-zinc-600">
        {result.stats.iterations} iteration(s) &middot; {result.stats.llmCalls} LLM call(s) &middot;{" "}
        {result.stats.toolCalls} tool call(s) &middot; {result.stats.durationSeconds.toFixed(1)}s
      </p>
    </section>
  );
}
