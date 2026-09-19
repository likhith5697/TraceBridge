import { AlertOctagon } from "lucide-react";

const FRIENDLY_REASON: Record<string, string> = {
  invalid_correlation_id: "That correlation ID isn't a valid UUID.",
  llm_unavailable: "The language model is unavailable right now.",
  mcp_unavailable: "The MCP evidence server is unavailable right now.",
};

export function ErrorState({ message, reason }: { message: string; reason?: string }) {
  const heading = (reason && FRIENDLY_REASON[reason]) ?? "Investigation could not complete";

  return (
    <section className="flex items-start gap-3 rounded-2xl border border-rose-900/60 bg-rose-950/30 p-6">
      <AlertOctagon className="mt-0.5 h-5 w-5 shrink-0 text-rose-400" />
      <div>
        <p className="text-sm font-medium text-rose-300">{heading}</p>
        <p className="mt-1 text-sm text-rose-400/80">{message}</p>
      </div>
    </section>
  );
}
