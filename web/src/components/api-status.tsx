"use client";

import { Loader2 } from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

type Status = "ok" | "waking" | "down";

const SLOW_AFTER_MS = 2500;
const GIVE_UP_AFTER_MS = 90_000;
const RETRY_MS = 3000;

/**
 * Free hosts put the API to sleep. When `/health` is slow or failing, say so instead of showing empty pages.
 * Renders nothing on mock data or once the API has answered.
 */
export function ApiStatus() {
  const [status, setStatus] = useState<Status>("ok");

  useEffect(() => {
    if (api.isMock) return;
    let cancelled = false;
    const started = Date.now();
    const slow = setTimeout(() => !cancelled && setStatus((s) => (s === "ok" ? "waking" : s)), SLOW_AFTER_MS);
    let retry: ReturnType<typeof setTimeout> | undefined;

    const attempt = () => {
      api.health().then(
        () => {
          if (cancelled) return;
          clearTimeout(slow);
          // Pages that already failed while the server slept do not refetch on their own: start them again.
          if (Date.now() - started > SLOW_AFTER_MS) window.location.reload();
          else setStatus("ok");
        },
        () => {
          if (cancelled) return;
          setStatus(Date.now() - started > GIVE_UP_AFTER_MS ? "down" : "waking");
          retry = setTimeout(attempt, RETRY_MS);
        },
      );
    };
    attempt();
    return () => {
      cancelled = true;
      clearTimeout(slow);
      clearTimeout(retry);
    };
  }, []);

  if (status === "ok") return null;
  return (
    <div role="status" className="no-print flex items-center gap-2 border-b bg-surface px-4 py-2 text-sm">
      <Loader2 aria-hidden className={status === "waking" ? "size-4 animate-spin text-muted-foreground" : "hidden"} />
      {status === "waking" ? (
        <p>The server is waking up. On the free plan this can take up to a minute; the page will fill in by itself.</p>
      ) : (
        <p>The server is not responding. Check that the API is running, then reload the page.</p>
      )}
    </div>
  );
}
