export const de = {
  app: {
    title: "Reno-Budget",
    subtitle: "Renovations- und Unterhaltskosten für Liegenschaften",
    version: "Version",
  },
  auth: {
    login: {
      title: "Anmelden",
      email: "E-Mail",
      password: "Passwort",
      submit: "Anmelden",
      forgot: "Passwort vergessen?",
      errorGeneric: "Anmeldung fehlgeschlagen. Bitte E-Mail und Passwort prüfen.",
      errorLocked: "Konto vorübergehend gesperrt. Bitte später erneut versuchen.",
      errorInactive: "Konto deaktiviert. Bitte Administrator kontaktieren.",
      errorRateLimited: "Zu viele Versuche. Bitte kurz warten und erneut versuchen.",
    },
    logout: "Abmelden",
    invite: {
      title: "Einladung annehmen",
      displayName: "Name",
      password: "Passwort wählen",
      passwordHint: "Mindestens 12 Zeichen; Kombination aus Buchstaben, Ziffern und Sonderzeichen.",
      submit: "Konto erstellen",
      errorInvalid: "Einladungslink ist ungültig oder abgelaufen.",
      errorConflict: "Diese E-Mail ist bereits registriert.",
    },
    reset: {
      requestTitle: "Passwort zurücksetzen",
      requestSubmit: "Link anfordern",
      requestSent:
        "Wenn die E-Mail-Adresse bei uns registriert ist, erhalten Sie in Kürze einen Link.",
      confirmTitle: "Neues Passwort vergeben",
      newPassword: "Neues Passwort",
      confirmSubmit: "Passwort speichern",
      confirmSuccess: "Passwort gespeichert. Sie können sich nun anmelden.",
      errorInvalid: "Reset-Link ist ungültig, abgelaufen oder bereits verwendet.",
    },
    me: {
      greeting: "Angemeldet als {{name}}",
    },
  },
  common: {
    loading: "Wird geladen…",
    error: "Es ist ein Fehler aufgetreten.",
    submitting: "Wird gesendet…",
  },
} as const;

export type TranslationKeys = typeof de;
