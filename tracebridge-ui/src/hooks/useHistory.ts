import { useCallback, useEffect, useState } from "react";
import { fetchHistory } from "../lib/api";
import type { HistorySummary } from "../types";

export function useHistory() {
  const [history, setHistory] = useState<HistorySummary[]>([]);

  const reload = useCallback(() => {
    fetchHistory()
      .then(setHistory)
      .catch(() => {
        /* history is a convenience panel, not critical - fail quietly */
      });
  }, []);

  useEffect(() => {
    reload();
  }, [reload]);

  return { history, reload };
}
