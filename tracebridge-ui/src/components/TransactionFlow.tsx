import { ArrowRight, Check, Circle, X } from "lucide-react";
import type { ObservedStage, StageStatus } from "../types";

// The backend reports 13 granular checkpoints; the flow diagram shows the
// 5 architectural hops from the system topology. Each hop is anchored to
// the specific checkpoint that proves a transaction reached it.
const MILESTONES: { label: string; matchLabel: string }[] = [
  { label: "service-request-api", matchLabel: "request received" },
  { label: "PostgreSQL", matchLabel: "database persisted" },
  { label: "Kafka", matchLabel: "Kafka published" },
  { label: "servicenow-consumer", matchLabel: "Kafka consumed" },
  { label: "ServiceNow", matchLabel: "downstream request" },
  // Phase 8: customer-db-consumer is a second, independent Kafka consumer of
  // the same event - its labels are deliberately distinct from
  // servicenow-consumer's above (see topology.py) so this lookup can never
  // collide with the boxes rendered from the milestones above.
  { label: "customer-db-consumer", matchLabel: "customer-db-consumer Kafka consumed" },
  { label: "customer-postgres", matchLabel: "customer-db-consumer database operation" },
];

function computeMilestones(path: ObservedStage[]): { label: string; status: StageStatus }[] {
  const byLabel = new Map(path.map((stage) => [stage.label, stage.status]));
  return MILESTONES.map((milestone) => ({
    label: milestone.label,
    status: byLabel.get(milestone.matchLabel) ?? "pending",
  }));
}

function MilestoneIcon({ status }: { status: StageStatus }) {
  if (status === "ok") {
    return (
      <div className="flex h-8 w-8 items-center justify-center rounded-full border border-emerald-700 bg-emerald-950/60">
        <Check className="h-4 w-4 text-emerald-400" strokeWidth={2.5} />
      </div>
    );
  }
  if (status === "failed") {
    return (
      <div className="flex h-8 w-8 items-center justify-center rounded-full border border-rose-700 bg-rose-950/60">
        <X className="h-4 w-4 text-rose-400" strokeWidth={2.5} />
      </div>
    );
  }
  return (
    <div className="flex h-8 w-8 items-center justify-center rounded-full border border-zinc-700 bg-zinc-900">
      <Circle className="h-3 w-3 text-zinc-600" />
    </div>
  );
}

export function TransactionFlow({
  observedPath,
  failureBoundary,
}: {
  observedPath: ObservedStage[];
  failureBoundary: string | null;
}) {
  const milestones = computeMilestones(observedPath);

  return (
    <section className="rounded-2xl border border-zinc-800 bg-zinc-900/40 p-6">
      <h3 className="text-sm font-medium text-zinc-300">Transaction flow</h3>

      <div className="mt-6 flex flex-col items-stretch gap-0 sm:flex-row sm:items-center sm:gap-0">
        {milestones.map((milestone, index) => (
          <div key={milestone.label} className="flex flex-1 items-center">
            <div className="flex flex-1 flex-col items-center gap-2 py-2">
              <MilestoneIcon status={milestone.status} />
              <span
                className={`text-center text-xs font-mono ${
                  milestone.status === "pending" ? "text-zinc-600" : "text-zinc-300"
                }`}
              >
                {milestone.label}
              </span>
            </div>
            {index < milestones.length - 1 && (
              <ArrowRight className="mx-1 hidden h-4 w-4 shrink-0 text-zinc-700 sm:block" />
            )}
          </div>
        ))}
      </div>

      {failureBoundary && (
        <div className="mt-6 flex items-center gap-2 rounded-lg border border-rose-900/60 bg-rose-950/30 px-4 py-3">
          <span className="text-xs uppercase tracking-wide text-rose-500">Failure boundary</span>
          <span className="font-mono text-sm text-rose-300">{failureBoundary}</span>
        </div>
      )}
    </section>
  );
}
