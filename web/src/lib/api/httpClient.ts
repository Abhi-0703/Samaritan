import {
  ApiError,
  type Agent,
  type AgentDetail,
  type AudioUrl,
  type Call,
  type CallDetail,
  type EvalRun,
  type ListCallsParams,
  type OverviewStats,
  type Paginated,
  type ReviewerStatus,
  type Rule,
  type UploadMetadata,
  type Violation,
} from "../types";
import type { ApiClient, UploadOptions } from "./client";

const baseUrl = (process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000").replace(/\/+$/, "");
/** Whether the API runs with DEMO_MODE=true. Set at build time; the passcode itself is never in the bundle. */
const demoMode = process.env.NEXT_PUBLIC_DEMO_MODE === "true";

const NETWORK_MESSAGE = "Could not reach the server. Check your connection and try again.";

function errorFrom(status: number, body: unknown): ApiError {
  const err = (body as { error?: { code?: unknown; message?: unknown } } | null)?.error;
  if (err && typeof err.code === "string" && typeof err.message === "string") return new ApiError(err.code, err.message);
  return new ApiError(status >= 500 ? "internal_error" : "http_error", `The server returned an unexpected response (${status}).`);
}

function parseJson(text: string): unknown {
  try {
    return text ? JSON.parse(text) : null;
  } catch {
    return null;
  }
}

async function request<T>(
  path: string,
  init: { method?: string; body?: unknown; passcode?: string; query?: Record<string, string | number | boolean | undefined> } = {},
): Promise<T> {
  const url = new URL(baseUrl + path);
  for (const [k, v] of Object.entries(init.query ?? {})) {
    if (v !== undefined && v !== "") url.searchParams.set(k, String(v));
  }
  const headers: Record<string, string> = {};
  if (init.body !== undefined) headers["Content-Type"] = "application/json";
  if (init.passcode) headers["X-Upload-Passcode"] = init.passcode;
  let res: Response;
  try {
    res = await fetch(url, {
      method: init.method ?? "GET",
      headers,
      body: init.body === undefined ? undefined : JSON.stringify(init.body),
      cache: "no-store",
    });
  } catch {
    throw new ApiError("network_error", NETWORK_MESSAGE);
  }
  const body = parseJson(await res.text());
  if (!res.ok) throw errorFrom(res.status, body);
  return body as T;
}

/** Multipart upload with progress. fetch cannot report upload progress, so this uses XMLHttpRequest. */
function upload(files: File[], metadata: UploadMetadata[], options: UploadOptions): Promise<Call[]> {
  return new Promise((resolve, reject) => {
    const form = new FormData();
    form.append("metadata", JSON.stringify(metadata));
    for (const file of files) form.append("files", file, file.name);

    // The body is sent in order, so bytes sent map onto files by their cumulative sizes.
    const sizes = files.map((f) => f.size);
    const total = sizes.reduce((a, b) => a + b, 0) || 1;
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${baseUrl}/calls/upload`);
    if (options.passcode) xhr.setRequestHeader("X-Upload-Passcode", options.passcode);
    xhr.upload.onprogress = (e) => {
      if (!e.lengthComputable) return;
      const sent = (e.loaded / e.total) * total;
      let start = 0;
      sizes.forEach((size, index) => {
        options.onProgress?.(index, Math.max(0, Math.min(1, size ? (sent - start) / size : 1)));
        start += size;
      });
    };
    xhr.onerror = () => reject(new ApiError("network_error", NETWORK_MESSAGE));
    xhr.onabort = () => reject(new ApiError("network_error", "The upload was cancelled."));
    xhr.onload = () => {
      const body = parseJson(xhr.responseText);
      if (xhr.status >= 200 && xhr.status < 300) {
        files.forEach((_, index) => options.onProgress?.(index, 1));
        resolve(body as Call[]);
      } else {
        reject(errorFrom(xhr.status, body));
      }
    };
    xhr.send(form);
  });
}

export const httpClient: ApiClient = {
  isMock: false,
  demoMode,

  health: async () => {
    await request<{ status: string }>("/health");
  },

  getOverview: () => request<OverviewStats>("/stats/overview"),

  listCalls: (params: ListCallsParams = {}) => request<Paginated<Call>>("/calls", { query: { ...params } }),

  getCall: (id: string) => request<CallDetail>(`/calls/${encodeURIComponent(id)}`),

  getAudioUrl: (id: string) => request<AudioUrl>(`/calls/${encodeURIComponent(id)}/audio`),

  uploadCalls: (files: File[], metadata: UploadMetadata[], options: UploadOptions = {}) => {
    if (files.length !== metadata.length) {
      return Promise.reject(new ApiError("invalid_request", "Each file needs its own details."));
    }
    return upload(files, metadata, options);
  },

  retryCall: (id: string, options = {}) =>
    request<Call>(`/calls/${encodeURIComponent(id)}/retry`, {
      method: "POST",
      passcode: options.passcode,
      query: { retranscribe: options.retranscribe ? true : undefined },
    }),

  swapRoles: (id: string, options = {}) =>
    request<CallDetail>(`/calls/${encodeURIComponent(id)}/swap-roles`, { method: "POST", passcode: options.passcode }),

  updateViolation: (id: string, reviewer_status: ReviewerStatus) =>
    request<{ violation: Violation; call_score: number }>(`/violations/${encodeURIComponent(id)}`, {
      method: "PATCH",
      body: { reviewer_status },
    }),

  listAgents: () => request<Agent[]>("/agents"),

  createAgent: (input: { name: string; team: string }) => request<Agent>("/agents", { method: "POST", body: input }),

  getAgent: (id: string) => request<AgentDetail>(`/agents/${encodeURIComponent(id)}`),

  listRules: () => request<Rule[]>("/rules"),

  updateRule: (code: string, enabled: boolean) =>
    request<Rule>(`/rules/${encodeURIComponent(code)}`, { method: "PATCH", body: { enabled } }),

  getLatestEval: () => request<{ rules_only: EvalRun | null; rules_plus_llm: EvalRun | null }>("/eval/latest"),
};
