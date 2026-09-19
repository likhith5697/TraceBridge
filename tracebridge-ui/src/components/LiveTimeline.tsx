import { CheckCircle2, CircleDot, Cpu, Database, Loader2, XCircle } from "lucide-react";
import type { LiveStep } from "../types";

interface Props {
  correlationId: string;
  steps: LiveStep[];
  isRunning: boolean;
}

export function LiveTimeline({ correlationId, steps, isRunning }: Props) {
  return (
    <section className="rounded-2xl border border-zinc-800 bg-zinc-900/40 p-6">
      <div className="mb-5 flex items-center gap-2 text-sm text-zinc-400">
        <span>Investigating</span>
        <span className="rounded-md bg-zinc-950 px-2 py-0.5 font-mono text-xs text-zinc-300">{correlationId}</span>
      </div>

      <ol className="flex flex-col">
        {steps.map((step, index) => (
          <TimelineRow key={index} step={step} isLast={index === steps.length - 1 && !isRunning} />
        ))}

        {isRunning && (
          <li className="flex items-center gap-3 py-2 text-sm text-zinc-500">
            <Loader2 className="h-4 w-4 animate-spin text-sky-500" />
            <span>Agent is reasoning...</span>
          </li>
        )}
      </ol>
    </section>
  );
}

function TimelineRow({ step, isLast }: { step: LiveStep; isLast: boolean }) {
  return (
    <li className="animate-step-in relative flex gap-3 pb-5 last:pb-0">
      {!isLast && <span className="absolute left-[13px] top-6 h-full w-px bg-zinc-800" />}
      <StepIcon step={step} />
      <StepBody step={step} />
    </li>
  );
}

function StepIcon({ step }: { step: LiveStep }) {
  const base = "z-10 flex h-[26px] w-[26px] shrink-0 items-center justify-center rounded-full border";

  if (step.kind === "started") {
    return (
      <div className={`${base} border-zinc-700 bg-zinc-900`}>
        <CircleDot className="h-3.5 w-3.5 text-zinc-500" />
      </div>
    );
  }
  if (step.kind === "agent_decision") {
    return (
      <div className={`${base} border-sky-800 bg-sky-950/60`}>
        <Cpu className="h-3.5 w-3.5 text-sky-400" />
      </div>
    );
  }
  const success = step.data.success;
  return (
    <div className={`${base} ${success ? "border-emerald-800 bg-emerald-950/50" : "border-rose-800 bg-rose-950/50"}`}>
      {success ? (
        <Database className="h-3.5 w-3.5 text-emerald-400" />
      ) : (
        <XCircle className="h-3.5 w-3.5 text-rose-400" />
      )}
    </div>
  );
}

function StepBody({ step }: { step: LiveStep }) {
  if (step.kind === "started") {
    return (
      <div className="pt-0.5">
        <p className="text-sm text-zinc-300">Investigation started</p>
      </div>
    );
  }

  if (step.kind === "agent_decision") {
    return (
      <div className="pt-0.5">
        <p className="text-sm text-zinc-200">
          Calling <span className="font-mono text-sky-400">{step.data.tool}</span>
        </p>
        <p className="mt-0.5 text-[11px] uppercase tracking-wide text-zinc-600">MCP tool call</p>
      </div>
    );
  }

  // evidence
  const { success, summary, durationMs, source } = step.data;
  return (
    <div className="pt-0.5">
      <p className="text-sm text-zinc-200">{success ? "Evidence received" : "Tool call failed"}</p>
      <p className={`mt-0.5 text-sm ${success ? "text-zinc-400" : "text-rose-400"}`}>{summary}</p>
      <p className="mt-1 flex items-center gap-2 text-[11px] uppercase tracking-wide text-zinc-600">
        <span>{source}</span>
        <span>&middot;</span>
        <span>{Math.round(durationMs)}ms</span>
      </p>
    </div>
  );
}

export function CompletionMarker() {
  return (
    <div className="flex items-center gap-2 pt-1 text-sm text-emerald-400">
      <CheckCircle2 className="h-4 w-4" />
      <span>Investigation complete</span>
    </div>
  );
}
