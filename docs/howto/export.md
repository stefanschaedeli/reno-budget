# How-To: Export (XLSX, PDF, NPK)

_Eingeführt mit Version: 0.9.0_

## Aufgabe

Diese Anleitung erklärt, wie Sie pro Objekt **Excel- und PDF-Berichte**
sowie einen **NPK-2025-JSON-Stub** herunterladen.

## Voraussetzungen

- Mindestens Rolle **Viewer** auf dem Objekt.
- Gescopte Editor/Viewer erhalten **pro-ratierte** Beträge (Anteil am
  Objekt), analog zur Budget-Seite.

## Schritt-für-Schritt

1. Objektliste → Objekt → Reiter **Budget** öffnen.
2. Im Export-Streifen oben wählen:
   - **Excel (XLSX)** — Arbeitsmappe mit zwei Blättern (Kostenpositionen,
     Budget).
   - **PDF** — Einseitiger Bericht: Kennzahlen + Top-10-Plan-Positionen.
   - **NPK-Stub (JSON)** — Strukturierter JSON-Stub für die geplante
     SIA-NPK-2025-Integration (siehe Hinweis unten).
3. Der Browser lädt eine Datei mit Namen
   `reno-budget_<objekt-slug>_<JJJJ-MM-TT>.<ext>`.

## Was enthält der XLSX?

- **Blatt „Kostenpositionen"**: eine Zeile pro Position mit BKP-Code,
  Bezeichnung, Titel, Status, Priorität, Geplant-Jahr, Geplant CHF,
  Effektiv CHF, Ausführungsdatum, Anteils-Verteilung, NPK-Stub.
  Beträge sind als Zahl formatiert (`#,##0.00`).
- **Blatt „Budget"**: Jahres-Aggregate (Plan, inflationsbereinigter
  Plan, Ist) plus eine Kennzahlen-Sektion (Beitragsmodus, Inflation,
  Anfangsreserve, Gesamtplan, Soll/Jahr, Soll/Monat).

## Was enthält der PDF?

- Kopfzeile: Objekt-Name, Adresse, Erstellungsdatum, Versionsstempel.
- Reserve-Kennzahlen (gleiche Werte wie das Budget-Blatt).
- Top-10-Plan-Positionen nach Plan-Betrag absteigend.
- Hinweis-Banner, falls die Renofond-Projektion eine Unterdeckung zeigt.

## Was enthält der NPK-Stub?

Ein JSON-Dokument, das die Mapping-Struktur für die spätere Integration
des SIA-NPK-2025-Katalogs vorbereitet. Bis die echten NPK-Daten
eingebunden sind, enthält jeder Eintrag Platzhalter — der Stub trägt
das Feld `"stub": true` und einen `"TODO"`-Marker im Kopf. Sobald die
NPK-Lizenz-Frage geklärt ist, ersetzt Phase 11+ den Stub durch die
echte Mapping-Logik.

## Audit-Log

Jeder erfolgreiche Export erzeugt einen Audit-Log-Eintrag
(`action="object.export"`) mit dem gewählten Format im `payload`.
Eigentümer können den Eintrag im Reiter **Verlauf** des Objekts sehen
(siehe [Audit-Log](audit.md)).

## Häufige Probleme

| Symptom | Ursache | Abhilfe |
|---------|---------|---------|
| 404 beim Klick auf einen Export-Button | Keine Mitgliedschaft am Objekt | Owner um Mitgliedschaft bitten |
| Excel öffnet leer | Keine Kostenpositionen erfasst | Mindestens eine Position anlegen |
| Andere Beträge als auf dem Bildschirm | Sie sind gescoptes Mitglied | Pro-Rating ist gewollt |
| PDF zeigt nur den Kopf | Keine planbaren Positionen vorhanden | Mindestens eine Position mit `planned_year` anlegen |

## API-Endpunkte (für Entwickler)

- `GET /api/v1/objects/{id}/export/xlsx`
- `GET /api/v1/objects/{id}/export/pdf`
- `GET /api/v1/objects/{id}/export/npk`

Alle drei Endpunkte erfordern ein gültiges Access-Token und Viewer-Rolle
auf dem Objekt; sie liefern `Content-Disposition: attachment; filename*=…`
und `Cache-Control: private, no-store`.
