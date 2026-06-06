# Changelog

All notable changes to **Reno-Budget** are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and
this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.0] — 2026-06-06

### Added
- **Authentifizierung** (Phase 1): lokale Konten mit Argon2id-Passwort-Hashing,
  JWT-Access-Token (15 min) + rotierender HttpOnly-Refresh-Cookie (14 d) mit
  Replay-Detection, CSRF-Schutz über Double-Submit-Cookie.
- Brute-Force-Schutz: 5-Versuche-Sperre für 15 Minuten, slowapi-Rate-Limits
  auf Login / Refresh / Reset / Accept-Endpoints.
- Einladungs-Flow: Admin (`is_superuser`) erstellt Einladungen per API;
  Empfänger setzt Name + Passwort über `/invite/<token>` (Token 7 Tage gültig).
- Passwort-Reset: Selbstbedienter Flow über E-Mail-Link (Token 1 h gültig,
  Einmal-Verwendung, widerruft alle bestehenden Sitzungen bei Erfolg).
- Server-seitige Passwort-Policy (12–128 Zeichen, ≥3 Zeichenklassen,
  kleine Denylist häufiger Passwörter).
- Outbound-SMTP-Versand (`aiosmtplib`); in Dev/Test fängt ein In-Memory-Mailer
  Nachrichten für Inspektion ein.
- Erste Alembic-Migration (`0001_initial_auth_schema`) für `users`,
  `refresh_tokens`, `password_reset_tokens`, `invitations`.
- Frontend-Seiten (Deutsch): Login, Einladung annehmen, Passwort-Reset
  (Anforderung + Bestätigung), Startseite mit Abmelden.
- 33 Backend-Tests (19 unit + 14 integration via testcontainers/Postgres);
  Frontend-Tests via Vitest (2).
- Dokumentation: `docs/howto/auth.md` (Anwender-Anleitung Deutsch).

### Security
- Refresh-Token werden nur als SHA-256-Hash gespeichert.
- Cookies sind HttpOnly + Secure (ausser Dev) + SameSite=Lax;
  Refresh-Cookie ist auf `/api/v1/auth` beschränkt.
- E-Mail-Enumeration bei Passwort-Reset wird vermieden (immer 202).

## [0.1.0] — 2026-06-06

### Added
- Initial project scaffolding (monorepo: `backend/`, `frontend/`, `deploy/`, `docs/`, `scripts/`).
- FastAPI backend skeleton with `/healthz` endpoint, Pydantic settings, async SQLAlchemy + Alembic stubs, pytest skeleton.
- React + TypeScript + Vite frontend skeleton with Tailwind, i18n stub (de-CH), Vitest skeleton.
- Docker Compose stack skeleton (`api`, `web`, `db`, `worker`) with healthchecks; nginx reverse-proxy config; `.env.example`.
- Tooling: ruff, mypy, bandit, pip-audit, eslint, prettier, gitleaks via pre-commit; conventional-commit + SemVer policy.
- Initial documentation: top-level `README.md`, `docs/howto/README.md` (index + template), `docs/architecture/adr/0001-stack-choice.md`, design spec under `docs/superpowers/specs/`.
- Approved master implementation plan referenced from `docs/architecture/`.
