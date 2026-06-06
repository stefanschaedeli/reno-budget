# ADR 0001 — Wahl des Technologie-Stacks

- **Status:** Angenommen
- **Datum:** 2026-06-06
- **Entscheider:** Eigentümer / Auftraggeber

## Kontext

Reno-Budget ist eine selbst-gehostete Web-Anwendung zur Erfassung und Planung
von Renovations- und Unterhaltskosten für Schweizer Liegenschaften. Sie wird
auf TrueNAS containerisiert betrieben, hinter dem bestehenden Reverse-Proxy
des Eigentümers. Zielgruppe: kleine Familie; Sprachen: Deutsch (UI), Englisch
(Code/Identifier).

Anforderungen, die den Stack bestimmen:

- Starkes Typsystem auf Backend **und** Frontend
- Reife Bibliotheken für PDF/XLSX-Generierung (BKP-/eBKP-H-Exporte)
- Saubere Containerisierung (TrueNAS SCALE, Docker Compose)
- Selbst-gehostet, Open Source, keine SaaS-Abhängigkeiten
- Sicherheit ist nicht verhandelbar; bekannte, gut-auditierte Komponenten

## Entscheidung

- **Backend:** Python 3.12, FastAPI, SQLAlchemy 2 (async), Alembic, Pydantic v2,
  PostgreSQL 16, Argon2id (passlib), PyJWT, APScheduler, ReportLab/WeasyPrint,
  openpyxl, python-magic, slowapi.
- **Frontend:** React 18 + TypeScript, Vite, TanStack Query, React Router,
  React Hook Form + Zod, Tailwind CSS + Radix Primitives, react-i18next.
- **Container:** docker-compose mit `api`, `web` (nginx), `db` (Postgres),
  `worker` (APScheduler). Kein eingebauter TLS-Container — vorgeschalteter
  Reverse-Proxy übernimmt TLS.

## Konsequenzen

**Positiv**

- End-to-End Typsicherheit; OpenAPI → generierter Frontend-Client später
  möglich.
- FastAPI / Pydantic v2 sind ausgereift; SQLAlchemy 2 async passt zur
  Datenmodellkomplexität (Objekte → Einheiten → Kosten mit Wertquoten-Splits).
- React/Vite ist Standard, gut wartbar, viel Personal verfügbar.
- Ökosystem für PDF/XLSX und SMTP unter Python stabil und gut auditiert.

**Negativ / Risiken**

- Zwei Sprachen (Python + TypeScript) statt einer.
- WeasyPrint hat Systemabhängigkeiten (Pango/Cairo); werden im API-Image
  vorinstalliert.
- NPK/CRB-Katalogdaten sind lizenziert; der Stack erlaubt nur strukturelle
  Stubs und Import-Mechanik, nicht das Mitliefern der Katalogdaten.

## Verworfene Alternativen

- **Node (NestJS) + React:** Einheitliche Sprache, aber schwächeres Ökosystem
  für serverseitige PDF- und Katalog-Verarbeitung.
- **Django + HTMX:** Schnellerer Initialbuild, aber langfristig limitierter
  für interaktive Allocation-/Dashboard-Komponenten.
