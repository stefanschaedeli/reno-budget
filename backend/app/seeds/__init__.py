"""Seed data for Reno-Budget.

Two flavours live side-by-side:

* ``ebkp_h.json`` — the eBKP-H catalogue, loaded by an Alembic data migration
  so every deployment ships with the same canonical codes.
* :mod:`app.seeds.dev_seed` — a developer-only fixture script that populates
  the database with a realistic Schweizer Renovations-Demo (two Objekte,
  members with mixed roles, ~18 multi-year Kostenpunkte across eBKP-H
  groups). Never invoke this in production: it inserts fake users and
  weakly-hashed passwords.

The dev seed is intentionally a runnable module rather than an Alembic data
migration: it must stay reversible (drop & re-seed during dev) and is allowed
to evolve as Phase 4+ adds new dashboards / fields without producing
migration churn.
"""
