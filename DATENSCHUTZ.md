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

Nie gesendet: Ton/Aufnahmen, Rechner-, Benutzer- oder Gerätenamen, Konten, Tokens, Playlists, Uhrzeiten.
Automatisch gesendet wird nur, was nach deiner Einwilligung entsteht (etwa alle 6 Stunden).

## Was bleibt auf deinem Rechner
- Verlauf, Playlists, Einstellungen (SQLite-Datenbank in `~/.local/share/tunebridge`)
- API-Keys und Login-Tokens (`~/.config/tunebridge/config.env`, `…/tokens/`, nur für dich lesbar)
- Sicherungen (Ordner frei wählbar)
- Das lokale KI-Modell und alles, was es verarbeitet
- Darstellung: Farben und ein eigenes Hintergrundbild (verkleinert, im Datenordner unter `appearance/`)
- Automatischer Abgleich: Einstellungen, Prüfsummen schon gesehener Songs (keine Titel) und die Liste „Neu für dich“
- Deine Entscheidungen zu eingebetteten Playern („immer laden“ je Anbieter, im Speicher des App-Fensters)
- Selbst gelernte Genres: unbekannte Last.fm-Tags deiner Songs und wie oft sie vorkamen. „Vorschlagen“
  öffnet nur ein GitHub-Issue mit dem Genre-Namen (ohne deine Songs) – abschicken musst du es selbst.

**Aufnahmen werden nie gespeichert.** Der Ausschnitt (6–20 s) liegt nur während der Erkennung als
temporäre Datei vor und wird danach sofort gelöscht. Stille wird gar nicht erst verschickt.

## Was deinen Rechner verlässt – und wann

| Empfänger | Daten | Wann |
|---|---|---|
| Shazam (Apple) | Fingerabdruck der Aufnahme – **kein hörbares Audio** | nur nach Klick auf „Erkennen“ (im Dauer-Modus bis zum nächsten Klick). Wird nichts Sicheres gefunden, bis zu 9 weitere Fingerabdrücke der lokal im Tempo umgerechneten Aufnahme (Slowed/Sped-up-Erkennung) |
| AudD, ACRCloud | Aufnahme-Ausschnitt (Audio) | **nur mit deiner Zustimmung**, getrennt für Desktop und Mikrofon |
| Deezer, iTunes-Suche, Last.fm, MusicBrainz | Künstler und Titel (ggf. ISRC); zur Genre-Prüfung die Kennung des schon gefundenen Künstlers | nach einer Erkennung, beim Link-Einfügen, Sortieren und automatischen Abgleich (Cover, Hörprobe, Genre, Mikro-Genre) |
| Deezer („Mehr vom Künstler“) | Kennung des Songs bzw. Künstlers | beim Öffnen eines Songs |
| YouTube, Spotify, Apple, TIDAL, SoundCloud, Deezer (offizielle Player) | IP-Adresse, Geräte-/Browserdaten, ggf. Cookies des Anbieters | **erst nach deinem Klick** auf „Player laden“ (siehe unten) |
| Webseiten, die du über „Öffnen“ oder „Kaufen“ aufrufst | IP-Adresse (dein Standard-Browser) | erst beim Klick |
| Spotify, TIDAL, Deezer, Last.fm, YouTube, SoundCloud | Abruf deiner Playlists und Lieblingssongs; bei Spotify/TIDAL auf Wunsch neue Playlists anlegen | unter „Dienste“ und beim automatischen Abgleich – nur mit deinem verbundenen Konto bzw. deinem öffentlichen Profil |
| Google (YouTube), SoundCloud | Anmeldung über deine **eigene** App (Client-ID/-Secret); Login-Token | nur wenn du den Login einrichtest – direkt zwischen deinem Rechner und dem Dienst, kein Server dazwischen |
| Deezer, Apple; bei verbundenen Diensten auch deren Bild-Server | deine IP-Adresse | beim Anzeigen von Covern und Abspielen von Hörproben (direkt vom Anbieter) |
| TIDAL | Playlists/Songs | nur wenn du TIDAL verbindest und überträgst |
| GitHub | deine IP-Adresse | Update-Prüfung (alle 6 Std.) |
| Hugging Face, GitHub | deine IP-Adresse | einmalig beim Download von Modell/Laufzeit |
| Entwickler (`shtunebridge.bs002.de`) | die Kategorien, die du erlaubt hast (siehe oben) + technisch deine IP-Adresse | **nur mit Einwilligung** |

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
  wieder, erkennt die App den Song ohne Shazam-Anfrage.
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

## YouTube- und SoundCloud-Login

Beide Logins laufen **komplett auf deinem Rechner**: Du legst beim Dienst selbst eine App an (Google Cloud bzw.
SoundCloud-Entwicklerbereich) und trägst deren Client-ID und Client-Secret ein. Angemeldet wird im Browser direkt
beim Dienst (OAuth mit PKCE); SH-Tunebridge sieht dein Passwort nie. Die Rückleitung geht an
`127.0.0.1` (diesen Rechner), das Token liegt in `…/tokens/youtube.json` bzw. `soundcloud.json` (nur für dich
lesbar). Berechtigung: **nur Lesen** (YouTube: `youtube.readonly`). „Trennen“ löscht das Token sofort. Für die
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
