"""Kommandozeile: `uv run tunebridge --help`"""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from . import config
from .genres import classify as classify_tags
from .models import Library, Track
from .providers import PROVIDERS, get_provider
from .split import split_by_genre

app = typer.Typer(help="SH-Tunebridge – Songs erkennen, Playlists übertragen, Genres einordnen.",
                  no_args_is_help=True)
con = Console()


def _parse(query: str) -> Track:
    if " - " not in query:
        raise typer.BadParameter('Format: "Künstler - Titel"')
    artist, title = query.split(" - ", 1)
    return Track(title=title.strip(), artists=[artist.strip()])


@app.command()
def providers():
    """Zeigt die unterstützten Plattformen und ihren Status."""
    t = Table("Plattform", "Status", "Hinweis")
    for k, (name, info, ok) in PROVIDERS.items():
        t.add_row(name, "verfügbar" if ok else "geplant", info)
    con.print(t)


@app.command()
def genre(query: str = typer.Argument(..., help='"Künstler - Titel"')):
    """Ordnet einen einzelnen Song einem (Sub-)Genre zu."""
    from .genres.sources.lastfm import LastFM

    tr = _parse(query)
    tags = LastFM().tags(tr)
    c = classify_tags(tags)
    con.print(f"[bold]{tr}[/]")
    con.print(f"  Genre:    [green]{c.genre or '?'}[/]")
    con.print(f"  Subgenre: [cyan]{c.subgenre or '–'}[/]  (Sicherheit {c.confidence:.0%})")
    con.print(f"  Tags:     {', '.join(list(tags)[:12])}")


@app.command()
def similar(query: str = typer.Argument(..., help='"Künstler - Titel"'),
            limit: int = 20,
            same_sub: bool = typer.Option(False, help="Nur Songs im selben Subgenre zeigen")):
    """Findet ähnliche Songs und zeigt deren (Sub-)Genre."""
    from .genres.sources.lastfm import LastFM

    lf = LastFM()
    tr = _parse(query)
    base = classify_tags(lf.tags(tr))
    con.print(f"[bold]{tr}[/] → {base.genre or '?'} / {base.subgenre or '–'}\n")
    t = Table("Match", "Song", "Genre", "Subgenre")
    for cand, m in lf.similar(tr, limit=limit):
        c = classify_tags(lf.tags(cand))
        if same_sub and (c.subgenre != base.subgenre or not c.subgenre):
            continue
        t.add_row(f"{m:.2f}", str(cand), c.genre or "?", c.subgenre or "–")
    con.print(t)


@app.command()
def classify(library: Path):
    """Ordnet alle Songs eines Exports (JSON) ein und speichert das Ergebnis zurück."""
    from .genres.sources.lastfm import LastFM

    lib = Library.load(library)
    lf = LastFM()
    all_tracks = lib.liked + [t for p in lib.playlists for t in p.tracks]
    with con.status("Hole Tags …") as st:
        for i, tr in enumerate(all_tracks, 1):
            st.update(f"{i}/{len(all_tracks)}  {tr}")
            tr.tags = lf.tags(tr)  # gecacht in der DB
            c = classify_tags(tr.tags)
            tr.genre, tr.subgenre = c.genre, c.subgenre
    lib.save(library)
    con.print(f"[green]Fertig:[/] {len(all_tracks)} Songs eingeordnet → {library}")


@app.command()
def split(library: Path,
          playlist: str = typer.Option(..., help="Name der Playlist, die aufgeteilt wird ('liked' = Likes)"),
          detail: str = typer.Option("sub", help="'main' = grob, 'sub' = mit Subgenre"),
          out: Path = typer.Option(None, help="Zieldatei (Standard: <library>-split.json)")):
    """Teilt eine (eingeordnete) Playlist in Genre-Playlists auf – erstmal nur als Vorschau-JSON."""
    lib = Library.load(library)
    tracks = lib.liked if playlist == "liked" else next(
        (p.tracks for p in lib.playlists if p.name == playlist), None)
    if tracks is None:
        raise typer.BadParameter(f"Playlist '{playlist}' nicht im Export")
    parts = split_by_genre(tracks, detail=detail)
    t = Table("Neue Playlist", "Songs")
    for p in parts:
        t.add_row(p.name, str(len(p.tracks)))
    con.print(t)
    out = out or library.with_name(library.stem + "-split.json")
    Library(source=lib.source, playlists=parts).save(out)
    con.print(f"Vorschau gespeichert: {out}")


@app.command()
def export(platform: str, out: Path = typer.Option(None)):
    """Exportiert Playlists + Likes einer Plattform als JSON."""
    lib = get_provider(platform).export()
    out = out or config.DATA / "exports" / f"{platform}.json"
    lib.save(out)
    con.print(f"Gespeichert: {out}")


@app.command()
def transfer(library: Path, to: str, dry_run: bool = True):
    """Überträgt einen Export auf eine andere Plattform (Standard: nur Probelauf)."""
    get_provider(to)  # TODO: suchen -> best_match -> anlegen; unsichere Treffer in Report


@app.command("app")
def app_window():
    """Startet SH-Tunebridge als eigenes Desktop-Fenster."""
    from .desktop import run
    run()


@app.command(hidden=True)
def companion(port: int = 8765):
    """Tray-Symbol und Schwebe-Icon (wird von der App selbst gestartet)."""
    from .companion import main
    main(port)


@app.command()
def ui(port: int = 8765, host: str = "127.0.0.1", browser: bool = True):
    """Startet die Oberfläche (Erkennen, Reinhören, Einsortieren) im Browser."""
    import os
    import socket
    import threading
    import webbrowser

    import uvicorn

    url = f"http://{host}:{port}"
    with socket.socket() as s:
        if s.connect_ex((host, port)) == 0:  # läuft schon -> nur Browser öffnen
            con.print(f"Läuft bereits: {url}")
            if browser:
                webbrowser.open(url)
            return
    if browser:
        threading.Timer(1.2, webbrowser.open, args=(url,)).start()
    con.print(f"SH-Tunebridge läuft auf [bold]{url}[/]  (Strg+C beendet)")
    if host not in ("127.0.0.1", "localhost", "::1"):
        os.environ["TUNEBRIDGE_OPEN_HOST"] = "1"   # bewusst im Netz geöffnet -> Host-Prüfung aus (Herkunft weiter geprüft)
    uvicorn.run("tunebridge.web.app:app", host=host, port=port, log_level="warning")


@app.command()
def listen(source: str = typer.Option("desktop", help="desktop | mic | Quellenname"),
           seconds: float = 10):
    """Song im Terminal erkennen (ohne Oberfläche)."""
    import asyncio

    from .enrich import enrich
    from .recognize.capture import record
    from .recognize.engines import recognize

    with con.status(f"Höre zu ({seconds:.0f} s) …"):
        wav = record(source, seconds)
    try:
        with con.status("Erkenne …"):
            res = asyncio.run(recognize(wav))
    finally:
        wav.unlink(missing_ok=True)
    if not res.best:
        con.print("[yellow]Nichts erkannt.[/]", res.errors or "")
        raise typer.Exit(1)
    track, extra = enrich(res.best)
    con.print(f"[bold]{track}[/]  ({res.best.engine}, {res.agreement} einig)")
    con.print(f"  {track.genre or '?'} / {track.subgenre or '–'}   Hörprobe: {extra.get('preview_url') or '–'}")


@app.command()
def setup():
    """Legt ~/.config/tunebridge/config.env aus der Vorlage an (falls noch nicht vorhanden)."""
    import os
    import shutil

    from importlib.resources import files

    config.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if config.CONFIG_FILE.exists():
        con.print(f"Existiert schon: {config.CONFIG_FILE}")
    else:
        shutil.copy(files("tunebridge") / "config.env.example", config.CONFIG_FILE)
        os.chmod(config.CONFIG_FILE, 0o600)
        con.print(f"Angelegt: {config.CONFIG_FILE}  → Keys eintragen")
    con.print(f"Daten: {config.DATA}")


@app.command("backup")
def backup_cmd(keys: bool = typer.Option(False, "--keys", help="API-Keys mitsichern"),
               out: Path = typer.Option(None, help="Zielordner (Standard: TUNEBRIDGE_BACKUP_DIR)")):
    """Sichert Datenbank, Exporte und optional die Keys in eine .tbbackup-Datei."""
    from . import backup
    f = backup.create(include_keys=keys, dest_dir=out)
    con.print(f"[green]Gesichert:[/] {f}  ({f.stat().st_size / 1024:.0f} KB)")


@app.command("backups")
def backups_cmd():
    """Listet vorhandene Sicherungen."""
    from datetime import datetime

    from . import backup
    t = Table("Datei", "Datum", "Rechner", "Songs", "Playlists", "Keys")
    for b in backup.list_backups():
        t.add_row(b["name"], datetime.fromtimestamp(b["created"]).strftime("%d.%m.%Y %H:%M"), b["host"],
                  str(b["stats"]["recognitions"]), str(b["stats"]["playlists"]), "ja" if b["includes_keys"] else "–")
    con.print(t)
    con.print(f"Ordner: {backup.backup_dir()}")


@app.command("restore")
def restore_cmd(file: Path,
                merge: bool = typer.Option(False, "--merge", help="Zu vorhandenen Daten hinzufügen statt ersetzen"),
                keys: bool = typer.Option(False, "--keys", help="Gesicherte API-Keys übernehmen"),
                yes: bool = typer.Option(False, "--yes", "-y", help="Nicht nachfragen")):
    """Stellt eine Sicherung wieder her (vorher wird automatisch der aktuelle Stand gesichert)."""
    from datetime import datetime

    from . import backup
    m = backup.inspect(file)
    con.print(f"Backup vom {datetime.fromtimestamp(m['created']):%d.%m.%Y %H:%M} ({m['host']}): "
              f"{m['stats']['recognitions']} Songs, {m['stats']['playlists']} Playlists"
              + (", mit Keys" if m["includes_keys"] else ""))
    mode = "merge" if merge else "replace"
    if not yes and not typer.confirm("Zusammenführen?" if merge else "Aktuelle Daten ERSETZEN?"):
        raise typer.Exit(1)
    r = backup.restore(file, mode, restore_keys=keys)
    keys_txt = f", {r['keys_restored']} Keys übernommen" if keys else ""
    con.print(f"[green]Fertig.[/] Jetzt: {r['stats']['recognitions']} Songs, {r['stats']['playlists']} Playlists"
              f"{keys_txt}. "
              f"Vorheriger Stand gesichert als {r['safety_backup']}")


if __name__ == "__main__":
    app()
