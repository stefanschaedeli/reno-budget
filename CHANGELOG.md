# Changelog

All notable changes to **Reno-Budget** are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and
this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.9.0] — 2026-06-06

### Added
- **Exporte** (Phase 8): Drei neue Download-Endpunkte pro Objekt für
  Eigentümer, Editoren und Viewer.
- **XLSX-Export** (`/api/v1/objects/{id}/export/xlsx`): Arbeitsmappe mit
  Blatt **Kostenpositionen** (BKP-Code, Titel, Status, Priorität, Plan-/
  Effektiv-Betrag, Datum, Anteils-Verteilung, NPK-Stub) und Blatt
  **Budget** (Jahres-Aggregate plus Reserve-Kennzahlen).
  Beträge mit Schweizer Zahlenformat (`#,##0.00`), Kopfzeile fett,
  fixierte erste Zeile.
- **PDF-Export** (`/api/v1/objects/{id}/export/pdf`): Einseitiger A4-
  Bericht mit Kopfdaten, Reserve-Kennzahlen, Top-10-Plan-Positionen und
  Renofond-Unterdeckungs-Hinweis.
- **NPK-Stub-Export** (`/api/v1/objects/{id}/export/npk`):
  Strukturiertes JSON, das die Mapping-Struktur für den späteren SIA-
  NPK-2025-Katalog vorbereitet. Jeder Eintrag trägt `stub: true` und
  einen `TODO`-Marker im Header.
- **RBAC-Pro-Rating**: Gescopte Editor/Viewer erhalten in XLSX und PDF
  alle Beträge anteilig (`Σ share_permille / 1000`), analog zu den
  Budget-Endpunkten.
- **Audit**: Jeder erfolgreiche Export schreibt ein `object.export`-
  Audit-Event (siehe [Audit-Log](docs/howto/audit.md)) mit dem Format
  im `payload`.
- **Frontend**: Drei Download-Buttons (XLSX, PDF, NPK-Stub) im Kopf
  der Budget-Seite (`/objekte/:id/budget`). Deutsche UI-Strings
  unter `export.*`.
- Dokumentation: `docs/howto/export.md` (Anwender-Anleitung Deutsch).
- 5 neue Backend-Integration-Tests (XLSX-Workbook-Inhalt, PDF-Magic-
  Bytes, NPK-JSON-Stub, Outsider-Schutz, Audit-Event-Erzeugung) —
  Gesamt: 158 Backend- und 61 Frontend-Tests.

### Changed
- Neue Backend-Abhängigkeiten: `openpyxl` (XLSX), `reportlab` (PDF).

### Security
- Alle Export-Endpunkte erfordern mindestens **Viewer**-Rolle; Outsider
  erhalten 403/404 analog zur Budget-Policy.
- Antworten setzen `Cache-Control: private, no-store` und liefern
  RFC-5987-konforme `Content-Disposition`-Header.

## [0.8.0] — 2026-06-06

### Added
- **Audit-Log** (Phase 7): Append-only Aktivitätsverlauf für
  mutierende Aktionen. Jeder Eintrag hält Akteur (`actor_user_id` +
  denormalisierte `actor_email`), Zeitstempel (UTC), `action` (z. B.
  `cost_item.create`), Ziel (`target_type`/`target_id`), `object_id`
  für die Objekt-Filterung, einen kurzen deutschen `summary`, optionalen
  `payload` (JSONB), `ip_address` und `user_agent` fest.
- **Service** `app/services/audit.py` mit der Kern-Funktion `record(...)`
  und Convenience-Helfern. Write-Hooks wurden in Auth-, Objekte-,
  Mitgliedschaften-, Kostenpositionen-, Anhänge-, Renofond- und
  BKP-Codes-Router eingehängt; reine Lese-Endpunkte schreiben **nichts**.
- **API**:
  - `GET /api/v1/objects/{id}/audit?limit=50&before=<cursor>` —
    Owner-only Per-Object-Feed mit Keyset-Paginierung (`next_before`).
  - `GET /api/v1/audit?limit=50&before=<cursor>` — Superuser-only,
    globaler Feed.
- **Frontend**: Neue Route `/objekte/:id/audit` (Owner-only, Reiter
  „Verlauf" im Objekt-Detail) und `/admin/audit` (Superuser-only,
  globaler Feed). Tabelle mit Zeit, Akteur, Aktion (deutsch übersetzt),
  Beschreibung; „Weitere laden"-Button für Cursor-Paginierung.
  Deutsche UI-Strings unter `audit.*`.
- Alembic-Migration `0007_audit_events` mit Indizes
  `ix_audit_events_object_id_created_at`, `ix_audit_events_created_at`
  und `ix_audit_events_actor_user_id`.
- Dokumentation: `docs/howto/audit.md` (Anwender-Anleitung Deutsch) inkl.
  Tabelle aller protokollierten Aktionen.
- 11 neue Backend-Integrations-Tests (Audit-Schreib-Hooks für die
  wichtigsten Mutationen + API/RBAC-Matrix für Owner, Editor, Viewer,
  Outsider, Superuser, sowie Cursor-Paginierung) und 5 neue
  Frontend-Tests für die Verlauf-Seite (Empty, gerenderte Zeilen,
  403-Banner, „Weitere laden", globaler Modus) — Gesamt: 153 Backend-
  und 61 Frontend-Tests.

### Security
- `GET /audit` erfordert `is_superuser`; nicht-Superuser erhalten 403.
- `GET /objects/{id}/audit` erfordert OWNER auf dem Objekt; Editor/
  Viewer/Outsider erhalten 403 bzw. 404 analog zur Budget-Policy.
- Das Log ist **nur lesbar** — es gibt keinen Schreib-, Update- oder
  Delete-Endpunkt auf `audit_events` über die API; Einträge werden
  ausschliesslich serverseitig durch den Audit-Service erzeugt.

## [0.7.0] — 2026-06-06

### Added
- **Anhänge** (Phase 6): Content-adressierte Datei-Uploads für
  Kostenpositionen und Objekte (Offerten, Rechnungen, Fotos, Verträge).
  Dedup über SHA-256, gesharded nach `<sha[:2]>/<sha>` analog Git-LFS.
  Max. 25 MiB pro Datei; erlaubte Mime-Typen: PDF, JPEG, PNG, WebP, HEIC,
  XLSX, XLS. Mime wird serverseitig per `libmagic` aus den ersten 4 KiB
  geschnüffelt — der Client-Header wird ignoriert.
- **Neues Modell** `Attachment(id, sha256, filename, mime, size_bytes,
  uploaded_by, target_type, target_id, created_at)`. Polymorphes Ziel
  (`cost_item` / `object`) ohne DB-FK — Existenz und RBAC werden im
  Router geprüft.
- **API**:
  - `POST /api/v1/cost-items/{id}/attachments` (Editor+, multipart)
  - `POST /api/v1/objects/{id}/attachments` (Editor+, multipart)
  - `GET  /api/v1/cost-items/{id}/attachments` / `GET /api/v1/objects/{id}/attachments` (Viewer+)
  - `GET  /api/v1/attachments/{id}/download` — Streaming mit RBAC-Check,
    RFC 6266-konformer `Content-Disposition` (ASCII-Fallback +
    `filename*=UTF-8''…`).
  - `DELETE /api/v1/attachments/{id}` (Editor+ am Parent; Uploader darf
    immer eigene Anhänge löschen).
- **Frontend**: Komponente `AttachmentList` mit Drag-Drop, Datei-Picker,
  Upload-Fortschritt (XHR), Client-seitiger Grössen-Prüfung,
  Lösch-Bestätigung. Eingebunden im Objekt-Detail und im
  Kostenposition-Edit-Drawer. Deutsche UI-Strings (`attachments.*`).
- Alembic-Migration `0006_attachments`.
- Dokumentation: `docs/howto/uploads.md` inkl. Hinweis auf die
  `libmagic`-Systemabhängigkeit (README ergänzt).
- 17 neue Backend-Tests (8 Storage-Unit-Tests für Dedup, Sharding,
  Mime-Schnüffeln, Grössen-Cap; 9 RBAC-Integration-Tests für Upload,
  Download, Delete) und 6 neue Frontend-Tests (Drag-Drop, Progress,
  Grössen-Ablehnung, Delete-Confirm) — Gesamt: 159 Backend- und
  62 Frontend-Tests.

### Changed
- Config-Setting `uploads_root` → `uploads_dir` (env `RENO_UPLOADS_DIR`)
  zur konsistenten Benennung; kein produktiver Aufrufer betroffen.

### Security
- Uploads werden niemals direkt über den Web-Root ausgeliefert — alle
  Downloads laufen durch den RBAC-geprüften Stream-Endpunkt mit
  `Content-Security-Policy: default-src 'none'`, `X-Content-Type-Options:
  nosniff` und `Cache-Control: private, no-store`.
- Dateiname-Validation lehnt `/`, `\`, Null-Bytes und `..` ab.
- Mime-Spoofing-Schutz: erlaubte Liste wird gegen das echte
  `libmagic`-Sniff-Ergebnis abgeglichen, nicht gegen den Client-Header.

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
