"""Mikro-Genre-Prüfstand, Stufe 2 (nur Test, nicht Teil der App): Stil-Erkennung am Klang.
Discogs-EffNet (Essentia, MTG-UPF; Modelle CC BY-NC-SA 4.0) auf der öffentlichen 30-s-Deezer-Hörprobe.
Die Hörprobe liegt nur Sekunden in einem Temp-Ordner und wird sofort gelöscht.
Aufruf: <essentia-venv>/bin/python micro_audio.py <modelle-ordner> out.json"""
import json
import os
import sys
import tempfile
import time
import urllib.parse
import urllib.request

import numpy as np
from essentia.standard import MonoLoader, TensorflowPredict2D, TensorflowPredictEffnetDiscogs

sys.path.insert(0, os.path.dirname(__file__))
from micro import MICRO  # noqa: E402

M = sys.argv[1]
emb_model = TensorflowPredictEffnetDiscogs(graphFilename=f"{M}/discogs-effnet-bs64-1.pb", output="PartitionedCall:1")
head = TensorflowPredict2D(graphFilename=f"{M}/genre_discogs400-discogs-effnet-1.pb",
                           input="serving_default_model_Placeholder", output="PartitionedCall:0")
CLASSES = json.load(open(f"{M}/genre_discogs400-discogs-effnet-1.json"))["classes"]


def preview(artist, title):
    a = artist.lower()
    for query in (f'artist:"{artist}" track:"{title}"', f"{artist} {title}"):
        q = urllib.parse.urlencode({"q": query, "limit": 8})
        data = json.load(urllib.request.urlopen(f"https://api.deezer.com/search?{q}", timeout=15)).get("data") or []
        for h in data:
            n = h["artist"]["name"].lower()
            if (a in n or n in a) and h.get("preview"):
                return h["preview"]
    return None


rows = []
for main, sub, songs in MICRO:
    for artist, title in songs:
        row = dict(main=main, sub=sub, artist=artist, title=title, styles=[])
        try:
            url = preview(artist, title)
            if url:
                with tempfile.TemporaryDirectory() as td:
                    p = os.path.join(td, "p.mp3")
                    urllib.request.urlretrieve(url, p)
                    audio = MonoLoader(filename=p, sampleRate=16000, resampleQuality=4)()
                emb = emb_model(audio)
                act = np.mean(head(emb), axis=0)
                top = np.argsort(act)[::-1][:8]
                row["styles"] = [(CLASSES[i], round(float(act[i]), 3)) for i in top]
        except Exception as e:  # noqa: BLE001
            row["error"] = str(e)
        rows.append(row)
        print(sub, "|", artist, "–", title, "|", [s for s, _ in row["styles"][:3]], row.get("error", ""), flush=True)
        json.dump(rows, open(sys.argv[2], "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        time.sleep(0.3)
