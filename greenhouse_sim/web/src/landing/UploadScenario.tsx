import { useId, useRef, useState } from "react";
import { installationFile } from "../builder/api";
import { missingWeatherProblem, type PickedFile, uploadFile } from "./sendScenarioFile";
import { keepHouse, keepSettings, uploadedAddress, uploadedHouseAddress } from "./uploaded";

/**
 * A file sent in (P17.11): the simulator says which kind it is, and the builder
 * opens it at its setup, never straight into a run. A scenario file's scenario
 * is registered; an installation's file has no settings, and is given them there.
 * A refusal is said next to the control, in words that name the file.
 */
export function UploadScenario({ navigate }: { navigate: (address: string) => void }) {
  const input = useRef<HTMLInputElement>(null);
  const hint = useId();
  const [reading, setReading] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);

  async function upload(file: PickedFile): Promise<void> {
    setReading(true);
    setProblem(null);
    const answer = await uploadFile(file);
    setReading(false);
    if (!answer.ok) {
      setProblem(answer.problem);
      return;
    }
    if (answer.value.kind === "installation") {
      const { installation, schema_version } = answer.value.assessed;
      const text = installationFile(schema_version, installation);
      if (keepHouse(installation.installation_id, { fileName: file.name, text })) {
        navigate(uploadedHouseAddress(installation.installation_id));
      } else {
        setProblem(
          `${file.name} cannot be passed to the builder: this window keeps no files. Open the builder and import it there.`,
        );
      }
      return;
    }
    const { missingWeather, scenario, settings } = answer.value;
    if (missingWeather !== null || scenario === null) {
      setProblem(missingWeatherProblem(file.name, missingWeather));
      return;
    }
    keepSettings(scenario.id, settings);
    navigate(uploadedAddress(scenario.id));
  }

  return (
    <div className="landing-upload">
      <button
        type="button"
        className="landing-link-button"
        disabled={reading}
        aria-describedby={hint}
        onClick={() => input.current?.click()}
      >
        Upload a scenario or house file
      </button>
      <input
        ref={input}
        type="file"
        accept="application/json,.json"
        hidden
        tabIndex={-1}
        aria-hidden="true"
        onChange={(event) => {
          const [file] = event.target.files ?? [];
          event.target.value = "";
          if (file !== undefined) {
            void upload(file);
          }
        }}
      />
      <p id={hint} className="landing-note">
        A scenario file, or a house exported from the builder, opens in the builder, where it can be
        changed before it is run.
      </p>
      <p role="status" className="landing-note">
        {reading ? "Reading the file…" : ""}
      </p>
      {problem !== null && (
        <p role="alert" className="landing-problem">
          {problem}
        </p>
      )}
    </div>
  );
}
