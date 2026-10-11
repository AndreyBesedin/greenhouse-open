// @vitest-environment jsdom
import { act } from "react";
import { describe, expect, it } from "vitest";

import { renderHook } from "../testing/renderHook";
import type { CommandResult, LiveCommand } from "./live";
import { useLiveCommands } from "./useLiveCommands";

/** A sender whose answers arrive when the test says, in the order it says. */
function answering() {
  const waiting: ((result: CommandResult) => void)[] = [];
  const sent: string[] = [];
  function send(scenarioId: string, command: LiveCommand): Promise<CommandResult> {
    sent.push(`${scenarioId} ${typeof command === "string" ? command : `speed ${command.speed}`}`);
    return new Promise((resolve) => {
      waiting.push(resolve);
    });
  }
  async function answer(index: number, result: CommandResult): Promise<void> {
    const resolve = waiting[index];
    if (resolve === undefined) {
      throw new Error(`no command ${index} was sent`);
    }
    await act(async () => resolve(result));
  }
  return { send, sent, answer };
}

const REFUSED: CommandResult = { ok: false, problem: "the simulator answered 409: it plays" };
const DONE: CommandResult = { ok: true };

describe("commands to a scenario played live", () => {
  it("are sent to the scenario followed, and say why the latest failed", async () => {
    const { send, sent, answer } = answering();
    const hook = renderHook((id: string | null) => useLiveCommands(id, send), "climate_box");

    act(() => hook.current.send("play"));
    await answer(0, REFUSED);
    expect(hook.current.problem).toBe("the simulator answered 409: it plays");
    act(() => hook.current.send("pause"));
    await answer(1, DONE);

    expect(sent).toEqual(["climate_box play", "climate_box pause"]);
    expect(hook.current.problem).toBeNull();
  });

  it("keep an older command's answer from overwriting the latest's", async () => {
    const { send, answer } = answering();
    const hook = renderHook((id: string | null) => useLiveCommands(id, send), "climate_box");
    act(() => hook.current.send("play"));
    act(() => hook.current.send("pause"));

    await answer(1, REFUSED);
    await answer(0, DONE);

    expect(hook.current.problem).toBe("the simulator answered 409: it plays");
  });

  it("drop an answer that arrives after the scenario changed, even back again", async () => {
    const { send, answer } = answering();
    const hook = renderHook((id: string | null) => useLiveCommands(id, send), "climate_box");
    act(() => hook.current.send("play"));

    hook.rerender("gh_001");
    hook.rerender("climate_box");
    await answer(0, REFUSED);

    expect(hook.current.problem).toBeNull();
  });

  it("are forgotten when asked, and send nothing without a scenario", async () => {
    const { send, sent, answer } = answering();
    const hook = renderHook((id: string | null) => useLiveCommands(id, send), "climate_box");
    act(() => hook.current.send("play"));

    act(() => hook.current.forget());
    await answer(0, REFUSED);
    expect(hook.current.problem).toBeNull();
    hook.rerender(null);
    act(() => hook.current.send("play"));

    expect(sent).toEqual(["climate_box play"]);
  });
});
