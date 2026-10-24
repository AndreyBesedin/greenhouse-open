import { framesPerSecond } from "./readouts";

/** How fast the view draws, over frames drawn one after another. */
export interface FrameRate {
  framesPerSecond: number;
  /** The mean and the longest time from one frame to the next, in milliseconds. */
  frameTimeMs: number;
  worstFrameMs: number;
}

// The view draws only when something changes (decision 0053): a longer gap
// between two frames is the view standing still, not a slow frame. Slower
// than this, a view that moves could not be used anyway.
export const IDLE_AFTER_MS = 1000;
// Often enough to read as live, rarely enough not to re-render the page on
// every frame.
export const SAMPLE_INTERVAL_MS = 250;

/**
 * Measures the view's frames as they are drawn. Only the gaps between frames
 * drawn in a row count, so that a frame drawn after the view stood still, a
 * click's, says nothing of its rate.
 */
export class FrameMeter {
  private lastFrame: number | null = null;
  private lastReport: number | null = null;
  private gaps = 0;
  private gapsMs = 0;
  private worstGapMs = 0;
  private measured: FrameRate | null = null;

  /** Counts a frame drawn at `now`, and says whether a report is due. */
  frame(now: number): boolean {
    if (this.lastFrame !== null && now - this.lastFrame <= IDLE_AFTER_MS) {
      const gap = now - this.lastFrame;
      this.gaps += 1;
      this.gapsMs += gap;
      this.worstGapMs = Math.max(this.worstGapMs, gap);
    }
    this.lastFrame = now;
    return this.lastReport === null || now - this.lastReport >= SAMPLE_INTERVAL_MS;
  }

  /** The rate over the frames counted since the last report, or, if none
   * came in a row, the last rate measured: null before any. */
  report(now: number): FrameRate | null {
    if (this.gaps > 0) {
      this.measured = {
        framesPerSecond: framesPerSecond(this.gaps, this.gapsMs),
        frameTimeMs: this.gapsMs / this.gaps,
        worstFrameMs: this.worstGapMs,
      };
    }
    this.gaps = 0;
    this.gapsMs = 0;
    this.worstGapMs = 0;
    this.lastReport = now;
    return this.measured;
  }
}
