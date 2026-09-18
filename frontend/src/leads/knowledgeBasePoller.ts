import { useEffect, useState } from "react";
import type { ClientKbStage, ClientKbStatus } from "../api/leads";

export const ACTIVE_STAGES = new Set<ClientKbStage>([
  "QUEUED",
  "CRAWLING",
  "EXTRACTING",
  "EMBEDDING",
]);

export const STAGE_ORDER: ClientKbStage[] = [
  "QUEUED",
  "CRAWLING",
  "EXTRACTING",
  "EMBEDDING",
  "READY",
];

export function normalizeStage(rawStage?: string | null): ClientKbStage {
  if (!rawStage) return "NOT_STARTED";
  const s = rawStage.toUpperCase().trim();
  if (s === "QUEUED" || s === "PENDING") return "QUEUED";
  if (s === "CRAWLING" || s === "RUNNING" || s === "REFRESHING") return "CRAWLING";
  if (s === "EXTRACTING" || s === "PROCESSING") return "EXTRACTING";
  if (s === "EMBEDDING" || s === "PROCESSING / EMBEDDING") return "EMBEDDING";
  if (s === "READY" || s === "COMPLETED") return "READY";
  if (s === "PARTIAL") return "PARTIAL";
  if (s === "FAILED") return "FAILED";
  return "NOT_STARTED";
}

export function isTransientError(error: unknown): boolean {
  if (error && typeof error === "object" && "status" in error) {
    const status = (error as { status: unknown }).status;
    if (typeof status === "number") {
      return status === 408 || status === 429 || status >= 500;
    }
  }
  return true;
}

export function sanitizeErrorMessage(msg: string): string {
  if (!msg) return msg;
  const lower = msg.toLowerCase();
  if (
    lower.includes("failed to fetch") ||
    lower.includes("networkerror") ||
    lower.includes("load failed") ||
    lower.includes("connection reset")
  ) {
    return "Connection interrupted — retrying...";
  }
  return msg;
}

export type PollerState = {
  status: ClientKbStatus | null;
  loading: boolean;
  error: string;
  pollingWarning: string;
  isPolling: boolean;
};

export type PollerConfig = {
  leadId: string;
  fetchStatus: (leadId: string) => Promise<ClientKbStatus>;
  onStateChange: (state: PollerState) => void;
  pollIntervalMs?: number;
};

export function startKnowledgeBasePolling(config: PollerConfig): { stop: () => void } {
  let cancelled = false;
  let timer: ReturnType<typeof setTimeout> | undefined;
  const interval = config.pollIntervalMs ?? 2500;

  let state: PollerState = {
    status: null,
    loading: true,
    error: "",
    pollingWarning: "",
    isPolling: true,
  };

  const updateState = (partial: Partial<PollerState>) => {
    if (cancelled) return;
    state = { ...state, ...partial };
    config.onStateChange(state);
  };

  const poll = async () => {
    try {
      const next = await config.fetchStatus(config.leadId);
      if (cancelled) return;
      const normalizedStage = normalizeStage(next.processing_stage);
      const updatedStatus: ClientKbStatus = { ...next, processing_stage: normalizedStage };
      const shouldContinue = ACTIVE_STAGES.has(normalizedStage);

      updateState({
        status: updatedStatus,
        loading: false,
        error:
          normalizedStage === "FAILED"
            ? next.error_message || "Website knowledge processing failed. Please try again."
            : "",
        pollingWarning: "",
        isPolling: shouldContinue,
      });

      if (shouldContinue && !cancelled) {
        timer = setTimeout(poll, interval);
      }
    } catch (caught: unknown) {
      if (cancelled) return;
      if (isTransientError(caught)) {
        // Transient transport/polling error: preserve last known status and retry
        updateState({
          loading: false,
          pollingWarning: "Connection interrupted — retrying...",
          isPolling: true,
        });
        if (!cancelled) {
          timer = setTimeout(poll, interval);
        }
      } else {
        // Non-transient API failure (e.g. 401, 403, 404): stop polling, surface sanitized error
        updateState({
          loading: false,
          error:
            caught instanceof Error
              ? sanitizeErrorMessage(caught.message)
              : "Could not load Client KB status.",
          pollingWarning: "",
          isPolling: false,
        });
      }
    }
  };

  void poll();

  return {
    stop: () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
      state = { ...state, isPolling: false };
      config.onStateChange(state);
    },
  };
}

export function useKnowledgeBasePolling(
  leadId: string,
  fetchFn: (id: string) => Promise<ClientKbStatus>,
  enabled: boolean,
  pollVersion: number = 0,
) {
  const [state, setState] = useState<PollerState>({
    status: null,
    loading: true,
    error: "",
    pollingWarning: "",
    isPolling: false,
  });

  useEffect(() => {
    if (!enabled || !leadId) return;
    const poller = startKnowledgeBasePolling({
      leadId,
      fetchStatus: fetchFn,
      onStateChange: setState,
    });
    return () => poller.stop();
  }, [leadId, enabled, pollVersion]);

  const setStatus = (next: ClientKbStatus) => {
    const normalizedStage = normalizeStage(next.processing_stage);
    setState((prev) => ({
      ...prev,
      status: { ...next, processing_stage: normalizedStage },
      error:
        normalizedStage === "FAILED"
          ? next.error_message || "Website knowledge processing failed. Please try again."
          : "",
    }));
  };

  const setError = (error: string) => {
    setState((prev) => ({ ...prev, error: sanitizeErrorMessage(error) }));
  };

  return {
    ...state,
    setStatus,
    setError,
  };
}
