import { fetchScene, type SceneState } from "../scene/sceneLoad";
import { useLoad } from "../useLoad";

/** A scene the simulator wrote to a file, fetched and checked once. */
export function useSceneFile(url: string): SceneState {
  return useLoad(url, fetchScene);
}
