import type { Plugin } from "vite";

/** How much a built viewer's scripts and styles weigh, minified, in kB of
 * 1,000 bytes, as Vite reports them. */
export interface BundleWeight {
  js: number;
  css: number;
}

/**
 * The most the built viewer may weigh, minified, in kB (AUDIT.20): a little
 * above its weight on 2026-10-23, 1,586 kB of scripts, Three.js about a
 * megabyte of them, and 16 kB of styles. A change that adds much to it
 * fails its build, so that it is weighed in its pull request; the budget is
 * raised there, if the weight is meant.
 */
export const BUNDLE_BUDGET_KB: BundleWeight = { js: 1700, css: 20 };

const BYTES_PER_KB = 1000;

/** What of `weight` is over `budget`, in words, if anything. */
export function overBudget(weight: BundleWeight, budget: BundleWeight): string[] {
  return (["js", "css"] as const)
    .filter((kind) => weight[kind] > budget[kind])
    .map(
      (kind) =>
        `the viewer's ${kind} weighs ${weight[kind].toFixed(0)} kB minified, over its budget of ${budget[kind]} kB (src/bundleBudget.ts)`,
    );
}

/** A build's scripts and styles, weighed from its output files' contents. */
export function weigh(files: readonly { fileName: string; bytes: number }[]): BundleWeight {
  const weight: BundleWeight = { js: 0, css: 0 };
  for (const { fileName, bytes } of files) {
    if (fileName.endsWith(".js")) {
      weight.js += bytes / BYTES_PER_KB;
    } else if (fileName.endsWith(".css")) {
      weight.css += bytes / BYTES_PER_KB;
    }
  }
  return weight;
}

/** Fails a build whose output weighs more than `budget`. */
export function bundleBudget(budget: BundleWeight = BUNDLE_BUDGET_KB): Plugin {
  return {
    name: "bundle-budget",
    apply: "build",
    generateBundle(_options, bundle) {
      const weight = weigh(
        Object.values(bundle).map((output) => ({
          fileName: output.fileName,
          bytes:
            output.type === "chunk"
              ? Buffer.byteLength(output.code)
              : typeof output.source === "string"
                ? Buffer.byteLength(output.source)
                : output.source.byteLength,
        })),
      );
      const over = overBudget(weight, budget);
      if (over.length > 0) {
        this.error(over.join("; "));
      }
    },
  };
}
