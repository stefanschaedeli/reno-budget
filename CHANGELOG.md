# Changelog

All notable changes to **Reno-Budget** are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and
this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] — 2026-06-06

### Added
- Initial project scaffolding (monorepo: `backend/`, `frontend/`, `deploy/`, `docs/`, `scripts/`).
- FastAPI backend skeleton with `/healthz` endpoint, Pydantic settings, async SQLAlchemy + Alembic stubs, pytest skeleton.
- React + TypeScript + Vite frontend skeleton with Tailwind, i18n stub (de-CH), Vitest skeleton.
- Docker Compose stack skeleton (`api`, `web`, `db`, `worker`) with healthchecks; nginx reverse-proxy config; `.env.example`.
- Tooling: ruff, mypy, bandit, pip-audit, eslint, prettier, gitleaks via pre-commit; conventional-commit + SemVer policy.
- Initial documentation: top-level `README.md`, `docs/howto/README.md` (index + template), `docs/architecture/adr/0001-stack-choice.md`, design spec under `docs/superpowers/specs/`.
- Approved master implementation plan referenced from `docs/architecture/`.
