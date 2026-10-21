import { useCallback, useEffect, useRef, useState } from "react";

import { PLACE_BY_CLICKING } from "./fields/FieldProbes";

/** The inputs that do an action on one kind of device. */
export interface Input {
  device: "Mouse" | "Trackpad" | "Touch";
  input: string;
}

/** One thing a person can do in the view, once: what it is, and either the
 * inputs that do it on each device, or how to do it. */
export interface Action {
  action: string;
  does: string;
  inputs?: readonly Input[];
}

/**
 * What the view's controls do (#207), as `orbit.ts` sets them up: three's
 * OrbitControls with its own mouse and touch bindings, no keys, and the wheel
 * aimed at the point under the pointer. Each action once, with the inputs
 * that do it on a mouse, a trackpad or a touch screen, and each mode with
 * how to start it (#272). Listed as they are, never more:
 * `ControlsHelp.test.tsx` holds the controls to it.
 */
export const CONTROLS: readonly { section: string; actions: readonly Action[] }[] = [
  {
    section: "Camera",
    actions: [
      {
        action: "Orbit",
        does: "around the point in view",
        inputs: [
          { device: "Mouse", input: "drag" },
          { device: "Trackpad", input: "click and drag" },
          { device: "Touch", input: "one finger" },
        ],
      },
      {
        action: "Pan",
        does: "across the view",
        inputs: [
          { device: "Mouse", input: "Shift-, Ctrl- or ⌘-drag, or right-drag" },
          { device: "Trackpad", input: "Shift- or ⌘-drag, or two-finger click and drag" },
          { device: "Touch", input: "two fingers, moved together" },
        ],
      },
      {
        action: "Zoom",
        does: "in and out, the wheel towards what is under the pointer",
        inputs: [
          { device: "Mouse", input: "scroll, or middle-drag" },
          { device: "Trackpad", input: "two-finger scroll, or pinch" },
          { device: "Touch", input: "pinch" },
        ],
      },
    ],
  },
  {
    section: "In the view",
    actions: [
      { action: "Select", does: "click what is under the pointer; click empty space to clear it" },
      {
        action: "Place a probe",
        does: `with an air field shown, tick “${PLACE_BY_CLICKING}” in the Probes section, then click the floor`,
      },
      {
        action: "Move equipment or a sensor",
        does: "select it, press Move in the inspector, then drag: it moves along the floor, the camera holding still but for the wheel; click and drag others alike, then start a new run with the moves",
      },
      { action: "Camera presets", does: "Top, Front, Side or Isometric, in the View panel" },
      {
        action: "The View panel",
        does: "drag its header elsewhere, or click it to fold the panel",
      },
    ],
  },
  {
    section: "Keyboard",
    actions: [
      { action: "?", does: "open or close this list" },
      { action: "Escape", does: "close this list; cancel a drag, or the moves" },
      { action: "Tab, then Enter or Space", does: "reach a control, open a folded panel" },
    ],
  },
];

/** Whether a key went to a field the person is typing in. */
function typing(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) {
    return false;
  }
  return (
    target.isContentEditable ||
    target instanceof HTMLInputElement ||
    target instanceof HTMLTextAreaElement ||
    target instanceof HTMLSelectElement
  );
}

/**
 * How to move around the view and act in it (#207): a button beside "What
 * am I seeing?", and `?` from anywhere but a field, open a card listing the
 * view's controls; × and Escape close it, and the button opens it again.
 * The view has no keys of its own to move by.
 */
export function ControlsHelp() {
  const [open, setOpen] = useState(false);
  const trigger = useRef<HTMLButtonElement | null>(null);
  const close = useRef<HTMLButtonElement | null>(null);
  // Focus follows the card: to its close button as it opens, and back to
  // the button that opens it as it closes.
  const opened = useRef(false);

  const shut = useCallback(() => setOpen(false), []);

  useEffect(() => {
    function onKey(event: KeyboardEvent): void {
      if (event.key === "?" && !typing(event.target)) {
        event.preventDefault();
        setOpen((was) => !was);
      } else if (event.key === "Escape") {
        setOpen(false);
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  useEffect(() => {
    if (open) {
      close.current?.focus();
    } else if (opened.current) {
      trigger.current?.focus();
    }
    opened.current = open;
  }, [open]);

  if (!open) {
    return (
      <button
        type="button"
        className="controls-open"
        ref={trigger}
        aria-keyshortcuts="?"
        onClick={() => setOpen(true)}
      >
        Controls <kbd>?</kbd>
      </button>
    );
  }
  return (
    <section className="controls-help" aria-labelledby="controls-help-title">
      <header>
        <h2 id="controls-help-title">Moving around the view</h2>
        <button type="button" ref={close} aria-label="Close the controls" onClick={shut}>
          ×
        </button>
      </header>
      {CONTROLS.map(({ section, actions }) => (
        <div key={section} data-testid={`controls-${section.toLowerCase().replaceAll(" ", "-")}`}>
          <h3>{section}</h3>
          <dl>
            {actions.map(({ action, does, inputs }) => (
              <div key={action} className={inputs === undefined ? undefined : "controls-moves"}>
                <dt>{action}</dt>
                <dd>{does}</dd>
                {inputs !== undefined && (
                  <dd>
                    <ul className="controls-inputs">
                      {inputs.map(({ device, input }) => (
                        <li key={device}>
                          <span className="controls-device">{device}</span> {input}
                        </li>
                      ))}
                    </ul>
                  </dd>
                )}
              </div>
            ))}
          </dl>
        </div>
      ))}
    </section>
  );
}
