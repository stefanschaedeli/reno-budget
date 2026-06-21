"""AI Project Assistant service package.

A self-contained module that turns a renovation project into a better
description, a rough cost estimate, and BKP positions, guarded by a three-layer
validation strategy. Only :mod:`app.services.ai.client` imports the Anthropic
SDK, keeping the rest of the module testable without a live API and extractable
into its own service later.
"""
