import { useCallback } from "react";
import { CompletionMarker, LiveTimeline } from "./components/LiveTimeline";
import { EvidenceList } from "./components/EvidenceList";
import { ErrorState } from "./components/ErrorState";
import { Header } from "./components/Header";
import { HistorySidebar } from "./components/HistorySidebar";
import { ResultPanel } from "./components/ResultPanel";
import { SearchHero } from "./components/SearchHero";
import { TransactionFlow } from "./components/TransactionFlow";
import { fetchInvestigationDetail } from "./lib/api";
import { useHistory } from "./hooks/useHistory";
import { useInvestigation } from "./hooks/useInvestigation";
import { useStatus } from "./hooks/useStatus";

export default function App() {
  const status = useStatus();
  const { history, reload } = useHistory();
  const { status: investigationStatus, correlationId, steps, result, errorMessage, errorReason, start, showPastResult } =
    useInvestigation(reload);

  const handleSelectHistory = useCallback(
    (investigationId: string) => {
      fetchInvestigationDetail(investigationId).then(showPastResult).catch(() => {});
    },
    [showPastResult],
  );

  const isRunning = investigationStatus === "running";

  return (
    <div className="min-h-screen bg-[#0a0b0d]">
      <Header status={status} />

      <main className="mx-auto grid max-w-6xl grid-cols-1 gap-8 px-6 py-10 lg:grid-cols-[1fr_300px]">
        <div className="flex flex-col gap-6">
          <SearchHero onInvestigate={start} disabled={isRunning} />

          {investigationStatus === "error" && <ErrorState message={errorMessage ?? "Unknown error"} reason={errorReason} />}

          {(isRunning || steps.length > 0) && investigationStatus !== "error" && (
            <LiveTimeline correlationId={correlationId ?? ""} steps={steps} isRunning={isRunning} />
          )}

          {result && (
            <>
              {steps.length > 0 && <CompletionMarker />}
              <TransactionFlow observedPath={result.observedPath} failureBoundary={result.failureBoundary} />
              <ResultPanel result={result} />
              <EvidenceList items={result.evidence} />
            </>
          )}
        </div>

        <HistorySidebar history={history} activeInvestigationId={result?.investigationId} onSelect={handleSelectHistory} />
      </main>
    </div>
  );
}
