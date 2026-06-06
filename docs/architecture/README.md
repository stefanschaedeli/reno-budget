# Architektur

Dieses Verzeichnis dokumentiert die technische Architektur von Reno-Budget:
warum bestimmte Entscheidungen getroffen wurden, wie die Komponenten
zusammenhängen und wie sich das Sicherheitsmodell zusammensetzt.

## Inhalt

- [`adr/`](adr/) — Architecture Decision Records (eine Datei pro Entscheidung)
- [`security.md`](security.md) — Sicherheits-Baseline (folgt in Phase 1ff.)

## Master-Plan

Der vollständige, vom Auftraggeber genehmigte Implementierungsplan liegt
ausserhalb des Repos unter
`/Users/stefan/.claude/plans/i-like-to-start-drifting-cloud.md`
(Spiegel siehe `docs/superpowers/specs/2026-06-06-reno-budget-design.md`).

## Phasen-Übersicht

| Phase | Inhalt                                              | Tag     |
|-------|-----------------------------------------------------|---------|
| 0     | Scaffolding, Tooling, Docker-Skeleton, Healthchecks | v0.1.0  |
| 1     | Auth, Users, Invitations                            | v0.2.0  |
| 2     | Objekte, Einheiten, RBAC                            | v0.3.0  |
| 3     | eBKP-H Katalog, Kostenpositionen, Allocations       | v0.4.0  |
| 4     | Jahres-Budgets                                      | v0.5.0  |
| 5     | Erneuerungsfonds-Projektion                         | v0.6.0  |
| 6     | Datei-Uploads / Anhänge                             | v0.7.0  |
| 7     | Audit-Log-Viewer                                    | v0.8.0  |
| 8     | Exporte (XLSX, PDF, NPK-Stub)                       | v0.9.0  |
| 9     | Worker: Backups + Erinnerungs-Digests               | v0.10.0 |
| 10    | Hardening / Pen-Test / Doku-Review                  | v1.0.0  |
