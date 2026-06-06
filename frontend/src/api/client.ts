import { API_BASE_URL } from "../config/env";
import type {
  AgentSession,
  ChatRequest,
  ChatResponse,
  EntitySummary,
  EntityType,
  FeedbackRequest,
  FeedbackResponse,
  GeneratedItinerary,
  ModifyRequest,
  ModifyResponse,
  TrendResponse,
} from "./types";

export class ApiError extends Error {
  status: number;
  detail: unknown;
  constructor(status: number, detail: unknown, message?: string) {
    super(message ?? `Request failed with status ${status}`);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE_URL}${path}`, {
      headers: { "Content-Type": "application/json", ...(options.headers ?? {}) },
      ...options,
    });
  } catch (cause) {
    throw new ApiError(0, cause, "Network error — is the backend running on :8000?");
  }

  let body: unknown = null;
  const text = await res.text();
  if (text) {
    try {
      body = JSON.parse(text);
    } catch {
      body = text;
    }
  }

  if (!res.ok) {
    const detail =
      body && typeof body === "object" && "detail" in body
        ? (body as { detail: unknown }).detail
        : body;
    const message = typeof detail === "string" ? detail : `Request failed (${res.status})`;
    throw new ApiError(res.status, detail, message);
  }

  return body as T;
}

/* ---- Agent ----------------------------------------------------------- */
export const chat = (payload: ChatRequest) =>
  request<ChatResponse>("/agent/chat", { method: "POST", body: JSON.stringify(payload) });

/** A real progress event streamed by the backend while the agent works. */
export interface ProgressEvent {
  stage: string;
  tool?: string;
  detail?: string | null;
  step?: number;
}

export interface ChatStreamHandlers {
  onStatus: (event: ProgressEvent) => void;
  onResult: (res: ChatResponse) => void;
  onError: (err: ApiError) => void;
}

/**
 * POST /agent/chat/stream and consume the SSE response. EventSource is GET-only
 * and we need to POST a body, so we read the stream manually: buffer the bytes,
 * split on the blank-line frame delimiter, and parse each frame's event/data lines.
 */
export async function chatStream(
  payload: ChatRequest,
  { onStatus, onResult, onError }: ChatStreamHandlers,
): Promise<void> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE_URL}/agent/chat/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
      body: JSON.stringify(payload),
    });
  } catch (cause) {
    onError(new ApiError(0, cause, "Network error — is the backend running on :8000?"));
    return;
  }
  if (!res.ok || !res.body) {
    onError(new ApiError(res.status, null, `Request failed (${res.status})`));
    return;
  }

  const handleFrame = (frame: string) => {
    let event = "message";
    const dataLines: string[] = [];
    for (const line of frame.split("\n")) {
      if (line.startsWith("event:")) event = line.slice(6).trim();
      else if (line.startsWith("data:")) dataLines.push(line.slice(5).trim());
    }
    if (!dataLines.length) return;
    let parsed: unknown;
    try {
      parsed = JSON.parse(dataLines.join("\n"));
    } catch {
      return; // ignore malformed frame
    }
    if (event === "status") onStatus(parsed as ProgressEvent);
    else if (event === "result") onResult(parsed as ChatResponse);
    else if (event === "error")
      onError(
        new ApiError(500, parsed, (parsed as { message?: string }).message ?? "Planning failed."),
      );
  };

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let idx: number;
    while ((idx = buffer.indexOf("\n\n")) !== -1) {
      const frame = buffer.slice(0, idx);
      buffer = buffer.slice(idx + 2);
      if (frame.trim()) handleFrame(frame);
    }
  }
}

export const getSession = (sessionId: string) =>
  request<AgentSession>(`/agent/session/${encodeURIComponent(sessionId)}`);

export const getItinerary = (itineraryId: string) =>
  request<GeneratedItinerary>(`/agent/itinerary/${encodeURIComponent(itineraryId)}`);

export const submitFeedback = (payload: FeedbackRequest) =>
  request<FeedbackResponse>("/agent/feedback", { method: "POST", body: JSON.stringify(payload) });

export const modifyEntity = (payload: ModifyRequest) =>
  request<ModifyResponse>("/agent/modify", { method: "POST", body: JSON.stringify(payload) });

/* ---- Ratings --------------------------------------------------------- */
export const getCities = () => request<string[]>("/ratings/cities");

export const getEntities = (entityType: EntityType, city: string) => {
  const qs = new URLSearchParams({ entity_type: entityType, city });
  return request<EntitySummary[]>(`/ratings/entities?${qs.toString()}`);
};

export const getTrend = (
  entityType: EntityType,
  entityId: string,
  from?: string,
  to?: string,
) => {
  const qs = new URLSearchParams();
  if (from) qs.set("from", from);
  if (to) qs.set("to", to);
  const suffix = qs.toString() ? `?${qs.toString()}` : "";
  return request<TrendResponse>(
    `/ratings/trend/${entityType}/${encodeURIComponent(entityId)}${suffix}`,
  );
};

/* ---- Misc ------------------------------------------------------------ */
export const health = () => request<{ status: string }>("/health");
