# How-To — eBKP-H-Katalog

Eingeführt mit Version 0.4.0.

## Aufgabe

Sie möchten Kostenpositionen nach dem Schweizer Standard **eBKP-H**
(Element­kosten­gliederung Hochbau, CRB/SIA) klassifizieren. Dies erlaubt
später konsolidierte Auswertungen pro Bauteilgruppe und ist Voraussetzung
für künftige Ausschreibungs-Exporte (Phase 8).

## Voraussetzungen

- Sie sind als Benutzer:in angemeldet (siehe [auth.md](./auth.md)).
- Für das Anlegen eigener Codes benötigen Sie Administrator-Rechte
  (Superuser).

## Was ist im Katalog enthalten?

Der mitgelieferte Katalog deckt die ersten beiden Ebenen von eBKP-H ab:

- **Hauptgruppen** (Ebene 1): einbuchstabig (A, B, C, …, J, V, W, Y, Z).
- **Elementgruppen** (Ebene 2): zweistellig, z. B. `C01` (Bodenplatte),
  `D05` (Heizungsanlage), `G02` (Bodenbelag).

Insgesamt sind rund 75 Codes vorinstalliert. Diese sind als
"Seed-Daten" markiert und werden bei Updates nicht überschrieben.

## Schritt-für-Schritt: Code beim Erfassen einer Kostenposition auswählen

1. Öffnen Sie ein Objekt und klicken Sie auf **Kosten**.
2. Klicken Sie auf **Neue Kostenposition**.
3. Im Feld **eBKP-H-Code** öffnen Sie den Baum-Auswahldialog.
4. Suchen Sie nach Code (z. B. `C01`) oder Bezeichnung (z. B. "Heizung").
   Die Baumstruktur klappt automatisch zu den Treffern auf.
5. Wählen Sie einen Eintrag aus. Die Hauptgruppe alleine ist erlaubt, eine
   Elementgruppe (Ebene 2) ist aber genauer.

## Schritt-für-Schritt: Eigenen Code anlegen (nur Administrator)

Wenn Ihr Anwendungsfall einen Code benötigt, der nicht im Standard enthalten
ist (z. B. ein hauseigener Untergliederungs-Code auf Ebene 3), kann ein
Administrator ihn ergänzen:

1. Melden Sie sich als Administrator an.
2. Senden Sie einen `POST /api/v1/bkp-codes` mit den Feldern `code`,
   `parent_code`, `level` und `label_de`. (Eine Admin-UI folgt in
   Phase 12.)
3. Der Code wird als `is_seed=false` markiert und steht ab sofort in der
   Auswahl zur Verfügung.

## Häufige Probleme

- **"Code nicht gefunden"** beim Anlegen einer Kostenposition: prüfen Sie
  Gross-/Kleinschreibung. eBKP-H-Codes sind grossgeschrieben (`C01`, nicht
  `c01`).
- **"Elternknoten existiert nicht"** beim Anlegen eines eigenen Codes:
  Der `parent_code` muss bereits im Katalog vorhanden sein.

## Verwandte Funktionen

- [Kostenpositionen erfassen](./kosten.md)
- [Objekte & Einheiten verwalten](./objekte.md)
