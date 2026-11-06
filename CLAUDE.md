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
- Windows ist immer Desktop-App: kein Browser-Ersatz (`desktop._window_failed` → Dialog + `logs/fenster-fehler.txt`).
  Installer: `packaging/windows/sh-tunebridge.iss` (AppId = `winapp.APP_ID`, nie ändern), gebaut mit
  `scripts/build-windows-setup.ps1`; CI installiert still und verlangt `/api/window` → `shown`.
- AppImage-Update: alte Datei nie löschen, sondern durch Verweis auf die neue ersetzen (`update._keep_old_path`).
- Der Code des Annahme-Servers ist privat – keine Server-Interna und keine lokalen Pfade in dieses öffentliche Repo.

## Release-Regeln (vereinbart 2026-11-03)
1. **Kein Release ohne grünen Probelauf:** vorher `gh workflow run build --ref main` – Linux, Windows und macOS
   inkl. Rauchtest (Server und App-Fenster) grün. Rot = nichts veröffentlichen.
2. **Windows-VM-Pflicht:** Änderungen an Fenster, Updater, Begleiter oder Paketbau vor dem Release zusätzlich in der
   lokalen Windows-VM testen.
3. **Updater-Echttest:** jede Updater-Änderung mit einem echten Update von der vorigen veröffentlichten Version
   prüfen (abgeschottetes HOME/Datenverzeichnis). Dateien, die der Nutzer starten könnte, nie löschen.
4. **Kaputtes Release:** sofort Hinweis im GitHub-Release setzen und schnellstmöglich eine reparierte Version
   nachschieben. Release-Dateien oder Tags nur nach ausdrücklicher Zustimmung entfernen.
5. **Server ausrollen** nur auf Ansage; vorher Sicherung auf dem Server, danach Health-Check, alles protokollieren.
6. **Gemeinschafts-Genre-Datenbank** nur auf Ansage („Genre-DB aktualisieren“) holen, bauen, veröffentlichen.
7. **Pushen und Releases** nur auf Ansage („pushe und baue zu github“) – auch reine Doku-Änderungen.
8. **Versionen:** Fehlerkorrektur = letzte Stelle (0.6.x), neue Funktion = mittlere (0.x.0).
   Jedes Release bekommt einen Eintrag in `CHANGELOG.md`.

## Android (vereinbart 2026-11-06)
- Native App (Kotlin + Jetpack Compose) im Ordner `android/` dieses Repos; APK in denselben GitHub-Releases,
  Update über die App selbst (signiertes Manifest wie am Desktop). Kein Google Play.
- Gemeinsame Daten (Genre-Baum u. a.) werden aus dem Python-Code als JSON erzeugt, nicht abgeschrieben.
- Formate und Server-Schnittstellen (Teilen, Verzeichnis, Gemeinschaft, Sicherung) bleiben mit dem Desktop kompatibel.
- **Android-Keystore** nie ins Repo oder in die CI; sofort offline sichern (Verlust = keine Updates mehr möglich).
- **Keine** Google-Play-Dienste, kein Firebase, keine Analyse-, Absturz- oder Werbe-SDKs. Nur nötige Berechtigungen,
  jede in DATENSCHUTZ.md; Mikrofon erst beim ersten Klick auf Erkennen, im Hintergrund nur mit sichtbarer Benachrichtigung.
- **Desktop darf nicht leiden:** Desktop-Tests und CI (Linux/Windows/macOS) müssen grün bleiben.
- **Vor jedem Android-Release** Test auf einem echten Handy per adb; Emulator nur ergänzend, GPU-Einstellungen nie ändern.
- Android-SDK nur im Docker-Build-Container, kein Eingriff ins System.
