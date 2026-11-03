"""Erkannten Song anreichern: Vorschau (Deezer), Tags (Last.fm), Genre/Subgenre,
optional Subgenre-Hilfe durch ein lokales LLM."""

from __future__ import annotations

import json
import re

import httpx

from . import config
from . import debuglog as dbg
from .ratelimit import LimitReached, httpx_hooks
from .genres import classify
from .genres.taxonomy import TAXONOMY
from .models import Track
from .matching import normalize
from .recognize.engines import Recognition

_http = httpx.Client(timeout=15, headers={"User-Agent": "tunebridge/0.1"},
                     event_hooks=httpx_hooks("deezer", max_wait=3))


def _dz(url: str, **kw) -> dict:
    """Deezer-Aufruf; Fehlercode 4 = „Quota limit exceeded“ -> Pause + LimitReached."""
    from . import ratelimit
    d = _http.get(url, **kw).json()
    if isinstance(d, dict) and (d.get("error") or {}).get("code") == 4:
        p = ratelimit.blocked("deezer", None, "Quota limit exceeded")
        raise LimitReached("deezer", p, f"Deezer-Limit erreicht – Pause {round(p)} s")
    return d


def deezer(rec: Recognition) -> dict:
    """Deezer: kostenlos, ohne Key; liefert 30-s-Vorschau, BPM, Cover.
    Reihenfolge: ISRC -> erweiterte Suche -> freie Suche (+ Abgleich, damit kein falscher Song kommt)."""
    from .matching import best_match

    from .versions import main_artist, split_version

    title, artists, _ = split_version(rec.title, rec.artists)
    try:
        if rec.isrc:
            d = _dz(f"https://api.deezer.com/track/isrc:{rec.isrc}")
            if "error" not in d:
                return d
        artist = main_artist(artists[0]) if artists else ""
        for q in (f'artist:"{artist}" track:"{title}"', f"{artist} {title}"):
            hits = _dz("https://api.deezer.com/search", params={"q": q, "limit": 8}).get("data") or []
            cands = [Track(title=h["title"], artists=[h["artist"]["name"]], duration_ms=h.get("duration", 0) * 1000,
                           ids={"deezer": str(h["id"])}) for h in hits]
            # Dauer nicht vergleichen, wenn es eine Slowed-Version ist (die ist länger als das Original)
            src = Track(title=title, artists=[artist], duration_ms=None if title != rec.title else rec.duration_ms)
            if (m := best_match(src, cands, threshold=75)):
                return _dz(f"https://api.deezer.com/track/{m.candidate.ids['deezer']}")
        dbg.problem("deezer", "Song bei Deezer nicht gefunden (keine Hörprobe/BPM)", suche=f"{artist} – {title}", isrc=rec.isrc)
    except LimitReached as e:
        dbg.problem("deezer", f"Übersprungen: {e}")
    except (httpx.HTTPError, ValueError, KeyError) as e:
        dbg.error("deezer", "Deezer-Abfrage fehlgeschlagen", e)
    return {}


def subgenre_prompt(track: Track, genre: str, subs: list[str]) -> str:
    options = "\n".join(f"- {s}: {', '.join(TAXONOMY[genre][s][:4])}" for s in subs)
    return (
        "You are an expert music curator for electronic and popular music.\n"
        f"Song: {track.artist} - {track.title}\nMain genre: {genre}\n"
        f"Community tags: {', '.join(list(track.tags)[:15]) or '-'}\n\n"
        "Use what you know about this artist and this specific track (sound, label, era) "
        "to pick the ONE subgenre it belongs to. Options (with typical tags):\n"
        f"{options}\n\n"
        'If you do not know the artist, answer null. Reply only with JSON: {"subgenre": "<exact option name or null>"}')


def _pick_option(answer, genre: str, subs: list[str]) -> str | None:
    """Antwort tolerant zuordnen: exakter Name, Groß/Klein, Teil vor „:“ oder ein typischer Tag."""
    if not isinstance(answer, str) or not answer.strip():
        return None
    a = answer.split(":")[0].strip().lower()
    for s in subs:
        if a == s.lower() or a in [x.strip().lower() for x in s.split("/")]:
            return s
    for s in subs:
        if a in TAXONOMY[genre][s]:
            return s
    return None


def _ai(prompt: str, provider: str | None = None) -> str | None:
    """Gewählter KI-Anbieter (ai.py). provider gesetzt = genau diesen fragen (Test-Knopf)."""
    from . import ai
    if provider:
        return ai.ask(prompt, 200, provider=provider)
    return ai.ask_auto(prompt)


def llm_subgenre(track: Track, genre: str, provider: str | None = None) -> str | None:
    """Fragt den gewählten KI-Anbieter (Einstellungen › KI) nach dem Subgenre."""

    subs = [s for s in TAXONOMY.get(genre, {}) if s != "_"]
    if not subs:
        return None
    prompt = subgenre_prompt(track, genre, subs)
    try:
        text = _ai(prompt, provider)
        if not text:
            return None
        text = re.sub(r"<think>.*?</think>", "", text, flags=re.S)
        sub = json.loads(text[text.find("{"): text.rfind("}") + 1]).get("subgenre")
        picked = _pick_option(sub, genre, subs)
        dbg.event("llm", "Subgenre-Antwort", antwort=text.strip()[:200], gewählt=picked)
        return picked
    except Exception as e:
        dbg.error("llm", "Subgenre-Anfrage fehlgeschlagen", e)
        return None


def llm_genre(track: Track) -> str | None:
    """Letzter Versuch, wenn keine Quelle ein Genre kennt: das lokale LLM aus der festen Liste wählen lassen."""
    from . import ai

    if not ai.ready()[0]:
        return None
    mains = list(TAXONOMY)
    prompt = (
        "You are an expert music curator.\n"
        f"Song: {track.artist} - {track.title}\n"
        f"Community tags: {', '.join(list(track.tags)[:15]) or '-'}\n\n"
        f"Pick the ONE main genre this song belongs to from: {', '.join(mains)}.\n"
        'If you do not know the artist, answer null. Reply only with JSON: {"genre": "<exact option or null>"}')
    try:
        text = _ai(prompt)
        text = re.sub(r"<think>.*?</think>", "", text or "", flags=re.S)
        g = json.loads(text[text.find("{"): text.rfind("}") + 1]).get("genre")
        dbg.event("llm", "Genre-Antwort", antwort=text.strip()[:200])
        if isinstance(g, str):
            return next((m for m in mains if m.lower() == g.strip().lower()), None)
    except Exception as e:
        dbg.error("llm", "Genre-Anfrage fehlgeschlagen", e)
    return None


_JUNK = re.compile(r"(^|[\s_-])(test|testing|tag\d*|batch|integration|debug|asdf|foo|bar)([\s_-]|$)", re.I)


def mb_tags(track: Track) -> dict[str, float]:
    from .genres.sources import musicbrainz
    return musicbrainz.tags(track)


def junk_tags(tags: dict) -> list[str]:
    """Tags, die nach Test-/Spam-Einträgen aussehen. Ab zwei solchen gilt der ganze Eintrag als unzuverlässig."""
    bad = [t for t in tags if _JUNK.search(t)]
    return bad if len(bad) >= 2 else []


def deezer_artist_genres(dz: dict) -> list[str]:
    """Genres des Künstlers bei Deezer – der Künstler kommt aus dem schon geprüften Song (Künstler + Titel
    passen), also kein Namensvetter. Gezählt über seine Veröffentlichungen, häufigstes zuerst (7 Tage gecacht)."""
    from collections import Counter
    from . import store
    aid = (dz.get("artist") or {}).get("id")
    if not aid:
        return []
    if (hit := store.cache_get("dz_artist_genres", str(aid), max_age=7 * 86400)) is not None:
        return hit
    try:
        names = store.cache_get("dz_genre_names", "all", max_age=30 * 86400)
        if not names:
            names = {str(g["id"]): g["name"] for g in _dz("https://api.deezer.com/genre").get("data", []) if g.get("id")}
            store.cache_set("dz_genre_names", "all", names)
        albums = _dz(f"https://api.deezer.com/artist/{aid}/albums", params={"limit": 30}).get("data") or []
    except (httpx.HTTPError, ValueError, KeyError, LimitReached):
        return []
    cnt = Counter(names.get(str(a.get("genre_id"))) for a in albums if a.get("genre_id", -1) > 0)
    out = [g for g, n in cnt.most_common() if g and (n >= 2 or n == len(albums))][:3]
    store.cache_set("dz_artist_genres", str(aid), out)
    return out


def deezer_genres(dz: dict) -> list[str]:
    """Genre(s) des Albums bei Deezer – 1 Aufruf, nur wenn sonst nichts bekannt ist."""
    alb = (dz.get("album") or {}).get("id")
    if not alb:
        return []
    try:
        d = _dz(f"https://api.deezer.com/album/{alb}")
        return [g["name"] for g in (d.get("genres") or {}).get("data", []) if g.get("name")]
    except (httpx.HTTPError, ValueError, KeyError, LimitReached):
        return []


_ELECTRONIC = {"dance", "electronic", "electronica", "edm", "drum & bass", "dubstep", "electro"}


def bpm_guess(bpm: float | None, coarse: list[str]) -> str | None:
    """Notlösung ohne brauchbare Tags: grobes Genre aus dem Tempo (nur bei elektronischer Musik)."""
    if not bpm or not any(g.lower() in _ELECTRONIC for g in coarse):
        return None
    if 165 <= bpm <= 180:
        return "Drum & Bass"
    if 138 <= bpm <= 152:
        return "Dubstep"  # oder 140er UK Bass / Trap – deshalb geringe Sicherheit
    if 150 < bpm <= 160:
        return "Hardstyle / Hardcore"
    return None


def enrich(rec: Recognition, fresh: bool = False) -> tuple[Track, dict]:
    """-> (Track mit Genre, Zusatzinfos für die Anzeige). Bekannte Songs kommen aus dem Speicher."""
    from . import aidetect, consent, songcache
    use_cache = consent.local("cache")
    if use_cache and not fresh and (hit := songcache.lookup(rec)):
        hit[1]["ai"] = aidetect.check(*hit)
        return hit
    track, extra = _enrich_online(rec)
    extra["ai"] = aidetect.check(track, extra)
    if not use_cache:
        return track, extra
    try:
        songcache.save(rec, track, extra)
    except Exception as e:
        dbg.error("speicher", "Song konnte nicht gespeichert werden", e)
    return track, extra


def _enrich_online(rec: Recognition) -> tuple[Track, dict]:
    from .versions import speed_label, split_version

    _, _, version = split_version(rec.title, rec.artists)
    if not version and rec.speed and abs(rec.speed - 1) > 0.03:
        version = speed_label(rec.speed)
    dz = deezer(rec)
    track = Track(title=rec.title, artists=rec.artists, album=rec.album,
                  isrc=rec.isrc or dz.get("isrc"),
                  duration_ms=rec.duration_ms or (dz.get("duration") or 0) * 1000 or None)
    if dz.get("id"):
        track.ids["deezer"] = str(dz["id"])

    steps: list[str] = []
    tags: dict[str, float] = {}
    lf = None
    track_tags = 0
    if config.opt("LASTFM_API_KEY"):
        from .genres.sources.lastfm import LastFM, lookup_track
        lf = LastFM()
        try:
            # nur Song-Tags; Künstler-Tags kommen weiter unten (halbes Gewicht) und zählen NICHT als Song-Tags –
            # sonst überstimmt ein Namensvetter alles andere (Poni – Nothing Left To Love: Dubstep, nicht Pop)
            tags = lf.song_tags(track)
            if junk_tags(tags):
                # Last.fm-Einträge sind manchmal mit Test-/Spam-Tags verseucht (gesehen: „test-tag“, „batch-test“
                # bei Taylor Swift – Anti-Hero, dazu „grunge“) -> den Song-Tags dann gar nicht trauen
                steps.append(f"Last.fm-Song-Tags verworfen (Test-/Spam-Tags: {', '.join(junk_tags(tags))})")
                dbg.problem("genre", "Verseuchte Last.fm-Tags verworfen", song=f"{track.artist} – {track.title}",
                            tags=list(tags)[:10])
                tags = {}
            track_tags = len(tags) if len(tags) >= 2 else 0
            lt = lookup_track(track)
            steps.append(f"Last.fm-Tags für „{lt.artist} – {lt.title}“: {len(tags)}")
        except LimitReached as e:
            steps.append(f"Last.fm übersprungen: {e}")
            dbg.problem("genre", f"Last.fm übersprungen: {e}")
        except httpx.HTTPError as e:
            steps.append(f"Last.fm-Fehler: {e}")
            dbg.error("genre", "Last.fm nicht erreichbar", e)
    else:
        steps.append("kein Last.fm-Key – nur grobe Genres der Erkennungsdienste")
    # grobe Genres von Shazam/ACRCloud: gehören zum Song selbst. Normal geringes Gewicht – fehlen die Song-Tags,
    # zählen sie mehr als die (halbierten) Künstler-Tags (Taylor Swift: Song „Pop“, Künstlerin „country“)
    service = list(rec.genres)
    if not service and not track_tags and rec.title and rec.artists and rec.artists[0]:
        # Song per Link/Playlist (kein Shazam-Genre) und Last.fm kennt ihn nicht -> Apples Genre nachschlagen
        # (freie iTunes-Suche, gecacht; dieselbe Einordnung, die Shazam sonst mitliefert)
        from .links import itunes_song
        if (g := (itunes_song(Track(title=rec.title, artists=rec.artists)) or {}).get("genre")):
            service = [g]
            steps.append(f"Apple-Genre: {g}")
    hint = service[0] if service else None
    weight, dzg = 30.0, None
    if service and not track_tags:
        # Last.fm kennt den Song nicht -> gegen das Dienst-Genre stehen nur Künstler-Tags (Namensvettern möglich).
        # Gegenprobe mit Deezers Album-Genre: sagen beide Dienste dieselbe Richtung, zählt das Dienst-Genre voll
        # (Poni: Apple „Dubstep“ + Deezer „Electro“; Taylor Swift: „Pop“ + „Pop“). Widersprechen sie sich, ist das
        # Dienst-Genre eher ein grobes Etikett (Kordhell: Apple „Pop“, Deezer „Electro“) -> schwach, kein Familienhinweis.
        from .genres.classify import services_agree
        dzg = deezer_genres(dz)
        votes = [services_agree(service[0], g) for g in dzg]
        if not dzg or any(votes) or all(v is None for v in votes):
            weight = 60.0
            steps.append(f"Dienst-Genre {service[0]} bestätigt (Deezer: {dzg or '–'})")
        else:
            hint = None
            steps.append(f"Dienst-Genre {service[0]} widerspricht Deezer {dzg} -> nur schwach gewertet")
    for g in service:
        tags.setdefault(g.lower(), weight)
    c = classify(tags, hint)
    steps.append(f"Tags -> {c.genre}/{c.subgenre}/{c.niche} ({c.confidence})")
    source = "tags"
    # Song-Tags passen auf kein Genre (z. B. nur „germany“, „instrumental“), fehlen ganz oder sind uneindeutig
    # -> Künstler-Tags dazunehmen (halbes Gewicht)
    weak = not c.genre or c.confidence <= 0.2 or track_tags == 0 or c.confidence < 0.5 \
        or c.genre not in TAXONOMY or (c.scores.get(c.genre, 0) < 15)
    if lf and weak:
        try:
            # Namensvettern: unter „Kanine“ führt Last.fm einen DnB-Produzenten UND eine Deathcore-Band.
            # Gibt es ein Song-Genre der Dienste (Shazam/Apple, ggf. von Deezer bestätigt), zählen nur
            # Künstler-Tags aus derselben Familie (Kanine – Deeper: Apple/Deezer „Dance“ -> kein Metal).
            # Zusätzlich: Genres des über den Song geprüften Künstlers bei Deezer (Künstler + Titel stimmen).
            from .genres.classify import _family, service_main

            def fam_of(g: str | None) -> set[str]:
                return set(_family(g) or ()) or ({m} if (m := service_main(g)) else set())
            fam: set[str] = fam_of(hint) if hint else set()
            art_g = deezer_artist_genres(dz)
            for g in art_g[:2]:
                fam |= fam_of(g)
            if art_g:
                steps.append(f"Künstler geprüft (Deezer, über Künstler + Titel): {', '.join(art_g)}")
            dropped = []
            for k, v in lf.artist_tags(track.artist).items():
                if fam and (g := classify({k: 1.0}).genre) and g not in fam:
                    dropped.append(k)
                    continue
                tags.setdefault(k, v * 0.5)
            if dropped:
                steps.append(f"Künstler-Tags verworfen (Namensvetter? passen nicht zu {', '.join(dict.fromkeys(x for x in [hint, *art_g[:2]] if x))}): "
                             f"{', '.join(dropped[:8])}")
            c = classify(tags, hint)
            steps.append(f"+ Künstler-Tags -> {c.genre}/{c.subgenre} ({c.confidence})")
        except (httpx.HTTPError, LimitReached) as e:
            steps.append(f"Künstler-Tags: {e}")
    # Mikro-Genre fehlt oder ist unsicher -> MusicBrainz (offen, CC0) dazunehmen. Im Test mit 177 Songs aus
    # 60 Mikro-Genres brachte das die meisten Treffer (scripts/genre_bench/micro_*.py).
    if not c.subgenre or c.confidence < 0.6 or not track_tags:
        try:
            mb = mb_tags(track)
            if mb:
                for k, v in mb.items():
                    tags[k] = tags.get(k, 0) + v
                c = classify(tags, hint)
                steps.append(f"+ MusicBrainz ({len(mb)} Tags) -> {c.genre}/{c.subgenre} ({c.confidence})")

        except (httpx.HTTPError, LimitReached, ValueError) as e:
            steps.append(f"MusicBrainz: {e}")
    if not c.genre or c.confidence <= 0.2:
        dzg = dzg if dzg is not None else deezer_genres(dz)
        for g in dzg:
            tags.setdefault(g.lower(), 25.0)
        c = classify(tags, hint)
        steps.append(f"+ Deezer-Genres {dzg or '(keine)'} -> {c.genre} ({c.confidence})")
    track.tags = tags
    track.genre, track.subgenre, track.niche = c.genre, c.subgenre, c.niche
    if track.niche and normalize(track.niche) in {normalize(a) for a in track.artists}:
        track.niche = None          # Künstlername als Tag ist kein Genre („Daft Punk“)
    if (not track.genre or c.confidence <= 0.2) and (g := bpm_guess(dz.get("bpm"), list(rec.genres) + list(tags))):
        track.genre, track.subgenre, source = g, None, "bpm"
        c.confidence = 0.3
        steps.append(f"Tempo {dz.get('bpm')} BPM -> {g}")
    # KI nur als letzter Notnagel: kein Genre aus unserer Liste gefunden. Sie bekommt die Tags mit
    # und darf nichts überschreiben, wofür es eindeutige Tags gibt.
    # Ganz ohne Hinweise (keine Tags, Song bei Deezer unbekannt) fragen wir die KI gar nicht – sie würde raten.
    evidence = bool(tags) or bool(dz.get("id"))
    if evidence and (not track.genre or track.genre not in TAXONOMY) and (g := llm_genre(track)):
        track.genre, track.subgenre, source = g, None, "llm_genre"
        c.confidence = 0.3
        steps.append(f"LLM -> {g}")
    if track.genre and not track.subgenre and track.genre in TAXONOMY and (sub := llm_subgenre(track, track.genre)):
        track.subgenre, source = sub, ("llm" if source == "tags" else source)

    # unbekannte Tags merken -> daraus lernt die App neue Genres (nur lokal)
    try:
        from . import store
        from .genres import learn
        learn.observe(store.track_key(track), tags, track.genre, classify(tags, hint).unmatched)
    except Exception as e:
        dbg.error("genre-lernen", "Tags konnten nicht gemerkt werden", e)

    info = dict(song=f"{track.artist} – {track.title}", ergebnis=f"{track.genre}/{track.subgenre}/{track.niche}",
                quelle=source, sicherheit=c.confidence, version=version, schritte=steps,
                tags=dict(sorted(tags.items(), key=lambda kv: -kv[1])[:20]), zugeordnet=c.matched)
    if not track.genre:
        dbg.problem("genre", "GENRE UNBEKANNT", grund="kein Tag passt auf ein bekanntes Genre" if tags else
                    "keine Tags gefunden (Song/Künstler bei Last.fm unbekannt, Deezer ohne Genre)", **info)
    elif not track.subgenre:
        dbg.event("genre", "Genre ohne Subgenre", **info)
    else:
        dbg.event("genre", "Genre bestimmt", **info)

    extra = {
        "preview_url": rec.preview_url or dz.get("preview"),
        "cover": rec.cover or (dz.get("album") or {}).get("cover_xl"),
        "bpm": dz.get("bpm") or None,
        "links": {**rec.links, **({"deezer": dz["link"]} if dz.get("link") else {})},
        "confidence": c.confidence, "genre_source": source, "genre_hint": hint,
        "label": rec.label, "year": rec.year,
        "version": version, "speed": rec.speed,
    }
    track.cover, track.preview_url = extra["cover"], extra["preview_url"]
    return track, extra
