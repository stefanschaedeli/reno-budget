# How-To — Rollen & Berechtigungen (RBAC)

Eingeführt mit Version 0.3.0.

## Aufgabe

Sie möchten verstehen, wer in Reno-Budget was darf, und wie Sie Familien-
oder Verwaltungsmitglieder kontrolliert auf einzelne Liegenschaften und
Stockwerk-Einheiten Zugriff geben.

## Konzept

Berechtigungen sind in Reno-Budget immer **pro Objekt** organisiert. Eine
Person ist nicht "Admin der Anwendung", sondern "OWNER von Haus X, EDITOR von
Haus Y, kein Zugriff auf Haus Z".

Pro Objekt gibt es drei Rollen:

| Rolle    | Bedeutung                                                                                  |
|----------|--------------------------------------------------------------------------------------------|
| OWNER    | Volle Kontrolle: Objekt löschen, Einheiten ersetzen, Mitglieder verwalten, alles ansehen.  |
| EDITOR   | Daten lesen und (ab Phase 3) Kostenpositionen pflegen — eingeschränkt auf eigene Einheiten. |
| VIEWER   | Nur Leserechte — eingeschränkt auf eigene Einheiten.                                       |

Zusätzlich kann eine EDITOR- oder VIEWER-Rolle auf **bestimmte Einheiten
beschränkt** werden ("Unit Scope"). Ohne Scope ist die Mitgliedschaft
"unbeschränkt", d. h. der/die Eingeladene sieht alle Einheiten.

Wichtige Regeln:

- **OWNER ignoriert Unit Scope.** Eine OWNER-Mitgliedschaft sieht immer alle
  Einheiten — selbst wenn versehentlich Scope-Einträge existieren würden.
- **Keine Mitgliedschaft = 404.** Wer keine Mitgliedschaft an einem Objekt
  hat, erhält "Objekt nicht gefunden", nicht "Zugriff verweigert". So lässt
  sich nicht herausfinden, welche anderen Objekte in der App existieren.
- **Mindestens ein:e OWNER pro Objekt.** Der letzte OWNER kann nicht entfernt
  oder herabgestuft werden, sonst wäre niemand mehr in der Lage, das Objekt
  zu verwalten.
- **Administratoren (`is_superuser`) erben keinen Daten-Zugriff.** Sie können
  Benutzerkonten verwalten und den eBKP-H-Katalog pflegen, sehen aber keine
  Kostenpositionen oder Einheiten, sofern sie nicht explizit Mitglied sind.
  Das ist bewusst so, damit Administratoren versehentlich keine Finanzdaten
  fremder Familien einsehen können.

## Voraussetzungen

- Sie sind OWNER des betreffenden Objekts.
- Die einzuladende Person ist bekannt mit E-Mail-Adresse.

## Schritt-für-Schritt: jemanden mit eingeschränktem Scope einladen

1. Notieren Sie die UUIDs der Einheiten, auf die der Scope beschränkt sein
   soll (zukünftige UI-Phase macht das per Mehrfachauswahl).
2. Senden Sie als OWNER:

   ```bash
   curl -X POST https://<host>/api/v1/objects/<object-id>/invitations \
     -H "Authorization: Bearer <access_token>" \
     -H "X-CSRF-Token: <csrf-cookie-wert>" \
     -H "Content-Type: application/json" \
     -b "reno_csrf=<csrf-cookie-wert>; reno_refresh=<refresh-cookie-wert>" \
     -d '{"email":"familie@example.ch","role":"editor","scope_unit_ids":["<u1>","<u2>"]}'
   ```

3. Der/Die Eingeladene erhält eine E-Mail (oder im Dev-/Test-Modus den Token
   in der API-Antwort) und folgt dem Link `/invite/<token>`, vergibt Name +
   Passwort. Beim Annehmen wird automatisch die Mitgliedschaft mit dem
   gewünschten Scope erstellt.

## Schritt-für-Schritt: Rolle ändern oder Scope erweitern

(API-only in Phase 2.)

```bash
curl -X PATCH https://<host>/api/v1/objects/<object-id>/members/<user-id> \
  -H "Authorization: Bearer <token>" -H "X-CSRF-Token: <csrf>" \
  -b "reno_csrf=<csrf>; reno_refresh=<refresh>" \
  -d '{"role":"owner"}'
```

Oder Scope-Listen ersetzen:

```bash
curl -X PATCH ... -d '{"scope_unit_ids":["<u1>"]}'
```

Eine leere Scope-Liste (`"scope_unit_ids": []`) macht die Mitgliedschaft
explizit **unbeschränkt** (alle Einheiten). Das ist Absicht: "kein Eintrag"
bedeutet "kein Filter", nicht "kein Zugriff".

## Mitglied entfernen

```bash
curl -X DELETE https://<host>/api/v1/objects/<object-id>/members/<user-id> \
  -H "Authorization: Bearer <token>" -H "X-CSRF-Token: <csrf>" \
  -b "reno_csrf=<csrf>; reno_refresh=<refresh>"
```

Das Entfernen scheitert mit HTTP 409 ("Letzter Eigentümer kann nicht entfernt
werden"), wenn es der einzige OWNER ist.

## Häufige Probleme

- **403 "Berechtigung für diese Aktion fehlt"** — Sie haben eine Rolle am
  Objekt, aber nicht die nötige Stufe (z. B. EDITOR möchte Objekt löschen).
- **404 "Objekt nicht gefunden"** — Sie haben keine Mitgliedschaft an diesem
  Objekt. Bitten Sie eine:n OWNER um Einladung.
- **409 "Letzter Eigentümer kann nicht entfernt werden"** — Befördern Sie
  zuerst ein anderes Mitglied zu OWNER.
- **400 "OWNER-Mitgliedschaft darf nicht unit-eingeschränkt sein"** —
  OWNERs haben immer Vollzugriff; ein Scope wäre wirkungslos und wird daher
  serverseitig abgelehnt.
- **400 "Einheiten gehören nicht zu diesem Objekt"** — eine angegebene
  Scope-Unit-ID gehört zu einem anderen Objekt. Korrekte IDs ermitteln Sie
  über `GET /api/v1/objects/<id>/units`.

## Verwandte Funktionen

- [objekte.md](./objekte.md) — Objekt und Einheiten anlegen.
- [auth.md](./auth.md) — Einladungs- und Anmeldeablauf.
