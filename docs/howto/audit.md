# How-To: Audit-Log (Verlauf)

_Eingeführt mit Version: 0.8.0_

## Aufgabe

Diese Anleitung erklärt, wie Sie als **Eigentümer** den Aktivitätsverlauf
eines Objekts einsehen und wie **Administratoren** das globale Audit-Log
nutzen, um Aktionen über alle Objekte hinweg nachzuvollziehen.

Das Audit-Log ist **anhängend**: Einträge werden nur erzeugt, nie verändert
oder gelöscht (die Worker-Phase 9 ergänzt eine optionale Aufräumstrategie).

## Voraussetzungen

- Für `/objekte/:id/audit`: Rolle **Eigentümer (Owner)** auf dem Objekt.
- Für `/admin/audit`: **Superuser**-Flag auf dem Benutzerkonto.

## Schritt-für-Schritt

### Verlauf eines Objekts ansehen

1. Objektliste → Objekt anklicken.
2. Im Reiterband oben **„Verlauf"** anklicken.
3. Sie sehen die letzten 50 Einträge, neueste zuerst:
   - **Zeit** — wann (Lokalzeit Browser)
   - **Benutzer** — E-Mail des Akteurs (auch wenn dieser später gelöscht
     wurde — der Wert wird beim Schreiben festgehalten)
   - **Aktion** — verb-noun-Kürzel (z. B. `cost_item.create`),
     übersetzt in eine lesbare deutsche Beschriftung
   - **Beschreibung** — eine Zeile, die den Vorgang zusammenfasst
4. Ist der Verlauf länger, **„Weitere laden"** anklicken — die App lädt
   die nächste Seite über Cursor-Paginierung. Die Sortierung bleibt
   stabil, auch wenn parallel neue Einträge entstehen.

### Globales Log (Administrator)

1. In der Top-Navigation: **Audit-Log** anklicken (nur sichtbar mit
   Superuser-Flag).
2. Gleiche Tabelle wie pro Objekt, jedoch über **alle Objekte und alle
   Aktionen** hinweg.

## Was wird protokolliert?

| Modul              | Aktionen                                                                 |
|--------------------|--------------------------------------------------------------------------|
| Anmeldung          | `auth.login`, `auth.password_reset_request`, `auth.password_reset_confirm`, `auth.invitation_accept` |
| Objekte            | `object.create`, `object.update`, `object.delete`, `object.units_replace` |
| Mitgliedschaften   | `membership.grant`, `membership.update`, `membership.revoke`             |
| Kostenpositionen   | `cost_item.create`, `cost_item.update`, `cost_item.delete`               |
| Anhänge            | `attachment.upload`, `attachment.delete`                                 |
| Reserve / Renofond | `reserve_contribution.create`, `reserve_contribution.delete`             |
| Stammdaten         | `bkp_code.create` (nur Administrator)                                    |

**Nicht protokolliert** werden Lese-Endpunkte (`GET …`), da sie keine
Datenänderung verursachen.

## Was steht in einem Eintrag?

- `actor_user_id`, `actor_email` (denormalisiert)
- `object_id` (für Objekt-bezogene Filter)
- `target_type` + `target_id` (z. B. `cost_item` + UUID)
- `summary` (1-Zeiler Deutsch)
- `payload` (optional, strukturierter Diff; bewusst klein gehalten)
- `ip_address`, `user_agent` (aus dem Request)
- `created_at` (UTC, indexiert)

## Aufbewahrung

Aktuell **unbegrenzt**. Die Tabelle ist über `(created_at)` und
`(object_id, created_at)` indexiert, so dass die Cursor-Paginierung auch
über grosse Zeiträume schnell bleibt. Die Worker-Phase 9 wird optional
einen Rotations-Job ergänzen.

## Häufige Probleme

| Symptom | Ursache | Abhilfe |
|---------|---------|---------|
| 403 beim Aufruf von `/objekte/:id/audit` | Nicht Eigentümer auf dem Objekt | Owner-Mitgliedschaft anfragen oder mit Owner-Account anmelden |
| Reiter „Verlauf" sichtbar, aber Liste leer | Noch keine Mutationen seit Phase 7 erfolgt | Erst nach Ereignis (z. B. neue Kostenposition) erscheint ein Eintrag |
| Aktion zeigt rohen Verb-Code statt deutscher Bezeichnung | Übersetzung fehlt im i18n-Katalog | `audit.actions.<verb>` in `src/i18n/locales/de.ts` ergänzen |
| Globales Log gibt 403 | Kein Superuser | Administrator bitten, das Flag zu setzen (`is_superuser`) |

## Verwandte Funktionen

- [Objekte & RBAC](rbac.md) — wer welche Aktionen überhaupt ausführen darf
- [Anhänge](uploads.md) — Upload-/Delete-Ereignisse erscheinen im Log
- [Renofond](renofond.md) — Einzahlungs-Ereignisse erscheinen im Log

## API-Endpunkte (für Entwickler)

- `GET /api/v1/objects/{id}/audit?limit=50&before=<cursor>` — Owner-only,
  Keyset-Paginierung, Antwort enthält `next_before` (null = Ende).
- `GET /api/v1/audit?limit=50&before=<cursor>` — Superuser-only, globaler
  Feed.

Beide Endpunkte geben `403` für Unbefugte und `404`, falls das Objekt
nicht existiert oder der Aufrufer nicht Mitglied ist (analog zur Budget-
und Renofond-Policy).
