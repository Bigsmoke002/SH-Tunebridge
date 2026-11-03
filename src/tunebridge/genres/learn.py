"""Neue Genres selbst dazulernen – aus den Last.fm-Tags der Songs, die du erkennst.

Ablauf
  1. Sammeln: Tags, die auf kein bekanntes Genre passen, werden mit den Songs gemerkt, bei
     denen sie vorkamen (nur lokal, Tabelle genre_terms).
  2. Aussortieren: Länder, Jahre, Stimmungen, „seen live“ … sind keine Genres.
  3. Entscheiden, sobald der Tag bei mindestens MIN_SONGS verschiedenen Songs vorkam:
       * Mitlauf-Genre: welches Hauptgenre hatten diese Songs? Eindeutig = ≥ 80 % dasselbe.
       * Lokales LLM (falls eingeschaltet): „Ist das ein Genre? Welche Familie?“
     Automatisch übernommen wird nur, wenn beides zusammenpasst – ohne LLM erst bei
     MIN_SONGS_NO_LLM Songs und 100 % Einigkeit. Sagt das LLM „kein Genre“, wird der Tag verworfen.
  4. Gelernte Genres zählen sofort; alte Einträge mit diesem Tag werden neu bestimmt.

Nichts davon verlässt den Rechner – außer der Nutzer schlägt ein Genre freiwillig per GitHub-Issue vor.
Es wird keine fremde Genre-Datenbank ausgelesen (§ 87b UrhG), nur Tags der eigenen Songs.
"""

from __future__ import annotations

import json
import re
import threading
import time

from ..matching import normalize

MIN_SONGS = 3            # ab so vielen verschiedenen Songs wird entschieden
MIN_SONGS_NO_LLM = 4     # ohne LLM etwas vorsichtiger
AGREEMENT = 0.8          # Anteil der Songs mit demselben Hauptgenre
MIN_WEIGHT = 5.0         # schwächere Tags zählen nicht (Last.fm: 0..100)
MAX_SONGS = 30

_lock = threading.Lock()
_busy: set[str] = set()

# ------------------------------------------------------------------ Was ist kein Genre?
_NOT_GENRE_WORDS = {
    "seen live", "favorite", "favorites", "favourite", "favourites", "love", "loved", "awesome", "beautiful", "cool",
    "good", "great", "best", "amazing", "epic shit", "my music", "spotify", "soundcloud", "youtube", "tiktok",
    "albums i own", "under 2000 listeners", "male vocalists", "female vocalists", "female vocalist", "male vocalist",
    "vocal", "vocals", "instrumental", "remix", "cover", "covers", "live", "single", "ep", "album", "mix",
    "sad", "happy", "chill", "dark", "melancholic", "melancholy", "emotional", "energetic", "mellow", "dreamy",
    "relax", "relaxing", "party", "workout", "gym", "driving", "night", "summer", "winter", "rain", "sleep",
    "slowed", "reverb", "sped up", "nightcore", "daycore", "bass boosted", "8d", "lyrics", "catchy", "banger",
    "soundtrack of my life", "check out", "beautiful voice", "guitar", "piano", "synth", "drums", "bass",
    "underground", "unknown", "obscure", "niche", "new", "old", "classic", "oldies", "heard on pandora",
    "all", "music", "song", "songs", "artist", "band", "producer", "dj", "rapper", "singer",
}
_COUNTRIES = (
    "american|usa|us|british|uk|english|german|deutsch|germany|french|france|italian|italy|spanish|spain|"
    "russian|russia|ukrainian|ukraine|polish|poland|japanese|japan|korean|korea|chinese|china|brazilian|brazil|"
    "swedish|sweden|norwegian|norway|finnish|finland|dutch|netherlands|belgian|belgium|canadian|canada|"
    "australian|australia|mexican|mexico|argentinian|argentina|turkish|turkey|kazakhstan|kazakh|austrian|austria|"
    "swiss|irish|scottish|danish|czech|hungarian|greek|portuguese|indian|african|european|asian|latin american"
)
_NOT_GENRE_RX = re.compile(
    rf"^(\d{{2,4}}s?|\d{{4}}\s*-\s*\d{{4}}|(19|20)\d\d|({_COUNTRIES})|(\d+\s*)?(of\s+)?\d+\s*stars?|"
    r"[a-z]?\d+|.*\bfavou?rites?\b.*|.*\bseen\b.*|.*\blisten(ed|ing)?\b.*|.*\bmy\b.*|.*\bi\b.*|"
    r".*\bplaylist\b.*|.*\balbum\b.*|.*\bsongs?\b.*|.*\brecords?\b$|.*\blabel\b.*)$")


def is_noise(tag: str) -> bool:
    t = normalize(tag)
    return (not t or len(t) < 3 or len(t) > 40 or t in _NOT_GENRE_WORDS or bool(_NOT_GENRE_RX.match(t))
            or len(t.split()) > 4)


def _label(tag: str) -> str:
    return " ".join(w if any(c.isupper() for c in w) else w[:1].upper() + w[1:] for w in tag.strip().split())


# ------------------------------------------------------------------ Index für classify()
def learned_index() -> dict[str, tuple[str | None, str | None, str | None]]:
    from .. import store
    try:
        with store._conn() as c:
            rows = c.execute("SELECT tag, main, sub, niche FROM genre_terms WHERE state IN ('learned','confirmed')").fetchall()
    except Exception:
        return {}
    return {r["tag"]: (r["main"], r["sub"], r["niche"]) for r in rows}


def _refresh_index() -> None:
    from .classify import set_learned   # (genres.classify ist auch der Name der Funktion)
    set_learned(learned_index())


# ------------------------------------------------------------------ Sammeln
def observe(song_key: str, tags: dict[str, float], genre: str | None, unmatched: list[str]) -> None:
    """Nach jeder Genre-Bestimmung: unbekannte Tags merken und ggf. entscheiden (im Hintergrund)."""
    from .. import store

    todo = []
    with _lock, store._conn() as c:
        for tag in unmatched:
            if tags.get(tag, 0) < MIN_WEIGHT or is_noise(tag):
                continue
            key = normalize(tag)
            r = c.execute("SELECT * FROM genre_terms WHERE tag=?", (key,)).fetchone()
            if r and r["state"] in ("learned", "confirmed", "rejected"):
                continue
            songs = json.loads(r["songs"]) if r else []
            cooc = json.loads(r["cooc"]) if r else {}
            if song_key in songs:
                continue
            songs = (songs + [song_key])[-MAX_SONGS:]
            if genre:
                cooc[genre] = cooc.get(genre, 0) + 1
            c.execute("""INSERT OR REPLACE INTO genre_terms(tag,label,state,main,sub,niche,how,songs,cooc,llm,updated)
                         VALUES(?,?,'candidate',NULL,NULL,NULL,NULL,?,?,?,?)""",
                      (key, r["label"] if r else _label(tag), json.dumps(songs), json.dumps(cooc),
                       r["llm"] if r else None, time.time()))
            if len(songs) >= MIN_SONGS and key not in _busy:
                todo.append(key)
                _busy.add(key)
    for key in todo:
        threading.Thread(target=_resolve_safe, args=(key,), daemon=True).start()


def _resolve_safe(key: str) -> None:
    try:
        resolve(key)
    except Exception as e:
        from .. import debuglog as dbg
        dbg.error("genre-lernen", f"Entscheidung für „{key}“ fehlgeschlagen", e)
    finally:
        _busy.discard(key)


# ------------------------------------------------------------------ Entscheiden
def _ask_llm(label: str, cooc: dict[str, int]) -> dict | None:
    from .. import ai
    from .taxonomy import TAXONOMY

    if not ai.ready()[0]:
        return None
    fams = list(TAXONOMY) + ["Electronic", "Blues", "Folk / Country / World", "Religious"]
    seen = ", ".join(f"{g} ({n}×)" for g, n in sorted(cooc.items(), key=lambda kv: -kv[1])) or "-"
    prompt = (
        "You are an expert music curator who knows obscure internet microgenres.\n"
        f'Listeners tagged songs with "{label}". Those songs were otherwise classified as: {seen}.\n'
        "1. Is this tag the name of a music genre or style (not a mood, place, era, label or artist)?\n"
        f"2. If yes, which ONE family does it belong to: {', '.join(fams)}?\n"
        "3. Optionally the closest known subgenre it belongs under (or null).\n"
        'Reply only with JSON: {"is_genre": true|false, "family": "<exact family or null>", "parent": "<subgenre or null>"}')
    try:
        text = ai.ask_auto(prompt)
        text = re.sub(r"<think>.*?</think>", "", text or "", flags=re.S)
        d = json.loads(text[text.find("{"): text.rfind("}") + 1])
        fam = next((f for f in fams if isinstance(d.get("family"), str) and f.lower() == d["family"].strip().lower()), None)
        return {"is_genre": bool(d.get("is_genre")), "family": fam, "parent": d.get("parent") or None}
    except Exception:
        return None


def resolve(key: str) -> str:
    """Entscheidet über einen Kandidaten -> neuer Zustand."""
    from .. import debuglog as dbg
    from .. import store
    from .taxonomy import TAXONOMY

    with store._conn() as c:
        r = c.execute("SELECT * FROM genre_terms WHERE tag=?", (key,)).fetchone()
    if not r or r["state"] != "candidate":
        return r["state"] if r else "?"
    songs, cooc = json.loads(r["songs"]), json.loads(r["cooc"])
    top, top_n = max(cooc.items(), key=lambda kv: kv[1]) if cooc else (None, 0)
    with_genre = sum(cooc.values())
    clear = bool(top) and top_n >= MIN_SONGS and top_n / max(with_genre, 1) >= AGREEMENT
    ans = _ask_llm(r["label"], cooc)

    state, main, sub, how = "candidate", None, None, None
    if ans and not ans["is_genre"]:
        state, how = "rejected", "llm-nein"
    elif ans and clear and ans["family"] == top:
        state, main, how = "learned", top, "auto"
    elif ans is None and clear and len(songs) >= MIN_SONGS_NO_LLM and top_n == with_genre:
        state, main, how = "learned", top, "auto"
    if state == "learned" and ans and ans.get("parent"):
        p = normalize(str(ans["parent"]))
        sub = next((s for s in TAXONOMY.get(main, {}) if s != "_" and
                    (normalize(s) == p or p in [normalize(a) for a in TAXONOMY[main][s]])), None)
    with store._conn() as c:
        c.execute("UPDATE genre_terms SET state=?, main=?, sub=?, niche=?, how=?, llm=?, updated=? WHERE tag=?",
                  (state, main, sub, r["label"] if state == "learned" else None, how,
                   json.dumps(ans) if ans else r["llm"], time.time(), key))
    dbg.event("genre-lernen", f"„{r['label']}“ -> {state}", songs=len(songs), mitlauf=cooc, llm=ans,
              ergebnis=f"{main}/{sub}" if main else None)
    if state == "learned":
        _refresh_index()
        reclassify(only_tag=key)
    return state


# ------------------------------------------------------------------ Nutzer-Aktionen
def set_term(key: str, action: str, main: str | None = None, sub: str | None = None) -> None:
    """action: accept | reject | reset"""
    from .. import store
    key = normalize(key)
    with store._conn() as c:
        r = c.execute("SELECT label FROM genre_terms WHERE tag=?", (key,)).fetchone()
        label = r["label"] if r else _label(key)
        if action == "accept":
            if not main:
                raise ValueError("Hauptgenre fehlt")
            c.execute("""INSERT INTO genre_terms(tag,label,state,main,sub,niche,how,songs,cooc,updated)
                         VALUES(?,?,'confirmed',?,?,?,'manuell','[]','{}',?)
                         ON CONFLICT(tag) DO UPDATE SET state='confirmed', main=excluded.main, sub=excluded.sub,
                         niche=excluded.niche, how='manuell', updated=excluded.updated""",
                      (key, label, main, sub or None, label, time.time()))
        elif action == "reject":
            c.execute("UPDATE genre_terms SET state='rejected', main=NULL, sub=NULL, niche=NULL, how='manuell', updated=? "
                      "WHERE tag=?", (time.time(), key))
        elif action == "reset":
            c.execute("UPDATE genre_terms SET state='candidate', main=NULL, sub=NULL, niche=NULL, how=NULL, updated=? "
                      "WHERE tag=?", (time.time(), key))
        else:
            raise ValueError(action)
    _refresh_index()
    reclassify(only_tag=key)


def overview() -> dict:
    from .. import store
    with store._conn() as c:
        rows = c.execute("SELECT * FROM genre_terms ORDER BY updated DESC").fetchall()
    out = {"learned": [], "candidates": [], "rejected": []}
    for r in rows:
        d = {"tag": r["tag"], "label": r["label"], "state": r["state"], "main": r["main"], "sub": r["sub"],
             "how": r["how"], "songs": len(json.loads(r["songs"] or "[]")), "cooc": json.loads(r["cooc"] or "{}"),
             "llm": json.loads(r["llm"]) if r["llm"] else None, "updated": r["updated"]}
        out["learned" if r["state"] in ("learned", "confirmed") else
            "rejected" if r["state"] == "rejected" else "candidates"].append(d)
    out["candidates"].sort(key=lambda d: -d["songs"])
    out["min_songs"] = MIN_SONGS
    return out


# ------------------------------------------------------------------ Alte Einträge neu bestimmen
def reclassify(only_tag: str | None = None) -> dict:
    """Genre aller gespeicherten Songs aus ihren gespeicherten Tags neu berechnen (ohne Netz).
    Schätzungen per BPM/LLM bleiben, wenn die Tags weiterhin nichts hergeben."""
    from .. import debuglog as dbg
    from .. import store

    def upd(track: dict, extra: dict | None) -> bool:
        tags = track.get("tags") or {}
        if only_tag and only_tag not in {normalize(t) for t in tags}:
            return False
        return reapply(track, extra)

    changed = total = 0
    for r in store.all_recognitions():
        total += 1
        if upd(r["track"], r["extra"]):
            store.update_recognition(r["id"], r["track"], r["extra"])
            changed += 1
    for e in store.all_entries():
        if upd(e["track"], None):
            store.update_entry(e["id"], e["track"])
    dbg.event("genre-lernen", "Neu bestimmt", tag=only_tag, geändert=changed, gesamt=total)
    return {"changed": changed, "total": total}


def reapply(track: dict, extra: dict | None) -> bool:
    """Genre eines gespeicherten Songs aus seinen Tags neu berechnen (offline). True = geändert."""
    from .classify import classify

    # mit demselben Song-Genre der Dienste wie bei der Online-Bestimmung – sonst kippt das Ergebnis offline
    c = classify(track.get("tags") or {}, (extra or {}).get("genre_hint"))
    if not c.genre and not c.niche:
        return False
    if c.confidence <= 0.2 and extra is not None and extra.get("genre_source") in ("bpm", "llm_genre"):
        return False   # nur grobe Tags -> bessere Schätzung (Tempo/LLM) nicht überschreiben
    old = (track.get("genre"), track.get("subgenre"), track.get("niche"))
    sub = c.subgenre
    if not sub and extra is not None and extra.get("genre_source") == "llm" and old[0] == c.genre:
        sub = old[1]   # vom LLM bestimmtes Subgenre behalten
    new = (c.genre or old[0], sub, c.niche)
    if new == old:
        return False
    if new[2] and normalize(new[2]) in {normalize(a) for a in track.get("artists") or []}:
        new = (new[0], new[1], None)            # Künstlername als Tag ist kein Genre
    track["genre"], track["subgenre"], track["niche"] = new
    if extra is not None and c.genre:
        extra["confidence"] = c.confidence
        if extra.get("genre_source") in ("bpm", "llm_genre", None):
            extra["genre_source"] = "tags"
    return True
