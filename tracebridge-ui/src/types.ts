export type StageStatus = "ok" | "failed" | "pending";

export interface ObservedStage {
  service: string;
  label: string;
  status: StageStatus;
}

export interface EvidenceItem {
  id: string;
  source: string;
  tool: string;
  success: boolean;
  summary: string;
}

export type Outcome = "SUCCESS" | "FAILURE" | "INCOMPLETE";
export type Confidence = "HIGH" | "MEDIUM" | "LOW";

export interface InvestigationStats {
  iterations: number;
  llmCalls: number;
  toolCalls: number;
  durationSeconds: number;
}

export interface FinalResult {
  investigationId: string;
  correlationId: string;
  outcome: Outcome;
  interpretation: string;
  limitations: string;
  failureBoundary: string | null;
  observedError: string | null;
  recommendedInvestigationArea: string | null;
  confidence: Confidence;
  observedPath: ObservedStage[];
  evidence: EvidenceItem[];
  stats: InvestigationStats;
  stoppedReason: string;
}

export interface StartedEventData {
  investigationId: string;
  correlationId: string;
}

export interface AgentDecisionEventData {
  tool: string;
  arguments: Record<string, unknown>;
}

export interface EvidenceEventData {
  tool: string;
  evidenceId: string;
  success: boolean;
  durationMs: number;
  summary: string;
  source: string;
  error: string | null;
}

export type LiveStep =
  | { kind: "started"; data: StartedEventData }
  | { kind: "agent_decision"; data: AgentDecisionEventData }
  | { kind: "evidence"; data: EvidenceEventData };

export interface HistorySummary {
  investigationId: string;
  correlationId: string;
  outcome: Outcome;
  confidence: Confidence;
  durationSeconds: number;
  timestamp: number;
}

export type ServiceStatus = "up" | "down";

export interface StatusResponse {
  investigator: ServiceStatus;
  mcp: ServiceStatus;
  opensearch: ServiceStatus;
  postgresql: ServiceStatus;
}
