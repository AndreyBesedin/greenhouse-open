import { useEffect, useState } from "react";

import { fetchScene, type SceneState } from "../scene/source";

/** A scene the simulator wrote to a file, fetched and checked once. */
export function useSceneFile(url: string): SceneState {
  const [scene, setScene] = useState<SceneState>({ status: "loading" });

  useEffect(() => {
    let current = true;
    void fetchScene(url).then((state) => {
      if (current) {
        setScene(state);
      }
    });
    return () => {
      current = false;
    };
  }, [url]);

  return scene;
}
