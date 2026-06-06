# How-To: Budget, Zeitachse und Reserveplanung

_Eingeführt mit Version: 0.5.0_

## Aufgabe

Diese Anleitung erklärt, wie Sie pro Objekt eine **Renovations-Zeitachse**
und einen **Reserveplan** (Soll-Beitrag pro Monat, Jahr oder als Einmal­einlage)
sehen — und wie Sie unter `/finanzen` einen objekt­übergreifenden Überblick
über alle Objekte erhalten, in denen Sie Mitglied sind.

Es gibt **keine** separate Budget-Tabelle: Alle Aggregate werden direkt aus
den Kostenpositionen abgeleitet. Eine Position zählt zum „Ist“, wenn sie ein
`actual_date` hat (das Jahr dieses Datums bestimmt den Bucket).

## Voraussetzungen

- Mindestens Rolle **Viewer** auf dem Objekt (für `/objekte/:id/budget`).
- Für die Bearbeitung der Reserve-Einstellungen (Inflationsrate, Beitrags-Modus,
  initiale Reserve) ist die Rolle **Owner** erforderlich.
- Mindestens eine Kostenposition mit `planned_amount_chf` und `planned_year`,
  damit die Zeitachse und der Reserveplan etwas anzeigen.

## Schritt-für-Schritt

### Per-Objekt-Budget öffnen

1. Objektliste → Objekt anklicken.
2. Im Objekt-Detail oben auf **Budget** klicken.
3. Sie sehen:
   - **Reserve-Panel** mit Beitrags-Modus, Inflationsrate, initialer Reserve
     und dem berechneten Soll-Beitrag.
   - **Zeitachsen-Diagramm** mit einem Balken pro Jahr (Plan vs. Ist).
   - **Aufschlüsselungen** nach eBKP-H-Gruppe, Einheit, Status und Priorität.

### Reserve-Einstellungen ändern (Owner)

1. Im Reserve-Panel:
   - **Beitrags-Modus** wählen: `monthly` / `yearly` / `lump-sum`.
   - **Inflationsrate** (%) eingeben (`0` deaktiviert die Aufzinsung).
   - **Initiale Reserve** in CHF eingeben (wird vom Soll abgezogen).
2. **Speichern** klicken — die Zeitachse und der Reserveplan werden
   automatisch neu berechnet.

### Inflation toggeln

In der Zeitachse können Sie zwischen **nominal** (rohe Plan-Beträge) und
**inflationiert** (Plan-Betrag × `(1 + rate)^Jahre`) umschalten. Die API
akzeptiert dafür den Query-Parameter `?inflated=false`.

### Cross-Objekt-Überblick (`/finanzen`)

1. Top-Navigation → **Finanzen** anklicken.
2. Sie sehen eine Zeile pro Objekt, an dem Sie Mitglied sind:
   - **Geplant (inflationiert)** und **Ist** in CHF.
   - **Soll pro Jahr**, abgeleitet aus Plan minus Reserve, geteilt durch
     den Planungshorizont des Objekts.
   - **Rolle** (`OWNER` / `EDITOR` / `VIEWER`).
   - Badge **„anteilig“**, falls Sie ein gescoptes Mitglied sind — die
     Zahlen sind dann auf Ihren Anteil pro-ratiert.

## Wie wird gerechnet?

**Pro-Rating bei Scope.** Owner und nicht gescopte Editor/Viewer sehen die
vollen Beträge. Ein gescopter Editor/Viewer sieht jede Position multipliziert
mit `Σ share_permille(eigene Einheiten) / 1000` — eine 400‰-Allokation
ergibt also 40 % des Plan-Betrags.

**Inflation.** Für einen Plan-Betrag im Jahr `Y` gilt:
`inflated = planned × (1 + rate)^(Y − current_year)`. Ist `Y ≤ current_year`,
ist `inflated = planned`.

**Soll-Beitrag.** `required_total = max(0, Σ planned_inflated − initial_reserve)`,
verteilt auf `planning_horizon_years`. Daraus folgen
`per_year = required_total / horizon` und `per_month = per_year / 12`. Für
den Modus **lump-sum** zeigt das System pro Plan-Jahr den jeweils nötigen
Einmal­betrag.

**Status-Filter.** In den Soll-Beitrag fliessen Positionen mit Status
`IDEA`, `PLANNED` und `IN_PROGRESS` ein. `COMPLETED` zählt nur dann zum
Ist, wenn ein `actual_date` gesetzt ist. `CANCELLED` wird komplett ignoriert.

## Häufige Probleme

| Symptom | Ursache | Abhilfe |
|---------|---------|---------|
| Zeitachse leer | Keine Position mit `planned_year` und `planned_amount_chf` | Mindestens eine Plan-Position anlegen |
| Soll-Beitrag = 0 | Initiale Reserve ≥ Gesamt-Plan (inflationiert) | Reserve oder Plan-Positionen prüfen |
| Andere Werte als bei Owner | Sie sind als Scoped-Editor/Viewer eingetragen | Per-Rating ist gewollt, siehe oben |
| 403 beim Speichern | Inflation/Reserve/Modus benötigen Owner-Rolle | Anfrage von einem Owner ausführen lassen |
| Zahlen weichen vom Excel-Export ab | Excel-Rundung weicht von Server-Rundung ab | Beträge werden serverseitig auf 2 Nachkommastellen (Half-Up) gerundet — das ist verbindlich |

## Verwandte Funktionen

- [Kostenpositionen anlegen](kosten.md) — Voraussetzung für sinnvolle Aggregate.
- [eBKP-H Codes](ebkp.md) — die Aufschlüsselung nach „Hauptgruppe“ nutzt die
  erste Ebene des eBKP-H-Katalogs.
- [Objekte & RBAC](rbac.md) — wie Scope-Beschränkungen die Pro-Rating-Logik
  steuern.

## API-Endpunkte (für Entwickler)

- `GET /api/v1/objects/{id}/budget/timeline?inflated=true|false`
- `GET /api/v1/objects/{id}/budget/reserve`
- `PATCH /api/v1/objects/{id}` mit `{contribution_mode, inflation_rate_percent, initial_reserve_chf, planning_horizon_years}`
- `GET /api/v1/finances/overview`

Alle Endpunkte erfordern ein gültiges Access-Token; PATCH-Mutationen
zusätzlich den CSRF-Header. Beträge werden als Decimal-String serialisiert.
