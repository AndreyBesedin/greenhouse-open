import { type PointerEvent, useEffect, useEffectEvent, useRef, useState } from "react";

import { PRESET_ORDER, type PresetName } from "./camera";
import { type Box, isMoved, type Offset, UNMOVED, unmoved, within } from "./hudPlace";
import {
  formatCount,
  formatFrameTime,
  formatInstant,
  formatMemory,
  formatMetres,
  formatPoint,
  type ViewSample,
} from "./readouts";
import type { LiveCommand, LiveConnection, LiveFrame } from "./scene/live";
import { describeSimulatorTime, type SimulatorTime } from "./simulatorTime";
import { TimeControls } from "./TimeControls";
import type { Point3 } from "./world";

const PRESET_LABELS: Record<PresetName, string> = {
  top: "Top",
  front: "Front",
  side: "Side",
  isometric: "Isometric",
};

const PENDING = "…";

// A narrow window docks the panels under the view (styles.css), where the
// HUD keeps its place among them.
const DOCKED = "(max-width: 840px)";
// How far the pointer moves, pressed on the HUD's header, before it drags
// the HUD rather than folds it.
const DRAG_FROM_PX = 4;

/** Whether the panels are docked under the view. */
function docked(): boolean {
  return typeof window.matchMedia === "function" && window.matchMedia(DOCKED).matches;
}

/** The window, the bounds a dragged HUD stays within. */
function windowBox(): Box {
  return { left: 0, top: 0, right: window.innerWidth, bottom: window.innerHeight };
}

/** Where a drag started: the pointer, and the HUD's offset then. */
interface Drag {
  pointer: Offset;
  from: Offset;
  moved: boolean;
}

const CONNECTION_LABELS: Record<LiveConnection, string> = {
  connecting: "connecting…",
  live: "live",
  disconnected: "disconnected, reconnecting…",
};

/** A live scenario's progress, when one is being followed. */
export interface LiveStatus {
  connection: LiveConnection;
  frame: LiveFrame | null;
  /** Why the latest command was not taken, if it was not. */
  problem: string | null;
}

export function Hud({
  sample,
  pointer,
  live = null,
  simulator = null,
  onPreset,
  onCommand,
}: {
  sample: ViewSample | null;
  pointer: Point3 | null;
  live?: LiveStatus | null;
  /** How long the simulator took to answer the latest request (P09.8). */
  simulator?: SimulatorTime | null;
  onPreset: (preset: PresetName) => void;
  onCommand: (command: LiveCommand) => void;
}) {
  const [open, setOpen] = useState(true);
  const [offset, setOffset] = useState<Offset>(UNMOVED);
  const hud = useRef<HTMLElement>(null);
  const drag = useRef<Drag | null>(null);
  // Whether the press that ends in the next click on the header dragged.
  const dragged = useRef(false);

  // The HUD moved to `wanted`, or as near as it stays within the window.
  const placed = (wanted: Offset): Offset => {
    const element = hud.current;
    if (element === null || docked()) {
      return UNMOVED;
    }
    return within(wanted, unmoved(element.getBoundingClientRect(), offset), windowBox());
  };
  // Back within the window when the window or the HUD changes size: a
  // smaller window, or the HUD unfolded near an edge.
  const settle = useEffectEvent(() => {
    const next = placed(offset);
    if (next.x !== offset.x || next.y !== offset.y) {
      setOffset(next);
    }
  });
  useEffect(() => {
    const element = hud.current;
    const resized = () => settle();
    window.addEventListener("resize", resized);
    const observer = typeof ResizeObserver === "undefined" ? null : new ResizeObserver(resized);
    if (element !== null) {
      observer?.observe(element);
    }
    return () => {
      window.removeEventListener("resize", resized);
      observer?.disconnect();
    };
  }, []);

  const press = (event: PointerEvent<HTMLElement>) => {
    // Should a drag's click have landed elsewhere, this press's click is
    // still the header's own.
    dragged.current = false;
    if (event.button !== 0 || docked()) {
      return;
    }
    event.currentTarget.setPointerCapture(event.pointerId);
    drag.current = { pointer: { x: event.clientX, y: event.clientY }, from: offset, moved: false };
  };
  const move = (event: PointerEvent<HTMLElement>) => {
    const pressed = drag.current;
    if (pressed === null) {
      return;
    }
    const x = event.clientX - pressed.pointer.x;
    const y = event.clientY - pressed.pointer.y;
    if (!pressed.moved && Math.hypot(x, y) < DRAG_FROM_PX) {
      return;
    }
    pressed.moved = true;
    setOffset(placed({ x: pressed.from.x + x, y: pressed.from.y + y }));
  };
  const release = () => {
    dragged.current = drag.current?.moved ?? false;
    drag.current = null;
  };

  return (
    <section
      ref={hud}
      className={open ? "hud" : "hud folded"}
      aria-label="View"
      style={isMoved(offset) ? { transform: `translate(${offset.x}px, ${offset.y}px)` } : undefined}
    >
      <details open={open} onToggle={(event) => setOpen(event.currentTarget.open)}>
        {/* biome-ignore lint/a11y/noStaticElementInteractions: a summary is its details' own control, which a keyboard folds; the pointer handlers only drag it. */}
        <summary
          title="Click to fold or unfold; drag to move"
          onPointerDown={press}
          onPointerMove={move}
          onPointerUp={release}
          onPointerCancel={release}
          onClick={(event) => {
            // A drag ends in a click on the header, which would fold it.
            if (dragged.current) {
              event.preventDefault();
              dragged.current = false;
            }
          }}
        >
          View
        </summary>
        <HudBody
          sample={sample}
          pointer={pointer}
          live={live}
          simulator={simulator}
          onPreset={onPreset}
          onCommand={onCommand}
        />
        {isMoved(offset) && (
          <button type="button" className="hud-put-back" onClick={() => setOffset(UNMOVED)}>
            Put it back
          </button>
        )}
      </details>
    </section>
  );
}

/** The HUD's presets, readouts and live controls, under its header. */
function HudBody({
  sample,
  pointer,
  live,
  simulator,
  onPreset,
  onCommand,
}: {
  sample: ViewSample | null;
  pointer: Point3 | null;
  live: LiveStatus | null;
  simulator: SimulatorTime | null;
  onPreset: (preset: PresetName) => void;
  onCommand: (command: LiveCommand) => void;
}) {
  return (
    <>
      <fieldset aria-label="Camera presets">
        {PRESET_ORDER.map((preset) => (
          <button type="button" key={preset} onClick={() => onPreset(preset)}>
            {PRESET_LABELS[preset]}
          </button>
        ))}
      </fieldset>
      <dl>
        <dt>Camera (m)</dt>
        <dd data-testid="camera-position">{sample ? formatPoint(sample.camera) : PENDING}</dd>
        <dt>Pointer on ground (m)</dt>
        <dd data-testid="pointer-position">
          {pointer ? `x ${formatMetres(pointer.x)}, y ${formatMetres(pointer.y)}` : "—"}
        </dd>
        {/* The view draws only when something changes (decision 0053): still,
            it has no frame rate, and its frame time is that of its last frames. */}
        <dt>Frame rate</dt>
        <dd data-testid="frame-rate">
          {sample === null
            ? PENDING
            : !sample.drawing
              ? "idle"
              : sample.rate === null
                ? PENDING
                : `${Math.round(sample.rate.framesPerSecond)} fps`}
        </dd>
        <dt>Frame time</dt>
        <dd data-testid="frame-time">
          {sample?.rate
            ? formatFrameTime(sample.rate.frameTimeMs, sample.rate.worstFrameMs)
            : PENDING}
        </dd>
        <dt>Draw calls</dt>
        <dd data-testid="draw-calls">
          {sample
            ? `${formatCount(sample.drawCalls)} (${formatCount(sample.triangles)} triangles)`
            : PENDING}
        </dd>
        <dt>Objects</dt>
        <dd data-testid="object-count">{sample ? sample.objects : PENDING}</dd>
        <dt>Memory</dt>
        <dd data-testid="memory">
          {sample ? formatMemory(sample.geometries, sample.textures, sample.heapBytes) : PENDING}
        </dd>
        <dt>Simulator</dt>
        {/* On one line, its path cut short and given whole on hover, so that
            the panel keeps its height whatever the latest request (#301). */}
        <dd
          className="hud-simulator"
          data-testid="simulator-time"
          title={simulator ? describeSimulatorTime(simulator) : undefined}
        >
          {simulator ? describeSimulatorTime(simulator) : "—"}
        </dd>
        {live && (
          <>
            <dt>Stream</dt>
            <dd data-testid="stream-status">{CONNECTION_LABELS[live.connection]}</dd>
            <dt>Simulation</dt>
            <dd data-testid="simulation-time">
              {live.frame
                ? `day ${live.frame.day} · ${formatInstant(live.frame.timestamp)}`
                : PENDING}
            </dd>
          </>
        )}
      </dl>
      {live && (
        <>
          <TimeControls
            frame={live.frame}
            connected={live.connection === "live"}
            onCommand={onCommand}
          />
          {live.problem && (
            <p className="command-problem" role="alert" data-testid="command-problem">
              {live.problem}
            </p>
          )}
        </>
      )}
    </>
  );
}
