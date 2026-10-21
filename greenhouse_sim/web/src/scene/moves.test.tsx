import { readFileSync } from "node:fs";

import { renderToStaticMarkup } from "react-dom/server";
import { Quaternion, Vector3 } from "three";
import { describe, expect, it } from "vitest";

import { entityBounds } from "../debug/overlays";

import { SceneStatus } from "../SceneStatus";
import { present } from "../testing/present";
import type { SceneEntity, SceneSnapshot } from "./generated/snapshotTypes";
import {
  baseLayout,
  keptInside,
  layoutText,
  layoutWith,
  movableItem,
  movedBy,
  movesBetween,
  movesIn,
  putBack,
  sameLayout,
  shifted,
  snapped,
} from "./moves";

// The climate box, 12 m by 6.4 m: its heater in the back right corner, 0.6
// m by 0.8 m, its base at (11.2, 0.7); its sensors; its weather station
// outside the front wall.
const EXAMPLE: SceneSnapshot = JSON.parse(
  readFileSync(new URL("../../public/scenes/example.json", import.meta.url), "utf8"),
);

function entity(id: string): SceneEntity {
  return present(
    EXAMPLE.entities.find((each) => each.entity_id === `climate_box_${id}`),
    `the example's ${id}`,
  );
}

const HOUSE = entity("bounds");
const HEATER = entity("heater");

describe("moves written in a layout's name", () => {
  it("are read by item, from the layout they move", () => {
    expect(baseLayout(undefined)).toBeUndefined();
    expect(baseLayout("benches")).toBe("benches");
    expect(baseLayout("default~heater:-1:0.5")).toBe("default");
    expect(movesIn("benches")).toEqual({});
    expect(movesIn("default~heater:-1:0.5,fan:0:2")).toEqual({
      heater: { dx: -1, dy: 0.5 },
      fan: { dx: 0, dy: 2 },
    });
    // None that is not written as item:dx:dy.
    expect(movesIn("default~heater:1,fan:x:0,co2:1:2:3,par:1:1")).toEqual({
      par: { dx: 1, dy: 1 },
    });
  });

  it("add up item by item, to the snap, and a move back is none", () => {
    const once = movedBy(undefined, "default", "heater", { dx: -0.96, dy: 0.04 });
    expect(once).toBe("default~heater:-1:0");
    const twice = movedBy(once, "default", "fan", { dx: 0.3, dy: 0 });
    expect(twice).toBe("default~fan:0.3:0,heater:-1:0");
    const again = movedBy(twice, "default", "heater", { dx: -0.1, dy: 0.5 });
    expect(again).toBe("default~fan:0.3:0,heater:-1.1:0.5");
    // Back where its layout places it, the fan has no move, and with none
    // left the layout is the scenario's own.
    expect(movedBy(again, "default", "fan", { dx: -0.3, dy: 0 })).toBe("default~heater:-1.1:0.5");
    expect(movedBy("default~fan:0.3:0", "default", "fan", { dx: -0.3, dy: 0 })).toBeUndefined();
    // Another layout's moves keep its name.
    expect(movedBy("benches", "default", "co2", { dx: 0.2, dy: 0 })).toBe("benches~co2:0.2:0");
    expect(putBack("benches~co2:0.2:0,par:1:0", "default", "co2")).toBe("benches~par:1:0");
    expect(putBack("benches~co2:0.2:0", "default", "co2")).toBe("benches");
  });

  it("are written in an address with the marks between them as they are", () => {
    expect(layoutText("default~heater:-1:0.5,fan:0:2")).toBe("default~heater:-1:0.5,fan:0:2");
    expect(layoutText("my layout")).toBe("my%20layout");
    expect(layoutWith("default", "default", { a: { dx: -0.04, dy: 0 } })).toBe("default~a:0:0");
  });

  it("name one layout however they are written, as the simulator knows it", () => {
    // As the viewer writes it, and as a run played back says it (#271).
    expect(sameLayout("default~heater:-1:0.5", "default~heater:-1.0:0.5", "default")).toBe(true);
    expect(
      sameLayout("default~fan:0:2,heater:-1:0", "default~heater:-1:0,fan:0:2", "default"),
    ).toBe(true);
    expect(sameLayout(undefined, "default", "default")).toBe(true);
    expect(sameLayout("default~heater:0:0", undefined, "default")).toBe(true);
    expect(sameLayout("default~heater:-1:0.5", "default~heater:-1:0.4", "default")).toBe(false);
    expect(sameLayout("default~heater:-1:0.5", "default", "default")).toBe(false);
    expect(sameLayout("benches~heater:-1:0.5", "default~heater:-1:0.5", "default")).toBe(false);
  });

  it("are drawn, in a session, as far as one layout moves each item from another", () => {
    // A session from a layout that moves the heater: it moves the heater on,
    // puts the fan back, and moves a sensor.
    expect(
      movesBetween("default~fan:0:2,heater:-1:0", "default~co2:0.3:0,heater:-1.5:0.5"),
    ).toEqual({
      co2: { dx: 0.3, dy: 0 },
      fan: { dx: 0, dy: -2 },
      heater: { dx: -0.5, dy: 0.5 },
    });
    expect(movesBetween("default~heater:-1:0", "default~heater:-1.0:0")).toEqual({});
    expect(movesBetween(undefined, undefined)).toEqual({});
  });

  it("move what is equipment or a sensor, and nothing else", () => {
    expect(movableItem(HEATER)).toBe("heater");
    expect(movableItem(entity("fan"))).toBe("fan");
    expect(movableItem(entity("temperature_front"))).toBe("temperature_front");
    expect(movableItem(entity("front_camera"))).toBe("front_camera");
    expect(movableItem(HOUSE)).toBeNull();
    expect(movableItem(entity("plant_001"))).toBeNull();
  });
});

describe("a drag's move", () => {
  it("snaps to 10 cm, never to minus nought", () => {
    expect(snapped({ dx: 0.149, dy: -0.04 })).toEqual({ dx: 0.1, dy: 0 });
    expect(Object.is(snapped({ dx: -0.01, dy: 0 }).dx, 0)).toBe(true);
  });

  it("keeps an item inside the house, its box stopping a step short of the walls", () => {
    // The heater's box reaches from 10.9 to 11.5 m along x and 0.3 to 1.1 m
    // along y; the house's walls stand at 0 and 12 m, 0 and 6.4 m. It never
    // touches one, where a rounding error would put it outside.
    expect(keptInside({ dx: 3, dy: -2 }, HEATER, HOUSE)).toEqual({ dx: 0.4, dy: -0.2 });
    expect(keptInside({ dx: -20, dy: 20 }, HEATER, HOUSE)).toEqual({ dx: -10.8, dy: 5.2 });
    expect(keptInside({ dx: -1.03, dy: 0.47 }, HEATER, HOUSE)).toEqual({ dx: -1, dy: 0.5 });
    // Without the house's bounds, only snapped.
    expect(keptInside({ dx: 3, dy: -2 }, HEATER, null)).toEqual({ dx: 3, dy: -2 });
  });

  it("holds a weather station's instrument nowhere: it stands outside", () => {
    const station = entity("station_temperature");
    expect(keptInside({ dx: -2, dy: 1 }, station, HOUSE)).toEqual({ dx: -2, dy: 1 });
  });

  it("is held by a turned house's own walls", () => {
    // The same house a quarter turn anticlockwise about its centre, and the
    // heater with it: along the world's y, the heater can go 0.4 m.
    const quarter = { w: Math.SQRT1_2, x: 0, y: 0, z: Math.SQRT1_2 };
    const house = { ...HOUSE, transform: { ...HOUSE.transform, rotation: quarter } };
    // Its corner nearest the house's back right corner, turned.
    const heater = {
      ...HEATER,
      transform: { position: { x: 6.5, y: 8.4, z: 0 }, rotation: quarter },
    };
    expect(keptInside({ dx: 0, dy: 3 }, heater, house)).toEqual({ dx: 0, dy: 0.4 });
  });

  it("keeps to the snap and inside a house turned across its steps", () => {
    // The house turned a twelfth of a turn about its centre, the heater with
    // it: its walls run across the world's 10 cm steps.
    const turn = new Quaternion().setFromAxisAngle(new Vector3(0, 0, 1), Math.PI / 6);
    const centre = new Vector3(6, 3.2, 0);
    const turned = (entity: SceneEntity): SceneEntity => {
      const { position, rotation } = entity.transform;
      const at = new Vector3(position.x, position.y, position.z)
        .sub(centre)
        .applyQuaternion(turn)
        .add(centre);
      const own = new Quaternion(rotation.x, rotation.y, rotation.z, rotation.w).premultiply(turn);
      return {
        ...entity,
        transform: {
          position: { x: at.x, y: at.y, z: at.z },
          rotation: { w: own.w, x: own.x, y: own.y, z: own.z },
        },
      };
    };
    const house = turned(HOUSE);
    const heater = turned(HEATER);
    const back = turn.clone().invert();
    // How far inside the house's walls the heater's box would stand, at
    // the least, in the house's own axes.
    const clearance = (by: { dx: number; dy: number }) => {
      const { min, max } = entityBounds(shifted(heater, by));
      const corners = [min.x, max.x].flatMap((x) =>
        [min.y, max.y].map((y) => new Vector3(x, y, 0).sub(centre).applyQuaternion(back)),
      );
      return Math.min(
        ...corners.flatMap((corner) => [6 - Math.abs(corner.x), 3.2 - Math.abs(corner.y)]),
      );
    };
    const towards = Array.from({ length: 24 }, (_, n) => (n * Math.PI) / 12);
    for (const angle of towards) {
      for (const metres of [0.37, 2.5, 20]) {
        const by = keptInside(
          { dx: metres * Math.cos(angle), dy: metres * Math.sin(angle) },
          heater,
          house,
        );
        expect(snapped(by)).toEqual(by);
        expect(clearance(by)).toBeGreaterThan(0);
      }
    }
    // Dragged far into its corner, the heater stops near the walls.
    const cornered = keptInside({ dx: 0, dy: 20 }, heater, house);
    expect(clearance(cornered)).toBeLessThan(0.2);
  });

  it("draws an item where it would stand, its height kept", () => {
    const moved = shifted(HEATER, { dx: -1, dy: 0.5 }).transform.position;
    expect(moved).toEqual({ x: 10.2, y: 1.2, z: 0 });
    expect(HEATER.transform.position).toEqual({ x: 11.2, y: 0.7, z: 0 });
  });
});

describe("the scene status of a moved layout", () => {
  it("names the layout moved from and what is moved", () => {
    const said = (layout: string) =>
      renderToStaticMarkup(
        <SceneStatus
          source={{ kind: "scenario", scenarioId: "climate_box", layout }}
          state={{ status: "loading" }}
        />,
      );
    expect(said("default~heater:-1:0,co2:0:1")).toContain(
      "Loading the scenario climate_box, co2, heater moved, before day one…",
    );
    expect(said("benches~co2:0:1")).toContain(
      "Loading the scenario climate_box with its benches layout, co2 moved, before day one…",
    );
  });
});
