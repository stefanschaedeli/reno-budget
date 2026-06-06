# Sicherheitsnotizen — Reno-Budget v1.0.0

Dieses Dokument fasst die Ergebnisse der Härtung in **Phase 10** zusammen und
hält fest, was bewusst akzeptiert (oder verschoben) wurde.

## Abhängigkeits-Audit

### Backend — `pip-audit` (2026-06-06)

```
$ pip-audit --skip-editable
No known vulnerabilities found
```

Keine offenen Advisories. Das eigene Wheel (`reno-budget-api`) wird als
`editable` übersprungen — erwartet.

### Frontend — `npm audit --omit=dev` (2026-06-06)

```
$ npm audit --omit=dev
found 0 vulnerabilities
```

Keine offenen Advisories in den Laufzeit-Abhängigkeiten der SPA.

## Bewusst akzeptierte Risiken / Hinweise

- **Eslint-Warnung „Unsafe Regular Expression" in
  `frontend/src/features/budget/types.ts:15`** — manuell geprüft: der Regex
  ist linear (kein Catastrophic-Backtracking), Eingabe stammt ausschliesslich
  aus der Server-API. Warnung bleibt bestehen, kein Fix nötig.
- **`SameSite=Lax` statt `Strict` auf dem Refresh-Cookie** — bewusst, weil
  der Einladungs-Akzeptanz- und der Passwort-Reset-Flow per E-Mail-Link in
  einer neuen Top-Level-Navigation landen; `Strict` würde den Cookie nicht
  mitsenden und die Session bräche. Mitigation: Refresh-Cookie ist `HttpOnly`,
  `Secure` (ausserhalb Dev), und auf den Pfad `/api/v1/auth` beschränkt.
- **HSTS wird nur über HTTPS gesetzt** — gating auf
  `X-Forwarded-Proto: https` bzw. `RENO_ENVIRONMENT=production`. Der Header
  über `http://` zu senden wäre laut RFC 6797 wirkungslos; im
  Self-Hosted-Setup terminiert der vorgeschaltete Proxy TLS und reicht den
  Header zusätzlich durch.
- **CSP für die SPA**: `style-src 'self' 'unsafe-inline'` ist erforderlich,
  weil Vite Style-Inserts zur Laufzeit verwendet. Skripte bleiben strikt
  `'self'`.
- **Swagger-UI (`/api/v1/docs`)** wird von der Middleware vom strikten
  CSP-Header ausgenommen — Swagger benötigt `unsafe-inline` / `unsafe-eval`
  für sein Rendering. Produktiv kann der Endpoint deaktiviert werden, indem
  `docs_url=None` gesetzt wird (Empfehlung für extern erreichbare
  Deployments).

## Sicherheits-Header

Der Baseline-Header-Satz wird durch
`backend/app/core/security_headers.py::SecurityHeadersMiddleware` auf jede
Antwort gesetzt (`setdefault` — endpoint-spezifisch strengere Header wie auf
`/attachments/{id}/download` überschreibt die Middleware **nicht**). Die SPA
über nginx bekommt denselben Header-Satz redundant über `add_header … always`
in `deploy/nginx.conf`.

## Härtungs-Spot-Checks (Phase 10)

Siehe:

- `docs/architecture/pentest-checklist.md` — laufende Verifikation per curl.
- `docs/architecture/asvs-l2-checklist.md` — OWASP-ASVS-Level-2-Sichtung.
- `docs/architecture/performance-baseline.md` — Performance-Snapshot v1.0.0.

## Nächste Schritte (post-v1.0.0)

- Optionales aktives Subresource-Integrity für SPA-Assets, sobald ein
  externer CDN dazu kommt.
- TLS-Cert-Rotation und Backup-Verschlüsselung at-rest sind Teil des
  Deployment-Runbooks und werden nicht im App-Code geleistet.
