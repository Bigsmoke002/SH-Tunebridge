# Änderungen

Alle Versionen sind mit dem Release-Schlüssel signiert (siehe `src/tunebridge/release_signers`).
Der Updater installiert nur signierte Versionen.

## 0.7.0 – 2026-11-03
Playlists teilen, Dienste ohne Fachwissen einrichten, Datenexporte importieren.
- **Schranz** ist ein eigenes Subgenre (vorher unter Hard Techno versteckt); „Schranz“ im Titel/Künstlernamen zählt.
- **Dienste einrichten ohne Fachwissen:** Schritt-für-Schritt-Assistent für Spotify, YouTube, SoundCloud und Last.fm
  mit Kopieren-Knöpfen, Skizzen und Hilfe bei Fehlermeldungen (z. B. „redirect_uri: Not matching configuration“).
- **Datenexport importieren:** Spotify-Kontodaten, Google Takeout (YouTube) und Apple-Music-Mediathek – ohne
  Premium und ohne Entwickler-App; alle Playlists auf einmal.
- **Playlists teilen** (neue Seite „Teilen“): eigene Playlists per Schlüssel teilen. Privater Schlüssel = lesen
  und ändern (z. B. zweiter Rechner), öffentlicher Schlüssel = nur lesen, nur Playlists, die du als „öffentlich“
  markierst. Ende-zu-Ende verschlüsselt (AES-256-GCM), nur Songlisten, Einwilligung „Playlists teilen“ (Standard aus).
  Playlists von Freunden ansehen, sortieren lassen und in eigene Playlists kopieren.
- Neustart nach einem Update behält die Startargumente (z. B. `ui --port 8800`).

## 0.6.3 – 2026-11-03
Windows-/macOS-Pakete zu den Starter-Reparaturen.
- Enthält alle Korrekturen aus 0.6.1 und 0.6.2, jetzt auch für Windows und macOS.

## 0.6.2 – 2026-11-03 (nur AppImage)
- Linux/AppImage: Starter, Panel-Pins und Autostart-Einträge, die nach einem Update auf eine gelöschte alte
  Version zeigten („Programm … ist nicht auffindbar“), werden beim Start repariert.
- Windows/macOS-Pakete fehlen in diesem Release (ein Linux-Test lief auch unter Windows), siehe 0.6.3.

## 0.6.1 – 2026-11-03
- **Windows:** Das App-Fenster stürzte beim Start sofort ab (WinForms akzeptiert als Fenstersymbol nur `.ico`,
  bekam aber `.svg`). Behoben. Kann das Fenster nicht starten, öffnet sich die App im Browser.
- **Linux/AppImage:** Beim Update wird die alte Datei nicht mehr gelöscht, sondern durch einen Verweis auf die neue
  Version ersetzt. Starter mit dem alten Dateinamen funktionieren weiter.
- **Update-Prüfung** jetzt stündlich (vorher 6 h), nach einem Fehler (offline) nach 15 Minuten erneut.
  Das Prüfergebnis gilt nur für die Version, die es ermittelt hat.
- Releases, deren Dateien gerade noch hochgeladen werden, gelten nicht mehr als „unsigniert“.
- Rauchtest (CI) startet jetzt auch das App-Fenster wie per Doppelklick.

**Hinweis Windows:** 0.6.0 startet unter Windows nicht und kann sich daher nicht selbst aktualisieren –
0.6.3 einmal von Hand laden.

## 0.6.0 – 2026-11-03
Genre-Datenbank und bessere Genre-Erkennung.
- Neue Seite **Genre-Datenbank**: Playlists analysieren (App-Ergebnis, Genre im Playlist-Namen – nur lokal –,
  optional KI nur mit Künstler/Titel/Album/Tempo), Vorschläge prüfen, übernehmen oder korrigieren.
- **Genre festlegen** direkt im Song-Detail; eigene Einordnungen gelten sofort bei jeder Erkennung.
- Optionale **Gemeinschafts-Genre-Datenbank**: beitragen (Einwilligung „genres“) und laden (Einwilligung
  „genredb“) getrennt; nur signierte Datei (Namespace `sh-tunebridge-genredb`) wird benutzt.
- Hardtekk wird erkannt; Genre-Angaben im Titel („(Hardtekk Remix)“) werden ausgewertet.
- Shazam: keine automatische Tempo-Suche mehr, wenn nichts gefunden wurde (Knopf „Als Slowed/Sped-up suchen“);
  Limit 10 Anfragen/Minute, 2 s Abstand.
- Schwebe-Icon erscheint sofort; Akzentfarbe im dunklen Modus repariert; Ersteinrichtung fragt nach
  Schwebe-Icon und Tray-Symbol.
- Erkennen-Seite: Anhören/Öffnen und Kaufen untereinander, Kaufen aufklappbar.

## 0.5.0 – 2026-11-03
Neustart mit sauberer Historie.
- YouTube- und SoundCloud-Login direkt in der App (eigene App-Zugangsdaten, nur Lesen).
- Automatischer Abgleich: „Neu für dich“ mit Genre und Playlist-Vorschlägen.
- Genre nur mit geprüftem Künstler und Titel (keine Namensvettern mehr).
- Offizielle Player mit Klick-zum-Laden (Datenschutz); „Mehr vom Künstler“.
- Links, Kaufen und Öffnen gehen im App-Fenster wieder auf.
- Datenverbrauch, Discord-Status, volle Breite, neue Playlist-Ansichten.
