import { type RootState, useFrame } from "@react-three/fiber";
import { useEffect, useRef } from "react";

import { FrameMeter, IDLE_AFTER_MS } from "./frameMeter";
import type { ViewSample } from "./readouts";
import { viewerToWorld } from "./world";

/** The page's JavaScript heap in bytes, which only Chromium reports. */
function heapBytes(): number | null {
  const { memory } = performance as Performance & { memory?: { usedJSHeapSize: number } };
  return memory === undefined ? null : memory.usedJSHeapSize;
}

/** What the view holds and last drew. */
function measured({ camera, scene, gl }: RootState): Omit<ViewSample, "drawing" | "rate"> {
  let objects = 0;
  scene.traverse(() => {
    objects += 1;
  });
  // The renderer counts each frame's work afresh; until this frame is drawn,
  // its counts are the previous frame's.
  const { render, memory } = gl.info;
  return {
    drawCalls: render.calls,
    triangles: render.triangles,
    geometries: memory.geometries,
    textures: memory.textures,
    heapBytes: heapBytes(),
    camera: viewerToWorld(camera.position),
    // The scene itself is not an object in it.
    objects: objects - 1,
  };
}

/**
 * Measures the view from inside the canvas, and reports it a few times a
 * second while it draws. The view draws only when something changes
 * (decision 0053), so no frame comes to say it has stopped: a report follows
 * the last frame once the view has stood still long enough to count as idle.
 */
export function HudProbe({ onSample }: { onSample: (sample: ViewSample) => void }) {
  const meter = useRef<FrameMeter | null>(null);
  const idle = useRef<number | undefined>(undefined);
  const told = useRef(onSample);
  told.current = onSample;

  useEffect(() => () => window.clearTimeout(idle.current), []);

  useFrame((state) => {
    meter.current ??= new FrameMeter();
    const frames = meter.current;
    const now = performance.now();
    const due = frames.frame(now);
    window.clearTimeout(idle.current);
    idle.current = window.setTimeout(() => {
      told.current({ ...measured(state), drawing: false, rate: frames.report(performance.now()) });
    }, IDLE_AFTER_MS);
    if (due) {
      told.current({ ...measured(state), drawing: true, rate: frames.report(now) });
    }
  });

  return null;
}
