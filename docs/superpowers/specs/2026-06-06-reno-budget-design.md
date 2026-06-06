# Reno-Budget — Design Spec (2026-06-06)

> Diese Spec spiegelt den vom Auftraggeber genehmigten Master-Plan unter
> `/Users/stefan/.claude/plans/i-like-to-start-drifting-cloud.md`. Bei
> Aktualisierungen sind beide Dokumente synchron zu halten.

## Kontext

Selbst-gehostete Web-Anwendung zur Erfassung und Planung von Renovations- und
Unterhaltskosten für mehrere Schweizer Liegenschaften (Einfamilien- und
Mehrfamilienhäuser / Stockwerkeigentum). Multi-User mit Rollen pro Objekt und
optionalem Einheiten-Scope. UI in Deutsch (CH). Containerisiert auf TrueNAS,
hinter vorgeschaltetem Reverse-Proxy.

## Stack

Siehe [`docs/architecture/adr/0001-stack-choice.md`](../../architecture/adr/0001-stack-choice.md).

## Datenmodell (Kernentitäten)

- **User** — Konto, Argon2id-Passwort-Hash, optional TOTP.
- **Object** — Liegenschaft (SFH/MFH, Planungs­horizont, Adresse, Baujahr).
- **Unit** — Wohn-/Nutzungs-Einheit innerhalb eines Objects, mit Wertquote
  (Promille). SFH erhält implizit eine Einheit mit 1000‰.
- **ObjectMembership** — User × Object × Rolle (OWNER | EDITOR | VIEWER).
- **UnitScope** — optionale Begrenzung einer Mitgliedschaft auf bestimmte
  Einheiten.
- **BkpCode** — hierarchisches eBKP-H-Code-Verzeichnis (gesät + benutzerdefiniert).
- **CostItem** — Kostenposition: BKP-Code, Status, Priorität, geplantes Jahr,
  geplanter Betrag, IST-Betrag/-Datum, Lebensdauer, Garantie, Scope.
- **CostItemUnitAllocation** — pro-Einheit-Aufteilung in Promille (Summe = 1000).
- **Attachment** — hochgeladene Dateien, content-addressed (sha256).
- **Budget** — Jahres-Budget pro Object.
- **RenofondContribution** — geplante/tatsächliche Erneuerungsfonds-Einlage.
- **AuditLog** — wer hat wann was geändert (Diff in JSON).

## RBAC

- Drei Rollen pro Object: OWNER, EDITOR, VIEWER.
- Optionale per-Unit-Beschränkung für EDITOR/VIEWER.
- Zentrale Dependency `get_object_access(user, object_id) -> (role, allowed_units)`;
  alle Repository-Queries enforced über `object_id`-Join und Unit-Filter.

## Phasen

| # | Inhalt                                                  |
|---|---------------------------------------------------------|
| 0 | Scaffolding, Tooling, Docker-Skeleton                   |
| 1 | Auth + Users + Invitations                              |
| 2 | Objects + Units + RBAC                                  |
| 3 | eBKP-H Katalog + CostItems + Allocations                |
| 4 | Yearly Budgets                                          |
| 5 | Renofond Projection                                     |
| 6 | Uploads / Attachments                                   |
| 7 | Audit-Log Viewer                                        |
| 8 | Exports: XLSX + PDF + NPK-Stub                          |
| 9 | Worker: nightly pg_dump + Reminder-Digests              |
|10 | Hardening / Dep-Audit / Pen-Test-Checklist / v1.0.0     |

Jede Phase endet mit: Tests grün → `docs/howto/<feature>.md` aktualisiert →
`CHANGELOG.md` ergänzt → `VERSION` erhöht → Conventional-Commit → Git-Tag.

## Sicherheits-Baseline

- HTTPS via vorgeschaltetem Proxy; HSTS, strikte CSP, X-Frame-Options DENY.
- Argon2id, zxcvbn-Komplexität, Rate-Limits, Account-Lockout.
- CSRF via Double-Submit-Cookie; Refresh-Token HttpOnly+Secure+SameSite=Lax.
- Pydantic-Input-Validierung; ORM-only-SQL; Pydantic-Output-Schemas.
- Uploads: Grössen-Limit, MIME-Allowlist, libmagic-Sniff, Storage ausserhalb
  Web-Root, signierte Kurz-URLs mit ACL-Prüfung bei Ausstellung.
- Secrets nur via env / docker secrets; `.env.example` committed,
  `.env` ignored.
- pip-audit, npm audit, bandit, semgrep, eslint-security in Pre-Commit.
- Strukturierte JSON-Logs mit PII-/Secret-Scrubbing.
- Audit-Log auf alle finanziellen Entitäten (Create/Update/Delete + Diff).

## Verifikation

- Backend: `pytest -q`, Coverage ≥85 % auf Services / ≥70 % auf Routern.
- Frontend: `npm test` (Vitest), später Playwright E2E.
- Stack: `docker compose up --build`, Smoke-Skript `scripts/smoke.sh`.
- Security: `pip-audit`, `npm audit`, `bandit -r backend/app`,
  `gitleaks detect` — alle clean vor Tag.
- Backup: `worker` schreibt nächtlich pg_dump nach `/backups`;
  `scripts/restore.sh` testet Restore in Wegwerf-DB.

## Versionierung

SemVer in `VERSION` + Keep-a-Changelog-Format in `CHANGELOG.md`.
Git-Tags `v<MAJOR>.<MINOR>.<PATCH>` pro Phase / Release.
