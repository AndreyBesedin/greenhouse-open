import { contractReader, loadJson } from "../loadJson";
import { runParameters, type ScenarioRun, scenarioUrl } from "../scene/run";
import { atItsCropsDay } from "./crop";
import { AREA_CROP_SCHEMA } from "./generated/areaCropSchema";
import type { AreaBasis, AreaCropCourse as ServedCourse } from "./generated/areaCropTypes";

/** How a scenario whose model grows its crop by area says so
 * (`ScenarioSummary.crop_grown_by`): it has no plants, and is charted, not
 * drawn (decision 0083). */
export const GROWN_BY_AREA = "area";

/** One quantity of a crop grown by area through a run's days, at each day's
 * start: the house's, its rows' mean weighted by their areas, and the
 * rows' least and most, each in the model's own unit. */
export interface AreaQuantityCourse {
  key: string;
  name: string;
  unit: string;
  house: number[];
  least: number[];
  most: number[];
}

/** A run's crop grown by area through the days ended by a moment (`GET
 * /api/scenarios/{id}/area_crop`): its model, the area its quantities are
 * per m² of, its days from 0, how many rows grow it, and each quantity it
 * charts, in the model's order. */
export interface AreaCropCourse {
  model: string;
  basis: AreaBasis;
  days: number[];
  rows: number;
  quantities: AreaQuantityCourse[];
}

export type AreaCropState =
  | { status: "none" }
  | { status: "loading" }
  | { status: "unavailable"; reason: string }
  | { status: "loaded"; course: AreaCropCourse };

/** Where a scenario's crop grown by area through a run is published, asked
 * for as its crop is: at the start of the moment's day, so that every
 * moment of a day asks for the same course. */
export function areaCropUrl(run: ScenarioRun): string {
  return scenarioUrl(run.scenarioId, "area_crop", runParameters(atItsCropsDay(run)));
}

const UNEXPECTED = "the crop's course is not what the viewer expects";
const readCourse = contractReader<ServedCourse>(AREA_CROP_SCHEMA, UNEXPECTED);

/** A crop's course, checked rather than trusted: rows that grow it, and, for
 * each quantity charted, a value on each of its days for the house and for
 * every row. */
export function parseAreaCrop(body: unknown): AreaCropCourse {
  const { model, basis, days, scopes, house, quantities } = readCourse(body);
  const daily = (values: readonly number[] | undefined): values is number[] =>
    values !== undefined && values.length === days.length;
  const charted = quantities.map(({ key, name, unit }) => {
    const ownHouse = house[key];
    const rows = scopes.map((scope) => scope.values[key]);
    if (!daily(ownHouse) || !rows.every(daily) || rows.length === 0) {
      throw new Error(UNEXPECTED);
    }
    const onEachDay = days.map((_, day) => rows.map((values) => values[day] ?? Number.NaN));
    return {
      key,
      name,
      unit,
      house: ownHouse,
      least: onEachDay.map((values) => Math.min(...values)),
      most: onEachDay.map((values) => Math.max(...values)),
    };
  });
  return { model, basis, days, rows: scopes.length, quantities: charted };
}

/** Fetches a crop's course through a run; every failure becomes
 * `unavailable`. */
export async function loadAreaCrop(
  url: string,
  fetchFn: typeof fetch = fetch,
): Promise<AreaCropState> {
  const answer = await loadJson(url, parseAreaCrop, fetchFn);
  return answer.status === "loaded" ? { status: "loaded", course: answer.value } : answer;
}
