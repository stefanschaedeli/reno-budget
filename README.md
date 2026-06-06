# Reno-Budget

Self-hosted Web-Anwendung zur Erfassung und Planung von Renovations- und
Unterhaltskosten für (mehrere) Schweizer Liegenschaften — inkl. Mehrfamilien-
häusern (Stockwerkeigentum), eBKP-H-konform, mit Familien-Zusammenarbeit
(Rollen pro Objekt, optional pro Einheit), Datei-Uploads, Jahres-Budgets,
historischen Daten und Erneuerungsfonds-Übersicht.

UI-Sprache: **Deutsch (Schweiz)**.
Code, Identifier und technische Doku: Englisch.

> Status: **v1.0.0** — Erste stabile Version. Alle Phasen 0–10 abgeschlossen
> (siehe Abschnitt „Roadmap → v1.0.0 erledigt" unten).

---

## Quickstart (Entwicklung)

Voraussetzungen:

- Docker + Docker Compose
- Python ≥ 3.12 (lokale Entwicklung ausserhalb von Docker, optional)
- Node ≥ 20 + npm (lokal, optional)
- [`uv`](https://docs.astral.sh/uv/) für die Backend-Python-Umgebung (empfohlen)
- `libmagic` auf dem Host (Linux: `apt install libmagic1`, macOS: `brew install libmagic`) — wird für Mime-Schnüffeln benötigt.

```bash
git clone git@github.com:stefanschaedeli/reno-budget.git
cd reno-budget

# Konfiguration
cp deploy/.env.example deploy/.env
# Werte (DB-Passwort, Secret-Keys, SMTP, ...) in deploy/.env eintragen

# Stack starten
docker compose -f deploy/docker-compose.yml up --build -d

# Schema-Migrationen
docker compose -f deploy/docker-compose.yml exec api alembic upgrade head

# Dev-Seed laden (optional — zwei Demo-Objekte + Owner-Account)
docker compose -f deploy/docker-compose.yml exec api python -m app.seeds.dev_seed
```

Danach erreichbar:

- Web-UI: <http://localhost:8080>
- API: <http://localhost:8080/api/v1>
- API-Doku: <http://localhost:8080/api/v1/docs>
- Healthcheck: <http://localhost:8080/api/v1/healthz>

Standard-Login aus dem Dev-Seed: `owner@example.com` / `owner-passwort-12!`.

## Was ist enthalten (v1.0.0)

- **Authentifizierung** — Argon2id-Passwörter, JWT + Refresh-Cookie,
  Einladungs-Flow, Passwort-Reset, Rate-Limits, CSRF-Schutz.
- **Objekte & Einheiten** — Wertquoten in Permille, per-Objekt-RBAC
  (Owner / Editor / Viewer), optional auf Einheiten beschränkt.
- **eBKP-H-Katalog** + **Kostenpositionen** mit Anteils-Verteilung,
  Status-Kanban und URL-getriebenen Filtern.
- **Budget & Reserve** — Jahres-Zeitachse, Inflations-Berechnung,
  Reserveplan (monatlich / jährlich / einmalig), Pro-Rating für
  gescopte Mitwirkende.
- **Cross-Object-Roll-up** — Finanzen-Seite über alle eigenen Objekte.
- **Renofond-Projektion** — Jahres-Saldo, Unterdeckungs-Banner,
  effektive Einzahlungen-Tabelle, SVG-Bilanzdiagramm.
- **Anhänge** — Content-adressierte Uploads (SHA-256), Mime-Schnüffeln
  per `libmagic`, RBAC-gesicherter Stream-Download, Drag-Drop-Frontend.
- **Audit-Log** — Append-only Aktivitätsverlauf, pro-Objekt-Feed
  (Owner) und globaler Feed (Superuser).
- **Exporte** — XLSX, einseitiger PDF-Bericht, NPK-Stub-JSON pro
  Objekt; alle exportierten Beträge werden für gescopte Mitwirkende
  pro-ratiert.
- **Worker** — nächtliches `pg_dump`-Backup mit Aufbewahrungs-Policy,
  wöchentlicher Erinnerungs-Digest per E-Mail.
- **Sicherheits-Baseline** — strikte CSP, HSTS hinter HTTPS, COOP,
  Permissions-Policy, vollständige ASVS-L2-Sichtung,
  Pen-Test-Checkliste, Performance-Baseline.

## Projektstruktur

```
backend/    FastAPI + SQLAlchemy + Alembic
frontend/   React + TypeScript + Vite
deploy/     Docker / Compose / nginx
docs/       Architektur, How-Tos, Spezifikationen
scripts/    Hilfs-Skripte (Seed, Restore, Performance-Smoke)
```

## Dokumentation

- **Wie benutze ich Funktion X?** → `docs/howto/`
- **Warum so gebaut?** → `docs/architecture/` (inkl. ADRs,
  Security-Notes, ASVS-Checkliste, Pen-Test-Checkliste,
  Performance-Baseline)
- **Vollständige Spezifikation?** → `docs/superpowers/specs/`

Jede neue Funktion **muss** ihre `docs/howto/<feature>.md` aktualisieren —
dies ist Pflicht, keine Empfehlung.

## Sicherheits-Grundsätze

- Alle Auth-Endpunkte rate-limited; Argon2id für Passwörter.
- HTTPS via vorgeschalteten Reverse-Proxy (kein eingebauter TLS-Container).
- Strikte CSP, HSTS, Secure/HttpOnly-Cookies, CSRF-Schutz.
- Keine Abkürzungen aus Bequemlichkeit — Details in
  [`docs/architecture/security-notes.md`](docs/architecture/security-notes.md)
  und der laufenden [Pen-Test-Checkliste](docs/architecture/pentest-checklist.md).

## Roadmap → v1.0.0 erledigt

| Phase | Tag       | Inhalt                                                                 |
|-------|-----------|------------------------------------------------------------------------|
| 0     | `v0.1.0`  | Initiales Scaffolding (Monorepo, Compose-Stack, Tooling)               |
| 1     | `v0.2.0`  | Auth: lokale Konten, JWT + Refresh, Einladungs- und Reset-Flow         |
| 2     | `v0.3.0`  | Objekte, Einheiten, Wertquoten, per-Objekt-RBAC                        |
| 3     | `v0.4.0`  | eBKP-H-Katalog + Kostenpositionen + Anteils-Verteilung                 |
| 4     | `v0.5.0`  | Budget-Aggregation + Reserveplanung + Finanzen-Roll-up                 |
| 5     | `v0.6.0`  | Renofond-Projektion + effektive Einzahlungen                           |
| 6     | `v0.7.0`  | Content-adressierte Anhänge mit Mime-Schnüffeln und Stream-Download    |
| 7     | `v0.8.0`  | Append-only Audit-Log + Verlauf-Ansicht                                |
| 8     | `v0.9.0`  | XLSX-/PDF-/NPK-Stub-Exporte pro Objekt                                 |
| 9     | `v0.10.0` | Worker: nächtliche Backups + wöchentlicher Erinnerungs-Digest          |
| 10    | `v1.0.0`  | Härtungs-Pass: Security-Header-Middleware, ASVS-L2, Pen-Test, Doku-Review, Performance-Baseline |

## Versionierung

[SemVer](https://semver.org/). Aktuelle Version in [`VERSION`](VERSION),
Änderungen in [`CHANGELOG.md`](CHANGELOG.md).
Git-Tags pro Release (`v<MAJOR>.<MINOR>.<PATCH>`).

## Lizenz

Privat — siehe [`LICENSE`](LICENSE).
