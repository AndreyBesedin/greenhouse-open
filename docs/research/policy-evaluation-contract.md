# What a policy reads and gives, and where its evaluation stands

A memo for item 7 of the [research priorities](../roadmap/research-validation-priorities.md)
(decision [0057](../decisions/0057-a-published-model-is-reproduced-and-validated-before-the-crops-grow.md)):
evaluate policies through one interface, a rule-based baseline first. It
reviews what the simulator already has for it, defines the least a policy
reads and gives and the boundary its evaluation keeps, and names what is
missing. It is the design the roadmap's intelligence components ask to be
settled first; decision
[0061](../decisions/0061-a-policy-acts-on-a-run-as-a-consumer-and-is-scored-from-outside-it.md)
proposes it.

Checked against `main` on 2026-10-28.

## What exists, and is reused unchanged

| Need | What the simulator has | Where |
| --- | --- | --- |
| The run a policy acts on | A scenario's run, played back against a clock; held until told to play; started over as a new epoch | `services.playback`, decision 0041 |
| What it reads | The consumer interface: the run, its greenhouse, observations, events and action outcomes, each a log read by cursor, up to the run's clock | `services.consumer`; `GET /consumer/v1/runs/{run_id}/…`, decision 0040 |
| What it gives | A plan, or its next revision, of the protocol's actions, given to the run's gateway by a principal; a receipt says what was taken | `Playback.submit`; `POST /actuation/v1/runs/{run_id}/plans`, decision 0046 |
| Who it is | A principal of kind `policy`, in a group whose grants say what it may do | `greenhouse_protocol.authorisation`, decision 0052 |
| What became of its actions | An outcome per action: executed, late, missed, refused, failed, cancelled, superseded or unconfirmed, and why | the outcomes log, P13.3 |
| The truth, for its score | What a perfect instrument would have read in place of each observation, from the run | `greenhouse_sim.ground_truth`, read only by `greenhouse_sim.evaluation` (`tests/test_dependencies.py`), decision 0059 |
| A loop that uses them | Observe, decide, give a revision, move the clock | `examples/03_close_the_loop.py`, P13.9 |

What a score can be made of is published already, for any consumer:

- **Energy:** the heat given, hour by hour
  (`heating_energy_increment_mj_m2` observations, P10.3).
- **Yield:** the crop's harvests, as events (`HARVEST`).
- **Climate:** the air's temperature and humidity as the sensors read them,
  and as they truly were (the ground truth).
- **Actuator use and labour:** the outcomes of the policy's actions, with
  their times and their executors; crop work takes a crew's hands and time
  (P13.6).
- **Missed actions:** outcomes `missed`, `late` and `refused`, with their
  reasons.

## The contract

### What a policy reads

The run's clock, and what the consumer interface gives up to it:
observations, events, and the outcomes of actions. Nothing else of the run:
not its configuration's hidden values, not its state, never the truth. The
greenhouse's description (`GreenhouseDescription`) says what it may act on.

### What a policy gives

Revisions of its plan, of the protocol's actions, by its own principal,
through the run's gateway. An action is checked and authorised as anyone's
is, and ends in an outcome the policy reads back. A policy may give nothing
at a step.

### When it is asked

At its own rate: its loop moves the run's clock to its next step and reads
what came in. A playback's moment follows its clock no further than the run
is worked out, and is worked again from each revision of a plan, so a loop
that moves the clock by hand waits for the run, and moves on from where it
stopped short (`advance`, in the example).

### Where the policy runs

The same contract in the simulator's process, through the services, or
apart from it, through `/consumer/v1` and `/actuation/v1`. The repository
holds the contract and its tests, not every policy.

### What its evaluation reads

Everything the policy read, and the ground truth besides, once the run has
ended or reached its horizon. The score is made outside the loop, from the
logs and the truth, so that nothing the policy can see depends on how it is
scored.

### What an evaluation records

As the research priorities' reproducibility contract asks: the scenario and
its seed, the run's identity and epoch, the policy's name and version, its
step, the horizon, the plan revisions it gave and their receipts, each
metric with its definition, the policy's compute time, and the command
that ran it. The same scenario, seed, policy and step should give the same
run: a test holds a loop to it before any comparison.

## What is missing

- **The loop's driver, once:** the hand-moved clock and `advance` are
  copied into each example. A thin library function holds them, in the
  simulator, beside the services.
- **A policy's shape:** one protocol, `decide(now, observations, events,
  outcomes) -> Plan | None`, with its principal. The loop calls it at each
  step; it keeps its own state.
- **The metrics,** each a function of the logs and the truth: energy over a
  horizon, yield, time outside a target band (by the true air), actuator
  switches, outcomes by status, compute time per step. They belong to
  `greenhouse_sim.evaluation`, which alone reads the truth.
- **A test that the boundary holds:** the policy's package imports neither
  the truth nor the evaluation, as `tests/test_dependencies.py` holds the
  truth to the evaluation today.
- **The baseline:** the example's rule made a documented policy, a heater
  on below a band and off above it, by what a sensor reads; and, beside it,
  the climate controller's own loops (P11.2), which act on the true air, as
  the reference a policy is compared with.

Nothing here needs a new package, a new interface or a change to the
protocol.

## Open

- Whether a policy may read the run's clock at a finer step than the
  consumer interface delivers observations, or only at its own step.
- How a policy's identity and version are recorded with a run: a run
  steered by plan revisions keeps its identity and its epoch (decision
  0043), and what the policy gave lives in the gateway's plans and
  outcomes, not in the run's identity.
- Scoring across seeds: how many seeds a comparison runs, and how its
  spread is reported.
