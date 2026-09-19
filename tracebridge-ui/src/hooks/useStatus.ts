import { useEffect, useState } from "react";
import { fetchStatus } from "../lib/api";
import type { StatusResponse } from "../types";

const POLL_INTERVAL_MS = 30_000;
const ALL_DOWN: StatusResponse = { investigator: "down", mcp: "down", opensearch: "down", postgresql: "down" };

export function useStatus(): StatusResponse | null {
  const [status, setStatus] = useState<StatusResponse | null>(null);

  useEffect(() => {
    let cancelled = false;

    const check = () => {
      fetchStatus()
        .then((result) => {
          if (!cancelled) setStatus(result);
        })
        .catch(() => {
          if (!cancelled) setStatus(ALL_DOWN);
        });
    };

    check();
    const interval = window.setInterval(check, POLL_INTERVAL_MS);
    return () => {
      cancelled = true;
      window.clearInterval(interval);
    };
  }, []);

  return status;
}
