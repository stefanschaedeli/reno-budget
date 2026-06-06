# How-To — Objekte & Einheiten

Eingeführt mit Version 0.3.0.

## Aufgabe

Sie möchten ein Gebäude (eine "Liegenschaft" bzw. ein "Objekt") in Reno-Budget
anlegen, dessen Wohn-/Stockwerk-Einheiten erfassen und – bei
Stockwerkeigentum – die Wertquoten (in ‰) hinterlegen, damit spätere
Kostenpositionen anteilsmässig auf die Einheiten verteilt werden können.

## Voraussetzungen

- Sie sind als Benutzer:in angemeldet (siehe [auth.md](./auth.md)).
- Für ein Mehrfamilienhaus (Stockwerkeigentum) kennen Sie die Wertquoten der
  einzelnen Einheiten. Die Summe der Wertquoten muss exakt **1000‰** ergeben.

## Schritt-für-Schritt: Objekt anlegen

1. Klicken Sie auf der Startseite auf **Objekte**.
2. Klicken Sie oben rechts auf **Neues Objekt**.
3. Geben Sie eine **Bezeichnung** ein (z. B. "Haus Bahnhofstrasse 1").
4. Optional: **Adresse**, **Baujahr**.
5. Wählen Sie den **Typ**:
   - **Einfamilienhaus (EFH)** — es wird automatisch eine einzige Einheit mit
     1000‰ angelegt. Sie können sie nicht weiter aufteilen.
   - **Mehrfamilienhaus (MFH / Stockwerkeigentum)** — Sie definieren die
     einzelnen Einheiten manuell.
6. Erfassen Sie die Einheiten:
   - **Bezeichnung** (z. B. "EG", "1.OG", "DG"),
   - **Wertquote in ‰** (Permille, 0–1000),
   - optional **Fläche in m²**.
   - Die Summenanzeige unten am Editor wird **grün**, sobald die Wertquoten
     genau 1000‰ ergeben.
   - Mit **Einheit hinzufügen** ergänzen Sie weitere Zeilen,
     mit **Entfernen** löschen Sie eine Zeile (mindestens eine Einheit muss
     bleiben).
7. Klicken Sie auf **Objekt anlegen**. Sie werden automatisch **Eigentümer:in**
   (OWNER) des neuen Objekts.

## Schritt-für-Schritt: Objektdetails ansehen

Auf der Objekt-Liste klicken Sie auf den Namen eines Objekts, um das Detail zu
sehen. Aktuell (Phase 2) wird der Einheiten-Editor nur lesend angezeigt. Das
Bearbeiten einzelner Einheiten nach dem Anlegen ist Teil von Phase 3 (sobald
Kostenpositionen existieren, die auf Einheiten verweisen — vorher würde eine
Änderung der Einheiten-IDs Daten verlieren).

## Rollen und Sichtbarkeit (RBAC)

Pro Objekt gibt es drei Rollen mit absteigender Berechtigung:

| Rolle    | Darf …                                                                      |
|----------|-----------------------------------------------------------------------------|
| OWNER    | Objekt löschen, Einheiten ersetzen, Mitglieder einladen/entfernen/ändern    |
| EDITOR   | (ab Phase 3) Kostenpositionen erstellen und ändern im eigenen Scope         |
| VIEWER   | Objekt lesen, eigene Einheiten und (ab Phase 3) Kostenpositionen ansehen    |

Editoren und Viewer können zusätzlich auf bestimmte **Einheiten beschränkt**
("scoped") werden. Wer scoped ist, sieht nur die zugewiesenen Einheiten in
der Liste und (ab Phase 3) nur die Kostenpositionen, die mindestens eine
dieser Einheiten betreffen.

Wichtig: Wer **keine** Mitgliedschaft an einem Objekt hat, erhält **404 — nicht
gefunden** statt 403, um die Existenz fremder Objekte nicht preiszugeben.

## Mitglieder hinzufügen (Einladung an ein Objekt)

(Für Phase 2 nur über die API; die UI dafür folgt mit dem Mitglieder-Editor in
einer späteren Phase.)

Als OWNER können Sie über `POST /api/v1/objects/<id>/invitations` eine
Einladung versenden:

```json
{
  "email": "familie@example.ch",
  "role": "editor",
  "scope_unit_ids": ["<unit-uuid>", "<unit-uuid>"]
}
```

Der/Die Eingeladene erhält eine E-Mail mit Link und legt ein Konto an
(`/invite/<token>`). Beim Annehmen wird automatisch die Mitgliedschaft an
Ihrem Objekt erstellt — keine zweite Aktion nötig.

## Häufige Probleme

- **"Summe der Wertquoten muss 1000‰ ergeben"** — Korrigieren Sie eine oder
  mehrere Wertquoten, bis die Summenanzeige grün wird.
- **"Einfamilienhaus muss genau eine Einheit mit 1000‰ enthalten"** — Wechseln
  Sie den Typ auf "Mehrfamilienhaus" oder reduzieren Sie auf eine Einheit.
- **"Letzter Eigentümer kann nicht entfernt werden"** — Jedes Objekt braucht
  mindestens eine:n OWNER. Befördern Sie zuerst ein anderes Mitglied zu
  OWNER, bevor Sie die letzte OWNER-Mitgliedschaft entfernen.
- **404 statt Objektdetail** — Sie haben keine Mitgliedschaft an diesem
  Objekt. Bitten Sie eine:n OWNER um eine Einladung.

## Verwandte Funktionen

- [auth.md](./auth.md) — Anmeldung, Einladung, Passwort-Reset.
- (folgt) `kostenpositionen.md` — Kostenpositionen pro Objekt erfassen und
  auf Einheiten verteilen.
