import { describe, expect, it } from "vitest";

import {
  draftAddress,
  draftAsked,
  LANDING_PATH,
  newRunAddress,
  newRunScenario,
  opensFramed,
  pageAt,
  REPLAY_PATH,
  replayAddress,
  replayTarget,
  runsAddress,
  runsScenario,
  VIEWER_PATH,
  viewerAddress,
} from "./paths";

describe("the addresses that open a scenario framed", () => {
  it("are the viewer's and a replay's, not a link from before the landing page", () => {
    expect(opensFramed(VIEWER_PATH)).toBe(true);
    expect(opensFramed(REPLAY_PATH)).toBe(true);
    expect(opensFramed("/")).toBe(false);
  });
});

describe("the viewer's addresses", () => {
  it("shows the landing page at the bare address, with or without its slash", () => {
    expect(pageAt(LANDING_PATH, "")).toBe("landing");
    expect(pageAt("", "")).toBe("landing");
  });

  it("still shows the viewer at an address with a query, as links to it always have", () => {
    expect(pageAt("/", "?scenario=climate_box")).toBe("viewer");
    expect(pageAt("/", "?scene=example")).toBe("viewer");
    expect(pageAt("/", "?plants=lab&day=45")).toBe("viewer");
  });

  it("shows the viewer at its own address and at any other path", () => {
    expect(pageAt(VIEWER_PATH, "")).toBe("viewer");
    expect(pageAt(`${VIEWER_PATH}/`, "")).toBe("viewer");
    expect(pageAt("/anything-else", "")).toBe("viewer");
  });

  it("writes an address that names the scenario, its identifier made safe", () => {
    expect(viewerAddress("climate_box")).toBe("/view?scenario=climate_box");
    expect(viewerAddress("a b&c")).toBe("/view?scenario=a%20b%26c");
  });

  it("shows the replay at its own address, even with a query", () => {
    expect(pageAt(REPLAY_PATH, "?run=r&epoch=0")).toBe("replay");
    expect(pageAt(`${REPLAY_PATH}/`, "")).toBe("replay");
  });

  it("names a replayed run by its run and its epoch, made safe", () => {
    expect(replayAddress("climate_box-abc", 2)).toBe("/replay?run=climate_box-abc&epoch=2");
    expect(replayAddress("a b&c", 0)).toBe("/replay?run=a%20b%26c&epoch=0");
    expect(replayTarget("?run=a%20b%26c&epoch=3")).toEqual({
      runId: "a b&c",
      epoch: 3,
      following: false,
    });
    expect(replayAddress("r", 3, true)).toBe("/replay?run=r&epoch=3&follow=1");
    expect(replayTarget("?run=r&epoch=3&follow=1")).toEqual({
      runId: "r",
      epoch: 3,
      following: true,
    });
  });

  it("asks for no replay unless a run and a whole epoch are named", () => {
    expect(replayTarget("")).toBeNull();
    expect(replayTarget("?run=r")).toBeNull();
    expect(replayTarget("?epoch=1")).toBeNull();
    expect(replayTarget("?run=&epoch=1")).toBeNull();
    expect(replayTarget("?run=r&epoch=-1")).toBeNull();
    expect(replayTarget("?run=r&epoch=1.5")).toBeNull();
    expect(replayTarget("?run=r&epoch=x")).toBeNull();
  });

  it("asks the landing page for a scenario's runs by a fragment, still the bare address", () => {
    expect(runsAddress("my house/1")).toBe("/#runs=my%20house%2F1");
    expect(runsScenario("#runs=my%20house%2F1")).toBe("my house/1");
    expect(runsScenario("#run=x")).toBeNull();
    expect(runsScenario("#runs=")).toBeNull();
    expect(runsScenario("#runs=%E0%A4%A")).toBeNull();
    expect(pageAt("/", "")).toBe("landing");
  });

  it("asks the landing page for a scenario's new-run form by a fragment, which is still the bare address", () => {
    expect(newRunAddress("my house/1")).toBe("/#run=my%20house%2F1");
    expect(pageAt("/", "")).toBe("landing");
    expect(newRunScenario("#run=my%20house%2F1")).toBe("my house/1");
    expect(newRunScenario("")).toBeNull();
    expect(newRunScenario("#run=")).toBeNull();
    expect(newRunScenario("#elsewhere")).toBeNull();
    expect(newRunScenario("#run=%E0%A4%A")).toBeNull();
  });
});

describe("the address of a saved draft", () => {
  it("is the builder's, its draft in a fragment, and reads back", () => {
    expect(draftAddress("my house")).toBe("/builder#draft=my%20house");
    expect(draftAsked("#draft=my%20house")).toBe("my house");
  });

  it("asks for none where it names none, or none that can be read", () => {
    expect(draftAsked("")).toBeNull();
    expect(draftAsked("#draft=")).toBeNull();
    expect(draftAsked("#scenario=box")).toBeNull();
    expect(draftAsked("#draft=%E0%A4%A")).toBeNull();
  });
});
