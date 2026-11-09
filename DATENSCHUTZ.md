# Datenschutz bei SH-Tunebridge

*Stand: 3. November 2026*

SH-Tunebridge ist eine Desktop-App, die **auf deinem Rechner** läuft. Kein Konto, kein Tracking, keine
Werbung. Grundsatz: **nur anonym bzw. pseudonym und nur das Nötigste.** Der Entwickler erhält nur dann
Daten, wenn du es beim ersten Start (oder später in den Einstellungen) ausdrücklich erlaubst – standardmäßig
ist alles Senden aus.

## Verantwortlicher und Kontakt

Verantwortlich für den Server `shtunebridge.bs002.de` und die dort gespeicherten Daten:
**Léon Döring** (Bigsmoke002), privates, nicht-gewerbliches Projekt
E-Mail für Datenschutzanfragen: **info@smokes-hub.de** · Discord: **Bigsmoke002.de**

Für alles, was nur auf deinem Rechner passiert, bist du selbst verantwortlich. Für die angebundenen Dienste
(Shazam, Deezer, TIDAL …) sind deren Betreiber verantwortlich; es gelten deren Datenschutzbestimmungen.

## Einwilligungen beim ersten Start

Beim allerersten Start fragt SH-Tunebridge einmal nach. Jede Kategorie ist einzeln abschaltbar, alles
lässt sich jederzeit unter **Einstellungen → Datenschutz → Einwilligungen** ändern oder widerrufen.

**Lokal speichern** (verlässt den Rechner nicht, standardmäßig an):
- *Liste „Nicht erkannt / Genre unbekannt“* – siehe unten.
- *Player-Infos (MPRIS)* – Titel, Künstler, Album, Länge des gerade laufenden Titels; ohne lokale
  Dateipfade, Web-Adressen ohne Tracking-Parameter.
- *Song-Speicher & lokale Fingerabdrücke* – siehe „Weniger Anfragen“.

**An den Entwickler senden** (standardmäßig aus; erst nach Bestätigung der Datenschutzerklärung und der
Ziel-Domain `shtunebridge.bs002.de` wählbar):
- *Liste „Nicht erkannt“* – je Eintrag: Datum (ohne Uhrzeit), Art, Art der Quelle (Anwendung/Standard/Gerät),
  Pegel, Treffer-Kandidaten und Fehlermeldungen der Dienste, Song (Künstler, Titel, ISRC) bzw. Player-Titel,
  -Künstler, -Album, Web-Adresse, Genre-Tags, deine Notiz, App-Version.
- *Fehlerberichte* – Datum, Bereich, Fehlermeldung, Fehlertyp, Programmstelle (Datei:Zeile), App-Version.
  Benutzername, Rechnername, Home-Pfad und Schlüssel werden vorher geschwärzt.
- *Erkannte Songs (Genre-Analyse)* – Datum, Künstler, Titel, ISRC, ermitteltes Genre/Subgenre/Nische,
  Sicherheit, Genre-Quelle, genutzter Dienst, Tempo-Faktor.
- *Zur Gemeinschafts-Genre-Datenbank beitragen* – je Song, den du selbst eingeordnet hast: Datum, Künstler,
  Titel, ISRC, Genre, Subgenre, Herkunft (Playlist-Name / App / KI / von dir geändert). Siehe „Genre-Datenbank“.
- *Genres meiner Bibliothek beitragen* – je Song, den die App schon kennt: Datum, Künstler, Titel, ISRC, Genre,
  Subgenre, Sicherheit. Das Genre wird dafür nur aus freien Quellen abgeleitet (MusicBrainz, Angaben im Titel).
  Siehe „Genre-Datenbank“.

- *Playlists teilen* – nur verschlüsselte Blöcke, siehe „Playlists teilen“.
- *Öffentliches Playlist-Verzeichnis nutzen* – Stöbern sendet nur die Suchanfrage. Veröffentlicht wird nur, was
  du **einzeln und mit Bestätigung** freigibst; diese Angaben sind dann für alle sichtbar. Siehe
  „Öffentliches Playlist-Verzeichnis“.

**Laden** (im Einrichtungsdialog vorausgewählt, abwählbar): *Gemeinschafts-Genre-Datenbank laden* – einmal am
Tag eine signierte Datei (nur Song → Genre) vom selben Server. Gesendet werden keine Inhalte; technisch erhält der
Server nur die Anfrage mit deiner IP-Adresse. Geladen wird erst, nachdem du den Einrichtungsdialog mit bestätigter
Datenschutzerklärung gespeichert hast. Rechtsgrundlage: berechtigtes Interesse (Art. 6 Abs. 1 lit. f DSGVO) an einer
besseren Genre-Erkennung; du kannst jederzeit widersprechen, indem du den Schalter abwählst (Einstellungen ›
Datenschutz oder › Gemeinschaft) – die geladene Datei wird dann sofort entfernt.

Nie gesendet: Ton/Aufnahmen, Rechner-, Benutzer- oder Gerätenamen, Konten, Tokens, ganze Playlists,
Playlist-Namen, Uhrzeiten.
Automatisch gesendet wird nur, was nach deiner Einwilligung entsteht (etwa alle 6 Stunden).

## Was bleibt auf deinem Rechner
- Verlauf, Playlists, Einstellungen (SQLite-Datenbank in `~/.local/share/tunebridge`)
- API-Keys und Login-Tokens (`~/.config/tunebridge/config.env`, `…/tokens/`, nur für dich lesbar)
- Sicherungen (Ordner frei wählbar)
- Das lokale KI-Modell und alles, was es verarbeitet
- Darstellung: Farben und ein eigenes Hintergrundbild (verkleinert, im Datenordner unter `appearance/`)
- Automatischer Abgleich: Einstellungen, Prüfsummen schon gesehener Songs (keine Titel) und die Liste „Neu für dich“
- Deine Entscheidungen zu eingebetteten Playern („immer laden“ je Anbieter, im Speicher des App-Fensters)
- Importierte Datenexporte (Spotify, YouTube, Apple Music, Shazam): nur Playlist-Namen und Songs (Titel, Künstler, Album,
  ISRC/Video-ID) – „Import löschen“ entfernt sie sofort; die hochgeladene Datei selbst wird nicht gespeichert
- Deine Genre-Einordnungen (Song → Genre, Herkunft) und – wenn erlaubt – die geladene Gemeinschafts-Genre-Datenbank
- Selbst gelernte Genres: unbekannte Last.fm-Tags deiner Songs und wie oft sie vorkamen. „Vorschlagen“
  öffnet nur ein GitHub-Issue mit dem Genre-Namen (ohne deine Songs) – abschicken musst du es selbst.

**Aufnahmen werden nie gespeichert.** Der Ausschnitt (6–20 s) liegt nur während der Erkennung als
temporäre Datei vor und wird danach sofort gelöscht. Stille wird gar nicht erst verschickt.

## Was deinen Rechner verlässt – und wann

| Empfänger | Daten | Wann |
|---|---|---|
| Shazam (Apple) | Fingerabdruck der Aufnahme – **kein hörbares Audio** | nur nach Klick auf „Erkennen“ (im Dauer-Modus bis zum nächsten Klick). Nur wenn du nach „Nichts erkannt“ oder einem unsicheren Treffer auf „Als Slowed/Sped-up suchen“ klickst: bis zu 3 weitere Fingerabdrücke der lokal im Tempo umgerechneten Aufnahme (nie automatisch) |
| AudD, ACRCloud | Aufnahme-Ausschnitt (Audio) | **nur mit deiner Zustimmung**, getrennt für Desktop und Mikrofon |
| Deezer, iTunes-Suche, Last.fm, MusicBrainz | Künstler und Titel (ggf. ISRC); zur Genre-Prüfung die Kennung des schon gefundenen Künstlers | nach einer Erkennung, beim Link-Einfügen, Sortieren und automatischen Abgleich (Cover, Hörprobe, Genre, Mikro-Genre) |
| Deezer („Mehr vom Künstler“) | Kennung des Songs bzw. Künstlers | beim Öffnen eines Songs |
| YouTube, Spotify, Apple, TIDAL, SoundCloud, Deezer (offizielle Player) | IP-Adresse, Geräte-/Browserdaten, ggf. Cookies des Anbieters | **erst nach deinem Klick** auf „Player laden“ (siehe unten) |
| Webseiten, die du über „Öffnen“ oder „Kaufen“ aufrufst | IP-Adresse (dein Standard-Browser) | erst beim Klick |
| Spotify, TIDAL, Deezer, Last.fm, YouTube, SoundCloud | Abruf deiner Playlists und Lieblingssongs; bei Spotify, TIDAL, YouTube und SoundCloud auf Wunsch Playlists anlegen/ergänzen und Songs liken | unter „Dienste“ und beim automatischen Abgleich – nur mit deinem verbundenen Konto bzw. deinem öffentlichen Profil |
| Google (YouTube), SoundCloud, Last.fm | Anmeldung über deine **eigene** App (Client-ID/-Secret bzw. API key/Shared secret); Login-Token bzw. Sitzungsschlüssel und dein Last.fm-Benutzername | nur wenn du den Login einrichtest – direkt zwischen deinem Rechner und dem Dienst, kein Server dazwischen |
| Deezer, Apple; bei verbundenen Diensten auch deren Bild-Server | deine IP-Adresse | beim Anzeigen von Covern und Abspielen von Hörproben (direkt vom Anbieter) |
| TIDAL, Spotify, YouTube, SoundCloud (Übertragen) | Titel und Künstler der zu übertragenden Songs (zum Suchen), Name der neuen Playlist | nur wenn du den Dienst verbindest und selbst „Übertragen“ startest |
| GitHub | deine IP-Adresse | Update-Prüfung (stündlich) |
| Hugging Face, GitHub | deine IP-Adresse | einmalig beim Download von Modell/Laufzeit |
| Microsoft (nur Windows) | deine IP-Adresse | nur wenn WebView2 fehlt und du der Installation zustimmst (Setup oder Dialog beim Start) |
| Dein gekoppeltes Handy (Android-App, im eigenen Netz) | Ende-zu-Ende verschlüsselt: deine Erkennungen (Song, Zeitpunkt, Gerät, Genre, Links) und lokalen Playlists | nur wenn du ein Handy koppelst; direkt im WLAN/LAN bzw. VPN, kein Server dazwischen (siehe „Android-App“) |
| Entwickler (`shtunebridge.bs002.de`) | die Kategorien, die du erlaubt hast (siehe oben) + technisch deine IP-Adresse | **nur mit Einwilligung** |
| Entwickler (`shtunebridge.bs002.de`) – Playlists teilen | nur Ende-zu-Ende-verschlüsselte Blöcke, zufällige Bereichs-Kennung, Prüfwert des Schreib-Schlüssels (technisch deine IP-Adresse) | beim Teilen, Aktualisieren und Ansehen von Freunde-Playlists, **nur mit Einwilligung** „Playlists teilen“ |
| Entwickler (`shtunebridge.bs002.de`) – Öffentliches Playlist-Verzeichnis | Suchanfrage; beim Veröffentlichen Playlist-Name, Pseudonym, Genre, Beschreibung, Songliste, Kennung deiner Installation (technisch deine IP-Adresse) | beim Stöbern, Veröffentlichen, Melden, **nur mit Einwilligung** „Verzeichnis“ |
| Entwickler (`shtunebridge.bs002.de`) – Gemeinschafts-Genre-Datenbank | nur die Anfrage (technisch deine IP-Adresse) | einmal am Tag, vorausgewählt und jederzeit abwählbar (erst nach dem Einrichtungsdialog) |

Für diese Dienste gelten deren eigene Datenschutzbestimmungen.

## Aufnahme nur auf Klick
Aufgenommen und gesendet wird **nur**, wenn du auf den Kreis „Erkennen“ klickst (oder auf das Schwebe-Icon bzw.
„Jetzt erkennen“ im Statusleisten-Menü, falls du diese eingeschaltet hast). Der Schalter
„Dauer-Modus“ startet von sich aus nichts; erst der Klick startet ihn, der nächste Klick beendet ihn.
Die Pegelanzeige für Desktop-Audio wird nur auf deinem Rechner berechnet. Tempo, Tonart und Energie
misst die App ebenfalls nur lokal an der öffentlichen 30-s-Hörprobe (Deezer); die Hörprobe wird dafür nur im
Arbeitsspeicher dekodiert und nicht gespeichert – gespeichert werden nur die drei Zahlen. Das Mikrofon wird nur
während einer Erkennung oder bei „Pegel testen“ geöffnet.

Wählst du unter „Gerät“ eine einzelne **Anwendung** (z. B. nur den Browser), wird nur deren Ton
aufgenommen. Sprach- und Videochat-Programme (Discord, Teams, Zoom, Skype …) werden dort nie angeboten.

## Mikrofon – bitte beachten
Das Mikrofon nimmt alles im Raum auf. Das nicht öffentlich gesprochene Wort anderer ohne deren
Einverständnis aufzunehmen, ist in Deutschland strafbar (§ 201 StGB). Nutze das Mikrofon nur für Musik und
nur, wenn niemand ungewollt mit aufgenommen wird. Standardmäßig geht beim Mikrofon nur der
Shazam-Fingerabdruck raus.

## Deine Kontrolle
In der App unter **Einstellungen → Datenschutz**: Einwilligungen ändern/widerrufen, Audio-Weitergabe ein/aus,
Verlauf löschen, Zwischenspeicher leeren, „immer laden“ für eingebettete Player widerrufen. Konten unter
**Dienste** oder **Übertragen** trennen (Token wird gelöscht). Den automatischen Abgleich unter **Neu für dich**
ausschalten oder zurücksetzen.
Die rechtliche Verantwortung für die Nutzung auf deinem Rechner liegt bei dir.

## Rücksicht auf die Dienste (Rate-Limits)
SH-Tunebridge hält sich vorab an die Anfrage-Grenzen der Dienste (Last.fm ≤ 5/s, Deezer 50 pro 5 s,
iTunes ~20/min, Shazam vorsichtig 12/min). Blockt ein Dienst trotzdem, pausiert die App ihn und zeigt
„Limit erreicht – wieder frei in … s“ an. Während einer Shazam-Pause wird nichts aufgenommen.

## Weniger Anfragen: Song-Speicher, lokale Wiedererkennung, Dauer-Modus

- **Song-Speicher:** Einmal nachgeschlagene Songs (Genre, Links, Cover- und Hörproben-*Adressen* – keine Bilder
  oder Audiodateien) bleiben lokal gespeichert. Häufig gebrauchte Einträge hält die App zusätzlich im
  Arbeitsspeicher, damit sie schneller ist. Erkennt die App denselben Song wieder, fragt sie Deezer, Last.fm und iTunes nicht
  erneut (frisch nachgeschlagen wird nach 30 Tagen oder auf „Infos neu laden“).
- **Lokale Fingerabdrücke:** Nach einer sicheren Erkennung merkt sich die App Frequenz-Merkmale
  (Hashes) der Aufnahme – kein Ton, daraus lässt sich nichts anhören. Läuft dieselbe Stelle
  wieder, erkennt die App den Song ohne Shazam-Anfrage. Bei einem **unsicheren Treffer** fragt die
  App nach („Stimmt“ / „Falsch“): Die Hashes bleiben bis dahin nur im Arbeitsspeicher (höchstens
  eine Stunde) und werden erst nach „Stimmt“ gespeichert; „Falsch“ verwirft sie und löscht den
  Eintrag aus dem Verlauf. Nichts davon wird gesendet.
- **Dauer-Modus:** Nach einem Treffer wartet die App, solange derselbe Song läuft, und hört dabei
  nur lokal auf Pausen und Klangwechsel (Pegel/Frequenzbänder im Arbeitsspeicher, nichts wird
  gespeichert oder gesendet). Zusätzlich liest sie über die Linux-Mediensteuerung (MPRIS), ob dein
  Player einen neuen Titel meldet. Das gilt nur, solange du den Dauer-Modus selbst gestartet hast.
- Unter Einstellungen › Speicher & Cache siehst du, was wie viel Platz belegt, und kannst es leeren.

## KI-Analyse (Claude, OpenAI, Gemini, Programme auf deinem Rechner, eigener Server)

Standard ist das **lokale Modell** – dabei verlässt nichts deinen Rechner. Wählst du unter Einstellungen › KI
einen Cloud-Anbieter, brauchst du einen **eigenen API-Key** und musst der Weitergabe einmal ausdrücklich zustimmen.
Gesendet werden dann nur Künstler, Titel, Album, Tags und Genre-Ergebnisse, bei einer Playlist-Analyse und bei der
„KI-Prüfung“ beim Sortieren (nur wenn du sie einschaltest) die Songliste mit diesen Angaben.
Kein Ton, keine Konten. Empfänger ist der jeweilige Anbieter (Anthropic, OpenAI, Google); es gelten deren
Bedingungen und Datenschutzbestimmungen, die Kosten rechnet der Anbieter direkt mit dir ab. Bei kostenlosen
Gemini-Keys kann Google Eingaben zur Verbesserung seiner Dienste nutzen (laut Google nicht im EWR, UK und der
Schweiz). Automatische Anfragen nach jeder Erkennung sind bei Cloud-Anbietern standardmäßig aus.
Login-Daten von Abos (ChatGPT, Claude, Gemini) liest die App nie aus. Ist ein **offizielles Programm** des Anbieters
installiert (Claude Code, Codex CLI, Gemini CLI), kann die App es auf deinen Wunsch starten und ihm die Frage geben –
das Programm meldet sich selbst an, es gelten dessen Bedingungen; Zustimmung wie bei den API-Keys. Lokale Server
(llama.cpp, Ollama, LM Studio, Jan) sucht die App nur auf deinem eigenen Rechner (127.0.0.1).
Nutzt du **mehrere KIs zusammen** („Abstimmung“), gehen dieselben Angaben an jede gewählte KI.

## Links einfügen, Playlists ansehen, Hörproben

Fügst du einen Link ein, liest SH-Tunebridge über die **offiziellen Schnittstellen** nur Titel, Künstler, Album
und ISRC: Deezer (öffentlich), Spotify (deine eigene Spotify-App, nur eigene Playlists), TIDAL (deine Verbindung),
Apple (iTunes-Lookup), YouTube (oEmbed bzw. dein eigener API-Key), SoundCloud (oEmbed). Dabei sieht der jeweilige
Dienst deine IP-Adresse. Es wird nie Musik heruntergeladen.
Hörproben sind die offiziellen 30-Sekunden-Ausschnitte von Deezer bzw. Apple. Der Player spielt sie **direkt
vom Anbieter** ab (Streaming) – SH-Tunebridge lädt sie dafür nicht herunter und speichert sie nicht; nur die
Abspiel-Adresse liegt kurz im Arbeitsspeicher. Unter dem Player steht, woher die Hörprobe kommt
(bei Apple: „provided courtesy of iTunes“), mit Link zum Anbieter. Reine Privatnutzung.

**Cover** werden nie als Bilddatei gespeichert oder exportiert: Die App merkt sich höchstens die Bild-Adresse,
das Bild lädt dein Rechner jedes Mal direkt beim Anbieter (Hinweis „Cover: Deezer“ o. Ä. mit Link). Sicherungen
und Exporte enthalten keine Cover- oder Hörproben-Adressen.

Playlists deiner verbundenen Dienste (Seitenleiste „Deine Dienste“, Seite „Playlists“) werden nur angezeigt:
Titel, Künstler, Album und Cover-Adressen liegen höchstens 10 Minuten im Arbeitsspeicher, nichts davon wird
auf die Platte geschrieben.

**Grauzone Tempo/Tonart:** Für „Sortieren“ wertet die App die Deezer-Hörprobe lokal aus (siehe oben). Deezers
Bedingungen verbieten das nicht ausdrücklich, erlauben es aber auch nicht ausdrücklich; die Hörprobe wird dafür
nur im Arbeitsspeicher gehalten und sofort verworfen. Spotify-Inhalte werden nie ausgewertet (das verbietet
Spotify), Apple-Hörproben ebenfalls nicht.

## Offizielle Player (eingebettet, Klick zum Laden)

Im Song-Detail kann SH-Tunebridge zusätzlich zur eigenen 30-Sekunden-Hörprobe den **offiziellen Einbettungs-Player**
des Anbieters zeigen (YouTube über `youtube-nocookie.com`, Spotify, Apple Music, TIDAL, SoundCloud, Deezer). Es
werden nur die Player genutzt, die der Anbieter selbst zum Einbetten anbietet, unverändert (keine Werbung
ausgeblendet, kein Ton abgegriffen).

- **Vorher wird nichts geladen.** Erst wenn du bei einem Anbieter auf „Player laden“ klickst, holt das Fenster den
  Player direkt vom Anbieter. Dabei erhält er deine IP-Adresse und Geräte-/Browserdaten und kann Cookies setzen
  bzw. lesen. Google (YouTube) und Apple können Daten in die USA übermitteln (beide sind nach dem
  EU-US Data Privacy Framework zertifiziert).
- **Rechtsgrundlage:** deine Einwilligung durch den Klick (Art. 6 Abs. 1 lit. a DSGVO, § 25 Abs. 1 TDDDG).
  Setzt du „Für … immer laden“, gilt das nur für diesen Anbieter und nur auf diesem Rechner; widerrufen unter
  Einstellungen › Datenschutz › „Offizielle Player“ → „Alle widerrufen“, oder einfach „Player schließen“.
- Für alles, was im Player passiert, ist der jeweilige Anbieter verantwortlich; es gelten seine
  Datenschutzhinweise (im Hinweis vor dem Laden verlinkt). Der Entwickler erhält davon nichts.

## Mehr vom Künstler

Im Song-Detail zeigt die App weitere Songs der beteiligten Künstler – getrennt in **Solo** und **Zusammen mit
anderen**. Der Künstler wird nicht über den Namen gesucht, sondern über den schon geprüften Song (Künstler und
Titel stimmen), damit keine Namensvettern auftauchen. Quelle ist Deezers öffentliche Schnittstelle (ohne Login);
die Liste bleibt höchstens eine Stunde im Arbeitsspeicher und wird nicht gespeichert. Hörproben dazu kommen wie
immer direkt vom Anbieter.

## Mix erstellen

Unter *Mix erstellen* baut die App aus Künstlern, die du auswählst, oder aus einem Genre/Subgenre eine neue Playlist.
Dafür geht an **Deezers öffentliche Schnittstelle** (ohne Login) nur der Künstlername, den du ins Suchfeld tippst, und
danach die Deezer-Kennungen der gewählten und ähnlicher Künstler (für Top-Songs, Künstler-Radio und ähnliche Künstler).
Bei der **Suche nach Genre** gehen nur die Genre-Tags (z. B. „liquid funk“) an **MusicBrainz** (offene Datenbank, CC0)
und – nur wenn du einen eigenen Last.fm-Key eingetragen hast – an **Last.fm**; die gefundenen Künstlernamen werden
danach bei Deezer gesucht. Deine Bibliothek, deine eigenen Einordnungen und die Gemeinschafts-Genre-Datenbank (falls
geladen) werden nur auf deinem Rechner ausgewertet und verlassen ihn nicht. Dabei sehen die Dienste wie bei jeder
Abfrage deine IP-Adresse. Für Tempo, Tonart und Energie wird – nur wenn die gewählte Stufe oder ein eigener
Filter es braucht – die offizielle 30-s-Hörprobe gestreamt und im Arbeitsspeicher ausgewertet (höchstens 150 pro Mix);
gespeichert werden wie beim Set-Planer nur die drei Zahlen.

Es gibt **keinen Suchverlauf**: Suchergebnisse und der fertige Mix bleiben nur im Arbeitsspeicher (höchstens 6 Stunden)
und werden erst gespeichert, wenn du „Als Playlist speichern“ wählst – dann als normale lokale Playlist. Deine zuletzt
gewählten Künstler und Einstellungen merkt sich nur die Oberfläche auf diesem Rechner. Nichts davon geht an den Server
des Entwicklers oder in die Gemeinschafts-Genre-Datenbank.

## Links öffnen

Links zu Diensten, Shops und Hilfeseiten öffnet die App in deinem **Standard-Browser** (nicht im App-Fenster).
Erst dann sieht die jeweilige Seite deine IP-Adresse; dort gelten deren Bedingungen.

## Discord-Status (optional, Standard: aus)

Schaltest du unter Einstellungen › Discord-Status die Anzeige ein, übergibt SH-Tunebridge dem **Discord-Programm
auf deinem Rechner** (lokale Schnittstelle, kein Internet-Umweg über den Entwickler), was du dort ausgewählt hast:
erkannter Song bzw. laufende Hörprobe (Titel, Künstler), auf Wunsch Cover-Adresse, Genre, Laufzeit, ein Link zum
Song bei Deezer und der Bereich der App, in dem du gerade bist (z. B. „Sortiert eine Playlist“ – keine Namen von
Playlists). Discord zeigt das deinen Kontakten; dafür gelten die Bedingungen von Discord. Ausschalten löscht den
Status sofort.

## Datenexporte der Dienste importieren (ohne Login)

Statt dich anzumelden, kannst du bei Spotify („Daten herunterladen“ → Kontodaten), Google (Takeout → YouTube:
Playlists und Musikbibliothek), in der Musik-App von Apple („Mediathek exportieren“) oder bei Shazam (Datenauskunft über shazam.com/privacy;
ältere „shazamlibrary.csv“-Dateien gehen auch) eine Kopie deiner Daten anfordern – das ist dein Recht nach Art. 15
und 20 DSGVO – und die Datei in SH-Tunebridge laden. Eine Anmeldung mit dem Shazam-Konto gibt es bewusst nicht:
Shazam/Apple bieten dafür keine Schnittstelle für fremde Apps. Aus der Shazam-Datei werden nur Titel, Künstler,
Shazam-Song-Nummer und das Jahr des Scans (für die Jahres-Playlists) gelesen; die genauen Zeitpunkte werden nicht gespeichert.
Ausgewertet wird **nur auf deinem Rechner**: SH-Tunebridge liest daraus nur Playlist-Namen und Songs (Titel,
Künstler, Album, ISRC bzw. Video-ID). Alles andere im Export – z. B. Hörverlauf, Suchanfragen, Zahlungs- oder
Kontodaten – wird nicht gelesen und nicht gespeichert, die Datei selbst wird nach dem Einlesen verworfen.
Einzige Netzanfrage: Bei Google Takeout stehen in Playlists nur Video-Nummern. Die Titel dazu fragt SH-Tunebridge
einzeln bei YouTube ab (öffentliches oEmbed, ohne Konto und ohne Key); YouTube sieht dabei die Video-Nummer und
deine IP-Adresse. Nichts davon geht an den Entwickler.

## Android-App und Handy-Abgleich (Standard: aus)

Die Android-App von SH-Tunebridge erkennt Songs selbst und gleicht auf Wunsch mit deinem PC ab.

**Berechtigungen der App** (nur diese):
- **Internet** – für Shazam, Cover und den Abgleich mit dem PC.
- **Mikrofon** – wird erst beim ersten Tipp auf „Erkennen“ erfragt; aufgenommen wird nur, solange der Ring läuft
  (Standard 10 s). Die Aufnahme bleibt im Arbeitsspeicher, wird nie gespeichert und nicht hochgeladen. Hinweis zu
  § 201 StGB wie am PC (siehe „Mikrofon – bitte beachten“).
  **Offline merken** (Mehr › Erkennen, Standard: an): Ist kein Internet da, speichert die App nur den Fingerabdruck
  (dieselben Zahlenwerte, die sonst sofort an Shazam gingen – kein Ton, nicht in Ton zurückzuverwandeln) und fragt
  Shazam, sobald wieder Netz da ist. Höchstens 50 Stück, höchstens 30 Tage; „Verwerfen“ löscht sie sofort.
- **Kamera** – nur beim Koppeln mit dem PC (Mehr › Mit PC koppeln), um den QR-Code zu lesen. Bilder werden nicht gespeichert.
- **Vordergrund-Dienst „Bildschirm teilen“ + Benachrichtigungen** – nur für „Handy-Ton“: Statt des Mikrofons hört die
  App direkt, was auf dem Handy abgespielt wird (Android-Funktion AudioPlaybackCapture). Android fragt dafür jedes Mal
  im System-Dialog nach; vorher erklärt ein Hinweis, was passiert. Genutzt wird nur der Ton (Medien und Spiele),
  kein Bild; Telefonate gibt Android nie heraus, und Apps, die das Mithören sperren (z. B. Kopierschutz), bleiben
  gesperrt – das wird nicht umgangen. Gehört wird wie beim Mikrofon nur nach dem Tippen, nur im Arbeitsspeicher; an
  Shazam geht nur der Fingerabdruck. Solange die Freigabe besteht, läuft ein Dienst mit Benachrichtigung („Beenden“);
  nach 15 Minuten ohne Erkennen endet sie von selbst.
- **Vordergrund-Dienst „Medienwiedergabe“** – nur solange der Hörproben-Player etwas in der Warteschlange hat: Steuerung
  in der Benachrichtigung, auf dem Sperrbildschirm und über Kopfhörer-/Auto-Tasten (Android-Mediensitzung). Titel,
  Künstler und Cover sieht dabei nur dein Handy (bzw. ein verbundenes Auto/Uhr, wie bei jeder Musik-App). Stopp oder
  Wegwischen beendet den Dienst.
- **Dauer-Erkennen: Vordergrund-Dienst „Mikrofon“ + kurz wach halten** – nur wenn du es startest (Erkennen ›
  „Dauer-Erkennen …“, vorher Hinweis inkl. § 201 StGB): Die App hört alle 1, 2 oder 5 Minuten für die eingestellte
  Aufnahmedauer zu, genau wie bei einem Tipp – Ton nur im Arbeitsspeicher, an Shazam nur der Fingerabdruck. Läuft nur
  mit sichtbarer Benachrichtigung („Beenden“; ohne erlaubte Benachrichtigungen startet es nicht) und endet spätestens
  nach der gewählten Dauer (höchstens 4 Stunden). Damit die Abstände stimmen, hält die App das Handy so lange wach
  (Wake-Lock); jeder Durchgang ist eine Shazam-Anfrage. Derselbe Song innerhalb von 20 Minuten wird nur einmal eingetragen.
- **Andere Apps sehen** – nur die Frage, ob die Shazam-App installiert ist (für „Verlauf aus der Shazam-App“).
- **Apps installieren** („Unbekannte Apps installieren“) – nur damit die App ein selbst geladenes Update an den
  Android-Installer übergeben kann. Android fragt dafür einmal nach; installiert wird erst, wenn du im Installer
  bestätigst. Ohne diese Erlaubnis funktioniert alles andere genauso.

**Teilen & Export:** Erst wenn du auf Teilen tippst, schreibt die App eine Datei (Text, CSV oder M3U) mit Titel,
Künstler, Album, ISRC, Genre, Zeitpunkt, Quelle und einem Link in ihren Cache und übergibt sie an die App, die du im
Android-Teilen-Menü wählst. Keine Cover, keine Musik; die Datei wird beim nächsten Export ersetzt.

**Schnellzugriffe:** Kachel in den Schnelleinstellungen, Startbildschirm-Widget und App-Verknüpfungen
(„Erkennen“, „Handy-Ton“) öffnen nur die App und starten das Erkennen wie ein Tipp auf den Kreis – mit denselben
Hinweisen und Rückfragen. Das Widget zeigt den letzten Treffer, gespeichert nur auf dem Handy.

**Updates (Standard: aus):** Ist „Automatisch nach Updates suchen“ an (Willkommen oder Mehr › Über), fragt die App
höchstens einmal am Tag beim Öffnen bei GitHub (`api.github.com`, Microsoft) nach neuen Versionen; von Hand geht das
mit „Nach Updates suchen“. GitHub sieht dabei die IP-Adresse und „SH-Tunebridge-Android“ als Programmkennung, sonst
nichts. Ein Update wird nur angeboten, wenn sein Manifest mit dem Release-Schlüssel signiert ist (geprüft mit der
Bibliothek Bouncy Castle, MIT-Lizenz); das geladene APK wird mit Größe und SHA-256 aus dem Manifest verglichen und
sonst verworfen. Android nimmt das Update zusätzlich nur an, wenn es mit demselben App-Schlüssel signiert ist.
Die Entwicklerversion sucht nie nach Updates.

**Verlauf aus der Shazam-App (nur mit Root, Standard: aus):** Auf gerooteten Handys kann die App unter
Mehr › Shazam-App deinen eigenen Shazam-Verlauf übernehmen. Vorher erscheint einmal eine ausdrückliche Warnung
(Root-Risiken, nur für erfahrene Nutzer, Nutzung auf eigene Verantwortung), die du bestätigen musst; danach fragt
dein Root-Manager selbst nach. Die App kopiert die Datenbank der Shazam-App kurz in ihren eigenen Cache, liest
daraus **nur** Song-Nummer, Titel, Künstler und Zeitpunkt und löscht die Kopie sofort. Nicht gelesen werden der
dort gespeicherte Standort, die Audio-Signatur sowie Konto- und Anmeldedaten; an der Shazam-App wird nichts
verändert. Fehlen Titel oder Künstler, fragt die App sie wie beim Teilen bei Shazam nach (Song-Nummer, IP-Adresse).
Die übernommenen Songs werden wie eigene Erkennungen mit gekoppelten PCs abgeglichen.

**Was die App sendet:**
- **Shazam (Apple):** wie am PC nur den Fingerabdruck der Aufnahme – kein hörbares Audio –, dazu Sprache/Land
  und technisch deine IP-Adresse. Teilst du einen Shazam-Link an die App, fragt sie bei Shazam die Song-Angaben
  zu dieser Song-Nummer ab.
- **Hörproben (Player):** Erst wenn du auf Reinhören/Abspielen tippst, streamt die App die offizielle
  30-Sekunden-Hörprobe direkt von Apple bzw. Deezer – nichts wird gespeichert. Deezer-Adressen laufen nach einiger
  Zeit ab; dann fragt die App bei Deezer (`api.deezer.com`) nach der aktuellen Adresse – mit Deezer-Nummer, ISRC oder
  Künstler + Titel des Songs. Deezer/Apple sehen dabei deine IP-Adresse. Den ganzen Song gibt es nur in deiner
  Musik-App („Öffnen“).
- **Mix erstellen & Set-Planer:** Rechnen am gekoppelten PC (verschlüsselt wie der Abgleich, nur im eigenen Netz/VPN).
  Das Handy schickt nur den Suchbegriff bzw. die gewählten Künstler/Genres und Einstellungen oder den Namen der
  Playlist; der PC fragt Deezer und misst Tempo/Tonart an den offiziellen Hörproben genau wie bei sich selbst (siehe
  oben). Gespeichert wird das Ergebnis nur, wenn du „Speichern“ tippst – als Playlist am PC.
- **Ähnliche Songs:** Kommen vom gekoppelten PC (verschlüsselt wie der Abgleich; der PC fragt Last.fm/Deezer wie bei
  sich selbst). Ist kein PC erreichbar, holt die App sie – nur wenn du es erlaubst („Ähnliche Songs ohne PC“, Standard:
  aus) – direkt bei Deezer: dafür gehen Titel und Künstler bzw. Deezer-Nummer/ISRC des Songs an Deezer, Deezer sieht
  deine IP-Adresse.
- **Cover:** Nur wenn du „Cover anzeigen“ einschaltest (beim ersten Start Standard: aus), lädt die App die Bilder
  direkt bei Apple/Deezer – die sehen dabei deine IP-Adresse.
- **Dein PC:** siehe unten. Sonst nichts – keine Google-Play-Dienste, kein Firebase, keine Analyse-, Absturz-
  oder Werbe-SDKs, keine Telemetrie. Android-Sicherungen in die Cloud sind für die App abgeschaltet.

**Koppeln und Abgleich mit dem PC:** Unter Einstellungen › Handy zeigt der PC einen QR-Code mit seinen Adressen
im eigenen Netz und einem Einmal-Code (100 Bit, 5 Minuten gültig, höchstens 8 Versuche, nur einmal nutzbar).
Gekoppelt wird nur mit **Zustimmung auf beiden Geräten**: Das Handy zeigt vorher, welche Adressen es benutzt und
was wann übertragen wird; danach zeigen Handy und PC dieselbe vierstellige Prüfzahl, und der PC fragt mit Gerätename,
IP-Adresse und App-Version nach („Zulassen“/„Ablehnen“, ohne Antwort nach 2 Minuten abgelehnt). Ein Handy kann mit
**mehreren PCs** gekoppelt sein; jede Kopplung hat ihr eigenes Geheimnis, Playlists bleiben dem jeweiligen PC zugeordnet.
Damit schickt das Handy verschlüsselt ein zufälliges Geräte-Geheimnis, das nur auf diesen beiden Geräten liegt
(am PC in `data/tokens/phone.json`, nur für dich lesbar). Jeder Abgleich ist mit AES-256-GCM verschlüsselt und
mit Zeitstempel und Einmal-Kennung gegen Wiederholung geschützt. Übertragen werden:
- vom Handy zum PC: die Erkennungen am Handy (Song, Zeitpunkt, Gerätename, Shazam-Angaben, ob unsicher/bestätigt),
  gelöschte Einträge und Änderungen an Playlists;
- vom PC zum Handy: deine Erkennungen am PC und deine lokalen Playlists (Titel, Künstler, Album, ISRC, Länge,
  Genre, Cover-Adresse, Hörprobe-Adresse, Dienst-Kennungen) – keine Konten, Tokens oder Schlüssel.

Songs vom Handy reichert der PC wie eigene Erkennungen an (Genre, BPM … über die Dienste in der Tabelle oben).
Der PC nimmt Handy-Anfragen nur auf einem eigenen Port (8766) an und nur, solange ein Kopplungs-Code offen ist oder
ein Handy gekoppelt und der Abgleich eingeschaltet ist. **Welche Netze**, legst du unter Einstellungen › Handy fest:
alle erkannten Heimnetze und VPNs (z. B. 192.168.178.0/24, 10.0.0.0/24, VPN), nur bestimmte oder nur das
Hauptnetz. Der PC lauscht dann ausschließlich auf seinen Adressen in diesen Netzen und nimmt nur Anfragen aus ihnen
an; virtuelle Netze (Docker, VMs) werden nie geöffnet. Erkannt werden die Netze aus den eigenen Netzwerkkarten des
PCs – dafür wird nichts gesendet. Der PC teilt dem gekoppelten Handy beim Abgleich seine aktuellen Adressen mit
(verschlüsselt), damit eine neue IP vom Router ankommt.

**Netzwerke erkennen nur mit Zustimmung (PC und Handy):** Bevor SH-Tunebridge die eigenen Netzwerkkarten ausliest
(IP-Adressen, Netze wie 192.168.178.0/24, Name der Karte, beim PC auch welche Karte ins Internet geht), fragt es
ausdrücklich – am PC unter Einstellungen › Handy, am Handy beim ersten Koppeln. Ohne Zustimmung wird nichts
ausgelesen, der PC öffnet keinen Handy-Zugang, und das Handy gleicht nicht ab; am PC ist das auch serverseitig
erzwungen (getestet in `tests/test_privacy.py`). Es wird kein Netz durchsucht, keine anderen Geräte, keine
WLAN-Namen, kein Standort; die Angaben bleiben auf dem Gerät. Widerruf jederzeit: PC unter Einstellungen › Handy ›
Netzwerke, Handy unter Mehr › Datenschutz › „Netzwerke erkennen“.

**Netze am Handy:** Je PC wählst du „Alle“, „Bestimmte“ oder „Nur diese“ Adressen. Die App liest dafür nur die
eigenen Netzwerkkarten des Handys (keine Standort- oder WLAN-Berechtigung) und spricht einen PC nur an, wenn das
Handy gerade im selben Netz ist – in fremden WLANs wird nichts versucht. Die
eigentliche App-Oberfläche bleibt nur auf deinem Rechner erreichbar. „Entfernen“ (PC) bzw. „Entkoppeln“ (Handy)
löscht das Geräte-Geheimnis; bereits übertragene Songs bleiben auf beiden Geräten, bis du sie löschst.

## Playlists teilen (Ende-zu-Ende verschlüsselt, Standard: aus)

Unter **Teilen** kannst du eigene Playlists mit Freunden teilen – ohne Konto, nur mit Schlüsseln:

- **Privater Schlüssel** (`SHT-P-…`): lesen und ändern, alle geteilten Playlists. Gehört nur dir (z. B. für
  deinen zweiten Rechner) – wie ein Passwort behandeln.
- **Öffentlicher Schlüssel** (`SHT-O-…`): nur lesen, nur die Playlists, die du als „öffentlich“ markierst.
  Den gibst du an Freunde weiter.

**Was geteilt wird:** je Song Titel, Künstler, Album, ISRC, Länge, Genre und Kennungen bei den Diensten.
**Nie:** Musik, Hörproben, Cover, Hörverlauf, Konten, Daten über dich.

**Was der Server sieht:** Die Playlists werden **auf deinem Rechner** mit AES-256-GCM verschlüsselt (Schlüssel
werden aus deinem privaten Schlüssel abgeleitet, der Server bekommt ihn nie). Gespeichert werden nur: eine
zufällige Bereichs-Kennung, ein Prüfwert (Hash) des Schreib-Schlüssels, zwei unlesbare Blöcke (privat und
öffentlich), eine Versionsnummer und das Datum (ohne Uhrzeit) der letzten Änderung. Keine IP-Adressen, keine
Namen, keine Playlist-Namen. Bereiche, die ein Jahr lang nicht geändert wurden, löscht der Server automatisch.
„Bereich löschen“ entfernt alles sofort; beide Schlüssel funktionieren danach nicht mehr.

**Wer was lesen kann:** nur wer einen Schlüssel hat – der Entwickler nicht. Wer deinen öffentlichen
Schlüssel weitergibt, gibt auch deine öffentlichen Playlists weiter; nimm sie dann aus „öffentlich“ heraus
oder lösche den Bereich und lege einen neuen an.

**Rechtliches:** Geteilt werden nur Songlisten (Titel/Künstler/Album) – keine Musik und keine geschützten
Bilder. Teile nur Playlists, die du selbst erstellt hast, und keine personenbezogenen Daten anderer (z. B. in
Playlist-Namen). Für das, was du teilst, bist du selbst verantwortlich. Playlists von Freunden werden nur
angezeigt; „In meine Playlists“ kopiert die Songliste in eine eigene, lokale Playlist.

## Öffentliches Playlist-Verzeichnis (Standard: aus)

Unter **Verzeichnis** kannst du Playlists anderer Nutzer durchstöbern, in eigene Playlists übernehmen und eigene
Playlists für alle sichtbar veröffentlichen. Dafür braucht es die Einwilligung „Öffentliches Playlist-Verzeichnis
nutzen“ (Art. 6 Abs. 1 lit. a DSGVO), weil das Verzeichnis auf dem Server des Entwicklers liegt.

- **Stöbern:** gesendet wird nur die Suchanfrage (Suchwörter, Genre, Seite) – technisch auch deine IP-Adresse,
  die die Annahme-Software nicht speichert (siehe „Technik vor dem Server“).
- **Veröffentlichen** geht nur einzeln, mit zwei ausdrücklichen Bestätigungen. **Für alle sichtbar** sind dann:
  Name der Playlist, dein selbst gewähltes **Pseudonym** (bitte kein Klarname), Genre, Beschreibung, Datum der
  letzten Änderung und je Song Titel, Künstler, Album, ISRC, Länge, Genre und Kennungen bei den Diensten.
  **Nie:** Musik, Hörproben, Cover, Konten, Rechnernamen.
- **Zuordnung:** Der Server speichert zusätzlich die Kennung deiner Installation (Hash deines
  Installations-Schlüssels), damit nur du deine Playlists ändern und löschen kannst. Sie ist für andere nicht
  sichtbar.
- **Texte:** Links, E-Mail-Adressen und Telefonnummern werden abgelehnt (gegen Spam und versehentlich
  veröffentlichte Kontaktdaten). Höchstens 500 Songs je Playlist und 20 Playlists je Installation.
- **Löschen:** jederzeit einzeln oder alles unter Verzeichnis › „Meine Veröffentlichungen“ – sofort, für alle.
  Das geht auch nach Widerruf der Einwilligung. Ohne Aktualisierung löscht der Server eine Playlist nach
  12 Monaten automatisch.
- **Melden (Art. 16 DSA):** Jede Playlist lässt sich mit Grund und optionaler Begründung melden. Gespeichert werden
  Grund, Begründung, Datum und die Kennung der meldenden Installation (nur gegen Mehrfach-Meldungen). Nach
  Meldungen von drei verschiedenen Installationen wird die Playlist automatisch ausgeblendet, bis der Betreiber
  sie geprüft hat. Bei deinen eigenen Playlists siehst du Status und Grund einer Ausblendung oder Sperre
  (Art. 17 DSA); Fragen und Widerspruch bitte per E-Mail an den Verantwortlichen (oben). Meldungen werden mit
  der Playlist gelöscht.
- **Verantwortung:** Veröffentliche nur Songlisten, die du selbst zusammengestellt hast, und keine Daten anderer
  Menschen. Für deine Texte bist du selbst verantwortlich. Übernommene Playlists werden nur als Songliste in eine
  lokale Playlist kopiert.

## YouTube- und SoundCloud-Login

Für alle Logins (Spotify, YouTube, SoundCloud, Last.fm-Key) führt ein Assistent Schritt für Schritt durch die
Einrichtung der eigenen Entwickler-App. Die eingegebenen Zugangsdaten bleiben nur auf deinem Rechner.

Beide Logins laufen **komplett auf deinem Rechner**: Du legst beim Dienst selbst eine App an (Google Cloud bzw.
SoundCloud-Entwicklerbereich) und trägst deren Client-ID und Client-Secret ein. Angemeldet wird im Browser direkt
beim Dienst (OAuth mit PKCE); SH-Tunebridge sieht dein Passwort nie. Die Rückleitung geht an
`127.0.0.1` (diesen Rechner), das Token liegt in `…/tokens/youtube.json` bzw. `soundcloud.json` (nur für dich
lesbar). Berechtigung beim Verbinden: **nur Lesen** (YouTube: `youtube.readonly`). Erst wenn du zum ersten Mal
zu YouTube **überträgst**, fragt SH-Tunebridge auf deinen Klick („Schreibrecht erteilen“) zusätzlich das Recht
`youtube` an – Google zeigt dir das vorher an. Damit werden nur private Playlists angelegt, Songs hinzugefügt oder
„Mag ich“ gesetzt, und zwar nur beim Übertragen. SoundCloud kennt keine getrennten Rechte; angelegte Playlists sind
dort ebenfalls privat. Zum Suchen der Songs gehen Titel und Künstler an den jeweiligen Dienst. „Trennen“ löscht das Token sofort. Für die
Verarbeitung durch Google bzw. SoundCloud gelten deren Datenschutzbestimmungen.

## Automatischer Abgleich („Neu für dich“)

Ist er eingeschaltet (Standard: an, alle 6 Stunden – wirkt aber nur, wenn du Dienste verbunden oder Profile
verknüpft hast), liest SH-Tunebridge die Lieblingssongs und – wenn gewünscht – Playlists deiner verbundenen
Dienste. Beim ersten Mal wird nur der Ist-Stand gemerkt. Neue Songs werden analysiert (wie beim Sortieren:
Deezer, Last.fm, MusicBrainz; KI nur, wenn du sie eingeschaltet hast) und erscheinen mit Playlist-Vorschlägen
unter „Neu für dich“. Gespeichert wird lokal nur: die Einstellungen, **kurze Prüfsummen** bereits gesehener Songs
(keine Titel) und die Liste der neuen Songs (höchstens 300, Cover nur als Adresse). Die gelesenen Dienst-Listen
bleiben im Arbeitsspeicher. An den Entwickler geht dabei nichts. Ausschalten und Zurücksetzen jederzeit unter
„Neu für dich“.

## Datenverbrauch

Die App zählt, wie viele Daten sie über das Internet lädt und sendet (Einstellungen › Datenverbrauch). Gezählt
wird nur auf deinem Rechner, gespeichert werden nur Tagessummen je Dienst (90 Tage). Nichts davon wird gesendet.

## Kaufen und KI-Musik-Hinweise

„Kaufen“ zeigt normale Links zu Qobuz, Bandcamp, Beatport, 7digital, iTunes und Amazon (sortiert von Hi-Res über
verlustfrei bis MP3/AAC) –
**ohne Provision oder Partner-Kennung**; der Entwickler verdient nichts daran. Erst beim Klick sieht der Shop
deine IP-Adresse.
Hinweise auf KI-generierte Musik ermittelt die App aus vorhandenen Angaben (Community-Tags bei Last.fm,
Label-/Titelangaben) und deiner eigenen Markierung. Das ist **kein Beweis** und wird nur als Hinweis mit Quelle
angezeigt. Deine Markierungen bleiben lokal; nur wenn du „Erkannte Songs senden“ erlaubst, geht der Hinweis-Status
mit.

## Genre-Datenbank (eigene Einordnungen und Gemeinschaft)

Unter **Genre-Datenbank** kannst du deine Playlists einordnen lassen und die Vorschläge bestätigen oder ändern;
im Song-Detail legst du mit **„Genre festlegen“** ein Genre selbst fest.

- **Was ausgewertet wird – lokal:** das Ergebnis der App, der **Name deiner Playlist** (z. B. „Hardtekk 2024“ →
  Hardtekk; Stimmungswörter wie „Chill“ oder „Party“ zählen nicht) und – nur wenn du es ankreuzt – ein Urteil
  deiner KI. Die KI bekommt dafür **nur Künstler, Titel, Album und Tempo**, ausdrücklich keine Tags oder Genres
  von Spotify, TIDAL, Last.fm oder Deezer. Es gelten die Hinweise unter „KI-Analyse“.
- **Gespeichert** wird erst, was du übernimmst – auf deinem Rechner. Deine Einordnung gilt sofort und geht bei der
  Erkennung allem anderen vor. Du kannst sie einzeln oder alle löschen.
- **Beitragen (nur mit Einwilligung):** gesendet werden je Song Datum, Künstler, Titel, ISRC, Genre, Subgenre und
  die Herkunft deiner Einordnung – **nie der Playlist-Name, nie ganze Playlists, kein Konto**. Es gelten dieselben
  Regeln wie im nächsten Abschnitt (pseudonyme Kennung, verschlüsselt, höchstens 12 Monate, selbst löschbar).
  Nur Einordnungen, die nach deiner Einwilligung entstehen, werden automatisch gesendet.
- **Genres deiner Bibliothek beitragen (nur mit Einwilligung, Einstellungen › Gemeinschaft):** für Songs, die die App
  schon kennt, wird das Genre **neu und nur aus freien Quellen** abgeleitet – MusicBrainz-Tags (CC0) und
  Genre-Angaben im Titel – und nur gesendet, wenn es mit dem Ergebnis der App übereinstimmt. Gesendet werden je Song
  Datum, Künstler, Titel, ISRC, Genre, Subgenre, Sicherheit und die freie Quelle; höchstens 2000 Songs pro Abgleich
  (der Rest folgt beim nächsten Abgleich), ohne Gesamtgrenze. Hier zählen auch Songs, die schon vor der Einwilligung bekannt waren. Daten von Last.fm,
  Deezer, Apple & Co. fließen **nicht** ein.
- **Abgleich manuell oder automatisch:** unter Einstellungen › Gemeinschaft wählst du, ob Beiträge und das Laden der
  Datenbank automatisch im Hintergrund (etwa alle 6 Stunden, Datenbank einmal am Tag) oder nur per Knopf passieren.
- **Gemeinschafts-Datenbank:** Der Entwickler wertet die Beiträge auf seinem eigenen Rechner aus. Übernommen
  wird ein Genre erst, wenn **mehrere verschiedene Installationen** (mindestens drei) es übereinstimmend melden
  und mindestens eine Meldung nicht nur von einer KI stammt; Widersprüche prüft der Entwickler von Hand. Die
  fertige Datenbank enthält **nur Song → Genre, Subgenre und die Zahl der Stimmen** – keine Kennungen, keine
  Zeitpunkte, nichts über einzelne Nutzer. Sie wird mit dem Release-Schlüssel signiert; die App nutzt sie nur,
  wenn die Signatur stimmt.
- **Laden (nur mit Einwilligung):** einmal am Tag, nur die Anfrage selbst wird gesendet. Nimmst du die Einwilligung
  zurück, löscht die App die geladene Datei.
- **Rechtsgrundlage:** deine Einwilligung (Art. 6 Abs. 1 lit. a DSGVO), jederzeit widerrufbar. Löschst du deine
  Beiträge auf dem Server, fließen sie in künftige Fassungen der Datenbank nicht mehr ein.
- **Keine fremden Datenbanken:** In die Gemeinschafts-Datenbank fließen nur Urteile von Menschen bzw. ihrer KI
  (aus Fakten) und freie Daten – keine Daten, die aus Spotify, TIDAL, Last.fm & Co. abgezogen wurden.

## Liste „Nicht erkannt“ und Senden an den Entwickler

Findet die App keinen Treffer oder kein Genre, legt sie (wenn erlaubt) einen Eintrag an: Datum, Pegel,
Fehlermeldungen der Dienste, unsichere Treffer – und, falls erlaubt, was laut Player gerade lief. Das bleibt
auf deinem Rechner, bis du das Senden erlaubst oder unter Einstellungen › Nicht erkannt selbst auf
„An Entwickler senden“ klickst (mit Vorschau, was genau gesendet wird).

- **Empfänger:** der Verantwortliche (oben), Server in Deutschland, ausschließlich
  `https://shtunebridge.bs002.de`. Keine Weitergabe an Dritte, kein Verkauf, keine Werbung.
- **Zwecke:** Erkennung und Genre-Zuordnung verbessern, Fehler finden und beheben, die Software optimieren,
  Songs und Genres analysieren.
- **Rechtsgrundlage:** deine Einwilligung (Art. 6 Abs. 1 lit. a DSGVO). Freiwillig, jederzeit mit Wirkung
  für die Zukunft widerrufbar (Schalter in den Einstellungen); die App funktioniert ohne Einschränkung weiter.
- **Pseudonym statt Name:** Deine Installation ist dort nur eine zufällige Kennung (Hash eines Schlüssels,
  den die App erzeugt und der nur auf deinem Rechner liegt). Damit kannst nur du deine Daten einsehen und
  löschen. Der Entwickler kann daraus nicht ableiten, wer du bist.
- **Schutz:** Übertragung per HTTPS, jede Anfrage von deiner Installation signiert. Auf dem Server wird jeder
  Eintrag sofort verschlüsselt; lesen kann ihn nur der Entwickler auf seinem eigenen Rechner. Die
  Annahme-Software speichert keine IP-Adressen (nur kurz im Arbeitsspeicher gegen Missbrauch) und von
  Zeitpunkten nur den Tag.
- **Dauer:** höchstens 12 Monate, dann automatisch gelöscht.
- **Selbst löschen und Auskunft:** in der App „Alles von mir dort löschen“ (sofort, ohne Begründung) und
  „Was liegt dort von mir?“.

### Technik vor dem Server: Firewall und Proxy
Die Verbindung läuft über eine Firewall (**pfSense**) und einen Reverse-Proxy (**Nginx Proxy Manager**),
beide vom Verantwortlichen selbst betrieben. Deshalb ist das Senden nur **teilweise anonym**: Die Inhalte
tragen keinen Namen, aber dort werden Verbindungsdaten protokolliert:
**IP-Adresse, Zeitpunkt, Anfragemethode und Pfad (z. B. `/v1/misses`), angefragter Host, Statuscode,
übertragene Datenmenge, Programmkennung (User-Agent „SH-Tunebridge“)** sowie auf der Firewall Ziel-Port und
Protokoll. Inhalte deiner Einträge sind darin nicht enthalten.
- **Zweck:** Schutz vor DDoS-Angriffen, Hacking-Versuchen, Bots und Spam; sicherer Betrieb und Fehlersuche.
- **Rechtsgrundlage:** berechtigtes Interesse (Art. 6 Abs. 1 lit. f DSGVO).
- **Speicherdauer:** höchstens 12 Monate, danach automatische Löschung; eine Auswertung erfolgt nur bei
  Störungen oder Angriffen.

### Deine Rechte
Du hast das Recht auf Auskunft (Art. 15), Berichtigung (Art. 16), Löschung (Art. 17), Einschränkung (Art. 18),
Datenübertragbarkeit (Art. 20) und Widerspruch (Art. 21 DSGVO) sowie das Recht, eine erteilte Einwilligung
jederzeit zu widerrufen (Art. 7 Abs. 3). Da der Entwickler dich nicht kennt, nenne bei Anfragen per E-Mail
bitte die Kennung aus Einstellungen › Nicht erkannt (Art. 11 DSGVO) – am schnellsten geht es direkt in der App.
Du kannst dich außerdem bei einer Datenschutz-Aufsichtsbehörde beschweren (Art. 77 DSGVO), z. B. bei der
Behörde deines Bundeslandes.

## Debug-Protokoll
Standardmäßig **aus**. Eingeschaltet schreibt SH-Tunebridge die einzelnen Schritte (erkannte Songs, Tags,
Fehlermeldungen, Gerätenamen, Systeminfos) in `<Daten>/logs/debug.log` – nur auf deinem Rechner, höchstens
ca. 6 MB, ältere Einträge werden überschrieben. API-Schlüssel, Tokens, Benutzer- und Rechnername werden
geschwärzt. **Das Protokoll selbst wird nie automatisch gesendet** (nur kurze Fehlerberichte, wenn du das
erlaubt hast – siehe oben): „Bericht speichern“ legt eine Textdatei in deinen
Download-Ordner; ob und wem du sie schickst, entscheidest du. Vorher kannst du dir unter „Ansehen“ genau
anschauen, was drinsteht. „Leeren“ löscht das Protokoll.

## Inoffizielle Schnittstellen
Shazam (über `shazamio`) und TIDAL (über `tidalapi`) werden über inoffizielle, öffentlich bekannte
Schnittstellen angesprochen. Das berührt ggf. die Nutzungsbedingungen dieser Dienste. SH-Tunebridge umgeht
keinen Kopierschutz und lädt keine kompletten Songs herunter – nur die offiziellen 30-s-Hörproben.
