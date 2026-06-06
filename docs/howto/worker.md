# How-To: Worker (Backups + wöchentliche Übersicht)

_Eingeführt mit Version: 0.10.0_

## Aufgabe

Diese Anleitung erklärt den Hintergrund-Worker von Reno-Budget. Er erledigt
zwei Aufgaben, die ausserhalb der API laufen müssen:

1. **Nächtliche Datenbank-Backups** mit Aufbewahrungsrichtlinie.
2. **Wöchentliche Erinnerungs-E-Mails** an alle aktiven Benutzer.

Der Worker läuft als eigener Container (`worker`) im selben
`docker-compose`-Stack wie die API und teilt sich das Daten-Volume.

## Voraussetzungen

- Docker-Compose-Stack gemäss `deploy/docker-compose.yml` läuft.
- `deploy/.env` enthält die Worker-Variablen (siehe `.env.example`):
  - `RENO_BACKUPS_DIR` (z. B. `/data/backups`),
  - `RENO_WORKER_BACKUP_CRON`, `RENO_WORKER_DIGEST_CRON`,
  - `RENO_WORKER_BACKUP_RETENTION_DAILY`, `RENO_WORKER_BACKUP_RETENTION_MONTHLY`,
  - SMTP-Konfiguration (sonst werden Digest-E-Mails nur geloggt).

## Was läuft wann

| Job              | Standard-Zeit (UTC) | Cron-Variable                  |
| ---------------- | ------------------- | ------------------------------ |
| DB-Backup        | täglich 02:30       | `RENO_WORKER_BACKUP_CRON`      |
| Wöchentl. Digest | Montag 07:00        | `RENO_WORKER_DIGEST_CRON`      |

Die Cron-Ausdrücke folgen dem APScheduler-Format
(`Minute Stunde Tag Monat Wochentag`). Wochentage werden in englischer
Kurzform angegeben (`MON`, `TUE`, …).

## Backups: Wo landen sie?

Backups werden im Worker-Container nach `${RENO_BACKUPS_DIR}` geschrieben
(per Default `/data/backups`). Das entsprechende Volume `backups_data`
wird auch vom API-Container eingehängt — auf dem Host findet sich der
Inhalt im Docker-Volume-Pfad, üblicherweise
`/var/lib/docker/volumes/reno-budget_backups_data/_data/` (bzw. dort, wo
TrueNAS das Volume einbindet).

Dateinamenformat: `reno-budget_YYYY-MM-DD-HHmmss.sql.gz` (gzip-komprimiertes
`pg_dump --format=plain`).

### Aufbewahrungsrichtlinie

Nach jedem erfolgreichen Backup räumt der Worker das Verzeichnis auf:

- Die **30** neuesten Backups werden in jedem Fall behalten
  (`RENO_WORKER_BACKUP_RETENTION_DAILY`).
- Zusätzlich wird pro Monat das **neueste** Backup für **12** Monate
  aufbewahrt (`RENO_WORKER_BACKUP_RETENTION_MONTHLY`).

Damit hat man rollierend einen Monat tägliche Stände und ein Jahr
Monatsstände — bei minimalem Speicherbedarf.

## Restore

Ein Restore erfolgt manuell. Vorgehen:

```bash
# 1. Zielcontainer mit psql betreten (API-Container hat psql nicht; nutzen
#    Sie stattdessen den DB-Container oder einen Wegwerf-Container).
docker compose exec db sh

# 2. Im DB-Container: Datenbank neu anlegen (Vorsicht — überschreibt!).
dropdb -U "$POSTGRES_USER" "$POSTGRES_DB"
createdb -U "$POSTGRES_USER" "$POSTGRES_DB"

# 3. Backup einspielen. Datei vorher auf den Host kopieren oder über das
#    gemountete Backup-Volume erreichen.
gunzip -c /data/backups/reno-budget_2026-06-01-023000.sql.gz \
  | psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"
```

**Tipp:** Vor einem Restore-Test die API anhalten
(`docker compose stop api worker`), um zu verhindern, dass Schreiboperationen
während des Imports stattfinden.

## Manuelle Ausführung (Smoke-Test, Ad-hoc-Backup)

Beide Jobs lassen sich von Hand einmalig ausführen — nützlich nach einem
Deploy oder zur Diagnose:

```bash
# Einmal ein Backup laufen lassen
docker compose exec worker python -m app.worker --run-once backup

# Einen Digest-Lauf auslösen (alle aktiven Benutzer)
docker compose exec worker python -m app.worker --run-once digest
```

Das Kommando läuft synchron und beendet sich nach Abschluss. Der reguläre
Scheduler wird dabei nicht angefasst.

## Welche E-Mails erhält ein Benutzer pro Woche?

Sofern es etwas zu berichten gibt (sonst keine E-Mail), enthält die
wöchentliche Übersicht:

- **Dringende/hochpriorisierte Kostenpositionen**, deren `planned_year`
  im laufenden Jahr liegt oder bereits vergangen ist und deren Status
  noch nicht abgeschlossen/storniert ist.
- **Renofond-Unterdeckung** für die nächsten 5 Jahre (nur für **Eigentümer**
  der jeweiligen Objekte).
- **Neue Anhänge der letzten 7 Tage**, die von **anderen** Mitwirkenden
  hochgeladen wurden (nur für Eigentümer).

Betreffzeile: `[Reno-Budget] Wöchentliche Übersicht — JJJJ-MM-TT`.

Ist die SMTP-Konfiguration leer (Entwicklung/Test), werden die Nachrichten
nur in den Worker-Logs erfasst und nicht versendet.

## Audit-Log

Jeder erfolgreiche Backup-Lauf schreibt ein `worker.backup`-Audit-Event,
jede versandte Digest-E-Mail ein `worker.digest_sent`-Event pro
Empfänger:in. Fehlgeschlagene Backups erzeugen **kein** Audit-Event —
der Fehler erscheint nur im Worker-Log.

## Beobachtung

Der Worker schreibt strukturierte JSON-Zeilen auf stdout (Schlüssel:
`event`, `level`, `timestamp`, plus jobspezifische Felder wie
`filename`, `sent`). Mit `docker compose logs -f worker` kann man die
Läufe live verfolgen.
