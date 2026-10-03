import { useFrame } from "@react-three/fiber";
import { useRef } from "react";

import { framesPerSecond, type ViewSample } from "./readouts";
import { viewerToWorld } from "./world";

// Often enough to read as live, rarely enough not to re-render the page on
// every frame.
const SAMPLE_INTERVAL_MS = 250;

/** Measures the view from inside the canvas and reports it a few times a second. */
export function HudProbe({ onSample }: { onSample: (sample: ViewSample) => void }) {
  const frames = useRef(0);
  const windowStart = useRef<number | null>(null);

  useFrame(({ camera, scene }) => {
    const now = performance.now();
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
    onSample({
      framesPerSecond: framesPerSecond(frames.current, elapsed),
      camera: viewerToWorld(camera.position),
      // The scene itself is not an object in it.
      objects: objects - 1,
    });
    frames.current = 0;
    windowStart.current = now;
  });

  return null;
}
