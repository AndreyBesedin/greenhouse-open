import { useId, useRef, useState } from "react";
import { type PickedFile, uploadScenarioFile } from "./sendScenarioFile";
import { keepSettings, uploadedAddress } from "./uploaded";

/**
 * A scenario file sent in (P17.11): the simulator reads it and registers its
 * scenario, and the builder opens it at its setup, never straight into a run.
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
    const answer = await uploadScenarioFile(file);
    setReading(false);
    if (!answer.ok) {
      setProblem(answer.problem);
      return;
    }
    const { missingWeather, scenario, settings } = answer.value;
    if (missingWeather !== null || scenario === null) {
      const weather = missingWeather ?? "a recorded weather";
      setProblem(
        `${file.name} runs under ${weather}, which it does not carry and this simulator does not have. Ask for the file with its recorded weather included.`,
      );
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
        Upload a scenario file
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
        A file a colleague sent opens in the builder, where it can be changed before it is run.
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
