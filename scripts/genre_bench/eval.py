"""Genre-Prüfstand: echte Online-Daten (Last.fm, Deezer, Apple-Genre wie bei Shazam), ohne Audio, ohne KI.
Nur Metadaten-Abfragen über offizielle Schnittstellen. Braucht LASTFM_API_KEY. Dauer: ~10 min pro Liste.
Aufruf: TUNEBRIDGE_DATA=$(mktemp -d) SONGSET=songs|songs2 uv run python scripts/genre_bench/eval.py ergebnis.json"""
import json, sys, time, httpx
from tunebridge import enrich
from tunebridge.recognize.engines import Recognition

import sys as _s; _s.path.insert(0, __import__('os').path.dirname(__file__))
import os
SONGS = __import__(os.environ.get('SONGSET','songs')).SONGS

def apple_genre(artist, title):
    try:
        r = httpx.get("https://itunes.apple.com/search", params={"term": f"{artist} {title}", "entity": "song", "limit": 1}, timeout=15)
        res = r.json().get("results") or []
        return [res[0]["primaryGenreName"]] if res else []
    except Exception:
        return []

llm_calls = []
enrich.llm_genre = lambda t: (llm_calls.append(f"{t.artist} – {t.title}: genre"), None)[1]
enrich.llm_subgenre = lambda t, g, provider=None: None
ok = 0; rows = []
for artist, title, allowed, sub in SONGS:
    g = apple_genre(artist, title); time.sleep(3.2)   # Apple-Suche ~20/min
    rec = Recognition(engine="shazam", title=title, artists=[artist], genres=g)
    tr, ex = enrich._enrich_online(rec)
    good = tr.genre in allowed and (sub is None or tr.subgenre == sub)
    ok += good
    top = ", ".join(f"{k}:{v:g}" for k, v in list(tr.tags.items())[:6])
    rows.append({"allowed": sorted(map(str, allowed)), "song": f"{artist} – {title}", "ok": good, "genre": tr.genre, "sub": tr.subgenre, "apple": g, "tags": top})
    print(("✓" if good else "✗"), f"{artist} – {title}  ->  {tr.genre} / {tr.subgenre}   [apple {g}]  {top}", flush=True)
print(f"\n{ok}/{len(SONGS)} richtig", "| KI wäre gefragt worden bei:", llm_calls)
json.dump(rows, open(sys.argv[1] if len(sys.argv) > 1 else "result.json", "w"), ensure_ascii=False, indent=1)
