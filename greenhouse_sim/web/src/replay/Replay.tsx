import { useMemo, useRef } from "react";

import { App } from "../App";
import { HomeButton } from "../landing/HomeButton";
import { replayTarget, runsAddress } from "../landing/paths";
import { loadScenarios, SCENARIOS_URL } from "../scenarios";
import { replayedMoment } from "../scene/useReplayMoment";
import { useLoad } from "../useLoad";
import { ReplayHeader } from "./ReplayHeader";
import { ReplayTransport } from "./ReplayTransport";
import { planKey, replaySource } from "./replaySource";
import { useFork } from "./useFork";
import { useReplay } from "./useReplay";

/**
 * The replay of a stored run (P17.6, decision 0065): a page whose address
 * names the run and its epoch. A position is opened over the epoch, the
 * viewer draws the scene at its moment, and the transport and the timeline
 * move the position through what the epoch has computed, while a worker
 * may still be computing it. A change made here is a fork from the moment
 * shown (P17.8): the epoch replayed is never changed, and the page goes to the
 * fork.
 */
export function Replay({ search = location.search }: { search?: string }) {
  const target = replayTarget(search);
  if (target === null) {
    return (
      <Notice>
        <p>This address names no run to replay: it wants a run and an epoch.</p>
      </Notice>
    );
  }
  return <ReplayOf runId={target.runId} epoch={target.epoch} />;
}

function ReplayOf({ runId, epoch }: { runId: string; epoch: number }) {
  const { load, refused, command, seek, pace } = useReplay(runId, epoch);
  const scenarios = useLoad(SCENARIOS_URL, (_url, fetchFn) => loadScenarios(fetchFn));
  const position = load.status === "loaded" ? load.position : null;
  // The scene is the epoch's own run, which no moment of the position changes.
  const scenarioId = position?.scenario_id;
  const layout = position?.layout;
  const seed = position?.seed;
  const plan = position === null ? null : planKey(position);
  const planned = useRef(position);
  planned.current = position;
  // biome-ignore lint/correctness/useExhaustiveDependencies: the plan's text says when it changed.
  const source = useMemo(
    () =>
      scenarioId === undefined ||
      layout === undefined ||
      seed === undefined ||
      planned.current === null
        ? null
        : replaySource(planned.current),
    [scenarioId, layout, seed, plan],
  );
  const { forking, refused, fork } = useFork(useMemo(() => ({ runId, epoch }), [runId, epoch]));

  if (position === null || source === null) {
    return (
      <Notice>
        <p role={load.status === "unavailable" ? "alert" : "status"} data-testid="replay-notice">
          {load.status === "unavailable"
            ? `This run cannot be replayed: ${load.reason}.`
            : "Opening the run…"}
        </p>
      </Notice>
    );
  }
  const name =
    scenarios.status === "loaded"
      ? (scenarios.scenarios.find((each) => each.id === position.scenario_id)?.name ?? null)
      : null;
  return (
    <div className="replay">
      <ReplayHeader
        name={name}
        position={position}
        otherRunsHref={runsAddress(position.scenario_id)}
        forking={forking}
        forkRefused={refused}
        onFork={() => void fork({ timeS: position.time_s })}
      />
      <div className="replay-scene">
        <App
          replay={{
            source,
            momentS: replayedMoment(position.time_s),
            seek,
            forkWith: (change, timeS) => void fork({ timeS, changes: [change] }),
            forkInLayout: (forkLayout, timeS) => fork({ timeS, layout: forkLayout }),
          }}
        />
      </div>
      <ReplayTransport
        position={position}
        refused={refused}
        onPlay={() => command("play")}
        onPause={() => command("pause")}
        onFollow={() => command("follow")}
        onSeek={seek}
        onPace={pace}
      />
    </div>
  );
}

/** What the page says while there is no run to show, with the way home. */
function Notice({ children }: { children: React.ReactNode }) {
  return (
    <div className="replay">
      <header className="replay-header">
        <HomeButton />
      </header>
      <div className="replay-notice">{children}</div>
    </div>
  );
}
