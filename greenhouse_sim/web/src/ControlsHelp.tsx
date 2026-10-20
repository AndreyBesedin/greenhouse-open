import { useCallback, useEffect, useRef, useState } from "react";

/** One way to move around the view, or to act in it: the input, and what
 * it does. */
export interface Control {
  input: string;
  does: string;
}

/**
 * What the view's controls do (#207), as `orbit.ts` sets them up: three's
 * OrbitControls with its own mouse and touch bindings, no keys, and the wheel
 * aimed at the point under the pointer. Listed as they are, never more:
 * `ControlsHelp.test.tsx` holds the controls to it.
 */
export const CONTROLS: readonly { device: string; controls: readonly Control[] }[] = [
  {
    device: "Mouse",
    controls: [
      { input: "Drag", does: "orbit around the point in view" },
      { input: "Shift-, Ctrl- or ⌘-drag, or right-drag", does: "pan" },
      { input: "Scroll", does: "zoom, towards what is under the pointer" },
      { input: "Middle-drag", does: "zoom" },
    ],
  },
  {
    device: "Trackpad",
    controls: [
      { input: "Two-finger scroll, or pinch", does: "zoom" },
      { input: "Shift- or ⌘-drag, or two-finger click and drag", does: "pan" },
    ],
  },
  {
    device: "Touch",
    controls: [
      { input: "One finger", does: "orbit" },
      { input: "Two fingers", does: "pinch to zoom, move together to pan" },
    ],
  },
  {
    device: "In the view",
    controls: [
      { input: "Click", does: "select what is under the pointer; click empty space to clear it" },
      { input: "Click, while placing probes", does: "place a probe" },
      {
        input: "Drag, while moving equipment or a sensor",
        does: "move it along the floor; the camera holds still but for the wheel",
      },
      { input: "Top, Front, Side, Isometric", does: "the View panel's camera presets" },
      { input: "The View panel's header", does: "fold it, or drag it elsewhere" },
    ],
  },
  {
    device: "Keyboard",
    controls: [
      { input: "?", does: "open or close this list" },
      { input: "Escape", does: "close this list; cancel a drag, or stop moving" },
      { input: "Tab, then Enter or Space", does: "reach a control, open a folded panel" },
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
      {CONTROLS.map(({ device, controls }) => (
        <div key={device} data-testid={`controls-${device.toLowerCase().replaceAll(" ", "-")}`}>
          <h3>{device}</h3>
          <dl>
            {controls.map(({ input, does }) => (
              <div key={input}>
                <dt>{input}</dt>
                <dd>{does}</dd>
              </div>
            ))}
          </dl>
        </div>
      ))}
    </section>
  );
}
