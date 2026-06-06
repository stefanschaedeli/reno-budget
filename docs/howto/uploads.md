# How-To: Anhänge hochladen

_Eingeführt mit Version: 0.7.0_

## Aufgabe

Dokumente (Offerten, Rechnungen, Verträge) und Fotos an einzelne
Kostenpositionen oder ganze Objekte heften, gemeinsam mit Familien­mitgliedern
nutzen und kontrolliert löschen.

## Voraussetzungen

- Rolle **Editor** oder **Eigentümer** auf dem Objekt — zum Hochladen und
  Löschen fremder Anhänge.
- Rolle **Viewer** genügt zum Ansehen und Herunterladen.
- Erlaubte Dateitypen: **PDF**, **JPG/JPEG**, **PNG**, **WEBP**, **HEIC**,
  **XLS**, **XLSX**.
- Maximale Dateigrösse: **25 MB** (konfigurierbar via `RENO_UPLOAD_MAX_BYTES`).
- Browser mit Drag-&-Drop und `FormData`-Unterstützung (jeder moderne
  Browser).

## Schritt-für-Schritt

### Anhang an eine Kostenposition

1. Im Objekt unter **Kosten** die gewünschte Position öffnen (Bleistift-Icon).
2. Im Detailbereich nach unten scrollen zu **Anhänge**.
3. Datei in den gestrichelten Bereich ziehen **oder** auf **Datei wählen**
   klicken und im Dateidialog die gewünschte Datei auswählen.
4. Der Fortschrittsbalken zeigt den Upload-Status. Nach Abschluss erscheint
   die Datei in der Liste mit Name, Grösse und Datum.

### Anhang an ein Objekt

1. Im Objekt-Detail oben den Bereich **Anhänge** ansteuern.
2. Datei ablegen oder auswählen — gleiches Verhalten wie oben.

### Herunterladen

- Auf den Dateinamen in der Liste klicken. Der Browser bietet die Datei zum
  Speichern an (`Content-Disposition: attachment`). Dateien werden **nicht
  inline** dargestellt — dies ist eine bewusste Sicherheitsentscheidung.

### Löschen

1. Auf **Löschen** neben dem Eintrag klicken.
2. Die Bestätigungs­abfrage erscheint inline.
3. Auf **Löschen** klicken (rote Schaltfläche), um endgültig zu entfernen.

Hinweise:

- Wer die Datei hochgeladen hat, darf sie immer selbst löschen, selbst als
  Viewer.
- Andere Anhänge darf nur löschen, wer mindestens **Editor**-Rolle hat.
- Das Löschen entfernt nur die Datenbank-Verknüpfung. Identische Inhalte
  werden über den SHA-256-Hash dedupliziert; eine spätere Garbage-Collection
  räumt unbenutzte Blobs auf.

## Sicherheit (technische Details)

- Der Dateityp wird **server­seitig** über `libmagic` (Python-Paket
  `python-magic`) aus den ersten 4 KiB der Datei erkannt. Der vom Client
  gesendete `Content-Type`-Header wird verworfen — so lassen sich
  Manipulationen verhindern.
- Dateinamen werden bereinigt (`..`-Sequenzen, Null-Bytes und Pfadtrenner
  führen zur Ablehnung).
- Die Dateien liegen ausserhalb des Web-Roots unter `<RENO_UPLOADS_DIR>` und
  sind nur über den authentifizierten Download-Endpunkt erreichbar.
- Die Download-Antwort trägt `Content-Security-Policy: default-src 'none'`
  und `X-Content-Type-Options: nosniff`, um Angriffe über manipulierte
  PDFs/HTML-Blobs zu verhindern.
- Alle schreibenden Endpunkte verlangen das CSRF-Doppel-Submit-Cookie wie
  der Rest der API.

## Konfiguration (Betrieb)

| Umgebungs­variable | Vorgabe | Beschreibung |
|--------------------|---------|--------------|
| `RENO_UPLOADS_DIR` | `./uploads` | Wurzelverzeichnis für inhalts­adressierte Blobs. In Produktion auf ein eigenes TrueNAS-Dataset legen. |
| `RENO_UPLOAD_MAX_BYTES` | `26214400` (25 MiB) | Hartes Limit pro Datei; grössere Uploads werden mit `413` abgelehnt. |

### System­abhängigkeit `libmagic`

`python-magic` benötigt die native Bibliothek **libmagic**. Auf
Docker-Images installieren:

```dockerfile
RUN apt-get update && apt-get install -y --no-install-recommends libmagic1
```

Auf macOS (Entwicklung): `brew install libmagic`.

## Häufige Probleme

| Symptom | Ursache | Abhilfe |
|---------|---------|---------|
| Upload bricht mit `415` ab | Dateityp nicht in der Allowlist | Datei in einen erlaubten Typ konvertieren (z. B. Word → PDF). |
| Upload bricht mit `413` ab | Datei grösser als `RENO_UPLOAD_MAX_BYTES` | Datei verkleinern oder Konfigurations­wert anheben. |
| `400 Dateiname ungültig` | Dateiname enthält `..`, `/` oder Null-Bytes | Datei lokal umbenennen und erneut versuchen. |
| Download liefert `404 Datei nicht verfügbar` | Blob auf der Festplatte fehlt (manuelle Bereinigung?) | Wiederherstellen aus Backup oder Datenbank­zeile löschen. |
| Server-Start scheitert mit `failed to find libmagic` | System­paket fehlt | Siehe Abschnitt **Konfiguration**. |

## Verwandte Funktionen

- [Kostenpositionen](./kosten.md)
- [Objekte & Einheiten](./objekte.md)
- [RBAC & Rollen](./rbac.md)
