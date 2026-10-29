# 0061: Greenhouse decisions are benchmarked through interfaces built for it

**Status:** Proposed
**Date:** 2026-10-29

## Context

Decision 0057 puts the evaluation of policies among the research
priorities, and the roadmap's intelligence components ask for their
interface to be designed first, in a decision. The goal is to evaluate
greenhouse decision-making meaningfully and reproducibly, not only to show
that a policy can give a plan. The
[policy evaluation memo](../research/policy-evaluation-contract.md) sets
out what exists and what is missing:

- **What a decision can be built on exists:** a run played back against a
  clock (decision 0041); the consumer interface, which delivers
  observations, events and action outcomes no earlier than they could be
  known (decision 0040); the gateway, which takes plans from authorised
  principals (decisions 0046 and 0052); and a ground truth only the
  evaluation reads (decision 0059). P13.9's example closes a loop through
  them, in the simulator's process.
- **What a benchmark needs does not, yet:**
  - *Identity.* Over HTTP every write is the local operator's: the local
    API authenticates no one (decision 0052).
  - *Isolation.* The local API serves people the simulated world itself,
    its fields, scene, crop and the sensors' truth (decision 0036, which
    asks for an interface of its own the day a policy reads HTTP).
  - *Context.* A consumer is told the greenhouse's layout and plants, but
    not its sensors, devices, capabilities, targets or ranges; the example
    names its heater and sensor by hand.
  - *Experiments.* A playback's clock moves by real time, with no step over
    HTTP; the example moves an injected clock. A run's id and epoch stay
    the same however a policy steers it (decision 0043), so they do not
    name what a policy did.
  - *Measures.* The records score some things honestly and not others: the
    heat given to the air, not fuel or cost; harvested fresh mass; the
    true air only at the sensors' sample moments; the policy's own actions,
    but not the climate controller's switches; a crew's hands and times,
    not labour's cost.
  - *Baselines.* The example's rule is a smoke test. The climate
    controller's loops (P11.2, decision 0058) read the house's true air, a
    budget no observation-driven policy has.

## Decision

- **The goal is a benchmark,** reproducible and fair: decisions compared
  on matched scenarios, information and budgets, with their measures
  defined and their limits stated. What the code does today does not bound
  the design: an interface, the protocol or the API change where the goal
  needs it, each change a pull request of its own.
- **One foundation for intelligence components:** what a component reads
  (observations available at the moment it decides, and the run's clock),
  what it may know of the greenhouse (a capability and goal context, below),
  its identity and version recorded, and never the truth or the simulated
  world's hidden state. On it:
  - **control policies first,** which give revisions of their plans to the
    run's gateway;
  - **forecasts and estimates later,** which give typed, timestamped
    records, evaluated by measures of their own;
  - **perception later,** from the cameras' images, likewise.
- **A policy-facing interface of its own** (decision 0036's revisit):
  observations, events and outcomes, the capability and goal context, and
  plans, and nothing else of the simulated world. Its caller is
  authenticated and acts as its own principal, with the least privilege
  the authorisation grants it (decision 0052's grants), and a policy, an
  operator and an evaluator are told apart; tests hold each to what it may
  read and do. The same contract holds in the process and over the
  network, a test giving the same plan the same receipt by either.
- **The local API stays what it is:** the local operator's tool for people,
  on this machine (decisions 0009, 0036 and 0052). It is not the policies'
  interface, and no policy reads it.
- **A capability and goal context:** a versioned record, part of the
  protocol, of what a policy may read and do: the sensors and their
  quantities, units and cadences (not their imperfections, which are the
  simulated world's); the devices and what each does, with its range and
  unit; the targets and their ranges; the gateway's limits; and an
  experiment's goals and constraints.
- **A lifecycle, owned and stated:**
  - the runner owns the cursors and epochs, the plans' identities and
    revisions, the receipts, retries (a revision resent is refused as
    stale, so a retry reads the plan in force first), timeouts and
    stopping;
  - the policy owns its memory, started and reset with each episode;
  - observations are fresh as their delivery says, late ones in the batch
    they arrive in; an action's deadline is its timing's (`Asap`'s
    deadline, a lateness); a policy decides at its own cadence.
- **A simulation-only experiment runner,** apart from the policy contract:
  it moves a run's clock by deterministic barriers (advance, observe, act),
  in the process first, its remote counterpart a design of its own. A
  policy against a real greenhouse, or one remote on its own schedule,
  keeps the same decision and action semantics, on the wall clock.
- **An experiment's identity:** an episode is named by its scenario,
  installation and models' versions and the configuration's digest; its
  inputs' hashes (weather, layout); the policy's identity, version,
  configuration, weights and seed; every plan revision and receipt; the
  observations' delivery trace; the compute and latency budgets; and the
  evaluation's version and its measures' definitions. A deterministic
  replay is a tested property of a given policy, not a promise for every
  one; a stochastic or remote policy's repeatability is measured.
- **Measures defined by what they measure:** each named with its source,
  unit and denominator, and its missing processes; evaluator-only
  instrumentation added where a measure needs it (the true air through
  time, the controller's switches); fuel, electricity, cost and emissions
  scored only once they are modelled.
- **A comparison protocol:** paired weather and scenarios, fixed starting
  states, matched sensors, permissions and budgets, held-out periods and
  repeated trials with the policies' own seeds; uncertainty and trade-offs
  reported, not one opaque reward.
- **A portfolio of baselines, each with its provenance:** the example's
  rule, as a smoke test; an observation-driven conventional controller, the
  matched baseline; documented grower practice, reconstructed as a labelled
  proxy, never as a counterfactual; published rule-based, MPC and learning
  controllers, once their sources are checked; and the climate controller's
  loops, reading the true air, as a labelled privileged reference, not a
  fair comparator. Each is named with its source and version, how faithful
  it is (exact, adapted or a proxy), its parameters, its sensors and
  actions, and a reference test.
- **Claims by stage:** climate-only comparisons can come early; claims on
  yield or economics wait for the crop models reproduced and validated
  (decision 0060). A result says how a policy did in this simulator, not in
  a greenhouse.
- **Staged, each stage its own pull requests:** (A) the policy-facing
  interface, its identity and capability context, and the experiment
  runner; (B) the baseline portfolio and comparable scenarios; (C) the
  evaluator's instrumentation, the measures and multi-run reports; (D)
  richer policies, and crop and economic scenarios on validated models.

## Consequences

- **New surfaces:** a policy-facing interface with authentication, a
  protocol record for the capability and goal context, an experiment
  record, and evaluator instrumentation. Each is designed in its own pull
  request against this decision.
- **Kept, not superseded:** decisions 0009, 0036 and 0052 hold for the
  local API. The policy-facing interface is the "interface of its own"
  0036 left for this day.
- **The roadmap's "one interface"** for intelligence components becomes a
  foundation with specialisations, control policies first.
- **Worth revisiting:** if authentication or the network transport proves
  to need a service outside the repository; or if a published baseline
  cannot be reproduced closely enough to compare with.
