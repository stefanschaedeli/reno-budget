# Reno-Budget

Self-hosted Web-Anwendung zur Erfassung und Planung von Renovations- und
Unterhaltskosten für (mehrere) Schweizer Liegenschaften — inkl. Mehrfamilien-
häusern (Stockwerkeigentum), eBKP-H-konform, mit Familien-Zusammenarbeit
(Rollen pro Objekt, optional pro Einheit), Datei-Uploads, Jahres-Budgets,
historischen Daten und Erneuerungsfonds-Übersicht.

UI-Sprache: **Deutsch (Schweiz)**.
Code, Identifier und technische Doku: Englisch.

> Status: **v0.1.0** — Initiales Scaffolding. Funktionen werden phasenweise
> ausgeliefert (siehe `docs/architecture/`).

---

## Quickstart (Entwicklung)

Voraussetzungen:

- Docker + Docker Compose
- Python ≥ 3.12 (lokale Entwicklung ausserhalb von Docker, optional)
- Node ≥ 20 + npm (lokal, optional)
- [`uv`](https://docs.astral.sh/uv/) für die Backend-Python-Umgebung (empfohlen)

```bash
git clone <local-path> reno-budget
cd reno-budget

# Konfiguration
cp deploy/.env.example deploy/.env
# Werte (DB-Passwort, Secret-Keys, SMTP, ...) in deploy/.env eintragen

# Stack starten
docker compose -f deploy/docker-compose.yml up --build
```

Danach erreichbar:

- Web-UI: <http://localhost:8080>
- API: <http://localhost:8080/api/v1>
- Healthcheck: <http://localhost:8080/api/v1/healthz>

## Projektstruktur

```
backend/    FastAPI + SQLAlchemy + Alembic
frontend/   React + TypeScript + Vite
deploy/     Docker / Compose / nginx
docs/       Architektur, How-Tos, Spezifikationen
scripts/    Hilfs-Skripte (Seed, Restore, Smoke)
```

## Dokumentation

- **Wie benutze ich Funktion X?** → `docs/howto/`
- **Warum so gebaut?** → `docs/architecture/` (inkl. ADRs)
- **Vollständige Spezifikation?** → `docs/superpowers/specs/`

Jede neue Funktion **muss** ihre `docs/howto/<feature>.md` aktualisieren —
dies ist Pflicht, keine Empfehlung.

## Sicherheits-Grundsätze

- Alle Auth-Endpunkte rate-limited; Argon2id für Passwörter.
- HTTPS via vorgeschalteten Reverse-Proxy (kein eingebauter TLS-Container).
- Strikte CSP, HSTS, Secure/HttpOnly-Cookies, CSRF-Schutz.
- Keine Abkürzungen aus Bequemlichkeit — Details siehe
  [`docs/architecture/security.md`](docs/architecture/security.md).

## Versionierung

[SemVer](https://semver.org/). Aktuelle Version in [`VERSION`](VERSION),
Änderungen in [`CHANGELOG.md`](CHANGELOG.md).
Git-Tags pro Release (`v<MAJOR>.<MINOR>.<PATCH>`).

## Lizenz

Privat — siehe [`LICENSE`](LICENSE).
