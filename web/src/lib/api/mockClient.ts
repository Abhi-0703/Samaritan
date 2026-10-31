import { getDb } from "../mock/store";
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

const MOCK_PASSCODE = "demo123";
const ALLOWED_EXTENSIONS = ["wav", "mp3", "m4a", "ogg", "flac"];
const MAX_UPLOAD_BYTES = 25 * 1024 * 1024;

const demoMode = process.env.NEXT_PUBLIC_MOCK_DEMO_MODE !== "false";

/** Artificial latency so loading states are visible, as they will be against the real API. */
function latency<T>(value: () => T, min = 220, max = 520): Promise<T> {
  const ms = min + Math.random() * (max - min);
  return new Promise((resolve, reject) => {
    setTimeout(() => {
      try {
        resolve(value());
      } catch (e) {
        reject(e);
      }
    }, ms);
  });
}

function requirePasscode(passcode: string | undefined) {
  if (demoMode && passcode !== MOCK_PASSCODE) {
    throw new ApiError("forbidden", "The passcode is missing or incorrect.");
  }
}

export const mockClient: ApiClient = {
  isMock: true,
  demoMode,

  getOverview: (): Promise<OverviewStats> => latency(() => getDb().overview()),

  listCalls: (params: ListCallsParams = {}): Promise<Paginated<Call>> => latency(() => getDb().list(params), 150, 380),

  getCall: (id: string): Promise<CallDetail> => latency(() => getDb().toDetail(getDb().find(id))),

  getAudioUrl: (id: string): Promise<AudioUrl> =>
    latency(() => ({ url: getDb().find(id).audio_url, expires_at: new Date(Date.now() + 3_600_000).toISOString() }), 80, 200),

  async uploadCalls(files: File[], metadata: UploadMetadata[], options: UploadOptions = {}): Promise<Call[]> {
    requirePasscode(options.passcode);
    if (files.length !== metadata.length) throw new ApiError("invalid_request", "Each file needs its own details.");
    for (const file of files) {
      const ext = file.name.split(".").pop()?.toLowerCase() ?? "";
      if (!ALLOWED_EXTENSIONS.includes(ext)) {
        throw new ApiError("unsupported_media", `${file.name} is not a supported audio file. Use wav, mp3, m4a, ogg or flac.`);
      }
      if (file.size > MAX_UPLOAD_BYTES) {
        throw new ApiError("file_too_large", `${file.name} is larger than 25 MB.`);
      }
    }
    // Simulated transfer so per-file progress can be shown.
    await Promise.all(
      files.map(
        (_, index) =>
          new Promise<void>((resolve) => {
            let step = 0;
            const timer = setInterval(() => {
              step += 1;
              options.onProgress?.(index, Math.min(1, step / 5));
              if (step >= 5) {
                clearInterval(timer);
                resolve();
              }
            }, 140 + index * 40);
          }),
      ),
    );
    return getDb().upload(metadata);
  },

  retryCall: (id: string, options = {}): Promise<Call> =>
    latency(() => {
      requirePasscode(options.passcode);
      return getDb().retry(id);
    }),

  swapRoles: (id: string, options = {}): Promise<CallDetail> =>
    latency(() => {
      requirePasscode(options.passcode);
      return getDb().swapRoles(id);
    }),

  updateViolation: (id: string, reviewer_status: ReviewerStatus): Promise<{ violation: Violation; call_score: number }> =>
    latency(() => getDb().review(id, reviewer_status), 120, 280),

  listAgents: (): Promise<Agent[]> =>
    latency(() => getDb().agents.map((a) => getDb().agentStats(a.id)!)),

  createAgent: (input: { name: string; team: string }): Promise<Agent> =>
    latency(() => {
      const rec = getDb().addAgent(input.name, input.team);
      return getDb().agentStats(rec.id)!;
    }, 120, 280),

  getAgent: (id: string): Promise<AgentDetail> => latency(() => getDb().agentDetail(id)),

  listRules: (): Promise<Rule[]> => latency(() => getDb().rules.map((r) => ({ ...r })), 120, 300),

  updateRule: (code: string, enabled: boolean): Promise<Rule> => latency(() => getDb().setRule(code, enabled), 120, 280),

  getLatestEval: (): Promise<{ rules_only: EvalRun | null; rules_plus_llm: EvalRun | null }> =>
    latency(() => ({ ...getDb().evals })),
};

export const MOCK_PASSCODE_HINT = MOCK_PASSCODE;
