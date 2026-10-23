import { describe, expect, it } from "vitest";

import { begun, edited, MOST_UNDOS, redone, undone } from "./history";

describe("a draft's edits (P12.2)", () => {
  it("are undone and redone one step at a time", () => {
    const history = edited(edited(begun("a"), "b"), "c");

    expect(undone(history).present).toBe("b");
    expect(undone(undone(history)).present).toBe("a");
    expect(redone(undone(undone(history))).present).toBe("b");
    // With nothing left to undo or redo, nothing changes.
    expect(undone(begun("a"))).toEqual(begun("a"));
    expect(redone(history)).toBe(history);
  });

  it("forget what an undo left to redo once another edit is made", () => {
    const history = edited(undone(edited(begun("a"), "b")), "c");

    expect(history).toEqual({ past: ["a"], present: "c", future: [] });
  });

  it("reach back as far as the most undos kept", () => {
    let history = begun(0);
    for (let step = 1; step <= MOST_UNDOS + 5; step += 1) {
      history = edited(history, step);
    }

    expect(history.past).toHaveLength(MOST_UNDOS);
    expect(history.past[0]).toBe(5);
  });
});
