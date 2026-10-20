"""Second pass over canvasSourceFiles/*/names.json: swap overly technical or overly specific names for simple ones.
The replaced name is kept in "aka" so it stays searchable. Safe to run repeatedly.

    python3 simplify_names.py
"""
import json, os

RENAMES = {
    "Microscopic": {
        "Coccus": "Round Bacterium", "Diplococcus": "Paired Bacterium", "Staphylococcus": "Cluster Bacterium",
        "Streptococcus": "Chain Bacterium", "Vibrio": "Comma Bacterium", "Spirochete": "Corkscrew Bacterium",
        "Spirillum": "Twisted Bacterium", "Helicobacter": "Tailed Bacterium", "Bacillus": "Capsule Bacterium",
        "Chlamydomonas": "Green Algae Cell", "Heliozoan": "Spiky Protist", "Foraminifera": "Shell Amoeba",
        "Radiolarian": "Glass Skeleton Plankton", "Spirulina": "Spiral Algae", "Euglena": "Green Swimmer",
        "Bacteriophage": "Phage Virus",
    },
    "Underwater": {
        "Achilles Tang": "Tang Fish", "Powder Blue Tang": "Tang Fish", "Yellowtail Tang": "Tang Fish",
        "Black Angelfish": "Angelfish", "Emperor Angelfish": "Angelfish", "Flame Angelfish": "Angelfish",
        "French Angelfish": "Angelfish", "Queen Angelfish": "Angelfish", "Striped Angelfish": "Angelfish",
        "Copperband Butterflyfish": "Butterflyfish", "Longnose Butterflyfish": "Butterflyfish",
        "Clown Triggerfish": "Triggerfish", "Rock Beauty": "Reef Fish", "Blue Chromis": "Reef Fish",
        "Black Moor": "Goldfish", "Blackfish": "Dark Fish", "Brine Shrimp": "Tiny Shrimp",
        "Murex Shell": "Spiky Shell", "Moon Shell": "Round Snail Shell", "Curly Pondweed": "Pondweed",
    },
    "Space": {
        "Mir Station": "Space Station", "Pioneer Probe": "Space Probe", "Voyager Probe": "Space Probe",
    },
    "Human": {
        "Washing Hands": "Hands", "Kufi Cap": "Skullcap", "Cash Stack": "Stack of Cash",
        "Toy Light Sword": "Toy Sword",
    },
    "Plants": {
        "Fly Agaric": "Toadstool", "Porcini": "Porcini Mushroom", "Dracaena": "Dragon Plant",
    },
    "Vehicles": {
        "Crawler Transporter": "Rocket Crawler",
    },
}

ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "canvasSourceFiles")
for cat, renames in RENAMES.items():
    path = os.path.join(ROOT, cat, "names.json")
    if not os.path.exists(path):
        continue
    names = json.load(open(path))
    changed = 0
    for entry in names.values():
        new = renames.get(entry["name"])
        if new:
            entry.setdefault("aka", entry["name"])
            entry["name"] = new
            changed += 1
    json.dump(names, open(path, "w"), indent=1)
    print(f"{cat}: {changed} renamed")
