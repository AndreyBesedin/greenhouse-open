import { DEFAULT_LAYOUT } from "../scenarios";
import { layoutText } from "../scene/moves";
import { viewerAddress } from "./paths";

/** The viewer following a scenario's run as it is played back, in the layout
 * that run has if it is not the scenario's own. Apart from `paths`, which the
 * browser tests read for their constants and which imports nothing. */
export function followAddress(scenarioId: string, layout = DEFAULT_LAYOUT): string {
  const shown = layout === DEFAULT_LAYOUT ? "" : `&layout=${layoutText(layout)}`;
  return viewerAddress(scenarioId, `${shown}&field=climate&follow=1`);
}
