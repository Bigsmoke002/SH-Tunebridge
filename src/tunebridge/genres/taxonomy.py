"""Genre-Baum: Hauptgenre -> Subgenres -> Tag-Synonyme.

Die Synonyme sind das, was in Tags von Last.fm / Discogs / MusicBrainz /
SoundCloud / Beatport typischerweise auftaucht. Gern erweitern!
Hauptgenre-Tags stehen unter dem Schlüssel "_".
"""

TAXONOMY: dict[str, dict[str, list[str]]] = {
    "Drum & Bass": {
        "_": ["drum and bass", "drum n bass", "drum & bass", "drum'n'bass", "dnb", "d&b", "d n b"],
        "Liquid": ["liquid", "liquid funk", "liquid dnb", "liquid drum and bass", "soulful dnb"],
        "Neurofunk": ["neurofunk", "neuro", "neuro dnb"],
        "Jump Up": ["jump up", "jump-up", "jumpup"],
        "Jungle": ["jungle", "ragga jungle", "oldschool jungle", "junglist"],
        "Rollers / Minimal": ["rollers", "minimal dnb", "minimal drum and bass", "deep dnb", "deep drum and bass"],
        "Dancefloor": ["dancefloor dnb", "dancefloor drum and bass", "mainstream dnb", "uk dnb"],
        "Darkstep / Techstep": ["darkstep", "techstep", "dark dnb", "crossbreed"],
        "Halftime": ["halftime", "half time", "halftime dnb"],
        "Atmospheric": ["atmospheric dnb", "atmospheric drum and bass", "intelligent dnb", "intelligent drum and bass", "drumfunk"],
        "Drumstep": ["drumstep"],
    },
    "Breakcore": {
        "_": ["breakcore", "amen breakcore", "amen break", "breakcore jungle"],
        "Atmospheric Breakcore": ["chill breakcore", "atmospheric breakcore", "ambient breakcore", "dreamy breakcore", "emo breakcore",
                                  "sad breakcore", "melodic breakcore"],
        "Mashcore / Dariacore": ["mashcore", "dariacore"],
        "Drill 'n' Bass": ["drill and bass", "drill n bass", "drill 'n' bass", "drillnbass"],
        "Digital Hardcore": ["digital hardcore", "raggacore"],
    },
    "Dubstep": {
        "_": ["dubstep"],
        "Riddim": ["riddim", "riddim dubstep", "briddim", "future riddim"],
        "Brostep / Tearout": ["brostep", "tearout", "tear out", "heavy dubstep", "deathstep", "colour bass", "color bass"],
        "Melodic Dubstep": ["melodic dubstep", "melodic bass", "chillstep", "emotional dubstep"],
        "Deep / UK Dubstep": ["deep dubstep", "uk dubstep", "140", "dungeon", "dub", "post-dubstep"],
    },
    "House": {
        "_": ["house"],
        "Deep House": ["deep house"],
        "Tech House": ["tech house"],
        "Bass House": ["bass house", "g-house", "g house"],
        "Progressive House": ["progressive house"],
        "Future House": ["future house"],
        "Afro / Organic House": ["afro house", "organic house"],
        "Melodic House": ["melodic house", "melodic house and techno"],
        "Nu-Disco": ["nu disco", "nu-disco", "disco", "french house"],
        "Slap House": ["slap house", "brazilian bass"],
        "Hard House": ["hard house", "uk hard house", "hard nrg"],
        "Jackin House": ["jackin house", "jackin"],
    },
    "Techno": {
        "_": ["techno"],
        "Melodic Techno": ["melodic techno"],
        "Hard Techno": ["hard techno", "industrial techno", "schranz"],
        "Minimal Techno": ["minimal techno", "minimal"],
        "Peak Time": ["peak time techno", "driving techno"],
        "Hardgroove": ["hardgroove", "hard groove"],
        "Acid Techno": ["acid techno"],
        "Dub Techno": ["dub techno"],
        # deutsche Szene: harte Kick, 150–170 BPM, oft Remixe/Bootlegs bekannter Songs („… (Hardtekk Remix)“)
        "Hardtekk": ["hardtekk", "hard tekk", "tekk", "tekkno", "hard tekkno", "hardtekk remix", "tekk remix"],
    },
    "UK Garage / Bass": {
        "_": ["uk garage", "ukg", "garage", "uk bass", "bassline"],
        "2-Step": ["2-step", "2 step", "two step"],
        "Speed Garage": ["speed garage"],
        "Grime": ["grime"],
        "Hard Drum": ["hard drum"],
        "Bassline": ["uk bassline", "bassline house"],
    },
    "Trance": {
        "_": ["trance"],
        "Uplifting": ["uplifting trance"],
        "Psytrance": ["psytrance", "psychedelic trance", "goa trance", "goa"],
        "Progressive Trance": ["progressive trance"],
        "Hard Trance": ["hard trance", "tech trance"],
    },
    "Hardstyle / Hardcore": {
        "_": ["hardstyle", "hardcore", "hard dance"],
        "Rawstyle": ["rawstyle", "raw hardstyle"],
        "Euphoric": ["euphoric hardstyle"],
        "Frenchcore": ["frenchcore"],
        "Uptempo": ["uptempo", "uptempo hardcore", "terrorcore"],
        "Happy Hardcore": ["happy hardcore", "uk hardcore"],
        "Speedcore / Gabber": ["speedcore", "extratone", "gabber", "gabba"],
    },
    "Trap / Future Bass": {
        "_": ["trap", "edm trap", "future bass"],
        "Hybrid Trap": ["hybrid trap"],
        "Wave": ["wave", "hardwave"],
    },
    "Phonk": {
        "_": ["phonk"],
        "Drift Phonk": ["drift phonk", "drift"],
        "Brazilian Phonk": ["brazilian phonk", "phonk brasileiro", "funk phonk", "br funk", "brazil phonk", "phonk br", "brazilian funk", "funk mandelao",
                            "funk automotivo", "automotivo"],
        "Phonk House": ["phonk house"],
        "Memphis / Rap Phonk": ["memphis phonk", "memphis rap", "rap phonk", "memphis"],
    },
    "Breakbeat": {"_": ["breakbeat", "breaks", "big beat"]},
    "IDM / Experimental": {"_": ["idm", "intelligent dance music", "experimental electronic", "glitch", "experimental"]},
    "Synthwave": {
        "_": ["synthwave", "retrowave", "outrun"],
        "Darksynth": ["darksynth", "dark synthwave"],
        "Chillwave / Vaporwave": ["chillwave", "vaporwave"],
    },
    "Hyperpop": {
        "_": ["hyperpop", "pc music", "bubblegum bass"],
        "Digicore": ["digicore"],
        "Glitchcore": ["glitchcore"],
        "Hexd": ["hexd", "hex d"],
    },
    "Hip-Hop": {
        "_": ["hip-hop", "hip hop", "rap"],
        "Deutschrap": ["deutschrap", "german rap", "german hip hop"],
        "Cloud Rap": ["cloud rap"],
        "Drill": ["drill", "uk drill", "ny drill"],
        "Boom Bap": ["boom bap", "old school hip hop"],
        "Emo Rap": ["emo rap", "sad rap"],
        "Rage": ["rage", "rage rap", "rage beat"],
        "Plugg / Pluggnb": ["plugg", "pluggnb", "plugg n b", "plugg rnb"],
        "Jerk": ["jerk", "jerk rap"],
        "Sigilkore": ["sigilkore"],
        "Trap Rap": ["trap rap", "atlanta trap"],
    },
    "R&B / Soul": {"_": ["rnb", "r&b", "rhythm and blues", "soul", "neo-soul", "contemporary r&b"]},
    "Pop": {
        "_": ["pop", "dance pop", "electropop"],
        "K-Pop": ["k-pop", "kpop"],
        "J-Pop / Anime": ["j-pop", "jpop", "anime", "city pop", "vocaloid"],
        "Synthpop": ["synthpop", "synth-pop"],
    },
    "Indie / Alternative": {
        "_": ["indie", "indie pop", "indie rock", "alternative", "alternative rock", "bedroom pop"],
        "Shoegaze / Dream Pop": ["shoegaze", "dream pop", "dreampop"],
    },
    "Rock / Metal": {
        "_": ["rock", "hard rock", "classic rock", "grunge", "industrial rock", "psychedelic rock", "garage rock"],
        "Metal": ["metal", "heavy metal", "metalcore", "deathcore", "nu metal", "death metal", "black metal",
                  "industrial metal", "neue deutsche harte", "neue deutsche härte", "thrash metal", "groove metal",
                  "alternative metal", "power metal", "symphonic metal", "doom metal", "progressive metal"],
        "Punk": ["punk", "pop punk", "punk rock", "post-punk"],
    },
    "Latin": {
        "_": ["latin", "latin pop", "bachata", "salsa", "cumbia"],
        "Reggaeton": ["reggaeton", "dembow", "latin trap"],
    },
    "Reggae / Dancehall": {"_": ["reggae", "dancehall", "roots reggae", "ska"]},
    "Jazz / Funk": {"_": ["jazz", "funk", "nu jazz", "acid jazz", "jazz fusion", "jazzhop", "jazz hop"]},
    "Country / Folk": {"_": ["country", "folk", "singer-songwriter", "acoustic", "americana"]},
    "Classical / Cinematic": {
        "_": ["classical", "classical crossover", "orchestral"],
        "Neoclassical / Piano": ["neoclassical", "neo-classical", "modern classical", "contemporary classical", "piano"],
        "Cinematic / Epic": ["cinematic", "epic", "epic music", "trailer music", "epic orchestral"],
        "Soundtrack": ["soundtrack", "score", "film score", "ost", "video game music", "game soundtrack"],
    },
    "Ambient / Chill": {
        "_": ["ambient", "chill"],
        "Dreamscape": ["dreamscape", "dreamscape records", "dreamy"],
        "Lo-Fi": ["lo-fi", "lofi", "lo-fi hip hop", "lofi hip hop", "chillhop", "lofi beats"],
        "Downtempo / Chillout": ["chillout", "downtempo", "chill out", "trip-hop", "trip hop"],
        "Dark Ambient / Drone": ["dark ambient", "drone"],
    },
}

# Nischen-Genres, die fast immer zusammen mit einem breiten „Eltern“-Genre getaggt werden
# (Breakcore mit Drum & Bass/Jungle, Phonk mit Hip-Hop/Trap …). Ohne Bonus gewinnt sonst
# das breite Genre, obwohl das Nischen-Tag die eigentliche Aussage ist.
PRIORITY: dict[str, float] = {
    "Breakcore": 1.8, "Phonk": 1.5, "Hyperpop": 1.4, "Synthwave": 1.2, "IDM / Experimental": 0.8,
}

# Tags, die eher Stimmung als Genre beschreiben – zählen nur abgeschwächt
# („chill“ bei Kavinsky – Nightcall ist kein Ambient)
WEAK_TAGS: dict[str, float] = {"chill": 0.35, "dreamy": 0.5, "atmospheric": 0.5}

# „trap“ ist doppeldeutig: mit Rap-Tags ist es Rap-Trap (Hip-Hop), sonst EDM-Trap
HIPHOP_SIGNALS = {"rap", "hip hop", "hip-hop", "hiphop", "hip-hop/rap", "hip hop/rap", "rap/hip hop", "pop rap",
                  "trap rap", "southern hip hop", "gangsta rap", "cloud rap"}

# Familien: Das grobe Genre des Erkennungsdienstes (Shazam/Apple: „Electronic“, „Hip-Hop/Rap“ …) gehört
# zum Song selbst. Gewinnt ein Genre außerhalb dieser Familie nur knapp, nimmt die App das passende.
_ELECTRONIC_FAMILY = {"Drum & Bass", "Breakcore", "Dubstep", "House", "Techno", "UK Garage / Bass", "Trance",
                      "Hardstyle / Hardcore", "Trap / Future Bass", "Phonk", "Breakbeat", "IDM / Experimental",
                      "Synthwave", "Hyperpop", "Ambient / Chill", "Electronic"}
FAMILIES: dict[str, set[str]] = {
    **{g: _ELECTRONIC_FAMILY for g in _ELECTRONIC_FAMILY},
    "Hip-Hop": {"Hip-Hop", "Phonk", "R&B / Soul", "Trap / Future Bass"},
    "R&B / Soul": {"R&B / Soul", "Hip-Hop", "Pop", "Jazz / Funk"},
    "Pop": {"Pop", "Hyperpop", "Indie / Alternative", "R&B / Soul", "Synthwave"},
    "Indie / Alternative": {"Indie / Alternative", "Rock / Metal", "Pop"},
    "Rock / Metal": {"Rock / Metal", "Indie / Alternative"},
}

# Notnagel: so allgemein, dass sie nur zählen, wenn sonst gar nichts passt
FALLBACK: dict[str, str] = {
    "electronic": "Electronic", "electronica": "Electronic", "edm": "Electronic", "dance": "Electronic",
    "electro": "Electronic", "bass music": "Electronic",
}

# Tags, die nichts übers Genre sagen
IGNORED_TAGS = {
    "seen live", "favorites", "favourite", "love", "awesome", "electronic", "electronica",
    "edm", "dance", "bass", "bass music", "beautiful", "male vocalists", "female vocalists",
    "slowed", "slowed and reverb", "slowed reverb", "reverb", "sped up", "nightcore", "daycore", "remix",
    "instrumental", "russian", "russia", "usa", "uk", "german", "japanese", "electro",
}
