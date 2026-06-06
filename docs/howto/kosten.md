# How-To — Kostenpositionen

Eingeführt mit Version 0.4.0.

## Aufgabe

Sie möchten geplante oder bereits ausgeführte Renovations- und
Unterhaltskosten zu einem Objekt erfassen, nach Bauteil ([eBKP-H](./ebkp.md))
klassifizieren und auf die einzelnen Einheiten verteilen.

## Voraussetzungen

- Sie sind als Benutzer:in mit Rolle **EDITOR** oder **OWNER** auf dem Objekt
  angemeldet (Rollen siehe [rbac.md](./rbac.md)).
- Das Objekt und seine Einheiten sind angelegt (siehe
  [objekte.md](./objekte.md)).

## Schritt-für-Schritt: Kostenposition anlegen

1. Öffnen Sie das Objekt und klicken Sie auf **Kosten**.
2. Klicken Sie auf **Neue Kostenposition**.
3. Erfassen Sie die Stammdaten:
   - **Titel** (Pflicht) — kurze Bezeichnung, z. B. "Heizungsersatz".
   - **eBKP-H-Code** (Pflicht) — über den Baum-Auswahldialog wählen.
   - **Status** — Idee / Geplant / In Arbeit / Abgeschlossen / Storniert.
   - **Priorität** — Tief / Mittel / Hoch / Dringend.
4. Erfassen Sie die finanziellen Angaben (mindestens eines der beiden ist
   Pflicht):
   - **Geplant CHF** und optional **Geplantes Jahr** — für die
     Renofond-Projektion (Phase 5).
   - **Effektiv CHF** und **Datum** — bei historischen / bereits
     bezahlten Posten.
5. Optional: **Lebensdauer (Jahre)**, **Garantie bis**.
6. Wählen Sie den **Verteilungs-Modus**:
   - **Gemeinsam** — die Kosten werden auf alle Einheiten verteilt. Per
     Voreinstellung anhand der Wertquoten; eine Übersteuerung pro Position
     ist möglich.
   - **Pro Einheit** — die Kosten betreffen nur ausgewählte Einheiten
     (z. B. Sanitärumbau in einer einzelnen Wohnung).
7. Im **Verteilungs-Editor** prüfen Sie, dass die Summe der Anteile
   exakt **1000‰** ergibt (Anzeige rechts oben). Mit der Schaltfläche
   **Standard (Wertquote)** stellen Sie die ursprüngliche Verteilung
   wieder her.
8. **Speichern**.

## Ansichten

- **Liste** — sortierbare Tabelle (Status, Priorität, Jahr, Beträge).
- **Board** — Kanban nach Status. Karten lassen sich per Drag-and-Drop
  zwischen Spalten verschieben; der Status wird sofort gespeichert.

## Filter

Über die Filterleiste lassen sich Status, Priorität, Jahr, Einheit,
Bauteilgruppe (eBKP-H-Präfix) und Titel-Suche kombinieren. Die Filter
sind in der URL kodiert — Sie können einen gefilterten Ausschnitt mit
anderen Familienmitgliedern teilen, indem Sie den Link kopieren.

## Sichtbarkeit & Berechtigungen

- **OWNER** sieht und ändert alle Positionen.
- **EDITOR** sieht und ändert Positionen im Rahmen seines Unit-Scopes
  (siehe [rbac.md](./rbac.md)).
- **VIEWER** kann lesen, aber nichts ändern oder löschen.
- Eingeschränkte EDITOR/VIEWER sehen eine "Gemeinsam"-Position nur, wenn
  mindestens eine ihrer Einheiten an der Verteilung beteiligt ist.

## Häufige Probleme

- **"Summe der Anteile muss 1000‰ ergeben"** — der Verteilungs-Editor zeigt
  die aktuelle Summe; korrigieren Sie die Werte oder klicken Sie auf
  **Standard (Wertquote)** zum Zurücksetzen.
- **"Mindestens ein Betrag (geplant oder effektiv) ist erforderlich"** —
  eine Kostenposition ohne Beträge ist nicht erlaubt. Tragen Sie wenigstens
  einen Schätzwert ein.
- **"Berechtigung für diese Aktion fehlt"** — Sie sind als VIEWER
  angemeldet oder ihre Rolle ist auf andere Einheiten beschränkt.

## Verwandte Funktionen

- [eBKP-H-Katalog](./ebkp.md)
- [Objekte & Einheiten verwalten](./objekte.md)
- [Rollen & Berechtigungen](./rbac.md)
