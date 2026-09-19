import { useCallback, useRef, useState } from "react";
import { streamInvestigation } from "../lib/api";
import type { FinalResult, LiveStep } from "../types";

export type InvestigationStatus = "idle" | "running" | "done" | "error";

interface InvestigationState {
  status: InvestigationStatus;
  correlationId: string | null;
  steps: LiveStep[];
  result: FinalResult | null;
  errorMessage: string | null;
  errorReason: string | undefined;
}

const initialState: InvestigationState = {
  status: "idle",
  correlationId: null,
  steps: [],
  result: null,
  errorMessage: null,
  errorReason: undefined,
};

export function useInvestigation(onCompleted?: () => void) {
  const [state, setState] = useState<InvestigationState>(initialState);
  const closeRef = useRef<(() => void) | null>(null);

  const start = useCallback(
    (correlationId: string) => {
      closeRef.current?.();
      setState({ status: "running", correlationId, steps: [], result: null, errorMessage: null, errorReason: undefined });

      closeRef.current = streamInvestigation(correlationId, {
        onStep: (step) => setState((prev) => ({ ...prev, steps: [...prev.steps, step] })),
        onFinal: (result) => {
          setState((prev) => ({ ...prev, status: "done", result }));
          onCompleted?.();
        },
        onError: (message, reason) =>
          setState((prev) => ({ ...prev, status: "error", errorMessage: message, errorReason: reason })),
      });
    },
    [onCompleted],
  );

  const reset = useCallback(() => {
    closeRef.current?.();
    setState(initialState);
  }, []);

  const showPastResult = useCallback((result: FinalResult) => {
    closeRef.current?.();
    setState({
      status: "done",
      correlationId: result.correlationId,
      steps: [],
      result,
      errorMessage: null,
      errorReason: undefined,
    });
  }, []);

  return { ...state, start, reset, showPastResult };
}
