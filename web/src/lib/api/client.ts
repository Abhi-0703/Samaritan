import type {
  Agent,
  AgentDetail,
  AudioUrl,
  Call,
  CallDetail,
  EvalRun,
  ListCallsParams,
  OverviewStats,
  Paginated,
  ReviewerStatus,
  Rule,
  UploadMetadata,
  Violation,
} from "../types";

export interface UploadOptions {
  passcode?: string;
  /** Called with the file index and a 0..1 fraction while the upload is in flight. */
  onProgress?: (index: number, fraction: number) => void;
}

/**
 * The only way pages and components reach data. `mockClient` serves it in Phase 1;
 * `httpClient` implements the same interface against the FastAPI service.
 */
export interface ApiClient {
  /** True when data is generated locally rather than coming from the API. */
  readonly isMock: boolean;
  /** True when upload, retry and swap-roles need a passcode (plan Section 8.4). */
  readonly demoMode: boolean;

  /** Resolves when the API answers `/health`. Free hosts sleep, so this can take a while. */
  health(): Promise<void>;
  getOverview(): Promise<OverviewStats>;
  listCalls(params?: ListCallsParams): Promise<Paginated<Call>>;
  getCall(id: string): Promise<CallDetail>;
  getAudioUrl(id: string): Promise<AudioUrl>;
  uploadCalls(files: File[], metadata: UploadMetadata[], options?: UploadOptions): Promise<Call[]>;
  retryCall(id: string, options?: { retranscribe?: boolean; passcode?: string }): Promise<Call>;
  swapRoles(id: string, options?: { passcode?: string }): Promise<CallDetail>;
  updateViolation(id: string, reviewer_status: ReviewerStatus): Promise<{ violation: Violation; call_score: number }>;
  listAgents(): Promise<Agent[]>;
  createAgent(input: { name: string; team: string }): Promise<Agent>;
  getAgent(id: string): Promise<AgentDetail>;
  listRules(): Promise<Rule[]>;
  updateRule(code: string, enabled: boolean): Promise<Rule>;
  getLatestEval(): Promise<{ rules_only: EvalRun | null; rules_plus_llm: EvalRun | null }>;
}
