import { useFrame } from "@react-three/fiber";
import { useRef } from "react";

import { framesPerSecond, type ViewSample } from "./readouts";
import { viewerToWorld } from "./world";

// Often enough to read as live, rarely enough not to re-render the page on
// every frame.
const SAMPLE_INTERVAL_MS = 250;

/** The page's JavaScript heap in bytes, which only Chromium reports. */
function heapBytes(): number | null {
  const { memory } = performance as Performance & { memory?: { usedJSHeapSize: number } };
  return memory === undefined ? null : memory.usedJSHeapSize;
}

/** Measures the view from inside the canvas and reports it a few times a second. */
export function HudProbe({ onSample }: { onSample: (sample: ViewSample) => void }) {
  const frames = useRef(0);
  const windowStart = useRef<number | null>(null);
  const lastFrame = useRef<number | null>(null);
  const worstFrame = useRef(0);

  useFrame(({ camera, scene, gl }) => {
    const now = performance.now();
    if (lastFrame.current !== null) {
      worstFrame.current = Math.max(worstFrame.current, now - lastFrame.current);
    }
    lastFrame.current = now;
    if (windowStart.current === null) {
      windowStart.current = now;
      return;
    }
    frames.current += 1;
    const elapsed = now - windowStart.current;
    if (elapsed < SAMPLE_INTERVAL_MS) {
      return;
    }

    let objects = 0;
    scene.traverse(() => {
      objects += 1;
    });
    // The renderer counts each frame's work afresh; until this frame is drawn,
    // its counts are the previous frame's.
    const { render, memory } = gl.info;
    onSample({
      framesPerSecond: framesPerSecond(frames.current, elapsed),
      frameTimeMs: elapsed / frames.current,
      worstFrameMs: worstFrame.current,
      drawCalls: render.calls,
      triangles: render.triangles,
      geometries: memory.geometries,
      textures: memory.textures,
      heapBytes: heapBytes(),
      camera: viewerToWorld(camera.position),
      // The scene itself is not an object in it.
      objects: objects - 1,
    });
    frames.current = 0;
    worstFrame.current = 0;
    windowStart.current = now;
  });

  return null;
}
