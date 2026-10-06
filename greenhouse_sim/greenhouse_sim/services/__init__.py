"""What the simulator does for a client, whatever way the client reaches it.

A service takes typed requests and returns typed results, or raises a
`ServiceError` (`greenhouse_sim.services.errors`) that says what went wrong
in the client's terms: something it asked for does not exist, or its request
cannot be met. Services hold the logic and the case handling: lookups,
composing the simulator's models, and turning their refusals into errors.

They know nothing of how they are reached. The local API (`greenhouse_sim.api`)
is one interface to them, and does no more than parse a request, call a
service, and turn its result or error into a response. Nothing in the
simulator's core imports the services; they import it.
"""
