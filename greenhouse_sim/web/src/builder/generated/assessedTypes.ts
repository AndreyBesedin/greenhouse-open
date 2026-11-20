// Generated from greenhouse_sim/services/builder.schema.json by `npm run generate`.
// Do not edit: change the simulator's types and regenerate.

export type OpeningKind = "door" | "roof_vent" | "side_vent";
/**
 * What a fixture, or a part of the envelope, is made of.
 */
export type Material = "steel" | "aluminium" | "plastic" | "concrete" | "substrate";
/**
 * What a fixture, or a part of the envelope, is made of.
 */
export type Material1 = "steel" | "aluminium" | "plastic" | "concrete" | "substrate";
export type Primitive =
  | BoxPrimitive
  | CylinderPrimitive
  | PipePrimitive
  | PipeRunPrimitive
  | RailPrimitive
  | TrayPrimitive
  | WalkwayPrimitive;
/**
 * What a fixture stands in the way of.
 */
export type Obstruction = "movement" | "airflow" | "light";
/**
 * What a fixture is, for every consumer of its geometry.
 */
export type FixtureKind = "crop_gutter" | "bench" | "slab" | "walkway" | "rail" | "pipe" | "wire" | "obstacle";
/**
 * What a fixture is, for every consumer of its geometry.
 */
export type FixtureKind1 = "crop_gutter" | "bench" | "slab" | "walkway" | "rail" | "pipe" | "wire" | "obstacle";
/**
 * What a fixture is, for every consumer of its geometry.
 */
export type FixtureKind2 = "crop_gutter" | "bench" | "slab" | "walkway" | "rail" | "pipe" | "wire" | "obstacle";
/**
 * What a fixture is, for every consumer of its geometry.
 */
export type FixtureKind3 = "crop_gutter" | "bench" | "slab" | "walkway" | "rail" | "pipe" | "wire" | "obstacle";
/**
 * What a fixture is, for every consumer of its geometry.
 */
export type FixtureKind4 = "crop_gutter" | "bench" | "slab" | "walkway" | "rail" | "pipe" | "wire" | "obstacle";
/**
 * What a fixture is, for every consumer of its geometry.
 */
export type FixtureKind5 = "crop_gutter" | "bench" | "slab" | "walkway" | "rail" | "pipe" | "wire" | "obstacle";
/**
 * What a fixture is, for every consumer of its geometry.
 */
export type FixtureKind6 = "crop_gutter" | "bench" | "slab" | "walkway" | "rail" | "pipe" | "wire" | "obstacle";
/**
 * What an area of the floor is kept for.
 */
export type ZoneKind = "service" | "keep_out";
export type Equipment = Fan | Heater | Dehumidifier;
export type Sensor = PointSensor | Camera;
export type PointKind =
  | "temperature"
  | "humidity"
  | "co2"
  | "air_speed"
  | "par"
  | "outside_temperature"
  | "outside_humidity"
  | "wind_speed"
  | "wind_direction"
  | "barometric_pressure";
/**
 * How a scenario's run grows its crop: plant by plant, by the simple
 * daily model (`greenhouse_sim.core.simple_crop`) or organ by organ
 * (`greenhouse_sim.core.crop`); or by area, by Reduced-State TOMGRO
 * (`greenhouse_sim.core.tomgro_crop`) or Vanthoor's model as Katzin
 * simplified it (`greenhouse_sim.core.vanthoor_crop`, decision 0060).
 */
export type CropModel = "simple" | "organ" | "reduced_tomgro" | "vanthoor_katzin";
export type CoverChoice = CoverMaterialName | CoverMaterial;
/**
 * A cover's sheet the catalogue names.
 */
export type CoverMaterialName = "single_glass";
export type WallBoundary = OnTheOutside | OnASpace | OnNothing;
export type Temperature = number;
export type LayerChoice = LayerMaterialName | LayerMaterial;
/**
 * A floor's or the soil's layer the catalogue names.
 */
export type LayerMaterialName = "concrete" | "soil";
/**
 * @minItems 1
 */
export type Screens = [Screen, ...Screen[]];
/**
 * What a screen drawn across the house is for.
 */
export type ScreenKind = "thermal" | "shading" | "blackout";
export type ScreenChoice = ScreenClothName | ScreenCloth;
/**
 * A screen's cloth the catalogue names.
 */
export type ScreenClothName = "thermal_screen_cloth";
/**
 * @minItems 1
 */
export type PipeNetworks = [PipeNetwork, ...PipeNetwork[]];
/**
 * Where a network of heating pipes runs.
 */
export type PipeKind = "rail" | "grow" | "perimeter";

/**
 * An installation, the format a file of it is written in, and what
 * stops it running, or what it lacks; and, if it is a draft's, the draft
 * and the revision it is (`services.drafts`). One answer for both, so that
 * the contract published for it describes an installation once.
 */
export interface Assessed {
  schema_version: number;
  installation: Installation;
  findings: Finding[];
  draft?: DraftRevision | null;
}
/**
 * A greenhouse as authored: no weather, period, control or policy,
 * which are a scenario's.
 */
export interface Installation {
  /**
   * Letters, digits, '_', '.' and '-' only: the API's parameters write it between ':' and ','.
   */
  installation_id: string;
  name: string;
  envelope: Envelope;
  layout: Layout;
  row_crops: RowCrop[];
  components?: HouseComponents | null;
}
/**
 * A greenhouse's envelope, in metres, no larger than any greenhouse.
 */
export interface Envelope {
  length: number;
  width: number;
  eave_height: number;
  ridge_height: number;
  spans: number;
  bays: number;
  inner_posts?: number[] | null;
  openings: Opening[];
  origin: Transform;
}
/**
 * A door or vent: a rectangle on its host surface, centred at `centre` in
 * the host's own x-y plane, `width` along the host's x and `height` along
 * its y, open by `opening`, from 0 (closed) to 1.
 */
export interface Opening {
  /**
   * Letters, digits, '_', '.' and '-' only: the API's parameters write it between ':' and ','.
   */
  opening_id: string;
  kind: OpeningKind;
  surface_id: string;
  centre: Point2;
  width: number;
  height: number;
  opening: number;
  largest_angle: number;
}
/**
 * A point in a shape's own x-y plane.
 */
export interface Point2 {
  x: number;
  y: number;
}
/**
 * Places a shape's own frame in the world: rotate, then translate.
 */
export interface Transform {
  position: Vector3;
  rotation: Quaternion;
}
export interface Vector3 {
  x: number;
  y: number;
  z: number;
}
/**
 * A rotation as a unit quaternion; the default is no rotation.
 */
export interface Quaternion {
  w: number;
  x: number;
  y: number;
  z: number;
}
/**
 * What stands inside a greenhouse, in metres, in its frame.
 */
export interface Layout {
  crop_rows: CropRows | null;
  placed: Primitive[];
  zones: Zone[];
  equipment: Equipment[];
  sensors: Sensor[];
}
/**
 * Parallel rows of planting positions, in metres and radians.
 */
export interface CropRows {
  origin: Point2;
  heading: number;
  rows: number;
  positions_per_row: number;
  plant_pitch: number;
  row_spacing: number;
  pair_gap: number | null;
  support: RowSupport | null;
  rails: RowRails | null;
  wires: CropWires | null;
}
/**
 * What carries each crop row: a top along the row, its upper surface
 * `height` above the floor, `width` across and `depth` thick, reaching
 * `overhang` beyond the row's first and last positions, its centre line
 * `offset` to the left of the row's. Legs stand under it at most
 * `leg_spacing` apart, from the floor to its underside; without, it hangs
 * from the structure above.
 */
export interface RowSupport {
  kind: "crop_gutter" | "bench";
  height: number;
  width: number;
  depth: number;
  overhang: number;
  offset: number;
  material: Material | null;
  leg_spacing: number | null;
  leg_radius: number;
  slab: Slab | null;
}
/**
 * Substrate laid along the top of a row's support.
 */
export interface Slab {
  width: number;
  height: number;
  material: Material1;
}
/**
 * A pipe rail in each path between neighbouring rows wide enough for it:
 * two tubes `gauge` apart from axis to axis, their axes `height` above the
 * floor, along the rows. They are often the heating pipes too.
 */
export interface RowRails {
  gauge: number;
  tube_radius: number;
  height: number;
  material: Material | null;
}
/**
 * A crop wire above each run of a row's positions, `height` above the
 * floor, which the plants are trained up to; or, `offset` to either side
 * of the row, a pair of them, a high-wire double row's, which its plants
 * are trained to by turns (`greenhouse_sim.world.training`).
 */
export interface CropWires {
  height: number;
  radius: number;
  offset: number;
}
/**
 * A box standing on the floor or anything else: its base centred on
 * `base`, turned about the vertical by `heading` radians from the
 * greenhouse's x.
 */
export interface BoxPrimitive {
  fixture_id: string;
  material: Material | null;
  obstructs: Obstruction[] | null;
  primitive: "box";
  kind: FixtureKind;
  base: Vector3;
  size_x: number;
  size_y: number;
  size_z: number;
  heading: number;
}
/**
 * An upright cylinder, its base centred on `base`.
 */
export interface CylinderPrimitive {
  fixture_id: string;
  material: Material | null;
  obstructs: Obstruction[] | null;
  primitive: "cylinder";
  kind: FixtureKind1;
  base: Vector3;
  radius: number;
  height: number;
}
/**
 * A straight pipe, its axis from `start` to `end`.
 */
export interface PipePrimitive {
  fixture_id: string;
  material: Material | null;
  obstructs: Obstruction[] | null;
  primitive: "pipe";
  kind: FixtureKind2;
  start: Vector3;
  end: Vector3;
  radius: number;
}
/**
 * Pipes repeated in parallel, such as heating pipes stacked along a wall:
 * the first from `start` to `end`, each next one `step` further on, `count`
 * in all. Each is its own multiple of the step from the first, and is called
 * `<fixture_id>_<n>`, from 1.
 */
export interface PipeRunPrimitive {
  fixture_id: string;
  material: Material | null;
  obstructs: Obstruction[] | null;
  primitive: "pipe_run";
  kind: FixtureKind3;
  start: Vector3;
  end: Vector3;
  radius: number;
  count: number;
  step: Vector3;
}
/**
 * A rail of two parallel tubes, `gauge` apart from axis to axis, either
 * side of its centre line from `start` to `end`. Its tubes are
 * `<fixture_id>_right` and `<fixture_id>_left`, as seen looking along it.
 */
export interface RailPrimitive {
  fixture_id: string;
  material: Material | null;
  obstructs: Obstruction[] | null;
  primitive: "rail";
  kind: FixtureKind4;
  start: Vector3;
  end: Vector3;
  gauge: number;
  tube_radius: number;
}
/**
 * An open tray, such as a crop gutter: `width` across and `depth` deep,
 * its bottom's centre line from `start` to `end`. It may slope, as gutters
 * do to drain; it stays level across.
 */
export interface TrayPrimitive {
  fixture_id: string;
  material: Material | null;
  obstructs: Obstruction[] | null;
  primitive: "tray";
  kind: FixtureKind5;
  start: Vector3;
  end: Vector3;
  width: number;
  depth: number;
}
/**
 * A path on the floor, `width` wide, its centre line from `start` to
 * `end`.
 */
export interface WalkwayPrimitive {
  fixture_id: string;
  material: Material | null;
  obstructs: Obstruction[] | null;
  primitive: "walkway";
  kind: FixtureKind6;
  start: Point2;
  end: Point2;
  width: number;
}
/**
 * A service zone or keep-out volume: a strip of the floor, rising
 * `height` above it.
 */
export interface Zone {
  zone_id: string;
  kind: ZoneKind;
  area: Strip;
  height: number;
}
/**
 * A rectangle of the floor: a centre line from `start` to `end`, `width`
 * wide.
 */
export interface Strip {
  start: Point2;
  end: Point2;
  width: number;
}
/**
 * A fan: a rotor of a diameter, centred on `position`, blowing its rated
 * flow of air along its heading.
 */
export interface Fan {
  /**
   * Letters, digits, '_', '.' and '-' only: the API's parameters write it between ':' and ','.
   */
  actuator_id: string;
  heading: number;
  kind: "fan";
  position: Vector3;
  diameter_m: number;
  flow_m3_s: number;
}
/**
 * A unit heater: its rated power, all of it given to the air as heat.
 */
export interface Heater {
  /**
   * Letters, digits, '_', '.' and '-' only: the API's parameters write it between ':' and ','.
   */
  actuator_id: string;
  heading: number;
  base: Vector3;
  size_x: number;
  size_y: number;
  size_z: number;
  kind: "heater";
  power_w: number;
}
/**
 * A dehumidifier: the water it takes out of the air at full power, and
 * the heat it gives the air while it does.
 */
export interface Dehumidifier {
  /**
   * Letters, digits, '_', '.' and '-' only: the API's parameters write it between ':' and ','.
   */
  actuator_id: string;
  heading: number;
  base: Vector3;
  size_x: number;
  size_y: number;
  size_z: number;
  kind: "dehumidifier";
  removal_kg_h: number;
  heat_w: number;
}
/**
 * A sensor reading one quantity of the air at its position, or, outside
 * the house, of the weather.
 */
export interface PointSensor {
  /**
   * Letters, digits, '_', '.' and '-' only: the API's parameters write it between ':' and ','.
   */
  sensor_id: string;
  position: Vector3;
  cadence_s: number;
  kind: PointKind;
  imperfections: Imperfections;
}
/**
 * How a sensor errs, each in its own unit; all nothing for a clean one.
 *
 * Noise is Gaussian, of a standard deviation; a reading is rounded to the
 * quantization step; a fixed bias is added, and a drift that grows linearly
 * with time since the run's start; a sample drops out with a probability;
 * and a reading is delivered a fixed time after its sample.
 */
export interface Imperfections {
  noise_sd: number;
  quantization: number;
  bias: number;
  drift_per_hour: number;
  dropout: number;
  latency_s: number;
}
/**
 * A camera at its position, looking at `target`, with its intrinsics.
 */
export interface Camera {
  /**
   * Letters, digits, '_', '.' and '-' only: the API's parameters write it between ':' and ','.
   */
  sensor_id: string;
  position: Vector3;
  cadence_s: number;
  kind: "camera";
  target: Vector3;
  intrinsics: CameraIntrinsics;
}
/**
 * Pinhole intrinsics of one image stream, in pixels, with the
 * calibration's distortion coefficients exactly as given.
 */
export interface CameraIntrinsics {
  width: number;
  height: number;
  fx: number;
  fy: number;
  ppx: number;
  ppy: number;
  distortion: number[];
}
/**
 * The crop one row grows: its model and its variety. Rows are numbered
 * from 1, as `CropRows` numbers them.
 */
export interface RowCrop {
  row: number;
  crop_model: CropModel;
  variety: string;
}
/**
 * What a house is made of and has beyond its envelope and layout, each
 * left out while undescribed: its cover's materials; what each wall it
 * names faces, the others facing the outside; its floor; the screens
 * drawn across it; and its networks of heating pipes. It describes one at
 * least: a house that describes none has no section of them. Its screens
 * and pipe networks are each named apart, as a command names one.
 */
export interface HouseComponents {
  cover?: Cover | null;
  boundaries?: Boundaries | null;
  floor?: Floor | null;
  screens?: Screens | null;
  pipe_networks?: PipeNetworks | null;
}
/**
 * What the cover is made of: the roof's slopes, all of one material,
 * and each wall it names, of its own; the walls it does not name are of
 * the roof's.
 */
export interface Cover {
  roof: CoverChoice;
  walls: {
    [k: string]: CoverChoice;
  };
}
/**
 * A sheet a cover is made of, given by its properties: what of the
 * sun's beam, falling square to it, and of the sky's diffuse light it
 * passes, what of the shortwave it reflects, what of the longwave it
 * emits and passes, and the heat it conducts and holds.
 */
export interface CoverMaterial {
  /**
   * the share of the sun's beam, falling square to it, that it passes
   */
  shortwave_beam_transmittance: number;
  /**
   * the share of the sky's diffuse light falling on it that it passes
   */
  shortwave_diffuse_transmittance: number;
  /**
   * the share of the shortwave falling on it that it reflects
   */
  shortwave_reflectance: number;
  /**
   * its longwave emissivity: the share of the longwave falling on it that it absorbs
   */
  longwave_emissivity: number;
  /**
   * the share of the longwave falling on it that it passes
   */
  longwave_transmittance: number;
  /**
   * its thickness
   */
  thickness_m: number;
  /**
   * its thermal conductivity
   */
  conductivity_w_m_k: number;
  /**
   * its heat capacity per volume: its density times its specific heat
   */
  volumetric_heat_capacity_j_m3_k: number;
}
export interface Boundaries {
  [k: string]: WallBoundary;
}
/**
 * A wall on the outside air, as a wall is unless it says otherwise.
 */
export interface OnTheOutside {
  faces: "outside";
}
/**
 * A wall on a neighbouring space, a corridor, a headhouse or another
 * house, at its temperature: constant, in °C, or recorded in a file of
 * its own, which names it; one of the two.
 */
export interface OnASpace {
  faces: "space";
  kind: "corridor" | "headhouse" | "house";
  temperature_c?: Temperature | null;
  recording?: string | null;
}
/**
 * A wall no heat crosses.
 */
export interface OnNothing {
  faces: "nothing";
}
/**
 * The floor, from its surface down: the surface's optics, its layers,
 * the first the floor's own and those under it the soil's, and the deep
 * soil's temperature under the last, in °C.
 */
export interface Floor {
  surface: FloorSurface;
  /**
   * @minItems 1
   */
  layers: [FloorLayer, ...FloorLayer[]];
  deep_soil_temperature_c: Temperature;
}
/**
 * The floor's surface, given by its properties: what of the shortwave
 * it reflects, and its longwave emissivity.
 */
export interface FloorSurface {
  /**
   * the share of the shortwave falling on it that it reflects
   */
  shortwave_reflectance: number;
  /**
   * its longwave emissivity: the share of the longwave falling on it that it absorbs
   */
  longwave_emissivity: number;
}
/**
 * A layer of the floor, or of the soil under it: its thickness, in
 * metres, and what it is made of.
 */
export interface FloorLayer {
  thickness_m: number;
  material: LayerChoice;
}
/**
 * What a layer of the floor, or of the soil under it, is made of, given
 * by its properties: the heat it conducts and holds.
 */
export interface LayerMaterial {
  /**
   * its thermal conductivity
   */
  conductivity_w_m_k: number;
  /**
   * its heat capacity per volume: its density times its specific heat
   */
  volumetric_heat_capacity_j_m3_k: number;
}
/**
 * A screen drawn across the house: what it is for, its cloth, the
 * height it is drawn at above the floor, the eaves at most, the floor it
 * covers, the whole house's if it names none, and how far it is drawn as
 * the run starts, from 0 (open) to 1 (closed). Commands and a screen
 * loop are to drive it, as they drive a vent (P24.4).
 */
export interface Screen {
  /**
   * Letters, digits, '_', '.' and '-' only: the API's parameters write it between ':' and ','.
   */
  screen_id: string;
  kind: ScreenKind;
  material: ScreenChoice;
  height_m: number;
  extent?: Strip | null;
  closure: number;
}
/**
 * A cloth a screen is made of, given by its properties: what of the
 * shortwave it passes and reflects, what of the longwave it emits and
 * passes, the air it lets through when it is drawn, and the heat it holds.
 * The air it lets through is Vanthoor's (2011) screen flux coefficient, K
 * in f = K |ΔT|^(2/3): the air through each square metre of it, in m³ a
 * second, for the difference of temperature across it.
 */
export interface ScreenCloth {
  /**
   * the share of the shortwave falling on it that it passes
   */
  shortwave_transmittance: number;
  /**
   * the share of the shortwave falling on it that it reflects
   */
  shortwave_reflectance: number;
  /**
   * its longwave emissivity: the share of the longwave falling on it that it absorbs
   */
  longwave_emissivity: number;
  /**
   * the share of the longwave falling on it that it passes
   */
  longwave_transmittance: number;
  /**
   * its screen flux coefficient K, of f = K |ΔT|^(2/3) through it drawn
   */
  air_permeability_m3_m2_s_k: number;
  /**
   * its thickness
   */
  thickness_m: number;
  /**
   * its heat capacity per volume: its density times its specific heat
   */
  volumetric_heat_capacity_j_m3_k: number;
}
/**
 * A network of heating pipes: where it runs, all its pipes' length end
 * to end, their outer and inner diameters, their height above the floor,
 * the eaves at most, and their longwave emissivity. Its heat leaves them
 * by convection to the air and by radiation to what they see, as the
 * model that heats them works out (P24.8).
 */
export interface PipeNetwork {
  /**
   * Letters, digits, '_', '.' and '-' only: the API's parameters write it between ':' and ','.
   */
  network_id: string;
  kind: PipeKind;
  length_m: number;
  outer_diameter_m: number;
  inner_diameter_m: number;
  height_m: number;
  longwave_emissivity: number;
}
/**
 * Something a draft gets wrong, or lacks: a stable code an editor
 * reads, a message a person reads, and what it concerns, the layout's
 * items by their ids and the crop rows by their numbers, so that an editor
 * can point at them.
 */
export interface Finding {
  severity: "error" | "warning";
  code: string;
  message: string;
  items: string[];
  rows: number[];
}
/**
 * The draft an installation is kept as, and its revision.
 */
export interface DraftRevision {
  draft_id: string;
  revision: number;
  saved_at: string;
}
