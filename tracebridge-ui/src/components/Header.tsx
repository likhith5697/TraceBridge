import { Radar } from "lucide-react";
import type { StatusResponse } from "../types";
import { StatusIndicators } from "./StatusIndicators";

export function Header({ status }: { status: StatusResponse | null }) {
  return (
    <header className="border-b border-zinc-800/80 bg-zinc-950/60 backdrop-blur">
      <div className="mx-auto flex max-w-6xl flex-col gap-4 px-6 py-5 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg border border-zinc-800 bg-zinc-900">
            <Radar className="h-5 w-5 text-sky-400" strokeWidth={1.75} />
          </div>
          <div>
            <h1 className="text-[15px] font-semibold leading-tight tracking-tight text-zinc-100">TraceBridge</h1>
            <p className="text-xs leading-tight text-zinc-500">AI Transaction Investigator</p>
          </div>
        </div>
        <StatusIndicators status={status} />
      </div>
    </header>
  );
}
