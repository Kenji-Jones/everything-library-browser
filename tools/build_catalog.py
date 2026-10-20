"""Merge data/parts/*.json (written by export_library.py) into the site's catalog.

    python3 build_catalog.py <out_dir>

Writes data/catalog.json and data/catalog.js (the .js copy lets index.html work when opened straight from disk).
"""
import json, os, re, sys, glob, shutil

OUT = os.path.abspath(sys.argv[1])
HERE = os.path.dirname(os.path.abspath(__file__))
LIBRARY = os.path.dirname(HERE)

CATEGORY_ORDER = ["Animals", "Buildings", "Consumables", "Furnishings", "Geology",
                  "Human", "Microscopic", "Plants", "Space", "Trees", "Underwater", "Vehicles", "Zeometry"]
CATEGORY_LABELS = {"Human": "Human-Made"}  # the source's "Human" category is objects people make, not people
SUBCATEGORY_NAMES = {
    "MeatsDairy": "Meats & Dairy",
    "BirdsUpright": "Birds (Standing)",
    "Birds": "Birds (Flying)",
    "Animals": "Mammals",
    "Sugar": "Sweets",
}
# Source names with typos; the original name stays searchable.
NAME_FIXES = {"Bleecher": "Bleacher", "Plateu": "Plateau", "Obsydian": "Obsidian", "WagonWheel_Wheel": "WagonWheel",
              "TableNLamp": "TableAndLamp"}
# Extra search words so common queries find things whose names don't contain them.
SUBCATEGORY_KEYWORDS = {
    "Animals": "mammal creature",
    "Amphibians": "frog toad",
    "Arachnids": "spider bug",
    "Insects": "bug",
    "FlyingInsects": "bug flying",
    "Birds": "bird flying",
    "BirdsUpright": "bird",
    "Imaginary": "fantasy mythical",
    "Reptiles": "lizard snake",
    "Business": "shop store commercial city",
    "Residential": "house home city",
    "Industrial": "factory city",
    "Historical": "ancient old",
    "Ruins": "ancient old",
    "Farm": "rural countryside",
    "Tents": "camping shelter",
    "LightSources": "light lamp",
    "Indoor": "interior home household",
    "Outdoor": "street city exterior",
    "Trash": "garbage litter rubbish",
    "Signs": "sign street",
    "Barriers": "fence wall",
    "Chairs": "seat seating",
    "Tables": "furniture",
    "Fruits": "fruit food",
    "Vegetables": "vegetable veg food",
    "Drinks": "drink beverage",
    "JunkFood": "fast food snack",
    "BakedGoods": "bakery bread food",
    "CannedFood": "can tin food",
    "MeatsDairy": "meat dairy food",
    "Sugar": "candy sweet dessert",
    "Crystals": "gem crystal mineral",
    "Pebbles": "stone rock",
    "Rocks": "stone boulder",
    "Landforms": "terrain landscape",
    "CarvedStone": "monument stone",
}
CATEGORY_KEYWORDS = {
    "Consumables": "food", "Furnishings": "furniture props", "Geology": "nature",
    "Human": "human made object item thing", "Microscopic": "micro tiny biology science", "Plants": "plant nature garden flora",
    "Space": "astronomy cosmos universe", "Trees": "tree forest nature wood", "Underwater": "ocean sea marine water",
    "Vehicles": "vehicle transport transportation", "Zeometry": "geometry abstract shape",
}


def words(name):
    name = name.replace("_", " ").replace(".", " ")
    name = re.sub(r"(?<=[a-z])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])|(?<=[A-Za-z])(?=\d)", " ", name)
    small = {"of", "the", "and", "a", "an", "in", "on", "with"}
    out = [w if w.isupper() and len(w) > 1 else w.lower() if i and w.lower() in small else w[:1].upper() + w[1:]
           for i, w in enumerate(name.split())]
    return " ".join(out).replace(" and ", " & ")


def size_class(m):
    if m < 0.1: return "Tiny"
    if m < 1: return "Small"
    if m < 4: return "Medium"
    if m < 20: return "Large"
    return "Huge"


shutil.copy(os.path.join(LIBRARY, "itchSourceFiles", "EverythingLibrary_Buildings_001", "LICENSE.txt"),
            os.path.join(OUT, "LICENSE.txt"))

items = []
for part in glob.glob(os.path.join(OUT, "data", "parts", "*.json")):
    items += json.load(open(part))

for it in items:
    src = it["name"]
    it["sourceName"] = src
    fixed = src
    for bad, good in NAME_FIXES.items():
        fixed = fixed.replace(bad, good)
    it["name"] = words(fixed)
    sub = it["subcategory"]
    it["subcategoryLabel"] = SUBCATEGORY_NAMES.get(sub, words(sub))
    it["tags"] = [words(t) for t in it.get("tags", [])]
    known = [v for v in it["variants"] if v.get("size") != "unknown"]
    size = max(max(v["dims"]) / v.get("magnified", 1) for v in known) if known else None
    it["size"] = float(f"{size:.4g}") if size is not None else None
    it["sizeClass"] = size_class(size) if size is not None else "Unknown"
    for v in it["variants"]:
        for k in ("glb", "fbx"):
            p = os.path.join(OUT, v[k])
            v[k + "Bytes"] = os.path.getsize(p) if os.path.exists(p) else 0
    bp = os.path.join(OUT, it["blend"])
    it["blendBytes"] = os.path.getsize(bp) if os.path.exists(bp) else 0
    kw = {src.lower(), it["name"].lower(), it["category"].lower(), it["subcategoryLabel"].lower(), sub.lower(),
          SUBCATEGORY_KEYWORDS.get(sub, ""), CATEGORY_KEYWORDS.get(it["category"], ""),
          it["sizeClass"].lower(), " ".join(t.lower() for t in it["tags"])}
    it["keywords"] = " ".join(sorted(w for w in set(" ".join(kw).split()) if w))

items.sort(key=lambda i: (CATEGORY_ORDER.index(i["category"]), i["subcategoryLabel"], i["name"]))

categories = []
for cat in CATEGORY_ORDER:
    cat_items = [i for i in items if i["category"] == cat]
    if not cat_items:
        continue
    subs = {}
    for i in cat_items:
        subs.setdefault(i["subcategory"], {"id": i["subcategory"], "label": i["subcategoryLabel"], "count": 0})
        subs[i["subcategory"]]["count"] += 1
    categories.append({"id": cat, "label": CATEGORY_LABELS.get(cat, cat), "count": len(cat_items),
                       "variants": sum(len(i["variants"]) for i in cat_items),
                       "subcategories": sorted(subs.values(), key=lambda s: s["label"])})

catalog = {
    "title": "Everything Library",
    "author": "David OReilly",
    "license": "CC BY 4.0",
    "sourceUrl": "http://davidoreilly.com/library",
    "itemCount": len(items),
    "variantCount": sum(len(i["variants"]) for i in items),
    "categories": categories,
    "items": items,
}
with open(os.path.join(OUT, "data", "catalog.json"), "w") as f:
    json.dump(catalog, f, separators=(",", ":"))
with open(os.path.join(OUT, "data", "catalog.js"), "w") as f:
    f.write("window.CATALOG = ")
    json.dump(catalog, f, separators=(",", ":"))
    f.write(";\n")
print(f"{len(items)} items, {catalog['variantCount']} variants, {len(categories)} categories")
