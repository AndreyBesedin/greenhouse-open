# 0061: A policy acts on a run as a consumer does, and is scored from outside it

**Status:** Proposed
**Date:** 2026-10-28

## Context

Decision 0057 puts the evaluation of policies after the reproduction and
the validation, a rule-based baseline first, and the roadmap's intelligence
components ask for one interface, designed first in a decision, for
anything that reads what a greenhouse observes and chooses what to do. The
[policy evaluation memo](../research/policy-evaluation-contract.md) reviews
what exists:

- **The pieces are there:** a run played back against a clock (decision
  0041), the consumer interface that reads its observations, events and
  action outcomes up to that clock (decision 0040), the gateway that takes
  a plan's revisions from a principal and authorises them (decisions 0046
  and 0052), and the truth, read by the evaluation alone (decision 0059).
  P13.9's example closes the loop through them.
- **What is missing is small:** the loop's driver, written once; a
  policy's shape; the metrics; and a test that the policy's side never
  reads the truth.

Two ways were weighed for where it lives: a thin library over the
services and the consumer interface, or a package of its own.

## Decision

- **A policy is a consumer that gives plans.** It reads the run's clock and
  what the consumer interface gives up to it: observations, events and the
  outcomes of actions. It gives revisions of its plan, of the protocol's
  actions, by its own principal of kind `policy`, through the run's gateway.
  It reads nothing else of the run, never the truth.
- **One contract, in the process or apart from it:** through the services,
  or through `/consumer/v1` and `/actuation/v1`. The repository holds the
  contract, its tests and its base policies, not every policy.
- **A thin library, in the simulator:** the loop's driver (moving the
  clock, waiting for the run, reading the logs by cursor, giving revisions)
  and a policy's shape, `decide(now, observations, events, outcomes) ->
  Plan | None`, beside the services. No new package and no change to the
  protocol.
- **Scored from outside the loop:** the metrics are functions of the logs
  and the truth, in `greenhouse_sim.evaluation`, which alone reads the
  truth. A test holds the policy's side to importing neither, as the truth
  is held to the evaluation today.
- **Recorded as an experiment:** the scenario and its seed, the run's
  identity and epoch, the policy's name, version and step, the horizon,
  the revisions given and their receipts, each metric with its definition,
  and the compute time per step.
- **A rule-based baseline first:** the example's heating rule made a
  documented policy, by what a sensor reads; the climate controller's loops
  (P11.2), acting on the true air, are the reference beside it.

## Consequences

- A policy written against the simulator is written against the protocol
  and the two interfaces, so it meets a real greenhouse's gateway and
  consumer interface the same way, and its score cannot lean on the truth.
- Each step of a loop costs the run's working out from the last revision
  (P13.7): a policy that revises often runs slowly. The gateway's bound of
  1,000 occurrences a plan stays until an experiment needs more.
- A comparison of policies needs the same run for the same policy, seed and
  step; a test holds the loop to that before any comparison is reported.
- **Worth revisiting:** if a policy needs the run's clock finer than the
  observations it reads, or an outside component needs to be called by the
  run rather than drive it.
