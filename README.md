<p align="center"><img src="assets/logo/logo.svg" width="120" alt="SH-Tunebridge-Logo"></p>

# SH-Tunebridge

Songs erkennen, bis ins Subgenre einordnen
(z. B. *Drum & Bass → Liquid / Neurofunk / Jump Up / Jungle*, *Dubstep → Riddim / Melodic / Tearout*),
ähnliche Songs finden, große Playlists in Genre-Playlists aufteilen, **Links zu Songs/Playlists einfügen und
analysieren**, reinhören, **Künstler direkt unterstützen** (Kauf-Links ohne Provision), **Hinweise auf KI-Musik**
sehen – und Playlists/Likes übertragen (**TIDAL** und **Spotify**). KI-Analyse lokal oder mit eigenem Key bei
Claude, OpenAI oder Gemini.

> **Community-Projekt – Nutzung auf eigene Gefahr.** SH-Tunebridge ist ein privates, kostenloses
> Projekt und steht in keiner Verbindung zu den angebundenen Diensten. Teile davon nutzen
> **inoffizielle Schnittstellen** – bitte vorher [„Community-Projekt, Haftung & Konten“](#community-projekt-haftung--konten) lesen.

## Installation als AppImage (empfohlen)

1. Unter [Releases](https://github.com/Bigsmoke002/SH-Tunebridge/releases) die Datei
   `SH-Tunebridge-<version>-x86_64.AppImage` herunterladen – am besten in einen festen Ordner wie `~/Programme`.
2. Ausführbar machen: Rechtsklick → Eigenschaften → „Als Programm ausführen“ – oder `chmod +x SH-Tunebridge-*.AppImage`.
3. Starten. SH-Tunebridge trägt sich selbst ins Startmenü ein und aktualisiert sich künftig selbst
   (nur signierte Versionen, vorher wird gesichert).

Beim Update lädt die App die neue Datei (`SH-Tunebridge-<neue version>-x86_64.AppImage`) in denselben Ordner.
Die alte Datei wird zu einem Verweis auf die neue – eigene Starter, Panel-Pins und Autostart-Einträge mit dem
alten Namen funktionieren also weiter.

Läuft auf aktuellen Linux-Desktops (x86_64, ab etwa Ubuntu 22.04 / Debian 12 / Fedora 38).
Falls das AppImage nicht startet, fehlt meist FUSE: Paket `fuse3` (bzw. `libfuse2`) installieren
oder mit `--appimage-extract-and-run` starten.

## Windows und macOS

**Windows 10/11 (64 Bit):** `SH-Tunebridge-<version>-windows-setup.exe` herunterladen und starten. Das Setup
installiert die App für deinen Benutzer (keine Adminrechte), legt Startmenü- und auf Wunsch Desktop-Verknüpfung an
und trägt sie unter *Einstellungen → Apps* ein (dort auch deinstallieren – deine Daten bleiben erhalten).
SH-Tunebridge ist unter Windows eine **richtige Desktop-App** (eigenes Fenster über Microsoft Edge WebView2, kein
Browser). Fehlt WebView2, installiert das Setup es von Microsoft mit; die App selbst bietet es sonst beim Start an.
Windows SmartScreen warnt beim ersten Start („Unbekannter Herausgeber“), weil das Programm nicht mit einem
kostenpflichtigen Zertifikat signiert ist → „Weitere Informationen“ → „Trotzdem ausführen“.
Desktop-Ton wird direkt über Windows (WASAPI-Loopback) aufgenommen – ohne Zusatzprogramme.
Wer lieber ohne Installation arbeitet: `SH-Tunebridge-<version>-windows-x64.zip` entpacken und `SH-Tunebridge.exe`
starten (dieses Paket nutzt auch der Updater).

**macOS (Apple Silicon):** `SH-Tunebridge-<version>-macos-arm64.dmg` öffnen und die App in „Programme“ ziehen.
Da die App nicht bei Apple notarisiert ist (kostet 99 $/Jahr), beim ersten Start: Rechtsklick → „Öffnen“
(bzw. *Systemeinstellungen → Datenschutz & Sicherheit → Trotzdem öffnen*).
Desktop-Ton erlaubt macOS nur über ein virtuelles Audiogerät, z. B. das kostenlose „BlackHole“; ohne
geht die Erkennung über das Mikrofon. Beim ersten Mal fragt macOS nach der Mikrofon-Erlaubnis.

Unterschiede zu Linux: einzelne Anwendungen lassen sich nur unter Linux getrennt aufnehmen, und „Was spielt
gerade?“ (Player-Erkennung) gibt es vorerst nur unter Linux. Updates: Die App prüft auf neue **signierte**
Versionen und installiert sie auf Klick (Windows/macOS: Austausch beim Neustart, vorher automatische Sicherung).
**Windows mit Version 0.6.0:** Diese Version startet nicht (Fehler im Fenstersymbol) und kann sich deshalb nicht
selbst aktualisieren – bitte 0.6.3 oder neuer einmal von Hand laden.
Gebaut und getestet werden diese Versionen auf GitHubs eigenen Windows- und Mac-Rechnern.

## Datenschutz

Kein Tracking, keine Werbung, kein Konto. Standardmäßig bleibt alles auf deinem Rechner. Beim ersten Start
fragt die App einmal, was gespeichert werden darf und ob (freiwillig, standardmäßig aus) anonymisierte
Daten zur Verbesserung an `shtunebridge.bs002.de` gesendet werden dürfen. Erhoben wird nur das Nötigste.
Details, was wann an wen geht: [DATENSCHUTZ.md](DATENSCHUTZ.md).

## Community-Projekt, Haftung & Konten

SH-Tunebridge ist ein privates, nicht-kommerzielles **Community-Projekt** von Bigsmoke002. Es ist kein
offizielles Produkt von Shazam/Apple, TIDAL, Spotify, Google/YouTube, SoundCloud, Deezer, Last.fm, AudD,
ACRCloud oder anderen genannten Diensten, wird von ihnen weder unterstützt noch geprüft. Genannte Namen und
Marken gehören ihren jeweiligen Inhabern und dienen nur der Beschreibung, womit die App zusammenarbeitet.

**Offizielle und inoffizielle Anbindungen** (Stand dieser Version):

| Dienst | Zugang | Wofür |
|---|---|---|
| Shazam | **inoffiziell** (`shazamio`, nachgebaute App-Schnittstelle) | Song-Erkennung (Fingerabdruck, kein Ton) |
| TIDAL | **inoffiziell** (`tidalapi`, Gerätelogin wie in der TIDAL-App – nicht die offizielle Developer-API) | Playlists lesen/anlegen, Lieblingssongs |
| Spotify | offiziell (Web API mit deiner eigenen Spotify-App, Client-ID; Besitzer braucht Premium) | eigene Playlists lesen/anlegen, Lieblingssongs |
| Claude, OpenAI, Gemini | offiziell (dein eigener API-Key, nur nach Zustimmung) | optionale KI-Analyse von Songs/Playlists |
| YouTube | offiziell (YouTube Data API: Google-Login mit deiner eigenen OAuth-App, nur Lesen; oEmbed für Links) | Playlists und „Mag ich“ lesen, Links einlesen |
| SoundCloud | offiziell (SoundCloud API mit deiner eigenen App – Konto braucht Artist Pro; oEmbed für Links) | Playlists und Likes lesen, Links einlesen |
| AudD, ACRCloud | offiziell (dein eigener API-Key) | optionale Erkennung mit Audio-Ausschnitt |
| Last.fm | offiziell (dein eigenes API-Konto; Login über die Last.fm-Web-Anmeldung) | Genre-Tags, Loved Tracks |
| Deezer | offiziell (öffentliche API ohne Login) | Cover, Hörprobe, BPM, Genre |
| iTunes-Suche (Apple) | offiziell (öffentliche Such-API) | Links, Cover |
| GitHub | offiziell | Update-Prüfung und -Download |
| Hugging Face | offiziell | optionaler Download des lokalen KI-Modells (Gemma-Bedingungen) |
| `shtunebridge.bs002.de` | Server des Entwicklers | nur mit deiner Einwilligung (siehe Datenschutz) |
| „Öffnen in …“ (Spotify, YouTube, SoundCloud …) | normale Such-Links im Browser | kein API-Zugriff |
| „Kaufen“ (Qobuz, Bandcamp, Beatport, 7digital, iTunes, Amazon) | normale Shop-Links, **ohne Provision**, sortiert von Hi-Res über verlustfrei bis MP3/AAC | Künstler unterstützen |

**Hörproben und GEMA:** Abgespielt werden nur die offiziellen 30-Sekunden-Hörproben von Deezer/Apple, privat auf
deinem Rechner und direkt vom Anbieter gestreamt (mit Quellenhinweis). Es wird keine Musik heruntergeladen,
gespeichert oder öffentlich wiedergegeben – damit entsteht keine GEMA-Pflicht. Cover werden nur angezeigt
(direkt vom Anbieter geladen, mit Quelle) und nie als Datei gespeichert oder exportiert. Wer die App öffentlich nutzt (z. B. Hörproben in einem Laden
oder auf einer Veranstaltung abspielt), braucht dafür selbst die nötigen Lizenzen.

**KI-Musik-Hinweise** stammen aus Community-Tags und Angaben der Dienste und sind **kein Beweis**. Sie werden
nur als „möglicherweise KI-generiert“ mit Quelle angezeigt und lassen sich von dir korrigieren.

Inoffizielle Schnittstellen können jederzeit ohne Vorwarnung aufhören zu funktionieren, und ihre Nutzung
ist von den Nutzungsbedingungen des jeweiligen Dienstes möglicherweise nicht gedeckt.

**Konten und Logins:** Du meldest dich direkt beim jeweiligen Dienst an (Gerätelogin im Browser bzw. dein
eigener API-Key). SH-Tunebridge speichert keine Passwörter; Tokens und Keys liegen nur auf deinem Rechner.
Ob die Nutzung mit deinem Konto zulässig ist, richtet sich nach den Bedingungen des jeweiligen Dienstes –
das zu prüfen liegt bei dir. Es ist nicht auszuschließen, dass ein Dienst die Nutzung inoffizieller Zugänge
erkennt und dein Konto einschränkt, sperrt oder löscht. Wer das nicht riskieren möchte, verbindet keine Konten
und nutzt nur die offiziellen Anbindungen.

**Haftung:** SH-Tunebridge wird kostenlos und ohne Gewähr überlassen; die Nutzung erfolgt auf eigene
Verantwortung. Soweit gesetzlich zulässig, haftet der Entwickler nicht für Schäden aus der Nutzung –
insbesondere nicht für Datenverlust, fehlerhafte, doppelte oder gelöschte Playlists und Likes, falsche
Erkennungen oder Genres sowie für Einschränkungen, Sperren oder Löschungen von Konten bei Drittanbietern.
Unberührt bleibt die Haftung für Vorsatz und grobe Fahrlässigkeit, bei arglistig verschwiegenen Mängeln,
bei Verletzung von Leben, Körper oder Gesundheit sowie nach dem Produkthaftungsgesetz
(verbindlich: [LICENSE](LICENSE), Abschnitt 6). Lege vor dem Übertragen eine Sicherung an.

## Installation mit uv (Alternative, z. B. für Entwickler)
Voraussetzungen: `uv`, `parecord`/`pactl` (libpulse bzw. pulseaudio-utils), ein Browser.
```fish
./scripts/install.sh              # aus dem Projektordner
./scripts/install.sh <git-url>    # oder direkt aus dem Repo
```
Keys: `~/.config/tunebridge/config.env` (Vorlage: `config.env.example`).
Daten: `TUNEBRIDGE_DATA` in der config, sonst `~/.local/share/tunebridge`.

## Starten
```fish
tunebridge app       # eigenes Desktop-Fenster (Startmenü: „SH-Tunebridge“)
tunebridge ui        # dasselbe im Browser
tunebridge listen    # schnell im Terminal
```
Bereiche (Sidebar): **Erkennen · Verlauf · Playlists · Entdecken · Aufteilen · Übertragen · Einstellungen**.
Tastatur: `Leertaste` erkennen/abspielen, `Strg+1…6` Bereiche, `Strg+,` Einstellungen, `Esc` Panel schließen.
Keys lassen sich direkt unter *Einstellungen* eintragen.

## Daten, Sicherung & neuer Rechner
Alles liegt in **einer SQLite-Datenbank** (`$TUNEBRIDGE_DATA/tunebridge.db`, WAL, versioniertes Schema
mit automatischen Migrationen): Verlauf, Playlists, Genre-Cache.

- **Automatisch**: einmal täglich beim Start → `$TUNEBRIDGE_BACKUP_DIR` (z. B. `~/Backups/tunebridge`), die letzten 14 bleiben.
- **Manuell**: in der App unter *Sicherung* oder `tunebridge backup [--keys]`.
- Ein Backup ist eine Datei `*.tbbackup` (ZIP: DB-Schnappschuss, Exporte, optional `config.env`; Rechte 600).

**Rechner neu aufgesetzt:**
```fish
./scripts/install.sh                                  # App installieren
tunebridge restore ~/Backups/tunebridge/<datei>.tbbackup --keys
```
oder in der App: *Sicherung → Datei importieren → Wiederherstellen*.
`--merge` bzw. „Zusammenführen“ fügt ein Backup zu vorhandenen Daten hinzu (z.B. zweiter Rechner) –
ohne Duplikate. Vor jeder Wiederherstellung wird der aktuelle Stand automatisch gesichert.

## Updates & Releases
- Repo-Zugang von diesem Rechner: Host-Alias `github-sh-tunebridge` (Deploy-Key `~/.ssh/sh_tunebridge_github_deploy`).
- Releases werden **signiert** (`~/.ssh/sh_tunebridge_signing`); der öffentliche Schlüssel steht in
  `src/tunebridge/release_signers` und wird mit ausgeliefert.
- Neue Version veröffentlichen – immer in dieser Reihenfolge:
  1. `uv run pytest -q`, committen, pushen, dann `gh workflow run build --ref main` – Tests und Bau auf
     Linux, Windows und macOS inkl. Rauchtest (Server **und** App-Fenster wie per Doppelklick) müssen grün sein.
  2. `./scripts/release.sh X.Y.Z "Kurzbeschreibung" "Punkt 1" …` – testet, erhöht die Version, signierter Tag,
     Push, baut das AppImage (Docker, ubuntu:22.04) und lädt es mit signiertem Manifest hoch.
  3. Der Tag startet die CI „build“ (Windows-zip, macOS-dmg). Danach `./scripts/publish-platforms.sh X.Y.Z`
     (prüft, signiert die Manifeste und lädt hoch). macOS-Runner manchmal überlastet → `gh run rerun`.
  4. Änderungen in `CHANGELOG.md` eintragen.
- Die App prüft beim Start, danach **stündlich** (und unter *Einstellungen → Jetzt prüfen*) auf neue
  **signierte** Versionen; nach einem Fehler (offline) nach 15 Minuten erneut. Sie zeigt die Änderungen, sichert
  die DB und installiert erst nach Klick. Unsignierte oder fremd signierte Versionen werden ignoriert; ein
  Release, dessen Dateien noch hochgeladen werden, wird einfach später erkannt. Der Signier-Schlüssel darf nie
  ins Repo und nie verloren gehen (Kopie mit ins Backup).
- Gemeinschafts-Genre-Datenbank: wird auf dem Rechner des Herausgebers gebaut und mit demselben Schlüssel
  signiert (Namespace `sh-tunebridge-genredb`); die App lädt sie höchstens einmal am Tag und nur mit Einwilligung.

## Song erkennen („Shazam“)
- Erkennung parallel über **Shazam** (kein Key), **AudD**, **ACRCloud** (Keys optional);
  stimmen mehrere überein, wird das angezeigt. SoundHound hat keine öffentliche API.
- Hörprobe: Apple-/Deezer-Vorschau (30 s), direkt vom Anbieter gestreamt.
- **Offizieller Player** (zusätzlich): YouTube, Spotify, Apple Music, TIDAL, SoundCloud, Deezer – lädt erst nach
  Klick und Datenschutz-Hinweis, „immer laden“ je Anbieter widerrufbar.
- **Mehr vom Künstler**: weitere Songs, getrennt in Solo und Zusammenarbeiten (Deezer, über den geprüften Song).
- Genre/Subgenre: Last.fm-Tags → Genre-Baum; optional lokales LLM fürs Subgenre;
  Notlösung über BPM (Deezer). **Künstler und Titel werden gegengeprüft**: Tags eines anderen Songs
  (Last.fm-Autokorrektur) zählen nicht, und Künstler-Tags von Namensvettern (z. B. „Kanine“: DnB-Produzent vs.
  Deathcore-Band) werden verworfen, wenn sie nicht zum Song-Genre bzw. zum geprüften Deezer-Künstler passen.
- Vorschlag der passenden Playlist: Genre-/Subgenre-Verteilung, Künstler, Tags und
  Playlist-Name (z.B. „Liquid Vibes“). Passt nichts → neue Genre-Playlist.
- **Dauer-Modus**: hört alle paar Sekunden zu und protokolliert jeden neuen Song (z.B. bei DJ-Sets).

## Dienste & Übertragen
- **Einrichten ohne Fachwissen:** Für Spotify, YouTube, SoundCloud und Last.fm führt ein Assistent Schritt für
  Schritt durch die Entwickler-App (Kopieren-Knöpfe, Skizzen, Häkchen-Kontrollen, Hilfe bei typischen Fehlermeldungen)
  und meldet dich danach an. Deezer: Login nicht möglich (Deezer nimmt keine neuen Entwickler-Apps an) – der
  Assistent hilft, das öffentliche Profil zu verknüpfen.
- **Ohne Login:** Spotify-Kontodaten (ZIP), Google Takeout (YouTube-Playlists + Musikbibliothek) oder die
  Apple-Music-Mediathek (XML) importieren – alle Playlists auf einmal, kein Premium, keine Entwickler-App.
- **Playlists teilen:** eigene Playlists per Schlüssel mit Freunden teilen – privater Schlüssel (lesen +
  ändern, z. B. für den zweiten Rechner), öffentlicher Schlüssel (nur lesen, nur freigegebene Playlists).
  Ende-zu-Ende verschlüsselt, nur Songlisten (keine Musik, keine Cover), standardmäßig aus. Details in
  [DATENSCHUTZ.md](DATENSCHUTZ.md#playlists-teilen-ende-zu-ende-verschlüsselt-standard-aus).

| Dienst | Status | Login |
|---|---|---|
| TIDAL | ✅ Playlists/Lieblingssongs lesen, Playlists anlegen, Songs liken | Gerätelogin im Browser, kein Entwickler-Key |
| Spotify | ✅ Playlists/Lieblingssongs lesen, Playlists anlegen | eigene kostenlose App im Spotify-Developer-Dashboard (Client-ID) |
| YouTube / YouTube Music | ✅ Playlists und „Mag ich“ lesen (nur Lesen) | Google-Login mit eigener OAuth-App (Desktop-App, Client-ID + Secret) |
| SoundCloud | ✅ Playlists und Likes lesen (nur Lesen) | Login mit eigener SoundCloud-App (Client-ID + Secret, Artist Pro nötig) |
| Apple Music | nur offiziell möglich | Apple Developer Program (99 $/Jahr) – kein inoffizieller Weg (Rechtslage) |

**Neu für dich:** Alle paar Stunden (einstellbar) schaut SH-Tunebridge in deine verbundenen Dienste. Neue Likes
und Playlist-Songs werden analysiert (Genre, Tempo) und mit Vorschlägen gezeigt, in welche deiner Playlists sie
passen – ein Klick sortiert sie ein. Alles lokal; gespeichert werden nur Prüfsummen schon gesehener Songs.

Abgleich: ISRC zuerst, sonst Textsuche + Fuzzy-Abgleich (Remix/VIP werden unterschieden).
Gefundene Treffer werden gespeichert – erneute Übertragungen kosten keine API-Aufrufe.

**„Öffnen in …“** im Song-Detail: direkte Links (Deezer, Apple Music über die freie iTunes-Suche, von den
Erkennungsdiensten gelieferte Links, TIDAL nach einem Abgleich), sonst Such-Links ohne API-Aufruf.

## Updates aus einem privaten Repo

Ist das GitHub-Repo privat, braucht jeder Rechner Lesezugriff: auf dem Rechner einen SSH-Schlüssel erzeugen,
im Repo unter *Settings → Deploy keys* **ohne** Schreibrecht hinzufügen und in `config.env`
`UPDATE_REPO=git@<ssh-alias>:Bigsmoke002/SH-Tunebridge.git` setzen. Bei einem öffentlichen Repo entfällt das.

## Lokales LLM

Einstellungen → **Lokales LLM**: Modell wählen (Leicht: Qwen3 4B · Mittel: Qwen3 8B · Qualität: Qwen3 32B),
Download läuft im Hintergrund (pausierbar, fortsetzbar, SHA256-geprüft). Ausführen auf **CPU + RAM** oder
**Grafikkarte** (Vulkan, NVIDIA/AMD/Intel). SH-Tunebridge startet dafür einen eigenen llama.cpp-Server auf
`127.0.0.1:8766` – nur bei Bedarf, stoppt nach 10 min ohne Nutzung und immer zusammen mit der App.
Speicherort: `<Daten>/llm` (änderbar über `TUNEBRIDGE_MODELS_DIR`).

## CLI
```fish
uv run tunebridge --help
uv run tunebridge genre "Netsky - Come Alive"
uv run tunebridge similar "Netsky - Come Alive" --same-sub
uv run pytest
```

## Ablauf einer Übertragung
```
Quelle --export--> data/exports/<quelle>.json --classify--> (Genres)
                          |                          \--split--> Genre-Playlists
                          \--transfer --to <ziel> --> Suche + Abgleich --> Ziel-Playlists
                                                       unsichere Treffer -> Report zum Prüfen
```
Abgleich (`matching.py`): **ISRC** zuerst (exakt), sonst Fuzzy-Vergleich von
Titel/Künstler/Dauer. Remix/VIP/Edit wird **nicht** mit dem Original verwechselt.

## Plattformen – was geht, was nervt (Recherche-Stand)
| Dienst | Zugang | ISRC | Hinweis |
|---|---|---|---|
| Spotify | Web API, eigene App (Dev-Mode reicht für dich selbst) | ja | Seit Ende 2024 für neue Apps **keine** Recommendations/Audio-Features/Genres mehr → Genres kommen von Last.fm & Co. |
| TIDAL | `tidalapi` (inoffiziell, Gerätelogin) – **umgesetzt** | ja | offizielle Developer-API wäre die sauberere Alternative |
| YouTube / YouTube Music | Data API v3 mit eigenem Google-OAuth-Client – **umgesetzt (nur Lesen)** | nein | YouTube-Music-Bibliothek (Alben, Uploads) bietet die API nicht; Likes landen meist in „Mag ich“ |
| SoundCloud | offizielle API mit eigener App (Artist Pro) – **umgesetzt (nur Lesen)** | teils | Tags der Uploader sind super für Subgenres |
| Apple Music | MusicKit | ja | **Apple Developer Program (99 $/Jahr)** nötig |

## Genre-Erkennung
- `genres/taxonomy.py`: Genre-Baum mit Tag-Synonymen – hier Subgenres ergänzen.
- `genres/classify.py`: gewichtete Tags → Genre/Subgenre + Sicherheit.
- Quellen: **Last.fm**, **MusicBrainz** (Song + geprüfter Künstler), Apple-/Deezer-Genres (fertig),
  Genre-Angaben im Titel („(Hardtekk Remix)“).
- **Genre-Datenbank** (`genredb.py`, Seite *Genre-Datenbank*): Playlists einordnen lassen (App-Ergebnis,
  Genre-Name der Playlist – nur lokal ausgewertet –, optional eine KI, die nur Künstler/Titel/Album/Tempo sieht),
  Vorschläge bestätigen oder korrigieren; im Song-Detail „Genre festlegen“. Eigene Einordnungen gelten sofort.
  Mit Einwilligung fließen sie pseudonym in die **Gemeinschafts-Genre-Datenbank** (erst ab mehreren unabhängigen
  Installationen, signiert mit dem Release-Schlüssel, Namespace `sh-tunebridge-genredb`).
  Geplant: Discogs-Styles, SoundCloud-Tags,
  optional **Audio-Analyse** (Essentia, Discogs-400-Modell, lokal) über 30-s-Previews
  (z. B. Deezer) – für Songs ohne brauchbare Tags.

## Roadmap
- [x] Datenmodell, Abgleich, Genre-Baum, Last.fm, Aufteilen (Vorschau), Tests
- [x] Song-Erkennung (Shazam/AudD/ACRCloud), Oberfläche, Playlist-Vorschläge, Dauer-Modus
- [x] Provider TIDAL, lokales KI-Modell, Sicherungen, signierte Updates
- [x] Song-Speicher, lokale Wiedererkennung, Liste „Nicht erkannt“, Einwilligungen beim ersten Start
- [x] Spotify (offiziell), Links einfügen & analysieren, KI-Anbieter (lokal/eigen/Claude/OpenAI/Gemini)
- [x] Kauf-Links ohne Provision, Hinweise auf KI-Musik
- [x] Windows und macOS (erste Version)
- [ ] Android
- [ ] Windows/macOS: „Was spielt gerade?“ über die System-Mediensteuerung
- [ ] Lokale Audio-Prüfung auf KI-Musik (offenes Modell, optional)
- [ ] `transfer` mit Report unsicherer Treffer (CSV/HTML zum Abhaken)
- [ ] Weitere Genre-Quellen + Audio-Analyse

## Lizenz

© 2026 Bigsmoke002 – alle Rechte vorbehalten. Private, nicht-kommerzielle Nutzung ist erlaubt;
kopieren, verändern und weitergeben nicht. Details: [LICENSE](LICENSE). Fremde Bestandteile: [THIRD_PARTY.md](THIRD_PARTY.md).

**Logo und Name:** Das SH-Tunebridge-Logo (`assets/logo/`) und der Name „SH-Tunebridge“ gehören Bigsmoke002 –
alle Rechte vorbehalten. Sie sind nicht von der Nutzungserlaubnis umfasst. Ohne vorherige schriftliche
Erlaubnis dürfen sie weder verwendet, verändert, nachgeahmt noch als eigene ausgegeben, angemeldet oder
beansprucht werden – auch nicht für Forks, andere Projekte, Shops oder Profile. Erlaubt bleibt nur, sie
unverändert zu zeigen, um auf dieses Projekt hinzuweisen.
