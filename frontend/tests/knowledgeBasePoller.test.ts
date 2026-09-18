import test, { describe, it } from "node:test";
import assert from "node:assert/strict";
import {
  startKnowledgeBasePolling,
  normalizeStage,
  isTransientError,
  sanitizeErrorMessage,
  ACTIVE_STAGES,
  type PollerState,
} from "../src/leads/knowledgeBasePoller.ts";
import type { ClientKbStatus } from "../src/api/leads.ts";

class MockApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

function mockStatus(stage: string, overrides: Partial<ClientKbStatus> = {}): ClientKbStatus {
  return {
    has_website: true,
    website_url: "https://example.com",
    website_id: "site-123",
    knowledge_base_id: "kb-123",
    status: stage,
    knowledge_base_status: stage,
    processing_stage: stage as any,
    pages_discovered: 10,
    pages_processed: 8,
    pages_succeeded: 8,
    pages_failed: 0,
    page_count: 8,
    chunk_count: 24,
    chunks_created: 24,
    embeddings_created: null,
    started_at: "2026-09-18T10:00:00Z",
    updated_at: "2026-09-18T10:01:00Z",
    completed_at: null,
    last_indexed_at: null,
    error_message: null,
    ...overrides,
  };
}

describe("Client Knowledge Poller Tests", () => {
  it("1. Normal processing pipeline: QUEUED -> CRAWLING -> EXTRACTING -> EMBEDDING -> READY", async () => {
    const stages = ["QUEUED", "CRAWLING", "EXTRACTING", "EMBEDDING", "READY"];
    let callCount = 0;
    const recordedStates: PollerState[] = [];

    const poller = startKnowledgeBasePolling({
      leadId: "lead-1",
      pollIntervalMs: 10,
      fetchStatus: async () => {
        const stage = stages[Math.min(callCount, stages.length - 1)];
        callCount++;
        return mockStatus(stage);
      },
      onStateChange: (state) => {
        recordedStates.push({ ...state });
      },
    });

    // Allow polling through all stages
    while (callCount < stages.length) {
      await new Promise((resolve) => setTimeout(resolve, 15));
    }
    await new Promise((resolve) => setTimeout(resolve, 30));

    poller.stop();

    const lastState = recordedStates[recordedStates.length - 1];
    assert.equal(lastState.status?.processing_stage, "READY");
    assert.equal(lastState.isPolling, false);
    assert.equal(lastState.pollingWarning, "");
    assert.equal(lastState.error, "");
  });

  it("2. Temporary polling failure: preserves CRAWLING, displays retry warning, and recovers", async () => {
    let poll = 0;
    const recordedStates: PollerState[] = [];

    let poll1Resolve!: () => void;
    const poll1Promise = new Promise<void>((r) => { poll1Resolve = r; });
    let poll2Resolve!: () => void;
    const poll2Promise = new Promise<void>((r) => { poll2Resolve = r; });
    let poll3Resolve!: () => void;
    const poll3Promise = new Promise<void>((r) => { poll3Resolve = r; });

    const poller = startKnowledgeBasePolling({
      leadId: "lead-2",
      pollIntervalMs: 10,
      fetchStatus: async () => {
        poll++;
        if (poll === 1) {
          return mockStatus("CRAWLING", { pages_processed: 3 });
        }
        if (poll === 2) {
          throw new TypeError("Failed to fetch");
        }
        return mockStatus("CRAWLING", { pages_processed: 6 });
      },
      onStateChange: (state) => {
        recordedStates.push({ ...state });
        if (state.status?.pages_processed === 3 && !state.pollingWarning) {
          poll1Resolve();
        } else if (state.pollingWarning === "Connection interrupted — retrying...") {
          poll2Resolve();
        } else if (state.status?.pages_processed === 6 && !state.pollingWarning) {
          poll3Resolve();
        }
      },
    });

    await poll1Promise;
    await poll2Promise;

    const failureState = recordedStates.find((s) => s.pollingWarning === "Connection interrupted — retrying...");
    assert.ok(failureState);
    assert.equal(failureState?.status?.processing_stage, "CRAWLING", "Must preserve last known stage");
    assert.equal(failureState?.status?.pages_processed, 3, "Must preserve last known progress");
    assert.equal(failureState?.error, "", "Must NOT mark job as failed");
    assert.equal(failureState?.isPolling, true, "Must continue polling");

    await poll3Promise;
    poller.stop();

    const recoveredState = recordedStates[recordedStates.length - 1];
    assert.equal(recoveredState.status?.pages_processed, 6);
    assert.equal(recoveredState.pollingWarning, "", "Warning must disappear after recovery");
    assert.equal(recoveredState.error, "");
  });

  it("3. Multiple temporary polling failures do not mark job FAILED", async () => {
    let callCount = 0;
    const recordedStates: PollerState[] = [];

    const poller = startKnowledgeBasePolling({
      leadId: "lead-3",
      pollIntervalMs: 10,
      fetchStatus: async () => {
        callCount++;
        if (callCount === 1) {
          return mockStatus("CRAWLING", { pages_discovered: 15 });
        }
        // Fail 3 times in a row
        throw new TypeError("Failed to fetch");
      },
      onStateChange: (state) => {
        recordedStates.push({ ...state });
      },
    });

    // Wait until at least 4 polls happen
    while (callCount < 4) await new Promise((r) => setTimeout(r, 12));
    poller.stop();

    const currentState = recordedStates[recordedStates.length - 1];
    assert.equal(currentState.status?.processing_stage, "CRAWLING");
    assert.equal(currentState.status?.pages_discovered, 15);
    assert.equal(currentState.pollingWarning, "Connection interrupted — retrying...");
    assert.equal(currentState.error, "", "Must NOT mark error on repeated network drops");
    assert.equal(currentState.isPolling, false, "Stopped cleanly after poller.stop()");
  });

  it("4. Actual backend FAILED status displays processing failure and stops polling", async () => {
    let callCount = 0;
    const recordedStates: PollerState[] = [];

    const poller = startKnowledgeBasePolling({
      leadId: "lead-4",
      pollIntervalMs: 10,
      fetchStatus: async () => {
        callCount++;
        if (callCount === 1) {
          return mockStatus("CRAWLING");
        }
        return mockStatus("FAILED", {
          error_message: "Website content could not be processed. Please try again.",
        });
      },
      onStateChange: (state) => {
        recordedStates.push({ ...state });
      },
    });

    while (callCount < 2) await new Promise((r) => setTimeout(r, 12));
    await new Promise((r) => setTimeout(r, 25));
    poller.stop();

    const failedState = recordedStates[recordedStates.length - 1];
    assert.equal(failedState.status?.processing_stage, "FAILED");
    assert.equal(failedState.error, "Website content could not be processed. Please try again.");
    assert.equal(failedState.pollingWarning, "");
    assert.equal(failedState.isPolling, false, "Must stop polling on FAILED");
    // Ensure no additional calls happened after FAILED
    assert.equal(callCount, 2);
  });

  it("5. READY stops polling immediately", async () => {
    let callCount = 0;

    const poller = startKnowledgeBasePolling({
      leadId: "lead-5",
      pollIntervalMs: 10,
      fetchStatus: async () => {
        callCount++;
        return mockStatus("READY");
      },
      onStateChange: () => {},
    });

    await new Promise((r) => setTimeout(r, 40));
    poller.stop();

    assert.equal(callCount, 1, "Poller must not schedule another poll after READY");
  });

  it("6. No raw 'Failed to fetch' browser exception is shown to users", () => {
    assert.equal(
      sanitizeErrorMessage("TypeError: Failed to fetch"),
      "Connection interrupted — retrying..."
    );
    assert.equal(
      sanitizeErrorMessage("failed to fetch"),
      "Connection interrupted — retrying..."
    );
    assert.equal(
      sanitizeErrorMessage("NetworkError when attempting to fetch resource."),
      "Connection interrupted — retrying..."
    );
    // Preserves legitimate application errors
    assert.equal(
      sanitizeErrorMessage("Website content could not be processed."),
      "Website content could not be processed."
    );
  });

  it("7. Permanent HTTP 404/401 stops polling and reports error", async () => {
    let callCount = 0;
    const recordedStates: PollerState[] = [];

    const poller = startKnowledgeBasePolling({
      leadId: "lead-6",
      pollIntervalMs: 10,
      fetchStatus: async () => {
        callCount++;
        throw new MockApiError("Lead not found", 404);
      },
      onStateChange: (state) => {
        recordedStates.push({ ...state });
      },
    });

    await new Promise((r) => setTimeout(r, 30));
    poller.stop();

    assert.equal(callCount, 1, "Must not retry 404 errors");
    const state = recordedStates[recordedStates.length - 1];
    assert.equal(state.error, "Lead not found");
    assert.equal(state.isPolling, false);
    assert.equal(state.pollingWarning, "");
  });

  it("8. Stage normalization handles uppercase, lowercase, and synonyms", () => {
    assert.equal(normalizeStage("queued"), "QUEUED");
    assert.equal(normalizeStage("pending"), "QUEUED");
    assert.equal(normalizeStage("crawling"), "CRAWLING");
    assert.equal(normalizeStage("running"), "CRAWLING");
    assert.equal(normalizeStage("refreshing"), "CRAWLING");
    assert.equal(normalizeStage("extracting"), "EXTRACTING");
    assert.equal(normalizeStage("processing"), "EXTRACTING");
    assert.equal(normalizeStage("embedding"), "EMBEDDING");
    assert.equal(normalizeStage("PROCESSING / EMBEDDING"), "EMBEDDING");
    assert.equal(normalizeStage("ready"), "READY");
    assert.equal(normalizeStage("completed"), "READY");
    assert.equal(normalizeStage("partial"), "PARTIAL");
    assert.equal(normalizeStage("failed"), "FAILED");
    assert.equal(normalizeStage(null), "NOT_STARTED");
  });

  it("9. isTransientError correctly categorizes transport vs permanent errors", () => {
    assert.equal(isTransientError(new TypeError("Failed to fetch")), true);
    assert.equal(isTransientError(new Error("Network timeout")), true);
    assert.equal(isTransientError(new MockApiError("Gateway Timeout", 504)), true);
    assert.equal(isTransientError(new MockApiError("Bad Gateway", 502)), true);
    assert.equal(isTransientError(new MockApiError("Service Unavailable", 503)), true);
    assert.equal(isTransientError(new MockApiError("Rate Limited", 429)), true);
    // Non-transient:
    assert.equal(isTransientError(new MockApiError("Not Found", 404)), false);
    assert.equal(isTransientError(new MockApiError("Unauthorized", 401)), false);
    assert.equal(isTransientError(new MockApiError("Forbidden", 403)), false);
  });
});
