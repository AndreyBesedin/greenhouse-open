import { vi } from "vitest";

/**
 * The browser's `fetch`, stood in for: it answers nothing, a request given
 * up fails as the browser's does, and every address asked for is kept, in
 * order, so that a test reads what a hook asked the API for.
 */
export function recordingFetch(): string[] {
  const asked: string[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(
      (input: RequestInfo | URL, init?: RequestInit) =>
        new Promise<Response>((_resolve, reject) => {
          asked.push(String(input));
          const signal = init?.signal;
          signal?.addEventListener("abort", () => reject(signal.reason));
        }),
    ),
  );
  return asked;
}
