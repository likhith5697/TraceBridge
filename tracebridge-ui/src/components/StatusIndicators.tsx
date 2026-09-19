import type { ServiceStatus, StatusResponse } from "../types";

const LABELS: Record<keyof StatusResponse, string> = {
  investigator: "Investigator",
  mcp: "MCP",
  opensearch: "OpenSearch",
  postgresql: "PostgreSQL",
};

function Dot({ status }: { status: ServiceStatus | undefined }) {
  if (!status) {
    return <span className="h-2 w-2 rounded-full bg-zinc-700" />;
  }
  const color = status === "up" ? "bg-emerald-400" : "bg-rose-500";
  return <span className={`h-2 w-2 rounded-full ${color}`} />;
}

export function StatusIndicators({ status }: { status: StatusResponse | null }) {
  const keys = Object.keys(LABELS) as (keyof StatusResponse)[];

  return (
    <div className="flex flex-wrap items-center gap-4 text-xs text-zinc-400">
      {keys.map((key) => (
        <div key={key} className="flex items-center gap-1.5" title={`${LABELS[key]}: ${status?.[key] ?? "checking"}`}>
          <Dot status={status?.[key]} />
          <span>{LABELS[key]}</span>
        </div>
      ))}
    </div>
  );
}
