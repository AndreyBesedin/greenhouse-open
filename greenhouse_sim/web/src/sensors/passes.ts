/**
 * A camera's depth and instance passes, as the viewer reads them back from
 * the GPU (`renderPasses`). Each pass is drawn at the camera's own size, one
 * pixel per pixel of its picture, into RGBA bytes:
 *
 * - **instance:** a pixel's red, green and blue hold, in base 256, one more
 *   than the index of the entity it shows; zero is nothing;
 * - **depth:** they hold, in base 256, how far ahead of the camera the
 *   surface it shows lies, along the way the camera looks, in millimetres.
 *   Its alpha is zero where nothing is.
 *
 * WebGL reads rows from the bottom of the picture up; a pass here is read
 * from its top row down, as the picture's pixels (u, v) are counted.
 */

// One byte's worth of values.
const BYTE = 256;
const BYTE_MAX = 255;
const CHANNELS = 4;
const ALPHA = 3;
// Depth is encoded in millimetres.
const DEPTH_STEPS_PER_M = 1000;
export const DEPTH_STEP_M = 1 / DEPTH_STEPS_PER_M;

/** An entity in the camera's view, its index in the passes, and how many of
 * its picture's pixels it covers. */
export interface InView {
  entityId: string;
  index: number;
  pixels: number;
}

export interface CameraPasses {
  width: number;
  height: number;
  /** Each pixel's entity, as an index into `entityIds`, or −1 for nothing,
   * row by row from the top. */
  instance: Int32Array;
  entityIds: readonly string[];
  /** Each pixel's depth ahead of the camera, in metres, or NaN for nothing. */
  depth: Float64Array;
  /** The entities in view, those covering the most pixels first. */
  inView: InView[];
}

function code(bytes: Uint8Array, offset: number): number {
  return (
    (bytes[offset] ?? 0) + (bytes[offset + 1] ?? 0) * BYTE + (bytes[offset + 2] ?? 0) * BYTE * BYTE
  );
}

/** The offset of pixel (u, v), counted from the top, in bytes read from the
 * bottom row up. */
function offsetOf(u: number, v: number, width: number, height: number): number {
  return ((height - 1 - v) * width + u) * CHANNELS;
}

/** The passes as read back from the GPU, `entityIds` in the instance pass's
 * order. */
export function decodePasses(
  instanceBytes: Uint8Array,
  depthBytes: Uint8Array,
  width: number,
  height: number,
  entityIds: readonly string[],
): CameraPasses {
  const instance = new Int32Array(width * height);
  const depth = new Float64Array(width * height);
  const pixels = new Array<number>(entityIds.length).fill(0);
  for (let v = 0; v < height; v += 1) {
    for (let u = 0; u < width; u += 1) {
      const pixel = v * width + u;
      const offset = offsetOf(u, v, width, height);
      const index = code(instanceBytes, offset) - 1;
      const known = index >= 0 && index < entityIds.length;
      instance[pixel] = known ? index : -1;
      if (known) {
        pixels[index] = (pixels[index] ?? 0) + 1;
      }
      depth[pixel] =
        (depthBytes[offset + ALPHA] ?? 0) > 0
          ? code(depthBytes, offset) / DEPTH_STEPS_PER_M
          : Number.NaN;
    }
  }
  const inView = entityIds
    .map((entityId, index) => ({ entityId, index, pixels: pixels[index] ?? 0 }))
    .filter((entry) => entry.pixels > 0)
    .sort((a, b) => b.pixels - a.pixels || a.entityId.localeCompare(b.entityId));
  return { width, height, instance, entityIds, depth, inView };
}

/** What the passes hold at pixel (u, v): the entity shown there and its
 * depth, or nulls where nothing is or beyond the picture. */
export function passesAt(
  passes: CameraPasses,
  u: number,
  v: number,
): { entityId: string | null; depth: number | null } {
  if (u < 0 || v < 0 || u >= passes.width || v >= passes.height) {
    return { entityId: null, depth: null };
  }
  const pixel = v * passes.width + u;
  const index = passes.instance[pixel] ?? -1;
  const depth = passes.depth[pixel] ?? Number.NaN;
  return {
    entityId: index < 0 ? null : (passes.entityIds[index] ?? null),
    depth: Number.isNaN(depth) ? null : depth,
  };
}

/** The nearest and the farthest depth in view, in metres, or null if
 * nothing is. */
export function depthRange(passes: CameraPasses): { nearest: number; farthest: number } | null {
  let nearest = Number.POSITIVE_INFINITY;
  let farthest = Number.NEGATIVE_INFINITY;
  for (const depth of passes.depth) {
    if (!Number.isNaN(depth)) {
      nearest = Math.min(nearest, depth);
      farthest = Math.max(farthest, depth);
    }
  }
  return nearest > farthest ? null : { nearest, farthest };
}

/** The depth pass as a picture: white at the nearest depth in view, black at
 * the farthest, and black where nothing is. Grey falls with the logarithm of
 * depth, so that what is near keeps its detail when something far, such as
 * the ground beyond the glass, is in view too. */
export function depthPicture(passes: CameraPasses): Uint8ClampedArray<ArrayBuffer> {
  const picture = new Uint8ClampedArray(passes.width * passes.height * CHANNELS);
  const range = depthRange(passes);
  const nearest = range?.nearest ?? 1;
  const spread = range === null ? 0 : Math.log(range.farthest / range.nearest);
  passes.depth.forEach((depth, pixel) => {
    const near = Number.isNaN(depth) ? 0 : spread > 0 ? 1 - Math.log(depth / nearest) / spread : 1;
    const grey = Math.round(near * BYTE_MAX);
    picture.set([grey, grey, grey, BYTE_MAX], pixel * CHANNELS);
  });
  return picture;
}

// Successive entities' hues are this far apart, in turns: the golden angle,
// so that no two neighbours in the list look alike.
const HUE_STEP = 0.381966;
const SATURATION = 0.65;
const LIGHTNESS = 0.55;
const HUE_SECTORS = 6;
const HALF = 0.5;

/** A colour of hue `hue`, in turns, at the pass's saturation and lightness,
 * as bytes. */
function hueColor(hue: number): [number, number, number] {
  const chroma = (1 - Math.abs(2 * LIGHTNESS - 1)) * SATURATION;
  const sector = (hue % 1) * HUE_SECTORS;
  const second = chroma * (1 - Math.abs((sector % 2) - 1));
  const base = LIGHTNESS - chroma * HALF;
  const sectors: [number, number, number][] = [
    [chroma, second, 0],
    [second, chroma, 0],
    [0, chroma, second],
    [0, second, chroma],
    [second, 0, chroma],
    [chroma, 0, second],
  ];
  const [r, g, b] = sectors[Math.floor(sector)] ?? [0, 0, 0];
  return [
    Math.round((r + base) * BYTE_MAX),
    Math.round((g + base) * BYTE_MAX),
    Math.round((b + base) * BYTE_MAX),
  ];
}

/** The colour the instance picture shows the `index`th entity in. */
export function instanceColor(index: number): [number, number, number] {
  return hueColor(index * HUE_STEP);
}

/** The instance pass as a picture: each entity in a colour of its own, and
 * black where nothing is. */
export function instancePicture(passes: CameraPasses): Uint8ClampedArray<ArrayBuffer> {
  const picture = new Uint8ClampedArray(passes.width * passes.height * CHANNELS);
  passes.instance.forEach((index, pixel) => {
    const [r, g, b] = index < 0 ? [0, 0, 0] : instanceColor(index);
    picture.set([r, g, b, BYTE_MAX], pixel * CHANNELS);
  });
  return picture;
}
