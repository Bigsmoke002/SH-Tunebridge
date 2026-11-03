# Projektregeln SH-Tunebridge

## ⚠ Oberste Regel: EU-Datenschutz (DSGVO) und deutsches Recht
Höchstens Grauzone, nie klar rechtswidrig – niemand darf zu Schaden kommen. Siehe DATENSCHUTZ.md.
- Privacy by default: Daten bleiben lokal; keine Telemetrie, kein Tracking, keine externen Fonts/CDNs.
- Daten an Dritte nur, wenn nötig, offen dokumentiert (DATENSCHUTZ.md + Einstellungen → Datenschutz) und bei Audio nur nach Einwilligung.
- Einwilligungen **serverseitig** erzwingen (nicht nur in der Oberfläche), mit Tests (tests/test_privacy.py).
- Aufnahmen nie speichern. Mikrofon: § 201 StGB – Hinweis bleibt Pflicht.
- Lizenzen einhalten (Modell-Bedingungen vor Download bestätigen lassen; GPL-Bibliotheken beim Weitergeben beachten).
- Tabu: Kopierschutz umgehen, komplette Songs laden, fremde App-Tokens/Keys extrahieren, Daten anderer Personen sammeln.
- Neue Datenflüsse immer in DATENSCHUTZ.md und im Datenschutz-Bereich der App nachtragen.
- **Nur anonym und nur das Nötigste erheben.** Jede Erhebung einzeln abwählbar, Einwilligung beim ersten Start
  (Datenschutzerklärung + Senden an genau shtunebridge.bs002.de). Ohne Einwilligung wird nichts gesendet.
  Was technisch pseudonym ist, ehrlich so benennen.
- Logo (assets/logo/) und Name „SH-Tunebridge“ gehören Bigsmoke002 – nicht von der Lizenz umfasst.

## Technik
- Python 3.14, uv, FastAPI + pywebview (Qt), Vanilla-JS ohne Build-Schritt.
- Tests: `uv run pytest -q`. Releases nur signiert: `./scripts/release.sh X.Y.Z "Titel" "Punkt" …`.
- Ablauf Release, Windows-Test und Gemeinschafts-Genre-Datenbank: README.md › „Updates & Releases“; Änderungen in CHANGELOG.md.
- Tests nie gegen die echte Datenbank (`data/`): `tests/conftest.py` isoliert DATA/DB/Outbox/Schlüssel.
- Fenstersymbol je System: Linux `icon.svg`, Windows nur `icon.ico` (sonst Absturz), macOS aus dem Bundle.
- AppImage-Update: alte Datei nie löschen, sondern durch Verweis auf die neue ersetzen (`update._keep_old_path`).
- Der Code des Annahme-Servers ist privat – keine Server-Interna und keine lokalen Pfade in dieses öffentliche Repo.
