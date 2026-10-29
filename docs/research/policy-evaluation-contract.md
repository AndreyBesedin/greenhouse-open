# Benchmarking greenhouse decisions: what exists, what is missing, and the baselines

A memo for item 7 of the [research priorities](../roadmap/research-validation-priorities.md)
(decision [0057](../decisions/0057-a-published-model-is-reproduced-and-validated-before-the-crops-grow.md)):
evaluating greenhouse decision-making meaningfully and reproducibly. It
reviews what the simulator has for it, corrects what a first draft claimed,
names what is missing, and inventories the baselines a benchmark could
start from. Decision
[0061](../decisions/0061-greenhouse-decisions-are-benchmarked-through-interfaces-built-for-it.md)
proposes the design.

Checked against `main` and against the sources cited on 2026-10-29: the
publications against Crossref and OpenAlex, the data against DataCite, the
code against its repositories. What could not be read is said to be so.

## What exists

| Need | What the simulator has | Where |
| --- | --- | --- |
| A run to act on | A scenario's run, played back against a clock, held until told to play | `services.playback`, decision 0041 |
| What a decision may read | The consumer interface: the run, its greenhouse, its observations, events and action outcomes, each a log read by cursor, nothing delivered before the clock reaches it, a late reading in the batch it arrives in | `services.consumer`; `GET /consumer/v1/…`, decision 0040 |
| What a decision gives | A plan's revisions of the protocol's actions, given to the run's gateway by a principal, authorised by grants | `Playback.submit`; `POST /actuation/v1/…`, decisions 0046, 0052 |
| What became of each action | An outcome per planned action, with its status and reason | the outcomes log, P13.3 |
| The truth, for a score | What a perfect instrument would have read in place of each observation, at its sample's moment, read only by `greenhouse_sim.evaluation` | `ground_truth`, decision 0059 |
| A loop through them | Observe, decide, give a revision, move an injected clock | `examples/03_close_the_loop.py`, in the simulator's process |

## What is missing

- **Identity over HTTP.** Every write through `/actuation/v1` is the local
  operator's: `services.actuation` submits as `person:local_operator`,
  whatever principal a plan's actions name, because the local API
  authenticates no one (decision 0052). A plan proposed for a `policy`
  principal is refused there unless the local operator is granted to
  propose on its behalf. In the process, the example submits as its own
  principal. The same plan can therefore be taken in the process and
  refused over HTTP.
- **An interface that shows a policy nothing else.** The local API serves
  people the simulated world: the house's true air, its fields, the crop,
  the scene's hidden values, each process's state, and the sensors' truth,
  with no flag in front of any of them (decision 0036 weighed a `--qa` flag
  and left it). Decision 0036 asks, the day a policy reads HTTP, for an
  interface of its own that serves observations and takes controls, and
  nothing else.
- **What a policy may know of the greenhouse.** A consumer's
  `GreenhouseDescription` gives the layout's rows and columns and the
  plants. It lists no sensors, devices, capabilities, targets, ranges or
  units. Sensor ids reach a consumer only on each observation; the run's
  actable items and the gateway's limits are known in the process only. The
  example names its heater and its sensor by hand.
- **A lifecycle.** The server owns the consumer cursors, one store for
  every client, with no client's key. A restart is a new epoch, and an
  earlier epoch's cursor is answered empty. A revision given twice is
  refused as stale the second time: nothing is idempotent. An `Asap` action
  without a deadline is never late.
- **A clock an experiment can step.** Over HTTP a playback's clock moves by
  real time at its pace: play, pause, restart and pace, and no step. The
  example steps by injecting its own clock, in the process; it then waits
  for the run to be worked out before the clock can pass it. A real
  greenhouse cannot be stepped at all.
- **An experiment's identity.** A run's id and epoch stay the same however
  a plan steers it (decision 0043): two policies' episodes on one scenario
  share both. The run id's digest covers the scenario, the models, the
  configuration and a plan given before the run, but not the authorisation,
  the crew, or what a policy gave as it played.
- **Measures that mean what they say:**
  - **Heat:** `heating_energy_increment_mj_m2` is the heat the heaters
    give the air each hour, per m² of floor, modelled from their rated
    output and levels. It is not fuel or electricity drawn, cost or
    emissions, none of which is modelled. The protocol has types for
    lighting electricity, CO₂ dosed and costs; the simulator emits none.
  - **Harvest:** `HARVEST` events carry `harvested_mass_g`, fresh grams,
    per plant per event. A plant can have two at one day's start, a crop
    work round's and a crop action's, of different fruit. Summing them
    needs both, and nothing standing or dry.
  - **The climate:** the truth is the sensors' sampled readings, not the air
    through time.
  - **The controller's own switches** are recorded nowhere a consumer or an
    evaluator reads: not as outcomes, events or observations.
  - **Labour:** a crew is hands and each crop action's time (P13.6), with
    no cost or hours; and the server's own runs have none.
  - **The policy's actions** are its plan's outcomes: they are not every
    switch of the equipment.
- **Fair baselines.** The example's rule is a smoke test. The climate
  controller's loops (P11.2, decision 0058, Proposed) read the house's true
  air, not its sensors: a reference with privileged information, not a
  comparator for a policy that reads observations.

## The targets, by stage

As decision 0061 has them, each stage its own pull requests:

- **(A) The ports:**
  - a policy-facing interface of its own: observations, events,
    outcomes, the capability and goal context, and plans, nothing else;
  - an authenticated caller acting as its own principal, policy,
    operator and evaluator told apart;
  - the same semantics in the process and over the network;
  - a versioned capability and goal context in the protocol;
  - a stated lifecycle;
  - a simulation-only experiment runner, stepping by deterministic
    barriers.
- **(B) The baselines and scenarios:** the portfolio below, each with its
  provenance and a reference test; comparable scenarios, with paired
  weather, fixed starting states and matched sensors, permissions and
  budgets.
- **(C) The measures:**
  - each defined with its source, unit, denominator and missing
    processes;
  - evaluator-only instrumentation: the true air through time, and the
    controller's switches;
  - repeated trials, held-out periods, uncertainty and trade-offs;
  - an experiment record of everything that names an episode.
- **(D) Richer policies,** and crop and economic scenarios, once the crop
  models are reproduced and validated (decision 0060).

## The baselines

| Source | What it is | Crop and model | Code | Data | What its controller sees | How reproducible |
| --- | --- | --- | --- | --- | --- | --- |
| The example's rule | Heater on below a band, off above it, by one sensor | the run's | in the repository | none | one sensor's readings | exactly; a smoke test only |
| An observation-driven conventional controller | Heating, venting and CO₂ lines with smoothed proportional bands, as GreenLight's rule-based controls (Katzin 2021) and Panagopoulos et al.'s secondary controller write them | the run's | to write | none | the sensors' readings | from the published rules; the matched baseline |
| The climate controller's loops | Staged heating, venting, circulation and dehumidifying, with hysteresis (P11.2) | the run's | in the repository | none | the true air | exactly; a privileged reference |
| AGC2's grower reference (Hemming et al. 2020) | Three Dutch growers' manual setpoints, against five AI teams | cherry tomato, a real greenhouse | none | AGC2 dataset, CC0: setpoints requested and realised, climate, resources, harvest (contents read only from its description) | real observations | as a labelled proxy only: the climate computer's logic is unpublished |
| Panagopoulos et al. 2025 | Economic NMPC choosing a rule-based controller's lines | lettuce, van Henten's model | public, no licence file (its citation file says MIT) | its weather and outputs | true state, a perfect forecast | high, from the paper; its rules transfer, its crop does not |
| Morcego et al. 2023 | NMPC against DDPG | lettuce, van Henten's model | none | none ("on request") | MPC true state; RL noise-free outputs, noisy weather | approximate |
| van Laatum et al. 2026 | PPO with a short-horizon NMPC and a trajectory selector | tomato, GreenLight, one-day episodes | public, no licence | weather in the repository; models on request | true state and perfect forecasts | low: retraining, an HSL solver by default, scripts that depart from the paper |

- **Hemming, S. et al. (2020),** "Cherry tomato production in intelligent
  greenhouses—sensors and AI for control of climate, irrigation, crop
  yield, and quality", *Sensors* 20(22), 6430,
  [doi:10.3390/s20226430](https://doi.org/10.3390/s20226430), CC BY 4.0.
  - Every AI team made a larger net profit than the growers' reference.
  - Humans stayed in every team's loop.
  - Its dataset:
    [doi:10.4121/uuid:88d22c60-21b3-4ea8-90db-20249a5be2a7](https://doi.org/10.4121/uuid:88d22c60-21b3-4ea8-90db-20249a5be2a7),
    CC0. Its archive could not be downloaded to check its files; its
    description lists the setpoints requested and realised.
  - A logged trace of setpoints is not an executable policy. Replayed, it
    is a proxy, and the compartments' differences are not counterfactuals.
- **Panagopoulos, I. et al. (2025),** "A cascaded economic model
  predictive control approach to greenhouse climate control",
  *IFAC-PapersOnLine* 59(23), 443–448,
  [doi:10.1016/j.ifacol.2025.11.828](https://doi.org/10.1016/j.ifacol.2025.11.828),
  CC BY-NC-ND 4.0.
  - Its code repository has no licence file, so it is not copied: the
    algorithm is implemented from the paper.
- **Morcego, B. et al. (2023),** "Reinforcement learning versus model
  predictive control on greenhouse climate control", *Computers and
  Electronics in Agriculture* 215, 108372,
  [doi:10.1016/j.compag.2023.108372](https://doi.org/10.1016/j.compag.2023.108372),
  CC BY-NC-ND 4.0.
  - It shows a degenerate policy scoring well on its economic indicator
    alone, a reason to report constraints and trade-offs, not one number.
- **van Laatum, B. et al. (2026),** "Improving greenhouse fruit-production
  control by integrating reinforcement learning into short-horizon model
  predictive control", *Computers and Electronics in Agriculture*, 112501,
  [doi:10.1016/j.compag.2026.112501](https://doi.org/10.1016/j.compag.2026.112501),
  CC BY 4.0; read in its preprint,
  [arXiv:2607.07365](https://arxiv.org/abs/2607.07365).
  - Its code,
    [BartvLaatum/RL-MPC-GreenLight](https://github.com/BartvLaatum/RL-MPC-GreenLight),
    has no licence. One of its files is identical to GreenLight-Gym's,
    which is AGPL-3.0.
- **Other environments:**
  - GreenLight-Gym
    ([arXiv:2410.05336](https://arxiv.org/abs/2410.05336), AGPL-3.0) and
    GreenLight (BSD 3-Clause Clear) can be run apart as references. Neither
    is copied into this Apache-2.0 repository: AGPL code cannot be, and
    code without a licence is not.

**A tractable first benchmark:** climate-only, on the run's own house, in
three steps:
1. the example's rule, as the smoke test;
2. the observation-driven conventional controller as the matched
   baseline;
3. the controller's loops as the privileged reference beside both.

AGC2's grower proxy and the published controllers come after, each once
its fidelity is known.

## The measures

| Measure | Its source today | Unit and denominator | What it is not | Needs |
| --- | --- | --- | --- | --- |
| Heat given | heat records | MJ per m² of floor, hourly | fuel, electricity, cost, emissions | nothing, as heat; a model, for the rest |
| Harvest | `HARVEST` events | fresh g per plant per event | dry matter, fruit standing, per m² | the plants' area; nothing summed twice |
| Climate outside its limits | true sampled readings | time at each sample | the air through time | evaluator-only instrumentation of the true air |
| Actuation | the policy's outcomes | actions, by status | the controller's own switches | instrumentation of the equipment's states |
| Late, missed, refused | outcomes | actions, with reasons | — | nothing |
| Labour | the crew's hands and times | actions and seconds | hours paid, cost | a labour model, if a comparison needs one |
| Compute and latency | the runner | seconds per decision | — | the runner's record |

## Open

- How a policy authenticates, and whether a transport needs a service
  outside the repository.
- The capability and goal context's record: what it lists, and how it is
  versioned.
- The first benchmark's scenarios, weather, horizons and budgets.
- Which published controller, once its fidelity is checked, comes first
  after the conventional one.
