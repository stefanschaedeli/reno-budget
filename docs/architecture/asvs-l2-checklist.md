# OWASP ASVS Level 2 — Spot-Check (Reno-Budget v1.0.0)

Stand: 2026-06-06. Dies ist eine **Baseline-Sichtung**, keine vollständige
externe Auditierung. Pro Kontrolle: ✅ implementiert, ⚠ teilweise, ❌ nicht
zutreffend.

## V2 — Authentication

| Kontrolle | Status | Beleg / Anmerkung |
|---|---|---|
| V2.1.1 — kein Klartext-Passwort gespeichert | ✅ | Argon2id (`app/core/security.py::hash_password`) |
| V2.1.2 — Passwort-Länge ≥ 12 | ✅ | `app/services/auth.py::validate_password_policy`, 12–128 Zeichen |
| V2.1.5 — Komplexitäts-Klassen | ✅ | Mindestens 3 Klassen + kleine Denylist |
| V2.2.1 — Account-Lockout | ✅ | 5 Fehlversuche → 15 min gesperrt |
| V2.2.3 — Rate-Limit Login | ✅ | slowapi `10/minute` |
| V2.5.1 — Passwort-Reset Token einmalig + kurzlebig | ✅ | 1 h, einmal nutzbar |
| V2.6.1 — Refresh-Token sicher gespeichert | ✅ | Server: nur SHA-256-Hash in DB |
| V2.7.x — MFA | ❌ | Self-hosted Familien-App; out-of-scope für v1.0 |

## V3 — Session Management

| Kontrolle | Status | Beleg / Anmerkung |
|---|---|---|
| V3.2.1 — Session-Token serverseitig generiert | ✅ | `secrets.token_urlsafe(64)` |
| V3.2.3 — Cookies `HttpOnly` + `Secure` | ✅ | `_set_session_cookies` in `auth.py` (Secure in Prod) |
| V3.4.1 — Rotation bei Refresh | ✅ | Refresh-Tokens rotieren, alter Token sofort widerrufen |
| V3.4.3 — Replay-Detection | ✅ | Wiederverwendeter Token → alle Sitzungen widerrufen |
| V3.4.5 — Logout invalidiert Session | ✅ | `revoke()`-Aufruf, `tests/integration/test_auth_flow.py` |
| V3.5.x — SameSite | ⚠ | Refresh-Cookie ist `SameSite=Lax`. Grund + Mitigation in `security-notes.md` |

## V4 — Access Control

| Kontrolle | Status | Beleg / Anmerkung |
|---|---|---|
| V4.1.3 — Deny by Default | ✅ | Alle Routen sind unter Auth, Ausnahmen explizit |
| V4.2.1 — IDOR-Schutz | ✅ | Per-Objekt-RBAC über `require_object_access_dep(role)` |
| V4.2.2 — Mass-Assignment | ✅ | Pydantic-Schemas pro Endpoint, keine `**kwargs` in ORM-Konstruktoren |
| V4.3.x — Superuser-Trennung | ✅ | Superuser bekommen keinen impliziten Objekt-Zugriff |

## V5 — Validation, Sanitization, Encoding

| Kontrolle | Status | Beleg / Anmerkung |
|---|---|---|
| V5.1.x — Server-side Validation | ✅ | Pydantic-Modelle für alle Request-Bodies |
| V5.2.x — Sanitisation | ✅ | DB-Layer: gebundene Parameter (SQLAlchemy); HTML: SPA escapt per React |
| V5.3.4 — SQL-Injection | ✅ | Keine String-konkatenierten SQL-Statements im Code |
| V5.3.10 — Mime-Schnüffeln | ✅ | `libmagic` über `app/services/storage.py` |
| V5.5.2 — Path-Traversal | ✅ | `validate_filename` lehnt `..`, `/`, NUL, `\` ab |

## V7 — Error Handling and Logging

| Kontrolle | Status | Beleg / Anmerkung |
|---|---|---|
| V7.1.1 — Keine Stack-Traces an Clients | ✅ | FastAPI liefert `500` ohne Trace; structlog im Backend |
| V7.1.2 — Sensitive Daten nicht geloggt | ✅ | Logging-Felder via structlog, Passwörter nie geloggt |
| V7.3.x — Audit-Trail | ✅ | Append-only `audit_events` (Phase 7), siehe `docs/howto/audit.md` |

## V8 — Data Protection

| Kontrolle | Status | Beleg / Anmerkung |
|---|---|---|
| V8.1.1 — Klassifikation | ✅ | Personenbezogene Daten: Name, E-Mail — separat dokumentiert |
| V8.2.1 — Cache-Header | ✅ | Downloads: `Cache-Control: private, no-store` |
| V8.3.x — Backups | ⚠ | Backups verschlüsselt nur, wenn Volume verschlüsselt ist — Deployment-Verantwortung |

## V9 — Communications

| Kontrolle | Status | Beleg / Anmerkung |
|---|---|---|
| V9.1.1 — TLS | ⚠ | TLS terminiert der vorgeschaltete Reverse-Proxy; kein eingebauter TLS-Container (per Design) |
| V9.1.2 — HSTS | ✅ | Middleware setzt `Strict-Transport-Security` über HTTPS |
| V9.2.1 — Sicherheits-Header | ✅ | Siehe `pentest-checklist.md` § 10 |

## V13 — API and Web Service

| Kontrolle | Status | Beleg / Anmerkung |
|---|---|---|
| V13.1.3 — API-Versionierung | ✅ | `/api/v1/...` |
| V13.2.1 — RESTful HTTP-Methoden | ✅ | GET nur lesend, POST/PATCH/DELETE schreibend |
| V13.2.2 — CSRF | ✅ | Double-Submit-Cookie (`require_csrf`) auf state-changing endpoints |
| V13.2.3 — Rate Limit | ✅ | slowapi auf Auth-Pfaden |
| V13.4.x — GraphQL | ❌ | Kein GraphQL eingesetzt |

## Zusammenfassung

37 zutreffende Kontrollen geprüft: 32 ✅, 4 ⚠ (mit dokumentierter
Mitigation), 1 ❌ (out-of-scope). Keine offenen ❌ in Kategorien, die für
eine Familien-orientierte Self-hosted-App relevant sind.
