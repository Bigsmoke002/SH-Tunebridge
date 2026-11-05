# Änderungen

Alle Versionen sind mit dem Release-Schlüssel signiert (siehe `src/tunebridge/release_signers`).
Der Updater installiert nur signierte Versionen.

## 0.8.0 – 2026-11-05
DJ-Werkzeuge (Set-Planer, „Passt dazu“, Mix-Tracklists), Statistik, doppelte Songs, lernendes Sortieren,
einstellbare Auto-Sicherung; geführte Anmeldung bei Spotify, SoundCloud, Last.fm und Deezer.
- **Spotify-Einrichtung neu:** 7 kurze Schritte mit Häkchen-Kontrolle (Premium, Dashboard, App anlegen,
  Redirect URI, Web API, Client ID, Schlusskontrolle). Ohne Premium direkt der Weg über den Datenexport.
  Behebt den häufigsten Fehler „redirect_uri: Not matching configuration“ (Adresse fehlte in der Spotify-App).
- **SoundCloud:** Client ID und Secret werden vor dem Öffnen des Browsers bei SoundCloud geprüft – statt einer
  leeren weißen Seite kommt eine klare Meldung mit „Einrichtung wiederholen“. Einrichtung mit Häkchen-Kontrolle.
- **Last.fm-Login:** Anleitung für das kostenlose API-Konto und danach richtige Anmeldung über Last.fm
  (offizielle Web-Anmeldung) – kein Benutzername-Eintippen mehr. „Nur Benutzername“ geht weiterhin.
- **Deezer-Anleitung:** Profil öffentlich machen und Profil-Link finden, mit Prüfung. Ein Deezer-Login ist nicht
  möglich, weil Deezer keine neuen Entwickler-Apps mehr annimmt – das steht jetzt auch so in der App.
- **Sortieren: in jede Playlist reinhören.** In der Vorschau hat jede Playlist „Anhören“ (alle Songs nacheinander,
  je 30 s offizielle Hörprobe) und jeder Song einen eigenen Play-Knopf – vor dem Übernehmen prüfen, ob alles passt.
- **Sortieren: große Listen bis 5000 Songs** (vorher 1000). Wird es mehr, zeigt die Vorschau, wie viele fehlen.
- Fehler behoben: Bei großen Listen landeten ab einigen hundert Songs die meisten unter „Unsortiert“. Grund: Bat
  Last.fm & Co. um eine Pause, bekamen die Songs in dieser Zeit kein Genre – und das wurde sogar gespeichert.
  Jetzt wartet das Sortieren die Pause ab (mit Hinweis im Fortschritt), Unvollständiges wird nicht gespeichert,
  und früher so gespeicherte Songs ohne Genre werden beim nächsten Sortieren neu nachgeschlagen.
- **Doppelte Songs** (neue Seite unter Werkzeuge): findet Songs, die in einer Playlist mehrfach stehen (z. B. einmal
  mit, einmal ohne ISRC – mit einem Klick entfernen, der älteste Eintrag bleibt), Songs in mehreren Playlists und
  Original + Remix/Edit/Slowed desselben Songs. Mit Reinhören, alles lokal.
- **Sortieren lernt aus deinen Korrekturen:** Verschiebst du in der Vorschau einen Song in eine Gruppe mit eindeutigem
  Genre, bietet die App an, das zu merken („Als Techno merken“). Oder „Genre selbst festlegen“ – beides gilt künftig
  beim Erkennen und Sortieren (eigene Einordnung in der Genre-Datenbank) und der Song wandert in die passende Gruppe.
- **„Unsortiert“ erklärt sich:** Jeder Song zeigt, warum er kein Genre bekam (nicht gefunden, keine Genre-Angaben,
  Tags passen zu keinem Genre …). Die Gruppe hat „Mit KI prüfen“ – die KI ordnet nur unsortierte Songs ein, die sie
  wirklich kennt; deine bisherigen Verschiebungen bleiben erhalten.
- **Neue Likes automatisch einsortieren** („Neu für dich“, Schalter „Automatisch einsortieren ab … %“, Standard aus):
  passt ein neuer Song sicher genug zu einer deiner Playlists, landet er selbst dort. In der Liste steht
  „Automatisch in X einsortiert“ mit „Passt“ und „Rückgängig“.
- **Set-Planer** (neue Seite): baut aus einer Playlist eine DJ-Reihenfolge – harmonische Tonarten (Camelot),
  kleine Tempo-Sprünge (halbes/doppeltes Tempo zählt als passend) und ein Energie-Verlauf nach Wahl (Aufbauen, Peak
  in der Mitte, Gleichmäßig, Runterfahren). Energie-Kurve mit Ziel-Verlauf, jeder Übergang bewertet, von Hand
  umstellbar. Als Playlist speichern, als M3U8/CSV (BPM, Tonart) in den Download-Ordner oder als Tracklist kopieren.
- **„Passt dazu – zum Mixen“** im Song-Detail (auch direkt nach dem Erkennen): Songs aus deinen Playlists mit
  passendem Tempo (±6 %, halbes/doppeltes Tempo zählt) und passender Tonart (gleich oder Camelot-Nachbar).
  Nutzt nur schon gemessene Werte – wie viele noch fehlen, steht dabei.
- **Statistik / Jahresrückblick** (neue Seite „Statistik“): Songs, Künstler, neu entdeckte Künstler und Genres pro
  Jahr; Top-Genres, Top-Mikro-Genres, meiste Songs von, Tempo-Verteilung und Verlauf pro Monat. Wahlweise nur
  Erkanntes, nur Playlists oder beides. Alles wird lokal ausgewertet, jedes Diagramm auch als Tabelle.
- **Mix-Tracklists** (Verlauf › „Mix-Tracklists“): Erkennungen am Stück (weniger als 15 Minuten Pause, z. B. ein
  DJ-Mix im Dauer-Modus) werden zur Tracklist mit Zeitstempeln – ab Start (00:00, passt als YouTube-Kapitel),
  mit Uhrzeit oder nur nummeriert, wahlweise mit Genre. Mehrfach erkannte Songs zählen einmal. Kopieren oder als
  Playlist speichern.
- **Automatische Sicherung einstellbar** (Sicherung): aus / täglich / wöchentlich, wie viele behalten, eigener Ordner
  (z. B. eine zweite Platte, wird vor dem Speichern geprüft). Geprüft wird beim Start und danach stündlich – auch
  wenn nur Playlists da sind.
- **Seitenleiste aufgeräumt:** Bibliothek, Werkzeuge, Deine Dienste und Deine Playlists lassen sich einzeln
  einklappen (Pfeil am Abschnitt, wird gemerkt). Einstellungen und Datenverbrauch stehen fest unten und bleiben
  immer sichtbar; nur die Mitte scrollt.
- **Sicherung ist jetzt unter Einstellungen › Sicherung** (alte Links und Strg+7 führen dorthin).
- **„Anzeige im Kreis“** (Spektrum / Welle 3-Band / Welle RGB) ist nach Einstellungen › Erkennung umgezogen –
  mit Beschreibung der Varianten. Auf der Erkennen-Seite führt ein kleiner Link dorthin.
- Fehler behoben: „Playlist löschen“ und „Doppelte entfernen“ nutzten einen Browser-Dialog, der das App-Fenster
  einfrieren konnte – jetzt der App-eigene Dialog.
- Fehler behoben: „Ordner öffnen“ meldete unter Windows nur „Internal Server Error“, wenn der Explorer nicht startet –
  jetzt mit verständlicher Meldung und dem Pfad. KI-Server nicht erreichbar: verständlicher Text statt
  „[WinError 10061] …“.
- Kleinigkeiten: Hinweistexte auf der Erkennen-Seite werden nicht mehr abgeschnitten; bei kleinen Auswahlfeldern
  (z. B. „alle 6 h“) liegt der Pfeil nicht mehr über dem Text.
- Fehler behoben: Nach „Übernehmen“ in der Sortier-Vorschau kam beim Klick auf OK „onConfirm is not a function“
  (die Playlists wurden trotzdem angelegt). Betraf auch zwei Info-Dialoge unter „Nicht erkannt“.
- Fehler behoben: Beim Sortieren von YouTube-„Mag ich“ landeten Hunderte Einträge unter „Unsortiert“ – das waren
  gelikte Videos ohne Musik (Shorts, Gaming, Dokus). Die App fragt jetzt die YouTube-Kategorie ab: Solche Videos
  kommen in eine eigene Gruppe „Keine Musik“ (standardmäßig nicht übernommen) und werden nicht mehr bei Last.fm & Co.
  nachgeschlagen – das Sortieren geht dadurch auch deutlich schneller.
- Fehler behoben: Nach dem letzten Einrichtungsschritt startete die Anmeldung nicht.
- Fehler behoben: Spotify meldete „verbunden“, obwohl Spotify den Zugriff sperrte (z. B. App-Besitzer ohne
  Premium). Jetzt wird nach der Anmeldung geprüft, und die Dienste-Karte zeigt den Grund an.

## 0.7.1 – 2026-11-04
Windows: richtige Desktop-App mit Installer.
- **Windows-Setup** (`…-windows-setup.exe`): Installation ohne Adminrechte, Startmenü- und Desktop-Verknüpfung,
  Eintrag unter „Apps“ zum Deinstallieren (Daten bleiben). Installiert Microsoft Edge WebView2 mit, falls es fehlt.
- **Windows öffnet nie mehr den Browser:** Fehlt WebView2, bietet die App an, es von Microsoft zu installieren
  (Signatur wird geprüft). Andere Fensterfehler erscheinen als Windows-Dialog und werden unter
  `logs\fenster-fehler.txt` gespeichert.
- Updates behalten den Deinstaller; die Versionsnummer unter „Apps“ wird nachgezogen.
- CI: Setup wird still installiert, das App-Fenster muss wirklich aufgehen, danach deinstalliert.

## 0.7.0 – 2026-11-03
Playlists teilen, Dienste ohne Fachwissen einrichten, Datenexporte importieren.
- **Lauf-Wellenform** im Erkennen-Kreis und im Schwebe-Icon (wie am DJ-Player, wandert von rechts nach links):
  „Welle 3-Band“ (Bass blau, Mitten orange, Höhen weiß) oder „Welle RGB“; umschaltbar unter Erkennen › „Anzeige im Kreis“.
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
