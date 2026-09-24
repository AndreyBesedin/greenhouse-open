# Contributing to greenhouse-open

Thank you for considering a contribution. Issues and pull requests are
welcome, from a typo fix to a new dataset adapter.

## Sign your commits (DCO)

This project uses the [Developer Certificate of Origin](https://developercertificate.org/)
instead of a contributor licence agreement. By adding a `Signed-off-by`
line to each commit, you certify that you wrote the change or otherwise
have the right to submit it under the project's licence (Apache-2.0):

```bash
git commit -s -m "Describe the change"
```

That adds `Signed-off-by: Your Name <you@example.com>`, using your Git
name and email. Pull requests with unsigned commits cannot be merged.

## Before opening a pull request

- Keep the change focused: one concern per pull request.
- Add or update tests. A new adapter comes with small synthetic fixtures;
  never commit dataset content.
- Run the checks described in the README's Development section. CI runs
  the same checks, with each package installed on its own.
- A package may import only the standard library, itself and the
  dependencies it declares; `tests/test_dependencies.py` enforces this.

## What belongs here

The shared record format and its contracts, the simulator, dataset adapters,
and evaluation tooling that works from public data. Changes to the protocol
are the most consequential: they affect every producer and consumer, so
open an issue to discuss them first.
