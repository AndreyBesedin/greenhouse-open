import { useEffect, useEffectEvent, useState } from "react";

// The address's part that turns QA mode on (P09.6): `qa=1`.
const QA_PART = "qa=1";
const QA_NAME = "qa";

/** Whether an address turns QA mode on. */
export function qaModeFrom(search: string): boolean {
  return new URLSearchParams(search).get(QA_NAME) === "1";
}

/** An address with QA mode on or off, the rest of it as it was: `qa=1` at
 * its end while on, and no `qa=` while off. */
export function withQaMode(search: string, on: boolean): string {
  const parts = search
    .replace(/^\?/, "")
    .split("&")
    .filter((part) => part !== "" && part.split("=")[0] !== QA_NAME);
  const kept = on ? [...parts, QA_PART] : parts;
  return kept.length === 0 ? "" : `?${kept.join("&")}`;
}

/** Writes QA mode into the address, unless the address says so already. */
function keepInAddress(on: boolean): void {
  if (qaModeFrom(location.search) !== on) {
    history.replaceState(null, "", `${location.pathname}${withQaMode(location.search, on)}`);
  }
}

/**
 * Whether the viewer is in QA mode, and how to change it: read from the
 * address once and kept in it, whatever the scene's source writes there
 * (`useSource`), so that a refresh, or the address shared, opens the same
 * view. Off by default. Only QA mode asks the simulator for truth.
 */
export function useQaMode(): [boolean, (on: boolean) => void] {
  const [on, setOn] = useState(() => qaModeFrom(location.search));

  useEffect(() => keepInAddress(on), [on]);

  // Back to a page whose address was written before QA mode changed: QA
  // mode stays as it is, and the address says so again.
  const returned = useEffectEvent(() => keepInAddress(on));
  useEffect(() => {
    const listener = () => returned();
    window.addEventListener("popstate", listener);
    return () => window.removeEventListener("popstate", listener);
  }, []);

  return [on, setOn];
}
