# Fremde Bestandteile

SH-Tunebridge selbst steht unter eigenen Bedingungen (siehe LICENSE). Die folgenden Bestandteile Dritter
behalten ihre eigenen Lizenzen; diese gehen für den jeweiligen Bestandteil vor.

## Mitgelieferte bzw. installierte Bibliotheken

| Bestandteil | Lizenz |
|---|---|
| PySide6 / Shiboken6 / Qt (inkl. Qt WebEngine) | LGPL-3.0 – wird unverändert und austauschbar (dynamisch) genutzt; Quellcode: https://code.qt.io |
| pywebview | BSD-3-Clause |
| QtPy | MIT |
| FastAPI, Pydantic | MIT |
| Starlette, Uvicorn, httpx | BSD-3-Clause |
| NumPy | BSD-3-Clause (und weitere freie Lizenzen) |
| RapidFuzz, Rich, Typer | MIT |
| shazamio, shazamio-core | MIT |
| tidalapi | LGPL-3.0-or-later – unverändert, als eigenständiges Paket genutzt |
| miniaudio (pyminiaudio, inkl. dr_mp3) | MIT – dekodiert Hörproben für Tempo/Tonart |
| Inter (Schrift) | SIL Open Font License 1.1 – siehe `src/tunebridge/web/static/fonts/OFL.txt` |

Die vollständigen Lizenztexte liegen den installierten Paketen bei (`…/site-packages/<paket>-*.dist-info/`).

## Daten

| Daten | Quelle | Lizenz |
|---|---|---|
| Genre-Katalog (`src/tunebridge/genres/catalog.json`, ~6 400 Genres mit Synonymen und Eltern-Genres) | [Wikidata](https://www.wikidata.org) inkl. der [MusicBrainz](https://musicbrainz.org/genres)-Genres, erzeugt mit `scripts/build-genres.py` | CC0 1.0 (gemeinfrei) |
| Tags/Genres einzelner Songs, Alben und Künstler (zur Laufzeit abgefragt, 30 Tage zwischengespeichert) | [MusicBrainz](https://musicbrainz.org) Web-Service | Kerndaten CC0 1.0 |

## Zusätzlich im AppImage

| Bestandteil | Lizenz |
|---|---|
| Python 3.14 (python-build-standalone) | PSF-2.0 |
| PulseAudio-Werkzeuge `pacat`/`pactl` mit libpulse, libsndfile u. a. (Ersatz, falls auf dem System nicht vorhanden) | LGPL-2.1+ bzw. jeweilige Lizenz |
| `ssh-keygen` aus OpenSSH (prüft die Update-Signatur, falls auf dem System nicht vorhanden) | BSD-Lizenz |
| libxcb-cursor/-icccm/-image/-keysyms/-render-util/-util/-xkb, libxkbcommon-x11 | MIT/X11 |

Die Lizenztexte liegen im AppImage unter `usr/share/licenses/` (aus den Ubuntu-22.04-Paketen) –
ansehen mit `./SH-Tunebridge-*.AppImage --appimage-extract usr/share/licenses`.

## Erst auf Wunsch heruntergeladen (nicht Teil von SH-Tunebridge)

| Bestandteil | Lizenz / Bedingungen |
|---|---|
| llama.cpp (Laufzeit für das lokale LLM) | MIT – https://github.com/ggml-org/llama.cpp |
| Gemma 3 (Modelle) | Gemma-Nutzungsbedingungen von Google – https://ai.google.dev/gemma/terms – werden vor dem Download in der App bestätigt |
