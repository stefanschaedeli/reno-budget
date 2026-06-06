# Changelog

All notable changes to **Reno-Budget** are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and
this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.6.0] — 2026-06-06

### Added
- **Renofond-Projektion** (Phase 5): Pro Objekt eine Jahres-Projektion des
  Reservesaldos über den Planungshorizont — beginnend mit der initialen
  Reserve, plus Soll-Einlage (aus Phase 4), plus effektive Einzahlungen,
  minus inflationierter geplanter Aufwand. Jahre mit negativem Saldo
  werden als `underfunding_years` aggregiert.
- **Effektive Einzahlungen** (`reserve_contributions`): Neues Modell pro
  Objekt mit Feldern `year`, `amount_chf` (Numeric 12,2), `note` und
  `created_at`. Mehrere Einzahlungen pro Jahr werden in der Projektion
  summiert.
- **API**:
  - `GET /api/v1/objects/{id}/renofond/projection` — Per-Jahr-Saldo,
    geplanter Aufwand, kumulierter Plan und Unterdeckungs-Digest.
  - `GET /api/v1/objects/{id}/renofond/contributions` — Liste der
    Einzahlungen plus `my_role` für UI-Gating.
  - `POST /api/v1/objects/{id}/renofond/contributions` (Owner + CSRF).
  - `DELETE /api/v1/objects/{id}/renofond/contributions/{contribution_id}`
    (Owner + CSRF).
- **Frontend**: Route `/objekte/:id/renofond` mit Unterdeckungs-Banner,
  SVG-Bilanzverlauf-Diagramm (ohne zusätzliche Chart-Abhängigkeit) und
  Einzahlungs-Tabelle inkl. Add/Delete-Formular (nur Owner).
  Verknüpfung von der Budget-Seite und neuer i18n-Block `renofond.*`.
- **Pro-Rating**: Gescopte Editor/Viewer sehen Saldo, Plan und effektive
  Einzahlungen jeweils auf ihren Anteil pro-ratiert (`Σ share_permille
  / 1000`); `scope_pro_rated` im Response.
- Alembic-Migration `0005_reserve_contributions` für die neue Tabelle
  inkl. Check-Constraints (`amount_chf >= 0`,
  `year BETWEEN 1900 AND 2200`) und zusammengesetztem Index
  `(object_id, year)`.
- Dokumentation: `docs/howto/renofond.md` (Anwender-Anleitung Deutsch)
  mit Erklärung der Projektionsformel und der Pro-Rating-Logik.
- 13 neue Backend-Tests (Service-Math + API/RBAC-Matrix + CSRF) sowie
  6 neue Frontend-Tests (Banner, Chart, Tabelle, Add-Formular, Empty-
  und Viewer-State) — Gesamt: 142 Backend- und 56 Frontend-Tests.

### Security
- Mutationen auf `/renofond/contributions` erfordern **Owner** + CSRF;
  Viewer und Editor erhalten 403 für POST/DELETE.
- Outsider erhalten 404 auf alle `/renofond/*`-Endpunkte (analog zur
  Budget-Policy) — verhindert Objekt-Enumeration.

## [0.5.0] — 2026-06-06

### Added
- **Budget-Aggregation & Reserveplanung** (Phase 4): Pro Objekt eine
  Jahres-Zeitachse mit Plan-, inflationiertem Plan- und Ist-Betrag, plus
  ein Reserveplan, der den Soll-Beitrag pro Monat, Jahr oder als
  Einmal­einlage ableitet.
- **Neue Objekt-Felder**: `contribution_mode` (`monthly` / `yearly` /
  `lump-sum`), `inflation_rate_percent` (Numeric 5,3) und
  `initial_reserve_chf` (Numeric 12,2) — alle vom Owner per `PATCH /objects/{id}`
  editierbar.
- **API**:
  - `GET /api/v1/objects/{id}/budget/timeline?inflated=true|false` —
    Jahres-Aggregate mit Aufschlüsselung nach eBKP-H-Hauptgruppe, Einheit,
    Status und Priorität.
  - `GET /api/v1/objects/{id}/budget/reserve` — Soll-Beitrag inkl.
    Initial-Reserve-Abzug und (für Lump-Sum) Pro-Jahr-Bedarf.
  - `GET /api/v1/finances/overview` — objekt­übergreifender Roll-up für
    alle Objekte des Users; respektiert RBAC und Scope-Pro-Rating.
- **Frontend**: Routen `/objekte/:id/budget` (Budget-Seite mit Reserve-Panel,
  Zeitachse und Aufschlüsselungen) und `/finanzen` (Cross-Object-Übersicht).
  Neue Tab-Verlinkung im Objekt-Detail; neuer Top-Nav-Eintrag „Finanzen“.
- **Pro-Rating für gescopte Mitglieder**: Editor/Viewer mit Unit-Scope sehen
  in Zeitachse, Reserve und Roll-up alle Beträge auf ihren Anteil
  (`Σ share_permille / 1000`) reduziert; ein UI-Badge zeigt das an.
- **Dev-Seed** (`backend/app/seeds/dev_seed.py`): Idempotentes Seed-Modul mit
  zwei Demo-Objekten (SFH + MFH), 4 Einheiten, 3 Mitgliedschaften (inkl.
  scoped EDITOR) und 18 mehrjährigen Kostenpositionen für Demo-Zwecke.
- Alembic-Migration `0004_object_finance_fields` für die neuen Spalten und
  Check-Constraints (`inflation_rate_percent BETWEEN 0 AND 20`,
  `initial_reserve_chf >= 0`).
- Dokumentation: `docs/howto/budget.md` (Anwender-Anleitung Deutsch) mit
  Erklärung der Inflations- und Pro-Rating-Mathematik.
- 23 neue Backend-Tests (Service + API) sowie 20 neue Frontend-Tests für
  Reserve-Panel, Zeitachse, Aufschlüsselungen und Finanzen-Seite —
  Gesamt: 112 Backend- und 44 Frontend-Tests.

### Changed
- `Object.contribution_mode` ersetzt die zuvor implizite Annahme "monatlich" —
  bestehende Objekte erhalten beim Migrieren den Default `monthly`.

### Security
- Alle Budget-Endpunkte erfordern mindestens **Viewer**-Rolle; Mutationen der
  Reserve-Einstellungen erfordern **Owner** und CSRF-Token.
- Outsider erhalten 404 (nicht 403) auf `/budget/timeline` — verhindert
  Objekt-Enumeration analog zur Cost-Items-Policy.

## [0.4.0] — 2026-06-06

### Added
- **eBKP-H-Katalog** (Phase 3): Hierarchisches Klassifikationsmodell
  (`bkp_codes`) mit rund 75 vorinstallierten Codes der ersten beiden
  Ebenen (Hauptgruppen A–Z, Elementgruppen Cxx/Dxx/…). Seed-Daten werden
  per Alembic-Datenmigration aus `backend/app/seeds/ebkp_h.json` geladen
  und sind als `is_seed=true` markiert.
- **Kostenpositionen** (`cost_items`): Modell mit Status (Idee … Storniert),
  Priorität, geplantem/effektivem Betrag (Numeric 12,2), Lebensdauer,
  Garantie, eBKP-H-Referenz und optionaler NPK-Stelle (Stub für Phase 8).
  Die DB erzwingt, dass mindestens ein Betrag gesetzt ist.
- **Anteils-Verteilung** (`cost_item_unit_allocations`): pro Position
  eine Verteilung in Permille auf die Einheiten des Objekts; serverseitig
  geprüft "Summe = 1000‰". Bei Modus **Gemeinsam** und fehlender Eingabe
  wird automatisch aus den Wertquoten materialisiert.
- **API**: `GET /api/v1/bkp-codes`, `GET /api/v1/bkp-codes/tree`,
  `POST /api/v1/bkp-codes` (nur Administrator);
  `GET/POST /api/v1/objects/{id}/cost-items`,
  `GET/PATCH/DELETE /api/v1/objects/{id}/cost-items/{item_id}`.
  Listen-Endpoint mit Filtern für Status, Priorität, Jahr, Einheit,
  eBKP-Präfix und Volltext (Titel).
- **RBAC-Erweiterung**: Eingeschränkte EDITOR/VIEWER sehen
  "Gemeinsam"-Positionen nur, wenn mindestens eine ihrer Einheiten an
  der Verteilung beteiligt ist; Mutation erfordert mindestens eine
  Einheit im Scope.
- **Frontend-Modul `features/costs`** (Deutsch): Tabellen- und
  Kanban-Ansicht, URL-getriebene Filterleiste, eBKP-H-Baum-Picker mit
  Suche, Verteilungs-Editor mit Live-‰-Summe und "Standard"-Reset, Form
  mit Zod-Validierung. Drag-and-drop-Statuswechsel mit optimistischer
  TanStack-Query-Mutation.
- 19 neue Frontend-Tests (`AllocationEditor`, `CostItemForm`,
  `CostItemFilters`, `BkpCodePicker`) sowie neue Backend-Tests für
  Allocation-Validatoren, eBKP-H-Katalog und die RBAC-Matrix der
  Kostenpositionen (Gesamtsuite 89 Backend-Tests grün).
- Dokumentation: `docs/howto/ebkp.md`, `docs/howto/kosten.md`.

### Changed
- `backend/app/services/allocations.py` ergänzt um
  `validate_allocation_sum` / `AllocationError` mit
  Kostenpositions-spezifischer Fehlermeldung; bestehende
  `validate_wertquoten_sum` bleibt unverändert.
- `Object.cost_items`-Relation (Cascade Delete) für Aufräumen bei
  Objekt-Löschung.

### Fixed
- Fehlende Typannotationen in `app/api/v1/objects.py` (mypy strict),
  Restbestand aus Phase 2.

## [0.3.0] — 2026-06-06

### Added
- **Objekte & Einheiten** (Phase 2): Datenmodell für `objects`, `units`,
  `object_memberships` und `unit_scopes`. Wertquoten in Permille (‰) mit
  serverseitiger Prüfung "Summe = 1000‰" und CHECK-Constraints in der DB.
- **Per-Objekt-RBAC** mit Rollen OWNER / EDITOR / VIEWER und optionaler
  Einschränkung von EDITOR/VIEWER auf einzelne Einheiten ("Unit Scope").
- **API**: `GET/POST /api/v1/objects`, `GET/PATCH/DELETE
  /api/v1/objects/{id}`, `GET/PUT /api/v1/objects/{id}/units`, Mitglieder-
  und Einladungs-Endpoints unter `/api/v1/objects/{id}/members[,/invitations]`.
- **FastAPI-Dependency** `require_object_access_dep(role)` als einzige
  Stelle, an der per-Objekt-Zugriff erzwungen wird (keine Ad-hoc-Checks in
  Routern).
- **Einladungs-Erweiterung**: Eine Einladung kann jetzt an ein Objekt
  gebunden werden; beim Annehmen wird automatisch die entsprechende
  Mitgliedschaft mit Rolle und Unit-Scope erstellt.
- **Alembic-Migration** `0002_objects_units_rbac` legt die neuen Tabellen
  an und ergänzt `invitations` um `object_id`, `role`, `scope_unit_ids`.
- **Frontend-Seiten** (Deutsch): Objekt-Liste, Objekt-Erstellung mit
  Live-‰-Summenanzeige, Objekt-Detail (Einheiten read-only in Phase 2);
  `react-router`-Routen `/objekte`, `/objekte/neu`, `/objekte/:id`.
- 20 neue Backend-Tests (6 Wertquoten-Unit, 14 Integrations-Tests für die
  RBAC-Matrix inkl. Last-Owner-Guard und Scope-Sichtbarkeit) sowie
  3 Frontend-Tests für den Unit-Editor.
- Dokumentation: `docs/howto/objekte.md`, `docs/howto/rbac.md`.

### Security
- OWNER-Mitgliedschaften ignorieren versehentliche Unit-Scope-Einträge
  (Defense-in-Depth gegen widersprüchliche Konfigurationen).
- 404 statt 403 für Nicht-Mitglieder, damit die Existenz fremder Objekte
  nicht enumeriert werden kann.
- Superuser erben **keinen** Zugriff auf Objektdaten — sie müssen explizit
  Mitglied sein, um Kostenpositionen / Einheiten zu sehen.
- "Letzter OWNER kann nicht entfernt/herabgestuft werden" verhindert
  Orphaning eines Objekts.

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
