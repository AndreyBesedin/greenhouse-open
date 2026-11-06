# P21: Rows of different crops

**Status:** proposed, not started. It was P12.5 in
[the setup builder](archive/p12-setup-builder.md), which closes without it. Part of the
[simulator roadmap](README.md).

## Goal

One house grows different models or varieties in different rows, and a run simulates
them reproducibly, or refuses by name what it cannot grow.

## Where it starts

A draft can already give its rows different crops, and the builder says that a run
cannot grow them: `scenario_house` refuses rows that grow different crops. P21 replaces
that refusal with a run.

## When

After [P20](p20-crop-parameter-assets.md), whose parameter sets say what a variety's
numbers are. The [research priorities](research-validation-priorities.md) place it
after their numbered items.

## What stays stable

- A house whose rows all grow one crop: its run ids, seeds, checkpoints and replay
  digests change only where a step says so, with a migration.
- One description of a house: an installation stays the house part of a scenario's
  manifest ([decision 0050](../decisions/0050-an-installation-is-the-house-part-of-a-scenario.md)).

## Steps

| Step | Work | Accepted when | Status |
| --- | --- | --- | --- |
| P21.1 | Rows of different crops run (was P12.5) | Different models or varieties per row simulated reproducibly, or refused by name | Proposed |
| P21.2 | The QA scenario below, run and recorded | Each step passes in the browser | Proposed |

## QA scenario (proposed)

In the browser: start from the reference greenhouse's house, give two rows another
variety, and run it. The two rows grow as their variety does, the run reads the same
when repeated, and a pair of crops a run cannot grow together is refused by name.

## Open questions

- Whether a row's crop belongs on an explicit row object rather than beside `CropRows`,
  which repeats one row. P21 migrates rather than keeping both.
- How a manifest gives each crop its model and parameters, when a house has more than
  one model of a part
  ([decision 0055](../decisions/0055-a-model-is-registered-with-all-that-tells-it-apart.md)).
