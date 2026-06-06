# How-To: Renofond — Projektion und Einzahlungen

_Eingeführt mit Version: 0.6.0_

## Aufgabe

Diese Anleitung erklärt, wie Sie pro Objekt eine **Jahresprojektion** des
Renofonds (= renovationsspezifische Reserve) sehen, wie Sie **effektive
Einzahlungen** erfassen und wie das System **Unterdeckungsjahre** sichtbar
macht.

Die Soll-Beiträge selbst (pro Monat / Jahr / Einmalbetrag) werden auf der
Budget-Seite berechnet (siehe [budget.md](./budget.md)). Phase 5 ergänzt
die Zeitperspektive: Wie entwickelt sich der Saldo des Renofonds Jahr für
Jahr, und in welchen Jahren reicht er nicht?

## Voraussetzungen

- Mindestens Rolle **Viewer** auf dem Objekt (für die Projektion und das
  Lesen der Einzahlungen).
- Für das Erfassen oder Löschen von **effektiven Einzahlungen** ist die
  Rolle **Owner** erforderlich.
- Mindestens eine Kostenposition mit `planned_amount_chf` und
  `planned_year`, damit die Projektion einen Aufwand modellieren kann.

## Schritt-für-Schritt

### Renofond-Seite öffnen

1. Objektliste → Objekt anklicken → Tab **Budget**.
2. Oben rechts auf **Renofond** klicken.
3. Sie sehen:
   - Eine **rote Banner-Warnung**, falls die Projektion in mindestens
     einem Jahr ein negatives Saldo zeigt.
   - Ein **Bilanzverlauf-Diagramm** (SVG): pro Planungsjahr ein Balken
     für den Saldo am Jahresende; ein hellerer Balken im Hintergrund
     visualisiert den kumulierten geplanten Aufwand.
   - Die Tabelle **Effektive Einzahlungen** mit allen erfassten
     Deposits.

### Einzahlung erfassen (Owner)

1. Im Formular unterhalb der Tabelle Jahr, Betrag (CHF) und optional
   eine Notiz eingeben.
2. **Speichern** klicken — die Projektion wird automatisch neu
   berechnet und der neue Eintrag erscheint in der Tabelle.

### Einzahlung löschen (Owner)

1. In der Tabelle bei der gewünschten Zeile auf **Löschen** klicken.
2. Die Projektion aktualisiert sich automatisch.

## Wie wird gerechnet?

Die Projektion läuft Jahr für Jahr über den Planungshorizont des Objekts
(`current_year .. current_year + planning_horizon_years`):

```
balance[Y0 - 1] = initial_reserve_chf
balance[Y] = balance[Y-1]
           + required_per_year_chf      # Soll-Einlage aus Phase 4
           + Σ effektive_einzahlungen(Y)
           - Σ inflationierter_geplanter_aufwand(Y)
is_underfunded[Y] = balance[Y] < 0
```

Die Zeile **unterdeckungsjahre** im API-Response (Banner im UI) enthält
jedes Jahr, in dem `balance[Y] < 0` — zusammen mit dem `shortfall_chf`
(= `-balance[Y]`).

**Pro-Rating bei Scope.** Gescopte Editor/Viewer sehen Saldo, Plan,
Soll-Einlage und effektive Einzahlungen jeweils auf ihren Anteil
reduziert — analog zur Budget-Seite (`Σ share_permille / 1000`).

**Inflation.** Der geplante Aufwand fliesst mit dem inflations­bereinigten
Betrag aus Phase 4 ein. Die Soll-Einlage ist nominal (Inflation ist im
Aufwand bereits eingepreist).

## Häufige Probleme

| Symptom | Ursache | Abhilfe |
|---------|---------|---------|
| Banner bleibt rot | Saldo wird in mindestens einem Jahr negativ | Mehr Einzahlungen, Planpositionen verschieben oder initiale Reserve erhöhen |
| Eigene Einzahlung fehlt in der Tabelle | Pro-Rating verbirgt fremde Anteile bei gescopten Mitgliedern | Mit dem Owner abgleichen; Wertquote prüfen |
| 403 beim Speichern | Einzahlung erfordert Owner-Rolle | Anfrage von einem Owner ausführen lassen |
| Saldo dreht nicht ins Plus | Soll-Einlage zu tief, weil initiale Reserve den Plan deckt | Auf Budget-Seite Reserve und Plan-Positionen prüfen |
| Beträge weichen vom Excel-Export ab | Server rundet auf 2 Nachkommastellen (Half-Up) | Server-Rundung ist verbindlich |

## Verwandte Funktionen

- [Budget, Zeitachse und Reserveplanung](budget.md) — Soll-Beiträge
  und Reserve-Einstellungen werden dort konfiguriert.
- [Kostenpositionen anlegen](kosten.md) — Voraussetzung für sinnvolle
  Projektionen.
- [Objekte & RBAC](rbac.md) — Pro-Rating-Logik.

## API-Endpunkte (für Entwickler)

- `GET /api/v1/objects/{id}/renofond/projection`
- `GET /api/v1/objects/{id}/renofond/contributions`
- `POST /api/v1/objects/{id}/renofond/contributions` (Owner + CSRF)
- `DELETE /api/v1/objects/{id}/renofond/contributions/{contribution_id}`
  (Owner + CSRF)

Alle Endpunkte erfordern ein gültiges Access-Token; Mutationen
zusätzlich den CSRF-Header. Beträge werden als Decimal-String
serialisiert.
