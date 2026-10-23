import { type ComponentProps, useEffect, useMemo, useState } from "react";

import type { MoveDragging } from "../MoveDrag";
import type { MoveDraft, MovePanel } from "../MovePanel";
import { DEFAULT_LAYOUT } from "../scenarios";
import type { SceneEntity, SceneSnapshot } from "./generated/snapshotTypes";
import {
  keptInside,
  movableItem,
  movesBetween,
  movesIn,
  NO_OFFSET,
  type Offset,
  plus,
  shifted,
} from "./moves";
import type { PlaybackLoad } from "./playback";
import type { SceneSource } from "./source";
import { useMoveSession } from "./useMoveSession";
import type { SetSource } from "./useSource";

/**
 * Moving equipment and sensors in a scenario's view (#209, #271): a Move
 * session's moves, held until they are applied, all at once (while the view
 * follows the run played back, it starts over with them), and the selected
 * item's drag under way.
 *
 * It gives what the view draws of them: each item a session moves, by
 * entity, where the session draws it (`nudged`), from where the scene shown
 * places it, the scene of the layout the session started from, the selected
 * item's drag added, and the selected item so drawn (`drawnSelected`); the
 * Move panel's props (`panel`), for the selected item if it can be moved
 * and for a session under way, whatever is selected; and the drag the view
 * runs on the selected item (`drag`), kept inside its house. Escape cancels
 * a session's moves, unless it cancels a drag (`MoveDrag`). Starting a
 * session calls `onStart`, as placing probes stops then.
 */
export function useMoveDrag({
  source,
  setSource,
  followed,
  onPlayback,
  sceneLoading,
  snapshot,
  selected,
  onStart,
}: {
  source: SceneSource;
  setSource: (change: SetSource) => void;
  followed: string | null;
  onPlayback: (load: PlaybackLoad) => void;
  sceneLoading: boolean;
  snapshot: SceneSnapshot | null;
  selected: SceneEntity | null;
  onStart: () => void;
}) {
  // The drag moving the selected item, how far from where the session draws
  // it.
  const [dragging, setDragging] = useState<{ entityId: string; by: Offset } | null>(null);
  const movable = source.kind === "scenario" && selected !== null ? movableItem(selected) : null;
  const layoutShown = source.kind === "scenario" ? source.layout : undefined;
  const moves = useMoveSession({
    source,
    setSource,
    defaultLayout: DEFAULT_LAYOUT,
    followed,
    onPlayback,
    sceneLoading,
  });
  const session = moves.session;
  if (dragging !== null && (session === null || session.applying)) {
    setDragging(null);
  }
  const moving = movable !== null && selected !== null && session !== null && !session.applying;
  const house = useMemo(
    () => snapshot?.entities.find((entity) => entity.kind === "GREENHOUSE_BOUNDS") ?? null,
    [snapshot],
  );
  const itemEntities = useMemo(() => {
    const entities = new Map<string, SceneEntity>();
    for (const entity of snapshot?.entities ?? []) {
      const item = movableItem(entity);
      if (item !== null) {
        entities.set(item, entity);
      }
    }
    return entities;
  }, [snapshot]);
  const sessionMoves = session === null ? {} : movesBetween(session.from, session.to);
  const nudged: Record<string, Offset> = {};
  for (const [item, by] of Object.entries(sessionMoves)) {
    const entity = itemEntities.get(item);
    if (entity !== undefined) {
      nudged[entity.entity_id] = by;
    }
  }
  const placedBy = movable === null ? null : (sessionMoves[movable] ?? null);
  if (dragging !== null && selected !== null && dragging.entityId === selected.entity_id) {
    nudged[dragging.entityId] = plus(placedBy ?? NO_OFFSET, dragging.by);
  }
  const selectedNudge = selected === null ? undefined : nudged[selected.entity_id];
  const drawnSelected =
    selected === null || selectedNudge === undefined ? selected : shifted(selected, selectedNudge);
  // How far the selected item stands from where its layout places it, as the
  // session draws it, a drag under way included.
  const layoutMoves = movesIn(session === null ? layoutShown : session.to);
  const standsBy = (() => {
    if (movable === null) {
      return null;
    }
    const placed = layoutMoves[movable] ?? null;
    const by = dragging !== null && dragging.entityId === selected?.entity_id ? dragging.by : null;
    const total = by === null ? placed : plus(placed ?? NO_OFFSET, by);
    return total === null || (total.dx === 0 && total.dy === 0) ? null : total;
  })();

  // A session's moves as the Move panel lists them, by what each item is
  // called, and what applying them does.
  const draft: MoveDraft | null =
    session === null
      ? null
      : {
          moves: Object.entries(movesIn(session.to))
            .filter(([, by]) => by.dx !== 0 || by.dy !== 0)
            .map(([item, by]) => ({ item, label: itemEntities.get(item)?.label ?? item, by })),
          changed: moves.changed,
          following: followed !== null,
          applying: session.applying,
          failure: session.failure,
        };
  function drop(by: Offset | null): void {
    setDragging(null);
    if (movable !== null && by !== null && (by.dx !== 0 || by.dy !== 0)) {
      moves.move(movable, by);
    }
  }

  const drafting = session !== null && !session.applying;
  const cancelMoves = moves.cancel;
  useEffect(() => {
    if (!drafting) {
      return;
    }
    function cancel(event: KeyboardEvent): void {
      if (event.key === "Escape" && !event.defaultPrevented) {
        cancelMoves();
      }
    }
    window.addEventListener("keydown", cancel);
    return () => window.removeEventListener("keydown", cancel);
  }, [drafting, cancelMoves]);

  const panel: ComponentProps<typeof MovePanel> | null =
    source.kind === "scenario" && (movable !== null || draft !== null)
      ? {
          item:
            movable === null || selected === null
              ? null
              : { label: selected.label ?? movable, movedBy: standsBy },
          draft,
          onMove: () => {
            onStart();
            moves.start();
          },
          onPutBack: moves.putBack,
          onPutEverythingBack: moves.putEverythingBack,
          onApply: () => void moves.apply(),
          onCancel: moves.cancel,
        }
      : null;
  const drag: MoveDragging | null =
    moving && selected !== null
      ? {
          heightM: selected.transform.position.z,
          // From where the session draws the item.
          shape: (by) =>
            keptInside(by, placedBy === null ? selected : shifted(selected, placedBy), house),
          onDrag: (by) => setDragging(by === null ? null : { entityId: selected.entity_id, by }),
          onDrop: drop,
        }
      : null;
  return { nudged, drawnSelected, panel, drag };
}
