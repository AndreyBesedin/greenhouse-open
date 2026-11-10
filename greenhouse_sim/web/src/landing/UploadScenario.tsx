import { useRef, useState } from "react";
import { installationFile } from "../builder/api";
import { Button } from "../design/Button";
import { Notice } from "../design/Notice";
import { missingWeatherProblem, type PickedFile, uploadFile } from "./sendScenarioFile";
import { keepHouse, keepSettings, uploadedAddress, uploadedHouseAddress } from "./uploaded";

/** What the button says on hover, and to whoever hears it, of what a file does. */
export const UPLOAD_NOTE =
  "Open a scenario or house file in the builder, to change it before it runs";

/**
 * A file sent in (P17.11): the simulator says which kind it is, and the builder
 * opens it at its setup, never straight into a run. A scenario file's scenario
 * is registered; an installation's file has no settings, and is given them there.
 * A refusal is said next to the control, in words that name the file.
 */
export function UploadScenario({ navigate }: { navigate: (address: string) => void }) {
  const input = useRef<HTMLInputElement>(null);
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
          `${file.name} is a house file, and cannot be passed to the builder: this window keeps no files. Open the builder and import it there.`,
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
      <Button
        className="landing-card-action"
        disabled={reading}
        title={UPLOAD_NOTE}
        onClick={() => input.current?.click()}
      >
        Upload a scenario or house file
      </Button>
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
      <Notice kind="status" className="landing-note">
        {reading ? "Reading the file…" : ""}
      </Notice>
      {problem !== null && <Notice kind="problem">{problem}</Notice>}
    </div>
  );
}
