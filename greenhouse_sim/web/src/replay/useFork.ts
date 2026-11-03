import { useRef, useState } from "react";

import { replayAddress } from "../landing/paths";
import { type ForkAsked, forkEpoch } from "./fork";

// What asks for a fork while one is under way is told so, and can ask again:
// that one may yet be refused, and the page stay.
const ONE_AT_A_TIME = "another fork is on its way";

/**
 * Forking the epoch a replay shows (P17.8, decision 0065): one at a time, and
 * once one is started the page goes to it, since it is what the person asked
 * to see. It returns why one could not be made, also for what asked for it.
 */
export function useFork(
  epoch: { runId: string; epoch: number } | null,
  {
    fetchFn = fetch,
    goTo = (address: string) => location.assign(address),
  }: { fetchFn?: typeof fetch; goTo?: (address: string) => void } = {},
) {
  const [forking, setForking] = useState(false);
  const [refused, setRefused] = useState<string | null>(null);
  // Asked for at once by whatever changes next, before a render says so.
  const underWay = useRef(false);

  async function fork(asked: ForkAsked): Promise<string | null> {
    if (epoch === null) {
      return null;
    }
    if (underWay.current) {
      return ONE_AT_A_TIME;
    }
    underWay.current = true;
    setForking(true);
    setRefused(null);
    const answer = await forkEpoch(epoch.runId, epoch.epoch, asked, fetchFn);
    if (answer.status === "started") {
      goTo(replayAddress(answer.runId, answer.epoch));
      return null;
    }
    underWay.current = false;
    setForking(false);
    setRefused(answer.reason);
    return answer.reason;
  }
  return { forking, refused, fork };
}
