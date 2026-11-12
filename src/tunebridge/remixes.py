"""Remixe, Covers und andere Versionen eines Songs finden.

Zu einem Song (Titel + Künstler) sucht Deezer (ohne Key) nach Aufnahmen mit demselben Kerntitel und ordnet sie ein:
Original, Remix (mit Remixer), Edit/Mix-Version, Live, Akustik, Instrumental, Slowed/Sped Up, Cover (anderer Künstler).
Karaoke-, Tribute- und „made famous by“-Uploads werden aussortiert – das sind fast immer Füllware.

Gesendet wird nur, was gesucht wird: Titel und Künstler des Songs (wie bei „Ähnliche Songs“). Ergebnisse 7 Tage im
lokalen Zwischenspeicher; leere Ergebnisse nicht (sonst bliebe eine kurze Störung hängen).
"""
from __future__ import annotations

import re
import unicodedata

from . import store
from .models import Track
from .versions import _label as _speed_label
from .versions import main_artist, split_version

TTL = 7 * 86400
MAX_PER_KIND = 25
MAX_TOTAL = 80

# Reihenfolge und Anzeige
KINDS = [("original", "Original"), ("remix", "Remixe"), ("edit", "Edits & Mix-Versionen"), ("live", "Live"),
         ("akustik", "Akustik"), ("instrumental", "Instrumental"), ("tempo", "Slowed & Sped Up"),
         ("andere", "Andere Künstler – gleicher Titel")]
# „andere“: Covers, Remixe und Versionen, die unter einem anderen Künstler erscheinen. Bei Allerwelts-Titeln kann
# darunter auch ein ganz anderer Song mit gleichem Namen sein – das sagt die Oberfläche dazu.

_BRACKET = re.compile(r"\s*[\(\[]([^\)\]]*)[\)\]]")
_DASH = re.compile(r"\s+[-–—|]\s+(.+)$")
_REMIX = re.compile(r"\b(re-?mix|rmx|bootleg|flip|rework|re-?edit|vip|refix|mash-?up)\b", re.I)
_LIVE = re.compile(r"\blive\b|\bunplugged\b(?=.*\blive\b)|\bin concert\b|\bmtv unplugged\b", re.I)
_ACOUSTIC = re.compile(r"\bacoustic|\bunplugged\b|\bakustik|\bpiano version\b|\bstripped\b|\borchestral\b", re.I)
_INSTR = re.compile(r"\binstrumental\b|\bkaraoke version\b", re.I)
_EDIT = re.compile(r"\b(radio edit|extended|club mix|dub mix|dub|edit|mix|version|radio)\b", re.I)
_ORIGINAL = re.compile(r"\b(original mix|original version|remaster(ed)?(\s+\d{4})?|\d{4}\s+remaster(ed)?|album version|single version|mono|stereo)\b", re.I)
_JUNK = re.compile(r"karaoke|tribute|made famous|in the style of|originally performed|as made popular|cover version of|"
                   r"backing track|cover band|lullaby|rockabye baby|8-?bit|ringtone|workout|tabata|fitness|\bbpm\b", re.I)
# Stil statt Name: „Hardstyle Remix“ ist ein Hardstyle-Remix, nicht „Remix von Hardstyle“
_STYLE = re.compile(r"^(?:(?:deep|tech|future|progressive|tropical|bass|melodic)\s+)?(?:house|techno|hardstyle|hardtekk|tekk|"
                    r"trance|psy|phonk|trap|drill|dubstep|dnb|drum (?:and|&|n) bass|edm|dance|club|disco|lo-?fi|jersey|"
                    r"amapiano|reggaeton|afro|garage|hyperpop|slap|bootleg|workout|extended|radio|official|original|the|"
                    r"festival|mashup|vip|remix|techno)$", re.I)
_FEAT = re.compile(r"\s*[\(\[]?\s*(feat\.?|ft\.?|featuring|with)\s+[^\)\]]*[\)\]]?", re.I)


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    s = s.replace("&", " and ")
    return re.sub(r"[^a-z0-9]+", "", s)


# Klammer-/Strich-Teile, die eine Version beschreiben (alles andere gehört zum Titel, z. B. „Blue (Da Ba Dee)“)
_VERSIONISH = re.compile(
    r"re-?mix|rmx|bootleg|flip|rework|edit|vip|refix|mash-?up|\bmix\b|version|\bver\.?|live|acoustic|akustik|unplugged|"
    r"stripped|piano|orchestral|instrumental|remaster|radio|extended|club|\bdub\b|original|mono|stereo|single|album|"
    r"slowed|sped|speed|nightcore|reverb|8d|bass boosted|cover|demo|session|\d{4}", re.I)


def _version_parts(title: str) -> tuple[str, list[str]]:
    """-> (Titel ohne Versions-Angaben, Liste der Versions-Angaben)."""
    parts: list[str] = []

    def drop(m: re.Match) -> str:
        if _VERSIONISH.search(m.group(1)):
            parts.append(m.group(1).strip())
            return ""
        return m.group(0)
    t = _BRACKET.sub(drop, title or "")
    if (m := _DASH.search(t)) and _VERSIONISH.search(m.group(1)):
        parts.append(m.group(1).strip())
        t = t[:m.start()]
    return t.strip(), parts


def core_title(title: str) -> str:
    """„Song (XYZ Remix) - Radio Edit“ -> „Song“; „Blue (Da Ba Dee)“ bleibt."""
    t, _, _ = split_version(title or "", [])
    t = _FEAT.sub("", t)
    t, _ = _version_parts(t)
    return t.strip() or (title or "").strip()


def _version_text(title: str, version: str = "") -> str:
    """Alles, was die Version beschreibt: Versions-Klammern, Teil nach „ - “ und Deezers title_version."""
    _, parts = _version_parts(_FEAT.sub("", title or ""))
    if version and _VERSIONISH.search(version):
        parts.append(version.strip("()[] "))
    return " · ".join(dict.fromkeys(p for p in parts if p))


def _remixer(vtext: str) -> tuple[str | None, str | None]:
    """„XYZ Remix“ -> („XYZ“, None); „Hardstyle Remix“ -> (None, „Hardstyle“); „Tiesto's Deep House Remix“ -> („Tiesto“, None)."""
    for part in re.split(r"\s*·\s*", vtext):
        m = re.match(r"^(.*?)\s*(?:re-?mix|rmx|bootleg|flip|rework|re-?edit|vip mix|vip|refix)\b", part, re.I)
        if not m or not m.group(1).strip():
            continue
        name = re.sub(r"\s+(extended|radio|club|edit|official)$", "", m.group(1).strip(" -–"), flags=re.I).strip()
        if "'s " in name or name.endswith("'s"):
            name = name.split("'s")[0].strip()
        if not name:
            continue
        if _STYLE.match(name):
            return None, name.title() if name.islower() or name.isupper() else name
        return name, None
    return None, None


def classify(title: str, version: str, artist: str, seed_artist: str) -> tuple[str, str]:
    """-> (Art, Beschriftung). Art aus KINDS."""
    vtext = _version_text(title, version)
    same = _same_artist(artist, seed_artist) or bool(
        seed_artist and _norm(seed_artist) in _norm(title) and not re.search(r"cover|reprise|tribute|style", title, re.I))
    if sp := (_speed_label(vtext) if vtext else None):
        return "tempo", sp
    if _REMIX.search(vtext):
        rx, style = _remixer(vtext)
        label = f"Remix von {rx}" if rx else f"{style}-Remix" if style else "Remix"
        if not same and not rx:
            label += f" · {artist}"
        return ("remix" if same else "andere"), label
    if _LIVE.search(vtext):
        return ("live", vtext) if same else ("andere", f"Live von {artist}")
    if _ACOUSTIC.search(vtext):
        return ("akustik", vtext) if same else ("andere", f"Akustik-Version von {artist}")
    if _INSTR.search(vtext):
        return ("instrumental", vtext) if same else ("andere", f"Instrumental von {artist}")
    if vtext and _EDIT.search(vtext) and not _ORIGINAL.search(vtext):
        return ("edit", vtext) if same else ("andere", f"{vtext} · {artist}")
    if same:
        return "original", vtext or "Original"
    return "andere", f"Cover oder gleichnamiger Song von {artist}"


def _same_artist(a: str, seed: str) -> bool:
    na, ns = _norm(a), _norm(seed)
    return bool(na and ns and (na == ns or ns in na or na in ns))


def _query(q: str, limit: int) -> list[dict]:
    from .enrich import _dz
    return _dz("https://api.deezer.com/search", params={"q": q, "limit": limit}).get("data") or []


def find(track: Track, limit: int = MAX_TOTAL) -> list[dict]:
    """Versionen zu [track], gruppiert sortiert (Original, Remixe, … Covers). Wirft ratelimit.LimitReached."""
    title, artists, _ = split_version(track.title, list(track.artists))
    core = core_title(title)
    seed_artist = main_artist(artists[0]) if artists else ""
    if not core:
        return []
    ck = f"{_norm(seed_artist)}|{_norm(core)}"
    if (hit := store.cache_get("versions", ck, max_age=TTL)) is not None and hit:
        return hit[:limit]
    want = _norm(core)
    queries = [(f'track:"{core}"', 100)]
    if seed_artist:
        queries = [(f'artist:"{seed_artist}" track:"{core}"', 50), (f"{seed_artist} {core} remix", 50)] + queries
    queries.append((f"{core} remix", 50))
    seen: dict[tuple[str, str], dict] = {}
    for q, n in queries:
        for h in _query(q, n):
            t, art = h.get("title") or "", (h.get("artist") or {}).get("name") or ""
            if not t or not art or _JUNK.search(f"{t} {art} {(h.get('album') or {}).get('title') or ''}"):
                continue
            if _norm(core_title(h.get("title_short") or t)) != want:
                continue
            kind, label = classify(t, h.get("title_version") or "", art, seed_artist)
            k = (_norm(art), _norm(t))
            if k in seen and (seen[k]["rank"] or 0) >= (h.get("rank") or 0):
                continue
            alb = h.get("album") or {}
            seen[k] = {
                "title": t, "artists": [art], "album": alb.get("title"), "duration_ms": (h.get("duration") or 0) * 1000 or None,
                "cover": alb.get("cover_medium") or alb.get("cover_big"), "preview_url": h.get("preview") or None,
                "ids": {"deezer": str(h["id"])}, "link": h.get("link"), "kind": kind, "label": label,
                "rank": h.get("rank") or 0,
            }
    by_kind: dict[str, list[dict]] = {}
    for v in seen.values():
        by_kind.setdefault(v["kind"], []).append(v)
    # Gleicher Titel ≠ Cover: bei kurzen Allerwelts-Titeln („Blue“) kämen sonst fremde Songs. Nicht-Remixe anderer
    # Künstler nur, wenn die Länge ungefähr zum Original passt (±35 %) – ohne bekanntes Original nur bei längeren Titeln.
    ref = track.duration_ms or next((v["duration_ms"] for v in sorted(by_kind.get("original", []), key=lambda v: -v["rank"])
                                     if v["duration_ms"]), None)

    def plausible(v: dict) -> bool:
        if v["label"].startswith("Remix") or "-Remix" in v["label"]:
            return True
        if ref:
            return bool(v["duration_ms"]) and abs(v["duration_ms"] - ref) <= ref * 0.35
        return len(want) >= 8
    by_kind["andere"] = [v for v in by_kind.get("andere", []) if plausible(v)]
    out: list[dict] = []
    for kind, _ in KINDS:
        items = sorted(by_kind.get(kind, []), key=lambda v: -v["rank"])[:MAX_PER_KIND]
        out.extend(items)
    out = out[:MAX_TOTAL]
    if out:
        store.cache_set("versions", ck, out)
    return out[:limit]


def to_track(v: dict) -> Track:
    return Track(title=v["title"], artists=list(v.get("artists") or []), album=v.get("album"), duration_ms=v.get("duration_ms"),
                 cover=v.get("cover"), preview_url=v.get("preview_url"), ids=dict(v.get("ids") or {}))
