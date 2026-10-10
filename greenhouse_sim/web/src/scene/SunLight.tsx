import { useFrame, useThree } from "@react-three/fiber";
import { type RefObject, useEffect, useMemo, useRef } from "react";
import { type DirectionalLight, type Group, type Material, Mesh, Object3D } from "three";

import type { SunLightPose } from "../weather/sunlight";
import { worldToViewer } from "../world";

// The sun's light, stronger than the fixed light it replaces, as the sky's
// light is dimmer beside it (`SUNLIT_AMBIENT_INTENSITY`); its shadow
// map's resolution, the depth its camera starts at and reaches to, past the
// house, and its biases, which keep a lit face from shading itself.
export const SUNLIGHT_INTENSITY = 2;
const SHADOW_MAP_SIZE = 2048;
const SHADOW_NEAR_M = 0.1;
const SHADOW_FAR_REACH = 2;
const SHADOW_BIAS = -0.0005;
const SHADOW_NORMAL_BIAS = 0.02;

function transparent(material: Material | Material[]): boolean {
  return Array.isArray(material) ? material.some((m) => m.transparent) : material.transparent;
}

/** Lets everything in `group` take shadows, and its opaque meshes cast
 * them; or neither, once the sun has gone. */
function shade(group: Group | null, on: boolean): void {
  group?.traverse((object) => {
    if (object instanceof Mesh) {
      object.castShadow = on && !transparent(object.material);
      object.receiveShadow = on;
    }
  });
}

/**
 * The scene lit from the sun's direction, casting shadows: a directional
 * light from `pose`, shining at its target, its shadow camera covering the
 * house. Everything opaque in `casters` casts a shadow, and everything there
 * takes them; glass and other see-through faces cast none, as glass lets the
 * light through. The canvas draws shadows only while this is drawn, so that
 * scenes lit otherwise, the QA pages among them, draw as before.
 */
export function SunLight({
  pose,
  casters,
}: {
  pose: SunLightPose;
  casters: RefObject<Group | null>;
}) {
  const light = useRef<DirectionalLight>(null);
  const target = useMemo(() => new Object3D(), []);
  const { gl, scene } = useThree();

  useEffect(() => {
    scene.add(target);
    return () => {
      scene.remove(target);
    };
  }, [scene, target]);

  useEffect(() => {
    const at = worldToViewer(pose.target);
    target.position.set(at.x, at.y, at.z);
    target.updateMatrixWorld();
    const shining = light.current;
    if (shining === null) {
      return;
    }
    shining.target = target;
    const camera = shining.shadow.camera;
    camera.left = -pose.shadowHalfWidthM;
    camera.right = pose.shadowHalfWidthM;
    camera.top = pose.shadowHalfWidthM;
    camera.bottom = -pose.shadowHalfWidthM;
    camera.near = SHADOW_NEAR_M;
    camera.far = pose.distanceM * SHADOW_FAR_REACH;
    camera.updateProjectionMatrix();
  }, [pose, target]);

  // The shadow map is drawn only when what it shows changes: the sun moves,
  // or the scene's meshes come and go, a selection among them; those there
  // then cast and take shadows. Drawn every frame, it costs a software
  // renderer, CI's, more than the scene itself.
  const drawn = useRef<{ pose: SunLightPose | null; meshes: number }>({ pose: null, meshes: -1 });
  useFrame(() => {
    const group = casters.current;
    let meshes = 0;
    group?.traverse((object) => {
      if (object instanceof Mesh) {
        meshes += 1;
      }
    });
    if (drawn.current.pose !== pose || drawn.current.meshes !== meshes) {
      shade(group, true);
      drawn.current = { pose, meshes };
      gl.shadowMap.needsUpdate = true;
    }
  });
  useEffect(() => () => shade(casters.current, false), [casters]);

  const position = worldToViewer(pose.position);
  return (
    <directionalLight
      ref={light}
      position={[position.x, position.y, position.z]}
      intensity={SUNLIGHT_INTENSITY * pose.beamShare}
      castShadow
      shadow-mapSize-width={SHADOW_MAP_SIZE}
      shadow-mapSize-height={SHADOW_MAP_SIZE}
      shadow-bias={SHADOW_BIAS}
      shadow-normalBias={SHADOW_NORMAL_BIAS}
    />
  );
}
