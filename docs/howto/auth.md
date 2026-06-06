# How-To: Anmeldung, Einladung & Passwort

_Eingeführt mit Version: 0.2.0_

## Aufgabe

Diese Anleitung beschreibt, wie sich Familienmitglieder bei Reno-Budget
anmelden, wie ein Administrator neue Personen einlädt und wie ein vergessenes
Passwort zurückgesetzt wird.

## Voraussetzungen

- Reno-Budget muss laufen (lokal: `docker compose -f deploy/docker-compose.yml up`).
- Für Einladungen: ein Konto mit der Rolle **Administrator** (in v0.2.0 = `is_superuser`).
- Für versendete E-Mails: SMTP-Konfiguration in `deploy/.env`
  (`RENO_SMTP_HOST`, `…_PORT`, `…_USER`, `…_PASSWORD`, `…_FROM`).
  Solange kein SMTP konfiguriert ist, werden E-Mails *nicht* versendet —
  die Einladungs-API gibt den Token im Entwicklungsmodus direkt zurück.

## Erstes Konto anlegen (Bootstrap)

In v0.2.0 gibt es noch keine UI für das erste Admin-Konto. Das erste
Administrator-Konto wird einmalig direkt in der Datenbank angelegt:

```bash
docker compose -f deploy/docker-compose.yml exec api python -c "
import asyncio, uuid
from app.core.db import SessionLocal
from app.core.security import hash_password
from app.models.user import User

async def main():
    async with SessionLocal() as s:
        s.add(User(
            id=uuid.uuid4(),
            email='admin@example.ch',
            display_name='Admin',
            password_hash=hash_password('IhrSicheresPasswort12!'),
            is_active=True,
            is_superuser=True,
        ))
        await s.commit()
asyncio.run(main())
"
```

## Schritt-für-Schritt

### Anmelden

1. Browser öffnen, App-URL aufrufen.
2. Sie werden automatisch auf **„Anmelden“** weitergeleitet.
3. **E-Mail** und **Passwort** eingeben → Schaltfläche **„Anmelden“**.
4. Bei Erfolg landen Sie auf der Startseite und sind eingeloggt.

### Familienmitglied einladen (nur Administrator)

1. Als Administrator anmelden.
2. Aktuell (Phase 1) erfolgt die Einladung per API-Aufruf — eine Admin-Oberfläche
   folgt in Phase 2:
   ```bash
   curl -X POST https://reno.example.ch/api/v1/auth/invitations \
     -H "Authorization: Bearer <ihr access token>" \
     -H "Content-Type: application/json" \
     -d '{"email":"cousine@example.ch"}'
   ```
3. Die eingeladene Person erhält eine E-Mail mit einem Einladungslink
   (Form: `https://reno.example.ch/invite/<token>`).
4. Sie öffnet den Link, gibt einen **Namen** und ein **Passwort** ein
   (mindestens 12 Zeichen, mind. drei Zeichenklassen) und klickt auf
   **„Konto erstellen“**.
5. Sie wird automatisch eingeloggt.

> Der Einladungslink ist **7 Tage** gültig und kann nur einmal verwendet werden.

### Passwort zurücksetzen

1. Auf der Anmeldeseite **„Passwort vergessen?“** anklicken.
2. E-Mail-Adresse eingeben → **„Link anfordern“**.
3. (Wenn die Adresse bei uns registriert ist:) E-Mail mit Reset-Link erhalten.
   Aus Sicherheitsgründen zeigt die UI immer dieselbe Bestätigung an,
   unabhängig davon, ob das Konto existiert.
4. Link öffnen (Form: `…/passwort-zuruecksetzen/<token>`),
   neues Passwort eingeben → **„Passwort speichern“**.
5. Sie werden auf die Anmeldeseite weitergeleitet und können sich
   mit dem neuen Passwort einloggen.

> Reset-Links sind **1 Stunde** gültig und können nur einmal verwendet
> werden. Ein Reset widerruft alle bestehenden Sitzungen (Sie müssen sich
> überall neu anmelden).

### Abmelden

Klick auf **„Abmelden“** auf der Startseite. Der Refresh-Cookie wird
serverseitig revoziert und lokal entfernt.

## Sicherheits-Hintergrund

- Passwörter werden mit **Argon2id** gespeichert (nie im Klartext).
- Refresh-Token sind HttpOnly-Cookies; der Server speichert nur den
  SHA-256-Hash. Bei jedem Refresh wird der Token rotiert.
- **Replay-Erkennung:** Wird ein bereits eingelöster Refresh-Token erneut
  verwendet, werden alle Sitzungen der/des Benutzer*in widerrufen.
- **Brute-Force-Schutz:** Nach 5 fehlgeschlagenen Anmeldeversuchen wird das
  Konto 15 Minuten gesperrt. Login- und Reset-Endpunkte sind zusätzlich
  pro IP rate-limited.
- **CSRF-Schutz:** Cookie-basierte Endpunkte (`/refresh`, `/logout`)
  verlangen ein passendes `X-CSRF-Token`-Header (Double-Submit-Cookie).
- Passwort-Anforderungen: 12–128 Zeichen, mindestens drei der vier
  Zeichenklassen (Kleinbuchstaben, Grossbuchstaben, Ziffern, Sonderzeichen).

## Häufige Probleme

| Symptom | Ursache | Abhilfe |
|---------|---------|---------|
| „E-Mail oder Passwort ungültig“ | Falsches Passwort oder unbekannte Adresse | Eingabe prüfen. Aus Sicherheitsgründen zeigt das System bewusst nicht an, welcher Teil falsch war. |
| „Konto vorübergehend gesperrt“ | 5 falsche Anmeldeversuche in Folge | 15 Minuten warten oder Administrator bitten, das Konto zurückzusetzen. |
| „Zu viele Versuche“ | Zu viele Anfragen von der gleichen IP | Kurz warten und erneut versuchen. |
| „Einladungslink ist ungültig oder abgelaufen“ | Link >7 Tage alt, bereits eingelöst oder revoziert | Neue Einladung anfordern. |
| „Reset-Link ist ungültig …“ | Link >1 Stunde alt oder bereits verwendet | Neuen Reset-Link anfordern. |

## Verwandte Funktionen

- _(noch keine — Objekte/Rollen folgen in Version 0.3.0)_
