// @vitest-environment jsdom
import { afterEach, describe, expect, it } from "vitest";

import { type CameraPose, framing } from "../camera";
import { type Rendered, render } from "../testing/render";
import type { Pending } from "../useLoad";
import type { SceneState } from "./sceneLoad";
import { useOpeningFrame } from "./useFollowFraming";

const SIZE = { x: 12, y: 6.4, z: 4.8 };
const BASE = { x: 6, y: 3.2, z: 0 };

/** A scene whose house stands in the box given. */
function sceneOf(size = SIZE): SceneState {
  return {
    status: "loaded",
    snapshot: {
      entities: [
        {
          kind: "GREENHOUSE_BOUNDS",
          transform: { position: BASE },
          shape: { shape: "box", size_x: size.x, size_y: size.y, size_z: size.z },
        },
      ],
    },
  } as unknown as SceneState;
}

const LOADING: Pending = { status: "loading" };

interface Asked {
  scenarioId?: string | null;
  latestScene?: SceneState | Pending;
  ownCamera?: boolean;
  presetChosen?: boolean;
}

describe("where the camera starts over a scenario opened to look at", () => {
  let rendered: Rendered | undefined;
  afterEach(() => rendered?.unmount());

  let pose: CameraPose | null = null;
  function Probe({
    scenarioId = "box",
    latestScene = sceneOf(),
    ownCamera = false,
    presetChosen = false,
  }: Asked) {
    pose = useOpeningFrame({ scenarioId, latestScene, ownCamera, presetChosen });
    return null;
  }
  const framedHouse = () => framing(BASE, SIZE, window.innerWidth / window.innerHeight);

  it("is its house, framed, once the scene says where the house stands", () => {
    rendered = render(<Probe latestScene={LOADING} />);
    expect(pose).toBeNull();

    rendered.rerender(<Probe />);
    expect(pose).toEqual(framedHouse());
  });

  it("stays the same pose as the scene changes, so that the camera is not moved again", () => {
    rendered = render(<Probe />);
    const first = pose;

    rendered.rerender(<Probe latestScene={sceneOf({ x: 40, y: 40, z: 9 })} />);

    expect(pose).toBe(first);
  });

  it("is nothing when the address or a followed run gives the camera its pose", () => {
    rendered = render(<Probe ownCamera />);
    expect(pose).toBeNull();
  });

  it("is nothing once a preset was chosen before the scene came", () => {
    rendered = render(<Probe presetChosen latestScene={LOADING} />);
    rendered.rerender(<Probe presetChosen />);
    expect(pose).toBeNull();
  });

  it("frames another scenario's house when the view goes to one", () => {
    rendered = render(<Probe />);
    const first = pose;

    rendered.rerender(<Probe scenarioId="other" latestScene={sceneOf({ x: 40, y: 40, z: 9 })} />);

    expect(pose).not.toBeNull();
    expect(pose).not.toEqual(first);
  });

  it("is nothing for a view of no scenario", () => {
    rendered = render(<Probe scenarioId={null} />);
    expect(pose).toBeNull();
  });
});
