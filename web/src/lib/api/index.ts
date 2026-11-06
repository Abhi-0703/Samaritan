import type { ApiClient } from "./client";
import { httpClient } from "./httpClient";
import { mockClient } from "./mockClient";

const source = process.env.NEXT_PUBLIC_DATA_SOURCE ?? "mock";

if (source !== "mock" && source !== "api") {
  throw new Error(`NEXT_PUBLIC_DATA_SOURCE=${source} is not valid. Use "mock" or "api".`);
}

/** The single entry point for data. Pages and components import this and nothing from lib/mock. */
export const api: ApiClient = source === "api" ? httpClient : mockClient;

export type { ApiClient } from "./client";
export { MOCK_PASSCODE_HINT } from "./mockClient";
