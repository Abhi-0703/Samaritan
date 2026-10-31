import type { ApiClient } from "./client";
import { mockClient } from "./mockClient";

const source = process.env.NEXT_PUBLIC_DATA_SOURCE ?? "mock";

if (source !== "mock") {
  // The HTTP client is built in Phase 4 against the FastAPI service.
  throw new Error(`NEXT_PUBLIC_DATA_SOURCE=${source} is not available yet. Set it to "mock".`);
}

/** The single entry point for data. Pages and components import this and nothing from lib/mock. */
export const api: ApiClient = mockClient;

export type { ApiClient } from "./client";
export { MOCK_PASSCODE_HINT } from "./mockClient";
