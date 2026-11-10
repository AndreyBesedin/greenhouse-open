import { useEffect, useId, useState } from "react";

import { Button } from "../design/Button";
import { Notice } from "../design/Notice";
import { sizeText } from "../landing/storedRuns";
import { bytesOf, downloadScenarioFile, offerFile } from "./scenarioFile";

/** A scenario's file as it can be had: with the recorded weather it runs
 * under, if it has one, and without it. */
interface Offer {
  fileName: string;
  withRecording: string;
  /** The file without the recording, if the scenario has one. */
  without: string | null;
}

/**
 * A registered scenario handed on as a file (P17.11): the file is downloaded
 * and sent to a colleague, who uploads it from the start page and finds it
 * open in the builder. A scenario under a recorded weather asks whether the
 * recording goes with it, and says what it adds.
 */
export function ShareScenario({ scenarioId }: { scenarioId: string }) {
  const heading = useId();
  const [offer, setOffer] = useState<Offer | null>(null);
  const [problem, setProblem] = useState<string | null>(null);
  const [include, setInclude] = useState(true);

  useEffect(() => {
    let current = true;
    setOffer(null);
    setProblem(null);
    void (async () => {
      const whole = await downloadScenarioFile(scenarioId, true);
      if (!current) {
        return;
      }
      if (whole.status !== "loaded") {
        setProblem(whole.reason);
        return;
      }
      const { file_name, text, has_recording } = whole.value;
      const bare = has_recording ? await downloadScenarioFile(scenarioId, false) : null;
      if (!current) {
        return;
      }
      if (bare !== null && bare.status !== "loaded") {
        setProblem(bare.reason);
        return;
      }
      setOffer({
        fileName: file_name,
        withRecording: text,
        without: bare === null ? null : bare.value.text,
      });
    })();
    return () => {
      current = false;
    };
  }, [scenarioId]);

  const recording =
    offer?.without == null ? 0 : bytesOf(offer.withRecording) - bytesOf(offer.without);

  function download(): void {
    if (offer === null) {
      return;
    }
    const carried = include || offer.without === null;
    offerFile(offer.fileName, carried ? offer.withRecording : (offer.without ?? ""));
  }

  return (
    <section className="builder-share" aria-labelledby={heading}>
      <h2 id={heading}>Share this scenario</h2>
      <p className="builder-note">
        Download it as a file and send it to a colleague. They upload it from the start page and it
        opens here.
      </p>
      {problem !== null && <Notice kind="problem">The file cannot be made: {problem}</Notice>}
      {offer?.without != null && (
        <label className="builder-share-recording">
          <input
            type="checkbox"
            checked={include}
            onChange={(event) => setInclude(event.target.checked)}
          />
          Include the recorded weather ({sizeText(recording)})
        </label>
      )}
      <Button disabled={offer === null} onClick={download}>
        Download scenario file
      </Button>
    </section>
  );
}
