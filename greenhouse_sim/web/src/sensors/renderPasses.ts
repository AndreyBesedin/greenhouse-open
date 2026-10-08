import {
  type Camera,
  Color,
  type InstancedMesh,
  type Material,
  type Mesh,
  type Object3D,
  type Scene,
  ShaderMaterial,
  type WebGLRenderer,
  WebGLRenderTarget,
} from "three";

import { type CameraPasses, DEPTH_STEP_M, decodePasses } from "./passes";

const RGBA = 4;
// Where no surface is, both passes hold nothing: zero, with no alpha.
const NOTHING = 0x000000;

// Writes a whole number, below 256³, in base 256 to red, green and blue.
const ENCODE = /* glsl */ `
vec4 encode(float value) {
  float code = floor(value + 0.5);
  return vec4(
    mod(code, 256.0) / 255.0,
    mod(floor(code / 256.0), 256.0) / 255.0,
    floor(code / 65536.0) / 255.0,
    1.0
  );
}
`;

// One more than the index of the entity a fragment is drawn for: an
// instanced batch's entities have successive indices from `first`.
const INSTANCE_VERTEX = /* glsl */ `
#include <common>
uniform float first;
flat varying float vCode;
void main() {
  #include <begin_vertex>
  #include <project_vertex>
  #ifdef USE_INSTANCING
    vCode = first + float(gl_InstanceID) + 1.0;
  #else
    vCode = first + 1.0;
  #endif
}
`;
const INSTANCE_FRAGMENT = /* glsl */ `
flat varying float vCode;
${ENCODE}
void main() {
  gl_FragColor = encode(vCode);
}
`;

// How far ahead of the camera a fragment lies, along the way it looks, in
// steps of `step` metres.
const DEPTH_VERTEX = /* glsl */ `
#include <common>
varying float vAhead;
void main() {
  #include <begin_vertex>
  #include <project_vertex>
  vAhead = -mvPosition.z;
}
`;
const DEPTH_FRAGMENT = /* glsl */ `
uniform float step;
varying float vAhead;
${ENCODE}
void main() {
  gl_FragColor = encode(vAhead / step);
}
`;

/** The entity an object is drawn for, as `SceneView` marks it, or null. */
function entityOf(object: Object3D): string | null {
  for (let at: Object3D | null = object; at !== null; at = at.parent) {
    const entityId: unknown = at.userData.entityId;
    if (typeof entityId === "string") {
      return entityId;
    }
  }
  return null;
}

/** The entities an instanced batch draws, in instance order, as
 * `InstancedShapes` lists them, or null if the mesh is not one. */
function batchOf(mesh: Mesh): string[] | null {
  const batch: unknown = mesh.userData.entityIds;
  if ((mesh as InstancedMesh).isInstancedMesh !== true || !Array.isArray(batch)) {
    return null;
  }
  return batch.slice(0, (mesh as InstancedMesh).count).map(String);
}

/** Whether a mesh is a surface the passes see: drawn opaque, as one
 * material, and not marked see-through, as glazing and zones are. */
function isSurface(mesh: Mesh): mesh is Mesh & { material: Material } {
  const { material } = mesh;
  return !Array.isArray(material) && !material.transparent && mesh.userData.seeThrough !== true;
}

function isDrawnFlat(object: Object3D): boolean {
  const drawn = object as { isLine?: boolean; isPoints?: boolean; isSprite?: boolean };
  return drawn.isLine === true || drawn.isPoints === true || drawn.isSprite === true;
}

/**
 * Draws a camera's depth and instance passes at its own size, `width` by
 * `height`, from the scene as it stands, and reads them back. For each pass,
 * every surface is drawn with a material that writes what the pass holds,
 * and the scene is then put back as it was: the camera's picture never sees
 * them. Lines, points and see-through surfaces are left out, so the passes
 * see through glazing as a click does.
 */
export function renderPasses(
  gl: WebGLRenderer,
  scene: Scene,
  camera: Camera,
  width: number,
  height: number,
): CameraPasses {
  const entityIds: string[] = [];
  const surfaces: { mesh: Mesh; material: Material; instance: ShaderMaterial }[] = [];
  const hidden: Object3D[] = [];
  scene.traverseVisible((object) => {
    const mesh = object as Mesh;
    if (mesh.isMesh !== true) {
      if (isDrawnFlat(object)) {
        hidden.push(object);
      }
      return;
    }
    const drawn = batchOf(mesh) ?? [entityOf(mesh)];
    if (!isSurface(mesh) || drawn.some((entityId) => entityId === null)) {
      hidden.push(mesh);
      return;
    }
    const instance = new ShaderMaterial({
      vertexShader: INSTANCE_VERTEX,
      fragmentShader: INSTANCE_FRAGMENT,
      uniforms: { first: { value: entityIds.length } },
      side: mesh.material.side,
    });
    entityIds.push(...(drawn as string[]));
    surfaces.push({ mesh, material: mesh.material, instance });
  });
  const depths = new Map(
    surfaces.map(({ material }) => [
      material.side,
      new ShaderMaterial({
        vertexShader: DEPTH_VERTEX,
        fragmentShader: DEPTH_FRAGMENT,
        uniforms: { step: { value: DEPTH_STEP_M } },
        side: material.side,
      }),
    ]),
  );

  const background = scene.background;
  const clearColor = gl.getClearColor(new Color());
  const clearAlpha = gl.getClearAlpha();
  const renderTarget = gl.getRenderTarget();
  const target = new WebGLRenderTarget(width, height);
  const instanceBytes = new Uint8Array(width * height * RGBA);
  const depthBytes = new Uint8Array(width * height * RGBA);
  const draw = (into: Uint8Array) => {
    gl.clear();
    gl.render(scene, camera);
    gl.readRenderTargetPixels(target, 0, 0, width, height, into);
  };
  try {
    scene.background = null;
    gl.setClearColor(NOTHING, 0);
    gl.setRenderTarget(target);
    for (const object of hidden) {
      object.visible = false;
    }
    for (const { mesh, instance } of surfaces) {
      mesh.material = instance;
    }
    draw(instanceBytes);
    for (const { mesh, material } of surfaces) {
      mesh.material = depths.get(material.side) ?? material;
    }
    draw(depthBytes);
  } finally {
    // The scene as it was, whatever the passes did.
    for (const { mesh, material, instance } of surfaces) {
      mesh.material = material;
      instance.dispose();
    }
    for (const object of hidden) {
      object.visible = true;
    }
    for (const depth of depths.values()) {
      depth.dispose();
    }
    scene.background = background;
    gl.setClearColor(clearColor, clearAlpha);
    gl.setRenderTarget(renderTarget);
    target.dispose();
  }
  return decodePasses(instanceBytes, depthBytes, width, height, entityIds);
}
