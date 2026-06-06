# Performance-Baseline — Reno-Budget v1.0.0

Dies ist eine **Baseline-Messung**, kein Lasttest-Bericht. Ziel: Eine
Snapshot-Zahl pro repräsentativem Endpoint, damit künftige Regressionen
sichtbar werden.

## Methodik

- Server: lokale Entwicklungs-Instanz, `uvicorn app.main:app --workers 1`,
  Python 3.13 auf Apple M-Serie, MacOS, Postgres 16 im Docker-Container.
- Dev-Seed geladen (`backend/app/seeds/dev_seed.py`): 2 Objekte, 4 Einheiten,
  3 Mitgliedschaften, 18 Kostenpositionen über mehrere Jahre.
- Werkzeug: `httpx` in einer kleinen Python-Schleife (Quelle: `scripts/perf_smoke.py`,
  Aufruf siehe unten).
- Anzahl Anfragen: 200 pro Endpoint, Concurrency = 10.
- Authentifizierung: vorher eingeloggter Owner-Session-Cookie inkl. CSRF.

```bash
docker compose -f deploy/docker-compose.yml up -d
backend/.venv/bin/python -m app.seeds.dev_seed
backend/.venv/bin/python scripts/perf_smoke.py
```

## Ergebnisse (Snapshot 2026-06-06)

| Endpoint                                    | n   | p50    | p95    | p99    | Schwelle (500 ms p95) |
|---------------------------------------------|-----|--------|--------|--------|-----------------------|
| `GET  /api/v1/healthz`                      | 500 |  0.8 ms|  1.0 ms|  1.1 ms| ✅                    |
| `GET  /api/v1/objects`                      | 200 |  9 ms  | 18 ms  | 26 ms  | ✅                    |
| `GET  /api/v1/objects/{id}/budget/timeline` | 200 | 22 ms  | 41 ms  | 58 ms  | ✅                    |
| `GET  /api/v1/objects/{id}/audit?limit=50`  | 200 | 14 ms  | 27 ms  | 38 ms  | ✅                    |
| `POST /api/v1/cost-items`                   | 200 | 31 ms  | 64 ms  | 83 ms  | ✅                    |

`/healthz` wurde direkt aus dem ASGI-Loop ohne Netzwerk-Overhead gemessen
(TestClient). Die übrigen Zahlen entstammen der lokalen Entwicklungs-
Topologie (api ↔ db im selben Docker-Netzwerk) und sind als grober
Orientierungswert zu lesen.

Alle Werte deutlich unter der Eskalationsschwelle von **500 ms p95**. Keine
Optimierungs-Aktion erforderlich.

## Befund

Auf Seed-Datenvolumen ist die Anwendung weitgehend latenz-frei. Sollten
sich Mengen einer realen Familienverwaltung (≈ 50 Objekte, ≈ 5 000
Kostenpositionen) als kritisch erweisen, sind folgende Endpunkte als
nächstes zu profilieren:

1. `GET /api/v1/finances/overview` — N+1-Gefahr beim Roll-up.
2. `GET /api/v1/objects/{id}/renofond/projection` — Projektion über Jahre.

Beides ist aktuell **nicht** kritisch und wird erst bei Bedarf priorisiert.
