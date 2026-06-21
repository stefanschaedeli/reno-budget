# How-To: KI-Assistent für Projekte

_Eingeführt mit Version: 1.1.0_

## Aufgabe

Diese Anleitung erklärt den **KI-Assistenten**, der ein neu angelegtes
**Projekt** in drei Schritten ausarbeitet:

1. eine **bessere Projektbeschreibung**,
2. eine **erste (grobe) Kostenschätzung**,
3. **BKP-Positionen** (eBKP-H) mit explizitem **In-Scope / Out-of-Scope**.

Der Assistent ist ein **geführter Ablauf** (Wizard): Er bestimmt zunächst den
Projekttyp, stellt dann die wenigen Fragen, die die Kosten am stärksten
beeinflussen (z. B. Dach → m²; Fenster → Anzahl + Dämmstufe), und erzeugt
daraus Entwürfe. **Nichts wird automatisch übernommen** — jeder Entwurf wird
erst nach ausdrücklicher Bestätigung in echte Daten (`Projekt`-Felder bzw.
neue Kostenpositionen) geschrieben.

## Voraussetzungen

- Mindestens Rolle **Editor** auf dem Objekt (Viewer können den Assistenten
  nicht nutzen, da er Tokens verbraucht und Daten schreibt).
- Ein bereits angelegtes Projekt.
- Ein konfigurierter Anthropic-API-Schlüssel auf dem Server
  (`RENO_ANTHROPIC_API_KEY`). Ohne Schlüssel ist die Funktion deaktiviert und
  die Endpunkte antworten mit `503`.

## Schritt-für-Schritt

1. Projekt öffnen → Schaltfläche **KI-Assistent** anklicken. Der Assistent
   öffnet sich als seitliches Panel.
2. **Projekttyp** bestimmen lassen. Bei Unsicherheit zeigt der Assistent seine
   Begründung an.
3. **Fragen generieren** lassen. Die Fragen erscheinen als echte Eingabefelder
   (Zahl mit Einheit, Auswahl, Ja/Nein, Text) und werden direkt geprüft
   (z. B. Wertebereich). **Antworten speichern**.
4. **Beschreibung** erstellen lassen, prüfen und ggf. **übernehmen** → schreibt
   `Projekt.Beschreibung`.
5. **Grobschätzung** erstellen lassen. Jede Position nennt ihre **Annahmen** und
   eine **Konfidenz**. **Übernehmen** → schreibt `Projekt.Grobschätzung`.
6. **BKP-Positionen** erstellen lassen, prüfen und **übernehmen** → legt
   Kostenpositionen an, die mit dem Projekt verknüpft sind.

Jeder Schritt kann **erneut ausgeführt** werden; bereits gegebene Antworten
bleiben erhalten und werden wiederverwendet (z. B. beim erneuten Schätzen nach
einer geänderten Fläche).

## Prüfung gegen Halluzinationen

Jeder Entwurf durchläuft vor der Anzeige drei Prüfebenen:

1. **Deterministische Prüfung (ohne KI):** BKP-Codes müssen im Katalog
   existieren, Beträge müssen positiv sein, Positionen müssen sich zur
   Gesamtsumme addieren, Kosten pro m² müssen im plausiblen Bereich liegen.
   Verstösse sind **Fehler** und blockieren die Übernahme.
2. **Selbst-Begründung:** Die KI muss zu jeder Zahl Annahmen und eine Konfidenz
   angeben; Positionen mit niedriger Konfidenz werden markiert (**Hinweis**,
   blockiert nicht).
3. **Zweitmeinung (anderes Modell):** Schätzung und BKP-Positionen werden von
   einem zweiten Modell kritisch geprüft; dessen Einwände werden als Hinweise
   angezeigt.

## Wichtige Hinweise

- Die Schätzungen sind **grobe Planungswerte für die Schweiz, keine Offerten.**
  Prüfen Sie sie vor der Übernahme.
- Es gibt **keine** öffentliche, autoritative Datenquelle für Schweizer
  Renovations-Einheitspreise. Die deterministische Bandbreitenprüfung ist daher
  bewusst grosszügig und fängt nur absurde Werte ab.
- Der API-Schlüssel liegt ausschliesslich serverseitig; er wird nie an den
  Browser ausgeliefert.

## Häufige Probleme

| Symptom | Ursache | Abhilfe |
|---------|---------|---------|
| Schaltfläche/Schritt antwortet mit „nicht konfiguriert" | Kein `RENO_ANTHROPIC_API_KEY` gesetzt | Schlüssel in der Server-Umgebung hinterlegen und Dienst neu starten |
| „Bitte zuerst den Projekttyp bestimmen" | Schritt vor `classify` ausgeführt | Zuerst den Schritt **Projekttyp** ausführen |
| **Übernehmen** ist deaktiviert | Entwurf hat einen Validierungsfehler (z. B. unbekannter BKP-Code) | Schritt erneut ausführen; ggf. Antworten anpassen |
| Viewer sieht keinen Assistenten | Rolle reicht nicht | Editor- oder Owner-Rolle anfordern |

## Geplante Erweiterungen

- **Referenz-Bandbreiten (Level 4):** eine eigene, mit echten Kostendaten
  wachsende Tabelle von CHF/Einheit-Bandbreiten als belastbarere
  Plausibilitätsquelle.
- **Live-Websuche (Level 5):** bewusst zurückgestellt (langsam, unzuverlässige
  Quellen, selten autoritativ).

## Verwandte Funktionen

- [Kostenpositionen](./kosten.md)
- [eBKP-H-Katalog](./ebkp.md)
- [Budget & Reserve](./budget.md)
- [Audit-Protokoll](./audit.md)
