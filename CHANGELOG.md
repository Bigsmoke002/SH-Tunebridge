# Änderungen

Alle Versionen sind mit dem Release-Schlüssel signiert (siehe `src/tunebridge/release_signers`).
Der Updater installiert nur signierte Versionen.

## Unveröffentlicht
- **Android: USB-Soundkarte:** Als Mikrofon nimmt die App jetzt immer das eingebaute Mikrofon des Handys – Android
  hatte sonst den (meist stummen) Eingang der Soundkarte genommen. Wer ein USB-/Headset-Mikrofon will, schaltet unter
  Mehr › Erkennen „Angeschlossenes Mikrofon nehmen“ ein. Beim Handy-Ton erklärt die App, warum mit Soundkarte Stille
  ankommen kann (Hi-Res/„bit-perfect“ geht am Handy vorbei) und was hilft; der Vorschlag „Handy-Ton nehmen“ kommt mit
  Soundkarte nicht mehr.

## 0.12.0 – 2026-11-09
- **Android: Musik auf dem eigenen Handy erkennen:** Läuft die Musik auf demselben Handy und ist „Mikrofon“ gewählt,
  schlägt die App „Handy-Ton“ vor – über das Mikrofon filtert Android den eigenen Lautsprecher oft heraus, dann kam
  „Nichts erkannt“.
- **Android: Player mit Vor/Zurück:** Verlauf und Playlists lassen sich als Hörproben (30 s) abspielen – nacheinander
  oder zufällig, mit Mini-Player (Zurück, Pause, Weiter) über der Navigation. Tippen auf den Song öffnet ihn ganz in
  deiner Musik-App (Spotify, YouTube Music, Deezer, TIDAL …, direkt, wenn die App die Nummer kennt).
- **Android: Ähnliche Songs:** Bei jedem Song „Ähnliche Songs“ – vom gekoppelten PC (neue verschlüsselte Anfrage
  `/phone/v1/similar`), unterwegs nach Einwilligung direkt von Deezer. Abspielen, zur Playlist hinzufügen, öffnen.
- **Android: Playlists auswählen:** Unter Mehr › (PC) › „Playlists auf dem Handy“ wählst du „Alle“ oder nur bestimmte
  PC-Playlists. Der PC schickt dann nur diese (plus eine Übersicht aller Namen zum Auswählen); was du am Handy anlegst
  oder befüllst, bleibt immer dabei und geht beim Abgleich zurück an den PC.
- **Android: Hörproben aus PC-Playlists gingen nicht:** Deren Deezer-Adressen waren abgelaufen; die App holt jetzt
  beim Abspielen eine frische Adresse.

## 0.11.0 – 2026-11-09
- **Weniger Shazam-Sperren:** Die Tempo-Suche (Slowed/Sped-up) läuft nie mehr automatisch – auch nicht bei
  unsicheren Treffern. Sie kostete bis zu 3 zusätzliche Anfragen pro Scan; jetzt gibt es sie nur per Knopf.
  Nach „Nichts erkannt“ zusätzlich „Länger aufnehmen (20 s)“: Shazam bekommt den mittleren Abschnitt – hilft bei
  leisen Intros oder Gerede am Anfang, weiterhin nur eine Anfrage.
- **Unsichere Treffer werden markiert:** Hat nur Shazam den Song gefunden und passt er nur mit Tempo-Abweichung,
  fragt die App „Stimmt das?“. „Stimmt“ merkt sich die Stelle lokal (nächstes Mal ohne Shazam-Anfrage), „Falsch“
  entfernt den Eintrag aus dem Verlauf. Auch sichere Treffer lassen sich direkt nach dem Erkennen als falsch verwerfen.
- **Shazam-Bibliothek importieren:** Unter Dienste › Shazam eine Shazam-CSV (alte „shazamlibrary.csv“ oder eine
  Datenkopie von Shazam) hineinziehen. Daraus werden „Meine Shazams“ (neueste zuerst, ohne Doppelte) und je Jahr eine Playlist – zum
  Sortieren, Übernehmen und Übertragen wie jede andere Playlist. Eine Anmeldung mit dem Shazam-Konto gibt es nicht,
  weil Shazam/Apple dafür keine Schnittstelle anbieten.
- **Handy koppeln (neu, Android):** Einstellungen › Handy zeigt einen QR-Code. Die Android-App von SH-Tunebridge
  scannt ihn und gleicht danach im eigenen WLAN direkt mit dem PC ab – Erkennungen vom Handy landen im Verlauf
  (Genre, BPM usw. ergänzt der PC), Playlists gehen in beide Richtungen. Ende-zu-Ende verschlüsselt, ohne Server
  dazwischen; der PC öffnet dafür Port 8766 nur fürs eigene Netz und nur, solange ein Handy gekoppelt ist.
- **Koppeln nur mit Zustimmung auf beiden Seiten:** Das Handy zeigt vorher, welche Adressen es benutzt und was wann
  übertragen wird; danach zeigen Handy und PC dieselbe Prüfzahl, und am PC muss man „Zulassen“ klicken (mit
  Gerätename, IP-Adresse und App-Version). Ohne Antwort wird nach 2 Minuten abgelehnt.
- **Nur noch ein Tray-/Schwebe-Icon:** Wurde die App schnell neu gestartet (z. B. nach einem Update), lief der alte
  Begleiter weiter und ein zweiter kam dazu. Jetzt beendet sich der alte von selbst.
- **Netzwerke erkennen nur mit Zustimmung:** PC und Handy lesen ihre Netzwerkkarten erst aus, wenn du es erlaubst
  (PC: Einstellungen › Handy, Handy: beim Koppeln). Ohne Zustimmung kein Handy-Zugang und kein Abgleich; widerrufbar.
- **Shazams vom Handy am PC:** Was das Handy aus der Shazam-App übernimmt, steht am PC im Verlauf (Filter „Aus der
  Shazam-App“) und als Playlists „Shazams vom Handy“ (plus je Jahr) unter Dienste › Shazam – zum Einsortieren nach Genre
  und Übertragen wie jede andere Playlist. Eine Shazam-CSV bleibt daneben erhalten. Der Verlauf zeigt jetzt bis zu 3000 Songs.
- **Willkommen am PC:** „Speichern“ ist erst klickbar, wenn die Datenschutzerklärung bestätigt ist (vorher ließ er sich
  ohne Haken anklicken und meldete erst dann einen Fehler).
- **Android: Handy-Ton erkennen:** Unter dem Erkennen-Kreis wählst du „Mikrofon“ oder „Handy-Ton“. Handy-Ton hört direkt,
  was auf dem Handy spielt (auch mit Kopfhörern) – mit Hinweis vorab, System-Freigabe und sichtbarer Benachrichtigung.
- **Android: Shazam-App wird gefunden:** „Verlauf aus der Shazam-App“ meldete auf neueren Android-Versionen fälschlich
  „nicht installiert“.
- **Android: Shazam-Datenbank wird gefunden:** Seit Android 11 sieht ein Root-Befehl im Bereich der App die Daten anderer
  Apps nicht; gelesen wird jetzt im globalen Bereich (Magisk/KernelSU „--mount-master“, sonst nsenter).
- **Android: Verlauf aus der Shazam-App (nur Root):** Auf gerooteten Handys übernimmt Mehr › Shazam-App die eigenen
  Shazams (Titel, Künstler, Zeitpunkt – kein Standort, keine Signatur). Vorher einmal eine ausdrückliche Warnung
  mit Bestätigung: nur für erfahrene Nutzer, Nutzung auf eigene Verantwortung.
- **Android: Updates in der App:** Mehr › Über sucht bei GitHub nach neuen Versionen (auf Wunsch einmal am Tag
  automatisch, Standard aus), prüft die Signatur des Manifests und die Prüfsumme des APK und übergibt es dann an den
  Android-Installer. Releases baut `scripts/publish-android.sh`, den App-Schlüssel legt `scripts/android-keystore.sh` an.
- **Android: schneller erkennen:** Kachel in den Schnelleinstellungen, Widget mit letztem Treffer und App-Verknüpfungen
  („Erkennen“, „Handy-Ton“ – Symbol lange drücken).
- **Android-CI:** eigener Ablauf „android“ (Tests + Debug-APK), die Desktop-CI bleibt unverändert.
- **Beispiele neutral:** Netz-Beispiele zeigen allgemeine Adressen; VPNs heißen überall einfach „VPN“.
- **Mehrere PCs:** Das Handy kann mit beliebig vielen PCs abgleichen; Playlists werden je PC gruppiert.
- **Netze wählen:** Der PC erkennt seine Heim- und VPN-Netze (z. B. 192.168.178.0/24, 10.0.0.0/24, VPN) und
  öffnet den Handy-Zugang nur dort, wo du willst – in allen, nur bestimmten oder nur dem Hauptnetz. Am Handy wählst
  du je PC die Adressen; gesendet wird nur, wenn das Handy gerade im Netz dieses PCs ist.

## 0.10.2 – 2026-11-08
- **Lange Dialoge scrollen:** Dialoge (z. B. „Fertig – 136 Playlists angelegt“) werden höchstens so hoch wie das
  Fenster; der Inhalt scrollt, Titel und Knöpfe bleiben sichtbar. Vorher ragte der OK-Knopf unten aus dem Fenster.
- **„Alles einlesen“ bis 80.000 Songs** (vorher 10.000). Damit das flüssig bleibt: Die Sortier-Vorschau zeigt große
  Gruppen in Portionen („Weitere anzeigen“), die Fortschrittsabfrage schickt die Songliste erst am Ende, und ein
  laufendes Einlesen wird auch nach vielen Stunden nicht mehr verworfen.
- **Genres der Bibliothek beitragen ohne Gesamtgrenze** (vorher höchstens 2.000 Songs). Pro Abgleich gehen bis zu
  2.000 Songs in Paketen à 200 raus, der Rest beim nächsten Abgleich.

## 0.10.1 – 2026-11-07
- **Weniger Last im Leerlauf auf „Erkennen“:** Die Pegelanzeige zeichnet nur noch, wenn neue Daten kommen (höchstens
  30 Bilder/s statt bei jeder Bildwiederholung), pausiert bei Stille und hält Verbindung und Aufnahme an, sobald das
  Fenster ins Tray geht (Windows/X11 auch beim Minimieren). Der Pegelbalken bewegt sich ohne Neuberechnung der Seite.
  Gemessen: CPU auf „Erkennen“ mit Musik etwa halbiert (52 % → 25 % eines Kerns), bei Stille ~5 %; der Fensterprozess
  wächst deutlich langsamer.
- **Grafikkarte gezielter:** Mit NVIDIA unter Wayland zeichnet das Fenster jetzt über Vulkan auf der GPU statt in
  Software (nochmals rund ein Drittel weniger Rechenzeit). Andere Systeme bleiben beim erprobten Software-Zeichnen.
  Startet das Fenster zweimal hintereinander nicht sauber, bleibt die App dauerhaft bei Software.
  `TUNEBRIDGE_GPU=0` erzwingt Software, `=1` die GPU, `=vulkan` den Vulkan-Weg.
- **Schneller bei großen Bibliotheken:** Statistik, Gemeinschafts-Status, Playlist-Übersicht und „Doppelte Songs“
  werden nur noch neu berechnet, wenn sich die Datenbank geändert hat (gemessen mit 50.000 Songs: Statistik 700 → 1 ms,
  Gemeinschaft 610 → 2 ms, Playlists 420 → 22 ms, Doppelte Songs 3,4 s → 13 ms beim erneuten Öffnen). Die
  Playlist-Übersicht liest nur noch Genre und Cover statt jeden Song komplett. „Doppelte Songs“ zeigt lange Listen
  in Portionen („Weitere anzeigen“) statt alles auf einmal. Titel- und Künstlervergleich merkt sich Ergebnisse.
- **Mix erstellen schneller:** Hörproben werden zu viert gleichzeitig gemessen (Deezers Anfrage-Grenze gilt weiter für
  alle zusammen). Ein neuer „Mixbar“-Mix mit 30 Songs: 29 → 21 s; mehr lässt Deezers Grenze nicht zu.

## 0.10.0 – 2026-11-07
- **Neu: Mix erstellen** (Werkzeuge › Mix erstellen, auch über Strg+K). Bis zu 5 Künstler suchen und auswählen –
  die App baut daraus eine neue Playlist aus ihren Top-Songs, ihrem Künstler-Radio und Songs ähnlicher Künstler (Deezer,
  ohne Login). **„Wie passend?“** in vier Stufen: *Locker* (nur Ähnlichkeit, ohne Messen), *Passend* (±15 % Tempo,
  ähnliche Energie), *Mixbar* (±6 % Tempo, halb/doppelt zählt, harmonische Übergänge in DJ-Reihenfolge) und
  *DJ-genau* (±3 % Tempo, Energie-Verlauf wie im Set-Planer). Feineinstellungen: BPM-Bereich, Tonart (Camelot),
  Energie, Bekanntheit (Hits/gemischt/eher unbekannt), höchstens N Songs pro Künstler, Remixe ja/nein, Songs aus
  den eigenen Playlists weglassen. Jede Zeile zeigt, warum der Song dabei ist, dazu BPM, Tonart und Energie. Alles
  sofort anhören, einzelne Songs gegen passende aus der Reserve tauschen oder entfernen, als Playlist speichern und
  im Set-Planer weiterbearbeiten. Kein Suchverlauf; gespeichert wird erst die fertige Playlist.
- **Mix erstellen nach Genre:** statt Künstlern ein Genre oder Subgenre aus dem Genre-Baum wählen (z. B.
  *Drum & Bass › Liquid*, *Dubstep › Riddim*). Die Künstler kommen aus deiner Bibliothek, deinen eigenen Einordnungen,
  der Gemeinschafts-Genre-Datenbank (falls geladen), MusicBrainz (nur Künstler, bei denen das Genre ein Schwerpunkt ist –
  einzelne Zufalls-Stimmen zählen nicht) und mit eigenem Key Last.fm. Jeder Song sagt, woher sein Genre stammt
  („Liquid laut MusicBrainz“). Das Ziel-Tempo richtet sich nach dem typischen Tempo des Genres (DnB 174 statt 87).
  Zu Nischen-Subgenres mit wenig Daten wird mit dem Hauptgenre ergänzt – deutlich als „nicht bestätigt“ markiert;
  bei „DJ-genau“ bleiben nur bestätigte Treffer.
- **Behoben: Playlists ließen sich nicht in andere Playlists übernehmen** (Nutzer-Meldung). Bisher entstand beim
  Übernehmen immer eine neue Playlist. Jetzt gibt es auf jeder eigenen Playlist **„In andere Playlist“** und
  **„Songs holen“** (aus eigenen Playlists, importierten Exporten oder verbundenen Diensten); bei Dienst- und
  Freundes-Playlists wählt „In meine Playlists“ eine bestehende oder neue Playlist. Doppelte Songs werden
  übersprungen, die Quelle bleibt unverändert. Unter „Übertragen“ lassen sich importierte Exporte
  als Quelle nutzen. „Ansehen“ zeigte bei eigenen Playlists eine leere Liste.
- **Neu: Übertragen zu YouTube und SoundCloud.** Beide waren bisher nur lesend angebunden. SoundCloud legt eine private
  Playlist an (höchstens 500 Songs) oder ergänzt eine bestehende. YouTube fragt das Schreibrecht erst beim ersten
  Übertragen per Klick bei Google an (beim normalen Verbinden bleibt es bei „nur Lesen“). Googles Tageskontingent für
  eigene Apps reicht für etwa 60–70 Songs am Tag; wird es knapp, stoppt die Übertragung sauber, und am nächsten Tag
  setzt „In bestehende Playlist“ fort, ohne Doppelte.
- **Übertragen neu gestaltet:** zwei klare Spalten „Von“ und „Nach“ mit Dienst-Knöpfen, die Playlist-Auswahl hat die
  Suche direkt eingebaut (auch per Tastatur), unten eine Zusammenfassung, was wohin geht. Als Ziel gibt es jetzt auch
  **„Bestehende“** Playlist, für jeden Dienst und für SH-Tunebridge.
- **Behoben (YouTube):** „The playlist identified with the request's playlistId parameter cannot be found“ direkt nach
  dem Anlegen. YouTube braucht ein paar Sekunden, bis eine neue Playlist sichtbar ist; die App wartet jetzt kurz und
  versucht es erneut.
- Mix erstellen: Die ganze Seite samt Suchfeld und Regler nutzt die volle Breite und passt sich dem Fenster an.

## 0.9.2 – 2026-11-06
- **Windows: Selbst-Update repariert.** Das Hilfsskript, das beim Neustart die alte gegen die neue Version tauscht,
  startete aus der fensterlosen App heraus nicht – die App beendete sich, das Update blieb liegen. Jetzt läuft der
  Tausch (geprüft in der Windows-VM: Update bei laufendem Schwebe-Icon, Neustart, Begleiter wieder da). Ein Protokoll
  des Tauschs liegt in `%TEMP%\sh-tunebridge-tausch.log`. **Wichtig:** Da der Tausch von der *alten* Version
  ausgeführt wird, bitte 0.9.2 unter Windows **einmal von Hand** installieren (Setup) – danach klappen Updates selbst.
- **Schwebe-Icon und Tray-Symbol unter Linux (AppImage) repariert:** Sie stürzten beim Start ab, weil das AppImage
  eine nicht passende Tastatur-Bibliothek (libxkbcommon) mit der des Systems mischte. Jetzt liegen beide passend bei.
- **Schwebe-Icon und Tray-Symbol jetzt auch unter Windows** (bisher nur Hinweis „kommt mit einem späteren Update“).
  Vor einem Update wird der Begleiter beendet, damit Windows den Programmordner austauschen kann.
- **Windows: Einfügen öffnet kein Konsolenfenster mehr.** Die Zwischenablage wird direkt über Windows gelesen statt
  über PowerShell; auch andere Hilfsprogramme starten ohne sichtbares Fenster.

## 0.9.1 – 2026-11-06
- **Gemeinschafts-Genre-Datenbank laden ist jetzt vorausgewählt** – im Einrichtungsdialog als eigener Punkt
  „Vom Entwickler laden“ (abwählbar). Es wird nichts gesendet; geladen wird erst nach dem Speichern des Dialogs und
  unabhängig von der Freigabe zum Senden. Bestehende Einstellungen bleiben unverändert.

## 0.9.0 – 2026-11-06
- **Alles durchsuchen** (oben in der Seitenleiste oder Strg+K): Seiten und Funktionen, Einstellungen, deine Playlists,
  Playlists deiner Dienste, Songs in deinen Playlists und der Erkennungsverlauf. Pfeiltasten + Enter; Einstellungen
  öffnen sich direkt an der richtigen Stelle (hervorgehoben). In den Einstellungen gibt es ein eigenes Suchfeld.
- **Playlists sortieren:** in der Seitenleiste (⇅ neben „Deine Playlists“) und in der Playlists-Ansicht – Name A–Z/Z–A,
  Größe, zuletzt geändert, neueste zuerst. Wird gemerkt.
- **„Neu für dich“ filtern:** Suche (Titel, Künstler, Album), Dienst, Quelle (Lieblingssongs/Playlist), Genre,
  Status (offen / automatisch einsortiert), BPM-Bereich und Sortierung. Wird gemerkt; „Alle erledigt“ wirkt bei
  aktivem Filter nur auf die gefilterten Songs.
- **Player: Vor und Zurück.** Neben ▶ gibt es ⏮/⏭. Klickst du einen Song an, bilden alle Songs der Ansicht die
  Warteschlange; ⏮ springt erst an den Anfang, dann zum vorigen Song.
- **Ähnliche Songs mit Tempo, Tonart und Energie:** jede Zeile zeigt BPM, Camelot-Tonart und Energie (gemessen aus
  der Hörprobe, nacheinander im Hintergrund, Gemessenes kommt aus dem Speicher) und „mixbar“, wenn Tempo (±6 %,
  auch halb/doppelt) und Tonart zum Ausgangssong passen. Gilt für „Erkennen“ und „Entdecken“.
- **Neu: Öffentliches Playlist-Verzeichnis** (Werkzeuge › Verzeichnis). Playlists anderer Nutzer durchsuchen
  (Name, Künstler, Pseudonym, Genre), ansehen und in eigene Playlists übernehmen. Eigene Playlists einzeln und mit
  Bestätigung veröffentlichen – unter einem Pseudonym, ohne Cover und Musik; aktualisieren und löschen jederzeit.
  Melden-Knopf: nach mehreren Meldungen wird bis zur Prüfung ausgeblendet; bei eigenen Playlists siehst du Status
  und Grund. Keine Links, Mail-Adressen oder Telefonnummern in Texten; höchstens 500 Songs und 20 Playlists;
  Löschung nach 12 Monaten ohne Aktualisierung. Eigene Einwilligung „Öffentliches Playlist-Verzeichnis nutzen“.
- **Sortier-Vorschau: einzeln oder alle bestätigen.** Jede Playlist hat „Diese übernehmen“; „Alle ausgewählten
  übernehmen“ legt den Rest an. Bereits angelegte Playlists sind markiert und werden beim Sammel-Knopf nicht doppelt angelegt.
- **Erkennen aufgeräumt:** Hinweistexte stehen nur noch als ⓘ-Icon da – Text beim Drüberfahren (oder per Tab-Taste).
- **Erkennen nach deinem Geschmack:** „Ansicht anpassen“ – Reihenfolge der Bereiche unter dem Song (Anhören & öffnen,
  Kaufen, Offizieller Player, Mehr vom Künstler, KI-Hinweis, Einsortieren, Ähnliche Songs, Passt dazu) ändern und
  Bereiche ausblenden. Gilt auch für die Song-Details, gemerkt pro Rechner.
- Fehler behoben: **Remixe, Flips, Bootlegs, VIPs, Cover und Live-Fassungen** wurden beim Nachschlagen dem Original
  zugeordnet (Abzug nur 15 von 100 Punkten, „Song (X Remix)“ landete bei 85) und bekamen dessen ISRC – danach galten
  sie als derselbe Song. Jetzt sind „harte“ Fassungen eigene Songs (auch „A Remix“ ≠ „B Remix“), Radio Edit /
  Extended Mix / Remaster bleiben derselbe Song. Slowed-/Sped-up-Fassungen übernehmen nicht mehr die ISRC des Originals.
- **Doppelte Songs:** Andere Fassungen desselben Titels zählen nicht mehr wie Duplikate – eigener, zugeklappter
  Bereich „kein Duplikat“. Auch alte Einträge mit falscher Original-ISRC werden nicht mehr als doppelt gemeldet.
- **Alles einlesen** (Dienste): liest Lieblingssongs und eigene (auf Wunsch auch gefolgte) Playlists aus allen
  verbundenen Diensten auf einmal ein, führt doppelte Songs zusammen und zeigt die gewohnte Sortier-Vorschau.
  Grenzen: 300 Playlists pro Dienst, 10.000 verschiedene Songs; Pausen der Dienste werden abgewartet, zwischen zwei
  Playlists eine kleine Pause; kaputte/private Listen werden übersprungen und am Ende aufgelistet.
- **Einstellungen › Gemeinschaft:** eigene Einordnungen und – neu – die Genres deiner Bibliothek zur
  Gemeinschafts-Genre-Datenbank beitragen und die Datenbank laden; Abgleich **manuell** (Knopf „Jetzt abgleichen“)
  oder **automatisch**. Bibliotheks-Genres werden nur aus freien Quellen (MusicBrainz, Angaben im Titel) abgeleitet
  und nur gesendet, wenn sie mit dem Ergebnis der App übereinstimmen – Last.fm-, Deezer- und Apple-Daten fließen
  nicht in die Gemeinschafts-Datenbank. Höchstens 400 Songs pro Abgleich, 2000 insgesamt. Standard: aus.
- Fehler behoben: **„Keine ähnlichen Songs gefunden“** bei fast jedem Song. Last.fm liefert seit etwa Oktober 2026
  für ähnliche Songs und Künstler meist gar nichts mehr (auch bei sehr bekannten Songs). Jetzt springt Deezer ein
  (ähnliche Künstler + Künstler-Radio, ohne Key, höchstens 2 Songs pro Künstler). Leere Antworten werden nicht
  mehr 7 Tage lang gemerkt. „Ähnliche Songs“ funktioniert damit auch ohne Last.fm-Key.
- **Vor/Zurück:** Pfeile rechts im Suchfeld der Seitenleiste, dazu Alt+←/→ und die Seitentasten der Maus –
  wie im Browser. Ist kein Schritt zurück/vor möglich, ist der Pfeil ausgegraut.
- **Sicherheit:** Die App nimmt nur noch Anfragen von sich selbst an. Fremde Webseiten im Browser konnten bisher im
  Hintergrund Anfragen an die App auf 127.0.0.1 schicken (bzw. per DNS-Rebinding Daten mitlesen) – jetzt werden
  fremder Host, fremde Herkunft und Anfragen von fremden Seiten abgewiesen (auch Live-Verbindungen).
  Rückleitungen nach dem Login bei Spotify & Co. funktionieren weiter.
- **Sicherheit:** Datenordner und Datenbank sind unter Linux/macOS nur noch für den eigenen Benutzer lesbar
  (vorher konnten andere Benutzer desselben Rechners die Datenbank lesen). Wird beim Start automatisch gesetzt.
- Fehler behoben: Playlists mit „/“ im Namen (z. B. „Ambient / Chill“, „Rock / Metal“) ließen sich nicht öffnen,
  umbenennen oder löschen – es kam nur „Da ist etwas schiefgelaufen – Not Found“.

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
