"""AI assistant skills — one module per pipeline step.

Each skill is a pure unit: it takes typed input, builds a prompt, calls the
shared :class:`~app.services.ai.client.AiClient`, and returns a schema-validated
typed output. Adding a new step means adding a module here and a pipeline entry —
nothing else in the module needs to change.
"""
