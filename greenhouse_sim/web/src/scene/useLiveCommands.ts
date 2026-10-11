import { useCallback, useEffect, useRef, useState } from "react";

import { type CommandResult, type LiveCommand, sendLiveCommand } from "./live";

export interface LiveCommands {
  /** Why the latest command failed, if it did. */
  problem: string | null;
  /** Sends a command to the scenario followed, if one is. */
  send: (command: LiveCommand) => void;
  /** Forgets what was sent: its answers, still to come, give no feedback. */
  forget: () => void;
}

/**
 * Commands to a scenario played live, and how the latest went. Only the
 * latest command, to the scenario followed now, may say so: an older one's
 * answer, or one that arrives after the scenario changed, even back again, or
 * after the viewer has gone, is dropped. It does not undo what the simulator
 * was already told.
 */
export function useLiveCommands(
  scenarioId: string | null,
  sendFn: (scenarioId: string, command: LiveCommand) => Promise<CommandResult> = sendLiveCommand,
): LiveCommands {
  const [problem, setProblem] = useState<string | null>(null);
  const latest = useRef(0);

  const forget = useCallback(() => {
    latest.current += 1;
    setProblem(null);
  }, []);

  // Another scenario, or none: what was sent to the last has nothing to say.
  // biome-ignore lint/correctness/useExhaustiveDependencies: forgotten whenever the scenario changes.
  useEffect(() => forget, [scenarioId, forget]);

  const send = useCallback(
    (command: LiveCommand) => {
      if (scenarioId === null) {
        return;
      }
      const sent = ++latest.current;
      void sendFn(scenarioId, command).then((result) => {
        if (sent === latest.current) {
          setProblem(result.ok ? null : result.problem);
        }
      });
    },
    [scenarioId, sendFn],
  );

  return { problem, send, forget };
}
