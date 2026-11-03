P, W, A = "Phonk", "Trap / Future Bass", "Ambient / Chill"
DNB, BC, DS, HO, TE = "Drum & Bass", "Breakcore", "Dubstep", "House", "Techno"
UKG, TR, HS, BB, IDM = "UK Garage / Bass", "Trance", "Hardstyle / Hardcore", "Breakbeat", "IDM / Experimental"
SW, HP, HH, RB, POP = "Synthwave", "Hyperpop", "Hip-Hop", "R&B / Soul", "Pop"
IND, RM, LAT, REG, JZ = "Indie / Alternative", "Rock / Metal", "Latin", "Reggae / Dancehall", "Jazz / Funk"
CF, CL = "Country / Folk", "Classical / Cinematic"
NONE = {None}
# (Künstler, Titel, erlaubte Hauptgenres, erwartetes Subgenre oder None)
SONGS = [
 # Phonk (+ Drift / Brazilian / Memphis)
 ("Kordhell", "Murder In My Mind", {P}, None), ("DVRST", "Close Eyes", {P}, None), ("INTERWORLD", "METAMORPHOSIS", {P}, None),
 ("PlayaPhonk", "PHONKY TOWN", {P}, None), ("MoonDeity", "NEON BLADE", {P}, None), ("Kaito Shoma", "Scary Garry", {P}, None),
 ("Ghostface Playa", "Why Not", {P}, None), ("Hensonn", "Sahara", {P}, None), ("KSLV Noh", "Override", {P}, None),
 ("LXNGVX", "Montagem Mysterious Game", {P}, "Brazilian Phonk"), ("Eternxlkz", "SLAY!", {P}, "Brazilian Phonk"),
 ("NCTS", "NEXT!", {P}, "Brazilian Phonk"), ("Freddie Dredd", "Limbo", {P, HH}, None),
 ("Vøj", "Memory Reboot", {P, W, SW}, None), ("Narvent", "Fainted", {P, W, SW}, None),
 # Wave
 ("Skeler", "Starry Eyed", {W, P}, None), ("Kareful", "Ghost", {W, P}, None),
 # Drum & Bass
 ("Sub Focus", "Solar System", {DNB}, None), ("Netsky", "Memory Lane", {DNB}, "Liquid"), ("Pendulum", "Watercolour", {DNB}, None),
 ("Noisia", "Stigmata", {DNB}, None), ("Wilkinson", "Afterglow", {DNB}, None),
 # Breakcore
 ("Sewerslvt", "Ecifircas", {BC}, None), ("Sewerslvt", "Purity", {BC}, None), ("Venetian Snares", "Szamar Madar", {BC, IDM}, None),
 ("usedcvnt", "Just Leave Me To Bleed", {BC}, None), ("Heavenly Snow", "I hope this song will find you", {BC}, None),
 # Dubstep
 ("Skrillex", "Scary Monsters and Nice Sprites", {DS}, None), ("Excision", "X Rated", {DS}, None),
 ("Rusko", "Cockney Thug", {DS}, None), ("Flux Pavilion", "Bass Cannon", {DS}, None),
 # House
 ("Daft Punk", "One More Time", {HO}, None), ("Avicii", "Levels", {HO}, None), ("Purple Disco Machine", "Hypnotized", {HO}, None),
 ("Lane 8", "Fingerprint", {HO}, None), ("Fred again..", "Delilah (pull me out of this)", {HO, UKG}, None),
 # Techno
 ("Amelie Lens", "Hypnotized", {TE}, None), ("Charlotte de Witte", "Selected", {TE}, None), ("Boris Brejcha", "Gravity", {TE}, None),
 ("Adam Beyer", "Your Mind", {TE}, None),
 # UK Garage / Bass
 ("Artful Dodger", "Re-Rewind", {UKG}, None), ("MJ Cole", "Sincere", {UKG}, None), ("Sammy Virji", "If U Need It", {UKG, HO}, None),
 ("Burial", "Archangel", {UKG, DS}, None), ("Disclosure", "Latch", {HO, UKG}, None),
 # Trance
 ("ATB", "9 PM (Till I Come)", {TR}, None), ("Tiësto", "Adagio for Strings", {TR}, None), ("Paul van Dyk", "For An Angel", {TR}, None),
 ("Infected Mushroom", "Becoming Insane", {TR}, "Psytrance"),
 # Hardstyle / Hardcore
 ("Headhunterz", "Dragonborn", {HS}, None), ("Angerfist", "Pennywise", {HS}, None), ("Da Tweekaz", "Jägermeister", {HS}, None),
 # Trap / Future Bass
 ("San Holo", "Light", {W}, None), ("Baauer", "Harlem Shake", {W}, None), ("RL Grime", "Core", {W}, None),
 ("Flume", "Never Be Like You", {W, POP}, None),
 # Breakbeat
 ("The Prodigy", "Firestarter", {BB, TE}, None), ("The Chemical Brothers", "Block Rockin' Beats", {BB}, None),
 ("Fatboy Slim", "Right Here, Right Now", {BB}, None),
 # IDM / Experimental
 ("Aphex Twin", "Windowlicker", {IDM}, None), ("Boards of Canada", "Roygbiv", {IDM, A}, None), ("Autechre", "Gantz Graf", {IDM}, None),
 ("Squarepusher", "My Red Hot Car", {IDM}, None),
 # Synthwave
 ("The Midnight", "Sunset", {SW}, None), ("Kavinsky", "Nightcall", {SW}, None), ("Perturbator", "Future Club", {SW}, None),
 ("Carpenter Brut", "Turbo Killer", {SW}, None), ("FM-84", "Running in the Night", {SW}, None),
 # Hyperpop
 ("100 gecs", "money machine", {HP}, None), ("SOPHIE", "Immaterial", {HP}, None), ("Dorian Electra", "Flamboyant", {HP, POP}, None),
 ("Odetari", "GMFU", {HP, P, HH}, None),
 # Hip-Hop
 ("Kendrick Lamar", "HUMBLE.", {HH}, None), ("Travis Scott", "SICKO MODE", {HH}, None), ("Juice WRLD", "Lucid Dreams", {HH}, None),
 ("Future", "Mask Off", {HH}, None), ("Capital Bra", "Cherry Lady", {HH}, "Deutschrap"), ("Central Cee", "Doja", {HH}, None),
 ("Playboi Carti", "Sky", {HH}, None),
 # R&B / Soul
 ("Frank Ocean", "Thinkin Bout You", {RB}, None), ("SZA", "Kill Bill", {RB, POP}, None), ("Daniel Caesar", "Get You", {RB}, None),
 ("Amy Winehouse", "Rehab", {RB, JZ}, None),
 # Pop
 ("Dua Lipa", "Levitating", {POP}, None), ("Billie Eilish", "bad guy", {POP}, None), ("Taylor Swift", "Anti-Hero", {POP}, None),
 ("Harry Styles", "As It Was", {POP}, None), ("The Weeknd", "Blinding Lights", {POP, RB, SW}, None),
 # Indie / Alternative
 ("Arctic Monkeys", "Do I Wanna Know?", {IND, RM}, None), ("Tame Impala", "The Less I Know The Better", {IND, POP}, None),
 ("The Strokes", "Last Nite", {IND, RM}, None), ("Phoebe Bridgers", "Motion Sickness", {IND}, None),
 # Rock / Metal
 ("Linkin Park", "Numb", {RM}, None), ("Metallica", "Enter Sandman", {RM}, None), ("Nirvana", "Smells Like Teen Spirit", {RM, IND}, None),
 ("Rammstein", "Du Hast", {RM}, None), ("Slipknot", "Duality", {RM}, None),
 # Latin
 ("Bad Bunny", "Tití Me Preguntó", {LAT}, None), ("Daddy Yankee", "Gasolina", {LAT}, None), ("ROSALÍA", "DESPECHÁ", {LAT}, None),
 ("KAROL G", "PROVENZA", {LAT}, None),
 # Reggae / Dancehall
 ("Bob Marley & The Wailers", "Is This Love", {REG}, None), ("Sean Paul", "Get Busy", {REG}, None),
 ("Damian Marley", "Welcome To Jamrock", {REG}, None), ("Gentleman", "Dem Gone", {REG}, None),
 # Jazz / Funk
 ("Miles Davis", "So What", {JZ}, None), ("The Dave Brubeck Quartet", "Take Five", {JZ}, None),
 ("James Brown", "Get Up (I Feel Like Being A) Sex Machine", {JZ, RB}, None), ("Herbie Hancock", "Chameleon", {JZ}, None),
 # Country / Folk
 ("Johnny Cash", "Hurt", {CF, RM}, None), ("Dolly Parton", "Jolene", {CF}, None), ("Luke Combs", "Fast Car", {CF}, None),
 ("Mumford & Sons", "Little Lion Man", {CF, IND}, None),
 # Classical / Cinematic
 ("Hans Zimmer", "Time", {CL}, None), ("Ludovico Einaudi", "Experience", {CL}, None),
 ("Max Richter", "On the Nature of Daylight", {CL, A}, None), ("Ludwig van Beethoven", "Für Elise", {CL}, None),
 # Ambient / Chill (+ Lo-Fi / Downtempo)
 ("Brian Eno", "An Ending (Ascent)", {A}, None), ("Tycho", "Awake", {A, SW, IDM}, None), ("Bonobo", "Kiara", {A, IDM}, None),
 ("Massive Attack", "Teardrop", {A}, None), ("Nujabes", "Aruarian Dance", {A, HH, JZ}, None),
 ("Øneheart", "Snowfall", {A, W, P}, None), ("METAHESH", "Life's Too Short", {A, W, P}, None),
 ("Ybyrayy", "hateful", {A, W, P}, None), ("Øneheart", "Anguish", {A, W, P}, None), ("Antent", "In My Dreams", {A, W, P}, None),
 # Schwer/obskur – lieber kein Genre als ein falsches
 ("Sadfriend", "Fear", {P, W, HH}, None), ("Gothboy", "Proxima", {W, P, SW, "Electronic"}, None),
 ("trapeia", "forget the past", NONE | {P, W, A}, None),
 # Gibt es nicht – darf kein (erfundenes) Genre bekommen
 ("Xqzvbl Kurnatt", "Glorpwave Ninety Nine", NONE, None), ("Mirelle Faunbrook", "Sixteen Copper Lanterns", NONE, None),
 ("DJ Plonkerstein", "Untitled Loop 4417", NONE, None),
]
