import { describe, expect, it } from "vitest";

import { FrameMeter, IDLE_AFTER_MS, SAMPLE_INTERVAL_MS } from "./frameMeter";

/** Draws a frame at each instant, in milliseconds, and reports after the last. */
function drawn(meter: FrameMeter, instants: number[]) {
  for (const instant of instants) {
    meter.frame(instant);
  }
  return meter.report(instants.at(-1) ?? 0);
}

describe("the view's frame meter", () => {
  it("measures the frames drawn in a row", () => {
    const rate = drawn(new FrameMeter(), [0, 20, 40, 70]);

    expect(rate).toEqual({ framesPerSecond: 3000 / 70, frameTimeMs: 70 / 3, worstFrameMs: 30 });
  });

  it("does not count the view standing still as a slow frame", () => {
    // Orbited, left still for two seconds, then orbited again.
    const rate = drawn(new FrameMeter(), [0, 20, 40, 2040, 2060]);

    expect(rate).toEqual({ framesPerSecond: 50, frameTimeMs: 20, worstFrameMs: 20 });
  });

  it("counts a slow frame up to the moment the view counts as still", () => {
    const rate = drawn(new FrameMeter(), [0, IDLE_AFTER_MS]);

    expect(rate?.worstFrameMs).toBe(IDLE_AFTER_MS);
  });

  it("has no rate before two frames are drawn in a row", () => {
    expect(drawn(new FrameMeter(), [0])).toBeNull();
    expect(drawn(new FrameMeter(), [0, IDLE_AFTER_MS + 1])).toBeNull();
  });

  it("keeps the last rate measured through a frame drawn on its own", () => {
    const meter = new FrameMeter();
    drawn(meter, [0, 20, 40]);

    // A click, long after: one frame, with no other near it.
    expect(drawn(meter, [5000])).toEqual({
      framesPerSecond: 50,
      frameTimeMs: 20,
      worstFrameMs: 20,
    });
  });

  it("measures each report's frames afresh", () => {
    const meter = new FrameMeter();
    drawn(meter, [0, 10, 20]);

    expect(drawn(meter, [60, 100])?.frameTimeMs).toBe(40);
  });

  it("says a report is due on the first frame, then once in each interval", () => {
    const meter = new FrameMeter();

    expect(meter.frame(0)).toBe(true);
    meter.report(0);
    expect(meter.frame(SAMPLE_INTERVAL_MS - 1)).toBe(false);
    expect(meter.frame(SAMPLE_INTERVAL_MS)).toBe(true);
  });
});
